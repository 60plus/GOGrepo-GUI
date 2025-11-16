from flask import Flask, render_template, jsonify, send_file, request, redirect, url_for
import os
from pathlib import Path

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['GOGREPO_DATA_DIR'] = os.environ.get('GOGREPO_DATA_DIR', '/app/data')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'change-me-in-production')

def check_status():
    """Check if cookies exist"""
    cookies_file = Path(app.config['GOGREPO_DATA_DIR']) / 'gog-cookies.dat'
    return {
        'cookies': cookies_file.exists()
    }

@app.route('/')
def index():
    """Main application page - redirect to setup if no cookies"""
    status = check_status()
    
    if not status['cookies']:
        return redirect(url_for('setup'))
    
    # If cookies exist, render main app
    return render_template('index.html', status=status)

@app.route('/setup')
def setup():
    """Setup page for cookie extraction"""
    return render_template('setup.html')

@app.route('/api/save_cookies', methods=['POST'])
def save_cookies():
    """Extract cookies from Chromium profile and save in gogrepo.py format"""
    try:
        import shutil
        import sqlite3
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
            
            # Save as text file - fix pickling error
            cookies_file = Path(app.config['GOGREPO_DATA_DIR']) / 'gog-cookies.dat'
            cookie_jar.save(str(cookies_file), ignore_discard=True, ignore_expires=True)
            
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

@app.route('/vnc/')
@app.route('/vnc/<path:path>')
def vnc_proxy(path=''):
    """Proxy noVNC static files - redirect root requests to actual noVNC on port 6080"""
    import os
    from flask import send_from_directory
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
