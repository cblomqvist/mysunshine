"""Multi-Year Historical ROI, Hardware Transition Modeling & Calculation Engine.

Ingests multi-year Sonnen energy exports (2023, 2024, 2025), aligns with historical
SE3 electricity spot prices, models operational hardware eras (11 kWh vs 22 kWh),
and computes validated 3-way comparative financial baselines across all historical years.
"""

import csv
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .baseline import (
    BaselineComparisonResult,
    BaselineEngine,
    BaselineScenarioResult,
    DEFAULT_DIURNAL_LOAD_WEIGHTS,
    DEFAULT_DIURNAL_SOLAR_WEIGHTS,
)
from .calculator_2025 import (
    AnnualFinancialReport,
    CapexPaybackMetrics,
    DailyFinancialRecord,
    MonthlyFinancialLedger,
)
from .tariff import SwedishTariff

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@dataclass
class HardwareEra:
    """Represents an operational hardware era."""
    name: str
    start_date: str
    end_date: Optional[str]
    solar_capacity_kw: float
    battery_capacity_kwh: float
    battery_modules_count: int
    net_capex_sek: float
    description: str


DEFAULT_HARDWARE_ERAS = [
    HardwareEra(
        name="Era 1: Solar Only",
        start_date="2021-01-01",
        end_date="2023-09-12",
        solar_capacity_kw=8.0,
        battery_capacity_kwh=0.0,
        battery_modules_count=0,
        net_capex_sek=165000.0,
        description="SMA STP8.0-3AV-40 Solar PV only",
    ),
    HardwareEra(
        name="Era 2: Sonnen 11 kWh",
        start_date="2023-09-13",
        end_date="2024-09-08",
        solar_capacity_kw=8.0,
        battery_capacity_kwh=11.0,
        battery_modules_count=2,
        net_capex_sek=240000.0,  # 165k Solar + 75k Net 11 kWh module
        description="SonnenBatterie 10 single module (11 kWh nominal / 10 kWh usable)",
    ),
    HardwareEra(
        name="Era 3: Sonnen 22 kWh Expansion",
        start_date="2024-09-09",
        end_date=None,
        solar_capacity_kw=8.0,
        battery_capacity_kwh=22.0,
        battery_modules_count=4,
        net_capex_sek=315000.0,  # 165k Solar + 150k Total Net Battery
        description="SonnenBatterie 10 dual module expansion (22 kWh nominal / 20 kWh usable)",
    ),
]


class HistoricalYearCalculator:
    """Calculates ROI, 3-way baselines, and monthly ledgers for any historical year."""

    def __init__(
        self,
        year: int,
        data_file: str,
        price_file: Optional[str] = None,
        tariff: Optional[SwedishTariff] = None,
    ):
        self.year = year
        self.data_file = data_file
        self.price_file = price_file
        self.tariff = tariff or SwedishTariff()
        self.engine = BaselineEngine(tariff=self.tariff)

    def load_spot_prices_by_date(self) -> Dict[str, List[float]]:
        """Load hourly spot prices indexed by date string (YYYY-MM-DD)."""
        prices_by_date: Dict[str, List[float]] = {}
        if not self.price_file or not os.path.exists(self.price_file):
            return prices_by_date

        try:
            with open(self.price_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            points = data.get("price_points", data) if isinstance(data, dict) else data
            for pt in points:
                ts_str = pt.get("timestamp")
                p_sek = pt.get("price_sek_per_kwh", pt.get("price_ore_per_kwh", 0.0) / 100.0)
                if ts_str:
                    dt = datetime.fromisoformat(ts_str)
                    d_key = dt.strftime("%Y-%m-%d")
                    if d_key not in prices_by_date:
                        prices_by_date[d_key] = []
                    prices_by_date[d_key].append(p_sek)
        except Exception as e:
            logging.warning("Error reading price file %s: %s", self.price_file, e)

        return prices_by_date

    def calculate_annual_report(self, capex_sek: Optional[float] = None) -> AnnualFinancialReport:
        """Calculate complete annual report for the configured year."""
        if not os.path.exists(self.data_file):
            raise FileNotFoundError(f"Data file not found: {self.data_file}")

        prices_by_date = self.load_spot_prices_by_date()
        daily_records: List[DailyFinancialRecord] = []
        default_spot_price = 0.50  # 50 öre/kWh fallback

        with open(self.data_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row["timestamp"]
                dt = datetime.fromisoformat(ts_str)
                date_key = dt.strftime("%Y-%m-%d")

                # Energy values in CSV are Wh -> convert to kWh
                produced_kwh = float(row.get("produced_energy", 0.0)) / 1000.0
                consumed_kwh = float(row.get("consumed_energy", 0.0)) / 1000.0
                batt_chg_kwh = float(row.get("battery_charged_energy", 0.0)) / 1000.0
                batt_dis_kwh = float(row.get("battery_discharged_energy", 0.0)) / 1000.0
                feedin_kwh = float(row.get("grid_feedin_energy", 0.0)) / 1000.0
                purchase_kwh = float(row.get("grid_purchase_energy", 0.0)) / 1000.0

                day_prices = prices_by_date.get(date_key)
                if day_prices:
                    avg_spot = sum(day_prices) / len(day_prices)
                else:
                    avg_spot = default_spot_price

                # If hourly prices exist, evaluate with diurnal profiles
                if day_prices and len(day_prices) in (23, 24, 25):
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

                        b1_imp_cost += self.tariff.calculate_import_cost(load_h, p_h)

                        sc_h = min(pv_h, load_h)
                        exp_h = max(0.0, pv_h - load_h)
                        imp_h = max(0.0, load_h - pv_h)

                        b2_sc_tot += sc_h
                        b2_exp_tot += exp_h
                        b2_imp_tot += imp_h

                        b2_imp_cost += self.tariff.calculate_import_cost(imp_h, p_h)
                        b2_exp_rev += self.tariff.calculate_export_revenue(exp_h, p_h)

                    act_imp_cost = self.tariff.calculate_import_cost(purchase_kwh, avg_spot)
                    act_exp_rev = self.tariff.calculate_export_revenue(feedin_kwh, avg_spot)
                    act_sc = max(0.0, produced_kwh - feedin_kwh)

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
        months_dict: Dict[int, List[DailyFinancialRecord]] = {}
        for rec in daily_records:
            dt = datetime.strptime(rec.date_str, "%Y-%m-%d")
            m_num = dt.month
            if m_num not in months_dict:
                months_dict[m_num] = []
            months_dict[m_num].append(rec)

        monthly_ledgers: List[MonthlyFinancialLedger] = []
        for m_num in sorted(months_dict.keys()):
            recs = months_dict[m_num]
            m_dt = datetime(self.year, m_num, 1)
            m_name = m_dt.strftime("%B")
            days_count = len(recs)
            months_frac = days_count / 30.4375

            tot_prod = sum(r.produced_kwh for r in recs)
            tot_cons = sum(r.consumed_kwh for r in recs)
            tot_imp = sum(r.imported_kwh for r in recs)
            tot_exp = sum(r.exported_kwh for r in recs)
            tot_chg = sum(r.battery_charged_kwh for r in recs)
            tot_dis = sum(r.battery_discharged_kwh for r in recs)

            avg_spot_sek = sum(r.avg_spot_price_sek_kwh for r in recs) / days_count

            # Fixed monthly fee for the month
            fixed_fee = self.tariff.calculate_fixed_costs(months_frac)

            b1_cost = sum(r.comparison.baseline_no_solar.import_cost_sek for r in recs) + fixed_fee
            b2_cost = (
                sum(r.comparison.baseline_solar_only.import_cost_sek for r in recs)
                - sum(r.comparison.baseline_solar_only.export_revenue_sek for r in recs)
                + fixed_fee
            )
            act_cost = (
                sum(r.comparison.actual_system.import_cost_sek for r in recs)
                - sum(r.comparison.actual_system.export_revenue_sek for r in recs)
                + fixed_fee
            )

            tot_sav = b1_cost - act_cost
            sol_sav = b1_cost - b2_cost
            bat_sav = tot_sav - sol_sav

            batt_eff = (tot_dis / tot_chg * 100.0) if tot_chg > 0 else 0.0
            b2_sc = sum(r.comparison.baseline_solar_only.self_consumed_kwh for r in recs)
            b2_pct = (b2_sc / tot_prod * 100.0) if tot_prod > 0 else 0.0
            act_sc = max(0.0, tot_prod - tot_exp)
            act_pct = (act_sc / tot_prod * 100.0) if tot_prod > 0 else 0.0

            monthly_ledgers.append(
                MonthlyFinancialLedger(
                    month_name=m_name,
                    month_number=m_num,
                    year=self.year,
                    days_count=days_count,
                    produced_kwh=tot_prod,
                    consumed_kwh=tot_cons,
                    imported_kwh=tot_imp,
                    exported_kwh=tot_exp,
                    battery_charged_kwh=tot_chg,
                    battery_discharged_kwh=tot_dis,
                    avg_spot_price_ore_kwh=avg_spot_sek * 100.0,
                    avg_spot_price_sek_kwh=avg_spot_sek,
                    baseline_no_solar_cost_sek=b1_cost,
                    baseline_solar_only_cost_sek=b2_cost,
                    actual_cost_sek=act_cost,
                    fixed_subscription_fee_sek=fixed_fee,
                    total_savings_sek=tot_sav,
                    solar_contribution_sek=sol_sav,
                    battery_marginal_value_sek=bat_sav,
                    battery_roundtrip_efficiency_pct=batt_eff,
                    solar_only_self_consumption_pct=b2_pct,
                    actual_self_consumption_pct=act_pct,
                )
            )

        # Annual Energy Totals
        ann_prod = sum(m.produced_kwh for m in monthly_ledgers)
        ann_cons = sum(m.consumed_kwh for m in monthly_ledgers)
        ann_imp = sum(m.imported_kwh for m in monthly_ledgers)
        ann_exp = sum(m.exported_kwh for m in monthly_ledgers)
        ann_chg = sum(m.battery_charged_kwh for m in monthly_ledgers)
        ann_dis = sum(m.battery_discharged_kwh for m in monthly_ledgers)
        ann_eff = (ann_dis / ann_chg * 100.0) if ann_chg > 0 else 0.0
        ann_sc = max(0.0, ann_prod - ann_exp)
        ann_sc_pct = (ann_sc / ann_prod * 100.0) if ann_prod > 0 else 0.0

        # Annual Financial Totals
        ann_b1 = sum(m.baseline_no_solar_cost_sek for m in monthly_ledgers)
        ann_b2 = sum(m.baseline_solar_only_cost_sek for m in monthly_ledgers)
        ann_act = sum(m.actual_cost_sek for m in monthly_ledgers)
        ann_fix = sum(m.fixed_subscription_fee_sek for m in monthly_ledgers)
        ann_sav = ann_b1 - ann_act
        ann_sol = ann_b1 - ann_b2
        ann_bat = ann_sav - ann_sol

        energy_totals = {
            "produced_kwh": ann_prod,
            "consumed_kwh": ann_cons,
            "imported_kwh": ann_imp,
            "exported_kwh": ann_exp,
            "battery_charged_kwh": ann_chg,
            "battery_discharged_kwh": ann_dis,
            "battery_roundtrip_efficiency_pct": ann_eff,
            "self_consumed_kwh": ann_sc,
            "actual_self_consumption_pct": ann_sc_pct,
        }

        financial_totals = {
            "baseline_no_solar_cost_sek": ann_b1,
            "baseline_solar_only_cost_sek": ann_b2,
            "actual_cost_sek": ann_act,
            "total_fixed_fee_sek": ann_fix,
            "total_savings_sek": ann_sav,
            "solar_contribution_sek": ann_sol,
            "battery_marginal_value_sek": ann_bat,
        }

        capex_metrics = None
        if capex_sek and capex_sek > 0:
            recouped_pct = (ann_sav / capex_sek) * 100.0
            simple_pb = capex_sek / ann_sav if ann_sav > 0 else 999.0
            roi_pct = (ann_sav / capex_sek) * 100.0
            rem_bal = capex_sek - ann_sav

            capex_metrics = CapexPaybackMetrics(
                capex_sek=capex_sek,
                annual_savings_sek=ann_sav,
                solar_contribution_sek=ann_sol,
                battery_marginal_value_sek=ann_bat,
                simple_payback_years=simple_pb,
                annual_roi_pct=roi_pct,
                recouped_pct=recouped_pct,
                remaining_balance_sek=rem_bal,
            )

        return AnnualFinancialReport(
            year=self.year,
            total_days=len(daily_records),
            energy_totals=energy_totals,
            financial_totals=financial_totals,
            monthly_ledgers=monthly_ledgers,
            daily_records=daily_records,
            capex_metrics=capex_metrics,
        )


class MultiYearEngine:
    """Orchestrates multi-year historical analysis and compiles comparative reports."""

    def __init__(
        self,
        data_dir: str,
        prices_dir: str,
        tariff: Optional[SwedishTariff] = None,
        hardware_eras: Optional[List[HardwareEra]] = None,
    ):
        self.data_dir = data_dir
        self.prices_dir = prices_dir
        self.tariff = tariff or SwedishTariff()
        self.hardware_eras = hardware_eras or DEFAULT_HARDWARE_ERAS

    def get_available_years(self) -> List[int]:
        """Find all available full-year CSV files (sonnen_energy_data_{YYYY}.csv) in data directory."""
        years = []
        for filename in os.listdir(self.data_dir):
            if filename.startswith("sonnen_energy_data_") and filename.endswith(".csv"):
                suffix = filename.replace("sonnen_energy_data_", "").replace(".csv", "")
                if suffix.isdigit() and len(suffix) == 4:
                    years.append(int(suffix))
        return sorted(list(set(years)))

    def calculate_all_years(self, net_capex_sek: float = 315000.0) -> Dict[str, Any]:
        """Execute multi-year calculations across all available years."""
        years = self.get_available_years()
        annual_reports: Dict[int, AnnualFinancialReport] = {}

        for y in years:
            csv_path = os.path.join(self.data_dir, f"sonnen_energy_data_{y}.csv")
            price_path = os.path.join(self.prices_dir, f"se3_prices_{y}.json")

            calc = HistoricalYearCalculator(
                year=y,
                data_file=csv_path,
                price_file=price_path if os.path.exists(price_path) else None,
                tariff=self.tariff,
            )
            report = calc.calculate_annual_report(capex_sek=net_capex_sek)
            annual_reports[y] = report
            logging.info("Processed Year %d: %d days, %.1f kWh PV, %.2f SEK savings",
                         y, report.total_days, report.energy_totals["produced_kwh"],
                         report.financial_totals["total_savings_sek"])

        # Compile Multi-Year Summary
        tot_days = sum(r.total_days for r in annual_reports.values())
        tot_prod = sum(r.energy_totals["produced_kwh"] for r in annual_reports.values())
        tot_cons = sum(r.energy_totals["consumed_kwh"] for r in annual_reports.values())
        tot_imp = sum(r.energy_totals["imported_kwh"] for r in annual_reports.values())
        tot_exp = sum(r.energy_totals["exported_kwh"] for r in annual_reports.values())
        tot_chg = sum(r.energy_totals["battery_charged_kwh"] for r in annual_reports.values())
        tot_dis = sum(r.energy_totals["battery_discharged_kwh"] for r in annual_reports.values())
        tot_sav = sum(r.financial_totals["total_savings_sek"] for r in annual_reports.values())
        tot_sol = sum(r.financial_totals["solar_contribution_sek"] for r in annual_reports.values())
        tot_bat = sum(r.financial_totals["battery_marginal_value_sek"] for r in annual_reports.values())

        tot_eff = (tot_dis / tot_chg * 100.0) if tot_chg > 0 else 0.0
        tot_sc = max(0.0, tot_prod - tot_exp)
        tot_sc_pct = (tot_sc / tot_prod * 100.0) if tot_prod > 0 else 0.0

        multi_year_summary = {
            "total_recorded_years": len(years),
            "years_list": years,
            "total_days": tot_days,
            "energy_totals": {
                "produced_kwh": round(tot_prod, 2),
                "consumed_kwh": round(tot_cons, 2),
                "imported_kwh": round(tot_imp, 2),
                "exported_kwh": round(tot_exp, 2),
                "battery_charged_kwh": round(tot_chg, 2),
                "battery_discharged_kwh": round(tot_dis, 2),
                "battery_roundtrip_efficiency_pct": round(tot_eff, 2),
                "self_consumed_kwh": round(tot_sc, 2),
                "actual_self_consumption_pct": round(tot_sc_pct, 2),
            },
            "financial_totals": {
                "total_savings_sek": round(tot_sav, 2),
                "solar_contribution_sek": round(tot_sol, 2),
                "battery_marginal_value_sek": round(tot_bat, 2),
                "recouped_pct": round((tot_sav / net_capex_sek) * 100.0, 2) if net_capex_sek > 0 else 0.0,
                "remaining_balance_sek": round(net_capex_sek - tot_sav, 2),
            },
            "annual_comparison": [
                {
                    "year": y,
                    "days": annual_reports[y].total_days,
                    "produced_kwh": round(annual_reports[y].energy_totals["produced_kwh"], 1),
                    "consumed_kwh": round(annual_reports[y].energy_totals["consumed_kwh"], 1),
                    "imported_kwh": round(annual_reports[y].energy_totals["imported_kwh"], 1),
                    "exported_kwh": round(annual_reports[y].energy_totals["exported_kwh"], 1),
                    "battery_charged_kwh": round(annual_reports[y].energy_totals["battery_charged_kwh"], 1),
                    "battery_discharged_kwh": round(annual_reports[y].energy_totals["battery_discharged_kwh"], 1),
                    "battery_efficiency_pct": round(
                        annual_reports[y].energy_totals["battery_roundtrip_efficiency_pct"], 1
                    ),
                    "no_solar_cost_sek": round(annual_reports[y].financial_totals["baseline_no_solar_cost_sek"], 2),
                    "solar_only_cost_sek": round(annual_reports[y].financial_totals["baseline_solar_only_cost_sek"], 2),
                    "actual_cost_sek": round(annual_reports[y].financial_totals["actual_cost_sek"], 2),
                    "total_savings_sek": round(annual_reports[y].financial_totals["total_savings_sek"], 2),
                    "solar_savings_sek": round(annual_reports[y].financial_totals["solar_contribution_sek"], 2),
                    "battery_savings_sek": round(annual_reports[y].financial_totals["battery_marginal_value_sek"], 2),
                }
                for y in years
            ]
        }

        return {
            "multi_year_summary": multi_year_summary,
            "years": {y: annual_reports[y].to_dict() for y in years},
            "hardware_eras": [
                {
                    "name": e.name,
                    "start_date": e.start_date,
                    "end_date": e.end_date,
                    "solar_capacity_kw": e.solar_capacity_kw,
                    "battery_capacity_kwh": e.battery_capacity_kwh,
                    "battery_modules_count": e.battery_modules_count,
                    "net_capex_sek": e.net_capex_sek,
                    "description": e.description,
                }
                for e in self.hardware_eras
            ],
        }
