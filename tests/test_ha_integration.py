"""Unit & Integration Tests for Milestone 7: Home Assistant Custom Sensor Integration & Telemetry Bridge."""

from datetime import datetime
import json
import os
import re
import unittest
from unittest.mock import patch
import urllib.error

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


class _FakeHTTPResponse:
    """Minimal context-manager mock for urllib.request.urlopen responses."""

    def __init__(self, status: int = 200, body_dict: dict | None = None):
        self.status = status
        self._raw = json.dumps(body_dict or {}).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


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
        """Verify all 4 dual-gate combinations: (F,F), (F,T), (T,F), and (T,T)."""
        # Combination 1: env=False, ha_switch=False -> Locked
        gate_ff = SonnenSafetyActuationGate(env_opt_in_enabled=False, ha_switch_on=False)
        self.assertFalse(gate_ff.is_unlocked)
        self.assertEqual(gate_ff.gate_state_label, "LOCKED_SHADOW_MODE_ONLY")
        cmd_ff = gate_ff.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=6.2,
        )
        self.assertFalse(cmd_ff.would_actuate)
        self.assertEqual(cmd_ff.target_operating_mode, 1)
        self.assertEqual(cmd_ff.target_power_watts, 6200)
        self.assertIn("/api/v2/setpoint/charge/6200", cmd_ff.endpoint)
        self.assertIn("MYSUNSHINE_ACTIVE_CONTROL_ENABLED=false", cmd_ff.blocked_reason)
        self.assertIn("input_boolean.mysunshine_active_battery_control=off", cmd_ff.blocked_reason)

        # Combination 2: env=False, ha_switch=True -> Still Locked
        gate_ft = SonnenSafetyActuationGate(env_opt_in_enabled=False, ha_switch_on=True)
        self.assertFalse(gate_ft.is_unlocked)
        self.assertEqual(gate_ft.gate_state_label, "LOCKED_SHADOW_MODE_ONLY")
        cmd_ft = gate_ft.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=6.2,
        )
        self.assertFalse(cmd_ft.would_actuate)
        self.assertIn("MYSUNSHINE_ACTIVE_CONTROL_ENABLED=false", cmd_ft.blocked_reason)

        # Combination 3: env=True, ha_switch=False -> Still Locked
        gate_tf = SonnenSafetyActuationGate(env_opt_in_enabled=True, ha_switch_on=False)
        self.assertFalse(gate_tf.is_unlocked)
        self.assertEqual(gate_tf.gate_state_label, "LOCKED_SHADOW_MODE_ONLY")
        cmd_tf = gate_tf.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=6.2,
        )
        self.assertFalse(cmd_tf.would_actuate)
        self.assertIn("input_boolean.mysunshine_active_battery_control=off", cmd_tf.blocked_reason)

        # Combination 4: env=True, ha_switch=True -> Unlocked
        gate_tt = SonnenSafetyActuationGate(env_opt_in_enabled=True, ha_switch_on=True)
        self.assertTrue(gate_tt.is_unlocked)
        self.assertEqual(gate_tt.gate_state_label, "UNLOCKED_ACTIVE_CONTROL")
        cmd_tt = gate_tt.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=6.2,
        )
        self.assertTrue(cmd_tt.would_actuate)
        self.assertEqual(cmd_tt.safety_gate_status, "UNLOCKED_ACTIVE_CONTROL")

    def test_hourly_command_parameters_no_hardcoded_6200w(self):
        """Verify dynamic hourly target_power_watts are exposed and no hard-coded 6200 W exists in YAML."""
        bridge = HomeAssistantTelemetryBridge(env_opt_in_enabled=False, ha_switch_on=False)
        pkg_h3 = bridge.build_state_package(
            multi_year_summary=self.multi_year_results["multi_year_summary"],
            next_day_forecast_pkg=self.next_day_pkg,
            utility_audit_report=self.audit_report,
            focus_hour=3,
        )
        pkg_h4 = bridge.build_state_package(
            multi_year_summary=self.multi_year_results["multi_year_summary"],
            next_day_forecast_pkg=self.next_day_pkg,
            utility_audit_report=self.audit_report,
            focus_hour=4,
        )

        # Hour 03:00 and Hour 04:00 have different precharge kWh in the forecast schedule
        w_h3 = int(pkg_h3.get_entity("sensor.mysunshine_target_power_watts").state)
        w_h4 = int(pkg_h4.get_entity("sensor.mysunshine_target_power_watts").state)
        self.assertGreater(w_h3, 0)
        self.assertGreater(w_h4, 0)
        self.assertNotEqual(w_h3, w_h4)
        self.assertEqual(
            pkg_h3.get_entity("sensor.mysunshine_shadow_action").attributes["target_power_watts"],
            w_h3,
        )
        self.assertEqual(
            pkg_h4.get_entity("sensor.mysunshine_shadow_action").attributes["target_power_watts"],
            w_h4,
        )

        # Verify generated YAML contains NO hard-coded 6200 W setpoint and references dynamic sensor
        auto_yaml = pkg_h3.automations_yaml_snippet
        cfg_yaml = pkg_h3.configuration_yaml_snippet
        self.assertNotIn("6200", auto_yaml)
        self.assertNotIn("6200", cfg_yaml)
        self.assertIn("sensor.mysunshine_target_power_watts", auto_yaml)
        self.assertIn("binary_sensor.mysunshine_env_active_control_opt_in", auto_yaml)
        self.assertIn("input_boolean.mysunshine_active_battery_control", auto_yaml)
        self.assertIn("mysunshine_active_control_enabled", cfg_yaml)
        self.assertIsNone(re.search(r"watts:\s*[1-9]\d{2,3}", auto_yaml))

    def test_peak_discharge_semantics_and_no_unsupported_payload_keys(self):
        """Verify PEAK_DISCHARGE never emits fake expected_peak_shave_w keys and stays non-actuating by default."""
        # Default mode: PEAK_DISCHARGE is shadow-only non-actuating Mode 2 even when dual gate is unlocked
        gate_passive = SonnenSafetyActuationGate(
            env_opt_in_enabled=True,
            ha_switch_on=True,
            enable_direct_discharge_setpoint=False,
        )
        cmd_passive = gate_passive.evaluate_hourly_command(
            hour=17,
            timestamp_local="2026-11-15T17:00:00",
            shadow_action="PEAK_DISCHARGE",
            discharged_kwh=2.35,
        )
        self.assertEqual(cmd_passive.target_operating_mode, 2)
        self.assertEqual(cmd_passive.target_power_watts, 0)
        self.assertEqual(cmd_passive.payload, {"EM_OperatingMode": "2"})
        self.assertNotIn("expected_peak_shave_w", cmd_passive.payload)
        self.assertFalse(cmd_passive.would_actuate)
        self.assertEqual(cmd_passive.actuation_semantics, "SHADOW_ONLY_NON_ACTUATING_PEAK_SHAVE")

        # Direct manual discharge setpoint mode: uses confirmed /api/v2/setpoint/discharge/<watts>
        gate_direct = SonnenSafetyActuationGate(
            env_opt_in_enabled=True,
            ha_switch_on=True,
            enable_direct_discharge_setpoint=True,
        )
        cmd_direct = gate_direct.evaluate_hourly_command(
            hour=17,
            timestamp_local="2026-11-15T17:00:00",
            shadow_action="PEAK_DISCHARGE",
            discharged_kwh=2.35,
        )
        self.assertEqual(cmd_direct.target_operating_mode, 1)
        self.assertEqual(cmd_direct.target_power_watts, 2350)
        self.assertIn("/api/v2/setpoint/discharge/2350", cmd_direct.endpoint)
        self.assertTrue(cmd_direct.would_actuate)
        self.assertEqual(cmd_direct.actuation_semantics, "DIRECT_MANUAL_DISCHARGE_SETPOINT")

    def test_failsafe_restoration_soc_bounds_staleness_and_idempotency(self):
        """Verify SoC limits, stale command rejection, idempotency deduplication, and fail-safe Mode 2 restore."""
        bridge = HomeAssistantTelemetryBridge(
            sonnen_token="valid_test_sonnen_token",
            env_opt_in_enabled=True,
            ha_switch_on=True,
            min_soc_pct=10.0,
            max_soc_pct=95.0,
        )
        cmd_chg = bridge.safety_gate.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=4.5,
        )

        # 1. Stale command check (> 3900s old triggers fail-safe Mode 2 restore)
        stale_now = datetime.fromisoformat("2026-11-15T06:00:00")
        res_stale = bridge.execute_sonnen_command(cmd_chg, dry_run=True, reference_now=stale_now)
        self.assertFalse(res_stale["executed"])
        self.assertTrue(res_stale["blocked"])
        self.assertEqual(res_stale["reason"], "stale_command_rejected")
        self.assertTrue(res_stale["fail_safe_restore"]["restored_to_mode_2"])

        # 2. Upper SoC limit reached (96% >= 95% max_soc_pct blocks pre-charge and restores Mode 2)
        valid_now = datetime.fromisoformat("2026-11-15T03:05:00")
        res_high_soc = bridge.execute_sonnen_command(
            cmd_chg,
            dry_run=True,
            reference_now=valid_now,
            current_status={"USOC": 96.0, "EM_OperatingMode": 1},
        )
        self.assertFalse(res_high_soc["executed"])
        self.assertEqual(res_high_soc["reason"], "soc_upper_limit_reached")
        self.assertTrue(res_high_soc["fail_safe_restore"]["restored_to_mode_2"])

        # 3. Live execution success with post-write status verification + idempotency block on retry
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _FakeHTTPResponse(200, {"EM_OperatingMode": "1"}),  # PUT /api/v2/configurations
                _FakeHTTPResponse(200, {}),  # POST /api/v2/setpoint/charge/4500
                _FakeHTTPResponse(200, {"USOC": 25.0, "EM_OperatingMode": 1}),  # GET /api/v2/status
            ]
            res_live = bridge.execute_sonnen_command(
                cmd_chg,
                dry_run=False,
                reference_now=valid_now,
                current_status={"USOC": 20.0, "EM_OperatingMode": 2},
            )
            self.assertTrue(res_live["executed"])
            self.assertEqual(res_live["verified_operating_mode"], 1)

            # Immediate retry with same command is blocked by idempotency key
            res_dup = bridge.execute_sonnen_command(
                cmd_chg,
                dry_run=False,
                reference_now=valid_now,
            )
            self.assertFalse(res_dup["executed"])
            self.assertTrue(res_dup["blocked"])
            self.assertEqual(res_dup["reason"], "duplicate_idempotency_key_blocked")

        # 4. Live execution failure or post-write mode mismatch triggers automatic fail-safe Mode 2 restore
        cmd_chg_h4 = bridge.safety_gate.evaluate_hourly_command(
            hour=4,
            timestamp_local="2026-11-15T04:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=5.0,
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _FakeHTTPResponse(200, {"EM_OperatingMode": "1"}),  # PUT mode 1
                _FakeHTTPResponse(200, {}),  # POST setpoint
                _FakeHTTPResponse(200, {"USOC": 30.0, "EM_OperatingMode": 2}),  # Mismatched mode!
                _FakeHTTPResponse(200, {"EM_OperatingMode": "2"}),  # Fail-safe PUT mode 2
            ]
            res_fail = bridge.execute_sonnen_command(
                cmd_chg_h4,
                dry_run=False,
                reference_now=datetime.fromisoformat("2026-11-15T04:05:00"),
            )
            self.assertFalse(res_fail["executed"])
            self.assertEqual(res_fail["mode"], "failed_with_failsafe_restore")
            self.assertTrue(res_fail["fail_safe_restore"]["restored_to_mode_2"])

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
        """Verify all 12 custom Home Assistant entities, attributes, dry-run, and live REST push paths."""
        bridge = HomeAssistantTelemetryBridge(
            ha_token="valid_ha_long_lived_token",
            env_opt_in_enabled=False,
            ha_switch_on=False,
        )
        pkg = bridge.build_state_package(
            multi_year_summary=self.multi_year_results["multi_year_summary"],
            next_day_forecast_pkg=self.next_day_pkg,
            utility_audit_report=self.audit_report,
            focus_hour=3,
        )

        self.assertEqual(len(pkg.entities), 12)
        self.assertEqual(len(pkg.sonnen_command_previews), 24)
        self.assertFalse(pkg.active_control_enabled)
        self.assertEqual(pkg.safety_gate_status, "LOCKED_SHADOW_MODE_ONLY")

        # Check key required sensors
        ent_action = pkg.get_entity("sensor.mysunshine_shadow_action")
        self.assertIsNotNone(ent_action)
        self.assertEqual(ent_action.state, "GRID_PRECHARGE")
        self.assertEqual(len(ent_action.attributes["hourly_schedule_24h"]), 24)

        ent_watts = pkg.get_entity("sensor.mysunshine_target_power_watts")
        self.assertIsNotNone(ent_watts)
        self.assertGreater(int(ent_watts.state), 0)

        ent_env_gate = pkg.get_entity("binary_sensor.mysunshine_env_active_control_opt_in")
        self.assertIsNotNone(ent_env_gate)
        self.assertEqual(ent_env_gate.state, "off")

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

        # 1. Dry-run publish
        receipt_dry = bridge.publish_to_home_assistant(pkg, dry_run=True)
        self.assertFalse(receipt_dry["published"])
        self.assertEqual(receipt_dry["mode"], "dry_run")
        self.assertEqual(receipt_dry["entities_prepared"], 12)

        # 2. Live publish success path (mocked HTTP 200 for all 12 entities)
        with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(200, {})):
            receipt_live = bridge.publish_to_home_assistant(pkg, dry_run=False)
            self.assertTrue(receipt_live["published"])
            self.assertEqual(receipt_live["mode"], "live_rest_push")
            self.assertEqual(receipt_live["entities_pushed"], 12)

        # 3. Live publish partial/network failure handling
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            receipt_err = bridge.publish_to_home_assistant(pkg, dry_run=False)
            self.assertFalse(receipt_err["published"])
            self.assertEqual(receipt_err["mode"], "live_rest_push")
            self.assertTrue(all(not r["ok"] for r in receipt_err["results"]))


if __name__ == "__main__":
    unittest.main()
