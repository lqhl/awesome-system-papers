---
type: paper
name: UEP
full_title: UEP: Portable Expert-Parallel Communication
authors: [Ziming Mao, Yihan Zhang, Chihan Cui, Zhen Huang, Kaichao You, Zhongjie Chen, Zhiying Xu, Zhenyu Gu, Scott Shenker, Costin Raiciu, Yang Zhou, Ion Stoica]
venue: OSDI
year: 2026
tags: [moe, expert-parallelism, rdma, gpu-communication, portability]
source_pdf: "[[osdi26-mao-ziming-uep.pdf]]"
source_md: "[[osdi26-mao-ziming-uep]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-21
---

# 可移植的专家并行通信（OSDI 2026）

> **原题**：UEP: Portable Expert-Parallel Communication

> **一句话总结**：现有 GPU 发起的专家并行通信依赖 GPU 与 NIC 的垂直耦合，UEP 用 GPU-CPU 无锁 FIFO 传递 128-bit 路由命令，再由多线程 CPU proxy 代表 GPU 发起 GPUDirect RDMA，并用 RDMA immediate data 在软件中补足乱序 NIC 所需的部分顺序语义；在 EFA 上 dispatch 吞吐最高达到 PPLX 的 2.1 倍，在 SGLang 上吞吐最高提升 40%，在 AMD+Broadcom 的 16 节点训练上比 RCCL 提升最高 45%。

## 问题与动机

MoE 模型把不同 expert 放在不同 GPU 上。路由器运行时为每个 token 选择少量 expert，系统随后执行 dispatch 和 combine。这种通信具有两个特征：单个 activation 很小（论文以约 7KB 为例），但请求数量多、目的地动态变化。传统 collective 要么逐 token 发送导致小消息效率低，要么先按目的地打包，增加 GPU kernel 和临界路径上的开销。论文指出，专家并行通信可以占前向过程的 43.6%，训练端到端时间的 32%。

DeepEP 等系统使用 GPU-initiated RDMA，让 GPU kernel 直接把细粒度传输命令提交给 NIC，并把数据复制、通信和计算流水化。这种方式保留了 token 级优化，例如 token 去重、节点内转发和分层 reduce，但要求 GPU 访问 NIC 定义的 MMIO 接口，并依赖特定 GPU、NIC 和软件栈的协同设计。GPU-NIC 组合数量从单一供应商扩展到多供应商时，移植工作近似为 O(m×n)。

UEP 的目标不是放弃 GPU 发起的细粒度通信，而是把“发起通信”和“执行通信”拆开：GPU 只提交小型控制命令，CPU proxy 通过 libibverbs 访问 NIC 并代表 GPU 发出 RDMA。这样既保留 token 级流水化，也把硬件差异和传输语义适配集中在 CPU 侧。

## 关键观察 / 隐含假设

- **观察 1：GPU 需要发起细粒度传输，但不需要亲自管理 NIC。** 图 4 显示，随着 token 数量增加，先在 GPU 上打包再做 bulk transfer 的方案会受到 packing 开销影响；GPU-initiated token-level communication 能把传输与计算、复制重叠。
  - **依赖假设**：GPU 到 CPU 的控制通道足够快，且 CPU 有空闲核心处理大量小命令。
  - **可能失效场景**：CPU 已被数据预处理、调度或其他服务占满，或者 GPU 与 CPU 通过较慢的 PCIe 路径连接时，proxy 可能成为新的瓶颈。

- **观察 2：异构 NIC 的差异主要体现在传输语义，而不只是带宽。** ConnectX 的 RC transport 提供有序语义，而 EFA 的 SRD 可靠但允许乱序；LL 模式需要“写入达到一定数量后再应用 atomic”，HT 模式需要按通信 channel 保持写入与 ring-buffer 指针更新的部分顺序。
  - **依赖假设**：NIC 至少提供可靠 RDMA 和可携带少量控制元数据的机制，例如 immediate data。
  - **可能失效场景**：设备缺少可靠传输、远端 completion 通知或 immediate data，UEP 的 CPU 侧补偿无法独立恢复这些能力。

- **假设 1：CPU 资源是可消耗的通信资源。** 论文引用生产 GPU 集群 20%–45% 的 CPU 利用率，并在实验中使用每个 GPU 最多 4 个 pinned CPU threads；EFA 上从 8% 增至 22% 的 CPU 利用率。
  - **证据强度**：中。论文在多个平台上测量了 CPU 开销，但没有在 CPU 与 GPU 共享的复杂生产工作负载下评估隔离和争用。

- **假设 2：每条需要顺序的通信流可以映射到单个 FIFO channel。** UEP 不保证跨 FIFO 的全局顺序，把必须排序的消息放到同一 channel，再由接收端按 sequence number 缓存和释放 atomic。
  - **证据强度**：强。设计和 §5.4 的 EP=16 到 EP=32 测试都明确采用这种局部顺序模型；但更大 EP 或更不均匀的路由分布仍未覆盖。

## 核心方法

UEP 为每个 GPU 建立多个 GPU-to-CPU 无锁 FIFO。GPU 线程写入 128-bit `TransferCmd`，命令包含目标 peer、源和目的 buffer offset、长度以及 sequence number。CPU proxy 使用 `Poll` 读取命令，发出 RDMA work request，再用 `Pop` 释放 FIFO 槽位；GPU 可以用 `Check-completion(Idx)` 查询某个命令是否已被消费。head 放在 GPU 更常读取的位置，tail 放在 CPU 更常读取的位置，以减少反复跨 PCIe 读取。

每个 GPU 配置一个多线程 CPU proxy，线程固定到 CPU core。对称内存让 GPU 只传 offset，proxy 在连接建立时交换 base address，并负责地址转换与边界检查。多条 FIFO 减少 GPU 线程竞争；代价是跨 FIFO 不再天然有序，调用方必须显式把有序命令放入同一 channel。

UEP 支持四类基础命令：`Write` 传输 payload，可附带 atomic；`Atomics` 更新远端计数器或 doorbell；`Drain` 等待 RDMA 操作完成；`Barrier` 建立全 peer 或同 rail 同步。数据仍由 GPU memory 直接通过 GPUDirect RDMA 传输，CPU 主要处理命令和完成队列，因此没有退化为传统的 CPU 打包方案。

对于 EFA 这类允许乱序交付的 NIC，UEP 把 sequence number 放入 RDMA immediate data。接收端 CPU proxy 记录每个 expert 已收到的 write 数量，把尚未满足条件的 atomic 暂存到 control buffer。LL 模式只要求某一 expert 的若干 write 先完成；HT 模式则按 channel 逐步释放 ring-buffer head/tail 更新。论文选择在接收端执行这些检查，避免发送端等待额外 RTT；图 7 显示接收端方案优于发送端方案。

UEP 保留 DeepEP 风格的两种通信模式。LL 面向小 batch、decode 型工作负载，尽快发送每个 token；HT 面向 prefill 和训练，使用 chunk、token 去重、节点内转发及分层 reduce，以换取更高吞吐。已有的 [[DeepEP]] 优化因此可以在新的 GPU-NIC 组合上复用，而无需修改上层模型代码。

## 设计取舍

- **用 CPU 换取可移植性。** CPU proxy 消除了 GPU 对 NIC 私有 MMIO 布局的直接依赖，但引入了 CPU 核心占用、线程调度和 GPU-CPU 控制通道开销。NV_EFA3 上 FIFO 开销约 3–5 µs，而 LL 通信约 200 µs、HT 通信超过 2000 µs；小消息场景仍可能暴露这项成本。
- **软件模拟部分顺序，而非要求 NIC 提供强一致语义。** 这让 UEP 能运行在 EFA 上，并且模拟 atomic 的延迟接近纯 RDMA write；代价是接收端需要维护 control buffer、sequence state 和条件检查，系统实现与调试复杂度转移到了软件。
- **只提供局部顺序。** 每条通信 channel 内有序可以避免全局硬件排序成本，但对应用的 channel 映射提出约束。负载严重倾斜时，某个 channel 的积压可能影响对应 expert。
- **LL 与 HT 分别针对不同工作负载。** HT 的 batching 和去重提升吞吐，却不适合追求最短单 token 延迟的 decode；LL 更灵活，但论文承认其在 EFA 小消息处理上仍有优化空间。

## 实验与结果

- 在 NVIDIA H200 + EFA 上，UEP 在 Megatron-LM 的三组训练配置中比 NCCL 高 12%–24% TFLOPS：Qwen3 长序列 22%、Qwen3 大 batch 12%、DeepSeek-V3 24%（表 3）。
- 在 AMD GPU + Broadcom NIC 的 16 节点 Primus/Megatron-LM 训练中，UEP 相比 RCCL 的 TFLOPS 提升 7%–36%，tokens/s 提升 7%–45%（图 8）。
- 在 SGLang v0.5.3、EFA、DeepSeek-R1 上，EP=16 时 UEP 达到 46K input tok/s，比 NCCL 高约 5%；EP=32 时达到 74K tok/s。Qwen3 在 EP=32 时达到 62K tok/s，相比 NCCL 的 44K tok/s 高约 40%（图 9）。
- 在 EFA 的 EP=32 微基准中，UEP 相比 PPLX 的 dispatch 延迟最高改善约 2.3×，combine 改善 1.1–1.5×（图 10、图 11）；作者还报告 dispatch 吞吐最高达到 2.1×。
- 在 CX7 InfiniBand 上，UEP 的 HT dispatch 延迟与 DeepEP 相差不超过 5%，并比 PPLX 的 dispatch 和 combine 分别快 2.1× 和 1.6×（图 12）。在 LL 小消息下，UEP 因 CPU proxy 略慢于 DeepEP 和 PPLX。
- FIFO 在 8 Mops 负载下仍能处理现代 MoE 工作负载，且队列延迟约为网络延迟的一个数量级以下（图 15）。把 CPU proxy 从 1 个线程增加到 4 个线程可明显改善性能（图 17）；EP 从 16 增至 32 时延迟只温和增加（图 16）。
- 模拟 atomic 的延迟接近纯 write；相比额外发出 RDMA atomic，后者在 8B–4KiB payload 上约多 1 µs（图 18）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CPU proxy 能保留 GPU-initiated EP 的吞吐 | EFA 上 dispatch 最高 2.3× 优于 PPLX；CX7 HT dispatch 与 DeepEP 相差不超过 5%（图 10、图 12） | 主要覆盖 EP=16/32、约 7KB token、公开云测试床 | 强 |
| UEP 能跨 GPU 和 NIC 供应商运行 | AMD+Broadcom、NVIDIA+EFA、NVIDIA+InfiniBand、GH200 均可运行（表 2、图 13、图 14） | 供应商组合仍有限，未覆盖故障、动态扩缩容和长期运行 | 强 |
| CPU 侧可模拟所需 delivery semantics | EFA 乱序传输上使用 immediate data 和 control buffer；模拟 atomic 接近 write-only 延迟（§3.3、图 18） | 前提是可靠 RDMA 与 immediate data 可用 | 中到强 |
| 上层训练和 serving 可以直接获得端到端收益 | SGLang 提升最高 40%，AMD 训练 tokens/s 提升最高 45%（图 8、图 9） | SGLang 主要是 prefill-heavy；EFA 上缺少 DeepEP 对照，部分对比只能使用 NCCL | 中到强 |

## 批判性分析

### 论证链条

论文的主链条基本闭合：MoE 需要细粒度 GPU 发起通信；GPU 直接操作 NIC 造成供应商耦合；CPU 适合通过通用接口访问 NIC，也能处理控制语义；FIFO 和多线程 proxy 把新增开销压到网络延迟的一小部分；跨平台实验显示性能和端到端收益。UEP 并未证明所有 GPU-initiated 优化都能无损迁移，而是证明一组 DeepEP 风格的 LL/HT 内核可以迁移。

最需要限定的是“可移植”的范围。论文展示的是 NVIDIA、AMD、EFA、InfiniBand 和 Broadcom 的若干静态组合，不是对任意 GPU/NIC 的自动适配。支持新设备仍需要实现 GPU 侧 channel、CPU 侧 libibverbs provider 以及相应的内存一致性和 completion 语义。

### 假设压力测试

CPU 空闲是 UEP 的核心资源假设。论文在专用 GPU 云实例上观察到 CPU 利用率仍较低，但没有测量 CPU 同时承担数据加载、通信编排、推理服务和监控任务时的 P99。若 CPU proxy 被抢占，FIFO 背压会直接暂停 GPU 发起命令，并放大 tail latency。

论文的顺序模拟只覆盖 partial ordering。若实际 kernel 需要跨多个 channel 的因果关系，或者 expert 路由高度偏斜导致某些 channel 长时间积压，当前设计的局部 sequence state 可能不足。论文的 EP 扩展实验只到 32，不能直接推出更大集群或更大 expert 数量下的表现。

### 实验可信度

实验覆盖了多个 GPU、NIC 和上层框架，且包含端到端训练、serving、微基准和线程数消融。对照并不完全对称：DeepEP 无法运行在 EFA，PPLX 当时未集成开源推理引擎；EFA 上部分 PPLX 对比还忽略了其 BF16-to-FP8 转换时间，作者在表 4 单独补充了这一点。GH200 实验只有 EP=2 的 LL 模式，适合说明 C2C 路径可行，不能代表生产规模。

### 系统性缺陷

UEP 把网络控制、完成队列轮询、地址检查和语义重排放到 CPU proxy，增加了线程 pinning、NUMA 放置、进程故障处理和可观测性要求。论文讨论了未来的拥塞控制和弹性 EP，但没有给出故障注入、节点失联、NIC 错误恢复或 proxy 重启实验。论文认为 CPU 与 GPU 通常 fate-share，因此没有新增独立故障域；这并不消除 proxy 线程卡死、CPU 过载和 GPU kernel 与 proxy 状态不一致的运维风险。

## 局限与后续工作

- **EFA 小消息路径仍不够强。** 论文承认 DeepEP 的 LL kernel 尚可优化，图 15 也显示小消息处理效率受限。后续应在固定 CPU 预算下报告 P50/P99，并比较 batching、doorbell 合并和不同 outstanding request 上限。
- **拥塞控制尚未实现。** CPU proxy 理论上可以按 NIC、QP 和目的地跟踪 outstanding requests 并限速，但当前评测没有展示 incast、热点 expert 或多租户竞争下的尾延迟。
- **更大规模和动态集群未验证。** 当前主要是 EP=16/32 的测试。应在更大 EP、更多 NIC rail、专家负载不均衡和动态扩缩容下验证 FIFO 背压与 partial ordering。
- **故障语义需要落地。** 论文提出 proxy 可隐藏 GPU failure、scale-up/down 等事件，但没有给出协议和恢复时间。可验证的后续目标是：在单个 NIC、CPU proxy 或节点故障时，定义 token 丢失、重试、重复写和 barrier 解除的精确语义。
- **移植成本仍需量化。** O(m) 对比 O(m×n) 是架构层面的目标，不是实测工程成本。后续应报告新增 GPU backend、NIC provider 和上层框架适配所需代码量及维护边界。

## 相关

- **相关概念**：[[Mixture-of-Experts]]、[[Expert Parallelism]]、[[RDMA]]、[[GPUDirect RDMA]]
- **同类系统**：[[DeepEP]]、[[NCCL]]、[[RCCL]]、[[SGLang]]、[[Megatron-LM]]
- **同会议**：[[OSDI-2026]]
