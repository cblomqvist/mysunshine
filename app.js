// MySunshine Web Dashboard Application Logic
// Milestone 5: Multi-Year Historical Expansion & Calculation Validation

// Global state and chart instances
let dashboardData = null;
let chartPaybackInstance = null;
let chartMonthlyBaselinesInstance = null;
let chartHourlyDispatchInstance = null;

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
        });
    });
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
function recalculateLedgerMonths(monthlyLedgers, energiskattSek, eemTransferSek, taxRedEnabled, tibberFee) {
    return monthlyLedgers.map(m => {
        const spotSek = (m.avg_spot_price_ore_kwh || m.avg_spot_price_ore || 50.0) / 100.0;
        
        // Import cost per kWh
        const importCostPerKwh = (spotSek + energiskattSek + eemTransferSek) * (1.0 + MOMS_RATE);
        
        // Export revenue per kWh
        const taxRedSek = taxRedEnabled ? 0.60 : 0.0;
        const eemNatnyttaSek = 0.08; // 8 öre/kWh standard grid benefit
        const exportRevPerKwh = spotSek + eemNatnyttaSek + taxRedSek;
        
        // Monthly fixed cost
        const daysInMonth = m.days_count || 30;
        const monthFraction = daysInMonth / 30.4375;
        const fixedCost = (tibberFee + 100.0) * monthFraction;

        // Baseline 1 (No Solar)
        const noSolarCost = (m.consumed_kwh * importCostPerKwh) + fixedCost;

        // Baseline 2 (Solar Only)
        const scPct = (m.solar_only_self_consumption_pct || m.solar_only_sc_pct || 35.0) / 100.0;
        const solarDirectSC = Math.min(m.consumed_kwh, m.produced_kwh * scPct);
        const solarOnlyImport = Math.max(0, m.consumed_kwh - solarDirectSC);
        const solarOnlyExport = Math.max(0, m.produced_kwh - solarDirectSC);
        const solarOnlyCost = (solarOnlyImport * importCostPerKwh) - (solarOnlyExport * exportRevPerKwh) + fixedCost;

        // Actual System (Solar + SonnenBatterie 10)
        const actualImportCost = m.imported_kwh * importCostPerKwh;
        const actualExportRev = m.exported_kwh * exportRevPerKwh;
        const actualCost = actualImportCost - actualExportRev + fixedCost;

        const totalSavings = noSolarCost - actualCost;
        const solarSavings = noSolarCost - solarOnlyCost;
        const batteryMarginal = totalSavings - solarSavings;

        return {
            ...m,
            month: m.month_name || m.month,
            year: m.year || 2025,
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
        const months = yrData.monthly_ledgers || [];
        const recalcedMonths = recalculateLedgerMonths(months, energiskattSek, eemTransferSek, taxRedEnabled, tibberFee);
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
        const daysCount = recalcedMonths.reduce((a, m) => a + (m.days_count || 30), 0);

        let eraName = "Sonnen 22 kWh (Dual)";
        if (yrStr === "2023") eraName = "Sonnen 11 kWh Installed (Sep)";
        else if (yrStr === "2024") eraName = "11 kWh → 22 kWh Expansion (Sep 9)";
        else if (yrStr === "2026") eraName = "Sonnen 22 kWh (No Skattereduktion)";

        annualSummaries.push({
            year: parseInt(yrStr, 10),
            era: eraName,
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
            battery_savings_sek: totBatSav
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

    // 4. 25-Year Projection & Payback (Base on 2025 full year stabilized run-rate)
    const baseMonths2025 = recalculatedYears['2025'] || displayMonths;
    const baseSavings2025 = baseMonths2025.reduce((a, m) => a + m.total_savings_sek, 0);
    const projection25y = calculate25YearProjection(netCapex, baseSavings2025, inflation, baseMonths2025);
    
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
    if (selectedPeriod === 'all') {
        renderAnnualComparisonChart(annualSummaries);
    } else {
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
function calculate25YearProjection(capex, baseYearSavings, inflationRate, monthsData) {
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

    for (let y = 1; y <= 25; y++) {
        const calYear = START_YEAR + (y - 1);
        const solarFactor = Math.pow(0.995, y - 1);
        const inflationFactor = Math.pow(1 + inflationRate, y - 1);

        const currentSolarGen = baseSolarGen * solarFactor;
        const currentSavings = baseYearSavings * solarFactor * inflationFactor;
        const previousNet = cumulative;
        cumulative += currentSavings;

        if (paybackYearFraction === null && cumulative >= 0) {
            const fraction = Math.abs(previousNet) / currentSavings;
            paybackYearFraction = (y - 1) + fraction;
            breakEvenCalendarYear = (START_YEAR + (y - 1) + fraction).toFixed(1);
        }

        let milestoneTag = '';
        if (calYear === 2021) {
            milestoneTag = ' (Solar Installed)';
        } else if (calYear === 2023) {
            milestoneTag = ' (+11 kWh Batt)';
        } else if (calYear === 2024) {
            milestoneTag = ' (+11 kWh Expansion)';
        } else if (calYear === 2025) {
            milestoneTag = ' (Full Year Actual)';
        } else if (calYear > 2025) {
            milestoneTag = ' (Proj)';
        }

        labels.push(`${calYear}`);
        dataPoints.push(Math.round(cumulative));

        tableRows.push({
            year: `${calYear}${milestoneTag}`,
            solarGen: Math.round(currentSolarGen),
            selfConsumed: Math.round(baseConsumed - baseImport),
            exported: Math.round(baseExport * solarFactor),
            imported: Math.round(baseImport),
            noSolarBill: Math.round(monthsData.reduce((a, m) => a + m.baseline_no_solar_sek, 0) * inflationFactor),
            actualBill: Math.round(monthsData.reduce((a, m) => a + m.actual_cost_sek, 0) * inflationFactor),
            savings: Math.round(currentSavings),
            balance: Math.round(cumulative)
        });
    }

    return {
        labels,
        dataPoints,
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

    chartPaybackInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: projection.labels,
            datasets: [{
                label: 'Cumulative Net Balance (SEK)',
                data: projection.dataPoints,
                borderColor: '#10b981',
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
                },
                {
                    label: 'Actual System (Teal)',
                    data: actualData,
                    backgroundColor: '#06b6d4',
                    borderRadius: 4,
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
                        font: { family: 'Plus Jakarta Sans', size: 11 },
                        boxWidth: 12
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            return ` ${context.dataset.label}: ${formatSEK(context.parsed.y)}`;
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
                },
                {
                    label: 'Actual System (Teal)',
                    data: actualData,
                    backgroundColor: '#06b6d4',
                    borderRadius: 4,
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
                        font: { family: 'Plus Jakarta Sans', size: 11 },
                        boxWidth: 12
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            return ` ${context.dataset.label}: ${formatSEK(context.parsed.y)}`;
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
    const pvPower = dayRecords.map(h => h.pv_power_kw);
    const loadPower = dayRecords.map(h => h.load_power_kw);
    const battPower = dayRecords.map(h => h.battery_power_kw);
    const socData = dayRecords.map(h => h.soc_pct);
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

// Populate 30-Day Variance Benchmark Table
function populateVarianceTable() {
    if (!ledgerVarianceBody || !dashboardData?.high_res_30d?.variance_benchmarks?.daily_averaged?.metrics) return;
    
    const metrics = dashboardData.high_res_30d.variance_benchmarks.daily_averaged.metrics;
    let html = '';
    metrics.forEach(m => {
        const deltaClass = m.delta_sek >= 0 ? 'text-solar' : 'text-battery';
        html += `
            <tr>
                <td>${m.metric}</td>
                <td>${formatSEK(m.exact_sek)}</td>
                <td>${formatSEK(m.estimated_sek)}</td>
                <td class="${deltaClass}">${m.delta_sek >= 0 ? '+' : ''}${m.delta_sek.toFixed(2)} SEK</td>
                <td>${m.percentage_error.toFixed(2)}%</td>
            </tr>
        `;
    });
    ledgerVarianceBody.innerHTML = html;
}

// Start application
document.addEventListener('DOMContentLoaded', initApp);
