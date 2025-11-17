...(wszystko jak wcześniej)...
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
            from http.cookiejar import LWPCookieJar
            cookie_jar = LWPCookieJar(str(cookies_file))
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
            # Zapis do LWP (Set-Cookie3) — poprawny format dla gogrepo.py
            cookie_jar.save(ignore_discard=True, ignore_expires=True)
            return jsonify({'success': True, 'message': f'Successfully extracted {len(rows)} cookies and saved to gog-cookies.dat'})
        finally:
            if temp_db.exists():
                temp_db.unlink()
    except Exception as e:
        app.logger.exception(f"Failed to save cookies: {e}")
        return jsonify({'success': False, 'error': f'Cookie extraction failed: {str(e)}'}), 500
...(reszta kodu jak wcześniej)...
