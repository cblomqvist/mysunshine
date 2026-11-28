import os
from src.financial_engine.multi_year import (
    HistoricalYearCalculator,
    MultiYearEngine,
)


def test_get_available_years():
    """Verify that MultiYearEngine discovers 2021 through 2026 dataset files."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    engine = MultiYearEngine(data_dir=data_dir, prices_dir=prices_dir)
    years = engine.get_available_years()

    assert years == [2021, 2022, 2023, 2024, 2025, 2026]


def test_historical_years_2021_2022_solar_only():
    """Verify 2021 & 2022 Solar Era empirical self-consumption and zero battery marginal value."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    calc_2021 = HistoricalYearCalculator(
        year=2021,
        data_file=os.path.join(data_dir, "sonnen_energy_data_2021.csv"),
        price_file=os.path.join(prices_dir, "se3_prices_2021.json"),
    )
    rep_2021 = calc_2021.calculate_annual_report(capex_sek=165000.0)
    assert rep_2021.total_days == 365
    assert abs(rep_2021.energy_totals["produced_kwh"] - 8381.5) < 1.0
    assert abs(rep_2021.energy_totals["exported_kwh"] - 5695.3) < 1.0
    assert abs(rep_2021.energy_totals["actual_self_consumption_pct"] - 32.0) < 0.2
    assert abs(rep_2021.financial_totals["battery_marginal_value_sek"]) < 0.01

    calc_2022 = HistoricalYearCalculator(
        year=2022,
        data_file=os.path.join(data_dir, "sonnen_energy_data_2022.csv"),
        price_file=os.path.join(prices_dir, "se3_prices_2022.json"),
    )
    rep_2022 = calc_2022.calculate_annual_report(capex_sek=165000.0)
    assert rep_2022.total_days == 365
    assert abs(rep_2022.energy_totals["produced_kwh"] - 9038.1) < 1.0
    assert abs(rep_2022.energy_totals["exported_kwh"] - 6998.0) < 1.0
    assert abs(rep_2022.energy_totals["actual_self_consumption_pct"] - 22.6) < 0.2
    assert abs(rep_2022.financial_totals["battery_marginal_value_sek"]) < 0.01
    assert rep_2022.financial_totals["total_savings_sek"] > 18000.0


def test_historical_year_2023_full_hybrid():
    """Verify that 2023 full hybrid year (365 days: Solar Only + Sonnen 11 kWh) calculates properly."""
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
    assert report.total_days == 365
    assert report.energy_totals["produced_kwh"] > 8500
    assert report.financial_totals["total_savings_sek"] > 9000
    assert len(report.monthly_ledgers) == 12


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


def test_historical_year_2026_ytd():
    """Verify that 2026 YTD calculates properly without skattereduktion."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    calc = HistoricalYearCalculator(
        year=2026,
        data_file=os.path.join(data_dir, "sonnen_energy_data_2026.csv"),
        price_file=os.path.join(prices_dir, "se3_prices_2026.json"),
    )
    report = calc.calculate_annual_report(capex_sek=315000.0)

    assert report.year == 2026
    assert report.total_days >= 240
    assert report.energy_totals["produced_kwh"] > 7000
    assert report.financial_totals["total_savings_sek"] > 0

    matched_by_date = calc.load_matched_hourly_by_date()
    assert len(matched_by_date) == 134
    assert "2026-07-16" in matched_by_date
    assert "2026-11-26" in matched_by_date
    assert len(matched_by_date["2026-10-25"]) == 25  # 25-hour DST fallback day


def test_multi_year_engine_aggregation():
    """Verify that MultiYearEngine combines all historical years accurately."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    prices_dir = os.path.join(data_dir, "prices")

    engine = MultiYearEngine(data_dir=data_dir, prices_dir=prices_dir)
    results = engine.calculate_all_years(net_capex_sek=315000.0)

    assert "multi_year_summary" in results
    summary = results["multi_year_summary"]
    assert summary["total_recorded_years"] == 6
    assert summary["total_days"] >= 1880
    assert summary["energy_totals"]["produced_kwh"] > 40000
    assert summary["financial_totals"]["total_savings_sek"] > 0
    assert len(summary["annual_comparison"]) == 6

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
    assert "2021" in data["years"]
    assert "2022" in data["years"]
    assert "2023" in data["years"]
    assert "2024" in data["years"]
    assert "2025" in data["years"]
    assert "2026" in data["years"]
