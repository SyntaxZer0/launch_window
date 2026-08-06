"""
Shared filesystem locations for the whole project, derived from this file's
position so everything works no matter the current directory:

    <root>/
      launch_window.py            entry point
      engine/  (this file lives here)
      apps/    guide_reader.py, notes.py, calculator.py
      saves/   all runtime state (savegame, notes, calc vars, session files)
"""
import os

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ENGINE_DIR)
APPS_DIR = os.path.join(ROOT, "apps")
SAVES_DIR = os.path.join(ROOT, "saves")
os.makedirs(SAVES_DIR, exist_ok=True)