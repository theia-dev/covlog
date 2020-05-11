import os
import sys

basedir = Path(__file__).absolute().resolve().parent
sys.path.insert(0, str(basedir))

from app import create_app
application = create_app()