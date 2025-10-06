FROM python:3.11-slim

ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

ENV VERSION=${VERSION} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/dockpeek/dockpeek" \
      org.opencontainers.image.url="https://github.com/dockpeek/dockpeek" \
      org.opencontainers.image.documentation="https://github.com/dockpeek/dockpeek#readme" \
      org.opencontainers.image.title="Dockpeek" \
      org.opencontainers.image.description="Docker container monitoring and management tool"

# Instalacja zależności systemowych przed instalacją Pythona
RUN apt-get update && apt-get install -y \
    curl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kopiowanie tylko requirements.txt dla lepszego cache'owania warstw
COPY requirements.txt .

# Instalacja zależności Pythona
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie reszty aplikacji (jako ostatnie dla cache'u)
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=15s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["sh", "-c", "gunicorn \
    --workers ${WORKERS:-4} \
    --worker-class gevent \
    --worker-connections 1000 \
    --bind 0.0.0.0:8000 \
    --timeout 300 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    run:app"]