#!/usr/bin/env python3
"""
使用 browser-tools 下载 SOSP 2024 论文的脚本。

使用方法:
    python3 download_sosp_2024_papers.py [output_dir]
"""

import subprocess
import json
import time
import shutil
import re
from pathlib import Path

# SOSP 2024 完整论文列表 (43篇)
PAPERS = [
    {"title": "Autobahn: Seamless high speed BFT", "doi": "10.1145/3694715.3695942"},
    {"title": "SWARM: Replicating Shared Disaggregated-Memory Data in No Time", "doi": "10.1145/3694715.3695945"},
    {"title": "Efficient Reproduction of Fault-Induced Failures in Distributed Systems with Feedback-Driven Fault Injection", "doi": "10.1145/3694715.3695979"},
    {"title": "If At First You Don't Succeed, Try, Try, Again...? Insights and LLM-informed Tooling for Detecting Retry Bugs in Software Systems", "doi": "10.1145/3694715.3695971"},
    {"title": "Tiered Memory Management: Access Latency is the Key!", "doi": "10.1145/3694715.3695968"},
    {"title": "Fast & Safe IO Memory Protection", "doi": "10.1145/3694715.3695943"},
    {"title": "CHIME: A Cache-Efficient and High-Performance Hybrid Index on Disaggregated Memory", "doi": "10.1145/3694715.3695959"},
    {"title": "Aceso: Achieving Efficient Fault Tolerance in Memory-Disaggregated Key-Value Stores", "doi": "10.1145/3694715.3695951"},
    {"title": "Reducing Energy Bloat in Large Model Training", "doi": "10.1145/3694715.3695970"},
    {"title": "Uncovering Nested Data Parallelism and Data Reuse in DNN Computation with FractalTensor", "doi": "10.1145/3694715.3695961"},
    {"title": "Enabling Parallelism Hot Switching for Efficient Training of Large Language Models", "doi": "10.1145/3694715.3695969"},
    {"title": "Tenplex: Dynamic Parallelism for Deep Learning using Parallelizable Tensor Collections", "doi": "10.1145/3694715.3695975"},
    {"title": "ReCycle: Resilient Training of Large DNNs using Pipeline Adaptation", "doi": "10.1145/3694715.3695960"},
    {"title": "OZZ: Identifying Kernel Out-of-Order Concurrency Bugs with In-Vivo Memory Access Reordering", "doi": "10.1145/3694715.3695944"},
    {"title": "Fast, Flexible, and Practical Kernel Extensions", "doi": "10.1145/3694715.3695950"},
    {"title": "Skyloft: A General High-Efficient Scheduling Framework in User Space", "doi": "10.1145/3694715.3695973"},
    {"title": "Fast Core Scheduling with Userspace Process Abstraction", "doi": "10.1145/3694715.3695976"},
    {"title": "LazyLog: A New Shared Log Abstraction for Low-Latency Applications", "doi": "10.1145/3694715.3695983"},
    {"title": "BIZA: Design of Self-Governing Block-Interface ZNS AFA for Endurance and Performance", "doi": "10.1145/3694715.3695953"},
    {"title": "Morph: Efficient File-Lifetime Redundancy Management for Cluster File Systems", "doi": "10.1145/3694715.3695981"},
    {"title": "Reducing Cross-Cloud/Region Costs with the Auto-Configuring MACARON Cache", "doi": "10.1145/3694715.3695972"},
    {"title": "Dirigent: Lightweight Serverless Orchestration", "doi": "10.1145/3694715.3695966"},
    {"title": "Unifying serverless and microservice workloads with SigmaOS", "doi": "10.1145/3694715.3695947"},
    {"title": "Caribou: Fine-Grained Geospatial Shifting of Serverless Applications for Sustainability", "doi": "10.1145/3694715.3695954"},
    {"title": "TrEnv: Transparently Share Serverless Execution Environments Across Different Functions and Nodes", "doi": "10.1145/3694715.3695967"},
    {"title": "Verus: A Practical Foundation for Systems Verification", "doi": "10.1145/3694715.3695952"},
    {"title": "Practical Verification of System-Software Components Written in Standard C", "doi": "10.1145/3694715.3695980"},
    {"title": "Icarus: Trustworthy Just-In-Time Compilers with Symbolic Meta-Execution", "doi": "10.1145/3694715.3695949"},
    {"title": "SilvanForge: A Schedule-Guided Retargetable Compiler for Decision Tree Inference", "doi": "10.1145/3694715.3695958"},
    {"title": "Scaling Deep Learning Computation over the Inter-Core Connected Intelligence Processor with T10", "doi": "10.1145/3694715.3695955"},
    {"title": "FBDetect: Catching Tiny Performance Regressions at Hyperscale through In-Production Monitoring", "doi": "10.1145/3694715.3695977"},
    {"title": "VPRI: Efficient I/O Page Fault Handling via Software-Hardware Co-Design for IaaS Clouds", "doi": "10.1145/3694715.3695957"},
    {"title": "vSoC: Efficient Virtual System-on-Chip on Heterogeneous Hardware", "doi": "10.1145/3694715.3695946"},
    {"title": "Unearthing Semantic Checks for Cloud Infrastructure-as-Code Programs", "doi": "10.1145/3694715.3695974"},
    {"title": "PowerInfer: Fast Large Language Model Serving with a Consumer-grade GPU", "doi": "10.1145/3694715.3695964"},
    {"title": "Apparate: Rethinking Early Exits to Tame Latency-Throughput Tensions in ML Serving", "doi": "10.1145/3694715.3695963"},
    {"title": "Improving DNN Inference Throughput Using Practical, Per-Input Compute Adaptation", "doi": "10.1145/3694715.3695978"},
    {"title": "LoongServe: Efficiently Serving Long-Context Large Language Models with Elastic Sequence Parallelism", "doi": "10.1145/3694715.3695948"},
    {"title": "Modular Verification of Secure and Leakage-Free Systems: From Application Specification to Circuit-Level Implementation", "doi": "10.1145/3694715.3695956"},
    {"title": "NOPE: Strengthening domain authentication with succinct proofs", "doi": "10.1145/3694715.3695962"},
    {"title": "Cookie Monster: Efficient On-Device Budgeting for Differentially-Private Ad-Measurement Systems", "doi": "10.1145/3694715.3695965"},
    {"title": "Sesame: Practical End-to-End Privacy Compliance with Policy Containers and Privacy Regions", "doi": "10.1145/3694715.3695984"},
    {"title": "DNS Congestion Control in Adversarial Settings", "doi": "10.1145/3694715.3695982"},
]

BROWSER_TOOLS_DIR = Path.home() / ".agents/skills/browser-tools"
DOWNLOADS_DIR = Path.home() / "Downloads"


def get_existing_downloaded_ids(output_dir: Path) -> set:
    """获取已经下载的文件 ID"""
    existing = set()
    for f in output_dir.glob("*.pdf"):
        match = re.search(r"(3694715\.\d+)", f.name)
        if match:
            existing.add(match.group(1))
    for f in DOWNLOADS_DIR.glob("3694715.*.pdf"):
        match = re.search(r"(3694715\.\d+)", f.name)
        if match:
            existing.add(match.group(1))
    return existing


def move_downloaded_files(output_dir: Path) -> int:
    """将 Downloads 中的 PDF 移动到 output_dir"""
    moved = 0
    for f in DOWNLOADS_DIR.glob("3694715.*.pdf"):
        try:
            dest = output_dir / f.name
            if not dest.exists():
                shutil.move(str(f), str(dest))
                moved += 1
                print(f"  [MOVED] {f.name}")
        except Exception as e:
            print(f"  [ERROR] Failed to move {f.name}: {e}")
    return moved


def browser_nav(url: str) -> bool:
    """使用 browser-nav.js 导航到指定 URL"""
    cmd = [str(BROWSER_TOOLS_DIR / "browser-nav.js"), url, "--new"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        return False


def browser_eval(js_code: str) -> str:
    """使用 browser-eval.js 执行 JavaScript"""
    cmd = [str(BROWSER_TOOLS_DIR / "browser-eval.js"), js_code]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception as e:
        return ""


def submit_cloudflare_form() -> bool:
    """提交 Cloudflare 验证表单"""
    result = browser_eval("""
        (function() {
            const form = document.querySelector("form");
            if (form) {
                form.submit();
                return "submitted";
            }
            return "no form";
        })()
    """)
    return "submitted" in result


def download_paper(doi: str, title: str, output_dir: Path) -> bool:
    """下载单篇论文"""
    doi_suffix = doi.replace("10.1145/", "").replace("10.1145:", "")
    pdf_url = f"https://dl.acm.org/doi/pdf/{doi}?download=true"
    expected_filename = f"{doi_suffix}.pdf"
    expected_path = DOWNLOADS_DIR / expected_filename
    output_path = output_dir / expected_filename
    
    # 检查文件是否已存在
    if output_path.exists():
        print(f"  [SKIP] {expected_filename} already exists")
        return True
    if expected_path.exists():
        print(f"  [FOUND] {expected_filename} already in Downloads")
        return True
    
    print(f"  [DOWNLOAD] {title[:60]}...")
    
    # 1. 打开 PDF URL
    if not browser_nav(pdf_url):
        pass  # ERR_ABORTED 通常意味着下载已开始
    
    # 2. 等待页面加载
    time.sleep(2)
    
    # 3. 提交 Cloudflare 表单
    submit_cloudflare_form()
    
    # 4. 等待文件下载完成
    print(f"    Waiting for download...")
    max_wait = 60
    for i in range(max_wait):
        time.sleep(1)
        if expected_path.exists():
            size1 = expected_path.stat().st_size
            time.sleep(0.5)
            size2 = expected_path.stat().st_size
            if size1 == size2 and size1 > 10000:
                print(f"    [SUCCESS] {expected_filename} ({size2//1024}KB)")
                return True
    
    print(f"    [FAILED] Download timeout")
    return False


def main():
    import sys
    
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sosp-2024")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 首先移动已有的下载文件
    moved = move_downloaded_files(output_dir)
    if moved > 0:
        print(f"Moved {moved} existing files from Downloads to {output_dir}")
    
    # 获取已下载的文件 ID
    existing_ids = get_existing_downloaded_ids(output_dir)
    print(f"Found {len(existing_ids)} already downloaded papers")
    
    # 过滤掉已下载的论文
    papers_to_download = [p for p in PAPERS 
                          if p["doi"].replace("10.1145/", "").replace("10.1145:", "") not in existing_ids]
    
    print(f"\nDownloading {len(papers_to_download)}/{len(PAPERS)} SOSP 2024 papers")
    print(f"Output: {output_dir.absolute()}")
    print("=" * 70)
    
    success_count = 0
    failed_papers = []
    
    for i, paper in enumerate(papers_to_download, 1):
        print(f"\n[{i}/{len(papers_to_download)}]")
        if download_paper(paper["doi"], paper["title"], output_dir):
            success_count += 1
            move_downloaded_files(output_dir)
        else:
            failed_papers.append(paper)
        
        if i < len(papers_to_download):
            time.sleep(2)
    
    # 最后再次移动所有下载的文件
    final_moved = move_downloaded_files(output_dir)
    
    # 打印总结
    print("\n" + "=" * 70)
    print(f"Download complete!")
    print(f"  Success: {success_count}/{len(papers_to_download)}")
    print(f"  Failed:  {len(failed_papers)}/{len(papers_to_download)}")
    
    if failed_papers:
        print(f"\nFailed papers:")
        for paper in failed_papers:
            print(f"  - {paper['title']}")
    
    # 统计
    downloaded_files = list(output_dir.glob("*.pdf"))
    total_size = sum(f.stat().st_size for f in downloaded_files)
    print(f"\nTotal: {len(downloaded_files)}/{len(PAPERS)} files, {total_size // (1024*1024)} MB")


if __name__ == "__main__":
    main()
