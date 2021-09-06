import secrets

from flask import Flask
from src.executor import executor

from .blueprints import bp

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    executor.init_app(app)
    app.secret_key = secrets.token_urlsafe(64)

    if test_config is None:
        app.config.from_envvar('MESSAGE_AUTOMATION_SETTINGS')
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    app.config['EXECUTOR_TYPE'] = 'thread'
    app.register_blueprint(bp)

    return app
