#!/bin/bash
set -e

# Only run Xvfb if not already running
if ! pgrep -f "Xvfb :99" > /dev/null; then
  Xvfb :99 -screen 0 1280x1024x24 &
fi
sleep 2

# Only run fluxbox if not already running
if ! pgrep -f "fluxbox.*:99" > /dev/null; then
  DISPLAY=:99 fluxbox &
fi
sleep 1

# Only run x11vnc if not already running
if ! pgrep -f "x11vnc.*:99" > /dev/null; then
  x11vnc -display :99 -nopw -listen 0.0.0.0 -xkb -ncache 10 -ncache_cr -forever -shared &
fi
sleep 2

# Only run websockify if not already running
if ! pgrep -f "websockify.*6080" > /dev/null; then
  websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
fi
sleep 2

echo "VNC server started on port 5900"
echo "noVNC web interface available on port 6080"

# Start Flask application in the foreground (blocks exit)
exec python -m flask --app app run --host 0.0.0.0 --port 8080
