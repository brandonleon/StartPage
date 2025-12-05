FROM python:3.10-slim

ENV LOG_LEVEL="info"\
    WORKERS=2 \
    ENVIRONMENT="production" \
    WORKING_DIR="/usr/startpage" \
    VIRTUAL_ENV="/usr/startpage/.venv"

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR $WORKING_DIR
COPY pyproject.toml uv.lock $WORKING_DIR

# System deps:
RUN pip install --no-cache-dir uv

# Project initialization:
RUN if [ "$ENVIRONMENT" = "production" ]; then \
        uv sync --frozen --no-dev; \
    else \
        uv sync --frozen; \
    fi

COPY . $WORKING_DIR
CMD uvicorn --host 0.0.0.0 --port 8080 --workers $WORKERS --log-level $LOG_LEVEL main:app
