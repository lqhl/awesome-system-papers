---
type: paper
name: UEP
full_title: "UEP: Portable Expert-Parallel Communication"
authors: [Ziming Mao, Yihan Zhang, Chihan Cui, Zhen Huang, Kaichao You, Zhongjie Chen, Zhiying Xu, Zhenyu Gu, Scott Shenker, Costin Raiciu, Yang Zhou, Ion Stoica]
venue: OSDI
year: 2026
tags: [mixture-of-experts, expert-parallelism, rdma, communication-library, portability]
source_pdf: "[[osdi26-mao-ziming-uep.pdf]]"
source_md: "[[osdi26-mao-ziming-uep]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# UEP：可移植的专家并行通信

> **原题**：UEP: Portable Expert-Parallel Communication

> **一句话总结**：UEP 发现 MoE 只要求 GPU 及时“发起”细粒度 token transfer，不要求 GPU 直接操作特定 NIC；它把 16-byte routing command 送给多线程 CPU proxy，再由 proxy 发 GPUDirect RDMA 并补齐乱序 NIC 的语义，在 NVIDIA/AMD 与 EFA/ConnectX/Broadcom 上运行，SGLang 吞吐最高提高 40%、AMD training 最高提高 45%，代价是每 GPU 最多 4 个 CPU cores 和新的 host-side correctness/failure surface。

## 问题与动机

[[MoE]] 把专家分散到不同 GPU。Router 对每个 token 在运行时选少数 experts，dispatch 把 activation 发给 expert GPU，combine 再把结果聚合回原 GPU。这是稀疏、动态、细粒度 all-to-all：以 DeepSeek-V3 为例，一个 [[Quantization|FP8]] token activation 约 7 KB，每个 token 可选 8 个 experts（§2.1、图 2）。

传统 [[NCCL]]/RCCL 会先按 destination 打包大 buffer，或逐条发送小消息。前者占 GPU SM cycles 并增加 packing latency，后者难以跑满 NIC。DeepEP 使用 GPU-initiated token-level RDMA，让 GPU 一边计算 routing、copy/convert，一边直接给 NIC 发命令，还能做 token deduplication 和 hierarchical reduce，性能更好（图 3–4）。

但 DeepEP 的 NVIDIA IBGDA 路径让 GPU kernel 直接写 NIC MMIO/driver interface，并假定特定 write/atomic ordering。换成 AMD GPU、AWS EFA 的 unordered SRD，或 Broadcom NIC 时，GPU 指令、doorbell、atomic 和 delivery semantics 都要重新组合。论文把支持成本概括为 `m` 种 GPU × `n` 种 NIC 的 `O(m×n)` 垂直适配。

## 关键观察 / 隐含假设

- **观察 1：GPU 必须决定 token routing，但不必亲自管理 NIC。** Routing 结果在 GPU 上动态产生；只要 command 很快送出，CPU 可以代为 post work request，payload 仍在 GPU 之间用 [[RDMA]] 直传（§3、图 5）。
- **观察 2：控制消息很小，CPU–GPU channel 可以追上 token rate。** UEP 的 TransferCmd 只有 128 bits；论文目标是承受 400G、7 KB activation 下约 7 Mops/s/GPU 的 command rate（§1、§3.1）。
- **观察 3：EP 需要的是局部语义，不是全局强顺序。** LL mode 只要求某 expert 的 X 个 writes 完成后再更新 counter；HT mode 只要求同一 ring channel 内按序。CPU receiver 可以用 immediate data 和小 control buffer 补这些语义，无需 NIC 为所有包提供强 ordering（§3.3）。
- **观察 4：GPU server 的 host CPU 常有余量。** 论文引用的工业数据为 20%–45% CPU utilization，一个训练团队的 Megatron-LM 平均仅 14.5%。这使“每 GPU 最多 4 个 pinned proxy cores”看起来可接受（§1、§3.2）。
- **隐含假设 1：NIC 至少提供可靠 RDMA 与接收端 metadata。** UEP 需要 RC/SRD 一类 reliable delivery、host-side verbs 和 immediate data；没有这些能力的新 NIC 仍需专门 transport。
- **隐含假设 2：CPU proxy 足够稳定。** OS scheduling、NUMA、PCIe、cache coherence 和 proxy polling 不能制造长尾。CPU-heavy preprocessing 或 inference 会削弱“空闲 cores”前提。
- **隐含假设 3：应用能接受 DeepEP 的 LL/HT 通信模型。** UEP 是 DeepEP-compatible drop-in，不是任意 collective 或任意动态 communication graph 的通用替代。

## 核心方法

### 1. 把 initiation 与 execution 分开

GPU kernel 仍按 token 粒度产生通信操作，但只向共享 FIFO 写 compact TransferCmd；CPU proxy 读取 command，做 address translation、bounds check、QP/NIC 选择，再通过 libibverbs 发 [[GPUDirect-RDMA]]。数据 payload 从源 GPU 直接到目标 GPU，不经过 CPU copy（图 5）。

因此，新 GPU 主要移植 GPU-side channel 与 EP kernel；新 NIC 主要接入已有 host verbs provider。论文称 AMD GPU 与 AWS EFA 的移植合计约 3 person-months，并把架构成本从 pair-wise `O(m×n)` 降到按 GPU 的 `O(m)`。这是有三个 NIC family 支持作依据的工程论断，不是对任意硬件组合的复杂度证明（§4）。

### 2. 16-byte lock-free FIFO 承载四种 command

每个 TransferCmd 为 16 bytes，一次 GPU instruction/MMIO transaction 可写入，包含 peer、source/destination offset、length、sequence 等。FIFO 由 GPU producer 推 head、CPU consumer 推 tail；head 放在 CPU memory 便于 CPU poll，tail 放在 GPU memory 便于 GPU 检查，从而避免一方 busy-poll 时反复跨 [[PCIe]]（图 6、§3.1）。

一块 GPU 有多个 FIFO，要求顺序的 commands 必须进入同一 queue，减少 GPU threads 对单 queue 的 contention。`kMaxInflight` 同时充当 backpressure：CPU 放慢 `Pop` 后 FIFO 填满，GPU 的 `Push` 会等待。双方访问 metadata 时绕过或 flush cache，避免看到 stale head/tail。

UEP 支持四种 command：`Write` 发 payload，并可 piggyback completion atomic；`Atomic` 更新 remote flag/counter；`Drain` 等待指定 index 前的 outstanding RDMA；`Barrier` 做 all-peer 或 same-rail synchronization。后两者会让 GPU 通过 `Check-completion(Idx)` 阻塞等待（§3.1）。

### 3. 多线程 proxy 隐藏 NIC 差异

每 GPU 一个 proxy，最多 4 条 CPU threads，每条 pin 到一个 core。第 `i` 条 local thread 只连接 remote proxy 的第 `i` 条 thread，限制 connection 数；同一 thread 同时 poll send/receive completion。Proxy 维护 symmetric memory base address，GPU command 只传 offset。例如 2 GB、16-byte aligned buffer 只需 27-bit offset，而不是 64-bit virtual address（§3.2）。

Proxy 还能 round-robin 多个 QPs，并聚合多 NIC：AWS H200 testbed 每 GPU 有两块 200G EFA，UEP 用 CPU threads 合成接近一块 400G NIC 的带宽。这个设计把 NIC-specific outstanding limit、QP placement 与 future pacing 从 GPU kernel 移到 host。

### 4. Receiver 用 immediate data 实现最小必要顺序

EFA SRD reliable 但不保证顺序，也没有硬件 RDMA atomic。UEP 让 write 携带 32-bit immediate data，receiver CPU 从 completion 中取得 expert/channel、sequence、offset/value 等压缩信息，再决定何时应用 host-pinned counter（§3.3、§4.1）。

LL mode 要 partial completion fence：某 expert 的 atomic 必须等对应 X 个 token writes 到达，但 token 之间无需有序。Receiver 暂存 atomic，计数满足才更新。HT mode 用通常 32 tokens 的 ring chunks，要求同 channel 的 head/tail update 按序；乱序 atomic 先放 control buffer，前序 writes/atomics 完成后再依次应用。

选择 receiver 端而不是 sender 端等待 completion，可少一个 RTT。Emulated atomic 还可和 write 共用一个 message；DeepEP 式 write+hardware atomic 要额外 NIC operation（图 7、18）。

### 5. 保留 LL/HT kernel，并移植到 AMD

LL 针对 decode 小 batch，token 一产生就发；HT 针对 training/prefill 大 batch，增加 batching、deduplication、intra-node forwarding 和 hierarchical reduce。UEP 延续 DeepEP API，SGLang、[[vLLM|vLLM]]、Megatron-LM、AMD Primus 无需改 model code（§3.3、§4）。

AMD port 把 CUDA/PTX atomic、fence、timer 换成 ROCm 版本，把 32-thread warp 改成 64-thread wavefront，并替换 TMA/copy 与 role assignment。GPU kernel 仍需移植，但 NIC proxy code 不必为 AMD×EFA、AMD×Broadcom 等每一对重写（§4.2）。

## 设计取舍

- **可移植性换 host cores。** 最多 4 proxy threads/GPU；8-GPU node 就可能长期占 32 cores。SGLang 实验中整体 CPU utilization 从 8% 增到 22%。
- **GPU 简单化换共享状态协议。** FIFO head/tail、cache flush、immediate-data encoding、control buffer 和 host counter 形成新的 CPU/GPU memory-ordering surface。
- **最小局部 ordering 换实现复杂度。** 避免昂贵全局强顺序，但 LL/HT 和每个 channel 都要定义、测试自己的 fence 条件。
- **多线程吞吐换小消息 latency。** 4 threads 能跑满 EFA，LL 小 batch 在 ConnectX-7 IB 上仍稍慢于 GPU-direct DeepEP/PPLX。
- **通用 verbs 换最小 NIC 前提。** libibverbs/immediate data 覆盖 EFA、ConnectX、Broadcom，但不代表所有 future NIC 的 atomic、failure 和 congestion semantics 相同。
- **DeepEP compatibility 换范围。** UEP 复用成熟 EP kernel 和应用接口，却继承 ring buffer、transport memory 与 LL/HT mode 的设计约束。

## 实验设计

UEP 在 DeepEP 上增加 20.8K 行 C++（其中 2.4K CUDA/ROCm）和 1K Python。所有 testbed 来自 public cloud（表 2）：4×8 H200+EFAv3、4×8 B200+EFAv4、4×8 H100+ConnectX-7、2×1 GH200+ConnectX-7、4–16×8 MI300X+ConnectX-7，以及 4×8 MI300X+Broadcom Thor-2。网络从每 NIC 200G 到 400G。

Baseline 按平台变化：NVIDIA collective 用 NCCL，AMD 用 RCCL；GPU-initiated NVIDIA/IB 用 DeepEP；EFA 上用 PPLX 和 single-thread CPU-assisted IBGDA；AMD/IB 用 Mori。相同 GPU SM/CU 数被保留，但没有一个 baseline 能横跨全部平台，这正是 portability 问题，也让跨图倍数不能直接相乘（§5.1）。

## 实验与结果

- **AMD training 提升相对 RCCL，但 16-node NIC 口径在论文内冲突。** 图 8 的 DeepSeek-V3 是 32 layers、379B parameters 的 downscaled model；16 servers 上 UEP 的 TFLOPS/GPU 高 7%–36%，tokens/s 高 7%–45%。图 8 caption 与表 2 指向 `AMD_IB`（MI300X+ConnectX-7），而摘要、Introduction 和 Conclusion 称“16-node AMD+Broadcom”；Broadcom testbed 在表 2 只有 4 servers。因此 45% 结果不能无条件写成“16-node Broadcom”（图 8、§5.2.1）。
- **H200/EFA training 相对 NCCL 提高 12%–24%。** 4 servers、32 H200、EFAv3 上，Qwen3-235B long-seq/large-batch 的 TFLOPS/GPU 分别高 22%/12%；12-layer、约 135B 的 truncated DeepSeek-V3 高 24%。DeepEP 无法在 EFA 上运行，所以这里证明 UEP 优于 coarse NCCL，不是与 DeepEP 的同硬件端到端 A/B（表 3、§5.2.2）。
- **SGLang 的 40% 来自 prefill-heavy Qwen EP32。** Input/output length 为 4,096/5。DeepSeek-R1 EP16 中 UEP 为 46K tok/s，比 NCCL 高约 5%；UEP 扩到 EP32 为 74K，相对自己的 EP16 为 1.6×，但 NCCL 当时不能跑 EP32。Qwen3 EP32 中 UEP 为 62K、NCCL 为 44K，即高约 40%；同时 CPU utilization 8%→22%（图 9、§5.2.3）。
- **Microbenchmark 显示 portability 不是所有 mode 都免费。** EFAv3 EP32 的 medium/large token count 下，UEP dispatch latency 比 PPLX 低 2.3×，combine 低 1.1–1.5×；论文还偏向 PPLX 地忽略其 BF16→FP8 conversion。ConnectX-7 IB 的 LL mode 中 UEP 略慢于 DeepEP/PPLX；HT dispatch 与 DeepEP 在 5% 内，同时比 PPLX dispatch/combine 低 2.1×/1.6×。GH200 只测不太实用的 EP2 LL（图 10–13、§5.3.1）。
- **跨 AMD NIC 的主要证据是 4-node microbenchmark。** EP32 下，UEP 能同时运行在 MI300X+Broadcom 和 MI300X+ConnectX-7；两者 LL/HT latency 相近，HT combine 还优于 Mori/IB，Mori 在 LL 略快。它支持“同一 GPU port 复用不同 NIC proxy”的 claim，但没有 AMD+EFA、Intel NIC 或更大 Broadcom application result（图 14、§5.3.2）。
- **Channel/proxy 消融支持 4-thread 设计，也暴露下一代风险。** 8 个 FIFO 同时测试可到约 8 Mops，FIFO/proxy latency 约 3–5 µs，而典型 LL/HT 为约 200 µs/大于 2,000 µs。1→4 proxy threads 明显降低 LL/HT latency；emulated atomic 接近 write-only，hardware write+atomic 多约 1 µs。作者只推测 lightweight batching 可支持 800G，尚未测试（图 15、17–18、§5.4）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CPU proxy 可以保留 GPU-initiated token-level EP 的主要性能 | EFA micro 比 PPLX 好；IB HT dispatch 与 DeepEP 在 5% 内；FIFO 约 3–5 µs | LL/IB 仍略慢；最多 EP32、400G | 强 |
| 一套架构可以跨 GPU 与 NIC vendor | NVIDIA/AMD 加 EFA/ConnectX/Broadcom 六类 testbed | Intel 仅实现声明；不是所有 GPU×NIC 组合都实测 | 中强 |
| UEP 改善真实 training 与 serving | AMD training +7%–45%，H200/EFA +12%–24%，Qwen SGLang +40% | 多数相对 NCCL/RCCL；模型有 downscale/truncation | 强 |
| 开发成本从 `O(m×n)` 降为 `O(m)` | AMD 与 EFA port 自报 3 person-months，NIC logic复用 | 复杂度是架构论证；新 NIC 仍需 verbs/provider 与语义适配 | 中 |
| CPU proxy 在更大规模、故障和拥塞下仍透明 | §6 把 congestion control、elastic EP 列为 future work | 无 fault injection、incast、EP大于32或800G实验 | 弱 |

## 批判性分析

### 论证链条

UEP 的抽象切分很有力量：routing decision 与 fine-grained initiation 留在 GPU，NIC management 与语义适配交给更通用的 CPU。16-byte FIFO、4-thread scaling、receiver-side ordering 和 emulated atomic 各自有消融；NVIDIA/AMD 与三类 NIC 又证明这不是只在一对硬件上工作的概念。

不过，`O(m)` 不是完全消除组合适配。新 GPU 仍需移植 EP kernel、wave/warp、atomic 与 copy engine；新 NIC 仍需 work request、QP/CQ、inflight limit 和 immediate-data semantics。论文真正证明的是“把大部分 pair-specific work 收敛到两个较清楚的接口”，而不是每个新设备零成本加入。

端到端结果也主要比较 NCCL/RCCL，因为 DeepEP 无法跑 EFA/AMD。它们缺少 token deduplication 和 hierarchical reduce，所以提升同时来自 fine-grained EP algorithm 与 portable transport，不能只归因于 CPU proxy。

### 假设压力测试

UEP 的 CPU surplus 假设在 data preprocessing、tokenization、storage、network stack 或 CPU offload 已经很重的 serving node 上可能失效。每 GPU 4 cores 在 8-GPU node 是 32 pinned cores；proxy 与应用跨 [[NUMA]]、OS jitter 或 thermal throttling 都可能进入 token critical path。SGLang CPU utilization 8%→22% 已显示成本不为零。

7 Mops/s/GPU 的目标与 8 Mops FIFO test 很接近。若 800G、小于 7 KB activation、top-k 更大或更多 QPs 把 command rate翻倍，现有 channel 余量有限。作者建议 batching，但 batching 又会损害 LL mode 的即时发送。

Correctness 依赖 GPU/CPU cache bypass/flush、同 channel ordering、immediate-data encoding 和 host counter visibility。弱 memory model、queue wraparound、proxy restart、duplicate completion 或 SRD retry 可能打破 head/tail 与 write-before-atomic 关系；论文没有形式化模型或 fault test。

### 实验可信度

测试硬件非常广：H200/B200/H100/GH200/MI300X，EFAv3/v4、ConnectX-7、Broadcom，且包含 training、serving、LL/HT micro 和 component drill-down。Baseline 按平台选可用最佳方案，PPLX 比较还忽略 conversion cost，整体并不刻意偏袒 UEP。

但硬件广不等于每个 claim 都大规模验证。Broadcom 只有 4 nodes 的 microbenchmark；GH200 只有 EP2；application 最大 EP32；无 multi-rack、incast 或 failure。AMD training 的 16-node 平台在论文内部更有直接冲突：Figure 8/表 2 写 AMD_IB，摘要/结论写 AMD+Broadcom。页面应以详细方法为准，并把不一致保留为证据质量问题。

模型也做了缩减：AMD DeepSeek-V3 为 32-layer/379B，H200/EFA DeepSeek 为 12-layer/约135B。SGLang 是 4,096-input/5-output 的 prefill-heavy case，不能代表 decode-heavy LL tail。40% headline 只来自 Qwen EP32；DeepSeek EP32 没有 NCCL baseline。

### 系统性缺陷

CPU proxy 成为每块 GPU 的通信控制点。虽然论文说 CPU/GPU 通常 fate-share，但 proxy process hang、core starvation、wrong QP state 或 completion backlog 可以在 GPU 正常时单独发生。Current system 仍假设 RDMA 操作成功；elastic EP、failure handling 和 congestion pacing 都在 future work（§6）。

UEP 增加 20.8K C++ 与 GPU/host shared protocol。LL/HT、多个 FIFOs/QPs/NICs、per-channel sequence 和 remote host counter 让 debug 跨 CPU、GPU、NIC 三层进行。没有端到端 checksum、replay protection、timeout/retry state machine 或可观测性数据。

资源评价主要是 throughput/latency 与平均 CPU utilization，没有 proxy cores 的 energy、云成本、P99 CPU scheduling delay 和与应用的 cache/memory-bandwidth interference。若 32 cores 不能视作闲置，UEP 的 cost/performance 优势会缩小。

## 局限与后续工作

- 修正并复测 16-node AMD+Broadcom/AMD+ConnectX 平台口径，分别报告 NIC、topology 和完整 model configuration。
- 在 EP64/128、多 rack、800G 和更小 activation 上测 FIFO headroom、CPU cores、P99 dispatch/combine 与 incast。
- 注入 proxy crash/hang、CQ overflow、duplicate/out-of-order completion、packet retry 和 GPU reset，验证 timeout、retry 与 queue recovery。
- 为 TransferCmd、FIFO wraparound 和 LL/HT partial ordering 建立形式化 memory/transport model，并做 cross-platform litmus tests。
- 在 CPU-heavy serving/training node 上测 NUMA、scheduler jitter、cache/memory bandwidth、energy 与云成本，不只报告平均 utilization。
- 将 CPU pacing、multi-QP congestion control 和 elastic EP 从讨论变成实现，并与 NIC-native control 比较 tail latency。
- 增加 decode-heavy SGLang、full DeepSeek-V3 和未缩减的长时间 training，验证 model quality 与训练稳定性。

## 相关

- **相关概念**：[[Expert-Parallelism]]、[[MoE]]、[[RDMA]]、GPUDirect RDMA、GPU-initiated communication、partial ordering
- **相关系统**：DeepEP、[[NCCL]]、RCCL、PPLX、Mori、[[SGLang]]、[[Megatron]]
- **同会议**：[[OSDI-2026]]
