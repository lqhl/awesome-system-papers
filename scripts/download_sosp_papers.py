#!/usr/bin/env python3
"""
使用 browser-tools 下载 SOSP 2025 论文的脚本。
通过 Chrome 浏览器访问 ACM Digital Library 来绕过 403 限制。

使用方法:
    python3 download_sosp_papers.py [output_dir]

示例:
    python3 download_sosp_papers.py sosp-2025
"""

import subprocess
import json
import time
import os
import shutil
import re
from pathlib import Path

# SOSP 2025 完整论文列表 (60篇) - 从 ACM DL proceedings 页面获取
PAPERS = [
    {"title": "LithOS: An Operating System for Efficient Machine Learning on GPUs", "doi": "10.1145/3731569.3764818"},
    {"title": "μFork: Supporting POSIX fork Within a Single-Address-Space OS", "doi": "10.1145/3731569.3764809"},
    {"title": "Tock: From Research To Securing 10 Million Computers", "doi": "10.1145/3731569.3764828"},
    {"title": "Proto: A Guided Journey through Modern OS Construction", "doi": "10.1145/3731569.3764811"},
    {"title": "CHERIoT RTOS: An OS for Fine-Grained Memory-Safe Compartments on Low-Cost Embedded Devices", "doi": "10.1145/3731569.3764844"},
    {"title": "The Design and Implementation of a Virtual Firmware Monitor", "doi": "10.1145/3731569.3764826"},
    {"title": "Oasis: Pooling PCIe Devices Over CXL to Boost Utilization", "doi": "10.1145/3731569.3764812"},
    {"title": "Spirit: Fair Allocation of Interdependent Resources in Remote Memory Systems", "doi": "10.1145/3731569.3764805"},
    {"title": "Scalable Far Memory: Balancing Faults and Evictions", "doi": "10.1145/3731569.3764842"},
    {"title": "Device-Assisted Live Migration of RDMA Devices", "doi": "10.1145/3731569.3764795"},
    {"title": "Demeter: A Scalable and Elastic Tiered Memory Solution for Virtualized Cloud via Guest Delegation", "doi": "10.1145/3731569.3764801"},
    {"title": "Robust LLM Training Infrastructure at ByteDance", "doi": "10.1145/3731569.3764838"},
    {"title": "Sailor: Automating Distributed Training over Dynamic, Heterogeneous, and Geo-distributed Clusters", "doi": "10.1145/3731569.3764839"},
    {"title": "DCP: Addressing Input Dynamism In Long-Context Training via Dynamic Context Parallelism", "doi": "10.1145/3731569.3764849"},
    {"title": "TrainVerify: Equivalence-Based Verification for Distributed LLM Training", "doi": "10.1145/3731569.3764850"},
    {"title": "Mycroft: Tracing Dependencies in Collective Communication Towards Reliable LLM Training", "doi": "10.1145/3731569.3764848"},
    {"title": "Mitigating Application Resource Overload with Targeted Task Cancellation", "doi": "10.1145/3731569.3764835"},
    {"title": "Orthrus: Efficient and Timely Detection of Silent User Data Corruption in the Cloud with Resource-Adaptive Computation Validation", "doi": "10.1145/3731569.3764832"},
    {"title": "Optimistic Recovery for High-Availability Software via Partial Process State Preservation", "doi": "10.1145/3731569.3764858"},
    {"title": "COpter: Efficient Large-Scale Resource-Allocation via Continual Optimization", "doi": "10.1145/3731569.3764846"},
    {"title": "Fast End-to-End Performance Simulation of Accelerated Hardware-Software Stacks", "doi": "10.1145/3731569.3764825"},
    {"title": "Characterizing Mobile SoC for Accelerating Heterogeneous LLM Inference", "doi": "10.1145/3731569.3764808"},
    {"title": "IC-Cache: Efficient Large Language Model Serving via In-context Caching", "doi": "10.1145/3731569.3764829"},
    {"title": "PrefillOnly: An Inference Engine for Prefill-only Workloads in Large Language Model Applications", "doi": "10.1145/3731569.3764834"},
    {"title": "Pie: A Programmable Serving System for Emerging LLM Applications", "doi": "10.1145/3731569.3764814"},
    {"title": "DiffKV: Differentiated Memory Management for Large Language Models with Parallel KV Compaction", "doi": "10.1145/3731569.3764810"},
    {"title": "Jenga: Effective Memory Management for Serving LLM with Heterogeneity", "doi": "10.1145/3731569.3764823"},
    {"title": "cache_ext: Customizing the Page Cache with eBPF", "doi": "10.1145/3731569.3764820"},
    {"title": "Aeolia: A Fast and Secure Userspace Interrupt-Based Storage Stack", "doi": "10.1145/3731569.3764816"},
    {"title": "Sleeping with One Eye Open: Fast, Sustainable Storage with Sandman", "doi": "10.1145/3731569.3764804"},
    {"title": "Loom: Efficient Capture and Querying of High-Frequency Telemetry", "doi": "10.1145/3731569.3764853"},
    {"title": "Pesto: Cooking up High Performance BFT Queries", "doi": "10.1145/3731569.3764799"},
    {"title": "Tiga: Accelerating Geo-Distributed Transactions with Synchronized Clocks", "doi": "10.1145/3731569.3764854"},
    {"title": "Tempo: Compiled Dynamic Deep Learning with Symbolic Dependence Graphs", "doi": "10.1145/3731569.3764840"},
    {"title": "SAND: A New Programming Abstraction for Video-based Deep Learning", "doi": "10.1145/3731569.3764847"},
    {"title": "METIS: Fast Quality-Aware RAG Systems with Configuration Adaptation", "doi": "10.1145/3731569.3764855"},
    {"title": "HedraRAG: Co-Optimizing Generation and Retrieval for Heterogeneous RAG Workflows", "doi": "10.1145/3731569.3764806"},
    {"title": "Coyote v2: Raising the Level of Abstraction for Data Center FPGAs", "doi": "10.1145/3731569.3764845"},
    {"title": "KNighter: Transforming Static Analysis with LLM-Synthesized Checkers", "doi": "10.1145/3731569.3764827"},
    {"title": "Fawkes: Finding Data Durability Bugs in DBMSs via Recovered Data State Verification", "doi": "10.1145/3731569.3764841"},
    {"title": "Ghost in the Android Shell: Pragmatic Test-oracle Specification of a Production Hypervisor", "doi": "10.1145/3731569.3764817"},
    {"title": "eBPF Misbehavior Detection: Fuzzing with a Specification-Based Oracle", "doi": "10.1145/3731569.3764797"},
    {"title": "WASIT: Deep and Continuous Differential Testing of WebAssembly System Interface Implementations", "doi": "10.1145/3731569.3764819"},
    {"title": "Prove It to the Kernel: Precise Extension Analysis via Proof-Guided Abstraction Refinement", "doi": "10.1145/3731569.3764796"},
    {"title": "Atmosphere: Practical Verified Kernels with Rust and Verus", "doi": "10.1145/3731569.3764821"},
    {"title": "AutoMan: Facilitating Verified Distributed Systems Development Through Automatic Code Generation and Manual Optimizations", "doi": "10.1145/3731569.3764822"},
    {"title": "TickTock: Verified Isolation in a Production Embedded OS", "doi": "10.1145/3731569.3764856"},
    {"title": "ORQ: Complex Analytics on Private Data with Strong Security Guarantees", "doi": "10.1145/3731569.3764833"},
    {"title": "TRIP: Coercion-resistant Registration for E-Voting with Verifiability and Usability in Votegral", "doi": "10.1145/3731569.3764837"},
    {"title": "Moirai: Optimizing Placement of Data and Compute in Hybrid Clouds", "doi": "10.1145/3731569.3764802"},
    {"title": "Tai Chi: A General High-Efficiency Scheduling Framework for SmartNICs in Hyperscale Clouds", "doi": "10.1145/3731569.3764851"},
    {"title": "Quilt: Resource-aware Merging of Serverless Workflows", "doi": "10.1145/3731569.3764830"},
    {"title": "Mantle: Efficient Hierarchical Metadata Management for Cloud Object Storage Services", "doi": "10.1145/3731569.3764824"},
    {"title": "Unlocking True Elasticity for the Cloud-Native Era with Dandelion", "doi": "10.1145/3731569.3764803"},
    {"title": "Running Consistent Applications Closer to Users with Radical for Lower Latency", "doi": "10.1145/3731569.3764831"},
    {"title": "Managing Scalable Direct Storage Accesses for GPUs with GoFS", "doi": "10.1145/3731569.3764857"},
    {"title": "PhoenixOS: Concurrent OS-level GPU Checkpoint and Restore with Validated Speculation", "doi": "10.1145/3731569.3764813"},
    {"title": "KTransformers: Unleashing the Full Potential of CPU/GPU Hybrid Inference for MoE Models", "doi": "10.1145/3731569.3764843"},
    {"title": "Aegaeon: Effective GPU Pooling for Concurrent LLM Serving on the Market", "doi": "10.1145/3731569.3764815"},
    {"title": "Mercury: Unlocking Multi-GPU Operator Optimization for LLMs via Remote Memory Scheduling", "doi": "10.1145/3731569.3764798"},
]

BROWSER_TOOLS_DIR = Path.home() / ".agents/skills/browser-tools"
DOWNLOADS_DIR = Path.home() / "Downloads"


def get_existing_downloaded_ids(output_dir: Path) -> set:
    """获取已经下载的文件 ID"""
    existing = set()
    # 检查 output_dir 中的文件
    for f in output_dir.glob("*.pdf"):
        match = re.search(r"(3731569\.\d+)", f.name)
        if match:
            existing.add(match.group(1))
    # 检查 Downloads 目录中的文件
    for f in DOWNLOADS_DIR.glob("3731569.*.pdf"):
        match = re.search(r"(3731569\.\d+)", f.name)
        if match:
            existing.add(match.group(1))
    return existing


def move_downloaded_files(output_dir: Path) -> int:
    """将 Downloads 中的 PDF 移动到 output_dir"""
    moved = 0
    for f in DOWNLOADS_DIR.glob("3731569.*.pdf"):
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
        print(f"  Timeout navigating to {url}")
        return False
    except Exception as e:
        print(f"  Error navigating to {url}: {e}")
        return False


def browser_eval(js_code: str) -> str:
    """使用 browser-eval.js 执行 JavaScript"""
    cmd = [str(BROWSER_TOOLS_DIR / "browser-eval.js"), js_code]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception as e:
        print(f"  Error evaluating JS: {e}")
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
        print(f"  [SKIP] {expected_filename} already exists in output dir")
        return True
    if expected_path.exists():
        print(f"  [FOUND] {expected_filename} already in Downloads")
        return True
    
    print(f"  [DOWNLOAD] {title[:60]}...")
    print(f"    URL: {pdf_url}")
    
    # 1. 打开 PDF URL
    if not browser_nav(pdf_url):
        print(f"    [FAILED] Failed to navigate")
        return False
    
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
            # 检查文件是否还在写入
            size1 = expected_path.stat().st_size
            time.sleep(0.5)
            size2 = expected_path.stat().st_size
            if size1 == size2 and size1 > 10000:
                print(f"    [SUCCESS] Downloaded {expected_filename} ({size2//1024}KB)")
                return True
    
    print(f"    [FAILED] Download timeout or incomplete")
    return False


def main():
    import sys
    
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sosp-2025")
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
    
    print(f"\nDownloading {len(papers_to_download)}/{len(PAPERS)} remaining SOSP 2025 papers")
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
