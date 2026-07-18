---
type: paper
name: GPreempt
full_title: "GPreempt: GPU Preemptive Scheduling Made General and Efficient"
authors: [Ruwen Fan, Tingxu Ren, Minhui Xie, Shiwei Gao, Jiwu Shu, Youyou Lu]
venue: ATC
year: 2025
tags: [gpu-scheduling, gpu-preemption, context-switch, latency-critical, resource-colocation]
source_pdf: "[[atc2025-fan.pdf]]"
source_md: "[[atc2025-fan]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# GPreempt: GPU Preemptive Scheduling Made General and Efficient (ATC 2025)

> **一句话总结**：GPREEMPT 的关键判断是 GPU 上 LC task 到来前通常有 CPU data preparation / CPU-GPU transfer 这段可利用窗口，因此它把 NVIDIA / AMD 驱动里的 timeslice 机制改造成通用 [[Preemption]] primitive，再用 hint-based pre-preemption 把约 100-200 µs 的 switch overhead 藏进准备阶段，使 NVIDIA A100 上 LC 平均延迟相对 LCO 只增加 2.4%、单 LC workload 的 preemption latency 低于 40 µs，同时避开 reset-based 方案对 idempotent kernel 的依赖。

## 问题与动机

GPU co-location 的基本矛盾是：LC（latency-critical）任务需要接近独占 GPU 的 tail behavior，BE（best-effort）任务又需要填满 LC 间隙以提高利用率。论文把应用场景放在 real-time recommendation、autonomous driving、VR 这类 LC 任务，以及 offline inference、data analytics、scientific computing 这类 BE 任务的混部上。这里的目标不是一般性的 GPU batch scheduler，而是当 LC 请求到达时，如何尽快从 BE 手里拿回 compute engine。

已有 [[GPU-Scheduling]] preemption 方案在 generality 和 latency 之间卡住。Wait-based 方案（kernel-level / block-level / checkpoint-based）不破坏 BE kernel 的正确性，但要等正在运行的 kernel 或 thread block 到达边界；论文的动机实验里 block-level preemption 在 workload C 上仍带来 66.4%（约 5 ms）的 LC latency increase。Reset-based 方案（如 REEF、Chimera）能直接杀掉 BE kernel，但只适用于可以安全重算的 idempotent DNN operators；graph computing、scientific computing、以及 [[CUDA-Graph]] 这种把多个 kernel 组织成图的执行方式都会让 reset 的正确性与恢复成本变脆。

GPREEMPT 想做的是第三条路：像 CPU 一样依靠 [[Context-Switch]] 做 switch-based preemption。难点在于 GPU 没有用户可见的 yield interface，而且 GPU context 很大；论文以 NVIDIA A100 为例估算单 GPU context 约 44.3 MB，context save 即使受 HBM bandwidth 支撑也不是零成本。因此，论文的核心不是“发现 context switch 可以 preempt”，而是把一个未文档化的 hardware timeslice 轮转机制包装成可控 yield，再把无法消除的切换成本尽量 overlap 掉。

## 关键观察 / 隐含假设

- **观察 1：GPU driver / hardware 已经有可被复用的 timeslice resource allocation。** 论文通过分析 NVIDIA open GPU kernel module，发现 GPU 会按每个 task 的 timeslice 在 task 间轮转；GPREEMPT 把 BE task 的 timeslice 设短、LC task 的 timeslice 设长，从而让 BE 在 LC 到达后最多一个 BE timeslice 内被动 yield。
  - **依赖假设**：目标 GPU driver 暴露或可 patch 这类 timeslice 配置，硬件 scheduler 对 timeslice 的行为稳定，并且 BE tasks 能被放进同一 scheduling group，避免没有 LC 时也被频繁切换。
  - **可能失效场景**：closed driver、driver version drift、MIG / MPS / 云厂商虚拟化层、或未来 GPU 改掉 scheduling group 语义时，这个 primitive 可能不可用或不可预测。

- **观察 2：LC GPU kernel 前通常存在 data preparation / data transfer 窗口，可作为即将需要 GPU 的 hint。** 许多 LC pipeline 在 kernel launch 前有 CPU preprocessing；即使最小 CPU-to-GPU `cudaMemcpy` 也约 80 µs。CPU、copy engine 与 GPU compute engine 可并行，因此这段时间可以提前触发 preemption。
  - **依赖假设**：LC 应用能在 data preparation 开始时发出 reservation command，且准备阶段足够长或可预测。论文的 Figure 7(a) 显示 data prepare time 超过 100 µs 后，额外 latency 稳定到 40 µs 以下。
  - **可能失效场景**：LC 请求几乎没有 CPU preprocessing、数据已经在 GPU 上、准备时间高度抖动、或应用无法改造以暴露 hint 时，pre-preemption 的收益会下降，只剩 switch-based preemption 本身约 100-200 µs 的额外成本。

- **观察 3：对很多非幂等 workload，reset-based preemption 的低延迟不是可用选项。** 论文用 scientific computing workload Y 和 graph computing workload Z 说明，BE 执行过程中会修改全局状态，杀掉重跑无法保证语义正确；[[CUDA-Graph]] 还会让 reset 范围和恢复成本更难界定。
  - **依赖假设**：switch-based context save/restore 对这些 workload 的 correctness 足够透明，且 driver 层 context 包含了 kernel 继续执行所需状态。
  - **证据强度**：中。实验覆盖了 graph / scientific synthetic workload，但没有系统展开 unified memory、multi-GPU communication、library runtime state、错误恢复等更复杂状态。

- **假设 1：preemption 的主要瓶颈是 BE yield latency 与 context-switch cost，而不是 LC queueing / admission / 多优先级策略。**
  - **证据强度**：中。论文在 7 类 workload 上测了平均 LC latency 与 throughput，但调度策略本身比较简单；多个 LC class、priority inversion、tenant fairness、starvation 没有成为主要实验对象。

## 核心方法

GPREEMPT 的第一层是 **timeslice-based general preemption**。系统初始化时把 BE task 的 timeslice 配成很短，例如 200 µs，把 LC task 的 timeslice 配得足够长，长到 LC task 生命周期内不会被 BE 打断。这样 LC 到达时，正在跑的 BE task 会在平均 `t1/2`、最坏 `t1` 的时间内耗尽 quota 并被硬件轮转出去。LC 完成后，剩余 timeslice 会被自动丢弃，GPU 可以继续执行其他 task。

这个设计回应了观察 1：它没有要求 BE kernel 插 checkpoint，也不要求 BE kernel 可被 reset 后重算，因此比 wait-based / reset-based 更接近 OS 意义上的 [[Context-Switch]] preemption。论文特别强调 BE tasks 放在同一 scheduling group 内，只有 BE 时不会因短 timeslice 互相抢占；短 timeslice 的成本主要在 LC 到达后才显现。

第二层是 **hint-based pre-preemption**。LC task 在 CPU preprocessing 或 CPU-GPU transfer 开始时向 GPREEMPT 发 reservation。GPREEMPT 在 GPU 上注入一个 preemption kernel，用来消耗 BE 的 timeslice 并占住 compute engine；随后它等待 LC compute kernel 准备好。LC kernel 通过 stream semantics 接在 preemption kernel 后面，一旦 preemption kernel 收到结束通知，就立刻开始执行。

通知路径使用 GDRCopy，把 GPU HBM 映射到 CPU address space，让 CPU 以约 1 µs 的延迟通知 preemption kernel 完成。这个机制回应观察 2：context switch 并没有消失，而是被移动到 LC kernel 真正 ready 之前发生。为了避免过早 reservation 让 GPU 空等，GPREEMPT 还支持 scheduled pre-preemption：用户提交预计需要 GPU 的时间点，后台线程按 schedule launch preemption kernel。

实现上，GPREEMPT 包含 driver code modification 和 user-level API。NVIDIA 版本依赖 NVIDIA Open GPU Kernel Module 的 timeslice 修改；AMD 新 GPU 可借助 MES（Micro Engine Scheduler）的 timeslice 机制，较早 AMD GPU 则通过修改 ROCm driver 并复用 debug mechanism 手动切换 context。这个实现路径让它比硬件模拟器方案更接近真实部署，但也把 portability 风险压在 driver / firmware 兼容性上。

## 设计取舍

- **取舍 1：用 driver patch 换 kernel-code transparency。** GPREEMPT 不需要改 BE kernel，也不要求 idempotence；代价是要修改 GPU driver，并依赖 vendor-specific、部分未文档化的 scheduling mechanism。
- **取舍 2：用 application hint 换低 observable latency。** Pre-preemption 把 switch overhead 藏进 data preparation；代价是 LC runtime 需要知道何时 reserve GPU，并承担 hint 过早、过晚、取消或误判时的资源浪费。
- **取舍 3：把 BE 同组以避免 BE-only 开销。** 这使短 BE timeslice 不影响没有 LC 时的 throughput；但也意味着论文没有真正解决 BE tenants 之间的公平性、隔离性和多 priority class 调度。
- **边界条件**：当 LC 有稳定 CPU preparation、GPU driver 可 patch、co-location policy 可控时，GPREEMPT 很优雅；当平台是托管云 GPU、LC kernel 几乎无前置阶段、或系统需要严格多租户隔离 / p99 SLO 证明时，设计会明显变脆。

## 实验与结果

- 实验平台是 Intel Xeon Gold 5420+、256 GB DRAM、NVIDIA A100-40GB；AMD 版本使用相同 CPU / memory 与 AMD Instinct MI100。NVIDIA baseline 包含 LCO、NP、SEQ、WB；AMD 额外包含 reset-based REEF，但受开源实现限制没有 dynamic kernel padding。
- Workload 包含 DISB DNN inference（A-E、REAL）和两个 synthetic non-idempotent workload：scientific computing Y、graph computing Z。DM 任务集合包括 ResNet、DenseNet、VGG、Inception、BERT；GM 包括 BFS、SSSP、PageRank、CC。
- NVIDIA A100 上，相对 LCO，NP、SEQ、WB、GPREEMPT 的平均 LC latency increase 分别是 58.4%、96.3%、15.3%、2.4%。AMD MI100 上，NP、SEQ、WB、REEF、GPREEMPT 分别是 170.1%、297.9%、43.5%、13.2%、10%。
- 总 throughput 以 NP 为 100% 归一化：NVIDIA 上 SEQ、WB、LC-only、GPREEMPT 分别为 66.0%、79.7%、30.3%、88.6%；AMD 上 REEF、SEQ、WB、LC-only、GPREEMPT 分别为 72.4%、53.1%、65.7%、38.8%、82.2%。
- 技术拆解显示，switch-only GPREEMPT 平均 preemption latency 约 200 µs；加入 hint-based pre-preemption 后平均减少约 160 µs。单 LC workload（A、B、C、Z）下 GPREEMPT 平均 preemption latency 低于 40 µs；10 个 LC+BE 并发的 workload E 中平均增加约 500 µs。
- Data preparation sensitivity 显示：无 preparation 时额外 latency 约 100 µs；preparation 超过 100 µs 后额外 latency 降到 40 µs 以下。Scheduled pre-preemption 相比不带 scheduling 的版本提升 BE throughput 4%-10%，GPREEMPT 相比 block-level wait-based preemption 提升 BE throughput 17%-26%。

## Critical Analysis

### 论证链条

论文的主链条是闭合的：wait-based 太慢、reset-based 不通用 → timeslice 可构造低粒度 yield → context-switch overhead 可被 preparation window overlap → 在 A100 / MI100 上同时得到低 LC latency 和较高 BE throughput。最有价值的点是把“GPU 没有 yield”重新表述成“driver 内已有 timeslice，只是缺 interface”，这个 observation 直接支撑了系统设计。

但 “general” 需要拆开看。它在 kernel semantics 上更 general：不要求 kernel idempotent、不插 checkpoint、能覆盖 graph / scientific workload。它在 deployment portability 上并不 general：需要 driver patch、依赖特定 vendor mechanism，并且 artifact 要求 Ubuntu 22.04、NVIDIA Open GPU Kernel Module 550.120、GDRCopy 等条件。论文标题里的 general 更像“对 GPU program transparent”，不是“任意 GPU / 任意云环境可部署”。

### 假设压力测试

最脆的假设是 preparation window。论文证明了当 data preparation 超过 100 µs 时 pre-preemption 很有效；但对于已经把 preprocessing 搬到 GPU、使用 persistent kernel、或数据常驻 GPU memory 的 LC service，hint 可能来得太晚。此时 GPREEMPT 仍能 preempt，但要暴露约 100-200 µs 的 switch-only overhead，是否满足 p99 SLA 取决于应用。

第二个压力点是 hardware generation。论文用 A100 和 MI100 证明机制可在两个 vendor 上实现，但没有覆盖 H100 / MI300、MIG、MPS、SR-IOV vGPU、Kubernetes device plugin、或云厂商驱动栈。未来 GPU context 更大时，论文认为 memory bandwidth 也会增长从而摊平 context save cost；这是合理推断，但不是实验结论。

第三个压力点是多租户 policy。GPREEMPT 主要证明“LC 可以抢 BE”；它没有完整回答多个 LC task 同时到达、多个 priority class、BE starvation、租户隔离、quota accounting、或 preemption abuse 怎么处理。Workload E 的 10-task co-location 是一个起点，但还不是 production scheduler 语义。

### 实验可信度

实验覆盖 idempotent DNN、non-idempotent scientific / graph workload、constant / Poisson / trace arrival，支撑“不是只对 DNN 成立”的 claim。主结果同时看 LC latency 和 aggregate throughput，比只报 latency 更可信；technical analysis 也把 switch-only、pre-preemption、scheduled pre-preemption 的贡献拆开了。

不足是 metric 主要是平均 latency / throughput，缺少 p95 / p99 / p999 SLO、jitter、admission under overload、以及长时间运行下的 fairness。REAL trace 来自 DISB，但论文没有给出更接近云 GPU 多租户的 production trace。Baseline 方面，NVIDIA 平台没有 reset-based REEF 对照；AMD 平台的 REEF 又因为开源实现限制缺少 dynamic kernel padding，所以 reset-based 对照不是完全对称。

### 系统性缺陷

论文未充分讨论 driver patch 的维护成本：driver upgrade、vendor firmware 行为变化、crash recovery、debuggability、observability、以及与 CUDA runtime / HIP runtime 的版本兼容都会影响真实部署。Preemption kernel 占住 GPU 等待 LC readiness 的期间，如果 LC 被取消或准备阶段异常变长，会形成主动制造的 GPU idle；scheduled pre-preemption 缓解了这个问题，但依赖用户估计。

Correctness 方面，switch-based preemption 理论上保留 execution state，因此比 reset-based 适合非幂等 kernel；不过论文没有系统测试 unified memory page fault、NCCL / multi-GPU collective、stream priority、host callback、long-running persistent kernel、或错误恢复场景。Resource isolation 也没有展开：BE 与 LC 是否共享 cache / memory bandwidth，preemption 后 LC 的 cache interference 是否可能推高 tail latency，论文只把 residual latency 解释为 cache interference 并认为相对毫秒级 LC 任务可忽略。

## 局限与 Future Work

- **局限 1**：平台依赖较强。论文证明 A100 / MI100 可行，但没有形成跨 driver version、GPU generation、MIG / MPS / vGPU 环境的 portability matrix。
- **局限 2**：pre-preemption 依赖 LC application hint 和足够长的 preparation window；对 GPU-resident pipeline、persistent serving runtime、或极短 LC kernel，隐藏 overhead 的能力不确定。
- **局限 3**：调度语义仍很薄。论文没有完整处理多 LC priority、tenant quota、BE starvation、preemption abuse、failure recovery 和 observability。
- **Future work 1**：在真实或公开 production trace 上测 p99 / p999 LC latency、BE starvation time、reservation waste，并把 preparation-time distribution 作为一等 measurement。
- **Future work 2**：做 CUDA / HIP runtime 层自动 hint inference，例如从 `cudaMemcpyAsync`、[[CUDA-Graph]] launch 或 framework request lifecycle 推断 reservation，减少 application API 改造。
- **Future work 3**：系统评估 H100 / MI300、MIG、MPS、SR-IOV vGPU、multi-GPU collective、unified memory 等组合，区分“机制不可用”“可用但 overhead 变大”“需要不同 driver hook”。
- **Future work 4**：把 timeslice length、scheduled reservation offset、LC admission control 建模成可在线调参的问题，用 objective 明确约束 LC SLO 与 BE throughput / fairness。

## 相关

- **相关概念**：[[GPU-Scheduling]]、[[Preemption]]、[[Context-Switch]]、[[GPU-Colocation]]、[[Latency-Critical-Inference]]、[[CUDA-Graph]]
- **同类系统**：REEF、Effisha、GPES、Chimera、SRM、[[XSched-OSDI25]]
- **同会议**：[[ATC-2025]]
- **对比**：[[XSched-OSDI25]] 更关注跨 XPU 的统一调度抽象与 portability；GPREEMPT 更像 GPU driver 层的一种低延迟 preemption primitive。
