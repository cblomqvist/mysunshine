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

* **Active Phase**: Milestone 7 (Phase 3): Home Assistant Custom Sensor Integration & Live Shadow Telemetry Bridge (**Completed — Ready for Commit, Push & PR to `main`**)
* **Current Branch**: `main` (ready to branch/commit as `feat/m7-ha-shadow-telemetry-bridge`)
* **Pre-Push Validation State**: **100% Green** (57/57 unit and integration tests passing, 0 flake8 errors in new modules).

---

## 2. Completed Work Summary (Milestones 5.5, 6 & 7)

### A. Milestone 7 (Phase 3): Home Assistant Custom Sensor Integration & Live Shadow Telemetry Bridge
1. **Home Assistant Custom Sensor Models & Long-Term Statistics (`src/ha_integration/sensor_models.py`)**:
   * Built `HomeAssistantEntityPayload` and `HomeAssistantStatePackage` generating canonical Home Assistant REST API payloads (`POST /api/states/<entity_id>`) with `device_class`, `state_class` (`total_increasing` and `measurement`), and rich attributes.
   * Exposed **10 custom Home Assistant entities**:
     1. `sensor.mysunshine_shadow_action` (`GRID_PRECHARGE`, includes 24-hour compact dispatch schedule in attributes)
     2. `sensor.mysunshine_breakeven_spot_ore` (`41.6 öre/kWh`, $\eta_{\text{rt}} = 76.8\%$ efficiency gate threshold)
     3. `sensor.mysunshine_expected_savings_sek` (`+9.65 SEK` shadow gain vs Default Self-Consumption)
     4. `sensor.mysunshine_recommended_precharge_kwh` (`12.43 kWh` during `03:00–05:00` night trough)
     5. `sensor.mysunshine_next_day_projected_bill_sek` (`17.67 SEK` vs `27.32 SEK` Default SC / `37.16 SEK` No Solar)
     6. `sensor.mysunshine_cumulative_savings_sek` (`72,247.07 SEK`, `state_class: total_increasing` for Home Assistant Long-Term Statistics)
     7. `sensor.mysunshine_capex_recouped_pct` (`22.94%` of `315,000 SEK` Net Capex recouped)
     8. `sensor.mysunshine_backtest_121d_upside_sek` (`+144.39 SEK` Oracle / `+109.05 SEK` Out-of-Sample Predictive / `+247.12 SEK` vs Raw Sonnen CT)
     9. `binary_sensor.mysunshine_efficiency_gate_passed` (`on`)
     10. `input_boolean.mysunshine_active_battery_control` (`off` — hardware safety gate switch)

2. **Dual Hardware Safety Actuation Gate (`SonnenSafetyActuationGate`)**:
   * Translates each hourly Shadow Advisor action (`GRID_PRECHARGE`, `HOLD_FOR_PEAK`, `PEAK_DISCHARGE`, `SOLAR_CHARGE`, `SELF_CONSUMPTION`, `IDLE`) into exact SonnenBatterie 10 API v2 endpoints (`/api/v2/setpoint/charge/<watts>`, `/api/v2/setpoint/discharge/0`, `/api/v2/configurations` with `EM_OperatingMode`).
   * Enforces a **dual safety lock**: physical actuation (`would_actuate = True`) is blocked (`LOCKED_SHADOW_MODE_ONLY`) unless **both** `MYSUNSHINE_ACTIVE_CONTROL_ENABLED=true` in `.env` **and** `input_boolean.mysunshine_active_battery_control=on` in Home Assistant are active.

3. **Live Telemetry Bridge, Dashboard UI Tab & Automated Tests (`src/ha_integration/telemetry_bridge.py`)**:
   * Built `HomeAssistantTelemetryBridge` with SonnenBatterie 10 `/api/v2/status` normalization (`USOC`, `RSOC`, `Pac_total_W`, `EM_OperatingMode`), dry-run/live REST state publisher to Home Assistant Green (`http://192.168.3.138:8123`), and ready-to-paste `configuration.yaml` and `automations.yaml` blueprints.
   * Integrated `ha_integration` into [`src/financial_engine/generate_dashboard_data.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/generate_dashboard_data.py), re-baked [`data/dashboard_data.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.json) and [`data/dashboard_data.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.js), added the interactive **Home Assistant Bridge** tab in [`index.html`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/index.html), [`style.css`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/style.css), and [`app.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/app.js), and added unit/integration tests in [`tests/test_ha_integration.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/tests/test_ha_integration.py).

### B. Milestones 5.5 & 6 Summary (Previously Completed & Merged to `main`)
* **Milestone 5.5**: Full Day-1 (`2021–2026`, `2,143` days) historical ledger realizing **`72,247.07 SEK`** cumulative savings (**`22.94%`** of `315,000 SEK` Net Capex recouped) and **24/24 (100%)** exact integer SEK post-`Leverantörsbyte` EEM invoice matches.
* **Milestone 6**: Day-Ahead Forecaster, Shadow Mode Advisor ($\eta_{\text{rt}} = 76.8\%$ efficiency gate), and 121-day (`2,905`-hour) rolling backtest (`PV MAE = 4.47 kWh/day`, `Load MAE = 3.89 kWh/day`, `Bill MAE = 4.66 SEK/day`, `+109.05 SEK` out-of-sample predictive savings, `+144.39 SEK` oracle dispatch savings).

---

## 3. Next Prioritized Steps & Copy-Paste Session Prompt

### Next Prioritized Steps
1. **Commit, Push & Open PR for Milestone 7 (`feat/m7-ha-shadow-telemetry-bridge` $\rightarrow$ `main`)** to deploy the Home Assistant Custom Sensor Integration & Live Shadow Telemetry Bridge tab to GitHub Pages.
2. **Phase 4 (Optional Future Milestone 8): Live Scheduled Polling Daemon & Multi-Day Rolling Shadow Ledger**:
   * Build a lightweight CLI/cron runner (`run_ha_shadow_sync.py`) for Home Assistant Green / Ubuntu 24/7 host that fetches live Tibber/ENTSO-E day-ahead prices at `13:15 CET`, queries `http://192.168.3.125/api/v2/status` for real-time Sonnen SoC, pushes the 10 custom entities to `http://192.168.3.138:8123/api/states`, and appends daily shadow vs. actual telemetry to a persistent JSONL audit log.

### Prompt for Next Session
```text
@HANDOVER.md @prd.md Review HANDOVER.md and prd.md. Proceed with Milestone 8: Live Scheduled Polling CLI Runner (run_ha_shadow_sync.py) & Persistent Daily Shadow Telemetry Audit Log.
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
