import requests
from flask import Response, request, stream_with_context
from app import app
import os

# --- Existing app routes come here ---

@app.route('/vnc/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def vnc_proxy(path):
    """
    Proxy endpoint to forward all /vnc/* requests to local noVNC/websockify
    """
    vnc_host = os.environ.get('VNC_HTTP_HOST', 'localhost')
    vnc_port = os.environ.get('NOVNC_PORT', '6080')
    proxied_url = f"http://{vnc_host}:{vnc_port}/{path}"

    headers = {key: value for (key, value) in request.headers if key.lower() != 'host'}

    try:
        resp = requests.request(
            method=request.method,
            url=proxied_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True)
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
        return Response(stream_with_context(resp.iter_content(chunk_size=8192)),
                        status=resp.status_code, headers=headers)
    except Exception as e:
        return Response(f"Proxy error: {e}", status=502)
