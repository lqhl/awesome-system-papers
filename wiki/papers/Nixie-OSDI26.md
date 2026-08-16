---
type: paper
name: Nixie
full_title: "Nixie: Efficient, Transparent Temporal Multiplexing for Consumer GPUs"
authors: [Yechen Xu, Yifei Wang, Nathanael Ren, Yiran Chen, Danyang Zhuo]
venue: OSDI
year: 2026
tags: [gpu, memory-management, temporal-multiplexing, llm-inference, scheduling]
source_pdf: "[[osdi26-xu-yechen.pdf]]"
source_md: "[[osdi26-xu-yechen]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 消费级 GPU 的透明时间复用

> **原题**：Nixie: Efficient, Transparent Temporal Multiplexing for Consumer GPUs

> **一句话总结**：当每个本地 ML App 都快占满显存时，Nixie 不让 UVM 在两个工作集间逐页抖动，而是把 kernel admission、整 App 显存驻留和双向迁移统一调度；在 RTX 5090 上，它让交互式代码补全比 nvshare 快 3.1–3.8 倍，并在相同 TTFT 下少用最多 66.8% pinned memory，但频繁交互时会牺牲 23.5% 后台吞吐。

## 问题与动机

消费级电脑开始同时运行本地 [[LLM|LLM]]、图像生成、图像编辑和后台 agent。与数据中心的小模型批量服务不同，这些 App 的 batch 常为 1，工作集各自就接近整张 RTX 4090/5090 的显存。两个 24 GB 模型放进 32 GB GPU 时，空间复用很难成立，只能频繁换入换出。

[[CUDA-UVM|CUDA Unified Virtual Memory]] 虽然透明，但它在 page fault 后先从 GPU 驱逐，再向 GPU 取页，两个 PCIe 方向不能重叠；LRU 只在 fault 时更新，且每份 GPU resident 数据都要有一份不可换出的 CPU pinned backing。论文举例：两个 24 GB 模型在 32 GB GPU 上轮流生成 token，每次至少迁移 16 GB；即使 PCIe 5.0x16 为 64 GB/s，也约需 250 ms，而无迁移 forward 只需 20–75 ms。Nixie 因而把共享问题从“缺页管理”改成“整 App 的时间复用”。

## 关键观察 / 隐含假设

- **观察 1：计算许可与内存驻留必须一起决定。** 若 App 可以随时 launch kernel，而内存系统事后按 fault 补页，多个大工作集必然相互驱逐；先选唯一运行 App，再主动把其工作集准备好，可消除这种抖动（§3）。
- **观察 2：PCIe 是全双工，但 UVM 只用半边。** Nixie 同时排队向上 fetch 和向下 eviction，在 RTX 5090 平台达到 18.4–20.7 GB/s，接近实测上限 21.49 GB/s，而 UVM 只有 9.8–10.3 GB/s（§5.2、图 7）。
- **观察 3：交互性可以从 CUDA API 间隙推断。** 距离最近一次 CUDA API 返回超过 100 ms 时，App 被视为 idle，并立即触发重新调度；持续占满时间预算者降级，经过扣除排队时间后的充分空闲才软恢复优先级，不要求用户标注（§6）。
- **假设 1：工作负载适合整 App 串行化。** Nixie 面向“单 App 几乎填满显存”的场景；多个小模型可以并发 kernel 时，空间复用可能更好。
- **假设 2：安全暂停点会及时到来。** 迁移前 Nixie 禁止新 kernel 并等待 outstanding kernel 完成；很长或卡死的 kernel 会推迟交互 App，论文没有给出最坏抢占延迟。

## 核心方法

**透明控制面。** 每个进程通过 `LD_PRELOAD` 加载 Nixie Shim，拦截 CUDA allocation/free、kernel/graph launch、隐式分配和 `cudaMemGetInfo`。集中式 Nixie Daemon 决定谁可 launch kernel、各内存块在哪一层以及迁移顺序。App 仍用自己的 CUDA context；已经获准且数据齐备时，launch 不经过 daemon。切换前 Shim 阻止新 launch 并执行 CUDA synchronization，避免迁移后 kernel 访问失效页面；CUDA VMM 保留原虚拟地址并重新映射物理内存（§3–§4，图 2）。

**四层唯一副本内存。** 对进入 CUDA VMM 管理的分配，一次 allocation 被切成最大 128 MB 的 chunk，chunk 再切成 VMM 最小物理粒度 2 MB 的 block，避免碎片；小于 2 MB 的分配仍直接使用 `cudaMalloc`。每个受管 block 只在 GPU、CPU pinned、CPU paged、disk 四层之一存在，而不是让 GPU 数据永远保留 pinned backing，因此能节省 host memory（§5.1、§7.1，图 3、图 10）。

**迁移规划与执行分离。** Planner 先计算下一个 App 要进入 GPU 的 block、必须驱逐的非目标 block和每层最终容量，尽量把数据放在最高的可用下层。Orchestrator 分开维护 upward/downward queue，并在 pinned memory 预留 streaming window，让 GPU→CPU eviction 与 CPU→GPU fetch 同时前进；worker threads 负责下层到 pinned 的搬运，Shim 发异步 CUDA copy。Scheduler 已知候选下一个 App 时，还会提前 prefetch 它的数据（§5.2、§6.3，图 4–5）。

**适合 GPU 的 MLFQ。** 最高优先队列的 demotion allotment 为 8 s、preemption threshold 为 4 s，每低一级都翻倍。同优先级 round robin；累计运行超预算则降级，持续 idle 则在扣除排队时间后软恢复优先级。100 ms idle 通知也会立即触发一次调度，而不用等完整 time window。这样短交互任务通常先运行，长 batch 用较长窗口摊薄整 App 迁移成本（§6，算法 1）。

## 设计取舍

- **无 page thrashing 换粗粒度切换。** 整 App 驻留使性能可预测，但每次切换要搬整个工作集；高频细粒度并发不适合。
- **透明性换语义浪费。** Nixie 不知道哪些数据是 immutable weights、[[KV-Cache|KV cache]] 或 activation，因此无法丢弃可重建副本，只能保守搬运。
- **交互延迟换后台吞吐。** 自动优先级在频繁代码补全下把更多 GPU 时间给前台，后台模型吞吐低于 nvshare；这是策略目标，不是免费收益。
- **单用户简化换隔离缺口。** Daemon 与 App 同 UID，迁移数据共用 pinned region；论文把同 UID 进程互读排除在 threat model 外，不适用于多租户。

## 实验与结果

- **主平台与基线**：AMD Ryzen 9 9950X、96 GB DDR5、两张 32 GB RTX 5090（PCIe 5.0x8）、Debian 12、CUDA 12.9；除“2 GPUs”上界外均只用一张卡。App 包括 Ollama、[[SGLang|SGLang]]、llama.cpp、ComfyUI，模型来自 Qwen3、Gemma3、Z-Image、Qwen-Image。基线为 UVM、nvshare、Ollama 和只用于 case study 的 TGS，全文报告平均端到端时间而非尾延迟（§7 setup）。
- **切换与带宽**：相对 UVM/nvshare，Nixie 在 Ollama 配置把 TTFT 降低 44.0%–82.3%，在 SGLang 配置降低 29.7%–36.3%；双向吞吐约为 UVM 两倍。ResNet-18 到 ResNet-152、batch 1 的运行中 inference latency 与 vanilla/简单 UVM hook 基本相同，说明获准运行期间的 launch fast path 开销很小（§7.1，图 6–7、图 10）。
- **Pinned memory**：为得到与 UVM 相同 TTFT，Gemma3 27B-Q8 只需 21.5 GB，而 UVM 用 53.5 GB，减少 59.8%；Qwen3-[[MoE|MoE]] 30B-Q6 只需 15.3 GB，而 UVM 用 46.3 GB，减少 66.8%。结论来自 16–32 GB Nixie pinned budget 的单机曲线，没有测 CPU paged/disk 大量参与时的性能（§7.1，图 9）。
- **跨 App 工作流**：Qwen3-MoE 扩写 prompt 后用 Z-Image/Qwen-Image 生成图片，Nixie 比 nvshare `W=4` 快 1.3/1.4 倍，达到双 GPU 上界性能的 60.4%/65.9%；三模型 planner-worker 工作流中，比 nvshare `W=4/30` 快 1.6 倍。TGS 在 Qwen-Image 上 15 分钟仍未完成，因为其固定高低优先级和 host DMA 假设不适合该 workload（§7.2，图 11–12）。
- **调度消融与代价**：代码补全间隔为 1/3/6 s 时，Nixie 响应 1.8/1.4/1.4 s，nvshare `W=4` 为 4.5–5.7 s，故快 3.1–3.8 倍；Nixie-RR 明显更慢，证明 MLFQ policy 有作用。后台 LLM 在 3/6 s 场景吞吐比 nvshare 高 90.6%/39.5%，但 1 s 频繁场景低 23.5%（§7.2，图 13）。
- **Batch 与硬件外推**：三个 batch job 共跑 300 s 时，Nixie 得到理想吞吐的 85%，接近 nvshare `W=30`；关闭 prefetch 后少约 5%，nvshare `W=4` 只有 49.5%。在 PCIe 4.0x16、24 GB RTX A5000 的第二平台，multi-agent workload 比 nvshare 快 3.4 倍，达到双 GPU 的 73%；作者也观察到旧 driver 的 UVM 更差，因此跨硬件增益掺杂了 driver 版本影响（§7.2–§7.3，图 14–15）。

## 论断—证据表

| 论断 | 直接证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 联合调度 compute 与 memory 能减少 UVM thrashing | 切换 TTFT 降低 29.7%–82.3%，双向带宽约为 UVM 两倍 | RTX 5090、整 App 大模型切换 | 强 |
| 可以在相同延迟下少用 pinned memory | 两模型分别减少 59.8% 和 66.8% | 只测两模型与 16–32 GB budget，disk tier 未覆盖 | 强 |
| 自动优先级能识别交互 App | MLFQ 比 Nixie-RR 延迟低，代码补全快于 nvshare 3.1–3.8 倍 | 人工设置 1/3/6 s 到达间隔，无用户 trace | 中强 |
| 透明机制适配多种未修改 App | Ollama、SGLang、llama.cpp、ComfyUI 和 CUDA graph case 均运行 | Linux `LD_PRELOAD` 原型；未测静态链接、Windows 或全部 CUDA API | 中强 |
| 时间复用仍可维持 batch 公平与吞吐 | 三 job 下达到 ideal 的 85%，prefetch 贡献约 5% | 300 s、三个固定 job，报告平均 throughput | 中 |

## 批判性分析

### 论证链条

论文先量化 UVM 的单向传输和 pinned backing 问题，再用集中 compute/memory 决策、全双工迁移和 MLFQ 分别对应，主链条完整。图 7 直接验证双向带宽，RR/no-prefetch 两个消融也支持 scheduler 和 prefetch。尚未拆开的部分是四层 memory planner：没有关闭“唯一副本”、不同 block/chunk 大小或 pinned streaming reservation 的消融，也没有单独展示 disk tier，因此不能判断复杂层级中每项设计的贡献。

### 假设压力测试

固定 100 ms idle threshold、4 s 抢占阈值和 8 s 降级预算没有敏感性实验。短促但间隔少于 100 ms 的交互 App 可能被当成 batch；长 kernel、CUDA persistent kernel 或卡住的 synchronization 可能让前台等很久。还应测试多个小模型、可 concurrent kernel 的 pipeline，以及工作集只有小幅超出显存的情况，找出时间复用输给空间复用的边界。

### 实验可信度

模型和 App 种类丰富，UVM、nvshare、Ollama、TGS 与双 GPU 上界覆盖了不同方案，且同时报告 TTFT、带宽、pinned memory、前台延迟和后台吞吐。限制是主实验只有一台高端 Linux desktop，第二台是服务器级 A5000；最常见的 Windows 消费环境没有实现。论文按前作只报平均值，没有 P95/P99、迁移 straggler 或连续用户交互 trace；TGS 本身只支持两个手工优先级 App，与 Nixie 目标并不完全等价。

### 系统性缺陷

“无需修改 App”仍依赖 `LD_PRELOAD` 完整拦截 CUDA 行为；静态链接、直接 driver API、未知隐式 allocation 或第三方 runtime 可能绕过 Shim。集中 daemon 的崩溃恢复、迁移中途故障和数据一致性未评测。内存层级允许落盘，但没有给出 disk 参与时的延迟与写放大。共享 pinned region 对同 UID 恶意进程没有隔离。最根本的上限是整 App 切换要经过 CPU-GPU link，Nixie 也只达到双 GPU 上界的 60%–73%，无法代替应用感知的 KV cache 缩放或细粒度空间共享。

## 局限与后续工作

- 在 Windows consumer PC 上实现并测试，补齐静态链接、CUDA Driver API、persistent kernel 和 CUDA graph 组合。
- 用真实桌面交互 trace 报告 P50/P95/P99、最坏抢占延迟和迁移 straggler，而不只报告平均值。
- 分别消融 block size、pinned reservation、paged memory、disk 和 scheduler threshold，画出时间复用与空间复用的分界。
- 为 daemon crash 和迁移中断设计可恢复状态机，并为共享 host memory 增加进程级隔离。

## 相关

- **相关概念**：[[GPU-Memory]]、[[CUDA-UVM]]、[[Temporal-Multiplexing]]、[[MLFQ]]、[[PCIe]]
- **同类系统**：[[nvshare]]、[[TGS]]、[[Prism]]、[[PipeSwitch]]
- **同会议**：[[OSDI-2026]]
