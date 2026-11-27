"""Home Assistant Custom Sensor Payload Models & Safety-Gated Sonnen Actuation Guard (Milestone 7).

Defines canonical Home Assistant REST `/api/states/<entity_id>` state and attribute payloads,
Long-Term Statistics (`state_class: total_increasing`, `measurement`) schemas, and the
Safety-Gated SonnenBatterie 10 Operating Mode (`EM_OperatingMode`) actuation guard.

Hardware safety architecture:
- By default, MySunshine operates strictly in **Shadow Mode** (`active_control_enabled = False`,
  `input_boolean.mysunshine_active_battery_control = off`).
- Home Assistant is strictly an **observer and operator UI** (`input_boolean.mysunshine_active_battery_control`).
  Home Assistant NEVER issues direct REST writes to SonnenBatterie 10 (`192.168.3.125`).
- The **sole hardware actuation path** is `HomeAssistantTelemetryBridge.execute_sonnen_command()`
  in Python, which enforces the synchronized dual safety gate, persistent disk-backed idempotency,
  live `/api/v2/status` pre-write & post-write verification, and bounded-retry verified Mode 2
  fail-safe restoration with a persistent latch on verification failure.
"""

from dataclasses import dataclass, field
import hashlib
from typing import Any, Dict, List, Optional


@dataclass
class HomeAssistantEntityPayload:
    """Represents a single Home Assistant entity state payload (`/api/states/<entity_id>`)."""
    entity_id: str
    state: Any
    friendly_name: str
    unit_of_measurement: Optional[str] = None
    device_class: Optional[str] = None
    state_class: Optional[str] = None
    icon: str = "mdi:solar-power"
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_ha_rest_payload(self) -> Dict[str, Any]:
        """Return exact JSON body expected by Home Assistant `POST /api/states/<entity_id>`."""
        merged_attrs: Dict[str, Any] = {
            "friendly_name": self.friendly_name,
            "icon": self.icon,
            "integration": "mysunshine",
        }
        if self.unit_of_measurement is not None:
            merged_attrs["unit_of_measurement"] = self.unit_of_measurement
        if self.device_class is not None:
            merged_attrs["device_class"] = self.device_class
        if self.state_class is not None:
            merged_attrs["state_class"] = self.state_class
        merged_attrs.update(self.attributes)
        return {
            "state": str(self.state),
            "attributes": merged_attrs,
        }

    def to_dict(self) -> Dict[str, Any]:
        rest_body = self.to_ha_rest_payload()
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "friendly_name": self.friendly_name,
            "unit_of_measurement": self.unit_of_measurement,
            "device_class": self.device_class,
            "state_class": self.state_class,
            "icon": self.icon,
            "attributes": rest_body["attributes"],
            "ha_rest_payload": rest_body,
        }


@dataclass
class SonnenWriteCommandPreview:
    """Preview of a SonnenBatterie 10 API v2 command evaluated by the safety actuation gate."""
    hour: int
    timestamp_local: str
    shadow_action: str
    target_operating_mode: int
    target_operating_mode_label: str
    target_power_watts: int
    endpoint: str
    http_method: str
    payload: Dict[str, Any]
    would_actuate: bool
    safety_gate_status: str
    blocked_reason: str
    actuation_semantics: str = "MANUAL_SETPOINT_OR_MODE2"
    idempotency_key: str = ""
    fail_safe_fallback_mode: int = 2
    python_executor_token: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hour": self.hour,
            "timestamp_local": self.timestamp_local,
            "shadow_action": self.shadow_action,
            "target_operating_mode": self.target_operating_mode,
            "target_operating_mode_label": self.target_operating_mode_label,
            "target_power_watts": self.target_power_watts,
            "endpoint": self.endpoint,
            "http_method": self.http_method,
            "payload": self.payload,
            "would_actuate": self.would_actuate,
            "safety_gate_status": self.safety_gate_status,
            "blocked_reason": self.blocked_reason,
            "actuation_semantics": self.actuation_semantics,
            "idempotency_key": self.idempotency_key,
            "fail_safe_fallback_mode": self.fail_safe_fallback_mode,
            "python_executor_token": self.python_executor_token,
        }


class SonnenSafetyActuationGate:
    """Hardware safety gate preventing unintended physical writes to SonnenBatterie 10.

    SonnenBatterie 10 API v2 Operating Modes (`EM_OperatingMode`):
    - Mode `2`: Automatic Self-Consumption (*Eigenverbrauch* — default factory mode)
    - Mode `1`: Manual / API Setpoint Mode (`/api/v2/setpoint/charge/<watts>` or `discharge/<watts>`)
    - Mode `10`: Time-of-Use (ToU) Schedule Mode (`EM_ToU_Schedule`)

    Physical actuation is strictly forbidden unless ALL conditions hold without conflict:
    1. `env_opt_in_enabled` (`MYSUNSHINE_ACTIVE_CONTROL_ENABLED=true` in Python) is explicitly enabled,
       and if `ha_env_opt_in_state` (`binary_sensor.mysunshine_env_active_control_opt_in`) is reported
       by Home Assistant, it must match (`"on"`) and not be stale or conflicting.
    2. `ha_switch_on` (`input_boolean.mysunshine_active_battery_control == 'on'`) is active and fresh.
    3. `emergency_latch_locked` is `False` (no unverified Mode 2 fail-safe restoration failure has occurred).
    """

    MODE_MANUAL_API = 1
    MODE_SELF_CONSUMPTION = 2
    MODE_TOU_SCHEDULE = 10

    def __init__(
        self,
        env_opt_in_enabled: Optional[bool] = False,
        ha_switch_on: Optional[bool] = False,
        ha_env_opt_in_state: Optional[Any] = None,
        sonnen_base_url: str = "http://192.168.3.125",
        min_soc_pct: float = 5.0,
        max_soc_pct: float = 100.0,
        max_charge_watts: int = 6500,
        max_discharge_watts: int = 6000,
        enable_direct_discharge_setpoint: bool = False,
        emergency_latch_locked: bool = False,
        emergency_latch_reason: Optional[str] = None,
    ):
        self._raw_env_opt_in = env_opt_in_enabled
        self._raw_ha_switch = ha_switch_on
        self.env_opt_in_enabled = bool(env_opt_in_enabled) if env_opt_in_enabled is not None else False
        self.ha_switch_on = bool(ha_switch_on) if ha_switch_on is not None else False
        self.ha_env_opt_in_state = ha_env_opt_in_state
        self.sonnen_base_url = sonnen_base_url.rstrip("/")
        self.min_soc_pct = float(min_soc_pct)
        self.max_soc_pct = float(max_soc_pct)
        self.max_charge_watts = int(max_charge_watts)
        self.max_discharge_watts = int(max_discharge_watts)
        self.enable_direct_discharge_setpoint = bool(enable_direct_discharge_setpoint)
        self.emergency_latch_locked = bool(emergency_latch_locked)
        self.emergency_latch_reason = emergency_latch_reason

    def trip_emergency_latch(self, reason: str) -> None:
        """Permanently lock out future actuation until explicitly reset."""
        self.emergency_latch_locked = True
        self.emergency_latch_reason = reason

    @staticmethod
    def _parse_ha_bool_state(val: Any) -> Optional[bool]:
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        if s in ("on", "true", "1", "yes"):
            return True
        if s in ("off", "false", "0", "no"):
            return False
        return None

    @property
    def has_gate_conflict(self) -> bool:
        """Return True if Python and Home Assistant report conflicting or missing/unknown gate states."""
        if self._raw_env_opt_in is None or self._raw_ha_switch is None:
            return True
        if self.ha_env_opt_in_state is not None:
            parsed_ha_env = self._parse_ha_bool_state(self.ha_env_opt_in_state)
            if parsed_ha_env is None:
                return True
            if parsed_ha_env != self.env_opt_in_enabled:
                return True
        return False

    @property
    def gate_conflict_reason(self) -> Optional[str]:
        if self._raw_env_opt_in is None or self._raw_ha_switch is None:
            return "Missing or undefined gate state (fail-closed)."
        if self.ha_env_opt_in_state is not None:
            parsed_ha_env = self._parse_ha_bool_state(self.ha_env_opt_in_state)
            if parsed_ha_env is None:
                return (
                    f"Home Assistant env opt-in state is invalid/unavailable "
                    f"({self.ha_env_opt_in_state!r}); failing closed."
                )
            if parsed_ha_env != self.env_opt_in_enabled:
                return (
                    f"Opt-in conflict between Python MYSUNSHINE_ACTIVE_CONTROL_ENABLED="
                    f"{self.env_opt_in_enabled} and Home Assistant "
                    f"binary_sensor.mysunshine_env_active_control_opt_in={self.ha_env_opt_in_state!r}; "
                    "failing closed."
                )
        return None

    @property
    def is_unlocked(self) -> bool:
        """Return True ONLY when emergency latch is clear, no conflict exists, and both gates are ON."""
        if self.emergency_latch_locked or self.has_gate_conflict:
            return False
        return self.env_opt_in_enabled and self.ha_switch_on

    @property
    def gate_state_label(self) -> str:
        if self.emergency_latch_locked:
            return "LOCKED_EMERGENCY_FAILSAFE_LATCH"
        if self.has_gate_conflict:
            return "LOCKED_GATE_CONFLICT_FAIL_CLOSED"
        if self.is_unlocked:
            return "UNLOCKED_ACTIVE_CONTROL"
        return "LOCKED_SHADOW_MODE_ONLY"

    @staticmethod
    def compute_idempotency_key(
        timestamp_local: str,
        shadow_action: str,
        target_operating_mode: int,
        target_power_watts: int,
    ) -> str:
        raw = f"{timestamp_local}|{shadow_action}|{target_operating_mode}|{target_power_watts}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def compute_executor_token(self, idempotency_key: str) -> str:
        """Compute cryptographic token proving Python safety gate authorized this exact command."""
        if not self.is_unlocked:
            return ""
        raw = f"PY_AUTH|{idempotency_key}|{self.env_opt_in_enabled}|{self.ha_switch_on}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _resolve_target_command(
        self,
        shadow_action: str,
        grid_precharge_kwh: float,
        discharged_kwh: float,
        current_soc_pct: Optional[float],
    ) -> tuple[int, str, int, str, Dict[str, Any], str, Optional[str]]:
        """Map shadow action and SoC bounds to target mode, label, watts, endpoint, payload, and semantics."""
        if shadow_action == "GRID_PRECHARGE" and grid_precharge_kwh > 0.01:
            return self._resolve_precharge_command(grid_precharge_kwh, current_soc_pct)
        if shadow_action == "HOLD_FOR_PEAK":
            return (
                self.MODE_MANUAL_API,
                "Manual API Hold / Zero-Discharge Setpoint (EM_OperatingMode=1, 0 W)",
                0,
                f"{self.sonnen_base_url}/api/v2/setpoint/discharge/0",
                {"EM_OperatingMode": "1", "setpoint_discharge_w": 0},
                "CONFIRMED_SONNEN_API_V2",
                None,
            )
        if shadow_action == "PEAK_DISCHARGE" and discharged_kwh > 0.01:
            return self._resolve_peak_discharge_command(discharged_kwh, current_soc_pct)
        return (
            self.MODE_SELF_CONSUMPTION,
            "Automatic Self-Consumption (EM_OperatingMode=2)",
            0,
            f"{self.sonnen_base_url}/api/v2/configurations",
            {"EM_OperatingMode": "2"},
            "CONFIRMED_SONNEN_API_V2",
            None,
        )

    def _resolve_precharge_command(
        self,
        grid_precharge_kwh: float,
        current_soc_pct: Optional[float],
    ) -> tuple[int, str, int, str, Dict[str, Any], str, Optional[str]]:
        if current_soc_pct is not None and current_soc_pct >= self.max_soc_pct:
            reason = (
                f"Battery SoC ({current_soc_pct:.1f}%) >= max SoC limit ({self.max_soc_pct:.1f}%): "
                "grid pre-charge blocked; reverting to EM_OperatingMode=2."
            )
            return (
                self.MODE_SELF_CONSUMPTION,
                "Automatic Self-Consumption (EM_OperatingMode=2 — SoC Limit Reached)",
                0,
                f"{self.sonnen_base_url}/api/v2/configurations",
                {"EM_OperatingMode": "2"},
                "SOC_CEILING_PROTECTED_MODE2",
                reason,
            )
        watts = max(0, min(self.max_charge_watts, int(round(grid_precharge_kwh * 1000.0))))
        return (
            self.MODE_MANUAL_API,
            "Manual API Charge Setpoint (EM_OperatingMode=1)",
            watts,
            f"{self.sonnen_base_url}/api/v2/setpoint/charge/{watts}",
            {"EM_OperatingMode": "1", "setpoint_charge_w": watts},
            "CONFIRMED_SONNEN_API_V2",
            None,
        )

    def _resolve_peak_discharge_command(
        self,
        discharged_kwh: float,
        current_soc_pct: Optional[float],
    ) -> tuple[int, str, int, str, Dict[str, Any], str, Optional[str]]:
        if current_soc_pct is not None and current_soc_pct <= self.min_soc_pct:
            reason = (
                f"Battery SoC ({current_soc_pct:.1f}%) <= min SoC floor ({self.min_soc_pct:.1f}%): "
                "discharge setpoint blocked; reverting to EM_OperatingMode=2."
            )
            return (
                self.MODE_SELF_CONSUMPTION,
                "Automatic Self-Consumption (EM_OperatingMode=2 — Min SoC Floor)",
                0,
                f"{self.sonnen_base_url}/api/v2/configurations",
                {"EM_OperatingMode": "2"},
                "SOC_FLOOR_PROTECTED_MODE2",
                reason,
            )
        if self.enable_direct_discharge_setpoint:
            watts = max(0, min(self.max_discharge_watts, int(round(discharged_kwh * 1000.0))))
            return (
                self.MODE_MANUAL_API,
                "Manual API Discharge Setpoint (EM_OperatingMode=1)",
                watts,
                f"{self.sonnen_base_url}/api/v2/setpoint/discharge/{watts}",
                {"EM_OperatingMode": "1", "setpoint_discharge_w": watts},
                "DIRECT_MANUAL_DISCHARGE_SETPOINT",
                None,
            )
        return (
            self.MODE_SELF_CONSUMPTION,
            "Shadow-Only Peak Shave / Passive Self-Consumption Restore (EM_OperatingMode=2, Non-Actuating Setpoint)",
            0,
            f"{self.sonnen_base_url}/api/v2/configurations",
            {"EM_OperatingMode": "2"},
            "SHADOW_ONLY_NON_ACTUATING_PEAK_SHAVE",
            None,
        )

    def evaluate_hourly_command(
        self,
        hour: int,
        timestamp_local: str,
        shadow_action: str,
        grid_precharge_kwh: float = 0.0,
        discharged_kwh: float = 0.0,
        current_soc_pct: Optional[float] = None,
    ) -> SonnenWriteCommandPreview:
        """Translate a Shadow Mode action into a SonnenBatterie 10 API v2 command and apply safety gate."""
        (
            mode,
            mode_label,
            watts,
            endpoint,
            payload,
            actuation_semantics,
            soc_violation_reason,
        ) = self._resolve_target_command(
            shadow_action=shadow_action,
            grid_precharge_kwh=grid_precharge_kwh,
            discharged_kwh=discharged_kwh,
            current_soc_pct=current_soc_pct,
        )

        idempotency_key = self.compute_idempotency_key(
            timestamp_local=timestamp_local,
            shadow_action=shadow_action,
            target_operating_mode=mode,
            target_power_watts=watts,
        )

        conflict_msg = self.gate_conflict_reason
        if self.emergency_latch_locked:
            would_actuate = False
            blocked_reason = (
                f"Emergency Fail-Safe Latch Locked ({self.emergency_latch_reason}): "
                "all future actuation disabled until manual operator reset."
            )
        elif conflict_msg:
            would_actuate = False
            blocked_reason = conflict_msg
        elif soc_violation_reason:
            would_actuate = False
            blocked_reason = soc_violation_reason
        elif actuation_semantics == "SHADOW_ONLY_NON_ACTUATING_PEAK_SHAVE":
            would_actuate = False
            blocked_reason = (
                "PEAK_DISCHARGE is non-actuating in passive Mode 2 (Sonnen Eigenverbrauch "
                "automatically covers household load without an active watt setpoint write)."
            )
        elif self.is_unlocked:
            would_actuate = True
            blocked_reason = "Active control unlocked by explicit operator opt-in + HA switch."
        else:
            would_actuate = False
            missing: List[str] = []
            if not self.env_opt_in_enabled:
                missing.append("MYSUNSHINE_ACTIVE_CONTROL_ENABLED=false")
            if not self.ha_switch_on:
                missing.append("input_boolean.mysunshine_active_battery_control=off")
            blocked_reason = (
                f"Shadow Mode Safety Gate Active ({', '.join(missing)}): "
                "physical Sonnen API write blocked; telemetry recorded for shadow verification."
            )

        executor_token = self.compute_executor_token(idempotency_key) if would_actuate else ""

        return SonnenWriteCommandPreview(
            hour=hour,
            timestamp_local=timestamp_local,
            shadow_action=shadow_action,
            target_operating_mode=mode,
            target_operating_mode_label=mode_label,
            target_power_watts=watts,
            endpoint=endpoint,
            http_method="PUT" if "configurations" in endpoint else "POST",
            payload=payload,
            would_actuate=would_actuate,
            safety_gate_status=self.gate_state_label,
            blocked_reason=blocked_reason,
            actuation_semantics=actuation_semantics,
            idempotency_key=idempotency_key,
            fail_safe_fallback_mode=self.MODE_SELF_CONSUMPTION,
            python_executor_token=executor_token,
        )


@dataclass
class HomeAssistantStatePackage:
    """Complete bundle of Home Assistant custom entities, hardware telemetry, and configuration YAML."""
    generated_at: str
    target_date: str
    ha_url: str
    sonnen_url: str
    sma_url: str
    safety_gate_status: str
    active_control_enabled: bool
    entities: List[HomeAssistantEntityPayload]
    sonnen_command_previews: List[SonnenWriteCommandPreview]
    hardware_telemetry: Dict[str, Any]
    configuration_yaml_snippet: str
    automations_yaml_snippet: str
    mqtt_discovery_topic_prefix: str = "homeassistant"

    def get_entity(self, entity_id: str) -> Optional[HomeAssistantEntityPayload]:
        for ent in self.entities:
            if ent.entity_id == entity_id:
                return ent
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "target_date": self.target_date,
            "endpoints": {
                "ha_url": self.ha_url,
                "sonnen_url": self.sonnen_url,
                "sma_url": self.sma_url,
            },
            "safety_gate": {
                "status": self.safety_gate_status,
                "active_control_enabled": self.active_control_enabled,
                "opt_in_switch_entity": "input_boolean.mysunshine_active_battery_control",
                "env_opt_in_sensor_entity": "binary_sensor.mysunshine_env_active_control_opt_in",
                "actuation_authority": "python_executor_only (HA direct Sonnen writes disabled)",
                "default_operating_mode": "Mode 2 (Eigenverbrauch / Automatic Self-Consumption)",
            },
            "entities_count": len(self.entities),
            "entities": [e.to_dict() for e in self.entities],
            "sonnen_command_previews": [c.to_dict() for c in self.sonnen_command_previews],
            "hardware_telemetry": self.hardware_telemetry,
            "configuration_yaml_snippet": self.configuration_yaml_snippet,
            "automations_yaml_snippet": self.automations_yaml_snippet,
            "mqtt_discovery_topic_prefix": self.mqtt_discovery_topic_prefix,
        }
