"""Unit & Integration Tests for Milestone 7: Home Assistant Custom Sensor Integration & Telemetry Bridge."""

from datetime import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import yaml

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


class _HomeAssistantYAMLValidatorLoader(yaml.SafeLoader):
    """YAML SafeLoader supporting Home Assistant's `!secret` tag outside Jinja templates."""


_HomeAssistantYAMLValidatorLoader.add_constructor(
    "!secret",
    lambda loader, node: f"__HA_SECRET__:{loader.construct_scalar(node)}",
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

    def _new_temp_state_path(self) -> str:
        fd, path = tempfile.mkstemp(prefix="mysunshine_test_exec_", suffix=".json")
        os.close(fd)
        os.unlink(path)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return path

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
        self.assertEqual(cmd_ff.python_executor_token, "")
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
        self.assertEqual(cmd_ft.python_executor_token, "")

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
        self.assertEqual(cmd_tf.python_executor_token, "")

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
        self.assertNotEqual(cmd_tt.python_executor_token, "")

    def test_ha_and_python_opt_in_conflict_and_stale_ha_entities(self):
        """Verify conflicting gate states and stale HA entities fail closed."""
        store_path = self._new_temp_state_path()
        bridge_conflict = HomeAssistantTelemetryBridge(
            ha_token="valid_ha_token",
            sonnen_token="valid_sonnen_token",
            env_opt_in_enabled=True,
            ha_switch_on=True,
            ha_env_opt_in_state="off",
            state_store_path=store_path,
        )
        self.assertTrue(bridge_conflict.safety_gate.has_gate_conflict)
        self.assertFalse(bridge_conflict.safety_gate.is_unlocked)
        self.assertEqual(bridge_conflict.safety_gate.gate_state_label, "LOCKED_GATE_CONFLICT_FAIL_CLOSED")

        cmd = bridge_conflict.safety_gate.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=5.0,
        )
        self.assertFalse(cmd.would_actuate)

        # Also test synchronize_and_verify_gates_with_ha detecting a stale HA Gate 2 entity
        bridge_sync = HomeAssistantTelemetryBridge(
            ha_token="valid_ha_token",
            sonnen_token="valid_sonnen_token",
            env_opt_in_enabled=True,
            ha_switch_on=True,
            ha_entity_max_age_seconds=3600,
            state_store_path=self._new_temp_state_path(),
        )
        now_dt = datetime.fromisoformat("2026-11-15T03:30:00")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _FakeHTTPResponse(200, {}),  # POST binary_sensor.mysunshine_env_active_control_opt_in
                _FakeHTTPResponse(
                    200,
                    {"state": "on", "last_updated": "2026-11-15T03:29:00"},
                ),  # GET Gate 1 (fresh)
                _FakeHTTPResponse(
                    200,
                    {"state": "on", "last_updated": "2026-11-15T01:00:00"},
                ),  # GET Gate 2 (stale: 9000s old > 3600s!)
            ]
            sync_res = bridge_sync.synchronize_and_verify_gates_with_ha(reference_now=now_dt)
            self.assertFalse(sync_res["ok"])
            self.assertEqual(sync_res["reason"], "stale_ha_gate2_entity")
            self.assertFalse(bridge_sync.safety_gate.is_unlocked)

        # And test synchronize_and_verify_gates_with_ha detecting a conflicting HA Gate 1 readback
        bridge_sync_conflict = HomeAssistantTelemetryBridge(
            ha_token="valid_ha_token",
            sonnen_token="valid_sonnen_token",
            env_opt_in_enabled=True,
            ha_switch_on=True,
            state_store_path=self._new_temp_state_path(),
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _FakeHTTPResponse(200, {}),  # POST Gate 1
                _FakeHTTPResponse(
                    200,
                    {"state": "off", "last_updated": "2026-11-15T03:29:30"},
                ),  # GET Gate 1 (conflicting 'off' vs Python True!)
                _FakeHTTPResponse(
                    200,
                    {"state": "on", "last_updated": "2026-11-15T03:29:30"},
                ),  # GET Gate 2
            ]
            sync_conf_res = bridge_sync_conflict.synchronize_and_verify_gates_with_ha(reference_now=now_dt)
            self.assertFalse(sync_conf_res["ok"])
            self.assertEqual(sync_conf_res["reason"], "gate_conflict_fail_closed")
            self.assertFalse(bridge_sync_conflict.safety_gate.is_unlocked)

    def test_yaml_validation_no_ha_direct_sonnen_writes_and_authenticated_usoc(self):
        """Verify Home Assistant YAML has no direct Sonnen rest_command writes and uses Auth-Token for USOC."""
        bridge = HomeAssistantTelemetryBridge(
            env_opt_in_enabled=False,
            ha_switch_on=False,
            state_store_path=self._new_temp_state_path(),
        )
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

        w_h3 = int(pkg_h3.get_entity("sensor.mysunshine_target_power_watts").state)
        w_h4 = int(pkg_h4.get_entity("sensor.mysunshine_target_power_watts").state)
        self.assertGreater(w_h3, 0)
        self.assertGreater(w_h4, 0)
        self.assertNotEqual(w_h3, w_h4)

        auto_yaml = pkg_h3.automations_yaml_snippet
        cfg_yaml = pkg_h3.configuration_yaml_snippet

        # 1. Parse both YAML snippets with PyYAML
        parsed_cfg = yaml.load(cfg_yaml, Loader=_HomeAssistantYAMLValidatorLoader)
        parsed_auto = yaml.load(auto_yaml, Loader=_HomeAssistantYAMLValidatorLoader)
        self.assertIsInstance(parsed_cfg, dict)
        self.assertIsInstance(parsed_auto, list)

        # 2. Verify NO direct Home Assistant `rest_command` Sonnen writes exist in configuration or automations
        self.assertNotIn("rest_command", parsed_cfg)
        self.assertNotIn("rest_command.", auto_yaml)
        self.assertNotIn("/api/v2/setpoint", cfg_yaml)
        self.assertNotIn("/api/v2/configurations", cfg_yaml)
        self.assertNotIn("(!secret", cfg_yaml)

        # 3. Verify authenticated live USOC fetching in Home Assistant REST sensor
        rest_sensors = parsed_cfg.get("sensor", [])
        self.assertEqual(len(rest_sensors), 1)
        self.assertEqual(rest_sensors[0]["headers"]["Auth-Token"], "__HA_SECRET__:sonnen_api_token")
        self.assertIn("USOC", rest_sensors[0]["json_attributes"])

    def test_ha_or_external_actuation_bypass_attempt_rejected(self):
        """Verify any attempt to invoke execute_sonnen_command without valid Python executor token/authority fails."""
        bridge = HomeAssistantTelemetryBridge(
            sonnen_token="valid_test_sonnen_token",
            env_opt_in_enabled=True,
            ha_switch_on=True,
            state_store_path=self._new_temp_state_path(),
        )
        cmd = bridge.safety_gate.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=4.5,
        )
        valid_now = datetime.fromisoformat("2026-11-15T03:05:00")

        # Bypass attempt 1: Caller authority is Home Assistant instead of python_executor
        res_ha_bypass = bridge.execute_sonnen_command(
            cmd,
            dry_run=True,
            reference_now=valid_now,
            caller_authority="home_assistant_automation",
        )
        self.assertFalse(res_ha_bypass["executed"])
        self.assertTrue(res_ha_bypass["blocked"])
        self.assertEqual(res_ha_bypass["reason"], "unauthorized_actuation_bypass_rejected")

        # Bypass attempt 2: Forged or missing python_executor_token
        forged_cmd = bridge.safety_gate.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=4.5,
        )
        forged_cmd.python_executor_token = "forged_token_from_external_caller"
        res_forged = bridge.execute_sonnen_command(
            forged_cmd,
            dry_run=True,
            reference_now=valid_now,
            caller_authority="python_executor",
        )
        self.assertFalse(res_forged["executed"])
        self.assertTrue(res_forged["blocked"])
        self.assertEqual(res_forged["reason"], "unauthorized_actuation_bypass_rejected")

    def test_peak_discharge_semantics_and_separate_charge_discharge_power_limits(self):
        """Verify PEAK_DISCHARGE passive vs direct modes and separate charge (6500 W) / discharge (6000 W) limits."""
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
        self.assertFalse(cmd_passive.would_actuate)
        self.assertEqual(cmd_passive.actuation_semantics, "SHADOW_ONLY_NON_ACTUATING_PEAK_SHAVE")

        bridge_direct = HomeAssistantTelemetryBridge(
            sonnen_token="valid_test_sonnen_token",
            env_opt_in_enabled=True,
            ha_switch_on=True,
            max_charge_watts=6500,
            max_discharge_watts=6000,
            enable_direct_discharge_setpoint=True,
            state_store_path=self._new_temp_state_path(),
        )
        cmd_direct = bridge_direct.safety_gate.evaluate_hourly_command(
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

        # Separate charge (6500 W) vs discharge (6000 W) power limit check
        valid_now = datetime.fromisoformat("2026-11-15T17:05:00")
        cmd_over_discharge = bridge_direct.safety_gate.evaluate_hourly_command(
            hour=17,
            timestamp_local="2026-11-15T17:00:00",
            shadow_action="PEAK_DISCHARGE",
            discharged_kwh=2.0,
        )
        cmd_over_discharge.target_power_watts = 6300  # > 6000 W max_discharge_watts
        res_over_dis = bridge_direct.execute_sonnen_command(
            cmd_over_discharge,
            dry_run=True,
            reference_now=valid_now,
            current_status={"USOC": 50.0, "EM_OperatingMode": 2},
        )
        self.assertFalse(res_over_dis["executed"])
        self.assertTrue(res_over_dis["blocked"])
        self.assertEqual(res_over_dis["reason"], "power_limit_exceeded")
        self.assertIn("max_discharge_watts (6000 W)", res_over_dis["detail"])

        cmd_over_charge = bridge_direct.safety_gate.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=6.3,
        )
        res_ok_chg = bridge_direct.execute_sonnen_command(
            cmd_over_charge,
            dry_run=True,
            reference_now=datetime.fromisoformat("2026-11-15T03:05:00"),
            current_status={"USOC": 20.0, "EM_OperatingMode": 2},
        )
        self.assertFalse(res_ok_chg["blocked"])
        self.assertEqual(res_ok_chg["target_power_watts"], 6300)

        cmd_over_charge.target_power_watts = 6600  # > 6500 W max_charge_watts
        res_over_chg = bridge_direct.execute_sonnen_command(
            cmd_over_charge,
            dry_run=True,
            reference_now=datetime.fromisoformat("2026-11-15T03:05:00"),
            current_status={"USOC": 20.0, "EM_OperatingMode": 2},
        )
        self.assertTrue(res_over_chg["blocked"])
        self.assertEqual(res_over_chg["reason"], "power_limit_exceeded")
        self.assertIn("max_charge_watts (6500 W)", res_over_chg["detail"])

    def test_live_usoc_validation_persistent_idempotency_and_verified_mode2_retry_exhaustion(self):
        """Verify mandatory live /api/v2/status fetch, stale/unavailable USOC rejection, post-write
        setpoint effect verification, disk-persisted idempotency across process restarts, and
        bounded-retry Mode 2 verification failure tripping the persistent emergency latch.
        """
        store_path = self._new_temp_state_path()
        bridge = HomeAssistantTelemetryBridge(
            sonnen_token="valid_test_sonnen_token",
            env_opt_in_enabled=True,
            ha_switch_on=True,
            min_soc_pct=10.0,
            max_soc_pct=95.0,
            status_max_age_seconds=120,
            state_store_path=store_path,
            mode2_restore_max_attempts=3,
            mode2_restore_poll_attempts=2,
        )
        cmd_chg = bridge.safety_gate.evaluate_hourly_command(
            hour=3,
            timestamp_local="2026-11-15T03:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=4.5,
        )
        valid_now = datetime.fromisoformat("2026-11-15T03:05:00")

        # 1. Missing or stale command timestamp rejected
        cmd_no_ts = bridge.safety_gate.evaluate_hourly_command(
            hour=3,
            timestamp_local="",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=4.5,
        )
        res_no_ts = bridge.execute_sonnen_command(cmd_no_ts, dry_run=True, reference_now=valid_now)
        self.assertTrue(res_no_ts["blocked"])
        self.assertEqual(res_no_ts["reason"], "missing_or_invalid_timestamp")

        # 2. Live USOC string 'unavailable' or stale status timestamp rejected even if caller passed current_status
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _FakeHTTPResponse(200, {"USOC": "unavailable", "EM_OperatingMode": 2}),  # Live pre-check GET
                _FakeHTTPResponse(200, {"EM_OperatingMode": "2"}),  # Fail-safe PUT Mode 2
                _FakeHTTPResponse(200, {"USOC": 50.0, "EM_OperatingMode": 2}),  # Fail-safe verify GET Mode 2
            ]
            res_unavail = bridge.execute_sonnen_command(
                cmd_chg,
                dry_run=False,
                reference_now=valid_now,
                current_status={"USOC": 50.0, "EM_OperatingMode": 2},  # Ignored in live mode!
            )
            self.assertFalse(res_unavail["executed"])
            self.assertTrue(res_unavail["blocked"])
            self.assertEqual(res_unavail["reason"], "live_status_unavailable_or_missing_usoc")
            self.assertTrue(res_unavail["fail_safe_restore"]["restored_to_mode_2"])

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _FakeHTTPResponse(
                    200,
                    {"USOC": 40.0, "EM_OperatingMode": 2, "Timestamp": "2026-11-15T02:50:00"},
                ),  # Stale status timestamp (900s > 120s)!
                _FakeHTTPResponse(200, {"EM_OperatingMode": "2"}),  # Fail-safe PUT Mode 2
                _FakeHTTPResponse(200, {"USOC": 40.0, "EM_OperatingMode": 2}),  # Fail-safe verify GET Mode 2
            ]
            res_stale_usoc = bridge.execute_sonnen_command(
                cmd_chg,
                dry_run=False,
                reference_now=valid_now,
            )
            self.assertFalse(res_stale_usoc["executed"])
            self.assertTrue(res_stale_usoc["blocked"])
            self.assertEqual(res_stale_usoc["reason"], "stale_usoc_status_rejected")
            self.assertTrue(res_stale_usoc["fail_safe_restore"]["restored_to_mode_2"])

        # 3. Post-write setpoint effect mismatch (discharging during GRID_PRECHARGE) triggers Mode 2 restore
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _FakeHTTPResponse(200, {"USOC": 20.0, "EM_OperatingMode": 2}),  # Pre-write GET
                _FakeHTTPResponse(200, {"EM_OperatingMode": "1"}),  # PUT Mode 1
                _FakeHTTPResponse(200, {}),  # POST charge setpoint
                _FakeHTTPResponse(
                    200,
                    {
                        "USOC": 20.0,
                        "EM_OperatingMode": 1,
                        "Pac_total_W": 1800,
                        "BatteryDischarging": True,
                    },
                ),  # Post-write GET: Mode 1 ok, but discharging instead of charging!
                _FakeHTTPResponse(200, {"EM_OperatingMode": "2"}),  # Fail-safe PUT Mode 2
                _FakeHTTPResponse(200, {"USOC": 20.0, "EM_OperatingMode": 2}),  # Fail-safe verify GET Mode 2
            ]
            res_effect_fail = bridge.execute_sonnen_command(
                cmd_chg,
                dry_run=False,
                reference_now=valid_now,
            )
            self.assertFalse(res_effect_fail["executed"])
            self.assertEqual(res_effect_fail["mode"], "failed_with_failsafe_restore")
            self.assertIn("setpoint effect mismatch", res_effect_fail["error"])
            self.assertTrue(res_effect_fail["fail_safe_restore"]["restored_to_mode_2"])

        # 4. Live execution success + persistent idempotency surviving process restart (new bridge instance)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _FakeHTTPResponse(200, {"USOC": 20.0, "EM_OperatingMode": 2}),  # Pre-write GET
                _FakeHTTPResponse(200, {"EM_OperatingMode": "1"}),  # PUT Mode 1
                _FakeHTTPResponse(200, {}),  # POST charge setpoint 4500W
                _FakeHTTPResponse(
                    200,
                    {
                        "USOC": 21.0,
                        "EM_OperatingMode": 1,
                        "Pac_total_W": -4450,
                        "BatteryCharging": True,
                        "BatteryDischarging": False,
                    },
                ),  # Post-write GET verifies BOTH Mode 1 AND charging effect
            ]
            res_live = bridge.execute_sonnen_command(
                cmd_chg,
                dry_run=False,
                reference_now=valid_now,
            )
            self.assertTrue(res_live["executed"])
            self.assertEqual(res_live["verified_operating_mode"], 1)
            self.assertEqual(res_live["verified_pac_total_w"], -4450)

        # Simulate process restart by instantiating a brand-new HomeAssistantTelemetryBridge pointing to store_path
        restarted_bridge = HomeAssistantTelemetryBridge(
            sonnen_token="valid_test_sonnen_token",
            env_opt_in_enabled=True,
            ha_switch_on=True,
            state_store_path=store_path,
        )
        res_dup_after_restart = restarted_bridge.execute_sonnen_command(
            cmd_chg,
            dry_run=False,
            reference_now=valid_now,
        )
        self.assertFalse(res_dup_after_restart["executed"])
        self.assertTrue(res_dup_after_restart["blocked"])
        self.assertEqual(res_dup_after_restart["reason"], "duplicate_idempotency_key_blocked")

        # 5. Bounded-retry Mode 2 verification exhaustion trips persistent emergency latch across restarts
        cmd_chg_h4 = restarted_bridge.safety_gate.evaluate_hourly_command(
            hour=4,
            timestamp_local="2026-11-15T04:00:00",
            shadow_action="GRID_PRECHARGE",
            grid_precharge_kwh=5.0,
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                _FakeHTTPResponse(200, {"USOC": 30.0, "EM_OperatingMode": 2}),  # Pre-write GET
                _FakeHTTPResponse(200, {"EM_OperatingMode": "1"}),  # PUT Mode 1
                _FakeHTTPResponse(500, {}),  # POST setpoint fails (HTTP 500) -> triggers restore_sonnen_safe_mode
                # Attempt 1 of Mode 2 restore: PUT succeeds, but 2 polls still report Mode 1!
                _FakeHTTPResponse(200, {"EM_OperatingMode": "2"}),
                _FakeHTTPResponse(200, {"USOC": 30.0, "EM_OperatingMode": 1}),
                _FakeHTTPResponse(200, {"USOC": 30.0, "EM_OperatingMode": 1}),
                # Attempt 2 of Mode 2 restore: PUT succeeds, 2 polls still report Mode 1!
                _FakeHTTPResponse(200, {"EM_OperatingMode": "2"}),
                _FakeHTTPResponse(200, {"USOC": 30.0, "EM_OperatingMode": 1}),
                _FakeHTTPResponse(200, {"USOC": 30.0, "EM_OperatingMode": 1}),
                # Attempt 3 of Mode 2 restore: PUT succeeds, 2 polls still report Mode 1!
                _FakeHTTPResponse(200, {"EM_OperatingMode": "2"}),
                _FakeHTTPResponse(200, {"USOC": 30.0, "EM_OperatingMode": 1}),
                _FakeHTTPResponse(200, {"USOC": 30.0, "EM_OperatingMode": 1}),
            ]
            res_exhausted = restarted_bridge.execute_sonnen_command(
                cmd_chg_h4,
                dry_run=False,
                reference_now=datetime.fromisoformat("2026-11-15T04:05:00"),
            )
            self.assertFalse(res_exhausted["executed"])
            self.assertFalse(res_exhausted["fail_safe_restore"]["restored_to_mode_2"])
            self.assertFalse(res_exhausted["fail_safe_restore"]["verified_mode_2"])
            self.assertEqual(res_exhausted["fail_safe_restore"]["attempts"], 3)
            self.assertTrue(res_exhausted["fail_safe_restore"]["emergency_latch_locked"])
            self.assertTrue(restarted_bridge.safety_gate.emergency_latch_locked)
            self.assertFalse(restarted_bridge.safety_gate.is_unlocked)

        # Simulate another process restart: emergency latch remains locked on disk and blocks all future commands
        post_latch_bridge = HomeAssistantTelemetryBridge(
            sonnen_token="valid_test_sonnen_token",
            env_opt_in_enabled=True,
            ha_switch_on=True,
            state_store_path=store_path,
        )
        self.assertTrue(post_latch_bridge.safety_gate.emergency_latch_locked)
        self.assertFalse(post_latch_bridge.safety_gate.is_unlocked)
        self.assertEqual(post_latch_bridge.safety_gate.gate_state_label, "LOCKED_EMERGENCY_FAILSAFE_LATCH")

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
            sonnen_token="valid_sonnen_token",
            env_opt_in_enabled=False,
            ha_switch_on=False,
            state_store_path=self._new_temp_state_path(),
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
            self.assertIsNone(receipt_live["fail_safe_restore"])

        # 3. Live publish partial/network failure triggers automatic fail-safe Mode 2 restoration
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            receipt_err = bridge.publish_to_home_assistant(pkg, dry_run=False)
            self.assertFalse(receipt_err["published"])
            self.assertEqual(receipt_err["mode"], "live_rest_push")
            self.assertTrue(all(not r["ok"] for r in receipt_err["results"]))
            self.assertIsNotNone(receipt_err["fail_safe_restore"])
            self.assertFalse(receipt_err["fail_safe_restore"]["restored_to_mode_2"])


if __name__ == "__main__":
    unittest.main()
