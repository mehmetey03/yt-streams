#!/usr/bin/env python3
"""
YouTube Stream Updater - URL Extractor Version
"""

import json
import os
import sys
import argparse
from pathlib import Path

# --- ENDPOINT IS HIDDEN ---
ENDPOINT = os.environ.get("ENDPOINT")
if not ENDPOINT:
    print("❌ ERROR: ENDPOINT environment variable is not set!")
    sys.exit(1)

ENDPOINT = ENDPOINT.rstrip("/")

FOLDER_NAME = "streams"
TIMEOUT = 25

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
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json", # JSON beklediğimizi belirtiyoruz
        "Connection": "keep-alive"
    }

    try:
        resp = make_request(url, headers)
        
        if resp.status_code == 404:
            print("  ⚠ 404 returned, retrying…")
            resp = make_request(url, headers)

        resp.raise_for_status()
        
        # Yanıtı JSON olarak ayrıştırıyoruz
        data = resp.json()
        
        # Örnekte verdiğin "hlsUrl" anahtarını arıyoruz
        hls_url = data.get("hlsUrl")

        if hls_url and "googlevideo.com" in hls_url:
            print(f"  ✓ URL extracted for {slug}")
            # Standart bir M3U8 dosyası içeriği oluşturuyoruz
            m3u8_content = f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=1280000\n{hls_url}"
            return m3u8_content, None
        else:
            print(f"  ✗ hlsUrl not found in response for {slug}")
            return None, "NoUrlFound"

    except Exception as e:
        print(f"  ✗ Error fetching/parsing {slug}: {e}")
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
        print(f"  ✓ Saved URL to M3U8: {outfile}")
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
        print(f"  ⚠ Deleted old: {path}")

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("config_files", nargs="+")
    p.add_argument("--folder", default=FOLDER_NAME)
    return p.parse_args()

def main():
    global FOLDER_NAME
    args = parse_args()
    FOLDER_NAME = args.folder

    print(f"✓ Using session: {SESSION_TYPE}")
    print("✓ Mode: JSON hlsUrl Extraction")

    total_ok = 0
    total_fail = 0

    for cfg in args.config_files:
        print(f"\n📄 Processing: {cfg}")
        streams = load_config(cfg)

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

    print("\n=========================")
    print(f"Done: {total_ok} success / {total_fail} fail")
    print("=========================")

if __name__ == "__main__":
    main()
