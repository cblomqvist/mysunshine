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
const btnPresetLatest = document.getElementById('btn-preset-latest');
const btnPresetPeakSolar = document.getElementById('btn-preset-peak-solar');
const btnPresetVolatility = document.getElementById('btn-preset-volatility');
const btnPresetCloudy = document.getElementById('btn-preset-cloudy');
const dispatchChartSubtitle = document.getElementById('dispatch-chart-subtitle');
const dispatchChartHeading = document.getElementById('dispatch-chart-heading');
const dispatchWindowBadge = document.getElementById('dispatch-window-badge');

// Multi-Day Dispatch Explorer & Stepping Controls
const btnDispatchLatest = document.getElementById('btn-dispatch-latest');
const btnStepBackFull = document.getElementById('btn-step-back-full');
const btnStepBackHalf = document.getElementById('btn-step-back-half');
const btnStepFwdHalf = document.getElementById('btn-step-fwd-half');
const btnStepFwdFull = document.getElementById('btn-step-fwd-full');
const lblStepBackFull = document.getElementById('lbl-step-back-full');
const lblStepBackHalf = document.getElementById('lbl-step-back-half');
const lblStepFwdHalf = document.getElementById('lbl-step-fwd-half');
const lblStepFwdFull = document.getElementById('lbl-step-fwd-full');

// Multi-Day Dispatch Window State (defaults to Latest Available 24h)
const dispatchExplorerState = {
    spanHours: 24,
    centerOnTimestamp: false,
    anchorIndex: null, // index into hourly_data representing either Start Timestamp (if centerOnTimestamp=false) or Center Timestamp (if centerOnTimestamp=true)
    endIndex: null     // exclusive index into high_res_30d.hourly_data; null = latest end
};

// Exact Time Span & Center Controls DOM Elements
const inputTsDate = document.getElementById('input-ts-date');
const btnToggleCalendar = document.getElementById('btn-toggle-calendar');
const isoCalendarPopover = document.getElementById('iso-calendar-popover');
const isoCalMonthTitle = document.getElementById('iso-cal-month-title');
const isoCalDaysGrid = document.getElementById('iso-cal-days-grid');
const isoCalBoundsHint = document.getElementById('iso-cal-bounds-hint');
const btnCalPrevMonth = document.getElementById('btn-cal-prev-month');
const btnCalNextMonth = document.getElementById('btn-cal-next-month');
const btnCalJumpLatest = document.getElementById('btn-cal-jump-latest');
const btnCalOk = document.getElementById('btn-cal-ok');
const customTimestampPickerWrapper = document.getElementById('custom-timestamp-picker-wrapper');

const inputTsHour = document.getElementById('input-ts-hour');
const btnTsHourUp = document.getElementById('btn-ts-hour-up');
const btnTsHourDown = document.getElementById('btn-ts-hour-down');
const btnApplyTimestampOk = document.getElementById('btn-apply-timestamp-ok');
const lblAnchorDatetime = document.getElementById('lbl-anchor-datetime');
const btnToggleCenterRange = document.getElementById('btn-toggle-center-range');
const lblCenterRangeMode = document.getElementById('lbl-center-range-mode');
const inputSpanDays = document.getElementById('input-span-days');
const btnSpanDaysUp = document.getElementById('btn-span-days-up');
const btnSpanDaysDown = document.getElementById('btn-span-days-down');
const inputRangeHours = document.getElementById('input-range-hours');
const btnRangeHoursUp = document.getElementById('btn-range-hours-up');
const btnRangeHoursDown = document.getElementById('btn-range-hours-down');
const inViewTimestampsText = document.getElementById('in-view-timestamps-text');
const inViewDurationPill = document.getElementById('in-view-duration-pill');

// Custom Monday-First (ISO-8601) Calendar Popover State
const isoCalendarState = {
    isOpen: false,
    viewYear: 2026,
    viewMonth: 10, // 0-indexed (10 = November)
    pendingDateStr: null,
    availableDatesSet: new Set(),
    minDateStr: '2026-07-16',
    maxDateStr: '2026-11-26'
};

// Dispatch Metric Visibility State (defaults to show all)
const dispatchMetricVisibility = {
    pv: true,
    load: true,
    battery: true,
    soc: true,
    spot: true,
    myPrice: true
};

const btnMetricsAll = document.getElementById('btn-metrics-all');
const btnMetricsPrices = document.getElementById('btn-metrics-prices');
const btnMetricsPower = document.getElementById('btn-metrics-power');

// Dispatch Price Component Toggles State (Taxes, Transfer Fees, Markup & Moms added to Nord Pool Spot when buying electricity — Default: All On)
const dispatchPriceComponents = {
    energiskatt: true,
    transfer: true,
    markup: true,
    moms: true
};

const btnCompAllOn = document.getElementById('btn-comp-all-on');
const btnCompPureSpot = document.getElementById('btn-comp-pure-spot');
const lblCompEnergiskatt = document.getElementById('lbl-comp-energiskatt');
const lblCompTransfer = document.getElementById('lbl-comp-transfer');

// Collapsible Panel & Sidebar Controls
const appMainGrid = document.getElementById('app-main-grid');
const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
const btnHideSidebarInner = document.getElementById('btn-hide-sidebar-inner');
const sidebarToggleLabel = document.getElementById('sidebar-toggle-label');
const btnFocusDispatch = document.getElementById('btn-focus-dispatch');

const panelVisibilityState = {
    sidebar: true,
    kpis: true,
    topCharts: true,
    dispatch: true,
    ledger: true
};

// Global Chart & UI Animation State (persisted in localStorage)
const btnToggleAnimations = document.getElementById('btn-toggle-animations');
const lblToggleAnimations = document.getElementById('lbl-toggle-animations');
let globalAnimationsEnabled = true;

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

        // Dispatch Day Selectors & Multi-Day Range Explorer
    dispatchDaySelect.addEventListener('change', () => {
        jumpToDateInDispatchExplorer(dispatchDaySelect.value);
    });

    if (btnPresetLatest) {
        btnPresetLatest.addEventListener('click', () => {
            jumpToLatest24h();
        });
    }

    if (btnDispatchLatest) {
        btnDispatchLatest.addEventListener('click', () => {
            jumpToLatest24h();
        });
    }

    btnPresetPeakSolar.addEventListener('click', () => {
        if (dashboardData && dashboardData.metadata && dashboardData.metadata.featured_days) {
            dispatchExplorerState.spanHours = 24;
            jumpToDateInDispatchExplorer(dashboardData.metadata.featured_days.peak_solar);
        }
    });

    btnPresetVolatility.addEventListener('click', () => {
        if (dashboardData && dashboardData.metadata && dashboardData.metadata.featured_days) {
            dispatchExplorerState.spanHours = 24;
            jumpToDateInDispatchExplorer(dashboardData.metadata.featured_days.peak_volatility);
        }
    });

    btnPresetCloudy.addEventListener('click', () => {
        if (dashboardData && dashboardData.metadata && dashboardData.metadata.featured_days) {
            dispatchExplorerState.spanHours = 24;
            jumpToDateInDispatchExplorer(dashboardData.metadata.featured_days.cloudy_day);
        }
    });

    // Step Back / Forward (Full Range & Half Range)
    if (btnStepBackFull) {
        btnStepBackFull.addEventListener('click', () => stepDispatchWindow(-1.0));
    }
    if (btnStepBackHalf) {
        btnStepBackHalf.addEventListener('click', () => stepDispatchWindow(-0.5));
    }
    if (btnStepFwdHalf) {
        btnStepFwdHalf.addEventListener('click', () => stepDispatchWindow(0.5));
    }
    if (btnStepFwdFull) {
        btnStepFwdFull.addEventListener('click', () => stepDispatchWindow(1.0));
    }

    // Timespan Duration Buttons (24h, 48h, 72h, 7D, 14D, 30D)
    document.querySelectorAll('.btn-dispatch-span').forEach(btn => {
        btn.addEventListener('click', () => {
            const hours = parseInt(btn.getAttribute('data-span-hours'), 10);
            if (!isNaN(hours) && hours > 0) {
                setDispatchSpanHours(hours);
            }
        });
    });

    // Exact Timestamp (Editable YYYY-MM-DD + Monday-First Calendar Popover + Hour + OK Button)
    if (btnApplyTimestampOk) {
        btnApplyTimestampOk.addEventListener('click', () => {
            closeIsoCalendarPopover();
            applyCustomTimestampAndRangeInputs();
        });
    }

    if (inputTsDate) {
        inputTsDate.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                closeIsoCalendarPopover();
                applyCustomTimestampAndRangeInputs();
            } else if (e.key === 'Escape') {
                closeIsoCalendarPopover();
            }
        });
    }

    if (btnToggleCalendar) {
        btnToggleCalendar.addEventListener('click', (e) => {
            e.stopPropagation();
            if (isoCalendarState.isOpen) {
                closeIsoCalendarPopover();
            } else {
                openIsoCalendarPopover();
            }
        });
    }

    if (btnCalPrevMonth) {
        btnCalPrevMonth.addEventListener('click', (e) => {
            e.stopPropagation();
            stepIsoCalendarMonth(-1);
        });
    }

    if (btnCalNextMonth) {
        btnCalNextMonth.addEventListener('click', (e) => {
            e.stopPropagation();
            stepIsoCalendarMonth(1);
        });
    }

    if (btnCalJumpLatest) {
        btnCalJumpLatest.addEventListener('click', (e) => {
            e.stopPropagation();
            if (isoCalendarState.maxDateStr) {
                isoCalendarState.pendingDateStr = isoCalendarState.maxDateStr;
                if (inputTsDate) inputTsDate.value = isoCalendarState.maxDateStr;
                const parts = isoCalendarState.maxDateStr.split('-');
                isoCalendarState.viewYear = parseInt(parts[0], 10);
                isoCalendarState.viewMonth = parseInt(parts[1], 10) - 1;
                renderIsoCalendarGrid();
            }
        });
    }

    if (btnCalOk) {
        btnCalOk.addEventListener('click', (e) => {
            e.stopPropagation();
            if (isoCalendarState.pendingDateStr && inputTsDate) {
                inputTsDate.value = isoCalendarState.pendingDateStr;
            }
            closeIsoCalendarPopover();
            applyCustomTimestampAndRangeInputs();
        });
    }

    // Close calendar popover when clicking outside
    document.addEventListener('click', (e) => {
        if (isoCalendarState.isOpen && customTimestampPickerWrapper && !customTimestampPickerWrapper.contains(e.target)) {
            closeIsoCalendarPopover();
        }
    });

    if (btnTsHourUp) {
        btnTsHourUp.addEventListener('click', () => {
            stepTimestampHour(1);
        });
    }
    if (btnTsHourDown) {
        btnTsHourDown.addEventListener('click', () => {
            stepTimestampHour(-1);
        });
    }
    if (inputTsHour) {
        inputTsHour.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') applyCustomTimestampAndRangeInputs();
        });
    }

    if (btnToggleCenterRange) {
        btnToggleCenterRange.addEventListener('click', () => {
            toggleCenterOnTimestampMode();
        });
    }

    if (btnSpanDaysUp) {
        btnSpanDaysUp.addEventListener('click', () => adjustExactDuration(24));
    }
    if (btnSpanDaysDown) {
        btnSpanDaysDown.addEventListener('click', () => adjustExactDuration(-24));
    }
    if (inputSpanDays) {
        inputSpanDays.addEventListener('change', () => applyManualDurationInputs());
        inputSpanDays.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') applyCustomTimestampAndRangeInputs();
        });
    }

    if (btnRangeHoursUp) {
        btnRangeHoursUp.addEventListener('click', () => adjustExactDuration(1));
    }
    if (btnRangeHoursDown) {
        btnRangeHoursDown.addEventListener('click', () => adjustExactDuration(-1));
    }

    if (inputRangeHours) {
        inputRangeHours.addEventListener('change', () => applyManualDurationInputs());
        inputRangeHours.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') applyCustomTimestampAndRangeInputs();
        });
    }

    // Dispatch Metric Visibility Toggle Buttons (Default: All Active)
    document.querySelectorAll('[data-dispatch-metric]').forEach(btn => {
        btn.addEventListener('click', () => {
            const metricKey = btn.getAttribute('data-dispatch-metric');
            if (metricKey in dispatchMetricVisibility) {
                dispatchMetricVisibility[metricKey] = !dispatchMetricVisibility[metricKey];
                syncDispatchMetricButtonsUI();
                updateHourlyDispatchChart();
            }
        });
    });

    if (btnMetricsAll) {
        btnMetricsAll.addEventListener('click', () => {
            Object.keys(dispatchMetricVisibility).forEach(k => {
                dispatchMetricVisibility[k] = true;
            });
            syncDispatchMetricButtonsUI();
            updateHourlyDispatchChart();
        });
    }

    if (btnMetricsPrices) {
        btnMetricsPrices.addEventListener('click', () => {
            dispatchMetricVisibility.pv = false;
            dispatchMetricVisibility.load = false;
            dispatchMetricVisibility.battery = false;
            dispatchMetricVisibility.soc = false;
            dispatchMetricVisibility.spot = true;
            dispatchMetricVisibility.myPrice = true;
            syncDispatchMetricButtonsUI();
            updateHourlyDispatchChart();
        });
    }

    if (btnMetricsPower) {
        btnMetricsPower.addEventListener('click', () => {
            dispatchMetricVisibility.pv = true;
            dispatchMetricVisibility.load = true;
            dispatchMetricVisibility.battery = true;
            dispatchMetricVisibility.soc = true;
            dispatchMetricVisibility.spot = false;
            dispatchMetricVisibility.myPrice = false;
            syncDispatchMetricButtonsUI();
            updateHourlyDispatchChart();
        });
    }

    syncDispatchMetricButtonsUI();

    // Dispatch Price Component Toggle Buttons (Energiskatt, EEM Transfer, Tibber Markup, 25% Moms, Nätnytta)
    document.querySelectorAll('[data-price-comp]').forEach(btn => {
        btn.addEventListener('click', () => {
            const compKey = btn.getAttribute('data-price-comp');
            if (compKey in dispatchPriceComponents) {
                dispatchPriceComponents[compKey] = !dispatchPriceComponents[compKey];
                syncDispatchPriceComponentButtonsUI();
                updateHourlyDispatchChart();
            }
        });
    });

    if (btnCompAllOn) {
        btnCompAllOn.addEventListener('click', () => {
            Object.keys(dispatchPriceComponents).forEach(k => {
                dispatchPriceComponents[k] = true;
            });
            syncDispatchPriceComponentButtonsUI();
            updateHourlyDispatchChart();
        });
    }

    if (btnCompPureSpot) {
        btnCompPureSpot.addEventListener('click', () => {
            Object.keys(dispatchPriceComponents).forEach(k => {
                dispatchPriceComponents[k] = false;
            });
            syncDispatchPriceComponentButtonsUI();
            updateHourlyDispatchChart();
        });
    }

    syncDispatchPriceComponentButtonsUI();

    // Collapsible Panels & Sidebar Controls
    setupCollapsiblePanels();
    setupGlobalAnimationsToggle();

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

function formatSpanDurationLabel(totalHours) {
    const d = Math.floor(totalHours / 24);
    const h = totalHours % 24;
    if (d > 0 && h === 0) {
        return `${d}d`;
    }
    if (d > 0) {
        return `${d}d ${h}h`;
    }
    return `${h}h`;
}

function formatSpanDaysAndHoursPill(totalHours) {
    const d = Math.floor(totalHours / 24);
    const h = totalHours % 24;
    return `${d}d ${h}h`;
}

function getEffectiveSpanHourlySlots(totalRecordsCount) {
    const h = Math.max(1, parseInt(dispatchExplorerState.spanHours, 10) || 24);
    return Math.min(totalRecordsCount, h);
}

function formatIndexAsDatetimeLocal(rec, hourOverride = null) {
    if (!rec) return '';
    const hr = hourOverride !== null ? hourOverride : rec.hour;
    return `${rec.date}T${String(hr).padStart(2, '0')}:00`;
}

function formatDisplayTimestamp(rec, addMinutesOffset = 0) {
    if (!rec) return '';
    const baseMs = new Date(`${rec.date}T${String(rec.hour).padStart(2, '0')}:00:00Z`).getTime();
    const targetDt = new Date(baseMs + addMinutesOffset * 60 * 1000);
    const yyyy = targetDt.getUTCFullYear();
    const mm = String(targetDt.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(targetDt.getUTCDate()).padStart(2, '0');
    const hh = String(targetDt.getUTCHours()).padStart(2, '0');
    const min = String(targetDt.getUTCMinutes()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
}

function recomputeWindowFromAnchor() {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length) return;
    const total = hourlyData.length;
    const slots = getEffectiveSpanHourlySlots(total);

    if (dispatchExplorerState.anchorIndex === null || dispatchExplorerState.anchorIndex === undefined) {
        dispatchExplorerState.endIndex = total;
        const startIdx = Math.max(0, total - slots);
        dispatchExplorerState.anchorIndex = dispatchExplorerState.centerOnTimestamp
            ? Math.round(startIdx + slots / 2)
            : startIdx;
        return;
    }

    const anchor = Math.max(0, Math.min(total - 1, dispatchExplorerState.anchorIndex));
    if (dispatchExplorerState.centerOnTimestamp) {
        // Half before anchor, half after anchor
        const halfBefore = Math.floor(slots / 2);
        const startIdx = Math.max(0, Math.min(total - slots, anchor - halfBefore));
        dispatchExplorerState.endIndex = Math.min(total, startIdx + slots);
    } else {
        // Anchor is the exact Start Timestamp
        const startIdx = Math.max(0, Math.min(total - slots, anchor));
        dispatchExplorerState.endIndex = Math.min(total, startIdx + slots);
    }
}

function toggleCenterOnTimestampMode() {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length) return;
    const total = hourlyData.length;
    const slots = getEffectiveSpanHourlySlots(total);
    const currentEnd = dispatchExplorerState.endIndex ?? total;
    const currentStart = Math.max(0, currentEnd - slots);

    dispatchExplorerState.centerOnTimestamp = !dispatchExplorerState.centerOnTimestamp;

    // When toggling Center ON, keep the current anchor timestamp (what's in the datetime box) and center the window around it!
    // When toggling Center OFF, treat the current anchor timestamp as the Start Timestamp!
    if (dispatchExplorerState.anchorIndex === null) {
        dispatchExplorerState.anchorIndex = currentStart;
    }
    recomputeWindowFromAnchor();
    updateHourlyDispatchChart();
    updatePresetButtonsState();
}

const MONTH_NAMES_FULL = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];

function openIsoCalendarPopover() {
    if (!isoCalendarPopover) return;
    const currentVal = (inputTsDate ? inputTsDate.value.trim() : '') || isoCalendarState.maxDateStr;
    isoCalendarState.pendingDateStr = currentVal;

    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(currentVal);
    if (match) {
        isoCalendarState.viewYear = parseInt(match[1], 10);
        isoCalendarState.viewMonth = parseInt(match[2], 10) - 1;
    }

    isoCalendarState.isOpen = true;
    isoCalendarPopover.classList.add('is-open');
    isoCalendarPopover.setAttribute('aria-hidden', 'false');
    if (btnToggleCalendar) btnToggleCalendar.classList.add('active');
    renderIsoCalendarGrid();
}

function closeIsoCalendarPopover() {
    if (!isoCalendarPopover) return;
    isoCalendarState.isOpen = false;
    isoCalendarPopover.classList.remove('is-open');
    isoCalendarPopover.setAttribute('aria-hidden', 'true');
    if (btnToggleCalendar) btnToggleCalendar.classList.remove('active');
}

function stepIsoCalendarMonth(deltaMonths) {
    let m = isoCalendarState.viewMonth + deltaMonths;
    let y = isoCalendarState.viewYear;
    while (m < 0) {
        m += 12;
        y -= 1;
    }
    while (m > 11) {
        m -= 12;
        y += 1;
    }
    isoCalendarState.viewYear = y;
    isoCalendarState.viewMonth = m;
    renderIsoCalendarGrid();
}

function renderIsoCalendarGrid() {
    if (!isoCalDaysGrid) return;
    const y = isoCalendarState.viewYear;
    const m = isoCalendarState.viewMonth;

    if (isoCalMonthTitle) {
        isoCalMonthTitle.innerText = `${MONTH_NAMES_FULL[m]} ${y}`;
    }

    // Determine min/max month bounds
    const minYm = isoCalendarState.minDateStr ? isoCalendarState.minDateStr.substring(0, 7) : '2026-07';
    const maxYm = isoCalendarState.maxDateStr ? isoCalendarState.maxDateStr.substring(0, 7) : '2026-11';
    const curYm = `${y}-${String(m + 1).padStart(2, '0')}`;

    if (btnCalPrevMonth) btnCalPrevMonth.disabled = (curYm <= minYm);
    if (btnCalNextMonth) btnCalNextMonth.disabled = (curYm >= maxYm);

    // ISO-8601 Monday-first weekday calculation:
    // JS getUTCDay(): 0 = Sunday, 1 = Monday, ..., 6 = Saturday
    // Convert to Monday-first: 0 = Monday, 1 = Tuesday, ..., 6 = Sunday
    const firstDayOfMonthUtc = new Date(Date.UTC(y, m, 1)).getUTCDay();
    const mondayFirstOffset = (firstDayOfMonthUtc + 6) % 7;
    const daysInMonth = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();

    let html = '';
    for (let e = 0; e < mondayFirstOffset; e++) {
        html += '<span class="iso-cal-day is-empty"></span>';
    }

    for (let dayNum = 1; dayNum <= daysInMonth; dayNum++) {
        const dStr = `${y}-${String(m + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
        const hasData = isoCalendarState.availableDatesSet.has(dStr);
        const isSelected = (dStr === isoCalendarState.pendingDateStr);
        const isLatest = (dStr === isoCalendarState.maxDateStr);

        const classes = ['iso-cal-day'];
        if (!hasData) classes.push('is-unavailable');
        if (isSelected) classes.push('is-selected');
        if (isLatest) classes.push('is-latest');

        const titleStr = hasData
            ? `${dStr}${isLatest ? ' (Latest Available High-Res Data)' : ''} — Click to select`
            : `${dStr} — No high-resolution data available`;

        html += `<button type="button" class="${classes.join(' ')}" data-cal-date="${dStr}" ${hasData ? '' : 'disabled'} title="${titleStr}">${dayNum}</button>`;
    }

    isoCalDaysGrid.innerHTML = html;

    isoCalDaysGrid.querySelectorAll('button[data-cal-date]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const picked = btn.getAttribute('data-cal-date');
            if (picked) {
                isoCalendarState.pendingDateStr = picked;
                if (inputTsDate) inputTsDate.value = picked;
                renderIsoCalendarGrid();
            }
        });
        btn.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            const picked = btn.getAttribute('data-cal-date');
            if (picked) {
                isoCalendarState.pendingDateStr = picked;
                if (inputTsDate) inputTsDate.value = picked;
                closeIsoCalendarPopover();
                applyCustomTimestampAndRangeInputs();
            }
        });
    });
}

function applyCustomTimestampAndRangeInputs() {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length) return;

    let rawDatePart = (inputTsDate ? inputTsDate.value.trim() : '') || hourlyData[hourlyData.length - 1].date;
    // Clamp typed date to valid dataset bounds if outside range
    if (rawDatePart < isoCalendarState.minDateStr) {
        rawDatePart = isoCalendarState.minDateStr;
    } else if (rawDatePart > isoCalendarState.maxDateStr) {
        rawDatePart = isoCalendarState.maxDateStr;
    }
    const datePart = rawDatePart;
    const hourPart = Math.max(0, Math.min(23, parseInt(inputTsHour ? inputTsHour.value : 0, 10) || 0));

    // Also sync any edited span days + hours when OK is clicked
    const rawD = Math.max(0, parseInt(inputSpanDays ? inputSpanDays.value : 1, 10) || 0);
    const rawH = Math.max(0, parseInt(inputRangeHours ? inputRangeHours.value : 0, 10) || 0);
    const combinedHours = Math.max(1, (rawD * 24) + rawH);
    dispatchExplorerState.spanHours = Math.min(hourlyData.length, combinedHours);

    // Find matching index in hourlyData
    let targetIdx = -1;
    for (let i = 0; i < hourlyData.length; i++) {
        if (hourlyData[i].date === datePart && hourlyData[i].hour === hourPart) {
            targetIdx = i;
            break;
        }
        if (hourlyData[i].date === datePart && targetIdx === -1) {
            targetIdx = i;
        }
    }

    if (targetIdx === -1) {
        // Find nearest available date if user typed a date in a gap
        let bestDist = Infinity;
        for (let i = 0; i < hourlyData.length; i++) {
            const dist = Math.abs(new Date(hourlyData[i].date).getTime() - new Date(datePart).getTime());
            if (dist < bestDist) {
                bestDist = dist;
                targetIdx = i;
            }
        }
    }

    if (targetIdx === -1) targetIdx = hourlyData.length - 1;

    dispatchExplorerState.anchorIndex = targetIdx;
    recomputeWindowFromAnchor();
    updateHourlyDispatchChart();
    updatePresetButtonsState();
}

function stepTimestampHour(deltaHr) {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length) return;
    const total = hourlyData.length;
    const currentAnchor = dispatchExplorerState.anchorIndex ?? Math.max(0, total - 24);
    dispatchExplorerState.anchorIndex = Math.max(0, Math.min(total - 1, currentAnchor + deltaHr));
    recomputeWindowFromAnchor();
    updateHourlyDispatchChart();
    updatePresetButtonsState();
}

function adjustExactDuration(deltaHours) {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length) return;

    const nextHours = Math.max(1, Math.min(hourlyData.length, (dispatchExplorerState.spanHours || 24) + deltaHours));
    dispatchExplorerState.spanHours = nextHours;

    recomputeWindowFromAnchor();
    updateHourlyDispatchChart();
    updatePresetButtonsState();
}

function applyManualDurationInputs() {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length) return;

    const rawD = Math.max(0, parseInt(inputSpanDays ? inputSpanDays.value : 0, 10) || 0);
    const rawH = Math.max(0, parseInt(inputRangeHours ? inputRangeHours.value : 0, 10) || 0);
    const combinedHours = Math.max(1, (rawD * 24) + rawH);
    dispatchExplorerState.spanHours = Math.min(hourlyData.length, combinedHours);

    recomputeWindowFromAnchor();
    updateHourlyDispatchChart();
    updatePresetButtonsState();
}

function syncDispatchMetricButtonsUI() {
    document.querySelectorAll('[data-dispatch-metric]').forEach(btn => {
        const key = btn.getAttribute('data-dispatch-metric');
        if (key in dispatchMetricVisibility) {
            const isVis = Boolean(dispatchMetricVisibility[key]);
            btn.classList.toggle('active', isVis);
            btn.setAttribute('aria-pressed', String(isVis));
        }
    });
}

function syncDispatchPriceComponentButtonsUI() {
    const rawEnergiskatt = parseFloat(energiskattInput ? energiskattInput.value : 42.8) || 42.8;
    const rawTransfer = parseFloat(eemTransferInput ? eemTransferInput.value : 17.6) || 17.6;

    if (lblCompEnergiskatt) {
        lblCompEnergiskatt.innerText = `Energiskatt (+${rawEnergiskatt.toFixed(1)} öre)`;
    }
    if (lblCompTransfer) {
        lblCompTransfer.innerText = `EEM Transfer (+${rawTransfer.toFixed(1)} öre)`;
    }

    document.querySelectorAll('[data-price-comp]').forEach(btn => {
        const key = btn.getAttribute('data-price-comp');
        if (key in dispatchPriceComponents) {
            const isOn = Boolean(dispatchPriceComponents[key]);
            btn.classList.toggle('active', isOn);
            btn.setAttribute('aria-pressed', String(isOn));
            const icon = btn.querySelector('i');
            if (icon) {
                icon.className = isOn ? 'fa-solid fa-check' : 'fa-solid fa-xmark';
            }
        }
    });
}

function setupCollapsiblePanels() {
    try {
        const saved = localStorage.getItem('mysunshine_panel_state_v1');
        if (saved) {
            const parsed = JSON.parse(saved);
            Object.keys(panelVisibilityState).forEach(k => {
                if (typeof parsed[k] === 'boolean') {
                    panelVisibilityState[k] = parsed[k];
                }
            });
        }
    } catch (e) {
        // Ignore storage errors in sandboxed/private contexts
    }

    if (btnToggleSidebar) {
        btnToggleSidebar.addEventListener('click', () => {
            panelVisibilityState.sidebar = !panelVisibilityState.sidebar;
            applyPanelVisibilityState();
        });
    }

    if (btnHideSidebarInner) {
        btnHideSidebarInner.addEventListener('click', () => {
            panelVisibilityState.sidebar = false;
            applyPanelVisibilityState();
        });
    }

    document.querySelectorAll('[data-collapse-panel]').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.getAttribute('data-collapse-panel');
            if (key in panelVisibilityState) {
                panelVisibilityState[key] = !panelVisibilityState[key];
                applyPanelVisibilityState();
            }
        });
    });

    document.querySelectorAll('[data-panel-target]').forEach(pill => {
        pill.addEventListener('click', () => {
            const key = pill.getAttribute('data-panel-target');
            if (key in panelVisibilityState) {
                panelVisibilityState[key] = !panelVisibilityState[key];
                applyPanelVisibilityState();
            }
        });
    });

    if (btnFocusDispatch) {
        btnFocusDispatch.addEventListener('click', () => {
            const isFocusActive = !panelVisibilityState.sidebar &&
                !panelVisibilityState.kpis &&
                !panelVisibilityState.topCharts &&
                !panelVisibilityState.ledger &&
                panelVisibilityState.dispatch;

            if (isFocusActive) {
                panelVisibilityState.sidebar = true;
                panelVisibilityState.kpis = true;
                panelVisibilityState.topCharts = true;
                panelVisibilityState.dispatch = true;
                panelVisibilityState.ledger = true;
            } else {
                panelVisibilityState.sidebar = false;
                panelVisibilityState.kpis = false;
                panelVisibilityState.topCharts = false;
                panelVisibilityState.dispatch = true;
                panelVisibilityState.ledger = false;
            }
            applyPanelVisibilityState();
        });
    }

    applyPanelVisibilityState();
}

function setupGlobalAnimationsToggle() {
    try {
        const savedAnim = localStorage.getItem('mysunshine_animations_enabled_v1');
        if (savedAnim !== null) {
            globalAnimationsEnabled = JSON.parse(savedAnim) !== false;
        }
    } catch (e) {
        // Ignore storage errors
    }

    if (btnToggleAnimations) {
        btnToggleAnimations.addEventListener('click', () => {
            globalAnimationsEnabled = !globalAnimationsEnabled;
            applyGlobalAnimationsState();
        });
    }

    applyGlobalAnimationsState();
}

function applyGlobalAnimationsState() {
    try {
        localStorage.setItem('mysunshine_animations_enabled_v1', JSON.stringify(globalAnimationsEnabled));
    } catch (e) {
        // Ignore storage errors
    }

    // 1. Update live chart instances' animation duration (never overwrite Chart.defaults.animation object!)
    const animDuration = globalAnimationsEnabled ? 400 : 0;
    [chartPaybackInstance, chartMonthlyBaselinesInstance, chartHourlyDispatchInstance, chartShadowForecastInstance].forEach(inst => {
        if (inst && inst.options) {
            inst.options.animation = { duration: animDuration };
        }
    });

    // 2. Toggle CSS transition override class on body
    document.body.classList.toggle('no-animations', !globalAnimationsEnabled);

    // 3. Update header button UI
    if (btnToggleAnimations) {
        btnToggleAnimations.classList.toggle('active', globalAnimationsEnabled);
        btnToggleAnimations.setAttribute('aria-pressed', String(globalAnimationsEnabled));
    }
    if (lblToggleAnimations) {
        lblToggleAnimations.innerText = globalAnimationsEnabled ? 'Animations: On' : 'Animations: Off';
    }
}

function applyPanelVisibilityState() {
    try {
        localStorage.setItem('mysunshine_panel_state_v1', JSON.stringify(panelVisibilityState));
    } catch (e) {
        // Ignore storage errors
    }

    // 1. Sidebar state
    if (appMainGrid) {
        appMainGrid.classList.toggle('sidebar-collapsed', !panelVisibilityState.sidebar);
    }
    if (btnToggleSidebar) {
        btnToggleSidebar.classList.toggle('collapsed', !panelVisibilityState.sidebar);
        btnToggleSidebar.setAttribute('aria-expanded', String(panelVisibilityState.sidebar));
    }
    if (sidebarToggleLabel) {
        sidebarToggleLabel.innerText = panelVisibilityState.sidebar ? 'Controls' : 'Show Controls';
    }

    // 2. Collapsible Section Panels
    ['kpis', 'topCharts', 'dispatch', 'ledger'].forEach(key => {
        const isVisible = panelVisibilityState[key];
        const panelEl = document.getElementById(`section-panel-${key}`);
        const btnEl = document.getElementById(`btn-collapse-${key}`);
        const pillEl = document.getElementById(`pill-toggle-${key}`);

        if (panelEl) {
            panelEl.classList.toggle('is-collapsed', !isVisible);
        }
        if (btnEl) {
            btnEl.setAttribute('aria-expanded', String(isVisible));
            btnEl.innerHTML = isVisible
                ? '<i class="fa-solid fa-minus"></i> <span>Minimize</span>'
                : '<i class="fa-solid fa-plus"></i> <span>Expand</span>';
        }
        if (pillEl) {
            pillEl.classList.toggle('active', isVisible);
        }
    });

    // 3. Focus Dispatch button highlight
    if (btnFocusDispatch) {
        const isFocusActive = !panelVisibilityState.sidebar &&
            !panelVisibilityState.kpis &&
            !panelVisibilityState.topCharts &&
            !panelVisibilityState.ledger &&
            panelVisibilityState.dispatch;
        btnFocusDispatch.classList.toggle('active', isFocusActive);
        btnFocusDispatch.innerHTML = isFocusActive
            ? '<i class="fa-solid fa-compress"></i> Restore All Panels'
            : '<i class="fa-solid fa-expand"></i> Focus Dispatch';
    }

    // Resize active Chart.js instances after layout transition
    setTimeout(() => {
        if (chartPaybackInstance) chartPaybackInstance.resize();
        if (chartMonthlyBaselinesInstance) chartMonthlyBaselinesInstance.resize();
        if (chartHourlyDispatchInstance) chartHourlyDispatchInstance.resize();
        if (chartShadowForecastInstance) chartShadowForecastInstance.resize();
    }, 60);
}

function jumpToLatest24h() {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length) return;
    const total = hourlyData.length;
    dispatchExplorerState.spanHours = 24;
    dispatchExplorerState.spanMinutes = 0;
    dispatchExplorerState.endIndex = total;
    const startIdx = Math.max(0, total - 24);
    dispatchExplorerState.anchorIndex = dispatchExplorerState.centerOnTimestamp
        ? Math.round(startIdx + 12)
        : startIdx;
    updateHourlyDispatchChart();
    updatePresetButtonsState();
}

function jumpToDateInDispatchExplorer(dateStr) {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length || !dateStr) return;

    let firstMatchIdx = -1;
    for (let i = 0; i < hourlyData.length; i++) {
        if (hourlyData[i].date === dateStr) {
            firstMatchIdx = i;
            break;
        }
    }

    if (firstMatchIdx !== -1) {
        const slots = getEffectiveSpanHourlySlots(hourlyData.length);
        // Set start of day as start of window (or center of day if centerOnTimestamp is enabled)
        dispatchExplorerState.anchorIndex = dispatchExplorerState.centerOnTimestamp
            ? Math.min(hourlyData.length - 1, firstMatchIdx + Math.floor(slots / 2))
            : firstMatchIdx;
        recomputeWindowFromAnchor();
        updateHourlyDispatchChart();
        updatePresetButtonsState();
    }
}

function setDispatchSpanHours(newSpanHours) {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length) return;
    const total = hourlyData.length;
    const clampedSpan = Math.min(total, Math.max(1, newSpanHours));
    dispatchExplorerState.spanHours = clampedSpan;
    dispatchExplorerState.spanMinutes = 0;

    if (dispatchExplorerState.anchorIndex !== null) {
        recomputeWindowFromAnchor();
    } else {
        dispatchExplorerState.endIndex = total;
        const startIdx = Math.max(0, total - clampedSpan);
        dispatchExplorerState.anchorIndex = dispatchExplorerState.centerOnTimestamp
            ? Math.round(startIdx + clampedSpan / 2)
            : startIdx;
    }

    updateHourlyDispatchChart();
    updatePresetButtonsState();
}

function stepDispatchWindow(rangeMultiplier) {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    if (!hourlyData.length) return;
    const total = hourlyData.length;
    const slots = getEffectiveSpanHourlySlots(total);
    const currentEnd = dispatchExplorerState.endIndex ?? total;

    const deltaHours = Math.max(1, Math.round(slots * Math.abs(rangeMultiplier))) * (rangeMultiplier < 0 ? -1 : 1);
    const nextEnd = Math.max(slots, Math.min(total, currentEnd + deltaHours));
    dispatchExplorerState.endIndex = nextEnd;
    const nextStart = Math.max(0, nextEnd - slots);
    dispatchExplorerState.anchorIndex = dispatchExplorerState.centerOnTimestamp
        ? Math.min(total - 1, nextStart + Math.floor(slots / 2))
        : nextStart;

    updateHourlyDispatchChart();
    updatePresetButtonsState();
}

function updatePresetButtonsState() {
    const hourlyData = dashboardData?.high_res_30d?.hourly_data || [];
    const total = hourlyData.length;
    const span = getEffectiveSpanHourlySlots(total);
    const endIdx = dispatchExplorerState.endIndex ?? total;
    const startIdx = Math.max(0, endIdx - span);
    const isLatest24h = (span === 24 && endIdx === total);

    const anchorDate = hourlyData[startIdx]?.date || dispatchDaySelect.value;
    const isSingleDayAligned = (span === 24 && hourlyData[startIdx]?.hour === 0);

    const feats = dashboardData?.metadata?.featured_days;
    if (btnPresetLatest) {
        btnPresetLatest.classList.toggle('active', isLatest24h);
    }
    if (btnDispatchLatest) {
        btnDispatchLatest.classList.toggle('active', isLatest24h);
    }
    btnPresetPeakSolar.classList.toggle('active', isSingleDayAligned && feats?.peak_solar === anchorDate);
    btnPresetVolatility.classList.toggle('active', isSingleDayAligned && feats?.peak_volatility === anchorDate);
    btnPresetCloudy.classList.toggle('active', isSingleDayAligned && feats?.cloudy_day === anchorDate);

    // Sync span preset buttons
    document.querySelectorAll('.btn-dispatch-span').forEach(btn => {
        const bHours = parseInt(btn.getAttribute('data-span-hours'), 10);
        btn.classList.toggle('active', bHours === dispatchExplorerState.spanHours);
    });

    // Sync exact span days (d) and hours (h) inputs (e.g. 24h -> 1d 0h, 23h -> 0d 23h, 25h -> 1d 1h)
    const spanDaysPart = Math.floor(dispatchExplorerState.spanHours / 24);
    const spanHoursPart = dispatchExplorerState.spanHours % 24;
    if (inputSpanDays && document.activeElement !== inputSpanDays) {
        inputSpanDays.value = spanDaysPart;
    }
    if (inputRangeHours && document.activeElement !== inputRangeHours) {
        inputRangeHours.value = spanHoursPart;
    }

    // Sync Center Span on Timestamp button & label
    const isCentered = Boolean(dispatchExplorerState.centerOnTimestamp);
    if (btnToggleCenterRange) {
        btnToggleCenterRange.classList.toggle('active', isCentered);
        btnToggleCenterRange.setAttribute('aria-pressed', String(isCentered));
    }
    if (lblCenterRangeMode) {
        lblCenterRangeMode.innerText = isCentered ? 'Center Span on Timestamp: On (±Half)' : 'Center Span on Timestamp: Off';
    }
    if (lblAnchorDatetime) {
        lblAnchorDatetime.innerHTML = isCentered
            ? '<i class="fa-solid fa-crosshairs"></i> Center Timestamp:'
            : '<i class="fa-regular fa-calendar-check"></i> Start Timestamp:';
    }

    // Sync editable YYYY-MM-DD date input + HH:00 input
    if (hourlyData.length) {
        const displayAnchorIdx = isCentered
            ? Math.min(total - 1, startIdx + Math.floor(span / 2))
            : startIdx;
        const anchorRec = hourlyData[displayAnchorIdx];
        if (anchorRec) {
            if (inputTsDate && document.activeElement !== inputTsDate) {
                inputTsDate.value = anchorRec.date;
            }
            if (inputTsHour && document.activeElement !== inputTsHour) {
                inputTsHour.value = String(anchorRec.hour).padStart(2, '0');
            }
        }
    }

    // Update prominent SPAN IN VIEW Start -> End banner
    if (hourlyData.length) {
        const firstRec = hourlyData[startIdx];
        const lastRec = hourlyData[Math.min(total - 1, endIdx - 1)];
        const startFormatted = formatDisplayTimestamp(firstRec, 0);
        const endFormatted = `${lastRec.date} ${String(lastRec.hour + 1).padStart(2, '0')}:00`;

        if (inViewTimestampsText) {
            inViewTimestampsText.innerHTML = `${startFormatted} &rarr; ${endFormatted}`;
        }
        if (inViewDurationPill) {
            const dhStr = formatSpanDaysAndHoursPill(dispatchExplorerState.spanHours);
            inViewDurationPill.innerText = isCentered ? `${dhStr} (Centered)` : dhStr;
        }
    }

    // Update full-span and half-span button labels and disabled states
    const fullStr = formatSpanDurationLabel(dispatchExplorerState.spanHours);
    const halfH = Math.max(1, Math.round(dispatchExplorerState.spanHours / 2));
    const halfStr = formatSpanDurationLabel(halfH);

    if (lblStepBackFull) lblStepBackFull.innerText = `-${fullStr}`;
    if (lblStepBackHalf) lblStepBackHalf.innerText = `-${halfStr}`;
    if (lblStepFwdHalf) lblStepFwdHalf.innerText = `+${halfStr}`;
    if (lblStepFwdFull) lblStepFwdFull.innerText = `+${fullStr}`;

    if (btnStepBackFull) btnStepBackFull.disabled = (startIdx <= 0);
    if (btnStepBackHalf) btnStepBackHalf.disabled = (startIdx <= 0);
    if (btnStepFwdHalf) btnStepFwdHalf.disabled = (endIdx >= total);
    if (btnStepFwdFull) btnStepFwdFull.disabled = (endIdx >= total);
}

// Populate Dispatch Day Dropdown (Defaults to Latest Available 24h Window)
function populateDispatchDays() {
    if (!dashboardData || !dashboardData.high_res_30d || !dashboardData.high_res_30d.days_list) return;
    
    const days = dashboardData.high_res_30d.days_list;
    const hourlyData = dashboardData.high_res_30d.hourly_data || [];
    dispatchDaySelect.innerHTML = '';
    
    // Show days in chronological order, marking the latest available day
    const firstDayDate = days[0]?.date || '2026-07-16';
    const latestDayDate = days[days.length - 1]?.date || '2026-11-26';
    isoCalendarState.minDateStr = firstDayDate;
    isoCalendarState.maxDateStr = latestDayDate;
    isoCalendarState.availableDatesSet = new Set(days.map(d => d.date));

    if (isoCalBoundsHint) {
        isoCalBoundsHint.innerHTML = `Data: ${firstDayDate} &rarr; ${latestDayDate}`;
    }

    days.forEach(day => {
        const opt = document.createElement('option');
        opt.value = day.date;
        const latestTag = (day.date === latestDayDate) ? ' ★ Latest' : '';
        opt.innerText = `${day.display_name}${latestTag} (${day.total_produced_kwh} kWh PV, ${day.avg_spot_price_ore} öre avg)`;
        dispatchDaySelect.appendChild(opt);
    });

    // Default to Latest Available 24h Data
    dispatchExplorerState.spanHours = 24;
    dispatchExplorerState.spanMinutes = 0;
    dispatchExplorerState.endIndex = hourlyData.length;
    dispatchExplorerState.anchorIndex = Math.max(0, hourlyData.length - 24);
    if (latestDayDate) {
        dispatchDaySelect.value = latestDayDate;
    }
    updatePresetButtonsState();
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
            animation: { duration: globalAnimationsEnabled ? 400 : 0 },
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
            animation: { duration: globalAnimationsEnabled ? 400 : 0 },
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
            animation: { duration: globalAnimationsEnabled ? 400 : 0 },
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

// Plugin to draw midnight day separators on multi-day dispatch views
const dispatchDaySeparatorPlugin = {
    id: 'dispatchDaySeparatorPlugin',
    beforeDatasetsDraw(chart) {
        const records = chart.config.options.plugins?.dispatchDaySeparatorPlugin?.records || [];
        if (records.length <= 24) return;

        const { ctx, chartArea, scales } = chart;
        const xScale = scales.x;
        if (!chartArea || !xScale) return;

        ctx.save();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.14)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);

        records.forEach((rec, idx) => {
            if (idx > 0 && rec.hour === 0) {
                const x = xScale.getPixelForValue(idx);
                if (x >= chartArea.left && x <= chartArea.right) {
                    ctx.beginPath();
                    ctx.moveTo(x, chartArea.top);
                    ctx.lineTo(x, chartArea.bottom);
                    ctx.stroke();
                }
            }
        });
        ctx.restore();
    }
};

// Chart 3 - Multi-Day High-Resolution Hourly Dispatch & Price Overlay
function updateHourlyDispatchChart() {
    const canvas = document.getElementById('chart-hourly-dispatch');
    const allHourly = dashboardData?.high_res_30d?.hourly_data;
    if (!canvas || !allHourly || !allHourly.length) return;
    const ctx = canvas.getContext('2d');

    const total = allHourly.length;
    const span = getEffectiveSpanHourlySlots(total);
    if (dispatchExplorerState.endIndex === null || dispatchExplorerState.endIndex > total) {
        dispatchExplorerState.endIndex = total;
    }
    const endIdx = Math.max(span, dispatchExplorerState.endIndex);
    const startIdx = Math.max(0, endIdx - span);
    dispatchExplorerState.endIndex = endIdx;

    const windowRecords = allHourly.slice(startIdx, endIdx);
    if (!windowRecords.length) return;

    const firstRec = windowRecords[0];
    const lastRec = windowRecords[windowRecords.length - 1];
    const isLatestWindow = (endIdx === total);
    const spanDays = span / 24;

    // Keep sidebar dropdown synced to the window's ending date (or starting date if single day)
    const syncDate = (span <= 24) ? firstRec.date : lastRec.date;
    if (dispatchDaySelect && dispatchDaySelect.value !== syncDate) {
        const hasOpt = Array.from(dispatchDaySelect.options).some(o => o.value === syncDate);
        if (hasOpt) dispatchDaySelect.value = syncDate;
    }

    // Compute current Swedish Tariff parameters from UI sliders & Price Component Toggles
    syncDispatchPriceComponentButtonsUI();
    const rawEnergiskattOre = parseFloat(energiskattInput ? energiskattInput.value : 42.8) || 42.8;
    const rawEemTransferOre = parseFloat(eemTransferInput ? eemTransferInput.value : 17.6) || 17.6;
    const energiskattOre = dispatchPriceComponents.energiskatt ? rawEnergiskattOre : 0.0;
    const eemTransferOre = dispatchPriceComponents.transfer ? rawEemTransferOre : 0.0;
    const tibberMarkupOre = dispatchPriceComponents.markup ? 2.0 : 0.0;
    const activeMomsRate = dispatchPriceComponents.moms ? MOMS_RATE : 0.0;

    // Build human-readable summary of active tax & fee add-ons per imported kWh
    const activeAddOnExVatOre = energiskattOre + eemTransferOre + tibberMarkupOre;
    const activeCompNames = [];
    if (dispatchPriceComponents.energiskatt) activeCompNames.push(`Tax ${energiskattOre.toFixed(1)}ö`);
    if (dispatchPriceComponents.transfer) activeCompNames.push(`Transfer ${eemTransferOre.toFixed(1)}ö`);
    if (dispatchPriceComponents.markup) activeCompNames.push('Markup 2.0ö');
    if (dispatchPriceComponents.moms) activeCompNames.push('+25% Moms');
    const activeCompSummaryStr = activeCompNames.length ? activeCompNames.join(' + ') : 'Pure Nord Pool Spot Only (0 Add-Ons)';

    // Calculate hourly price & cost series for every hour in the active window:
    // 1. Nord Pool Spot Price (öre/kWh): Raw wholesale spot price (always shown as base reference)
    // 2. Grid Buy Price (öre/kWh): Nord Pool Spot + currently toggled taxes, transfer fees & VAT
    //    (When all add-ons are toggled OFF, Grid Buy Price still equals the raw Nord Pool Spot Price!)
    // 3. My Effective Price (öre/kWh consumed): What your consumed electricity actually cost you per kWh.
    //    You ONLY pay Grid Buy Price (including the toggled taxes & transfer fees) when you actually import/buy electricity from the grid!
    //    When Solar PV or Battery covers 100% of your household load (importKwh === 0), your cost is 0 öre/kWh.
    const hourlyPriceDetails = windowRecords.map(h => {
        const spotOre = h.spot_price_ore ?? 0;
        const loadKwh = h.load_power_kw ?? h.consumed_kw ?? 0;
        const importKwh = h.grid_import_kw ?? 0;
        const exportKwh = h.grid_export_kw ?? 0;

        // Grid Buy Price per kWh = (Nord Pool Spot + active tax/transfer/markup) * (1 + active VAT)
        const gridBuyPriceOre = (spotOre + activeAddOnExVatOre) * (1.0 + activeMomsRate);
        const taxAndFeesBurdenPerImportKwhOre = gridBuyPriceOre - spotOre;

        // Baseline Grid Cost if all household load was bought from the grid at Grid Buy Price
        const baselineGridCostSek = (loadKwh * gridBuyPriceOre) / 100.0;
        // Actual Purchase Cost for the electricity actually bought from the grid in this hour
        const actualImportCostSek = (importKwh * gridBuyPriceOre) / 100.0;
        const hourlySavingsSek = baselineGridCostSek - actualImportCostSek;

        // My Effective Price per kWh of household load consumed:
        // Only affected by Grid Buy Price (and its tax/fee components) in hours where you actually buy electricity (importKwh > 0)!
        const myEffectivePriceOre = (loadKwh > 0.001 && importKwh > 0.0001)
            ? ((importKwh * gridBuyPriceOre) / loadKwh)
            : (importKwh > 0.0001 ? gridBuyPriceOre : 0.0);

        const priceDiffVsGridBuyOre = myEffectivePriceOre - gridBuyPriceOre;
        const priceDiffVsRawSpotOre = myEffectivePriceOre - spotOre;

        return {
            spotOre: Number(spotOre.toFixed(2)),
            gridBuyPriceOre: Number(gridBuyPriceOre.toFixed(2)),
            taxAndFeesBurdenPerImportKwhOre: Number(taxAndFeesBurdenPerImportKwhOre.toFixed(2)),
            myEffectivePriceOre: Number(myEffectivePriceOre.toFixed(2)),
            priceDiffVsGridBuyOre: Number(priceDiffVsGridBuyOre.toFixed(2)),
            priceDiffVsRawSpotOre: Number(priceDiffVsRawSpotOre.toFixed(2)),
            baselineGridCostSek: Number(baselineGridCostSek.toFixed(2)),
            actualNetCostSek: Number(actualImportCostSek.toFixed(2)),
            hourlySavingsSek: Number(hourlySavingsSek.toFixed(2)),
            loadKwh,
            importKwh,
            exportKwh
        };
    });

    // Lock the Y-axis bounds across the FULL possible range (including all-in taxes & 25% VAT)
    // so toggling price components OR hiding/showing any curve NEVER causes the Y-axis to rescale or lines to jump!
    const maxPossibleAddOnExVat = rawEnergiskattOre + rawEemTransferOre + 2.0;
    const allPriceValues = [0];
    hourlyPriceDetails.forEach(d => {
        const fullAllInGridOre = (d.spotOre + maxPossibleAddOnExVat) * (1.0 + MOMS_RATE);
        allPriceValues.push(d.spotOre, d.gridBuyPriceOre, d.myEffectivePriceOre, fullAllInGridOre);
    });
    const rawMinPrice = Math.min(...allPriceValues);
    const rawMaxPrice = Math.max(...allPriceValues);
    const fixedPriceAxisMin = rawMinPrice < 0 ? Math.floor(rawMinPrice / 10) * 10 : 0;
    const fixedPriceAxisMax = Math.max(50, Math.ceil((rawMaxPrice * 1.05) / 20) * 20);

    const allPowerValues = [0];
    windowRecords.forEach(h => {
        const pv = h.pv_power_kw ?? h.produced_kw ?? 0;
        const ld = h.load_power_kw ?? h.consumed_kw ?? 0;
        const bt = h.battery_power_kw ?? ((h.battery_discharged_kw || 0) - (h.battery_charged_kw || 0));
        allPowerValues.push(pv, ld, bt);
    });
    const rawMinPower = Math.min(...allPowerValues);
    const rawMaxPower = Math.max(...allPowerValues);
    const fixedPowerAxisMin = rawMinPower < 0 ? Math.floor(rawMinPower * 2) / 2 : 0;
    const fixedPowerAxisMax = Math.max(2, Math.ceil(rawMaxPower * 2) / 2);

    // Compute window summary metrics
    const totPvKwh = windowRecords.reduce((acc, h) => acc + (h.pv_power_kw ?? h.produced_kw ?? 0), 0);
    const totLoadKwh = windowRecords.reduce((acc, h) => acc + (h.load_power_kw ?? h.consumed_kw ?? 0), 0);
    const avgSpotOre = windowRecords.reduce((acc, h) => acc + (h.spot_price_ore ?? 0), 0) / windowRecords.length;
    const totGridBaselineSek = hourlyPriceDetails.reduce((acc, d) => acc + d.baselineGridCostSek, 0);
    const totActualCostSek = hourlyPriceDetails.reduce((acc, d) => acc + d.actualNetCostSek, 0);
    const totWindowSavingsSek = totGridBaselineSek - totActualCostSek;
    const avgGridBuyOre = totLoadKwh > 0 ? ((totGridBaselineSek * 100.0) / totLoadKwh) : 0;
    const avgMyEffectiveOre = totLoadKwh > 0 ? ((totActualCostSek * 100.0) / totLoadKwh) : 0;

    const daysList = dashboardData.high_res_30d.days_list || [];
    const firstDayInfo = daysList.find(d => d.date === firstRec.date);
    const lastDayInfo = daysList.find(d => d.date === lastRec.date);
    const firstDateLabel = firstDayInfo ? firstDayInfo.display_name : firstRec.date;
    const lastDateLabel = lastDayInfo ? lastDayInfo.display_name : lastRec.date;
    const firstHourStr = `${String(firstRec.hour).padStart(2, '0')}:00`;
    const lastHourEndStr = `${String(lastRec.hour + 1).padStart(2, '0')}:00`;

    // Update Heading & Badge
    if (dispatchChartHeading) {
        const spanTitle = span === 24 ? '24h' : (span % 24 === 0 ? `${span / 24}-Day (${span}h)` : `${span}h`);
        dispatchChartHeading.innerText = `${spanTitle} High-Resolution Dispatch & Price Comparison`;
    }
    if (dispatchWindowBadge) {
        const spanDatesLabel = (firstRec.date === lastRec.date)
            ? firstDateLabel
            : `${firstDateLabel} → ${lastDateLabel}`;
        if (isLatestWindow) {
            dispatchWindowBadge.className = 'badge badge-success';
            dispatchWindowBadge.innerHTML = `<i class="fa-solid fa-calendar-check"></i> ${spanDatesLabel} • Latest Data`;
        } else {
            dispatchWindowBadge.className = 'badge badge-accent';
            dispatchWindowBadge.innerHTML = `<i class="fa-solid fa-calendar-day"></i> ${spanDatesLabel}`;
        }
    }

    if (dispatchChartSubtitle) {
        const rangeText = (firstRec.date === lastRec.date)
            ? `${firstDateLabel} (${firstHourStr}–${lastHourEndStr})`
            : `${firstDateLabel} ${firstHourStr} → ${lastDateLabel} ${lastHourEndStr} (${windowRecords.length}h)`;
        dispatchChartSubtitle.innerText =
            `${rangeText} | PV: ${totPvKwh.toFixed(1)} kWh | Load: ${totLoadKwh.toFixed(1)} kWh | Spot Avg: ${avgSpotOre.toFixed(1)} öre | Grid Price Avg: ${avgGridBuyOre.toFixed(1)} öre vs My Price Avg: ${avgMyEffectiveOre.toFixed(1)} öre (Saved ${totWindowSavingsSek >= 0 ? '+' : ''}${totWindowSavingsSek.toFixed(2)} SEK)`;
    }

    updatePresetButtonsState();

    // Append a 24:00 (end-of-last-hour) closing boundary point so the 23:00–24:00 hour span is drawn across the full 24h width!
    const labels = windowRecords.map(h => {
        const hrStr = `${String(h.hour).padStart(2, '0')}:00`;
        if (span <= 24 && firstRec.date === lastRec.date) {
            return hrStr;
        }
        const shortMonthDay = h.date.substring(5); // MM-DD
        return `${shortMonthDay} ${hrStr}`;
    });
    const closingLabel = (span <= 24 && firstRec.date === lastRec.date)
        ? lastHourEndStr
        : `${lastRec.date.substring(5)} ${lastHourEndStr}`;
    labels.push(closingLabel);

    const withClosingPoint = (arr) => (arr.length ? [...arr, arr[arr.length - 1]] : arr);

    const pvPower = withClosingPoint(windowRecords.map(h => h.pv_power_kw ?? h.produced_kw ?? 0));
    const loadPower = withClosingPoint(windowRecords.map(h => h.load_power_kw ?? h.consumed_kw ?? 0));
    const battPower = withClosingPoint(windowRecords.map(h => h.battery_power_kw ?? ((h.battery_discharged_kw || 0) - (h.battery_charged_kw || 0))));
    const socData = withClosingPoint(windowRecords.map(h => h.soc_pct ?? h.battery_soc_pct ?? 0));
    // The cyan Spot / Grid Price curve shows Nord Pool Spot + whichever add-ons (Energiskatt, EEM Transfer, Tibber Markup, 25% Moms) are currently toggled ON.
    // When "Pure Nord Pool Only" is clicked (all add-ons OFF), this curve shows the pure Nord Pool Spot price!
    const spotOrGridPriceData = withClosingPoint(hourlyPriceDetails.map(d => d.gridBuyPriceOre));
    const myEffectivePriceData = withClosingPoint(hourlyPriceDetails.map(d => d.myEffectivePriceOre));

    const pointRadiusVal = span <= 48 ? 2 : 0;
    const borderW = span <= 72 ? 2 : 1.5;

    const showPowerAxis = dispatchMetricVisibility.pv || dispatchMetricVisibility.load || dispatchMetricVisibility.battery;
    const showSocAxis = dispatchMetricVisibility.soc;
    const showPriceAxis = dispatchMetricVisibility.spot || dispatchMetricVisibility.myPrice;

    const spotCurveLabel = activeCompNames.length
        ? `Spot + Add-Ons Price (${activeCompSummaryStr} — öre/kWh)`
        : 'Nord Pool Spot Price (Pure Spot — öre/kWh)';

    const datasetsConfig = [
        {
            metricKey: 'pv',
            label: 'Solar PV (kW)',
            data: pvPower,
            hidden: !dispatchMetricVisibility.pv,
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245, 158, 11, 0.16)',
            borderWidth: borderW,
            pointRadius: pointRadiusVal,
            pointHoverRadius: 4,
            fill: true,
            tension: 0.25,
            yAxisID: 'yPower'
        },
        {
            metricKey: 'load',
            label: 'Household Load (kW)',
            data: loadPower,
            hidden: !dispatchMetricVisibility.load,
            borderColor: '#ef4444',
            borderWidth: borderW,
            borderDash: [4, 4],
            pointRadius: 0,
            pointHoverRadius: 4,
            fill: false,
            tension: 0.2,
            yAxisID: 'yPower'
        },
        {
            metricKey: 'battery',
            label: 'Battery Dispatch (+Dis / -Chg kW)',
            data: battPower,
            hidden: !dispatchMetricVisibility.battery,
            borderColor: '#8b5cf6',
            borderWidth: borderW,
            pointRadius: 0,
            pointHoverRadius: 4,
            fill: false,
            tension: 0.2,
            yAxisID: 'yPower'
        },
        {
            metricKey: 'soc',
            label: 'Battery SoC (%)',
            data: socData,
            hidden: !dispatchMetricVisibility.soc,
            borderColor: '#10b981',
            borderWidth: borderW,
            pointRadius: 0,
            pointHoverRadius: 4,
            fill: false,
            tension: 0.2,
            yAxisID: 'ySoc'
        },
        {
            metricKey: 'spot',
            label: spotCurveLabel,
            data: spotOrGridPriceData,
            hidden: !dispatchMetricVisibility.spot,
            borderColor: '#06b6d4',
            borderWidth: borderW + 0.6,
            borderDash: [6, 4],
            pointRadius: 0,
            pointHoverRadius: 5,
            fill: false,
            tension: 0.2,
            order: 1,
            yAxisID: 'yPrice'
        },
        {
            metricKey: 'myPrice',
            label: 'My Effective Price (öre/kWh)',
            data: myEffectivePriceData,
            hidden: !dispatchMetricVisibility.myPrice,
            borderColor: '#a3e635',
            backgroundColor: 'rgba(163, 230, 53, 0.14)',
            borderWidth: borderW + 0.4,
            pointRadius: pointRadiusVal,
            pointHoverRadius: 5,
            fill: true,
            tension: 0.2,
            order: 2,
            yAxisID: 'yPrice'
        }
    ];

    const tooltipCallbacks = {
        title: function(items) {
            if (!items.length) return '';
            const rawIdx = items[0].dataIndex;
            const clampedIdx = Math.min(windowRecords.length - 1, rawIdx);
            const rec = windowRecords[clampedIdx];
            if (!rec) return items[0].label;
            const startHr = `${String(rec.hour).padStart(2, '0')}:00`;
            const endHr = `${String(rec.hour + 1).padStart(2, '0')}:00`;
            return `${rec.date} — ${startHr} to ${endHr}`;
        },
        label: function(context) {
            const unit = context.dataset.label.includes('öre') ? 'öre/kWh' : 
                         context.dataset.label.includes('SoC') ? '%' : 'kW';
            return ` ${context.dataset.label}: ${context.parsed.y.toFixed(2)} ${unit}`;
        },
        afterBody: function(items) {
            if (!items.length) return [];
            const idx = Math.min(hourlyPriceDetails.length - 1, items[0].dataIndex);
            const d = hourlyPriceDetails[idx];
            if (!d) return [];

            const diffGridSign = d.priceDiffVsGridBuyOre > 0 ? '+' : '';
            const diffGridWord = d.priceDiffVsGridBuyOre <= 0 ? 'saved vs grid buy' : 'above grid buy';
            const diffSpotSign = d.priceDiffVsRawSpotOre > 0 ? '+' : '';
            const savSign = d.hourlySavingsSek >= 0 ? '+' : '';

            return [
                '────────────────────────────────────────',
                ` Active Tariff Add-Ons: ${activeCompSummaryStr} (+${d.taxAndFeesBurdenPerImportKwhOre.toFixed(2)} öre/kWh over Spot)`,
                ` Diff (My Price − Grid Buy Price): ${diffGridSign}${d.priceDiffVsGridBuyOre.toFixed(2)} öre/kWh (${diffGridWord})`,
                ` Diff (My Price − Raw Spot Price): ${diffSpotSign}${d.priceDiffVsRawSpotOre.toFixed(2)} öre/kWh`,
                ` Hourly Bill: ${d.actualNetCostSek.toFixed(2)} SEK vs ${d.baselineGridCostSek.toFixed(2)} SEK Grid (${savSign}${d.hourlySavingsSek.toFixed(2)} SEK saved)`
            ];
        }
    };

    // Update existing chart instance in-place to avoid full canvas teardown/re-draw from zero
    if (chartHourlyDispatchInstance) {
        chartHourlyDispatchInstance.data.labels = labels;
        chartHourlyDispatchInstance.data.datasets.length = datasetsConfig.length;
        datasetsConfig.forEach((dsCfg, i) => {
            if (chartHourlyDispatchInstance.data.datasets[i]) {
                Object.assign(chartHourlyDispatchInstance.data.datasets[i], dsCfg);
            } else {
                chartHourlyDispatchInstance.data.datasets[i] = dsCfg;
            }
            chartHourlyDispatchInstance.setDatasetVisibility(i, !dsCfg.hidden);
        });
        chartHourlyDispatchInstance.options.animation = { duration: globalAnimationsEnabled ? 350 : 0 };
        chartHourlyDispatchInstance.options.plugins.dispatchDaySeparatorPlugin.records = windowRecords;
        chartHourlyDispatchInstance.options.plugins.tooltip.callbacks = tooltipCallbacks;
        chartHourlyDispatchInstance.options.scales.yPower.display = showPowerAxis;
        chartHourlyDispatchInstance.options.scales.yPower.min = fixedPowerAxisMin;
        chartHourlyDispatchInstance.options.scales.yPower.max = fixedPowerAxisMax;
        chartHourlyDispatchInstance.options.scales.ySoc.display = showSocAxis;
        chartHourlyDispatchInstance.options.scales.yPrice.display = showPriceAxis;
        chartHourlyDispatchInstance.options.scales.yPrice.min = fixedPriceAxisMin;
        chartHourlyDispatchInstance.options.scales.yPrice.max = fixedPriceAxisMax;
        chartHourlyDispatchInstance.options.scales.yPrice.grid.drawOnChartArea = !showPowerAxis;
        chartHourlyDispatchInstance.options.scales.x.ticks.maxTicksLimit = spanDays <= 1 ? 25 : (spanDays <= 3 ? 13 : 15);
        chartHourlyDispatchInstance.update(globalAnimationsEnabled ? undefined : 'none');
        return;
    }

    chartHourlyDispatchInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasetsConfig
        },
        plugins: [dispatchDaySeparatorPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: globalAnimationsEnabled ? 400 : 0 },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                dispatchDaySeparatorPlugin: {
                    records: windowRecords
                },
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.96)',
                    borderColor: 'rgba(255, 255, 255, 0.14)',
                    borderWidth: 1,
                    padding: 12,
                    callbacks: tooltipCallbacks
                }
            },
            scales: {
                yPower: {
                    type: 'linear',
                    display: showPowerAxis,
                    position: 'left',
                    min: fixedPowerAxisMin,
                    max: fixedPowerAxisMax,
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
                    display: showSocAxis,
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
                    display: showPriceAxis,
                    position: 'right',
                    min: fixedPriceAxisMin,
                    max: fixedPriceAxisMax,
                    grid: { drawOnChartArea: !showPowerAxis },
                    ticks: { color: '#a3e635', callback: (v) => `${v} ö` },
                    title: {
                        display: true,
                        text: 'Price (öre/kWh)',
                        color: '#a3e635',
                        font: { size: 10 }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        color: '#94a3b8',
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: spanDays <= 1 ? 25 : (spanDays <= 3 ? 13 : 15)
                    }
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
    const realUnlocked = Boolean(haPkg.safety_gate?.active_control_enabled);
    const realGateStatus = haPkg.safety_gate?.status || 'LOCKED_SHADOW_MODE_ONLY';
    const gateBadge = document.getElementById('ha-safety-gate-badge');
    if (gateBadge) {
        if (realUnlocked && realGateStatus === 'UNLOCKED_ACTIVE_CONTROL') {
            gateBadge.className = 'badge badge-success';
            gateBadge.innerHTML = '<i class="fa-solid fa-shield-check"></i> REAL GATE: UNLOCKED_ACTIVE_CONTROL';
        } else if (simUnlocked) {
            gateBadge.className = 'badge badge-accent';
            gateBadge.innerHTML = `<i class="fa-solid fa-shield-halved"></i> REAL GATE: ${realGateStatus} (UI DRY-RUN PREVIEW ONLY)`;
        } else {
            gateBadge.className = 'badge badge-accent';
            gateBadge.innerHTML = `<i class="fa-solid fa-shield-halved"></i> SAFETY GATE: ${realGateStatus}`;
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
            // Always show real baked entity state; never spoof input_boolean or env gate in UI preview
            const stateVal = e.state;
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
            let gateTag = '<span class="era-tag" style="background:rgba(245,158,11,0.16);color:#fbbf24;">BLOCKED (LOCKED_SHADOW_MODE_ONLY)</span>';
            if (c.actuation_semantics === 'SHADOW_ONLY_NON_ACTUATING_PEAK_SHAVE') {
                gateTag = '<span class="era-tag" style="background:rgba(148,163,184,0.16);color:#94a3b8;">SHADOW-ONLY (NON-ACTUATING MODE 2)</span>';
            } else if (realUnlocked && c.would_actuate) {
                gateTag = '<span class="era-tag era-batt2">REAL GATE UNLOCKED (ACTIVE)</span>';
            } else if (simUnlocked) {
                gateTag = '<span class="era-tag" style="background:rgba(6,182,212,0.16);color:#38bdf8;">DRY-RUN PREVIEW (REAL GATE LOCKED)</span>';
            }

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
