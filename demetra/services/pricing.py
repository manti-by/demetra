import logging
import time
from typing import Literal

import aiohttp

from demetra.library.models import ModelPrice, TokenUsage
from demetra.settings import OPENROUTER


logger = logging.getLogger(__name__)


Provider = Literal["opencode", "openrouter", "minimax", "deepseek"]

RATES_PER_TOKEN = 1_000_000

PRICE_CACHE_TTL_SECONDS = 3600

OPENROUTER_MODELS_PATH = "/models"

MINIMAX_SOURCE = "https://www.minimax.io/pricing"

DEEPSEEK_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing"

MINIMAX_PRICES: dict[str, ModelPrice] = {
    "m3": ModelPrice(provider="minimax", source=MINIMAX_SOURCE, input=0.30, output=1.20, cache_read=0.06),
    "m3.1-flash": ModelPrice(provider="minimax", source=MINIMAX_SOURCE, input=0.15, output=0.60, cache_read=0.015),
}

DEEPSEEK_PRICES: dict[str, ModelPrice] = {
    "deepseek-flash": ModelPrice(
        provider="deepseek", source=DEEPSEEK_SOURCE, input=0.30, output=1.20, cache_read=0.006
    ),
    "deepseek-v4-flash": ModelPrice(
        provider="deepseek", source=DEEPSEEK_SOURCE, input=0.30, output=1.20, cache_read=0.006
    ),
    "deepseek-v4-flash-vision-exp": ModelPrice(
        provider="deepseek", source=DEEPSEEK_SOURCE, input=0.30, output=1.20, cache_read=0.006
    ),
    "deepseek-v4-pro": ModelPrice(
        provider="deepseek", source=DEEPSEEK_SOURCE, input=1.32, output=3.96, cache_read=0.044
    ),
}


class _OpenRouterPriceCache:
    """In-process snapshot of the OpenRouter rate card with a monotonic TTL."""

    def __init__(self) -> None:
        self.prices: dict[str, ModelPrice] = {}
        self.fetched_at: float | None = None

    def fresh(self) -> dict[str, ModelPrice] | None:
        """Return the cached rates while they are still fresh."""
        if self.fetched_at is None:
            return None
        if time.monotonic() - self.fetched_at >= PRICE_CACHE_TTL_SECONDS:
            return None
        return self.prices

    def set(self, prices: dict[str, ModelPrice]) -> None:
        """Replace the snapshot and restart the TTL."""
        self.prices = prices
        self.fetched_at = time.monotonic()

    def clear(self) -> None:
        """Drop the snapshot so the next lookup refetches."""
        self.prices = {}
        self.fetched_at = None


_openrouter_cache = _OpenRouterPriceCache()


def resolve_provider(model: str, *, default_provider: Provider | None = None) -> Provider | None:
    """Resolve the provider serving a serialized model string.

    ``opencode`` and ``opencode-go`` are the vendor-priced OpenCode providers;
    their calls already carry a cost in the export, so no rate lookup is needed.
    A model with no recognized prefix is assigned ``default_provider``, which
    lets direct OpenRouter calls record a model such as ``openai/gpt-oss-120b``.

    Args:
        model: The serialized model string from an export or LLM config.
        default_provider: Provider to assume when the model has no known prefix.

    Returns:
        Provider | None: The resolved provider, or None when no rate applies.
    """
    prefix = model.split("/", 1)[0].lower() if "/" in model else ""
    providers: dict[str, Provider] = {
        "opencode": "opencode",
        "opencode-go": "opencode",
        "openrouter": "openrouter",
        "minimax": "minimax",
        "deepseek": "deepseek",
    }
    return providers.get(prefix, default_provider)


def _model_id(model: str) -> str:
    """Strip an OpenCode variant suffix and a known provider prefix, leaving the vendor's model id."""
    model = model.split("#", 1)[0]
    if "/" not in model:
        return model
    prefix, rest = model.split("/", 1)
    known = ("opencode", "opencode-go", "openrouter", "minimax", "deepseek")
    return rest if prefix.lower() in known else model


def _per_million(value: object) -> float:
    """Convert a per-token OpenRouter rate into a per-million-token rate."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0.0
    try:
        return float(value) * RATES_PER_TOKEN
    except ValueError:
        return 0.0


def _price_from_openrouter(pricing: dict, source: str) -> ModelPrice:
    """Build a rate card from one OpenRouter ``data[]`` pricing object."""
    input_rate = _per_million(pricing.get("prompt"))
    output_rate = _per_million(pricing.get("completion"))
    return ModelPrice(
        provider="openrouter",
        source=source,
        input=input_rate,
        output=output_rate,
        cache_read=_per_million(pricing["input_cache_read"]) if "input_cache_read" in pricing else input_rate,
        cache_write=_per_million(pricing["input_cache_write"]) if "input_cache_write" in pricing else input_rate,
    )


async def _fetch_openrouter_prices() -> dict[str, ModelPrice]:
    """Fetch the public OpenRouter model list and index it by model id."""
    url = f"{OPENROUTER['base_url'].rstrip('/')}{OPENROUTER_MODELS_PATH}"
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise ValueError("OpenRouter models response has no data list")
    prices: dict[str, ModelPrice] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        pricing = entry.get("pricing")
        if isinstance(model_id, str) and isinstance(pricing, dict):
            prices[model_id] = _price_from_openrouter(pricing=pricing, source=url)
    return prices


async def _refresh_openrouter_prices() -> dict[str, ModelPrice] | None:
    """Fetch and cache the OpenRouter rate card, degrading to None on failure."""
    try:
        prices = await _fetch_openrouter_prices()
    except (aiohttp.ClientError, TimeoutError, ValueError, TypeError):
        logger.warning("Failed to fetch OpenRouter prices", exc_info=True)
        return None
    _openrouter_cache.set(prices)
    return prices


async def get_price(model: str, *, default_provider: Provider | None = None) -> ModelPrice | None:
    """Resolve the current rate card for a model, when one is published.

    OpenRouter rates are fetched from its public models endpoint and cached for
    one hour; MiniMax and DeepSeek rates are snapshots of their international
    price pages. OpenCode models return None because their cost is already
    reported by the export.

    Args:
        model: The serialized model string.
        default_provider: Provider to assume for models with no known prefix.

    Returns:
        ModelPrice | None: The rate card, or None when no price is available.
    """
    provider = resolve_provider(model=model, default_provider=default_provider)
    if provider is None or provider == "opencode":
        return None
    if provider == "openrouter":
        cached = _openrouter_cache.fresh()
        prices = cached if cached is not None else await _refresh_openrouter_prices()
        if prices is None:
            return None
        return prices.get(_model_id(model)) or prices.get(model)
    table = MINIMAX_PRICES if provider == "minimax" else DEEPSEEK_PRICES
    return table.get(_model_id(model).lower())


def calculate_cost(usage: TokenUsage, price: ModelPrice) -> float:
    """Compute a USD cost from disjoint token counters and a rate card.

    Reasoning tokens are billed at the output rate. All rates are per one
    million tokens, so the summed charge is divided by that same factor.

    Args:
        usage: The token counters to bill.
        price: The rate card to bill them at.

    Returns:
        float: The cost in USD.
    """
    return (
        usage.input * price.input
        + (usage.output + usage.reasoning) * price.output
        + usage.cache_read * price.cache_read
        + usage.cache_write * price.cache_write
    ) / RATES_PER_TOKEN


def price_to_dict(price: ModelPrice) -> dict[str, float]:
    """Return the billable rates of a rate card for JSONB persistence."""
    return {
        "input": price.input,
        "output": price.output,
        "cache_read": price.cache_read,
        "cache_write": price.cache_write,
    }
