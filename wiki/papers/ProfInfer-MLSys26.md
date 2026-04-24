---
type: paper
name: ProfInfer
full_title: "ProfInfer: An eBPF-Based Fine-Grained LLM Inference Profiler"
authors: [Bohua Zou, Debayan Roy, Dhimankumar Yogesh Airao, Weihao Xu, Binqi Sun, "et al."]
venue: MLSys
year: 2026
tags: [profiling, ebpf, llm-inference, edge, llama-cpp]
source_pdf: "[[6ea9ab1baa0efb9e19094440c317e21b.pdf]]"
source_md: "[[6ea9ab1baa0efb9e19094440c317e21b]]"
---

# ProfInfer: An eBPF-Based Fine-Grained LLM Inference Profiler (MLSys 2026)

> **一句话总结**：用 eBPF uprobe 非侵入式挂到 llama.cpp 的 token/graph/operator 三层函数上，结合 hardware PMC 计数器（cache refill、memory access、stall cycles 等），提供 DAG/timeline/statistical 三种视图，overhead < 4%（libbpf 下 1.7%），支持 dense、MoE、speculative decoding 分析。

## 问题

LLM 推理从研究走向 production，但 inference engine 的 runtime 行为对开发者是黑盒：

- 通用 ML 引擎（ONNX Runtime、TensorRT）有 operator-level profiler，但 LLM 引擎（尤其 on-device 的 llama.cpp、MNN-LLM、mlc-llm）缺乏 fine-grained、非侵入式 profiling 支持
- 现有 profiler 要么需要重编译/插桩，要么只给 throughput 或 token rate 这种粗粒度指标
- 连「这个 workload 是 memory-bound 还是 compute-bound」这种基本问题都难回答
- Mobile/edge 设备上 overhead 约束更严

现有的 eBPF-based DL tracer 也少与 LLM 语义（operator DAG、MoE routing、KV cache、offloading）挂钩。

## 核心方法

ProfInfer 基于 [[eBPF]]，三大设计目标：fine-grained、non-intrusive、lightweight。

**Tracer 架构**（用户空间 + 内核空间）：
- User-space 应用：按配置文件编译 BPF 程序，attach uprobe/uretprobe/tracepoint，poll ring buffer / perf buffer，处理 event，根据 QoS（如 decoding speed < 5 tok/s）动态开关 probe
- Kernel-space probe handler：记录 PID、CPU ID、timestamp，解析函数参数（C struct pointer）得到 operator 类型、tensor 维度等

**多粒度 probe 点**：

| 层级 | 函数 | 抓取信息 |
|---|---|---|
| Token | `llama_decode` | TTFT / TPOT、batch size |
| Graph | `ggml_backend_graph_compute_async` | backend type（CPU/CUDA/OpenCL/NPU） |
| Operator（CPU） | `ggml_compute_forward` | tensor info、PMC |
| Operator（GPU） | `ggml_cl_compute_forward` | tensor info |
| Operator（NPU） | `ggml_rk_compute_forward` | tensor info |
| Scheduler | `sched_switch`/`sched_wakeup` | thread state |

**Hardware PMC 集成**：per-core 打开 perf event fd，用 `perf_read` 在 operator probe 进入/返回时读 counter（l3d_cache_refill、mem_access_wr、major_faults、cycles、idle_backend_cycles），差值反映该 operator 的内存访问、DRAM 读取等。

**MoE expert tracing**：hook `ggml_compute_forward_mul_mat_id`，从第三个 source tensor 解引用出 top-k expert ID，追踪 expert activation 序列（DRAM 不够时会从 storage fetch，影响 operator 时间）。

**分析器三视图**：
1. **ProfDAG view**：从 raw trace 重建 operator DAG（llama.cpp 的 gguf 格式丢了拓扑）；按 thread ID 分组 → 算 elapsed time 和 PMC 差值 → 迭代查 source 节点地址加边
2. **ProfTime view**：转 Chrome Trace Event Format，用 Perfetto 可视化 token/graph/operator 级时间线 + 线程调度（running/runnable/idle）
3. **ProfStat view**：across tokens / per-operator-type / across experts 三个维度统计

**实现**：Ubuntu 上用 BCC + Python；OpenHarmony 上（不支持 Python）用 libbpf + C。

## 关键结果

- **Overhead**：BCC 下 decoding speed 下降 2.8%-4%（全开 PMC+structure+perf-buf）；libbpf 最低 1.7%。只做 token+graph 层 tracing 时仅 0.1%
- 对比 baseline：llama.cpp 内建 `ggml_graph_dump_dot` 有 **13%** overhead，ONNX Runtime profiler 约 **8%**
- Prefill 阶段 **零 overhead**
- Probe handler 本身 CPU load 可忽略
- 在三台边缘设备（Orange Pi 5 Plus/Ultra、RUBIK Pi 3）上验证，支持 Cortex-A76 CPU + Rockchip/Qualcomm NPU
- 能诊断：compute/memory bottleneck、[[KV-Cache]] 效应、workload 干扰、backend 性能差异、MoE 动态特性

## 相关

- **相关概念**：[[eBPF]]、[[KV-Cache]]、[[MoE]]、[[Speculative-Decoding]]、Perfetto、PMC
- **同类系统**：llama.cpp（target）、MNN-LLM、mlc-llm、PowerInfer、ONNX Runtime profiler、TensorRT profiler
- **同会议**：[[MLSys-2026]]
