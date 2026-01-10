# =====================
# Stage 1: Builder
# =====================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS builder

WORKDIR /build

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY prompts/ ./prompts/
COPY Makefile ./
COPY deploy/*.sh ./
COPY data/*.json ./data/


# =====================
# Stage 2: Runtime
# =====================
FROM python:3.12-slim-bookworm AS runtime

ARG UID=1000
ARG GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd make \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g ${GID} appuser \
    && useradd -u ${UID} -g appuser -m -s /bin/bash appuser

WORKDIR /app

# Single COPY from builder
COPY --from=builder --chown=appuser:appuser /build ./

# Organize and set permissions
RUN mv entrypoint.sh etl_entrypoint.sh / \
    && chmod +x /*.sh \
    && chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

# Download NLTK data
RUN python -m nltk.downloader averaged_perceptron_tagger_eng punkt_tab

ENTRYPOINT ["/entrypoint.sh"]
