"""Unit & Integration Tests for Milestone 7: Home Assistant Custom Sensor Integration & Telemetry Bridge."""

import os
import unittest

from src.financial_engine.multi_res import ResolutionMatcher, SonnenHourlyIngestor
from src.financial_engine.multi_year import MultiYearEngine
from src.financial_engine.tariff import SwedishTariff, TariffConfig
from src.financial_engine.tariff_audit import UtilityTariffAuditor
from src.forecast_engine.backtester import ShadowBacktester
from src.ha_integration import (
    HomeAssistantEntityPayload,
    HomeAssistantTelemetryBridge,
    SonnenSafetyActuationGate,
)


class TestHomeAssistantIntegration(unittest.TestCase):
    """Verify Home Assistant custom entity payloads, Sonnen v2 status parser, and dual safety gate."""

    @classmethod
    def setUpClass(cls):
        cls.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.data_dir = os.path.join(cls.base_dir, "data")
        cls.prices_dir = os.path.join(cls.data_dir, "prices")
        cls.tariff = SwedishTariff(config=TariffConfig())

        cls.multi_year_engine = MultiYearEngine(
            data_dir=cls.data_dir,
            prices_dir=cls.prices_dir,
            tariff=cls.tariff,
        )
        cls.multi_year_results = cls.multi_year_engine.calculate_all_years(net_capex_sek=315000.0)
        cls.audit_report = UtilityTariffAuditor(
            data_dir=cls.data_dir,
            baseline_tariff=cls.tariff,
        ).run_audit().to_dict()

        energy_records = SonnenHourlyIngestor.parse_directory(cls.data_dir)
        price_file = os.path.join(cls.prices_dir, "se3_prices_2026.json")
        price_points = ResolutionMatcher.load_prices_from_json(price_file)
        matched = ResolutionMatcher.match_hourly_energy_with_prices(energy_records, price_points)

        backtester = ShadowBacktester(tariff=cls.tariff)
        cls.next_day_pkg = backtester.build_next_day_dashboard_package(
            price_points=price_points,
            matched_intervals=matched,
            target_date="2026-11-15",
        )

    def test_entity_payload_rest_schema(self):
        """Verify HomeAssistantEntityPayload produces standard HA REST /api/states JSON schema."""
        ent = HomeAssistantEntityPayload(
            entity_id="sensor.mysunshine_breakeven_spot_ore",
            state=41.6,
            friendly_name="MySunshine Arbitrage Break-Even Spot Price",
            unit_of_measurement="öre/kWh",
            state_class="measurement",
            attributes={"efficiency_gate_passed": True},
        )
        rest_payload = ent.to_ha_rest_payload()
        self.assertEqual(rest_payload["state"], "41.6")
        self.assertEqual(rest_payload["attributes"]["friendly_name"], "MySunshine Arbitrage Break-Even Spot Price")
        self.assertEqual(rest_payload["attributes"]["unit_of_measurement"], "öre/kWh")
        self.assertEqual(rest_payload["attributes"]["state_class"], "measurement")
        self.assertEqual(rest_payload["attributes"]["integration"], "mysunshine")
        self.assertTrue(rest_payload["attributes"]["efficiency_gate_passed"])

    def test_sonnen_safety_actuation_gate_locked_by_default(self):
        """Verify physical SonnenBatterie 10 API writes are blocked unless BOTH env and HA switch are ON."""
        # Case 1: Both False (Default Shadow Mode)
        gate_default = SonnenSafetyActuationGate(env_opt_in_enabled=False, ha_switch_on=False)
        self.assertFalse(gate_default.is_unlocked)
        self.assertEqual(gate_default.gate_state_label, "LOCKED_SHADOW_MODE_ONLY")
        cmd_locked = gate_default.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=6.2,
        )
        self.assertFalse(cmd_locked.would_actuate)
        self.assertEqual(cmd_locked.target_operating_mode, 1)
        self.assertEqual(cmd_locked.target_power_watts, 6200)
        self.assertIn("/api/v2/setpoint/charge/6200", cmd_locked.endpoint)
        self.assertIn("Shadow Mode Safety Gate Active", cmd_locked.blocked_reason)

        # Case 2: Only env_opt_in True, HA switch False -> Still Locked
        gate_half1 = SonnenSafetyActuationGate(env_opt_in_enabled=True, ha_switch_on=False)
        self.assertFalse(gate_half1.is_unlocked)

        # Case 3: Only HA switch True, env_opt_in False -> Still Locked
        gate_half2 = SonnenSafetyActuationGate(env_opt_in_enabled=False, ha_switch_on=True)
        self.assertFalse(gate_half2.is_unlocked)

        # Case 4: Both True -> Unlocked
        gate_unlocked = SonnenSafetyActuationGate(env_opt_in_enabled=True, ha_switch_on=True)
        self.assertTrue(gate_unlocked.is_unlocked)
        self.assertEqual(gate_unlocked.gate_state_label, "UNLOCKED_ACTIVE_CONTROL")
        cmd_unlocked = gate_unlocked.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=6.2,
        )
        self.assertTrue(cmd_unlocked.would_actuate)

    def test_sonnen_v2_status_parser(self):
        """Verify live and offline fallback parsing of SonnenBatterie 10 /api/v2/status."""
        mock_live = {
            "USOC": 45.0,
            "RSOC": 49.0,
            "Pac_total_W": -3200,
            "Production_W": 4100,
            "Consumption_W": 900,
            "GridFeedIn_W": 0,
            "EM_OperatingMode": 2,
            "BatteryCharging": True,
            "BatteryDischarging": False,
            "SystemStatus": "OnGrid",
        }
        parsed = HomeAssistantTelemetryBridge.parse_sonnen_v2_status(mock_live)
        self.assertEqual(parsed["source"], "sonnen_api_v2_live")
        self.assertEqual(parsed["usoc_pct"], 45.0)
        self.assertEqual(parsed["remaining_capacity_kwh"], 9.0)
        self.assertEqual(parsed["em_operating_mode"], 2)
        self.assertTrue(parsed["battery_charging"])

        fallback = HomeAssistantTelemetryBridge.parse_sonnen_v2_status(None, fallback_soc_pct=12.5)
        self.assertEqual(fallback["source"], "offline_deterministic_snapshot")
        self.assertEqual(fallback["usoc_pct"], 12.5)
        self.assertEqual(fallback["remaining_capacity_kwh"], 2.5)

    def test_full_home_assistant_state_package_and_dry_run_publish(self):
        """Verify all 10 custom Home Assistant entities, attributes, and dry-run REST push."""
        bridge = HomeAssistantTelemetryBridge(env_opt_in_enabled=False, ha_switch_on=False)
        pkg = bridge.build_state_package(
            multi_year_summary=self.multi_year_results["multi_year_summary"],
            next_day_forecast_pkg=self.next_day_pkg,
            utility_audit_report=self.audit_report,
            focus_hour=3,
        )

        self.assertEqual(len(pkg.entities), 10)
        self.assertEqual(len(pkg.sonnen_command_previews), 24)
        self.assertFalse(pkg.active_control_enabled)
        self.assertEqual(pkg.safety_gate_status, "LOCKED_SHADOW_MODE_ONLY")

        # Check key required sensors from HANDOVER.md & PRD Phase 3
        ent_action = pkg.get_entity("sensor.mysunshine_shadow_action")
        self.assertIsNotNone(ent_action)
        self.assertEqual(ent_action.state, "GRID_PRECHARGE")
        self.assertEqual(len(ent_action.attributes["hourly_schedule_24h"]), 24)

        ent_be = pkg.get_entity("sensor.mysunshine_breakeven_spot_ore")
        self.assertIsNotNone(ent_be)
        self.assertAlmostEqual(float(ent_be.state), 41.6, places=1)

        ent_sav = pkg.get_entity("sensor.mysunshine_expected_savings_sek")
        self.assertIsNotNone(ent_sav)
        self.assertAlmostEqual(float(ent_sav.state), 9.65, places=1)

        ent_lts = pkg.get_entity("sensor.mysunshine_cumulative_savings_sek")
        self.assertIsNotNone(ent_lts)
        self.assertEqual(ent_lts.state_class, "total_increasing")
        self.assertAlmostEqual(float(ent_lts.state), 72247.07, places=1)

        # Dry-run publish should never fail or require live network sockets
        receipt = bridge.publish_to_home_assistant(pkg, dry_run=True)
        self.assertFalse(receipt["published"])
        self.assertEqual(receipt["mode"], "dry_run")
        self.assertEqual(receipt["entities_prepared"], 10)


if __name__ == "__main__":
    unittest.main()
