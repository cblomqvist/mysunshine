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

## 5. Feature Requirements

### Phase 1: Historical ROI & Value Analysis

1. **3-Way Comparative Financial Baseline**:
   * **Baseline 1 (No Solar, No Battery)**: Simulates total electricity bill if 100% of household consumption had to be purchased from the grid.
   * **Baseline 2 (Solar Only, No Battery)**: Simulates the financial outcome if solar panels were installed without a battery (direct self-consumption capped at instant load, remainder exported).
   * **Actual (Solar + SonnenBatterie 10)**: Realized electricity bills and export revenues.
   * **Marginal Battery Value**: $\text{Savings}_{\text{Actual}} - \text{Savings}_{\text{Solar-Only}}$ to show the exact annual SEK contribution of the battery.
2. **Capex & Payback Period Tracking**:
   * Input field for Net Capex (after Swedish *Grön Teknik* deduction: 20% solar, 50% battery).
   * Calculates dynamic payback years, cumulative net cash flow curve, and annualized ROI %.
3. **Battery Health & Performance Diagnostics**:
   * Continuous tracking of round-trip efficiency (observed ~76.7%–77.0%), daily throughput cycles, and standby losses.
4. **Interactive Dashboard & Financial Ledger**:
   * Monthly and annual breakdown of energy flows (produced, self-consumed, charged, discharged, exported, imported).
   * Financial ledger showing costs, export revenue, tax reductions, and net savings.

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

## 6. Implementation Roadmap & Milestones

1. **Milestone 1: Price Provider Module**: Implement the modular `PriceProvider` interface with adapters for Tibber API, Elering, Energy-Charts, and ENTSO-E (handling the 2025-10-01 hourly-to-quarterly transition).
2. **Milestone 2: 2025 Full-Year ROI Engine**: Ingest `sonnen_energy_data_2025.csv`, match against 2025 SE3 prices, apply Tibber/EEM/Swedish tax rules, and compute 2025 realized savings.
3. **Milestone 3: High-Resolution 30-Day Analyzer**: Ingest `sonnen_energy_data_Sun_Aug_16_2026.csv` for exact hourly/quarterly spot-price matching and compare against daily aggregated approximations.
4. **Milestone 4: Interactive Web Dashboard**: Provide interactive charts for 3-way baseline comparisons, cumulative ROI, and hourly dispatch views.
5. **Milestone 5: Home Assistant Integration / Phase 2 Optimization**: Setup continuous data logging and Phase 2 dispatch advice.
