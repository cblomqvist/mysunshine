"""2025 Full-Year ROI and Financial Ledger Engine.

Ingests Sonnen historical logs, matches against SE3 spot prices,
and computes 3-way baseline economics, monthly ledgers, and payback metrics.
"""

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .baseline import (
    BaselineComparisonResult,
    BaselineEngine,
    DEFAULT_DIURNAL_LOAD_WEIGHTS,
    DEFAULT_DIURNAL_SOLAR_WEIGHTS,
)
from .tariff import SwedishTariff


@dataclass
class DailyFinancialRecord:
    """Financial and energy balance record for a single day."""
    date_str: str
    produced_kwh: float
    consumed_kwh: float
    imported_kwh: float
    exported_kwh: float
    battery_charged_kwh: float
    battery_discharged_kwh: float
    avg_spot_price_sek_kwh: float
    comparison: BaselineComparisonResult


@dataclass
class MonthlyFinancialLedger:
    """Aggregated financial and energy ledger for a calendar month."""
    month_name: str
    month_number: int
    year: int
    days_count: int

    # Energy Totals (kWh)
    produced_kwh: float
    consumed_kwh: float
    imported_kwh: float
    exported_kwh: float
    battery_charged_kwh: float
    battery_discharged_kwh: float

    # Pricing
    avg_spot_price_ore_kwh: float
    avg_spot_price_sek_kwh: float

    # Financial Bills & Baselines (SEK)
    baseline_no_solar_cost_sek: float
    baseline_solar_only_cost_sek: float
    actual_cost_sek: float
    fixed_subscription_fee_sek: float

    # Value Creation (SEK)
    total_savings_sek: float           # Actual vs No Solar
    solar_contribution_sek: float      # Solar Only vs No Solar
    battery_marginal_value_sek: float  # Actual Savings - Solar Only Savings

    # Key Performance Indicators
    battery_roundtrip_efficiency_pct: float
    solar_only_self_consumption_pct: float
    actual_self_consumption_pct: float


@dataclass
class CapexPaybackMetrics:
    """Financial investment and payback metrics."""
    capex_sek: float
    annual_savings_sek: float
    solar_contribution_sek: float
    battery_marginal_value_sek: float
    simple_payback_years: float
    annual_roi_pct: float
    recouped_pct: float
    remaining_balance_sek: float
    break_even_year: Optional[float] = None
    projected_25y_cash_flow: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class AnnualFinancialReport:
    """Full-year financial report containing monthly ledgers and overall ROI."""
    year: int
    total_days: int
    energy_totals: Dict[str, float]
    financial_totals: Dict[str, float]
    monthly_ledgers: List[MonthlyFinancialLedger]
    daily_records: List[DailyFinancialRecord]
    capex_metrics: Optional[CapexPaybackMetrics] = None

    def to_dict(self) -> Dict:
        """Serialize report to a dictionary for JSON output."""
        return {
            "year": self.year,
            "total_days": self.total_days,
            "energy_totals": self.energy_totals,
            "financial_totals": self.financial_totals,
            "monthly_ledgers": [
                {
                    "month": m.month_name,
                    "month_number": m.month_number,
                    "days": m.days_count,
                    "produced_kwh": round(m.produced_kwh, 2),
                    "consumed_kwh": round(m.consumed_kwh, 2),
                    "imported_kwh": round(m.imported_kwh, 2),
                    "exported_kwh": round(m.exported_kwh, 2),
                    "battery_charged_kwh": round(m.battery_charged_kwh, 2),
                    "battery_discharged_kwh": round(m.battery_discharged_kwh, 2),
                    "battery_efficiency_pct": round(m.battery_roundtrip_efficiency_pct, 1),
                    "avg_spot_price_ore": round(m.avg_spot_price_ore_kwh, 2),
                    "baseline_no_solar_sek": round(m.baseline_no_solar_cost_sek, 2),
                    "baseline_solar_only_sek": round(m.baseline_solar_only_cost_sek, 2),
                    "actual_cost_sek": round(m.actual_cost_sek, 2),
                    "total_savings_sek": round(m.total_savings_sek, 2),
                    "solar_savings_sek": round(m.solar_contribution_sek, 2),
                    "battery_savings_sek": round(m.battery_marginal_value_sek, 2),
                    "solar_only_sc_pct": round(m.solar_only_self_consumption_pct, 1),
                    "actual_sc_pct": round(m.actual_self_consumption_pct, 1),
                }
                for m in self.monthly_ledgers
            ],
            "capex_metrics": (
                {
                    "capex_sek": self.capex_metrics.capex_sek,
                    "annual_savings_sek": round(self.capex_metrics.annual_savings_sek, 2),
                    "solar_contribution_sek": round(self.capex_metrics.solar_contribution_sek, 2),
                    "battery_marginal_value_sek": round(self.capex_metrics.battery_marginal_value_sek, 2),
                    "simple_payback_years": round(self.capex_metrics.simple_payback_years, 2),
                    "annual_roi_pct": round(self.capex_metrics.annual_roi_pct, 2),
                    "recouped_pct": round(self.capex_metrics.recouped_pct, 2),
                    "remaining_balance_sek": round(self.capex_metrics.remaining_balance_sek, 2),
                    "break_even_year": self.capex_metrics.break_even_year,
                }
                if self.capex_metrics
                else None
            ),
        }


class Year2025Calculator:
    """Calculates full-year 2025 historical ROI, 3-way baselines, and Capex metrics."""

    def __init__(
        self,
        tariff: Optional[SwedishTariff] = None,
        baseline_engine: Optional[BaselineEngine] = None,
        data_file: str = "data/sonnen_energy_data_2025.csv",
        price_file: Optional[str] = "data/prices/se3_prices_2025.json",
    ):
        self.tariff = tariff or SwedishTariff()
        self.engine = baseline_engine or BaselineEngine(tariff=self.tariff)
        self.data_file = data_file
        self.price_file = price_file

    def _load_prices_by_date(self) -> Dict[str, List[float]]:
        """Load spot prices grouped by date string (YYYY-MM-DD) in SEK/kWh."""
        prices_by_date: Dict[str, List[float]] = {}

        if self.price_file and os.path.exists(self.price_file):
            with open(self.price_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    ts_str = item.get("timestamp", "")
                    if not ts_str:
                        continue
                    dt = datetime.fromisoformat(ts_str)
                    date_key = dt.strftime("%Y-%m-%d")
                    p_sek = item.get("price_sek_kwh")
                    if p_sek is None and "price_eur_mwh" in item:
                        p_sek = SwedishTariff().config.energiskatt_sek_per_kwh  # fallback
                    if p_sek is not None:
                        prices_by_date.setdefault(date_key, []).append(float(p_sek))

        return prices_by_date

    def calculate_2025_report(
        self,
        capex_sek: Optional[float] = None,
    ) -> AnnualFinancialReport:
        """Compute the complete 2025 full-year financial report."""
        if not os.path.exists(self.data_file):
            raise FileNotFoundError(f"Sonnen 2025 data file not found: {self.data_file}")

        prices_by_date = self._load_prices_by_date()

        # Fallback default price if price lookup is empty (approx 0.58 SEK/kWh ~ 58 öre/kWh)
        default_spot_price = 0.58

        daily_records: List[DailyFinancialRecord] = []

        with open(self.data_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row["timestamp"]
                dt = datetime.fromisoformat(ts_str)
                date_key = dt.strftime("%Y-%m-%d")

                # Energy readings are in Wh -> convert to kWh
                produced_kwh = float(row.get("produced_energy", 0.0)) / 1000.0
                consumed_kwh = float(row.get("consumed_energy", 0.0)) / 1000.0
                batt_chg_kwh = float(row.get("battery_charged_energy", 0.0)) / 1000.0
                batt_dis_kwh = float(row.get("battery_discharged_energy", 0.0)) / 1000.0
                feedin_kwh = float(row.get("grid_feedin_energy", 0.0)) / 1000.0
                purchase_kwh = float(row.get("grid_purchase_energy", 0.0)) / 1000.0

                # Determine spot price for the day
                day_prices = prices_by_date.get(date_key)
                if day_prices:
                    avg_spot = sum(day_prices) / len(day_prices)
                else:
                    avg_spot = default_spot_price

                # If hourly price points exist for the day, evaluate hourly precision for baselines
                if day_prices and len(day_prices) in (23, 24, 25):
                    # We have 24-hour prices for this day
                    # Disaggregate load and pv across 24h
                    n_h = len(day_prices)
                    b1_imp_cost = 0.0
                    b2_imp_cost = 0.0
                    b2_exp_rev = 0.0
                    b2_sc_tot = 0.0
                    b2_exp_tot = 0.0
                    b2_imp_tot = 0.0

                    for h in range(n_h):
                        w_l = DEFAULT_DIURNAL_LOAD_WEIGHTS[h % 24]
                        w_pv = DEFAULT_DIURNAL_SOLAR_WEIGHTS[h % 24]
                        load_h = consumed_kwh * w_l
                        pv_h = produced_kwh * w_pv
                        p_h = day_prices[h]

                        # B1
                        b1_imp_cost += self.tariff.calculate_import_cost(load_h, p_h)

                        # B2
                        sc_h = min(pv_h, load_h)
                        exp_h = max(0.0, pv_h - load_h)
                        imp_h = max(0.0, load_h - pv_h)

                        b2_sc_tot += sc_h
                        b2_exp_tot += exp_h
                        b2_imp_tot += imp_h

                        b2_imp_cost += self.tariff.calculate_import_cost(imp_h, p_h)
                        b2_exp_rev += self.tariff.calculate_export_revenue(exp_h, p_h)

                    # Actual system
                    act_imp_cost = self.tariff.calculate_import_cost(purchase_kwh, avg_spot)
                    act_exp_rev = self.tariff.calculate_export_revenue(feedin_kwh, avg_spot)
                    act_sc = max(0.0, produced_kwh - feedin_kwh)

                    from .baseline import BaselineScenarioResult
                    b1 = BaselineScenarioResult(
                        name="Baseline 1: No Solar, No Battery",
                        consumed_kwh=consumed_kwh,
                        produced_kwh=0.0,
                        imported_kwh=consumed_kwh,
                        exported_kwh=0.0,
                        self_consumed_kwh=0.0,
                        import_cost_sek=b1_imp_cost,
                        export_revenue_sek=0.0,
                        fixed_cost_sek=0.0,
                        net_cost_sek=b1_imp_cost,
                        savings_sek=0.0,
                    )
                    b2_net = b2_imp_cost - b2_exp_rev
                    b2 = BaselineScenarioResult(
                        name="Baseline 2: Solar Only",
                        consumed_kwh=consumed_kwh,
                        produced_kwh=produced_kwh,
                        imported_kwh=b2_imp_tot,
                        exported_kwh=b2_exp_tot,
                        self_consumed_kwh=b2_sc_tot,
                        import_cost_sek=b2_imp_cost,
                        export_revenue_sek=b2_exp_rev,
                        fixed_cost_sek=0.0,
                        net_cost_sek=b2_net,
                        savings_sek=b1_imp_cost - b2_net,
                    )
                    act_net = act_imp_cost - act_exp_rev
                    act = BaselineScenarioResult(
                        name="Actual: Solar + SonnenBatterie 10",
                        consumed_kwh=consumed_kwh,
                        produced_kwh=produced_kwh,
                        imported_kwh=purchase_kwh,
                        exported_kwh=feedin_kwh,
                        self_consumed_kwh=act_sc,
                        import_cost_sek=act_imp_cost,
                        export_revenue_sek=act_exp_rev,
                        fixed_cost_sek=0.0,
                        net_cost_sek=act_net,
                        savings_sek=b1_imp_cost - act_net,
                    )
                    tot_sav = b1_imp_cost - act_net
                    sol_sav = b1_imp_cost - b2_net
                    bat_sav = tot_sav - sol_sav
                    eff = (batt_dis_kwh / batt_chg_kwh * 100.0) if batt_chg_kwh > 0 else 0.0
                    b2_pct = (b2_sc_tot / produced_kwh * 100.0) if produced_kwh > 0 else 0.0
                    act_pct = (act_sc / produced_kwh * 100.0) if produced_kwh > 0 else 0.0

                    comp = BaselineComparisonResult(
                        baseline_no_solar=b1,
                        baseline_solar_only=b2,
                        actual_system=act,
                        total_savings_sek=tot_sav,
                        solar_contribution_sek=sol_sav,
                        battery_marginal_value_sek=bat_sav,
                        battery_charged_kwh=batt_chg_kwh,
                        battery_discharged_kwh=batt_dis_kwh,
                        battery_roundtrip_efficiency=eff,
                        battery_net_throughput_kwh=batt_chg_kwh + batt_dis_kwh,
                        solar_only_self_consumption_pct=b2_pct,
                        actual_self_consumption_pct=act_pct,
                    )
                else:
                    comp = self.engine.evaluate_daily_point(
                        consumed_kwh=consumed_kwh,
                        produced_kwh=produced_kwh,
                        actual_imported_kwh=purchase_kwh,
                        actual_exported_kwh=feedin_kwh,
                        battery_charged_kwh=batt_chg_kwh,
                        battery_discharged_kwh=batt_dis_kwh,
                        spot_price_sek_per_kwh=avg_spot,
                        months_fraction=0.0,
                    )

                daily_records.append(
                    DailyFinancialRecord(
                        date_str=date_key,
                        produced_kwh=produced_kwh,
                        consumed_kwh=consumed_kwh,
                        imported_kwh=purchase_kwh,
                        exported_kwh=feedin_kwh,
                        battery_charged_kwh=batt_chg_kwh,
                        battery_discharged_kwh=batt_dis_kwh,
                        avg_spot_price_sek_kwh=avg_spot,
                        comparison=comp,
                    )
                )

        # Monthly aggregation
        months_data: Dict[int, List[DailyFinancialRecord]] = {}
        for rec in daily_records:
            m_num = int(rec.date_str.split("-")[1])
            months_data.setdefault(m_num, []).append(rec)

        monthly_ledgers: List[MonthlyFinancialLedger] = []
        month_names = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        fixed_fee_per_month = self.tariff.calculate_fixed_costs(1.0)

        for m_num in sorted(months_data.keys()):
            recs = months_data[m_num]
            m_days = len(recs)
            m_prod = sum(r.produced_kwh for r in recs)
            m_cons = sum(r.consumed_kwh for r in recs)
            m_imp = sum(r.imported_kwh for r in recs)
            m_exp = sum(r.exported_kwh for r in recs)
            m_chg = sum(r.battery_charged_kwh for r in recs)
            m_dis = sum(r.battery_discharged_kwh for r in recs)
            m_spot_avg = sum(r.avg_spot_price_sek_kwh for r in recs) / m_days

            m_b1_cost = sum(r.comparison.baseline_no_solar.net_cost_sek for r in recs) + fixed_fee_per_month
            m_b2_cost = sum(r.comparison.baseline_solar_only.net_cost_sek for r in recs) + fixed_fee_per_month
            m_act_cost = sum(r.comparison.actual_system.net_cost_sek for r in recs) + fixed_fee_per_month

            m_tot_sav = m_b1_cost - m_act_cost
            m_sol_sav = m_b1_cost - m_b2_cost
            m_bat_sav = m_b2_cost - m_act_cost

            m_eff = (m_dis / m_chg * 100.0) if m_chg > 0 else 0.0
            m_b2_sc = sum(r.comparison.baseline_solar_only.self_consumed_kwh for r in recs)
            m_act_sc = sum(r.comparison.actual_system.self_consumed_kwh for r in recs)

            m_b2_sc_pct = (m_b2_sc / m_prod * 100.0) if m_prod > 0 else 0.0
            m_act_sc_pct = (m_act_sc / m_prod * 100.0) if m_prod > 0 else 0.0

            monthly_ledgers.append(
                MonthlyFinancialLedger(
                    month_name=month_names[m_num],
                    month_number=m_num,
                    year=2025,
                    days_count=m_days,
                    produced_kwh=m_prod,
                    consumed_kwh=m_cons,
                    imported_kwh=m_imp,
                    exported_kwh=m_exp,
                    battery_charged_kwh=m_chg,
                    battery_discharged_kwh=m_dis,
                    avg_spot_price_ore_kwh=m_spot_avg * 100.0,
                    avg_spot_price_sek_kwh=m_spot_avg,
                    baseline_no_solar_cost_sek=m_b1_cost,
                    baseline_solar_only_cost_sek=m_b2_cost,
                    actual_cost_sek=m_act_cost,
                    fixed_subscription_fee_sek=fixed_fee_per_month,
                    total_savings_sek=m_tot_sav,
                    solar_contribution_sek=m_sol_sav,
                    battery_marginal_value_sek=m_bat_sav,
                    battery_roundtrip_efficiency_pct=m_eff,
                    solar_only_self_consumption_pct=m_b2_sc_pct,
                    actual_self_consumption_pct=m_act_sc_pct,
                )
            )

        # Annual Totals
        tot_prod = sum(m.produced_kwh for m in monthly_ledgers)
        tot_cons = sum(m.consumed_kwh for m in monthly_ledgers)
        tot_imp = sum(m.imported_kwh for m in monthly_ledgers)
        tot_exp = sum(m.exported_kwh for m in monthly_ledgers)
        tot_chg = sum(m.battery_charged_kwh for m in monthly_ledgers)
        tot_dis = sum(m.battery_discharged_kwh for m in monthly_ledgers)
        tot_eff = (tot_dis / tot_chg * 100.0) if tot_chg > 0 else 0.0

        tot_b1_cost = sum(m.baseline_no_solar_cost_sek for m in monthly_ledgers)
        tot_b2_cost = sum(m.baseline_solar_only_cost_sek for m in monthly_ledgers)
        tot_act_cost = sum(m.actual_cost_sek for m in monthly_ledgers)
        tot_fixed_fee = sum(m.fixed_subscription_fee_sek for m in monthly_ledgers)

        tot_sav = tot_b1_cost - tot_act_cost
        tot_sol_sav = tot_b1_cost - tot_b2_cost
        tot_bat_sav = tot_b2_cost - tot_act_cost

        energy_totals = {
            "produced_kwh": tot_prod,
            "consumed_kwh": tot_cons,
            "imported_kwh": tot_imp,
            "exported_kwh": tot_exp,
            "battery_charged_kwh": tot_chg,
            "battery_discharged_kwh": tot_dis,
            "battery_roundtrip_efficiency_pct": tot_eff,
            "self_consumed_kwh": max(0.0, tot_prod - tot_exp),
            "actual_self_consumption_pct": (max(0.0, tot_prod - tot_exp) / tot_prod * 100.0) if tot_prod > 0 else 0.0,
        }

        financial_totals = {
            "baseline_no_solar_cost_sek": tot_b1_cost,
            "baseline_solar_only_cost_sek": tot_b2_cost,
            "actual_cost_sek": tot_act_cost,
            "total_fixed_fee_sek": tot_fixed_fee,
            "total_savings_sek": tot_sav,
            "solar_contribution_sek": tot_sol_sav,
            "battery_marginal_value_sek": tot_bat_sav,
        }

        # Capex & Payback
        capex_metrics = None
        if capex_sek is not None and capex_sek > 0:
            capex_metrics = self.calculate_capex_payback(
                capex_sek=capex_sek,
                annual_savings_sek=tot_sav,
                solar_contribution_sek=tot_sol_sav,
                battery_marginal_value_sek=tot_bat_sav,
            )

        return AnnualFinancialReport(
            year=2025,
            total_days=len(daily_records),
            energy_totals=energy_totals,
            financial_totals=financial_totals,
            monthly_ledgers=monthly_ledgers,
            daily_records=daily_records,
            capex_metrics=capex_metrics,
        )

    def calculate_capex_payback(
        self,
        capex_sek: float,
        annual_savings_sek: float,
        solar_contribution_sek: float,
        battery_marginal_value_sek: float,
        energy_inflation_rate: float = 0.02,
        solar_degradation_rate: float = 0.005,
        projection_years: int = 25,
    ) -> CapexPaybackMetrics:
        """Calculate dynamic investment payback years and 25-year cash flow projections."""
        simple_payback = (capex_sek / annual_savings_sek) if annual_savings_sek > 0 else 999.0
        annual_roi = (annual_savings_sek / capex_sek * 100.0) if capex_sek > 0 else 0.0
        recouped_pct = (annual_savings_sek / capex_sek * 100.0) if capex_sek > 0 else 0.0
        remaining_balance = capex_sek - annual_savings_sek

        # 25-year projection
        projected_cash_flow: List[Dict[str, float]] = []
        cumulative_balance = -capex_sek
        break_even_year: Optional[float] = None

        for year in range(1, projection_years + 1):
            # Energy prices inflate, panels slowly degrade
            inflation_factor = (1.0 + energy_inflation_rate) ** (year - 1)
            degradation_factor = (1.0 - solar_degradation_rate) ** (year - 1)
            year_savings = annual_savings_sek * inflation_factor * degradation_factor

            prev_balance = cumulative_balance
            cumulative_balance += year_savings

            if prev_balance < 0 and cumulative_balance >= 0 and break_even_year is None:
                # Linear interpolation for fractional break-even year
                frac = (-prev_balance) / year_savings
                break_even_year = round((year - 1) + frac, 2)

            projected_cash_flow.append({
                "year": year,
                "annual_savings_sek": round(year_savings, 2),
                "cumulative_balance_sek": round(cumulative_balance, 2),
            })

        return CapexPaybackMetrics(
            capex_sek=capex_sek,
            annual_savings_sek=annual_savings_sek,
            solar_contribution_sek=solar_contribution_sek,
            battery_marginal_value_sek=battery_marginal_value_sek,
            simple_payback_years=round(simple_payback, 2),
            annual_roi_pct=round(annual_roi, 2),
            recouped_pct=round(recouped_pct, 2),
            remaining_balance_sek=round(remaining_balance, 2),
            break_even_year=break_even_year,
            projected_25y_cash_flow=projected_cash_flow,
        )
