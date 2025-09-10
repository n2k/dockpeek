import os
import logging
from flask import Flask
from config import Config
from .extensions import login_manager, cors

def create_app(config_class=Config):
    """
    Tworzy i konfiguruje instancję aplikacji Flask.
    """
    # Konfiguracja logowania
    logging.basicConfig(level=config_class.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    # Inicjalizacja aplikacji
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicjalizacja rozszerzeń
    login_manager.init_app(app)
    cors.init_app(app)

    # Rejestracja Blueprints
    from . import auth
    app.register_blueprint(auth.auth_bp)

    from . import main
    app.register_blueprint(main.main_bp)

    return app