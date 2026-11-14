"""Next-Day Forecasting & Shadow Recommendation Engine package (Milestone 6)."""

from .backtester import BacktestDayRecord, BacktestSummaryReport, ShadowBacktester
from .forecaster import (
    DailyWeatherSummary,
    DayAheadHourlyPrice,
    DayAheadPriceForecaster,
    HourlyWeatherForecast,
    NextDayHourlyForecastPoint,
    NextDayScenarioProjection,
    SolarLoadForecaster,
    WeatherIrradianceProvider,
    swedish_tz_offset_hours,
    to_swedish_local,
)
from .shadow_advisor import (
    BatteryPhysicsConfig,
    DayAheadShadowPlan,
    HourlyShadowStep,
    ShadowAdvisorDayResult,
    ShadowModeAdvisor,
)

__all__ = [
    "BacktestDayRecord",
    "BacktestSummaryReport",
    "BatteryPhysicsConfig",
    "DailyWeatherSummary",
    "DayAheadHourlyPrice",
    "DayAheadPriceForecaster",
    "DayAheadShadowPlan",
    "HourlyShadowStep",
    "HourlyWeatherForecast",
    "NextDayHourlyForecastPoint",
    "NextDayScenarioProjection",
    "ShadowAdvisorDayResult",
    "ShadowBacktester",
    "ShadowModeAdvisor",
    "SolarLoadForecaster",
    "WeatherIrradianceProvider",
    "swedish_tz_offset_hours",
    "to_swedish_local",
]
