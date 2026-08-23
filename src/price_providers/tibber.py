"""Tibber GraphQL API price provider implementation using standard library urllib."""

import json
import os
import urllib.request
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from .base import PricePoint, PriceProvider
from .entsoe import load_dotenv_fallback

load_dotenv_fallback()


class TibberPriceProvider(PriceProvider):
    """
    Fetches spot prices and household energy prices via Tibber's GraphQL API.
    Requires a personal access token (TIBBER_API_TOKEN).
    """

    DEFAULT_API_URL = "https://api.tibber.com/v1-beta/gql"

    def __init__(self, api_token: Optional[str] = None, api_url: Optional[str] = None):
        load_dotenv_fallback()
        self.api_token = api_token or os.getenv("TIBBER_API_TOKEN")
        self.api_url = api_url or os.getenv("TIBBER_API_URL", self.DEFAULT_API_URL)

    @property
    def name(self) -> str:
        return "Tibber"

    def _execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against Tibber's endpoint using standard urllib."""
        if not self.api_token:
            raise ValueError(
                "TIBBER_API_TOKEN is not configured in environment or .env file."
            )

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "MySunshine/1.0",
        }
        payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")

        req = urllib.request.Request(self.api_url, data=payload, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if "errors" in data:
            raise ValueError(f"Tibber GraphQL Error: {data['errors']}")
        return data.get("data", {})

    def get_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        bidding_zone: str = "SE3"
    ) -> List[PricePoint]:
        """
        Fetch price information for available periods via Tibber.
        """
        query = """
        {
          viewer {
            homes {
              id
              currentSubscription {
                priceInfo {
                  current {
                    total
                    energy
                    startsAt
                  }
                  today {
                    total
                    energy
                    startsAt
                  }
                  tomorrow {
                    total
                    energy
                    startsAt
                  }
                }
              }
            }
          }
        }
        """
        data = self._execute_query(query)
        homes = data.get("viewer", {}).get("homes", [])
        if not homes:
            raise ValueError("No homes associated with this Tibber account.")

        price_points: List[PricePoint] = []
        home = homes[0]
        price_info = home.get("currentSubscription", {}).get("priceInfo", {})

        records = []
        if price_info.get("today"):
            records.extend(price_info["today"])
        if price_info.get("tomorrow"):
            records.extend(price_info["tomorrow"])

        # Convert query bounds to UTC for consistent comparison
        s_utc = start_date.astimezone(timezone.utc) if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc)
        e_utc = end_date.astimezone(timezone.utc) if end_date.tzinfo else end_date.replace(tzinfo=timezone.utc)

        for rec in records:
            starts_at = rec.get("startsAt")
            if not starts_at:
                continue

            dt = datetime.fromisoformat(starts_at)
            dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

            if not (s_utc <= dt_utc <= e_utc):
                continue

            sek_kwh = float(rec.get("energy", rec.get("total", 0.0)))
            rate = self.get_eur_sek_rate(dt)
            eur_mwh = (sek_kwh / rate) * 1000.0 if rate > 0 else 0.0

            res_minutes = 15 if dt >= datetime(2025, 10, 1, tzinfo=timezone.utc) else 60

            price_points.append(
                PricePoint(
                    timestamp=dt.isoformat(),
                    price_eur_mwh=eur_mwh,
                    price_sek_kwh=sek_kwh,
                    bidding_zone=bidding_zone.upper(),
                    resolution_minutes=res_minutes,
                    provider=self.name,
                )
            )

        price_points.sort(key=lambda x: x.timestamp)
        return price_points
