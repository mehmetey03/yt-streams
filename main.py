#!/usr/bin/env python3
"""
YouTube Stream Updater - URL Extractor (Fixed Global Scope)
"""

import json
import os
import sys
import argparse
from pathlib import Path

# --- GLOBAL DEĞİŞKENLER ---
ENDPOINT = os.environ.get("ENDPOINT")
if not ENDPOINT:
    print("❌ ERROR: ENDPOINT environment variable is not set!")
    sys.exit(1)

ENDPOINT = ENDPOINT.rstrip("/")
FOLDER_NAME = "streams"
TIMEOUT = 50

# Session motoru seçimi
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

    url = f"{ENDPOINT}/?ID={stream_id}"
    print(f"  Fetching: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/plain, */*"
    }

    try:
        resp = make_request(url, headers)
        
        if resp.status_code >= 500:
            return None, f"ServerError_{resp.status_code}"

        resp.raise_for_status()
        
        # URL'yi temizle: Sadece ilk satırı al ve boşlukları at
        raw_output = resp.text.strip().split('\n')[0].replace('\r', '')

        if "googlevideo.com" in raw_output or raw_output.startswith("http"):
            print(f"  ✓ URL extracted for {slug}")
            # M3U8 formatında sarmala
            m3u8_content = (
                "#EXTM3U\n"
                "#EXT-X-VERSION:3\n"
                "#EXT-X-STREAM-INF:BANDWIDTH=1280000,RESOLUTION=1280x720\n"
                f"{raw_output}\n"
            )
            return m3u8_content, None
        else:
            print(f"  ✗ Invalid URL format for {slug}")
            return None, "InvalidFormat"

    except Exception as e:
        print(f"  ✗ Error for {slug}: {str(e)}")
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
        print(f"  ⚠ Deleted broken/old: {path}")

def main():
    # HATANIN ÇÖZÜMÜ: global bildirimi fonksiyonun EN BAŞINDA olmalı
    global FOLDER_NAME

    parser = argparse.ArgumentParser()
    parser.add_argument("config_files", nargs="+")
    parser.add_argument("--folder", default=FOLDER_NAME)
    args = parser.parse_args()

    # Kullanıcıdan gelen folder bilgisini global değişkene ata
    FOLDER_NAME = args.folder

    print(f"--- YouTube Stream Updater ---")
    print(f"✓ Session Provider: {SESSION_TYPE}")
    print(f"✓ Output Directory: {FOLDER_NAME}")

    total_ok = 0
    total_fail = 0

    for cfg in args.config_files:
        if not os.path.exists(cfg):
            print(f"⚠ Config not found: {cfg}")
            continue
        
        streams = load_config(cfg)
        print(f"\n📄 Processing: {cfg}")

        for i, stream in enumerate(streams, 1):
            slug = stream['slug']
            print(f"\n[{i}/{len(streams)}] {slug}")

            content, err = fetch_stream_url(stream)

            if content:
                if save_stream(stream, content):
                    total_ok += 1
                else:
                    total_fail += 1
            else:
                delete_old(stream)
                total_fail += 1

    print("\n" + "="*30)
    print(f"DONE: {total_ok} Success / {total_fail} Fail")
    print("="*30)

if __name__ == "__main__":
    main()
