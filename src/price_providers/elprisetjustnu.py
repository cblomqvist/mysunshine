"""Elprisetjustnu.se API price provider for Swedish bidding zones (SE1-SE4)."""

import json
import urllib.request
from datetime import datetime, timedelta
from typing import List
from .base import PricePoint, PriceProvider


class ElprisetjustnuPriceProvider(PriceProvider):
    """
    Fetches exact Swedish spot prices from elprisetjustnu.se public API.
    Zero-auth, highly accurate with official Nordpool settlement prices and exchange rates.
    """

    BASE_URL = "https://www.elprisetjustnu.se/api/v1/prices"

    @property
    def name(self) -> str:
        return "Elprisetjustnu"

    def get_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        bidding_zone: str = "SE3"
    ) -> List[PricePoint]:
        """Fetch daily price endpoints for each day in range and aggregate."""
        cur = start_date.date()
        end = end_date.date()

        price_points: List[PricePoint] = []

        while cur <= end:
            year_str = cur.strftime("%Y")
            mm_dd = cur.strftime("%m-%d")
            url = f"{self.BASE_URL}/{year_str}/{mm_dd}_{bidding_zone.upper()}.json"

            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "MySunshine/1.0", "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    daily_data = json.loads(resp.read().decode("utf-8"))

                for item in daily_data:
                    start_str = item.get("time_start")
                    if not start_str:
                        continue

                    dt = datetime.fromisoformat(start_str)
                    sek_kwh = float(item.get("SEK_per_kWh", 0.0))
                    eur_kwh = float(item.get("EUR_per_kWh", 0.0))
                    eur_mwh = eur_kwh * 1000.0

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
            except Exception:
                # If a specific future day is not yet published, continue
                pass

            cur += timedelta(days=1)

        price_points.sort(key=lambda x: x.timestamp)
        return price_points
