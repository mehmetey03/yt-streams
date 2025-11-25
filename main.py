#!/usr/bin/env python3
"""
YouTube Stream Updater - Full Working Version
Fetches YouTube stream URLs and updates m3u8 playlists
Enhanced with JS challenge handling and error recovery
"""

import json
import os
import sys
import argparse
import time
from pathlib import Path

# Optional challenge bypass libraries
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

# Fallback requests
import requests

# Default config
ENDPOINT = os.environ.get('ENDPOINT', 'https://your-endpoint.com')
FOLDER_NAME = os.environ.get('FOLDER_NAME', 'streams')
TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2
VERBOSE = False


def create_session():
    if CLOUDSCRAPER_AVAILABLE:
        print("✓ Using cloudscraper for JS challenge bypass")
        return cloudscraper.create_scraper(), 'cloudscraper'
    elif CURL_CFFI_AVAILABLE:
        print("✓ Using curl_cffi for advanced challenge bypass")
        return None, 'curl_cffi'
    else:
        print("⚠ Using basic requests")
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session, 'requests'


session, session_type = create_session()


def load_config(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✓ Loaded {len(data)} stream(s) from config")
        return data
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        sys.exit(1)


def make_request(url, headers=None, cookies=None, referer=None):
    headers = headers or {}
    if referer:
        headers['Referer'] = referer

    if session_type == 'curl_cffi':
        return curl_requests.get(url, headers=headers, cookies=cookies, timeout=TIMEOUT, impersonate="chrome120")
    else:
        return session.get(url, headers=headers, cookies=cookies, timeout=TIMEOUT)


def fetch_stream_url(stream_config):
    slug = stream_config.get('slug', 'unknown')
    stream_id = stream_config.get('id')
    url = f"{ENDPOINT}?ID={stream_id}"
    print(f"  Fetching: {url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = make_request(url, headers=headers)
            response.raise_for_status()
            content = response.text
            if '#EXTM3U' in content:
                print(f"  ✓ m3u8 detected for {slug}")
                return content, None
            else:
                print(f"  ✗ Invalid content for {slug}")
                return None, 'InvalidContent'
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Attempt {attempt} failed for {slug}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                return None, 'RequestFailed'

    return None, 'UnknownError'


def save_stream(stream_config, content):
    slug = stream_config.get('slug', 'unknown')
    subfolder = stream_config.get('subfolder', '')
    out_dir = Path(FOLDER_NAME) / subfolder if subfolder else Path(FOLDER_NAME)
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{slug}.m3u8"
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Saved: {file_path}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to save {file_path}: {e}")
        return False


def delete_old_file(stream_config):
    slug = stream_config.get('slug', 'unknown')
    subfolder = stream_config.get('subfolder', '')
    file_path = Path(FOLDER_NAME) / subfolder / f"{slug}.m3u8" if subfolder else Path(FOLDER_NAME) / f"{slug}.m3u8"
    if file_path.exists():
        try:
            file_path.unlink()
            print(f"  ⚠ Deleted old file: {file_path}")
            return True
        except Exception as e:
            print(f"  ⚠ Could not delete {file_path}: {e}")
    return False


def parse_args():
    parser = argparse.ArgumentParser(description='YouTube Stream Updater')
    parser.add_argument('config_files', nargs='+', help='Config JSON file(s)')
    parser.add_argument('--folder', default=FOLDER_NAME)
    parser.add_argument('--endpoint', default=ENDPOINT)
    parser.add_argument('--timeout', type=int, default=TIMEOUT)
    parser.add_argument('--retries', type=int, default=MAX_RETRIES)
    parser.add_argument('--retry-delay', type=int, default=RETRY_DELAY)
    parser.add_argument('--fail-on-error', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    return parser.parse_args()


def main():
    global ENDPOINT, FOLDER_NAME, TIMEOUT, MAX_RETRIES, RETRY_DELAY, VERBOSE
    args = parse_args()
    ENDPOINT = args.endpoint
    FOLDER_NAME = args.folder
    TIMEOUT = args.timeout
    MAX_RETRIES = args.retries
    RETRY_DELAY = args.retry_delay
    VERBOSE = args.verbose

    total_success = 0
    total_fail = 0
    error_summary = {}

    for config_file in args.config_files:
        print(f"\n📄 Processing config: {config_file}")
        streams = load_config(config_file)
        for i, stream in enumerate(streams, 1):
            slug = stream.get('slug', 'unknown')
            print(f"\n[{i}/{len(streams)}] Processing: {slug}")
            content, error_type = fetch_stream_url(stream)
            if content:
                if save_stream(stream, content):
                    total_success += 1
                else:
                    total_fail += 1
                    delete_old_file(stream)
                    error_summary['SaveError'] = error_summary.get('SaveError', 0) + 1
            else:
                total_fail += 1
                delete_old_file(stream)
                if error_type:
                    error_summary[error_type] = error_summary.get(error_type, 0) + 1

    print("\n" + "="*50)
    print(f"Complete: {total_success} successful, {total_fail} failed")
    if error_summary:
        print("\nError Breakdown:")
        for err, count in error_summary.items():
            print(f"  • {err}: {count}")
    print("="*50)

    if total_fail > 0 and args.fail_on_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
