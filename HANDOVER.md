# MySunshine Project Handover & Session State

> **Protocol**: This document serves as the single source of truth for cross-session continuity. When starting a fresh chat session or resuming after context compaction/restart, review this file and [prd.md](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/prd.md) first.

---

## 1. Current Status & Active Milestone

* **Active Phase**: Milestone 5.5: Full Day-1 Historical Expansion (2021–2023 Solar Era) & Utility Audit
* **Current Branch**: `feat/m5.5-day1-historical-expansion`
* **Pre-Push Validation State**: **100% Green** (42/42 unit tests passing, flake8 syntax & style passing).

---

## 2. Completed Work in Milestone 5.5 Step 1 (2021–2022 Solar Era & Nov 2026 Expansion)

1. **Solar Era Ingestion & Empirical Calibration (Milestone 5.5.1–5.5.3)**:
   * Built [`src/financial_engine/solar_ingestor.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/solar_ingestor.py) (`SMAInverterIngestor`, `EEMMeterIngestor`, `SolarEraSynthesizer`):
     * Ingested monthly solar PV yields from [`data/sunnyportal-sma-inverter-data-2026-10-24.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sunnyportal-sma-inverter-data-2026-10-24.csv) (8,381.5 kWh in 2021, 9,038.1 kWh in 2022, 8,532.4 kWh in 2023).
     * Ingested official export meter readings (`7359992924582514P`, UTF-16LE) from [`data/EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv) (5,695.3 kWh exported in 2021, 6,998.0 kWh exported in 2022).
     * Calibrated exact empirical self-consumption ($\text{Self-Consumed} = P_{\text{solar}} - E_{\text{export}}$): **32.0% in 2021** (2,686.2 kWh) and **22.6% in 2022** (2,040.2 kWh).
   * Synthesized daily operational datasets [`data/sonnen_energy_data_2021.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_2021.csv) (365 days), [`data/sonnen_energy_data_2022.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_2022.csv) (365 days), and backfilled Jan 1 – Sep 12, 2023 Solar-Only into [`data/sonnen_energy_data_2023.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_2023.csv) (365 days hybrid: 255 Solar-Only days + 110 Sonnen 11 kWh days).
   * Fetched and cached SE3 spot prices via ENTSO-E for 2021 ([`data/prices/se3_prices_2021.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/prices/se3_prices_2021.json), 8,730 points, avg 74.95 öre/kWh) and 2022 ([`data/prices/se3_prices_2022.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/prices/se3_prices_2022.json), 8,713 points, avg 146.79 öre/kWh).
   * Calibrated [`HistoricalYearCalculator`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/multi_year.py) so Solar-Only days match `Actual System == Baseline 2` with zero battery marginal value, realizing **12,061.83 SEK** savings in 2021, **22,465.11 SEK** savings in 2022, and **10,646.33 SEK** savings in full-year 2023.

2. **November 2026 High-Res Expansion & 25-Year Payback Actuals Integration**:
   * Ingested [`data/sonnen_energy_data_Sat_Nov_14_2026.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_Sat_Nov_14_2026.csv) (745 hourly records covering Oct 14 – Nov 13, 2026, including the 25-hour DST fallback day on Oct 25).
   * Enhanced [`SonnenHourlyIngestor.parse_csvs`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/src/financial_engine/multi_res.py) to skip any incomplete trailing day (`< 23` hours) in an export file so overlapping subsequent files supply complete days.
   * Updated [`data/sonnen_energy_data_2026.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/sonnen_energy_data_2026.csv) by replacing the incomplete `2026-08-30` row (`1214` measurements) and extending 2026 YTD to **317 complete days** (`2026-01-01` through `2026-11-13`, 8,346.3 kWh PV, 10,355.23 SEK savings).
   * Fetched and merged 2,639 15-minute SE3 spot prices (`2026-10-19` to `2026-11-15`) into [`data/prices/se3_prices_2026.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/prices/se3_prices_2026.json) (now 30,245 points), expanding continuous high-res dispatch coverage from 94 to **121 consecutive days** (2,905 hours, July 16 – Nov 13, 2026).
   * Updated `calculate25YearProjection` and `renderPaybackSCurveChart` in [`app.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/app.js) to anchor years 2021–2026 on actual historical realized savings (`annualSummaries`, rendered as a solid line) before projecting 2027–2045 forward (rendered as a dashed line).
   * Extended [`index.html`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/index.html), [`app.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/app.js), and [`calc_multi_year_roi.py`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/calc_multi_year_roi.py) across 2021–2026 (2,143 days, cumulative savings **73,172.21 SEK**, **23.23%** of 315k SEK Net Capex recouped) and re-baked [`data/dashboard_data.json`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.json) and [`data/dashboard_data.js`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/dashboard_data.js).

---

## 3. Next Prioritized Steps

1. **Step 2 (Next Up — Milestone 5.5.4)**:
   * **Utility Tariff Benchmarking & Invoicing Audit**:
     * Compare modeled EEM grid fees in `SwedishTariff` against actual billed amounts in [`data/eem-yearly-costs-2024-2026.csv`](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/data/eem-yearly-costs-2024-2026.csv).
     * Account for the `Leverantörsbyte` on `2024-09-28` (transition from EEM combined supply+grid to pure grid fee + Tibber).

2. **Step 3 (Milestone 5.5.5 — Formerly Item 4)**:
   * **Granular Hourly Actual Export Arbitrage**:
     * Use high-resolution hourly export records from the 121-day continuous dataset (July 16 – Nov 13, 2026) to calculate exact spot price matching for battery revenue.

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
