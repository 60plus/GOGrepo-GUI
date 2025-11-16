# Cookie Import Guide - GOGrepo GUI

## Overview

GOGrepo GUI now supports **two methods** for logging into GOG.com:

1. **Username/Password** - Traditional login method (with 2FA support)
2. **Cookie Import** - Import authentication cookies directly from your browser

## Why Use Cookie Import?

- ✅ **No password entry** - More secure, especially in shared environments
- ✅ **2FA bypass** - Cookies are already authenticated
- ✅ **Quick setup** - One-time export from browser
- ✅ **Session preservation** - Keep your existing GOG session active

## How to Export Cookies from Browser

### Step 1: Install Browser Extension

Choose one of these trusted cookie export extensions:

#### Chrome/Edge/Brave:
- **Get cookies.txt** - [Chrome Web Store](https://chrome.google.com/webstore)
- **Cookie Editor** - Popular alternative with GUI
- **EditThisCookie** - Classic option

#### Firefox:
- **cookies.txt** - [Firefox Add-ons](https://addons.mozilla.org/)
- **Cookie Quick Manager** - Full-featured option

#### Safari:
- Use **Safari Cookie Editor** extension
- Or export manually via Developer Tools

### Step 2: Export GOG Cookies

1. **Navigate to GOG.com**
   - Go to [https://www.gog.com](https://www.gog.com)
   - Make sure you're logged in

2. **Open the extension**
   - Click the extension icon in your browser toolbar
   - Most extensions show a popup interface

3. **Export cookies**
   - Look for "Export" or "Export All" button
   - Choose **"Netscape format"** or **"cookies.txt format"**
   - Save the file (typically named `cookies.txt`)

### Step 3: Import Cookies to GOGrepo GUI

1. **Open GOGrepo GUI** in your browser
2. **Navigate to the Login section** in the right sidebar
3. **Click "Or import cookies from browser"** to expand the section
4. **Click "Choose cookies.txt file"** and select your exported file
5. **Click "Import Cookies"**
6. **Success!** You should see a green confirmation message

## Detailed Instructions by Extension

### Using "Get cookies.txt" (Recommended)

1. Install from Chrome Web Store
2. Visit gog.com and login
3. Click the extension icon
4. Click **"Export"**
5. File automatically downloads as `cookies.txt`
6. Upload this file to GOGrepo GUI

### Using "Cookie Editor"

1. Install the extension
2. Visit gog.com and login  
3. Click the extension icon
4. Click **"Export"** → **"Netscape HTTP Cookie File"**
5. Save the exported content as `cookies.txt`
6. Upload to GOGrepo GUI

### Manual Export (Advanced)

If you prefer not to use extensions:

1. Open Browser **Developer Tools** (F12)
2. Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
3. Select **Cookies** → **https://www.gog.com**
4. Manually copy cookie values
5. Format as Netscape cookies.txt format:

```
# Netscape HTTP Cookie File
.gog.com	TRUE	/	TRUE	1234567890	gog_lc	PL_PLN_en-US
.gog.com	TRUE	/	TRUE	1234567890	gog-al	YOUR_SESSION_TOKEN
```

## Netscape Cookie Format

The expected format for `cookies.txt` is:

```
domain	flag	path	secure	expiration	name	value
```

**Example:**
```
.gog.com	TRUE	/	TRUE	1735689600	gog_lc	US_USD_en-US
.gog.com	TRUE	/	FALSE	1735689600	cookie_consent	true
```

## Troubleshooting

### "No valid cookies found in file"

**Causes:**
- File is not in Netscape format
- File contains no GOG.com cookies
- File is corrupted

**Solutions:**
1. Re-export cookies using recommended extension
2. Make sure you're logged into gog.com before exporting
3. Check file is plain text (open in notepad/text editor)

### "Failed to save cookies"

**Causes:**
- No GOG-specific cookies in the file
- File permissions issue

**Solutions:**
1. Verify the cookies are from gog.com domain
2. Check Docker volume permissions if using Docker
3. Try re-exporting with a different extension

### Cookies expire quickly

**Cause:**
- GOG cookies have short expiration times

**Solution:**
- Re-import cookies when needed
- Use username/password login for long-term sessions

## Security Considerations

⚠️ **Important Security Notes:**

1. **Cookie files contain authentication tokens** - Treat them like passwords
2. **Don't share cookie files** - Anyone with your cookies can access your account
3. **Delete cookies.txt after import** - No need to keep the file
4. **Cookies expire** - You'll need to re-import periodically
5. **Use HTTPS only** - Never export cookies over unsecured connections

## Recommended Workflow

### For Regular Users:
1. Use **username/password** login once
2. Keep session active in GOGrepo GUI

### For Docker/Server Deployments:
1. Export cookies from browser
2. Import into GOGrepo GUI
3. Delete the cookies.txt file
4. Perform updates/downloads
5. Re-import when session expires

### For Advanced Users:
1. Script cookie export using browser automation
2. Automatically import to GOGrepo
3. Schedule regular updates

## FAQ

**Q: Do I need to re-import cookies every time?**

A: No, once imported, cookies are saved to `gog-cookies.dat` and persist between sessions. Re-import only when they expire (usually weeks/months).

**Q: Can I use both login methods?**

A: Yes! You can switch between username/password and cookie import at any time. The latest login method overwrites previous cookies.

**Q: Is cookie import more secure than username/password?**

A: It depends. Cookie import avoids typing passwords but requires careful handling of the cookie file. Both methods are secure when used properly.

**Q: What if I use 2FA?**

A: Cookie import bypasses 2FA since the cookies are already authenticated. If using username/password with 2FA, you'll need to enter the code as normal.

**Q: Can I automate cookie import?**

A: Yes, you can POST to `/import_cookies` endpoint with a cookies file. See API documentation for details.

## Support

If you encounter issues:

1. Check the browser console (F12) for JavaScript errors
2. Review Docker/application logs for backend errors  
3. Verify your cookies.txt file format
4. Try the alternative username/password login method
5. Open an issue on GitHub with details

## See Also

- [Main README](README.md) - General GOGrepo GUI documentation
- [GOG Two-Factor Authentication](https://support.gog.com/hc/en-us/articles/115000861805-Two-step-login)
- [Netscape Cookie Format Specification](http://www.cookiecentral.com/faq/#3.5)
