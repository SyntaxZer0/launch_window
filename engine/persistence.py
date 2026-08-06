"""
Manual save / load for LAUNCH WINDOW.

Saving is deliberately manual — a scientist saves the logbook before going
home; nothing is written automatically. The whole universe is deterministic
from its seed, so a save is tiny: the seed plus your rocket and progress.
"""

import json, os, time
import paths

SAVE_PATH = os.path.join(paths.SAVES_DIR, "savegame.json")


def has_save():
    return os.path.exists(SAVE_PATH)


def save_game(state):
    data = {
        "seed": state["sys"]["seed"],
        "target_i": state["sys"].get("target_i", 0),
        "rocket": list(state["rocket"]) if state["rocket"] else None,
        "attempts": state["attempts"],
        "won": state["won"],
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return SAVE_PATH


def load_game():
    with open(SAVE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("rocket"):
        data["rocket"] = tuple(data["rocket"])   # JSON lists -> tuple
    return data


def clear_save():
    if has_save():
        os.remove(SAVE_PATH)


# ---- flight plans (per solar system) ----
def _plan_path(seed):
    return os.path.join(paths.SAVES_DIR, f"plan_{seed}.json")


def save_plan(seed, launch_day, plan):
    with open(_plan_path(seed), "w", encoding="utf-8") as f:
        json.dump({"launch_day": launch_day, "plan": plan}, f, indent=2)


def load_plan(seed):
    try:
        with open(_plan_path(seed), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None