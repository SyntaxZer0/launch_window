"""
Render the orbital map as a Rich Text object for the TUI's map panel.
Same idea as the terminal ui._frame_lines, but returns styled Text sized to
the panel. Colours: star=amber, home=cyan, target=red, ship=white, trail=blue,
orbits=grey.
"""

import math
from rich.text import Text
import physics as P

ASPECT = 2.0
STAR = "#f9e2af"; HOME = "#89dceb"; TARGET = "#f38ba8"
SHIP = "#eff1f5"; TRAIL = "#585b70"; DOT = "#45475a"


def render(sys, t=0.0, trail=None, rocket=None, width=60, height=24):
    W = max(20, width)
    Hh = max(10, height)
    cx, cy = W // 2, Hh // 2
    # a styled cell grid: None = blank, else (char, colour)
    grid: list[list] = [[None] * W for _ in range(Hh)]

    rmax = sys["r2"] * 1.16
    scale = max(rmax / (cy - 1), ASPECT * rmax / (cx - 1))

    def put(x, y, ch, col):
        cc = cx + int(round(ASPECT * x / scale))
        rr = cy - int(round(y / scale))
        if 0 <= rr < Hh and 0 <= cc < W:
            grid[rr][cc] = (ch, col)

    for ring_r, ch in ((sys["r1"], "."), (sys["r2"], "\u00b7")):
        for a in range(0, 360, 3):
            rad = math.radians(a)
            put(ring_r * math.cos(rad), ring_r * math.sin(rad), ch, DOT)

    if trail:
        for (_, x, y) in trail:
            put(x, y, "*", TRAIL)

    put(0, 0, "S", STAR)
    (hx, hy), _ = P.planet_pos(sys["r1"], sys["T1"], sys["th1_0"], t)
    (tx, ty), _ = P.planet_pos(sys["r2"], sys["T2"], sys["th2_0"], t)
    put(hx, hy, "H", HOME)
    put(tx, ty, "T", TARGET)
    if rocket is not None:
        put(rocket[0], rocket[1], "o", SHIP)

    text = Text()
    for r in range(Hh):
        for cc in range(W):
            cell = grid[r][cc]
            if cell is None:
                text.append(" ")
            else:
                text.append(cell[0], style=cell[1])
        if r != Hh - 1:
            text.append("\n")
    return text