"""ENTSO-E Transparency Platform API price provider implementation using standard library urllib."""

import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from .base import PricePoint, PriceProvider


def load_dotenv_fallback(filepath: str = ".env"):
    """Lightweight .env loader without third-party dependencies."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


load_dotenv_fallback()

ENTSOE_ZONE_EIC = {
    "SE1": "10Y1001A1001A44P",
    "SE2": "10Y1001A1001A45N",
    "SE3": "10Y1001A1001A46L",
    "SE4": "10Y1001A1001A47J",
    "FI": "10YFI-1--------U",
    "NO1": "10YNO-1--------2",
}


class EntsoePriceProvider(PriceProvider):
    """
    Fetches official European day-ahead electricity spot prices via ENTSO-E Transparency Platform API.
    Requires an API token (securityToken).
    """

    DEFAULT_API_URL = "https://web-api.tp.entsoe.eu/api"

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        load_dotenv_fallback()
        self.api_key = api_key or os.getenv("ENTSOE_API_KEY")
        self.api_url = api_url or os.getenv("ENTSOE_API_URL", self.DEFAULT_API_URL)

    @property
    def name(self) -> str:
        return "ENTSO-E"

    def get_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        bidding_zone: str = "SE3"
    ) -> List[PricePoint]:
        """Fetch spot prices for the given date range and zone from ENTSO-E."""
        if not self.api_key:
            raise ValueError(
                "ENTSOE_API_KEY is not configured in environment or .env file."
            )

        eic_code = ENTSOE_ZONE_EIC.get(bidding_zone.upper())
        if not eic_code:
            raise ValueError(f"Unknown bidding zone EIC code for: {bidding_zone}")

        if start_date.tzinfo is None:
            s_utc = start_date.replace(tzinfo=timezone.utc)
        else:
            s_utc = start_date.astimezone(timezone.utc)

        if end_date.tzinfo is None:
            e_utc = end_date.replace(tzinfo=timezone.utc)
        else:
            e_utc = end_date.astimezone(timezone.utc)

        period_start = s_utc.strftime("%Y%m%d%H%M")
        period_end = e_utc.strftime("%Y%m%d%H%M")

        params = {
            "securityToken": self.api_key,
            "documentType": "A44",  # Day-ahead Price Document
            "in_Domain": eic_code,
            "out_Domain": eic_code,
            "periodStart": period_start,
            "periodEnd": period_end,
        }

        url = f"{self.api_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MySunshine/1.0", "Accept": "application/xml"}
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_content = resp.read().decode("utf-8")

        return self._parse_xml_response(xml_content, bidding_zone)

    def _parse_xml_response(self, xml_content: str, bidding_zone: str) -> List[PricePoint]:
        """Parse ENTSO-E XML response into a list of PricePoint objects."""
        root = ET.fromstring(xml_content)

        # Strip namespaces
        for elem in root.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

        # Check for error / acknowledgment response
        reason = root.find(".//Reason")
        if reason is not None:
            code = reason.findtext("code", "")
            text = reason.findtext("text", "")
            if code != "999":
                raise ValueError(f"ENTSO-E API Error ({code}): {text}")

        price_points: List[PricePoint] = []

        for ts in root.findall(".//TimeSeries"):
            period = ts.find("Period")
            if period is None:
                continue

            time_interval = period.find("timeInterval")
            start_str = time_interval.findtext("start") if time_interval is not None else None
            if not start_str:
                continue

            period_start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

            resolution_str = period.findtext("resolution", "PT60M")
            if resolution_str == "PT15M":
                step = timedelta(minutes=15)
                res_mins = 15
            else:
                step = timedelta(minutes=60)
                res_mins = 60

            for point in period.findall("Point"):
                pos = int(point.findtext("position", "1"))
                price_eur_mwh = float(point.findtext("price.amount", "0.0"))

                point_dt = period_start_dt + (pos - 1) * step
                sek_kwh = self.eur_mwh_to_sek_kwh(price_eur_mwh, point_dt)

                price_points.append(
                    PricePoint(
                        timestamp=point_dt.isoformat(),
                        price_eur_mwh=price_eur_mwh,
                        price_sek_kwh=sek_kwh,
                        bidding_zone=bidding_zone.upper(),
                        resolution_minutes=res_mins,
                        provider=self.name,
                    )
                )

        price_points.sort(key=lambda x: x.timestamp)
        return price_points
