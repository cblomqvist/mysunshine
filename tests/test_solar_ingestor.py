"""Unit tests for SMA Inverter and EEM Meter Readings Solar Era Ingestion."""

import os
from src.financial_engine.solar_ingestor import (
    EEMMeterIngestor,
    SMAInverterIngestor,
    SolarEraSynthesizer,
)


def test_sma_inverter_ingestor():
    """Verify Sunny Portal SMA inverter monthly yields for 2021, 2022, and 2023."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sma_path = os.path.join(base_dir, "data", "sunnyportal-sma-inverter-data-2026-10-24.csv")

    ingestor = SMAInverterIngestor(sma_path)
    yields = ingestor.parse_monthly_yields()

    assert 2021 in yields
    assert 2022 in yields
    assert 2023 in yields
    assert abs(ingestor.get_annual_yield(2021) - 8381.46) < 0.1
    assert abs(ingestor.get_annual_yield(2022) - 9038.13) < 0.1
    assert abs(ingestor.get_annual_yield(2023) - 8532.41) < 0.1


def test_eem_meter_ingestor():
    """Verify official EEM utility export meter readings for 2021 and 2022."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    eem_path = os.path.join(
        base_dir, "data", "EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv"
    )

    ingestor = EEMMeterIngestor(eem_path)
    exports = ingestor.parse_monthly_exports()

    assert 2021 in exports
    assert 2022 in exports
    assert abs(ingestor.get_annual_export(2021) - 5695.287) < 0.1
    assert abs(ingestor.get_annual_export(2022) - 6997.963) < 0.1


def test_solar_era_empirical_calibration():
    """Verify empirical self-consumption calibration (32.0% in 2021, 22.6% in 2022)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")

    synth = SolarEraSynthesizer(data_dir)
    s2021 = synth.get_annual_empirical_summary(2021)
    s2022 = synth.get_annual_empirical_summary(2022)

    assert abs(s2021.produced_kwh - 8381.46) < 0.2
    assert abs(s2021.exported_kwh - 5695.29) < 0.2
    assert abs(s2021.self_consumption_pct - 32.05) < 0.1

    assert abs(s2022.produced_kwh - 9038.13) < 0.2
    assert abs(s2022.exported_kwh - 6997.96) < 0.2
    assert abs(s2022.self_consumption_pct - 22.57) < 0.1

