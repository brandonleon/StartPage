#!/bin/sh
set -e

exec uvicorn \
    --host 0.0.0.0 \
    --port 8080 \
    --workers "${WORKERS:-2}" \
    --log-level "${LOG_LEVEL:-info}" \
    main:app
