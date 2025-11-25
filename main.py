#!/usr/bin/env python3
"""
YouTube Stream Updater - ENDPOINT is fully hidden
"""

import json
import os
import sys
import argparse
from pathlib import Path

# --- ENDPOINT IS HIDDEN ---
ENDPOINT = os.environ.get("ENDPOINT")  # <-- NO DEFAULT URL
if not ENDPOINT:
    print("❌ ERROR: ENDPOINT environment variable is not set!")
    sys.exit(1)

ENDPOINT = ENDPOINT.rstrip("/")  # just clean it

FOLDER_NAME = "streams"
TIMEOUT = 25

# Session selection
try:
    from curl_cffi import requests as curl_requests
    SESSION_TYPE = "curl_cffi"
except ImportError:
    import requests
    SESSION_TYPE = "requests"


# Create session for requests
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

    # Construct Worker URL (NOT visible)
    url = f"{ENDPOINT}/?ID={stream_id}"

    print(f"  Fetching: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    try:
        resp = make_request(url, headers)

        # Retry if Worker gives empty 404
        if resp.status_code == 404:
            print("  ⚠ 404 returned, retrying…")
            resp = make_request(url, headers)

        resp.raise_for_status()
        text = resp.text

        if "#EXTM3U" in text:
            print(f"  ✓ Valid m3u8 for {slug}")
            return text, None
        else:
            print(f"  ✗ Invalid response for {slug}")
            return None, "InvalidContent"

    except Exception as e:
        print(f"  ✗ Error fetching {slug}: {e}")
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
    print("✓ ENDPOINT is loaded from environment (hidden!)")

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
