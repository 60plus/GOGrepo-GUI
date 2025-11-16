#!/bin/bash

# Start Xvfb (virtual display)
Xvfb :99 -screen 0 1280x1024x24 &
sleep 2

# Start Fluxbox window manager
fluxbox &
sleep 1

# Start x11vnc server
x11vnc -display :99 -nopw -listen 0.0.0.0 -xkb -ncache 10 -ncache_cr -forever -shared &
sleep 2

# Start noVNC websocket proxy
websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
sleep 2

echo "VNC server started on port 5900"
echo "noVNC web interface available on port 6080"

# Start Flask application
exec python -m flask --app app run --host 0.0.0.0 --port 8080