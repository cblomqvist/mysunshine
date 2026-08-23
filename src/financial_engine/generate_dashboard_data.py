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
from .calculator_2025 import Year2025Calculator
from .multi_res import ResolutionMatcher, SonnenHourlyIngestor
from .tariff import SwedishTariff, TariffConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def generate_dashboard_dataset() -> Dict[str, Any]:
    """Compile full 2025 annual data and 30-day high-resolution dispatch data."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data")

    # 1. 2025 Annual Financial Report
    sonnen_2025_csv = os.path.join(data_dir, "sonnen_energy_data_2025.csv")
    se3_2025_prices_json = os.path.join(data_dir, "prices", "se3_prices_2025.json")

    logging.info("Calculating 2025 full-year ROI and 3-way baseline...")
    tariff = SwedishTariff(config=TariffConfig())
    calc_2025 = Year2025Calculator(
        tariff=tariff,
        data_file=sonnen_2025_csv,
        price_file=se3_2025_prices_json if os.path.exists(se3_2025_prices_json) else None,
    )
    report_2025 = calc_2025.calculate_2025_report(capex_sek=315000.0)

    # 2. 30-Day High Resolution Ingestion and Analysis
    sonnen_30d_csv = os.path.join(data_dir, "sonnen_energy_data_Sun_Aug_16_2026.csv")
    prices_30d_candidates = [
        os.path.join(data_dir, "prices", "auto_SE3_20260716_20260816.json"),
        os.path.join(data_dir, "prices", "entsoe_SE3_20260716_20260816.json"),
        os.path.join(data_dir, "prices", "se3_prices_2025.json"),
    ]
    price_file_30d = None
    for pfc in prices_30d_candidates:
        if os.path.exists(pfc):
            price_file_30d = pfc
            break

    logging.info("Ingesting 30-day hourly Sonnen logs from %s...", sonnen_30d_csv)
    energy_records = SonnenHourlyIngestor.parse_csv(sonnen_30d_csv)
    price_points = ResolutionMatcher.load_prices_from_json(price_file_30d) if price_file_30d else []

    logging.info("Matching multi-resolution hourly/quarterly intervals...")
    matched_intervals = ResolutionMatcher.match_hourly_energy_with_prices(energy_records, price_points)

    analyzer_30d = HighResAnalyzer(tariff=tariff)
    report_30d = analyzer_30d.analyze_matched_intervals(matched_intervals)
    report_30d_dict = report_30d.to_dict()

    # Compute battery SoC progression for the 30 days (assuming initial ~50% / 10 kWh SoC)
    # SonnenBatterie 10: 20 kWh usable capacity
    battery_capacity_kwh = 20.0
    current_soc_kwh = 10.0  # Initial SoC start estimate

    hourly_records_list: List[Dict[str, Any]] = []
    days_dict: Dict[str, List[Dict[str, Any]]] = {}

    for interval in matched_intervals:
        en = interval.energy
        # Update SoC based on battery charge and discharge
        charge = en.battery_charged_kwh
        discharge = en.battery_discharged_kwh
        current_soc_kwh = max(0.0, min(battery_capacity_kwh, current_soc_kwh + charge - discharge))
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

    dataset: Dict[str, Any] = {
        "metadata": {
            "app": "MySunshine",
            "version": "1.0.0",
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
        "year_2025": report_2025.to_dict(),
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
