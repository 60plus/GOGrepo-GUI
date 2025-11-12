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

import pexpect
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, send_from_directory

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev")

APP_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("GOGREPO_DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)

GOGREPO = os.environ.get("GOGREPO_PATH", os.path.join(APP_DIR, "gogrepo.py"))
PY      = os.environ.get("PYTHON_BIN", "python3")

MANIFEST = os.path.join(DATA_DIR, "gog-manifest.dat")
COOKIES  = os.path.join(DATA_DIR, "gog-cookies.dat")

CACHE_DIR = os.path.join(DATA_DIR, "Cache")
DESC_DIR  = os.path.join(CACHE_DIR, "desc")
COVER_DIR = os.path.join(CACHE_DIR, "cover")
os.makedirs(DESC_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)

DAY_MS    = 24 * 60 * 60 * 1000
DESC_TTL  = 7 * DAY_MS
COVER_TTL = 30 * DAY_MS
PAGE_TTL  = 14 * DAY_MS

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

def _desc_cache_path(product_id: str, locale: str) -> str:
    key = _sha256(f"product:{product_id}|locale:{locale}")
    return os.path.join(DESC_DIR, f"{key}.json")

def _page_cache_path(title: str) -> str:
    key = _sha256(f"page:{title}")
    return os.path.join(DESC_DIR, f"page_{key}.json")

def _cover_cache_path_from_url(url: str) -> str:
    base_ext = ".bin"
    for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        if url.lower().split("?")[0].endswith(ext):
            base_ext = ext
            break
    key = _sha256(url.strip())
    return os.path.join(COVER_DIR, f"{key}{base_ext}")

def _cache_get_json(path: str, ttl_ms: int):
    if _is_fresh(path, ttl_ms):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def _cache_put_json(path: str, data) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass

def _cache_get_or_fetch_json(product_id: str, locale: str, fetcher):
    path = _desc_cache_path(product_id, locale)
    cached = _cache_get_json(path, DESC_TTL)
    if cached is not None:
        return cached
    data = fetcher()
    _cache_put_json(path, data)
    return data

def _cache_cover_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    path = _cover_cache_path_from_url(url)
    if _is_fresh(path, COVER_TTL):
        return path
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(r.content)
        os.replace(tmp, path)
        return path
    except Exception:
        if os.path.exists(path):
            return path
        return None

def _abs_url(u: str) -> str:
    if not u:
        return ""
    u = u.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return "https://www.gog.com" + u
    if not u.lower().startswith("http"):
        return "https://" + u
    return u

def _pick_from_dict(d: dict, keys: list[str]) -> str:
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return ""

def _extract_url_from_value(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return _pick_from_dict(v, ["image_url", "url", "href", "src", "original"]) or ""
    return ""

def _get_image_from_images(images) -> str:
    if isinstance(images, dict):
        for key in ["background", "background_2x", "boxArtImage", "logo2x", "vertical", "logo", "square", "icon"]:
            if key in images:
                url = _extract_url_from_value(images.get(key))
                if url:
                    return url
        url = _pick_from_dict(images, ["image_url", "url", "href", "src", "original"])
        if url:
            return url
        for v in images.values():
            url = _extract_url_from_value(v)
            if url:
                return url
    elif isinstance(images, list):
        for item in images:
            url = _extract_url_from_value(item)
            if url:
                return url
    return ""

def _format_date(date_str: str) -> str:
    """Convert various date formats to DD Month YYYY"""
    if not date_str:
        return ""
    try:
        if 'T' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%d %B %Y')
        if '-' in date_str and len(date_str) >= 10:
            dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
            return dt.strftime('%d %B %Y')
        if date_str.isdigit():
            dt = datetime.fromtimestamp(int(date_str))
            return dt.strftime('%d %B %Y')
    except Exception:
        pass
    return date_str

def _scrape_gog_page(title: str) -> Optional[dict]:
    """Scrape game details from GOG product page"""
    page_url = f"https://www.gog.com/en/game/{title}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(page_url, timeout=30, headers=headers)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        game_data = {
            'title': '',
            'description': '',
            'image': '',
            'rating': None,
            'release_date': '',
            'developer': '',
            'publisher': '',
            'languages': {'audio': [], 'text': [], 'subtitles': []},
            'systems': {'windows': False, 'linux': False, 'mac': False},
            'genre': []
        }
        
        lang_rows = soup.find_all('div', class_=re.compile('details__languages-row'))
        for row in lang_rows:
            lang_name_div = row.find('div', class_=re.compile('language-name'))
            if lang_name_div:
                lang_name = lang_name_div.get_text().strip()
                
                audio_div = row.find('div', class_=re.compile('audio-support'))
                if audio_div and audio_div.find('svg'):
                    game_data['languages']['audio'].append(lang_name)
                
                text_div = row.find('div', class_=re.compile('text-support'))
                if text_div and text_div.find('svg'):
                    game_data['languages']['text'].append(lang_name)
                
                sub_div = row.find('div', class_=re.compile('subtitle'))
                if sub_div and sub_div.find('svg'):
                    game_data['languages']['subtitles'].append(lang_name)
        
        detail_links = soup.find_all('a', class_=re.compile('details__link'))
        for link in detail_links:
            href = link.get('href', '')
            text = link.get_text().strip()
            
            if 'developers=' in href and not game_data['developer']:
                game_data['developer'] = text
            elif 'publishers=' in href and not game_data['publisher']:
                game_data['publisher'] = text
        
        os_section = soup.find('div', class_=re.compile('details__system|operating.*system|table__row.*system'))
        if os_section:
            os_text = os_section.get_text().lower()
            if 'windows' in os_text:
                game_data['systems']['windows'] = True
            if 'linux' in os_text or 'ubuntu' in os_text:
                game_data['systems']['linux'] = True
            if 'mac' in os_text or 'osx' in os_text:
                game_data['systems']['mac'] = True
        
        for script in soup.find_all('script'):
            if script.get('type') == 'application/ld+json':
                try:
                    json_data = json.loads(script.string)
                    
                    if not game_data['title']:
                        game_data['title'] = json_data.get('name', '')
                    if not game_data['description']:
                        game_data['description'] = json_data.get('description', '')
                    if not game_data['image']:
                        game_data['image'] = json_data.get('image', '')
                    if not game_data['release_date']:
                        game_data['release_date'] = json_data.get('datePublished', '')
                    
                    if not game_data['developer'] and 'author' in json_data:
                        if isinstance(json_data['author'], dict):
                            game_data['developer'] = json_data['author'].get('name', '')
                        elif isinstance(json_data['author'], list) and len(json_data['author']) > 0:
                            author = json_data['author'][0]
                            if isinstance(author, dict):
                                game_data['developer'] = author.get('name', '')
                    
                    if not game_data['rating'] and 'aggregateRating' in json_data:
                        rating_obj = json_data['aggregateRating']
                        if isinstance(rating_obj, dict):
                            rating_value = rating_obj.get('ratingValue')
                            rating_scale = rating_obj.get('bestRating', 5)
                            if rating_value is not None:
                                try:
                                    game_data['rating'] = (float(rating_value) / float(rating_scale)) * 100
                                except (ValueError, ZeroDivisionError):
                                    pass
                    
                    if 'genre' in json_data and not game_data['genre']:
                        if isinstance(json_data['genre'], list):
                            game_data['genre'] = json_data['genre']
                        else:
                            game_data['genre'] = [json_data['genre']]
                            
                except json.JSONDecodeError:
                    pass
        
        return game_data
            
    except Exception as e:
        app.logger.exception(f"Error scraping GOG page for {title}")
        return None
    
    return None

def _fetch_product_details_raw(product_id, locale="en-US"):
    url = f"https://api.gog.com/products/{product_id}"
    params = {"expand": "description,images", "locale": locale}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def fetch_product_details(product_id, locale="en-US"):
    return _cache_get_or_fetch_json(str(product_id), locale, lambda: _fetch_product_details_raw(product_id, locale))

def fetch_game_info_combined(product_id: str, title: str) -> dict:
    # Get full title from manifest first
    full_title = title
    manifest_data = None
    
    if title:
        manifest_data = _find_game_raw_by_title(title)
        if manifest_data:
            full_title = (manifest_data.get("long_title") or 
                         manifest_data.get("game_title") or 
                         manifest_data.get("name") or 
                         title)
    
    # Fallback: replace underscores with spaces and capitalize
    if '_' in full_title:
        full_title = full_title.replace('_', ' ').title()
    
    info = {
        'title': full_title,
        'description_html': '',
        'cover_url': '',
        'rating': None,
        'release_date': '',
        'developer': '',
        'publisher': '',
        'languages': {'audio': [], 'text': [], 'subtitles': []},
        'systems': {'windows': False, 'linux': False, 'mac': False}
    }
    
    if title:
        page_cache = _page_cache_path(title)
        cached_page = _cache_get_json(page_cache, PAGE_TTL)
        if cached_page:
            # Update title from cache but ensure it's the full one
            cached_page['title'] = full_title
            app.logger.info(f"Using cached page data for {title}")
            return {**info, **cached_page}
    
    scraped_data = None
    api_data = None
    
    if title:
        try:
            scraped_data = _scrape_gog_page(title)
            if scraped_data:
                app.logger.info(f"Scraped: {title}")
                # If scraped title is better (no underscores), use it
                if scraped_data.get('title') and '_' not in scraped_data['title']:
                    info['title'] = scraped_data['title']
        except Exception as e:
            app.logger.exception(f"Scraping failed: {title}")
    
    if product_id:
        try:
            api_data = fetch_product_details(product_id)
            app.logger.info(f"API fetched: {product_id}")
            # If API title is better, use it
            if api_data.get('title') and '_' not in api_data.get('title', ''):
                info['title'] = api_data['title']
        except Exception as e:
            app.logger.exception(f"API failed: {product_id}")
    
    cover_found = False
    
    if scraped_data and scraped_data.get('image'):
        cover_img = scraped_data['image']
        if cover_img:
            cover_abs = _abs_url(cover_img)
            if '_' in cover_abs and '.jpg' in cover_abs:
                cover_abs = re.sub(r'_\d+\.jpg', '_665.jpg', cover_abs)
            cached_path = _cache_cover_from_url(cover_abs)
            if cached_path:
                info['cover_url'] = url_for("serve_cover", name=os.path.basename(cached_path))
                cover_found = True
            else:
                info['cover_url'] = cover_abs
                cover_found = True
    
    if not cover_found and api_data:
        images = api_data.get("images", {}) or {}
        cover = _get_image_from_images(images) or _extract_url_from_value(api_data.get("image"))
        if cover:
            cover_abs = _abs_url(cover)
            cached_path = _cache_cover_from_url(cover_abs)
            if cached_path:
                info["cover_url"] = url_for("serve_cover", name=os.path.basename(cached_path))
                cover_found = True
            else:
                info["cover_url"] = cover_abs
                cover_found = True
    
    if not cover_found and manifest_data:
        cover = manifest_data.get("bg_url") or manifest_data.get("image_url") or manifest_data.get("image") or ""
        cover = _extract_url_from_value(cover)
        if cover:
            cover_abs = _abs_url(cover)
            cached_path = _cache_cover_from_url(cover_abs)
            if cached_path:
                info["cover_url"] = url_for("serve_cover", name=os.path.basename(cached_path))
            elif cover_abs:
                info["cover_url"] = cover_abs
    
    if api_data:
        desc_obj = api_data.get("description", {})
        desc = ""
        if isinstance(desc_obj, dict):
            desc = desc_obj.get("full") or desc_obj.get("lead") or ""
        if desc:
            info["description_html"] = desc
    
    if not info["description_html"] and scraped_data:
        desc = scraped_data.get('description', '')
        if desc:
            info["description_html"] = desc
    
    if scraped_data and scraped_data.get('rating') is not None:
        info["rating"] = scraped_data['rating']
    elif api_data and api_data.get("rating") is not None:
        info["rating"] = api_data["rating"]
    elif manifest_data and manifest_data.get("rating"):
        info["rating"] = manifest_data["rating"] * 2
    
    raw_date = None
    if scraped_data and scraped_data.get('release_date'):
        raw_date = scraped_data['release_date']
    elif api_data:
        raw_date = api_data.get("release_date") or api_data.get("releaseDate") or api_data.get("global_release_date")
    elif manifest_data and manifest_data.get("release_timestamp"):
        ts = manifest_data["release_timestamp"]
        if ts:
            raw_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
    
    if raw_date:
        info["release_date"] = _format_date(raw_date)
    
    if scraped_data and scraped_data.get('developer'):
        info["developer"] = scraped_data['developer']
    elif api_data:
        dev_data = api_data.get("developer") or api_data.get("developers")
        if isinstance(dev_data, dict):
            info["developer"] = dev_data.get("name", "")
        elif isinstance(dev_data, list) and len(dev_data) > 0:
            info["developer"] = dev_data[0] if isinstance(dev_data[0], str) else dev_data[0].get("name", "")
    
    if scraped_data and scraped_data.get('publisher'):
        info["publisher"] = scraped_data['publisher']
    elif api_data:
        pub_data = api_data.get("publisher") or api_data.get("publishers")
        if isinstance(pub_data, dict):
            info["publisher"] = pub_data.get("name", "")
        elif isinstance(pub_data, list) and len(pub_data) > 0:
            info["publisher"] = pub_data[0] if isinstance(pub_data[0], str) else pub_data[0].get("name", "")
    
    if not info["publisher"] and info["developer"]:
        info["publisher"] = info["developer"]
    
    all_audio = set()
    all_text = set()
    all_subs = set()
    
    if scraped_data and scraped_data.get('languages'):
        langs = scraped_data['languages']
        all_audio.update(langs.get('audio', []))
        all_text.update(langs.get('text', []))
        all_subs.update(langs.get('subtitles', []))
    
    if api_data:
        langs = api_data.get("languages") or {}
        if isinstance(langs, dict):
            all_audio.update(langs.get("audio", []))
            all_text.update(langs.get("text", []))
            all_subs.update(langs.get("subtitles", []))
    
    info["languages"]["audio"] = sorted(list(all_audio))
    info["languages"]["text"] = sorted(list(all_text))
    info["languages"]["subtitles"] = sorted(list(all_subs))
    
    if scraped_data and scraped_data.get('systems'):
        sys = scraped_data['systems']
        info["systems"]["windows"] = info["systems"]["windows"] or sys.get('windows', False)
        info["systems"]["linux"] = info["systems"]["linux"] or sys.get('linux', False)
        info["systems"]["mac"] = info["systems"]["mac"] or sys.get('mac', False)
    
    if api_data:
        systems = api_data.get("content_system_compatibility") or {}
        if isinstance(systems, dict):
            info["systems"]["windows"] = info["systems"]["windows"] or bool(systems.get("windows"))
            info["systems"]["linux"] = info["systems"]["linux"] or bool(systems.get("linux"))
            info["systems"]["mac"] = info["systems"]["mac"] or bool(systems.get("mac") or systems.get("osx"))
    
    if title:
        _cache_put_json(_page_cache_path(title), info)
    
    return info

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

def _extract_games_from_obj(data):
    if isinstance(data, dict):
        if isinstance(data.get("products"), dict):
            source = list(data["products"].values())
        elif "games" in data:
            source = list(data["games"].values()) if isinstance(data["games"], dict) else data["games"]
        else:
            source = [v for v in data.values() if isinstance(v, dict)]
    elif isinstance(data, list):
        source = data
    else:
        source = []
    out, seen = [], set()
    for g in source:
        if not isinstance(g, dict):
            continue
        slug = (g.get("title") or g.get("slug") or "").strip()
        nice = (g.get("long_title") or g.get("game_title") or g.get("name") or slug).strip()
        
        # Fallback: if still has underscores, replace them
        if '_' in nice and nice == slug:
            nice = nice.replace('_', ' ').title()
        
        pid  = g.get("product_id") or g.get("productId") or g.get("productid") or g.get("id")
        if slug and slug.lower() not in seen:
            seen.add(slug.lower())
            out.append({"title": slug, "long_title": nice, "product_id": pid})
    out.sort(key=lambda x: x["long_title"].lower())
    return out

def _load_manifest_raw():
    try:
        with open(MANIFEST, "rb") as f:
            return pickle.load(f)
    except Exception:
        pass
    try:
        with open(MANIFEST, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        pass
    try:
        with open(MANIFEST, "r", encoding="utf-8", errors="ignore") as f:
            return ast.literal_eval(f.read())
    except Exception:
        return None

def load_manifest_games():
    raw = _load_manifest_raw()
    return _extract_games_from_obj(raw) if raw is not None else []

def _find_game_raw_by_title(slug: str):
    data = _load_manifest_raw()
    if data is None:
        return None
    if isinstance(data, dict):
        if isinstance(data.get("products"), dict):
            items = list(data["products"].values())
        elif "games" in data:
            items = list(data["games"].values()) if isinstance(data["games"], dict) else data["games"]
        else:
            items = [v for v in data.values() if isinstance(v, dict)]
    elif isinstance(data, list):
        items = data
    else:
        items = []
    for g in items:
        if isinstance(g, dict) and (g.get("title") or "").strip() == slug:
            return g
    return None

login_children = {}

@app.route("/")
def index():
    status = {
        "cookies": os.path.exists(COOKIES),
        "manifest": os.path.exists(MANIFEST),
        "need_2fa": session.pop("need_2fa", False),
        "login_token": session.get("login_token"),
    }
    games = load_manifest_games()
    return render_template("index.html", status=status, games=games)

@app.route("/login", methods=["POST"])
def login():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    otp      = (request.form.get("otp") or "").strip()
    token    = (request.form.get("login_token") or "").strip()

    if token:
        child = login_children.get(token)
        if not child:
            flash("Login session expired — start again.", "error")
            return redirect(url_for("index"))
        try:
            child.sendline(otp)
            child.expect(pexpect.EOF, timeout=240)
            flash(child.before, "info")
        except Exception as e:
            flash(f"2FA login error: {e}", "error")
        finally:
            try:
                child.close(force=True)
            except Exception:
                pass
            login_children.pop(token, None)
            session.pop("login_token", None)
        return redirect(url_for("index"))

    cmd = f"{shlex.quote(PY)} {shlex.quote(GOGREPO)} login"
    try:
        child = pexpect.spawn(cmd, cwd=DATA_DIR, encoding="utf-8", timeout=300)
        child.expect(["[Uu]sername", "enter username", "Enter username"], timeout=120)
        child.sendline(username)
        child.expect(["[Pp]assword", "enter password", "Enter password"], timeout=120)
        child.sendline(password)
        idx = child.expect([
            "Enter the code from your authenticator",
            "Enter the security code",
            "Enter the code sent to your email",
            "2FA code",
            "Two-Factor Code",
            pexpect.EOF
        ], timeout=240)

        if idx == 5:
            flash(child.before, "info")
            try:
                child.close(force=True)
            except Exception:
                pass
            return redirect(url_for("index"))

        token = str(uuid.uuid4())
        login_children[token] = child
        session["need_2fa"] = True
        session["login_token"] = token
        flash("Enter 2FA code from email/app — login process is waiting for your code.", "info")
        return redirect(url_for("index"))
    except pexpect.TIMEOUT:
        flash("Timeout during login", "error")
    except Exception as e:
        flash(f"Login error: {e}", "error")
    return redirect(url_for("index"))

@app.route("/run_update", methods=["POST"])
def run_update():
    os_list = [v for v in request.form.getlist("os") if v.strip()]
    langs   = [v for v in (request.form.get("langs") or "").strip().split() if v.strip()]
    args = [PY, GOGREPO, "update"]
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

@app.route("/job_status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "unknown", "output": "", "rc": None})
    with job.lock:
        return jsonify({"status": job.status, "output": job.output, "rc": job.rc})

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
    try:
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
    except Exception as e:
        app.logger.exception("download_selected failed")
        return jsonify({"error": str(e)}), 500

@app.route("/download_all", methods=["POST"])
def download_all():
    try:
        args = [PY, GOGREPO, "download"]
        if request.form.get("skipextras"):
            args.append("-skipextras")
        if request.form.get("skipgames"):
            args.append("-skipgames")
        job_id = start_job(args, cwd=DATA_DIR)
        return jsonify({"job_id": job_id})
    except Exception as e:
        app.logger.exception("download_all failed")
        return jsonify({"error": str(e)}), 500

@app.route("/cache/cover/<path:name>")
def serve_cover(name: str):
    return send_from_directory(COVER_DIR, name)

@app.route("/game_info")
def game_info():
    pid   = (request.args.get("product_id") or "").strip()
    title = (request.args.get("title") or "").strip()
    info = fetch_game_info_combined(pid, title)
    return jsonify(info)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
