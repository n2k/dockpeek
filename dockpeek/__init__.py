import os
import logging
from flask import Flask
from config import Config
from .extensions import login_manager, cors

def create_app(config_class=Config):
    log_level = getattr(logging, config_class.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='[%(levelname)s] - %(message)s'
    )
    
    if log_level > logging.DEBUG:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('gunicorn').setLevel(logging.WARNING)
        logging.getLogger('gunicorn.access').setLevel(logging.WARNING)
        logging.getLogger('gunicorn.error').setLevel(logging.ERROR)
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    login_manager.init_app(app)
    cors.init_app(app)
    
    if not app.config.get('DISABLE_AUTH', False):
        logging.debug("Authentication enabled")
    else:
        logging.info("Authentication disabled")

    from . import auth
    app.register_blueprint(auth.auth_bp)

    from . import main
    app.register_blueprint(main.main_bp)

    return app