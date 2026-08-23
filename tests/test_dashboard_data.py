"""Unit tests for the dashboard data generator and payload integrity."""

import os
from src.financial_engine.generate_dashboard_data import generate_dashboard_dataset


def test_generate_dashboard_dataset_structure():
    """Verify that generate_dashboard_dataset produces complete and valid data structures."""
    dataset = generate_dashboard_dataset()

    # Metadata checks
    assert "metadata" in dataset
    assert dataset["metadata"]["bidding_zone"] == "SE3"
    assert dataset["metadata"]["retailer"] == "Tibber"
    assert dataset["metadata"]["grid_operator"] == "Eskilstuna Energi & Miljö (EEM)"
    assert "featured_days" in dataset["metadata"]
    assert dataset["metadata"]["featured_days"]["peak_solar"] is not None

    # Year 2025 checks
    assert "year_2025" in dataset
    y2025 = dataset["year_2025"]
    assert y2025["year"] == 2025
    assert len(y2025["monthly_ledgers"]) == 12
    assert "financial_totals" in y2025
    assert y2025["financial_totals"]["total_savings_sek"] > 0
    assert y2025["financial_totals"]["baseline_no_solar_cost_sek"] > y2025["financial_totals"]["actual_cost_sek"]

    # High-Res 30d checks
    assert "high_res_30d" in dataset
    hr = dataset["high_res_30d"]
    assert "period" in hr
    assert hr["period"]["total_hours"] == 744
    assert len(hr["days_list"]) == 31
    assert len(hr["hourly_data"]) == 744
    assert "variance_benchmarks" in hr

    # Hourly interval check
    first_hour = hr["hourly_data"][0]
    assert "timestamp" in first_hour
    assert "spot_price_ore" in first_hour
    assert "battery_soc_kwh" in first_hour
    assert "produced_kw" in first_hour
    assert "consumed_kw" in first_hour


def test_dashboard_static_files_exist():
    """Ensure that data/dashboard_data.json and data/dashboard_data.js exist on disk."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "data", "dashboard_data.json")
    js_path = os.path.join(base_dir, "data", "dashboard_data.js")

    assert os.path.exists(json_path), f"Missing {json_path}"
    assert os.path.exists(js_path), f"Missing {js_path}"
    assert os.path.getsize(json_path) > 10000
    assert os.path.getsize(js_path) > 10000
