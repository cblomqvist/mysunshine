# MySunshine Project Handover & Session State

> **Protocol**: This document serves as the single source of truth for cross-session continuity.
> 1. **Session Start**: When starting a fresh chat session or resuming after context compaction/restart, review this file and [prd.md](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/prd.md) first.
> 2. **Session / Step Close**: At the conclusion of every step or milestone:
>    * Update `HANDOVER.md` with completed work, key findings, and updated metrics.
>    * **Always include a copy-pasteable prompt for the next step/phase** in `HANDOVER.md`.
>    * **Always suggest a ready-to-use Git commit message in your chat response** when finishing a step or milestone.

---

## 1. Current Status & Active Milestone

* **Active Phase**: Milestone 5.5: Full Day-1 Historical Expansion (2021–2023 Solar Era) & Utility Audit (**Completed — Ready for PR / Milestone 6**)
* **Current Branch**: `feat/m5.5-day1-historical-expansion`
* **Pre-Push Validation State**: **100% Green** (48/48 unit tests passing, flake8 syntax & style passing).

---

## 2. Completed Work in Milestone 5.5 (Steps 1, 2 & 3)

1. **Solar Era Ingestion & Empirical Calibration (Milestone 5.5.1–5.5.3 — Step 1)**:
   * Built [`src/financial_engine/solar_ingestor.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/solar_ingestor.py) (`SMAInverterIngestor`, `EEMMeterIngestor`, `SolarEraSynthesizer`):
     * Ingested monthly solar PV yields from [`data/sunnyportal-sma-inverter-data-2026-10-24.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sunnyportal-sma-inverter-data-2026-10-24.csv) (8,381.5 kWh in 2021, 9,038.1 kWh in 2022, 8,532.4 kWh in 2023).
     * Ingested official export meter readings (`7359992924582514P`, UTF-16LE) from [`data/EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv) (5,695.3 kWh exported in 2021, 6,998.0 kWh exported in 2022).
     * Calibrated exact empirical self-consumption ($\text{Self-Consumed} = P_{\text{solar}} - E_{\text{export}}$): **32.0% in 2021** (2,686.2 kWh) and **22.6% in 2022** (2,040.2 kWh).
   * Synthesized daily operational datasets [`data/sonnen_energy_data_2021.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_2021.csv) (365 days), [`data/sonnen_energy_data_2022.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_2022.csv) (365 days), and backfilled Jan 1 – Sep 12, 2023 Solar-Only into [`data/sonnen_energy_data_2023.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_2023.csv) (365 days hybrid: 255 Solar-Only days + 110 Sonnen 11 kWh days).
   * Fetched and cached SE3 spot prices via ENTSO-E for 2021 ([`data/prices/se3_prices_2021.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/prices/se3_prices_2021.json), 8,730 points, avg 74.95 öre/kWh) and 2022 ([`data/prices/se3_prices_2022.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/prices/se3_prices_2022.json), 8,713 points, avg 146.79 öre/kWh).
   * Calibrated [`HistoricalYearCalculator`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/multi_year.py) so Solar-Only days match `Actual System == Baseline 2` with zero battery marginal value, realizing **12,061.83 SEK** savings in 2021 and **22,465.11 SEK** savings in 2022.

2. **November 2026 High-Res Expansion & 25-Year Payback Actuals Integration**:
   * Ingested [`data/sonnen_energy_data_Sat_Nov_14_2026.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_Sat_Nov_14_2026.csv) (745 hourly records covering Oct 14 – Nov 13, 2026, including the 25-hour DST fallback day on Oct 25).
   * Enhanced [`SonnenHourlyIngestor.parse_csvs`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/multi_res.py) to skip any incomplete trailing day (`< 23` hours) in an export file so overlapping subsequent files supply complete days.
   * Updated [`data/sonnen_energy_data_2026.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_2026.csv) by replacing the incomplete `2026-08-30` row (`1214` measurements) and extending 2026 YTD to **317 complete days** (`2026-01-01` through `2026-11-13`, 8,346.3 kWh PV).
   * Fetched and merged 2,639 15-minute SE3 spot prices (`2026-10-19` to `2026-11-15`) into [`data/prices/se3_prices_2026.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/prices/se3_prices_2026.json) (now 30,245 points), expanding continuous high-res dispatch coverage from 94 to **121 consecutive days** (2,905 hours, July 16 – Nov 13, 2026).
   * Updated `calculate25YearProjection` and `renderPaybackSCurveChart` in [`app.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/app.js) to anchor years 2021–2026 on actual historical realized savings (`annualSummaries`, rendered as a solid line) before projecting 2027–2045 forward (rendered as a dashed line).

3. **Utility Tariff Benchmarking & Invoicing Audit (Milestone 5.5.4 — Step 2)**:
   * Built [`src/financial_engine/tariff_audit.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/tariff_audit.py) (`EEMYearlyCostsIngestor`, `AuditedEEMTariffSchedule`, `UtilityTariffAuditor`) and added `SwedishTariff.for_audited_year(year)` in [`src/financial_engine/tariff.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/tariff.py):
     * **Regime 1 — Pre-`Leverantörsbyte` (`2024-01` to `2024-09`, switch on `2024-09-28` at meter stand `22,217.291 kWh`)**: Decomposed EEM's combined retail+grid invoices (`8,741.00 SEK` across `3,257.00 kWh`) into `5,706.51 SEK` EEM Grid+Energiskatt and `3,034.49 SEK` EEM Retail Supply (`0.9317 SEK/kWh` incl. VAT).
     * **Regime 2 — Post-`Leverantörsbyte` (`2024-10` to `2026-09`, 24 billed months)**: Audited EEM pure grid schedules (`2024`: `10.9726 SEK/day` fixed + `82.90 öre/kWh` var incl. VAT; `2025`: `11.8904 SEK/day` / `4,340 SEK/yr` fixed + `84.26 öre/kWh` var incl. VAT; `2026`: `13.3260 SEK/day` / `4,864 SEK/yr` fixed + `74.44 öre/kWh` var incl. VAT after the 2026 statutory `Energiskatt` cut to `36.0 öre/kWh` ex. VAT). Achieved **24/24 (100.0%) exact integer SEK invoice match** (`14,313.00 SEK` billed vs `14,312.99 SEK` modeled, MAE = `0.20 SEK`).
     * **`SwedishTariff` Benchmark & CT Clamp Audit**: Identified that EEM's actual variable transfer fee (`Överföringsavgift`) is `23.51–23.55 öre/kWh` ex. VAT (vs `17.60 öre/kWh` baseline default), and verified Sonnen CT clamp import readings against EEM fiscal meter readings (`-5.92%` cumulative CT bias across 33 billed months; Oct 1–24, 2026 partial export `179.261 kWh` EEM vs `170.395 kWh` Sonnen = `-4.95%`).
     * Added the **Utility Billing Audit** tab in [`index.html`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/index.html) and [`app.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/app.js), baked `utility_tariff_audit` into [`data/dashboard_data.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.json) and [`data/dashboard_data.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.js), and added unit tests in [`tests/test_tariff_audit.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/tests/test_tariff_audit.py).

4. **Granular Hourly Actual Export & Import Arbitrage (Milestone 5.5.5 — Step 3)**:
   * Calibrated empirical 24-hour battery-era dispatch profiles in [`src/financial_engine/baseline.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/baseline.py) and added [`SonnenHourlyIngestor.calibrate_diurnal_profiles`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/multi_res.py) from the 121-day continuous high-resolution dataset (`2,905` hours, `2026-07-16` through `2026-11-13`):
     * `DEFAULT_DIURNAL_BATTERY_EXPORT_WEIGHTS`: Captures battery self-consumption charging during early morning solar (`05:00–08:00`) and grid overflow concentration during `09:00–14:00`.
     * `DEFAULT_DIURNAL_BATTERY_ACTIVE_IMPORT_WEIGHTS` (101 active-cycling days where `battery_discharged >= 25%` of load), `DEFAULT_DIURNAL_BATTERY_LOW_SOLAR_IMPORT_WEIGHTS` (20 low-solar days), `DEFAULT_DIURNAL_NIGHT_GRID_CHARGE_WEIGHTS` (`00:00–05:00` night trough for winter grid-to-battery arbitrage pre-charging days in `2024-10` to `2025-03`), `DEFAULT_DIURNAL_BATTERY_CHARGE_WEIGHTS`, and `DEFAULT_DIURNAL_BATTERY_DISCHARGE_WEIGHTS`.
   * Added [`BaselineEngine.disaggregate_daily_actual_battery`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/baseline.py) and updated [`HighResAnalyzer._compute_synthetic_weighted_variance`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/analyzer_30d.py), reducing 121-day `Actual System Net Cost` estimation error from `-226.81 SEK` (`-58.04%`) to **`-3.16 SEK` (`-0.81%`)** (`387.64 SEK` estimated vs `390.80 SEK` exact).
   * Updated [`HistoricalYearCalculator`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/multi_year.py) and [`Year2025Calculator`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/calculator_2025.py) to evaluate the 121 high-res days (`2026-07-16` to `2026-11-13`) using exact spot-matched hourly intervals (`load_matched_hourly_by_date`) and non-high-res battery days using `disaggregate_daily_actual_battery`.
   * Updated `recalculateLedgerMonths` and `populateVarianceTable` in [`app.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/app.js) to anchor on baked hourly/diurnal-matched monthly bills with exact linear slider deltas and display both daily-averaged and calibrated diurnal profile variance benchmarks.
   * Re-baked [`data/dashboard_data.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.json) and [`data/dashboard_data.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.js): across `2,143` days (`2021–2026`), cumulative realized savings are **`72,247.07 SEK`** (**`22.94%`** of `315,000 SEK` Net Capex recouped: `12,061.83 SEK` in 2021, `22,465.11 SEK` in 2022, `10,673.93 SEK` in 2023, `8,277.06 SEK` in 2024, `9,265.97 SEK` in 2025, and `9,503.16 SEK` in 2026 YTD with `+1,481.45 SEK` battery marginal value).

---

## 3. Next Prioritized Steps & Copy-Paste Session Prompt

### Next Prioritized Steps
1. **Commit, Push & Merge Milestone 5.5 (`feat/m5.5-day1-historical-expansion`) into `main`**, then create branch `feat/m6-next-day-forecast` from `main`.
2. **Milestone 6 (Phase 2): Next-Day Forecasting & Shadow Recommendation Engine**:
   * **Step 1 (`6.1` & `6.2`) — Day-Ahead Price, Weather/Irradiance & Next-Day Cost/Savings Forecaster**:
     * Build `src/forecast_engine/` to ingest tomorrow's SE3 day-ahead spot prices (hourly/15-min) and local Eskilstuna weather/solar irradiance forecasts (Open-Meteo API with offline/deterministic fallback fixtures), predict next-day PV generation and household load using our calibrated seasonal/diurnal profiles, and project tomorrow's 3-way baseline bills and expected savings.
   * **Step 2 (`6.3`) — Dynamic Grid Pre-Charging & Arbitrage Advisor (Shadow Mode)**:
     * Model optimal night-trough grid pre-charging and peak-shaving dispatch against the round-trip efficiency gate ($\eta \approx 76.8\%$), outputting explicit hourly shadow recommendations without physical hardware actuation.
   * **Step 3 (`6.4`) — Prediction vs. Actual Backtesting & Dashboard Tab**:
     * Backtest the shadow advisor across the 121-day (`2,905`-hour) high-resolution dataset to quantify theoretical optimization upside (*"Shadow advisor would have saved +X SEK vs. default self-consumption dispatch"*), bake results into `dashboard_data.json` / `dashboard_data.js`, and add the **Next-Day Forecast & Shadow Advisor** tab to the web dashboard.

### Prompt for Next Session
```text
@HANDOVER.md @prd.md Review HANDOVER.md and prd.md. First verify that we are on an up-to-date `main` branch (checkout `main` and pull latest if needed) and create the new branch `feat/m6-next-day-forecast` from `main`. Then proceed with Milestone 6 (Next-Day Forecasting & Shadow Recommendation Engine): implement Day-Ahead Price & Solar/Load Forecasting (6.1 & 6.2), the Shadow Mode Grid Pre-Charging & Arbitrage Advisor (6.3), and Backtesting against the 121-day high-res dataset + Dashboard UI integration (6.4).
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
