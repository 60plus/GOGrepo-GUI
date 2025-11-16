# --- FULL FLASK APP.PY RESTORE ---
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

# ---- Job management and core logic ----
class Job:
    def __init__(self):
        self.status = "running"
        self.output = ""
        self.rc: Optional[int] = None
        self.lock = threading.Lock()
        self.proc: Optional[subprocess.Popen] = None
    def append(self, text: str):
        with self.lock:
            self.output += text
    def finish(self, rc: int, status: Optional[str] = None):
        with self.lock:
            self.rc = rc
            self.status = status if status else ("finished" if rc == 0 else "error")
jobs = {}
_current_job_id = None
_current_job_lock = threading.Lock()
def _run_stream(job_id, args, cwd=None):
    global _current_job_id
    job = jobs[job_id]
    try:
        job.append("$ " + " ".join(shlex.quote(a) for a in args) + "\n")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)
        job.proc = proc
        for line in proc.stdout:
            job.append(line)
        rc = proc.wait()
        if job.status == "running":
            job.finish(rc)
    except Exception as e:
        job.append(f"\n[ERROR] {e}\n{traceback.format_exc()}\n")
        job.finish(1)
    finally:
        with _current_job_lock:
            if _current_job_id == job_id:
                _current_job_id = None
def start_job(args, cwd=None) -> str:
    global _current_job_id
    job_id = str(uuid.uuid4())
    jobs[job_id] = Job()
    with _current_job_lock:
        _current_job_id = job_id
    t = threading.Thread(target=_run_stream, args=(job_id, args, cwd), daemon=True)
    t.start()
    return job_id
def cancel_job(job_id: Optional[str]) -> tuple[bool, str]:
    job = jobs.get(job_id or "")
    if not job or job.status != "running" or not job.proc:
        return False, "No running job"
    try:
        job.append("\n[INFO] Cancel requested, terminating process...\n")
        job.proc.terminate()
        try:
            job.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            job.append("[INFO] Process did not terminate, killing...\n")
            job.proc.kill()
            job.proc.wait(timeout=5)
        job.finish(-9, status="canceled")
        return True, "Canceled"
    except Exception as e:
        job.append(f"[ERROR] Cancel failed: {e}\n")
        return False, str(e)
# ---- Helper: Game download status ----
def normalize_game_folder_name(title: str) -> str:
    if not title:
        return ""
    normalized = title.lower().strip()
    normalized = re.sub(r'[:\'\'"!?.,™®©]', '', normalized)
    normalized = re.sub(r'[\s\-_]+', '_', normalized)
    normalized = normalized.strip('_')
    return normalized
def is_game_downloaded(title: str) -> bool:
    if not title:
        return False
    folder_name = normalize_game_folder_name(title)
    if not folder_name:
        return False
    game_path = os.path.join(DOWNLOAD_DIR, folder_name)
    return os.path.isdir(game_path)
# ---- ROUTES ----
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
    # Normally pass games list here for UI if needed...
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
            cookie_jar = http.cookiejar.LWPCookieJar(str(cookies_file))
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
@app.route("/run_update", methods=["POST"])
def run_update():
    args = [PY, GOGREPO, "update"]
    os_list = [v for v in request.form.getlist("os") if v.strip()]
    langs   = [v for v in (request.form.get("langs") or "").strip().split() if v.strip()]
    if os_list:
        args += ["-os"] + os_list
    if langs:
        args += ["-lang"] + langs
    if request.form.get("skipknown"):
        args.append("-skipknown")
    if request.form.get("updateonly"):
        args.append("-updateonly")
    job_id = start_job(args, cwd=DATA_DIR)
    return jsonify({"job_id": job_id})
@app.route("/current_job")
def current_job():
    with _current_job_lock:
        jid = _current_job_id
    if not jid:
        for k, j in jobs.items():
            with j.lock:
                if j.status == "running":
                    jid = k
                    break
    if not jid or jid not in jobs:
        return jsonify({"job_id": None, "status": "idle", "output": "", "rc": None})
    j = jobs[jid]
    with j.lock:
        return jsonify({"job_id": jid, "status": j.status, "output": j.output, "rc": j.rc})
@app.route("/job_status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "unknown", "output": "", "rc": None})
    with job.lock:
        return jsonify({"status": job.status, "output": job.output, "rc": job.rc})
@app.route("/cancel_job", methods=["POST"])
def cancel_job_endpoint():
    job_id = (request.form.get("job_id") or None)
    if not job_id:
        with _current_job_lock:
            job_id = _current_job_id
    ok, msg = cancel_job(job_id)
    return jsonify({"ok": ok, "message": msg, "job_id": job_id})
@app.route("/download_selected", methods=["POST"])
def download_selected():
    title = (request.form.get("selected_title") or "").strip()
    if not title:
        return jsonify({"error": "Select a game from the list"}), 400
    args = [PY, GOGREPO, "download", "-id", title]
    if request.form.get("skipextras"):
        args.append("-skipextras")
    if request.form.get("skipgames"):
        args.append("-skipgames")
    job_id = start_job(args, cwd=DATA_DIR)
    return jsonify({"job_id": job_id})
@app.route("/download_all", methods=["POST"])
def download_all():
    args = [PY, GOGREPO, "download"]
    if request.form.get("skipextras"):
        args.append("-skipextras")
    if request.form.get("skipgames"):
        args.append("-skipgames")
    job_id = start_job(args, cwd=DATA_DIR)
    return jsonify({"job_id": job_id})
@app.route("/game_info")
def game_info():
    title = (request.args.get("title") or "").strip()
    return jsonify({
        "title": title.replace('_', ' ').title() if title else "Unknown",
        "description_html": "<p>No description available.</p>",
        "cover_url": "",
        "rating": None,
        "release_date": "",
        "developer": "N/A",
        "publisher": "N/A",
        "languages": {"audio": [], "text": [], "subtitles": []},
        "systems": {"windows": False, "linux": False, "mac": False}
    })
@app.route('/vnc/')
@app.route('/vnc/<path:path>')
def vnc_proxy(path=''):
    if not path:
        return redirect('http://{}:6080/vnc.html'.format(request.host.split(':')[0]))
    novnc_path = '/usr/share/novnc'
    file_path = path.split('?')[0]
    full_path = os.path.join(novnc_path, file_path)
    if os.path.exists(full_path):
        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        return send_from_directory(directory, filename)
    else:
        return "File not found", 404
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
