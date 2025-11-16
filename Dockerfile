# Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GOGREPO_DATA_DIR=/app/data \
    DISPLAY=:99 \
    VNC_PORT=5900 \
    NOVNC_PORT=6080

WORKDIR /app

# Install system dependencies for VNC, noVNC, Chromium and GUI backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    git \
    # VNC server
    x11vnc \
    xvfb \
    # Window manager
    fluxbox \
    # Chromium browser
    chromium \
    chromium-driver \
    # noVNC dependencies
    net-tools \
    novnc \
    # Cookie extraction
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Setup noVNC
RUN ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Application files
COPY app.py /app/app.py
COPY vnc_browser.py /app/vnc_browser.py
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY gogrepo.py /app/gogrepo.py

# Create necessary directories
RUN mkdir -p /app/data /app/vnc_profiles

# Startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8080 6080

CMD ["/app/start.sh"]