---
type: paper
name: CoPilotIO
full_title: "CoPilotIO: CPU as a Co-pilot for GPU I/O to Free GPU Compute"
authors: [Guanyi Chen, Qi Chen, Shu Yin, Jian Zhang]
venue: OSDI
year: 2026
tags: [gpu-io, nvme, storage, gpu-computing, asynchronous-io]
source_pdf: "[[osdi26-chen-guanyi.pdf]]"
source_md: "[[osdi26-chen-guanyi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 以 CPU 协助 GPU I/O，释放 GPU 算力（OSDI 2026）

> **原题**：CoPilotIO: CPU as a Co-pilot for GPU I/O to Free GPU Compute

> **一句话总结**：GPU-centric I/O 的 completion polling 会造成 intra-warp、inter-warp 与 inter-SM stall；CoPilotIO 将 SQ 留在 GPU、CQ 放到 CPU memory，以 CPU user-level polling 和 hardware barrier 完成通知，并在高 IOPS 时自适应启用 GPU co-polling，最高减少 55.5% stall、用 24 而非 72+ SM 饱和 25 GB/s PCIe，并让 DLRM 加速 1.85×。

## 问题与动机

GPU HBM 只有 40–192 GB，而模型状态和数据集已达数百 GB 至 TB，GPU 必须直接、按需访问 NVMe。CPU-centric GDS 不占 GPU core，却受 kernel I/O stack 和 CPU parallelism 限制，GPU kernel 也不能真正 on-demand 发请求；GPU-centric BaM 把 SQ/CQ 与控制路径移到 GPU，能高吞吐按需访问，却让 GPU warp 忙等 completion，把昂贵 SM 变成 I/O controller。

论文把代价分成三层：发 I/O 的 warp 因 in-order execution 无法继续 independent compute（intra-warp）；polling warp 长期处于 ready，挤占同 SM compute warp 的 issue slot（inter-warp）；GPU-memory CQ polling 与 application traffic 争 global memory bandwidth（inter-SM，图 1/2）。CoPilotIO 的目标不是完全绕过 CPU，而是让 GPU 负责低延迟 submission、CPU 负责 completion，在 CPU 不够时才让 GPU协助。

## 关键观察 / 隐含假设

- **观察 1**：GPU-side polling 是三类 stall 的共同根因；BaM 使 intra-warp execution time 最高增 1.87×、inter-warp execution time 最高增 1.71×，heavy memory contention 下 I/O bandwidth 最高降 50.6%（§3、图 2/6）。
  - **依赖假设**：workload 同时有可运行 compute，释放的 warp/SM cycle 能转成应用进展。
  - **可能失效场景**：纯 I/O 或纯 compute、大块顺序传输时 overlap 和 polling savings 有限。
- **观察 2**：绕过 kernel 后，16 CPU threads 在 I/O size 大于 16 KB 时可饱和 SSD；控制条目仅几个 bytes，GPU zero-copy 访问 CPU-resident CQ 不显著限制 NVMe throughput（图 3）。
  - **依赖假设**：[[PCIe|PCIe]] topology、pinned memory 和 coherence 路径允许低成本 control traffic。
  - **可能失效场景**：跨 [[NUMA|NUMA]] socket、PCIe switch congestion 或 GPU/CPU 非同 root complex 时，CQ 与 barrier traffic 成本可能上升。
- **观察 3**：CQ pending count 可作为 CPU polling 跟不上负载的在线信号，因此能按 queue 在 CPU/GPU polling 间切换（§4.5）。
  - **依赖假设**：pending count 主要由 poller capacity 而不是 SSD tail latency 或 burst completion 引起。
- **假设 1**：为 I/O 保留 4–16 CPU cores 比占用 GPU SM 更经济。
  - **证据强度**：中；应用结果支持 GPU cycle 更稀缺，但未计入整机 CPU opportunity cost 和能耗。

## 核心方法

CoPilotIO 采用 split queue：NVMe SQ 在 GPU VRAM，GPU 可直接填 command 和 ring doorbell；CQ 在 CPU DRAM，避免 application GPU-memory traffic 与 polling 争带宽。GPU 侧 `CoPilot-GPUIOLib` 暴露 `async_read/write`，CPU 侧 `CoPilot-CPUIOLib` 以 [[SPDK|SPDK]]-like user-level queue 绕过 kernel（§4.2–§4.4）。

每个 I/O 绑定 16-bit CID 和 `cuda::barrier`。GPU 把 `(cid, barrier)` 写入 CPU-memory lock-free barrier table，CPUAgent poll CQ 后按 CID 找 barrier 并 signal；等待依赖数据的 warp 由 hardware barrier 挂起，GPU scheduler 可运行其他 warp。四 SSD、128 queue、QD=1024 时表约 4 MB（图 4）。

CPU capacity 不足时，CQ-based adaptive co-polling 以 high/low pending threshold 和 hysteresis 决定新 completion 绑定到 CPU-polled 或 GPU-polled CQ。它不迁移 thread，CPUAgent 与 GPUAgent poll 各自 queue；GPUAgent 每 SM 仅一个 warp，idle 时 sleep/disable，CQ仍在 CPU memory，以减少 BaM/AGILE 的 polling interference（§4.5、算法 1）。

错误 completion 会在 barrier table 置 error flag、signal waiter 并回收 CID。无 hardware barrier 的平台可用 GDRCopy 写 GPU completion flag，但论文主要结果依赖 CUDA barrier 路径。

## 设计取舍

- **GPU SM 换 CPU core**：默认释放 GPU polling resource，但中等负载仍需 4–8 dedicated CPU cores，低负载可达 16 cores（图 9c）。
- **自适应吞吐换可预测性**：负载高时 GPUAgent 恢复一部分 GPU polling；系统逐渐接近它要避免的 GPU-centric 行为。
- **split control path 换跨设备协调**：barrier table 和 CID 映射轻量，却引入 CPU/GPU visibility、error propagation 与 queue rebinding 不变量。
- **on-demand API 换平台依赖**：实现依赖 NVIDIA zero-copy、GDRCopy/`cuda::barrier` 与 NVMe queue mapping，跨 vendor 可移植性未展示。
- **边界条件**：4–64 KB、compute/I/O mixed、高 SM pressure 最受益；纯 compute、大顺序 I/O 或 CPU 极度紧张时收益小（§6）。

## 实验与结果

- 双路 Xeon Gold 6530（64 cores）、256 GB DDR5、A100 40 GB/H800 80 GB、四块 Samsung 990 Pro PCIe 4.0 SSD；CoPilotIO 相对 BaM intra-warp stall 最高降 55.5%、inter-warp stall 最高降 18.6%，而 BaM/AGILE 在 memory contention 下 bandwidth 最高降 50.6%（图 6）。
- 4 KB random I/O 中 CoPilotIO 的 throughput/latency 均优于 BaM、AGILE；相对 16-thread GDS，在全部 I/O size 上 bandwidth 更高，4 KB 时也接近 peak（图 7/8、表 2）。
- adaptive load 下 CPU-only throughput 随 IOPS 波动，co-polling 维持稳定高带宽；GPU接管更多 CQ 后 active CPU pollers 从 16 降至 3–4，moderate steady state 常为 4–8（图 9）。
- 四 SSD、8 KB random read、108 queue/QD 1024 下，CoPilotIO 用 24 SM 饱和 PCIe 4.0 x16 的 25 GB/s，BaM/AGILE 需要 72+ SM（图 10a）。
- 替换 GoFS I/O engine 只改少于 20 LOC，4 KB random read 性能最高提升 17.4%（图 10b）。
- SSD-offloaded FlashMoE（2048 experts、64 GB weights）相对 BaM 最高加速 1.44×；Criteo DLRM、batch 2048、10,000 iterations 下 CoPilotIO 为 1.85×，AGILE 为 1.41×（图 11）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| GPU polling 会在 warp、SM 与 memory 三层干扰 compute/I/O | 图 2/6 | A100/H800 synthetic co-run workload | 强 |
| split SQ/CQ 加 CPU polling 可兼顾 on-demand 与高 throughput | 图 7/8、表 2 | 四块 990 Pro、4 KB random I/O 及 size sweep | 强 |
| pending-CQ adaptive co-polling 可应对 CPU不足 | 图 9 | 人工变化 IOPS、最多 16 CPU pollers | 中 |
| CoPilotIO 用显著更少 SM 饱和 PCIe | 图 10a | 四 SSD、8 KB reads、25 GB/s PCIe 4.0 x16 | 强 |
| 收益可转化为 mixed AI workload 的端到端加速 | 图 11 | synthetic FlashMoE offload 与 Criteo DLRM | 强 |

## 批判性分析

### 论证链条

论文先拆解 polling 的三类 stall，再证明 CPU user-level polling 与 CPU-resident CQ 可行，设计和测量一一对应。adaptive GPUAgent 则揭示一个张力：CPU-only 并不能覆盖 small-I/O/high-IOPS，系统最终仍需 GPU poll。因而最准确结论是“最小化、按需启用 GPU polling”，而不是完全消除。

### 假设压力测试

pending CQ 可能因 SSD firmware tail、PCIe congestion 或 completion burst 增长，而非 CPU poller 不足；阈值算法可能错误启用 GPUAgent。多 GPU 共用 CPU cores/SSDs、跨 socket GPU、GPU virtualization/MIG 与 CPU noisy neighbor 均会改变“CPU更便宜”的前提。hardware barrier 的 wake latency 和可扩展数量也是未充分压力测试的资源。

### 实验可信度

评测包含 microbenchmark、adaptive trace、scaling、GoFS 与两个 AI workload，并对 BaM、AGILE、GDS 各自在可运行场景比较，覆盖较好。缺口是 [[MoE|MoE]] workload 为 synthetic routing/config，AGILE 因 runtime error 被排除 GoFS/MoE；论文只给两种 NVIDIA GPU 和一套 CPU/PCIe topology，未报告 error bars、energy 或 CPU-side interference。

### 系统性缺陷

dedicated busy-poll CPU cores 会影响共置服务与整机能耗，但系统只报告 active core 数，没有 end-to-end cost。CID reuse、barrier visibility、CQ rebinding 和 device error 的 race 虽有设计描述，缺少 fault injection。CPUAgent crash、GPU kernel cancellation、SSD reset、queue overflow 与 barrier-table exhaustion 的 recovery 未讨论。

## 局限与后续工作

- **局限 1**：收益依赖可与 I/O overlap 的 compute；纯 I/O、大顺序 I/O与纯 compute 都不是优势区间。
- **局限 2**：CPU scarcity 会迫使 GPUAgent 开启，恢复 GPU资源干扰；论文未给统一 cost model 决定何时值得迁移。
- **局限 3**：单 GPU、四 SSD、单 vendor runtime，缺乏多 GPU/NUMA/virtualization 证据。
- **后续工作 1**：在 SSD tail latency、CPU contention 与 PCIe congestion 独立变化时，比较 pending-count、CPU service time 和 queueing-delay controller 的错误迁移率与 p99 latency。
- **后续工作 2**：把 CPU core-seconds、GPU SM-seconds、energy 与 application latency 放入统一目标函数，验证 adaptive policy 是否真正降低整机成本。
- **后续工作 3**：注入 SSD reset、CPUAgent failure、GPU kernel abort 和 CID wraparound，检查 barrier waiter 是否有界完成且无 CID reuse race。

## 相关

- **相关概念**：[[GPU-Direct-Storage]]、[[GPUDirect-RDMA]]、[[Asynchronous-IO]]、[[NVMe]]、[[GPU-Memory-Tiering]]
- **同类系统**：[[BaM]]、[[AGILE]]、[[GoFS]]、[[GeminiFS]]
- **同会议**：[[OSDI-2026]]
