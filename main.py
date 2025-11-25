#!/usr/bin/env python3
"""
Stable YouTube Stream Updater (Worker Compatible)
"""

import json
import os
import sys
import argparse
from pathlib import Path

# --- Session Selection ---
try:
    from curl_cffi import requests as curl_requests
    SESSION_TYPE = "curl_cffi"
except ImportError:
    import requests
    SESSION_TYPE = "requests"

# --- DEFAULTS ---
ENDPOINT = os.environ.get("ENDPOINT", "https://ytb.metvmetv07.workers.dev")
FOLDER_NAME = os.environ.get("FOLDER_NAME", "streams")
TIMEOUT = 25

# --- CREATE SESSION ---
if SESSION_TYPE == "requests":
    session = requests.Session()
else:
    session = None


def clean_endpoint(url):
    """Remove trailing slash at end of endpoint"""
    return url.rstrip("/")


ENDPOINT = clean_endpoint(ENDPOINT)


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✓ Loaded {len(data)} stream(s) from config")
    return data


def make_request(url, headers):
    """Safe wrapper for curl_cffi + requests"""

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

    # --- Build Correct Worker URL ---
    url = f"{ENDPOINT}/?ID={stream_id}"

    print(f"  Fetching: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    try:
        response = make_request(url, headers)

        # --- FIX for curl_cffi returning empty reason with 404 ---
        if response.status_code == 404:
            print("  ⚠ 404 received, retrying once…")
            response = make_request(url, headers)

        response.raise_for_status()

        text = response.text

        if "#EXTM3U" in text:
            print(f"  ✓ m3u8 content detected for {slug}")
            return text, None
        else:
            print(f"  ✗ Invalid content for {slug}")
            return None, "InvalidContent"

    except Exception as e:
        print(f"  ✗ Error for {slug}: {e}")
        return None, "RequestError"


def save_stream(stream, content):
    slug = stream["slug"]
    subfolder = stream.get("subfolder", "")

    outdir = Path(FOLDER_NAME) / subfolder
    outdir.mkdir(parents=True, exist_ok=True)

    outfile = outdir / f"{slug}.m3u8"

    try:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✓ Saved: {outfile}")
        return True
    except Exception as e:
        print(f"  ✗ Cannot save file {outfile}: {e}")
        return False


def delete_old(stream):
    slug = stream["slug"]
    subfolder = stream.get("subfolder", "")

    outdir = Path(FOLDER_NAME) / subfolder
    outfile = outdir / f"{slug}.m3u8"

    if outfile.exists():
        outfile.unlink()
        print(f"  ⚠ Deleted old file: {outfile}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("config_files", nargs="+")
    p.add_argument("--endpoint", default=ENDPOINT)
    p.add_argument("--folder", default=FOLDER_NAME)
    return p.parse_args()


def main():
    global ENDPOINT, FOLDER_NAME

    args = parse_args()
    ENDPOINT = clean_endpoint(args.endpoint)
    FOLDER_NAME = args.folder

    total_ok = 0
    total_fail = 0

    print(f"✓ Using {SESSION_TYPE} session")

    for config in args.config_files:
        print(f"\n📄 Processing config: {config}")
        streams = load_config(config)

        for i, stream in enumerate(streams, 1):
            print(f"\n[{i}/{len(streams)}] Processing: {stream['slug']}")

            content, err = fetch_stream_url(stream)

            if content:
                if save_stream(stream, content):
                    total_ok += 1
                else:
                    total_fail += 1
            else:
                total_fail += 1
                delete_old(stream)

    print("\n===============================")
    print(f"Done → {total_ok} success / {total_fail} failed")
    print("===============================")


if __name__ == "__main__":
    main()
