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

* **Active Phase**: Milestone 7 (Phase 3.1): Home Assistant Custom Sensor Integration & Read-Only Shadow Telemetry Bridge (**Completed & Merged to `main` — Data Updated through Nov 26, 2026**)
* **Current Branch**: `main`
* **Pre-Push Validation State**: **100% Green** (`64 passed, 1 hardware test skipped` across `65 collected tests`, PyYAML syntax validation passing with zero write-capable Sonnen `rest_command` definitions, 0 flake8 errors/warnings in `src/ha_integration/` and `tests/test_ha_integration.py`).

---

## 2. Completed Work Summary (Milestones 5.5, 6, 7 & Nov 27 Data Update)

### A. Data Ingestion Update (`sonnen_energy_data_Fri_Nov_27_2026.csv` — Nov 28, 2026)
1. **High-Resolution Energy & Spot Price Expansion (`2026-07-16` through `2026-11-26`)**:
   * Ingested `data/sonnen_energy_data_Fri_Nov_27_2026.csv` (`744` hourly records covering `2026-10-27` to `2026-11-26`), extending continuous deduplicated high-resolution coverage from `121` days (`2,905` hours) to **`134` days (`3,217` hours)**.
   * Fetched and cached `1,336` 15-minute SE3 spot prices from ENTSO-E (`2026-11-15` to `2026-11-28`) in `data/prices/auto_SE3_20261115_20261128.json` and `data/prices/entsoe_SE3_20261115_20261128.json`, and merged into `data/prices/se3_prices_2026.json` (**`31,485`** total 2026 points).
   * Aggregated `13` new complete daily records (`2026-11-14` through `2026-11-26`) into `data/sonnen_energy_data_2026.csv` (**`330` days** in 2026 YTD; **`2,156` total days** across `2021–2026`).
   * Updated empirical diurnal battery import/maintenance grid-charge calibration in `src/financial_engine/baseline.py` (`Actual System Net Cost` variance `-0.22%` / `-2.25 SEK` across `3,217` hours) and re-baked `data/dashboard_data.json` and `data/dashboard_data.js` (**`72,185.28 SEK`** cumulative savings, **`22.92%`** of `315,000 SEK` Net Capex recouped; `134`-day backtest upside **`+204.82 SEK`** Oracle / **`+158.48 SEK`** Out-of-Sample Predictive / **`+384.46 SEK`** vs Raw Sonnen CT across `31` pre-charge days and `6` smart-hold days).

### B. Milestone 7 (Phase 3.1): Home Assistant Custom Sensor Integration & Read-Only Shadow Telemetry Bridge
1. **Home Assistant Custom Sensor Models & Long-Term Statistics (`src/ha_integration/sensor_models.py`)**:
   * Built `HomeAssistantEntityPayload` and `HomeAssistantStatePackage` generating canonical Home Assistant REST API payloads (`POST /api/states/<entity_id>`) with `device_class`, `state_class` (`total_increasing` and `measurement`), and rich attributes.
   * Exposed **12 custom Home Assistant entities**:
     1. `sensor.mysunshine_shadow_action` (`GRID_PRECHARGE`, includes dynamic `target_power_watts`, `target_operating_mode`, `idempotency_key`, and 24-hour schedule `hourly_schedule_24h`)
     2. `sensor.mysunshine_target_power_watts` (dynamic hourly watt setpoint, eliminating hard-coded wattage)
     3. `sensor.mysunshine_breakeven_spot_ore` (`41.6 öre/kWh`, $\eta_{\text{rt}} = 76.8\%$ efficiency gate threshold)
     4. `sensor.mysunshine_expected_savings_sek` (`+9.65 SEK` shadow gain vs Default Self-Consumption)
     5. `sensor.mysunshine_recommended_precharge_kwh` (`12.43 kWh` during `03:00–05:00` night trough)
     6. `sensor.mysunshine_next_day_projected_bill_sek` (`17.67 SEK` vs `27.32 SEK` Default SC / `37.16 SEK` No Solar)
     7. `sensor.mysunshine_cumulative_savings_sek` (`72,247.07 SEK`, `state_class: total_increasing` for Home Assistant Long-Term Statistics)
     8. `sensor.mysunshine_capex_recouped_pct` (`22.94%` of `315,000 SEK` Net Capex recouped)
     9. `sensor.mysunshine_backtest_121d_upside_sek` (`+144.39 SEK` Oracle / `+109.05 SEK` Out-of-Sample Predictive / `+247.12 SEK` vs Raw Sonnen CT)
     10. `binary_sensor.mysunshine_efficiency_gate_passed` (`on`)
     11. `binary_sensor.mysunshine_env_active_control_opt_in` (`off` — Gate 1 authoritative Python environment opt-in mirror)
     12. `input_boolean.mysunshine_active_battery_control` (`off` — Gate 2 Home Assistant operator UI switch)

2. **Read-Only Shadow Telemetry Lock & Hardened Safety Executor Architecture (`SonnenSafetyActuationGate`, `HomeAssistantTelemetryBridge`)**:
   * **Read-Only Shadow Telemetry Scope (`M7_RELEASE_SHADOW_TELEMETRY_ONLY = True`)**: Milestone 7 performs **read-only shadow telemetry, no live Sonnen writes, and no live Sonnen hardware verification**.
   * **Zero Write-Capable Home Assistant `rest_command` Definitions**: Removed all write-capable `rest_command` entries from `configuration.yaml` and `automations.yaml`. Home Assistant is strictly an observer and Gate 2 UI controller.
   * **Canonical Command Registry & Centralized HA Gate Read-Back**: Validates candidate commands against an internal canonical command registry (no published executor tokens), requires fresh read-back synchronization of Gate 1 and Gate 2 from Home Assistant before any future live write, and enforces durable non-temp atomic disk persistence (`data/runtime/ha_executor_state.json`), SoC/power bounds, and bounded-retry verified fail-safe restoration to `EM_OperatingMode=2`.
   * **Strict UI Separation**: The dashboard's dry-run preview selector never alters the real gate status (`LOCKED_SHADOW_MODE_ONLY`) or entity states.

### C. Milestones 5.5 & 6 Summary (Previously Completed & Merged to `main`)
* **Milestone 5.5**: Full Day-1 (`2021–2026`, `2,156` days through Nov 26, 2026) historical ledger realizing **`72,185.28 SEK`** cumulative savings (**`22.92%`** of `315,000 SEK` Net Capex recouped) and **24/24 (100%)** exact integer SEK post-`Leverantörsbyte` EEM invoice matches.
* **Milestone 6**: Day-Ahead Forecaster, Shadow Mode Advisor ($\eta_{\text{rt}} = 76.8\%$ efficiency gate), and 134-day (`3,217`-hour) rolling backtest (`PV MAE = 4.19 kWh/day`, `Load MAE = 3.83 kWh/day`, `Bill MAE = 5.15 SEK/day`, `+158.48 SEK` out-of-sample predictive savings, `+204.82 SEK` oracle dispatch savings).

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
