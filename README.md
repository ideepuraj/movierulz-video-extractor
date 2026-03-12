# 🎬 Movierulz Video Extractor

A lightweight Python server that extracts direct, ad-free HLS video stream URLs from Movierulz movie pages — bypassing pop-up ads and page distractions so the stream can be played directly in VLC, ExoPlayer, or any HLS-compatible player.

> ⚠️ **DISCLAIMER — Please Read**
>
> This project is created **purely for educational and demonstration purposes** to learn about:
> - Web scraping and HTTP request handling
> - HLS (HTTP Live Streaming) protocol internals
> - Reverse engineering of obfuscation techniques (e.g. fake MIME-type headers)
> - Building proxy servers in Python/Flask
>
> The author **does not condone, encourage, or support piracy** in any form.  
> This tool is **not intended** to be used to infringe on any copyright or intellectual property rights.  
> It is the user's sole responsibility to ensure that any content they access complies with applicable laws in their jurisdiction.  
> Always support content creators by using official, licensed platforms.

---

## How It Works

```
Movierulz Page URL
      │
      ▼
 extractor.py          — Scrapes iFrame player URLs from the movie page
      │
      ▼
   yt-dlp             — Resolves obfuscated iframe URL → raw .m3u8 HLS URL
      │
      ▼
standalone_server.py   — Flask server with:
 ├── /api/extract      — REST API to trigger extraction
 └── /api/proxy        — Transparent proxy that:
                          • Rewrites M3U8 playlist segment URLs
                          • Strips fake PNG headers from .ts video chunks
                          • Attaches required Referer/Origin headers
```

---

## Files

| File | Description |
|------|-------------|
| `extractor.py` | Core extraction logic. Fetches the Movierulz page, finds the embedded player iframe URLs, and uses `yt-dlp` to resolve the raw `.m3u8` stream URL. |
| `standalone_server.py` | Flask HTTP server exposing the REST API and the M3U8 proxy. |
| `test_ui.html` | Simple browser-based test interface. Served at `http://localhost:8001/`. |
| `requirements.txt` | Python dependencies. |

---

## Setup

### Requirements
- Python 3.9+
- pip

### Install

```bash
# Clone the repo
git clone https://github.com/ideepuraj/movierulz-video-extractor.git
cd movierulz-video-extractor

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Install yt-dlp binary into the venv
pip install yt-dlp
```

### Run

```bash
python standalone_server.py
```

Server starts on **http://0.0.0.0:8001** by default.  
Use the `PORT` environment variable to change the port:

```bash
PORT=9000 python standalone_server.py
```

---

## REST API

### `POST /api/extract`

Extract the stream URL from a Movierulz movie page.

**Request:**
```http
POST /api/extract
Content-Type: application/json

{"url": "https://www.5movierulz.viajes/movie-name/movie-watch-online-free-XXXX.html"}
```

**Response (success):**
```json
{
  "success": true,
  "raw_url":   "https://hls2.vcdnx.com/hls/...",
  "proxy_url": "http://localhost:8001/api/proxy?url=..."
}
```

**Response (error):**
```json
{"error": "Could not find embedded player URLs on the page"}
```

> **Use `proxy_url` for playback.** The raw URL requires specific `Referer`/`Origin` HTTP headers that most video players (VLC, ExoPlayer) cannot set. The proxy URL routes through this server which attaches those headers automatically.

### `GET /api/proxy?url=<encoded_url>`

Internal proxy endpoint called by the player. Not meant for direct use — use the `proxy_url` returned from `/api/extract`.

---

## Testing

Open **http://localhost:8001** in your browser.  
Paste a Movierulz movie page URL and click **Extract**.

- Copy the **Proxy URL** to paste into VLC (`Media → Open Network Stream`)
- Click **▶ Open in VLC** to launch directly via VLC intent
- Click **▶ Play in Browser** to test in-page with the built-in HLS player

---

## Raspberry Pi / Remote Access

To run on a Raspberry Pi and access from outside your home network:

```bash
# Install cloudflared for a free HTTPS tunnel (no port forwarding needed)
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64
chmod +x cloudflared-linux-arm64
./cloudflared-linux-arm64 tunnel --url http://localhost:8001
```

This gives you a public URL like `https://xxxx.trycloudflare.com` accessible from anywhere.

---

## Technical Notes

### Why a proxy?
The HLS video host (`vcdnlare.com` / `vcdnx.com`) requires the HTTP `Referer` and `Origin` headers to match their domain. VLC and most native video players cannot set custom headers — so a direct URL would return a 403. The local proxy adds these headers transparently.

### Fake PNG header on `.ts` chunks
The video host prepends a valid 69-byte PNG image to every `.ts` segment to confuse Cloudflare's content scanner. The proxy detects this by looking for the PNG magic bytes (`\x89PNG`) and scans for the real MPEG-TS sync byte (`0x47`) at 188-byte intervals, then strips the fake header before forwarding the clean segment.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

This software is provided "as is" without warranty of any kind. The authors are not responsible for how this software is used.
