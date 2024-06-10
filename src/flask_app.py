import secrets
from flask import Flask
from src.executor import executor
from .blueprints import bp
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore, hash_password
from flask_security.models import fsqla_v3 as fsqla
import os
from dotenv import load_dotenv, dotenv_values

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    executor.init_app(app)
    #app.secret_key = secrets.token_urlsafe(64)

    if test_config is None:
        app.config.from_envvar('MESSAGE_AUTOMATION_SETTINGS')
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # load .env file for security info
    load_dotenv()

    # get security info from env file, default if it doesn't exist
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", 'Dev')
    app.config['SECURITY_PASSWORD_SALT'] = os.getenv("PASSWORD_SALT",
                                                     '123456789012345678901234567890123456789')

    # remember cookie and session cookie
    app.config["REMEMBER_COOKIE_SAMESITE"] = "strict"
    app.config["SESSION_COOKIE_SAMESITE"] = "strict"

    # in-memory database setup
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # db connection object
    db = SQLAlchemy(app)

    # security models
    fsqla.FsModels.set_db_info(db)

    class Role(db.Model, fsqla.FsRoleMixin):
        pass
    
    class User(db.Model, fsqla.FsUserMixin):
        pass

    # security setup
    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    app.security = Security(app, user_datastore)

    # one time setup of user login info
    with app.app_context():
        db.create_all()
        # creates user if it doesn't exist
        if not app.security.datastore.find_user(email=os.getenv("LOGIN_EMAIL")):
            app.security.datastore.create_user(email=os.getenv("LOGIN_EMAIL"),
                                               password=hash_password(os.getenv("LOGIN_PASS")))
        db.session.commit()

    app.config['EXECUTOR_TYPE'] = 'thread'
    app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True
    app.register_blueprint(bp)

    return app
