#!/usr/bin/env python3
"""
Cookie Extractor Web Interface
Provides a simple web page with a button to extract cookies from Chromium profile
"""

import os
import sys
import sqlite3
import logging
import http.cookiejar as cookiejar
from flask import Flask, render_template_string, jsonify
from pathlib import Path

app = Flask(__name__)

# Configuration
DATA_DIR = os.environ.get("GOGREPO_DATA_DIR", "/app/data")
COOKIES_FILE = os.path.join(DATA_DIR, "gog-cookies.dat")
CHROME_PROFILE = os.environ.get("CHROME_PROFILE", "/tmp/chrome-profile")
COMPLETION_FLAG = "/tmp/cookies_extracted"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Simple HTML template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>GOG Cookie Extractor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 500px;
            width: 100%;
            text-align: center;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 16px;
        }
        
        .instructions {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin-bottom: 30px;
            text-align: left;
            border-radius: 5px;
        }
        
        .instructions ol {
            margin-left: 20px;
            color: #555;
        }
        
        .instructions li {
            margin: 8px 0;
            line-height: 1.6;
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            font-size: 18px;
            font-weight: bold;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.6);
        }
        
        button:active:not(:disabled) {
            transform: translateY(0);
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            font-weight: bold;
            display: none;
        }
        
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
            display: block;
        }
        
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
            display: block;
        }
        
        .status.info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
            display: block;
        }
        
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
            display: none;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .icon {
            font-size: 60px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🍪</div>
        <h1>GOG Cookie Extractor</h1>
        <p class="subtitle">Extract cookies after logging into GOG</p>
        
        <div class="instructions">
            <strong>Instructions:</strong>
            <ol>
                <li>Open <strong>Chromium</strong> via noVNC (port 6080)</li>
                <li>Navigate to <strong>gog.com</strong> and log in</li>
                <li>Complete <strong>2FA</strong> and <strong>captcha</strong> if prompted</li>
                <li>Return here and click the button below</li>
            </ol>
        </div>
        
        <button id="extractBtn" onclick="extractCookies()">Extract Cookies</button>
        <div class="spinner" id="spinner"></div>
        <div class="status" id="status"></div>
    </div>
    
    <script>
        async function extractCookies() {
            const btn = document.getElementById('extractBtn');
            const status = document.getElementById('status');
            const spinner = document.getElementById('spinner');
            
            btn.disabled = true;
            status.style.display = 'none';
            spinner.style.display = 'block';
            
            try {
                const response = await fetch('/extract', { method: 'POST' });
                const data = await response.json();
                
                spinner.style.display = 'none';
                
                if (data.success) {
                    status.className = 'status success';
                    status.innerHTML = '✓ ' + data.message + '<br><br>GOGrepo GUI will start automatically in a few seconds...';
                    setTimeout(() => {
                        window.location.href = 'http://localhost:8080';
                    }, 3000);
                } else {
                    status.className = 'status error';
                    status.innerHTML = '✗ ' + data.message;
                    btn.disabled = false;
                }
            } catch (error) {
                spinner.style.display = 'none';
                status.className = 'status error';
                status.innerHTML = '✗ Error: ' + error.message;
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
'''

def extract_chrome_cookies():
    """Extract cookies from Chromium SQLite database"""
    cookies_db = os.path.join(CHROME_PROFILE, "Default", "Cookies")
    
    if not os.path.exists(cookies_db):
        logger.error(f"Cookies database not found: {cookies_db}")
        return None
    
    # Copy database to avoid locking issues
    import shutil
    temp_db = "/tmp/cookies_temp.db"
    try:
        shutil.copy2(cookies_db, temp_db)
    except Exception as e:
        logger.error(f"Failed to copy cookies database: {e}")
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
                logger.warning(f"Skipping encrypted cookie: {name}")
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
        
        logger.info(f"Extracted {len(cookies)} GOG cookies from Chromium")
        return cookies
        
    except Exception as e:
        logger.error(f"Failed to extract cookies: {e}")
        if os.path.exists(temp_db):
            os.remove(temp_db)
        return None

def save_cookies_lwp(cookies):
    """Save cookies in LWP format for gogrepo"""
    if not cookies:
        return False
    
    try:
        jar = cookiejar.LWPCookieJar(COOKIES_FILE)
        
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
        os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
        
        # Save cookies
        jar.save(ignore_discard=True, ignore_expires=True)
        logger.info(f"Saved {len(jar)} cookies to {COOKIES_FILE}")
        
        # Create completion flag
        Path(COMPLETION_FLAG).touch()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to save cookies: {e}")
        return False

@app.route('/')
def index():
    """Serve the main page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/extract', methods=['POST'])
def extract():
    """Extract cookies endpoint"""
    logger.info("Cookie extraction requested")
    
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
            'message': f'Successfully extracted {len(cookies)} cookies!'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to save cookies. Check logs for details.'
        })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    logger.info("Starting Cookie Extractor Web Interface...")
    logger.info(f"Chrome profile: {CHROME_PROFILE}")
    logger.info(f"Cookies will be saved to: {COOKIES_FILE}")
    logger.info("Access the interface at http://localhost:3000")
    
    app.run(host='0.0.0.0', port=3000, debug=False)
