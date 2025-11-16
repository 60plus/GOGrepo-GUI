from flask import Flask, render_template, jsonify, send_file, request
import os

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['GOGREPO_DATA_DIR'] = os.environ.get('GOGREPO_DATA_DIR', '/app/data')

@app.route('/')
def index():
    # Główna aplikacja GOGrepo-GUI (możesz podpiąć swoją stronę główną tutaj)
    return render_template('index.html')

@app.route('/setup')
def setup():
    return render_template('setup.html')

@app.route('/api/save_cookies', methods=['POST'])
def save_cookies():
    """Extract cookies from Chromium profile and save in gogrepo.py format"""
    try:
        import shutil
        import sqlite3
        import pickle
        import http.cookiejar
        from pathlib import Path
        
        # Paths
        chrome_profile = Path('/app/chrome-profile')
        cookies_db = chrome_profile / 'Default' / 'Cookies'
        
        # Try alternative path if Default doesn't exist
        if not cookies_db.exists():
            cookies_db = chrome_profile / 'Cookies'
        
        if not cookies_db.exists():
            return jsonify({
                'success': False,
                'error': 'Cookies database not found in browser profile. Please log in to GOG.com first.'
            }), 400
        
        # Copy database to avoid locking issues
        temp_db = Path('/tmp/temp_cookies.db')
        shutil.copy2(cookies_db, temp_db)
        
        try:
            # Connect to SQLite database
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.cursor()
            
            # Query GOG cookies
            cursor.execute(
                "SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly "
                "FROM cookies WHERE host_key LIKE '%gog.com%'"
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return jsonify({
                    'success': False,
                    'error': 'No GOG cookies found. Please log in to GOG.com first.'
                }), 400
            
            # Create cookie jar
            cookie_jar = http.cookiejar.LWPCookieJar()
            
            for row in rows:
                name, value, domain, path, expires, secure, httponly = row

                # Convert Chromium timestamp (microseconds since 1601) to Unix timestamp
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
                    rfc2109=False
                )
                cookie_jar.set_cookie(cookie)
            
            # Save as pickle file (gogrepo.py format)
            cookies_file = Path(app.config['GOGREPO_DATA_DIR']) / 'gog-cookies.dat'
            with open(cookies_file, 'wb') as f:
                pickle.dump(cookie_jar, f)
            
            return jsonify({
                'success': True,
                'message': f'Successfully extracted {len(rows)} cookies and saved to gog-cookies.dat'
            })
            
        finally:
            # Clean up temp database
            if temp_db.exists():
                temp_db.unlink()
    except Exception as e:
        app.logger.exception(f"Failed to save cookies: {e}")
        return jsonify({
            'success': False,
            'error': f'Cookie extraction failed: {str(e)}'
        }), 500

@app.route('/vnc/<path:path>')
def vnc_proxy(path):
    """Proxy noVNC static files"""
    import os
    novnc_path = '/usr/share/novnc'
    file_path = os.path.join(novnc_path, path)
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return "File not found", 404

# Dodaj tu swoje pozostałe endpointy GOGrepo-GUI jeśli masz!

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
