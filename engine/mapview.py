"""
Render the orbital map as a Rich Text object for the TUI's map panel.

Orbits and the flight trail are drawn with BRAILLE sub-pixels (each character
cell packs a 2x4 dot grid, ~8x the resolution of one glyph per cell), so the
curves are smooth. A terminal cell is ~2x taller than wide, which makes the
2x4 sub-dots nearly square — so circles come out round with no aspect fudge.
Star / home / target / ship stay as letters for legibility.
"""

import math
from rich.text import Text
import physics as P

STAR = "#f9e2af"; HOME = "#89dceb"; TARGET = "#f38ba8"
SHIP = "#eff1f5"; TRAIL = "#89b4fa"; DOT = "#585b70"; OTHER = "#9399b2"

# braille dot bit for sub-cell (dx in 0..1, dy in 0..3): _BITS[dy][dx]
_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))


def render(sys, t=0.0, trail=None, rocket=None, width=60, height=24):
    W = max(20, width)
    H = max(8, height)
    SW, SH = W * 2, H * 4
    orb = bytearray(W * H)
    trl = bytearray(W * H)
    planets = sys.get("planets") or [{
        "r": sys["r2"], "T": sys["T2"], "th0": sys["th2_0"], "name": "target"}]
    target_i = sys.get("target_i", 0)
    scx, scy = SW / 2.0, SH / 2.0
    rmax = max(p["r"] for p in planets) * 1.12
    scale = rmax / (min(SW / 2.0, SH / 2.0) - 1.0)

    def sub(x, y):                       # world -> sub-pixel coords
        return scx + x / scale, scy - y / scale

    def dot(buf, sx, sy):                # set one sub-pixel
        ix, iy = int(round(sx)), int(round(sy))
        if 0 <= ix < SW and 0 <= iy < SH:
            buf[(iy // 4) * W + (ix // 2)] |= _BITS[iy % 4][ix % 2]

    # orbit rings — home plus every candidate world
    for ring_r in [sys["r1"]] + [p["r"] for p in planets]:
        n = max(240, int(2 * math.pi * ring_r / scale))
        for k in range(n):
            a = 2 * math.pi * k / n
            dot(orb, *sub(ring_r * math.cos(a), ring_r * math.sin(a)))

    # flight trail — interpolate between samples so the line is continuous
    if trail:
        prev = None
        for (_, x, y) in trail:
            sx, sy = sub(x, y)
            if prev is not None:
                px0, py0 = prev
                steps = int(max(abs(sx - px0), abs(sy - py0))) + 1
                for s in range(steps + 1):
                    f = s / steps
                    dot(trl, px0 + (sx - px0) * f, py0 + (sy - py0) * f)
            prev = (sx, sy)

    # markers (letters) override the cell they land in
    markers = {}

    def mark(x, y, ch, col):
        ix, iy = (int(round(v)) for v in sub(x, y))
        if 0 <= ix < SW and 0 <= iy < SH:
            markers[(iy // 4) * W + (ix // 2)] = (ch, col)

    mark(0, 0, "S", STAR)
    (hx, hy), _ = P.planet_pos(sys["r1"], sys["T1"], sys["th1_0"], t)
    mark(hx, hy, "H", HOME)
    for i, p in enumerate(planets):
        (x, y), _ = P.planet_pos(p["r"], p["T"], p["th0"], t)
        ch = (p["name"][:1] or "o")
        mark(x, y, ch, TARGET if i == target_i else OTHER)
    if rocket is not None:
        mark(rocket[0], rocket[1], "o", SHIP)

    text = Text()
    for cy in range(H):
        for cx in range(W):
            i = cy * W + cx
            if i in markers:
                ch, col = markers[i]
                text.append(ch, style=col)
            elif trl[i]:
                text.append(chr(0x2800 + trl[i]), style=TRAIL)
            elif orb[i]:
                text.append(chr(0x2800 + orb[i]), style=DOT)
            else:
                text.append(" ")
        if cy != H - 1:
            text.append("\n")
    return text