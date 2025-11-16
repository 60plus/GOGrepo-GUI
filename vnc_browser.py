#!/usr/bin/env python3
"""
VNC Browser Manager for GOG Login
Handles Chromium browser sessions in VNC for interactive login
and cookie extraction for gogrepo.py
"""

import os
import json
import time
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
import threading
import logging

logger = logging.getLogger(__name__)

class VNCBrowserManager:
    def __init__(self, data_dir: str = "/app/data", profile_dir: str = "/app/vnc_profiles"):
        self.data_dir = Path(data_dir)
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        self.cookies_file = self.data_dir / "gog-cookies.dat"
        self.browser_process: Optional[subprocess.Popen] = None
        self.current_profile = self.profile_dir / "gog_session"
        self.lock = threading.Lock()
        
    def is_browser_running(self) -> bool:
        """Check if browser process is running"""
        with self.lock:
            if self.browser_process is None:
                return False
            return self.browser_process.poll() is None
    
    def start_browser(self, url: str = "https://www.gog.com/") -> bool:
        """Start Chromium browser in VNC session"""
        try:
            with self.lock:
                if self.is_browser_running():
                    logger.info("Browser already running")
                    return True
                
                # Create fresh profile directory
                if self.current_profile.exists():
                    shutil.rmtree(self.current_profile)
                self.current_profile.mkdir(parents=True, exist_ok=True)
                
                # Chromium arguments for VNC session
                args = [
                    "chromium",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1200,900",
                    f"--user-data-dir={self.current_profile}",
                    "--disable-features=TranslateUI",
                    "--disable-infobars",
                    "--no-first-run",
                    "--no-default-browser-check",
                    url
                ]
                
                env = os.environ.copy()
                env["DISPLAY"] = ":99"
                
                self.browser_process = subprocess.Popen(
                    args,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                logger.info(f"Browser started with PID {self.browser_process.pid}")
                time.sleep(2)  # Give browser time to start
                return True
                
        except Exception as e:
            logger.exception(f"Failed to start browser: {e}")
            return False
    
    def stop_browser(self) -> bool:
        """Stop the browser process"""
        try:
            with self.lock:
                if self.browser_process is None:
                    return True
                
                if self.browser_process.poll() is None:
                    self.browser_process.terminate()
                    try:
                        self.browser_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.browser_process.kill()
                        self.browser_process.wait(timeout=5)
                
                self.browser_process = None
                logger.info("Browser stopped")
                return True
                
        except Exception as e:
            logger.exception(f"Failed to stop browser: {e}")
            return False
    
    def extract_cookies(self) -> Dict:
        """Extract cookies from Chromium profile and save in gogrepo.py format"""
        try:
            # Path to Chromium cookies database
            cookies_db = self.current_profile / "Default" / "Cookies"
            
            if not cookies_db.exists():
                # Try alternative path
                cookies_db = self.current_profile / "Cookies"
                
            if not cookies_db.exists():
                return {
                    "success": False,
                    "error": "Cookies database not found in browser profile"
                }
            
            # Copy database to avoid locking issues
            temp_db = self.data_dir / "temp_cookies.db"
            shutil.copy2(cookies_db, temp_db)
            
            try:
                # Connect to SQLite database
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                
                # Query GOG cookies
                cursor.execute(
                    "SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly "
                    "FROM cookies WHERE host_key LIKE '%gog.com%'"
                )
                
                gog_cookies = []
                for row in cursor.fetchall():
                    name, value, domain, path, expires, secure, httponly = row
                    gog_cookies.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": path,
                        "expires": expires,
                        "secure": bool(secure),
                        "httponly": bool(httponly)
                    })
                
                conn.close()
                
                if not gog_cookies:
                    return {
                        "success": False,
                        "error": "No GOG cookies found. Please log in to GOG.com first."
                    }
                
                # Save cookies in gogrepo.py compatible format
                self._save_cookies_for_gogrepo(gog_cookies)
                
                return {
                    "success": True,
                    "cookies_count": len(gog_cookies),
                    "message": f"Successfully extracted {len(gog_cookies)} cookies"
                }
                
            finally:
                # Clean up temp database
                if temp_db.exists():
                    temp_db.unlink()
                    
        except Exception as e:
            logger.exception(f"Failed to extract cookies: {e}")
            return {
                "success": False,
                "error": f"Cookie extraction failed: {str(e)}"
            }
    
    def _save_cookies_for_gogrepo(self, cookies: List[Dict]):
        """Save cookies in format compatible with gogrepo.py"""
        import http.cookiejar
        import pickle
        
        # Create cookie jar
        cookie_jar = http.cookiejar.LWPCookieJar()
        
        for cookie_data in cookies:
            # Convert Chromium timestamp (microseconds since 1601) to Unix timestamp
            expires = None
            if cookie_data.get("expires"):
                chromium_epoch = cookie_data["expires"]
                # Chromium uses Windows epoch (1601-01-01), convert to Unix epoch
                unix_timestamp = (chromium_epoch / 1000000) - 11644473600
                if unix_timestamp > 0:
                    expires = int(unix_timestamp)
            
            cookie = http.cookiejar.Cookie(
                version=0,
                name=cookie_data["name"],
                value=cookie_data["value"],
                port=None,
                port_specified=False,
                domain=cookie_data["domain"],
                domain_specified=True,
                domain_initial_dot=cookie_data["domain"].startswith("."),
                path=cookie_data["path"],
                path_specified=True,
                secure=cookie_data["secure"],
                expires=expires,
                discard=False,
                comment=None,
                comment_url=None,
                rest={"HttpOnly": cookie_data.get("httponly", False)},
                rfc2109=False
            )
            cookie_jar.set_cookie(cookie)
        
        # Save as pickle file (gogrepo.py format)
        with open(self.cookies_file, "wb") as f:
            pickle.dump(cookie_jar, f)
        
        logger.info(f"Cookies saved to {self.cookies_file}")
    
    def get_status(self) -> Dict:
        """Get current browser and cookies status"""
        return {
            "browser_running": self.is_browser_running(),
            "cookies_exist": self.cookies_file.exists(),
            "profile_exists": self.current_profile.exists()
        }

# Global instance
_browser_manager: Optional[VNCBrowserManager] = None

def get_browser_manager() -> VNCBrowserManager:
    """Get or create browser manager instance"""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = VNCBrowserManager()
    return _browser_manager