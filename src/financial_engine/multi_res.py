"""Multi-Resolution Matching & High-Resolution Energy Data Ingestion Engine.

Handles alignment between high-resolution energy time-series (e.g., hourly Sonnen exports)
and dynamic electricity spot price time-series across multiple resolutions (15-min quarterly
and 60-min hourly), normalizing timezones and calculating resolution aggregations.
"""

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Union

from ..price_providers.base import PricePoint


@dataclass
class HourlyEnergyRecord:
    """A single high-resolution hourly energy record."""
    timestamp: datetime
    measurements_count: int
    produced_kwh: float
    consumed_kwh: float
    battery_charged_kwh: float
    battery_discharged_kwh: float
    grid_feedin_kwh: float
    grid_purchase_kwh: float

    # Self-consumption metrics for the actual system
    @property
    def direct_solar_self_consumption_kwh(self) -> float:
        """Instant solar energy consumed directly by the home (PV - BatteryCharge - Export)."""
        return max(0.0, self.produced_kwh - self.battery_charged_kwh - self.grid_feedin_kwh)

    @property
    def total_solar_self_consumption_kwh(self) -> float:
        """Total solar energy retained on-site (PV - Export)."""
        return max(0.0, self.produced_kwh - self.grid_feedin_kwh)


@dataclass
class MatchedHourlyInterval:
    """An hourly energy record matched with its corresponding spot price."""
    energy: HourlyEnergyRecord
    spot_price_sek_kwh: float
    spot_price_eur_mwh: float
    price_resolution_minutes: int
    quarterly_prices_sek_kwh: List[float] = field(default_factory=list)
    provider: str = "Unknown"


class SonnenHourlyIngestor:
    """Parses and validates Sonnen high-resolution hourly CSV exports."""

    @staticmethod
    def parse_csv(file_path: str) -> List[HourlyEnergyRecord]:
        """Parse a Sonnen hourly CSV export file into a list of HourlyEnergyRecord objects.

        Energy values in the CSV are in Watt-hours (Wh) and are converted to kilowatt-hours (kWh).
        Timestamps are parsed with timezone awareness.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Sonnen high-resolution export not found: {file_path}")

        records: List[HourlyEnergyRecord] = []

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_cols = {
                "timestamp",
                "measurements_count",
                "produced_energy",
                "consumed_energy",
                "battery_charged_energy",
                "battery_discharged_energy",
                "grid_feedin_energy",
                "grid_purchase_energy",
            }
            if not required_cols.issubset(set(reader.fieldnames or [])):
                missing = required_cols - set(reader.fieldnames or [])
                raise ValueError(f"CSV missing required columns: {missing}")

            for row in reader:
                ts_str = row["timestamp"]
                ts = datetime.fromisoformat(ts_str)

                # Wh to kWh conversion (/ 1000.0)
                record = HourlyEnergyRecord(
                    timestamp=ts,
                    measurements_count=int(row.get("measurements_count", 60)),
                    produced_kwh=float(row.get("produced_energy", 0.0)) / 1000.0,
                    consumed_kwh=float(row.get("consumed_energy", 0.0)) / 1000.0,
                    battery_charged_kwh=float(row.get("battery_charged_energy", 0.0)) / 1000.0,
                    battery_discharged_kwh=float(row.get("battery_discharged_energy", 0.0)) / 1000.0,
                    grid_feedin_kwh=float(row.get("grid_feedin_energy", 0.0)) / 1000.0,
                    grid_purchase_kwh=float(row.get("grid_purchase_energy", 0.0)) / 1000.0,
                )
                records.append(record)

        return sorted(records, key=lambda r: r.timestamp)


class ResolutionMatcher:
    """Matches energy time-series with spot price data across 15-min and 60-min resolutions."""

    @staticmethod
    def _normalize_dt(dt: datetime) -> datetime:
        """Convert datetime to UTC aware for reliable comparison."""
        if dt.tzinfo is None:
            # Assume UTC if naive
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def load_prices_from_json(cls, json_path_or_data: Union[str, List[Dict]]) -> List[PricePoint]:
        """Load PricePoint objects from a JSON file or list of dicts."""
        if isinstance(json_path_or_data, str):
            with open(json_path_or_data, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json_path_or_data

        points: List[PricePoint] = []
        for item in data:
            ts_str = item.get("timestamp")
            if not ts_str:
                continue
            ts = datetime.fromisoformat(ts_str)
            p_sek = item.get("price_sek_kwh")
            p_eur = item.get("price_eur_mwh", 0.0)
            if p_sek is None:
                p_sek = item.get("price_ore_kwh", 0.0) / 100.0

            res = item.get("resolution_minutes", 60)
            provider = item.get("provider", "ENTSO-E")
            zone = item.get("bidding_zone", "SE3")

            point = PricePoint(
                timestamp=ts,
                price_eur_mwh=float(p_eur),
                price_sek_kwh=float(p_sek),
                bidding_zone=zone,
                resolution_minutes=int(res),
                provider=provider,
            )
            points.append(point)

        return sorted(points, key=lambda p: p.timestamp)

    @classmethod
    def match_hourly_energy_with_prices(
        cls,
        energy_records: List[HourlyEnergyRecord],
        price_points: List[PricePoint],
        default_spot_price_sek: float = 0.50,
    ) -> List[MatchedHourlyInterval]:
        """Align 1-hour energy intervals with spot prices (supporting both 15-min and 60-min prices).

        For each hourly energy interval [T, T + 1 hour):
        - If prices are 15-minute resolution, finds the 4 quarters falling in [T, T + 1 hour)
          and averages them.
        - If prices are 60-minute resolution, matches the exact hourly interval.
        - If no price points match, falls back to default_spot_price_sek.
        """
        # Index price points by normalized UTC start time
        prices_by_utc: Dict[datetime, PricePoint] = {}
        for p in price_points:
            utc_dt = cls._normalize_dt(p.timestamp)
            prices_by_utc[utc_dt] = p

        matched: List[MatchedHourlyInterval] = []

        for rec in energy_records:
            start_utc = cls._normalize_dt(rec.timestamp)

            # Look for 15-minute price quarters: [start, start+15m, start+30m, start+45m]
            q_times = [start_utc + timedelta(minutes=15 * i) for i in range(4)]
            quarters = [prices_by_utc.get(qt) for qt in q_times if qt in prices_by_utc]

            if len(quarters) == 4:
                # Full 4-quarter 15-minute match
                q_prices_sek = [q.price_sek_kwh for q in quarters]
                avg_sek = sum(q_prices_sek) / 4.0
                avg_eur = sum(q.price_eur_mwh for q in quarters) / 4.0
                provider = quarters[0].provider
                matched.append(
                    MatchedHourlyInterval(
                        energy=rec,
                        spot_price_sek_kwh=avg_sek,
                        spot_price_eur_mwh=avg_eur,
                        price_resolution_minutes=15,
                        quarterly_prices_sek_kwh=q_prices_sek,
                        provider=provider,
                    )
                )
            elif start_utc in prices_by_utc:
                # Direct 60-minute match
                p = prices_by_utc[start_utc]
                matched.append(
                    MatchedHourlyInterval(
                        energy=rec,
                        spot_price_sek_kwh=p.price_sek_kwh,
                        spot_price_eur_mwh=p.price_eur_mwh,
                        price_resolution_minutes=p.resolution_minutes,
                        quarterly_prices_sek_kwh=[p.price_sek_kwh] if p.resolution_minutes == 15 else [],
                        provider=p.provider,
                    )
                )
            elif quarters:
                # Partial quarter match (e.g. 1-3 quarters found)
                q_prices_sek = [q.price_sek_kwh for q in quarters]
                avg_sek = sum(q_prices_sek) / len(quarters)
                avg_eur = sum(q.price_eur_mwh for q in quarters) / len(quarters)
                matched.append(
                    MatchedHourlyInterval(
                        energy=rec,
                        spot_price_sek_kwh=avg_sek,
                        spot_price_eur_mwh=avg_eur,
                        price_resolution_minutes=15,
                        quarterly_prices_sek_kwh=q_prices_sek,
                        provider=quarters[0].provider,
                    )
                )
            else:
                # Fallback default price
                matched.append(
                    MatchedHourlyInterval(
                        energy=rec,
                        spot_price_sek_kwh=default_spot_price_sek,
                        spot_price_eur_mwh=default_spot_price_sek * 100.0,
                        price_resolution_minutes=60,
                        quarterly_prices_sek_kwh=[],
                        provider="Fallback",
                    )
                )

        return matched
