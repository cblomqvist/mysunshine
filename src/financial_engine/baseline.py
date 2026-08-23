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
DEFAULT_DIURNAL_LOAD_WEIGHTS = [
    0.028, 0.026, 0.025, 0.026, 0.030, 0.038,  # 00:00 - 05:00 (Night base)
    0.052, 0.060, 0.054, 0.045, 0.040, 0.039,  # 06:00 - 11:00 (Morning peak)
    0.038, 0.037, 0.039, 0.044, 0.055, 0.066,  # 12:00 - 17:00 (Afternoon ramp)
    0.072, 0.068, 0.058, 0.048, 0.038, 0.032   # 18:00 - 23:00 (Evening peak)
]

# Standard solar generation diurnal bell curve (normalized sum = 1.0)
DEFAULT_DIURNAL_SOLAR_WEIGHTS = [
    0.000, 0.000, 0.000, 0.000, 0.002, 0.012,  # 00:00 - 05:00
    0.035, 0.068, 0.105, 0.135, 0.155, 0.160,  # 06:00 - 11:00 (Ramp to noon)
    0.150, 0.125, 0.095, 0.062, 0.035, 0.015,  # 12:00 - 17:00 (Afternoon drop)
    0.003, 0.000, 0.000, 0.000, 0.000, 0.000   # 18:00 - 23:00
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
        b2_exp_rev = self.tariff.calculate_export_revenue(b2_exported, spot_price_sek_per_kwh)
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
        act_exp_rev = self.tariff.calculate_export_revenue(actual_exported_kwh, spot_price_sek_per_kwh)
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
