#!/usr/bin/env python3
"""CLI utility to calculate high-resolution 30-day ROI, 3-way baselines, and estimation accuracy deltas."""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from src.financial_engine import (
    HighResAnalyzer,
    ResolutionMatcher,
    SonnenHourlyIngestor,
    SwedishTariff,
)
from src.price_providers import PriceManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def format_sek(val: float) -> str:
    """Format SEK amount with thousand separators."""
    return f"{val:10,.2f} SEK"


def format_kwh(val: float) -> str:
    """Format kWh amount."""
    return f"{val:10,.2f} kWh"


def format_pct(val: float) -> str:
    """Format percentage."""
    return f"{val:6.1f} %"


def main():
    parser = argparse.ArgumentParser(
        description="Calculate high-resolution 30-day ROI, 3-way baselines, and variance benchmark."
    )
    parser.add_argument(
        "--data",
        default="data/sonnen_energy_data_Sun_Aug_16_2026.csv",
        help="Path to Sonnen hourly CSV export (default: data/sonnen_energy_data_Sun_Aug_16_2026.csv)",
    )
    parser.add_argument(
        "--prices",
        default=None,
        help="Path to cached spot prices JSON file (optional; will auto-fetch or locate cached file if omitted)",
    )
    parser.add_argument(
        "--zone",
        default="SE3",
        help="Bidding zone (default: SE3)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output JSON file path to save audited report",
    )

    args = parser.parse_args()

    if not os.path.exists(args.data):
        logging.error("Data file not found: %s", args.data)
        sys.exit(1)

    # 1. Ingest Sonnen Hourly Data
    try:
        energy_records = SonnenHourlyIngestor.parse_csv(args.data)
        logging.info("Successfully ingested %d hourly records from %s", len(energy_records), args.data)
    except Exception as e:
        logging.error("Failed to parse energy data: %s", e)
        sys.exit(1)

    start_dt = energy_records[0].timestamp
    end_dt = energy_records[-1].timestamp

    # 2. Retrieve or Load Spot Prices
    price_points = []
    if args.prices and os.path.exists(args.prices):
        price_points = ResolutionMatcher.load_prices_from_json(args.prices)
        logging.info("Loaded %d price points from %s", len(price_points), args.prices)
    else:
        # Check standard cache locations or use PriceManager
        candidate_files = [
            "data/prices/se3_prices_2026_30d.json",
            "data/prices/auto_SE3_20260716_20260816.json",
            "data/prices/entsoe_SE3_20260716_20260816.json",
            "data/prices/se3_prices_2025.json",
        ]
        for cf in candidate_files:
            if os.path.exists(cf):
                pts = ResolutionMatcher.load_prices_from_json(cf)
                if pts and pts[0].timestamp <= end_dt and pts[-1].timestamp >= start_dt:
                    price_points = pts
                    logging.info("Using cached price data from %s (%d points)", cf, len(pts))
                    break

        if not price_points:
            logging.info("Fetching price points via PriceManager for %s to %s...", start_dt.date(), end_dt.date())
            pm = PriceManager()
            price_points = pm.get_prices(
                start_date=start_dt,
                end_date=end_dt,
                bidding_zone=args.zone,
                use_cache=True,
            )

    # 3. Align Energy and Prices
    matched_intervals = ResolutionMatcher.match_hourly_energy_with_prices(
        energy_records=energy_records,
        price_points=price_points,
    )
    logging.info(
        "Aligned %d intervals (Matched price resolution: %d min)",
        len(matched_intervals),
        matched_intervals[0].price_resolution_minutes if matched_intervals else 60,
    )

    # 4. Run High-Resolution Analysis
    analyzer = HighResAnalyzer(tariff=SwedishTariff())
    report = analyzer.analyze_matched_intervals(matched_intervals)

    # 5. Display Formatted Results
    print("\n" + "=" * 78)
    print("      MYSUNSHINE - 30-DAY HIGH-RESOLUTION ROI & BASELINE REPORT")
    print("=" * 78)
    print(f" Period:               {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}")
    print(f" Total Duration:       {report.total_hours} Hours ({report.total_days:.1f} Days)")
    print(f" Price Resolution:     {matched_intervals[0].price_resolution_minutes}-minute intervals (Provider: {matched_intervals[0].provider})")
    print(f" Spot Price SE3:       Avg: {report.avg_spot_price_ore_kwh:6.2f} öre/kWh  [Min: {report.min_spot_price_ore_kwh:5.2f} öre | Max: {report.max_spot_price_ore_kwh:5.2f} öre]")
    print("-" * 78)

    print("\n[1] 30-DAY ENERGY BALANCE & HARDWARE PERFORMANCE")
    print("-" * 78)
    print(f" Solar Generation:       {format_kwh(report.produced_kwh)}")
    print(f" Household Consumption:  {format_kwh(report.consumed_kwh)}")
    print(f" Actual Grid Import:     {format_kwh(report.imported_kwh)}")
    print(f" Actual Grid Export:     {format_kwh(report.exported_kwh)}")
    print(f" Battery Charged:        {format_kwh(report.battery_charged_kwh)}")
    print(f" Battery Discharged:     {format_kwh(report.battery_discharged_kwh)}")
    print(f" Round-Trip Efficiency:  {format_pct(report.battery_roundtrip_efficiency_pct)}")
    print(f" Solar-Only Self-Cons:   {format_pct(report.solar_only_self_consumption_pct)} (Simulated without battery)")
    print(f" Actual Self-Cons:       {format_pct(report.actual_self_consumption_pct)} (Achieved with SonnenBatterie 10)")
    print("-" * 78)

    print("\n[2] 3-WAY COMPARATIVE FINANCIAL LEDGER (30 DAYS)")
    print("-" * 78)
    print(f"{'Scenario / Baseline':<35} | {'Import Cost':>12} | {'Export Rev':>11} | {'Net Cost':>11}")
    print("-" * 78)
    b1 = report.baseline_no_solar
    b2 = report.baseline_solar_only
    act = report.actual_system
    print(f"{b1.name:<35} | {b1.import_cost_sek:9.2f} SEK | {b1.export_revenue_sek:8.2f} SEK | {b1.net_cost_sek:8.2f} SEK")
    print(f"{b2.name:<35} | {b2.import_cost_sek:9.2f} SEK | {b2.export_revenue_sek:8.2f} SEK | {b2.net_cost_sek:8.2f} SEK")
    print(f"{act.name:<35} | {act.import_cost_sek:9.2f} SEK | {act.export_revenue_sek:8.2f} SEK | {act.net_cost_sek:8.2f} SEK")
    print("-" * 78)
    print(f" TOTAL REALIZED SAVINGS (vs No Solar):       {format_sek(report.total_savings_sek)}")
    print(f" -> Solar Panels Contribution:               {format_sek(report.solar_contribution_sek)}")
    print(f" -> SonnenBatterie 10 Marginal Contribution: {format_sek(report.battery_marginal_value_sek)}")
    print("-" * 78)

    # 6. Variance Analysis Benchmarks
    print("\n[3] ESTIMATION ACCURACY BENCHMARK & VARIANCE ANALYSIS")
    print("-" * 78)
    print("Comparison: Exact High-Res Settlement vs Estimation Methods")
    print("-" * 78)

    if report.daily_averaged_variance:
        print(f"\nMethod A: {report.daily_averaged_variance.method_name}")
        print(f"{'Financial Metric':<32} | {'Exact High-Res':>13} | {'Estimated':>11} | {'Delta SEK':>10} | {'Error %':>7}")
        print("-" * 84)
        for m in report.daily_averaged_variance.metrics:
            print(f"{m.metric_name:<32} | {m.exact_sek:10.2f} SEK | {m.estimated_sek:8.2f} SEK | {m.delta_sek:7.2f} SEK | {m.percentage_error:6.1f} %")
        print(f" Average Absolute Error: {report.daily_averaged_variance.avg_absolute_error_sek:.2f} SEK (RMSE: {report.daily_averaged_variance.root_mean_square_error_sek:.2f} SEK)")

    if report.synthetic_weighted_variance:
        print(f"\nMethod B: {report.synthetic_weighted_variance.method_name}")
        print(f"{'Financial Metric':<32} | {'Exact High-Res':>13} | {'Estimated':>11} | {'Delta SEK':>10} | {'Error %':>7}")
        print("-" * 84)
        for m in report.synthetic_weighted_variance.metrics:
            print(f"{m.metric_name:<32} | {m.exact_sek:10.2f} SEK | {m.estimated_sek:8.2f} SEK | {m.delta_sek:7.2f} SEK | {m.percentage_error:6.1f} %")
        print(f" Average Absolute Error: {report.synthetic_weighted_variance.avg_absolute_error_sek:.2f} SEK (RMSE: {report.synthetic_weighted_variance.root_mean_square_error_sek:.2f} SEK)")

    print("\n" + "=" * 78)

    # 7. Output JSON if requested
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nSaved audited 30-day report to {args.output}")


if __name__ == "__main__":
    main()
