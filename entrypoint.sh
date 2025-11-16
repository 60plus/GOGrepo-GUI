#!/bin/bash
set -e

echo "==============================================="
echo "  GOGrepo GUI - Interactive Login"
echo "==============================================="

# Environment variables
DATA_DIR="${GOGREPO_DATA_DIR:-/app/data}"
COOKIES_FILE="${DATA_DIR}/gog-cookies.dat"
CHROME_PROFILE="/tmp/chrome-profile"
COMPLETION_FLAG="/tmp/cookies_extracted"
VNC_PORT="${VNC_PORT:-6080}"
EXTRACTOR_PORT="3000"
FLASK_PORT="${FLASK_PORT:-8080}"

# Create directories
mkdir -p "$DATA_DIR"
mkdir -p "$CHROME_PROFILE"

echo ""
echo "Configuration:"
echo "  Data directory: $DATA_DIR"
echo "  Cookies file: $COOKIES_FILE"
echo "  Chrome profile: $CHROME_PROFILE"
echo "  VNC port: $VNC_PORT"
echo "  Extractor port: $EXTRACTOR_PORT"
echo "  Flask port: $FLASK_PORT"
echo ""

# Function to check if cookies exist and are valid
check_cookies() {
    if [ -f "$COOKIES_FILE" ]; then
        if [ -s "$COOKIES_FILE" ]; then
            echo "✓ Found existing cookies file"
return 0
        else
            echo "✗ Cookies file exists but is empty"
            return 1
        fi
    else
        echo "✗ No cookies file found"
        return 1
    fi
}

# Function to start VNC server
start_vnc() {
    echo ""
    echo "Starting VNC server..."
    
    # Start Xvfb (Virtual framebuffer)
    Xvfb :99 -screen 0 1280x720x24 &
    export DISPLAY=:99
    sleep 2
    
    # Start x11vnc
    x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &
    sleep 1
    
    # Start noVNC
    /usr/share/novnc/utils/novnc_proxy --vnc localhost:5900 --listen $VNC_PORT &
    sleep 2
    
    echo "✓ VNC server started"
    echo "  Access at: http://localhost:$VNC_PORT"
}

# Function to start Chromium browser
start_chromium() {
    echo ""
    echo "Starting Chromium browser..."
    
    # Start Chromium with GOG homepage
    DISPLAY=:99 chromium \
        --user-data-dir="$CHROME_PROFILE" \
        --no-first-run \
        --no-default-browser-check \
        --disable-infobars \
        --start-maximized \
        "https://www.gog.com" &
    
    sleep 3
    echo "✓ Chromium started"
    echo "  Profile: $CHROME_PROFILE"
}

# Function to start cookie extractor web interface
start_extractor() {
    echo ""
    echo "Starting Cookie Extractor interface..."
    
    cd /app
    python3 cookie_extractor.py &
    
    sleep 2
    echo "✓ Cookie Extractor started"
    echo "  Access at: http://localhost:$EXTRACTOR_PORT"
}

# Function to wait for cookie extraction
wait_for_extraction() {
    echo ""
    echo "==============================================="
    echo "  Waiting for Cookie Extraction"
    echo "==============================================="
    echo ""
    echo "Please complete the following steps:"
    echo ""
    echo "1. Open noVNC: http://localhost:$VNC_PORT"
    echo "   (You'll see Chromium browser with GOG.com)"
    echo ""
    echo "2. Log in to your GOG account"
    echo "   - Complete captcha if prompted"
    echo "   - Enter 2FA code if required"
    echo ""
    echo "3. After successful login, open:"
    echo "   http://localhost:$EXTRACTOR_PORT"
    echo ""
    echo "4. Click 'Extract Cookies' button"
    echo ""
    echo "Waiting for cookies to be extracted..."
    echo ""
    
    # Wait for completion flag or cookies file
    while true; do
        if [ -f "$COMPLETION_FLAG" ] || [ -f "$COOKIES_FILE" ]; then
            echo ""
            echo "✓ Cookies have been extracted!"
            break
        fi
        sleep 2
    done
    
    # Give a moment for file operations to complete
    sleep 2
}

# Function to cleanup browser processes
cleanup_browser() {
    echo ""
    echo "Cleaning up browser processes..."
    
    # Kill Chromium
    pkill -f chromium || true
    
    # Kill cookie extractor
    pkill -f cookie_extractor.py || true
    
    # Keep VNC running for potential debugging
    # pkill -f x11vnc || true
    # pkill -f novnc || true
    
    sleep 2
    echo "✓ Cleanup complete"
}

# Function to start Flask GUI
start_gui() {
    echo ""
    echo "==============================================="
    echo "  Starting GOGrepo GUI"
    echo "==============================================="
    echo ""
    echo "✓ Cookies are ready"
    echo "✓ Starting Flask GUI..."
    echo ""
    echo "GUI will be available at: http://localhost:$FLASK_PORT"
    echo ""
    
    cd /app
    exec python3 app.py
}

# Main logic
echo "Checking for existing cookies..."
echo ""

if check_cookies; then
    echo ""
    echo "✓ Valid cookies found"
    echo "✓ Skipping interactive login"
    start_gui
else
    echo ""
    echo "✗ No valid cookies found"
    echo "✓ Starting interactive login process..."
    echo ""
    
    # Start VNC server
    start_vnc
    
    # Start Chromium browser
    start_chromium
    
    # Start cookie extractor interface
    start_extractor
    
    # Wait for user to extract cookies
    wait_for_extraction
    
    # Verify cookies were created
    if check_cookies; then
        echo ""
        echo "✓ Cookie extraction successful!"
        
        # Cleanup browser
        cleanup_browser
        
        # Start GUI
        start_gui
    else
        echo ""
        echo "✗ Cookie extraction failed"
        echo "✗ Cookies file not found or empty"
        echo ""
        echo "Please check:"
        echo "  1. You logged in to GOG successfully"
        echo "  2. You clicked 'Extract Cookies' button"
        echo "  3. Check logs for any errors"
        echo ""
        echo "Container will keep running for debugging..."
        echo "VNC: http://localhost:$VNC_PORT"
        echo "Extractor: http://localhost:$EXTRACTOR_PORT"
        echo ""
        
        # Keep container alive for debugging
        tail -f /dev/null
    fi
fi
