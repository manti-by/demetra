---
title: 'MNT-321: External providers prices'
generated: {by: demetra, at: '2026-11-24T00:00:00Z'}
description: This session implemented a unified pricing service for external LLM providers (OpenRouter, MiniMax, DeepSeek) that fetches rates, calculates costs per invocation, and stores pricing snapshots in the session history table alongside computed costs.
type: implementation
status: stable
session_id: ses_df1fa4b75ffe5x7UVJ2D59A6gy
services: [api, library, agents/opencode, llm/openrouter, persistence/database, pricing, c4d5e6f7a8b9_add_session_history_price_column, pyproject, SessionHistory.test, SessionHistory, conftest, test_api, test_database, test_opencode, test_openrouter, test_pricing, uv, INDEX, 2026-11-24-mnt-321-external-providers-prices]
branch: mnt-321-external-providers-prices
tickets: [MNT-321]
tags: [wiki, feature, backend]
related: [2026-10-25-session-history-cost-and-failure-reasons.md, 2026-10-27-mnt-260-openrouter-call-history.md, 2026-10-25-session-history-per-invocation-rows.md, 2026-08-18-migrate-llm-groq-to-openrouter.md]
---

# MNT-321: External providers prices

## TL;DR
This session implemented cost calculation for external LLM providers (OpenRouter, MiniMax, DeepSeek) in addition to OpenCode. A unified pricing service was added to fetch rates and calculate costs per invocation. The session history table was extended to store pricing snapshots alongside computed costs.

## Overview
The changes introduce a pricing service that handles rate lookup and cost calculation across multiple LLM providers. OpenRouter rates are fetched from its API, while MiniMax and DeepSeek use static rates from settings. Costs are computed per invocation and stored in the session history alongside the pricing snapshot.

## Step 1 — Add ModelPrice dataclass and price field
**File:** demetra/library/models.py:209
```python
@dataclass
class ModelPrice:
    """USD price per one million tokens for one model of one provider."""
    provider: str
    source: str
    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0
```

**File:** demetra/library/models.py:251
```python
class SessionHistory:
    price: dict[str, float] | None = None
```

## Step 2 — Add price column to session_history table
**File:** demetra/library/tables.py:268
```python
session_history = Table(
    Column(name="price", type_=JSONB(), nullable=True),
)
```

## Step 3 — Create unified pricing service
The pricing service handles rate lookup and cost calculation:
- OpenRouter: Fetches rates from its API
- MiniMax/DeepSeek: Uses static rates from settings
- OpenCode: Uses existing cost reporting

**File:** demetra/services/pricing.py
```python
async def get_price(model: str, default_provider: str | None = None) -> ModelPrice | None:
    """Resolve the per-million-token rates for one model."""
    provider = resolve_provider(model, default_provider)
    if provider == "openrouter":
        return await _fetch_openrouter_price(model)
    elif provider in ("minimax", "deepseek"):
        return _get_static_price(model, provider)
    return None
```

## Step 4 — Integrate pricing into session capture
Costs are now computed and stored for both agent invocations and LLM calls:

**File:** demetra/services/agents/opencode.py:945
```python
if export is not None and model is not None:
    provider = resolve_provider(model=model)
    if provider is not None and provider != "opencode":
        price = await get_price(model=model)
        if price is not None:
            cost = calculate_cost(usage=export.tokens, price=price)
```

**File:** demetra/services/llm/openrouter.py:131
```python
price = await get_price(model=model, default_provider="openrouter")
cost = calculate_cost(usage=usage, price=price) if usage is not None and price is not None else None
```

## Test Results
All 1627 tests passed successfully. The new pricing functionality was verified through:
- Unit tests for the pricing service
- Integration tests for session history capture
- End-to-end workflow tests with external providers

## Follow-ups
- None

## References
- External: https://linear.app/mnt/issue/MNT-321/external-providers-prices
- Related: [2026-10-25-session-history-cost-and-failure-reasons](/pages/2026-10-25-session-history-cost-and-failure-reasons.md)
- Related: [2026-10-27-mnt-260-openrouter-call-history](/pages/2026-10-27-mnt-260-openrouter-call-history.md)
- Related: [2026-10-25-session-history-per-invocation-rows](/pages/2026-10-25-session-history-per-invocation-rows.md)
- Related: [2026-08-18-migrate-llm-groq-to-openrouter](/pages/2026-08-18-migrate-llm-groq-to-openrouter.md)

> **Consistency note (2026-11-27, Consistency Agent):** Two code details differ from Steps 3–4 above: (1) `MINIMAX_PRICES` and `DEEPSEEK_PRICES` live in `demetra/services/pricing.py:26-44` (not `demetra/settings.py`), and `get_price` takes a keyword-only `*, default_provider: Provider | None = None` backed by the 1-hour `_openrouter_cache`; (2) `capture_agent_session` (`demetra/services/agents/opencode.py:1130-1145`) passes `rate_card=price` into `record_agent_invocation` rather than billing cumulative `export.tokens` directly, so external-provider cost is computed on the per-invocation token delta when vendor cost is absent or zero.
