---
type: paper
name: SERENO
full_title: "Inference in the Shadows: Taming Memory Bandwidth Contention in Mobile LLM Inference with SERENO"
authors: [Tong Xin, Xinrui Shi, Mingkai Dong, Zeyu Mi]
venue: OSDI
year: 2026
tags: [mobile-llm-inference, memory-bandwidth, foreground-qos, speculative-decoding, npu]
source_pdf: "[[osdi26-xin.pdf]]"
source_md: "[[osdi26-xin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# SERENO：移动端 LLM 推理中的内存带宽争用治理（OSDI 2026）

> **原题**：Inference in the Shadows: Taming Memory Bandwidth Contention in Mobile LLM Inference with SERENO

> **一句话总结**：移动 SoC 的 NPU 内存流量具有硬件优先级，后台 LLM 推理会让 25 个前台应用的 aggregate jank rate 增加 153%，但自身吞吐只下降约 1%；SERENO 将 speculative decoding 改造成亚毫秒级可让出的执行窗口，在不修改硬件和内核的前提下把平均 jank 降低 58.5%，并把吞吐提高 26.4%。

## 问题与动机

手机上的 LLM 推理通常在 NPU 上运行。CPU、GPU 和 NPU 通过 Unified Memory Architecture（UMA）共享 DRAM。推理尤其是 decode 阶段持续读取模型权重，因此会和前台 UI 渲染争用内存带宽。论文在 25 个应用上的测量显示，前台卡顿明显恶化，而后台推理几乎不受影响。

作者将问题归因于 SoC 的历史性优先级策略：NPU 原本服务于录像等延迟敏感的媒体任务，因此获得了较高的内存访问优先级；LLM 这个 best-effort 负载继承了该优先级。普通的降频或固定睡眠既不能快速响应前台的短突发，也会浪费后台推理进度。

## 关键观察 / 隐含假设

- **观察 1：干扰具有明显的不对称性。** 共跑时前台 aggregate jank rate 增加 153%，而 prefill 和 decode 吞吐只分别下降 1.01% 和 1.64%（§3.1，图 2）。
  - **依赖假设**：前台渲染和 NPU 推理共享同一 UMA 内存系统，且 NPU 流量确实保持较高优先级。
  - **可能失效场景**：若 SoC 已提供公平的 NPU 带宽仲裁，或前台瓶颈转为 CPU/GPU 计算，带宽调节的收益会下降。
- **观察 2：主导瓶颈是 DRAM 争用，而非计算或缓存争用。** Memory Stall Cycles 增加 3.8×，LLC Miss Latency 增加 3.5×，GPU memory stall rate 增加 3.1×，但 CPU/GPU 利用率、频率和缓存指标基本稳定（§3.2，图 3）。
  - **依赖假设**：内存访问延迟能代表前台 QoS 压力，且该压力可由推理执行时间间接观测。
- **假设 1：speculative decoding 的候选草稿可以安全丢弃。** SERENO 在 draft 的任意子图边界中止剩余候选，再由 target model 验证提交；因此不会改变输出语义。证据强度：强，论文明确说明所有候选都经过验证，但没有单独报告准确率实验。
- **假设 2：草稿子图延迟是稳定且足够准确的带宽传感器。** 论文离线校准每个静态子图，并报告其延迟与 CPLM 在 125,060 个样本上的 Pearson R 约为 0.86（§7.3，图 11）。在 CPLM 大于 22 的区域，相关性和控制精度是否仍然可靠，论文没有充分展开。

## 核心方法

SERENO 将 draft model 按 Transformer layer 编译成多个静态 NPU 子图。每个子图执行时间小于 1 ms，控制器可在边界丢弃未完成的 draft，立即释放带宽。这利用了 speculative decoding 候选本来就可以被拒绝的性质，同时保留静态图的 NPU 效率。

为了弥补被中止的候选，SERENO 使用 N-gram Filling。从已提交输出、prompt 和被拒绝的 draft 中构建本地 n-gram cache，并用命中频率清除低质量序列、给较长匹配更高权重。补出的候选仍由 target model 验证，所以缓存只影响候选供给，不改变正确性。

verification 阶段预编译多个 batch size 的静态图。较大的 batch 让一次权重读取验证更多候选，平均带宽需求较低，但形成更长的原子执行突发。控制器在争用较重时选择较大 batch，并在 verification 子图之间插入 micro-sleep；争用较轻时选择较小 batch，减少等待。

控制面采用亚毫秒级 Sense-Decide-Act 闭环：用 draft 子图实际延迟相对离线基线的增长计算 Contention Score，再由 PI controller 选择 Draft Preemption、Selective Batching 和 Micro-Sleeps 的强度。hysteresis 减少噪声导致的振荡，Token Bucket 则在持续让出导致吞吐不足时放宽目标，避免后台任务饿死。

## 设计取舍

- **前台保护换取候选接受率。** SERENO 的 tentative-token acceptance ratio 平均为 18.9%，低于吞吐优先 speculative decoding 的 30.4%；它用更积极的中止和更大的 verification batch 换取带宽余量。
- **静态图兼容性换取预编译开销。** 每种 batch size 都要预先导出图，运行时灵活性受限，但避免了动态算子带来的 NPU 效率损失。
- **用户态可部署性换取调节能力边界。** SERENO 不修改 SoC 仲裁、内核或厂商驱动，只能在 NPU 图之间控制执行。因此它无法中断正在运行的图，也无法处理计算饱和主导的卡顿。

## 实验与结果

- 在 OnePlus 13（Snapdragon 8 Elite，24 GB LPDDR5X）上，30 个应用、Llama-3.1-8B-Instruct W4A16 和 15 次重复实验中，SERENO 平均 jank rate 为 6.21%，接近 Native 的 4.91%；相对 PowerServe 平均降低 58.5%，吞吐提高 26.4%（§7.2，图 5）。
- Social 应用的 jank rate 从 PowerServe 的 22.12% 降至 8.14%，吞吐为 16.00 tokens/s；相对吞吐优先 speculative decoding，Reader 的 jank 降低 72.1%，吞吐只下降 6.2%（图 5）。
- SERENO 将端到端请求延迟从 PowerServe 的 11.25 s 降至 10.21 s。prefill 因可抢占的小 batch 从 0.99 s 增至 2.09 s，但 decode 加速抵消了该开销（图 7）。
- Draft Preemption 将消融实验中的 jank 从 8.5% 降至 4.5%；再加入 Selective Batching 和 Micro-Sleeps 后降至 3.6%，N-gram Filling 将吞吐从 12.9 提高到 15.6 tokens/s（§7.4，图 12）。
- SERENO 将 CPLM 从 PowerServe 的 7.15 降至 4.17 cycles，下降 42%；能效为 3.52 tokens/J，略低于 speculative decoding 的 3.78 tokens/J（§7.3、§7.5，图 8、图 13）。
- 在 Snapdragon 8 Gen 3 上，Tools 和 Social 的 jank 降幅仍为 58.79% 和 62.34%，但 Gaming 降至 29.70%，因为该场景更多受 CPU/GPU 计算饱和限制（图 14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| NPU 推理会优先占用 UMA 带宽并严重伤害前台 QoS | §3.1–§3.3，图 2–3；jank +153%，内存 stall 3.8× | 三类 SoC 源码分析；主要实验为 Snapdragon 8 Elite | 强 |
| draft 子图延迟可作为低开销争用信号 | §5.2、§7.3，图 11；125,060 样本，R≈0.86 | CPLM ≤ 22 时相关性明确 | 中 |
| 亚毫秒让出比固定降频/睡眠更有效 | §7.2、§7.4，图 5、12 | 30 个应用，单前台应用与单后台 LLM 共跑 | 强 |
| SERENO 能同时改善前台 QoS 和后台吞吐 | §7.2，图 5–7；平均 jank -58.5%，吞吐 +26.4% | Llama 系列、两代 Snapdragon 手机；未覆盖更多 NPU 厂商的实机结果 | 中 |

## 批判性分析

### 论证链条

从内存 stall 测量到 NPU 优先级分析，再到利用 speculative decoding 释放带宽，论文的主要链条是闭合的。消融实验也显示 Draft Preemption 是 QoS 改善的主要来源，Selective Batching 和 Micro-Sleeps 处理剩余 verification 突发。论文对“广泛适用于移动 LLM”的外推仍有限，因为核心模型实验集中在 Llama 系列，且每次只运行一个前台应用。

### 假设压力测试

SERENO 依赖带宽争用是主要瓶颈。Gen 3 Gaming 结果说明，一旦瓶颈转为计算，调节 NPU 带宽不能恢复全部 QoS。多租户后台任务、不同 NPU 驱动的仲裁策略和更高并发的前台服务也可能改变控制器的反馈分布。Token Bucket 的 fail-safe 会在持续吞吐不足时退回普通 speculative decoding，这会重新引入前台风险。

### 实验可信度

实验覆盖 30 个应用、四类负载、两代 Snapdragon 手机，并报告 QoS、吞吐、延迟、能效和微架构指标。对照包括 PowerServe、llama.cpp、MNN 以及固定降频和固定睡眠策略。限制在于主要硬件来自 OnePlus/Snapdragon，SoC 间优先级结论虽有源码佐证，却缺少其他厂商的同等端到端验证；论文也没有报告输出质量指标，只依据验证过程主张无损。

### 系统性缺陷

每个 draft layer 和多个 verification batch 都需要预编译，模型更新或 NPU SDK 变化会增加维护成本。额外内存占用为 0.86 GB（约 19%），主要来自 draft model。控制器还增加单核约 4.7% CPU 利用率。论文未讨论应用权限、厂商 NPU runtime 接口稳定性、后台任务公平性和异常恢复；这些因素会影响产品化部署。

## 局限与后续工作

- **局限 1**：模型和硬件覆盖仍窄，主要使用 Llama-3.1/3.2 与 Snapdragon 手机；需要在不同架构、量化格式和 NPU runtime 上验证 Contention Score 的可迁移性。
- **局限 2**：主要压力测试把一个前台应用与一个后台 LLM 共跑；应增加多个后台模型、媒体任务和系统服务，测量优先级叠加后的控制稳定性。
- **后续工作 1**：建立跨 SoC 的带宽—QoS 标定集，分别测量带宽争用和计算饱和时的控制误判率，并报告 P95/P99 卡顿及能耗。
- **后续工作 2**：评估更小 draft model、动态模型切换和模型更新时的图缓存策略，验证其能否降低 0.86 GB 内存开销与预编译成本。

## 相关

- **相关概念**：[[Speculative Decoding]]、[[Memory Bandwidth]]、[[NPU]]、[[Unified Memory Architecture]]
- **同类系统**：[[PowerServe]]、[[llama.cpp]]、[[MNN]]
- **同会议**：[[OSDI-2026]]
