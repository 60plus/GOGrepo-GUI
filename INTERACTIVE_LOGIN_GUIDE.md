# Interactive Browser Login Guide

## Overview

GOGrepo GUI features an **interactive browser login** system that makes authentication simple and secure:

- **No credentials needed** - You log in manually through a real browser
- **Full 2FA support** - Complete any 2FA challenge (email, authenticator app)
- **Captcha handling** - Solve captchas as you normally would
- **One-click extraction** - Cookies are automatically saved for future use
- **Seamless transition** - GUI starts immediately after login

## How It Works

```
┌─────────────────────────────────────────────┐
│  Container Starts                           │
└──────────────┬──────────────────────────────┘
               │
               ▼
      ┌────────────────┐
      │ Cookies exist? │
      └────┬───────┬───┘
           │       │
        YES│       │NO
           │       │
           │       ▼
           │  ┌──────────────────────┐
           │  │ Start Interactive    │
           │  │ Login Environment:   │
           │  │ • Chromium Browser   │
           │  │ • noVNC (port 6080)  │
           │  │ • Extractor (3000)   │
           │  └──────────┬───────────┘
           │             │
           │             ▼
           │  ┌──────────────────────┐
           │  │ You manually:        │
           │  │ 1. Log in to GOG     │
           │  │ 2. Complete 2FA      │
           │  │ 3. Solve captcha     │
           │  │ 4. Click 'Extract'   │
           │  └──────────┬───────────┘
           │             │
           │             ▼
           │  ┌──────────────────────┐
           │  │ Cookies Saved        │
           │  │ Browser Closed       │
           │  └──────────┬───────────┘
           │             │
           └─────────────┴───────────┐
                         │
                         ▼
              ┌──────────────────────┐
              │ GOGrepo GUI Starts   │
              │ (port 8080)          │
              └──────────────────────┘
```

## Quick Start

### 1. Clone and Build

```bash
# Clone the repository
git clone -b feature/interactive-browser-login https://github.com/60plus/GOGrepo-GUI.git
cd GOGrepo-GUI

# Build and start
docker-compose up --build
```

### 2. First Time Login

When the container starts for the first time (no cookies):

```
===============================================
  GOGrepo GUI - Interactive Login
===============================================

✗ No cookies file found
✓ Starting interactive login process...

✓ VNC server started
  Access at: http://localhost:6080

✓ Chromium started
  Profile: /tmp/chrome-profile

✓ Cookie Extractor started
  Access at: http://localhost:3000

===============================================
  Waiting for Cookie Extraction
===============================================

Please complete the following steps:

1. Open noVNC: http://localhost:6080
2. Log in to your GOG account
3. After successful login, open: http://localhost:3000
4. Click 'Extract Cookies' button
```

### 3. Access the Browser

Open in your browser:
**http://localhost:6080**

You'll see:
- Chromium browser running
- GOG.com already loaded
- Full keyboard and mouse control

### 4. Log In to GOG

In the noVNC window:
1. **Enter your GOG email and password**
2. **Complete 2FA if prompted** (email code or authenticator app)
3. **Solve captcha if shown**
4. **Verify you're logged in** (see your username in top-right)

### 5. Extract Cookies

In a new browser tab, open:
**http://localhost:3000**

You'll see a beautiful interface:
- 🍪 **GOG Cookie Extractor** header
- **Instructions** (which you just completed!)
- **Extract Cookies** button

**Click the button!**

You'll see:
```
✓ Successfully extracted X cookies!

GOGrepo GUI will start automatically in a few seconds...
```

### 6. Use GOGrepo GUI

After cookie extraction:
- Browser automatically closes
- GOGrepo GUI starts
- Redirects to **http://localhost:8080**
- You can now update manifest and download games!

## Subsequent Starts

Once cookies are saved, future container starts are instant:

```bash
docker-compose up
```

```
===============================================
  GOGrepo GUI - Interactive Login
===============================================

✓ Found existing cookies file
✓ Valid cookies found
✓ Skipping interactive login

===============================================
  Starting GOGrepo GUI
===============================================

GUI will be available at: http://localhost:8080
```

**No browser, no login, instant access!**

## Ports

| Port | Service | When Active | Purpose |
|------|---------|-------------|----------|
| **8080** | GOGrepo GUI | Always (after cookies) | Main application interface |
| **6080** | noVNC | During login only | Remote browser access |
| **3000** | Cookie Extractor | During login only | Extract cookies button |

## Directory Structure

```
GOGrepo-GUI/
├── data/                    # Persistent data (mounted volume)
│   ├── gog-cookies.dat     # Saved cookies (LWP format)
│   ├── gog-manifest.dat    # Game manifest
│   └── [downloaded games]  # Your GOG games
├── app.py                   # Main Flask GUI
├── cookie_extractor.py      # Cookie extraction web interface
├── gogrepo.py              # GOG repository tool
├── entrypoint.sh           # Container startup logic
├── Dockerfile              # Container definition
└── docker-compose.yml      # Service configuration
```

## Cookie Extraction Details

### How It Works

1. **Chromium Profile**: Browser uses `/tmp/chrome-profile` for session data
2. **SQLite Database**: Cookies stored in `Cookies` SQLite file
3. **Extraction**: Python script reads SQLite and filters GOG.com cookies
4. **Conversion**: Chromium cookie format → LWP format (for gogrepo.py)
5. **Saving**: Cookies written to `/app/data/gog-cookies.dat`

### What's Extracted

- All cookies from `*.gog.com` domains
- Session cookies and persistent cookies
- Secure and non-secure cookies
- All cookie attributes (domain, path, expiry, etc.)

### Cookie Lifetime

GOG cookies typically last:
- **Session cookies**: Until browser closes
- **Persistent cookies**: Several weeks to months
- **After extraction**: Cookies persist indefinitely (until expired)

## Troubleshooting

### Issue: "Cannot access noVNC at localhost:6080"

**Solution:**
```bash
# Check if container is running
docker ps

# Check logs
docker-compose logs

# Ensure port isn't in use
lsof -i :6080  # Linux/Mac
netstat -ano | findstr :6080  # Windows
```

### Issue: "Chromium shows blank screen in noVNC"

**Solution:**
```bash
# Restart container
docker-compose restart

# Check Xvfb is running
docker exec gogrepo-gui ps aux | grep Xvfb

# Check display
docker exec gogrepo-gui echo $DISPLAY
# Should show: :99
```

### Issue: "Extract Cookies button doesn't work"

**Solution:**
1. **Ensure you're logged in to GOG** - Check browser shows your username
2. **Check browser console** - Press F12 in extractor page
3. **View logs**:
   ```bash
   docker-compose logs -f
   ```
4. **Manually check cookies**:
   ```bash
   docker exec gogrepo-gui ls -lh /tmp/chrome-profile/Default/Cookies
   ```

### Issue: "No GOG cookies found"

**Cause**: You didn't complete login or browser profile is empty

**Solution:**
1. Go back to noVNC (http://localhost:6080)
2. Verify you're on gog.com
3. Log in completely
4. Try extracting again

### Issue: "GUI doesn't start after extraction"

**Solution:**
```bash
# Check if cookies file was created
docker exec gogrepo-gui ls -lh /app/data/gog-cookies.dat

# Check entrypoint logs
docker-compose logs | grep -A 10 "Cookie extraction"

# Manually start GUI (debug)
docker exec -it gogrepo-gui python3 /app/app.py
```

### Issue: "Cookies expired"

**Symptom**: GUI shows "not logged in" or downloads fail

**Solution:**
```bash
# Delete old cookies
docker exec gogrepo-gui rm /app/data/gog-cookies.dat

# Restart container (will trigger interactive login)
docker-compose restart

# Follow login steps again
```

## Advanced Usage

### Manual Cookie Extraction

If automatic extraction fails:

```bash
# Enter container
docker exec -it gogrepo-gui bash

# Run extraction script
python3 /app/cookie_extractor.py &

# In another terminal, trigger extraction
curl -X POST http://localhost:3000/extract
```

### Keep noVNC Running

By default, noVNC stays running for debugging. To access it:

```bash
# Even after GUI starts, noVNC is available
open http://localhost:6080
```

### Export Cookies Manually

```bash
# View cookies in SQLite
docker exec -it gogrepo-gui sqlite3 /tmp/chrome-profile/Default/Cookies \
  "SELECT host_key, name, value FROM cookies WHERE host_key LIKE '%gog.com%'"
```

### Remote Access

For headless servers:

```bash
# SSH tunnel for noVNC
ssh -L 6080:localhost:6080 user@remote-server

# Access locally
open http://localhost:6080
```

## Security Notes

### 🔒 Cookie Security

- **Cookies = Your Session**: Treat them like passwords
- **File Permissions**: Ensure `data/` directory is protected
- **No Sharing**: Never share `gog-cookies.dat` file
- **Container Only**: Cookies only accessible inside container

### 🔒 Network Security

- **Local Only**: Ports should not be exposed to internet
- **Firewall**: Block 6080 and 3000 from external access
- **VPN**: Use VPN if accessing remotely

### 🔒 Best Practices

```bash
# Set proper permissions
chmod 700 ./data
chmod 600 ./data/gog-cookies.dat

# Use firewall
sudo ufw allow 8080/tcp  # GUI only
sudo ufw deny 6080/tcp   # Block noVNC
sudo ufw deny 3000/tcp   # Block extractor
```

## FAQ

**Q: Do I need to log in every time?**

A: No! Once cookies are extracted, container starts directly with GUI. Re-login only when cookies expire (weeks/months).

**Q: Can I use this on a headless server?**

A: Yes! Use SSH tunneling to access noVNC remotely:
```bash
ssh -L 6080:localhost:6080 user@server
```

**Q: What if I have 2FA enabled?**

A: Perfect! Interactive login supports all 2FA methods (email, authenticator app, etc.). Just complete it normally in the browser.

**Q: Can I run multiple instances?**

A: Yes, but change ports in docker-compose.yml:
```yaml
ports:
  - "8081:8080"  # GUI
  - "6081:6080"  # noVNC
  - "3001:3000"  # Extractor
```

**Q: How do I update to latest version?**

```bash
git pull origin feature/interactive-browser-login
docker-compose down
docker-compose build --no-cache
docker-compose up
```

**Q: Cookies not working with gogrepo?**

A: Ensure cookies are in LWP format. Check:
```bash
docker exec gogrepo-gui head -5 /app/data/gog-cookies.dat
```
Should start with `#LWP-Cookies-2.0`

## Support

If you encounter issues:

1. **Check logs**: `docker-compose logs -f`
2. **Review this guide**: Most issues covered above
3. **Test manually**: Access each port individually
4. **Open issue**: Include logs and error messages

## See Also

- [Main README](README.md) - General project documentation
- [GOGrepo Documentation](https://github.com/eddie3/gogrepo) - Original gogrepo tool
- [noVNC Project](https://github.com/novnc/noVNC) - Web-based VNC client

## Credits

This feature combines:
- **GOGrepo** by eddie3 - GOG repository management
- **noVNC** - Web-based VNC access
- **Chromium** - Open-source browser
- **Flask** - Web framework for interfaces
