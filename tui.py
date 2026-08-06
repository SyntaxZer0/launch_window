#!/usr/bin/env python3
"""
LAUNCH WINDOW — Textual GUI (Stage 1: the overhaul).

One window. Left: the orbital map + a mission console. Right: a reference dock
with the guide, your notes, and a calculator — all visible at once. Panels
toggle (m/g/n/c) and zoom (z). The rolling mission clock comes in Stage 2.

Run:  python3 tui.py           (random system)
      python3 tui.py 42        (seeded)
Needs:  pip install textual
"""

import os, sys, json, math, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine"))
import paths
import physics as P
import persistence as save_mod
import calc_core as CC
import mapview

from rich.text import Text
from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Input, RichLog, TextArea


class Panel(Vertical):
    @property
    def allow_maximize(self):
        return True


class ScrollPanel(VerticalScroll):
    @property
    def allow_maximize(self):
        return True

GUIDE_PATH = os.path.join(paths.ROOT, "GUIDE.txt")

# mission-clock time-speed multipliers
SPEEDS = [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64]

# ---- light semantic highlighting for the guide ----
_NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?")
_G_BASE = "#cdd6f4"; _G_HEAD = "#cba6f7"; _G_SUB = "#89dceb"
_G_DIM = "#45475a"; _G_NUM = "#f9e2af"; _G_EQ = "#89b4fa"


def _append_nums(out, s, base, numc):
    """Append s in `base`, but with numbers in `numc`."""
    i = 0
    for m in _NUM.finditer(s):
        if m.start() > i:
            out.append(s[i:m.start()], style=base)
        out.append(m.group(), style=numc)
        i = m.end()
    if i < len(s):
        out.append(s[i:], style=base)


def highlight_guide(raw):
    """Colour numbers, equations, and headers lightly; keep prose calm."""
    out = Text()
    for line in raw.split("\n"):
        s = line.strip()
        if s and set(s) <= set("-=—_ "):                     # divider rule
            out.append(line + "\n", style=_G_DIM); continue
        letters = [c for c in s if c.isalpha()]
        upper = (letters and sum(c.isupper() for c in letters) / len(letters) > 0.7)
        if upper and len(s) <= 64:                           # SECTION HEADER
            out.append(line + "\n", style="bold " + _G_HEAD); continue
        stripped = line.lstrip()
        indented = len(line) - len(stripped) >= 4
        if indented and "=" in s and re.search(r"[A-Za-z]", s):   # equation
            _append_nums(out, line, _G_EQ, _G_NUM); out.append("\n"); continue
        if s.endswith(":") and len(s) <= 44:                 # sub-label
            _append_nums(out, line, "bold " + _G_SUB, _G_NUM); out.append("\n"); continue
        _append_nums(out, line, _G_BASE, _G_NUM); out.append("\n")   # prose
    return out

# ---- maneuver parsing (shared grammar) ----
_TRIGS = {"day": "day", "radius": "radius", "r": "radius", "apo": "apo",
          "apoapsis": "apo", "peri": "peri", "periapsis": "peri", "near": "near"}
_DIRS = {"prograde": "prograde", "pro": "prograde", "retrograde": "retrograde",
         "retro": "retrograde", "out": "out", "in": "in",
         "heading": "heading", "head": "heading", "angle": "heading"}


def _val(tok):
    t = tok.lower()
    return float(t[:-2]) * P.AU if t.endswith("au") else float(tok)


def parse_maneuver(text):
    toks = text.split()
    if not toks:
        return None, "nothing to add"
    tkey = toks[0].lower()
    if tkey not in _TRIGS:
        return None, f"unknown trigger '{toks[0]}'"
    trig = _TRIGS[tkey]; i = 1; tval = None
    try:
        if trig in ("day", "radius", "near"):
            if i >= len(toks):
                return None, f"'{trig}' needs a value"
            tval = _val(toks[i]); i += 1
        if i >= len(toks):
            return None, "missing a direction"
        dkey = toks[i].lower()
        if dkey not in _DIRS:
            return None, f"unknown direction '{toks[i]}'"
        dirn = _DIRS[dkey]; i += 1; head = None
        if dirn == "heading":
            if i >= len(toks):
                return None, "heading needs an angle"
            head = float(toks[i]); i += 1
        if i >= len(toks):
            return None, "missing the burn size (m/s)"
        dv = float(toks[i])
        if dv <= 0:
            return None, "burn must be positive"
    except ValueError:
        return None, "couldn't read a number"
    return {"trig": trig, "tval": tval, "dirn": dirn, "head": head, "dv": dv}, None


def fmt_maneuver(m):
    t = m["trig"]
    when = ({"day": f"day {m['tval']:g}", "radius": f"radius {m['tval']:.2e}",
             "near": f"near {m['tval']:.2e}"}).get(t, t)
    d = m["dirn"] if m["dirn"] != "heading" else f"heading {m['head']:g}"
    return f"{when:<16}{d:<11}{m['dv']:.0f} m/s"


class LaunchWindow(App):
    CSS = """
    Screen { background: #11111b; color: #cdd6f4; }
    #status { height: 1; background: #181825; color: #6c7086; padding: 0 1; }
    #main { width: 3fr; }
    #dock { width: 2fr; }
    .panel { border: round #313244; background: #181825;
             border-title-color: #6c7086; border-title-align: left; }
    .panel:focus-within { border: round #cba6f7; border-title-color: #cba6f7; }
    #mapbox:focus { border: round #cba6f7; }
    #mapbox { height: 3fr; }
    #consolebox { height: 2fr; }
    #g { height: 1fr; } #n { height: 1fr; } #cx { height: 1fr; }
    RichLog { background: #181825; }
    Input { background: #11111b; border: none; }
    TextArea { background: #181825; }
    #keys { height: 1; background: #181825; color: #6c7086; padding: 0 1; }
    """

    BINDINGS = [
        Binding("ctrl+q", "leave", "quit"),
        Binding("ctrl+s", "save", "save"),
        Binding("f1", "help", "help"),
        Binding("ctrl+o", "toggle_panel('mapbox')", "map"),
        Binding("ctrl+g", "toggle_panel('g')", "guide"),
        Binding("ctrl+n", "toggle_panel('n')", "notes"),
        Binding("ctrl+b", "toggle_panel('cx')", "calc"),
        Binding("ctrl+z", "zoom", "zoom"),
        Binding("space", "toggle_clock", "play/pause", show=False),
        Binding("plus", "speed_up", "faster", show=False),
        Binding("equals_sign", "speed_up", "faster", show=False),
        Binding("minus", "speed_down", "slower", show=False),
        Binding("escape", "focus_map", "clock keys", show=False),
    ]

    def __init__(self, seed=None):
        super().__init__()
        resume = None
        if seed is None and save_mod.has_save():
            try:
                resume = save_mod.load_game()
            except Exception:
                resume = None
        if resume:
            seed = resume["seed"]
        self.sys = P.generate_system(seed)
        self.rocket = resume["rocket"] if resume else None
        self.attempts = resume["attempts"] if resume else 0
        self._resumed = bool(resume)
        if resume and resume.get("target_i"):
            P.select_target(self.sys, resume["target_i"])
        self.plan = []
        self.day = 0.0            # live mission clock (days)
        self.playing = True       # is the clock rolling?
        self.speed_i = 2          # index into SPEEDS -> x1
        self.last_trail = None
        self.env = dict(CC.BASE); self.env["ans"] = 0.0

    # ---------- layout ----------
    def compose(self) -> ComposeResult:
        yield Static(id="status")
        with Horizontal():
            with Vertical(id="main"):
                with Panel(id="mapbox", classes="panel"):
                    yield Static(id="map")
                with Panel(id="consolebox", classes="panel"):
                    yield RichLog(id="console", markup=True, wrap=True, highlight=False)
                    yield Input(id="cmd", placeholder="mission command  (help)")
            with Vertical(id="dock"):
                with ScrollPanel(id="g", classes="panel"):
                    yield Static(id="guide")
                with Panel(id="n", classes="panel"):
                    yield TextArea(id="notes")
                with Panel(id="cx", classes="panel"):
                    yield RichLog(id="calc-log", markup=True, wrap=True, highlight=False)
                    yield Input(id="calc-in", placeholder="calc  (type help)")
        yield Static(id="keys")

    # ---------- setup ----------
    def on_mount(self):
        self.title = "launch window"
        titles = {"mapbox": "system map", "consolebox": "mission console",
                  "g": "guide", "n": "notes", "cx": "calculator"}
        for wid, t in titles.items():
            self.query_one("#" + wid).border_title = t
        self.query_one("#mapbox").can_focus = True
        self.query_one("#keys", Static).update(
            "^o map  ^g guide  ^n notes  ^b calc  ^z zoom  ^s save  ^q quit"
            "   ·   clock: type play/pause/speed, or esc→map then space +/-")
        self.query_one("#guide", Static).update(self._guide_text())
        self._load_plan()
        self._load_notes()
        self._load_calc()
        self.call_after_refresh(self._render_map)
        self._update_status()
        log = self.query_one("#console", RichLog)
        log.write(Text.from_markup(
            f"[#cba6f7]LAUNCH WINDOW[/]   seed [b]{self.sys['seed']}[/]\n"
            "The clock is [#a6e3a1]running[/] — the worlds move as you work. Watch the "
            "[#cba6f7]phase[/] up top; [b]fly[/] when it hits your window.\n"
            "Several worlds orbit here — [#89dceb]target[/] lists them. "
            "Type [#89dceb]help[/] for commands · [#89dceb]measure[/] to read instruments.\n"))
        if self._resumed:
            log.write(Text.from_markup(
                f"[#a6e3a1]resumed your saved run[/] — seed {self.sys['seed']}, "
                f"{self.attempts} attempt(s)"
                + (", rocket ready" if self.rocket else "")))
        clog = self.query_one("#calc-log", RichLog)
        clog.write(Text.from_markup("[#6c7086]calculator — '^' is power, vars persist · type [/][#89dceb]help[/]"))
        self.query_one("#cmd", Input).focus()
        self.set_interval(0.1, self._tick)

    def _tick(self):
        if self.playing:
            self.day += SPEEDS[self.speed_i] * 0.2
            if self.query_one("#mapbox").display:
                self._render_map()
            self._update_status()

    def on_resize(self, event):
        self._render_map()

    # ---------- helpers ----------
    def _update_status(self):
        s = self.sys
        rk = (f"v_e={self.rocket[0]:.0f} MR={self.rocket[1]:.2f} "
              f"Δv={P.tsiolkovsky_dv(*self.rocket):.0f}" if self.rocket else "no rocket")
        t = self.day * P.DAY
        phase = math.degrees((P.planet_angle(s["T2"], s["th2_0"], t)
                              - P.planet_angle(s["T1"], s["th1_0"], t)) % P.TWO_PI)
        run = "[#a6e3a1]▶[/]" if self.playing else "[#f9e2af]⏸[/]"
        tname = self.sys["planets"][self.sys["target_i"]]["name"]
        self.query_one("#status", Static).update(Text.from_markup(
            f"seed {s['seed']}  ·  {rk}  ·  {run} day [b]{self.day:7.1f}[/]  "
            f"×{SPEEDS[self.speed_i]:g}  ·  phase [#cba6f7]{phase:5.1f}°[/]  ·  "
            f"→ [#f38ba8]{tname}[/]"))

    def _render_map(self):
        try:
            box = self.query_one("#mapbox")
            w = max(20, box.size.width - 2)
            h = max(8, box.size.height - 2)
        except Exception:
            w, h = 60, 20
        txt = mapview.render(self.sys, self.day * P.DAY, trail=self.last_trail,
                             width=w, height=h)
        self.query_one("#map", Static).update(txt)

    def _guide_text(self):
        try:
            with open(GUIDE_PATH, encoding="utf-8") as f:
                return highlight_guide(f.read())
        except Exception:
            return Text("GUIDE.txt not found.")

    def action_toggle_clock(self):
        self.playing = not self.playing
        self._update_status()

    def action_speed_up(self):
        self.speed_i = min(len(SPEEDS) - 1, self.speed_i + 1)
        self._update_status()

    def action_speed_down(self):
        self.speed_i = max(0, self.speed_i - 1)
        self._update_status()

    def action_focus_map(self):
        self.query_one("#mapbox").focus()

    def _load_plan(self):
        saved = save_mod.load_plan(self.sys["seed"])
        if saved:
            self.plan = saved.get("plan", [])
            self.day = saved.get("launch_day", 0.0)
        else:
            self.plan = []
            self.day = 0.0

    def _switch_to(self, seed, rocket=None, attempts=0):
        # persist the universe we're leaving, then load the new one
        self._save_notes(); self._save_calc()
        self.sys = P.generate_system(seed)
        self.rocket = rocket
        self.attempts = attempts
        self.last_trail = None
        self._load_plan()
        self.env = dict(CC.BASE); self.env["ans"] = 0.0
        self._load_calc()
        self._load_notes()
        self._render_map()
        self._update_status()

    def _notes_path(self):
        return os.path.join(paths.SAVES_DIR, f"notes_{self.sys['seed']}.txt")

    def _load_notes(self):
        ta = self.query_one("#notes", TextArea)
        try:
            with open(self._notes_path(), encoding="utf-8") as f:
                ta.text = f.read()
        except Exception:
            ta.text = ""

    def _save_notes(self):
        try:
            with open(self._notes_path(), "w", encoding="utf-8") as f:
                f.write(self.query_one("#notes", TextArea).text)
        except Exception:
            pass

    def _calc_path(self):
        return os.path.join(paths.SAVES_DIR, f"calc_vars_{self.sys['seed']}.json")

    def _load_calc(self):
        try:
            with open(self._calc_path(), encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    if isinstance(v, (int, float)):
                        self.env[k] = v
        except Exception:
            pass

    def _save_calc(self):
        try:
            with open(self._calc_path(), "w", encoding="utf-8") as f:
                json.dump(CC.user_vars(self.env), f)
        except Exception:
            pass

    # ---------- actions ----------
    def action_toggle_panel(self, wid):
        w = self.query_one("#" + wid)
        w.display = not w.display
        self.call_after_refresh(self._render_map)

    def action_zoom(self):
        try:
            if self.screen.maximized is not None:
                self.screen.minimize()
            else:
                w = self.focused
                while w is not None and "panel" not in getattr(w, "classes", set()):
                    w = w.parent
                if w is not None:
                    self.screen.maximize(w)
        except Exception:
            pass
        self.call_after_refresh(self._render_map)

    def _list_saves(self):
        import glob, re
        d = paths.SAVES_DIR
        lines = []
        if save_mod.has_save():
            try:
                g = save_mod.load_game()
                rk = (f"rocket v_e={g['rocket'][0]:.0f} MR={g['rocket'][1]:.2f}"
                      if g.get("rocket") else "no rocket")
                lines.append(f"[b]save slot[/]  seed [#a6e3a1]{g['seed']}[/]  ·  {rk}  ·  "
                             f"{g.get('attempts', 0)} attempt(s)  ·  "
                             f"saved {g.get('saved_at', '?')}")
                lines.append("  [#6c7086]type[/] [#89dceb]resume[/] "
                             "[#6c7086]to load this run[/]")
            except Exception:
                lines.append("[#6c7086]save slot unreadable[/]")
        else:
            lines.append("[#6c7086]no save slot yet — type[/] [#89dceb]save[/] "
                         "[#6c7086](or ^s) to write one[/]")
        seeds = set()
        for pat in ("plan_*.json", "notes_*.txt", "calc_vars_*.json"):
            for f in glob.glob(os.path.join(d, pat)):
                m = re.search(r"_(-?\d+)\.", os.path.basename(f))
                if m:
                    seeds.add(int(m.group(1)))
        if seeds:
            lines.append("[b]universes with saved work[/]  (plan / notes / calc):")
            for s in sorted(seeds):
                here = "  [#a6e3a1]← current[/]" if s == self.sys["seed"] else ""
                lines.append(f"  seed [#89dceb]{s}[/]{here}   "
                             f"[#6c7086]— 'load {s}' to open[/]")
        else:
            lines.append("[#6c7086]no per-universe work saved yet[/]")
        self._clog("\n".join(lines))

    def _resume(self):
        if not save_mod.has_save():
            self._clog("  [#f38ba8]no save slot — nothing to resume[/]"); return
        try:
            g = save_mod.load_game()
        except Exception:
            self._clog("  [#f38ba8]couldn't read the save[/]"); return
        self._switch_to(g["seed"], rocket=g.get("rocket"),
                        attempts=g.get("attempts", 0))
        self._clog(f"  [#a6e3a1]resumed[/] seed {g['seed']} — "
                   f"{self.attempts} attempt(s)"
                   + (", rocket ready" if self.rocket else ""))

    def _load_seed(self, rest):
        try:
            seed = int(rest[0])
        except Exception:
            self._clog("  [#f38ba8]load <seed>[/]  (see 'saves' for your universes)")
            return
        self._switch_to(seed, rocket=self.rocket, attempts=0)
        n = len(self.plan)
        self._clog(f"  [#a6e3a1]loaded[/] universe seed {seed} — "
                   f"{n} maneuver(s) in its plan"
                   + ("" if self.rocket else "; build a rocket to fly"))

    def action_save(self):
        state = {"sys": self.sys, "rocket": self.rocket,
                 "attempts": self.attempts, "won": False}
        save_mod.save_game(state)
        save_mod.save_plan(self.sys["seed"], self.day, self.plan)
        self._save_notes(); self._save_calc()
        self._clog("[#a6e3a1]saved — game, plan, notes, and calculator vars[/]", "#console")

    def action_help(self):
        self._clog(
            "[b]commands[/]\n"
            "  measure                 show the raw instrument readings\n"
            "  target [n]              list worlds / pick which one to reach\n"
            "  rocket <v_e> <mr>       build a rocket (Tsiolkovsky)\n"
            "  add <trig> <dir> <dv>   add a maneuver  (near/day/apo · pro/retro/heading)\n"
            "  del <n> · clear · plan  edit / show the flight plan\n"
            "  fly                     launch NOW (at the current clock day)\n"
            "  [b]the clock:[/]\n"
            "  play · pause            start / stop time  (space when the map is focused)\n"
            "  speed <x>               set time speed  (or +/- ; ×0.25 … ×64)\n"
            "  warp <day>              jump the clock forward to a day (no rewind)\n"
            "  key                     answer key (spoilers)\n"
            "  saves · resume · load <seed>    saved runs & universes\n"
            "  save                    save everything (also ^s)\n", "#console")

    # ---------- input routing ----------
    def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        event.input.value = ""
        if event.input.id == "calc-in":
            self._do_calc(text)
        else:
            self._do_command(text)

    def _clog(self, markup, target="#console"):
        self.query_one(target, RichLog).write(Text.from_markup(markup))

    # ---------- calculator ----------
    def _do_calc(self, text):
        if not text:
            return
        if text.lower() in ("help", "?", "h"):
            self._clog(
                "[b]calculator[/]\n"
                "  type an expression:  [#89dceb]sqrt(mu/r1)[/]   [#89dceb]4*pi^2*a^3[/]\n"
                "  [#89dceb]^[/] is power   ·   assign with [#89dceb]x = expr[/]   ·   "
                "[#89dceb]ans[/] = last result\n"
                "  functions: sqrt sin cos tan asin acos atan atan2 ln log log10\n"
                "             exp hypot floor ceil abs pow radians degrees\n"
                "  constants: pi tau e G c AU DAY YEAR\n"
                "  your variables persist between sessions.", "#calc-log")
            return
        self._clog(f"[#f9e2af]calc>[/] {escape(text)}", "#calc-log")
        m = CC.ASSIGN.match(text)
        try:
            if m:
                val = CC.evaluate(m.group(2), self.env)
                self.env[m.group(1)] = val; self.env["ans"] = val
                self._save_calc()
                self._clog(f"  [#a6e3a1]{m.group(1)} = {CC.fmt(val)}[/]", "#calc-log")
            else:
                val = CC.evaluate(text, self.env); self.env["ans"] = val
                self._clog(f"  [#a6e3a1]= {CC.fmt(val)}[/]", "#calc-log")
        except Exception as e:
            self._clog(f"  [#f38ba8]error: {escape(str(e))}[/]", "#calc-log")

    # ---------- mission commands ----------
    def _do_command(self, text):
        if not text:
            return
        self._clog(f"[#6c7086]>[/] {escape(text)}")
        parts = text.split()
        cmd = parts[0].lower()
        rest = parts[1:]
        if cmd == "help":
            self.action_help()
        elif cmd in ("measure", "read", "instruments"):
            self._measure()
        elif cmd == "rocket":
            self._rocket(rest)
        elif cmd in ("launch", "warp"):
            self._warp(rest)
        elif cmd in ("pause", "stop"):
            self.playing = False; self._update_status()
            self._clog("  [#6c7086]clock paused[/]")
        elif cmd in ("play", "go"):
            self.playing = True; self._update_status()
            self._clog("  [#a6e3a1]clock running[/]")
        elif cmd == "speed":
            try:
                v = float(rest[0])
                self.speed_i = min(range(len(SPEEDS)),
                                   key=lambda i: abs(SPEEDS[i] - v))
                self._update_status()
                self._clog(f"  [#a6e3a1]speed ×{SPEEDS[self.speed_i]:g}[/]")
            except Exception:
                self._clog("  [#f38ba8]speed <x>  (e.g. speed 8)[/]")
        elif cmd == "add":
            m, err = parse_maneuver(" ".join(rest))
            if err:
                self._clog(f"  [#f38ba8]{err}[/]")
            else:
                self.plan.append(m)
                self._clog(f"  [#a6e3a1]added[/]  {fmt_maneuver(m)}")
        elif cmd in ("del", "rm"):
            try:
                n = int(rest[0]) - 1
                if 0 <= n < len(self.plan):
                    self.plan.pop(n); self._clog("  [#a6e3a1]removed[/]")
            except Exception:
                self._clog("  [#f38ba8]del <n>[/]")
        elif cmd == "clear":
            self.plan = []; self._clog("  [#a6e3a1]plan cleared[/]")
        elif cmd == "plan":
            self._show_plan()
        elif cmd == "fly":
            self._fly()
        elif cmd in ("target", "targets", "worlds"):
            self._target(rest)
        elif cmd == "key":
            self._answer_key()
        elif cmd == "saves":
            self._list_saves()
        elif cmd == "resume":
            self._resume()
        elif cmd == "load":
            self._load_seed(rest)
        elif cmd == "save":
            self.action_save()
        else:
            self._clog(f"  [#f38ba8]unknown: {cmd}[/]  (help)")

    def _measure(self):
        s = self.sys
        tname = s["planets"][s["target_i"]]["name"]
        dth = math.degrees(1.0e6 / s["R_home"])
        drop = math.sqrt(2 * 50.0 / s["g_home"])
        radar = 2 * (s["r2"] - s["r1"]) / P.C_LIGHT
        phi0 = math.degrees((s["th2_0"] - s["th1_0"]) % P.TWO_PI)
        self._clog(
            f"[b]raw readings[/] — target [#f38ba8]{tname}[/] — derive the rest yourself\n"
            f"  shadow survey   Δθ [b]{dth:.4f}[/]° over 1.000e6 m baseline\n"
            f"  drop test       [b]{drop:.4f}[/] s from 50 m\n"
            f"  years           home [b]{s['T1']/P.DAY:.3f}[/] d   target [b]{s['T2']/P.DAY:.3f}[/] d\n"
            f"  radar echo      [b]{radar:.3f}[/] s round-trip at opposition\n"
            f"  target radius   [b]{s['R_target']/1e3:.1f}[/] km\n"
            f"  target moon     a [b]{s['a_moon']/1e3:.3e}[/] km   T [b]{s['T_moon']/P.DAY:.4f}[/] d\n"
            f"  ephemeris       target leads home by [b]{phi0:.3f}[/]°\n"
            f"  constants       G {P.G:.3e}   c {P.C_LIGHT:.3e}   parking 300 km")

    def _rocket(self, rest):
        try:
            ve, mr = float(rest[0]), float(rest[1])
            if ve <= 0 or mr <= 1:
                raise ValueError
        except Exception:
            self._clog("  [#f38ba8]rocket <v_e m/s> <mass ratio>[/]  e.g. rocket 4000 1.6")
            return
        self.rocket = (ve, mr)
        dv = P.tsiolkovsky_dv(ve, mr)
        self._clog(f"  [#a6e3a1]built[/]  Δv capacity {dv:.0f} m/s  "
                   f"(fuel {100*(1-1/mr):.0f}% of mass)")
        self._update_status()

    def _warp(self, rest):
        try:
            d = float(rest[0])
        except Exception:
            self._clog("  [#f38ba8]launch <day>  /  warp <day>[/]"); return
        if d < self.day - 1e-9:
            self._clog(f"  [#f38ba8]day {d:g} has already passed[/] "
                       f"(clock at {self.day:.1f}) — time only moves forward. "
                       "Wait for the next window.")
        else:
            self.day = d
            self._render_map(); self._update_status()
            self._clog(f"  [#a6e3a1]clock → day {self.day:.1f}[/]")

    def _show_plan(self):
        if not self.plan:
            self._clog("  [#6c7086]plan is empty[/]")
            return
        lines = "\n".join(f"  [#89dceb]{i+1}.[/] {fmt_maneuver(m)}"
                          for i, m in enumerate(self.plan))
        self._clog(f"[b]flight plan[/]  (launches at day {self.day:.1f})\n" + lines)

    def _fly(self):
        if not self.rocket:
            self._clog("  [#f38ba8]build a rocket first:  rocket 4000 1.6[/]"); return
        if not self.plan:
            self._clog("  [#f38ba8]add at least one maneuver[/]"); return
        self.playing = False          # freeze the clock to read the outcome
        budget = P.tsiolkovsky_dv(*self.rocket)
        t_launch = self.day * P.DAY
        res = P.fly_plan(self.sys, t_launch, self.plan, budget)
        self.attempts += 1
        self.last_trail = res["trail"]
        self._render_map()
        self._clog(f"[b]flight log[/]  (launched day {self.day:.1f})")
        for day, desc in res["events"]:
            self._clog(f"  [#6c7086]day {day:6.1f}[/]  {escape(desc)}")
        soi = res["soi"]
        if res["captured"]:
            self._clog("[b #a6e3a1]★ ORBIT ACHIEVED[/]")
            self._clog(f"  arrived day {res['t_close_days']:.1f}, "
                       f"{res['min_dist']/1e3:,.0f} km (SOI {soi/1e3:,.0f}), "
                       f"Δv left {res['budget_left']:.0f}")
        else:
            self._clog(f"[#f38ba8]✗ missed[/] — closest {res['min_dist']/1e3:,.0f} km "
                       f"(need within {soi/1e3:,.0f} km)")
            self._diag(res)

    def _diag(self, res):
        r2 = self.sys["r2"]; apo = res["r_apo_reached"]; soi = res["soi"]
        if res["fuel_out"]:
            self._clog("  [#6c7086]ran out of Δv mid-plan — bigger rocket or fewer burns[/]")
        if apo < r2 * 0.98:
            self._clog(f"  [#6c7086]arc fell short ({apo/r2:.0%} of target orbit) — "
                       "more prograde Δv early[/]")
        elif apo > r2 * 1.05:
            self._clog(f"  [#6c7086]arc overshot ({apo/r2:.0%}) — ease off early Δv[/]")
        elif res["min_dist"] < soi:
            self._clog(f"  [#6c7086]grazed the SOI too fast — needed "
                       f"{res['capture_need']:.0f} m/s, had {res['budget_at_close']:.0f}[/]")
        else:
            self._clog("  [#6c7086]right orbit, wrong time — fix the launch day, or add a "
                       "'near <D> retrograde' brake[/]")

    def _target(self, rest):
        planets = self.sys["planets"]
        if not rest:
            lines = [f"[b]worlds[/]   home orbit r1 = {self.sys['r1']/P.AU:.3f} AU"]
            for i, p in enumerate(planets):
                sel = "[#a6e3a1]►[/]" if i == self.sys["target_i"] else " "
                lines.append(
                    f" {sel} [#89dceb]{i}[/] {p['name']:<6}  "
                    f"r [b]{p['r']/P.AU:.3f}[/] AU  ({p['r']/self.sys['r1']:.2f}× home)  "
                    f"T {p['T']/P.DAY:.0f} d")
            lines.append("[#6c7086]  farther = more Δv. 'target <n>' to aim at one.[/]")
            self._clog("\n".join(lines))
            return
        tok = rest[0]
        try:
            if tok.lstrip("-").isdigit():
                i = int(tok)
            else:
                i = [p["name"].lower() for p in planets].index(tok.lower())
        except Exception:
            self._clog("  [#f38ba8]target <n or name>  (see 'target')[/]"); return
        if not 0 <= i < len(planets):
            self._clog("  [#f38ba8]no such target[/]"); return
        p = P.select_target(self.sys, i)
        self.last_trail = None                      # old trail was a different world
        self._render_map(); self._update_status()
        self._clog(f"  [#a6e3a1]now aiming at {p['name']}[/] — {p['r']/P.AU:.3f} AU out. "
                   "Its window, injection, and capture are all different — recompute.")

    def _answer_key(self):
        s = self.sys
        tname = s["planets"][s["target_i"]]["name"]
        h = P.hohmann(s["mu_sun"], s["r1"], s["r2"])
        w1, w2 = P.TWO_PI / s["T1"], P.TWO_PI / s["T2"]
        phi_req = P.phase_required(s["mu_sun"], s["r1"], s["r2"], s["T2"])
        phi0 = (s["th2_0"] - s["th1_0"]) % P.TWO_PI
        t_launch = ((phi0 - phi_req) % P.TWO_PI) / (w1 - w2)
        dep = P.oberth_burn(P.circular_v(s["mu_home"], s["R_home"] + s["park_alt"]), h["dv_inject"])
        cap = P.oberth_burn(P.circular_v(s["mu_target"], s["R_target"] + s["park_alt"]), h["dv_arrive"])
        self._clog(
            f"[b]answer key[/] — target [#f38ba8]{tname}[/] (spoilers)\n"
            f"  mu_sun {s['mu_sun']:.4e}   r1 {s['r1']:.4e}   r2 {s['r2']:.4e}\n"
            f"  transfer time {h['t_transfer']/P.DAY:.1f} d   launch day "
            f"[#a6e3a1]{t_launch/P.DAY:.2f}[/]\n"
            f"  injection [#a6e3a1]{h['dv_inject']:.1f}[/] m/s   min total Δv "
            f"{dep+cap:.0f} m/s\n"
            f"  as a plan:  launch {t_launch/P.DAY:.2f} ; add day 0 prograde "
            f"{h['dv_inject']:.0f} ; fly")

    def action_leave(self):
        self._save_notes(); self._save_calc()
        self.exit()


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip("-").isdigit() else None
    LaunchWindow(seed).run()


if __name__ == "__main__":
    main()