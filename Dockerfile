# Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GOGREPO_DATA_DIR=/app/data

WORKDIR /app

# Wymagane biblioteki dla GUI-backendu i parsowania
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Zależności Pythona
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Aplikacja
COPY app.py /app/app.py
COPY templates/ /app/templates/
COPY static/ /app/static/

# Skrypt gogrepo.py (umieść w kontekście buildu lub podmontuj volume)
COPY gogrepo.py /app/gogrepo.py

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "-m", "flask", "--app", "app", "run", "--host", "0.0.0.0", "--port", "8080"]
