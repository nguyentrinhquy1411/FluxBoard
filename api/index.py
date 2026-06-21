import sys
import os

# Add apps/api directory to path so that Python can resolve "app.*" modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.api import app
