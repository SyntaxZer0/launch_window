"""
sidecar.py — open the guide and notes apps in their OWN terminal windows.

macOS is first-class (via osascript / Terminal.app). Linux and Windows have
best-effort fallbacks. EVERY path is guarded: if a window can't be opened
(headless machine, over SSH, unknown terminal), the functions simply return
False and the main game carries on unaffected. Opening side windows is a
convenience, never a requirement.
"""

import os, sys, platform, shlex, subprocess, threading, time, shutil
import paths

PY = sys.executable or "python3"
SESSION = os.path.join(paths.SAVES_DIR, ".lab_session")   # game PID
REG = os.path.join(paths.SAVES_DIR, ".lab_windows")        # companion ttys
TITLE_TAG = "LAUNCHWINDOW"                       # marks our terminal windows
SCRIPTS = ("guide_reader.py", "notes.py", "calculator.py")


def _escape_osa(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ----------------------------------------------------------------------
# macOS window tiling — put the four windows in four quadrants
# ----------------------------------------------------------------------
_SCREEN = None

def _screen():
    """Main-display size (W, H) in pixels; cached. Falls back if unknown."""
    global _SCREEN
    if _SCREEN:
        return _SCREEN
    W, H = 1440, 900
    try:
        out = subprocess.run(
            ["osascript", "-e",
             'tell application "Finder" to get bounds of window of desktop'],
            capture_output=True, text=True, timeout=3).stdout.strip()
        nums = [int(n) for n in out.replace(",", " ").split()]
        if len(nums) == 4:
            W, H = nums[2], nums[3]
    except Exception:
        pass
    _SCREEN = (W, H)
    return _SCREEN


def _quadrant(name):
    """Return {left, top, right, bottom} for a screen quadrant (macOS coords)."""
    W, H = _screen()
    menubar = 26                      # leave room for the menu bar
    half_w = W // 2
    half_h = (H - menubar) // 2
    top = menubar
    mid = top + half_h
    return {
        "tl": (0, top, half_w, mid),
        "tr": (half_w, top, W, mid),
        "bl": (0, mid, half_w, H),
        "br": (half_w, mid, W, H),
    }[name]


def _mac_spawn_script(inner, title, quadrant):
    """AppleScript that opens a Terminal window running `inner`, titles it, and
    positions it. Uses `front window` for bounds — reliable now that spawns are
    serialized (one osascript finishes before the next starts), so 'front' is
    unambiguously the window we just opened. (Matching by tab reference is
    unreliable in Terminal's AppleScript.)"""
    bounds_block = ""
    if quadrant:
        l, t, r, b = _quadrant(quadrant)
        bounds_block = ('  delay 0.2\n'
                        f'  set bounds of front window to {{{l}, {t}, {r}, {b}}}\n')
    return ('tell application "Terminal"\n'
            '  activate\n'
            f'  set _t to do script "{_escape_osa(inner)}"\n'
            f'  set custom title of _t to "{TITLE_TAG} - {_escape_osa(title)}"\n'
            f'{bounds_block}'
            'end tell')


def _spawn(cmd_list, title, quadrant=None):
    """cmd_list: argv to run (python + script + args). Returns True on launch.
    quadrant (macOS only): 'tl'|'tr'|'bl'|'br' to tile the new window."""
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            inner = "cd " + shlex.quote(paths.ROOT) + " && " + \
                    " ".join(shlex.quote(a) for a in cmd_list)
            script = _mac_spawn_script(inner, title, quadrant)
            # run (not fire-and-forget) so each window opens & positions before
            # the next starts — prevents the windows from racing each other
            try:
                subprocess.run(["osascript", "-e", script], timeout=8,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                subprocess.Popen(["osascript", "-e", script],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

        if system == "Windows":
            # 'start' opens a new console; title in quotes, then the command
            subprocess.Popen(
                f'start "{title}" {subprocess.list2cmdline(cmd_list)}',
                shell=True)
            return True

        # ---- Linux / other unix: need a graphical display ----
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False
        for name in _linux_order():
            if shutil.which(name) is None:
                continue
            if _try_terminal(name, cmd_list):
                return True
        return False
    except Exception:
        return False


# per-terminal flag to "run this command", then the command's argv
_TERM_EXEC = {
    "gnome-terminal": ["--"], "ptyxis": ["--"], "mate-terminal": ["--"],
    "tilix": ["-e"], "konsole": ["-e"], "xfce4-terminal": ["-x"],
    "terminator": ["-x"], "alacritty": ["-e"], "kitty": [], "foot": [],
    "wezterm": ["start", "--"], "st": ["-e"], "urxvt": ["-e"], "rxvt": ["-e"],
    "xterm": ["-e"], "x-terminal-emulator": ["-e"], "qterminal": ["-e"],
    "lxterminal": ["-e"], "deepin-terminal": ["-e"],
}

def _linux_argv(name, cmd_list):
    return [name] + _TERM_EXEC.get(name, ["-e"]) + cmd_list

def _linux_order():
    """Terminals to try, honouring $LAUNCH_WINDOW_TERMINAL / $TERMINAL first."""
    order = ["gnome-terminal", "ptyxis", "konsole", "xfce4-terminal",
             "mate-terminal", "tilix", "terminator", "kitty", "alacritty",
             "wezterm", "foot", "qterminal", "lxterminal", "deepin-terminal",
             "st", "urxvt", "rxvt", "xterm", "x-terminal-emulator"]
    pref = os.environ.get("LAUNCH_WINDOW_TERMINAL") or os.environ.get("TERMINAL")
    if pref:
        pref = os.path.basename(pref)
        order = [pref] + [t for t in order if t != pref]
    return order

def _try_terminal(name, cmd_list, wait=0.4):
    """Launch one terminal; return True only if it didn't immediately error.
    (A wrong flag makes the launcher exit non-zero fast; a real window either
    keeps the launcher alive or, for client/server terminals, exits 0.)"""
    try:
        p = subprocess.Popen(_linux_argv(name, cmd_list),
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except Exception:
        return False
    time.sleep(wait)
    rc = p.poll()
    return rc is None or rc == 0


def open_guide():
    return _spawn([PY, os.path.join(paths.APPS_DIR, "guide_reader.py")],
                  "Launch Window — Guide", quadrant="tr")


def open_notes(seed):
    return _spawn([PY, os.path.join(paths.APPS_DIR, "notes.py"), str(seed)],
                  f"Launch Window — Notes (seed {seed})", quadrant="bl")


def open_calc(seed=None):
    args = [PY, os.path.join(paths.APPS_DIR, "calculator.py")]
    if seed is not None:
        args.append(str(seed))
    return _spawn(args, "Launch Window — Calculator", quadrant="br")


def position_self(quadrant="tl"):
    """Move the game's OWN window into a quadrant (macOS).
    First tries Terminal.app scripting (no permissions). Then also asks System
    Events to place the frontmost window there — which works for ANY terminal
    app (iTerm2, VS Code, ...), but needs that app granted Accessibility in
    System Settings > Privacy & Security > Accessibility. No-op off macOS."""
    if platform.system() != "Darwin":
        return
    l, t, r, b = _quadrant(quadrant)

    # 1) Terminal.app path — matches our own window by tty, no permission needed
    tty = _my_tty()
    if tty:
        script = ('tell application "Terminal"\n'
                  '  repeat with w in windows\n'
                  '    repeat with tb in tabs of w\n'
                  '      try\n'
                  f'        if tty of tb is "{tty}" then set bounds of w to '
                  f'{{{l}, {t}, {r}, {b}}}\n'
                  '      end try\n'
                  '    end repeat\n'
                  '  end repeat\n'
                  'end tell')
        try:
            subprocess.run(["osascript", "-e", script], timeout=6,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # 2) System Events fallback — positions the frontmost window (the terminal
    #    you launched from). Covers iTerm2 / VS Code / etc. Silently no-ops if
    #    Accessibility permission hasn't been granted to the launching app.
    w_px, h_px = r - l, b - t
    se = ('tell application "System Events"\n'
          '  try\n'
          '    set frontApp to first application process whose frontmost is true\n'
          '    tell frontApp\n'
          f'      set position of window 1 to {{{l}, {t}}}\n'
          f'      set size of window 1 to {{{w_px}, {h_px}}}\n'
          '    end tell\n'
          '  end try\n'
          'end tell')
    try:
        subprocess.run(["osascript", "-e", se], timeout=6,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ----------------------------------------------------------------------
# session lifetime — so the companion windows close when the game does
# ----------------------------------------------------------------------
def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return True


def write_session():
    """Called by the game at startup: marks the session live and resets the
    window registry."""
    try:
        with open(SESSION, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    try:
        if os.path.exists(REG):
            os.remove(REG)
    except Exception:
        pass


def clear_session():
    try:
        if os.path.exists(SESSION):
            os.remove(SESSION)
    except Exception:
        pass


def session_active():
    """True if the game that owns this session is still running."""
    if not os.path.exists(SESSION):
        return False
    try:
        pid = int(open(SESSION).read().strip() or "0")
    except Exception:
        return True
    return _pid_alive(pid) if pid > 0 else True


def _my_tty():
    for stream in (sys.stdout, sys.stdin):
        try:
            return os.ttyname(stream.fileno())
        except Exception:
            continue
    return None


def _register_window():
    """A companion records its own tty so the game can close it exactly."""
    if platform.system() != "Darwin":
        return
    tty = _my_tty()
    if not tty:
        return
    try:
        with open(REG, "a") as f:
            f.write(tty + "\n")
    except Exception:
        pass


def _close_ttys(ttys, delay=0.35):
    """Close the Terminal windows whose tab tty is in `ttys` (macOS).
    Detached + delayed so the window's python has exited first (no prompt)."""
    if platform.system() != "Darwin" or not ttys:
        return
    lst = ", ".join('"%s"' % t for t in ttys)
    script = (f'delay {delay}\n'
              'tell application "Terminal"\n'
              '  repeat with w in windows\n'
              '    repeat with tb in tabs of w\n'
              '      try\n'
              f'        if (tty of tb) is in {{{lst}}} then close w saving no\n'
              '      end try\n'
              '    end repeat\n'
              '  end repeat\n'
              'end tell')
    try:
        subprocess.Popen(["osascript", "-e", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception:
        pass


def close_own_window():
    """A companion closes its own window (macOS). No-op elsewhere: on Linux/
    Windows the window closes on its own when the app's process exits."""
    tty = _my_tty()
    if tty:
        _close_ttys([tty])


def start_watcher(poll=1.0):
    """
    Called by each companion app. If launched inside a live game session, it
    registers its window and watches the session in the background; when the
    game exits, the app closes itself (and its window on macOS). Launched
    standalone (no session), it does nothing and the app runs normally.
    """
    if not session_active():
        return
    _register_window()
    tty = _my_tty()

    def _watch():
        while True:
            time.sleep(poll)
            if not session_active():
                if tty:
                    _close_ttys([tty], delay=0.1)
                os._exit(0)   # exiting also closes the window on Linux/Windows

    threading.Thread(target=_watch, daemon=True).start()


def close_all():
    """Called by the game on quit: shut the companion windows immediately."""
    system = platform.system()
    ttys = []
    try:
        if os.path.exists(REG):
            ttys = [ln.strip() for ln in open(REG) if ln.strip()]
    except Exception:
        pass
    # 1) kill the companion python processes (matched by FULL path only, so an
    #    unrelated process that merely mentions the filename is never touched)
    try:
        if system == "Windows":
            subprocess.run(
                ["taskkill", "/F", "/FI", "WINDOWTITLE eq Launch Window*"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            for name in SCRIPTS:
                try:
                    subprocess.run(["pkill", "-9", "-f", os.path.join(paths.APPS_DIR, name)],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                except FileNotFoundError:
                    pass
    except Exception:
        pass
    # 2) on macOS, close the now-idle windows: by exact tty, plus a title sweep
    if system == "Darwin":
        _close_ttys(ttys, delay=0.3)
        title_script = (
            'delay 0.35\n'
            'tell application "Terminal"\n'
            '  repeat with w in windows\n'
            '    try\n'
            f'      if custom title of selected tab of w starts with "{TITLE_TAG}" '
            'then close w saving no\n'
            '    end try\n'
            '  end repeat\n'
            'end tell')
        try:
            subprocess.Popen(["osascript", "-e", title_script],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except Exception:
            pass
    try:
        if os.path.exists(REG):
            os.remove(REG)
    except Exception:
        pass


# ----------------------------------------------------------------------
# diagnostics — why aren't the windows opening?
# ----------------------------------------------------------------------
def diagnose():
    system = platform.system()
    print("Launch Window — window diagnostics")
    print("-" * 52)
    print(f"platform : {system} {platform.release()}")
    print(f"python   : {sys.version.split()[0]}")
    if system == "Darwin":
        print("macOS uses AppleScript + Terminal.app; windows should open if")
        print("you launch from Terminal.app (e.g. open_lab.command).")
        return
    if system == "Windows":
        print("Windows opens each app with 'start'; should work in a normal shell.")
        return
    if system != "Linux":
        print("Unknown OS — window opening is best-effort.")
        return

    sess = os.environ.get("XDG_SESSION_TYPE")
    disp = os.environ.get("DISPLAY")
    wl = os.environ.get("WAYLAND_DISPLAY")
    print(f"session  : {sess}")
    print(f"DISPLAY  : {disp}")
    print(f"WAYLAND  : {wl}")
    if not (disp or wl):
        print("\n>> No graphical display (DISPLAY/WAYLAND_DISPLAY are empty).")
        print("   This is a text-only session (plain SSH or a bare TTY), so no")
        print("   windows can open. The game still runs in this one terminal;")
        print("   open notes.py / calculator.py in your own tabs if you like.")
        return

    order = _linux_order()
    found = [t for t in order if shutil.which(t)]
    print("\nterminals on PATH:", ", ".join(found) if found else "(NONE)")
    if not found:
        print(">> No known terminal emulator was found. Install one, e.g.:")
        print("     sudo apt install gnome-terminal      # or xterm, kitty, ...")
        return

    test = found[0]
    print(f"\nTrying a test window with '{test}' — a window should briefly appear.")
    argv = _linux_argv(test, [PY, "-c",
                              "print('Launch Window: test window OK'); "
                              "import time; time.sleep(2)"])
    print("  command:", " ".join(argv))
    try:
        p = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(0.6)
        rc = p.poll()
        if rc is None or rc == 0:
            print("  result : launcher OK (no immediate error).")
            print("  If you saw a window flash, opening works. If NOT, your")
            print("  compositor may block it — try another terminal via:")
            print("     LAUNCH_WINDOW_TERMINAL=kitty ./run.sh")
        else:
            err = (p.stderr.read().decode(errors="replace")[:300]
                   if p.stderr else "")
            print(f"  result : '{test}' exited {rc}.")
            if err.strip():
                print("  stderr :", err.strip())
            print("  Try a different one:  LAUNCH_WINDOW_TERMINAL=xterm ./run.sh")
    except Exception as e:
        print("  result : failed to launch —", e)