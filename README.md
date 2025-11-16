# GOGrepo GUI ✨

A lightweight Flask-based web UI around gogrepo to log in, update your manifest, and download your GOG library with real-time logs, progress, and inline game info. Now with **interactive browser login** using noVNC and Chromium for seamless 2FA and CAPTCHA handling! 🚀

## 🆕 New Feature: Interactive Browser Login

### Why Interactive Browser?

The traditional CLI login flow can struggle with:
- **2FA authentication** (app-based or email codes)
- **CAPTCHA challenges**
- **Complex login flows**

### How It Works

1. **First Run Setup**: When cookies are not present, you'll see a setup screen
2. **VNC Browser**: Chromium runs in a VNC session, accessible through noVNC in your browser
3. **Manual Login**: Log in to GOG.com directly in the embedded browser
   - Complete 2FA authentication
   - Solve CAPTCHA if needed
   - Stay logged in as needed
4. **Extract Cookies**: Click "Extract Cookies" to save your session
5. **Automatic Flow**: Once cookies are saved, the app works normally

### Ports

- **8080**: Flask web UI (main application)
- **6080**: noVNC web interface (for browser login)

## Screenshots 📸

_Coming soon: Setup screen with embedded browser_

## Features ✅

- **Interactive browser login** with noVNC-embedded Chromium
  - Full 2FA support (authenticator apps and email codes)
  - CAPTCHA handling
  - Real browser environment for complex login flows
- Two-step login flow integrated with `gogrepo` (legacy CLI method still available)
- Update manifest with OS and language filters, plus:
  - `skipknown` — Only update new games in your library.
  - `updateonly` — Only update games with the updated tag in your library.
- Download options:
  - Download all titles, or a single selected game from your library.
  - Real-time output panel with progress estimation and a Cancel button.
- Downloaded games indicator
  - Automatic detection based on folder existence in download directory.
  - Checks game folders using normalized names (e.g., "blood_fresh_supply").
  - Visual markers (✅ icon and green accent) for already downloaded games in the library.
- Inline game details:
  - Description and cover fetched from GOG API with manifest fallback for robustness.
- Disk cache for descriptions and covers:
  - Stores JSON in Cache/desc and images in Cache/cover to reduce external API calls; cached covers are served locally for faster details panel.
- Helpful hover tooltips on toggles:
  - `skipknown`, `updateonly`, `skipextras`, `skipgames` show what each option does.

## Roadmap 🗺️

- ✅ **Interactive browser login with 2FA and CAPTCHA support**
- Multi-select downloads:
  - Select several games at once (not just one or all).
- Multi-account sessions:
  - Log into multiple GOG accounts and download without duplicates across libraries.

## To build the Docker image locally 🐳

### 1) Clone the repository

Make sure you have the project files locally (the build context must include the `Dockerfile`).

```bash
git clone https://github.com/60plus/GOGrepo-GUI.git
cd GOGrepo-GUI
git checkout test  # Use test branch for interactive browser feature
```

### 2) Build a local image

Build directly from the provided Dockerfile in the repo root.

```bash
docker build -t gogrepo-gui:test .
```

### 3) Run with docker run

Run the container binding ports 8080 (web UI) and 6080 (noVNC) and mounting a local `./data` folder to persist cookies and manifest.

```bash
docker run -d --name gogrepo-gui \
  -p 8080:8080 \
  -p 6080:6080 \
  -v "$PWD/data:/app/data" \
  -e FLASK_SECRET_KEY="${FLASK_SECRET_KEY:-change-me}" \
  -e GOGREPO_DATA_DIR="/app/data" \
  -e GOGREPO_DOWNLOAD_DIR="/app/data" \
  -e PYTHON_BIN="python3" \
  --restart unless-stopped \
  gogrepo-gui:test
```

Open:
- **Main UI**: http://localhost:8080
- **noVNC** (if needed directly): http://localhost:6080

The setup screen will automatically appear on first run if no cookies are present.

### 4) Portainer Stack (Compose)

Use this minimal Compose spec as a Portainer "Stack" for persistent deployment.

```yaml
version: "3.9"

services:
  gogrepo-gui:
    image: gogrepo-gui:test
    container_name: gogrepo-gui
    ports:
      - "8080:8080"   # Flask web UI
      - "6080:6080"   # noVNC web interface
    environment:
      - FLASK_SECRET_KEY=${FLASK_SECRET_KEY:-change-me}
      - GOGREPO_DATA_DIR=/app/data
      - GOGREPO_DOWNLOAD_DIR=/app/data
      - PYTHON_BIN=python3
      - DISPLAY=:99
      - VNC_PORT=5900
      - NOVNC_PORT=6080
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    # Optional: run as your host user
    # user: "${UID:-1000}:${GID:-1000}"
```

## Prebuilt Docker Images 🐳

_Note: Prebuilt images with interactive browser feature will be available soon._

For now, use the local build instructions above with the `test` branch.

## Usage 📖

### First Time Setup

1. Start the container (see above)
2. Navigate to http://localhost:8080
3. You'll see the **Setup Screen** with an embedded browser
4. Click "Start Browser" to launch Chromium in the VNC window
5. Log in to GOG.com in the embedded browser
   - Complete any 2FA challenges
   - Solve CAPTCHA if presented
6. Click "Extract Cookies" to save your session
7. You'll be redirected to the main application

### Normal Usage

After initial setup, the app works normally:

1. **Update Manifest**: Fetch your game library from GOG
2. **Browse Games**: View your games with covers and details
3. **Download**: Download individual games or your entire library
4. **Monitor Progress**: Real-time logs and progress tracking

### gogrepo.py Standalone

> **Tip**: gogrepo.py in the repository still works on its own and can be used standalone if you prefer.

## Quick Start -- Typical Use Case

### Using the Web UI (Recommended)

1. Open http://localhost:8080
2. Complete setup if needed (first run)
3. Click "Update Manifest" with desired OS/language filters
4. Browse your library and download games

### Using gogrepo.py CLI

- **Login** to GOG and save your login cookie for later commands:
  ```bash
  gogrepo.py login
  ```

- **Update** manifest - fetch all game and bonus information:
  ```bash
  gogrepo.py update -os windows linux mac -lang en de fr
  ```

- **Download** games and bonus files:
  ```bash
  gogrepo.py download
  ```

- **Verify** integrity of all downloaded files:
  ```bash
  gogrepo.py verify
  ```

## Advanced Usage -- Common Tasks

- Add new games from your library to the manifest:
  ```bash
  gogrepo.py update -os windows -lang en de -skipknown
  ```

- Update games with the updated tag:
  ```bash
  gogrepo.py update -os windows -lang en de -updateonly
  ```

- Update a single game:
  ```bash
  gogrepo.py update -os windows -lang en de -id trine_2_complete_story
  ```

- Download a single game:
  ```bash
  gogrepo.py download -id trine_2_complete_story
  ```

## Technical Details

### Architecture

- **Flask**: Web framework for UI and API
- **Xvfb**: Virtual display server (`:99`)
- **x11vnc**: VNC server for remote display access
- **noVNC**: Web-based VNC client (websockify proxy)
- **Chromium**: Browser for interactive login
- **Python**: Backend logic and cookie management

### Cookie Extraction

Cookies are extracted from Chromium's SQLite database and converted to Python's `http.cookiejar.LWPCookieJar` format, which is compatible with gogrepo.py.

### Security Notes

- Cookies are stored in `/app/data/gog-cookies.dat`
- Browser profiles are temporary and cleared between sessions
- VNC server runs without password (localhost only in container)
- Use proper network security when exposing ports

## Requirements

### Docker (Recommended)

- Docker 20.10+
- Docker Compose 1.29+ (optional)

### Manual Installation

- Python 3.11+
- System packages: `chromium`, `x11vnc`, `xvfb`, `fluxbox`, `novnc`, `sqlite3`
- Python packages: see `requirements.txt`

## Troubleshooting

### Browser doesn't start

- Check container logs: `docker logs gogrepo-gui`
- Ensure Xvfb is running (should auto-start)
- Verify VNC port 5900 is accessible internally

### noVNC shows black screen

- Wait a few seconds for browser to load
- Try clicking "Start Browser" again
- Check if Chromium process is running in container

### Cookie extraction fails

- Make sure you're logged in to GOG.com
- Verify you can see your account name in the browser
- Try refreshing the GOG page before extracting

### Port conflicts

- Change ports in `docker-compose.yml` if 8080 or 6080 are in use
- Update `NOVNC_PORT` environment variable accordingly

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

See repository license file.

## Credits

- Based on [gogrepo](https://github.com/Kalanyr/gogrepo) by Kalanyr
- noVNC by [novnc/noVNC](https://github.com/novnc/noVNC)
- Flask web framework

---

**Enjoy your GOG library management with seamless browser-based authentication! 🎮✨**