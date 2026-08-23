# Handover Document: Milestone 4 - Interactive Web Dashboard & GitHub Pages CD

## 1. Project Context & Completed State

* **Repository**: `mysunshine` on branch `feat/m3-high-res-analyzer`.
* **PRD**: [`prd.md`](prd.md) (Detailed specifications).
* **Milestone 1 Completed**: Price ingestion, caching, and CI testing.
* **Milestone 2 Completed**: Swedish tariff engine, 3-way comparative baseline, and 2025 full-year ROI calculator.
* **Milestone 3 Completed**:
  * High-Resolution 30-Day Ingestion ([`src/financial_engine/multi_res.py`](src/financial_engine/multi_res.py)).
  * Multi-Resolution Matcher: 15-minute quarterly spot price grouping and averaging for hourly logs.
  * High-Resolution 30-Day Analyzer ([`src/financial_engine/analyzer_30d.py`](src/financial_engine/analyzer_30d.py)).
  * Estimation Variance & Accuracy Delta Benchmarking (High-res exact vs simple daily sum vs synthetic diurnal profiles).
  * CLI tool ([`calc_30d_roi.py`](calc_30d_roi.py)).
  * Comprehensive test suite ([`tests/test_multi_res.py`](tests/test_multi_res.py)) with 26 passing tests across the repo.

---

## 2. Milestone 4 Objectives & Deliverables

1. **Interactive Web Dashboard UI**:
   - Modern dark-themed glassmorphic UI with Chart.js and interactive controls.
   - **4.1 KPI Cards & Capex Progress Ring**: Total savings, % Capex recouped, simple payback estimate, battery marginal value, and avoided CO2.
   - **4.2 Cumulative Payback S-Curve Chart (Chart 1)**: Interactive 25-year cash flow curve with dynamic break-even point.
   - **4.3 3-Way Baseline Bar Chart (Chart 2)**: Monthly comparison of No Solar vs. Solar Only vs. Actual System.
   - **4.4 Hourly Dispatch & Price Overlay Chart (Chart 3)**: 24h interactive dispatch viewer comparing SoC, solar, load, and spot price.
   - **4.5 Financial Ledger Table & Capex Slider Controls**: Live updating calculations on client-side with zero secret leaks.
2. **Automated CD Workflow (GitHub Actions)**:
   - Add `.github/workflows/deploy.yml` for automated GitHub Pages continuous deployment on merge to `main`.
