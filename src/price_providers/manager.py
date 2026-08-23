"""PriceManager coordinator with multi-provider fallback and caching."""

import logging
from datetime import datetime
from typing import List, Optional, Dict
from .base import PricePoint, PriceProvider
from .cache import PriceCache
from .elering import EleringPriceProvider
from .energy_charts import EnergyChartsPriceProvider
from .elprisetjustnu import ElprisetjustnuPriceProvider
from .entsoe import EntsoePriceProvider
from .tibber import TibberPriceProvider

logger = logging.getLogger(__name__)


class PriceManager:
    """
    Coordinates fetching electricity spot prices across multiple providers
    with automatic fallback and disk caching.
    """

    def __init__(
        self,
        cache_dir: str = "data/prices",
        custom_providers: Optional[Dict[str, PriceProvider]] = None
    ):
        self.cache = PriceCache(cache_dir=cache_dir)
        self.providers: Dict[str, PriceProvider] = custom_providers or {
            "entsoe": EntsoePriceProvider(),
            "tibber": TibberPriceProvider(),
            "energy_charts": EnergyChartsPriceProvider(),
            "elprisetjustnu": ElprisetjustnuPriceProvider(),
            "elering": EleringPriceProvider(),
        }

    def get_prices(
        self,
        start_date: datetime,
        end_date: datetime,
        bidding_zone: str = "SE3",
        provider_name: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[PricePoint]:
        """
        Fetch prices for the specified date range and bidding zone.

        Args:
            start_date: Start datetime.
            end_date: End datetime.
            bidding_zone: SE3, SE1, SE2, SE4, etc.
            provider_name: Specific provider to use.
                           If None, attempts primary providers with automatic fallback.
            use_cache: If True, checks and populates the local disk cache.

        Returns:
            List of PricePoint objects.
        """
        # 1. Check cache first
        if use_cache:
            p_key = provider_name or "auto"
            cached = self.cache.get(p_key, bidding_zone, start_date, end_date)
            if cached:
                logger.info("Retrieved %d prices from cache for %s (%s to %s)",
                            len(cached), bidding_zone, start_date, end_date)
                return cached

        # 2. Determine provider order
        if provider_name:
            p_name_lower = provider_name.lower().replace("-", "_")
            if p_name_lower not in self.providers:
                raise ValueError(
                    f"Unknown provider '{provider_name}'. Available: {list(self.providers.keys())}"
                )
            active_providers = [(p_name_lower, self.providers[p_name_lower])]
        else:
            # Default priority order: ENTSO-E -> Tibber -> Energy-Charts -> Elprisetjustnu -> Elering
            priority_order = ["entsoe", "tibber", "energy_charts", "elprisetjustnu", "elering"]
            active_providers = [
                (name, self.providers[name])
                for name in priority_order
                if name in self.providers
            ]
            for name, provider in self.providers.items():
                if name not in priority_order:
                    active_providers.append((name, provider))

        # 3. Attempt providers in order
        errors = []
        for name, provider in active_providers:
            try:
                logger.info("Attempting to fetch spot prices using %s provider...", provider.name)
                prices = provider.get_prices(start_date, end_date, bidding_zone)
                if prices:
                    if use_cache:
                        self.cache.save(name, bidding_zone, start_date, end_date, prices)
                        self.cache.save("auto", bidding_zone, start_date, end_date, prices)
                    return prices
            except Exception as e:
                logger.warning("Provider %s failed: %s", provider.name, str(e))
                errors.append(f"{provider.name}: {str(e)}")

        raise RuntimeError(
            f"All price providers failed for {bidding_zone} ({start_date} to {end_date}). Errors: {'; '.join(errors)}"
        )
