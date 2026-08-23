"""Base definitions and data structures for electricity spot price providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional


# Approximate default EUR/SEK exchange rates by year if dynamic lookup is not available
DEFAULT_EUR_SEK_RATES = {
    2024: 11.45,
    2025: 11.35,
    2026: 11.25,
}
FALLBACK_EUR_SEK_RATE = 11.35


@dataclass
class PricePoint:
    """Represents an electricity spot price at a specific time interval."""
    timestamp: str  # ISO-8601 string with timezone offset
    price_eur_mwh: float
    price_sek_kwh: float
    bidding_zone: str = "SE3"
    resolution_minutes: int = 60
    provider: str = "unknown"

    @property
    def price_ore_kwh(self) -> float:
        """Price in Swedish öre per kWh."""
        return self.price_sek_kwh * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary including computed properties."""
        d = asdict(self)
        d["price_ore_kwh"] = round(self.price_ore_kwh, 4)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PricePoint":
        """Deserialize from dictionary."""
        return cls(
            timestamp=data["timestamp"],
            price_eur_mwh=float(data["price_eur_mwh"]),
            price_sek_kwh=float(data["price_sek_kwh"]),
            bidding_zone=data.get("bidding_zone", "SE3"),
            resolution_minutes=int(data.get("resolution_minutes", 60)),
            provider=data.get("provider", "unknown"),
        )


class PriceProvider(ABC):
    """Abstract base class for electricity price providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier name."""
        pass

    @abstractmethod
    def get_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        bidding_zone: str = "SE3"
    ) -> List[PricePoint]:
        """
        Fetch electricity spot prices for a given date range and bidding zone.

        Args:
            start_date: Start of the query range (inclusive).
            end_date: End of the query range (inclusive).
            bidding_zone: Bidding zone identifier (default 'SE3').

        Returns:
            List of PricePoint objects ordered chronologically.
        """
        pass

    @staticmethod
    def get_eur_sek_rate(dt: datetime, custom_rate: Optional[float] = None) -> float:
        """Returns the EUR/SEK exchange rate for a given date."""
        if custom_rate is not None:
            return custom_rate
        return DEFAULT_EUR_SEK_RATES.get(dt.year, FALLBACK_EUR_SEK_RATE)

    @classmethod
    def eur_mwh_to_sek_kwh(
        cls,
        eur_mwh: float,
        dt: datetime,
        custom_rate: Optional[float] = None
    ) -> float:
        """
        Convert EUR/MWh spot price to SEK/kWh.
        1 MWh = 1,000 kWh -> Price in EUR/kWh = eur_mwh / 1000.
        Price in SEK/kWh = (eur_mwh / 1000) * eur_sek_rate.
        """
        rate = cls.get_eur_sek_rate(dt, custom_rate)
        return (eur_mwh / 1000.0) * rate
