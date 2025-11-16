# Dockerfile - GOGrepo GUI with Interactive Browser Login
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GOGREPO_DATA_DIR=/app/data \
    DISPLAY=:99 \
    VNC_PORT=6080 \
    FLASK_PORT=8080 \
    CHROME_PROFILE=/tmp/chrome-profile

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Basic tools
    ca-certificates \
    curl \
    wget \
    gnupg \
    # Chromium browser
    chromium \
    chromium-driver \
    # VNC and X11
    xvfb \
    x11vnc \
    # noVNC
    novnc \
    websockify \
    # SQLite for cookie extraction
    sqlite3 \
    # Other utilities
    procps \
    psmisc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application files
COPY app.py /app/app.py
COPY cookie_extractor.py /app/cookie_extractor.py
COPY gogrepo.py /app/gogrepo.py
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY entrypoint.sh /app/entrypoint.sh

# Make scripts executable
RUN chmod +x /app/entrypoint.sh /app/cookie_extractor.py

# Create directories
RUN mkdir -p /app/data /tmp/chrome-profile

# Expose ports
# 8080 - Flask GUI (GOGrepo-GUI)
# 6080 - noVNC web interface
# 3000 - Cookie extractor interface
EXPOSE 8080 6080 3000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
