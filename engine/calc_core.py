"""
Pure calculator core, shared by the TUI's calculator panel.
No I/O, no UI — just the expression evaluator, constants, and formatting.
'^' means power (converted to Python's **).
"""

import re, math

BASE = {k: getattr(math, k) for k in
        ("sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
         "log", "log10", "exp", "pi", "tau", "radians", "degrees",
         "hypot", "floor", "ceil", "fabs", "pow")}
BASE["ln"] = math.log
BASE["e"] = math.e
BASE["abs"] = abs
BASE.update({
    "G": 6.674e-11, "c": 2.998e8, "AU": 1.496e11,
    "DAY": 86400.0, "YEAR": 365.25 * 86400.0,
})

ASSIGN = re.compile(r"^\s*([A-Za-z_]\w*)\s*=(?!=)\s*(.+)$")


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
    """Evaluate an expression (with ^ as power) against env. Raises on error."""
    return eval(expr.replace("^", "**"), {"__builtins__": {}}, env)


def user_vars(env):
    return {k: v for k, v in env.items()
            if k not in BASE and k != "ans" and isinstance(v, (int, float, bool))}