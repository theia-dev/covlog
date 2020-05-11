from pathlib import Path
import os
import hashlib
import getpass
from app import create_app, db
from flask_security.utils import hash_password
from flask_security import SQLAlchemyUserDatastore

basedir = Path(os.path.abspath(os.path.dirname(__file__)))
db_file = basedir / 'app/db/db_local.sqlite'

db_file.parent.mkdir(exist_ok=True, parents=True)

print('Delete old database')
try:
    db_file.unlink()
except OSError:
    print('No old database')

user_config_base = """
user_config = dict(
    SECURITY_PASSWORD_SALT="%s",
    SECRET_KEY='%s',
    SECRET_KEY_TOKEN='%s',
    SERVER_NAME_PDF='%s',
    ORGANIZATION_NAME='%s',
)
"""

user_config = basedir / 'user_config.py'

if not user_config.is_file():
    orga_name = input('Organization name:')
    server_name = input('Short server name (PDF|QR):')
    print('Create user config template with random security keys')
    sps = os.urandom(128)
    sps = hashlib.md5(sps).hexdigest()
    sk = os.urandom(128)
    sk = hashlib.md5(sk).hexdigest()
    skt = os.urandom(128)
    skt = hashlib.md5(skt).hexdigest()
    with open(str(user_config), 'w') as user_config_file:
        user_config_file.write(user_config_base % (sps, sk, skt, server_name, orga_name))


app = create_app()
print('Change to app context')
with app.app_context():

    print("Create new database")
    db.create_all()
    db.session.commit()
    import app.models as model
    user_data_store = SQLAlchemyUserDatastore(db, model.User, model.Role)
    user_role = model.Role(name='user')
    super_user_role = model.Role(name='superuser')
    db.session.add(user_role)
    db.session.add(super_user_role)
    db.session.commit()
    print('Set the password for the "admin" account')
    admin_key = getpass.getpass()

    test_user = user_data_store.create_user(
        first_name='Admin',
        email='admin',
        password=hash_password(admin_key),
        roles=[user_role, super_user_role]
    )

    db.session.commit()

print('Finished')
