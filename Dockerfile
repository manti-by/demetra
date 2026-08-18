FROM python:3.13.9-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg git \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      | tee /etc/apt/sources.list.d/githubcli.list > /dev/null \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.21 /uv /uvx /bin/

RUN curl -fsSL https://opencode.ai/install | bash

WORKDIR /app/

COPY pyproject.toml uv.lock ./

ENV UV_PROJECT_ENVIRONMENT="/opt/venv"

RUN uv sync --frozen --no-dev --no-cache

FROM python:3.13.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git gnupg openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.opencode/bin/opencode /usr/local/bin/opencode
COPY --from=builder /usr/bin/gh /usr/bin/gh
COPY --from=builder /bin/uv /bin/uvx /bin/
COPY --from=builder /opt/venv /opt/venv

RUN useradd -m -s /bin/bash -d /home/demetra demetra

RUN mkdir -p /srv/demetra/src/ /var/log/demetra/
RUN chown -R demetra:demetra /srv/demetra/src/ /var/log/demetra/ /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
ENV UV_PATH="/bin/uv"

USER demetra

WORKDIR /srv/demetra/src/

CMD ["python", "main.py", "--help"]
