import os
from datetime import datetime
from pathlib import Path
try:
    from user_config import user_config
except ImportError:
    user_config = {}
basedir = Path(__file__).absolute().parent


class Config:
    ORGANIZATION_NAME = 'TUD NANO'

    WTF_CSRF_ENABLED = True
    # This setting should be overridden in production in user_config.py
    SECRET_KEY = 'jDXgSR61HPphM4OedKByVIXpySe3z5'
    SECRET_KEY_TOKEN = 'Rnc6renKaTwis3dim2DZmvHW6LfLGqMx6ha'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///db/db_local.sqlite'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BOOTSTRAP_SERVE_LOCAL = True

    # Flask-Security config
    SECURITY_URL_PREFIX = "/admin"
    SECURITY_PASSWORD_HASH = "pbkdf2_sha512"
    # This setting should be overridden in production in user_config.py
    SECURITY_PASSWORD_SALT = "J5moL8J4ao2npt6wsgzK69soHlI9Eq6"

    # Flask-Security URLs, overridden because they don't put a / at the end
    SECURITY_LOGIN_URL = "/login/"
    SECURITY_LOGOUT_URL = "/logout/"
    SECURITY_REGISTER_URL = "/register/"

    SECURITY_POST_LOGIN_VIEW = "/admin"
    SECURITY_POST_LOGOUT_VIEW = "/admin"
    SECURITY_POST_REGISTER_VIEW = "/admin"

    # Flask-Security features
    SECURITY_REGISTERABLE = False
    SECURITY_SEND_REGISTER_EMAIL = False

    version_path = basedir / 'version.txt'
    if os.path.isfile(version_path):
        with open(version_path) as version_file:
            version_data = version_file.read()

        raw_date = version_data.partition('Date:')[2].partition('\n')[0].strip()
        LAST_UPDATE = datetime.strptime(raw_date, '%a %b %d %H:%M:%S %Y %z')
        LAST_UPDATE = LAST_UPDATE - LAST_UPDATE.utcoffset()
        LAST_UPDATE = LAST_UPDATE.replace(tzinfo=None)
        VERSION = version_data.partition('commit')[2].partition('\n')[0].strip()[:8]
    else:
        LAST_UPDATE = datetime.utcnow()
        VERSION = '0000000'

    LOG_FOLDER = basedir / 'log'
    LOG_FOLDER.mkdir(exist_ok=True)
    LOG_FILE = LOG_FOLDER / 'covlog.log'

    BUILD_FOLDER = basedir / 'app' / 'build'
    TEX_TEMPLATES = basedir / 'app' / 'templates' / 'tex'

    def __init__(self):
        for key, value in user_config.items():
            setattr(self, key, value)

