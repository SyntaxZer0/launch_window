#!/bin/bash
# Double-click this on macOS to start LAUNCH WINDOW.
# It runs the game in this window; the game then opens the guide and
# notes in their own windows. You can also pass a seed:  ./open_lab.command 42
cd "$(dirname "$0")"
exec python3 launch_window.py "$@"
