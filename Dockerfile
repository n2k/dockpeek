FROM python:3.11-slim AS builder

ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /install

COPY requirements.txt .

RUN pip install --prefix=/install/deps --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS final

ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/dockpeek/dockpeek" \
      org.opencontainers.image.url="https://github.com/dockpeek/dockpeek" \
      org.opencontainers.image.documentation="https://github.com/dockpeek/dockpeek#readme" \
      org.opencontainers.image.title="Dockpeek" \
      org.opencontainers.image.description="Docker container monitoring and management tool" \
      org.opencontainers.image.authors="Dockpeek"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /install/deps /usr/local

COPY . .

EXPOSE 8000

ENTRYPOINT ["python"]
CMD ["app.py"]
