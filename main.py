#!/usr/bin/env python3
"""
YouTube Stream Updater - URL Extractor (JSON & Plain Text Compatible)
"""

import json
import os
import sys
import argparse
from pathlib import Path

# --- ENDPOINT AYARI ---
# Ortam değişkeninden ENDPOINT'i alıyoruz
ENDPOINT = os.environ.get("ENDPOINT")
if not ENDPOINT:
    print("❌ ERROR: ENDPOINT environment variable is not set!")
    sys.exit(1)

ENDPOINT = ENDPOINT.rstrip("/")

FOLDER_NAME = "streams"
TIMEOUT = 25

# İstek motoru seçimi (curl_cffi veya standart requests)
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
    """JSON formatındaki kanal listesini yükler."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def make_request(url, headers):
    """Belirlenen session tipiyle HTTP isteği atar."""
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
    """Endpoint'ten URL çeker ve M3U8 formatına dönüştürür."""
    stream_id = stream["id"]
    slug = stream["slug"]

    url = f"{ENDPOINT}/?ID={stream_id}"
    print(f"  Fetching: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    try:
        resp = make_request(url, headers)
        
        # 404 durumunda bir kez tekrar dene
        if resp.status_code == 404:
            print("  ⚠ 404 returned, retrying…")
            resp = make_request(url, headers)

        resp.raise_for_status()
        raw_text = resp.text.strip()

        hls_url = None

        # --- AYIKLAMA MANTIĞI ---
        # 1. Adım: Yanıt JSON mı diye kontrol et
        try:
            data = json.loads(raw_text)
            hls_url = data.get("hlsUrl")
        except (json.JSONDecodeError, ValueError):
            # 2. Adım: JSON değilse, yanıtın kendisi direkt bir URL mi?
            if raw_text.startswith("http"):
                hls_url = raw_text

        if hls_url:
            print(f"  ✓ URL extracted for {slug}")
            # M3U8 içeriğini oluştur (Direkt linki içeren yönlendirici dosya)
            m3u8_content = f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=1280000\n{hls_url}\n"
            return m3u8_content, None
        else:
            print(f"  ✗ Could not find a valid URL in response for {slug}")
            return None, "InvalidResponse"

    except Exception as e:
        print(f"  ✗ Error fetching/parsing {slug}: {e}")
        return None, "RequestError"

def save_stream(stream, content):
    """İçeriği .m3u8 dosyası olarak kaydeder."""
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
    """Başarısız olan veya artık yayında olmayan kanalın eski dosyasını siler."""
    slug = stream["slug"]
    sub = stream.get("subfolder", "")
    path = Path(FOLDER_NAME) / sub / f"{slug}.m3u8"
    if path.exists():
        path.unlink()
        print(f"  ⚠ Deleted old/broken file: {path}")

def parse_args():
    """Komut satırı argümanlarını okur."""
    p = argparse.ArgumentParser()
    p.add_argument("config_files", nargs="+", help="Kanal listesi JSON dosyaları")
    p.add_argument("--folder", default=FOLDER_NAME, help="Kaydedilecek ana klasör")
    return p.parse_args()

def main():
    global FOLDER_NAME
    args = parse_args()
    FOLDER_NAME = args.folder

    print(f"--- YouTube Stream Updater ---")
    print(f"✓ Session Provider: {SESSION_TYPE}")
    print(f"✓ Target Folder: {FOLDER_NAME}")

    total_ok = 0
    total_fail = 0

    for cfg in args.config_files:
        if not os.path.exists(cfg):
            print(f"❌ Config file not found: {cfg}")
            continue

        print(f"\n📄 Processing: {cfg}")
        streams = load_config(cfg)

        for i, stream in enumerate(streams, 1):
            slug = stream.get('slug', f"stream_{i}")
            print(f"\n[{i}/{len(streams)}] {slug}")

            content, err = fetch_stream_url(stream)

            if content:
                if save_stream(stream, content):
                    total_ok += 1
                else:
                    total_fail += 1
            else:
                # Başarısız olursa eski (bozuk) dosyayı sil
                delete_old(stream)
                total_fail += 1

    print("\n" + "="*30)
    print(f"COMPLETED: {total_ok} Success / {total_fail} Fail")
    print("="*30)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        sys.exit(0)
