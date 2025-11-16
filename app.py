#!/usr/bin/env python3
import os
import json
import pickle
import shlex
import uuid
import subprocess
import threading
import ast
import time
import hashlib
import traceback
import re
import sqlite3
import http.cookiejar as cookiejar
from typing import Optional
from datetime import datetime
from pathlib import Path

import pexpect
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, send_from_directory, render_template_string

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev")

APP_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("GOGREPO_DATA_DIR", "/app/data")
os.makedirs(DATA_DIR, exist_ok=True)

GOGREPO = os.environ.get("GOGREPO_PATH", os.path.join(APP_DIR, "gogrepo.py"))
PY      = os.environ.get("PYTHON_BIN", "python3")

MANIFEST = os.path.join(DATA_DIR, "gog-manifest.dat")
COOKIES  = os.path.join(DATA_DIR, "gog-cookies.dat")
CHROME_PROFILE = os.environ.get("CHROME_PROFILE", "/tmp/chrome-profile")
VNC_PORT = os.environ.get("VNC_PORT", "6080")

# Download directory for checking downloaded games
DOWNLOAD_DIR = os.environ.get("GOGREPO_DOWNLOAD_DIR", DATA_DIR)

CACHE_DIR = os.path.join(DATA_DIR, "Cache")
DESC_DIR  = os.path.join(CACHE_DIR, "desc")
COVER_DIR = os.path.join(CACHE_DIR, "cover")
os.makedirs(DESC_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)

DAY_MS    = 24 * 60 * 60 * 1000
DESC_TTL  = 7 * DAY_MS
COVER_TTL = 30 * DAY_MS
PAGE_TTL  = 14 * DAY_MS

def check_cookies_exist() -> bool:
    """Check if valid cookies file exists"""
    if not os.path.exists(COOKIES):
        return False
    try:
        if os.path.getsize(COOKIES) > 0:
            return True
    except:
        pass
    return False

def extract_chrome_cookies():
    """Extract cookies from Chromium SQLite database"""
    cookies_db = os.path.join(CHROME_PROFILE, "Default", "Cookies")
    
    if not os.path.exists(cookies_db):
        app.logger.error(f"Cookies database not found: {cookies_db}")
        return None
    
    # Copy database to avoid locking issues
    import shutil
    temp_db = "/tmp/cookies_temp.db"
    try:
        shutil.copy2(cookies_db, temp_db)
    except Exception as e:
        app.logger.error(f"Failed to copy cookies database: {e}")
        return None
    
    cookies = []
    try:
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Query cookies from Chromium database
        cursor.execute("""
            SELECT host_key, path, is_secure, expires_utc, name, value, encrypted_value
            FROM cookies
            WHERE host_key LIKE '%gog.com%'
        """)
        
        for row in cursor.fetchall():
            host, path, secure, expires, name, value, encrypted = row
            
            # Skip encrypted cookies for now (would need crypto key)
            if not value and encrypted:
                app.logger.warning(f"Skipping encrypted cookie: {name}")
                continue
            
            cookies.append({
                'domain': host,
                'path': path,
                'secure': bool(secure),
                'expires': expires,
                'name': name,
                'value': value
            })
        
        conn.close()
        os.remove(temp_db)
        
        app.logger.info(f"Extracted {len(cookies)} GOG cookies from Chromium")
        return cookies
        
    except Exception as e:
        app.logger.error(f"Failed to extract cookies: {e}")
        if os.path.exists(temp_db):
            os.remove(temp_db)
        return None

def save_cookies_lwp(cookies):
    """Save cookies in LWP format for gogrepo"""
    if not cookies:
        return False
    
    try:
        jar = cookiejar.LWPCookieJar(COOKIES)
        
        for cookie_data in cookies:
            # Convert Chromium timestamp (microseconds since 1601) to Unix timestamp
            expires = None
            if cookie_data['expires']:
                try:
                    # Chromium uses Windows epoch (1601-01-01)
                    # Convert to Unix epoch (1970-01-01)
                    chromium_epoch = 11644473600  # seconds between 1601 and 1970
                    expires = int(cookie_data['expires'] / 1000000 - chromium_epoch)
                except:
                    expires = None
            
            cookie = cookiejar.Cookie(
                version=0,
                name=cookie_data['name'],
                value=cookie_data['value'],
                port=None,
                port_specified=False,
                domain=cookie_data['domain'],
                domain_specified=True,
                domain_initial_dot=cookie_data['domain'].startswith('.'),
                path=cookie_data['path'],
                path_specified=True,
                secure=cookie_data['secure'],
                expires=expires,
                discard=False,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False
            )
            jar.set_cookie(cookie)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(COOKIES), exist_ok=True)
        
        # Save cookies
        jar.save(ignore_discard=True, ignore_expires=True)
        app.logger.info(f"Saved {len(jar)} cookies to {COOKIES}")
        
        return True
        
    except Exception as e:
        app.logger.error(f"Failed to save cookies: {e}")
        return False

# [Previous helper functions remain the same...]
# Copy all the helper functions from the original app.py
# (_now_ms, _is_fresh, _sha256, etc.)

def _now_ms() -> int:
    return int(time.time() * 1000)

def _is_fresh(path: str, ttl_ms: int) -> bool:
    try:
        st = os.stat(path)
        return (_now_ms() - int(st.st_mtime * 1000)) < ttl_ms
    except FileNotFoundError:
        return False
    except Exception:
        return False

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# ... [rest of helper functions from original app.py] ...

@app.route("/")
def index():
    """Main route - shows setup or GUI based on cookie status"""
    if not check_cookies_exist():
        # No cookies - show setup page
        return render_template("setup.html", vnc_port=VNC_PORT)
    else:
        # Cookies exist - show main GUI
        status = {
            "cookies": True,
            "manifest": os.path.exists(MANIFEST),
            "need_2fa": False,
            "login_token": None,
        }
        games = load_manifest_games()
        return render_template("index.html", status=status, games=games)

@app.route("/extract_cookies", methods=["POST"])
def extract_cookies_endpoint():
    """Extract cookies from Chromium and save"""
    app.logger.info("Cookie extraction requested")
    
    # Extract cookies from Chromium
    cookies = extract_chrome_cookies()
    
    if not cookies:
        return jsonify({
            'success': False,
            'message': 'No GOG cookies found. Please log in to gog.com first.'
        })
    
    # Save in LWP format
    if save_cookies_lwp(cookies):
        return jsonify({
            'success': True,
            'message': f'Successfully extracted {len(cookies)} cookies! Page will reload...'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to save cookies. Check logs for details.'
        })

# ... [Keep all other routes from original app.py] ...

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
