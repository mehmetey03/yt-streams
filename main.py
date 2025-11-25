#!/usr/bin/env python3
"""
YouTube Stream Updater - Improved Version
Fetches YouTube stream URLs and updates m3u8 playlists
Enhanced with better JS challenge handling and error recovery
"""

import json
import os
import sys
import argparse
import time
import re
from pathlib import Path
from urllib.parse import urlparse

# Try to import cloudscraper first (best option)
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

# Try to import curl_cffi (alternative for tough challenges)
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

# Fallback to standard requests
import requests

# Configuration
ENDPOINT = os.environ.get('ENDPOINT', 'https://your-endpoint.com')
FOLDER_NAME = os.environ.get('FOLDER_NAME', 'streams')
TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
VERBOSE = False

def create_session():
    """Create the best available HTTP session"""
    if CLOUDSCRAPER_AVAILABLE:
        print("✓ Using cloudscraper for JavaScript challenge bypass")
        scraper = cloudscraper.create_scraper()
        return scraper, 'cloudscraper'
    elif CURL_CFFI_AVAILABLE:
        print("✓ Using curl_cffi for advanced challenge bypass")
        return None, 'curl_cffi'
    else:
        print("⚠ Using basic requests (limited challenge support)")
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session, 'requests'

# Initialize session
session, session_type = create_session()

def load_config(config_path):
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"✓ Loaded {len(config)} stream(s) from config")
        return config
    except FileNotFoundError:
        print(f"✗ Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON in config file: {e}")
        sys.exit(1)

def make_request(url, timeout, headers, cookies=None, referer=None):
    """Make HTTP request using the best available method"""
    final_headers = headers.copy()
    if referer:
        final_headers['Referer'] = referer

    if session_type == 'curl_cffi':
        response = curl_requests.get(
            url,
            timeout=timeout,
            headers=final_headers,
            cookies=cookies,
            impersonate="chrome120",
            allow_redirects=True
        )
        return response
    else:
        response = session.get(
            url,
            timeout=timeout,
            headers=final_headers,
            cookies=cookies,
            allow_redirects=True
        )
        return response

def fetch_stream_url(stream_config):
    """Fetch the YouTube stream m3u8 URL"""
    stream_id = stream_config['id']
    slug = stream_config['slug']
    url = f"{ENDPOINT}?ID={stream_id}"
    print(f"  Fetching: {url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        response = make_request(url, TIMEOUT, headers)
        response.raise_for_status()
        content = response.text

        if '#EXTM3U' in content:
            print(f"  ✓ m3u8 content detected for {slug}")
            return content, None
        else:
            print(f"  ✗ Invalid content received for {slug}")
            return None, 'InvalidContent'

    except requests.exceptions.Timeout:
        print(f"  ✗ Timeout occurred for {slug}")
        return None, 'Timeout'
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Request error for {slug}: {e}")
        return None, 'RequestError'

def save_stream(stream_config, m3u8_content):
    """Save m3u8 content to file"""
    slug = stream_config['slug']
    subfolder = stream_config.get('subfolder', '')
    if subfolder:
        output_dir = Path(FOLDER_NAME) / subfolder
    else:
        output_dir = Path(FOLDER_NAME)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{slug}.m3u8"

    try:
        with open(output_file, 'w') as f:
            f.write(m3u8_content)
        print(f"  ✓ Saved: {output_file}")
        return True
    except Exception as e:
        print(f"  ✗ Error saving {output_file}: {e}")
        return False

def delete_old_file(stream_config):
    """Delete the old m3u8 file if it exists"""
    slug = stream_config['slug']
    subfolder = stream_config.get('subfolder', '')
    if subfolder:
        output_dir = Path(FOLDER_NAME) / subfolder
    else:
        output_dir = Path(FOLDER_NAME)

    output_file = output_dir / f"{slug}.m3u8"
    try:
        if output_file.exists():
            output_file.unlink()
            print(f"  ⚠ Deleted old file: {output_file}")
            return True
    except Exception as e:
        print(f"  ⚠ Could not delete old file {output_file}: {e}")
        return False
    return False

def parse_arguments():
    parser = argparse.ArgumentParser(description='Update YouTube stream m3u8 playlists')
    parser.add_argument('config_files', nargs='+', help='Configuration file(s) to process')
    parser.add_argument('--endpoint', default=ENDPOINT, help='API endpoint URL')
    parser.add_argument('--folder', default=FOLDER_NAME, help='Output folder name')
    parser.add_argument('--timeout', type=int, default=TIMEOUT, help='Request timeout in seconds')
    parser.add_argument('--retries', type=int, default=MAX_RETRIES, help='Maximum retry attempts')
    parser.add_argument('--retry-delay', type=int, default=RETRY_DELAY, help='Initial retry delay in seconds')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose debug output')
    parser.add_argument('--fail-on-error', action='store_true', help='Exit with error code if any streams fail')
    return parser.parse_args()

def main():
    global VERBOSE, ENDPOINT, FOLDER_NAME, TIMEOUT, MAX_RETRIES, RETRY_DELAY
    args = parse_arguments()
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
            m3u8_content, error_type = fetch_stream_url(stream)
            if m3u8_content:
                if save_stream(stream, m3u8_content):
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
        for error_type, count in error_summary.items():
            print(f"  • {error_type}: {count}")
    print("="*50)

    if total_fail > 0 and args.fail_on_error:
        sys.exit(1)

if __name__ == "__main__":
    main()
