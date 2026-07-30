---
type: paper
name: LithOS
full_title: "LithOS: An Operating System for Efficient Machine Learning on GPUs"
authors: [Patrick H. Coppock, Brian Zhang, Eliot H. Solomon, Vasilis Kypriotis, Leon Yang, et al.]
venue: SOSP
year: 2025
tags: [gpu-os, ml-systems, scheduling, multitenancy, power-management]
source_pdf: "[[3731569.3764828.pdf]]"
source_md: "[[3731569.3764818]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# LithOS：用于在 GPU 上进行高效机器学习的操作系统（SOSP 2025）

> **原题**：LithOS: An Operating System for Efficient Machine Learning on GPUs

> **一句话总结**：Meta 生产测量显示 inference GPU 利用率常 <30%、SM 更低；据此用 TPC 粒度调度 + 透明 kernel atomization + right-sizing/DVFS，在不动模型/框架的前提下相对 [[MPS]] 将 tail latency 降 13×（inference stacking）、hybrid infer-train 场景降 4.7×，并节省约 1/4 GPU 容量/能耗（<7% 性能损失）。

## 问题与动机

ML workload 使 GPU 成为数据中心主力，但利用率长期偏低（Microsoft 公开 52%、Alibaba 10%、Meta inference 周级 trace 显示 device utilization 波动大、SM 可低至 15%）。根因包括：单 job 独占 GPU、batch 小、通信 stall、请求分布长尾等。[[MPS]]/[[MIG]] 等空间/时间共享过粗，导致 head-of-line blocking 与 interference；许多研究方案需改 framework 或 offline profiling，难以在快速演进的 ML 栈中透明部署。

作者 claim GPU 需要 **OS 式** 一等公民资源管理：细粒度时空调度、隔离、功耗控制，且对 [[CUDA]]/PyTorch 栈完全透明。

## 关键观察 / 隐含假设

- **观察 1**：GPC 数量近十年几乎平坦（P100 6 个 → B100 8 个），而 SM/带宽暴涨，粗粒度 GPC 分区（[[MIG]]）浪费严重；intra-SM 控制应由硬件/编译器处理，OS 有效粒度是 **TPC**。
  - **依赖假设**：可通过 reverse-engineering 管理 TPC/SM；未来硬件可 native 暴露 TPC 控制。
  - **可能失效场景**：新架构改变 TPC 拓扑或禁止软件重映射；atomization 对某些 kernel 模式失效。
- **观察 2**：kernel 时长从微秒到数十毫秒剧烈变化（LLM 大 prompt、DLRM training），monolithic kernel 调度必然 HoL blocking；需 thread-block 级可抢占单元。
  - **依赖假设**：kernel 可透明拆成 atom（无需 PTX/源码）；atom 预测器在线估计时长足够准。
  - **可能失效场景**：极短 kernel 主导时 atomization 开销可能得不偿失；预测错误导致 TPC stealing 误判。
- **观察 3**：Meta production 多模型频率差异数百倍、请求 diurnal 2.2× 波动，static GPU 分配导致 overprovisioning。
  - **依赖假设**：LC+BE collocate 是主要提 utilization 路径；SLO 以 tail latency 为主。
  - **可能失效场景**：若生产已广泛采用 request-level 隔离 + 充足 overprovision，收益缩小。

## 核心方法

LithOS 在 driver 层 interpose，提供 LibLithOS 模拟 [[CUDA]] API：

1. **Launch queue**：解耦 kernel submission 与 GPU 执行，defer dispatch 以减少 outstanding work。
2. **TPC Scheduler + TPC Stealing**：按 TPC quota 分配；idle TPC 借给其它 workload；用在线 latency predictor + per-TPC timer 限制从长任务偷取。
3. **Kernel Atomizer**：无源码/PTX 地把 kernel 拆成 thread-block **atoms**，降低 HoL blocking，允许 mid-execution TPC 重配。
4. **Hardware right-sizing**：轻量模型动态决定每个 kernel/atom 最小 TPC 数，平均节省约 **1/4** GPU capacity（<4% perf hit）。
5. **Transparent DVFS**：按 in-flight work 调频，平均节省约 **1/4** 能耗（~7% perf hit）。

Rust 实现；对应用完全透明。

## 设计取舍

- **Reverse-engineered TPC 控制换透明度**：不修改 ML 栈，但绑定 NVIDIA 栈与特定硬件代际，可维护性风险高。
- **Atomization + stealing 换 isolation 纯度**：偷来的 TPC 上用较低 hardware stream priority，仍可能有 interference residual。
- **Right-sizing/DVFS 换峰值性能**：需用户/admin 指定可容忍性能损失旋钮。
- **TPC 级隔离**：比 MPS 强、比 MIG 灵活，但不及硬件硬分区安全。

## 实验与结果

- Inference stacking：tail latency 比 [[MPS]] 降 **13×**；比 best SotA 降 **4×**，aggregate goodput **1.3×**。
- Hybrid inference-training：tail latency 比 MPS 降 **4.7×**；比 best SotA 降 **1.18×**，吞吐 **1.35×**。
- Right-sizing：<4% 性能损失下平均节省 **1/4** GPU capacity；DVFS ~7% 损失下节省 **1/4** 总能耗。
- Meta production trace 驱动的 motivation study（Fig.1–6）支撑 workload 假设。

## 批判性分析

### 论证链条

Production measurement（低 utilization、kernel 时长分布）→ TPC 为 OS 有效粒度 → atomization/stealing/right-sizing → tail latency/goodput/energy 实验，逻辑链清晰。从 academic prototype 到 Meta fleet 默认路径的外推仍大——论文是 research OS 而非 shipping NVIDIA driver。

### 假设压力测试

- Latency predictor 错误时 TPC stealing 可能伤害 LC SLO——论文用 timer/limit outstanding atoms 缓解，但极端 bursty 场景未充分覆盖。
- 仅评估 NVIDIA H100 类环境；AMD/TPU 不适用。
- 「透明」依赖 LibLithOS 完整 CUDA 语义覆盖；未覆盖算子可能 silent fallback 或 crash。

### 实验可信度

- Baseline 含 MPS 与多种 SotA research systems；有 inference + hybrid 场景。
- Meta trace 增强动机可信度；实验规模相对 production fleet 仍小。
- 缺少长期稳定性、fault isolation、多租户公平性生产数据。

### 系统性缺陷

- 论文未讨论 driver 崩溃恢复、可观测性、与 K8s/device plugin 集成运维成本。
- Security/fault containment 相对 MIG 的定量对比有限。
- Reverse-engineering 随 GPU 代际更新成本高——论文未讨论。

## 局限与后续工作

- **局限**：绑定 NVIDIA + LibLithOS；predictor/atomization 对 exotic kernel 可能失效；生产 fault 模型未验证。
- **Future work**：硬件 native TPC 调度接口；formal SLO 隔离保证；跨代 GPU 可移植抽象。

## 相关

- **相关概念**：[[GPU-Scheduling]]、[[MPS]]、[[MIG]]、[[CUDA]]、[[LLM-Inference]]
- **同类系统**：[[REEF]]、[[Orion]]、[[AntMan]]、[[Clockwork]]、[[MPS]]
- **同会议**：[[SOSP-2025]]
