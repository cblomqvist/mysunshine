# Handover Document: Milestone 3 - High-Resolution 30-Day & Multi-Resolution Engine

## 1. Project Context & Current State

* **Repository**: `mysunshine` on branch `feat/m2-financial-engine`.
* **PRD**: [`prd.md`](prd.md) (Detailed specifications).
* **Milestone 2 Completed**:
  * Implemented Swedish Electricity Tariff Module ([`src/financial_engine/tariff.py`](src/financial_engine/tariff.py)).
  * Implemented 3-Way Comparative Baseline Engine ([`src/financial_engine/baseline.py`](src/financial_engine/baseline.py)).
  * Implemented 2025 Full-Year ROI Engine ([`src/financial_engine/calculator_2025.py`](src/financial_engine/calculator_2025.py)).
  * Implemented CLI tool ([`calc_2025_roi.py`](calc_2025_roi.py)).
  * Verified 100% passing tests in `tests/test_financial_engine.py` and `tests/test_price_providers.py`.
  * Fetched and cached full 2025 SE3 spot price time-series (`data/prices/se3_prices_2025.json`).

---

## 2. Milestone 3 Objectives & Deliverables

1. **High-Resolution 30-Day Hourly Ingestion**:
   - Ingest [`data/sonnen_energy_data_Sun_Aug_16_2026.csv`](data/sonnen_energy_data_Sun_Aug_16_2026.csv) (744 hourly rows for July/August).
2. **Resolution Matching Engine**:
   - Dynamic alignment of hourly energy logs with 15-minute / quarterly spot prices (applicable post-2025-10-01).
3. **Accuracy Comparison & Estimation Variance Analysis**:
   - Benchmark exact hourly calculations vs. synthetic daily-averaged estimations to quantify precision deltas.
4. **CI Multi-Resolution Automated Tests**:
   - Expand `tests/` with timestamp matching, quarterly aggregation, and resolution alignment test vectors.
