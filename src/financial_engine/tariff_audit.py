"""Utility Tariff Benchmarking & Invoicing Audit Module (Milestone 5.5.4).

Benchmarks modeled EEM grid fees and statutory taxes in SwedishTariff against
actual utility invoices in `data/eem-yearly-costs-2024-2026.csv` and official
meter logs in `data/EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv`.

Accounts for:
1. The `Leverantörsbyte` on `2024-09-28` (transition from EEM combined retail+grid
   billing in Jan–Sep 2024 to pure EEM grid+tax billing + Tibber retail in Oct 2024+).
2. Exact daily fixed fuse fees (`Fast elnätsavgift per dag`) and statutory variable
   rates (`Överföringsavgift + Energiskatt + 25% Moms`) across 2024, 2025, and 2026.
3. Fiscal utility meter vs. Sonnen CT clamp import kWh cross-validation.
"""

import calendar
import csv
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .tariff import SwedishTariff, TariffConfig

MONTH_ABBR_TO_NUM: Dict[str, int] = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

MONTH_NUM_TO_NAME: Dict[int, str] = {
    i: calendar.month_name[i] for i in range(1, 13)
}


@dataclass
class AuditedEEMTariffSchedule:
    """Empirically audited Eskilstuna Energi & Miljö (EEM) grid tariff schedule for a year."""
    year: int
    fixed_daily_fee_sek_inc_vat: float
    fixed_annual_fee_sek_inc_vat: float
    energiskatt_sek_per_kwh_ex_vat: float
    eem_transfer_fee_sek_per_kwh_ex_vat: float
    moms_rate: float = 0.25

    @property
    def variable_grid_and_tax_sek_per_kwh_ex_vat(self) -> float:
        """Total variable EEM transfer + Energiskatt in SEK/kWh ex. VAT."""
        return self.energiskatt_sek_per_kwh_ex_vat + self.eem_transfer_fee_sek_per_kwh_ex_vat

    @property
    def variable_grid_and_tax_sek_per_kwh_inc_vat(self) -> float:
        """Total variable EEM transfer + Energiskatt in SEK/kWh incl. 25% VAT."""
        return self.variable_grid_and_tax_sek_per_kwh_ex_vat * (1.0 + self.moms_rate)

    def calculate_fixed_fee_sek(self, days_in_month: int) -> float:
        """Calculate monthly fixed EEM grid fee for a given number of calendar days."""
        return self.fixed_daily_fee_sek_inc_vat * days_in_month

    def calculate_variable_fee_sek(self, imported_kwh: float) -> float:
        """Calculate monthly variable EEM transfer + Energiskatt fee incl. VAT."""
        return imported_kwh * self.variable_grid_and_tax_sek_per_kwh_inc_vat

    def calculate_grid_invoice_sek(self, imported_kwh: float, days_in_month: int) -> float:
        """Calculate total pure EEM grid invoice in SEK incl. VAT."""
        return self.calculate_fixed_fee_sek(days_in_month) + self.calculate_variable_fee_sek(imported_kwh)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "year": self.year,
            "fixed_daily_fee_sek_inc_vat": round(self.fixed_daily_fee_sek_inc_vat, 4),
            "fixed_annual_fee_sek_inc_vat": round(self.fixed_annual_fee_sek_inc_vat, 2),
            "energiskatt_ore_per_kwh_ex_vat": round(self.energiskatt_sek_per_kwh_ex_vat * 100.0, 2),
            "energiskatt_ore_per_kwh_inc_vat": round(
                self.energiskatt_sek_per_kwh_ex_vat * (1.0 + self.moms_rate) * 100.0, 3
            ),
            "eem_transfer_ore_per_kwh_ex_vat": round(self.eem_transfer_fee_sek_per_kwh_ex_vat * 100.0, 2),
            "eem_transfer_ore_per_kwh_inc_vat": round(
                self.eem_transfer_fee_sek_per_kwh_ex_vat * (1.0 + self.moms_rate) * 100.0, 3
            ),
            "total_variable_ore_per_kwh_ex_vat": round(
                self.variable_grid_and_tax_sek_per_kwh_ex_vat * 100.0, 2
            ),
            "total_variable_ore_per_kwh_inc_vat": round(
                self.variable_grid_and_tax_sek_per_kwh_inc_vat * 100.0, 2
            ),
        }


DEFAULT_AUDITED_EEM_SCHEDULES: Dict[int, AuditedEEMTariffSchedule] = {
    2024: AuditedEEMTariffSchedule(
        year=2024,
        fixed_daily_fee_sek_inc_vat=10.9726,
        fixed_annual_fee_sek_inc_vat=4016.0,
        energiskatt_sek_per_kwh_ex_vat=0.4280,
        eem_transfer_fee_sek_per_kwh_ex_vat=0.2352,
    ),
    2025: AuditedEEMTariffSchedule(
        year=2025,
        fixed_daily_fee_sek_inc_vat=4340.0 / 365.0,
        fixed_annual_fee_sek_inc_vat=4340.0,
        energiskatt_sek_per_kwh_ex_vat=0.4390,
        eem_transfer_fee_sek_per_kwh_ex_vat=0.2351,
    ),
    2026: AuditedEEMTariffSchedule(
        year=2026,
        fixed_daily_fee_sek_inc_vat=4864.0 / 365.0,
        fixed_annual_fee_sek_inc_vat=4864.0,
        energiskatt_sek_per_kwh_ex_vat=0.3600,
        eem_transfer_fee_sek_per_kwh_ex_vat=0.23552,
    ),
}


@dataclass
class EEMBillingRecord:
    """Single monthly entry parsed from `data/eem-yearly-costs-2024-2026.csv`."""
    year: int
    month: int
    month_abbr: str
    month_name: str
    days_in_month: int
    billed_kwh: float
    billed_kr: float
    is_billed: bool
    billing_regime: str


@dataclass
class MonthlyTariffAuditRecord:
    """Detailed monthly audit comparison between EEM utility invoice, audited schedule, and SwedishTariff."""
    year: int
    month: int
    month_name: str
    days_in_month: int
    billing_regime: str
    is_billed: bool
    eem_billed_kwh: float
    sonnen_imported_kwh: float
    kwh_delta: float
    kwh_delta_pct: float
    eem_billed_kr: float
    audited_grid_fixed_kr: float
    audited_grid_variable_kr: float
    audited_grid_total_kr: float
    inferred_eem_retail_supply_kr: float
    uncalibrated_tariff_variable_kr: float
    invoice_residual_kr: float
    exact_rounded_match: Optional[bool]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "year": self.year,
            "month": self.month,
            "month_name": self.month_name,
            "days_in_month": self.days_in_month,
            "billing_regime": self.billing_regime,
            "is_billed": self.is_billed,
            "eem_billed_kwh": round(self.eem_billed_kwh, 3),
            "sonnen_imported_kwh": round(self.sonnen_imported_kwh, 3),
            "kwh_delta": round(self.kwh_delta, 3),
            "kwh_delta_pct": round(self.kwh_delta_pct, 2),
            "eem_billed_kr": round(self.eem_billed_kr, 2),
            "audited_grid_fixed_kr": round(self.audited_grid_fixed_kr, 2),
            "audited_grid_variable_kr": round(self.audited_grid_variable_kr, 2),
            "audited_grid_total_kr": round(self.audited_grid_total_kr, 2),
            "inferred_eem_retail_supply_kr": round(self.inferred_eem_retail_supply_kr, 2),
            "uncalibrated_tariff_variable_kr": round(self.uncalibrated_tariff_variable_kr, 2),
            "invoice_residual_kr": round(self.invoice_residual_kr, 2),
            "exact_rounded_match": self.exact_rounded_match,
        }


@dataclass
class UtilityTariffAuditReport:
    """Consolidated utility tariff benchmarking and invoicing audit report."""
    leverantorsbyte_date: str
    leverantorsbyte_meter_stand_kwh: Optional[float]
    audited_schedules: Dict[int, AuditedEEMTariffSchedule]
    pre_switch_summary: Dict[str, Any]
    post_switch_summary: Dict[str, Any]
    tariff_benchmark_summary: Dict[str, Any]
    metering_audit_summary: Dict[str, Any]
    annual_summaries: List[Dict[str, Any]]
    monthly_records: List[MonthlyTariffAuditRecord]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leverantorsbyte_date": self.leverantorsbyte_date,
            "leverantorsbyte_meter_stand_kwh": self.leverantorsbyte_meter_stand_kwh,
            "audited_schedules": {
                y: sched.to_dict() for y, sched in self.audited_schedules.items()
            },
            "pre_switch_summary": self.pre_switch_summary,
            "post_switch_summary": self.post_switch_summary,
            "tariff_benchmark_summary": self.tariff_benchmark_summary,
            "metering_audit_summary": self.metering_audit_summary,
            "annual_summaries": self.annual_summaries,
            "monthly_records": [r.to_dict() for r in self.monthly_records],
        }


class EEMYearlyCostsIngestor:
    """Ingests EEM yearly costs CSV (`data/eem-yearly-costs-2024-2026.csv`) and meter transition metadata."""

    DEFAULT_LEVERANTORSBYTE_DATE = "2024-09-28"

    def __init__(self, costs_csv_path: str, meter_csv_path: Optional[str] = None):
        self.costs_csv_path = costs_csv_path
        self.meter_csv_path = meter_csv_path

    def detect_leverantorsbyte_event(self) -> Tuple[str, Optional[float]]:
        """Detect the official `Leverantörsbyte` date and meter stand from EEM meter readings CSV."""
        if not self.meter_csv_path or not os.path.exists(self.meter_csv_path):
            return self.DEFAULT_LEVERANTORSBYTE_DATE, None

        try:
            with open(self.meter_csv_path, "r", encoding="utf-16le") as f:
                reader = csv.reader(f, delimiter=";")
                for row in reader:
                    if not row or len(row) < 7:
                        continue
                    note = row[6].strip()
                    if "Leverantörsbyte" in note:
                        date_str = row[1].strip()
                        stand_val = float(row[2].replace(",", "."))
                        return date_str, stand_val
        except Exception:
            pass

        return self.DEFAULT_LEVERANTORSBYTE_DATE, None

    def parse_records(self) -> List[EEMBillingRecord]:
        """Parse all monthly billing records across 2024, 2025, and 2026."""
        if not os.path.exists(self.costs_csv_path):
            raise FileNotFoundError(f"EEM yearly costs file not found: {self.costs_csv_path}")

        raw_rows: List[Dict[str, str]] = []
        with open(self.costs_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                if row.get("Month", "").strip() == "Total":
                    continue
                raw_rows.append(row)

        records: List[EEMBillingRecord] = []
        for year in (2024, 2025, 2026):
            for row in raw_rows:
                m_abbr = row["Month"].strip()
                if m_abbr not in MONTH_ABBR_TO_NUM:
                    continue
                m_num = MONTH_ABBR_TO_NUM[m_abbr]
                m_name = MONTH_NUM_TO_NAME[m_num]
                days = calendar.monthrange(year, m_num)[1]

                kwh_val = float(row.get(f"kWh{year}", "0") or 0.0)
                kr_val = float(row.get(f"kr{year}", "0") or 0.0)
                is_billed = kr_val > 0.0

                # Pre-Leverantörsbyte (Jan-Sep 2024) was combined EEM Retail + Grid
                if year == 2024 and m_num <= 9:
                    regime = "combined_retail_and_grid"
                else:
                    regime = "pure_grid_tibber"

                records.append(
                    EEMBillingRecord(
                        year=year,
                        month=m_num,
                        month_abbr=m_abbr,
                        month_name=m_name,
                        days_in_month=days,
                        billed_kwh=kwh_val,
                        billed_kr=kr_val,
                        is_billed=is_billed,
                        billing_regime=regime,
                    )
                )

        return records


class UtilityTariffAuditor:
    """Audits SwedishTariff against EEM utility invoices and Sonnen CT clamp records."""

    def __init__(
        self,
        data_dir: str,
        schedules: Optional[Dict[int, AuditedEEMTariffSchedule]] = None,
        baseline_tariff: Optional[SwedishTariff] = None,
    ):
        self.data_dir = data_dir
        self.costs_csv_path = os.path.join(data_dir, "eem-yearly-costs-2024-2026.csv")
        self.meter_csv_path = os.path.join(
            data_dir, "EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv"
        )
        self.schedules = schedules or DEFAULT_AUDITED_EEM_SCHEDULES
        self.baseline_tariff = baseline_tariff or SwedishTariff(config=TariffConfig())
        self.ingestor = EEMYearlyCostsIngestor(self.costs_csv_path, self.meter_csv_path)

    def _load_sonnen_monthly_imports(self) -> Dict[int, Dict[int, float]]:
        """Load monthly imported kWh from `sonnen_energy_data_{year}.csv` for 2024–2026."""
        sonnen_imports: Dict[int, Dict[int, float]] = {}
        for year in (2024, 2025, 2026):
            path = os.path.join(self.data_dir, f"sonnen_energy_data_{year}.csv")
            month_map: Dict[int, float] = {m: 0.0 for m in range(1, 13)}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        ts = row.get("timestamp", "")
                        if len(ts) >= 7:
                            m_num = int(ts[5:7])
                            imp_kwh = float(row.get("grid_purchase_energy", 0.0)) / 1000.0
                            month_map[m_num] = month_map.get(m_num, 0.0) + imp_kwh
            sonnen_imports[year] = month_map
        return sonnen_imports

    def _load_sonnen_oct_2026_cutoff_import(self, cutoff_date: str = "2026-10-24") -> float:
        """Load Sonnen imported kWh for October 2026 up to the EEM CSV export cutoff date."""
        path = os.path.join(self.data_dir, "sonnen_energy_data_2026.csv")
        if not os.path.exists(path):
            return 0.0
        tot_wh = 0.0
        with open(path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                d_str = row.get("timestamp", "")[:10]
                if "2026-10-01" <= d_str <= cutoff_date:
                    tot_wh += float(row.get("grid_purchase_energy", 0.0))
        return tot_wh / 1000.0

    def run_audit(self) -> UtilityTariffAuditReport:
        """Execute full utility tariff and invoicing audit across 2024–2026."""
        switch_date, switch_stand = self.ingestor.detect_leverantorsbyte_event()
        billing_records = self.ingestor.parse_records()
        sonnen_imports = self._load_sonnen_monthly_imports()
        sonnen_oct24_kwh = self._load_sonnen_oct_2026_cutoff_import("2026-10-24")

        # Uncalibrated baseline SwedishTariff variable grid+tax rate incl. VAT:
        # (0.428 + 0.176) * 1.25 = 0.755 SEK/kWh
        uncal_var_rate_inc_vat = (
            self.baseline_tariff.config.energiskatt_sek_per_kwh
            + self.baseline_tariff.config.eem_transfer_fee_sek_per_kwh
        ) * (1.0 + self.baseline_tariff.config.moms_rate)

        monthly_audit_records: List[MonthlyTariffAuditRecord] = []

        for rec in billing_records:
            sched = self.schedules[rec.year]
            sonnen_kwh = sonnen_imports.get(rec.year, {}).get(rec.month, 0.0)

            # For October 2026 (unbilled partial month exported on 2026-10-24), compare against Oct 1-24 Sonnen import
            if rec.year == 2026 and rec.month == 10 and not rec.is_billed and rec.billed_kwh > 0:
                sonnen_kwh_comp = sonnen_oct24_kwh
            elif not rec.is_billed and rec.billed_kwh == 0.0:
                sonnen_kwh_comp = 0.0
            else:
                sonnen_kwh_comp = sonnen_kwh

            kwh_delta = rec.billed_kwh - sonnen_kwh_comp
            kwh_delta_pct = (
                ((sonnen_kwh_comp - rec.billed_kwh) / rec.billed_kwh * 100.0)
                if rec.billed_kwh > 0
                else 0.0
            )

            if rec.is_billed:
                fixed_kr = sched.calculate_fixed_fee_sek(rec.days_in_month)
                var_kr = sched.calculate_variable_fee_sek(rec.billed_kwh)
                tot_grid_kr = fixed_kr + var_kr
                uncal_var_kr = rec.billed_kwh * uncal_var_rate_inc_vat

                if rec.billing_regime == "combined_retail_and_grid":
                    retail_supply_kr = max(0.0, rec.billed_kr - tot_grid_kr)
                    residual_kr = 0.0
                    exact_match = None
                else:
                    retail_supply_kr = 0.0
                    residual_kr = rec.billed_kr - tot_grid_kr
                    exact_match = round(tot_grid_kr) == round(rec.billed_kr)
            else:
                fixed_kr = 0.0
                var_kr = 0.0
                tot_grid_kr = 0.0
                uncal_var_kr = 0.0
                retail_supply_kr = 0.0
                residual_kr = 0.0
                exact_match = None

            monthly_audit_records.append(
                MonthlyTariffAuditRecord(
                    year=rec.year,
                    month=rec.month,
                    month_name=rec.month_name,
                    days_in_month=rec.days_in_month,
                    billing_regime=rec.billing_regime,
                    is_billed=rec.is_billed,
                    eem_billed_kwh=rec.billed_kwh,
                    sonnen_imported_kwh=sonnen_kwh_comp,
                    kwh_delta=kwh_delta,
                    kwh_delta_pct=kwh_delta_pct,
                    eem_billed_kr=rec.billed_kr,
                    audited_grid_fixed_kr=fixed_kr,
                    audited_grid_variable_kr=var_kr,
                    audited_grid_total_kr=tot_grid_kr,
                    inferred_eem_retail_supply_kr=retail_supply_kr,
                    uncalibrated_tariff_variable_kr=uncal_var_kr,
                    invoice_residual_kr=residual_kr,
                    exact_rounded_match=exact_match,
                )
            )

        # 1. Pre-Switch Summary (Jan - Sep 2024, 9 months)
        pre_recs = [
            r for r in monthly_audit_records
            if r.is_billed and r.billing_regime == "combined_retail_and_grid"
        ]
        pre_kwh = sum(r.eem_billed_kwh for r in pre_recs)
        pre_billed_kr = sum(r.eem_billed_kr for r in pre_recs)
        pre_grid_kr = sum(r.audited_grid_total_kr for r in pre_recs)
        pre_retail_kr = sum(r.inferred_eem_retail_supply_kr for r in pre_recs)

        pre_switch_summary = {
            "period": "2024-01 to 2024-09 (Pre-Leverantörsbyte)",
            "months_count": len(pre_recs),
            "billed_kwh": round(pre_kwh, 3),
            "total_billed_kr": round(pre_billed_kr, 2),
            "decomposed_grid_and_tax_kr": round(pre_grid_kr, 2),
            "decomposed_eem_retail_supply_kr": round(pre_retail_kr, 2),
            "avg_all_in_sek_per_kwh": round(pre_billed_kr / pre_kwh, 4) if pre_kwh > 0 else 0.0,
            "avg_retail_supply_sek_per_kwh": round(pre_retail_kr / pre_kwh, 4) if pre_kwh > 0 else 0.0,
        }

        # 2. Post-Switch Summary (Oct 2024 - Sep 2026, 24 billed months)
        post_recs = [
            r for r in monthly_audit_records
            if r.is_billed and r.billing_regime == "pure_grid_tibber"
        ]
        post_kwh = sum(r.eem_billed_kwh for r in post_recs)
        post_billed_kr = sum(r.eem_billed_kr for r in post_recs)
        post_modeled_kr = sum(r.audited_grid_total_kr for r in post_recs)
        post_fixed_kr = sum(r.audited_grid_fixed_kr for r in post_recs)
        post_var_kr = sum(r.audited_grid_variable_kr for r in post_recs)
        exact_matches_count = sum(1 for r in post_recs if r.exact_rounded_match)
        mae_kr = (
            sum(abs(r.invoice_residual_kr) for r in post_recs) / len(post_recs)
            if post_recs
            else 0.0
        )
        max_abs_err_kr = max((abs(r.invoice_residual_kr) for r in post_recs), default=0.0)

        post_switch_summary = {
            "period": "2024-10 to 2026-09 (Post-Leverantörsbyte Pure Grid)",
            "months_count": len(post_recs),
            "billed_kwh": round(post_kwh, 3),
            "total_billed_kr": round(post_billed_kr, 2),
            "total_modeled_grid_kr": round(post_modeled_kr, 2),
            "total_fixed_fee_kr": round(post_fixed_kr, 2),
            "total_variable_fee_kr": round(post_var_kr, 2),
            "net_cumulative_residual_kr": round(post_billed_kr - post_modeled_kr, 2),
            "mean_absolute_error_kr": round(mae_kr, 2),
            "max_absolute_error_kr": round(max_abs_err_kr, 2),
            "exact_integer_invoice_matches": exact_matches_count,
            "exact_match_rate_pct": round(
                (exact_matches_count / len(post_recs) * 100.0) if post_recs else 0.0, 1
            ),
        }

        # 3. SwedishTariff Benchmark Summary
        billed_all = [r for r in monthly_audit_records if r.is_billed]
        tot_audited_var_kr = sum(r.audited_grid_variable_kr for r in billed_all)
        tot_uncal_var_kr = sum(r.uncalibrated_tariff_variable_kr for r in billed_all)

        tariff_benchmark_summary = {
            "uncalibrated_energiskatt_ore_ex_vat": round(
                self.baseline_tariff.config.energiskatt_sek_per_kwh * 100.0, 2
            ),
            "uncalibrated_eem_transfer_ore_ex_vat": round(
                self.baseline_tariff.config.eem_transfer_fee_sek_per_kwh * 100.0, 2
            ),
            "uncalibrated_total_variable_ore_inc_vat": round(uncal_var_rate_inc_vat * 100.0, 2),
            "audited_eem_transfer_ore_ex_vat_range": "23.50 - 23.55",
            "audited_total_variable_ore_inc_vat_by_year": {
                y: round(s.variable_grid_and_tax_sek_per_kwh_inc_vat * 100.0, 2)
                for y, s in self.schedules.items()
            },
            "variable_rate_delta_ore_inc_vat_by_year": {
                y: round(
                    (s.variable_grid_and_tax_sek_per_kwh_inc_vat - uncal_var_rate_inc_vat) * 100.0,
                    2,
                )
                for y, s in self.schedules.items()
            },
            "total_33m_audited_variable_kr": round(tot_audited_var_kr, 2),
            "total_33m_uncalibrated_variable_kr": round(tot_uncal_var_kr, 2),
            "total_33m_variable_underestimation_kr": round(
                tot_audited_var_kr - tot_uncal_var_kr, 2
            ),
        }

        # 4. Metering & CT Clamp Cross-Validation Summary
        tot_eem_billed_kwh = sum(r.eem_billed_kwh for r in billed_all)
        tot_sonnen_billed_kwh = sum(r.sonnen_imported_kwh for r in billed_all)
        oct26_rec = next(
            (r for r in monthly_audit_records if r.year == 2026 and r.month == 10),
            None,
        )

        metering_audit_summary = {
            "billed_months_count": len(billed_all),
            "total_eem_fiscal_import_kwh": round(tot_eem_billed_kwh, 2),
            "total_sonnen_ct_import_kwh": round(tot_sonnen_billed_kwh, 2),
            "total_kwh_delta": round(tot_eem_billed_kwh - tot_sonnen_billed_kwh, 2),
            "sonnen_ct_bias_pct": round(
                (tot_sonnen_billed_kwh - tot_eem_billed_kwh) / tot_eem_billed_kwh * 100.0, 2
            ) if tot_eem_billed_kwh > 0 else 0.0,
            "oct_2026_partial_export_check": {
                "cutoff_date": "2026-10-24",
                "eem_partial_kwh": round(oct26_rec.eem_billed_kwh, 3) if oct26_rec else 0.0,
                "sonnen_oct1_to_oct24_kwh": round(sonnen_oct24_kwh, 3),
                "bias_pct": round(oct26_rec.kwh_delta_pct, 2) if oct26_rec else 0.0,
            },
        }

        # 5. Annual Summaries (2024, 2025, 2026)
        annual_summaries: List[Dict[str, Any]] = []
        for year in (2024, 2025, 2026):
            y_recs = [r for r in monthly_audit_records if r.year == year and r.is_billed]
            y_eem_kwh = sum(r.eem_billed_kwh for r in y_recs)
            y_son_kwh = sum(r.sonnen_imported_kwh for r in y_recs)
            y_billed_kr = sum(r.eem_billed_kr for r in y_recs)
            y_grid_fixed = sum(r.audited_grid_fixed_kr for r in y_recs)
            y_grid_var = sum(r.audited_grid_variable_kr for r in y_recs)
            y_grid_tot = sum(r.audited_grid_total_kr for r in y_recs)
            y_retail = sum(r.inferred_eem_retail_supply_kr for r in y_recs)
            y_uncal_var = sum(r.uncalibrated_tariff_variable_kr for r in y_recs)

            sched = self.schedules[year]
            annual_summaries.append({
                "year": year,
                "billed_months": len(y_recs),
                "regime_description": (
                    "Jan–Sep Combined Retail+Grid; Oct–Dec Pure Grid"
                    if year == 2024
                    else "Pure EEM Grid + Energiskatt (Tibber Retail)"
                ),
                "eem_billed_kwh": round(y_eem_kwh, 2),
                "sonnen_imported_kwh": round(y_son_kwh, 2),
                "ct_clamp_bias_pct": round(
                    (y_son_kwh - y_eem_kwh) / y_eem_kwh * 100.0, 2
                ) if y_eem_kwh > 0 else 0.0,
                "eem_billed_kr": round(y_billed_kr, 2),
                "audited_grid_fixed_kr": round(y_grid_fixed, 2),
                "audited_grid_variable_kr": round(y_grid_var, 2),
                "audited_grid_total_kr": round(y_grid_tot, 2),
                "inferred_eem_retail_supply_kr": round(y_retail, 2),
                "uncalibrated_tariff_variable_kr": round(y_uncal_var, 2),
                "fixed_daily_fee_sek_inc_vat": round(sched.fixed_daily_fee_sek_inc_vat, 2),
                "variable_rate_ore_inc_vat": round(
                    sched.variable_grid_and_tax_sek_per_kwh_inc_vat * 100.0, 2
                ),
            })

        return UtilityTariffAuditReport(
            leverantorsbyte_date=switch_date,
            leverantorsbyte_meter_stand_kwh=switch_stand,
            audited_schedules=self.schedules,
            pre_switch_summary=pre_switch_summary,
            post_switch_summary=post_switch_summary,
            tariff_benchmark_summary=tariff_benchmark_summary,
            metering_audit_summary=metering_audit_summary,
            annual_summaries=annual_summaries,
            monthly_records=monthly_audit_records,
        )
