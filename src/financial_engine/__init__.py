"""Financial Engine package for Swedish solar & battery ROI analysis."""

from .tariff import SwedishTariff, TariffConfig
from .baseline import (
    BaselineEngine,
    BaselineScenarioResult,
    BaselineComparisonResult,
    DEFAULT_DIURNAL_LOAD_WEIGHTS,
    DEFAULT_DIURNAL_SOLAR_WEIGHTS,
    DEFAULT_DIURNAL_BATTERY_IMPORT_WEIGHTS,
    DEFAULT_DIURNAL_BATTERY_ACTIVE_IMPORT_WEIGHTS,
    DEFAULT_DIURNAL_BATTERY_LOW_SOLAR_IMPORT_WEIGHTS,
    DEFAULT_DIURNAL_BATTERY_EXPORT_WEIGHTS,
    DEFAULT_DIURNAL_NIGHT_GRID_CHARGE_WEIGHTS,
    DEFAULT_DIURNAL_BATTERY_CHARGE_WEIGHTS,
    DEFAULT_DIURNAL_BATTERY_DISCHARGE_WEIGHTS,
)
from .calculator_2025 import (
    Year2025Calculator,
    AnnualFinancialReport,
    MonthlyFinancialLedger,
    DailyFinancialRecord,
    CapexPaybackMetrics,
)
from .multi_res import (
    HourlyEnergyRecord,
    MatchedHourlyInterval,
    SonnenHourlyIngestor,
    ResolutionMatcher,
)
from .analyzer_30d import (
    HighResAnalyzer,
    HighRes30DayReport,
    HighResScenarioSummary,
    VarianceAnalysisReport,
    VarianceMetric,
)

from .multi_year import (
    HistoricalYearCalculator,
    MultiYearEngine,
    HardwareEra,
    DEFAULT_HARDWARE_ERAS,
)
from .solar_ingestor import (
    SMAInverterIngestor,
    EEMMeterIngestor,
    SolarEraSynthesizer,
    SolarEraMetrics,
)
from .tariff_audit import (
    AuditedEEMTariffSchedule,
    DEFAULT_AUDITED_EEM_SCHEDULES,
    EEMBillingRecord,
    EEMYearlyCostsIngestor,
    MonthlyTariffAuditRecord,
    UtilityTariffAuditReport,
    UtilityTariffAuditor,
)

__all__ = [
    # Tariffs
    "SwedishTariff",
    "TariffConfig",
    # Baseline Engine
    "BaselineEngine",
    "BaselineScenarioResult",
    "BaselineComparisonResult",
    "DEFAULT_DIURNAL_LOAD_WEIGHTS",
    "DEFAULT_DIURNAL_SOLAR_WEIGHTS",
    "DEFAULT_DIURNAL_BATTERY_IMPORT_WEIGHTS",
    "DEFAULT_DIURNAL_BATTERY_ACTIVE_IMPORT_WEIGHTS",
    "DEFAULT_DIURNAL_BATTERY_LOW_SOLAR_IMPORT_WEIGHTS",
    "DEFAULT_DIURNAL_BATTERY_EXPORT_WEIGHTS",
    "DEFAULT_DIURNAL_NIGHT_GRID_CHARGE_WEIGHTS",
    "DEFAULT_DIURNAL_BATTERY_CHARGE_WEIGHTS",
    "DEFAULT_DIURNAL_BATTERY_DISCHARGE_WEIGHTS",
    # 2025 Annual Calculator
    "Year2025Calculator",
    "AnnualFinancialReport",
    "MonthlyFinancialLedger",
    "DailyFinancialRecord",
    "CapexPaybackMetrics",
    # Multi-Year Engine
    "HistoricalYearCalculator",
    "MultiYearEngine",
    "HardwareEra",
    "DEFAULT_HARDWARE_ERAS",
    # Solar Era Ingestion
    "SMAInverterIngestor",
    "EEMMeterIngestor",
    "SolarEraSynthesizer",
    "SolarEraMetrics",
    # Utility Tariff Audit
    "AuditedEEMTariffSchedule",
    "DEFAULT_AUDITED_EEM_SCHEDULES",
    "EEMBillingRecord",
    "EEMYearlyCostsIngestor",
    "MonthlyTariffAuditRecord",
    "UtilityTariffAuditReport",
    "UtilityTariffAuditor",
    # Multi-Resolution & Ingestion
    "HourlyEnergyRecord",
    "MatchedHourlyInterval",
    "SonnenHourlyIngestor",
    "ResolutionMatcher",
    # 30-Day High-Resolution Analyzer
    "HighResAnalyzer",
    "HighRes30DayReport",
    "HighResScenarioSummary",
    "VarianceAnalysisReport",
    "VarianceMetric",
]
