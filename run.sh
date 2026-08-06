#!/usr/bin/env bash
# Launch Window — finds a suitable Python, then starts the game.
# Works on Linux and macOS.   Usage:  ./run.sh   or   ./run.sh 42
cd "$(dirname "$0")" || exit 1

# Requires Python 3.12+ (widely available; easy to install everywhere).
need_major=3
need_minor=12

check() {   # $1 = interpreter name; succeeds if it's new enough
    "$1" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= ($need_major,$need_minor) else 1)" \
        >/dev/null 2>&1
}

PY=""
for cand in python3 python python3.14 python3.13 python3.12; do
    if command -v "$cand" >/dev/null 2>&1 && check "$cand"; then
        PY="$cand"; break
    fi
done

if [ -z "$PY" ]; then
    echo "Launch Window needs Python ${need_major}.${need_minor} or newer."
    if command -v python3 >/dev/null 2>&1; then
        echo "The Python it found is too old:  $(python3 --version 2>&1)"
    else
        echo "No Python was found on your PATH."
    fi
    echo
    echo "Install a recent Python:"
    echo "  macOS:          brew install python     (or python.org/downloads)"
    echo "  Debian/Ubuntu:  sudo apt update && sudo apt install python3"
    echo "  Fedora:         sudo dnf install python3"
    echo "  Arch:           sudo pacman -S python"
    echo "  Windows/other:  https://www.python.org/downloads/"
    exit 1
fi

echo "Using $($PY --version 2>&1) — starting Launch Window..."

# Launch Window needs Textual. If it's missing, offer to install it (no root).
if ! "$PY" -c "import textual" >/dev/null 2>&1; then
    echo
    echo "Launch Window needs the 'textual' package, which isn't installed."
    printf "Install it now with pip?  [Y/n] "
    read -r ans
    case "$ans" in
        [Nn]*)
            echo "OK — install it later with:  $PY -m pip install textual"
            exit 1
            ;;
        *)
            "$PY" -m pip3 install --user textual 2>/dev/null \
                || "$PY" -m pip3 install --break-system-packages textual
            if ! "$PY" -c "import textual" >/dev/null 2>&1; then
                echo "Install didn't work. Try manually:  $PY -m pip install textual"
                exit 1
            fi
            ;;
    esac
fi

exec "$PY" tui.py "$@"