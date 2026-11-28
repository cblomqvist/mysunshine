"""Generate consolidated static dashboard data package for MySunshine web UI.

Bakes 2025 full-year baseline reports, 30-day high-resolution hourly dispatch time-series,
and variance benchmarks into data/dashboard_data.json and data/dashboard_data.js.
Ensures zero-secret client runtime deployment.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from .analyzer_30d import HighResAnalyzer
from .multi_res import ResolutionMatcher, SonnenHourlyIngestor
from .multi_year import MultiYearEngine
from .tariff import SwedishTariff, TariffConfig
from .tariff_audit import UtilityTariffAuditor
from ..forecast_engine import ShadowBacktester
from ..ha_integration import HomeAssistantTelemetryBridge

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def generate_dashboard_dataset() -> Dict[str, Any]:
    """Compile multi-year historical data (2023, 2024, 2025) and 30-day high-res dispatch data."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    # 1. Multi-Year Historical Financial Engine (2023, 2024, 2025)
    logging.info("Executing Multi-Year Historical Engine (2023, 2024, 2025)...")
    tariff = SwedishTariff(config=TariffConfig())
    multi_year_engine = MultiYearEngine(
        data_dir=data_dir,
        prices_dir=prices_dir,
        tariff=tariff,
    )
    multi_year_results = multi_year_engine.calculate_all_years(net_capex_sek=315000.0)
    report_2025_dict = multi_year_results["years"].get(2025, {})

    # 2. High Resolution Ingestion and Analysis (All Available Hourly Logs)
    hourly_files = SonnenHourlyIngestor.find_hourly_files(data_dir)
    logging.info("Ingesting %d high-resolution hourly Sonnen files from %s...", len(hourly_files), data_dir)
    energy_records = SonnenHourlyIngestor.parse_directory(data_dir)

    prices_candidates = [
        os.path.join(data_dir, "prices", "se3_prices_2026.json"),
        os.path.join(data_dir, "prices", "auto_SE3_20260716_20260816.json"),
        os.path.join(data_dir, "prices", "entsoe_SE3_20260716_20260816.json"),
        os.path.join(data_dir, "prices", "se3_prices_2025.json"),
    ]
    price_file_highres = None
    for pfc in prices_candidates:
        if os.path.exists(pfc):
            price_file_highres = pfc
            break

    price_points = ResolutionMatcher.load_prices_from_json(price_file_highres) if price_file_highres else []
    logging.info("Loaded %d price points from %s", len(price_points), price_file_highres)

    logging.info("Matching multi-resolution hourly/quarterly intervals (%d energy records)...", len(energy_records))
    matched_intervals = ResolutionMatcher.match_hourly_energy_with_prices(energy_records, price_points)

    analyzer_30d = HighResAnalyzer(tariff=tariff)
    report_30d = analyzer_30d.analyze_matched_intervals(matched_intervals)
    report_30d_dict = report_30d.to_dict()

    # Compute battery User SoC (USOC, 0-100% usable capacity, excluding hardware deep-discharge reserve)
    # SonnenBatterie 10: 22 kWh nominal -> 20.0 kWh usable capacity (0% USOC in Sonnen app = ~7% RSOC reserve).
    # Why raw (charge - discharge) integration drifted to ~26.8% on Nov 26:
    #   1. Sonnen's CSV reports AC-side `battery_charged_energy` (into inverter) and `battery_discharged_energy` (out of inverter).
    #      Because roundtrip efficiency is ~76.8% (one-way ~87.6% each way) and the BMS draws ~40-45W standby/keep-alive
    #      plus periodic ~195 Wh protective reserve top-ups when sitting at 0% USOC, summing raw (charge - discharge)
    #      without efficiency weighting accumulates ~23% phantom energy over a charge/discharge cycle.
    #   2. When the home has significant unmet load (grid_purchase > 0.25 kWh) and the battery stops discharging
    #      (discharge == 0 while in standard Self-Consumption mode), the battery has hit its 0% USOC floor.
    battery_capacity_kwh = 20.0
    tot_chg_all = sum(i.energy.battery_charged_kwh for i in matched_intervals)
    tot_dis_all = sum(i.energy.battery_discharged_kwh for i in matched_intervals)
    empirical_eta = (tot_dis_all / tot_chg_all) if tot_chg_all > 0 else 0.7685
    # Split roundtrip efficiency into charge efficiency and discharge efficiency (sqrt(eta) ~ 87.66%)
    one_way_eff = empirical_eta ** 0.5
    current_soc_kwh = 0.0  # Start from 0% USOC and calibrate with physical empty/full boundary anchors

    hourly_records_list: List[Dict[str, Any]] = []
    days_dict: Dict[str, List[Dict[str, Any]]] = {}

    for interval in matched_intervals:
        en = interval.energy
        charge = en.battery_charged_kwh
        discharge = en.battery_discharged_kwh
        grid_imp = en.grid_purchase_kwh
        load = en.consumed_kwh

        # Check if this hour is just a protective BMS reserve trickle / maintenance pulse while sitting at 0% USOC:
        # e.g., in winter when battery was already at 0% USOC, solar is 0, and BMS pulls ~195 Wh from grid to keep reserve above min voltage.
        is_bms_reserve_maintenance = (
            current_soc_kwh <= 0.05
            and en.produced_kwh < 0.02
            and charge <= 0.22
            and discharge == 0.0
            and grid_imp >= load
        )

        if is_bms_reserve_maintenance:
            # Protective BMS reserve top-up goes into the hidden 7% hardware reserve, not usable USOC
            current_soc_kwh = 0.0
        else:
            # Apply one-way conversion efficiency to AC charge going in and AC discharge coming out
            net_usable_delta_kwh = (charge * one_way_eff) - (discharge / one_way_eff)
            current_soc_kwh = max(0.0, min(battery_capacity_kwh, current_soc_kwh + net_usable_delta_kwh))

            # Physical 0% USOC floor anchor: if the battery stops discharging completely while the home
            # is forced to import > 0.30 kWh from the grid and no standby top-up at 100% is occurring,
            # usable SoC is exhausted (0% USOC).
            if discharge == 0.0 and charge < 0.03 and grid_imp > 0.30 and current_soc_kwh < 18.0:
                current_soc_kwh = 0.0

        soc_pct = (current_soc_kwh / battery_capacity_kwh) * 100.0

        ts_iso = en.timestamp.isoformat()
        date_str = en.timestamp.strftime("%Y-%m-%d")
        hour_int = en.timestamp.hour
        spot_price_ore = round(interval.spot_price_sek_kwh * 100.0, 2)

        record_item = {
            "timestamp": ts_iso,
            "date": date_str,
            "hour": hour_int,
            "produced_kw": round(en.produced_kwh, 3),
            "consumed_kw": round(en.consumed_kwh, 3),
            "battery_charged_kw": round(en.battery_charged_kwh, 3),
            "battery_discharged_kw": round(en.battery_discharged_kwh, 3),
            "battery_soc_kwh": round(current_soc_kwh, 2),
            "battery_soc_pct": round(soc_pct, 1),
            "grid_import_kw": round(en.grid_purchase_kwh, 3),
            "grid_export_kw": round(en.grid_feedin_kwh, 3),
            "spot_price_sek": round(interval.spot_price_sek_kwh, 4),
            "spot_price_ore": spot_price_ore,
            "price_resolution_min": interval.price_resolution_minutes,
        }
        hourly_records_list.append(record_item)

        if date_str not in days_dict:
            days_dict[date_str] = []
        days_dict[date_str].append(record_item)

    # Compile day summaries
    days_summary = []
    for d_str, hours in days_dict.items():
        tot_gen = sum(h["produced_kw"] for h in hours)
        tot_load = sum(h["consumed_kw"] for h in hours)
        tot_import = sum(h["grid_import_kw"] for h in hours)
        tot_export = sum(h["grid_export_kw"] for h in hours)
        avg_price = sum(h["spot_price_ore"] for h in hours) / len(hours)
        max_price = max(h["spot_price_ore"] for h in hours)
        min_price = min(h["spot_price_ore"] for h in hours)

        days_summary.append({
            "date": d_str,
            "display_name": datetime.strptime(d_str, "%Y-%m-%d").strftime("%b %d, %Y"),
            "total_produced_kwh": round(tot_gen, 2),
            "total_consumed_kwh": round(tot_load, 2),
            "total_import_kwh": round(tot_import, 2),
            "total_export_kwh": round(tot_export, 2),
            "avg_spot_price_ore": round(avg_price, 2),
            "max_spot_price_ore": round(max_price, 2),
            "min_spot_price_ore": round(min_price, 2),
            "hours_count": len(hours),
        })

    # Find interesting featured days for quick selection
    # 1. Peak Solar Day
    peak_solar_day = max(days_summary, key=lambda x: x["total_produced_kwh"])["date"]
    # 2. Peak Price Volatility Day (max - min spot price)
    peak_volatility_day = max(days_summary, key=lambda x: (x["max_spot_price_ore"] - x["min_spot_price_ore"]))["date"]
    # 3. Cloudy / High Grid Dependency Day
    cloudy_day = min(days_summary, key=lambda x: x["total_produced_kwh"])["date"]

    # 3. Utility Tariff & Invoicing Audit (Milestone 5.5.4)
    logging.info("Executing Utility Tariff & Invoicing Audit (2024-2026)...")
    tariff_auditor = UtilityTariffAuditor(data_dir=data_dir, baseline_tariff=tariff)
    tariff_audit_report = tariff_auditor.run_audit().to_dict()

    # 4. Next-Day Forecast & Shadow Mode Recommendation Engine + 121-Day Backtest (Milestone 6)
    logging.info("Executing Milestone 6 Next-Day Forecast & 121-Day Shadow Advisor Backtest...")
    shadow_backtester = ShadowBacktester(tariff=tariff)
    next_day_forecast_pkg = shadow_backtester.build_next_day_dashboard_package(
        price_points=price_points,
        matched_intervals=matched_intervals,
        target_date="2026-11-15",
    )

    # 5. Home Assistant Custom Sensor Integration & Live Shadow Telemetry Bridge (Milestone 7)
    logging.info("Building Milestone 7 Home Assistant Custom Sensor & Shadow Telemetry Package...")
    ha_bridge = HomeAssistantTelemetryBridge()
    ha_state_pkg = ha_bridge.build_state_package(
        multi_year_summary=multi_year_results["multi_year_summary"],
        next_day_forecast_pkg=next_day_forecast_pkg,
        utility_audit_report=tariff_audit_report,
    ).to_dict()

    dataset: Dict[str, Any] = {
        "metadata": {
            "app": "MySunshine",
            "version": "1.2.0",
            "generated_at": datetime.now().isoformat(),
            "bidding_zone": "SE3",
            "retailer": "Tibber",
            "grid_operator": "Eskilstuna Energi & Miljö (EEM)",
            "hardware": {
                "inverter": "SMA STP8.0-3AV-40 (8.0 kW)",
                "battery": "SonnenBatterie 10 (20 kWh usable, ~77% roundtrip efficiency)",
            },
            "featured_days": {
                "peak_solar": peak_solar_day,
                "peak_volatility": peak_volatility_day,
                "cloudy_day": cloudy_day,
            }
        },
        "multi_year": multi_year_results["multi_year_summary"],
        "years": multi_year_results["years"],
        "hardware_eras": multi_year_results["hardware_eras"],
        "year_2025": report_2025_dict,
        "utility_tariff_audit": tariff_audit_report,
        "next_day_forecast": next_day_forecast_pkg,
        "ha_integration": ha_state_pkg,
        "high_res_30d": {
            **report_30d_dict,
            "days_list": days_summary,
            "hourly_data": hourly_records_list,
        }
    }
    return dataset


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    dataset = generate_dashboard_dataset()

    json_path = os.path.join(data_dir, "dashboard_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    logging.info("Saved dashboard JSON dataset to: %s (%d KB)", json_path, os.path.getsize(json_path) // 1024)

    js_path = os.path.join(data_dir, "dashboard_data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("// Auto-generated static baked data package for MySunshine Dashboard\n")
        f.write("window.MYSUNSHINE_DATA = ")
        json.dump(dataset, f, indent=2)
        f.write(";\n")
    logging.info("Saved dashboard JS dataset to: %s (%d KB)", js_path, os.path.getsize(js_path) // 1024)


if __name__ == "__main__":
    main()
