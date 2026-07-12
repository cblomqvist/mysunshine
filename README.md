# MySunshine ☀️🔋

A premium, interactive web application to simulate and calculate the financial and environmental return on investment (ROI) for solar panels and home battery systems.

## Features

- **Dynamic Financial Model**: Instantly calculates payback period, net savings, ROI, and localized CO2 reduction.
- **Hourly Energy Simulation**: Visualizes daily household load profiles, solar generation curves, and battery state-of-charge (SoC).
- **Interactive Lifetime Charts**: Interactive Chart.js graph depicting cumulative cash flow over a 25-year lifetime.
- **Glassmorphism UI**: Beautiful, dark-themed responsive design optimized for desktop and mobile screens.

## Quick Start

1. Clone or download this project.
2. Open `index.html` directly in any modern web browser.
3. Adjust the system size, installation costs, electricity rates, and battery parameters to see your customized payoff results instantly.

## Solar & Battery Simulation Logic

MySunshine simulates household energy flows hourly using:
1. **Solar Production**: Modeled using a Bell curve peaking at solar noon, scaled by your location's daily sun hours and system capacity.
2. **Household Load**: Modeled using a standard dual-peak daily residential consumption profile (morning prep and evening peak).
3. **Battery Operations**:
   - Charge battery when solar production exceeds household usage (up to battery capacity).
   - Discharge battery when usage exceeds solar production (down to 0% SoC).
   - Draw from grid if usage exceeds solar production and battery is depleted.
   - Export excess solar to the grid once battery is fully charged.
