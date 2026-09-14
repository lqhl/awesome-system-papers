---
type: paper
name: Nixie
full_title: Nixie: Efficient, Transparent Temporal Multiplexing for Consumer GPUs
authors: [Yechen Xu, Yifei Wang, Nathanael Ren, Yiran Chen, Danyang Zhuo]
venue: OSDI
year: 2026
tags: [gpu-multiplexing, consumer-gpu, unified-memory, memory-management, gpu-scheduling]
source_pdf: "[[osdi26-xu-yechen.pdf]]"
source_md: "[[osdi26-xu-yechen]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-12
---

# 面向消费级 GPU 的高效透明时间复用（OSDI 2026）

> **原题**：Nixie: Efficient, Transparent Temporal Multiplexing for Consumer GPUs

> **一句话总结**：消费级 GPU 上多个模型的工作集通常共同超过显存，UVM 的按页迁移会造成抖动；Nixie 在应用安全点按 2 MB block 主动搬迁整块工作集，并用 MLFQ 风格调度自动优先交互任务，在 RTX 5090 上将代码补全延迟降低 3.1–3.8×，并将 CPU pinned memory 降低最多 66.8%。

## 问题与动机

消费级机器开始同时运行 LLM、图像生成和图像编辑，但消费级 GPU 的显存相对有限。每个模型的参数、激活和临时空间往往已经接近显存容量，因此多个应用并行时更适合时间复用，而不是把多个模型同时驻留在 GPU 上。

停止应用再重启会触发数十 GB 模型重载。UVM 虽然透明，却依赖缺页后迁移，无法协调计算与内存；两个大模型交替生成时会反复驱逐和取回数据。UVM 还串行使用 PCIe 两个方向，并为 GPU 上的页保留 CPU pinned memory。面向数据中心的系统通常需要修改特定推理框架，也不适用于 ComfyUI 等非 LLM 工作负载。

## 关键观察 / 隐含假设

- **观察 1**：当两个 24 GB 模型共享 32 GB GPU、轮流生成 token 时，每次前向可能至少迁移 16 GB；在 PCIe 5.0x16 上数据搬运约需 250 ms，而无迁移前向仅 20–75 ms（§2.2）。
  - **依赖假设**：应用工作集大到无法共存，且完整工作集驻留后能连续执行一段时间。
  - **可能失效场景**：模型较小、请求可批处理或工作集可稳定共存时，空间复用和批处理可能优于整应用切换。
- **观察 2**：UVM 的缺页和 LRU 信息不足以预测大模型下一步访问；它还只能依次执行 GPU→CPU 和 CPU→GPU 传输（§2.2、图 1、图 7）。
  - **依赖假设**：主动按分配块搬迁能减少重复流量，并能通过计划同时占满双向链路。
- **假设 1**：应用可以在阻止新 kernel、同步已有 kernel 后被安全暂停，且 CUDA VMM 能保持虚拟地址不变。证据强度：强；§4 描述了 CUDA graph、地址映射和同步处理。
- **假设 2**：最近的 kernel/API 行为足以区分交互应用与后台应用。证据强度：中；作者使用 100 ms API 超时，但没有覆盖更广泛的应用行为。

## 核心方法

Nixie 由 LD_PRELOAD 注入的 Nixie Shim 和集中式 Nixie Daemon 组成。Shim 拦截 CUDA 分配、释放、kernel/graph launch、隐式分配及显存查询；Daemon 决定哪个应用运行、数据放在哪一层以及迁移顺序。应用仍使用自己的 CUDA context，减少 kernel launch 的运行时开销（图 2）。

Nixie 不依赖缺页，而是在 `cudaMalloc` 分配层管理 chunk，并把大分配切成最多 128 MB 的 chunk，再切成 2 MB block。每个 block 只存在于 GPU、CPU pinned memory、CPU paged memory 或 disk 的一个位置。调度选中应用后，系统先将其所需 block 搬入 GPU，并将其他应用数据主动下移，使应用开始执行时工作集已经就绪。

迁移分为 planner 和 orchestrator。planner 计算各层最终状态和最小 block 移动集合，优先把无法留在 pinned memory 的 block 提前下移。orchestrator 维护上下行队列，并预留 pinned-memory streaming window，避免向上取数阻塞 GPU→CPU 驱逐（§5.2、图 4–5）。Shim 在迁移前阻止新 kernel 并同步已有 kernel；CUDA VMM 负责在不同物理分配间重新映射稳定的虚拟地址。

调度器采用 MLFQ 风格。高优先级队列使用 8 s time allotment 和 4 s preemption threshold，低优先级参数逐级翻倍。应用在窗口内没有继续发起 kernel 时被视为交互型，窗口缩短并提升优先级；持续占满窗口则降级。队列头部应用还会被预取，以减少下一次切换时间（§6）。

## 设计取舍

- **主动整块迁移换取可预测性**：避免 UVM 的 page-fault thrashing，但迁移决策依赖分配粒度，不能利用 tensor 语义区分权重、激活和 KV cache。
- **透明性换取策略保守**：无需修改应用或驱动，兼容 llama.cpp、SGLang 和 ComfyUI；代价是无法做 Prism、Aegaeon 一类的模型/请求级优化。
- **自动优先级换取可配置性**：无需用户标注交互任务，但 100 ms idleness threshold、8 s/4 s 调度参数可能不适合所有应用。
- **单用户安全模型**：Daemon 与应用共享 UID 和 pinned-memory 区域；恶意同 UID 进程可能读取迁移数据，论文明确不把多租户隔离纳入威胁模型。

## 实验与结果

- RTX 5090、32 GB VRAM、PCIe 5.0x8 上，Nixie 的上下行传输吞吐接近硬件双向上限，约为 UVM 的 2×（图 7）。相对 UVM/nvshare，Ollama 场景 TTFT 降低 44.0–82.3%，SGLang 场景降低 29.7–36.3%（图 6）。
- 在相同 TTFT 要求下，Nixie 只使用 UVM 约 33.2–40.2% 的 CPU pinned memory（图 9），对应最多 66.8% 的节省。
- prompt expansion + ComfyUI 工作流中，Nixie 比 nvshare（4 s window）快 1.3–1.4×；达到双 GPU 理想结果的 60.4–65.9%（图 11）。
- KVCOMM 多智能体工作负载中，Nixie 总体端到端延迟比 nvshare 快 1.6×；数学和代码请求分别快 1.5× 和 1.7×（图 12）。
- 代码补全与长任务共置时，Nixie 平均响应时间为 1.4–1.8 s，较 nvshare（4 s）快 3.1–3.8×；频繁请求场景下后台吞吐反而低 23.5%，明确体现交互性与后台吞吐的取舍（图 13）。三种批处理任务中，Nixie 达到理想吞吐的 85%，预取再带来 5% 提升（图 14）。
- 在 PCIe 4.0x16 的 RTX A5000 集群上，多智能体工作负载比 nvshare 快 3.4×，达到双 GPU 结果的 73%；旧 UVM 实现的 PCIe 空闲更多（图 15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 主动整应用工作集迁移减少切换开销 | 图 6、图 7：TTFT 降低 29.7–82.3%，双向吞吐约为 UVM 2× | RTX 5090；Ollama/SGLang；大模型 | 强 |
| Nixie 降低 pinned-memory 压力 | 图 9：达到类似 TTFT 时仅使用 UVM 的 33.2–40.2% | Gemma3 27B-Q8、Qwen3-MoE；16–32 GB pinned memory | 强 |
| 自动调度改善交互延迟 | 图 13：代码补全 1.4–1.8 s，较 nvshare 快 3.1–3.8×；RR 消融明显变差 | Qwen3-Coder + Gemma3；1/3/6 s 请求间隔 | 强 |
| 透明方案可覆盖多应用工作流 | 图 11–12、15：图像生成、多智能体和 A5000 结果 | Linux、CUDA、指定模型和应用版本 | 中 |

## 批判性分析

### 论证链条

从“工作集超过显存”到“先切换计算、再主动搬迁工作集”的链条是闭合的，图 6–9 同时覆盖切换延迟、带宽和 pinned memory。调度器的收益也有 RR 消融支撑。论文没有证明 Nixie 在工作集可共存或请求可批处理时优于空间复用系统；作者也明确将其定位为大工作集的时间复用。

### 假设压力测试

固定 2 MB block 和 128 MB chunk 对大模型权重较合适，但高频小分配、强随机访问或频繁释放可能增加规划和映射开销。100 ms 超时可能把短暂 CPU 阻塞误判为空闲，或者无法识别 GPU 内部长 kernel 的真实交互性。Nixie 还假设 CUDA 同步可以提供足够安全的暂停点；超长 kernel 会直接拉长响应尾延迟。

### 实验可信度

实验覆盖 LLM、扩散模型、图像生成、多智能体和批处理，并包含 UVM、nvshare、Ollama、TGS 以及双 GPU 上界。主要限制是硬件平台和模型集合较窄，平均端到端时间为主，P99、故障恢复、功耗和长期运维成本未充分报告。TGS 需要显式优先级且只支持两个应用，因此其结果更像兼容性边界，不能完全代表所有调度基线。

### 系统性缺陷

Nixie Daemon 是单点协调者，论文未量化 daemon 故障恢复、进程崩溃后的内存清理和迁移一致性。共享 pinned memory 的安全边界只适合单用户环境。Windows 移植仅是可行性讨论，AMD 支持也未展示实测结果。对 datacenter 的并发请求、KV cache 选择性驱逐和模型语义感知，Nixie 不具备现有专用系统的优势。

## 局限与后续工作

- **局限 1**：策略不理解权重、激活和 KV cache 的语义，可能搬运本可保留或直接释放的数据。
- **局限 2**：当前只做时间复用；多个小模型适合空间复用时，Nixie 可能浪费并行计算能力。
- **后续工作 1**：将迁移粒度和调度决策与模型区域语义结合，比较“整块迁移”和“保留权重/释放 KV cache”在 TTFT、吞吐及 pinned memory 上的 Pareto 曲线。
- **后续工作 2**：在 Windows、AMD GPU、不同 PCIe 拓扑和真实桌面后台噪声下测量 P95/P99 延迟及恢复时间。

## 相关

- **相关概念**：[[Unified Memory]]、[[GPU Multiplexing]]、[[KV-Cache]]、[[MLFQ]]
- **同类系统**：[[nvshare]]、[[TGS]]、[[Prism]]、[[Aegaeon]]、[[SGLang]]
- **同会议**：[[OSDI-2026]]
