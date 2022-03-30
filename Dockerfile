FROM python:3.10
WORKDIR /usr/src/app
COPY . .
RUN pip3 install poetry
RUN poetry install --no-dev
EXPOSE 800  0
ENV LOG_LEVEL "info"
ENV WORKERS 2
CMD poetry run uvicorn --host 0.0.0.0 --port 8000 --workers $WORKERS --log-level $LOG_LEVEL main:app