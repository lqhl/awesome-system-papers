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
FUZZY_THRESHOLD = 0.55  # Jaccard 相似度阈值,接受略微不同措辞的同一论文


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


_STOPWORDS = {'a', 'an', 'the', 'of', 'for', 'and', 'or', 'to', 'in', 'on', 'with', 'via', 'by', 'at', 'from', 'is', 'are'}


def normalize_title(title: str) -> str:
    """标准化标题：小写、去标点、合并空格"""
    title = title.lower()
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def title_tokens(title: str) -> set[str]:
    """返回标题的去停用词 token 集合,用于 Jaccard 相似度"""
    return {w for w in normalize_title(title).split() if w not in _STOPWORDS and len(w) > 1}


def title_similarity(a: str, b: str) -> float:
    """Jaccard 相似度,忽略大小写/标点/常见停用词"""
    sa, sb = title_tokens(a), title_tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _query_arxiv(query: str, max_results: int = 10) -> list[tuple[str, ET.Element]]:
    """执行一次 arXiv 查询,返回 [(title, entry), ...]"""
    params = urllib.parse.urlencode({
        'search_query': query,
        'start': 0,
        'max_results': max_results,
    })
    url = f"{ARXIV_API_URL}?{params}"
    data = fetch_url(url, timeout=30)
    root = ET.fromstring(data)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    out = []
    for entry in root.findall('atom:entry', ns):
        t = entry.find('atom:title', ns)
        if t is None or t.text is None:
            continue
        out.append((' '.join(t.text.split()), entry))
    return out


def _entry_pdf_url(entry: ET.Element) -> str | None:
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    for link in entry.findall('atom:link', ns):
        if link.get('title') == 'pdf':
            return link.get('href') + '.pdf'
    entry_id = entry.find('atom:id', ns)
    if entry_id is not None and entry_id.text:
        return entry_id.text.replace('/abs/', '/pdf/') + '.pdf'
    return None


def _distinctive_word(title: str) -> str | None:
    """
    提取标题里的"项目名"——通常是第一个 CamelCase 或全大写的 token(像 LEANN、
    ProTrain、HexiScale)。用它做 `ti:<name>` 搜索比整句查询更准,因为 arXiv 的
    `ti:X Y` 只把 `ti:` 作用在首词 X 上,后续 token 会退化成全文搜索。
    """
    # 取冒号或破折号之前的部分(项目名通常在标题开头)
    prefix = re.split(r'[:\-–]', title, maxsplit=1)[0]
    for word in re.findall(r"[A-Za-z][A-Za-z0-9]*", prefix):
        if word.lower() in _STOPWORDS:
            continue
        # CamelCase(如 ProTrain, HexiScale)或全大写(如 LEANN, WAVE)
        if re.search(r'[A-Z].*[a-z].*[A-Z]|[A-Z][a-z]+[A-Z]', word):
            return word
        if word.isupper() and len(word) >= 3:
            return word
    return None


def _best_arxiv_match(query: str, title: str, require_substring: str | None = None) -> tuple[str, ET.Element, float] | None:
    """执行一次 arXiv 查询,在结果中选 Jaccard 最高的候选;可选强制 arxiv 标题含某子串"""
    try:
        candidates = _query_arxiv(query, max_results=10)
    except Exception as e:
        print(f"    arXiv API error: {e}")
        return None

    best = None
    for arxiv_title, entry in candidates:
        if require_substring and require_substring.lower() not in arxiv_title.lower():
            continue
        sim = title_similarity(title, arxiv_title)
        if best is None or sim > best[0]:
            best = (sim, arxiv_title, entry)
    return best


def search_arxiv(title: str) -> tuple[str, str, float] | None:
    """
    通过 arXiv API 按标题搜索,返回 (pdf_url, matched_title, similarity) 或 None。

    两阶段策略:
    1. 若能提取项目名(CamelCase/全大写),用 `ti:<name>` 定点搜索,要求 arxiv 标题
       含该项目名。这样能捕获 arXiv 版本标题大改但项目名不变的情况
       (如 "ProTrain: Efficient LLM Training via Memory-Aware Techniques" vs
       会议版 "...Automatic Memory Management")。
    2. 若项目名搜索命中不足,或根本没有项目名,回退到去停用词整句模糊查询。
    取两阶段结果中 Jaccard 最高者,>= FUZZY_THRESHOLD 才接受。
    """
    best_overall = None

    # 阶段 1: 项目名精准搜索
    name = _distinctive_word(title)
    if name:
        r = _best_arxiv_match(f'ti:{name}', title, require_substring=name)
        if r:
            best_overall = r

    # 阶段 2: 停用词过滤的整句搜索(总是跑,和阶段 1 取最优)
    clean_tokens = [w for w in normalize_title(title).split() if w not in _STOPWORDS][:8]
    if clean_tokens:
        terms = ' '.join(clean_tokens)
        r = _best_arxiv_match(f'ti:{terms}', title)
        if r and (best_overall is None or r[0] > best_overall[0]):
            best_overall = r

    if best_overall is None or best_overall[0] < FUZZY_THRESHOLD:
        return None

    sim, arxiv_title, entry = best_overall
    pdf_url = _entry_pdf_url(entry)
    if pdf_url is None:
        return None
    return (pdf_url, arxiv_title, sim)


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
            print(f"[{i}/{len(papers)}] [SKIP] {uid}.pdf", flush=True)
            continue

        # 搜索 arXiv
        result = search_arxiv(title)

        if result is None:
            not_found.append(paper)
            print(f"[{i}/{len(papers)}] [MISS] {title[:65]}", flush=True)
            time.sleep(ARXIV_DELAY)
            continue

        pdf_url, matched_title, sim = result

        # 下载
        if download_pdf(pdf_url, filepath):
            size_kb = filepath.stat().st_size // 1024
            success_count += 1
            tag = "OK  " if sim >= 0.99 else f"OK~{sim:.2f}"
            print(f"[{i}/{len(papers)}] [{tag}] {uid}.pdf ({size_kb}KB) - {title[:45]}", flush=True)
            if sim < 0.99:
                print(f"           fuzzy match: {matched_title[:80]}", flush=True)
        else:
            failed.append(paper)
            print(f"[{i}/{len(papers)}] [FAIL] {title[:65]}", flush=True)

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
