---
type: paper
name: SuperInfer
full_title: "SuperInfer: SLO-Aware Rotary Scheduling and Memory Management for LLM Inference on Superchips"
authors: [Jiahuan Yu, Mingtao Hu, Zichao Lin, Minjia Zhang]
venue: MLSys
year: 2026
tags: [llm-inference, slo, gh200, nvlink-c2c, offloading, scheduling]
source_pdf: "[[8f14e45fceea167a5a36dedd4bea2543.pdf]]"
source_md: "[[8f14e45fceea167a5a36dedd4bea2543]]"
---

# SuperInfer: SLO-Aware Rotary Scheduling and Memory Management for LLM Inference on Superchips (MLSys 2026)

> **一句话总结**：在 NVIDIA GH200 Superchip（Grace+Hopper 用 NVLink-C2C 互联，900GB/s）上，设计 OS 风格的主动 rotary scheduler（用 Virtual Lag Time 的 LVF 策略）+ DuplexKV 全双工 KV cache rotation engine（eager block rotation 消除读写 race、layout 变换合并小段），把 C2C 有效带宽从 <5% 拉到近理论峰值，TTFT SLO 达成率比 SOTA 提升最多 **74.7%**。

## 问题

LLM serving 的核心矛盾：严格的 TTFT/TBT SLO ↔ 有限 GPU memory。高请求率下 [[KV-Cache]] 爆满，HOL blocking 严重。已有方案：

1. **基于 PCIe 的 offload**（FlexGen、FastDecode、NEO、CachedAttention）：PCIe Gen5x16 带宽 32-64GB/s，swap 太慢——offload 清 backlog 不及时，resume 也 HOL block
2. **SLO-aware scheduler**（Sarathi-Serve、SOLA、FastServe）：假设 all-on-GPU，受 GPU memory 硬约束
3. **静态 offload 策略**（Waiting-First、Swapped-First）：非 SLO-aware，要么 TTFT 好 TBT 差，要么反之

**Superchip 机遇和陷阱**：GH200 用 NVLink-C2C 把 Hopper GPU 和 Grace CPU 粘起来，900GB/s 双向带宽（比 PCIe 高一个数量级）。但把现有 PCIe offload 直接搬过来，**实际带宽利用率 <5%**（vLLM 只跑出 ~10GB/s）。瓶颈在软件栈，不是硬件。

## 核心方法

**RotaSched（主动 rotary scheduler）**：
借鉴 OS 调度（CFS、EEVDF）的 time-slicing 思想，把 LLM serving 类比 OS：request = thread、Hopper HBM = cache、Grace DRAM = main memory、KV cache = thread data。

- **Rotary state**：新引入的 transient 状态，请求的 KV 被 swap 到 CPU 等待下次 rotation（不是传统「OOM 时才 passive preempt」）
- **Virtual Lag Time (VLT)**：类 EEVDF lag，衡量请求偏离 SLO progress 的程度。对三种 state 分别定义：
  - Running：$-(t_{now}-t_{run})$（负值，越跑越「advance」）
  - Waiting：$\text{ReLU}(t_{now}-t_{arr}-\beta_F S_F)$（TTFT SLO 容忍后开始「lag」）
  - Rotary：$\alpha \cdot \text{ReLU}(t_{now}-t_{last}-\beta_B S_B)$（TBT SLO 容忍；$\alpha \geq 1$ 反映 TBT 对延迟更敏感）
- **Largest-VLT-First (LVF) 策略**：每次 iteration：
  1. HBM 够用则 fallback FCFS
  2. VLT 降序排列
  3. 从头（高 lag 的 waiting/rotary）选请求进入 running，直到 $B_{xfer}+B_{HBM}$ 用完
  4. 从尾（低 lag 的 running）开始 preempt，swap 出 $B_{swap}$ blocks

**DuplexKV（C2C 友好 rotation engine）**：

根因分析 C2C 利用率 <5%：[[PagedAttention]] 把 KV cache 切成 small segments（Qwen2.5-32B 单 segment 仅 64KB），每个 segment 独立 `cudaMemcpyAsync`；C2C 只在 segment ≥ 8MB 才跑满；内核 launch overhead 在 ≤4MB 时超过传输时间；加上 Grace DRAM 是 half-duplex（双向合计 ~384GB/s）。

三项优化：
1. **Eager block rotation**（消除 H2D/D2H race）：观察 KV cache generation 是 incremental，把 block 分 Dirty（正在写）和 Synced（已满）。后台 eagerly 把 synced block swap-out 到 DRAM，preempt 时只要 swap 最后 dirty block；swap-in/out 两个 CUDA stream 无冲突全双工跑
2. **Layout transformation + batched transfer**：把分散 fragment 合并成大连续块（≥8MB），一次 launch 一大包，摊薄 kernel launch overhead
3. **Cross-iteration pipeline**：把 transfer 与模型执行 overlap

## 关键结果

- 多模型多工作负载（Qwen2.5-32B、ShareGPT 等）在 GH200 上评估
- **高请求率下 TTFT SLO 达成率比 SOTA 高最多 74.7%**，TBT 和吞吐量持平
- 低请求率下（memory 足够）与 baseline 持平——说明收益完全来自高压下的 SLO-aware 调度
- C2C 带宽从 <5% 利用率提升到接近 200GB/s 理论上限
- 首个把 OS 风格的主动 preemption（而非 reactive OOM prevention）用于 LLM serving、并针对 Superchip 做全双工 offload 的系统

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、NVLink-C2C、SLO、[[Continuous-Batching]]、[[Chunked-Prefill]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Sarathi-Serve、FlexGen、NEO、FastDecode、Pie、SuperOffload、StreamRL
- **同会议**：[[MLSys-2026]]
