"""Unit and integration tests for Milestone 6: Next-Day Forecasting & Shadow Recommendation Engine."""

from datetime import datetime, timezone
import os

from src.financial_engine.multi_res import ResolutionMatcher, SonnenHourlyIngestor
from src.financial_engine.tariff import SwedishTariff
from src.forecast_engine import (
    BatteryPhysicsConfig,
    DayAheadPriceForecaster,
    NextDayHourlyForecastPoint,
    ShadowBacktester,
    ShadowModeAdvisor,
    SolarLoadForecaster,
    WeatherIrradianceProvider,
    swedish_tz_offset_hours,
    to_swedish_local,
)
from src.price_providers.base import PricePoint


def test_swedish_timezone_cet_cest_transitions():
    """Verify Swedish local timezone conversion across CET (winter) and CEST (summer)."""
    winter_utc = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
    summer_utc = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)

    assert swedish_tz_offset_hours(winter_utc) == 1
    assert swedish_tz_offset_hours(summer_utc) == 2

    loc_winter = to_swedish_local(winter_utc)
    loc_summer = to_swedish_local(summer_utc)
    assert loc_winter.hour == 13
    assert loc_summer.hour == 14


def test_day_ahead_price_forecaster_nov15_2026():
    """Verify extraction of 2026-11-15 day-ahead SE3 prices (96 quarters -> 24 hourly blocks)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    price_path = os.path.join(base_dir, "data", "prices", "se3_prices_2026.json")
    forecaster = DayAheadPriceForecaster.from_json_file(price_path)

    assert "2026-11-15" in forecaster.available_dates()
    prices_nov15 = forecaster.get_day_ahead_prices("2026-11-15")
    assert len(prices_nov15) == 24

    # Night trough at 03:00 (~12.81 öre/kWh) vs evening peak at 17:00 (~118.28 öre/kWh)
    assert prices_nov15[3].spot_price_ore_kwh < 20.0
    assert prices_nov15[17].spot_price_ore_kwh > 110.0
    assert len(prices_nov15[3].quarterly_prices_ore_kwh) == 4
    assert prices_nov15[3].resolution_minutes == 15


def test_weather_irradiance_and_solar_load_forecaster():
    """Verify seasonal clear-sky PV potential, cloud transmittance, and hourly load/PV forecasts."""
    summer_clear_pv = WeatherIrradianceProvider.clear_sky_daily_pv_kwh("2026-06-21")
    winter_clear_pv = WeatherIrradianceProvider.clear_sky_daily_pv_kwh("2026-11-15")
    assert summer_clear_pv > 50.0
    assert 6.0 <= winter_clear_pv <= 14.0

    w_clear = WeatherIrradianceProvider.build_weather_forecast(
        "2026-11-15", cloud_cover_pct=15.0, avg_temp_c=1.0
    )
    w_overcast = WeatherIrradianceProvider.build_weather_forecast(
        "2026-11-15", cloud_cover_pct=95.0, avg_temp_c=-3.0
    )
    assert w_clear.solar_transmittance_factor > w_overcast.solar_transmittance_factor
    assert len(w_clear.hourly_weather) == 24

    # Create mock 24-hour price curve
    pts = [
        PricePoint(
            timestamp=datetime(2026, 11, 15, h, 0, tzinfo=timezone.utc),
            price_eur_mwh=50.0,
            price_sek_kwh=0.50,
        )
        for h in range(24)
    ]
    da_prices = DayAheadPriceForecaster(pts).get_day_ahead_prices("2026-11-15")
    sl_forecaster = SolarLoadForecaster()

    f_clear = sl_forecaster.forecast_next_day_hourly(
        "2026-11-15",
        da_prices,
        w_clear,
        trailing_daily_pv_kwh=[2.0, 2.5, 1.8],
        trailing_daily_load_kwh=[18.0, 19.0, 18.5],
    )
    f_overcast = sl_forecaster.forecast_next_day_hourly(
        "2026-11-15",
        da_prices,
        w_overcast,
        trailing_daily_pv_kwh=[2.0, 2.5, 1.8],
        trailing_daily_load_kwh=[18.0, 19.0, 18.5],
    )
    assert len(f_clear) == 24
    assert sum(p.predicted_pv_kwh for p in f_clear) > sum(p.predicted_pv_kwh for p in f_overcast)
    # Cold snap (-3.0°C) increases heating load vs +1.0°C
    assert sum(p.predicted_load_kwh for p in f_overcast) > sum(p.predicted_load_kwh for p in f_clear)


def test_shadow_advisor_efficiency_gate_and_precharging():
    """Verify that ShadowModeAdvisor triggers grid pre-charging only when the η=76.8% gate passes."""
    tariff = SwedishTariff()
    advisor = ShadowModeAdvisor(tariff=tariff, physics=BatteryPhysicsConfig(roundtrip_efficiency=0.768))

    # Case A: Volatile winter day (night trough 12 öre, evening peak 180 öre, low PV) -> Gate Passes
    volatile_pts = []
    for h in range(24):
        spot_sek = 0.12 if h in (1, 2, 3, 4) else (1.80 if h in (16, 17, 18, 19, 20) else 0.70)
        volatile_pts.append(
            NextDayHourlyForecastPoint(
                date_str="2026-11-15",
                hour=h,
                timestamp_local=f"2026-11-15T{h:02d}:00:00+01:00",
                spot_price_sek_kwh=spot_sek,
                spot_price_ore_kwh=spot_sek * 100.0,
                min_quarterly_ore_kwh=spot_sek * 100.0,
                max_quarterly_ore_kwh=spot_sek * 100.0,
                import_price_sek_kwh=tariff.get_import_price(spot_sek),
                export_price_sek_kwh=tariff.get_export_price(spot_sek, date_str="2026-11-15"),
                predicted_pv_kwh=0.3 if 10 <= h <= 13 else 0.0,
                predicted_load_kwh=1.2 if 16 <= h <= 21 else 0.6,
                cloud_cover_pct=85.0,
                temperature_c=1.0,
                irradiance_wm2=40.0 if 10 <= h <= 13 else 0.0,
            )
        )
    res_vol = advisor.evaluate_day(volatile_pts, initial_soc_kwh=1.0)
    assert res_vol.efficiency_gate_passed is True
    assert res_vol.recommended_grid_precharge_kwh > 5.0
    assert res_vol.shadow_savings_vs_default_sek > 5.0
    assert res_vol.shadow_optimized.net_cost_sek < res_vol.default_self_consumption.net_cost_sek
    assert any(s.shadow_action == "GRID_PRECHARGE" for s in res_vol.hourly_steps)
    assert any(s.shadow_action == "PEAK_DISCHARGE" for s in res_vol.hourly_steps)

    # Case B: Flat price curve (50 öre all day) -> Efficiency Gate blocks grid pre-charging
    flat_pts = []
    for h in range(24):
        spot_sek = 0.50
        flat_pts.append(
            NextDayHourlyForecastPoint(
                date_str="2026-11-15",
                hour=h,
                timestamp_local=f"2026-11-15T{h:02d}:00:00+01:00",
                spot_price_sek_kwh=spot_sek,
                spot_price_ore_kwh=50.0,
                min_quarterly_ore_kwh=50.0,
                max_quarterly_ore_kwh=50.0,
                import_price_sek_kwh=tariff.get_import_price(spot_sek),
                export_price_sek_kwh=tariff.get_export_price(spot_sek, date_str="2026-11-15"),
                predicted_pv_kwh=0.2 if 10 <= h <= 13 else 0.0,
                predicted_load_kwh=0.8,
                cloud_cover_pct=80.0,
                temperature_c=2.0,
                irradiance_wm2=20.0,
            )
        )
    res_flat = advisor.evaluate_day(flat_pts, initial_soc_kwh=1.0)
    assert res_flat.efficiency_gate_passed is False
    assert res_flat.recommended_grid_precharge_kwh == 0.0


def test_121_day_shadow_backtest_and_package():
    """Verify full 121-day high-res backtesting and next-day forecast package generation."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    price_path = os.path.join(data_dir, "prices", "se3_prices_2026.json")

    energy_records = SonnenHourlyIngestor.parse_directory(data_dir)
    price_points = ResolutionMatcher.load_prices_from_json(price_path)
    matched = ResolutionMatcher.match_hourly_energy_with_prices(energy_records, price_points)

    backtester = ShadowBacktester()
    pkg = backtester.build_next_day_dashboard_package(
        price_points=price_points,
        matched_intervals=matched,
        target_date="2026-11-15",
    )

    assert pkg["target_date"] == "2026-11-15"
    assert "baseline_forecast" in pkg["scenarios"]
    assert "clear_autumn_sun" in pkg["scenarios"]
    assert "cold_overcast_spike" in pkg["scenarios"]

    bt = pkg["backtest_121d"]
    assert bt["period"]["total_days"] == 121
    assert bt["period"]["total_hours"] == 2905
    assert bt["strategy_trigger_summary"]["grid_precharge_days_count"] >= 15
    assert bt["financial_totals_sek"]["predictive_upside_vs_default_sek"] > 50.0
    assert bt["financial_totals_sek"]["oracle_upside_vs_default_sek"] > 100.0
    assert bt["financial_totals_sek"]["oracle_upside_vs_actual_sonnen_sek"] > 200.0
    assert len(bt["daily_records"]) == 121
