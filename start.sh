#!/bin/bash
set -e

# Clean up any old Xvfb locks that could prevent display startup
rm -rf /tmp/.X99-lock /tmp/.X11-unix/X99

# Start Xvfb
Xvfb :99 -screen 0 1280x1024x24 &
sleep 2

# Start minimal window manager
DISPLAY=:99 fluxbox &
sleep 2

# Start Chromium (always visible)
CHROMIUM_PROFILE=/app/chrome-profile
rm -rf "$CHROMIUM_PROFILE"
mkdir -p "$CHROMIUM_PROFILE"
DISPLAY=:99 chromium --no-sandbox --disable-dev-shm-usage --disable-gpu --user-data-dir=$CHROMIUM_PROFILE --window-size=1200,900 --no-first-run --no-default-browser-check "https://www.gog.com/" &
sleep 5

# Start x11vnc
x11vnc -display :99 -nopw -listen 0.0.0.0 -xkb -ncache 10 -ncache_cr -forever -shared &
sleep 2

# Start noVNC
websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
sleep 2

echo "VNC and Chromium running. Access via noVNC/Flask."

exec python -m flask --app app run --host 0.0.0.0 --port 8080
