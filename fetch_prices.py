#!/usr/bin/env python3
"""CLI utility to fetch, inspect, and export electricity spot prices."""

import argparse
import json
import logging
import sys
from datetime import datetime

from src.price_providers import PriceManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def parse_date(date_str: str) -> datetime:
    """Parse YYYY-MM-DD or ISO-8601 string to datetime."""
    try:
        if len(date_str) == 10:
            return datetime.strptime(date_str, "%Y-%m-%d")
        return datetime.fromisoformat(date_str)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date format '{date_str}': {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch electricity spot prices for Nordic bidding zones (e.g. SE3)."
    )
    parser.add_argument(
        "--start",
        required=True,
        type=parse_date,
        help="Start date (YYYY-MM-DD or ISO format)",
    )
    parser.add_argument(
        "--end",
        required=True,
        type=parse_date,
        help="End date (YYYY-MM-DD or ISO format)",
    )
    parser.add_argument(
        "--zone",
        default="SE3",
        help="Bidding zone (default: SE3)",
    )
    parser.add_argument(
        "--provider",
        default=None,
        choices=["elering", "entsoe", "tibber", "energy_charts", "elprisetjustnu"],
        help="Specific provider to query (default: auto fallback)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cache and force fetch from remote API",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output JSON file path to save results",
    )

    args = parser.parse_args()

    manager = PriceManager()
    try:
        prices = manager.get_prices(
            start_date=args.start,
            end_date=args.end,
            bidding_zone=args.zone,
            provider_name=args.provider,
            use_cache=not args.no_cache,
        )
    except Exception as e:
        logging.error("Failed to fetch prices: %s", e)
        sys.exit(1)

    if not prices:
        logging.warning("No price points returned for the specified range.")
        return

    # Compute summary metrics
    ore_prices = [p.price_ore_kwh for p in prices]
    avg_ore = sum(ore_prices) / len(ore_prices)
    min_ore = min(ore_prices)
    max_ore = max(ore_prices)

    print("\n" + "=" * 60)
    print(f"Electricity Spot Price Summary: {args.zone.upper()}")
    print(f"Period:       {args.start.strftime('%Y-%m-%d')} to {args.end.strftime('%Y-%m-%d')}")
    print(f"Data Points:  {len(prices)} ({prices[0].resolution_minutes}-minute resolution)")
    print(f"Provider:     {prices[0].provider}")
    print("-" * 60)
    print(f"Average Price: {avg_ore:8.2f} öre/kWh  ({(avg_ore / 100):.4f} SEK/kWh)")
    print(f"Minimum Price: {min_ore:8.2f} öre/kWh  ({(min_ore / 100):.4f} SEK/kWh)")
    print(f"Maximum Price: {max_ore:8.2f} öre/kWh  ({(max_ore / 100):.4f} SEK/kWh)")
    print("=" * 60 + "\n")

    # Display sample records
    print("Sample Records:")
    sample_records = prices[:3] + (prices[-3:] if len(prices) > 6 else [])
    for p in sample_records:
        print(f"  {p.timestamp} | {p.price_eur_mwh:6.2f} EUR/MWh | {p.price_ore_kwh:6.2f} öre/kWh ({p.provider})")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in prices], f, indent=2)
        print(f"\nSaved {len(prices)} price points to {args.output}")


if __name__ == "__main__":
    main()
