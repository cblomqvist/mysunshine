"""3-Way Comparative Baseline Engine for Solar and Battery Economics.

Compares:
1. Baseline 1: No Solar, No Battery (100% grid import for all household load)
2. Baseline 2: Solar Only (Direct self-consumption capped at instant load, excess exported)
3. Actual System: Solar + SonnenBatterie 10 (Realized grid purchase & feed-in)

Calculates the isolated marginal value of the battery storage system.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from .tariff import SwedishTariff


# Standard residential diurnal load weights (normalized sum = 1.0)
# Reflects Swedish single-family home with morning & evening peaks
_RAW_LOAD_WEIGHTS = [
    0.028, 0.026, 0.025, 0.026, 0.030, 0.038,  # 00:00 - 05:00 (Night base)
    0.052, 0.060, 0.054, 0.045, 0.040, 0.039,  # 06:00 - 11:00 (Morning peak)
    0.038, 0.037, 0.039, 0.044, 0.055, 0.066,  # 12:00 - 17:00 (Afternoon ramp)
    0.072, 0.068, 0.058, 0.048, 0.038, 0.032   # 18:00 - 23:00 (Evening peak)
]
_LOAD_SUM = sum(_RAW_LOAD_WEIGHTS)
DEFAULT_DIURNAL_LOAD_WEIGHTS = [w / _LOAD_SUM for w in _RAW_LOAD_WEIGHTS]

# Standard solar generation diurnal bell curve (normalized sum = 1.0)
_RAW_SOLAR_WEIGHTS = [
    0.000, 0.000, 0.000, 0.000, 0.002, 0.012,  # 00:00 - 05:00
    0.035, 0.068, 0.105, 0.135, 0.155, 0.160,  # 06:00 - 11:00 (Ramp to noon)
    0.150, 0.125, 0.095, 0.062, 0.035, 0.015,  # 12:00 - 17:00 (Afternoon drop)
    0.003, 0.000, 0.000, 0.000, 0.000, 0.000   # 18:00 - 23:00
]
_SOLAR_SUM = sum(_RAW_SOLAR_WEIGHTS)
DEFAULT_DIURNAL_SOLAR_WEIGHTS = [w / _SOLAR_SUM for w in _RAW_SOLAR_WEIGHTS]

# Empirical battery-era diurnal grid export weights calibrated from 121-day continuous
# high-resolution Sonnen dataset (2,905 hours, 2026-07-16 through 2026-11-13).
# Morning solar (05:00-08:00) charges the battery first; grid overflow peaks 09:00-14:00.
_RAW_BATTERY_EXPORT_WEIGHTS = [
    0.0007, 0.0007, 0.0005, 0.0006, 0.0006, 0.0010,  # 00:00 - 05:00
    0.0028, 0.0095, 0.0471, 0.1102, 0.1555, 0.1780,  # 06:00 - 11:00
    0.1679, 0.1491, 0.1023, 0.0446, 0.0128, 0.0066,  # 12:00 - 17:00
    0.0034, 0.0017, 0.0015, 0.0011, 0.0009, 0.0008   # 18:00 - 23:00
]
_BATT_EXP_SUM = sum(_RAW_BATTERY_EXPORT_WEIGHTS)
DEFAULT_DIURNAL_BATTERY_EXPORT_WEIGHTS = [w / _BATT_EXP_SUM for w in _RAW_BATTERY_EXPORT_WEIGHTS]

# Empirical battery-era overall diurnal grid import weights (2,905 hours, 2026-07-16 to 2026-11-13)
_RAW_BATTERY_IMPORT_WEIGHTS = [
    0.0416, 0.0400, 0.0416, 0.0471, 0.0479, 0.0451,  # 00:00 - 05:00
    0.0518, 0.0481, 0.0399, 0.0309, 0.0226, 0.0205,  # 06:00 - 11:00
    0.0242, 0.0186, 0.0224, 0.0290, 0.0365, 0.0425,  # 12:00 - 17:00
    0.0580, 0.0538, 0.0584, 0.0681, 0.0625, 0.0490   # 18:00 - 23:00
]
_BATT_IMP_SUM = sum(_RAW_BATTERY_IMPORT_WEIGHTS)
DEFAULT_DIURNAL_BATTERY_IMPORT_WEIGHTS = [w / _BATT_IMP_SUM for w in _RAW_BATTERY_IMPORT_WEIGHTS]

# Empirical grid import weights on active battery-cycling days (battery_discharged >= 25% of load, 101 days)
_RAW_BATTERY_ACTIVE_IMPORT_WEIGHTS = [
    0.0491, 0.0481, 0.0491, 0.0598, 0.0622, 0.0617,  # 00:00 - 05:00
    0.0650, 0.0495, 0.0409, 0.0337, 0.0257, 0.0218,  # 06:00 - 11:00
    0.0214, 0.0134, 0.0124, 0.0149, 0.0206, 0.0246,  # 12:00 - 17:00
    0.0541, 0.0301, 0.0432, 0.0633, 0.0690, 0.0665   # 18:00 - 23:00
]
_BATT_ACT_IMP_SUM = sum(_RAW_BATTERY_ACTIVE_IMPORT_WEIGHTS)
DEFAULT_DIURNAL_BATTERY_ACTIVE_IMPORT_WEIGHTS = [
    w / _BATT_ACT_IMP_SUM for w in _RAW_BATTERY_ACTIVE_IMPORT_WEIGHTS
]

# Empirical grid import weights on low-solar / winter days (battery_discharged < 25% of load, 20 days)
_RAW_BATTERY_LOW_SOLAR_IMPORT_WEIGHTS = [
    0.0371, 0.0350, 0.0371, 0.0393, 0.0391, 0.0349,  # 00:00 - 05:00
    0.0436, 0.0473, 0.0393, 0.0292, 0.0207, 0.0197,  # 06:00 - 11:00
    0.0259, 0.0218, 0.0285, 0.0376, 0.0462, 0.0535,  # 12:00 - 17:00
    0.0603, 0.0683, 0.0677, 0.0711, 0.0585, 0.0384   # 18:00 - 23:00
]
_BATT_LOW_IMP_SUM = sum(_RAW_BATTERY_LOW_SOLAR_IMPORT_WEIGHTS)
DEFAULT_DIURNAL_BATTERY_LOW_SOLAR_IMPORT_WEIGHTS = [
    w / _BATT_LOW_IMP_SUM for w in _RAW_BATTERY_LOW_SOLAR_IMPORT_WEIGHTS
]

# Winter night-trough grid pre-charging profile (00:00 - 05:00) for grid-to-battery arbitrage days
_RAW_NIGHT_GRID_CHARGE_WEIGHTS = [
    0.10, 0.22, 0.26, 0.24, 0.14, 0.04,              # 00:00 - 05:00 (Night trough)
    0.00, 0.00, 0.00, 0.00, 0.00, 0.00,              # 06:00 - 11:00
    0.00, 0.00, 0.00, 0.00, 0.00, 0.00,              # 12:00 - 17:00
    0.00, 0.00, 0.00, 0.00, 0.00, 0.00               # 18:00 - 23:00
]
_NIGHT_CHG_SUM = sum(_RAW_NIGHT_GRID_CHARGE_WEIGHTS)
DEFAULT_DIURNAL_NIGHT_GRID_CHARGE_WEIGHTS = [
    w / _NIGHT_CHG_SUM for w in _RAW_NIGHT_GRID_CHARGE_WEIGHTS
]

# Empirical battery charge & discharge diurnal weights (2,905 hours, 2026-07-16 to 2026-11-13)
_RAW_BATTERY_CHARGE_WEIGHTS = [
    0.0002, 0.0003, 0.0001, 0.0002, 0.0002, 0.0084,  # 00:00 - 05:00
    0.0526, 0.1229, 0.1899, 0.1707, 0.1483, 0.1105,  # 06:00 - 11:00
    0.0798, 0.0490, 0.0283, 0.0194, 0.0104, 0.0048,  # 12:00 - 17:00
    0.0027, 0.0003, 0.0001, 0.0005, 0.0002, 0.0000   # 18:00 - 23:00
]
_BATT_CHG_SUM = sum(_RAW_BATTERY_CHARGE_WEIGHTS)
DEFAULT_DIURNAL_BATTERY_CHARGE_WEIGHTS = [w / _BATT_CHG_SUM for w in _RAW_BATTERY_CHARGE_WEIGHTS]

_RAW_BATTERY_DISCHARGE_WEIGHTS = [
    0.0464, 0.0415, 0.0408, 0.0445, 0.0455, 0.0401,  # 00:00 - 05:00
    0.0328, 0.0203, 0.0132, 0.0114, 0.0106, 0.0076,  # 06:00 - 11:00
    0.0088, 0.0109, 0.0161, 0.0218, 0.0377, 0.0576,  # 12:00 - 17:00
    0.0706, 0.0880, 0.1036, 0.0922, 0.0780, 0.0601   # 18:00 - 23:00
]
_BATT_DIS_SUM = sum(_RAW_BATTERY_DISCHARGE_WEIGHTS)
DEFAULT_DIURNAL_BATTERY_DISCHARGE_WEIGHTS = [
    w / _BATT_DIS_SUM for w in _RAW_BATTERY_DISCHARGE_WEIGHTS
]


@dataclass
class BaselineScenarioResult:
    """Financial and energy outcome for a single scenario."""
    name: str
    consumed_kwh: float
    produced_kwh: float
    imported_kwh: float
    exported_kwh: float
    self_consumed_kwh: float
    import_cost_sek: float
    export_revenue_sek: float
    fixed_cost_sek: float
    net_cost_sek: float
    savings_sek: float  # Savings relative to Baseline 1 (No Solar)


@dataclass
class BaselineComparisonResult:
    """Comprehensive 3-way comparative financial and energy summary."""
    baseline_no_solar: BaselineScenarioResult
    baseline_solar_only: BaselineScenarioResult
    actual_system: BaselineScenarioResult

    # Value Partitioning
    total_savings_sek: float           # Actual vs No Solar
    solar_contribution_sek: float      # Solar Only vs No Solar
    battery_marginal_value_sek: float  # Actual Savings - Solar Only Savings

    # Battery Diagnostics
    battery_charged_kwh: float
    battery_discharged_kwh: float
    battery_roundtrip_efficiency: float
    battery_net_throughput_kwh: float

    # Self-Consumption Metrics
    solar_only_self_consumption_pct: float
    actual_self_consumption_pct: float


class BaselineEngine:
    """Evaluates comparative energy flows and calculates financial baselines."""

    def __init__(
        self,
        tariff: Optional[SwedishTariff] = None,
        load_weights: Optional[List[float]] = None,
        solar_weights: Optional[List[float]] = None,
    ):
        self.tariff = tariff or SwedishTariff()
        self.load_weights = load_weights or DEFAULT_DIURNAL_LOAD_WEIGHTS
        self.solar_weights = solar_weights or DEFAULT_DIURNAL_SOLAR_WEIGHTS

        # Normalize weights
        load_sum = sum(self.load_weights)
        self.load_weights = [w / load_sum for w in self.load_weights]
        solar_sum = sum(self.solar_weights)
        self.solar_weights = [w / solar_sum for w in self.solar_weights]

    def disaggregate_daily_solar_only(
        self,
        daily_consumed_kwh: float,
        daily_produced_kwh: float,
    ) -> Tuple[float, float, float]:
        """Disaggregate daily total consumption and production into 24-hour steps

        to compute realistic instant solar self-consumption, export, and import
        for a system without a battery.

        Returns:
            (self_consumed_kwh, exported_kwh, imported_kwh)
        """
        self_consumed = 0.0
        exported = 0.0
        imported = 0.0

        for h in range(24):
            load_h = daily_consumed_kwh * self.load_weights[h]
            pv_h = daily_produced_kwh * self.solar_weights[h]

            instant_sc = min(pv_h, load_h)
            instant_exp = max(0.0, pv_h - load_h)
            instant_imp = max(0.0, load_h - pv_h)

            self_consumed += instant_sc
            exported += instant_exp
            imported += instant_imp

        return self_consumed, exported, imported

    def disaggregate_daily_actual_battery(
        self,
        daily_consumed_kwh: float,
        daily_produced_kwh: float,
        actual_imported_kwh: float,
        actual_exported_kwh: float,
        battery_charged_kwh: float,
        battery_discharged_kwh: float,
        hours_count: int = 24,
    ) -> Tuple[List[float], List[float]]:
        """Disaggregate daily actual battery-era grid import and export into hourly steps.

        Uses empirical diurnal profiles calibrated from the 121-day (2,905-hour) continuous
        Sonnen dataset:
        - Exports follow DEFAULT_DIURNAL_BATTERY_EXPORT_WEIGHTS (morning solar charges the
          battery first; grid overflow peaks in late morning/midday 09:00-14:00).
        - Imports distinguish winter grid-to-battery night pre-charging (00:00-05:00) from
          residual household grid load, which follows DEFAULT_DIURNAL_BATTERY_ACTIVE_IMPORT_WEIGHTS
          on active battery-cycling days (battery_discharged >= 25% of load) or
          DEFAULT_DIURNAL_BATTERY_LOW_SOLAR_IMPORT_WEIGHTS on low-solar/winter days.

        Returns:
            (hourly_imports_kwh, hourly_exports_kwh) of length hours_count
        """
        if hours_count <= 0:
            return [], []

        solar_retained_kwh = max(0.0, daily_produced_kwh - actual_exported_kwh)
        grid_chg_kwh = min(
            actual_imported_kwh,
            max(0.0, battery_charged_kwh - solar_retained_kwh),
        )
        residual_imp_kwh = max(0.0, actual_imported_kwh - grid_chg_kwh)

        is_active_cycling = (
            daily_consumed_kwh > 0.0 and battery_discharged_kwh >= 0.25 * daily_consumed_kwh
        )
        res_imp_weights = (
            DEFAULT_DIURNAL_BATTERY_ACTIVE_IMPORT_WEIGHTS
            if is_active_cycling
            else DEFAULT_DIURNAL_BATTERY_LOW_SOLAR_IMPORT_WEIGHTS
        )

        raw_night_w = [DEFAULT_DIURNAL_NIGHT_GRID_CHARGE_WEIGHTS[h % 24] for h in range(hours_count)]
        raw_res_w = [res_imp_weights[h % 24] for h in range(hours_count)]
        raw_exp_w = [DEFAULT_DIURNAL_BATTERY_EXPORT_WEIGHTS[h % 24] for h in range(hours_count)]

        sum_night_w = sum(raw_night_w) or 1.0
        sum_res_w = sum(raw_res_w) or 1.0
        sum_exp_w = sum(raw_exp_w) or 1.0

        hourly_imports = [
            grid_chg_kwh * (raw_night_w[h] / sum_night_w)
            + residual_imp_kwh * (raw_res_w[h] / sum_res_w)
            for h in range(hours_count)
        ]
        hourly_exports = [
            actual_exported_kwh * (raw_exp_w[h] / sum_exp_w)
            for h in range(hours_count)
        ]

        return hourly_imports, hourly_exports

    def evaluate_daily_point(
        self,
        consumed_kwh: float,
        produced_kwh: float,
        actual_imported_kwh: float,
        actual_exported_kwh: float,
        battery_charged_kwh: float,
        battery_discharged_kwh: float,
        spot_price_sek_per_kwh: float,
        months_fraction: float = 0.0,
        date_str: Optional[str] = None,
    ) -> BaselineComparisonResult:
        """Evaluate a single daily interval (or aggregated period) with average spot price."""
        # 1. Baseline 1: No Solar, No Battery
        b1_imported = consumed_kwh
        b1_exported = 0.0
        b1_sc = 0.0
        b1_imp_cost = self.tariff.calculate_import_cost(b1_imported, spot_price_sek_per_kwh)
        b1_exp_rev = 0.0
        b1_fixed = self.tariff.calculate_fixed_costs(months_fraction)
        b1_net_cost = b1_imp_cost - b1_exp_rev + b1_fixed

        b1 = BaselineScenarioResult(
            name="Baseline 1: No Solar, No Battery",
            consumed_kwh=consumed_kwh,
            produced_kwh=0.0,
            imported_kwh=b1_imported,
            exported_kwh=b1_exported,
            self_consumed_kwh=b1_sc,
            import_cost_sek=b1_imp_cost,
            export_revenue_sek=b1_exp_rev,
            fixed_cost_sek=b1_fixed,
            net_cost_sek=b1_net_cost,
            savings_sek=0.0,
        )

        # 2. Baseline 2: Solar Only (No Battery)
        b2_sc, b2_exported, b2_imported = self.disaggregate_daily_solar_only(
            consumed_kwh, produced_kwh
        )
        b2_imp_cost = self.tariff.calculate_import_cost(b2_imported, spot_price_sek_per_kwh)
        b2_exp_rev = self.tariff.calculate_export_revenue(
            b2_exported, spot_price_sek_per_kwh, date_str=date_str
        )
        b2_fixed = self.tariff.calculate_fixed_costs(months_fraction)
        b2_net_cost = b2_imp_cost - b2_exp_rev + b2_fixed
        b2_savings = b1_net_cost - b2_net_cost

        b2 = BaselineScenarioResult(
            name="Baseline 2: Solar Only",
            consumed_kwh=consumed_kwh,
            produced_kwh=produced_kwh,
            imported_kwh=b2_imported,
            exported_kwh=b2_exported,
            self_consumed_kwh=b2_sc,
            import_cost_sek=b2_imp_cost,
            export_revenue_sek=b2_exp_rev,
            fixed_cost_sek=b2_fixed,
            net_cost_sek=b2_net_cost,
            savings_sek=b2_savings,
        )

        # 3. Actual System: Solar + SonnenBatterie 10
        act_sc = max(0.0, produced_kwh - actual_exported_kwh)
        act_imp_cost = self.tariff.calculate_import_cost(actual_imported_kwh, spot_price_sek_per_kwh)
        act_exp_rev = self.tariff.calculate_export_revenue(
            actual_exported_kwh, spot_price_sek_per_kwh, date_str=date_str
        )
        act_fixed = self.tariff.calculate_fixed_costs(months_fraction)
        act_net_cost = act_imp_cost - act_exp_rev + act_fixed
        act_savings = b1_net_cost - act_net_cost

        act = BaselineScenarioResult(
            name="Actual: Solar + SonnenBatterie 10",
            consumed_kwh=consumed_kwh,
            produced_kwh=produced_kwh,
            imported_kwh=actual_imported_kwh,
            exported_kwh=actual_exported_kwh,
            self_consumed_kwh=act_sc,
            import_cost_sek=act_imp_cost,
            export_revenue_sek=act_exp_rev,
            fixed_cost_sek=act_fixed,
            net_cost_sek=act_net_cost,
            savings_sek=act_savings,
        )

        # Battery metrics
        marginal_battery_val = act_savings - b2_savings
        battery_eff = (
            (battery_discharged_kwh / battery_charged_kwh * 100.0)
            if battery_charged_kwh > 0
            else 0.0
        )
        b2_sc_pct = (b2_sc / produced_kwh * 100.0) if produced_kwh > 0 else 0.0
        act_sc_pct = (act_sc / produced_kwh * 100.0) if produced_kwh > 0 else 0.0

        return BaselineComparisonResult(
            baseline_no_solar=b1,
            baseline_solar_only=b2,
            actual_system=act,
            total_savings_sek=act_savings,
            solar_contribution_sek=b2_savings,
            battery_marginal_value_sek=marginal_battery_val,
            battery_charged_kwh=battery_charged_kwh,
            battery_discharged_kwh=battery_discharged_kwh,
            battery_roundtrip_efficiency=battery_eff,
            battery_net_throughput_kwh=battery_charged_kwh + battery_discharged_kwh,
            solar_only_self_consumption_pct=b2_sc_pct,
            actual_self_consumption_pct=act_sc_pct,
        )
