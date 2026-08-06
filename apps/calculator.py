#!/usr/bin/env python3
"""
calculator.py — a small scientific REPL for the lab bench, in its own window.

Type arithmetic; the answer prints underneath, just like Python's terminal —
except '^' means "to the power of" (so 2^10 = 1024), which is what you want
when you're doing orbital maths by hand.

  * powers use ^     e.g.  a_t^3,  2^0.5
  * store variables  e.g.  R = 6.1e6   then use R later
    variables are REMEMBERED between sessions (saved per solar system)
  * 'ans' is the previous result
  * built-in: sqrt sin cos tan asin acos atan atan2 ln log exp
              pi e tau radians degrees hypot abs floor ceil
  * constants: G c AU DAY YEAR   (SI; matches the game)

  commands:  /vars    show your variables    /clear   clear the screen
             /forget  forget a variable      /help    this help
             /forget name   forget just one  /quit    close the window

Usage:  python3 calculator.py
"""

import os, sys, re, math, json
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))
import paths

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
def col(t, code):
    return f"\033[{code}m{t}\033[0m" if USE_COLOR else t

SEED = sys.argv[1] if len(sys.argv) > 1 else None
# variables persist per solar system (per seed); standalone uses a shared file
VARS = os.path.join(paths.SAVES_DIR,
                    f"calc_vars_{SEED}.json" if SEED else "calc_vars.json")

# names available inside expressions
BASE = {k: getattr(math, k) for k in
        ("sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
         "log", "log10", "exp", "pi", "e", "tau", "radians", "degrees",
         "hypot", "floor", "ceil", "fabs", "pow")}
BASE["ln"] = math.log
BASE["abs"] = abs
BASE.update({
    "G": 6.674e-11, "c": 2.998e8, "AU": 1.496e11,
    "DAY": 86400.0, "YEAR": 365.25 * 86400.0,
})

ASSIGN = re.compile(r"^\s*([A-Za-z_]\w*)\s*=(?!=)\s*(.+)$")


def load_vars():
    """Return previously-saved user variables (numbers only)."""
    try:
        with open(VARS) as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if isinstance(v, (int, float))}
    except Exception:
        return {}


def save_vars(env):
    """Persist the user's own variables (not built-ins, not 'ans')."""
    data = {k: v for k, v in env.items()
            if k not in BASE and k != "ans" and isinstance(v, (int, float, bool))}
    try:
        with open(VARS, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def fmt(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != 0 and (abs(v) >= 1e6 or abs(v) < 1e-3):
            return f"{v:.6e}"
        return f"{v:.6g}"
    return str(v)


def evaluate(expr, env):
    expr = expr.replace("^", "**")   # powers the human way
    return eval(expr, {"__builtins__": {}}, env)


def main():
    try:
        import sidecar
        sidecar.start_watcher()
    except Exception:
        pass
    env = dict(BASE)
    env["ans"] = 0.0
    env.update(load_vars())                       # remember last session's vars
    nload = sum(1 for k in env if k not in BASE and k != "ans")
    print(col("=" * 56, "36"))
    print(col("  LAB CALCULATOR   ('^' = power, /help for more)", "1"))
    print(col("=" * 56, "36"))
    if nload:
        print(col(f"  (remembered {nload} variable(s) from last time — /vars)", "90"))
    while True:
        try:
            line = input(col("calc> ", "33"))
        except (EOFError, KeyboardInterrupt):
            print("\nCalculator closed.")
            return
        s = line.strip()
        if not s:
            continue

        if s.startswith("/"):
            cmd = s.lower()
            if cmd in ("/quit", "/q", "/exit"):
                print("Calculator closed.")
                try:
                    import sidecar; sidecar.close_own_window()
                except Exception:
                    pass
                return
            if cmd == "/clear":
                os.system("cls" if os.name == "nt" else "clear")
                continue
            if cmd == "/vars":
                user = {k: v for k, v in env.items()
                        if k not in BASE and k != "ans"}
                if not user:
                    print(col("  (no variables yet — try  R = 6.1e6)", "90"))
                for k, v in user.items():
                    print(f"  {k} = {col(fmt(v), '36')}")
                print(f"  ans = {col(fmt(env['ans']), '36')}")
                continue
            if cmd == "/help":
                print(__doc__.strip())
                continue
            if cmd.startswith("/forget"):
                # /forget name   forgets one; /forget   forgets all your vars
                names = s.split()[1:]
                targets = names or [k for k in list(env)
                                    if k not in BASE and k != "ans"]
                for nm in targets:
                    if nm in env and nm not in BASE and nm != "ans":
                        del env[nm]
                save_vars(env)
                print(col("  forgotten.", "90"))
                continue
            print(col("  unknown command (/help)", "90"))
            continue

        try:
            m = ASSIGN.match(s)
            if m:
                name, rhs = m.group(1), m.group(2)
                val = evaluate(rhs, env)
                env[name] = val
                env["ans"] = val
                save_vars(env)                    # remember it for next time
                print(f"  {name} = {col(fmt(val), '32')}")
            else:
                val = evaluate(s, env)
                env["ans"] = val
                print(f"  = {col(fmt(val), '32')}")
        except ZeroDivisionError:
            print(col("  error: division by zero", "31"))
        except NameError as e:
            print(col(f"  error: {e} (unknown name — /vars to see yours)", "31"))
        except Exception as e:
            print(col(f"  error: {e}", "31"))


if __name__ == "__main__":
    main()