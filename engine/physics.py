"""
Orbital transfer game — physics core.

Everything here is honest two-body / patched-conics physics in SI units.
The rocket is flown by a real RK4 integrator under the star's gravity, so a
correctly-planned transfer genuinely arrives and a mis-measured one genuinely
misses. Nothing is faked or fudged toward the player.

Model / simplifications (documented for the guide):
  * Planets ride circular, coplanar orbits (analytic positions, exact).
  * The rocket's heliocentric trajectory feels only the star's point-mass
    gravity (patched conics: we ignore the depth of the planetary wells for
    the *trajectory*, but the planetary masses fully determine the *fuel*
    needed for the departure and capture burns via the Oberth-correct
    rocket equation).
  * Burns are impulsive (instantaneous).
These are the standard first-order approximations; they keep every number the
player computes exactly predictive of what the integrator does.
"""

import math
import random

# ---- universal constants (the player is allowed to know these) ----
G = 6.674e-11          # gravitational constant, m^3 kg^-1 s^-2
C_LIGHT = 2.998e8      # speed of light, m/s
AU = 1.496e11          # metres (for display only)
DAY = 86400.0          # seconds
YEAR = 365.25 * DAY

TWO_PI = 2.0 * math.pi


# ----------------------------------------------------------------------
# system generation (seeded, so runs are shareable)
# ----------------------------------------------------------------------
def generate_system(seed=None):
    if seed is None:
        seed = random.randrange(1, 10_000)
    rng = random.Random(seed)

    mu_sun = rng.uniform(0.85, 1.25) * 1.327e20      # ~ solar mu
    r1 = rng.uniform(0.85, 1.15) * AU                # home orbit radius
    ratio = rng.uniform(1.35, 1.90)                  # target further out
    r2 = r1 * ratio

    # periods follow from Kepler (kept exactly consistent)
    T1 = TWO_PI * math.sqrt(r1**3 / mu_sun)
    T2 = TWO_PI * math.sqrt(r2**3 / mu_sun)

    # home world — sampled from radius + density so mass, gravity and mu all
    # follow physically. Wide ranges: small dense rock ... chunky super-Earth.
    R_home = rng.uniform(2.4e6, 1.10e7)             # radius, m
    rho_home = rng.uniform(3000.0, 6000.0)          # rocky density, kg/m^3
    mu_home = G * (4.0 / 3.0 * math.pi) * R_home**3 * rho_home
    g_home = mu_home / R_home**2                    # surface gravity, m/s^2

    # target world + its moon (moon gives us the target's mass, via Kepler)
    R_target = rng.uniform(2.4e6, 1.10e7)
    rho_target = rng.uniform(3000.0, 6000.0)
    mu_target = G * (4.0 / 3.0 * math.pi) * R_target**3 * rho_target
    a_moon = R_target * rng.uniform(8.0, 28.0)      # moon orbit radius, m
    T_moon = TWO_PI * math.sqrt(a_moon**3 / mu_target)

    # starting angular positions (radians, prograde = CCW)
    th1_0 = rng.uniform(0, TWO_PI)
    th2_0 = rng.uniform(0, TWO_PI)

    park_alt = 300e3   # both parking orbits sit 300 km up

    return {
        "seed": seed,
        "mu_sun": mu_sun, "r1": r1, "r2": r2, "T1": T1, "T2": T2,
        "R_home": R_home, "g_home": g_home, "mu_home": mu_home,
        "R_target": R_target, "mu_target": mu_target,
        "a_moon": a_moon, "T_moon": T_moon,
        "th1_0": th1_0, "th2_0": th2_0,
        "park_alt": park_alt,
    }


# ----------------------------------------------------------------------
# analytic orbital mechanics (what the player must rediscover)
# ----------------------------------------------------------------------
def circular_v(mu, r):
    return math.sqrt(mu / r)

def period(mu, r):
    return TWO_PI * math.sqrt(r**3 / mu)

def planet_pos(r, T, th0, t):
    th = th0 + TWO_PI * t / T
    return (r * math.cos(th), r * math.sin(th)), th

def planet_angle(T, th0, t):
    return (th0 + TWO_PI * t / T) % TWO_PI


def hohmann(mu, r1, r2):
    """Return a dict of the classic outbound Hohmann quantities."""
    a_t = 0.5 * (r1 + r2)
    v1 = math.sqrt(mu / r1)
    v2 = math.sqrt(mu / r2)
    v_peri = math.sqrt(mu * (2.0 / r1 - 1.0 / a_t))   # transfer speed at r1
    v_apo = math.sqrt(mu * (2.0 / r2 - 1.0 / a_t))     # transfer speed at r2
    dv_inject = v_peri - v1                             # heliocentric, at departure
    dv_arrive = v2 - v_apo                              # heliocentric, at target
    t_transfer = math.pi * math.sqrt(a_t**3 / mu)       # half the ellipse period
    return {
        "a_t": a_t, "v1": v1, "v2": v2, "v_peri": v_peri, "v_apo": v_apo,
        "dv_inject": dv_inject, "dv_arrive": dv_arrive, "t_transfer": t_transfer,
    }

def phase_required(mu, r1, r2, T2):
    """Angle by which the target must LEAD home at launch (radians)."""
    tau = hohmann(mu, r1, r2)["t_transfer"]
    return math.pi - TWO_PI * tau / T2

def synodic_period(T1, T2):
    return 1.0 / abs(1.0 / T1 - 1.0 / T2)

def oberth_burn(v_park, v_inf):
    """
    Real Δv spent burning out of / into a circular parking orbit to obtain
    hyperbolic excess speed v_inf.  This is where the planet's mass matters:
    a deeper well (bigger v_park) makes the same v_inf CHEAPER (Oberth effect).
    """
    return math.sqrt(v_park * v_park + v_inf * v_inf) - v_park

def soi_radius(a_planet, mu_planet, mu_sun):
    """Sphere-of-influence radius — the capture target."""
    return a_planet * (mu_planet / mu_sun) ** 0.4

def tsiolkovsky_dv(v_e, mass_ratio):
    return v_e * math.log(mass_ratio)

def tsiolkovsky_ratio(v_e, dv):
    return math.exp(dv / v_e)


# ----------------------------------------------------------------------
# the integrator that actually flies the rocket
# ----------------------------------------------------------------------
def _accel(x, y, mu_sun):
    r2 = x * x + y * y
    r = math.sqrt(r2)
    a = -mu_sun / r2
    return a * x / r, a * y / r

def fly(sys, t_launch, dv_inject, max_time=None, steps=12000):
    """
    Launch the rocket at time t_launch with a prograde heliocentric burn of
    dv_inject (m/s), applied at the home planet's position/velocity.  Integrate
    under the star's gravity with RK4 and return the trajectory + the closest
    approach to the target.

    Returns dict:
      trail            : list of (t, x, y) samples for plotting
      min_dist         : closest approach distance to target (m)
      t_close          : time of closest approach
      v_rel_close      : rocket-target relative speed at closest approach (m/s)
      r_apo_reached    : farthest heliocentric radius reached (m)
      arrived          : bool, entered target SOI
    """
    mu = sys["mu_sun"]
    r1, T1, th1_0 = sys["r1"], sys["T1"], sys["th1_0"]
    r2, T2, th2_0 = sys["r2"], sys["T2"], sys["th2_0"]

    # initial state at t_launch
    th1 = planet_angle(T1, th1_0, t_launch)
    px, py = r1 * math.cos(th1), r1 * math.sin(th1)
    v1 = circular_v(mu, r1)
    speed = v1 + dv_inject
    # prograde (CCW) tangential unit vector at angle th1 is (-sin, cos)
    vx, vy = -math.sin(th1) * speed, math.cos(th1) * speed

    if max_time is None:
        # integrate a bit beyond the ideal transfer time
        max_time = 1.6 * hohmann(mu, r1, r2)["t_transfer"]
    dt = max_time / steps

    trail = [(t_launch, px, py)]
    min_dist = float("inf")
    t_close = t_launch
    v_rel_close = 0.0
    r_apo = math.hypot(px, py)

    t = t_launch
    for i in range(steps):
        # target position at this instant
        th2 = th2_0 + TWO_PI * t / T2
        tx, ty = r2 * math.cos(th2), r2 * math.sin(th2)
        d = math.hypot(px - tx, py - ty)
        if d < min_dist:
            min_dist = d
            t_close = t
            # target velocity (for relative speed)
            v2 = circular_v(mu, r2)
            tvx, tvy = -math.sin(th2) * v2, math.cos(th2) * v2
            v_rel_close = math.hypot(vx - tvx, vy - tvy)

        # RK4 step
        ax1, ay1 = _accel(px, py, mu)
        k1x, k1y, k1vx, k1vy = vx, vy, ax1, ay1
        ax2, ay2 = _accel(px + 0.5*dt*k1x, py + 0.5*dt*k1y, mu)
        k2x, k2y, k2vx, k2vy = vx + 0.5*dt*k1vx, vy + 0.5*dt*k1vy, ax2, ay2
        ax3, ay3 = _accel(px + 0.5*dt*k2x, py + 0.5*dt*k2y, mu)
        k3x, k3y, k3vx, k3vy = vx + 0.5*dt*k2vx, vy + 0.5*dt*k2vy, ax3, ay3
        ax4, ay4 = _accel(px + dt*k3x, py + dt*k3y, mu)
        k4x, k4y, k4vx, k4vy = vx + dt*k3vx, vy + dt*k3vy, ax4, ay4

        px += dt/6.0 * (k1x + 2*k2x + 2*k3x + k4x)
        py += dt/6.0 * (k1y + 2*k2y + 2*k3y + k4y)
        vx += dt/6.0 * (k1vx + 2*k2vx + 2*k3vx + k4vx)
        vy += dt/6.0 * (k1vy + 2*k2vy + 2*k3vy + k4vy)
        t += dt

        r_apo = max(r_apo, math.hypot(px, py))
        if i % max(1, steps // 400) == 0:
            trail.append((t, px, py))

    soi = soi_radius(r2, sys["mu_target"], mu)
    return {
        "trail": trail, "min_dist": min_dist, "t_close": t_close,
        "v_rel_close": v_rel_close, "r_apo_reached": r_apo,
        "arrived": min_dist < soi, "soi": soi,
    }


# ----------------------------------------------------------------------
# staged flight plans — a sequence of triggered burns
# ----------------------------------------------------------------------
# A maneuver is a dict (JSON-friendly, easy to save):
#   {"trig": "day"|"radius"|"apo"|"peri"|"near",
#    "tval": float|None,          # days (day), metres (radius), metres (near)
#    "dirn": "prograde"|"retrograde"|"out"|"in"|"heading",
#    "head": float|None,          # degrees, for "heading"
#    "dv":   float}               # m/s
#
# Maneuvers fire in the order given: the executor waits for maneuver i's
# trigger, applies its burn, then waits for maneuver i+1's, and so on.

def _burn_dir(dirn, head, px, py, vx, vy):
    r = math.hypot(px, py) or 1.0
    sp = math.hypot(vx, vy) or 1.0
    if dirn == "prograde":
        return vx / sp, vy / sp
    if dirn == "retrograde":
        return -vx / sp, -vy / sp
    if dirn == "out":
        return px / r, py / r
    if dirn == "in":
        return -px / r, -py / r
    if dirn == "heading":
        a = math.radians(head or 0.0)
        return math.cos(a), math.sin(a)
    return 0.0, 0.0


def fly_plan(sys, t_launch, maneuvers, dv_budget, steps=None):
    """
    Release the rocket into solar orbit at time t_launch (seconds from now,
    riding the home planet's velocity), then execute `maneuvers` in order,
    integrating under the star's gravity. Returns trajectory + outcome.
    """
    mu = sys["mu_sun"]
    r1, T1, th1_0 = sys["r1"], sys["T1"], sys["th1_0"]
    r2, T2, th2_0 = sys["r2"], sys["T2"], sys["th2_0"]
    soi = soi_radius(r2, sys["mu_target"], mu)
    v_park_t = circular_v(sys["mu_target"], sys["R_target"] + sys["park_alt"])

    # initial heliocentric state: home position, home orbital velocity
    th1 = planet_angle(T1, th1_0, t_launch)
    px, py = r1 * math.cos(th1), r1 * math.sin(th1)
    v1 = circular_v(mu, r1)
    vx, vy = -math.sin(th1) * v1, math.cos(th1) * v1

    budget = float(dv_budget)
    events = []
    v_park_h = circular_v(sys["mu_home"], sys["R_home"] + sys["park_alt"])

    def _cost_of(dv, where):
        if where == "deep":
            return dv
        vp = v_park_h if where == "home" else v_park_t
        return oberth_burn(vp, dv)          # burning in a well is cheaper (Oberth)

    def _dv_from_fuel(fuel, where):
        if where == "deep":
            return fuel
        vp = v_park_h if where == "home" else v_park_t
        return math.sqrt((fuel + vp) ** 2 - vp ** 2)

    # integration horizon: cover the last 'day' trigger plus a transfer, capped
    tau_ref = hohmann(mu, r1, r2)["t_transfer"]
    last_day = max([m["tval"] for m in maneuvers
                    if m["trig"] == "day" and m["tval"] is not None], default=0.0)
    horizon = min(6 * T2, max(2.5 * tau_ref, last_day * DAY + 1.5 * tau_ref))
    if steps is None:
        steps = int(min(120000, max(8000, horizon / (2 * 3600))))  # ~2h/step
    dt = horizon / steps

    def target_state(t):
        th2 = th2_0 + TWO_PI * t / T2
        tx, ty = r2 * math.cos(th2), r2 * math.sin(th2)
        v2 = circular_v(mu, r2)
        return tx, ty, -math.sin(th2) * v2, math.cos(th2) * v2

    def apply(m, mday, where):
        nonlocal vx, vy, budget
        want = m["dv"]
        cost = _cost_of(want, where)
        if cost <= budget:
            dv = want; budget -= cost
        else:
            dv = _dv_from_fuel(budget, where); budget = 0.0
        dx, dy = _burn_dir(m["dirn"], m.get("head"), px, py, vx, vy)
        vx += dv * dx
        vy += dv * dy
        short = "" if dv >= want - 1e-6 else f" (only {dv:.0f} m/s — out of fuel)"
        d = m["dirn"] if m["dirn"] != "heading" else f"heading {m.get('head',0):g}deg"
        where_tag = {"home": " [home Oberth]", "target": " [capture Oberth]",
                     "deep": ""}[where]
        events.append((mday, f"{want:.0f} m/s {d}{where_tag}{short}; "
                             f"Δv left {budget:.0f}"))

    trail = [(t_launch, px, py)]
    min_dist = float("inf"); t_close = 0.0; v_rel_close = 0.0
    budget_at_close = budget; r_apo = math.hypot(px, py)
    captured = False; fuel_out = False

    i = 0
    mission_t = 0.0
    # previous-step values for crossing/extremum detection
    prev_r = math.hypot(px, py)
    prev_rdot = (px * vx + py * vy) / prev_r
    tx, ty, tvx, tvy = target_state(t_launch)
    prev_dist = math.hypot(px - tx, py - ty)

    for step in range(steps):
        t = t_launch + mission_t
        r = math.hypot(px, py)
        rdot = (px * vx + py * vy) / (r or 1.0)
        tx, ty, tvx, tvy = target_state(t)
        dist = math.hypot(px - tx, py - ty)

        # fire the next pending maneuver if its trigger is satisfied
        if i < len(maneuvers):
            m = maneuvers[i]
            fired = False
            k = m["trig"]
            if k == "day":
                fired = mission_t >= (m["tval"] or 0.0) * DAY
            elif k == "radius":
                R = m["tval"] or 0.0
                fired = (prev_r - R) == 0 or (prev_r - R) * (r - R) < 0 or r == R
            elif k == "near":
                fired = dist <= (m["tval"] or 0.0)
            elif k == "apo":
                fired = prev_rdot > 0 >= rdot          # radial vel + -> -
            elif k == "peri":
                fired = prev_rdot < 0 <= rdot          # radial vel - -> +
            if fired:
                where = ("home" if i == 0 else
                         "target" if dist < soi else "deep")
                apply(m, mission_t / DAY, where)
                if budget <= 1e-6:
                    fuel_out = True
                i += 1
                # recompute velocity-derived values after the burn
                rdot = (px * vx + py * vy) / (r or 1.0)

        # track closest approach + capture opportunity
        if dist < min_dist:
            min_dist = dist; t_close = mission_t
            v_rel_close = math.hypot(vx - tvx, vy - tvy)
            budget_at_close = budget
        if dist < soi:
            v_rel = math.hypot(vx - tvx, vy - tvy)
            need = oberth_burn(v_park_t, v_rel)
            if budget >= need:
                captured = True
                min_dist = min(min_dist, dist)
                t_close = mission_t; v_rel_close = v_rel; budget_at_close = budget
                break

        # RK4 under the star's gravity
        ax1, ay1 = _accel(px, py, mu)
        ax2, ay2 = _accel(px + 0.5*dt*vx, py + 0.5*dt*vy, mu)
        vx2, vy2 = vx + 0.5*dt*ax1, vy + 0.5*dt*ay1
        ax3, ay3 = _accel(px + 0.5*dt*vx2, py + 0.5*dt*vy2, mu)
        vx3, vy3 = vx + 0.5*dt*ax2, vy + 0.5*dt*ay2
        ax4, ay4 = _accel(px + dt*vx3, py + dt*vy3, mu)
        vx4, vy4 = vx + dt*ax3, vy + dt*ay3
        px += dt/6.0 * (vx + 2*vx2 + 2*vx3 + vx4)
        py += dt/6.0 * (vy + 2*vy2 + 2*vy3 + vy4)
        vx += dt/6.0 * (ax1 + 2*ax2 + 2*ax3 + ax4)
        vy += dt/6.0 * (ay1 + 2*ay2 + 2*ay3 + ay4)

        prev_r = r; prev_rdot = rdot; prev_dist = dist
        r_apo = max(r_apo, math.hypot(px, py))
        mission_t += dt
        if step % max(1, steps // 500) == 0:
            trail.append((t_launch + mission_t, px, py))

    need_close = oberth_burn(v_park_t, v_rel_close)
    return {
        "trail": trail, "events": events,
        "min_dist": min_dist, "t_close_days": t_close / DAY,
        "v_rel_close": v_rel_close, "budget_left": budget,
        "budget_at_close": budget_at_close, "capture_need": need_close,
        "r_apo_reached": r_apo, "soi": soi,
        "captured": captured, "fuel_out": fuel_out,
        "maneuvers_done": i, "maneuvers_total": len(maneuvers),
    }