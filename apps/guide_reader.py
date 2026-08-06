#!/usr/bin/env python3
"""
guide_reader.py — a simple, read-only pager for GUIDE.txt, meant to run in
its own terminal window next to the game. No dependencies, no editing.

  [enter]/space/n  next page      p/b  previous page
  t  top     g  bottom     q  quit
"""

import os, sys
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))
import paths

GUIDE = os.path.join(paths.ROOT, "GUIDE.txt")
PAGE = 34
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def col(t, code):
    return f"\033[{code}m{t}\033[0m" if USE_COLOR else t


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def main():
    try:
        import sidecar
        sidecar.start_watcher()
    except Exception:
        pass
    if not os.path.exists(GUIDE):
        print("GUIDE.txt was not found next to this script.")
        input("[enter] to close ")
        return
    with open(GUIDE, encoding="utf-8") as f:
        lines = f.read().splitlines()
    n = len(lines)
    i = 0
    while True:
        clear()
        for ln in lines[i:i + PAGE]:
            # lightly emphasise the manual's rule/section lines
            if set(ln.strip()) <= {"=", " "} and "=" in ln:
                print(col(ln, "36"))
            elif ln.strip().startswith("STEP") or ln.strip().endswith("?)"):
                print(col(ln, "1"))
            else:
                print(ln)
        end = min(i + PAGE, n)
        pct = int(100 * end / n)
        print(col("-" * 70, "90"))
        print(col(f"  lines {i+1}-{end} of {n}  ({pct}%)   "
                  "[enter]=next  p=prev  t=top  g=end  q=quit", "33"))
        try:
            cmd = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd == "q":
            break
        elif cmd in ("p", "b"):
            i = max(0, i - PAGE)
        elif cmd == "t":
            i = 0
        elif cmd == "g":
            i = max(0, n - PAGE)
        else:  # enter / space / n / anything else -> forward
            if end < n:
                i += PAGE
    clear()
    print("Guide closed. Clear skies.")
    try:
        import sidecar; sidecar.close_own_window()
    except Exception:
        pass


if __name__ == "__main__":
    main()