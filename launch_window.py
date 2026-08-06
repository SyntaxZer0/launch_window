#!/usr/bin/env python3
"""
LAUNCH WINDOW — a game about being the scientist, not the pilot.

Your instruments are blank. You are not told the mass of your world, the size
of your solar system, or where your target will be. You must MEASURE, then do
the orbital mechanics by hand, then commit a launch. A real integrator flies
your rocket. Correct maths arrives; wrong maths misses, and the void says why.

Run:  python3 launch_window.py           (random system)
      python3 launch_window.py 42        (seeded — share the number with a friend)

This package is three files, kept in the same folder:
    physics.py        the honest simulation (no game text)
    ui.py             colour, formatting, input, the ASCII map
    launch_window.py  this file — menus and game flow

Nothing here does the orbital maths for you. Keep paper handy.
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine"))
import physics as P
import persistence as save_mod
import sidecar
from ui import (c, hr, clear, banner, sci, ask, num, draw_map,
                animate_orbits, animate_flight,
                R, B, Y, G, M, CY, GRY, BOLD)


# ----------------------------------------------------------------------
# instruments — RAW observations only. No derived answers here.
# ----------------------------------------------------------------------
def instruments(s):
    d_base = 1.0e6                                    # 1000 km baseline
    dtheta_deg = math.degrees(d_base / s["R_home"])   # Eratosthenes angle
    drop_h = 50.0
    drop_t = math.sqrt(2 * drop_h / s["g_home"])
    D_opp = s["r2"] - s["r1"]                          # opposition distance
    radar_rt = 2 * D_opp / P.C_LIGHT                   # round-trip light time
    phi0_deg = math.degrees((s["th2_0"] - s["th1_0"]) % P.TWO_PI)

    while True:
        clear(); banner()
        print(c("  INSTRUMENTS  — raw readings. Derivations are yours to do.", BOLD))
        print(hr())
        print("  1. Shadow-angle survey (two ground stations)")
        print("  2. Weight-drop experiment")
        print("  3. Sidereal clock — orbital periods")
        print("  4. Radar ranging (fires at opposition)")
        print("  5. Target telescope + its moon")
        print("  6. Ephemeris — tonight's sky positions")
        print("  7. Known constants (G, c, parking altitude)")
        print(hr())
        print("  [1-7] take a reading   [b]ack")
        k = ask("  > ").lower()

        if k in ("b", ""):
            return
        print()
        if k == "1":
            print(c("  SHADOW-ANGLE SURVEY", CY))
            print(f"    Two stations {sci(d_base,'m')} apart, north-south.")
            print(f"    At local noon the sun's angle differs by "
                  f"{c(f'{dtheta_deg:.4f} deg', BOLD)} between them.")
            print(c("    (Eratosthenes: a full 360 deg of shadow-swing spans the", GRY))
            print(c("     whole circumference. What is your world's radius?)", GRY))
        elif k == "2":
            print(c("  WEIGHT-DROP EXPERIMENT", CY))
            print(f"    A mass dropped from {c(f'{drop_h:.1f} m', BOLD)} takes "
                  f"{c(f'{drop_t:.4f} s', BOLD)} to hit the ground.")
            print(c("    (Constant acceleration from rest. Find surface gravity g,", GRY))
            print(c("     then combine with your radius for the planet's mass.)", GRY))
        elif k == "3":
            print(c("  SIDEREAL CLOCK", CY))
            print(f"    Your world's year:   {c(f'{s['T1']/P.DAY:.3f} days', BOLD)}")
            print(f"    Target's year:       {c(f'{s['T2']/P.DAY:.3f} days', BOLD)}")
            print(c("    (Same star. Kepler's third law ties periods to orbit sizes", GRY))
            print(c("     as a ratio — but a ratio isn't a distance. Yet.)", GRY))
        elif k == "4":
            print(c("  RADAR RANGING", CY))
            print(f"    Fired when the target sits at opposition (nearest point).")
            print(f"    Round-trip echo time: {c(f'{radar_rt:.3f} s', BOLD)} "
                  f"({radar_rt/60:.3f} min).")
            print(c("    (Light goes there and back. That gives you ONE real distance", GRY))
            print(c("     in metres — the gap between the two orbits. Now the ratio", GRY))
            print(c("     from the periods snaps the whole system to absolute scale.)", GRY))
        elif k == "5":
            print(c("  TARGET TELESCOPE", CY))
            print(f"    Target radius (from angular size at known range): "
                  f"{c(f'{s['R_target']/1e3:.1f} km', BOLD)}")
            print(f"    It has a moon. Moon orbit radius: "
                  f"{c(f'{s['a_moon']/1e3:.4e} km', BOLD)}")
            print(f"    Moon's period:                    "
                  f"{c(f'{s['T_moon']/P.DAY:.4f} days', BOLD)}")
            print(c("    (A moon is a free scale. Kepler again — the moon's orbit", GRY))
            print(c("     gives the TARGET's mass, which you'll need to stop there.)", GRY))
        elif k == "6":
            print(c("  EPHEMERIS (t = 0, 'tonight')", CY))
            print(f"    Along the direction of orbital motion, the target currently")
            print(f"    LEADS your world by {c(f'{phi0_deg:.3f} deg', BOLD)}.")
            print(c("    (Both worlds move counter-clockwise. Your inner orbit is", GRY))
            print(c("     faster, so this lead angle changes every night.)", GRY))
        elif k == "7":
            print(c("  KNOWN CONSTANTS", CY))
            print(f"    G = {sci(P.G,'m^3 kg^-1 s^-2')}")
            print(f"    c = {sci(P.C_LIGHT,'m/s')}")
            print(f"    Both parking orbits sit {c('300 km', BOLD)} above the surface.")
            print(f"    1 day = 86400 s   (periods above are in days)")
        else:
            print(c("  No such instrument.", GRY))
        ask(c("\n  [enter] to return to the rack ", GRY))


# ----------------------------------------------------------------------
# rocket build — Tsiolkovsky
# ----------------------------------------------------------------------
def build_rocket(state):
    clear(); banner()
    print(c("  ROCKET ASSEMBLY  — the tyranny of the rocket equation", BOLD))
    print(hr())
    print("  dv_capacity = v_e * ln(m0/mf)")
    print("  You need enough dv for the DEPARTURE burn plus the CAPTURE burn.")
    print("  (Deep wells help you: the Oberth effect makes burns near a planet")
    print("   cheaper than the raw heliocentric dv you compute.)")
    print(hr())
    if state["rocket"]:
        ve, mr = state["rocket"]
        print(f"  Current build: v_e={ve:.0f} m/s, mass ratio={mr:.2f} "
              f"-> dv={P.tsiolkovsky_dv(ve, mr):.0f} m/s")
        print(hr())
    ve = num("  Exhaust velocity v_e in m/s (chemical ~3000-4500), blank to cancel: ")
    if ve is None or ve <= 0:
        return
    mr = num("  Mass ratio m0/mf (fuelled / dry), e.g. 3.0: ")
    if mr is None or mr <= 1:
        return
    dv = P.tsiolkovsky_dv(ve, mr)
    fuel_frac = 1 - 1 / mr
    state["rocket"] = (ve, mr)
    state["dirty"] = True
    print(hr())
    print(f"  Built. dv capacity = {c(f'{dv:.0f} m/s', G)}  "
          f"(fuel is {fuel_frac:.0%} of launch mass)")
    ask(c("\n  [enter] ", GRY))


# ----------------------------------------------------------------------
# launch console
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# flight plan — a sequence of triggered burns
# ----------------------------------------------------------------------
_TRIGS = {"day": "day", "radius": "radius", "r": "radius", "apo": "apo",
          "apoapsis": "apo", "peri": "peri", "periapsis": "peri", "near": "near"}
_DIRS = {"prograde": "prograde", "pro": "prograde", "retrograde": "retrograde",
         "retro": "retrograde", "out": "out", "radial-out": "out",
         "in": "in", "radial-in": "in", "heading": "heading", "head": "heading",
         "angle": "heading"}


def _val(tok):
    t = tok.lower()
    if t.endswith("au"):
        return float(t[:-2]) * P.AU
    return float(tok)


def _parse_maneuver(text):
    """Parse '<trigger> <direction> <dv>' -> (maneuver_dict, None) or (None, err)."""
    toks = text.split()
    if not toks:
        return None, "nothing to add"
    tkey = toks[0].lower()
    if tkey not in _TRIGS:
        return None, f"unknown trigger '{toks[0]}' — use day/radius/apo/peri/near"
    trig = _TRIGS[tkey]
    i = 1
    tval = None
    try:
        if trig in ("day", "radius", "near"):
            if i >= len(toks):
                return None, f"'{trig}' needs a value (e.g. '{trig} 20')"
            tval = _val(toks[i]); i += 1
        if i >= len(toks):
            return None, "missing a direction (prograde/retrograde/out/in/heading)"
        dkey = toks[i].lower()
        if dkey not in _DIRS:
            return None, f"unknown direction '{toks[i]}'"
        dirn = _DIRS[dkey]; i += 1
        head = None
        if dirn == "heading":
            if i >= len(toks):
                return None, "heading needs an angle in degrees"
            head = float(toks[i]); i += 1
        if i >= len(toks):
            return None, "missing the burn size in m/s"
        dv = float(toks[i])
        if dv <= 0:
            return None, "burn Δv must be positive"
    except ValueError:
        return None, "couldn't read a number in that line"
    return {"trig": trig, "tval": tval, "dirn": dirn, "head": head, "dv": dv}, None


def _fmt_maneuver(m):
    t = m["trig"]
    if t == "day":
        when = f"day {m['tval']:g}"
    elif t == "radius":
        when = f"radius {m['tval']:.3e} m"
    elif t == "near":
        when = f"near {m['tval']:.3e} m"
    else:
        when = t
    d = m["dirn"] if m["dirn"] != "heading" else f"heading {m['head']:g}deg"
    return f"{when:<20}{d:<12}{m['dv']:.0f} m/s"


def _plan_help():
    clear(); banner()
    print(c("  FLIGHT PLAN — how to write maneuvers", BOLD)); print(hr())
    print("  Each maneuver is:   <trigger>  <direction>  <Δv m/s>")
    print()
    print(c("  triggers (WHEN the burn fires):", CY))
    print("    day N        at mission day N (day 0 = the moment you launch)")
    print("    radius R     when your distance from the star reaches R metres")
    print("                 (your 'height'; accepts AU, e.g. 'radius 1.5au')")
    print("    apo          at the high point of your current arc (apoapsis)")
    print("    peri         at the low point (periapsis)")
    print("    near D       when you come within D metres of the target")
    print()
    print(c("  directions (WHICH way to burn):", CY))
    print("    prograde     along your motion (speeds up, raises the far side)")
    print("    retrograde   against your motion (slows down — braking/capture)")
    print("    out / in     away from / toward the star (radial)")
    print("    heading A    an absolute angle A degrees (0 = the +x reference)")
    print()
    print(c("  examples:", CY))
    print("    day 0 prograde 3200      the classic injection at launch")
    print("    apo prograde 700         raise the low side at apoapsis")
    print("    near 3e9 retrograde 500  brake as you close on the target")
    print("    day 60 heading 240 300   a mid-course nudge at 240 degrees")
    print(hr())
    print("  Fuel: the first burn (still at home) and burns inside the target's")
    print("  sphere get the Oberth discount; deep-space burns cost full Δv.")
    ask(c("\n  [enter] ", GRY))


def launch(state):
    s = state["sys"]
    if state.get("plan") is None:
        saved = save_mod.load_plan(s["seed"])
        if saved:
            state["plan"] = saved.get("plan", [])
            state["launch_day"] = saved.get("launch_day", 0.0)
        else:
            state["plan"] = []
            state["launch_day"] = 0.0

    while True:
        clear(); banner()
        if state["rocket"]:
            ve, mr = state["rocket"]
            budget = P.tsiolkovsky_dv(ve, mr)
            budget_str = c(f"{budget:.0f} m/s", G)
        else:
            budget = 0.0
            budget_str = c("no rocket yet (build one: menu 2)", Y)
        print(c("  FLIGHT PLAN CONSOLE", BOLD))
        print(f"  Launch day: {c(f'{state['launch_day']:g}', BOLD)} (days from tonight)"
              f"    Rocket Δv: {budget_str}")
        print(hr())
        if state["plan"]:
            for n, m in enumerate(state["plan"], 1):
                print(f"   {c(f'{n:>2}', CY)}. {_fmt_maneuver(m)}")
        else:
            print(c("   (empty — 'add day 0 prograde 3000' to begin, 'help' for how)", GRY))
        print(hr())
        print("  add <trigger> <dir> <Δv>   launch <days>   del <n>   clear")
        print("  fly    save    help    back")
        raw = ask("  > ").strip()
        if not raw:
            continue
        parts = raw.split(None, 1)
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if cmd in ("back", "b", "q"):
            return
        elif cmd == "help":
            _plan_help()
        elif cmd == "launch":
            v = num("  Launch in how many days from now? ") if not rest else None
            try:
                state["launch_day"] = float(rest) if rest else (v if v is not None
                                                                else state["launch_day"])
                state["dirty"] = True
            except ValueError:
                ask(c("  need a number of days. [enter] ", GRY))
        elif cmd == "add":
            m, err = _parse_maneuver(rest)
            if err:
                ask(c(f"  {err}. [enter] ", GRY))
            else:
                state["plan"].append(m); state["dirty"] = True
        elif cmd in ("del", "rm", "remove"):
            try:
                n = int(rest) - 1
                if 0 <= n < len(state["plan"]):
                    state["plan"].pop(n); state["dirty"] = True
            except ValueError:
                ask(c("  del <number>. [enter] ", GRY))
        elif cmd == "clear":
            state["plan"] = []; state["dirty"] = True
        elif cmd == "save":
            save_mod.save_plan(s["seed"], state["launch_day"], state["plan"])
            ask(c("  Flight plan saved. [enter] ", GRY))
        elif cmd == "fly":
            if not state["rocket"]:
                ask(c("  Build a rocket first (main menu option 2). [enter] ", GRY))
                continue
            if not state["plan"]:
                ask(c("  Add at least one maneuver first. [enter] ", GRY)); continue
            state["attempts"] += 1; state["dirty"] = True
            t_launch = state["launch_day"] * P.DAY
            res = P.fly_plan(s, t_launch, state["plan"], budget)
            _flight_report(state, res, t_launch)
            if res["captured"]:
                state["won"] = True
                ask(c("\n  Mission complete. [enter] to keep exploring "
                      "(remember to Save) ", GRY))
                return
        else:
            ask(c("  unknown command ('help'). [enter] ", GRY))


def _flight_report(state, res, t_launch):
    s = state["sys"]
    t_close_abs = t_launch + res["t_close_days"] * P.DAY
    animate_flight(s, {"trail": res["trail"], "t_close": t_close_abs})
    clear(); banner()
    draw_map(s, t=t_close_abs, trail=res["trail"],
             title=f"TRAJECTORY  (attempt {state['attempts']})")
    print(hr())
    print(c("  flight log:", CY))
    if res["events"]:
        for day, desc in res["events"]:
            print(f"    day {day:6.1f}:  {desc}")
    else:
        print(c("    (no burns fired — check your triggers; nothing left home)", GRY))
    print(hr())
    soi = res["soi"]
    if res["captured"]:
        print(c("  *  ORBIT ACHIEVED. You flew a plan of your own design to", G + ";1"))
        print(c("     another world — and the void agreed with your maths.", G + ";1"))
        print(f"\n     Arrived day {res['t_close_days']:.1f}, "
              f"{res['min_dist']/1e3:,.0f} km from target (SOI {soi/1e3:,.0f} km).")
        print(f"     Δv to spare: {res['budget_left']:.0f} m/s.")
        print(f"     Solved in {state['attempts']} attempt(s).")
    else:
        print(c(f"  x  Missed. Closest approach {res['min_dist']/1e3:,.0f} km "
                f"(need within {soi/1e3:,.0f} km).", R))
        _plan_diag(s, res)
    if not res["captured"]:
        ask(c("\n  [enter] ", GRY))


def _plan_diag(s, res):
    r2 = s["r2"]; apo = res["r_apo_reached"]; soi = res["soi"]
    print(c("  diagnostics:", CY))
    if res["fuel_out"]:
        print("     You ran out of Δv mid-plan — build a bigger rocket (main")
        print("     menu option 2) or use fewer / smaller burns.")
    if apo < r2 * 0.98:
        print(f"     Your arc fell short — it reached {apo/r2:.0%} of the target's")
        print("     orbit radius. Add prograde Δv early (or a burn at apoapsis).")
    elif apo > r2 * 1.05:
        print(f"     Your arc overshot — it reached {apo/r2:.0%} of the target's")
        print("     orbit radius. Ease off the early prograde Δv.")
    elif res["min_dist"] < soi:
        print("     You grazed the sphere of influence but couldn't hold on:")
        print(f"     needed {res['capture_need']:.0f} m/s to capture, had "
              f"{res['budget_at_close']:.0f}. Arrive slower (a 'near <D> retrograde'")
        print("     brake) or carry more Δv.")
    else:
        print("     Your arc reaches the target's orbit but you crossed it at the")
        print("     wrong time. Adjust the LAUNCH day (the window), or bend your")
        print("     approach with a 'near <D> retrograde' arrival burn.")


# ----------------------------------------------------------------------
# answer key (for checking your work / showing a friend)
# ----------------------------------------------------------------------
def reveal(s):
    clear(); banner()
    print(c("  ANSWER KEY  — spoilers. For checking your working.", BOLD)); print(hr())
    h = P.hohmann(s["mu_sun"], s["r1"], s["r2"])
    phi = math.degrees(P.phase_required(s["mu_sun"], s["r1"], s["r2"], s["T2"]))
    syn = P.synodic_period(s["T1"], s["T2"])
    w1, w2 = P.TWO_PI / s["T1"], P.TWO_PI / s["T2"]
    phi0 = (s["th2_0"] - s["th1_0"]) % P.TWO_PI
    phi_req = P.phase_required(s["mu_sun"], s["r1"], s["r2"], s["T2"])
    t_launch = ((phi0 - phi_req) % P.TWO_PI) / (w1 - w2)
    v_park_h = P.circular_v(s["mu_home"], s["R_home"] + s["park_alt"])
    v_park_t = P.circular_v(s["mu_target"], s["R_target"] + s["park_alt"])
    depart = P.oberth_burn(v_park_h, h["dv_inject"])
    capture = P.oberth_burn(v_park_t, h["dv_arrive"])
    rows = [
        ("home radius R", f"{s['R_home']:.4e} m"),
        ("surface gravity g", f"{s['g_home']:.4f} m/s^2"),
        ("home mass param mu_home", f"{s['mu_home']:.4e} m^3/s^2"),
        ("star mass param mu_sun", f"{s['mu_sun']:.4e} m^3/s^2"),
        ("home orbit r1", f"{s['r1']:.4e} m  ({s['r1']/P.AU:.3f} AU)"),
        ("target orbit r2", f"{s['r2']:.4e} m  ({s['r2']/P.AU:.3f} AU)"),
        ("target mass param mu_target", f"{s['mu_target']:.4e} m^3/s^2"),
        ("transfer time", f"{h['t_transfer']/P.DAY:.2f} days"),
        ("required lead angle", f"{phi:.3f} deg"),
        ("synodic period", f"{syn/P.DAY:.1f} days"),
        ("-> LAUNCH in", f"{t_launch/P.DAY:.2f} days"),
        ("-> injection dv", f"{h['dv_inject']:.1f} m/s"),
        ("departure burn (Oberth)", f"{depart:.1f} m/s"),
        ("capture burn (Oberth)", f"{capture:.1f} m/s"),
        ("-> minimum total dv", f"{depart+capture:.1f} m/s"),
    ]
    for k, v in rows:
        print(f"    {k:<30} {c(v, G)}")
    print(hr())
    print(c(f"  seed = {s['seed']}  (share it to give a friend the same system)", GRY))
    ask(c("\n  [enter] ", GRY))


# ----------------------------------------------------------------------
# lab windows + saving
# ----------------------------------------------------------------------
def open_lab_windows(s):
    """Open the guide, notes, and calculator apps in their own windows,
    tiled into screen quadrants (macOS): steps top-left, guide top-right,
    notes bottom-left, calculator bottom-right."""
    sidecar.position_self("tl")          # the game / steps window -> top-left
    opened = sum([
        sidecar.open_guide(),            # -> top-right
        sidecar.open_notes(s["seed"]),   # -> bottom-left
        sidecar.open_calc(s["seed"]),    # -> bottom-right
    ])
    if opened == 3:
        print(c("  Opened guide, notes, and calculator windows beside the lab.", G))
    elif opened > 0:
        print(c(f"  Opened {opened} companion window(s); the rest couldn't "
                f"launch here.", Y))
    else:
        print(c("  (Couldn't open extra windows in this environment. You can still", GRY))
        print(c("   read GUIDE.txt and run notes.py / calculator.py yourself.)", GRY))


def save_work(state, announce=True):
    path = save_mod.save_game(state)
    state["dirty"] = False
    if announce:
        print(c(f"  Work saved. ({path})", G))
        print(c("  You can close safely and resume this exact run later.", GRY))


def do_quit(state):
    """Manual-save ritual: warn if there is unsaved work before leaving."""
    if state["dirty"]:
        clear(); banner()
        print(c("  You have unsaved work, scientist.", R))
        print("  Nothing is saved automatically — a good scientist saves the")
        print("  logbook before going home.")
        print(hr())
        a = ask("  [s]ave and quit   [q]uit anyway   [c]ancel: ").lower()
        if a.startswith("c") or a == "":
            return False
        if a.startswith("s"):
            save_work(state)
            ask(c("\n  [enter] to leave ", GRY))
    sidecar.clear_session()   # tell companion windows the session is over
    sidecar.close_all()       # and close them now
    print("Clear skies.")
    return True


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------
def main():
    if "--diagnose" in sys.argv or "--diagnostics" in sys.argv:
        sidecar.diagnose()
        return
    cli_seed = (int(sys.argv[1]) if len(sys.argv) > 1
                and sys.argv[1].lstrip('-').isdigit() else None)

    state = {"sys": None, "rocket": None, "attempts": 0, "won": False,
             "dirty": False}

    clear(); banner()
    resumed = False
    # Offer to resume only when no explicit seed was requested on the command line.
    if cli_seed is None and save_mod.has_save():
        try:
            data = save_mod.load_game()
            print(f"\n  A saved run exists: seed {c(str(data['seed']), BOLD)}, "
                  f"{data['attempts']} attempt(s), saved {data.get('saved_at','?')}.")
            a = ask("  [r]esume it, or [n]ew run? ").lower()
            if a.startswith("r") or a == "":
                state["sys"] = P.generate_system(data["seed"])
                state["rocket"] = data["rocket"]
                state["attempts"] = data["attempts"]
                state["won"] = data["won"]
                resumed = True
        except Exception:
            pass  # corrupt/old save — just start fresh

    if state["sys"] is None:
        state["sys"] = P.generate_system(cli_seed)
    s = state["sys"]
    sidecar.write_session()   # mark the session live for companion windows

    clear(); banner()
    print(f"""
  A target planet circles your star, further out than your own world.
  Reach it. You will not be handed a single number that matters — only
  raw instrument readings. Everything else is pencil, paper, and Kepler.

  The path, roughly:
    1  Measure your own world      -> its mass, hence escape speed
    2  Measure the solar system    -> real distances and the star's mass
    3  Measure the target + moon   -> where it is, and its mass
    4  Do the transfer maths       -> the launch window and the burns
    5  Build a rocket, then launch -> the void grades your arithmetic

  System seed: {c(str(s['seed']), BOLD)}  (same seed = same universe)
  {c('Resumed your saved run.', G) if resumed else ''}
""")
    ask(c("  [enter] to open the lab ", GRY))
    print()
    open_lab_windows(s)
    ask(c("  [enter] ", GRY))

    while True:
        clear(); banner()
        r = state["rocket"]
        rk = (f"v_e={r[0]:.0f}, MR={r[1]:.2f}, dv={P.tsiolkovsky_dv(*r):.0f} m/s"
              if r else c("none built", GRY))
        flag = c("  * unsaved", Y) if state["dirty"] else ""
        print(f"  Seed {s['seed']}    Rocket: {rk}    "
              f"Attempts: {state['attempts']}{flag}")
        print(hr())
        print("  1. Instruments        take raw measurements")
        print("  2. Assemble rocket    Tsiolkovsky / fuel")
        print("  3. System map         ASCII top-down view (tonight)")
        print("  4. LAUNCH             commit your window + burn")
        print("  5. Answer key         reveal truth (check your work)")
        print("  6. Open lab windows   guide + notes + calculator")
        print("  7. Save work          manual save — resume later")
        print("  8. Quit")
        print(hr())
        k = ask("  > ").lower()
        if k == "1":
            instruments(s)
        elif k == "2":
            build_rocket(state)
        elif k == "3":
            animate_orbits(s)
            clear(); banner(); draw_map(s, 0.0); ask(c("\n  [enter] ", GRY))
        elif k == "4":
            launch(state)
        elif k == "5":
            reveal(s)
        elif k == "6":
            clear(); banner(); open_lab_windows(s); ask(c("\n  [enter] ", GRY))
        elif k == "7":
            clear(); banner(); save_work(state); ask(c("\n  [enter] ", GRY))
        elif k in ("8", "q", "quit"):
            if do_quit(state):
                return
        else:
            pass


if __name__ == "__main__":
    main()