"""
Presentation layer for LAUNCH WINDOW: colour, formatting, input helpers,
and the top-down ASCII system map. Kept separate from physics (pure sim)
and game logic (menus/flow) so each can change without disturbing the others.
"""

import sys, os, math, time, shutil
import physics as P

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

# ANSI codes
R, B, Y, G, M, CY, GRY, BOLD = "31", "34", "33", "32", "35", "36", "90", "1"

def c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

def hr(ch="-", n=66):
    return ch * n

def clear():
    if USE_COLOR:
        print("\033[2J\033[H", end="")

def banner():
    print(c(hr("="), CY))
    print(c("  L A U N C H   W I N D O W".center(66), BOLD))
    print(c("  you are the scientist, not the pilot".center(66), GRY))
    print(c(hr("="), CY))

def sci(x, unit="", d=4):
    """Readable scientific notation, optionally with a unit."""
    return f"{x:.{d}e}" + (f" {unit}" if unit else "")


# ----------------------------------------------------------------------
# input helpers
# ----------------------------------------------------------------------
def ask(prompt):
    try:
        return input(c(prompt, Y)).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nClear skies.")
        sys.exit(0)

def num(prompt):
    """Read a number; accepts arithmetic like '3.4e7*2' and blank to cancel."""
    while True:
        s = ask(prompt)
        if s == "" or s.lower() in ("b", "back"):
            return None
        try:
            return float(eval(s, {"__builtins__": {}},
                              {"pi": math.pi, "sqrt": math.sqrt, "e": math.e}))
        except Exception:
            print(c("  (enter a number — arithmetic like 3.4e7*2 is fine)", GRY))


# ----------------------------------------------------------------------
# ASCII system map
# ----------------------------------------------------------------------
# A terminal character cell is roughly twice as tall as it is wide. To draw a
# true circle we must therefore spend ~ASPECT times as many COLUMNS as rows
# for the same physical distance, otherwise circles look stretched vertically.
ASPECT = 2.0

def _dims():
    """Map size that fits the current terminal (so animation never scrolls)."""
    try:
        cols, rows = shutil.get_terminal_size((80, 30))
    except Exception:
        cols, rows = 80, 30
    W = max(30, min(64, cols - 4))
    W -= W % 2                       # keep even for the centred aspect maths
    Hh = max(15, min(27, rows - 5))  # leave a few rows for title/legend/prompt
    return W, Hh


def _frame_lines(s, t=0.0, trail=None, rocket=None,
                 title="THE SYSTEM  (top-down, to scale)"):
    """Build the map as a list of strings (no printing)."""
    W, Hh = _dims()
    cx, cy = W // 2, Hh // 2
    grid = [[" "] * W for _ in range(Hh)]

    rmax = s["r2"] * 1.18
    scale = max(rmax / (cy - 1), ASPECT * rmax / (cx - 1))

    def put(x, y, ch, col=None):
        cc = cx + int(round(ASPECT * x / scale))   # columns get the stretch
        rr = cy - int(round(y / scale))            # y up
        if 0 <= rr < Hh and 0 <= cc < W:
            grid[rr][cc] = c(ch, col) if col else ch

    for ring_r, ch in ((s["r1"], "."), (s["r2"], "\u00b7")):
        for a in range(0, 360, 3):
            rad = math.radians(a)
            put(ring_r * math.cos(rad), ring_r * math.sin(rad), ch, GRY)

    if trail:
        for (_, x, y) in trail:
            put(x, y, "*", B)

    put(0, 0, "S", Y)
    (hx, hy), _ = P.planet_pos(s["r1"], s["T1"], s["th1_0"], t)
    (tx, ty), _ = P.planet_pos(s["r2"], s["T2"], s["th2_0"], t)
    put(hx, hy, "H", CY)
    put(tx, ty, "T", R)
    if rocket is not None:
        put(rocket[0], rocket[1], "o", BOLD)   # the ship itself

    lines = [c("  " + title, BOLD), "  +" + "-" * W + "+"]
    for row in grid:
        lines.append("  |" + "".join(row) + "|")
    lines.append("  +" + "-" * W + "+")
    legend = (f"  {c('S', Y)}=star  {c('H', CY)}=home  {c('T', R)}=target"
              + (f"  {c('o', BOLD)}=ship  {c('*', B)}=path" if (trail or rocket) else "")
              + f"    t={t / P.DAY:>6.0f} d")
    lines.append(legend)
    return lines


def draw_map(s, t=0.0, trail=None, title="THE SYSTEM  (top-down, to scale)"):
    print("\n".join(_frame_lines(s, t, trail, None, title)))


def _paint(lines):
    """Repaint a frame in place: home, overwrite each line, clear below."""
    frame = "\033[H" + "\n".join(ln + "\033[K" for ln in lines) + "\033[J"
    sys.stdout.write(frame)
    sys.stdout.flush()


def _animatable():
    return USE_COLOR and sys.stdout.isatty()


def animate_orbits(s, frames=140, fps=24, title="ORBITS — worlds in motion"):
    """Sweep the planets around their orbits so the sky feels alive."""
    if not _animatable():
        draw_map(s, 0.0, title=title)
        return
    Tmax = s["T2"] * 1.3
    clear()
    sys.stdout.write("\033[?25l")   # hide cursor -> no flicker
    try:
        for i in range(frames + 1):
            t = Tmax * i / frames
            _paint(_frame_lines(s, t, None, None, title))
            time.sleep(1.0 / fps)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


def animate_flight(s, res, frames=90, fps=30, title="TRAJECTORY  — coasting"):
    """Fly the ship along its computed path, planets moving with it."""
    if not _animatable():
        return
    trail = res["trail"]
    if len(trail) < 2:
        return
    tc = res["t_close"]
    pts = [p for p in trail if p[0] <= tc + 1e-9] or trail
    n = len(pts)
    step = max(1, n // frames)
    clear()
    sys.stdout.write("\033[?25l")
    try:
        for k in range(0, n, step):
            t, x, y = pts[k]
            _paint(_frame_lines(s, t, pts[:k + 1], (x, y), title))
            time.sleep(1.0 / fps)
        t, x, y = pts[-1]
        _paint(_frame_lines(s, t, pts, (x, y), title))
        time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()