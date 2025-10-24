import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("ERROR: SECRET_KEY environment variable is not set.")

    DISABLE_AUTH = os.environ.get("DISABLE_AUTH", "false").lower() == "true"

    if not DISABLE_AUTH:
        ADMIN_USERNAME = os.environ.get("USERNAME")
        ADMIN_PASSWORD = os.environ.get("PASSWORD")
        if not ADMIN_USERNAME or not ADMIN_PASSWORD:
            raise RuntimeError("USERNAME and PASSWORD environment variables must be set.")
    else:
        ADMIN_USERNAME = None
        ADMIN_PASSWORD = None
        
    TRAEFIK_ENABLE = os.environ.get("TRAEFIK_LABELS", "true").lower() == "true"
    TAGS_ENABLE = os.environ.get("TAGS", "true").lower() == "true"
    PORT_RANGE_GROUPING = os.environ.get("PORT_RANGE_GROUPING", "true").lower() == "true"
    PORT_RANGE_THRESHOLD = int(os.environ.get("PORT_RANGE_THRESHOLD", "5"))
    
    # Inactive container tracking configuration
    INACTIVE_TRACKING_ENABLE = os.environ.get("INACTIVE_TRACKING", "true").lower() == "true"
    PERSIST_INACTIVE = os.environ.get("PERSIST_INACTIVE", "")
    INACTIVE_IGNORE_THRESHOLD = os.environ.get("INACTIVE_IGNORE", "5min")
    INACTIVE_WARN_THRESHOLD = os.environ.get("INACTIVE_WARN", "30min")
    INACTIVE_CRITICAL_THRESHOLD = os.environ.get("INACTIVE_CRITICAL", "1h")
    INACTIVE_WARN_COLOR = os.environ.get("INACTIVE_WARN_COLOR", "#ff9e00")
    INACTIVE_CRITICAL_COLOR = os.environ.get("INACTIVE_CRITICAL_COLOR", "#ff0000")
    
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    
    APP_VERSION = os.environ.get('VERSION', 'dev')
        
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    DOCKER_CONNECTION_TIMEOUT = float(os.environ.get("DOCKER_CONNECTION_TIMEOUT", "0.5"))
    
    PORT = int(os.environ.get("PORT", "8000"))