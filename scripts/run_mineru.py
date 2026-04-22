#!/usr/bin/env python3
"""
用 mineru pipeline 后端批量把 PDF 转成 Markdown + 图片。

架构:
- 脚本启动一个常驻的 mineru-api 服务,OCR/布局/公式模型只加载一次(~2 GB)
- 多个客户端以 HTTP 方式并发提交到同一个 api
- 所有任务结束后关闭 api

特性:
- 跳过目标已存在 {stem}.md 的 PDF
- 只保留 {stem}.md 和 images/,删除 mineru 产生的辅助文件
- 失败时把 mineru 输出写到 {output_dir}/{stem}/mineru.log 方便排查

Mac 注意事项:
  MinerU 上游在 Mac 上把 api 并发硬编码为 1(fast_api.py:248),
  --jobs 在 Mac 上只是客户端发请求的并行度,服务端仍串行执行。
  相比旧的每篇论文独立启动 mineru 进程的方式,本脚本仍带来:
  (1) 峰值内存稳定在单进程规模,避免 OOM
  (2) 模型只加载一次,省掉 (N-1) × 冷启动时间
  想真正提升吞吐需要在 Linux + GPU 上跑。

使用方法:
    uv run scripts/run_mineru.py <input_dir> <output_dir> [-j N]

示例:
    uv run scripts/run_mineru.py papers/osdi-2025 markdowns/osdi-2025 -j 2
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_health(base_url: str, timeout: float = 180.0) -> bool:
    """轮询 /health 直到 200 或超时(首次启动需要下载/加载模型,可能较慢)。"""
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except urllib.error.HTTPError as e:
            last_err = e
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as e:
            last_err = e
        time.sleep(2)
    if last_err is not None:
        print(f"最后一次健康检查错误: {last_err}", file=sys.stderr)
    return False


class Progress:
    """线程安全的进度跟踪:记录活跃任务、完成数、平均耗时。"""

    def __init__(self, total: int) -> None:
        self.total = total
        self.done = 0
        self.failed = 0
        self.active: dict[str, float] = {}
        self.start_time = time.time()
        self.lock = threading.Lock()

    def start(self, stem: str) -> int:
        with self.lock:
            self.active[stem] = time.time()
            return self.done + self.failed + len(self.active)

    def finish(self, stem: str) -> tuple[int, float]:
        with self.lock:
            started = self.active.pop(stem, time.time())
            return self.done + self.failed + 1, time.time() - started

    def mark(self, status: str) -> None:
        with self.lock:
            if status == "done":
                self.done += 1
            elif status != "skip":
                self.failed += 1

    def heartbeat_msg(self) -> str | None:
        with self.lock:
            if not self.active:
                return None
            now = time.time()
            finished = self.done + self.failed
            running = ", ".join(
                f"{stem}({int(now - t)}s)" for stem, t in self.active.items()
            )
            parts = [f"进度 {finished}/{self.total}", f"运行中 [{running}]"]
            if finished > 0:
                avg = (now - self.start_time) / finished
                remaining = self.total - finished - len(self.active)
                eta_sec = int(remaining * avg)
                parts.append(f"平均 {int(avg)}s/doc, 剩余约 {eta_sec // 60}m{eta_sec % 60}s")
            return " | ".join(parts)


def process_pdf(
    pdf_path: Path, output_dir: Path, api_url: str, progress: Progress, method: str
) -> tuple[str, str, float]:
    """处理单个 PDF,返回 (stem, status, elapsed_sec)。"""
    stem = pdf_path.stem
    target = output_dir / stem
    md_file = target / f"{stem}.md"

    if md_file.exists():
        return stem, "skip", 0.0

    idx = progress.start(stem)
    print(f"[start {idx}/{progress.total}] {stem}")
    sys.stdout.flush()

    target.mkdir(parents=True, exist_ok=True)
    log_path = target / "mineru.log"

    with log_path.open("w") as log_f:
        result = subprocess.run(
            [
                "mineru",
                "-p", str(pdf_path),
                "-o", str(output_dir),
                "--backend", "pipeline",
                "--method", method,
                "--api-url", api_url,
            ],
            stdout=log_f,
            stderr=subprocess.STDOUT,
        )

    _, elapsed = progress.finish(stem)

    def fail(msg: str) -> tuple[str, str, float]:
        progress.mark("fail")
        return stem, f"fail: {msg}", elapsed

    if result.returncode != 0:
        return fail(f"mineru exit {result.returncode} (see {log_path})")

    # mineru 按 --method 命名中间子目录: auto/txt/ocr
    method_dir = target / method
    if not method_dir.is_dir():
        return fail(f"no {method}/ dir")

    src_md = method_dir / f"{stem}.md"
    src_images = method_dir / "images"
    if not src_md.exists():
        return fail("no markdown produced")

    shutil.move(str(src_md), str(md_file))
    if src_images.is_dir():
        dst_images = target / "images"
        if dst_images.exists():
            shutil.rmtree(dst_images)
        shutil.move(str(src_images), str(dst_images))
    shutil.rmtree(method_dir)
    log_path.unlink(missing_ok=True)
    progress.mark("done")
    return stem, "done", elapsed


def heartbeat_loop(progress: Progress, stop: threading.Event, interval: float = 20.0) -> None:
    while not stop.wait(interval):
        msg = progress.heartbeat_msg()
        if msg:
            print(f"  ... {msg}")
            sys.stdout.flush()


def start_api(port: int, log_path: Path) -> subprocess.Popen:
    """启动 mineru-api 子进程,输出重定向到日志文件。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w")
    proc = subprocess.Popen(
        ["mineru-api", "--host", "127.0.0.1", "--port", str(port)],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # 独立进程组,方便整组 kill
    )
    return proc


def stop_api(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_dir", type=Path, help="含 PDF 的目录(非递归,只扫一层)")
    parser.add_argument("output_dir", type=Path, help="输出目录,每个 PDF 产出 {stem}/{stem}.md + images/")
    parser.add_argument(
        "-j", "--jobs", type=int, default=2,
        help="客户端并发数,默认 2。Mac 上 api 串行处理,2 能与 HTTP/后处理流水线化;Linux/GPU 上可调大"
    )
    parser.add_argument(
        "-m", "--method", choices=["auto", "txt", "ocr"], default="auto",
        help=(
            "正文抽取方式,默认 auto。"
            "对矢量 PDF(如 LaTeX 排版的学术论文)推荐 txt: "
            "从 PDF 原生文本层直读,比 OCR 更准、单篇快 60-90 秒。"
            "图片/表格/公式不受此选项影响,始终走视觉模型独立处理。"
        ),
    )
    parser.add_argument(
        "--api-log", type=Path, default=None,
        help="mineru-api 日志文件路径,默认 {output_dir}/.mineru-api.log"
    )
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"error: {args.input_dir} 不是目录", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(p for p in args.input_dir.glob("*.pdf") if p.is_file())
    if not pdfs:
        print(f"{args.input_dir} 下没有 PDF 文件", file=sys.stderr)
        return 1

    pending = [p for p in pdfs if not (args.output_dir / p.stem / f"{p.stem}.md").exists()]
    pre_skipped = len(pdfs) - len(pending)
    if pre_skipped:
        print(f"跳过 {pre_skipped} 个已处理的 PDF")
    if not pending:
        print("全部已处理,退出")
        return 0

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    api_log = args.api_log or (args.output_dir / ".mineru-api.log")

    print(f"启动 mineru-api 于 {base_url} (日志: {api_log})")
    api_proc = start_api(port, api_log)

    try:
        print("等待 api 启动并加载模型(首次约 20-60s)...")
        if not wait_for_health(base_url, timeout=300):
            print(f"api 启动超时,请检查 {api_log}", file=sys.stderr)
            return 1
        print(f"api 就绪,处理 {len(pending)} 个 PDF,客户端并发 {args.jobs}")
        print(f"提示: 另开终端 `tail -f {api_log}` 可看 mineru 单页处理进度")

        progress = Progress(total=len(pending))
        stop_heartbeat = threading.Event()
        hb_thread = threading.Thread(
            target=heartbeat_loop, args=(progress, stop_heartbeat), daemon=True
        )
        hb_thread.start()

        try:
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                futures = {
                    pool.submit(
                        process_pdf, pdf, args.output_dir, base_url, progress, args.method
                    ): pdf
                    for pdf in pending
                }
                for fut in as_completed(futures):
                    pdf = futures[fut]
                    try:
                        stem, status, elapsed = fut.result()
                    except Exception as exc:
                        progress.mark("fail")
                        print(f"[fail] {pdf.name}: {exc}", file=sys.stderr)
                        continue

                    tag = status.split(":")[0]
                    idx = progress.done + progress.failed
                    detail = f" — {status}" if status.startswith("fail") else ""
                    print(f"[{tag} {idx}/{progress.total}] {stem} ({int(elapsed)}s){detail}")
                    sys.stdout.flush()
        finally:
            stop_heartbeat.set()
            hb_thread.join(timeout=1)

        total_elapsed = int(time.time() - progress.start_time)
        print(
            f"\n汇总: done={progress.done}  skip={pre_skipped}  fail={progress.failed}  "
            f"总耗时 {total_elapsed // 60}m{total_elapsed % 60}s"
        )
        return 0 if progress.failed == 0 else 1
    finally:
        print("关闭 mineru-api")
        stop_api(api_proc)


if __name__ == "__main__":
    sys.exit(main())
