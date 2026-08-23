# Product Requirements Document (PRD): MySunshine

A comprehensive system to track, simulate, and calculate the actual financial return on investment (ROI) for a household solar panel and home battery system in Sweden (SE3), with future capabilities for solar forecasting, smart charging, and price arbitrage.

---

## 1. Objectives

### Core Objective (Phase 1: Historical ROI & Value Analysis)
Calculate the **true financial ROI and savings** of the existing solar and battery installation using real historical electricity price data (Nordpool SE3 / Tibber) and actual consumption/production logs.
- Quantify total savings against realistic baselines (No Solar/Battery, Solar-only).
- Isolate the **marginal financial contribution** of the SonnenBatterie 10.
- Account for Swedish electricity market specifics: spot prices (both hourly and 15-minute/quarterly), energy tax (*energiskatt*), grid fees (*nätavgift*), grid benefit (*nätnytta*), 25% VAT (*moms*), Tibber fees, and micro-production tax deduction (*skattereduktion* 60 öre/kWh).

### Future Objective (Phase 2: Smart Strategy & Arbitrage Optimizer)
Implement predictive battery control strategies and dynamic charging recommendations:
- **Low-Price Grid Pre-charging**: Charge the battery from the grid during cheap night hours when solar generation is forecast to be low, winter load is high, and SoC is below target threshold.
- **Spot Price Arbitrage**: Strategically charge low and discharge during high-demand/peak-price hours while factoring in the ~77% round-trip efficiency hurdle, 15-minute price volatility, and grid transfer fees.

---

## 2. System Hardware & Environmental Configuration

* **Bidding Zone**: **SE3** (Sweden - Stockholm / Central Sweden, Nordpool market).
* **Electricity Retailer (Elhandelsbolag)**: **Tibber** (`https://tibber.com/se`).
  * Price Model: Dynamic spot pricing.
  * **Pricing Resolution Transition Date**: **2025-10-01** (Switched from 60-min hourly prices to 15-min quarterly prices).
  * Fixed Subscription: 49 SEK / month (incl. moms).
* **Grid Operator (Elnätsbolag)**: **Eskilstuna Energi & Miljö (EEM)** (`https://eem.se`).
* **Solar Inverter**: **SMA Inverter model STP8.0-3AV-40** (3-phase, 8.0 kW AC rating).
* **Battery Storage**: **SonnenBatterie 10 performance** with 4 modules:
  * Nominal Capacity: ~22 kWh (~20 kWh usable).
  * Continuous Power: Up to 7.0–8.0 kW.
  * Observed Round-Trip Efficiency: ~76.7% – 77.0%.
* **Execution & Data Hub**:
  * Primary: **Home Assistant Green** (local polling, long-term statistics storage, automation hub).
  * Fallback / Analysis Host: Dedicated Ubuntu laptop running 24/7.
* **Network & Local Device Endpoints**:
  * Home Assistant Green: `192.168.3.138` (`http://ha.home`)
  * SonnenBatterie 10: `192.168.3.125` (`http://sonnen.home`)
  * SMA Inverter: `192.168.3.61` (`http://sma.home`)

---

## 3. Data Architecture & Integration Strategy

```mermaid
flowchart TD
    subgraph Data Sources
        sonnen[SonnenBatterie Local API / App Export]
        sma[SMA Inverter Webconnect / HA Integration]
        tibber[Tibber API / HA Tibber Integration]
        ha[Home Assistant Green History DB]
        price_apis[Modular Price Providers: Tibber / ENTSO-E / Elering / Energy-Charts]
    end

    subgraph Core Engine: MySunshine Analyzer
        ingest[Data Ingestion & Multi-Resolution Normalizer (15-min / Hourly / Daily)]
        price_mod[Price Matching & Swedish Tariff Engine (Tibber + EEM SE3)]
        baseline[3-Way Baseline Engine (No Solar vs. Solar Only vs. Solar+Battery)]
        roi_calc[ROI, Capex & Cash Flow Calculator]
    end

    subgraph Outputs
        ui[Interactive Dashboard & Charts]
        ha_sensor[HA Custom Sensors & Dispatch Advice (Phase 2)]
    end

    sonnen --> ingest
    sma --> ingest
    tibber --> ingest
    ha --> ingest
    price_apis --> price_mod
    ingest --> price_mod
    price_mod --> baseline
    baseline --> roi_calc
    roi_calc --> ui
    roi_calc --> ha_sensor
```

### A. Energy Data Ingestion & Resolution Matching

Because the electricity market transitioned from hourly to 15-minute prices on **2025-10-01**, the analyzer supports dynamic multi-resolution alignment:

1. **Pre-2025-10-01 Timeline (Hourly Market)**:
   * Market spot prices: Hourly (60 min).
   * Energy data: Ingested as hourly or mapped from daily aggregated totals.
2. **Post-2025-10-01 Timeline (15-Minute / Quarterly Market)**:
   * Market spot prices: 15-minute intervals (96 intervals/day).
   * **When Energy Data is Hourly (e.g. Sonnen 30-day export)**: The 4 quarterly prices within each hour are arithmetic/volume averaged for the hourly block, or synthetic quarter-hour disaggregation is applied.
   * **When Energy Data is 15-Minute (e.g. Tibber API / Home Assistant logs)**: Exact interval-by-interval multiplication for peak precision.
3. **Daily Aggregated Time-Series (2025 Historical Baseline)**:
   * Evaluated using synthetic diurnal load/generation profile weighting across the year.

### B. Modular Historical Electricity Price Engine

A pluggable adapter interface (`PriceProvider`) to fetch and cache historical SE3 spot prices with automatic fallback:

| Provider | Data Coverage | Granularity | Auth / API Key | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Tibber API (GraphQL)** | Exact household prices & historical spot | 15-min (post-2025-10-01) & Hourly (pre-2025-10-01) | Free Personal Access Token | Direct retailer ground truth |
| **ENTSO-E Transparency Platform** | Official European TSO | Hourly & 15-min | Free API Token (via email) | Primary European official source |
| **Elering API** | Nordic & Baltic Bidding Zones | Hourly | None (Public REST) | Instant fallback & verification |
| **Energy-Charts API (Fraunhofer ISE)** | European Day-Ahead Spot | Hourly | None (Public REST) | Robust secondary fallback |
| **Local Cache / Static File Adapter** | User-supplied or pre-fetched | Any | Local file | Offline & rapid test execution |

### C. Configuration, Endpoints & Secrets Management

All external API endpoints, local hardware URLs, and private security tokens are managed via a local, git-ignored `.env` file:
* **External Price APIs**:
  * `ENTSOE_API_URL` & `ENTSOE_API_KEY`: ENTSO-E Transparency Platform endpoint & security token.
  * `TIBBER_API_URL` Tibber GraphQL endpoint. 
  * `TIBBER_API_TOKEN`: Tibber GraphQL token for these scopes:
    * tibber_graph
    * user
    * homes
    * price
    * consumption
  * `ELERING_API_URL`: Elering public spot price API endpoint.
  * `ENERGY_CHARTS_API_URL`: Fraunhofer Energy-Charts API endpoint.
* **Local Hardware & Hub Endpoints**:
  * `HA_URL` & `HA_TOKEN`: Home Assistant Green base URL and optional Long-Lived Access Token.
  * `SONNEN_URL` & `SONNEN_API_TOKEN`: SonnenBatterie 10 local API base URL & token.
  * `SMA_URL`: SMA Inverter Webconnect URL.
* A template [` .env.example `](file:///C:/Users/chris/.gemini/antigravity-ide/scratch/mysunshine/.env.example) is committed to version control to provide the full configuration schema.

---

## 4. Swedish Electricity Pricing & Tariff Model (Tibber + EEM / SE3)

To determine the true financial payoff, every kWh imported and exported is calculated using the Swedish market tariff structure:

### 1. Grid Import Cost Formula ($C_{\text{import}}$)
$$C_{\text{import}}(t) = \left( \text{SpotPrice}_{\text{SE3}}(t) + \text{TibberMarkup} + \text{Elcertifikat} + \text{Energiskatt} + \text{Överföringsavgift}_{\text{EEM}} \right) \times (1 + \text{Moms}_{25\%})$$
* **SpotPrice**: 15-minute quarterly or hourly spot price (öre/kWh).
* **Tibber Markup & Certificates**: Variable retailer cost component.
* **Energiskatt (Energy Tax)**: Government energy tax (~42.8–53.5 öre/kWh incl. VAT).
* **Överföringsavgift (EEM Grid Transfer Fee)**: Variable distribution fee from Eskilstuna Energi & Miljö.
* **Moms**: 25% Swedish Value Added Tax applied to all applicable components.
* **Fixed Monthly Costs**: Tibber base fee (49 SEK/mo) + EEM grid connection subscription (*säkringsavgift*).

### 2. Grid Export Revenue Formula ($R_{\text{export}}$)
$$R_{\text{export}}(t) = \text{SpotPrice}_{\text{SE3}}(t) + \text{Nätnytta}_{\text{EEM}} + \text{Skattereduktion}_{60\text{öre}}$$
* **SpotPrice**: Received spot price per exported kWh via Tibber.
* **Nätnytta (EEM Grid Benefit)**: Payment from EEM for localized micro-production grid relief (~5–10 öre/kWh, tax-free).
* **Skattereduktion (60 öre/kWh)**: Tax reduction for green micro-production (*skattereduktion för mikroproduktion av förnybar el*, inkomstskattelagen 67 kap). Active for 2025; configurable/toggleable for 2026+ calculations.

---

## 5. Feature & Visualization Requirements

### Phase 1: Historical ROI & Financial Analytics

#### 1. Core Financial Engine
* **3-Way Comparative Financial Baselines**:
  * **Baseline 1 (No Solar, No Battery)**: Simulates total electricity bill if 100% of household consumption had to be purchased from the grid.
  * **Baseline 2 (Solar Only, No Battery)**: Simulates the financial outcome if solar panels were installed without a battery (direct self-consumption capped at instant load, remainder exported).
  * **Actual (Solar + SonnenBatterie 10)**: Realized electricity bills and export revenues.
  * **Marginal Battery Value**: $\text{Savings}_{\text{Actual}} - \text{Savings}_{\text{Solar-Only}}$ to isolate the exact annual SEK contribution of the battery.
* **Capex & Investment Payback Tracking**:
  * Configurable Net Capex input (after Swedish *Grön Teknik* deduction: 20% solar, 50% battery).
  * Computes percentage of Capex recouped to date, remaining unrecovered balance, and dynamic break-even year.
* **Battery Health & Performance Diagnostics**:
  * Tracks real-world round-trip efficiency (observed ~76.7%–77.0%), annual cycle counts, and standby energy losses.

#### 2. Dashboard UI & Visualization Blueprint
The web interface will feature a modern dark-theme dashboard with interactive visualizations:

1. **Top-Level KPI Dashboard Cards**:
   * **Total Savings to Date (SEK)**: Cumulative financial gain compared to the "No Solar" baseline.
   * **Capex Recouped Progress Gauge / Card**: e.g., *"34.2% of Capex Recouped (112,400 / 328,000 SEK)"* with a radial progress ring.
   * **Payback Period Estimate**: Estimated years to break-even based on historical run-rate and energy inflation.
   * **Marginal Battery Contribution**: Extra SEK earned solely due to battery load shifting.
   * **Annual CO₂ Offset**: Kilograms/tonnes of carbon emissions avoided.

2. **Cumulative Cash Flow & Payback S-Curve (Chart 1)**:
   * Line chart starting below zero ($-\text{Capex}$) at Year 0 and ascending through time.
   * Shows historical actuals (solid green curve) transitioning into 25-year projections (dashed line).
   * Highlights the Break-Even point ($0 line intersection) with an interactive milestone marker.

3. **3-Way Baseline Monthly Comparison (Chart 2 - Stacked Bar)**:
   * Side-by-side monthly cost breakdown comparing:
     1. Bill without Solar/Battery (Grey)
     2. Bill with Solar Only (Amber)
     3. Actual Bill with Solar + Battery (Teal)
   * Visually reveals winter vs. summer savings dynamics.

4. **Hourly Dispatch & Price Heatmap (Chart 3 - Interactive Time-Series)**:
   * Dual-axis chart overlaying 15-min/hourly SE3 spot prices against battery state-of-charge (SoC), solar generation, and home load.
   * Visually highlights how the battery charges during cheap hours and discharges during peak price spikes.

5. **25-Year Detailed Financial Ledger Table**:
   * Year-by-year tabular view: Solar Gen, Self-Consumption, Exported kWh, Imported kWh, Raw Bill, Solar Bill, Annual Savings, and Net Cumulative Balance.

---

### Phase 2: Smart Strategy & Arbitrage Optimizer

1. **Solar & Consumption Forecasting**:
   * Integrate solar generation forecasts (via SMA Inverter data or Forecast.Solar) and household consumption patterns.
   * Model battery autonomy (current battery lasts ~24h on full charge in summer, slightly less in winter).
2. **Dynamic Grid Pre-Charging Recommendation Engine**:
   * Evaluate next-day 15-minute spot prices and solar forecast.
   * Recommend force-charging the battery during cheap night hours when next-day solar is forecast to be low and peak daytime prices are high.
3. **Arbitrage Feasibility & Efficiency Gate**:
   * Gate arbitrage actions behind the efficiency threshold:
     $$\Delta \text{Price} > \frac{C_{\text{import}}}{\eta_{\text{roundtrip}}} - R_{\text{export}} + \text{LossMargin}$$
     Ensures battery is never cycled for arbitrage unless the net spread guarantees profit after accounting for the ~23% round-trip conversion loss.

---

## 6. Implementation Roadmap & Verifiable Milestones

Development is organized around **Milestone Branches** (`feat/mX-...`) that merge into `main` via GitHub Pull Requests, with CI/CD automation established starting from Milestone 1:

```mermaid
flowchart TD
    subgraph Git Workflow
        m1_branch["feat/m1-price-providers"] -->|PR + CI Check| main["main (trunk)"]
        m2_branch["feat/m2-financial-engine"] -->|PR + CI Check| main
        m3_branch["feat/m3-high-res-analyzer"] -->|PR + CI Check| main
        m4_branch["feat/m4-dashboard-ui"] -->|PR + CI Check| main
        main -->|Auto Deploy (M4+)| pages["GitHub Pages Live App"]
    end
```

### Milestone 1: Price Ingestion, Provider Module & CI Foundation
* **Branch**: `feat/m1-price-providers`
* **Deliverables**:
  * `1.1 CI Foundation`: Establish `.github/workflows/ci.yml` with **Gitleaks secret scanner**, linter, and automated test harness.
  * `1.2 PriceProvider Interface & Disk Cache`: Core modular interface and local file cache (`data/prices/`).
  * `1.3 Elering Adapter`: Zero-auth public REST client fetching hourly SE3 spot prices.
  * `1.4 ENTSO-E Adapter`: Authenticated client fetching official SE3 spot prices (hourly & 15-min).
  * `1.5 Tibber GraphQL Adapter`: Authenticated client fetching actual household spot prices.
* **Verification Gate**:
  * CI pipeline passes: Gitleaks scan is clean, and automated test suite validates price fetching and caching across providers.

### Milestone 2: 2025 Full-Year ROI & Baseline Engine
* **Branch**: `feat/m2-financial-engine`
* **Deliverables**:
  * `2.1 Swedish Tariff Calculator`: Logic for EEM grid fees, energiskatt, moms, 60 öre skattereduktion, and Tibber fees.
  * `2.2 3-Way Baseline Calculator`: Ingest `sonnen_energy_data_2025.csv`, compute synthetic hourly weights, and calculate realized vs. baseline costs.
  * `2.3 Capex & Payback Calculator`: Compute cumulative savings and percentage of investment recouped.
  * `2.4 CI Tariff Tests`: Add automated test vectors for Swedish tax/fee equations to CI.
* **Verification Gate**:
  * Audited JSON/CLI report of the 2025 financial ledger showing exact monthly/annual SEK savings and battery marginal value; CI tests pass.

### Milestone 3: High-Resolution 30-Day & Multi-Resolution Engine
* **Branch**: `feat/m3-high-res-analyzer`
* **Deliverables**:
  * `3.1 30-Day Hourly Ingestion`: Ingest `sonnen_energy_data_Sun_Aug_16_2026.csv` (744 hours).
  * `3.2 Resolution Matcher`: Align hourly energy logs with post-2025-10-01 15-minute spot prices.
  * `3.3 Accuracy Comparison Analysis`: Compare exact hourly calculation vs. daily average estimation.
  * `3.4 CI Multi-Res Tests`: Add resolution alignment tests to CI.
* **Verification Gate**:
  * Accuracy delta report measuring variance between daily-averaged vs. hourly-settled energy costs; CI tests pass.

### Milestone 4: Interactive Web Dashboard & GitHub Pages CD
* **Branch**: `feat/m4-dashboard-ui`
* **Deliverables**:
  * `4.1 KPI Cards & Capex Progress Ring`: Display total savings, recouped investment %, and payback estimate.
  * `4.2 Cumulative Payback S-Curve Chart`: Interactive Chart.js graph tracking cash flow across 25 years.
  * `4.3 3-Way Baseline Bar Chart`: Monthly visual comparison of No Solar vs. Solar Only vs. Actual.
  * `4.4 Hourly Dispatch & Price Overlay Chart`: 24h interactive dispatch viewer.
  * `4.5 Interactive Financial Ledger Table & Capex Slider`: Live updating UI controls.
  * `4.6 Automated CD Workflow`: Add `.github/workflows/deploy.yml` for automated GitHub Pages continuous deployment on merge to `main`.
* **Verification Gate**:
  * Merging PR to `main` automatically deploys the live, responsive web app to GitHub Pages with zero secret leakage.

### Milestone 5: Home Assistant Integration & Phase 2 Optimizer
* **Branch**: `feat/m5-ha-integration`
* **Deliverables**:
  * `5.1 Home Assistant Polling Integration`: Ingest live metrics from Sonnen/SMA HA entities.
  * `5.2 Custom HA Sensor / Dashboard Cards`: Publish live ROI and daily savings to HA.
  * `5.3 Phase 2 Grid Pre-Charging Advisor`: Implement the efficiency-gated dynamic charging recommendation engine.
* **Verification Gate**:
  * Publish a verified sensor state to Home Assistant advising optimal charging schedule for the next day.

---

## 7. CI/CD & Automated Deployment Strategy (GitHub Actions)

Because the repository is hosted on a **public GitHub profile**, we establish an automated quality and security pipeline from Day 1:

```mermaid
flowchart LR
    push[Git Push / PR to main] --> sec[Gitleaks Secret Scan]
    push --> lint[Lint & Syntax Check]
    push --> test[Automated Tariff & Price Tests]
    sec & lint & test --> merge[PR Approved & Merged to main]
    merge --> deploy[GitHub Pages Automated Deployment]
    deploy --> live[Live Web Dashboard]
```

### 1. Phased Pipeline Evolution Roadmap

| Pipeline Feature | Introduced In | Purpose |
| :--- | :--- | :--- |
| **Gitleaks Secret Leak Scan** | **Milestone 1** | Scans every PR/commit to ensure `.env` and tokens are never committed to public GitHub. |
| **Lint & Syntax Validation** | **Milestone 1** | Ensures code quality and consistent formatting. |
| **Price Provider & Cache Tests** | **Milestone 1** | Verifies spot price parsers and caching logic against mock responses. |
| **Tariff & Baseline Math Tests** | **Milestone 2** | Tests Swedish tax/fee equations and 3-way baseline logic against test vectors. |
| **Resolution Alignment Tests** | **Milestone 3** | Verifies hourly/quarterly timestamp synchronization. |
| **GitHub Pages Auto-Deployment (CD)** | **Milestone 4** | Automatically publishes the web app on merge to `main`. |

### 2. API Key Security & Zero Client-Side Secret Exposure Architecture

> [!CAUTION]
> **Strict Security Boundary**: Private API keys (`ENTSOE_API_KEY`, `TIBBER_API_TOKEN`, Home Assistant tokens) **must NEVER be shipped to, embedded in, or called directly from client-side JavaScript** deployed on public GitHub Pages.

1. **Build-Time / Local Data Pipeline (Static Data Baking)**:
   * Data fetching using authenticated APIs (ENTSO-E / Tibber) runs **strictly server-side** (locally on your machine or inside ephemeral GitHub Actions runners).
   * The pipeline processes and normalizes the historical price data into sanitized, static JSON data files (`data/prices/se3_prices_2025.json`).
   * The static web app on GitHub Pages merely loads these pre-computed JSON files. **No API tokens exist in the browser bundle or client network requests.**
2. **Zero-Auth Fallbacks for Client Runtime**:
   * If the browser needs live day-ahead spot prices at runtime without a backend server, it exclusively queries **unauthenticated public APIs** (such as Elering public REST or Energy-Charts) that do not require any secret tokens.
3. **GitHub Secrets for CI Automation**:
   * API tokens used in automated build or test workflows are stored as encrypted **GitHub Repository Secrets** (`Settings -> Secrets and variables -> Actions`). They are injected into ephemeral GitHub Actions runners during build time and are never exposed in build artifacts or public web pages.




