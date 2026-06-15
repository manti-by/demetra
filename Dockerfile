FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates gnupg wget

RUN wget https://releases.astral.sh/github/uv/releases/download/0.11.21/uv-x86_64-unknown-linux-gnu.tar.gz && \
    tar -xzf uv-x86_64-unknown-linux-gnu.tar.gz && \
    install -m 755 uv-x86_64-unknown-linux-gnu/uv /usr/local/bin/ && \
    install -m 755 uv-x86_64-unknown-linux-gnu/uvx /usr/local/bin/ && \
    rm -rf uv-x86_64-unknown-linux-gnu.tar.gz uv-x86_64-unknown-linux-gnu

RUN curl -fsSL https://opencode.ai/install | bash

RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    | tee /etc/apt/sources.list.d/githubcli.list > /dev/null

RUN apt-get update && apt-get install -y gh

RUN rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

FROM python:3.13-slim

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/bin/uvx /usr/local/bin/uvx

COPY --from=builder /root/.opencode/bin/opencode /usr/local/bin/opencode
COPY --from=builder /usr/bin/gh /usr/bin/gh

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /app/.venv /app/.venv

WORKDIR /app
COPY . .

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "main.py", "--help"]
