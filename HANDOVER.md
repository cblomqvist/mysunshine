# MySunshine Project Handover & Session State

> **Protocol**: This document serves as the single source of truth for cross-session continuity.
> 1. **Session Start**: When starting a fresh chat session or resuming after context compaction/restart, review this file and [prd.md](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/prd.md) first.
> 2. **Session / Step Close**: At the conclusion of every step or milestone:
>    * Update `HANDOVER.md` with completed work, key findings, and updated metrics.
>    * **Always include a copy-pasteable prompt for the next step/phase** in `HANDOVER.md`.
>    * **Always suggest a ready-to-use Git commit message in your chat response** when finishing a step or milestone.
>    * **Whenever a Pull Request (PR) is suitable** (e.g., upon completing a milestone or feature branch), suggest opening a PR and generate a ready-to-use **PR title and description** in your chat response.

---

## 1. Current Status & Active Milestone

* **Active Phase**: Milestone 7 (Phase 3): Home Assistant Custom Sensor Integration & Live Shadow Telemetry Bridge (**Completed & Hardened for PR #9 Review — Shadow/Telemetry-Ready Only; Physical Actuation Unverified Pending Real `SONNEN_API_TOKEN`**)
* **Current Branch**: `feat/m7-ha-shadow-telemetry-bridge`
* **Pre-Push Validation State**: **100% Green** (64 offline/mocked unit & integration tests passing + 1 live hardware test skipped without real `SONNEN_API_TOKEN`, PyYAML syntax validation passing, 0 flake8 errors/warnings in `src/ha_integration/` and `tests/test_ha_integration.py`).

---

## 2. Completed Work Summary (Milestones 5.5, 6 & 7)

### A. Milestone 7 (Phase 3): Home Assistant Custom Sensor Integration & Live Shadow Telemetry Bridge
1. **Home Assistant Custom Sensor Models & Long-Term Statistics (`src/ha_integration/sensor_models.py`)**:
   * Built `HomeAssistantEntityPayload` and `HomeAssistantStatePackage` generating canonical Home Assistant REST API payloads (`POST /api/states/<entity_id>`) with `device_class`, `state_class` (`total_increasing` and `measurement`), and rich attributes.
   * Exposed **12 custom Home Assistant entities**:
     1. `sensor.mysunshine_shadow_action` (`GRID_PRECHARGE`, includes dynamic `target_power_watts`, `target_operating_mode`, `idempotency_key`, and 24-hour schedule `hourly_schedule_24h`)
     2. `sensor.mysunshine_target_power_watts` (dynamic hourly watt setpoint for Home Assistant REST commands, eliminating hard-coded wattage)
     3. `sensor.mysunshine_breakeven_spot_ore` (`41.6 öre/kWh`, $\eta_{\text{rt}} = 76.8\%$ efficiency gate threshold)
     4. `sensor.mysunshine_expected_savings_sek` (`+9.65 SEK` shadow gain vs Default Self-Consumption)
     5. `sensor.mysunshine_recommended_precharge_kwh` (`12.43 kWh` during `03:00–05:00` night trough)
     6. `sensor.mysunshine_next_day_projected_bill_sek` (`17.67 SEK` vs `27.32 SEK` Default SC / `37.16 SEK` No Solar)
     7. `sensor.mysunshine_cumulative_savings_sek` (`72,247.07 SEK`, `state_class: total_increasing` for Home Assistant Long-Term Statistics)
     8. `sensor.mysunshine_capex_recouped_pct` (`22.94%` of `315,000 SEK` Net Capex recouped)
     9. `sensor.mysunshine_backtest_121d_upside_sek` (`+144.39 SEK` Oracle / `+109.05 SEK` Out-of-Sample Predictive / `+247.12 SEK` vs Raw Sonnen CT)
     10. `binary_sensor.mysunshine_efficiency_gate_passed` (`on`)
     11. `binary_sensor.mysunshine_env_active_control_opt_in` (`off` — Gate 1 environment / `secrets.yaml` opt-in sensor)
     12. `input_boolean.mysunshine_active_battery_control` (`off` — Gate 2 hardware safety gate switch)

2. **Fail-Closed Dual Hardware Safety Actuation Gate & Fail-Safe Executor (`SonnenSafetyActuationGate`, `HomeAssistantTelemetryBridge.execute_sonnen_command`)**:
   * Enforces the **dual safety gate across both Python and Home Assistant YAML**: physical actuation is blocked (`LOCKED_SHADOW_MODE_ONLY`) unless both `MYSUNSHINE_ACTIVE_CONTROL_ENABLED=true` (`binary_sensor.mysunshine_env_active_control_opt_in: "on"`) and `input_boolean.mysunshine_active_battery_control: "on"` pass.
   * **Verified Sonnen API v2 Semantics**: Removed unsupported `expected_peak_shave_w` configuration payloads. By default, `PEAK_DISCHARGE` is explicitly marked non-actuating (`SHADOW_ONLY_NON_ACTUATING_PEAK_SHAVE`, `would_actuate=False`, passive `EM_OperatingMode=2`), or optionally uses confirmed manual discharge setpoints (`/api/v2/setpoint/discharge/<watts>`) when `enable_direct_discharge_setpoint=True`.
   * **Fail-Safe Restoration & Bounds**: Enforces min/max SoC (`5%–100%`), max charge/discharge power (`6500 W / 6000 W`), command staleness timeout (`3900 s`), SHA-256 idempotency deduplication, post-write `/api/v2/status` verification, and automatic fail-safe restoration to `EM_OperatingMode=2` on any fault or gate lock.
   * **Strict UI Separation**: The dashboard's dry-run preview selector never alters the real gate status (`LOCKED_SHADOW_MODE_ONLY`) or entity states.

### B. Milestones 5.5 & 6 Summary (Previously Completed & Merged to `main`)
* **Milestone 5.5**: Full Day-1 (`2021–2026`, `2,143` days) historical ledger realizing **`72,247.07 SEK`** cumulative savings (**`22.94%`** of `315,000 SEK` Net Capex recouped) and **24/24 (100%)** exact integer SEK post-`Leverantörsbyte` EEM invoice matches.
* **Milestone 6**: Day-Ahead Forecaster, Shadow Mode Advisor ($\eta_{\text{rt}} = 76.8\%$ efficiency gate), and 121-day (`2,905`-hour) rolling backtest (`PV MAE = 4.47 kWh/day`, `Load MAE = 3.89 kWh/day`, `Bill MAE = 4.66 SEK/day`, `+109.05 SEK` out-of-sample predictive savings, `+144.39 SEK` oracle dispatch savings).

---

## 3. Next Prioritized Steps & Copy-Paste Session Prompt

### Next Prioritized Steps
1. **Commit, Push & Merge PR #9 for Milestone 7 (`feat/m7-ha-shadow-telemetry-bridge` $\rightarrow$ `main`)**:
   * Deploys the 100% read-only **Home Assistant Bridge** tab (`M7_RELEASE_SHADOW_TELEMETRY_ONLY = True`), 12 custom sensor schemas, Long-Term Statistics ROI entities, and observer YAML blueprints to GitHub Pages.
2. **Phase 3.2 (Milestone 7.5): Live Hardware Authentication & 7-Day Read-Only Telemetry Burn-In (`feat/m7.5-sonnen-live-read-probe`)**:
   * Provision real `SONNEN_API_TOKEN` from `http://192.168.3.125` and `HA_TOKEN` from `http://192.168.3.138:8123`, run `TestLiveSonnenHardwareStaging` (`MYSUNSHINE_RUN_LIVE_HARDWARE_TESTS=true`), verify `/api/v2/status` schema and firmware watchdog behavior, and run a 7-day read-only Phase A telemetry burn-in.
3. **Phase 3.3 (Milestone 8): Supervised Single-Window Night Pre-Charge & Fail-Safe Staging (`feat/m8-supervised-precharge-staging`)**:
   * Build `run_ha_shadow_sync.py` with watchdog heartbeat refreshes and execute supervised Phase B (`GRID_PRECHARGE` & `< 15 s` Mode 2 restore) and Phase C (fault-injection latch drill) on the physical SonnenBatterie 10.
4. **Phase 3.4 (Milestone 9): Unattended Scheduled Dispatch Daemon & Optional Direct Peak-Discharge Evaluation (`feat/m9-unattended-dispatch-daemon`)**.

### Prompt for Next Session
```text
@HANDOVER.md @prd.md Review HANDOVER.md and prd.md. Proceed with Milestone 7.5: Live Hardware Authentication, Sonnen /api/v2/status Schema Probe & 7-Day Read-Only Telemetry Burn-In Runner.
```

---

## 4. Environment & Validation Commands

* **Python Launcher (Sandbox-Safe)**:
  * `py -3.15` (invokes `C:\dev\Python315\python.exe` cleanly via `C:\Windows\py.exe`)
* **Mandatory Pre-Push Check**:
  ```bash
  py -3.15 run_checks.py
  ```
* **Test Suite**:
  ```bash
  py -3.15 -m pytest tests/ -v
  ```
* **Re-Bake Static Dashboard Package**:
  ```bash
  py -3.15 -m src.financial_engine.generate_dashboard_data
  ```
