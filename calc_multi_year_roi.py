#!/usr/bin/env python3
"""CLI utility to calculate Multi-Year Solar & Battery ROI and 3-Way Comparative Baselines."""

import argparse
import json
import os
import sys

from src.financial_engine import (
    MultiYearEngine,
    SwedishTariff,
    TariffConfig,
)


def format_currency(amount: float) -> str:
    """Format SEK amount with comma separation and 2 decimals."""
    return f"{amount:12,.2f} SEK"


def main():
    parser = argparse.ArgumentParser(
        description="Calculate Multi-Year (2023-2025) Solar & Battery ROI and Baselines."
    )
    parser.add_argument(
        "--year",
        type=int,
        choices=[2023, 2024, 2025, 2026],
        default=None,
        help="Specific year to calculate (default: all available years)",
    )
    parser.add_argument(
        "--capex",
        type=float,
        default=315000.0,
        help="Net Capex investment in SEK (default: 315,000 SEK)",
    )
    parser.add_argument(
        "--no-tax-reduction",
        action="store_true",
        help="Disable 60 öre/kWh skattereduktion microproduction tax reduction",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Save calculated multi-year report to JSON file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON to stdout",
    )

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    tariff_config = TariffConfig(
        enable_tax_reduction=not args.no_tax_reduction,
    )
    tariff = SwedishTariff(config=tariff_config)

    engine = MultiYearEngine(
        data_dir=data_dir,
        prices_dir=prices_dir,
        tariff=tariff,
    )

    results = engine.calculate_all_years(net_capex_sek=args.capex)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Report saved to {args.output}")

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if args.year:
        yr_data = results["years"].get(args.year)
        if not yr_data:
            print(f"Error: No data available for year {args.year}", file=sys.stderr)
            sys.exit(1)

        print("=" * 75)
        print(f"           MYSUNSHINE: YEAR {args.year} HISTORICAL ROI REPORT")
        print("=" * 75)
        print(f"Recorded Days:           {yr_data['total_days']} days")
        print(f"Solar Generation:        {yr_data['energy_totals']['produced_kwh']:,.1f} kWh")
        print(f"Household Consumption:   {yr_data['energy_totals']['consumed_kwh']:,.1f} kWh")
        print(f"Grid Import:             {yr_data['energy_totals']['imported_kwh']:,.1f} kWh")
        print(f"Grid Export:             {yr_data['energy_totals']['exported_kwh']:,.1f} kWh")
        print(f"Battery Roundtrip Eff:   {yr_data['energy_totals']['battery_roundtrip_efficiency_pct']:.1f}%")
        print("-" * 75)
        print(f"{'Month':<12} {'Solar kWh':<10} {'No Solar Cost':<16} {'Actual Cost':<16} {'Savings (SEK)'}")
        print("-" * 75)
        for m in yr_data.get("monthly_ledgers", []):
            month_label = m.get("month", m.get("month_name", ""))
            print(
                f"{month_label:<12} {m['produced_kwh']:<10,.1f} "
                f"{format_currency(m.get('baseline_no_solar_cost_sek', m.get('baseline_no_solar_sek', 0.0))):<16} "
                f"{format_currency(m.get('actual_cost_sek', 0.0)):<16} "
                f"{format_currency(m.get('total_savings_sek', 0.0))}"
            )
        print("-" * 75)
        tot_sav_str = format_currency(yr_data['financial_totals']['total_savings_sek'])
        sol_sav_str = format_currency(yr_data['financial_totals']['solar_contribution_sek'])
        bat_sav_str = format_currency(yr_data['financial_totals']['battery_marginal_value_sek'])
        print(f"Total Year {args.year} Realized Savings:  {tot_sav_str}")
        print(f"Solar PV Direct Savings:          {sol_sav_str}")
        print(f"SonnenBattery Marginal Value:     {bat_sav_str}")
        print("=" * 75)
        return

    summary = results["multi_year_summary"]
    print("=" * 70)
    print("           MYSUNSHINE: MULTI-YEAR HISTORICAL ROI REPORT")
    print("=" * 70)
    print(f"Recorded Years:          {', '.join(str(y) for y in summary['years_list'])}")
    print(f"Total Recorded Days:     {summary['total_days']} days")
    print(f"Total Solar Generation:  {summary['energy_totals']['produced_kwh']:,.1f} kWh")
    print(f"Total Consumption:       {summary['energy_totals']['consumed_kwh']:,.1f} kWh")
    print(f"Total Grid Import:       {summary['energy_totals']['imported_kwh']:,.1f} kWh")
    print(f"Total Grid Export:       {summary['energy_totals']['exported_kwh']:,.1f} kWh")
    print(f"Battery Roundtrip Eff:   {summary['energy_totals']['battery_roundtrip_efficiency_pct']:.1f}%")
    print("-" * 70)
    print("ANNUAL COMPARISON SUMMARY:")
    print(f"{'Year':<6} {'Days':<6} {'Solar kWh':<12} {'Actual Cost':<16} {'Savings (SEK)':<16} {'Battery Val'}")
    print("-" * 70)
    for ac in summary["annual_comparison"]:
        print(
            f"{ac['year']:<6} {ac['days']:<6} {ac['produced_kwh']:<12,.1f} "
            f"{format_currency(ac['actual_cost_sek']):<16} "
            f"{format_currency(ac['total_savings_sek']):<16} "
            f"{format_currency(ac['battery_savings_sek'])}"
        )
    print("-" * 70)
    tot_cum_sav = format_currency(summary['financial_totals']['total_savings_sek'])
    rem_bal_str = format_currency(summary['financial_totals']['remaining_balance_sek'])
    print(f"Cumulative Total Realized Savings:  {tot_cum_sav}")
    print(f"Net Capex Investment:               {format_currency(args.capex)}")
    print(f"Recouped Investment:                {summary['financial_totals']['recouped_pct']:.1f}%")
    print(f"Remaining Balance to Break-Even:    {rem_bal_str}")
    print("=" * 70)


if __name__ == "__main__":
    main()
