#!/usr/bin/env python3
"""
下载 USENIX 会议论文 PDF 的脚本。
支持 OSDI, ATC, NSDI 等 USENIX 会议。

使用方法:
    python3 download_usenix_papers.py <conference> <year> [output_dir]

示例:
    python3 download_usenix_papers.py osdi 2025 osdi-2025
    python3 download_usenix_papers.py atc 2025 atc-2025
    python3 download_usenix_papers.py nsdi 2025 nsdi-2025
"""

import urllib.request
import urllib.error
import os
import sys
import time
import re
from pathlib import Path


def fetch_page(url: str, timeout: int = 30) -> str:
    """获取网页内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        raise
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        raise


def extract_paper_ids(html: str, conference: str, year: int) -> list:
    """
    从会议页面提取所有 paper ID。
    Paper ID 格式通常是: /conference/{conf}{year}/presentation/{paper-id}
    """
    # 匹配 presentation 链接
    pattern = rf'/conference/{conference}{year}/presentation/([a-z0-9-]+)'
    matches = re.findall(pattern, html)
    
    # 去重并保持顺序
    seen = set()
    unique_papers = []
    for paper in matches:
        if paper not in seen:
            seen.add(paper)
            unique_papers.append(paper)
    
    return unique_papers


def download_pdf(paper_id: str, conference: str, year: int, output_dir: Path, 
                 min_size: int = 50000) -> bool:
    """
    下载单篇论文的 PDF。
    
    Args:
        paper_id: 论文 ID
        conference: 会议名称 (如 'osdi', 'atc')
        year: 年份 (如 2025)
        output_dir: 输出目录
        min_size: 最小有效文件大小（字节），小于此值认为是下载失败
    
    Returns:
        下载是否成功
    """
    url = f"https://www.usenix.org/system/files/{conference}{year}-{paper_id}.pdf"
    filename = output_dir / f"{conference}{year}-{paper_id}.pdf"
    
    # 检查文件是否已存在且有效
    if filename.exists():
        size = filename.stat().st_size
        if size > min_size:
            print(f"[SKIP] {filename.name} already exists ({size//1024}KB)")
            return True
        else:
            print(f"[REMOVE] {filename.name} is too small ({size} bytes), re-downloading")
            filename.unlink()
    
    print(f"[DOWNLOAD] {filename.name}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
            
            # 验证文件大小
            if len(data) < min_size:
                print(f"[FAILED] {filename.name} - too small ({len(data)} bytes)")
                return False
            
            # 验证是否是 PDF（检查文件头）
            if not data.startswith(b'%PDF'):
                print(f"[FAILED] {filename.name} - not a valid PDF")
                return False
            
            # 保存文件
            with open(filename, 'wb') as f:
                f.write(data)
            
            print(f"[SUCCESS] {filename.name} ({len(data)//1024}KB)")
            return True
            
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[FAILED] {filename.name} - not found (404)")
        else:
            print(f"[FAILED] {filename.name} - HTTP {e.code}")
        return False
    except Exception as e:
        print(f"[FAILED] {filename.name} - {str(e)[:60]}")
        return False


def download_conference_papers(conference: str, year: int, output_dir: str = None):
    """
    下载指定会议和年份的所有论文。
    
    Args:
        conference: 会议名称 (如 'osdi', 'atc', 'nsdi')
        year: 年份 (如 2025)
        output_dir: 输出目录，默认为 {conference}-{year}
    """
    conference = conference.lower()
    
    if output_dir is None:
        output_dir = f"{conference}-{year}"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 构建会议页面 URL
    session_url = f"https://www.usenix.org/conference/{conference}{year}/technical-sessions"
    
    print(f"Fetching paper list from: {session_url}")
    
    try:
        html = fetch_page(session_url)
    except Exception as e:
        print(f"Failed to fetch paper list: {e}")
        # 尝试去掉年份后两位（如 osdi25 而不是 osdi2025）
        short_year = str(year)[-2:]
        session_url = f"https://www.usenix.org/conference/{conference}{short_year}/technical-sessions"
        print(f"Trying alternate URL: {session_url}")
        html = fetch_page(session_url)
    
    # 提取 paper IDs
    paper_ids = extract_paper_ids(html, conference, year)
    
    if not paper_ids:
        # 尝试短年份格式
        short_year = str(year)[-2:]
        paper_ids = extract_paper_ids(html, conference, short_year)
    
    if not paper_ids:
        print("No papers found. Please check the conference name and year.")
        return
    
    print(f"Found {len(paper_ids)} papers")
    print("-" * 50)
    
    # 下载所有论文
    success_count = 0
    failed_count = 0
    failed_papers = []
    
    for i, paper_id in enumerate(paper_ids, 1):
        print(f"[{i}/{len(paper_ids)}] ", end="")
        if download_pdf(paper_id, conference, year, output_path):
            success_count += 1
        else:
            failed_count += 1
            failed_papers.append(paper_id)
        
        # 礼貌地等待，避免对服务器造成压力
        time.sleep(0.5)
    
    # 打印总结
    print("-" * 50)
    print(f"Download complete!")
    print(f"  Success: {success_count}/{len(paper_ids)}")
    print(f"  Failed:  {failed_count}/{len(paper_ids)}")
    
    if failed_papers:
        print(f"\nFailed papers:")
        for paper in failed_papers:
            print(f"  - {paper}")
    
    # 统计下载的文件
    downloaded_files = list(output_path.glob(f"{conference}{year}-*.pdf"))
    total_size = sum(f.stat().st_size for f in downloaded_files)
    print(f"\nTotal downloaded: {len(downloaded_files)} files, {total_size // (1024*1024)} MB")
    print(f"Output directory: {output_path.absolute()}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    conference = sys.argv[1]
    year = int(sys.argv[2])
    output_dir = sys.argv[3] if len(sys.argv) > 3 else None
    
    download_conference_papers(conference, year, output_dir)


if __name__ == "__main__":
    main()
