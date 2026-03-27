#!/usr/bin/env python3
"""
下载 MLSys 会议论文 PDF 的脚本。
支持自动检测并使用环境变量中的 HTTP/HTTPS 代理。
支持并行下载以提高速度。

使用方法:
    python3 download_mlsys_papers.py <year> [output_dir] [max_workers]

示例:
    python3 download_mlsys_papers.py 2025 mlsys-2025
    python3 download_mlsys_papers.py 2025 mlsys-2025 10  # 使用10个并行线程
"""

import urllib.request
import urllib.error
import os
import sys
import time
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_proxy_handler():
    """
    从环境变量中获取代理配置，返回 ProxyHandler。
    支持的环境变量: http_proxy, https_proxy, HTTP_PROXY, HTTPS_PROXY
    """
    # 检查各种可能的环境变量名
    http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
    https_proxy = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
    
    proxy_dict = {}
    if http_proxy:
        proxy_dict['http'] = http_proxy
        print(f"Using HTTP proxy: {http_proxy}")
    if https_proxy:
        proxy_dict['https'] = https_proxy
        print(f"Using HTTPS proxy: {https_proxy}")
    
    if proxy_dict:
        return urllib.request.ProxyHandler(proxy_dict)
    return None


def create_opener():
    """创建带有代理支持的 urllib opener"""
    handlers = []
    
    # 添加代理支持
    proxy_handler = get_proxy_handler()
    if proxy_handler:
        handlers.append(proxy_handler)
    
    # 添加 HTTPS 支持
    handlers.append(urllib.request.HTTPSHandler())
    
    return urllib.request.build_opener(*handlers)


def fetch_page(url: str, timeout: int = 30) -> str:
    """获取网页内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    opener = create_opener()
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with opener.open(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        raise
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        raise


def extract_paper_hashes(html: str) -> list:
    """
    从会议页面提取所有 paper hash。
    Paper hash 格式: /paper_files/paper/2025/hash/{hash}-Abstract-Conference.html
    """
    # 匹配 abstract 页面链接，提取 hash
    pattern = r'/paper_files/paper/\d+/hash/([a-f0-9]+)-Abstract-Conference\.html'
    matches = re.findall(pattern, html)
    
    # 去重并保持顺序
    seen = set()
    unique_hashes = []
    for hash_val in matches:
        if hash_val not in seen:
            seen.add(hash_val)
            unique_hashes.append(hash_val)
    
    return unique_hashes


def download_pdf(hash_val: str, year: int, output_dir: Path, 
                 min_size: int = 50000) -> tuple:
    """
    下载单篇论文的 PDF。
    
    Args:
        hash_val: 论文的 hash 值
        year: 年份 (如 2025)
        output_dir: 输出目录
        min_size: 最小有效文件大小（字节），小于此值认为是下载失败
    
    Returns:
        (hash_val, success: bool, message: str)
    """
    pdf_url = f"https://proceedings.mlsys.org/paper_files/paper/{year}/file/{hash_val}-Paper-Conference.pdf"
    filename = output_dir / f"{hash_val}.pdf"
    
    # 检查文件是否已存在且有效
    if filename.exists():
        size = filename.stat().st_size
        if size > min_size:
            return (hash_val, True, f"[SKIP] {filename.name} already exists ({size//1024}KB)")
        else:
            print(f"[REMOVE] {filename.name} is too small ({size} bytes), re-downloading")
            filename.unlink()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        opener = create_opener()
        req = urllib.request.Request(pdf_url, headers=headers)
        
        with opener.open(req, timeout=120) as response:
            data = response.read()
            
            # 验证文件大小
            if len(data) < min_size:
                return (hash_val, False, f"[FAILED] {filename.name} - too small ({len(data)} bytes)")
            
            # 验证是否是 PDF（检查文件头）
            if not data.startswith(b'%PDF'):
                return (hash_val, False, f"[FAILED] {filename.name} - not a valid PDF")
            
            # 保存文件
            with open(filename, 'wb') as f:
                f.write(data)
            
            return (hash_val, True, f"[SUCCESS] {filename.name} ({len(data)//1024}KB)")
            
    except urllib.error.HTTPError as e:
        return (hash_val, False, f"[FAILED] {filename.name} - HTTP {e.code}")
    except Exception as e:
        return (hash_val, False, f"[FAILED] {filename.name} - {str(e)[:60]}")


def download_conference_papers(year: int, output_dir: str = None, max_workers: int = 5):
    """
    下载指定年份的所有 MLSys 论文。
    
    Args:
        year: 年份 (如 2025)
        output_dir: 输出目录，默认为 mlsys-{year}
        max_workers: 并行下载线程数，默认为 5
    """
    if output_dir is None:
        output_dir = f"mlsys-{year}"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 构建会议页面 URL
    proceedings_url = f"https://proceedings.mlsys.org/paper_files/paper/{year}"
    
    print(f"Fetching paper list from: {proceedings_url}")
    
    try:
        html = fetch_page(proceedings_url)
    except Exception as e:
        print(f"Failed to fetch paper list: {e}")
        return
    
    # 提取 paper hashes
    paper_hashes = extract_paper_hashes(html)
    
    if not paper_hashes:
        print("No papers found. Please check the year.")
        return
    
    print(f"Found {len(paper_hashes)} papers")
    print(f"Using {max_workers} parallel workers")
    print("-" * 50)
    
    # 并行下载所有论文
    success_count = 0
    failed_count = 0
    failed_papers = []
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_hash = {
            executor.submit(download_pdf, hash_val, year, output_path): hash_val 
            for hash_val in paper_hashes
        }
        
        # 处理完成的任务
        for future in as_completed(future_to_hash):
            hash_val = future_to_hash[future]
            completed += 1
            
            try:
                _, success, message = future.result()
                print(f"[{completed}/{len(paper_hashes)}] {message}")
                
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    failed_papers.append(hash_val)
            except Exception as e:
                print(f"[{completed}/{len(paper_hashes)}] [ERROR] {hash_val}: {e}")
                failed_count += 1
                failed_papers.append(hash_val)
    
    # 打印总结
    print("-" * 50)
    print(f"Download complete!")
    print(f"  Success: {success_count}/{len(paper_hashes)}")
    print(f"  Failed:  {failed_count}/{len(paper_hashes)}")
    
    if failed_papers:
        print(f"\nFailed papers:")
        for paper in failed_papers:
            print(f"  - {paper}")
    
    # 统计下载的文件
    downloaded_files = list(output_path.glob("*.pdf"))
    total_size = sum(f.stat().st_size for f in downloaded_files)
    print(f"\nTotal downloaded: {len(downloaded_files)} files, {total_size // (1024*1024)} MB")
    print(f"Output directory: {output_path.absolute()}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    year = int(sys.argv[1])
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    max_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    
    download_conference_papers(year, output_dir, max_workers)


if __name__ == "__main__":
    main()
