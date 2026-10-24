# MySunshine Project Handover & Session State

> **Protocol**: This document serves as the single source of truth for cross-session continuity. When starting a fresh chat session or resuming after context compaction, review this file and [prd.md](file:///c:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/prd.md) first.

---

## 1. Current Status & Active Milestone

* **Active Phase**: Milestone 5.5: Full Day-1 Historical Expansion (2021–2023 Solar Era) & Utility Audit
* **Current Branch**: `main`
* **Last Clean Git Commit**: `6e6e00c` (*"feat(engine): normalize diurnal weights, add date-aware skattereduktion, and augment baseline charts"*)
* **Pre-Push Validation State**: **100% Green** (38/38 unit tests passing, flake8 syntax & style passing).

---

## 2. Environment & Validation Commands

* **Python Executables**:
  * Development & scripts: `C:\dev\Python315\python.exe`
  * System/Git Bash default: `C:\Users\chris\AppData\Local\Python\pythoncore-3.15-64\python.exe`
* **Mandatory Pre-Push Check** (Always run before completing tasks or pushing):
  ```bash
  # In PowerShell / Windows:
  & "C:\Program Files\Git\bin\bash.exe" .git/hooks/pre-push
  # or
  python run_checks.py
  ```
* **Test Suite**:
  ```bash
  python -m pytest tests/ -v
  ```
* **Re-Bake Static Dashboard Package**:
  ```bash
  python -m src.financial_engine.generate_dashboard_data
  ```

---

## 3. Prioritized Execution Sequence

As requested, the execution sequence has been reordered:

1. **Step 1 (Next Up — Milestone 5.5.1–5.5.3)**:
   * **Ingest 2021 & 2022 Solar Era**:
     * Ingest monthly solar PV generation from `data/sunnyportal-sma-inverter-data-2026-10-24.csv` (8,381.5 kWh in 2021, 9,038.1 kWh in 2022, 8,532.4 kWh in 2023).
     * Ingest official monthly export meter readings from `data/EEM-meter-readings-402520-2026-10-24-20-10-44-5195.csv` (meter `7359992924582514P`, UTF-16LE, 5,695.3 kWh exported in 2021, 6,998.0 kWh exported in 2022).
     * Calculate exact empirical self-consumption: $\text{Self-Consumed} = P_{\text{solar}} - E_{\text{export}}$ (measured at **32.0% in 2021** and **22.6% in 2022**).
     * Fetch/cache SE3 2021 and 2022 spot prices to compute exact financial returns during the 2021–2022 energy crisis.
     * Extend `MultiYearEngine` and the dashboard timeline back to Day 1 (January 2021).

2. **Step 2 (Milestone 5.5.4)**:
   * **Utility Tariff Benchmarking & Invoicing Audit**:
     * Compare modeled EEM grid fees in `SwedishTariff` against actual billed amounts in `data/eem-yearly-costs-2024-2026.csv`.
     * Note the `Leverantörsbyte` on 2024-09-28 (transition from EEM combined supply+grid to pure grid fee + Tibber).

3. **Step 3 (Milestone 5.5.5 — Formerly Item 4)**:
   * **Granular Hourly Actual Export Arbitrage**:
     * Use high-resolution hourly export records from the 94-day continuous dataset (July 16 – Oct 17, 2026) to calculate exact spot price matching for battery revenue.

---

## 4. Key Architectural Constants & Rules

* **Diurnal Weights**: Both `DEFAULT_DIURNAL_LOAD_WEIGHTS` and `DEFAULT_DIURNAL_SOLAR_WEIGHTS` in `baseline.py` must strictly sum to $1.0000$.
* **Skattereduktion Expiration**: 60 öre/kWh subsidy ended on **2026-01-01** (`date_str < "2026-01-01"`).
* **Sub-Hourly Spot Prices**: Nordic market transitioned to 15-minute resolution on 2025-10-01. Sub-hourly prices must be aggregated to 24 hourly averages in Swedish local time (CET/CEST) via `_to_swedish_local()`.
* **Zero Client-Side Secrets**: No API keys in web bundles; all client runtime runs on pre-baked static JSON/JS files or zero-auth public APIs.
* **Capital Expenditure**:
  * Solar PV (Jan 2021): 165,000 SEK net (206,250 SEK gross).
  * Battery (Sep 2023 / Sep 2024 expansion): 150,000 SEK net (300,000 SEK gross).
  * Combined Net Capex: **315,000 SEK**.

---

## 5. Session Kickoff Action

When starting the next session, prompt:
> *"Proceed with Step 1 of Milestone 5.5: Ingesting 2021 & 2022 Solar Era data from Sunny Portal and EEM into the Multi-Year Engine."*
