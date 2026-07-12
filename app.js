// MySunshine Solar & Battery Simulation Logic

// Hourly residential energy usage distribution (weights sum up to 1.0)
const loadWeights = [
    0.02, 0.02, 0.02, 0.02, 0.03, 0.05, 
    0.08, 0.07, 0.05, 0.04, 0.03, 0.03, 
    0.03, 0.03, 0.03, 0.04, 0.06, 0.08, 
    0.10, 0.09, 0.07, 0.05, 0.03, 0.02
];

// Solar production curve based on daylight hours (weights normalized to sum to 1.0)
const solarWeights = Array(24).fill(0);
let solarWeightSum = 0;
for (let h = 6; h < 18; h++) {
    const w = Math.sin(Math.PI * (h - 6) / 12);
    solarWeights[h] = w;
    solarWeightSum += w;
}
for (let h = 6; h < 18; h++) {
    solarWeights[h] /= solarWeightSum;
}

// Chart Instances
let savingsChartInstance = null;
let energyFlowChartInstance = null;

// DOM Elements
const solarCapacityInput = document.getElementById('solar-capacity');
const solarCostInput = document.getElementById('solar-cost');
const sunHoursInput = document.getElementById('sun-hours');
const batteryCapacityInput = document.getElementById('battery-capacity');
const batteryCostInput = document.getElementById('battery-cost');
const dailyUsageInput = document.getElementById('daily-usage');
const gridRateInput = document.getElementById('grid-rate');
const feedInTariffInput = document.getElementById('feed-in-tariff');
const inflationRateInput = document.getElementById('inflation-rate');

// Value Display Elements
const solarCapacityVal = document.getElementById('solar-capacity-val');
const sunHoursVal = document.getElementById('sun-hours-val');
const batteryCapacityVal = document.getElementById('battery-capacity-val');
const dailyUsageVal = document.getElementById('daily-usage-val');
const gridRateVal = document.getElementById('grid-rate-val');
const feedInTariffVal = document.getElementById('feed-in-tariff-val');
const inflationRateVal = document.getElementById('inflation-rate-val');

// KPI Displays
const valPayback = document.getElementById('val-payback');
const valSavings = document.getElementById('val-savings');
const valNetCost = document.getElementById('val-net-cost');
const valCo2 = document.getElementById('val-co2');

// Spec Displays
const specSelfConsumption = document.getElementById('spec-self-consumption');
const specBatteryUtil = document.getElementById('spec-battery-util');
const specGridIndep = document.getElementById('spec-grid-indep');
const specAnnualGen = document.getElementById('spec-annual-gen');
const specAnnualImport = document.getElementById('spec-annual-import');

// Ledger Table Body
const ledgerBody = document.getElementById('ledger-body');

// Helper functions for formatting
function formatCurrency(val) {
    if (val < 0) return `-$${Math.abs(Math.round(val)).toLocaleString()}`;
    return `$${Math.round(val).toLocaleString()}`;
}

function updateDisplays() {
    solarCapacityVal.innerText = `${parseFloat(solarCapacityInput.value).toFixed(1)} kW`;
    sunHoursVal.innerText = `${parseFloat(sunHoursInput.value).toFixed(1)} hrs`;
    batteryCapacityVal.innerText = `${parseFloat(batteryCapacityInput.value).toFixed(1)} kWh`;
    dailyUsageVal.innerText = `${parseFloat(dailyUsageInput.value).toFixed(1)} kWh`;
    gridRateVal.innerText = `$${parseFloat(gridRateInput.value).toFixed(2)} /kWh`;
    feedInTariffVal.innerText = `$${parseFloat(feedInTariffInput.value).toFixed(2)} /kWh`;
    inflationRateVal.innerText = `${parseFloat(inflationRateInput.value).toFixed(1)}%`;
}

// Hourly simulator function
function runHourlySimulation(solarCapacity, sunHours, batteryCapacity, dailyUsage) {
    const dailyGen = solarCapacity * sunHours;
    let soc = 0;
    
    // Steady state: run 3 times so SoC settles
    let dailySelfConsumed = 0;
    let dailyExport = 0;
    let dailyImport = 0;
    let dailyBatteryCharged = 0;
    let dailyBatteryDischarged = 0;
    
    const hourlyData = [];
    
    for (let day = 0; day < 3; day++) {
        dailySelfConsumed = 0;
        dailyExport = 0;
        dailyImport = 0;
        dailyBatteryCharged = 0;
        dailyBatteryDischarged = 0;
        
        for (let h = 0; h < 24; h++) {
            const load = dailyUsage * loadWeights[h];
            const gen = dailyGen * solarWeights[h];
            
            let exp = 0;
            let imp = 0;
            let selfC = 0;
            let charge = 0;
            let discharge = 0;
            
            if (gen > load) {
                const excess = gen - load;
                charge = Math.min(excess, batteryCapacity - soc);
                soc += charge;
                exp = excess - charge;
                selfC = load;
                dailyBatteryCharged += charge;
            } else {
                const deficit = load - gen;
                discharge = Math.min(deficit, soc);
                soc -= discharge;
                imp = deficit - discharge;
                selfC = gen + discharge;
                dailyBatteryDischarged += discharge;
            }
            
            dailySelfConsumed += selfC;
            dailyExport += exp;
            dailyImport += imp;
            
            if (day === 2) {
                hourlyData.push({
                    hour: h,
                    solarGen: gen,
                    load: load,
                    soc: soc,
                    imported: imp,
                    exported: exp
                });
            }
        }
    }
    
    return {
        dailySelfConsumed,
        dailyExport,
        dailyImport,
        dailyGen,
        dailyBatteryCharged,
        dailyBatteryDischarged,
        hourlyData
    };
}

// Main Calculate & Update Logic
function updateSimulation() {
    // Inputs
    const solarCapacity = parseFloat(solarCapacityInput.value);
    const solarCost = parseFloat(solarCostInput.value);
    const sunHours = parseFloat(sunHoursInput.value);
    const batteryCapacity = parseFloat(batteryCapacityInput.value);
    const batteryCost = parseFloat(batteryCostInput.value);
    const dailyUsage = parseFloat(dailyUsageInput.value);
    const gridRate = parseFloat(gridRateInput.value);
    const feedInTariff = parseFloat(feedInTariffInput.value);
    const inflationRate = parseFloat(inflationRateInput.value) / 100;

    const netSystemCost = solarCost + batteryCost;
    valNetCost.innerText = formatCurrency(netSystemCost);

    // Year 1 base simulation for charts & specs
    const simY1 = runHourlySimulation(solarCapacity, sunHours, batteryCapacity, dailyUsage);
    
    // Performance Specs displays
    const selfConsPct = simY1.dailyGen > 0 ? (simY1.dailySelfConsumed / simY1.dailyGen) * 100 : 0;
    specSelfConsumption.innerText = `${selfConsPct.toFixed(1)}%`;
    
    const maxPossBatteryCharge = batteryCapacity * 365;
    const batteryUtilPct = maxPossBatteryCharge > 0 ? (simY1.dailyBatteryCharged * 365 / maxPossBatteryCharge) * 100 : 0;
    specBatteryUtil.innerText = batteryCapacity > 0 ? `${batteryUtilPct.toFixed(1)}%` : '0.0%';
    
    const gridIndepPct = dailyUsage > 0 ? ((dailyUsage - simY1.dailyImport) / dailyUsage) * 100 : 0;
    specGridIndep.innerText = `${gridIndepPct.toFixed(1)}%`;
    
    specAnnualGen.innerText = `${Math.round(simY1.dailyGen * 365).toLocaleString()} kWh`;
    specAnnualImport.innerText = `${Math.round(simY1.dailyImport * 365).toLocaleString()} kWh`;

    // Carbon reduction: 0.4 kg CO2 per kWh saved (self-consumed or exported)
    const annualCo2Saved = (simY1.dailyGen * 365 * 0.0004);
    valCo2.innerText = annualCo2Saved.toFixed(1);
    
    // 25-Year Projection Loop
    let cumulativeSavings = 0;
    let paybackYear = null;
    const chartLabels = ['Year 0'];
    const chartSavingsData = [-netSystemCost];
    
    let tableHtml = '';
    
    for (let y = 1; y <= 25; y++) {
        // Degrade capacities
        const solarDegradation = Math.pow(0.995, y - 1); // 0.5% degradation per year
        const batteryDegradation = Math.pow(0.99, y - 1); // 1.0% degradation per year
        
        const simYear = runHourlySimulation(
            solarCapacity * solarDegradation,
            sunHours,
            batteryCapacity * batteryDegradation,
            dailyUsage
        );
        
        // Rates with inflation
        const inflatedGridRate = gridRate * Math.pow(1 + inflationRate, y);
        const inflatedFeedInTariff = feedInTariff * Math.pow(1 + inflationRate, y);
        
        // Bills
        const annualImportedCost = simYear.dailyImport * 365 * inflatedGridRate;
        const annualExportedRevenue = simYear.dailyExport * 365 * inflatedFeedInTariff;
        
        const billWithoutSolar = dailyUsage * 365 * inflatedGridRate;
        const billWithSolar = annualImportedCost - annualExportedRevenue;
        
        const annualSavings = billWithoutSolar - billWithSolar;
        cumulativeSavings += annualSavings;
        const netBalance = cumulativeSavings - netSystemCost;
        
        // Find Payback point
        if (paybackYear === null && netBalance >= 0) {
            const prevNetVal = chartSavingsData[chartSavingsData.length - 1]; // negative number
            const fraction = Math.abs(prevNetVal) / (annualSavings);
            paybackYear = (y - 1) + fraction;
        }
        
        chartLabels.push(`Year ${y}`);
        chartSavingsData.push(netBalance);
        
        // Table row builder
        tableHtml += `
            <tr>
                <td>Year ${y}</td>
                <td>${Math.round(simYear.dailyGen * 365).toLocaleString()}</td>
                <td>${Math.round(simYear.dailySelfConsumed * 365).toLocaleString()}</td>
                <td>${Math.round(simYear.dailyExport * 365).toLocaleString()}</td>
                <td>${Math.round(simYear.dailyImport * 365).toLocaleString()}</td>
                <td>${formatCurrency(billWithoutSolar)}</td>
                <td>${formatCurrency(billWithSolar)}</td>
                <td class="text-savings">${formatCurrency(annualSavings)}</td>
                <td class="${netBalance >= 0 ? 'text-savings' : 'text-loss'}">${formatCurrency(netBalance)}</td>
            </tr>
        `;
    }
    
    // Update Ledger
    ledgerBody.innerHTML = tableHtml;
    
    // Update Payback KPI
    if (paybackYear !== null) {
        valPayback.innerText = paybackYear.toFixed(1);
        valPayback.parentElement.classList.remove('text-loss');
    } else {
        valPayback.innerText = '>25';
    }
    
    // Update Savings KPI
    const totalNetProfit = cumulativeSavings - netSystemCost;
    valSavings.innerText = formatCurrency(totalNetProfit);
    if (totalNetProfit >= 0) {
        valSavings.className = 'kpi-value text-savings';
    } else {
        valSavings.className = 'kpi-value text-loss';
    }
    
    // Update Charts
    renderSavingsChart(chartLabels, chartSavingsData);
    renderEnergyFlowChart(simY1.hourlyData);
}

// Render Cumulative Savings Chart
function renderSavingsChart(labels, data) {
    const ctx = document.getElementById('savings-chart').getContext('2d');
    
    if (savingsChartInstance) {
        savingsChartInstance.destroy();
    }
    
    savingsChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Net Project Balance ($)',
                data: data,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.3,
                pointBackgroundColor: data.map(v => v >= 0 ? '#10b981' : '#f59e0b'),
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return ` Net Balance: ${formatCurrency(context.parsed.y)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#94a3b8',
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#94a3b8'
                    }
                }
            }
        }
    });
}

// Render Daily Energy Flow Simulator Chart
function renderEnergyFlowChart(hourlyData) {
    const ctx = document.getElementById('energy-flow-chart').getContext('2d');
    
    if (energyFlowChartInstance) {
        energyFlowChartInstance.destroy();
    }
    
    const labels = hourlyData.map(d => `${d.hour.toString().padStart(2, '0')}:00`);
    const solarGen = hourlyData.map(d => d.solarGen);
    const load = hourlyData.map(d => d.load);
    const soc = hourlyData.map(d => d.soc);

    energyFlowChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Solar Generation (kW)',
                    data: solarGen,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y'
                },
                {
                    label: 'Household Load (kW)',
                    data: load,
                    borderColor: '#06b6d4',
                    backgroundColor: 'transparent',
                    borderWidth: 2.5,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.4,
                    yAxisID: 'y'
                },
                {
                    label: 'Battery SoC (kWh)',
                    data: soc,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.05)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#94a3b8',
                        font: {
                            family: 'Plus Jakarta Sans',
                            size: 11
                        }
                    }
                }
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#94a3b8'
                    },
                    title: {
                        display: true,
                        text: 'Power (kW)',
                        color: '#94a3b8'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: {
                        drawOnChartArea: false
                    },
                    ticks: {
                        color: '#94a3b8'
                    },
                    title: {
                        display: true,
                        text: 'Battery State of Charge (kWh)',
                        color: '#94a3b8'
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#94a3b8'
                    }
                }
            }
        }
    });
}

// Add Event Listeners for Live Calculations
const inputs = [
    solarCapacityInput, solarCostInput, sunHoursInput,
    batteryCapacityInput, batteryCostInput, dailyUsageInput,
    gridRateInput, feedInTariffInput, inflationRateInput
];

inputs.forEach(input => {
    input.addEventListener('input', () => {
        updateDisplays();
        updateSimulation();
    });
});

// Initial Setup
updateDisplays();
updateSimulation();
