"""Dynamic Grid Pre-Charging & Arbitrage Advisor in Shadow Mode (Milestone 6.3).

Evaluates day-ahead SE3 spot price curves against predicted household load and
solar generation under the SonnenBatterie 10 (20 kWh usable, ~76.8% round-trip
efficiency) physical constraints. Enforces the round-trip efficiency gate:

    C_import(t_peak) > C_import(t_trough) / eta_roundtrip + LossMargin

Generates explicit hourly shadow dispatch recommendations (GRID_PRECHARGE,
SOLAR_CHARGE, HOLD_FOR_PEAK, PEAK_DISCHARGE, SELF_CONSUMPTION, IDLE) and
human-readable executive guidance without physical hardware actuation.
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..financial_engine.tariff import SwedishTariff
from .forecaster import NextDayHourlyForecastPoint, NextDayScenarioProjection


@dataclass
class BatteryPhysicsConfig:
    """Physical and economic parameters for the SonnenBatterie 10 (Dual 22 kWh / 20 kWh usable)."""
    usable_capacity_kwh: float = 20.0
    max_charge_kw: float = 6.5
    max_discharge_kw: float = 6.0
    roundtrip_efficiency: float = 0.768
    arbitrage_loss_margin_sek_kwh: float = 0.05

    @property
    def one_way_efficiency(self) -> float:
        return math.sqrt(self.roundtrip_efficiency)


@dataclass
class HourlyShadowStep:
    """Detailed hourly dispatch comparison between Default Self-Consumption and Shadow Advisor."""
    hour: int
    timestamp_local: str
    spot_price_ore_kwh: float
    import_price_sek_kwh: float
    export_price_sek_kwh: float
    pv_kwh: float
    load_kwh: float

    # Default Self-Consumption ("Eigenverbrauch")
    default_charged_kwh: float
    default_discharged_kwh: float
    default_soc_kwh: float
    default_soc_pct: float
    default_grid_import_kwh: float
    default_grid_export_kwh: float
    default_net_cost_sek: float

    # Shadow Advisor Dispatch
    shadow_action: str
    shadow_reason: str
    shadow_solar_charged_kwh: float
    shadow_grid_precharged_kwh: float
    shadow_total_charged_kwh: float
    shadow_discharged_kwh: float
    shadow_soc_kwh: float
    shadow_soc_pct: float
    shadow_grid_import_kwh: float
    shadow_grid_export_kwh: float
    shadow_net_cost_sek: float
    hourly_savings_delta_sek: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hour": self.hour,
            "timestamp_local": self.timestamp_local,
            "spot_price_ore_kwh": round(self.spot_price_ore_kwh, 2),
            "import_price_sek_kwh": round(self.import_price_sek_kwh, 3),
            "export_price_sek_kwh": round(self.export_price_sek_kwh, 3),
            "pv_kwh": round(self.pv_kwh, 3),
            "load_kwh": round(self.load_kwh, 3),
            "default_charged_kwh": round(self.default_charged_kwh, 3),
            "default_discharged_kwh": round(self.default_discharged_kwh, 3),
            "default_soc_kwh": round(self.default_soc_kwh, 2),
            "default_soc_pct": round(self.default_soc_pct, 1),
            "default_grid_import_kwh": round(self.default_grid_import_kwh, 3),
            "default_grid_export_kwh": round(self.default_grid_export_kwh, 3),
            "default_net_cost_sek": round(self.default_net_cost_sek, 2),
            "shadow_action": self.shadow_action,
            "shadow_reason": self.shadow_reason,
            "shadow_solar_charged_kwh": round(self.shadow_solar_charged_kwh, 3),
            "shadow_grid_precharged_kwh": round(self.shadow_grid_precharged_kwh, 3),
            "shadow_total_charged_kwh": round(self.shadow_total_charged_kwh, 3),
            "shadow_discharged_kwh": round(self.shadow_discharged_kwh, 3),
            "shadow_soc_kwh": round(self.shadow_soc_kwh, 2),
            "shadow_soc_pct": round(self.shadow_soc_pct, 1),
            "shadow_grid_import_kwh": round(self.shadow_grid_import_kwh, 3),
            "shadow_grid_export_kwh": round(self.shadow_grid_export_kwh, 3),
            "shadow_net_cost_sek": round(self.shadow_net_cost_sek, 2),
            "hourly_savings_delta_sek": round(self.hourly_savings_delta_sek, 2),
        }


@dataclass
class DayAheadShadowPlan:
    """Actionable control schedule derived from day-ahead forecast."""
    date_str: str
    grid_precharge_kwh_by_hour: List[float]
    discharge_cutoff_import_price_sek: float
    efficiency_gate_passed: bool
    cheapest_trough_hours: List[int]
    peak_target_hours: List[int]
    avg_trough_spot_ore_kwh: float
    breakeven_peak_spot_ore_kwh: float
    max_peak_spot_ore_kwh: float
    avg_peak_spot_ore_kwh: float


@dataclass
class ShadowAdvisorDayResult:
    """Complete 24-hour evaluation of the Shadow Mode Advisor and 3-way baselines."""
    date_str: str
    initial_soc_kwh: float
    final_default_soc_kwh: float
    final_shadow_soc_kwh: float

    # 4-way scenario projections
    baseline_no_solar: NextDayScenarioProjection
    baseline_solar_only: NextDayScenarioProjection
    default_self_consumption: NextDayScenarioProjection
    shadow_optimized: NextDayScenarioProjection

    # Efficiency Gate & Arbitrage Diagnostics
    efficiency_gate_passed: bool
    roundtrip_efficiency_pct: float
    loss_margin_sek_kwh: float
    cheapest_trough_window: str
    avg_trough_spot_ore_kwh: float
    avg_trough_import_sek_kwh: float
    breakeven_peak_import_sek_kwh: float
    breakeven_peak_spot_ore_kwh: float
    peak_spike_window: str
    avg_peak_spot_ore_kwh: float
    max_peak_spot_ore_kwh: float
    recommended_grid_precharge_kwh: float
    hold_hours_count: int
    peak_discharge_hours_count: int
    shadow_savings_vs_default_sek: float
    headline_recommendation: str

    plan: DayAheadShadowPlan
    hourly_steps: List[HourlyShadowStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date_str,
            "initial_soc_kwh": round(self.initial_soc_kwh, 2),
            "final_default_soc_kwh": round(self.final_default_soc_kwh, 2),
            "final_shadow_soc_kwh": round(self.final_shadow_soc_kwh, 2),
            "scenarios": {
                "baseline_no_solar": self.baseline_no_solar.to_dict(),
                "baseline_solar_only": self.baseline_solar_only.to_dict(),
                "default_self_consumption": self.default_self_consumption.to_dict(),
                "shadow_optimized": self.shadow_optimized.to_dict(),
            },
            "arbitrage_diagnostics": {
                "efficiency_gate_passed": self.efficiency_gate_passed,
                "roundtrip_efficiency_pct": round(self.roundtrip_efficiency_pct, 1),
                "loss_margin_sek_kwh": round(self.loss_margin_sek_kwh, 2),
                "cheapest_trough_window": self.cheapest_trough_window,
                "avg_trough_spot_ore_kwh": round(self.avg_trough_spot_ore_kwh, 2),
                "avg_trough_import_sek_kwh": round(self.avg_trough_import_sek_kwh, 2),
                "breakeven_peak_import_sek_kwh": round(self.breakeven_peak_import_sek_kwh, 2),
                "breakeven_peak_spot_ore_kwh": round(self.breakeven_peak_spot_ore_kwh, 2),
                "peak_spike_window": self.peak_spike_window,
                "avg_peak_spot_ore_kwh": round(self.avg_peak_spot_ore_kwh, 2),
                "max_peak_spot_ore_kwh": round(self.max_peak_spot_ore_kwh, 2),
                "recommended_grid_precharge_kwh": round(self.recommended_grid_precharge_kwh, 2),
                "hold_hours_count": self.hold_hours_count,
                "peak_discharge_hours_count": self.peak_discharge_hours_count,
                "shadow_savings_vs_default_sek": round(self.shadow_savings_vs_default_sek, 2),
                "headline_recommendation": self.headline_recommendation,
            },
            "hourly_steps": [s.to_dict() for s in self.hourly_steps],
        }


class ShadowModeAdvisor:
    """Evaluates day-ahead prices & energy forecasts to produce Shadow Mode dispatch advice."""

    def __init__(
        self,
        tariff: Optional[SwedishTariff] = None,
        physics: Optional[BatteryPhysicsConfig] = None,
    ):
        self.tariff = tariff or SwedishTariff()
        self.physics = physics or BatteryPhysicsConfig()

    def build_day_ahead_plan(
        self,
        forecast_points: Sequence[NextDayHourlyForecastPoint],
        initial_soc_kwh: float = 4.0,
    ) -> DayAheadShadowPlan:
        """Compute optimal night-trough grid pre-charging and peak-preservation discharge threshold."""
        n = len(forecast_points)
        date_str = forecast_points[0].date_str if forecast_points else "2026-11-15"
        eta_rt = self.physics.roundtrip_efficiency
        eta_one = self.physics.one_way_efficiency
        cap = self.physics.usable_capacity_kwh
        max_chg = self.physics.max_charge_kw
        max_dis = self.physics.max_discharge_kw
        loss_margin = self.physics.arbitrage_loss_margin_sek_kwh

        c_imp = [pt.import_price_sek_kwh for pt in forecast_points]
        p_ore = [pt.spot_price_ore_kwh for pt in forecast_points]
        surplus = [max(0.0, pt.predicted_pv_kwh - pt.predicted_load_kwh) for pt in forecast_points]
        deficit = [max(0.0, pt.predicted_load_kwh - pt.predicted_pv_kwh) for pt in forecast_points]

        # Expected chemical energy added from free daytime solar
        exp_solar_chem = min(cap - initial_soc_kwh, sum(min(max_chg, s) * eta_one for s in surplus))
        avail_free_ac = (initial_soc_kwh + exp_solar_chem) * eta_one

        # Identify candidate night-trough charging hours (00:00 - 06:00)
        night_count = min(7, n)
        trough_candidates = sorted(range(night_count), key=lambda i: c_imp[i])
        best_trough_hours = sorted(trough_candidates[:4]) if trough_candidates else [0]
        min_trough_imp_sek = (
            sum(c_imp[i] for i in best_trough_hours[:3]) / min(3, len(best_trough_hours))
            if best_trough_hours
            else 1.0
        )
        avg_trough_spot_ore = (
            sum(p_ore[i] for i in best_trough_hours[:3]) / min(3, len(best_trough_hours))
            if best_trough_hours
            else 50.0
        )

        # Round-Trip Efficiency Gate required import price & equivalent spot price
        breakeven_imp_sek = (min_trough_imp_sek / eta_rt) + loss_margin
        fixed_var_add_sek = (
            self.tariff.config.tibber_markup_sek_per_kwh
            + self.tariff.config.energiskatt_sek_per_kwh
            + self.tariff.config.eem_transfer_fee_sek_per_kwh
        )
        breakeven_spot_sek = (breakeven_imp_sek / (1.0 + self.tariff.config.moms_rate)) - fixed_var_add_sek
        breakeven_spot_ore = max(0.0, breakeven_spot_sek * 100.0)

        # Rank all deficit hours by import price descending
        peak_def_indices = sorted(
            [i for i in range(n) if deficit[i] > 0.01],
            key=lambda i: c_imp[i],
            reverse=True,
        )
        qualifying_peak_indices = [i for i in peak_def_indices if c_imp[i] > breakeven_imp_sek]
        qualifying_peak_ac = sum(min(max_dis, deficit[i]) for i in qualifying_peak_indices)

        # How much profitable peak load is uncovered by initial SoC + solar?
        uncovered_peak_ac = max(0.0, qualifying_peak_ac - avail_free_ac)
        max_headroom_for_grid_chem = max(0.0, (cap - exp_solar_chem) - initial_soc_kwh)
        target_grid_chem = min(max_headroom_for_grid_chem, uncovered_peak_ac / eta_one)

        grid_plan = [0.0] * n
        rem_chem = target_grid_chem
        max_peak_imp = max(c_imp) if c_imp else 0.0
        used_trough_hours: List[int] = []

        for idx in trough_candidates:
            if rem_chem <= 1e-4:
                break
            if (c_imp[idx] / eta_rt) + loss_margin < max_peak_imp:
                room_ac = max(0.0, max_chg - surplus[idx])
                add_chem = min(rem_chem, room_ac * eta_one)
                if add_chem > 0.05:
                    grid_plan[idx] = add_chem / eta_one
                    rem_chem -= add_chem
                    used_trough_hours.append(idx)

        gate_passed = sum(grid_plan) >= 0.25
        if used_trough_hours:
            avg_trough_spot_ore = sum(p_ore[i] * grid_plan[i] for i in used_trough_hours) / sum(
                grid_plan[i] for i in used_trough_hours
            )

        # Determine discharge cutoff import price to reserve stored energy for top-priced deficit hours
        tot_expected_ac = min(
            cap * eta_one,
            (initial_soc_kwh + sum(grid_plan) * eta_one + exp_sol_chem_val(exp_solar_chem)) * eta_one,
        )
        cum_def = 0.0
        cutoff_imp_sek = 0.0
        target_peak_hours: List[int] = []
        for idx in peak_def_indices:
            target_peak_hours.append(idx)
            cum_def += min(max_dis, deficit[idx])
            if cum_def >= tot_expected_ac and tot_expected_ac > 0.1:
                cutoff_imp_sek = c_imp[idx] * 0.96
                break

        top_peak_hours = sorted(target_peak_hours[:6]) if target_peak_hours else [17, 18, 19]
        max_peak_ore = max(p_ore) if p_ore else 0.0
        avg_peak_ore = (
            sum(p_ore[i] for i in top_peak_hours) / len(top_peak_hours)
            if top_peak_hours
            else max_peak_ore
        )

        return DayAheadShadowPlan(
            date_str=date_str,
            grid_precharge_kwh_by_hour=grid_plan,
            discharge_cutoff_import_price_sek=cutoff_imp_sek,
            efficiency_gate_passed=gate_passed,
            cheapest_trough_hours=sorted(used_trough_hours) if used_trough_hours else best_trough_hours[:3],
            peak_target_hours=top_peak_hours,
            avg_trough_spot_ore_kwh=avg_trough_spot_ore,
            breakeven_peak_spot_ore_kwh=breakeven_spot_ore,
            max_peak_spot_ore_kwh=max_peak_ore,
            avg_peak_spot_ore_kwh=avg_peak_ore,
        )

    def evaluate_day(
        self,
        forecast_points: Sequence[NextDayHourlyForecastPoint],
        initial_soc_kwh: float = 4.0,
        plan_override: Optional[DayAheadShadowPlan] = None,
    ) -> ShadowAdvisorDayResult:
        """Simulate Default Self-Consumption vs Shadow Mode Advisor across 24 hours."""
        plan = plan_override or self.build_day_ahead_plan(forecast_points, initial_soc_kwh=initial_soc_kwh)
        n = len(forecast_points)
        date_str = forecast_points[0].date_str if forecast_points else "2026-11-15"
        eta_rt = self.physics.roundtrip_efficiency
        eta_one = self.physics.one_way_efficiency
        cap = self.physics.usable_capacity_kwh
        max_chg = self.physics.max_charge_kw
        max_dis = self.physics.max_discharge_kw

        fixed_daily_sek = self.tariff.calculate_fixed_costs(1.0 / 30.4375)

        # Compute exact priority discharge allocations when evaluating with known forecast points
        c_imp = [pt.import_price_sek_kwh for pt in forecast_points]
        surplus = [max(0.0, pt.predicted_pv_kwh - pt.predicted_load_kwh) for pt in forecast_points]
        deficit = [max(0.0, pt.predicted_load_kwh - pt.predicted_pv_kwh) for pt in forecast_points]
        exp_solar_chem = min(cap - initial_soc_kwh, sum(min(max_chg, s) * eta_one for s in surplus))
        tot_avail_ac = min(
            cap * eta_one,
            (initial_soc_kwh + sum(plan.grid_precharge_kwh_by_hour) * eta_one + exp_solar_chem) * eta_one,
        )
        peak_def_indices = sorted(
            [i for i in range(n) if deficit[i] > 0.0],
            key=lambda i: c_imp[i],
            reverse=True,
        )
        allowed_dis_ac = [0.0] * n
        rem_dis = tot_avail_ac
        for idx in peak_def_indices:
            if rem_dis <= 1e-6:
                break
            alloc = min(rem_dis, max_dis, deficit[idx])
            allowed_dis_ac[idx] = alloc
            rem_dis -= alloc

        soc_def = initial_soc_kwh
        soc_shd = initial_soc_kwh

        b1_imp_cost = 0.0
        b2_imp_cost = 0.0
        b2_exp_rev = 0.0
        b2_imp_kwh = 0.0
        b2_exp_kwh = 0.0
        b2_sc_kwh = 0.0

        def_imp_cost = 0.0
        def_exp_rev = 0.0
        def_imp_kwh = 0.0
        def_exp_kwh = 0.0
        def_chg_kwh = 0.0
        def_dis_kwh = 0.0

        shd_imp_cost = 0.0
        shd_exp_rev = 0.0
        shd_imp_kwh = 0.0
        shd_exp_kwh = 0.0
        shd_chg_kwh = 0.0
        shd_dis_kwh = 0.0

        steps: List[HourlyShadowStep] = []
        hold_count = 0
        peak_dis_count = 0

        for i, pt in enumerate(forecast_points):
            pv_h = pt.predicted_pv_kwh
            ld_h = pt.predicted_load_kwh
            imp_p = pt.import_price_sek_kwh
            exp_p = pt.export_price_sek_kwh
            sur_h = surplus[i]
            def_h = deficit[i]

            # 1. Baseline 1 (No Solar)
            b1_imp_cost += ld_h * imp_p

            # 2. Baseline 2 (Solar Only)
            sc_h = min(pv_h, ld_h)
            b2_sc_kwh += sc_h
            b2_imp_kwh += def_h
            b2_exp_kwh += sur_h
            b2_imp_cost += def_h * imp_p
            b2_exp_rev += sur_h * exp_p

            # 3. Default Self-Consumption ("Eigenverbrauch")
            d_chg = min(sur_h, max_chg, max(0.0, (cap - soc_def) / eta_one))
            soc_def += d_chg * eta_one
            d_dis = min(def_h, max_dis, soc_def * eta_one)
            soc_def -= d_dis / eta_one
            d_imp = def_h - d_dis
            d_exp = sur_h - d_chg
            d_net_cost = d_imp * imp_p - d_exp * exp_p

            def_chg_kwh += d_chg
            def_dis_kwh += d_dis
            def_imp_kwh += d_imp
            def_exp_kwh += d_exp
            def_imp_cost += d_imp * imp_p
            def_exp_rev += d_exp * exp_p

            # 4. Shadow Mode Advisor
            s_sol_chg = min(sur_h, max_chg, max(0.0, (cap - soc_shd) / eta_one))
            soc_shd += s_sol_chg * eta_one

            planned_g = plan.grid_precharge_kwh_by_hour[i] if i < len(plan.grid_precharge_kwh_by_hour) else 0.0
            s_grid_chg = min(planned_g, max(0.0, max_chg - s_sol_chg), max(0.0, (cap - soc_shd) / eta_one))
            soc_shd += s_grid_chg * eta_one
            s_tot_chg = s_sol_chg + s_grid_chg

            if plan_override is not None:
                # Out-of-sample execution using cutoff price from day-ahead plan
                can_dis = (
                    (imp_p >= plan.discharge_cutoff_import_price_sek)
                    or (soc_shd >= 0.88 * cap)
                    or (pt.hour >= 21 and imp_p >= 1.15)
                ) and (s_grid_chg <= 1e-4)
                s_dis = min(def_h, max_dis, soc_shd * eta_one) if can_dis else 0.0
            else:
                s_dis = min(def_h, allowed_dis_ac[i], max_dis, soc_shd * eta_one) if s_grid_chg <= 1e-4 else 0.0

            soc_shd -= s_dis / eta_one
            s_imp = def_h - s_dis + s_grid_chg
            s_exp = sur_h - s_sol_chg
            s_net_cost = s_imp * imp_p - s_exp * exp_p

            shd_chg_kwh += s_tot_chg
            shd_dis_kwh += s_dis
            shd_imp_kwh += s_imp
            shd_exp_kwh += s_exp
            shd_imp_cost += s_imp * imp_p
            shd_exp_rev += s_exp * exp_p

            action, reason = self._classify_step_action(
                pt=pt,
                sur_h=sur_h,
                def_h=def_h,
                s_sol_chg=s_sol_chg,
                s_grid_chg=s_grid_chg,
                s_dis=s_dis,
                soc_shd=soc_shd,
                plan=plan,
            )
            if action == "HOLD_FOR_PEAK":
                hold_count += 1
            elif action == "PEAK_DISCHARGE":
                peak_dis_count += 1

            steps.append(
                HourlyShadowStep(
                    hour=pt.hour,
                    timestamp_local=pt.timestamp_local,
                    spot_price_ore_kwh=pt.spot_price_ore_kwh,
                    import_price_sek_kwh=imp_p,
                    export_price_sek_kwh=exp_p,
                    pv_kwh=pv_h,
                    load_kwh=ld_h,
                    default_charged_kwh=d_chg,
                    default_discharged_kwh=d_dis,
                    default_soc_kwh=soc_def,
                    default_soc_pct=(soc_def / cap) * 100.0,
                    default_grid_import_kwh=d_imp,
                    default_grid_export_kwh=d_exp,
                    default_net_cost_sek=d_net_cost,
                    shadow_action=action,
                    shadow_reason=reason,
                    shadow_solar_charged_kwh=s_sol_chg,
                    shadow_grid_precharged_kwh=s_grid_chg,
                    shadow_total_charged_kwh=s_tot_chg,
                    shadow_discharged_kwh=s_dis,
                    shadow_soc_kwh=soc_shd,
                    shadow_soc_pct=(soc_shd / cap) * 100.0,
                    shadow_grid_import_kwh=s_imp,
                    shadow_grid_export_kwh=s_exp,
                    shadow_net_cost_sek=s_net_cost,
                    hourly_savings_delta_sek=d_net_cost - s_net_cost,
                )
            )

        # Value any end-of-day residual stored chemical SoC difference at mean day export/replacement value
        soc_diff_chem = soc_shd - soc_def
        avg_imp_sek = sum(c_imp) / len(c_imp) if c_imp else 1.2
        terminal_soc_credit_sek = (soc_diff_chem * eta_one) * (avg_imp_sek * 0.75)

        tot_pv = sum(pt.predicted_pv_kwh for pt in forecast_points)
        tot_load = sum(pt.predicted_load_kwh for pt in forecast_points)

        b1_net = b1_imp_cost + fixed_daily_sek
        b2_net = b2_imp_cost - b2_exp_rev + fixed_daily_sek
        def_net = def_imp_cost - def_exp_rev + fixed_daily_sek
        shd_net = (shd_imp_cost - shd_exp_rev + fixed_daily_sek) - terminal_soc_credit_sek

        b1_proj = NextDayScenarioProjection(
            name="Baseline 1: No Solar, No Battery",
            produced_kwh=0.0,
            consumed_kwh=tot_load,
            imported_kwh=tot_load,
            exported_kwh=0.0,
            self_consumed_kwh=0.0,
            battery_charged_kwh=0.0,
            battery_discharged_kwh=0.0,
            import_cost_sek=b1_imp_cost,
            export_revenue_sek=0.0,
            fixed_cost_sek=fixed_daily_sek,
            net_cost_sek=b1_net,
            savings_vs_no_solar_sek=0.0,
        )
        b2_proj = NextDayScenarioProjection(
            name="Baseline 2: Solar Only (No Battery)",
            produced_kwh=tot_pv,
            consumed_kwh=tot_load,
            imported_kwh=b2_imp_kwh,
            exported_kwh=b2_exp_kwh,
            self_consumed_kwh=b2_sc_kwh,
            battery_charged_kwh=0.0,
            battery_discharged_kwh=0.0,
            import_cost_sek=b2_imp_cost,
            export_revenue_sek=b2_exp_rev,
            fixed_cost_sek=fixed_daily_sek,
            net_cost_sek=b2_net,
            savings_vs_no_solar_sek=b1_net - b2_net,
        )
        def_proj = NextDayScenarioProjection(
            name="Default Sonnen Mode (Self-Consumption)",
            produced_kwh=tot_pv,
            consumed_kwh=tot_load,
            imported_kwh=def_imp_kwh,
            exported_kwh=def_exp_kwh,
            self_consumed_kwh=max(0.0, tot_pv - def_exp_kwh),
            battery_charged_kwh=def_chg_kwh,
            battery_discharged_kwh=def_dis_kwh,
            import_cost_sek=def_imp_cost,
            export_revenue_sek=def_exp_rev,
            fixed_cost_sek=fixed_daily_sek,
            net_cost_sek=def_net,
            savings_vs_no_solar_sek=b1_net - def_net,
        )
        shd_proj = NextDayScenarioProjection(
            name="Shadow Advisor (Grid Pre-Charge + Peak Shaving)",
            produced_kwh=tot_pv,
            consumed_kwh=tot_load,
            imported_kwh=shd_imp_kwh,
            exported_kwh=shd_exp_kwh,
            self_consumed_kwh=max(0.0, tot_pv - shd_exp_kwh),
            battery_charged_kwh=shd_chg_kwh,
            battery_discharged_kwh=shd_dis_kwh,
            import_cost_sek=shd_imp_cost,
            export_revenue_sek=shd_exp_rev,
            fixed_cost_sek=fixed_daily_sek,
            net_cost_sek=shd_net,
            savings_vs_no_solar_sek=b1_net - shd_net,
        )

        trough_hrs = plan.cheapest_trough_hours
        trough_win = (
            f"{min(trough_hrs):02d}:00–{max(trough_hrs) + 1:02d}:00" if trough_hrs else "01:00–05:00"
        )
        pk_hrs = plan.peak_target_hours
        pk_win = f"{min(pk_hrs):02d}:00–{max(pk_hrs) + 1:02d}:00" if pk_hrs else "16:00–20:00"

        avg_trough_imp = self.tariff.get_import_price(plan.avg_trough_spot_ore_kwh / 100.0)
        be_imp = (avg_trough_imp / eta_rt) + self.physics.arbitrage_loss_margin_sek_kwh
        tot_grid_precharge = sum(s.shadow_grid_precharged_kwh for s in steps)
        shd_delta_sek = def_net - shd_net

        headline = self._build_headline(
            tot_grid_precharge=tot_grid_precharge,
            trough_win=trough_win,
            avg_trough_ore=plan.avg_trough_spot_ore_kwh,
            be_spot_ore=plan.breakeven_peak_spot_ore_kwh,
            pk_win=pk_win,
            max_peak_ore=plan.max_peak_spot_ore_kwh,
            hold_count=hold_count,
            shd_delta_sek=shd_delta_sek,
        )

        return ShadowAdvisorDayResult(
            date_str=date_str,
            initial_soc_kwh=initial_soc_kwh,
            final_default_soc_kwh=soc_def,
            final_shadow_soc_kwh=soc_shd,
            baseline_no_solar=b1_proj,
            baseline_solar_only=b2_proj,
            default_self_consumption=def_proj,
            shadow_optimized=shd_proj,
            efficiency_gate_passed=tot_grid_precharge >= 0.25,
            roundtrip_efficiency_pct=eta_rt * 100.0,
            loss_margin_sek_kwh=self.physics.arbitrage_loss_margin_sek_kwh,
            cheapest_trough_window=trough_win,
            avg_trough_spot_ore_kwh=plan.avg_trough_spot_ore_kwh,
            avg_trough_import_sek_kwh=avg_trough_imp,
            breakeven_peak_import_sek_kwh=be_imp,
            breakeven_peak_spot_ore_kwh=plan.breakeven_peak_spot_ore_kwh,
            peak_spike_window=pk_win,
            avg_peak_spot_ore_kwh=plan.avg_peak_spot_ore_kwh,
            max_peak_spot_ore_kwh=plan.max_peak_spot_ore_kwh,
            recommended_grid_precharge_kwh=tot_grid_precharge,
            hold_hours_count=hold_count,
            peak_discharge_hours_count=peak_dis_count,
            shadow_savings_vs_default_sek=shd_delta_sek,
            headline_recommendation=headline,
            plan=plan,
            hourly_steps=steps,
        )

    def _classify_step_action(
        self,
        pt: NextDayHourlyForecastPoint,
        sur_h: float,
        def_h: float,
        s_sol_chg: float,
        s_grid_chg: float,
        s_dis: float,
        soc_shd: float,
        plan: DayAheadShadowPlan,
    ) -> Tuple[str, str]:
        if s_grid_chg > 0.05:
            eta_pct = self.physics.roundtrip_efficiency * 100
            return (
                "GRID_PRECHARGE",
                f"Pre-charge {s_grid_chg:.2f} kWh from grid at trough {pt.spot_price_ore_kwh:.1f} öre/kWh "
                f"(passes η={eta_pct:.1f}% gate vs {plan.max_peak_spot_ore_kwh:.1f} öre peak)",
            )
        if s_sol_chg > 0.05:
            return (
                "SOLAR_CHARGE",
                f"Capture {s_sol_chg:.2f} kWh surplus solar PV into battery (avoiding low-value export)",
            )
        if def_h > 0.05 and s_dis <= 0.02 and soc_shd > 0.5:
            return (
                "HOLD_FOR_PEAK",
                f"Hold battery SoC ({soc_shd:.1f} kWh) at moderate spot {pt.spot_price_ore_kwh:.1f} öre/kWh "
                f"to preserve capacity for {plan.max_peak_spot_ore_kwh:.1f} öre/kWh peak",
            )
        if s_dis > 0.05:
            if pt.spot_price_ore_kwh >= plan.avg_peak_spot_ore_kwh * 0.85:
                return (
                    "PEAK_DISCHARGE",
                    f"Discharge {s_dis:.2f} kWh to shave high-price spike at {pt.spot_price_ore_kwh:.1f} öre/kWh",
                )
            return (
                "SELF_CONSUMPTION",
                f"Discharge {s_dis:.2f} kWh to cover household load at {pt.spot_price_ore_kwh:.1f} öre/kWh",
            )
        return ("IDLE", f"Standby / direct grid coverage at {pt.spot_price_ore_kwh:.1f} öre/kWh")

    @staticmethod
    def _build_headline(
        tot_grid_precharge: float,
        trough_win: str,
        avg_trough_ore: float,
        be_spot_ore: float,
        pk_win: str,
        max_peak_ore: float,
        hold_count: int,
        shd_delta_sek: float,
    ) -> str:
        if tot_grid_precharge >= 0.25:
            return (
                f"Pre-charge {tot_grid_precharge:.1f} kWh between {trough_win} at avg {avg_trough_ore:.1f} öre/kWh "
                f"(efficiency gate break-even: {be_spot_ore:.1f} öre/kWh) and hold for {pk_win} peak spike "
                f"(up to {max_peak_ore:.1f} öre/kWh) to save +{shd_delta_sek:.2f} SEK vs. default self-consumption."
            )
        if hold_count > 0 and shd_delta_sek > 0.15:
            return (
                f"No night grid pre-charging needed (solar/SoC sufficient or spread below {be_spot_ore:.1f} öre/kWh "
                f"break-even), but hold battery across {hold_count} low-price hours to target {pk_win} peak "
                f"({max_peak_ore:.1f} öre/kWh), saving +{shd_delta_sek:.2f} SEK."
            )
        return (
            f"Keep standard Solar Self-Consumption mode: price spread (trough {avg_trough_ore:.1f} öre vs peak "
            f"{max_peak_ore:.1f} öre) does not require night grid pre-charging (break-even {be_spot_ore:.1f} öre/kWh)."
        )


def exp_sol_chem_val(val: float) -> float:
    return max(0.0, val)
