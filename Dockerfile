FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      | tee /etc/apt/sources.list.d/githubcli.list > /dev/null \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN curl -fsSL https://opencode.ai/install | bash

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

FROM python:3.13-slim

COPY --from=builder /root/.opencode/bin/opencode /usr/local/bin/opencode
COPY --from=builder /usr/bin/gh /usr/bin/gh
COPY --from=builder /bin/uv /bin/uvx /bin/
COPY --from=builder /app/.venv /app/.venv

WORKDIR /app
COPY . .

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "main.py", "--help"]
