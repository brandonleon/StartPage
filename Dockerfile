FROM ghcr.io/astral-sh/uv:python3.10-alpine

ENV LOG_LEVEL="info"\
    WORKERS=2 \
    ENVIRONMENT="production" \
    WORKING_DIR="/usr/startpage" \
    VIRTUAL_ENV="/usr/startpage/.venv"

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR $WORKING_DIR
COPY pyproject.toml uv.lock README.md $WORKING_DIR
COPY services $WORKING_DIR/services

# Build deps needed for uvloop wheels on Alpine
RUN apk add --no-cache build-base

# Project initialization:
RUN if [ "$ENVIRONMENT" = "production" ]; then \
        uv sync --frozen --no-dev; \
    else \
        uv sync --frozen; \
    fi

COPY . $WORKING_DIR
CMD ["./docker-entrypoint.sh"]
