# Handover Document: Milestone 5 - Multi-Year Historical Expansion & Calculation Validation

## 1. Project Context & Completed State

* **Repository**: `mysunshine` on branch `feat/m4-dashboard-ui`.
* **PRD**: [`prd.md`](../../prd.md) (Updated with actual hardware installation milestones & revised roadmap).
* **Milestone 1 Completed**: Price ingestion, caching, and CI testing.
* **Milestone 2 Completed**: Swedish tariff engine, 3-way comparative baseline, and 2025 full-year ROI calculator.
* **Milestone 3 Completed**: High-Resolution 30-Day Ingestion, Multi-Resolution Matcher, High-Resolution 30-Day Analyzer, and Estimation Variance Benchmarking.
* **Milestone 4 Completed**:
  * **Interactive Web Dashboard** (`index.html`, `style.css`, `app.js`):
    * **4.1 KPI Cards & Capex Progress Ring**: Total savings (SEK), animated SVG radial progress ring, payback period in years, SonnenBatterie 10 marginal value, and avoided CO₂.
    * **4.2 25-Year Cumulative Payback S-Curve (Chart 1)**: Interactive 25-year cash flow curve with calendar years (2021–2045) and dynamic break-even indicator.
    * **4.3 3-Way Baseline Bar Chart (Chart 2)**: Side-by-side monthly cost breakdown comparing No Solar vs Solar Only vs Actual System.
    * **4.4 Hourly Dispatch & Price Overlay Chart (Chart 3)**: 24h interactive dispatch viewer comparing Solar PV, Load, Battery SoC, and spot prices with multi-day selectors.
    * **4.5 Financial Ledger Table & Dynamic Tariff Controls**: Live client-side recalculations with Net Capex & *Grön Teknik* deduction toggles, 60 öre/kWh *skattereduktion*, energy tax, and inflation sliders across 2025 monthly, 25-year, and 30-day estimation variance tables.
  * **Static Data Baking Pipeline** (`src/financial_engine/generate_dashboard_data.py` -> `data/dashboard_data.json` & `data/dashboard_data.js`).
  * **Automated CD Workflow** (`.github/workflows/deploy.yml`): Continuous deployment of static web application to GitHub Pages on merge to `main`.
  * **Automated Validation Suite**: 28 passing unit tests across the repository (`python run_checks.py`).

---

## 2. Milestone 5 Objectives & Deliverables

1. **Multi-Year Sonnen CSV Ingestion (5.1)**:
   - Ingest newly added `data/sonnen_energy_data_2023.csv` (September 2023 onwards) and `data/sonnen_energy_data_2024.csv` (Full Year 2024).
2. **Hardware Transition Modeling (5.2)**:
   - Accurately model the three operational eras:
     - **Era 1 (Solar Only)**: Jan 2021 – Aug 2023.
     - **Era 2 (Single 11 kWh Battery)**: Sep 2023 – Sep 8, 2024 (~11 kWh capacity, ~77% efficiency).
     - **Era 3 (Dual 22 kWh Battery)**: Sep 9, 2024 – Present (Expanded 22 kWh capacity, ~150,000 SEK battery Capex).
3. **Historical Spot Price Fetching & Multi-Year Caching (5.3)**:
   - Fetch and cache full SE3 historical prices for 2023 and 2024 (`data/prices/se3_prices_2023.json`, `data/prices/se3_prices_2024.json`).
4. **Multi-Year Validation & Dashboard Integration (5.4)**:
   - Verify calculation correctness and energy balances across 2023, 2024, and 2025.
   - Add a multi-year selector / comparison view to the web dashboard to allow switching or aggregating historical years (2023, 2024, 2025).
