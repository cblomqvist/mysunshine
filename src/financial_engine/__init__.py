"""Financial Engine package for Swedish solar & battery ROI analysis."""

from .tariff import SwedishTariff, TariffConfig
from .baseline import (
    BaselineEngine,
    BaselineScenarioResult,
    BaselineComparisonResult,
    DEFAULT_DIURNAL_LOAD_WEIGHTS,
    DEFAULT_DIURNAL_SOLAR_WEIGHTS,
)
from .calculator_2025 import (
    Year2025Calculator,
    AnnualFinancialReport,
    MonthlyFinancialLedger,
    DailyFinancialRecord,
    CapexPaybackMetrics,
)

__all__ = [
    "SwedishTariff",
    "TariffConfig",
    "BaselineEngine",
    "BaselineScenarioResult",
    "BaselineComparisonResult",
    "DEFAULT_DIURNAL_LOAD_WEIGHTS",
    "DEFAULT_DIURNAL_SOLAR_WEIGHTS",
    "Year2025Calculator",
    "AnnualFinancialReport",
    "MonthlyFinancialLedger",
    "DailyFinancialRecord",
    "CapexPaybackMetrics",
]
