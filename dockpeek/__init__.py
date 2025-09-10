import os
import logging
from flask import Flask
from config import Config
from .extensions import login_manager, cors

def create_app(config_class=Config):
    logging.basicConfig(level=config_class.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    app = Flask(__name__)
    app.config.from_object(config_class)

    login_manager.init_app(app)
    cors.init_app(app)

    from . import auth
    app.register_blueprint(auth.auth_bp)

    from . import main
    app.register_blueprint(main.main_bp)

    return app