#!/usr/bin/env python3
"""Download official MLSys 2026 PDFs from OpenReview (camera-ready versions).
Replaces arXiv versions in papers/mlsys-2026/ using the uids from the conference list.
"""
import json
import urllib.request
import urllib.error
import re
import time
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

JSON_URL = "https://mlsys.org/static/virtual/data/mlsys-2026-orals-posters.json"
OUTPUT_DIR = Path("papers/mlsys-2026")
MIN_SIZE = 20000
DELAY = 1.8  # seconds between requests to avoid 429

def fetch_json():
    req = urllib.request.Request(JSON_URL, headers={"User-Agent": "Mozilla/5.0 (compatible)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def extract_forums(papers):
    uid_to_forum = {}
    for p in papers:
        pu = p.get("paper_url") or ""
        m = re.search(r"openreview.net/forum\?id=([A-Za-z0-9_-]+)", pu)
        if m:
            uid_to_forum[p.get("uid")] = m.group(1)
    return uid_to_forum

def download_pdf(uid, forum_id, output_dir, max_retries=3):
    url = f"https://openreview.net/pdf?id={forum_id}"
    filepath = output_dir / f"{uid}.pdf"
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            if len(data) < MIN_SIZE or not data.startswith(b"%PDF"):
                return uid, False, f"bad content {len(data)}B (attempt {attempt})"
            with open(filepath, "wb") as f:
                f.write(data)
            return uid, True, f"{len(data)//1024}KB"
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                sleep = 5 * attempt
                print(f"    {uid} 429, retrying in {sleep}s (attempt {attempt})...")
                time.sleep(sleep)
                continue
            return uid, False, f"HTTP {e.code}"
        except Exception as e:
            if attempt < max_retries:
                time.sleep(3)
                continue
            return uid, False, str(e)[:70]
    return uid, False, "max retries exceeded"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching paper list...")
    papers = fetch_json().get("results", [])
    uid_to_forum = extract_forums(papers)
    print(f"Found {len(uid_to_forum)} papers with OpenReview links")

    # Force replace all to ensure official versions (re-downloads are ok, rate controlled)
    targets = list(uid_to_forum.items())
    print(f"Targeting {len(targets)} downloads (FORCING replace for all with forum links)")

    success = 0
    fail = 0

    # Conservative concurrency + delay + retries to avoid rate limits
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_map = {}
        for uid, fid in targets:
            fut = executor.submit(download_pdf, uid, fid, OUTPUT_DIR)
            future_map[fut] = (uid, fid)

        done = 0
        for future in as_completed(future_map):
            uid, fid = future_map[future]
            done += 1
            try:
                uid_r, ok, msg = future.result()
                if ok:
                    success += 1
                    print(f"[{done}/{len(targets)}] [OK] {uid}.pdf {msg}")
                else:
                    fail += 1
                    print(f"[{done}/{len(targets)}] [FAIL] {uid}: {msg}")
            except Exception as e:
                fail += 1
                print(f"[{done}/{len(targets)}] [ERR] {uid}: {e}")
            time.sleep(DELAY)

    # Final stats
    pdfs = list(OUTPUT_DIR.glob("*.pdf"))
    total_mb = sum(f.stat().st_size for f in pdfs) // (1024*1024)
    print("\n=== Summary ===")
    print(f"Success: {success}  Fail: {fail}")
    print(f"Total PDFs now: {len(pdfs)} ({total_mb} MB)")
    print(f"Output: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
