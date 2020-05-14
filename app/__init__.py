import logging.handlers
import os
import warnings

import jinja2
import telegram_handler
from flask import Flask, url_for
from flask_admin import Admin
from flask_admin import helpers as admin_helpers
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_qrcode import QRcode
from flask_security import Security, SQLAlchemyUserDatastore
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from config import Config

warnings.filterwarnings("ignore", category=DeprecationWarning)

bootstrap = Bootstrap()
moment = Moment()
db = SQLAlchemy()
qr = QRcode()
migrate = Migrate()
admin = Admin(template_mode='bootstrap4')
security = None

base_folder = os.path.dirname(os.path.realpath(__file__))

tex_env = jinja2.Environment(
        block_start_string=r'\BLOCK{',
        block_end_string='}',
        variable_start_string=r'\VAR{',
        variable_end_string='}',
        comment_start_string=r'\#{',
        comment_end_string='}',
        line_statement_prefix='%%',
        line_comment_prefix='%#',
        trim_blocks=True,
        autoescape=False,
        lstrip_blocks=True,
        loader=jinja2.FileSystemLoader(str(Config.TEX_TEMPLATES.absolute()))
    )

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    file_handler = logging.handlers.TimedRotatingFileHandler(
        str(Config.LOG_FILE),
        when='midnight',
        backupCount=14,
        encoding='utf8',
        utc=True
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s|%(module)s|%(funcName)s] %(message)s'
    ))

    if not hasattr(Config, 'TESTING') and hasattr(Config, 'TELEGRAM_TOKEN'):
        telegram_hand = telegram_handler.TelegramHandler(
            token=Config.TELEGRAM_TOKEN,
            chat_id=Config.TELEGRAM_CHAT_ID
        )
        tele_form = telegram_handler.HtmlFormatter(
            fmt='placeholder'
        )
        tele_form.fmt = '👽 covlog\n🔖 <b>%(name)s</b>|%(module)s|%(funcName)s\n🕰 <i>%(asctime)s</i>\n<code>%(message)s</code>'
        telegram_hand.setFormatter(tele_form)
        telegram_hand.setLevel(logging.WARNING)
        app.logger.addHandler(telegram_hand)
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    app.logger.info('Start covlog')
    app.logger.info(f'Version {Config.VERSION}')

    bootstrap.init_app(app)
    moment.init_app(app)
    db.init_app(app)
    qr.init_app(app)
    migrate.init_app(app, db)
    from .models import Role, User
    user_data_store = SQLAlchemyUserDatastore(db, User, Role)
    security = Security(app, user_data_store)
    admin.base_template = 'admin_master.html'
    admin.template_mode = 'bootstrap3'
    admin.init_app(app)
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    @security.context_processor
    def security_context_processor():
        return dict(
            admin_base_template=admin.base_template,
            admin_view=admin.index_view,
            h=admin_helpers,
            get_url=url_for)

    return app
