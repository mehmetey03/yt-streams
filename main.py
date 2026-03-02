#!/usr/bin/env python3
"""
YouTube Stream Updater - URL Extractor (Direct Text Mode)
"""

import json
import os
import sys
import argparse
from pathlib import Path

# --- ENDPOINT AYARI ---
ENDPOINT = os.environ.get("ENDPOINT")
if not ENDPOINT:
    print("❌ ERROR: ENDPOINT environment variable is not set!")
    sys.exit(1)

ENDPOINT = ENDPOINT.rstrip("/")

FOLDER_NAME = "streams"
TIMEOUT = 30 # YouTube yanıtları bazen yavaş olabilir, süreyi artırdık.

try:
    from curl_cffi import requests as curl_requests
    SESSION_TYPE = "curl_cffi"
except ImportError:
    import requests
    SESSION_TYPE = "requests"

if SESSION_TYPE == "requests":
    session = requests.Session()
else:
    session = None

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def make_request(url, headers):
    if SESSION_TYPE == "curl_cffi":
        return curl_requests.get(
            url,
            headers=headers,
            timeout=TIMEOUT,
            impersonate="chrome120",
            allow_redirects=True
        )
    else:
        return session.get(
            url,
            headers=headers,
            timeout=TIMEOUT,
            allow_redirects=True
        )

def fetch_stream_url(stream):
    stream_id = stream["id"]
    slug = stream["slug"]

    # Senin verdiğin yapı: ENDPOINT/?ID=...
    url = f"{ENDPOINT}/?ID={stream_id}"
    print(f"  Fetching: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/plain, */*"
    }

    try:
        resp = make_request(url, headers)
        
        if resp.status_code >= 500:
            print(f"  ✗ Server Error {resp.status_code}")
            return None, "ServerError"

        resp.raise_for_status()
        
        # Yanıtı temizle (başındaki/sonundaki boşlukları sil)
        raw_output = resp.text.strip()

        # --- YAKALAMA MANTIĞI ---
        # Eğer gelen metin manifest.googlevideo.com içeriyorsa veya http ile başlıyorsa
        if "googlevideo.com" in raw_output or raw_output.startswith("http"):
            print(f"  ✓ URL found for {slug}")
            
            # IPTV Oynatıcılar için M3U8 formatı oluşturuyoruz
            m3u8_content = (
                "#EXTM3U\n"
                "#EXT-X-VERSION:3\n"
                "#EXT-X-STREAM-INF:BANDWIDTH=1280000,RESOLUTION=1280x720\n"
                f"{raw_output}\n"
            )
            return m3u8_content, None
        else:
            # Gelen yanıt boş veya geçersizse (Error 500 veya boş dönme durumu)
            print(f"  ✗ Invalid response (No URL found): {raw_output[:50]}...")
            return None, "NoValidUrlFound"

    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
        return None, "RequestError"

def save_stream(stream, content):
    slug = stream["slug"]
    sub = stream.get("subfolder", "")

    outdir = Path(FOLDER_NAME) / sub
    outdir.mkdir(parents=True, exist_ok=True)

    outfile = outdir / f"{slug}.m3u8"

    try:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✓ Saved: {outfile}")
        return True
    except Exception as e:
        print(f"  ✗ Cannot save {outfile}: {e}")
        return False

def delete_old(stream):
    slug = stream["slug"]
    sub = stream.get("subfolder", "")
    path = Path(FOLDER_NAME) / sub / f"{slug}.m3u8"
    if path.exists():
        path.unlink()
        print(f"  ⚠ Deleted broken/old link: {path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_files", nargs="+")
    parser.add_argument("--folder", default=FOLDER_NAME)
    args = parser.parse_args()

    global FOLDER_NAME
    FOLDER_NAME = args.folder

    print(f"--- YouTube M3U8 Link Extractor ---")
    print(f"Session: {SESSION_TYPE}")

    for cfg in args.config_files:
        if not os.path.exists(cfg): continue
        
        print(f"\n📄 File: {cfg}")
        streams = load_config(cfg)

        for i, stream in enumerate(streams, 1):
            slug = stream['slug']
            print(f"\n[{i}/{len(streams)}] {slug}")

            content, err = fetch_stream_url(stream)

            if content:
                save_stream(stream, content)
            else:
                # Eğer link bulunamazsa, eski (geçersiz) m3u8'i siler
                delete_old(stream)

    print("\n--- İşlem Tamamlandı ---")

if __name__ == "__main__":
    main()
