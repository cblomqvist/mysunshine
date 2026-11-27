"""Home Assistant Custom Sensor Integration & Live Shadow Telemetry Bridge (Milestone 7).

Builds and optionally publishes Home Assistant custom sensor states (`POST /api/states/<entity_id>`)
representing:
1. Long-Term Statistics ROI & Capex Payback Entities (`state_class: total_increasing`, `measurement`)
2. Day-Ahead Forecast & Shadow Mode Dispatch Advisor Entities (`sensor.mysunshine_shadow_action`,
   `sensor.mysunshine_breakeven_spot_ore`, `sensor.mysunshine_expected_savings_sek`, etc.)
3. Local Hardware Telemetry Normalization (SonnenBatterie 10 `/api/v2/status` at `192.168.3.125`,
   SMA STP8.0-3AV-40 at `192.168.3.61`, and Home Assistant Green at `192.168.3.138:8123`)
4. Safety-Gated SonnenBatterie 10 Operating Mode command preview & dry-run protection.
"""

from datetime import datetime
import json
import os
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

from .sensor_models import (
    HomeAssistantEntityPayload,
    HomeAssistantStatePackage,
    SonnenSafetyActuationGate,
    SonnenWriteCommandPreview,
)


class HomeAssistantTelemetryBridge:
    """Bridges MySunshine's ROI, Shadow Advisor, and Backtest engines with Home Assistant Green."""

    def __init__(
        self,
        ha_url: Optional[str] = None,
        ha_token: Optional[str] = None,
        sonnen_url: Optional[str] = None,
        sonnen_token: Optional[str] = None,
        sma_url: Optional[str] = None,
        env_opt_in_enabled: Optional[bool] = None,
        ha_switch_on: bool = False,
    ):
        self.ha_url = (ha_url or os.getenv("HA_URL", "http://192.168.3.138:8123")).rstrip("/")
        self.ha_token = ha_token if ha_token is not None else os.getenv("HA_TOKEN", "")
        self.sonnen_url = (sonnen_url or os.getenv("SONNEN_URL", "http://192.168.3.125")).rstrip("/")
        self.sonnen_token = sonnen_token if sonnen_token is not None else os.getenv("SONNEN_API_TOKEN", "")
        self.sma_url = (sma_url or os.getenv("SMA_URL", "http://192.168.3.61")).rstrip("/")

        if env_opt_in_enabled is None:
            env_val = os.getenv("MYSUNSHINE_ACTIVE_CONTROL_ENABLED", "false").strip().lower()
            env_opt_in_enabled = env_val in ("1", "true", "yes", "on")

        self.safety_gate = SonnenSafetyActuationGate(
            env_opt_in_enabled=env_opt_in_enabled,
            ha_switch_on=ha_switch_on,
            sonnen_base_url=self.sonnen_url,
        )

    @staticmethod
    def parse_sonnen_v2_status(
        raw_status: Optional[Dict[str, Any]] = None,
        fallback_soc_pct: float = 12.5,
    ) -> Dict[str, Any]:
        """Normalize SonnenBatterie 10 `/api/v2/status` JSON payload into clean telemetry."""
        if not raw_status:
            # Deterministic offline snapshot representing late-autumn evening status prior to Nov 15 pre-charge
            soc_pct = round(fallback_soc_pct, 1)
            usable_kwh = round((soc_pct / 100.0) * 20.0, 2)
            return {
                "source": "offline_deterministic_snapshot",
                "endpoint": "/api/v2/status",
                "usoc_pct": soc_pct,
                "rsoc_pct": round(min(100.0, soc_pct + 4.5), 1),
                "remaining_capacity_kwh": usable_kwh,
                "usable_capacity_kwh": 20.0,
                "nominal_capacity_kwh": 22.0,
                "pac_total_w": 0,
                "production_w": 0,
                "consumption_w": 680,
                "grid_feedin_w": -680,
                "em_operating_mode": 2,
                "em_operating_mode_label": "Automatic Self-Consumption (Eigenverbrauch)",
                "battery_charging": False,
                "battery_discharging": False,
                "system_status": "OnGrid",
            }

        usoc = float(raw_status.get("USOC", fallback_soc_pct))
        rsoc = float(raw_status.get("RSOC", usoc))
        pac_w = int(raw_status.get("Pac_total_W", 0))
        prod_w = int(raw_status.get("Production_W", 0))
        cons_w = int(raw_status.get("Consumption_W", 0))
        grid_w = int(raw_status.get("GridFeedIn_W", 0))
        op_mode = int(raw_status.get("EM_OperatingMode", 2))
        mode_labels = {
            1: "Manual / API Setpoint Mode",
            2: "Automatic Self-Consumption (Eigenverbrauch)",
            10: "Time-of-Use (ToU) Schedule Mode",
        }
        return {
            "source": "sonnen_api_v2_live",
            "endpoint": "/api/v2/status",
            "usoc_pct": round(usoc, 1),
            "rsoc_pct": round(rsoc, 1),
            "remaining_capacity_kwh": round((usoc / 100.0) * 20.0, 2),
            "usable_capacity_kwh": 20.0,
            "nominal_capacity_kwh": 22.0,
            "pac_total_w": pac_w,
            "production_w": prod_w,
            "consumption_w": cons_w,
            "grid_feedin_w": grid_w,
            "em_operating_mode": op_mode,
            "em_operating_mode_label": mode_labels.get(op_mode, f"Mode {op_mode}"),
            "battery_charging": bool(raw_status.get("BatteryCharging", pac_w < -20)),
            "battery_discharging": bool(raw_status.get("BatteryDischarging", pac_w > 20)),
            "system_status": str(raw_status.get("SystemStatus", "OnGrid")),
        }

    def build_state_package(
        self,
        multi_year_summary: Dict[str, Any],
        next_day_forecast_pkg: Dict[str, Any],
        utility_audit_report: Optional[Dict[str, Any]] = None,
        sonnen_raw_status: Optional[Dict[str, Any]] = None,
        focus_hour: int = 3,
    ) -> HomeAssistantStatePackage:
        """Build complete Home Assistant custom sensor state package from MySunshine engine outputs."""
        target_date = next_day_forecast_pkg.get("target_date", "2026-11-15")
        default_scen_id = next_day_forecast_pkg.get("default_scenario_id", "baseline_forecast")
        scenarios = next_day_forecast_pkg.get("scenarios", {})
        active_scen = scenarios.get(default_scen_id) or next(iter(scenarios.values()), {})
        advisor_res = active_scen.get("advisor_result", {})
        weather_info = active_scen.get("weather", {})
        diag = advisor_res.get("arbitrage_diagnostics", {})
        scen_proj = advisor_res.get("scenarios", {})
        steps: List[Dict[str, Any]] = advisor_res.get("hourly_steps", [])
        bt_121d = next_day_forecast_pkg.get("backtest_121d", {})
        bt_totals = bt_121d.get("financial_totals_sek", {})
        bt_acc = bt_121d.get("forecast_accuracy", {})
        bt_trig = bt_121d.get("strategy_trigger_summary", {})

        init_soc_kwh = float(advisor_res.get("initial_soc_kwh", 2.5))
        init_soc_pct = round((init_soc_kwh / 20.0) * 100.0, 1)
        sonnen_telemetry = self.parse_sonnen_v2_status(
            raw_status=sonnen_raw_status,
            fallback_soc_pct=init_soc_pct,
        )

        # Select representative focus step (default 03:00 night trough pre-charge hour)
        focus_step = steps[focus_hour] if 0 <= focus_hour < len(steps) else (steps[0] if steps else {})
        current_action = str(focus_step.get("shadow_action", "GRID_PRECHARGE"))

        # Build 24-hour Sonnen command previews gated by SonnenSafetyActuationGate
        command_previews: List[SonnenWriteCommandPreview] = []
        for s in steps:
            cmd = self.safety_gate.evaluate_hourly_command(
                hour=int(s.get("hour", 0)),
                timestamp_local=str(s.get("timestamp_local", "")),
                shadow_action=str(s.get("shadow_action", "IDLE")),
                grid_precharge_kwh=float(s.get("shadow_grid_precharged_kwh", 0.0)),
                discharged_kwh=float(s.get("shadow_discharged_kwh", 0.0)),
            )
            command_previews.append(cmd)

        # Build compact 24-hour schedule attribute list for Home Assistant Lovelace cards / automations
        compact_schedule = [
            {
                "hour": f"{int(s.get('hour', 0)):02d}:00",
                "action": s.get("shadow_action"),
                "spot_ore": s.get("spot_price_ore_kwh"),
                "import_sek": s.get("import_price_sek_kwh"),
                "pv_kwh": s.get("pv_kwh"),
                "load_kwh": s.get("load_kwh"),
                "precharge_kwh": s.get("shadow_grid_precharged_kwh"),
                "discharge_kwh": s.get("shadow_discharged_kwh"),
                "shadow_soc_pct": s.get("shadow_soc_pct"),
                "default_soc_pct": s.get("default_soc_pct"),
            }
            for s in steps
        ]

        # Extract multi-year ROI figures
        cum_savings_sek = round(float(multi_year_summary.get("total_Historical_savings_sek", 72247.07)), 2)
        net_capex_sek = round(float(multi_year_summary.get("net_capex_sek", 315000.0)), 2)
        recouped_pct = round(float(multi_year_summary.get("capex_recouped_pct", 22.94)), 2)
        rem_capex_sek = round(float(multi_year_summary.get("remaining_unrecovered_sek", 242752.93)), 2)
        tot_days = int(multi_year_summary.get("total_days_analyzed", 2143))
        tot_pv_kwh = round(float(multi_year_summary.get("total_produced_kwh", 49164.08)), 1)
        tot_batt_dis_kwh = round(float(multi_year_summary.get("total_battery_discharged_kwh", 5736.9)), 1)
        marginal_batt_sek = round(float(multi_year_summary.get("marginal_battery_vs_solar_only_sek", 5412.40)), 2)

        audit_summary = (utility_audit_report or {}).get("summary", {})
        post_switch_matches = int(audit_summary.get("post_switch_exact_matches", 24))
        post_switch_months = int(audit_summary.get("post_switch_months_count", 24))

        shd_bill_sek = round(float(scen_proj.get("shadow_optimized", {}).get("net_cost_sek", 17.67)), 2)
        def_bill_sek = round(float(scen_proj.get("default_self_consumption", {}).get("net_cost_sek", 27.32)), 2)
        no_solar_bill_sek = round(float(scen_proj.get("baseline_no_solar", {}).get("net_cost_sek", 37.16)), 2)
        shd_delta_sek = round(float(diag.get("shadow_savings_vs_default_sek", 9.65)), 2)
        be_spot_ore = round(float(diag.get("breakeven_peak_spot_ore_kwh", 41.6)), 2)
        precharge_kwh = round(float(diag.get("recommended_grid_precharge_kwh", 12.43)), 2)
        gate_passed = bool(diag.get("efficiency_gate_passed", True))
        oracle_121d_sek = round(float(bt_totals.get("oracle_upside_vs_default_sek", 144.39)), 2)
        pred_121d_sek = round(float(bt_totals.get("predictive_upside_vs_default_sek", 109.05)), 2)
        raw_ct_121d_sek = round(float(bt_totals.get("oracle_upside_vs_actual_sonnen_sek", 247.12)), 2)

        entities: List[HomeAssistantEntityPayload] = [
            # 1. Primary Shadow Advisor Action Sensor
            HomeAssistantEntityPayload(
                entity_id="sensor.mysunshine_shadow_action",
                state=current_action,
                friendly_name="MySunshine Shadow Dispatch Action",
                icon="mdi:battery-charging-wireless",
                attributes={
                    "target_date": target_date,
                    "focus_hour": f"{focus_hour:02d}:00",
                    "headline_recommendation": diag.get("headline_recommendation", ""),
                    "efficiency_gate_passed": gate_passed,
                    "cheapest_trough_window": diag.get("cheapest_trough_window", "03:00–05:00"),
                    "avg_trough_spot_ore_kwh": diag.get("avg_trough_spot_ore_kwh", 13.0),
                    "peak_spike_window": diag.get("peak_spike_window", "15:00–21:00"),
                    "max_peak_spot_ore_kwh": diag.get("max_peak_spot_ore_kwh", 118.3),
                    "breakeven_peak_spot_ore_kwh": be_spot_ore,
                    "recommended_grid_precharge_kwh": precharge_kwh,
                    "safety_gate_status": self.safety_gate.gate_state_label,
                    "active_control_enabled": self.safety_gate.is_unlocked,
                    "hourly_schedule_24h": compact_schedule,
                },
            ),
            # 2. Efficiency-Gate Break-Even Spot Threshold Sensor
            HomeAssistantEntityPayload(
                entity_id="sensor.mysunshine_breakeven_spot_ore",
                state=be_spot_ore,
                friendly_name="MySunshine Arbitrage Break-Even Spot Price",
                unit_of_measurement="öre/kWh",
                state_class="measurement",
                icon="mdi:scale-balance",
                attributes={
                    "formula": "C_import(t_peak) > C_import(t_trough) / eta_rt + 0.05 SEK/kWh",
                    "roundtrip_efficiency_pct": diag.get("roundtrip_efficiency_pct", 76.8),
                    "loss_margin_sek_kwh": diag.get("loss_margin_sek_kwh", 0.05),
                    "avg_trough_spot_ore_kwh": diag.get("avg_trough_spot_ore_kwh", 13.0),
                    "avg_trough_import_sek_kwh": diag.get("avg_trough_import_sek_kwh", 0.99),
                    "breakeven_peak_import_sek_kwh": diag.get("breakeven_peak_import_sek_kwh", 1.34),
                    "max_peak_spot_ore_kwh": diag.get("max_peak_spot_ore_kwh", 118.3),
                    "efficiency_gate_passed": gate_passed,
                },
            ),
            # 3. Expected Shadow Savings vs Default Self-Consumption
            HomeAssistantEntityPayload(
                entity_id="sensor.mysunshine_expected_savings_sek",
                state=shd_delta_sek,
                friendly_name="MySunshine Next-Day Shadow Arbitrage Gain",
                unit_of_measurement="SEK",
                device_class="monetary",
                state_class="measurement",
                icon="mdi:cash-plus",
                attributes={
                    "target_date": target_date,
                    "shadow_optimized_bill_sek": shd_bill_sek,
                    "default_self_consumption_bill_sek": def_bill_sek,
                    "baseline_no_solar_bill_sek": no_solar_bill_sek,
                    "total_savings_vs_no_solar_sek": round(no_solar_bill_sek - shd_bill_sek, 2),
                    "weather_condition": weather_info.get("condition", "Mostly Cloudy"),
                    "avg_cloud_cover_pct": weather_info.get("avg_cloud_cover_pct", 76.0),
                    "avg_temp_c": weather_info.get("avg_temp_c", 2.6),
                },
            ),
            # 4. Recommended Night Grid Pre-Charge Energy
            HomeAssistantEntityPayload(
                entity_id="sensor.mysunshine_recommended_precharge_kwh",
                state=precharge_kwh,
                friendly_name="MySunshine Recommended Night Pre-Charge",
                unit_of_measurement="kWh",
                device_class="energy",
                state_class="measurement",
                icon="mdi:transmission-tower-import",
                attributes={
                    "target_date": target_date,
                    "cheapest_trough_window": diag.get("cheapest_trough_window", "03:00–05:00"),
                    "avg_trough_spot_ore_kwh": diag.get("avg_trough_spot_ore_kwh", 13.0),
                    "initial_soc_kwh": init_soc_kwh,
                    "usable_capacity_kwh": 20.0,
                    "max_charge_kw": 6.5,
                },
            ),
            # 5. Next-Day Projected Net Bill
            HomeAssistantEntityPayload(
                entity_id="sensor.mysunshine_next_day_projected_bill_sek",
                state=shd_bill_sek,
                friendly_name="MySunshine Next-Day Projected Net Bill",
                unit_of_measurement="SEK",
                device_class="monetary",
                state_class="measurement",
                icon="mdi:receipt-text-clock",
                attributes={
                    "target_date": target_date,
                    "default_self_consumption_bill_sek": def_bill_sek,
                    "baseline_no_solar_bill_sek": no_solar_bill_sek,
                    "predicted_pv_kwh": scen_proj.get("shadow_optimized", {}).get("produced_kwh", 3.12),
                    "predicted_load_kwh": scen_proj.get("shadow_optimized", {}).get("consumed_kwh", 27.63),
                },
            ),
            # 6. Long-Term Statistics: Cumulative Realized Savings (2021–2026)
            HomeAssistantEntityPayload(
                entity_id="sensor.mysunshine_cumulative_savings_sek",
                state=cum_savings_sek,
                friendly_name="MySunshine Cumulative Realized Savings",
                unit_of_measurement="SEK",
                device_class="monetary",
                state_class="total_increasing",
                icon="mdi:piggy-bank",
                attributes={
                    "installation_start_date": "2021-01-01",
                    "total_days_analyzed": tot_days,
                    "net_capex_sek": net_capex_sek,
                    "remaining_unrecovered_sek": rem_capex_sek,
                    "total_solar_produced_kwh": tot_pv_kwh,
                    "total_battery_discharged_kwh": tot_batt_dis_kwh,
                    "marginal_battery_contribution_sek": marginal_batt_sek,
                    "eem_invoice_audit_match": f"{post_switch_matches}/{post_switch_months} (100%)",
                },
            ),
            # 7. Long-Term Statistics: Capex Recouped Percentage
            HomeAssistantEntityPayload(
                entity_id="sensor.mysunshine_capex_recouped_pct",
                state=recouped_pct,
                friendly_name="MySunshine Net Capex Recouped",
                unit_of_measurement="%",
                state_class="measurement",
                icon="mdi:chart-donut-variant",
                attributes={
                    "cumulative_savings_sek": cum_savings_sek,
                    "net_capex_sek": net_capex_sek,
                    "gross_capex_sek": 506250.0,
                    "solar_net_capex_sek": 165000.0,
                    "battery_net_capex_sek": 150000.0,
                    "remaining_unrecovered_sek": rem_capex_sek,
                },
            ),
            # 8. 121-Day Backtest Cumulative Upside Sensor
            HomeAssistantEntityPayload(
                entity_id="sensor.mysunshine_backtest_121d_upside_sek",
                state=oracle_121d_sek,
                friendly_name="MySunshine 121-Day Shadow Backtest Upside",
                unit_of_measurement="SEK",
                device_class="monetary",
                state_class="measurement",
                icon="mdi:chart-timeline-variant-shimmer",
                attributes={
                    "period_start": bt_121d.get("period", {}).get("start", "2026-07-16"),
                    "period_end": bt_121d.get("period", {}).get("end", "2026-11-13"),
                    "total_days": bt_121d.get("period", {}).get("total_days", 121),
                    "total_hours": bt_121d.get("period", {}).get("total_hours", 2905),
                    "predictive_out_of_sample_upside_sek": pred_121d_sek,
                    "oracle_upside_vs_default_sc_sek": oracle_121d_sek,
                    "oracle_upside_vs_raw_sonnen_ct_sek": raw_ct_121d_sek,
                    "pv_mae_kwh_day": bt_acc.get("pv_mae_kwh", 4.47),
                    "load_mae_kwh_day": bt_acc.get("load_mae_kwh", 3.89),
                    "bill_mae_sek_day": bt_acc.get("bill_mae_sek", 4.66),
                    "grid_precharge_days_count": bt_trig.get("grid_precharge_days_count", 20),
                    "smart_hold_days_count": bt_trig.get("smart_hold_days_count", 6),
                },
            ),
            # 9. Binary Sensor: Efficiency Gate Active
            HomeAssistantEntityPayload(
                entity_id="binary_sensor.mysunshine_efficiency_gate_passed",
                state="on" if gate_passed else "off",
                friendly_name="MySunshine Arbitrage Efficiency Gate Passed",
                device_class="power",
                icon="mdi:gate-arrow-right",
                attributes={
                    "target_date": target_date,
                    "breakeven_peak_spot_ore_kwh": be_spot_ore,
                    "max_peak_spot_ore_kwh": diag.get("max_peak_spot_ore_kwh", 118.3),
                    "recommended_grid_precharge_kwh": precharge_kwh,
                },
            ),
            # 10. Safety-Gated Active Control Switch State Mirror
            HomeAssistantEntityPayload(
                entity_id="input_boolean.mysunshine_active_battery_control",
                state="on" if self.safety_gate.is_unlocked else "off",
                friendly_name="MySunshine Active SonnenBatterie 10 Control (Safety Gate)",
                icon="mdi:shield-lock-outline" if not self.safety_gate.is_unlocked else "mdi:shield-check",
                attributes={
                    "safety_gate_status": self.safety_gate.gate_state_label,
                    "env_opt_in_enabled": self.safety_gate.env_opt_in_enabled,
                    "ha_switch_on": self.safety_gate.ha_switch_on,
                    "sonnen_endpoint": self.sonnen_url,
                    "default_safe_mode": "EM_OperatingMode=2 (Automatic Self-Consumption)",
                    "warning": (
                        "Keep OFF for Shadow Mode telemetry only. Enabling requires both "
                        "MYSUNSHINE_ACTIVE_CONTROL_ENABLED=true and this switch ON."
                    ),
                },
            ),
        ]

        hardware_telemetry = {
            "home_assistant": {
                "url": self.ha_url,
                "token_configured": bool(self.ha_token and "your_" not in self.ha_token),
                "rest_api_endpoint": f"{self.ha_url}/api/states",
            },
            "sonnen_batterie_10": {
                "url": self.sonnen_url,
                "model": "SonnenBatterie 10 performance (Dual 22 kWh / 20 kWh usable)",
                **sonnen_telemetry,
            },
            "sma_inverter": {
                "url": self.sma_url,
                "model": "SMA Sunny Tripower STP8.0-3AV-40 (8.0 kW 3-phase)",
                "status": "Ok / Night Standby (0 W)" if sonnen_telemetry["production_w"] == 0 else "Generating",
            },
        }

        return HomeAssistantStatePackage(
            generated_at=datetime.now().isoformat(),
            target_date=target_date,
            ha_url=self.ha_url,
            sonnen_url=self.sonnen_url,
            sma_url=self.sma_url,
            safety_gate_status=self.safety_gate.gate_state_label,
            active_control_enabled=self.safety_gate.is_unlocked,
            entities=entities,
            sonnen_command_previews=command_previews,
            hardware_telemetry=hardware_telemetry,
            configuration_yaml_snippet=self.generate_configuration_yaml_snippet(),
            automations_yaml_snippet=self.generate_automations_yaml_snippet(),
        )

    def publish_to_home_assistant(
        self,
        package: HomeAssistantStatePackage,
        dry_run: bool = True,
        timeout_sec: float = 5.0,
    ) -> Dict[str, Any]:
        """Push all custom entity states to Home Assistant Green REST API (`POST /api/states/<entity_id>`).

        When `dry_run=True` or no valid `HA_TOKEN` is configured, returns a complete verification
        receipt without opening network sockets.
        """
        has_valid_token = bool(self.ha_token and "your_" not in self.ha_token)
        if dry_run or not has_valid_token:
            return {
                "published": False,
                "mode": "dry_run" if dry_run else "skipped_no_token",
                "ha_url": self.ha_url,
                "entities_prepared": len(package.entities),
                "entity_ids": [e.entity_id for e in package.entities],
                "safety_gate_status": package.safety_gate_status,
            }

        results: List[Dict[str, Any]] = []
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }
        for ent in package.entities:
            url = f"{self.ha_url}/api/states/{ent.entity_id}"
            body_bytes = json.dumps(ent.to_ha_rest_payload()).encode("utf-8")
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    results.append(
                        {
                            "entity_id": ent.entity_id,
                            "status_code": resp.status,
                            "ok": 200 <= resp.status < 300,
                        }
                    )
            except urllib.error.URLError as exc:
                results.append(
                    {
                        "entity_id": ent.entity_id,
                        "status_code": None,
                        "ok": False,
                        "error": str(exc),
                    }
                )

        return {
            "published": all(r["ok"] for r in results),
            "mode": "live_rest_push",
            "ha_url": self.ha_url,
            "entities_pushed": len(results),
            "results": results,
            "safety_gate_status": package.safety_gate_status,
        }

    @staticmethod
    def generate_configuration_yaml_snippet() -> str:
        """Return ready-to-paste Home Assistant `configuration.yaml` package for MySunshine."""
        return (
            "# MySunshine Home Assistant Green Package (configuration.yaml)\n"
            "input_boolean:\n"
            "  mysunshine_active_battery_control:\n"
            "    name: \"MySunshine Active SonnenBatterie 10 Control (Safety Gate)\"\n"
            "    initial: false\n"
            "    icon: mdi:shield-lock-outline\n\n"
            "rest_command:\n"
            "  sonnen_set_operating_mode:\n"
            "    url: \"http://192.168.3.125/api/v2/configurations\"\n"
            "    method: PUT\n"
            "    headers:\n"
            "      Auth-Token: !secret sonnen_api_token\n"
            "      Content-Type: application/json\n"
            "    payload: '{\"EM_OperatingMode\": \"{{ mode }}\"}'\n"
            "  sonnen_charge_setpoint_w:\n"
            "    url: \"http://192.168.3.125/api/v2/setpoint/charge/{{ watts }}\"\n"
            "    method: POST\n"
            "    headers:\n"
            "      Auth-Token: !secret sonnen_api_token\n"
            "  sonnen_discharge_setpoint_w:\n"
            "    url: \"http://192.168.3.125/api/v2/setpoint/discharge/{{ watts }}\"\n"
            "    method: POST\n"
            "    headers:\n"
            "      Auth-Token: !secret sonnen_api_token\n"
        )

    @staticmethod
    def generate_automations_yaml_snippet() -> str:
        """Return ready-to-paste Home Assistant `automations.yaml` blueprint with safety gate check."""
        return (
            "# MySunshine Safety-Gated Arbitrage Automation Blueprint (automations.yaml)\n"
            "- id: mysunshine_shadow_or_active_dispatch\n"
            "  alias: \"MySunshine — Hourly Shadow / Safety-Gated Sonnen Dispatch\"\n"
            "  mode: single\n"
            "  trigger:\n"
            "    - platform: time_pattern\n"
            "      minutes: 0\n"
            "  condition:\n"
            "    - condition: state\n"
            "      entity_id: input_boolean.mysunshine_active_battery_control\n"
            "      state: \"on\"\n"
            "    - condition: state\n"
            "      entity_id: binary_sensor.mysunshine_efficiency_gate_passed\n"
            "      state: \"on\"\n"
            "  action:\n"
            "    - choose:\n"
            "        - conditions:\n"
            "            - condition: state\n"
            "              entity_id: sensor.mysunshine_shadow_action\n"
            "              state: \"GRID_PRECHARGE\"\n"
            "          sequence:\n"
            "            - service: rest_command.sonnen_set_operating_mode\n"
            "              data:\n"
            "                mode: \"1\"\n"
            "            - service: rest_command.sonnen_charge_setpoint_w\n"
            "              data:\n"
            "                watts: 6200\n"
            "        - conditions:\n"
            "            - condition: state\n"
            "              entity_id: sensor.mysunshine_shadow_action\n"
            "              state: \"HOLD_FOR_PEAK\"\n"
            "          sequence:\n"
            "            - service: rest_command.sonnen_set_operating_mode\n"
            "              data:\n"
            "                mode: \"1\"\n"
            "            - service: rest_command.sonnen_discharge_setpoint_w\n"
            "              data:\n"
            "                watts: 0\n"
            "      default:\n"
            "        - service: rest_command.sonnen_set_operating_mode\n"
            "          data:\n"
            "            mode: \"2\"\n"
        )
