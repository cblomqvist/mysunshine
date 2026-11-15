"""Next-Day Spot Price, Weather/Irradiance, and Solar/Load Forecaster (Milestone 6.1 & 6.2).

Ingests published day-ahead SE3 spot prices (hourly & 15-minute resolution), models
Eskilstuna (59.37°N, 16.51°E) solar irradiance and weather conditions (supporting
Open-Meteo API with deterministic offline fallback profiles), predicts next-day
hourly PV generation and household consumption, and projects 3-way baseline bills
and expected savings.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import json
import math
from typing import Any, Dict, List, Optional, Sequence
import urllib.request

from ..financial_engine.baseline import (
    DEFAULT_DIURNAL_LOAD_WEIGHTS,
    DEFAULT_DIURNAL_SOLAR_WEIGHTS,
)
from ..financial_engine.multi_res import ResolutionMatcher
from ..financial_engine.tariff import SwedishTariff
from ..price_providers.base import PricePoint


# Eskilstuna (SE3) coordinates & SMA STP8.0-3AV-40 PV array constants
ESKILSTUNA_LAT = 59.3712
ESKILSTUNA_LON = 16.5098
SMA_INVERTER_AC_CAPACITY_KW = 8.0


def swedish_tz_offset_hours(utc_dt: datetime) -> int:
    """Return Swedish local time offset from UTC (+1 for CET, +2 for CEST).

    EU DST rules: starts last Sunday of March at 01:00 UTC, ends last Sunday of October at 01:00 UTC.
    """
    yr = utc_dt.year
    # Last Sunday of March
    march_last = date(yr, 3, 31)
    march_sun = march_last - timedelta(days=(march_last.weekday() + 1) % 7)
    dst_start = datetime(yr, 3, march_sun.day, 1, 0, 0, tzinfo=timezone.utc)

    # Last Sunday of October
    oct_last = date(yr, 10, 31)
    oct_sun = oct_last - timedelta(days=(oct_last.weekday() + 1) % 7)
    dst_end = datetime(yr, 10, oct_sun.day, 1, 0, 0, tzinfo=timezone.utc)

    return 2 if dst_start <= utc_dt < dst_end else 1


def to_swedish_local(dt: datetime) -> datetime:
    """Convert any datetime (UTC or aware) to Swedish local time (CET/CEST)."""
    if dt.tzinfo is None:
        utc_dt = dt.replace(tzinfo=timezone.utc)
    else:
        utc_dt = dt.astimezone(timezone.utc)
    offset_h = swedish_tz_offset_hours(utc_dt)
    tz_se = timezone(timedelta(hours=offset_h))
    return utc_dt.astimezone(tz_se)


@dataclass
class DayAheadHourlyPrice:
    """Published day-ahead SE3 spot price for a single local hour (with 15-min sub-intervals)."""
    timestamp_local: str
    date_str: str
    hour: int
    spot_price_sek_kwh: float
    spot_price_ore_kwh: float
    min_quarterly_ore_kwh: float
    max_quarterly_ore_kwh: float
    quarterly_prices_ore_kwh: List[float] = field(default_factory=list)
    resolution_minutes: int = 15
    provider: str = "ENTSO-E"


@dataclass
class HourlyWeatherForecast:
    """Hourly weather and solar irradiance forecast for Eskilstuna (SE3)."""
    hour: int
    temperature_c: float
    cloud_cover_pct: float
    global_tilted_irradiance_wm2: float
    clear_sky_irradiance_wm2: float


@dataclass
class DailyWeatherSummary:
    """Daily aggregated weather and irradiance forecast summary for Eskilstuna."""
    date_str: str
    condition_name: str
    condition_code: str
    avg_temperature_c: float
    min_temperature_c: float
    max_temperature_c: float
    avg_cloud_cover_pct: float
    daylight_cloud_cover_pct: float
    total_gti_kwh_m2: float
    clear_sky_gti_kwh_m2: float
    solar_transmittance_factor: float
    hourly_weather: List[HourlyWeatherForecast] = field(default_factory=list)
    source: str = "Calibrated Eskilstuna SE3 Weather Model"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date_str,
            "condition_name": self.condition_name,
            "condition_code": self.condition_code,
            "avg_temperature_c": round(self.avg_temperature_c, 1),
            "min_temperature_c": round(self.min_temperature_c, 1),
            "max_temperature_c": round(self.max_temperature_c, 1),
            "avg_cloud_cover_pct": round(self.avg_cloud_cover_pct, 1),
            "daylight_cloud_cover_pct": round(self.daylight_cloud_cover_pct, 1),
            "total_gti_kwh_m2": round(self.total_gti_kwh_m2, 2),
            "clear_sky_gti_kwh_m2": round(self.clear_sky_gti_kwh_m2, 2),
            "solar_transmittance_factor": round(self.solar_transmittance_factor, 3),
            "source": self.source,
        }


@dataclass
class NextDayHourlyForecastPoint:
    """Predicted hourly energy, weather, and price vector for the target day."""
    date_str: str
    hour: int
    timestamp_local: str
    spot_price_sek_kwh: float
    spot_price_ore_kwh: float
    min_quarterly_ore_kwh: float
    max_quarterly_ore_kwh: float
    import_price_sek_kwh: float
    export_price_sek_kwh: float
    predicted_pv_kwh: float
    predicted_load_kwh: float
    cloud_cover_pct: float
    temperature_c: float
    irradiance_wm2: float


@dataclass
class NextDayScenarioProjection:
    """Financial & energy projection for a single baseline or dispatch scenario."""
    name: str
    produced_kwh: float
    consumed_kwh: float
    imported_kwh: float
    exported_kwh: float
    self_consumed_kwh: float
    battery_charged_kwh: float
    battery_discharged_kwh: float
    import_cost_sek: float
    export_revenue_sek: float
    fixed_cost_sek: float
    net_cost_sek: float
    savings_vs_no_solar_sek: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "produced_kwh": round(self.produced_kwh, 2),
            "consumed_kwh": round(self.consumed_kwh, 2),
            "imported_kwh": round(self.imported_kwh, 2),
            "exported_kwh": round(self.exported_kwh, 2),
            "self_consumed_kwh": round(self.self_consumed_kwh, 2),
            "battery_charged_kwh": round(self.battery_charged_kwh, 2),
            "battery_discharged_kwh": round(self.battery_discharged_kwh, 2),
            "import_cost_sek": round(self.import_cost_sek, 2),
            "export_revenue_sek": round(self.export_revenue_sek, 2),
            "fixed_cost_sek": round(self.fixed_cost_sek, 2),
            "net_cost_sek": round(self.net_cost_sek, 2),
            "savings_vs_no_solar_sek": round(self.savings_vs_no_solar_sek, 2),
        }


class DayAheadPriceForecaster:
    """Extracts and normalizes published SE3 day-ahead spot prices for a target date."""

    def __init__(self, price_points: Optional[Sequence[PricePoint]] = None):
        self.price_points: List[PricePoint] = list(price_points) if price_points else []
        self._by_local_date_hour: Dict[str, Dict[int, List[PricePoint]]] = {}
        self._index_prices()

    def _index_prices(self) -> None:
        self._by_local_date_hour.clear()
        for p in self.price_points:
            loc_dt = to_swedish_local(p.timestamp)
            d_str = loc_dt.strftime("%Y-%m-%d")
            h = loc_dt.hour
            self._by_local_date_hour.setdefault(d_str, {}).setdefault(h, []).append(p)

    @classmethod
    def from_json_file(cls, json_path: str) -> "DayAheadPriceForecaster":
        points = ResolutionMatcher.load_prices_from_json(json_path)
        return cls(price_points=points)

    def available_dates(self) -> List[str]:
        """Return sorted list of dates with complete (>= 23 hours) day-ahead prices."""
        return sorted(
            d for d, hours_map in self._by_local_date_hour.items() if len(hours_map) >= 23
        )

    def get_day_ahead_prices(
        self,
        target_date: str,
        default_spot_sek: float = 0.65,
    ) -> List[DayAheadHourlyPrice]:
        """Return 24 hourly day-ahead price blocks (with 15-min sub-interval stats) for target_date."""
        hours_map = self._by_local_date_hour.get(target_date, {})
        result: List[DayAheadHourlyPrice] = []

        for h in range(24):
            pts = sorted(hours_map.get(h, []), key=lambda x: x.timestamp)
            if pts:
                q_ore = [round(p.price_sek_kwh * 100.0, 2) for p in pts]
                avg_sek = sum(p.price_sek_kwh for p in pts) / len(pts)
                avg_ore = round(avg_sek * 100.0, 2)
                min_ore = min(q_ore)
                max_ore = max(q_ore)
                res_min = pts[0].resolution_minutes
                prov = pts[0].provider
                loc_iso = to_swedish_local(pts[0].timestamp).replace(minute=0, second=0).isoformat()
            else:
                avg_sek = default_spot_sek
                avg_ore = round(default_spot_sek * 100.0, 2)
                min_ore = avg_ore
                max_ore = avg_ore
                q_ore = [avg_ore]
                res_min = 60
                prov = "Fallback"
                loc_iso = f"{target_date}T{h:02d}:00:00+01:00"

            result.append(
                DayAheadHourlyPrice(
                    timestamp_local=loc_iso,
                    date_str=target_date,
                    hour=h,
                    spot_price_sek_kwh=avg_sek,
                    spot_price_ore_kwh=avg_ore,
                    min_quarterly_ore_kwh=min_ore,
                    max_quarterly_ore_kwh=max_ore,
                    quarterly_prices_ore_kwh=q_ore,
                    resolution_minutes=res_min,
                    provider=prov,
                )
            )
        return result


class WeatherIrradianceProvider:
    """Provides hourly solar irradiance, cloud cover, and temperature for Eskilstuna (SE3).

    Supports Open-Meteo REST API with deterministic offline astronomical/seasonal models
    so tests and static dashboard builds operate cleanly without external network access.
    """

    # Empirical clear-sky daily PV potential (kWh/day) by month for the 8.0 kW SMA system in Eskilstuna
    CLEAR_SKY_DAILY_PV_KWH_BY_MONTH: Dict[int, float] = {
        1: 7.5,
        2: 18.0,
        3: 34.0,
        4: 48.0,
        5: 56.0,
        6: 58.5,
        7: 55.0,
        8: 46.5,
        9: 34.0,
        10: 21.5,
        11: 9.5,
        12: 5.5,
    }

    # Seasonal baseline outdoor temperature (°C) by month in Eskilstuna (SE3)
    SEASONAL_TEMP_C_BY_MONTH: Dict[int, float] = {
        1: -3.2,
        2: -2.8,
        3: 0.8,
        4: 6.2,
        5: 11.8,
        6: 16.2,
        7: 18.8,
        8: 17.5,
        9: 12.6,
        10: 7.2,
        11: 2.6,
        12: -1.4,
    }

    @classmethod
    def clear_sky_daily_pv_kwh(cls, target_date: str) -> float:
        """Interpolate smooth clear-sky daily PV generation potential (kWh) for target_date."""
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        doy = dt.timetuple().tm_yday
        # Peak around summer solstice (doy 172 -> ~58.5 kWh), trough around winter solstice (doy 355 -> ~5.0 kWh)
        phase = 2.0 * math.pi * (doy - 172.0) / 365.0
        elev_factor = ((1.0 + math.cos(phase)) / 2.0) ** 1.15
        return 5.0 + 53.5 * elev_factor

    @classmethod
    def seasonal_solar_weights(cls, target_date: str) -> List[float]:
        """Compute daylight-window-adjusted 24-hour solar weights summing to 1.0 for Eskilstuna."""
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        doy = dt.timetuple().tm_yday
        # Approximate sunrise/sunset hours in Eskilstuna (59.37°N)
        phase = math.cos(2.0 * math.pi * (doy - 172.0) / 365.0)
        half_daylight = 6.2 + 3.3 * phase  # ~9.5h half-day in June, ~2.9h half-day in Dec
        solar_noon = 12.0

        weights: List[float] = []
        for h in range(24):
            dist = abs((h + 0.5) - solar_noon)
            if dist >= half_daylight:
                weights.append(0.0)
            else:
                cos_val = math.cos((math.pi / 2.0) * (dist / half_daylight))
                w = (cos_val ** 1.6) * (0.5 + 0.5 * DEFAULT_DIURNAL_SOLAR_WEIGHTS[h] * 10.0)
                weights.append(max(0.0, w))

        tot = sum(weights)
        if tot <= 0.0:
            return list(DEFAULT_DIURNAL_SOLAR_WEIGHTS)
        return [w / tot for w in weights]

    @classmethod
    def build_weather_forecast(
        cls,
        target_date: str,
        cloud_cover_pct: Optional[float] = None,
        avg_temp_c: Optional[float] = None,
        condition_override: Optional[str] = None,
        allow_network: bool = False,
    ) -> DailyWeatherSummary:
        """Build a 24-hour weather and tilted irradiance forecast for Eskilstuna."""
        if allow_network and cloud_cover_pct is None:
            live = cls._try_fetch_open_meteo(target_date)
            if live is not None:
                return live

        dt = datetime.strptime(target_date, "%Y-%m-%d")
        month = dt.month
        base_temp = cls.SEASONAL_TEMP_C_BY_MONTH.get(month, 5.0) if avg_temp_c is None else avg_temp_c

        if cloud_cover_pct is None:
            # Deterministic seasonal cloud cover (~42% in summer, ~76% in November)
            doy = dt.timetuple().tm_yday
            seasonal_cloud = 60.0 - 20.0 * math.cos(2.0 * math.pi * (doy - 185.0) / 365.0)
            day_mod = ((doy * 37) % 29) - 14.0
            cloud_cover_pct = max(8.0, min(96.0, seasonal_cloud + day_mod))

        transmittance = max(0.08, 1.0 - 0.78 * ((cloud_cover_pct / 100.0) ** 1.3))
        clear_pv_kwh = cls.clear_sky_daily_pv_kwh(target_date)
        clear_gti_kwh_m2 = clear_pv_kwh / 6.8  # ~8 kWp array with system performance ratio ~0.85
        total_gti_kwh_m2 = clear_gti_kwh_m2 * transmittance
        solar_w = cls.seasonal_solar_weights(target_date)

        hourly_list: List[HourlyWeatherForecast] = []
        for h in range(24):
            # Diurnal temperature wave: coldest at 05:00, warmest at 14:00
            diurnal_t = -2.2 * math.cos(2.0 * math.pi * (h - 5.0) / 24.0)
            temp_h = base_temp + diurnal_t
            cloud_h = max(0.0, min(100.0, cloud_cover_pct + 4.0 * math.sin(2.0 * math.pi * h / 24.0)))
            cs_irr = clear_gti_kwh_m2 * 1000.0 * solar_w[h]
            act_irr = total_gti_kwh_m2 * 1000.0 * solar_w[h]
            hourly_list.append(
                HourlyWeatherForecast(
                    hour=h,
                    temperature_c=round(temp_h, 1),
                    cloud_cover_pct=round(cloud_h, 1),
                    global_tilted_irradiance_wm2=round(act_irr, 1),
                    clear_sky_irradiance_wm2=round(cs_irr, 1),
                )
            )

        if condition_override:
            cond_name = condition_override
        elif cloud_cover_pct < 25.0:
            cond_name = "Clear Sky / Crisp Sunshine"
        elif cloud_cover_pct < 60.0:
            cond_name = "Partly Cloudy / Scattered Sun"
        elif cloud_cover_pct < 85.0:
            cond_name = "Mostly Cloudy / Autumn Overcast"
        else:
            cond_name = "Heavy Overcast / Low Irradiance"

        cond_code = (
            "clear"
            if cloud_cover_pct < 25.0
            else "partly_cloudy"
            if cloud_cover_pct < 60.0
            else "cloudy"
            if cloud_cover_pct < 85.0
            else "overcast"
        )

        temps = [hw.temperature_c for hw in hourly_list]
        return DailyWeatherSummary(
            date_str=target_date,
            condition_name=cond_name,
            condition_code=cond_code,
            avg_temperature_c=sum(temps) / len(temps),
            min_temperature_c=min(temps),
            max_temperature_c=max(temps),
            avg_cloud_cover_pct=cloud_cover_pct,
            daylight_cloud_cover_pct=cloud_cover_pct,
            total_gti_kwh_m2=total_gti_kwh_m2,
            clear_sky_gti_kwh_m2=clear_gti_kwh_m2,
            solar_transmittance_factor=transmittance,
            hourly_weather=hourly_list,
        )

    @classmethod
    def _try_fetch_open_meteo(cls, target_date: str) -> Optional[DailyWeatherSummary]:
        """Attempt live Open-Meteo query for Eskilstuna; return None on any network/range error."""
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={ESKILSTUNA_LAT}&longitude={ESKILSTUNA_LON}"
            f"&hourly=temperature_2m,cloud_cover,global_tilted_irradiance"
            f"&tilt=38&azimuth=15&timezone=Europe%2FStockholm"
            f"&start_date={target_date}&end_date={target_date}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MySunshine/1.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            hourly = payload.get("hourly", {})
            temps = hourly.get("temperature_2m", [])
            clouds = hourly.get("cloud_cover", [])
            gtis = hourly.get("global_tilted_irradiance", [])
            if len(temps) < 24:
                return None
            avg_cloud = sum(clouds[:24]) / 24.0
            avg_temp = sum(temps[:24]) / 24.0
            summary = cls.build_weather_forecast(
                target_date=target_date,
                cloud_cover_pct=avg_cloud,
                avg_temp_c=avg_temp,
                allow_network=False,
            )
            summary.source = "Open-Meteo API (Eskilstuna SE3)"
            if gtis and len(gtis) >= 24:
                summary.total_gti_kwh_m2 = sum(max(0.0, float(g)) for g in gtis[:24]) / 1000.0
            return summary
        except Exception:
            return None


class SolarLoadForecaster:
    """Predicts next-day hourly PV production and household consumption.

    Combines trailing historical daily/hourly energy patterns with seasonal solar
    elevation, weather transmittance, and outdoor temperature heating sensitivity.
    """

    def __init__(
        self,
        tariff: Optional[SwedishTariff] = None,
        load_weights: Optional[List[float]] = None,
        solar_weights: Optional[List[float]] = None,
    ):
        self.tariff = tariff or SwedishTariff()
        self.load_weights = list(load_weights or DEFAULT_DIURNAL_LOAD_WEIGHTS)
        self.solar_weights = list(solar_weights or DEFAULT_DIURNAL_SOLAR_WEIGHTS)

    def predict_daily_totals(
        self,
        target_date: str,
        weather: DailyWeatherSummary,
        trailing_daily_pv_kwh: Optional[Sequence[float]] = None,
        trailing_daily_load_kwh: Optional[Sequence[float]] = None,
    ) -> Dict[str, float]:
        """Predict next-day total PV generation (kWh) and household consumption (kWh)."""
        clear_sky_pv = WeatherIrradianceProvider.clear_sky_daily_pv_kwh(target_date)
        weather_pv = clear_sky_pv * weather.solar_transmittance_factor

        if trailing_daily_pv_kwh and len(trailing_daily_pv_kwh) >= 3:
            recent_7 = list(trailing_daily_pv_kwh[-7:])
            recent_3 = list(trailing_daily_pv_kwh[-3:])
            hist_pv = 0.55 * (sum(recent_7) / len(recent_7)) + 0.45 * (sum(recent_3) / len(recent_3))
            # Day-ahead solar irradiance forecast is the primary physical driver (85%),
            # with 15% weight on trailing empirical array trend
            pred_pv = min(clear_sky_pv, 0.85 * weather_pv + 0.15 * hist_pv)
        else:
            pred_pv = min(clear_sky_pv, weather_pv)

        # Predict daily household load (kWh)
        # Heating degree day adjustment below 15°C (~0.38 kWh per °C below 15°C)
        hdd = max(0.0, 15.0 - weather.avg_temperature_c)
        seasonal_load = 14.8 + 0.38 * hdd

        if trailing_daily_load_kwh and len(trailing_daily_load_kwh) >= 3:
            recent_7_ld = sorted(trailing_daily_load_kwh[-7:])
            # Trimmed mean of trailing 7 days to avoid single-day EV/appliance outlier distortion
            if len(recent_7_ld) >= 5:
                trimmed = recent_7_ld[1:-1]
                hist_load_7 = sum(trimmed) / len(trimmed)
            else:
                hist_load_7 = sum(recent_7_ld) / len(recent_7_ld)
            recent_3_ld = list(trailing_daily_load_kwh[-3:])
            hist_load_3 = sum(min(28.0, x) for x in recent_3_ld) / len(recent_3_ld)
            hist_load = 0.65 * hist_load_7 + 0.35 * hist_load_3
            pred_load = 0.75 * hist_load + 0.25 * seasonal_load
        elif trailing_daily_load_kwh:
            pred_load = 0.60 * (sum(trailing_daily_load_kwh) / len(trailing_daily_load_kwh)) + 0.40 * seasonal_load
        else:
            pred_load = seasonal_load

        return {
            "predicted_pv_kwh": max(0.1, round(pred_pv, 3)),
            "predicted_load_kwh": max(4.0, round(pred_load, 3)),
            "clear_sky_pv_kwh": round(clear_sky_pv, 3),
        }

    def forecast_next_day_hourly(
        self,
        target_date: str,
        day_ahead_prices: Sequence[DayAheadHourlyPrice],
        weather: DailyWeatherSummary,
        trailing_daily_pv_kwh: Optional[Sequence[float]] = None,
        trailing_daily_load_kwh: Optional[Sequence[float]] = None,
        trailing_hourly_load_weights: Optional[Sequence[float]] = None,
        override_daily_pv_kwh: Optional[float] = None,
        override_daily_load_kwh: Optional[float] = None,
    ) -> List[NextDayHourlyForecastPoint]:
        """Generate 24 hourly forecast points aligning prices, weather, PV, and household load."""
        totals = self.predict_daily_totals(
            target_date=target_date,
            weather=weather,
            trailing_daily_pv_kwh=trailing_daily_pv_kwh,
            trailing_daily_load_kwh=trailing_daily_load_kwh,
        )
        day_pv = override_daily_pv_kwh if override_daily_pv_kwh is not None else totals["predicted_pv_kwh"]
        day_load = (
            override_daily_load_kwh if override_daily_load_kwh is not None else totals["predicted_load_kwh"]
        )

        # Seasonal daylight weights for PV
        pv_w = WeatherIrradianceProvider.seasonal_solar_weights(target_date)

        # Blend trailing hourly load weights (if available) with calibrated diurnal load weights
        if trailing_hourly_load_weights and len(trailing_hourly_load_weights) == 24:
            raw_ld_w = [
                0.60 * trailing_hourly_load_weights[h] + 0.40 * self.load_weights[h]
                for h in range(24)
            ]
            sum_ld_w = sum(raw_ld_w) or 1.0
            ld_w = [w / sum_ld_w for w in raw_ld_w]
        else:
            ld_w = self.load_weights

        points: List[NextDayHourlyForecastPoint] = []
        for h in range(24):
            p_info = day_ahead_prices[h] if h < len(day_ahead_prices) else day_ahead_prices[-1]
            w_info = weather.hourly_weather[h] if h < len(weather.hourly_weather) else weather.hourly_weather[-1]
            spot_sek = p_info.spot_price_sek_kwh
            imp_sek = self.tariff.get_import_price(spot_sek)
            exp_sek = self.tariff.get_export_price(spot_sek, date_str=target_date)

            pv_h = min(SMA_INVERTER_AC_CAPACITY_KW, day_pv * pv_w[h])
            load_h = day_load * ld_w[h]

            points.append(
                NextDayHourlyForecastPoint(
                    date_str=target_date,
                    hour=h,
                    timestamp_local=p_info.timestamp_local,
                    spot_price_sek_kwh=round(spot_sek, 4),
                    spot_price_ore_kwh=round(p_info.spot_price_ore_kwh, 2),
                    min_quarterly_ore_kwh=round(p_info.min_quarterly_ore_kwh, 2),
                    max_quarterly_ore_kwh=round(p_info.max_quarterly_ore_kwh, 2),
                    import_price_sek_kwh=round(imp_sek, 4),
                    export_price_sek_kwh=round(exp_sek, 4),
                    predicted_pv_kwh=round(pv_h, 3),
                    predicted_load_kwh=round(load_h, 3),
                    cloud_cover_pct=w_info.cloud_cover_pct,
                    temperature_c=w_info.temperature_c,
                    irradiance_wm2=w_info.global_tilted_irradiance_wm2,
                )
            )
        return points
