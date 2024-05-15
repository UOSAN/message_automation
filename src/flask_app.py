import secrets
from flask import Flask
from src.executor import executor
from .blueprints import bp
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemySessionUserDatastore, hash_password
from flask_security.models import fsqla_v3 as fsqla

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

    # get security key, replace with environment variable from secrets.token_urlsafe()
    app.config['SECRET_KEY'] = app.config.from_envvar("SECRET_KEY",'a11sm226j8oXjGECf7NgJs5ZbCK_OzWbw1pc5KRrWik')
    # get password salt, replace with environment variable from secrets.SystemRandom().getrandbits(128)
    app.config['SECURITY_PASSWORD_SALT'] = app.config.from_envvar("SECURITY_PASSWORD_SALT", '137874679584510511859835183498768811669')

    # remember cookie and sessin cookie
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
    user_datastore = SQLAlchemySessionUserDatastore(db, User, Role)
    app.security = Security(app, user_datastore)

    # one time setup of user login info
    with app.app_context():
        db.create_all()
        # testing info, replace with envvar     ! ! ! EXTREMELY IMPORTANT TO DO ! ! !
        if not app.security.datastore.find_user(email=app.config.from_envvar("LOGIN_EMAIL", "Test@email.com")):
            app.security.datastore.create_user(email=app.config.from_envvar("LOGIN_EMAIL", "Test@email.com"), password=hash_password(app.config.from_envvar("LOGIN_PASS", "Password1!")))
        db.session.commit()

    app.config['EXECUTOR_TYPE'] = 'thread'
    app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True
    app.register_blueprint(bp)

    return app
