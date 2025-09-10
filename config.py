import os
from datetime import timedelta

class Config:
    """Główna klasa konfiguracyjna."""
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("ERROR: SECRET_KEY environment variable is not set.")

    # Dane logowania
    ADMIN_USERNAME = os.environ.get("USERNAME")
    ADMIN_PASSWORD = os.environ.get("PASSWORD")
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise RuntimeError("USERNAME and PASSWORD environment variables must be set.")
        
    # Ustawienia funkcji aplikacji
    TRAEFIK_ENABLE = os.environ.get("TRAEFIK_LABELS", "true").lower() == "true"
    TAGS_ENABLE = os.environ.get("TAGS", "true").lower() == "true"
    
    # Czas życia sesji
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    
    # Wersja aplikacji
    APP_VERSION = os.environ.get('VERSION', 'dev')
    
    # Konfiguracja Dockera
    DOCKER_TIMEOUT = 0.5
    
    # Ustawienia logowania
    LOG_LEVEL = "INFO"