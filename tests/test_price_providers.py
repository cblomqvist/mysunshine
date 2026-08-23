"""Unit and integration tests for electricity spot price providers.
Built using standard library unittest and unittest.mock for zero-dependency execution.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.price_providers.base import PricePoint, PriceProvider
from src.price_providers.cache import PriceCache
from src.price_providers.elering import EleringPriceProvider
from src.price_providers.entsoe import EntsoePriceProvider
from src.price_providers.tibber import TibberPriceProvider
from src.price_providers.manager import PriceManager


class TestPricePointAndBase(unittest.TestCase):
    """Test PricePoint data structure and base conversion utilities."""

    def test_price_point_properties_and_serialization(self):
        pt = PricePoint(
            timestamp="2025-01-01T00:00:00+00:00",
            price_eur_mwh=50.0,
            price_sek_kwh=0.5675,
            bidding_zone="SE3",
            resolution_minutes=60,
            provider="TestProvider",
        )

        self.assertAlmostEqual(pt.price_ore_kwh, 56.75, places=3)
        d = pt.to_dict()
        self.assertEqual(d["price_ore_kwh"], 56.75)
        self.assertEqual(d["bidding_zone"], "SE3")

        # Test deserialization
        restored = PricePoint.from_dict(d)
        self.assertEqual(restored.timestamp, pt.timestamp)
        self.assertEqual(restored.price_eur_mwh, pt.price_eur_mwh)
        self.assertEqual(restored.price_sek_kwh, pt.price_sek_kwh)

    def test_eur_mwh_to_sek_kwh_conversion(self):
        dt = datetime(2025, 6, 1, tzinfo=timezone.utc)
        # 100 EUR/MWh = 0.1 EUR/kWh. With rate 11.35 -> 1.135 SEK/kWh
        sek_kwh = PriceProvider.eur_mwh_to_sek_kwh(100.0, dt, custom_rate=11.35)
        self.assertAlmostEqual(sek_kwh, 1.135, places=4)


class TestPriceCache(unittest.TestCase):
    """Test local disk caching mechanics."""

    def test_cache_save_and_retrieve(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = PriceCache(cache_dir=tmp_dir)
            s_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
            e_date = datetime(2025, 1, 2, tzinfo=timezone.utc)

            # Cache miss initially
            self.assertIsNone(cache.get("elering", "SE3", s_date, e_date))

            pts = [
                PricePoint("2025-01-01T00:00:00+00:00", 40.0, 0.454, "SE3", 60, "elering"),
                PricePoint("2025-01-01T01:00:00+00:00", 45.0, 0.510, "SE3", 60, "elering"),
            ]

            saved_path = cache.save("elering", "SE3", s_date, e_date, pts)
            self.assertTrue(saved_path.endswith(".json"))
            self.assertTrue(os.path.exists(saved_path))

            # Cache hit
            loaded = cache.get("elering", "SE3", s_date, e_date)
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].price_eur_mwh, 40.0)
            self.assertEqual(loaded[1].price_eur_mwh, 45.0)


class TestEleringPriceProvider(unittest.TestCase):
    """Test Elering public API adapter."""

    @patch("urllib.request.urlopen")
    def test_elering_fetch_success(self, mock_urlopen):
        provider = EleringPriceProvider()
        s_date = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        e_date = datetime(2025, 1, 1, 2, 0, tzinfo=timezone.utc)

        mock_data = {
            "success": True,
            "data": {
                "se3": [
                    {"timestamp": 1735689600, "price": 30.50},  # 2025-01-01 00:00 UTC
                    {"timestamp": 1735693200, "price": 28.00},  # 2025-01-01 01:00 UTC
                ]
            },
        }

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        prices = provider.get_prices(s_date, e_date, "SE3")
        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0].price_eur_mwh, 30.50)
        self.assertEqual(prices[1].price_eur_mwh, 28.00)
        self.assertEqual(prices[0].provider, "Elering")
        self.assertEqual(prices[0].bidding_zone, "SE3")


class TestEntsoePriceProvider(unittest.TestCase):
    """Test ENTSO-E XML price provider adapter."""

    def test_missing_api_key_raises_error(self):
        provider = EntsoePriceProvider(api_key=None)
        provider.api_key = None
        with self.assertRaises(ValueError):
            provider.get_prices(datetime.now(), datetime.now(), "SE3")

    @patch("urllib.request.urlopen")
    def test_entsoe_xml_parsing_success(self, mock_urlopen):
        provider = EntsoePriceProvider(api_key="mock_secret_token_123")
        s_date = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        e_date = datetime(2025, 1, 1, 2, 0, tzinfo=timezone.utc)

        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0">
            <TimeSeries>
                <Period>
                    <timeInterval>
                        <start>2025-01-01T00:00Z</start>
                        <end>2025-01-01T02:00Z</end>
                    </timeInterval>
                    <resolution>PT60M</resolution>
                    <Point>
                        <position>1</position>
                        <price.amount>42.50</price.amount>
                    </Point>
                    <Point>
                        <position>2</position>
                        <price.amount>38.10</price.amount>
                    </Point>
                </Period>
            </TimeSeries>
        </Publication_MarketDocument>
        """

        mock_response = MagicMock()
        mock_response.read.return_value = mock_xml.encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        prices = provider.get_prices(s_date, e_date, "SE3")
        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0].price_eur_mwh, 42.50)
        self.assertEqual(prices[1].price_eur_mwh, 38.10)
        self.assertEqual(prices[0].resolution_minutes, 60)
        self.assertEqual(prices[0].provider, "ENTSO-E")


class TestTibberPriceProvider(unittest.TestCase):
    """Test Tibber GraphQL price provider adapter."""

    def test_missing_api_token_raises_error(self):
        provider = TibberPriceProvider(api_token=None)
        provider.api_token = None
        with self.assertRaises(ValueError):
            provider.get_prices(datetime.now(), datetime.now(), "SE3")

    @patch("urllib.request.urlopen")
    def test_tibber_graphql_fetch_success(self, mock_urlopen):
        provider = TibberPriceProvider(api_token="mock_tibber_token_xyz")
        # Cover range for 2025-01-01 in timezone +01:00
        s_date = datetime(2024, 12, 31, 23, 0, tzinfo=timezone.utc)
        e_date = datetime(2025, 1, 1, 23, 0, tzinfo=timezone.utc)

        mock_gql_data = {
            "data": {
                "viewer": {
                    "homes": [
                        {
                            "id": "mock_home_123",
                            "currentSubscription": {
                                "priceInfo": {
                                    "today": [
                                        {
                                            "total": 0.85,
                                            "energy": 0.55,
                                            "startsAt": "2025-01-01T00:00:00+01:00",
                                        },
                                        {
                                            "total": 0.90,
                                            "energy": 0.60,
                                            "startsAt": "2025-01-01T01:00:00+01:00",
                                        },
                                    ]
                                }
                            },
                        }
                    ]
                }
            }
        }

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_gql_data).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        prices = provider.get_prices(s_date, e_date, "SE3")
        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0].price_sek_kwh, 0.55)
        self.assertEqual(prices[1].price_sek_kwh, 0.60)
        self.assertEqual(prices[0].provider, "Tibber")


class TestPriceManager(unittest.TestCase):
    """Test PriceManager fallback and caching orchestration."""

    def test_manager_fallback_and_cache_integration(self):
        s_date = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        e_date = datetime(2025, 1, 1, 2, 0, tzinfo=timezone.utc)

        class FailingProvider(PriceProvider):
            @property
            def name(self) -> str:
                return "FailingMock"

            def get_prices(self, start, end, zone):
                raise ConnectionError("Server unavailable")

        class WorkingProvider(PriceProvider):
            @property
            def name(self) -> str:
                return "WorkingMock"

            def get_prices(self, start, end, zone):
                return [
                    PricePoint("2025-01-01T00:00:00Z", 55.0, 0.62, zone, 60, self.name)
                ]

        custom_providers = {
            "entsoe": FailingProvider(),
            "elering": WorkingProvider(),
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = PriceManager(cache_dir=tmp_dir, custom_providers=custom_providers)

            # 1. Fetch triggers fallback to WorkingProvider
            prices = manager.get_prices(s_date, e_date, "SE3")
            self.assertEqual(len(prices), 1)
            self.assertEqual(prices[0].price_eur_mwh, 55.0)
            self.assertEqual(prices[0].provider, "WorkingMock")

            # 2. Subsequent call retrieves from cache directly
            cached_prices = manager.get_prices(s_date, e_date, "SE3")
            self.assertEqual(len(cached_prices), 1)
            self.assertEqual(cached_prices[0].price_eur_mwh, 55.0)


if __name__ == "__main__":
    unittest.main()
