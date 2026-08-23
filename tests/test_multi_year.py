import os
from src.financial_engine.multi_year import (
    HistoricalYearCalculator,
    MultiYearEngine,
)


def test_get_available_years():
    """Verify that MultiYearEngine discovers 2023, 2024, and 2025 dataset files."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    engine = MultiYearEngine(data_dir=data_dir, prices_dir=prices_dir)
    years = engine.get_available_years()

    assert 2023 in years
    assert 2024 in years
    assert 2025 in years
    assert len(years) == 3


def test_historical_year_2023_partial():
    """Verify that 2023 partial year (110 days from Sep 13) calculates properly."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    calc = HistoricalYearCalculator(
        year=2023,
        data_file=os.path.join(data_dir, "sonnen_energy_data_2023.csv"),
        price_file=os.path.join(prices_dir, "se3_prices_2023.json"),
    )
    report = calc.calculate_annual_report(capex_sek=315000.0)

    assert report.year == 2023
    assert report.total_days == 110
    assert report.energy_totals["produced_kwh"] > 900
    assert report.financial_totals["total_savings_sek"] > 0
    assert len(report.monthly_ledgers) == 4  # Sep, Oct, Nov, Dec


def test_historical_year_2024_full_leap():
    """Verify that 2024 leap year (366 days) calculates properly."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    calc = HistoricalYearCalculator(
        year=2024,
        data_file=os.path.join(data_dir, "sonnen_energy_data_2024.csv"),
        price_file=os.path.join(prices_dir, "se3_prices_2024.json"),
    )
    report = calc.calculate_annual_report(capex_sek=315000.0)

    assert report.year == 2024
    assert report.total_days == 366
    assert report.energy_totals["produced_kwh"] > 8000
    assert report.financial_totals["total_savings_sek"] > 0
    assert len(report.monthly_ledgers) == 12


def test_multi_year_engine_aggregation():
    """Verify that MultiYearEngine combines all historical years accurately."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    engine = MultiYearEngine(data_dir=data_dir, prices_dir=prices_dir)
    results = engine.calculate_all_years(net_capex_sek=315000.0)

    assert "multi_year_summary" in results
    summary = results["multi_year_summary"]
    assert summary["total_recorded_years"] == 3
    assert summary["total_days"] == 110 + 366 + 365
    assert summary["energy_totals"]["produced_kwh"] > 17000
    assert summary["financial_totals"]["total_savings_sek"] > 0
    assert len(summary["annual_comparison"]) == 3

    assert "hardware_eras" in results
    assert len(results["hardware_eras"]) == 3


def test_multi_year_cli():
    """Verify that calc_multi_year_roi.py CLI executes cleanly and outputs valid JSON."""
    import json
    import subprocess
    import sys

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cmd = [
        sys.executable,
        os.path.join(base_dir, "calc_multi_year_roi.py"),
        "--capex",
        "315000",
        "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    assert "multi_year_summary" in data
    assert "years" in data
    assert "2023" in data["years"]
    assert "2024" in data["years"]
    assert "2025" in data["years"]
