#!/usr/bin/env python3
"""
下载 MLSys 2026 论文 PDF。

从 mlsys.org JSON API 获取 accepted papers 列表，通过 arXiv API 按标题搜索并下载 PDF。
会议 proceedings 尚未公开（会议日期 2026.5.18），故使用 arXiv 预印本。

使用方法:
    uv run scripts/download_mlsys2026_papers.py [output_dir]

示例:
    uv run scripts/download_mlsys2026_papers.py papers/mlsys-2026
"""

import urllib.request
import urllib.error
import urllib.parse
import json
import os
import sys
import time
import re
import xml.etree.ElementTree as ET
from pathlib import Path

MLSYS_JSON_URL = "https://mlsys.org/static/virtual/data/mlsys-2026-orals-posters.json"
ARXIV_API_URL = "http://export.arxiv.org/api/query"
MIN_PDF_SIZE = 50000  # 50KB
ARXIV_DELAY = 3.0  # arXiv API rate limit


def create_opener():
    """创建带有代理支持的 urllib opener"""
    handlers = [urllib.request.HTTPSHandler()]
    http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
    https_proxy = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
    proxies = {}
    if http_proxy:
        proxies['http'] = http_proxy
    if https_proxy:
        proxies['https'] = https_proxy
    if proxies:
        handlers.append(urllib.request.ProxyHandler(proxies))
        print(f"Using proxy: {proxies}")
    return urllib.request.build_opener(*handlers)


OPENER = None


def get_opener():
    global OPENER
    if OPENER is None:
        OPENER = create_opener()
    return OPENER


def fetch_url(url: str, timeout: int = 30) -> bytes:
    """获取 URL 内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    with get_opener().open(req, timeout=timeout) as response:
        return response.read()


def fetch_paper_list() -> list[dict]:
    """从 mlsys.org 获取 accepted papers 列表"""
    print(f"Fetching paper list from: {MLSYS_JSON_URL}")
    data = fetch_url(MLSYS_JSON_URL)
    result = json.loads(data)
    papers = result.get("results", [])
    print(f"Found {len(papers)} papers")
    return papers


def normalize_title(title: str) -> str:
    """标准化标题：小写、去标点、合并空格"""
    title = title.lower()
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def search_arxiv(title: str) -> str | None:
    """通过 arXiv API 按标题搜索，返回 PDF URL 或 None"""
    query = f'ti:"{title}"'
    params = urllib.parse.urlencode({
        'search_query': query,
        'start': 0,
        'max_results': 5,
    })
    url = f"{ARXIV_API_URL}?{params}"

    try:
        data = fetch_url(url, timeout=30)
        root = ET.fromstring(data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        norm_query = normalize_title(title)

        for entry in entries:
            arxiv_title = entry.find('atom:title', ns)
            if arxiv_title is None or arxiv_title.text is None:
                continue
            arxiv_title_text = ' '.join(arxiv_title.text.split())

            if normalize_title(arxiv_title_text) == norm_query:
                for link in entry.findall('atom:link', ns):
                    if link.get('title') == 'pdf':
                        return link.get('href') + '.pdf'
                entry_id = entry.find('atom:id', ns).text
                return entry_id.replace('/abs/', '/pdf/') + '.pdf'
    except Exception as e:
        print(f"    arXiv API error: {e}")

    return None


def download_pdf(url: str, filepath: Path) -> bool:
    """下载并验证 PDF"""
    try:
        data = fetch_url(url, timeout=120)
        if len(data) < MIN_PDF_SIZE:
            return False
        if not data.startswith(b'%PDF'):
            return False
        with open(filepath, 'wb') as f:
            f.write(data)
        return True
    except Exception:
        return False


def main():
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("papers/mlsys-2026")
    output_dir.mkdir(parents=True, exist_ok=True)

    papers = fetch_paper_list()
    if not papers:
        print("No papers found!")
        return

    success_count = 0
    skip_count = 0
    not_found = []
    failed = []

    for i, paper in enumerate(papers, 1):
        uid = paper['uid']
        title = paper['name']
        filepath = output_dir / f"{uid}.pdf"

        # 跳过已下载
        if filepath.exists() and filepath.stat().st_size > MIN_PDF_SIZE:
            skip_count += 1
            print(f"[{i}/{len(papers)}] [SKIP] {uid}.pdf")
            continue

        # 搜索 arXiv
        pdf_url = search_arxiv(title)

        if pdf_url is None:
            not_found.append(paper)
            print(f"[{i}/{len(papers)}] [MISS] {title[:65]}")
            time.sleep(ARXIV_DELAY)
            continue

        # 下载
        if download_pdf(pdf_url, filepath):
            size_kb = filepath.stat().st_size // 1024
            success_count += 1
            print(f"[{i}/{len(papers)}] [OK]   {uid}.pdf ({size_kb}KB) - {title[:45]}")
        else:
            failed.append(paper)
            print(f"[{i}/{len(papers)}] [FAIL] {title[:65]}")

        time.sleep(ARXIV_DELAY)

    # 统计
    print(f"\n{'='*60}")
    print(f"下载完成！")
    print(f"  跳过(已存在): {skip_count}")
    print(f"  arXiv 成功:   {success_count}")
    print(f"  arXiv 未找到: {len(not_found)}")
    print(f"  下载失败:     {len(failed)}")

    if not_found:
        print(f"\narXiv 未找到的论文 ({len(not_found)} 篇):")
        for p in not_found:
            forum_id = ""
            match = re.search(r'id=([A-Za-z0-9_-]+)', p.get('paper_url', ''))
            if match:
                forum_id = match.group(1)
            print(f"  - {p['name'][:70]}")
            if forum_id:
                print(f"    https://openreview.net/forum?id={forum_id}")

    downloaded_files = list(output_dir.glob("*.pdf"))
    total_size = sum(f.stat().st_size for f in downloaded_files)
    print(f"\n总计: {len(downloaded_files)} 个 PDF, {total_size // (1024*1024)} MB")
    print(f"输出目录: {output_dir.absolute()}")


if __name__ == "__main__":
    main()
