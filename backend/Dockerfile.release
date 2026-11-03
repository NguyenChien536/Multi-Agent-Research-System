FROM python:3.11-slim-bookworm AS dependencies

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.lock.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.lock.txt

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    DEBUG=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt .
RUN --mount=type=bind,from=dependencies,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.lock.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
RUN getent passwd root >/dev/null \
    && groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid 10001 --create-home appuser \
    && mkdir -p /app/storage/artifacts \
    && chown -R 10001:10001 /app \
    && test "$(id -u appuser)" = 10001

ARG VCS_URL
ARG VCS_REF=unknown
LABEL org.opencontainers.image.source=$VCS_URL
LABEL org.opencontainers.image.revision=$VCS_REF

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
