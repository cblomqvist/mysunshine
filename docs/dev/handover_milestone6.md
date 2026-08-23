# Handover Document: Milestone 6 - Next-Day Forecasting & Shadow Recommendation Engine

## 1. Project Context & Completed State

* **Repository**: `mysunshine` on branch `feat/m5-multi-year-validation`.
* **PRD**: [`prd.md`](../../prd.md) (Updated with verified hardware eras & shadow predictive scope).
* **Milestone 1 Completed**: Price ingestion, caching, and CI testing.
* **Milestone 2 Completed**: Swedish tariff engine, 3-way comparative baseline, and 2025 full-year ROI calculator.
* **Milestone 3 Completed**: High-Resolution 30-Day Ingestion, Multi-Resolution Matcher, High-Resolution 30-Day Analyzer, and Estimation Variance Benchmarking.
* **Milestone 4 Completed**: Interactive Web Dashboard & GitHub Pages CD automation (`.github/workflows/deploy.yml`).
* **Milestone 5 Completed**:
  * **Multi-Year Historical Ingestion & Modeling** (`src/financial_engine/multi_year.py`):
    * Ingested `data/sonnen_energy_data_2023.csv` (110 days from Sep 13 install), `data/sonnen_energy_data_2024.csv` (366 days leap year), and `data/sonnen_energy_data_2025.csv` (365 days).
    * Integrated and cached historical SE3 spot prices for 2023 (`data/prices/se3_prices_2023.json`) and 2024 (`data/prices/se3_prices_2024.json`).
    * Modeled hardware eras:
      - **Era 1 (Jan 2021 – Aug 2023)**: Solar Only (~8.0 kW SMA Inverter, 165,000 SEK Net Capex).
      - **Era 2 (Sep 2023 – Sep 8, 2024)**: 11 kWh SonnenBatterie 10 single module.
      - **Era 3 (Sep 9, 2024 – Present)**: 22 kWh dual-module expansion (150,000 SEK Total Battery Net Capex; 315,000 SEK Total Net Capex).
  * **CLI Multi-Year Engine** (`calc_multi_year_roi.py`):
    * Calculate all-time cumulative ROI summary or drill down into any single year (`--year 2024`).
  * **Web Dashboard Multi-Year UI Updates** (`index.html`, `style.css`, `app.js`):
    * **Historical Year Selector**: Switch between `All Historical Data (2023–2025 Cumulative)`, `2025`, `2024`, and `2023`.
    * **Hardware Era Timeline Card**: Visual milestone pills for Jan 2021 Solar, Sep 2023 11 kWh, and Sep 2024 22 kWh.
    * **Annual Multi-Year Comparison Chart**: Side-by-side comparative bars for No Solar vs Solar Only vs Actual across 2023, 2024, and 2025.
    * **Multi-Year Summary Ledger Tab**: Table comparing 2023, 2024, and 2025 with hardware era badges.
  * **Test Suite**: 33 passing unit tests across the repository (`python run_checks.py`).

---

## 2. Milestone 6 Objectives & Deliverables

1. **Day-Ahead Price & Local Weather Ingestion (6.1)**:
   - Ingest tomorrow's published spot prices (available daily at ~13:00 CET).
   - Ingest local weather forecast (solar irradiance, cloud cover, temperature) via Open-Meteo or Forecast.Solar.
2. **Next-Day Cost & Savings Projection (6.2)**:
   - Estimate next-day solar generation and household load profile.
   - Forecast tomorrow's electricity cost and expected savings vs. No-Solar baseline.
3. **Dynamic Charging Advisor (Shadow Mode / Metrics Only) (6.3)**:
   - Evaluate whether overnight pre-charging yields positive returns through the round-trip efficiency hurdle equation:
     $$\Delta \text{Price} > \frac{C_{\text{import}}}{\eta_{\text{roundtrip}}} - R_{\text{export}} + \text{LossMargin}$$
   - Generate concrete recommendations without physical hardware manipulation.
4. **Prediction vs. Actual Backtesting Engine (6.4)**:
   - Evaluate recommendations the next day against actual realized meter logs (*"Recommendation engine would have saved/lost X SEK"*).
