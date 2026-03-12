"""
extractor.py — Movierulz Video URL Extractor
=============================================
Fetches a Movierulz movie page, finds the embedded video player iframes,
then uses yt-dlp to resolve the obfuscated iframe URL into a raw .m3u8 HLS
stream URL that can be played by VLC, ExoPlayer, or our local proxy.

Usage as a library:
    from extractor import extract_video_url
    result = extract_video_url("https://www.5movierulz.viajes/...")
    # result = {"success": True, "url": "https://hls2.vcdnx.com/hls/..."}
    # result = {"error": "some error message"}

Usage from command line:
    python extractor.py "https://www.5movierulz.viajes/..."
"""

import os
import re
import sys
import subprocess
import requests


# Path to yt-dlp binary — prefers the venv's copy, falls back to system PATH
def _find_yt_dlp():
    venv_path = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
    if os.path.exists(venv_path):
        return venv_path
    return "yt-dlp"


def extract_video_url(movierulz_url):
    """
    Given a Movierulz movie page URL, returns a dict:
      {"success": True, "url": "<raw m3u8 url>"}   on success
      {"error": "<message>"}                        on failure
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # --- Step 1: Fetch the Movierulz movie page ---
    print(f"[extractor] Fetching: {movierulz_url}")
    try:
        resp = requests.get(movierulz_url, headers=headers, timeout=15)
    except Exception as e:
        return {"error": f"Failed to fetch page: {e}"}

    if resp.status_code != 200:
        return {"error": f"Received HTTP {resp.status_code} from Movierulz"}

    # --- Step 2: Extract the embedded iframe player URLs ---
    # Movierulz stores them as: var locations = ["url1", "url2"];
    iframe_urls = []
    match = re.search(r'var locations\s*=\s*\[(.*?)\];', resp.text)
    if match:
        for raw_url in re.findall(r'"([^"]+)"', match.group(1)):
            iframe_urls.append(raw_url.replace('\\/', '/'))

    if not iframe_urls:
        return {"error": "Could not find embedded player URLs on the page"}

    print(f"[extractor] Found {len(iframe_urls)} player iframe(s): {iframe_urls}")

    # --- Step 3: Use yt-dlp to extract the raw .m3u8 stream from each iframe ---
    yt_dlp = _find_yt_dlp()
    for iframe_url in iframe_urls:
        print(f"[extractor] Trying yt-dlp on: {iframe_url}")
        try:
            result = subprocess.run(
                [
                    yt_dlp,
                    "-g",                         # print direct stream URL
                    "--add-header", f"Referer:{movierulz_url}",
                    iframe_url
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            for line in result.stdout.strip().split('\n'):
                if line.startswith("http"):
                    print(f"[extractor] Extracted stream: {line}")
                    return {"success": True, "url": line}

        except Exception as e:
            print(f"[extractor] yt-dlp failed on {iframe_url}: {e}")

    return {"error": "yt-dlp could not extract a stream URL from any mirror"}


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else (
        "https://www.5movierulz.viajes/pennu-case-2026-malayalam/movie-watch-online-free-6561.html"
    )
    import json
    print(json.dumps(extract_video_url(url), indent=2))
