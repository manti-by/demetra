from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from demetra.library.models import ModelPrice, TokenUsage
from demetra.services import pricing


@pytest.fixture(autouse=True)
def stub_pricing_fetch():
    """Override the suite-wide stub so the fetch itself can be exercised."""
    pricing._openrouter_cache.clear()
    yield
    pricing._openrouter_cache.clear()


class TestResolveProvider:
    def test_opencode_providers_are_vendor_priced(self):
        assert pricing.resolve_provider(model="opencode/minimax-m2.5-free") == "opencode"
        assert pricing.resolve_provider(model="opencode-go/minimax-m3") == "opencode"

    def test_external_providers_are_resolved_from_prefix(self):
        assert pricing.resolve_provider(model="openrouter/minimax/minimax-m3") == "openrouter"
        assert pricing.resolve_provider(model="minimax/m3") == "minimax"
        assert pricing.resolve_provider(model="deepseek/deepseek-v4-pro") == "deepseek"

    def test_default_provider_applies_only_without_a_known_prefix(self):
        assert pricing.resolve_provider(model="openai/gpt-oss-120b") is None
        assert pricing.resolve_provider(model="openai/gpt-oss-120b", default_provider="openrouter") == "openrouter"
        assert pricing.resolve_provider(model="deepseek/deepseek-flash", default_provider="openrouter") == "deepseek"


class TestCalculateCost:
    def test_each_counter_is_billed_at_its_own_rate(self):
        usage = TokenUsage(input=1_000_000, output=500_000, reasoning=200_000, cache_read=300_000, cache_write=100_000)
        price = ModelPrice(provider="openrouter", source="test", input=1.0, output=2.0, cache_read=0.1, cache_write=0.5)

        assert pricing.calculate_cost(usage=usage, price=price) == pytest.approx(2.48)

    def test_zero_usage_costs_nothing(self):
        price = ModelPrice(provider="minimax", source="test", input=0.3, output=1.2)

        assert pricing.calculate_cost(usage=TokenUsage(), price=price) == 0.0


class TestPriceToDict:
    def test_only_billable_rates_are_persisted(self):
        price = ModelPrice(provider="deepseek", source="test", input=0.3, output=1.2, cache_read=0.006)

        assert pricing.price_to_dict(price) == {
            "input": 0.3,
            "output": 1.2,
            "cache_read": 0.006,
            "cache_write": 0.0,
        }


class TestGetPrice:
    async def test_opencode_model_needs_no_rate(self):
        assert await pricing.get_price(model="opencode-go/deepseek-v4-flash") is None

    async def test_unknown_provider_needs_no_rate(self):
        assert await pricing.get_price(model="openai/gpt-oss-120b") is None

    async def test_openrouter_model_is_looked_up_and_cached(self):
        rates = {"minimax/minimax-m3": ModelPrice(provider="openrouter", source="test", input=0.3, output=1.2)}
        with patch.object(pricing, "_fetch_openrouter_prices", new_callable=AsyncMock, return_value=rates) as fetch:
            first = await pricing.get_price(model="openrouter/minimax/minimax-m3")
            second = await pricing.get_price(model="openrouter/minimax/minimax-m3")

        assert first == rates["minimax/minimax-m3"]
        assert second == rates["minimax/minimax-m3"]
        fetch.assert_awaited_once()

    async def test_openrouter_prefix_is_stripped_before_lookup(self):
        rates = {"minimax/minimax-m3": ModelPrice(provider="openrouter", source="test", input=0.3, output=1.2)}
        with patch.object(pricing, "_fetch_openrouter_prices", new_callable=AsyncMock, return_value=rates):
            price = await pricing.get_price(model="openrouter/minimax/minimax-m3")

        assert price is not None
        assert price.input == 0.3

    async def test_minimax_rate_comes_from_the_static_table(self):
        price = await pricing.get_price(model="minimax/M3")

        assert price is not None
        assert price.provider == "minimax"
        assert price.input == 0.30
        assert price.output == 1.20
        assert price.cache_read == 0.06

    async def test_deepseek_rate_comes_from_the_static_table(self):
        price = await pricing.get_price(model="deepseek/deepseek-v4-pro")

        assert price is not None
        assert price.provider == "deepseek"
        assert price.input == 1.32
        assert price.output == 3.96

    async def test_unknown_static_model_has_no_rate(self):
        assert await pricing.get_price(model="minimax/unknown-model") is None


class TestFetchOpenrouterPrices:
    async def test_parses_the_public_models_payload(self):
        payload = {
            "data": [
                {
                    "id": "deepseek/deepseek-chat",
                    "pricing": {
                        "prompt": "0.000001",
                        "completion": "0.000005",
                        "input_cache_read": "0.0000001",
                    },
                },
                {"id": "openai/broken", "pricing": None},
            ]
        }
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = AsyncMock(return_value=payload)
        response_cm = MagicMock()
        response_cm.__aenter__ = AsyncMock(return_value=response)
        response_cm.__aexit__ = AsyncMock(return_value=None)
        session = MagicMock()
        session.get = MagicMock(return_value=response_cm)
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch.object(pricing.aiohttp, "ClientSession", return_value=session_cm):
            prices = await pricing._fetch_openrouter_prices()

        assert list(prices) == ["deepseek/deepseek-chat"]
        assert prices["deepseek/deepseek-chat"].input == pytest.approx(1.0)
        assert prices["deepseek/deepseek-chat"].output == pytest.approx(5.0)
        assert prices["deepseek/deepseek-chat"].cache_read == pytest.approx(0.1)
        assert prices["deepseek/deepseek-chat"].cache_write == pytest.approx(1.0)

    async def test_network_failure_degrades_to_none(self):
        with patch.object(
            pricing, "_fetch_openrouter_prices", new_callable=AsyncMock, side_effect=aiohttp.ClientError("offline")
        ):
            assert await pricing.get_price(model="openrouter/any/model") is None
