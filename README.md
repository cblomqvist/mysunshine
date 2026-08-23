# MySunshine ☀️🔋

A comprehensive system and interactive web application to track, simulate, and calculate the actual financial return on investment (ROI) for a household solar panel and home battery system in Sweden (SE3), with support for dynamic spot pricing, Swedish tariffs, multi-resolution timestamp matching, and estimation accuracy analysis.

## Features & Modules

- **Modular Electricity Spot Price Engine** (`src/price_providers`):
  - Fetches and caches historical hourly and 15-minute spot prices for SE3 from ENTSO-E, Tibber, Elering, and Elprisetjustnu.
- **Swedish Tariff & Tax Engine** (`src/financial_engine/tariff.py`):
  - Models *energiskatt*, EEM *överföringsavgift*, Tibber markups, 25% *moms*, EEM *nätnytta*, and 60 öre/kWh *skattereduktion för mikroproduktion*.
- **3-Way Baseline Financial Engine** (`src/financial_engine/baseline.py`):
  - Simulates Baseline 1 (No Solar/Battery), Baseline 2 (Solar Only), and Actual System (Solar + SonnenBatterie 10) to isolate marginal battery contribution.
- **2025 Full-Year Historical ROI Engine** (`src/financial_engine/calculator_2025.py`):
  - Full-year daily-to-monthly financial ledger, Capex payback timeline, and ROI metrics.
- **High-Resolution 30-Day & Multi-Resolution Engine** (`src/financial_engine/multi_res.py`, `src/financial_engine/analyzer_30d.py`):
  - Ingests 744 hours of granular Sonnen data, aligns with 15-minute / quarterly spot prices, and benchmarks precision against daily-averaged estimations.

## CLI Utilities

### 1. Fetch & Inspect Spot Prices
```bash
python fetch_prices.py --start 2025-01-01 --end 2025-12-31 --zone SE3 -o data/prices/se3_prices_2025.json
```

### 2. Full-Year 2025 ROI Calculator
```bash
python calc_2025_roi.py --capex 328000 --output data/report_2025.json
```

### 3. High-Resolution 30-Day Analyzer & Variance Benchmark
```bash
python calc_30d_roi.py --data data/sonnen_energy_data_Sun_Aug_16_2026.csv --output data/report_30d_2026.json
```

## Running Tests
```bash
python -m pytest
```

