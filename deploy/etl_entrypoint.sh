#!/bin/bash
set -e

echo "Starting ETL pipeline..."

# Fix permissions for data volumes
echo "Fixing permissions..."
chown -R appuser:appuser /app/data

echo "Switched to appuser for pipeline execution..."

su appuser -c "set -e && \
    python -m src.data_gen.download_wiki && \
    python -m src.data_gen.anonymize && \
    python -m src.data_gen.ingest"

echo "ETL completed"
