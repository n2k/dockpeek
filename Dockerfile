FROM python:3.11-slim

# Ustawianie argumentów przekazywanych podczas budowania
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

# Ustawianie zmiennych środowiskowych dla Pythona i PIP
ENV VERSION=${VERSION} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Metadane obrazu zgodne ze standardem Open Containers Initiative
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/dockpeek/dockpeek" \
      org.opencontainers.image.url="https://github.com/dockpeek/dockpeek" \
      org.opencontainers.image.documentation="https://github.com/dockpeek/dockpeek#readme" \
      org.opencontainers.image.title="Dockpeek" \
      org.opencontainers.image.description="Docker container monitoring and management tool"

# Ustawienie katalogu roboczego w kontenerze
WORKDIR /app

# Kopiowanie pliku z zależnościami
COPY requirements.txt .

# Instalacja zależności (ten krok jest cachowany przez Dockera)
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie reszty kodu aplikacji
COPY . .

# Uwidocznienie portu, na którym działa aplikacja
EXPOSE 8000

# ZAKTUALIZOWANA KOMENDA URUCHOMIENIOWA
# Używamy Gunicorn do uruchomienia aplikacji w trybie produkcyjnym,
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "run:app"]