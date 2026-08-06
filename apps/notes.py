#!/usr/bin/env python3
"""
notes.py — a plain-text lab logbook, one file per solar system (per seed),
meant to run in its own terminal window beside the game.

Type any line to add it to the log (jot your measured radius, your derived
mu_sun, a launch window you computed...). Commands start with a slash:

  /save     write the log to disk        /list   show the whole log
  /del      delete the last line         /clear  wipe the log (asks first)
  /help     show commands                /quit   leave (warns if unsaved)

Saving is MANUAL, on purpose — save before you go home.
Usage:  python3 notes.py [seed]
"""

import os, sys
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))
import paths

SEED = sys.argv[1] if len(sys.argv) > 1 else "scratch"
NOTES = os.path.join(paths.SAVES_DIR, f"notes_{SEED}.txt")
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def col(t, code):
    return f"\033[{code}m{t}\033[0m" if USE_COLOR else t


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def load():
    if os.path.exists(NOTES):
        with open(NOTES, encoding="utf-8") as f:
            return f.read().splitlines()
    return []


def save(lines):
    with open(NOTES, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def header(dirty):
    clear()
    print(col("=" * 60, "36"))
    print(col(f"  LAB LOGBOOK  —  seed {SEED}", "1"))
    print(col(f"  file: {os.path.basename(NOTES)}"
              + ("   " + col("[unsaved changes]", "31") if dirty else "   saved"),
              "90"))
    print(col("=" * 60, "36"))


def show_tail(lines, k=16):
    start = max(0, len(lines) - k)
    if start > 0:
        print(col(f"  ... {start} earlier line(s) ...", "90"))
    for idx, ln in enumerate(lines[start:], start + 1):
        print(f"  {col(f'{idx:>3}', '90')}  {ln}")
    if not lines:
        print(col("  (empty — type a line to begin your log)", "90"))


def main():
    try:
        import sidecar
        sidecar.start_watcher()
    except Exception:
        pass
    lines = load()
    dirty = False
    while True:
        header(dirty)
        show_tail(lines)
        print(col("-" * 60, "90"))
        print(col("  type a line to log it  |  /help for commands", "33"))
        try:
            s = input("  > ").rstrip("\n")
        except (EOFError, KeyboardInterrupt):
            s = "/quit"

        if not s.strip():
            continue

        if s.startswith("/"):
            cmd = s.strip().lower()
            if cmd == "/quit":
                if dirty:
                    header(dirty)
                    print(col("  Unsaved changes, scientist.", "31"))
                    a = input("  Save before going home? [y]es / [n]o / [c]ancel: ").lower()
                    if a.startswith("c"):
                        continue
                    if a.startswith("y"):
                        save(lines)
                        print(col("  Logbook saved.", "32"))
                clear()
                print("Logbook closed. Clear skies.")
                try:
                    import sidecar; sidecar.close_own_window()
                except Exception:
                    pass
                return
            elif cmd == "/save":
                save(lines)
                dirty = False
            elif cmd == "/list":
                header(dirty)
                for idx, ln in enumerate(lines, 1):
                    print(f"  {col(f'{idx:>3}', '90')}  {ln}")
                if not lines:
                    print(col("  (empty)", "90"))
                input(col("\n  [enter] ", "90"))
            elif cmd == "/del":
                if lines:
                    lines.pop()
                    dirty = True
            elif cmd == "/clear":
                a = input("  Wipe the entire log? type 'yes' to confirm: ").strip().lower()
                if a == "yes":
                    lines = []
                    dirty = True
            elif cmd == "/help":
                header(dirty)
                print("""  /save    write the log to disk
  /list    show the whole log
  /del     delete the last line
  /clear   wipe the log (asks first)
  /quit    leave (warns if unsaved)

  Anything not starting with '/' is added as a new line.""")
                input(col("\n  [enter] ", "90"))
            else:
                pass  # unknown command, ignore
        else:
            lines.append(s)
            dirty = True


if __name__ == "__main__":
    main()