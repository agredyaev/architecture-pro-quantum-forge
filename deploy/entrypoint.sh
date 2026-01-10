#!/bin/bash
set -e

# Wait for Redis
if [ -n "$REDIS_URL" ]; then
    echo "Waiting for Redis..."
    while ! nc -z redis 6379 2>/dev/null; do
        sleep 1
    done
    echo "Redis is ready"
fi

# Check vector DB
if [ ! -d "/app/data/chroma_storage" ] || [ -z "$(ls -A /app/data/chroma_storage 2>/dev/null)" ]; then
    echo "ERROR: Vector database not found. Run ETL first: make docker-etl"
    exit 1
fi

echo "Starting RAG bot..."
exec python -m src.bot.main
