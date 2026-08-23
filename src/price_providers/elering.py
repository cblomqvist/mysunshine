"""Elering Public NPS Spot Price Provider implementation using standard library urllib."""

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import List, Optional

from .base import PricePoint, PriceProvider


class EleringPriceProvider(PriceProvider):
    """
    Fetches Nordpool day-ahead electricity spot prices via Elering's public API.
    Does not require authentication.
    """

    DEFAULT_API_URL = "https://dashboard.elering.ee/api/nps/price"

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv("ELERING_API_URL", self.DEFAULT_API_URL)

    @property
    def name(self) -> str:
        return "Elering"

    def get_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        bidding_zone: str = "SE3"
    ) -> List[PricePoint]:
        """
        Fetch prices for a date range from Elering.
        Dates are converted to ISO UTC format.
        """
        if start_date.tzinfo is None:
            s_utc = start_date.replace(tzinfo=timezone.utc)
        else:
            s_utc = start_date.astimezone(timezone.utc)

        if end_date.tzinfo is None:
            e_utc = end_date.replace(tzinfo=timezone.utc)
        else:
            e_utc = end_date.astimezone(timezone.utc)

        params = {
            "start": s_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "end": e_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }

        url = f"{self.api_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MySunshine/1.0", "Accept": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            json_data = json.loads(resp.read().decode("utf-8"))

        zone_key = bidding_zone.lower()
        if not json_data.get("success") or "data" not in json_data:
            raise ValueError(f"Elering API returned unexpected format: {json_data}")

        zone_data = json_data["data"].get(zone_key, [])
        if not zone_data:
            zone_data = json_data["data"].get(bidding_zone.upper(), [])

        price_points: List[PricePoint] = []
        for item in zone_data:
            ts_val = item.get("timestamp")
            if isinstance(ts_val, (int, float)):
                dt = datetime.fromtimestamp(ts_val, tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(str(ts_val))

            eur_mwh = float(item["price"])
            sek_kwh = self.eur_mwh_to_sek_kwh(eur_mwh, dt)

            price_points.append(
                PricePoint(
                    timestamp=dt.isoformat(),
                    price_eur_mwh=eur_mwh,
                    price_sek_kwh=sek_kwh,
                    bidding_zone=bidding_zone.upper(),
                    resolution_minutes=60,
                    provider=self.name,
                )
            )

        price_points.sort(key=lambda x: x.timestamp)
        return price_points
