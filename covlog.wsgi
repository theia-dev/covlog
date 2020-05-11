import os
import sys

sys.path.insert(0, os.environ['covlog_folder'])

from app import create_app
application = create_app()