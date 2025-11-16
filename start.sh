#!/bin/bash
set -e

# Clean up possible leftovers from previous crashed sessions
rm -rf /tmp/.X99-lock /tmp/.X11-unix/X99

# Start Xvfb (virtual display server)
Xvfb :99 -screen 0 1280x1024x24 &
sleep 2

# Start window manager
DISPLAY=:99 fluxbox &
sleep 2

# Start x11vnc (one shot, always)
x11vnc -display :99 -nopw -listen 0.0.0.0 -xkb -ncache 10 -ncache_cr -forever -shared &
sleep 2

# Start noVNC websocket proxy
websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
sleep 2

echo "VNC server started on port 5900"
echo "noVNC web interface available on port 6080"

# Start Flask application (blocking/main process)
exec python -m flask --app app run --host 0.0.0.0 --port 8080
