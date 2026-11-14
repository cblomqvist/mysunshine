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

* **Active Phase**: Milestone 6 (Phase 2): Next-Day Forecasting & Shadow Recommendation Engine (**Completed — Ready for Commit, Push & PR to `main`**)
* **Current Branch**: `feat/m6-next-day-forecast`
* **Pre-Push Validation State**: **100% Green** (53/53 unit and integration tests passing, flake8 syntax & style passing).

---

## 2. Completed Work Summary (Milestones 5.5 & 6)

### A. Milestone 6: Next-Day Forecasting & Shadow Recommendation Engine (Steps 1, 2 & 3)
1. **Day-Ahead Price, Weather/Irradiance & Solar/Load Forecaster (Deliverables 6.1 & 6.2)**:
   * Built [`src/forecast_engine/forecaster.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/forecast_engine/forecaster.py) (`DayAheadPriceForecaster`, `WeatherIrradianceProvider`, `SolarLoadForecaster`):
     * Normalizes 15-minute (96 quarters/day) and 60-minute SE3 day-ahead spot prices into Swedish local time (`CET/CEST` via deterministic EU DST conversion) and preserves intra-hour min/max quarterly price spreads.
     * Models Eskilstuna (`59.37°N, 16.51°E`) clear-sky daily PV potential, seasonal daylight window weights, and cloud-cover solar transmittance ($\tau_{\text{cloud}} = 1 - 0.78 \cdot (\text{cloud}/100)^{1.3}$), supporting Open-Meteo REST queries with deterministic offline weather/irradiance models.
     * Predicts next-day hourly PV generation and household consumption combining day-ahead irradiance (`85%` weight) with trailing 7-day empirical array trend (`15%` weight), heating degree day (`HDD < 15°C`) sensitivity, and trimmed trailing 7-day load profiles.

2. **Dynamic Grid Pre-Charging & Arbitrage Advisor in Shadow Mode (Deliverable 6.3)**:
   * Built [`src/forecast_engine/shadow_advisor.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/forecast_engine/shadow_advisor.py) (`BatteryPhysicsConfig`, `ShadowModeAdvisor`, `DayAheadShadowPlan`, `ShadowAdvisorDayResult`):
     * Models the SonnenBatterie 10 (`20.0 kWh` usable capacity, `6.5 kW` max charge, `6.0 kW` max discharge, $\eta_{\text{rt}} = 76.8\%$ round-trip efficiency).
     * Enforces the PRD round-trip efficiency & tariff gate:
       $$C_{\text{import}}(t_{\text{peak}}) > \frac{C_{\text{import}}(t_{\text{trough}})}{\eta_{\text{roundtrip}}} + 0.05\text{ SEK/kWh}$$
     * Schedules night-trough grid pre-charging (`00:00–06:00`) only for profitable peak load uncovered by initial SoC + expected daytime solar surplus, and applies **Smart Peak-Preservation Hold** (`HOLD_FOR_PEAK`) to prevent premature battery discharge during cheap/moderate hours.
     * For tomorrow (**Sunday, Nov 15, 2026**, published SE3 15-min prices in `data/prices/se3_prices_2026.json`):
       * Night trough (`03:00–05:00`) averages **`13.0 öre/kWh`** $\rightarrow$ efficiency-gate break-even peak spot is **`41.6 öre/kWh`**.
       * Afternoon/evening peak (`15:00–21:00`) reaches **`118.3 öre/kWh`**.
       * Shadow Advisor recommends: *"Pre-charge 12.4 kWh between 03:00–05:00 at avg 13.0 öre/kWh (efficiency gate break-even: 41.6 öre/kWh) and hold for 15:00–21:00 peak spike (up to 118.3 öre/kWh) to save +9.65 SEK vs. default self-consumption"* (reducing tomorrow's net bill from `27.32 SEK` under Default Self-Consumption / `37.16 SEK` No-Solar to **`17.67 SEK`**).

3. **121-Day Prediction vs. Actual Backtesting & Dashboard UI Integration (Deliverable 6.4)**:
   * Built [`src/forecast_engine/backtester.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/forecast_engine/backtester.py) (`ShadowBacktester`, `BacktestSummaryReport`, `BacktestDayRecord`) and evaluated across all **121 consecutive days (`2,905` hours, `2026-07-16` through `2026-11-13`)**:
     * **Day-Ahead Forecast Accuracy**: `PV MAE = 4.47 kWh/day` (`RMSE = 5.88 kWh`), `Load MAE = 3.89 kWh/day` (`RMSE = 6.37 kWh`), and `Daily Bill MAE = 4.66 SEK/day`.
     * **Strategy Trigger Distribution**: `20 days` triggered Night-Trough Grid Pre-Charging (`144.9 kWh` total pre-charged), `6 days` triggered Smart Peak-Preservation Hold, and `95 days` kept Standard Self-Consumption.
     * **Cumulative 121-Day Financial Backtest (incl. fixed fees)**:
       * Baseline 1 (No Solar, No Battery): `3,922.65 SEK`
       * Actual Realized Sonnen System (CT Logs): `390.80 SEK`
       * Simulated Default Self-Consumption (Same Physics): `288.08 SEK` (`102.72 SEK` sub-hourly 3-phase/ramp trickle residual)
       * **Out-of-Sample Predictive Shadow Advisor**: **`179.03 SEK`** (**`+109.05 SEK`** saved vs Default Self-Consumption, **`+211.77 SEK`** vs Raw Realized Sonnen)
       * **Oracle Shadow Advisor (Exact Weather Foresight)**: **`143.68 SEK`** (**`+144.39 SEK`** pure dispatch arbitrage savings vs Default Self-Consumption, **`+247.12 SEK`** vs Raw Realized Sonnen)
       * Top single-day arbitrage gains occurred during the November cold/cloudy price spikes when Sonnen sat at `0%` SoC: `2026-11-10` (`523.3 öre/kWh` peak, **`+32.14 SEK`** saved), `2026-11-11` (`437.6 öre/kWh` peak, **`+25.07 SEK`** saved), `2026-10-12` (`222.5 öre/kWh` peak, **`+22.45 SEK`** saved), and `2026-11-09` (`485.7 öre/kWh` peak, **`+14.42 SEK`** saved).
   * Integrated `next_day_forecast` into [`src/financial_engine/generate_dashboard_data.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/generate_dashboard_data.py), re-baked [`data/dashboard_data.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.json) and [`data/dashboard_data.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.js), added the **Next-Day Forecast & Shadow Advisor** tab in [`index.html`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/index.html), [`style.css`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/style.css), and [`app.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/app.js), and added unit/integration tests in [`tests/test_forecast_engine.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/tests/test_forecast_engine.py).

### B. Milestone 5.5 Summary (Previously Completed)
* Complete Day-1 (`2021–2026`, `2,143` days) historical ledger realizing **`72,247.07 SEK`** cumulative savings (**`22.94%`** of `315,000 SEK` Net Capex recouped), **24/24 (100%)** exact integer SEK post-`Leverantörsbyte` EEM invoice matches, and **`-0.81%`** (`-3.16 SEK`) 121-day diurnal battery dispatch net cost variance.

---

## 3. Next Prioritized Steps & Copy-Paste Session Prompt

### Next Prioritized Steps
1. **Commit, Push & Open PR for Milestone 6 (`feat/m6-next-day-forecast` $\rightarrow$ `main`)** to deploy the updated dashboard with the **Utility Billing Audit** and **Next-Day Forecast & Shadow Advisor** tabs to GitHub Pages.
2. **Phase 3 (Future Milestone 7): Home Assistant Custom Integration & Live Telemetry Bridge**:
   * Build `src/ha_integration/` to expose MySunshine's ROI metrics, daily shadow dispatch schedule, and efficiency-gate break-even price threshold as Home Assistant sensors (`sensor.mysunshine_shadow_action`, `sensor.mysunshine_breakeven_spot_ore`, `sensor.mysunshine_expected_savings_sek`) via Home Assistant REST/MQTT or custom component, while keeping hardware actuation gated behind an explicit opt-in switch.

### Prompt for Next Session
```text
@HANDOVER.md @prd.md Review HANDOVER.md and prd.md. Verify git status on feat/m6-next-day-forecast, assist with merging Milestone 6 to main if needed, and proceed with Phase 3 (Milestone 7: Home Assistant Custom Sensor Integration & Live Shadow Telemetry Bridge).
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
