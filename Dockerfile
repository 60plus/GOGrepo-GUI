# Dockerfile - robust APT install with retry
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GOGREPO_DATA_DIR=/app/data \
    DISPLAY=:99 \
    VNC_PORT=5900 \
    NOVNC_PORT=6080

WORKDIR /app

# --- Robust apt-get install with 3 automatic retries ---
RUN set -e; \
    for i in 1 2 3; do \
      apt-get update && \
      apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        wget \
        git \
        x11vnc \
        xvfb \
        fluxbox \
        chromium \
        chromium-driver \
        net-tools \
        novnc \
        sqlite3 \
        && rm -rf /var/lib/apt/lists/* && break || (echo "APT failed on attempt $i" && apt-get clean && rm -rf /var/lib/apt/lists/* && sleep 5); \
    done

RUN ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY app.py /app/app.py
COPY vnc_browser.py /app/vnc_browser.py
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY gogrepo.py /app/gogrepo.py

RUN mkdir -p /app/data /app/vnc_profiles

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8080 6080

CMD ["/app/start.sh"]
