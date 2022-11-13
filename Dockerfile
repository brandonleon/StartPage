FROM python:3.10-slim

ENV LOG_LEVEL="info"\
    WORKERS=2 \
    ENVIRONMENT="production" \
    POETRY_VERSION=1.1.13 \
    WORKING_DIR="/usr/startpage"

WORKDIR $WORKING_DIR
COPY poetry.lock pyproject.toml $WORKING_DIR

# System deps:
RUN pip install "poetry==$POETRY_VERSION"

# Project initialization:
RUN poetry config virtualenvs.create false \
  && poetry install $(test "ENVIRONMENT" == production && echo "--no-dev") --no-interaction --no-ansi

COPY . $WORKING_DIR
CMD uvicorn --host 0.0.0.0 --port 8080 --workers $WORKERS --log-level $LOG_LEVEL main:app