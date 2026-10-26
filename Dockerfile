FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY alembic.ini ./
COPY migrations ./migrations
COPY fixtures ./fixtures

ENV GPU_TWIN_FLEET_FIXTURE_PATH=/app/fixtures/fleet.json

EXPOSE 8000
# Single worker on purpose: writes are serialized by an in-process lock (AD-1, NFR-12 process-local baseline).
CMD ["sh", "-c", "alembic upgrade head && uvicorn gpu_lab_twin.main:app --host 0.0.0.0 --port 8000"]
