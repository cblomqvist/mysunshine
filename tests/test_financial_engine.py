"""Unit and integration tests for the financial engine and Swedish tariff model."""

import json
import os
import subprocess
import sys
import unittest

from src.financial_engine import (
    BaselineEngine,
    SwedishTariff,
    TariffConfig,
    Year2025Calculator,
)


class TestSwedishTariff(unittest.TestCase):
    """Test Swedish tariff, tax, grid fee, and export revenue calculations."""

    def setUp(self):
        self.config = TariffConfig(
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
        self.tariff = SwedishTariff(config=self.config)

    def test_import_price_calculation(self):
        # Spot price = 0.50 SEK/kWh (50 öre/kWh)
        # Ex moms = 0.50 + 0.020 + 0.428 + 0.176 = 1.124 SEK/kWh
        # Incl moms (25%) = 1.124 * 1.25 = 1.405 SEK/kWh (140.5 öre/kWh)
        spot_sek = 0.50
        import_price = self.tariff.get_import_price(spot_sek)
        self.assertAlmostEqual(import_price, 1.405, places=4)

        # In öre
        import_ore = self.tariff.get_import_price_ore(50.0)
        self.assertAlmostEqual(import_ore, 140.5, places=2)

    def test_export_price_calculation_with_tax_reduction(self):
        # Spot price = 0.50 SEK/kWh
        # Export = 0.50 + 0.080 (nätnytta) + 0.600 (skattereduktion) = 1.180 SEK/kWh
        spot_sek = 0.50
        export_price = self.tariff.get_export_price(spot_sek, include_tax_reduction=True)
        self.assertAlmostEqual(export_price, 1.180, places=4)

        # In öre
        export_ore = self.tariff.get_export_price_ore(50.0, include_tax_reduction=True)
        self.assertAlmostEqual(export_ore, 118.0, places=2)

    def test_export_price_without_tax_reduction(self):
        # Without 60 öre skattereduktion
        # Export = 0.50 + 0.080 = 0.580 SEK/kWh
        spot_sek = 0.50
        export_price = self.tariff.get_export_price(spot_sek, include_tax_reduction=False)
        self.assertAlmostEqual(export_price, 0.580, places=4)

    def test_import_cost_and_export_revenue(self):
        spot_sek = 1.00
        # Import price = (1.00 + 0.020 + 0.428 + 0.176) * 1.25 = 1.624 * 1.25 = 2.030 SEK/kWh
        # Cost for 100 kWh = 203.0 SEK
        cost = self.tariff.calculate_import_cost(100.0, spot_sek)
        self.assertAlmostEqual(cost, 203.0, places=2)

        # Export price = 1.00 + 0.080 + 0.600 = 1.680 SEK/kWh
        # Revenue for 50 kWh = 84.0 SEK
        revenue = self.tariff.calculate_export_revenue(50.0, spot_sek)
        self.assertAlmostEqual(revenue, 84.0, places=2)

    def test_fixed_costs(self):
        # 1 month Tibber base fee = 49.0 SEK
        fixed_1m = self.tariff.calculate_fixed_costs(1.0)
        self.assertAlmostEqual(fixed_1m, 49.0, places=2)

        # 12 months = 588.0 SEK
        fixed_12m = self.tariff.calculate_fixed_costs(12.0)
        self.assertAlmostEqual(fixed_12m, 588.0, places=2)


class TestBaselineEngine(unittest.TestCase):
    """Test 3-way baseline scenario comparative mathematics."""

    def setUp(self):
        self.tariff = SwedishTariff()
        self.engine = BaselineEngine(tariff=self.tariff)

    def test_disaggregate_daily_solar_only(self):
        daily_load = 20.0  # kWh
        daily_pv = 30.0    # kWh

        sc, exp, imp = self.engine.disaggregate_daily_solar_only(daily_load, daily_pv)

        # Energy balance must hold
        # Produced = self_consumed + exported
        self.assertAlmostEqual(sc + exp, daily_pv, places=4)
        # Consumed = self_consumed + imported
        self.assertAlmostEqual(sc + imp, daily_load, places=4)

        # Instant self-consumption should be between 0 and daily_load
        self.assertGreater(sc, 0.0)
        self.assertLessEqual(sc, daily_load)
        self.assertLessEqual(sc, daily_pv)

    def test_baseline_eval_single_day(self):
        # 10 kWh load, 15 kWh PV, 3 kWh actual import, 7 kWh actual export
        # 8 kWh charged, 6.16 kWh discharged (77% eff)
        res = self.engine.evaluate_daily_point(
            consumed_kwh=10.0,
            produced_kwh=15.0,
            actual_imported_kwh=3.0,
            actual_exported_kwh=7.0,
            battery_charged_kwh=8.0,
            battery_discharged_kwh=6.16,
            spot_price_sek_per_kwh=0.50,
        )

        self.assertAlmostEqual(res.battery_roundtrip_efficiency, 77.0, places=1)
        self.assertGreater(res.baseline_no_solar.net_cost_sek, res.baseline_solar_only.net_cost_sek)
        self.assertAlmostEqual(
            res.total_savings_sek,
            res.solar_contribution_sek + res.battery_marginal_value_sek,
            places=4,
        )


class TestYear2025Calculator(unittest.TestCase):
    """Test full-year 2025 calculation, ledgers, and payback metrics."""

    def setUp(self):
        self.calculator = Year2025Calculator(
            data_file="data/sonnen_energy_data_2025.csv",
            price_file="data/prices/se3_prices_2025.json",
        )

    def test_2025_report_generation(self):
        report = self.calculator.calculate_2025_report(capex_sek=150000.0)

        self.assertEqual(report.year, 2025)
        self.assertEqual(report.total_days, 365)
        self.assertEqual(len(report.monthly_ledgers), 12)

        # Check annual energy totals match Sonnen recorded figures
        e = report.energy_totals
        self.assertAlmostEqual(e["produced_kwh"], 8209.6, places=1)
        self.assertAlmostEqual(e["consumed_kwh"], 7515.5, places=1)
        self.assertAlmostEqual(e["imported_kwh"], 3405.7, places=1)
        self.assertAlmostEqual(e["exported_kwh"], 3321.1, places=1)
        self.assertAlmostEqual(e["battery_charged_kwh"], 3542.4, places=1)
        self.assertAlmostEqual(e["battery_discharged_kwh"], 2728.5, places=1)
        self.assertAlmostEqual(e["battery_roundtrip_efficiency_pct"], 77.0, places=1)

        # Check financial totals
        f = report.financial_totals
        self.assertGreater(f["baseline_no_solar_cost_sek"], 10000.0)
        self.assertGreater(f["total_savings_sek"], 8000.0)
        self.assertAlmostEqual(
            f["total_savings_sek"],
            f["solar_contribution_sek"] + f["battery_marginal_value_sek"],
            places=2,
        )

        # Check capex metrics
        cm = report.capex_metrics
        self.assertIsNotNone(cm)
        self.assertEqual(cm.capex_sek, 150000.0)
        self.assertGreater(cm.annual_savings_sek, 0.0)
        self.assertGreater(cm.recouped_pct, 0.0)
        self.assertEqual(len(cm.projected_25y_cash_flow), 25)

        # Check serialization
        d = report.to_dict()
        self.assertEqual(d["year"], 2025)
        self.assertEqual(len(d["monthly_ledgers"]), 12)
        self.assertIn("capex_metrics", d)


class TestCliUtility(unittest.TestCase):
    """Test CLI execution."""

    def test_cli_execution_with_json_flag(self):
        cmd = [
            sys.executable,
            "calc_2025_roi.py",
            "--capex", "100000",
            "--json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data["year"], 2025)
        self.assertEqual(data["capex_metrics"]["capex_sek"], 100000.0)


if __name__ == "__main__":
    unittest.main()
