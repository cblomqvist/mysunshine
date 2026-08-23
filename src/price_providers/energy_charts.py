"""Energy-Charts (Fraunhofer ISE) API price provider for European and Nordic bidding zones."""

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import List, Optional

from .base import PricePoint, PriceProvider


class EnergyChartsPriceProvider(PriceProvider):
    """
    Fetches European day-ahead electricity spot prices via Fraunhofer ISE's Energy-Charts API.
    Zero-auth public endpoint covering SE1, SE2, SE3, SE4, DE, etc.
    """

    DEFAULT_API_URL = "https://api.energy-charts.info/price"

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv("ENERGY_CHARTS_API_URL", self.DEFAULT_API_URL)

    @property
    def name(self) -> str:
        return "Energy-Charts"

    def get_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        bidding_zone: str = "SE3"
    ) -> List[PricePoint]:
        """Fetch spot prices for the given date range and zone."""
        s_str = start_date.strftime("%Y-%m-%dT00:00")
        e_str = end_date.strftime("%Y-%m-%dT23:59")

        params = {
            "bzn": bidding_zone.upper(),
            "start": s_str,
            "end": e_str,
        }

        url = f"{self.api_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MySunshine/1.0", "Accept": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        unix_seconds = data.get("unix_seconds", [])
        prices_eur = data.get("price", [])

        if not unix_seconds or not prices_eur or len(unix_seconds) != len(prices_eur):
            raise ValueError(f"Energy-Charts API returned no data or mismatched arrays for {bidding_zone}")

        price_points: List[PricePoint] = []
        for ts, eur_mwh in zip(unix_seconds, prices_eur):
            if eur_mwh is None:
                continue

            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            eur_val = float(eur_mwh)
            sek_kwh = self.eur_mwh_to_sek_kwh(eur_val, dt)

            price_points.append(
                PricePoint(
                    timestamp=dt.isoformat(),
                    price_eur_mwh=eur_val,
                    price_sek_kwh=sek_kwh,
                    bidding_zone=bidding_zone.upper(),
                    resolution_minutes=60,
                    provider=self.name,
                )
            )

        price_points.sort(key=lambda x: x.timestamp)
        return price_points
