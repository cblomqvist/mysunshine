#!/usr/bin/env python3
"""CLI utility to calculate 2025 Full-Year ROI, 3-Way Baselines, and Capex Payback."""

import argparse
import json
import os
import sys

from src.financial_engine import (
    SwedishTariff,
    TariffConfig,
    Year2025Calculator,
)


def format_currency(amount: float) -> str:
    """Format SEK amount with comma separation and 2 decimals."""
    return f"{amount:12,.2f} SEK"


def main():
    parser = argparse.ArgumentParser(
        description="Calculate 2025 Full-Year Solar & Battery ROI and 3-Way Baselines."
    )
    parser.add_argument(
        "--capex",
        type=float,
        default=None,
        help="Net Capex investment in SEK (e.g. after Grön Teknik deduction)",
    )
    parser.add_argument(
        "--data",
        default="data/sonnen_energy_data_2025.csv",
        help="Path to Sonnen historical CSV data file (default: data/sonnen_energy_data_2025.csv)",
    )
    parser.add_argument(
        "--prices",
        default="data/prices/se3_prices_2025.json",
        help="Path to SE3 spot prices JSON file (default: data/prices/se3_prices_2025.json)",
    )
    parser.add_argument(
        "--monthly",
        action="store_true",
        help="Display detailed month-by-month financial ledger table",
    )
    parser.add_argument(
        "--no-tax-reduction",
        action="store_true",
        help="Disable 60 öre/kWh skattereduktion microproduction tax reduction",
    )
    parser.add_argument(
        "--energiskatt",
        type=float,
        default=0.428,
        help="Swedish energy tax in SEK/kWh ex moms (default: 0.428)",
    )
    parser.add_argument(
        "--eem-transfer",
        type=float,
        default=0.176,
        help="EEM överföringsavgift in SEK/kWh ex moms (default: 0.176)",
    )
    parser.add_argument(
        "--tibber-fee",
        type=float,
        default=49.0,
        help="Tibber monthly subscription fee in SEK incl moms (default: 49.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON results to standard output",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Save report as JSON to specified file path",
    )

    args = parser.parse_args()

    # Configure Swedish Tariff
    tariff_config = TariffConfig(
        energiskatt_sek_per_kwh=args.energiskatt,
        eem_transfer_fee_sek_per_kwh=args.eem_transfer,
        enable_tax_reduction=not args.no_tax_reduction,
        tibber_monthly_fee_sek=args.tibber_fee,
    )
    tariff = SwedishTariff(config=tariff_config)

    # Initialize Calculator
    calculator = Year2025Calculator(
        tariff=tariff,
        data_file=args.data,
        price_file=args.prices if os.path.exists(args.prices) else None,
    )

    try:
        report = calculator.calculate_2025_report(capex_sek=args.capex)
    except Exception as e:
        print(f"Error calculating 2025 ROI report: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return

    # Print Formatted CLI Report
    print("\n" + "=" * 78)
    print("       MySunshine: 2025 Full-Year ROI & 3-Way Baseline Financial Report")
    print("       Bidding Zone: SE3 | Retailer: Tibber | Grid Operator: EEM")
    print("=" * 78)

    e_tot = report.energy_totals
    f_tot = report.financial_totals

    print("\n[1] 2025 Physical Energy Balance Summary (365 Days)")
    print("-" * 78)
    print(f"  Solar PV Generation:      {e_tot['produced_kwh']:10.1f} kWh")
    print(f"  Household Load Consumed:  {e_tot['consumed_kwh']:10.1f} kWh")
    print(f"  Grid Purchase (Import):   {e_tot['imported_kwh']:10.1f} kWh")
    print(f"  Grid Feed-in (Export):    {e_tot['exported_kwh']:10.1f} kWh")
    print(f"  Battery Charged Energy:   {e_tot['battery_charged_kwh']:10.1f} kWh")
    print(f"  Battery Discharged Energy:{e_tot['battery_discharged_kwh']:10.1f} kWh")
    print(f"  Battery Roundtrip Eff.:   {e_tot['battery_roundtrip_efficiency_pct']:10.1f} %")
    print(f"  Solar Self-Consumption:   {e_tot['actual_self_consumption_pct']:10.1f} %")

    print("\n[2] 3-Way Comparative Financial Baselines (Full Year 2025)")
    print("-" * 78)
    print(f"  Baseline 1 (No Solar, No Battery): {format_currency(f_tot['baseline_no_solar_cost_sek'])}")
    print(f"  Baseline 2 (Solar Only, No Battery):{format_currency(f_tot['baseline_solar_only_cost_sek'])}")
    print(f"  Actual Bill (Solar + Sonnen 10):    {format_currency(f_tot['actual_cost_sek'])}")
    print("-" * 78)
    print(f"  Total Realized Savings:             {format_currency(f_tot['total_savings_sek'])}  (vs. No Solar)")
    print(f"    - Solar Panels Contribution:      {format_currency(f_tot['solar_contribution_sek'])}")
    print(f"    - SonnenBatterie 10 Marginal Val: {format_currency(f_tot['battery_marginal_value_sek'])}")

    if args.monthly:
        print("\n[3] Month-by-Month Financial Ledger Breakdown")
        print("-" * 115)
        hdr = (
            f"{'Month':<10} | {'PV (kWh)':<8} | {'Load':<8} | {'Spot (öre)':<10} | "
            f"{'No Solar':<12} | {'Solar Only':<12} | {'Actual':<12} | {'Total Sav':<12} | {'Battery Val':<12}"
        )
        print(hdr)
        print("-" * 115)
        for m in report.monthly_ledgers:
            line = (
                f"{m.month_name:<10} | "
                f"{m.produced_kwh:8.1f} | "
                f"{m.consumed_kwh:8.1f} | "
                f"{m.avg_spot_price_ore_kwh:10.1f} | "
                f"{m.baseline_no_solar_cost_sek:12.2f} | "
                f"{m.baseline_solar_only_cost_sek:12.2f} | "
                f"{m.actual_cost_sek:12.2f} | "
                f"{m.total_savings_sek:12.2f} | "
                f"{m.battery_marginal_value_sek:12.2f}"
            )
            print(line)
        print("-" * 115)

    if report.capex_metrics:
        cm = report.capex_metrics
        print("\n[4] Capex & Payback Analysis")
        print("-" * 78)
        print(f"  Net Capex Investment:              {format_currency(cm.capex_sek)}")
        print(f"  Recouped to Date (2025):            {cm.recouped_pct:10.2f} %  ({format_currency(cm.annual_savings_sek).strip()})")
        print(f"  Remaining Unrecovered Balance:      {format_currency(cm.remaining_balance_sek)}")
        print(f"  Simple Payback Period:              {cm.simple_payback_years:10.1f} years")
        if cm.break_even_year:
            print(f"  Estimated Break-Even Year:          {cm.break_even_year:10.1f} years (with 2% inflation)")
        print(f"  Annual Return on Investment (ROI):  {cm.annual_roi_pct:10.2f} %")

    print("=" * 78 + "\n")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Full financial report saved to: {args.output}\n")


if __name__ == "__main__":
    main()
