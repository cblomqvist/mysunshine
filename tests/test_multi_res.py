"""Unit and integration tests for Multi-Resolution Matching & High-Resolution Analyzer."""

import os
from datetime import datetime, timezone, timedelta
import pytest

from src.financial_engine import (
    HighResAnalyzer,
    HourlyEnergyRecord,
    MatchedHourlyInterval,
    ResolutionMatcher,
    SonnenHourlyIngestor,
    SwedishTariff,
    TariffConfig,
)
from src.price_providers.base import PricePoint


@pytest.fixture
def sample_tariff():
    """Default tariff with skattereduktion enabled."""
    return SwedishTariff(
        TariffConfig(
            energiskatt_sek_per_kwh=0.428,
            eem_transfer_fee_sek_per_kwh=0.176,
            tibber_markup_sek_per_kwh=0.020,
            moms_rate=0.25,
            eem_grid_benefit_sek_per_kwh=0.080,
            tax_reduction_sek_per_kwh=0.600,
            enable_tax_reduction=True,
            tibber_monthly_fee_sek=49.0,
            eem_monthly_fee_sek=0.0,
        )
    )


class TestSonnenHourlyIngestor:
    """Test suite for Sonnen hourly CSV parsing."""

    def test_parse_30d_csv(self):
        csv_path = "data/sonnen_energy_data_Sun_Aug_16_2026.csv"
        if not os.path.exists(csv_path):
            pytest.skip(f"{csv_path} not found")

        records = SonnenHourlyIngestor.parse_csv(csv_path)
        assert len(records) == 744  # 31 days * 24 hours

        first = records[0]
        assert first.timestamp.isoformat().startswith("2026-07-16T00:00:00")
        assert first.produced_kwh >= 0.0
        assert first.consumed_kwh >= 0.0
        assert first.measurements_count == 60

        last = records[-1]
        assert last.timestamp.isoformat().startswith("2026-08-15T23:00:00")

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            SonnenHourlyIngestor.parse_csv("non_existent_file.csv")


class TestResolutionMatcher:
    """Test suite for multi-resolution matching between energy and spot prices."""

    def test_match_60min_prices(self):
        t0 = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc)
        energy_rec = HourlyEnergyRecord(
            timestamp=t0,
            measurements_count=60,
            produced_kwh=5.0,
            consumed_kwh=1.0,
            battery_charged_kwh=2.0,
            battery_discharged_kwh=0.0,
            grid_feedin_kwh=2.0,
            grid_purchase_kwh=0.0,
        )
        price_pt = PricePoint(
            timestamp=t0,
            price_eur_mwh=50.0,
            price_sek_kwh=0.55,
            bidding_zone="SE3",
            resolution_minutes=60,
            provider="ENTSO-E",
        )

        matched = ResolutionMatcher.match_hourly_energy_with_prices(
            [energy_rec], [price_pt]
        )
        assert len(matched) == 1
        assert matched[0].spot_price_sek_kwh == 0.55
        assert matched[0].price_resolution_minutes == 60

    def test_match_15min_quarterly_prices(self):
        # 1-hour energy starting at 10:00 UTC
        t0 = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc)
        energy_rec = HourlyEnergyRecord(
            timestamp=t0,
            measurements_count=60,
            produced_kwh=4.0,
            consumed_kwh=1.0,
            battery_charged_kwh=0.0,
            battery_discharged_kwh=0.0,
            grid_feedin_kwh=3.0,
            grid_purchase_kwh=0.0,
        )

        # 4 quarters with distinct prices: 0.40, 0.50, 0.60, 0.70 (Mean = 0.55 SEK/kWh)
        quarters = [
            PricePoint(
                timestamp=t0 + timedelta(minutes=15 * i),
                price_eur_mwh=40.0 + 10.0 * i,
                price_sek_kwh=0.40 + 0.10 * i,
                bidding_zone="SE3",
                resolution_minutes=15,
                provider="ENTSO-E",
            )
            for i in range(4)
        ]

        matched = ResolutionMatcher.match_hourly_energy_with_prices(
            [energy_rec], quarters
        )
        assert len(matched) == 1
        assert matched[0].price_resolution_minutes == 15
        assert len(matched[0].quarterly_prices_sek_kwh) == 4
        assert pytest.approx(matched[0].spot_price_sek_kwh, 0.0001) == 0.55
        assert pytest.approx(matched[0].spot_price_eur_mwh, 0.0001) == 55.0

    def test_timezone_normalization(self):
        # Energy in Swedish CEST (+02:00) at 12:00:00+02:00 (which is 10:00:00 UTC)
        cest_tz = timezone(timedelta(hours=2))
        t_cest = datetime(2026, 7, 16, 12, 0, tzinfo=cest_tz)
        t_utc = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc)

        energy_rec = HourlyEnergyRecord(
            timestamp=t_cest,
            measurements_count=60,
            produced_kwh=6.0,
            consumed_kwh=2.0,
            battery_charged_kwh=1.0,
            battery_discharged_kwh=0.0,
            grid_feedin_kwh=3.0,
            grid_purchase_kwh=0.0,
        )
        price_pt = PricePoint(
            timestamp=t_utc,
            price_eur_mwh=60.0,
            price_sek_kwh=0.68,
            bidding_zone="SE3",
            resolution_minutes=60,
            provider="ENTSO-E",
        )

        matched = ResolutionMatcher.match_hourly_energy_with_prices(
            [energy_rec], [price_pt]
        )
        assert len(matched) == 1
        assert matched[0].spot_price_sek_kwh == 0.68

    def test_fallback_price_when_no_match(self):
        t0 = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc)
        energy_rec = HourlyEnergyRecord(
            timestamp=t0,
            measurements_count=60,
            produced_kwh=1.0,
            consumed_kwh=1.0,
            battery_charged_kwh=0.0,
            battery_discharged_kwh=0.0,
            grid_feedin_kwh=0.0,
            grid_purchase_kwh=0.0,
        )
        matched = ResolutionMatcher.match_hourly_energy_with_prices(
            [energy_rec], [], default_spot_price_sek=0.75
        )
        assert len(matched) == 1
        assert matched[0].spot_price_sek_kwh == 0.75
        assert matched[0].provider == "Fallback"


class TestHighResAnalyzer:
    """Test suite for HighResAnalyzer 3-way baseline and variance calculation."""

    def test_high_res_baseline_math(self, sample_tariff):
        analyzer = HighResAnalyzer(tariff=sample_tariff)

        t0 = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
        # Hour 1: High Solar, Low Load
        rec1 = HourlyEnergyRecord(
            timestamp=t0,
            measurements_count=60,
            produced_kwh=5.0,
            consumed_kwh=1.0,
            battery_charged_kwh=2.0,
            battery_discharged_kwh=0.0,
            grid_feedin_kwh=2.0,
            grid_purchase_kwh=0.0,
        )
        # Hour 2: Zero Solar, Evening Load
        rec2 = HourlyEnergyRecord(
            timestamp=t0 + timedelta(hours=8),
            measurements_count=60,
            produced_kwh=0.0,
            consumed_kwh=2.0,
            battery_charged_kwh=0.0,
            battery_discharged_kwh=1.5,
            grid_feedin_kwh=0.0,
            grid_purchase_kwh=0.5,
        )

        int1 = MatchedHourlyInterval(
            energy=rec1,
            spot_price_sek_kwh=0.50,
            spot_price_eur_mwh=50.0,
            price_resolution_minutes=60,
        )
        int2 = MatchedHourlyInterval(
            energy=rec2,
            spot_price_sek_kwh=1.00,
            spot_price_eur_mwh=100.0,
            price_resolution_minutes=60,
        )

        report = analyzer.analyze_matched_intervals([int1, int2])

        # B1: Total load = 1.0 + 2.0 = 3.0 kWh
        # Hour 1 load 1.0 at 0.50 SEK: import price = (0.50+0.428+0.176+0.02)*1.25 = 1.124 * 1.25 = 1.405 SEK
        # Hour 2 load 2.0 at 1.00 SEK: import price = (1.00+0.428+0.176+0.02)*1.25 = 1.624 * 1.25 = 2.030 SEK * 2 = 4.06 SEK
        # Total B1 imp cost = 1.405 + 4.06 = 5.465 SEK
        assert pytest.approx(report.baseline_no_solar.import_cost_sek, 0.001) == 5.465

        # B2:
        # Hour 1: PV 5.0, Load 1.0 -> self_cons = 1.0, export = 4.0 at 0.50 SEK
        # Export rev = 4.0 * (0.50 + 0.08 + 0.60) = 4.0 * 1.18 = 4.72 SEK. Import cost = 0.
        # Hour 2: PV 0.0, Load 2.0 -> self_cons = 0.0, export = 0, import = 2.0 at 1.00 SEK -> 4.06 SEK.
        assert pytest.approx(report.baseline_solar_only.import_cost_sek, 0.001) == 4.06
        assert pytest.approx(report.baseline_solar_only.export_revenue_sek, 0.001) == 4.72

        # Actual:
        # Hour 1: Import 0, Export 2.0 -> Export rev = 2.0 * 1.18 = 2.36 SEK
        # Hour 2: Import 0.5 at 1.00 SEK -> 0.5 * 2.03 = 1.015 SEK, Export 0.
        assert pytest.approx(report.actual_system.import_cost_sek, 0.001) == 1.015
        assert pytest.approx(report.actual_system.export_revenue_sek, 0.001) == 2.36

        # Savings
        assert report.total_savings_sek == report.baseline_no_solar.net_cost_sek - report.actual_system.net_cost_sek
        assert report.battery_marginal_value_sek == report.total_savings_sek - report.solar_contribution_sek

    def test_full_30d_analysis(self, sample_tariff):
        csv_path = "data/sonnen_energy_data_Sun_Aug_16_2026.csv"
        price_json = "data/prices/auto_SE3_20260716_20260816.json"
        if not (os.path.exists(csv_path) and os.path.exists(price_json)):
            pytest.skip("Test data files not present")

        analyzer = HighResAnalyzer(tariff=sample_tariff)
        report = analyzer.analyze_file(csv_path, price_json)

        assert report.total_hours == 744
        assert pytest.approx(report.battery_roundtrip_efficiency_pct, 0.1) == 76.7
        assert report.daily_averaged_variance is not None
        assert report.synthetic_weighted_variance is not None
        assert len(report.daily_averaged_variance.metrics) == 6

        # Check serialization
        d = report.to_dict()
        assert d["period"]["total_hours"] == 744
        assert "financial_summary_sek" in d
        assert "variance_benchmarks" in d
