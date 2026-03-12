"""
standalone_server.py — Movierulz Stream Extractor & Proxy Server
=================================================================
A self-contained Flask server that:
  1. Extracts ad-free video stream URLs from Movierulz movie pages
  2. Proxies the HLS video stream (adding required headers, stripping obfuscation)

REST API
--------
POST /api/extract
    Body:    {"url": "<movierulz page url>"}
    Returns: {
               "success": true,
               "raw_url":   "<direct m3u8 — needs headers to play>",
               "proxy_url": "<http://this-server/api/proxy?url=... — works in any player>"
             }
    Errors:  {"error": "<message>"}, HTTP 400 or 500

GET /api/proxy?url=<encoded url>
    Internal proxy endpoint. Fetches the URL with required Referer/Origin headers,
    rewrites M3U8 playlist chunk URLs to also go through this proxy, and strips
    the fake PNG headers that the video host injects to obfuscate .ts chunks.
    ⚠ Not meant to be called directly — used by the proxy_url returned from /api/extract.

GET /
    Serves test_ui.html (web test interface)

Run
---
    pip install flask requests yt-dlp
    python standalone_server.py
"""

import os
import re
import urllib.parse

import requests as http_client
from flask import Flask, request, jsonify, send_from_directory, Response

from extractor import extract_video_url

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Headers required by the video host to allow segment/playlist access
STREAM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://ww7.vcdnlare.com/",
    "Origin":  "https://ww7.vcdnlare.com",
}


# ---------------------------------------------------------------------------
# Web UI
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "test_ui.html")


# ---------------------------------------------------------------------------
# Internal M3U8 proxy
# ---------------------------------------------------------------------------

@app.route("/api/proxy")
def proxy_stream():
    """
    Proxy endpoint for the HLS stream. Handles two cases:
      - M3U8 playlist: rewrites all segment URLs to also go through this proxy
      - .ts video chunk: strips the fake PNG header the host injects
    """
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing 'url' query parameter"}), 400

    try:
        resp = http_client.get(url, headers=STREAM_HEADERS, timeout=30)
        content = resp.content

        if content.startswith(b"#EXTM3U"):
            # --- M3U8 Playlist: rewrite all segment URLs through this proxy ---
            text = content.decode("utf-8", errors="ignore")
            new_lines = []
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    # Rewrite any URI= attribute values (e.g. for encryption keys)
                    def rewrite_uri(m):
                        orig = m.group(1)
                        abs_uri = urllib.parse.urljoin(url, orig)
                        return f'URI="{_proxy_url(abs_uri)}"'
                    line = re.sub(r'URI="([^"]+)"', rewrite_uri, line)
                    new_lines.append(line)
                else:
                    # Segment URL — make absolute then proxy it
                    new_lines.append(_proxy_url(urllib.parse.urljoin(url, line)))

            return Response("\n".join(new_lines), mimetype="application/vnd.apple.mpegurl")

        elif content.startswith(b"\x89PNG\r\n\x1a\n"):
            # --- TS chunk disguised as a PNG image: strip the fake header ---
            # The host prepends a small PNG to bypass Cloudflare hot-link detection.
            # Real MPEG-TS data starts at the first 0x47 sync byte with a valid
            # 188-byte packet boundary.
            content = _strip_png_header(content)
            return Response(content, mimetype="video/MP2T")

        else:
            # Plain TS chunk
            return Response(content, mimetype="video/MP2T")

    except Exception as e:
        print(f"[proxy] Error fetching {url}: {e}")
        return jsonify({"error": str(e)}), 500


def _proxy_url(target_url):
    """Build a /api/proxy?url=... URL pointing to this server."""
    return request.host_url.rstrip("/") + "/api/proxy?url=" + urllib.parse.quote(target_url)


def _strip_png_header(data: bytes) -> bytes:
    """
    Strip the fake PNG header prepended to obfuscated .ts chunks.
    Finds the first valid MPEG-TS sync byte (0x47) confirmed by a second
    sync byte 188 bytes later, then slices from that offset.
    """
    for i in range(min(200, len(data) - 188)):
        if data[i] == 0x47 and data[i + 188] == 0x47:
            return data[i:]
    return data  # couldn't find sync — return as-is


# ---------------------------------------------------------------------------
# Public REST API
# ---------------------------------------------------------------------------

@app.route("/api/extract", methods=["POST"])
def api_extract():
    """
    Extract the stream URL from a Movierulz movie page.

    Request body (JSON):
        {"url": "https://www.5movierulz.viajes/..."}

    Response (JSON):
        {
          "success": true,
          "raw_url": "https://hls2.vcdnx.com/...",
          "proxy_url": "http://this-server/api/proxy?url=..."
        }

    Use `proxy_url` for playback — it:
      - automatically attaches the required Referer/Origin headers
      - strips the fake PNG obfuscation headers from .ts chunks
      - rewrites all M3U8 segment URLs through itself
    """
    body = request.get_json(silent=True) or {}
    url = body.get("url", "").strip()

    if not url:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    print(f"[api] Extract request for: {url}")
    result = extract_video_url(url)

    if "error" in result:
        return jsonify(result), 500

    raw_url = result["url"]
    return jsonify({
        "success": True,
        "raw_url": raw_url,
        "proxy_url": _proxy_url(raw_url),
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    print("=" * 60)
    print("  Movierulz Extractor & Proxy Server")
    print("=" * 60)
    print(f"  Web UI:   http://localhost:{port}/")
    print(f"  API:      POST http://localhost:{port}/api/extract")
    print(f"  Proxy:    GET  http://localhost:{port}/api/proxy?url=...")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)
