"""Unit and integration tests for Utility Tariff Benchmarking & Invoicing Audit (Milestone 5.5.4)."""

import os
from src.financial_engine import (
    DEFAULT_AUDITED_EEM_SCHEDULES,
    EEMYearlyCostsIngestor,
    SwedishTariff,
    UtilityTariffAuditor,
)


def test_detect_leverantorsbyte_event():
    """Verify detection of the 2024-09-28 Leverantörsbyte event in official EEM meter readings."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    ingestor = EEMYearlyCostsIngestor(
        costs_csv_path=os.path.join(data_dir, "eem-yearly-costs-2024-2026.csv"),
        meter_csv_path=os.path.join(
            data_dir, "EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv"
        ),
    )
    switch_date, switch_stand = ingestor.detect_leverantorsbyte_event()
    assert switch_date == "2024-09-28"
    assert switch_stand is not None
    assert abs(switch_stand - 22217.291) < 0.01


def test_eem_yearly_costs_ingestor_parsing():
    """Verify parsing of 2024, 2025, and 2026 monthly records from eem-yearly-costs-2024-2026.csv."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    ingestor = EEMYearlyCostsIngestor(
        costs_csv_path=os.path.join(data_dir, "eem-yearly-costs-2024-2026.csv")
    )
    records = ingestor.parse_records()
    assert len(records) == 36  # 12 months * 3 years

    billed_records = [r for r in records if r.is_billed]
    assert len(billed_records) == 33  # 12 in 2024 + 12 in 2025 + 9 in 2026 (Jan-Sep)

    # Check regime classification around Leverantörsbyte (2024-09-28)
    rec_sep_24 = next(r for r in records if r.year == 2024 and r.month == 9)
    rec_oct_24 = next(r for r in records if r.year == 2024 and r.month == 10)
    assert rec_sep_24.billing_regime == "combined_retail_and_grid"
    assert rec_oct_24.billing_regime == "pure_grid_tibber"


def test_post_switch_pure_grid_exact_invoice_match():
    """Verify all 24 post-Leverantörsbyte pure grid invoices (Oct 2024 - Sep 2026) match to exact rounded SEK."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    auditor = UtilityTariffAuditor(data_dir=data_dir)
    report = auditor.run_audit()

    post = report.post_switch_summary
    assert post["months_count"] == 24
    assert post["exact_integer_invoice_matches"] == 24
    assert post["exact_match_rate_pct"] == 100.0
    assert post["mean_absolute_error_kr"] < 0.30
    assert post["max_absolute_error_kr"] <= 0.55

    # Verify annual billed totals match EEM CSV exactly
    ann_by_yr = {a["year"]: a for a in report.annual_summaries}
    assert ann_by_yr[2024]["eem_billed_kr"] == 10818.0
    assert ann_by_yr[2025]["eem_billed_kr"] == 7336.0
    assert ann_by_yr[2026]["eem_billed_kr"] == 4900.0


def test_pre_switch_combined_retail_and_grid_decomposition():
    """Verify Jan-Sep 2024 pre-Leverantörsbyte combined invoice decomposition into grid and retail components."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    auditor = UtilityTariffAuditor(data_dir=data_dir)
    report = auditor.run_audit()

    pre = report.pre_switch_summary
    assert pre["months_count"] == 9
    assert abs(pre["total_billed_kr"] - 8741.0) < 0.01
    assert abs(
        pre["decomposed_grid_and_tax_kr"] + pre["decomposed_eem_retail_supply_kr"] - 8741.0
    ) < 0.05
    assert pre["decomposed_eem_retail_supply_kr"] > 2900.0


def test_swedish_tariff_for_audited_year_and_ct_clamp_audit():
    """Verify SwedishTariff.for_audited_year factory and Sonnen CT clamp vs EEM fiscal kWh audit."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    auditor = UtilityTariffAuditor(data_dir=data_dir)
    report = auditor.run_audit()

    # Check SwedishTariff.for_audited_year(2025)
    t_2025 = SwedishTariff.for_audited_year(2025)
    sched_2025 = DEFAULT_AUDITED_EEM_SCHEDULES[2025]
    assert abs(
        t_2025.config.eem_transfer_fee_sek_per_kwh - sched_2025.eem_transfer_fee_sek_per_kwh_ex_vat
    ) < 1e-6
    assert abs(
        t_2025.config.energiskatt_sek_per_kwh - sched_2025.energiskatt_sek_per_kwh_ex_vat
    ) < 1e-6

    # Check Oct 2026 partial cutoff check (179.261 kWh EEM vs ~170.395 kWh Sonnen Oct 1-24)
    oct_check = report.metering_audit_summary["oct_2026_partial_export_check"]
    assert abs(oct_check["eem_partial_kwh"] - 179.261) < 0.01
    assert abs(oct_check["sonnen_oct1_to_oct24_kwh"] - 170.395) < 0.1
    assert -6.0 < oct_check["bias_pct"] < -4.0
