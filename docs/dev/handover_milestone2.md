# Handover Document: Milestone 2 - 2025 Full-Year ROI & Baseline Engine

## 1. Project Context & Current State

* **Repository**: `mysunshine` on branch `main` (synced with GitHub remote).
* **PRD**: [`prd.md`](prd.md) (Fully detailed with hardware, Swedish tariffs, multi-resolution alignment, CI/CD, and visual blueprints).
* **Milestone 1 Completed & Merged**:
  * Established `.github/workflows/ci.yml` with **Gitleaks secret scanning**, flake8 linting, and automated `pytest` test runner.
  * Implemented pluggable price providers (`ENTSO-E`, `Tibber`, `Elprisetjustnu`, `Energy-Charts`, `Elering`) with disk caching (`data/prices/`) and `PriceManager`.
  * Verified 100% unit tests pass in CI on GitHub Actions.

---

## 2. Hardware & Market Parameters for Milestone 2

* **Bidding Zone**: **SE3** (Stockholm / Central Sweden).
* **Grid Operator**: **Eskilstuna Energi & Miljö (EEM)** (`https://eem.se`).
* **Electricity Retailer**: **Tibber** (`https://tibber.com/se`) (49 SEK/mo subscription fee; switched to 15-min pricing on 2025-10-01).
* **Solar Installation**: **SMA Inverter STP8.0-3AV-40** (8.0 kW AC rating).
* **Battery Installation**: **SonnenBatterie 10 performance** (4 modules, ~22 kWh nominal, ~76.7%–77.0% measured round-trip efficiency).
* **Swedish Tax & Tariff Formulas**:
  * **Import Cost ($C_{\text{import}}$)**:
    $$\left( \text{SpotPrice}_{\text{SE3}} + \text{TibberMarkup} + \text{Elcertifikat} + \text{Energiskatt} + \text{Överföringsavgift}_{\text{EEM}} \right) \times 1.25$$
  * **Export Revenue ($R_{\text{export}}$)**:
    $$\text{SpotPrice}_{\text{SE3}} + \text{Nätnytta}_{\text{EEM}} + \text{Skattereduktion}_{60\text{öre}}$$
    *(60 öre/kWh skattereduktion applies to all 2025 exported kWh)*.

---

## 3. Data Available

* [`data/sonnen_energy_data_2025.csv`](data/sonnen_energy_data_2025.csv): 365 daily rows for full-year 2025 (8,209.6 kWh produced, 7,515.5 kWh consumed, 3,321.1 kWh exported, 3,405.7 kWh imported, 3,542.4 kWh charged, 2,728.5 kWh discharged).
* [`data/sonnen_energy_data_Sun_Aug_16_2026.csv`](data/sonnen_energy_data_Sun_Aug_16_2026.csv): 744 hourly rows for July/August 2026.

---

## 4. Milestone 2 Deliverables (Next Session Action Plan)

1. **Create Branch**: `git checkout -b feat/m2-financial-engine`
2. **Implement Swedish Tariff Module** (`src/financial_engine/tariff.py`):
   - Configurable parameters for EEM grid fees, energiskatt, moms, Tibber markup, nätnytta, and 60 öre skattereduktion.
3. **Implement 3-Way Comparative Baseline Engine** (`src/financial_engine/baseline.py`):
   - **Baseline 1 (No Solar, No Battery)**: Theoretical cost if 100% of consumption was bought from grid.
   - **Baseline 2 (Solar Only, No Battery)**: Self-consumption capped at instant daytime load + remainder exported.
   - **Actual System (Solar + SonnenBatterie 10)**: Realized net cost and battery marginal value ($\text{Savings}_{\text{Actual}} - \text{Savings}_{\text{Solar-Only}}$).
4. **Implement 2025 Full-Year ROI Engine** (`src/financial_engine/calculator_2025.py`):
   - Ingest `data/sonnen_energy_data_2025.csv`.
   - Match against full 2025 SE3 hourly/daily price series from `PriceManager`.
   - Compute month-by-month and full-year financial ledgers.
5. **Create CLI Tool** (`calc_2025_roi.py`):
   - Accepts `--capex <SEK>` to calculate dynamic payback years, ROI %, and percentage of investment recouped.
6. **Unit Tests** (`tests/test_financial_engine.py`):
   - Automated tests for all tariff equations, 3-way baselines, and 2025 test vectors.
7. **CI & PR Workflow**:
   - Push to `feat/m2-financial-engine`, open PR, let GitHub Actions verify, and merge into `main`.
