import secrets

from flask import Flask

from src.executor import executor

from .blueprints import bp, auto_bp


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
    app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True
    app.register_blueprint(bp)
    app.register_blueprint(auto_bp, url_prefix='/downloads')

    return app
