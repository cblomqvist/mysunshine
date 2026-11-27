"""Home Assistant Custom Sensor Payload Models & Safety-Gated Sonnen Actuation Guard (Milestone 7).

Defines canonical Home Assistant REST `/api/states/<entity_id>` state and attribute payloads,
Long-Term Statistics (`state_class: total_increasing`, `measurement`) schemas, and the
Safety-Gated SonnenBatterie 10 Operating Mode (`EM_OperatingMode`) actuation guard.

Hardware safety architecture:
- By default, MySunshine operates strictly in **Shadow Mode** (`active_control_enabled = False`,
  `input_boolean.mysunshine_active_battery_control = off`).
- Any request to write to the SonnenBatterie 10 local API (`/api/v2/configurations` or
  `/api/v2/setpoint`) is evaluated by `SonnenSafetyActuationGate`. When the gate is locked,
  physical actuation is blocked (`would_actuate = False`) and a dry-run preview of the command
  is returned for logging and dashboard inspection.
"""

from dataclasses import dataclass, field
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
        }


class SonnenSafetyActuationGate:
    """Hardware safety gate preventing unintended physical writes to SonnenBatterie 10.

    SonnenBatterie 10 API v2 Operating Modes (`EM_OperatingMode`):
    - Mode `2`: Automatic Self-Consumption (*Eigenverbrauch* — default factory mode)
    - Mode `1`: Manual / API Setpoint Mode (`/api/v2/setpoint/charge/<watts>` or `discharge/<watts>`)
    - Mode `10`: Time-of-Use (ToU) Schedule Mode (`EM_ToU_Schedule`)

    Physical actuation is strictly forbidden unless BOTH conditions hold:
    1. `env_opt_in_enabled` (`MYSUNSHINE_ACTIVE_CONTROL_ENABLED=true`) is explicitly enabled.
    2. `ha_switch_on` (`input_boolean.mysunshine_active_battery_control == 'on'`) is active.
    """

    MODE_MANUAL_API = 1
    MODE_SELF_CONSUMPTION = 2
    MODE_TOU_SCHEDULE = 10

    def __init__(
        self,
        env_opt_in_enabled: bool = False,
        ha_switch_on: bool = False,
        sonnen_base_url: str = "http://192.168.3.125",
    ):
        self.env_opt_in_enabled = bool(env_opt_in_enabled)
        self.ha_switch_on = bool(ha_switch_on)
        self.sonnen_base_url = sonnen_base_url.rstrip("/")

    @property
    def is_unlocked(self) -> bool:
        """Return True ONLY when both environment opt-in and HA boolean switch are active."""
        return self.env_opt_in_enabled and self.ha_switch_on

    @property
    def gate_state_label(self) -> str:
        if self.is_unlocked:
            return "UNLOCKED_ACTIVE_CONTROL"
        return "LOCKED_SHADOW_MODE_ONLY"

    def evaluate_hourly_command(
        self,
        hour: int,
        timestamp_local: str,
        shadow_action: str,
        grid_precharge_kwh: float = 0.0,
        discharged_kwh: float = 0.0,
    ) -> SonnenWriteCommandPreview:
        """Translate a Shadow Mode action into a SonnenBatterie 10 API v2 command and apply safety gate."""
        if shadow_action == "GRID_PRECHARGE" and grid_precharge_kwh > 0.01:
            watts = int(round(min(6500.0, grid_precharge_kwh * 1000.0)))
            mode = self.MODE_MANUAL_API
            mode_label = "Manual API Charge Setpoint (EM_OperatingMode=1)"
            endpoint = f"{self.sonnen_base_url}/api/v2/setpoint/charge/{watts}"
            payload = {"EM_OperatingMode": "1", "setpoint_charge_w": watts}
        elif shadow_action == "HOLD_FOR_PEAK":
            watts = 0
            mode = self.MODE_MANUAL_API
            mode_label = "Manual API Hold / Zero-Discharge Setpoint (EM_OperatingMode=1, 0 W)"
            endpoint = f"{self.sonnen_base_url}/api/v2/setpoint/discharge/0"
            payload = {"EM_OperatingMode": "1", "setpoint_discharge_w": 0}
        elif shadow_action == "PEAK_DISCHARGE" and discharged_kwh > 0.01:
            watts = int(round(min(6000.0, discharged_kwh * 1000.0)))
            mode = self.MODE_SELF_CONSUMPTION
            mode_label = "Self-Consumption Peak Shaving (EM_OperatingMode=2)"
            endpoint = f"{self.sonnen_base_url}/api/v2/configurations"
            payload = {"EM_OperatingMode": "2", "expected_peak_shave_w": watts}
        else:
            watts = 0
            mode = self.MODE_SELF_CONSUMPTION
            mode_label = "Automatic Self-Consumption (EM_OperatingMode=2)"
            endpoint = f"{self.sonnen_base_url}/api/v2/configurations"
            payload = {"EM_OperatingMode": "2"}

        if self.is_unlocked:
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
