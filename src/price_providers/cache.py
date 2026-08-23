"""Disk cache manager for electricity spot prices."""

import json
import os
from datetime import datetime
from typing import List, Optional
from .base import PricePoint


class PriceCache:
    """Manages reading and writing cached spot price data to JSON files."""

    def __init__(self, cache_dir: str = "data/prices"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_filename(
        self,
        provider: str,
        bidding_zone: str,
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Generate standardized cache file path."""
        s_str = start_date.strftime("%Y%m%d")
        e_str = end_date.strftime("%Y%m%d")
        safe_provider = provider.lower().replace(" ", "_")
        filename = f"{safe_provider}_{bidding_zone.upper()}_{s_str}_{e_str}.json"
        return os.path.join(self.cache_dir, filename)

    def get(
        self,
        provider: str,
        bidding_zone: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[List[PricePoint]]:
        """Retrieve cached prices if file exists and is valid."""
        filepath = self._get_filename(provider, bidding_zone, start_date, end_date)
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [PricePoint.from_dict(p) for p in data]
        except Exception:
            return None

    def save(
        self,
        provider: str,
        bidding_zone: str,
        start_date: datetime,
        end_date: datetime,
        prices: List[PricePoint]
    ) -> str:
        """Save price points to cache file and return the filepath."""
        filepath = self._get_filename(provider, bidding_zone, start_date, end_date)
        data = [p.to_dict() for p in prices]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return filepath
