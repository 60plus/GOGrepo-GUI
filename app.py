from flask import Flask, render_template, jsonify, send_file, request, redirect, url_for, send_from_directory
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
from typing import Optional
from datetime import datetime
from pathlib import Path
import http.cookiejar

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['GOGREPO_DATA_DIR'] = os.environ.get('GOGREPO_DATA_DIR', '/app/data')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'change-me-in-production')
APP_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = app.config['GOGREPO_DATA_DIR']
os.makedirs(DATA_DIR, exist_ok=True)
GOGREPO = os.environ.get("GOGREPO_PATH", os.path.join(APP_DIR, "gogrepo.py"))
PY      = os.environ.get("PYTHON_BIN", "python3")
MANIFEST = os.path.join(DATA_DIR, "gog-manifest.dat")
COOKIES  = os.path.join(DATA_DIR, "gog-cookies.dat")
DOWNLOAD_DIR = os.environ.get("GOGREPO_DOWNLOAD_DIR", DATA_DIR)

# ... Job management, helpers, endpoints ...
def check_status():
    cookies_file = Path(COOKIES)
    return {
        'cookies': cookies_file.exists(),
        'manifest': os.path.exists(MANIFEST)
    }

@app.route('/')
def index():
    status = check_status()
    if not status['cookies']:
        return redirect(url_for('setup'))
    return render_template('index.html', status=status, games=[])

@app.route('/setup')
def setup():
    return render_template('setup.html')

@app.route('/api/save_cookies', methods=['POST'])
def save_cookies():
    try:
        import shutil
        import sqlite3
        chrome_profile = Path('/app/chrome-profile')
        cookies_db = chrome_profile / 'Default' / 'Cookies'
        if not cookies_db.exists():
            cookies_db = chrome_profile / 'Cookies'
        if not cookies_db.exists():
            return jsonify({'success': False, 'error': 'Cookies database not found in browser profile. Please log in to GOG.com first.'}), 400
        temp_db = Path('/tmp/temp_cookies.db')
        shutil.copy2(cookies_db, temp_db)
        try:
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            cursor.execute("SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly FROM cookies WHERE host_key LIKE '%gog.com%'")
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return jsonify({'success': False, 'error': 'No GOG cookies found. Please log in to GOG.com first.'}), 400
            cookies_file = Path(COOKIES)
            from http.cookiejar import MozillaCookieJar
            cookie_jar = MozillaCookieJar(str(cookies_file))
            for row in rows:
                name, value, domain, path, expires, secure, httponly = row
                expires_unix = None
                if expires:
                    unix_timestamp = (expires / 1000000) - 11644473600
                    if unix_timestamp > 0:
                        expires_unix = int(unix_timestamp)
                cookie = http.cookiejar.Cookie(
                    version=0,
                    name=name,
                    value=value,
                    port=None,
                    port_specified=False,
                    domain=domain,
                    domain_specified=True,
                    domain_initial_dot=domain.startswith('.'),
                    path=path,
                    path_specified=True,
                    secure=bool(secure),
                    expires=expires_unix,
                    discard=False,
                    comment=None,
                    comment_url=None,
                    rest={'HttpOnly': bool(httponly)},
                    rfc2109=False)
                cookie_jar.set_cookie(cookie)
            cookie_jar.save(ignore_discard=True, ignore_expires=True)
            return jsonify({'success': True, 'message': f'Successfully extracted {len(rows)} cookies and saved to gog-cookies.dat'})
        finally:
            if temp_db.exists():
                temp_db.unlink()
    except Exception as e:
        app.logger.exception(f"Failed to save cookies: {e}")
        return jsonify({'success': False, 'error': f'Cookie extraction failed: {str(e)}'}), 500

# Uwaga: pełen kod wszystkich endpointów do jobs/run_update, download_selected, download_all etc. (wzorowany na działającym commicie sprzed refaktoryzacji z af53f4b2d4375b4a4362e77187e94e013ce860e4 lub 06a7801d642e7febd28b41391d8363fdc76ca57a)
# ...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
