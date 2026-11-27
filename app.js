// MySunshine Web Dashboard Application Logic
// Milestone 5: Multi-Year Historical Expansion & Calculation Validation

// Global state and chart instances
let dashboardData = null;
let chartPaybackInstance = null;
let chartMonthlyBaselinesInstance = null;
let chartHourlyDispatchInstance = null;
let chartShadowForecastInstance = null;

// Default Swedish Tariff & Capex Constants
const DEFAULT_NET_CAPEX = 315000;   // 165k SEK Net Solar (Jan 2021) + 150k SEK Net Battery (Sep 2023/2024)
const DEFAULT_GROSS_CAPEX = 506250; // Pre-subsidy gross (~206.25k solar + ~300k battery)
const MOMS_RATE = 0.25;

// DOM Elements: Controls
const netCapexInput = document.getElementById('net-capex');
const netCapexVal = document.getElementById('net-capex-val');
const gronTeknikToggle = document.getElementById('gron-teknik-toggle');
const skattereduktionToggle = document.getElementById('skattereduktion-toggle');
const inflationRateInput = document.getElementById('inflation-rate');
const inflationRateVal = document.getElementById('inflation-rate-val');
const energiskattInput = document.getElementById('energiskatt-rate');
const energiskattVal = document.getElementById('energiskatt-rate-val');
const eemTransferInput = document.getElementById('eem-transfer-rate');
const eemTransferVal = document.getElementById('eem-transfer-rate-val');
const tibberFeeInput = document.getElementById('tibber-fee');
const tibberFeeVal = document.getElementById('tibber-fee-val');

// Historical Year & Dispatch Controls
const historyYearSelect = document.getElementById('history-year-select');
const monthlyTabTitle = document.getElementById('monthly-tab-title');
const dispatchDaySelect = document.getElementById('dispatch-day-select');
const btnPresetPeakSolar = document.getElementById('btn-preset-peak-solar');
const btnPresetVolatility = document.getElementById('btn-preset-volatility');
const btnPresetCloudy = document.getElementById('btn-preset-cloudy');
const dispatchChartSubtitle = document.getElementById('dispatch-chart-subtitle');

// KPI Displays
const valTotalSavings = document.getElementById('val-total-savings');
const subSavingsBaseline = document.getElementById('sub-savings-baseline');
const valRecoupedPct = document.getElementById('val-recouped-pct');
const valRecoupedSek = document.getElementById('val-recouped-sek');
const progressRingCircle = document.getElementById('progress-ring-circle');
const valPayback = document.getElementById('val-payback');
const subPaybackDetail = document.getElementById('sub-payback-detail');
const valBatteryMarginal = document.getElementById('val-battery-marginal');
const valCo2 = document.getElementById('val-co2');
const breakevenBadge = document.getElementById('breakeven-badge');

// Diagnostics Displays
const diagScPct = document.getElementById('diag-sc-pct');
const diagEffPct = document.getElementById('diag-eff-pct');
const diagAnnualGen = document.getElementById('diag-annual-gen');

// Table Bodies
const ledger2025Body = document.getElementById('ledger-2025-body');
const ledgerMultiyearBody = document.getElementById('ledger-multiyear-body');
const ledger25yBody = document.getElementById('ledger-25y-body');
const ledgerVarianceBody = document.getElementById('ledger-variance-body');
const ledgerUtilityAuditBody = document.getElementById('ledger-utility-audit-body');
const shadowScenarioSelect = document.getElementById('shadow-scenario-select');
const ledgerShadowHourlyBody = document.getElementById('ledger-shadow-hourly-body');
const ledgerShadowBacktestBody = document.getElementById('ledger-shadow-backtest-body');
const haSafetySimToggle = document.getElementById('ha-safety-sim-toggle');
const ledgerHaEntitiesBody = document.getElementById('ledger-ha-entities-body');
const ledgerHaCommandsBody = document.getElementById('ledger-ha-commands-body');

// Formatting Helpers
function formatSEK(num) {
    if (isNaN(num)) return '0 SEK';
    return `${Math.round(num).toLocaleString('sv-SE')} SEK`;
}

function formatCurrencyNoUnit(num) {
    if (isNaN(num)) return '0';
    return Math.round(num).toLocaleString('sv-SE');
}

function formatKWh(num) {
    if (isNaN(num)) return '0';
    return `${Math.round(num).toLocaleString('sv-SE')} kWh`;
}

// Initialize Application
async function initApp() {
    try {
        if (window.MYSUNSHINE_DATA) {
            dashboardData = window.MYSUNSHINE_DATA;
        } else {
            const resp = await fetch('data/dashboard_data.json');
            dashboardData = await resp.json();
        }
        setupEventListeners();
        populateDispatchDays();
        populateVarianceTable();
        populateUtilityAuditTable();
        populateShadowAdvisorTab();
        populateHomeAssistantBridgeTab();
        updateSimulation();
    } catch (err) {
        console.error('Failed to load dashboard data:', err);
    }
}

// Setup Event Listeners
function setupEventListeners() {
    // Sliders
    netCapexInput.addEventListener('input', () => {
        netCapexVal.innerText = formatSEK(parseFloat(netCapexInput.value));
        updateSimulation();
    });

    gronTeknikToggle.addEventListener('change', () => {
        if (gronTeknikToggle.checked) {
            netCapexInput.value = DEFAULT_NET_CAPEX;
            netCapexVal.innerText = formatSEK(DEFAULT_NET_CAPEX);
        } else {
            netCapexInput.value = DEFAULT_GROSS_CAPEX;
            netCapexVal.innerText = formatSEK(DEFAULT_GROSS_CAPEX);
        }
        updateSimulation();
    });

    skattereduktionToggle.addEventListener('change', updateSimulation);

    inflationRateInput.addEventListener('input', () => {
        inflationRateVal.innerText = `${parseFloat(inflationRateInput.value).toFixed(1)}%`;
        updateSimulation();
    });

    energiskattInput.addEventListener('input', () => {
        energiskattVal.innerText = `${parseFloat(energiskattInput.value).toFixed(1)} öre/kWh`;
        updateSimulation();
    });

    eemTransferInput.addEventListener('input', () => {
        eemTransferVal.innerText = `${parseFloat(eemTransferInput.value).toFixed(1)} öre/kWh`;
        updateSimulation();
    });

    tibberFeeInput.addEventListener('input', () => {
        tibberFeeVal.innerText = `${parseFloat(tibberFeeInput.value).toFixed(0)} SEK`;
        updateSimulation();
    });

    // Historical Year Filter
    if (historyYearSelect) {
        historyYearSelect.addEventListener('change', updateSimulation);
    }

    // Dispatch Day Selectors
    dispatchDaySelect.addEventListener('change', () => {
        updateHourlyDispatchChart();
        updatePresetButtonsState();
    });

    btnPresetPeakSolar.addEventListener('click', () => {
        if (dashboardData && dashboardData.metadata && dashboardData.metadata.featured_days) {
            dispatchDaySelect.value = dashboardData.metadata.featured_days.peak_solar;
            updateHourlyDispatchChart();
            updatePresetButtonsState();
        }
    });

    btnPresetVolatility.addEventListener('click', () => {
        if (dashboardData && dashboardData.metadata && dashboardData.metadata.featured_days) {
            dispatchDaySelect.value = dashboardData.metadata.featured_days.peak_volatility;
            updateHourlyDispatchChart();
            updatePresetButtonsState();
        }
    });

    btnPresetCloudy.addEventListener('click', () => {
        if (dashboardData && dashboardData.metadata && dashboardData.metadata.featured_days) {
            dispatchDaySelect.value = dashboardData.metadata.featured_days.cloudy_day;
            updateHourlyDispatchChart();
            updatePresetButtonsState();
        }
    });

    // Tab Navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const target = btn.getAttribute('data-tab');
            const targetEl = document.getElementById(target);
            if (targetEl) targetEl.classList.add('active');
            if (target === 'tab-shadow-forecast') {
                updateShadowAdvisorView();
            } else if (target === 'tab-ha-bridge') {
                populateHomeAssistantBridgeTab();
            }
        });
    });

    if (shadowScenarioSelect) {
        shadowScenarioSelect.addEventListener('change', updateShadowAdvisorView);
    }

    if (haSafetySimToggle) {
        haSafetySimToggle.addEventListener('change', populateHomeAssistantBridgeTab);
    }
}

function updatePresetButtonsState() {
    const selectedDate = dispatchDaySelect.value;
    const feats = dashboardData?.metadata?.featured_days;
    btnPresetPeakSolar.classList.toggle('active', feats?.peak_solar === selectedDate);
    btnPresetVolatility.classList.toggle('active', feats?.peak_volatility === selectedDate);
    btnPresetCloudy.classList.toggle('active', feats?.cloudy_day === selectedDate);
}

// Populate Dispatch Day Dropdown
function populateDispatchDays() {
    if (!dashboardData || !dashboardData.high_res_30d || !dashboardData.high_res_30d.days_list) return;
    
    const days = dashboardData.high_res_30d.days_list;
    dispatchDaySelect.innerHTML = '';
    
    days.forEach(day => {
        const opt = document.createElement('option');
        opt.value = day.date;
        opt.innerText = `${day.display_name} (${day.total_produced_kwh} kWh PV, ${day.avg_spot_price_ore} öre avg)`;
        dispatchDaySelect.appendChild(opt);
    });

    const defaultDay = dashboardData.metadata?.featured_days?.peak_solar || days[0].date;
    dispatchDaySelect.value = defaultDay;
}

// Helper: Recalculate financial costs for a list of monthly ledgers given current tariff settings
function recalculateLedgerMonths(monthlyLedgers, energiskattSek, eemTransferSek, taxRedEnabled, tibberFee, defaultYear = 2025) {
    const BAKED_ENERGISKATT_SEK = 0.428;
    const BAKED_EEM_TRANSFER_SEK = 0.176;
    const BAKED_TIBBER_FEE_SEK = 49.0;

    return monthlyLedgers.map(m => {
        const year = m.year || defaultYear;

        // Export revenue subsidy (Skattereduktion 60 öre/kWh ended 2026-01-01)
        const isTaxRedValid = taxRedEnabled && (year < 2026);
        const taxRedSek = isTaxRedValid ? 0.60 : 0.0;
        const bakedTaxRedSek = (year < 2026) ? 0.60 : 0.0;

        // Monthly fixed cost delta relative to baked 49 SEK/month Tibber fee
        const daysInMonth = m.days_count || m.days || 30;
        const monthFraction = daysInMonth / 30.4375;
        const deltaFixedCost = (tibberFee - BAKED_TIBBER_FEE_SEK) * monthFraction;

        // Linear variable tariff deltas per kWh relative to baked defaults
        const deltaImportCostPerKwh = ((energiskattSek - BAKED_ENERGISKATT_SEK) + (eemTransferSek - BAKED_EEM_TRANSFER_SEK)) * (1.0 + MOMS_RATE);
        const deltaExportRevPerKwh = taxRedSek - bakedTaxRedSek;

        // Baseline 2 (Solar Only) kWh volumes
        const isSolarOnlyMonth = (!m.battery_charged_kwh && !m.battery_discharged_kwh);
        const scPct = (m.solar_only_self_consumption_pct ?? m.solar_only_sc_pct ?? 35.0) / 100.0;
        const solarDirectSC = isSolarOnlyMonth ? Math.max(0, m.produced_kwh - m.exported_kwh) : Math.min(m.consumed_kwh, m.produced_kwh * scPct);
        const solarOnlyImport = isSolarOnlyMonth ? m.imported_kwh : Math.max(0, m.consumed_kwh - solarDirectSC);
        const solarOnlyExport = isSolarOnlyMonth ? m.exported_kwh : Math.max(0, m.produced_kwh - solarDirectSC);
        const solarOnlyTaxRed = solarOnlyExport * taxRedSek;
        const actualTaxRed = m.exported_kwh * taxRedSek;

        // Anchor on baked hourly/diurnal-matched bills and apply exact linear slider deltas
        const bakedNoSolar = m.baseline_no_solar_cost_sek ?? m.baseline_no_solar_sek ?? 0;
        const bakedSolarOnly = m.baseline_solar_only_cost_sek ?? m.baseline_solar_only_sek ?? 0;
        const bakedActual = m.actual_cost_sek ?? 0;

        const noSolarCost = bakedNoSolar + (m.consumed_kwh * deltaImportCostPerKwh) + deltaFixedCost;
        const solarOnlyCost = isSolarOnlyMonth
            ? (bakedActual + (m.imported_kwh * deltaImportCostPerKwh) - (m.exported_kwh * deltaExportRevPerKwh) + deltaFixedCost)
            : (bakedSolarOnly + (solarOnlyImport * deltaImportCostPerKwh) - (solarOnlyExport * deltaExportRevPerKwh) + deltaFixedCost);
        const actualCost = bakedActual + (m.imported_kwh * deltaImportCostPerKwh) - (m.exported_kwh * deltaExportRevPerKwh) + deltaFixedCost;

        const totalSavings = noSolarCost - actualCost;
        const solarSavings = noSolarCost - solarOnlyCost;
        const batteryMarginal = totalSavings - solarSavings;

        return {
            ...m,
            month: m.month_name || m.month,
            year: year,
            is_tax_red_valid: isTaxRedValid,
            solar_only_tax_red_sek: solarOnlyTaxRed,
            actual_tax_red_sek: actualTaxRed,
            solar_only_export_kwh: solarOnlyExport,
            baseline_no_solar_sek: noSolarCost,
            baseline_solar_only_sek: solarOnlyCost,
            actual_cost_sek: actualCost,
            total_savings_sek: totalSavings,
            solar_savings_sek: solarSavings,
            battery_savings_sek: batteryMarginal
        };
    });
}

// Main Recalculate and Update Function
function updateSimulation() {
    if (!dashboardData) return;

    const netCapex = parseFloat(netCapexInput.value);
    const taxRedEnabled = skattereduktionToggle.checked;
    const inflation = parseFloat(inflationRateInput.value) / 100.0;
    const energiskattSek = parseFloat(energiskattInput.value) / 100.0;
    const eemTransferSek = parseFloat(eemTransferInput.value) / 100.0;
    const tibberFee = parseFloat(tibberFeeInput.value);
    const selectedPeriod = historyYearSelect ? historyYearSelect.value : 'all';

    // 1. Process all available historical years
    const rawYearsData = dashboardData.years || (dashboardData.year_2025 ? { 2025: dashboardData.year_2025 } : {});
    const availableYearKeys = Object.keys(rawYearsData).sort();

    const recalculatedYears = {};
    const annualSummaries = [];

    availableYearKeys.forEach(yrStr => {
        const yrData = rawYearsData[yrStr];
        const yrInt = parseInt(yrStr, 10);
        const months = yrData.monthly_ledgers || [];
        const recalcedMonths = recalculateLedgerMonths(months, energiskattSek, eemTransferSek, taxRedEnabled, tibberFee, yrInt);
        recalculatedYears[yrStr] = recalcedMonths;

        const totProd = recalcedMonths.reduce((a, m) => a + m.produced_kwh, 0);
        const totCons = recalcedMonths.reduce((a, m) => a + m.consumed_kwh, 0);
        const totImp = recalcedMonths.reduce((a, m) => a + m.imported_kwh, 0);
        const totExp = recalcedMonths.reduce((a, m) => a + m.exported_kwh, 0);
        const totDis = recalcedMonths.reduce((a, m) => a + m.battery_discharged_kwh, 0);
        const totNoSol = recalcedMonths.reduce((a, m) => a + m.baseline_no_solar_sek, 0);
        const totSolOnly = recalcedMonths.reduce((a, m) => a + m.baseline_solar_only_sek, 0);
        const totAct = recalcedMonths.reduce((a, m) => a + m.actual_cost_sek, 0);
        const totSav = totNoSol - totAct;
        const totSolSav = totNoSol - totSolOnly;
        const totBatSav = totSav - totSolSav;
        const daysCount = recalcedMonths.reduce((a, m) => a + (m.days_count || m.days || 30), 0);
        const totSolTaxRed = recalcedMonths.reduce((a, m) => a + (m.solar_only_tax_red_sek || 0), 0);
        const totActTaxRed = recalcedMonths.reduce((a, m) => a + (m.actual_tax_red_sek || 0), 0);

        let eraName = "Sonnen 22 kWh (Dual)";
        if (yrStr === "2021") eraName = "Solar PV Only (SMA 8 kW)";
        else if (yrStr === "2022") eraName = "Solar PV Only (Energy Crisis)";
        else if (yrStr === "2023") eraName = "Sonnen 11 kWh Installed (Sep)";
        else if (yrStr === "2024") eraName = "11 kWh → 22 kWh Expansion (Sep 9)";
        else if (yrStr === "2026") eraName = "Sonnen 22 kWh (No Skattereduktion)";

        annualSummaries.push({
            year: yrInt,
            era: eraName,
            is_tax_red_valid: yrInt < 2026 && taxRedEnabled,
            days: daysCount,
            produced_kwh: totProd,
            consumed_kwh: totCons,
            imported_kwh: totImp,
            exported_kwh: totExp,
            battery_discharged_kwh: totDis,
            baseline_no_solar_sek: totNoSol,
            baseline_solar_only_sek: totSolOnly,
            actual_cost_sek: totAct,
            total_savings_sek: totSav,
            solar_savings_sek: totSolSav,
            battery_savings_sek: totBatSav,
            solar_only_tax_red_sek: totSolTaxRed,
            actual_tax_red_sek: totActTaxRed
        });
    });

    // 2. Determine Active Selection (All vs Specific Year)
    let displayMonths = [];
    let kpiNoSolar = 0;
    let kpiActual = 0;
    let kpiSolarOnly = 0;
    let kpiSolarGen = 0;
    let kpiSubTitle = '';

    const firstYear = availableYearKeys[0] || '2023';
    const lastYear = availableYearKeys[availableYearKeys.length - 1] || '2026';

    if (selectedPeriod === 'all') {
        availableYearKeys.forEach(yk => {
            displayMonths = displayMonths.concat(recalculatedYears[yk]);
        });
        kpiNoSolar = annualSummaries.reduce((a, y) => a + y.baseline_no_solar_sek, 0);
        kpiActual = annualSummaries.reduce((a, y) => a + y.actual_cost_sek, 0);
        kpiSolarOnly = annualSummaries.reduce((a, y) => a + y.baseline_solar_only_sek, 0);
        kpiSolarGen = annualSummaries.reduce((a, y) => a + y.produced_kwh, 0);
        kpiSubTitle = `vs. ${formatSEK(kpiNoSolar)} No-Solar baseline (${firstYear}–${lastYear} Cumulative)`;
        if (monthlyTabTitle) monthlyTabTitle.innerText = `All Historical Months (${firstYear}–${lastYear})`;
    } else {
        displayMonths = recalculatedYears[selectedPeriod] || recalculatedYears['2025'] || [];
        const yrSummary = annualSummaries.find(y => y.year === parseInt(selectedPeriod, 10));
        if (yrSummary) {
            kpiNoSolar = yrSummary.baseline_no_solar_sek;
            kpiActual = yrSummary.actual_cost_sek;
            kpiSolarOnly = yrSummary.baseline_solar_only_sek;
            kpiSolarGen = yrSummary.produced_kwh;
        }
        kpiSubTitle = `vs. ${formatSEK(kpiNoSolar)} No-Solar baseline (${selectedPeriod})`;
        if (monthlyTabTitle) monthlyTabTitle.innerText = `${selectedPeriod} Monthly Ledger`;
    }

    const kpiSavings = kpiNoSolar - kpiActual;
    const kpiSolarContribution = kpiNoSolar - kpiSolarOnly;
    const kpiBatteryMarginal = kpiSavings - kpiSolarContribution;

    // 3. Update Deliverable 4.1 & 5.4: KPI Cards & Radial Ring
    valTotalSavings.innerText = formatSEK(kpiSavings);
    subSavingsBaseline.innerText = kpiSubTitle;

    const recoupedPct = netCapex > 0 ? (kpiSavings / netCapex) * 100.0 : 0.0;
    valRecoupedPct.innerText = `${recoupedPct.toFixed(1)}%`;
    valRecoupedSek.innerText = `${formatCurrencyNoUnit(kpiSavings)} / ${formatCurrencyNoUnit(netCapex)} SEK`;

    // Radial Progress Ring (Circumference = 201.06)
    const ringCircumference = 201.06;
    const ringOffset = ringCircumference - (Math.min(100.0, recoupedPct) / 100.0) * ringCircumference;
    if (progressRingCircle) {
        progressRingCircle.style.strokeDashoffset = ringOffset.toFixed(2);
    }

    // Battery Marginal Value KPI
    valBatteryMarginal.innerText = `${Math.round(kpiBatteryMarginal).toLocaleString('sv-SE')} SEK`;
    if (kpiBatteryMarginal < 0) {
        valBatteryMarginal.classList.add('text-loss');
        valBatteryMarginal.classList.remove('text-savings');
    } else {
        valBatteryMarginal.classList.add('text-savings');
        valBatteryMarginal.classList.remove('text-loss');
    }

    // CO2 Saved (0.4 kg CO2 per kWh solar)
    const annualCo2Tons = (kpiSolarGen * 0.0004);
    valCo2.innerText = annualCo2Tons.toFixed(2);

    // Diagnostics (from latest full year 2025 or summary)
    if (dashboardData.year_2025 && dashboardData.year_2025.energy_totals) {
        diagScPct.innerText = `${dashboardData.year_2025.energy_totals.actual_self_consumption_pct.toFixed(1)}%`;
        diagEffPct.innerText = `${dashboardData.year_2025.energy_totals.battery_roundtrip_efficiency_pct.toFixed(1)}%`;
        diagAnnualGen.innerText = formatKWh(dashboardData.year_2025.energy_totals.produced_kwh);
    }

    // 4. 25-Year Projection & Payback (Actual historicals for 2021–2026 + stabilized 22 kWh run-rate forward)
    const baseMonths2025 = recalculatedYears['2025'] || displayMonths;
    const baseSavings2025 = baseMonths2025.reduce((a, m) => a + m.total_savings_sek, 0);
    const projection25y = calculate25YearProjection(netCapex, baseSavings2025, inflation, baseMonths2025, annualSummaries);
    
    if (projection25y.paybackYear !== null) {
        valPayback.innerText = projection25y.paybackYear.toFixed(1);
        subPaybackDetail.innerText = `Break-even: ~${Math.round(parseFloat(projection25y.breakEvenCalendarYear))} (${projection25y.paybackYear.toFixed(1)} yrs from 2021)`;
        breakevenBadge.innerHTML = `<i class="fa-solid fa-flag-checkered"></i> Break-Even: Year ${Math.round(parseFloat(projection25y.breakEvenCalendarYear))} (${projection25y.paybackYear.toFixed(1)}y)`;
    } else {
        valPayback.innerText = '>25';
        subPaybackDetail.innerText = 'Payback exceeds 25-year window';
        breakevenBadge.innerHTML = `<i class="fa-solid fa-hourglass-end"></i> Payback > 25 Years`;
    }

    // 5. Render Chart 1 (Cumulative Payback S-Curve)
    renderPaybackSCurveChart(projection25y);

    // 6. Render Chart 2 (3-Way Baseline Comparison - Annual Comparison if 'all', Monthly if specific year)
    const baselineChartTitleText = document.getElementById('baseline-chart-title-text');
    const baselineChartSubtitleText = document.getElementById('baseline-chart-subtitle-text');
    const skatBadge = document.getElementById('skattereduktion-chart-badge');
    const skatBadgeText = document.getElementById('skattereduktion-badge-text');

    if (selectedPeriod === 'all') {
        if (baselineChartTitleText) baselineChartTitleText.innerText = '3-Way Baseline Yearly Comparison';
        if (baselineChartSubtitleText) baselineChartSubtitleText.innerText = `Annual Totals (${firstYear}–${lastYear}): No Solar (Grey) vs. Solar Only (Amber) vs. Actual System (Teal)`;
        if (skatBadge && skatBadgeText) {
            skatBadge.className = 'badge badge-accent';
            skatBadgeText.innerText = 'Hatched Area = Skattereduktion (2021–2025; 0 kr in 2026)';
        }
        renderAnnualComparisonChart(annualSummaries);
    } else {
        if (baselineChartTitleText) baselineChartTitleText.innerText = `${selectedPeriod} 3-Way Baseline Monthly Comparison`;
        if (baselineChartSubtitleText) baselineChartSubtitleText.innerText = `${selectedPeriod} Monthly: No Solar (Grey) vs. Solar Only (Amber) vs. Actual System (Teal)`;
        if (skatBadge && skatBadgeText) {
            const is2026OrLater = parseInt(selectedPeriod, 10) >= 2026;
            if (is2026OrLater || !taxRedEnabled) {
                skatBadge.className = 'badge badge-muted';
                skatBadgeText.innerText = is2026OrLater ? 'Skattereduktion: 0 öre/kWh (Abolished 2026)' : 'Skattereduktion: Disabled';
            } else {
                skatBadge.className = 'badge badge-accent';
                skatBadgeText.innerText = 'Hatched Area = Skattereduktion (60 öre/kWh)';
            }
        }
        renderMonthlyBaselinesChart(displayMonths);
    }

    // 7. Render Chart 3 (Hourly Dispatch & Price Overlay)
    updateHourlyDispatchChart();

    // 8. Populate Financial Ledger Tables
    renderMonthlyLedgerTable(displayMonths);
    renderMultiYearSummaryTable(annualSummaries);
    render25YearLedgerTable(projection25y.tableRows);
}

// 25-Year Projection Math (Starting Jan 2021 Solar Installation)
function calculate25YearProjection(capex, baseYearSavings, inflationRate, monthsData, annualSummaries = []) {
    const START_YEAR = 2021;
    let cumulative = -capex;
    let paybackYearFraction = null;
    let breakEvenCalendarYear = null;
    const labels = [`${START_YEAR} (Install)`];
    const dataPoints = [-capex];
    const tableRows = [];

    const baseSolarGen = monthsData.reduce((acc, m) => acc + m.produced_kwh, 0);
    const baseConsumed = monthsData.reduce((acc, m) => acc + m.consumed_kwh, 0);
    const baseImport = monthsData.reduce((acc, m) => acc + m.imported_kwh, 0);
    const baseExport = monthsData.reduce((acc, m) => acc + m.exported_kwh, 0);
    const baseNoSolarBill = monthsData.reduce((a, m) => a + m.baseline_no_solar_sek, 0);
    const baseActualBill = monthsData.reduce((a, m) => a + m.actual_cost_sek, 0);

    const summaryByYear = {};
    annualSummaries.forEach(s => {
        summaryByYear[s.year] = s;
    });

    let historicalCount = 0;

    for (let y = 1; y <= 25; y++) {
        const calYear = START_YEAR + (y - 1);
        const solarFactor = Math.pow(0.995, y - 1);
        const inflationFactor = Math.pow(1 + inflationRate, y - 1);
        const hist = summaryByYear[calYear];

        let currentSolarGen;
        let selfConsumed;
        let exported;
        let imported;
        let noSolarBill;
        let actualBill;
        let currentSavings;

        if (hist) {
            historicalCount = y;
            currentSolarGen = hist.produced_kwh;
            selfConsumed = Math.max(0, hist.produced_kwh - hist.exported_kwh);
            exported = hist.exported_kwh;
            imported = hist.imported_kwh;
            noSolarBill = hist.baseline_no_solar_sek;
            actualBill = hist.actual_cost_sek;
            currentSavings = hist.total_savings_sek;
        } else {
            currentSolarGen = baseSolarGen * solarFactor;
            selfConsumed = Math.max(0, baseConsumed - baseImport);
            exported = baseExport * solarFactor;
            imported = baseImport;
            noSolarBill = baseNoSolarBill * inflationFactor;
            actualBill = baseActualBill * inflationFactor;
            currentSavings = baseYearSavings * solarFactor * inflationFactor;
        }

        const previousNet = cumulative;
        cumulative += currentSavings;

        if (paybackYearFraction === null && cumulative >= 0) {
            const fraction = Math.abs(previousNet) / currentSavings;
            paybackYearFraction = (y - 1) + fraction;
            breakEvenCalendarYear = (START_YEAR + (y - 1) + fraction).toFixed(1);
        }

        let milestoneTag = '';
        if (calYear === 2021) {
            milestoneTag = ' (Solar Installed - Actual)';
        } else if (calYear === 2022) {
            milestoneTag = ' (Energy Crisis - Actual)';
        } else if (calYear === 2023) {
            milestoneTag = ' (+11 kWh Batt - Actual)';
        } else if (calYear === 2024) {
            milestoneTag = ' (+22 kWh Exp - Actual)';
        } else if (calYear === 2025) {
            milestoneTag = ' (Full Year Actual)';
        } else if (calYear === 2026 && hist) {
            milestoneTag = ' (YTD Actual)';
        } else {
            milestoneTag = ' (Proj)';
        }

        labels.push(`${calYear}`);
        dataPoints.push(Math.round(cumulative));

        tableRows.push({
            year: `${calYear}${milestoneTag}`,
            solarGen: Math.round(currentSolarGen),
            selfConsumed: Math.round(selfConsumed),
            exported: Math.round(exported),
            imported: Math.round(imported),
            noSolarBill: Math.round(noSolarBill),
            actualBill: Math.round(actualBill),
            savings: Math.round(currentSavings),
            balance: Math.round(cumulative)
        });
    }

    return {
        labels,
        dataPoints,
        historicalCount,
        paybackYear: paybackYearFraction,
        breakEvenCalendarYear,
        tableRows
    };
}

// Chart 1 - Cumulative Payback S-Curve
function renderPaybackSCurveChart(projection) {
    const canvas = document.getElementById('chart-payback-scurve');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (chartPaybackInstance) {
        chartPaybackInstance.destroy();
    }

    const breakEvenIdx = projection.paybackYear ? Math.ceil(projection.paybackYear) : null;
    const histLimitIdx = projection.historicalCount || 0;

    chartPaybackInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: projection.labels,
            datasets: [{
                label: 'Cumulative Net Balance (SEK)',
                data: projection.dataPoints,
                borderColor: '#10b981',
                segment: {
                    borderDash: (segCtx) => (segCtx.p0DataIndex >= histLimitIdx ? [6, 4] : undefined)
                },
                backgroundColor: (context) => {
                    const chart = context.chart;
                    const { ctx, chartArea } = chart;
                    if (!chartArea) return null;
                    const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                    gradient.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
                    gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');
                    return gradient;
                },
                borderWidth: 3,
                fill: true,
                tension: 0.35,
                pointBackgroundColor: projection.dataPoints.map((v, idx) => {
                    if (idx === breakEvenIdx) return '#34d399';
                    return v >= 0 ? '#10b981' : '#f59e0b';
                }),
                pointBorderColor: projection.dataPoints.map((v, idx) => {
                    if (idx === breakEvenIdx) return '#ffffff';
                    return v >= 0 ? '#10b981' : '#f59e0b';
                }),
                pointRadius: projection.dataPoints.map((v, idx) => (idx === breakEvenIdx ? 7 : 4)),
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#f8fafc',
                    bodyColor: '#cbd5e1',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            return ` Net Cash Flow: ${formatSEK(context.parsed.y)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    grid: {
                        color: (context) => context.tick.value === 0 ? 'rgba(255, 255, 255, 0.35)' : 'rgba(255, 255, 255, 0.05)',
                        lineWidth: (context) => context.tick.value === 0 ? 2 : 1
                    },
                    ticks: {
                        color: '#94a3b8',
                        callback: (value) => `${formatCurrencyNoUnit(value)} kr`
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

// Plugin to augment 3-way baseline comparison columns with hatched pattern showing Skattereduktion portion
const skattereduktionBarPlugin = {
    id: 'skattereduktionBarPlugin',
    afterDatasetsDraw(chart) {
        const { ctx } = chart;

        // Build striped diagonal pattern
        const pCanvas = document.createElement('canvas');
        pCanvas.width = 10;
        pCanvas.height = 10;
        const pCtx = pCanvas.getContext('2d');
        pCtx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
        pCtx.lineWidth = 2.5;
        pCtx.beginPath();
        pCtx.moveTo(0, 10);
        pCtx.lineTo(10, 0);
        pCtx.stroke();
        const stripePattern = ctx.createPattern(pCanvas, 'repeat');

        // Affected columns are dataset 1 (Solar Only) and dataset 2 (Actual System)
        [1, 2].forEach(dsIndex => {
            const meta = chart.getDatasetMeta(dsIndex);
            if (!meta || meta.hidden) return;
            const dataset = chart.data.datasets[dsIndex];
            const skatArray = dataset.skattereduktionData || [];

            meta.data.forEach((bar, idx) => {
                const skatSek = skatArray[idx] || 0;
                if (skatSek <= 0) return; // Abolished in 2026 or 0 export

                const val = dataset.data[idx];
                const left = bar.x - bar.width / 2;
                const width = bar.width;
                const top = Math.min(bar.y, bar.base);
                const bottom = Math.max(bar.y, bar.base);
                const totalHeight = bottom - top;
                if (totalHeight <= 2) return;

                // Proportion of column represented by skattereduktion:
                // For positive cost (val >= 0), gross cost without subsidy is val + skatSek
                // For negative bill (val < 0), skatSek generated the negative credit below zero
                const grossImpact = Math.abs(val) + (val >= 0 ? skatSek : 0);
                const portion = Math.min(1.0, Math.max(0.08, skatSek / (grossImpact || 1)));
                const portionHeight = Math.round(totalHeight * portion);

                ctx.save();
                ctx.beginPath();
                if (ctx.roundRect) {
                    ctx.roundRect(left, top, width, totalHeight, 4);
                } else {
                    ctx.rect(left, top, width, totalHeight);
                }
                ctx.clip();

                ctx.fillStyle = stripePattern;
                if (val >= 0) {
                    // Subsidy reduced net cost from the top
                    ctx.fillRect(left, top, width, portionHeight);
                    // Subtle dashed separation line
                    ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([2, 2]);
                    ctx.beginPath();
                    ctx.moveTo(left, top + portionHeight);
                    ctx.lineTo(left + width, top + portionHeight);
                    ctx.stroke();
                } else {
                    // Subsidy created negative revenue down from 0
                    ctx.fillRect(left, bottom - portionHeight, width, portionHeight);
                    ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([2, 2]);
                    ctx.beginPath();
                    ctx.moveTo(left, bottom - portionHeight);
                    ctx.lineTo(left + width, bottom - portionHeight);
                    ctx.stroke();
                }
                ctx.restore();
            });
        });
    }
};

// Chart 2 - Monthly Breakdown
function renderMonthlyBaselinesChart(months) {
    const canvas = document.getElementById('chart-monthly-baselines');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (chartMonthlyBaselinesInstance) {
        chartMonthlyBaselinesInstance.destroy();
    }

    const labels = months.map(m => {
        const yr = m.year ? `'${String(m.year).substring(2)} ` : '';
        return `${yr}${(m.month || '').substring(0, 3)}`;
    });
    const noSolarData = months.map(m => Math.round(m.baseline_no_solar_sek));
    const solarOnlyData = months.map(m => Math.round(m.baseline_solar_only_sek));
    const actualData = months.map(m => Math.round(m.actual_cost_sek));

    const solarTaxRedData = months.map(m => Math.round(m.solar_only_tax_red_sek || 0));
    const actualTaxRedData = months.map(m => Math.round(m.actual_tax_red_sek || 0));
    const taxRedValidList = months.map(m => !!m.is_tax_red_valid);

    chartMonthlyBaselinesInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'No Solar/Battery (Grey)',
                    data: noSolarData,
                    backgroundColor: '#64748b',
                    borderRadius: 4,
                },
                {
                    label: 'Solar Only (Amber)',
                    data: solarOnlyData,
                    backgroundColor: '#f59e0b',
                    borderRadius: 4,
                    skattereduktionData: solarTaxRedData,
                    isTaxRedValid: taxRedValidList,
                },
                {
                    label: 'Actual System (Teal)',
                    data: actualData,
                    backgroundColor: '#06b6d4',
                    borderRadius: 4,
                    skattereduktionData: actualTaxRedData,
                    isTaxRedValid: taxRedValidList,
                }
            ]
        },
        plugins: [skattereduktionBarPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#94a3b8',
                        font: { family: 'Plus Jakarta Sans', size: 11 },
                        boxWidth: 12
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            const ds = context.dataset;
                            const idx = context.dataIndex;
                            const val = context.parsed.y;
                            const skat = ds.skattereduktionData ? ds.skattereduktionData[idx] : null;
                            const isValid = ds.isTaxRedValid ? ds.isTaxRedValid[idx] : false;

                            let str = ` ${ds.label}: ${formatSEK(val)}`;
                            if (skat !== null && skat !== undefined) {
                                if (isValid && skat > 0) {
                                    const gross = Math.abs(val) + (val >= 0 ? skat : 0);
                                    const pct = gross > 0 ? ((skat / gross) * 100).toFixed(0) : 0;
                                    str += ` (incl. -${formatCurrencyNoUnit(skat)} kr Skatt, ~${pct}% of column)`;
                                } else if (!isValid) {
                                    str += ` (Skattereduktion: 0 kr - Abolished 2026)`;
                                }
                            }
                            return str;
                        }
                    }
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#94a3b8',
                        callback: (v) => `${v} kr`
                    },
                    title: {
                        display: true,
                        text: 'Monthly Net Electricity Cost (SEK)',
                        color: '#94a3b8',
                        font: { size: 11 }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

// Chart 2 - Annual Multi-Year Side-by-Side Comparison
function renderAnnualComparisonChart(annualSummaries) {
    const canvas = document.getElementById('chart-monthly-baselines');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (chartMonthlyBaselinesInstance) {
        chartMonthlyBaselinesInstance.destroy();
    }

    const labels = annualSummaries.map(y => `${y.year} (${y.era.includes('22') ? '22 kWh' : '11 kWh'})`);
    const noSolarData = annualSummaries.map(y => Math.round(y.baseline_no_solar_sek));
    const solarOnlyData = annualSummaries.map(y => Math.round(y.baseline_solar_only_sek));
    const actualData = annualSummaries.map(y => Math.round(y.actual_cost_sek));

    const solarTaxRedData = annualSummaries.map(y => Math.round(y.solar_only_tax_red_sek || 0));
    const actualTaxRedData = annualSummaries.map(y => Math.round(y.actual_tax_red_sek || 0));
    const taxRedValidList = annualSummaries.map(y => !!y.is_tax_red_valid);

    chartMonthlyBaselinesInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'No Solar/Battery (Grey)',
                    data: noSolarData,
                    backgroundColor: '#64748b',
                    borderRadius: 4,
                },
                {
                    label: 'Solar Only (Amber)',
                    data: solarOnlyData,
                    backgroundColor: '#f59e0b',
                    borderRadius: 4,
                    skattereduktionData: solarTaxRedData,
                    isTaxRedValid: taxRedValidList,
                },
                {
                    label: 'Actual System (Teal)',
                    data: actualData,
                    backgroundColor: '#06b6d4',
                    borderRadius: 4,
                    skattereduktionData: actualTaxRedData,
                    isTaxRedValid: taxRedValidList,
                }
            ]
        },
        plugins: [skattereduktionBarPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#94a3b8',
                        font: { family: 'Plus Jakarta Sans', size: 11 },
                        boxWidth: 12
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            const ds = context.dataset;
                            const idx = context.dataIndex;
                            const val = context.parsed.y;
                            const skat = ds.skattereduktionData ? ds.skattereduktionData[idx] : null;
                            const isValid = ds.isTaxRedValid ? ds.isTaxRedValid[idx] : false;

                            let str = ` ${ds.label}: ${formatSEK(val)}`;
                            if (skat !== null && skat !== undefined) {
                                if (isValid && skat > 0) {
                                    const gross = Math.abs(val) + (val >= 0 ? skat : 0);
                                    const pct = gross > 0 ? ((skat / gross) * 100).toFixed(0) : 0;
                                    str += ` (incl. -${formatCurrencyNoUnit(skat)} SEK Skattereduktion, ~${pct}% of column)`;
                                } else if (!isValid) {
                                    str += ` (Skattereduktion: 0 SEK - Abolished 2026)`;
                                }
                            }
                            return str;
                        }
                    }
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#94a3b8',
                        callback: (v) => `${v} kr`
                    },
                    title: {
                        display: true,
                        text: 'Annual Total Electricity Cost (SEK)',
                        color: '#94a3b8',
                        font: { size: 11 }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

// Chart 3 - 24h Hourly Dispatch & Price Overlay
function updateHourlyDispatchChart() {
    const canvas = document.getElementById('chart-hourly-dispatch');
    if (!canvas || !dashboardData?.high_res_30d?.hourly_data) return;
    const ctx = canvas.getContext('2d');

    const selectedDate = dispatchDaySelect.value;
    const dayRecords = dashboardData.high_res_30d.hourly_data.filter(h => h.date === selectedDate);
    if (!dayRecords.length) return;

    if (dispatchChartSubtitle) {
        const dayInfo = dashboardData.high_res_30d.days_list.find(d => d.date === selectedDate);
        dispatchChartSubtitle.innerText = `Showing: ${dayInfo ? dayInfo.display_name : selectedDate} (PV: ${dayInfo?.total_produced_kwh || 0} kWh, Avg Spot: ${dayInfo?.avg_spot_price_ore || 0} öre)`;
    }

    if (chartHourlyDispatchInstance) {
        chartHourlyDispatchInstance.destroy();
    }

    const labels = dayRecords.map(h => `${String(h.hour).padStart(2, '0')}:00`);
    const pvPower = dayRecords.map(h => h.pv_power_kw ?? h.produced_kw ?? 0);
    const loadPower = dayRecords.map(h => h.load_power_kw ?? h.consumed_kw ?? 0);
    const battPower = dayRecords.map(h => h.battery_power_kw ?? ((h.battery_discharged_kw || 0) - (h.battery_charged_kw || 0)));
    const socData = dayRecords.map(h => h.soc_pct ?? h.battery_soc_pct ?? 0);
    const priceData = dayRecords.map(h => h.spot_price_ore);

    chartHourlyDispatchInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Solar PV (kW)',
                    data: pvPower,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    yAxisID: 'yPower'
                },
                {
                    label: 'Household Load (kW)',
                    data: loadPower,
                    borderColor: '#ef4444',
                    borderWidth: 2,
                    borderDash: [4, 4],
                    fill: false,
                    tension: 0.2,
                    yAxisID: 'yPower'
                },
                {
                    label: 'Battery Dispatch (kW)',
                    data: battPower,
                    borderColor: '#8b5cf6',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.2,
                    yAxisID: 'yPower'
                },
                {
                    label: 'Battery SoC (%)',
                    data: socData,
                    borderColor: '#10b981',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.2,
                    yAxisID: 'ySoc'
                },
                {
                    label: 'Spot Price (öre/kWh)',
                    data: priceData,
                    borderColor: '#06b6d4',
                    borderWidth: 1.5,
                    borderDash: [2, 2],
                    fill: false,
                    tension: 0.2,
                    yAxisID: 'yPrice'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#94a3b8',
                        font: { family: 'Plus Jakarta Sans', size: 10 },
                        boxWidth: 10
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            const unit = context.dataset.label.includes('Spot') ? 'öre/kWh' : 
                                         context.dataset.label.includes('SoC') ? '%' : 'kW';
                            return ` ${context.dataset.label}: ${context.parsed.y.toFixed(2)} ${unit}`;
                        }
                    }
                }
            },
            scales: {
                yPower: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' },
                    title: {
                        display: true,
                        text: 'Power (kW)',
                        color: '#f59e0b',
                        font: { size: 10 }
                    }
                },
                ySoc: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    min: 0,
                    max: 100,
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#10b981', callback: (v) => `${v}%` },
                    title: {
                        display: true,
                        text: 'SoC (%)',
                        color: '#10b981',
                        font: { size: 10 }
                    }
                },
                yPrice: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#06b6d4', callback: (v) => `${v} ö` },
                    title: {
                        display: true,
                        text: 'Spot Price (öre)',
                        color: '#06b6d4',
                        font: { size: 10 }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

// Populate Monthly Ledger Table
function renderMonthlyLedgerTable(months) {
    if (!ledger2025Body) return;
    
    let html = '';
    months.forEach(m => {
        const battClass = m.battery_savings_sek >= 0 ? 'text-savings' : 'text-loss';
        const displayMonth = m.year ? `${m.month} ${m.year}` : m.month;
        html += `
            <tr>
                <td>${displayMonth}</td>
                <td class="text-solar">${m.produced_kwh.toFixed(1)}</td>
                <td>${m.consumed_kwh.toFixed(1)}</td>
                <td>${m.imported_kwh.toFixed(1)}</td>
                <td>${m.exported_kwh.toFixed(1)}</td>
                <td>${(m.avg_spot_price_ore_kwh || m.avg_spot_price_ore || 0).toFixed(1)} öre</td>
                <td>${formatSEK(m.baseline_no_solar_sek)}</td>
                <td>${formatSEK(m.baseline_solar_only_sek)}</td>
                <td>${formatSEK(m.actual_cost_sek)}</td>
                <td class="text-solar">${formatSEK(m.solar_savings_sek)}</td>
                <td class="${battClass}">${formatSEK(m.battery_savings_sek)}</td>
                <td class="text-savings">${formatSEK(m.total_savings_sek)}</td>
            </tr>
        `;
    });
    ledger2025Body.innerHTML = html;
}

// Populate Multi-Year Annual Comparison Table
function renderMultiYearSummaryTable(annualSummaries) {
    if (!ledgerMultiyearBody) return;

    let html = '';
    annualSummaries.forEach(y => {
        let eraBadge = `<span class="era-tag era-batt2">${y.era}</span>`;
        if (y.year === 2023) eraBadge = `<span class="era-tag era-batt1">${y.era}</span>`;
        else if (y.year === 2024) eraBadge = `<span class="era-tag era-solar">${y.era}</span>`;

        html += `
            <tr>
                <td><strong>Year ${y.year}</strong></td>
                <td>${eraBadge}</td>
                <td>${y.days} days</td>
                <td class="text-solar">${Math.round(y.produced_kwh).toLocaleString()}</td>
                <td>${Math.round(y.consumed_kwh).toLocaleString()}</td>
                <td>${Math.round(y.imported_kwh).toLocaleString()}</td>
                <td>${Math.round(y.exported_kwh).toLocaleString()}</td>
                <td class="text-battery">${Math.round(y.battery_discharged_kwh).toLocaleString()}</td>
                <td>${formatSEK(y.baseline_no_solar_sek)}</td>
                <td>${formatSEK(y.baseline_solar_only_sek)}</td>
                <td>${formatSEK(y.actual_cost_sek)}</td>
                <td class="text-savings">${formatSEK(y.total_savings_sek)}</td>
            </tr>
        `;
    });
    ledgerMultiyearBody.innerHTML = html;
}

// Populate 25-Year Projection Ledger Table
function render25YearLedgerTable(rows) {
    if (!ledger25yBody) return;
    
    let html = '';
    rows.forEach(r => {
        const balClass = r.balance >= 0 ? 'text-savings' : 'text-loss';
        html += `
            <tr>
                <td>${r.year}</td>
                <td>${r.solarGen.toLocaleString()}</td>
                <td>${r.selfConsumed.toLocaleString()}</td>
                <td>${r.exported.toLocaleString()}</td>
                <td>${r.imported.toLocaleString()}</td>
                <td>${formatSEK(r.noSolarBill)}</td>
                <td>${formatSEK(r.actualBill)}</td>
                <td class="text-savings">${formatSEK(r.savings)}</td>
                <td class="${balClass}">${formatSEK(r.balance)}</td>
            </tr>
        `;
    });
    ledger25yBody.innerHTML = html;
}

// Populate High-Res Variance Benchmark Table
function populateVarianceTable() {
    if (!ledgerVarianceBody || !dashboardData?.high_res_30d?.variance_benchmarks?.daily_averaged?.metrics) return;
    
    const dailyMetrics = dashboardData.high_res_30d.variance_benchmarks.daily_averaged.metrics;
    const synthMetrics = dashboardData.high_res_30d.variance_benchmarks.synthetic_weighted?.metrics || [];
    let html = '';
    dailyMetrics.forEach((m, idx) => {
        const s = synthMetrics[idx];
        const deltaClass = m.delta_sek >= 0 ? 'text-solar' : 'text-battery';
        const sDeltaClass = s && s.delta_sek >= 0 ? 'text-solar' : 'text-battery';
        const synthEstStr = s ? formatSEK(s.estimated_sek) : '&mdash;';
        const synthErrStr = s
            ? `${s.delta_sek >= 0 ? '+' : ''}${s.delta_sek.toFixed(2)} SEK (${s.percentage_error >= 0 ? '+' : ''}${s.percentage_error.toFixed(2)}%)`
            : '&mdash;';
        html += `
            <tr>
                <td><strong>${m.metric}</strong></td>
                <td>${formatSEK(m.exact_sek)}</td>
                <td>${formatSEK(m.estimated_sek)}</td>
                <td class="${deltaClass}">${m.delta_sek >= 0 ? '+' : ''}${m.delta_sek.toFixed(2)} SEK (${m.percentage_error >= 0 ? '+' : ''}${m.percentage_error.toFixed(2)}%)</td>
                <td>${synthEstStr}</td>
                <td class="${sDeltaClass}">${synthErrStr}</td>
            </tr>
        `;
    });
    ledgerVarianceBody.innerHTML = html;
}

// Populate Utility Tariff & Invoicing Audit Table
function populateUtilityAuditTable() {
    if (!ledgerUtilityAuditBody || !dashboardData?.utility_tariff_audit?.monthly_records) return;

    const audit = dashboardData.utility_tariff_audit;
    const records = audit.monthly_records.filter(r => r.is_billed);
    let html = '';

    records.forEach(r => {
        const isPureGrid = r.billing_regime === 'pure_grid_tibber';
        const regimeBadge = isPureGrid
            ? '<span class="era-tag era-batt2">Pure EEM Grid + Tibber</span>'
            : '<span class="era-tag era-solar">EEM Combined Retail+Grid</span>';
        const retailStr = isPureGrid ? '&mdash;' : formatSEK(r.inferred_eem_retail_supply_kr);
        const matchStr = isPureGrid
            ? `<span class="text-savings">&#10003; Exact (${r.invoice_residual_kr >= 0 ? '+' : ''}${r.invoice_residual_kr.toFixed(2)} kr)</span>`
            : `<span class="text-solar">Pre-Switch (${r.year}-09-28)</span>`;

        html += `
            <tr>
                <td><strong>${r.month_name.substring(0, 3)} ${r.year}</strong></td>
                <td>${regimeBadge}</td>
                <td>${r.eem_billed_kwh.toFixed(1)}</td>
                <td>${r.sonnen_imported_kwh.toFixed(1)} (${r.kwh_delta_pct.toFixed(1)}%)</td>
                <td><strong>${formatSEK(r.eem_billed_kr)}</strong></td>
                <td>${r.audited_grid_fixed_kr.toFixed(2)} SEK</td>
                <td>${r.audited_grid_variable_kr.toFixed(2)} SEK</td>
                <td>${r.audited_grid_total_kr.toFixed(2)} SEK</td>
                <td>${retailStr}</td>
                <td>${matchStr}</td>
            </tr>
        `;
    });

    ledgerUtilityAuditBody.innerHTML = html;
}

// Milestone 6: Populate Next-Day Forecast & Shadow Mode Recommendation Engine Tab
function populateShadowAdvisorTab() {
    if (!dashboardData?.next_day_forecast) return;
    const ndf = dashboardData.next_day_forecast;

    if (shadowScenarioSelect) {
        shadowScenarioSelect.innerHTML = '';

        // 1. Tomorrow Forecast Scenarios (2026-11-15)
        const optGroupTomorrow = document.createElement('optgroup');
        optGroupTomorrow.label = `Tomorrow Forecast Scenarios (${ndf.target_display_date || ndf.target_date})`;
        Object.values(ndf.scenarios || {}).forEach(scen => {
            const opt = document.createElement('option');
            opt.value = `scen:${scen.id}`;
            opt.innerText = scen.label;
            optGroupTomorrow.appendChild(opt);
        });
        shadowScenarioSelect.appendChild(optGroupTomorrow);

        // 2. Top Backtest Arbitrage Days (from 121-day high-res backtest)
        const bt = ndf.backtest_121d;
        if (bt?.featured_backtest_hourly) {
            const optGroupBt = document.createElement('optgroup');
            optGroupBt.label = 'Historical Backtest Days (2026 High-Res Arbitrage Audit)';
            const featuredDates = Object.keys(bt.featured_backtest_hourly).sort().reverse();
            featuredDates.forEach(dStr => {
                const dayRec = (bt.daily_records || []).find(r => r.date === dStr);
                const upside = dayRec ? dayRec.oracle_upside_vs_default_sek : 0;
                const maxOre = dayRec ? dayRec.max_spot_ore_kwh : 0;
                const opt = document.createElement('option');
                opt.value = `bt:${dStr}`;
                opt.innerText = `${dStr} — Saved +${upside.toFixed(2)} SEK (Peak ${maxOre.toFixed(1)} öre/kWh, ${dayRec?.primary_strategy || 'Audit'})`;
                optGroupBt.appendChild(opt);
            });
            shadowScenarioSelect.appendChild(optGroupBt);
        }

        shadowScenarioSelect.value = `scen:${ndf.default_scenario_id || 'baseline_forecast'}`;
    }

    renderShadowBacktestTable(ndf.backtest_121d);
    updateShadowAdvisorView();
}

function updateShadowAdvisorView() {
    if (!dashboardData?.next_day_forecast) return;
    const ndf = dashboardData.next_day_forecast;
    const bt = ndf.backtest_121d || {};
    const selVal = shadowScenarioSelect ? shadowScenarioSelect.value : 'scen:baseline_forecast';

    let advisorResult = null;
    let viewLabel = '';

    if (selVal.startsWith('scen:')) {
        const scenId = selVal.replace('scen:', '');
        const scenObj = ndf.scenarios?.[scenId] || Object.values(ndf.scenarios || {})[0];
        if (scenObj) {
            advisorResult = scenObj.advisor_result;
            viewLabel = scenObj.label;
        }
    } else if (selVal.startsWith('bt:')) {
        const dStr = selVal.replace('bt:', '');
        advisorResult = bt.featured_backtest_hourly?.[dStr];
        viewLabel = `Backtest Day ${dStr} (Realized High-Res PV & Load vs Shadow Dispatch)`;
    }

    if (!advisorResult) return;

    const diag = advisorResult.arbitrage_diagnostics || {};
    const scens = advisorResult.scenarios || {};
    const shdScen = scens.shadow_optimized || {};
    const defScen = scens.default_self_consumption || {};

    // Update Banner & Gate Badge
    const gateBadge = document.getElementById('shadow-gate-badge');
    const headlineEl = document.getElementById('shadow-headline-text');
    if (gateBadge) {
        if (diag.efficiency_gate_passed) {
            gateBadge.className = 'badge badge-success';
            gateBadge.innerHTML = `<i class="fa-solid fa-bolt"></i> GATE PASSED: PRE-CHARGE ${diag.recommended_grid_precharge_kwh.toFixed(1)} kWh`;
        } else if (diag.hold_hours_count > 0 && diag.shadow_savings_vs_default_sek > 0.15) {
            gateBadge.className = 'badge badge-accent';
            gateBadge.innerHTML = `<i class="fa-solid fa-shield-halved"></i> SMART PEAK HOLD (${diag.hold_hours_count}h)`;
        } else {
            gateBadge.className = 'badge badge-muted';
            gateBadge.innerHTML = `<i class="fa-solid fa-solar-panel"></i> STANDARD SELF-CONSUMPTION`;
        }
    }
    if (headlineEl) {
        headlineEl.innerText = diag.headline_recommendation || '';
    }

    // Update 4 Mini KPI Cards
    const valDayBill = document.getElementById('shadow-val-day-bill');
    const subDayBill = document.getElementById('shadow-sub-day-bill');
    const valGateSpread = document.getElementById('shadow-val-gate-spread');
    const subGateBe = document.getElementById('shadow-sub-gate-breakeven');
    const val121Upside = document.getElementById('shadow-val-121d-upside');
    const sub121Upside = document.getElementById('shadow-sub-121d-upside');
    const val121Mae = document.getElementById('shadow-val-121d-mae');
    const sub121Mae = document.getElementById('shadow-sub-121d-mae');

    if (valDayBill) valDayBill.innerText = `${(shdScen.net_cost_sek ?? 0).toFixed(2)} SEK`;
    if (subDayBill) {
        const delta = diag.shadow_savings_vs_default_sek ?? 0;
        subDayBill.innerText = `Saves +${delta.toFixed(2)} SEK vs Default SC (${(defScen.net_cost_sek ?? 0).toFixed(2)} SEK)`;
    }
    if (valGateSpread) {
        valGateSpread.innerHTML = `${(diag.avg_trough_spot_ore_kwh ?? 0).toFixed(1)} &rarr; ${(diag.max_peak_spot_ore_kwh ?? 0).toFixed(1)} öre`;
    }
    if (subGateBe) {
        subGateBe.innerText = `Break-Even Peak Spot: ${(diag.breakeven_peak_spot_ore_kwh ?? 0).toFixed(1)} öre/kWh (η=${(diag.roundtrip_efficiency_pct ?? 76.8).toFixed(1)}%)`;
    }
    if (bt.financial_totals_sek) {
        const ft = bt.financial_totals_sek;
        if (val121Upside) val121Upside.innerText = `+${(ft.oracle_upside_vs_default_sek ?? 0).toFixed(2)} SEK`;
        if (sub121Upside) {
            sub121Upside.innerText = `+${(ft.predictive_upside_vs_default_sek ?? 0).toFixed(2)} SEK Out-of-Sample | +${(ft.oracle_upside_vs_actual_sonnen_sek ?? 0).toFixed(2)} SEK vs Raw CT`;
        }
    }
    if (bt.forecast_accuracy && bt.strategy_trigger_summary) {
        const fa = bt.forecast_accuracy;
        const st = bt.strategy_trigger_summary;
        if (val121Mae) val121Mae.innerText = `${(fa.bill_mae_sek ?? 0).toFixed(2)} SEK/day`;
        if (sub121Mae) {
            sub121Mae.innerText = `PV MAE: ${fa.pv_mae_kwh} kWh | Load MAE: ${fa.load_mae_kwh} kWh (${st.grid_precharge_days_count} Pre-Charge Days)`;
        }
    }

    renderShadowForecastChart(advisorResult, viewLabel);
    renderShadowHourlyTable(advisorResult.hourly_steps || []);
}

function renderShadowForecastChart(advisorResult, viewLabel) {
    const canvas = document.getElementById('chart-shadow-forecast');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const subtitleEl = document.getElementById('shadow-chart-subtitle');
    if (subtitleEl) {
        subtitleEl.innerText = `${viewLabel} — Comparing Shadow SoC (%), Default SoC (%), Spot Price (öre), and η=76.8% Break-Even Threshold`;
    }

    if (chartShadowForecastInstance) {
        chartShadowForecastInstance.destroy();
    }

    const steps = advisorResult.hourly_steps || [];
    const diag = advisorResult.arbitrage_diagnostics || {};
    const labels = steps.map(s => `${String(s.hour).padStart(2, '0')}:00`);
    const shadowSoc = steps.map(s => s.shadow_soc_pct);
    const defaultSoc = steps.map(s => s.default_soc_pct);
    const spotOre = steps.map(s => s.spot_price_ore_kwh);
    const breakevenLine = steps.map(() => diag.breakeven_peak_spot_ore_kwh || 0);
    const shadowNetBattKw = steps.map(s => Number((s.shadow_discharged_kwh - s.shadow_total_charged_kwh).toFixed(2)));

    chartShadowForecastInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Shadow Advisor SoC (%)',
                    data: shadowSoc,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.14)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.25,
                    yAxisID: 'ySoc'
                },
                {
                    label: 'Default Self-Consumption SoC (%)',
                    data: defaultSoc,
                    borderColor: '#94a3b8',
                    borderWidth: 2,
                    borderDash: [5, 4],
                    fill: false,
                    tension: 0.25,
                    yAxisID: 'ySoc'
                },
                {
                    label: 'Day-Ahead Spot Price (öre/kWh)',
                    data: spotOre,
                    borderColor: '#06b6d4',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.2,
                    yAxisID: 'yPrice'
                },
                {
                    label: 'Efficiency Gate Break-Even (öre/kWh)',
                    data: breakevenLine,
                    borderColor: '#f59e0b',
                    borderWidth: 1.5,
                    borderDash: [3, 3],
                    pointRadius: 0,
                    fill: false,
                    yAxisID: 'yPrice'
                },
                {
                    type: 'bar',
                    label: 'Shadow Battery Power (+Dis / -Chg kW)',
                    data: shadowNetBattKw,
                    backgroundColor: shadowNetBattKw.map(v => v < 0 ? 'rgba(6, 182, 212, 0.35)' : 'rgba(168, 85, 247, 0.4)'),
                    borderColor: shadowNetBattKw.map(v => v < 0 ? '#06b6d4' : '#a855f7'),
                    borderWidth: 1,
                    borderRadius: 3,
                    yAxisID: 'yPower'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 10 }, boxWidth: 10 }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.94)',
                    padding: 10
                }
            },
            scales: {
                ySoc: {
                    type: 'linear',
                    position: 'left',
                    min: 0,
                    max: 100,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#10b981', callback: v => `${v}%` },
                    title: { display: true, text: 'Battery SoC (%)', color: '#10b981', font: { size: 10 } }
                },
                yPrice: {
                    type: 'linear',
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#06b6d4', callback: v => `${v} ö` },
                    title: { display: true, text: 'Spot Price (öre/kWh)', color: '#06b6d4', font: { size: 10 } }
                },
                yPower: {
                    type: 'linear',
                    position: 'right',
                    display: false,
                    min: -7,
                    max: 7
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

function renderShadowHourlyTable(steps) {
    if (!ledgerShadowHourlyBody) return;
    let html = '';

    steps.forEach(s => {
        let actionBadge = '<span class="era-tag" style="background:rgba(148,163,184,0.12);color:#94a3b8;">IDLE</span>';
        if (s.shadow_action === 'GRID_PRECHARGE') {
            actionBadge = '<span class="era-tag era-batt1">GRID PRE-CHARGE</span>';
        } else if (s.shadow_action === 'SOLAR_CHARGE') {
            actionBadge = '<span class="era-tag era-solar">SOLAR CHARGE</span>';
        } else if (s.shadow_action === 'HOLD_FOR_PEAK') {
            actionBadge = '<span class="era-tag" style="background:rgba(245,158,11,0.18);color:#fbbf24;">HOLD FOR PEAK</span>';
        } else if (s.shadow_action === 'PEAK_DISCHARGE') {
            actionBadge = '<span class="era-tag era-batt2">PEAK DISCHARGE</span>';
        } else if (s.shadow_action === 'SELF_CONSUMPTION') {
            actionBadge = '<span class="era-tag era-batt2">SELF-CONSUME</span>';
        }

        const chgDisStr = s.shadow_total_charged_kwh > 0.02
            ? `+${s.shadow_total_charged_kwh.toFixed(2)} chg`
            : (s.shadow_discharged_kwh > 0.02 ? `-${s.shadow_discharged_kwh.toFixed(2)} dis` : '0.00');
        const deltaClass = s.hourly_savings_delta_sek > 0.01 ? 'text-savings' : (s.hourly_savings_delta_sek < -0.01 ? 'text-solar' : '');
        const deltaStr = `${s.hourly_savings_delta_sek >= 0 ? '+' : ''}${s.hourly_savings_delta_sek.toFixed(2)} kr`;

        html += `
            <tr>
                <td><strong>${String(s.hour).padStart(2, '0')}:00</strong></td>
                <td>${s.spot_price_ore_kwh.toFixed(1)} öre</td>
                <td>${s.import_price_sek_kwh.toFixed(2)} kr</td>
                <td><span class="text-solar">${s.pv_kwh.toFixed(2)}</span> / ${s.load_kwh.toFixed(2)}</td>
                <td>${s.default_soc_pct.toFixed(0)}%</td>
                <td>${actionBadge}</td>
                <td>${chgDisStr}</td>
                <td class="text-battery">${s.shadow_soc_pct.toFixed(0)}% (${s.shadow_soc_kwh.toFixed(1)} kWh)</td>
                <td class="${deltaClass}">${deltaStr}</td>
                <td style="font-family:var(--font-body);font-size:0.75rem;color:var(--text-secondary);">${s.shadow_reason}</td>
            </tr>
        `;
    });

    ledgerShadowHourlyBody.innerHTML = html;
}

function renderShadowBacktestTable(backtest) {
    if (!ledgerShadowBacktestBody || !backtest?.daily_records) return;

    // Sort by date descending so November volatility days appear at the top, or show all 121 days
    const records = [...backtest.daily_records].sort((a, b) => {
        if (b.oracle_upside_vs_default_sek !== a.oracle_upside_vs_default_sek) {
            return b.oracle_upside_vs_default_sek - a.oracle_upside_vs_default_sek;
        }
        return b.date.localeCompare(a.date);
    });

    let html = '';
    records.forEach(r => {
        let stratBadge = '<span class="era-tag" style="background:rgba(148,163,184,0.12);color:#94a3b8;">Standard SC</span>';
        if (r.primary_strategy.includes('Pre-Charge')) {
            stratBadge = '<span class="era-tag era-batt1">Grid Pre-Charge</span>';
        } else if (r.primary_strategy.includes('Hold')) {
            stratBadge = '<span class="era-tag era-solar">Peak Hold</span>';
        }

        const hasFeatured = backtest.featured_backtest_hourly && backtest.featured_backtest_hourly[r.date];
        const rowCursor = hasFeatured ? 'cursor:pointer;' : '';
        const rowTitle = hasFeatured ? 'Click to inspect this day in the 24h Shadow Trajectory Chart above' : r.headline_advice;

        html += `
            <tr style="${rowCursor}" title="${rowTitle}" data-bt-date="${hasFeatured ? r.date : ''}">
                <td><strong>${r.display_name}</strong></td>
                <td><span class="text-solar">${r.predicted_pv_kwh.toFixed(1)}</span> / ${r.actual_pv_kwh.toFixed(1)} kWh</td>
                <td>${r.predicted_load_kwh.toFixed(1)} / ${r.actual_load_kwh.toFixed(1)} kWh</td>
                <td>${r.min_spot_ore_kwh.toFixed(0)}–<strong>${r.max_spot_ore_kwh.toFixed(0)}</strong> öre</td>
                <td>${r.breakeven_peak_spot_ore_kwh.toFixed(0)} öre</td>
                <td>${r.recommended_grid_precharge_kwh > 0 ? `${r.recommended_grid_precharge_kwh.toFixed(1)} kWh` : '&mdash;'}</td>
                <td>${stratBadge}</td>
                <td>${r.actual_sonnen_cost_sek.toFixed(2)} kr</td>
                <td>${r.default_sc_cost_sek.toFixed(2)} kr</td>
                <td>${r.predictive_shadow_cost_sek.toFixed(2)} kr</td>
                <td>${r.oracle_shadow_cost_sek.toFixed(2)} kr</td>
                <td class="text-savings">+${r.oracle_upside_vs_default_sek.toFixed(2)} SEK</td>
            </tr>
        `;
    });

    ledgerShadowBacktestBody.innerHTML = html;

    ledgerShadowBacktestBody.querySelectorAll('tr[data-bt-date]').forEach(tr => {
        const dt = tr.getAttribute('data-bt-date');
        if (dt && shadowScenarioSelect) {
            tr.addEventListener('click', () => {
                shadowScenarioSelect.value = `bt:${dt}`;
                updateShadowAdvisorView();
            });
        }
    });
}

// Milestone 7: Home Assistant Custom Sensor Integration & Live Shadow Telemetry Bridge
function populateHomeAssistantBridgeTab() {
    const haPkg = dashboardData?.ha_integration;
    if (!haPkg) return;

    const simUnlocked = haSafetySimToggle && haSafetySimToggle.value === 'unlocked';
    const gateBadge = document.getElementById('ha-safety-gate-badge');
    if (gateBadge) {
        if (simUnlocked) {
            gateBadge.className = 'badge badge-success';
            gateBadge.innerHTML = '<i class="fa-solid fa-shield-check"></i> PREVIEW: DUAL SAFETY GATE UNLOCKED';
        } else {
            gateBadge.className = 'badge badge-accent';
            gateBadge.innerHTML = '<i class="fa-solid fa-shield-halved"></i> SAFETY GATE: LOCKED (SHADOW MODE ONLY)';
        }
    }

    const entities = haPkg.entities || [];
    const commands = haPkg.sonnen_command_previews || [];
    const hw = haPkg.hardware_telemetry || {};

    const valCount = document.getElementById('ha-val-entities-count');
    const subEndpoint = document.getElementById('ha-sub-endpoint');
    const valSonnenMode = document.getElementById('ha-val-sonnen-mode');
    const subSonnenEndpoint = document.getElementById('ha-sub-sonnen-endpoint');

    if (valCount) valCount.innerText = `${entities.length} Entities`;
    if (subEndpoint && hw.home_assistant) {
        subEndpoint.innerText = `POST ${hw.home_assistant.rest_api_endpoint}`;
    }
    if (valSonnenMode && hw.sonnen_batterie_10) {
        valSonnenMode.innerText = `Mode ${hw.sonnen_batterie_10.em_operating_mode} (Auto SC)`;
    }
    if (subSonnenEndpoint && hw.sonnen_batterie_10) {
        subSonnenEndpoint.innerText = `${hw.sonnen_batterie_10.url}${hw.sonnen_batterie_10.endpoint} (USOC: ${hw.sonnen_batterie_10.usoc_pct}%)`;
    }

    if (ledgerHaEntitiesBody) {
        let entHtml = '';
        entities.forEach(e => {
            const stateVal = (e.entity_id === 'input_boolean.mysunshine_active_battery_control' && simUnlocked)
                ? 'on'
                : e.state;
            const unitStr = e.unit_of_measurement || '—';
            const clsParts = [];
            if (e.device_class) clsParts.push(e.device_class);
            if (e.state_class) clsParts.push(e.state_class);
            const clsStr = clsParts.length ? clsParts.join(' / ') : 'state';

            const attrPreview = Object.entries(e.attributes || {})
                .filter(([k]) => !['friendly_name', 'icon', 'integration', 'unit_of_measurement', 'device_class', 'state_class', 'hourly_schedule_24h'].includes(k))
                .slice(0, 4)
                .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
                .join(' | ');

            entHtml += `
                <tr>
                    <td><strong class="text-battery">${e.entity_id}</strong></td>
                    <td>${e.friendly_name}</td>
                    <td><strong class="text-savings">${stateVal}</strong></td>
                    <td>${unitStr}</td>
                    <td><span class="era-tag" style="background:rgba(6,182,212,0.14);color:#38bdf8;">${clsStr}</span></td>
                    <td style="font-family:var(--font-body);font-size:0.74rem;color:var(--text-secondary);">${attrPreview}</td>
                </tr>
            `;
        });
        ledgerHaEntitiesBody.innerHTML = entHtml;
    }

    if (ledgerHaCommandsBody) {
        let cmdHtml = '';
        commands.forEach(c => {
            const actuateNow = simUnlocked ? true : c.would_actuate;
            const gateTag = actuateNow
                ? '<span class="era-tag era-batt2">WOULD ACTUATE (ACTIVE)</span>'
                : '<span class="era-tag" style="background:rgba(245,158,11,0.16);color:#fbbf24;">BLOCKED (SHADOW SAFE)</span>';

            cmdHtml += `
                <tr>
                    <td><strong>${String(c.hour).padStart(2, '0')}:00</strong></td>
                    <td><span class="text-solar">${c.shadow_action}</span></td>
                    <td>Mode ${c.target_operating_mode}</td>
                    <td>${c.target_power_watts} W</td>
                    <td><code>${c.http_method} ${c.endpoint.replace('http://192.168.3.125', '')}</code></td>
                    <td><code>${JSON.stringify(c.payload)}</code></td>
                    <td>${gateTag}</td>
                </tr>
            `;
        });
        ledgerHaCommandsBody.innerHTML = cmdHtml;
    }

    const cfgEl = document.getElementById('ha-config-yaml-code');
    const autoEl = document.getElementById('ha-automations-yaml-code');
    if (cfgEl) cfgEl.textContent = haPkg.configuration_yaml_snippet || '';
    if (autoEl) autoEl.textContent = haPkg.automations_yaml_snippet || '';
}

// Start application
document.addEventListener('DOMContentLoaded', initApp);
