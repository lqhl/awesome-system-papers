---
type: paper
name: Chitu
full_title: "Chitu: Avoiding Unnecessary Fallback in Byzantine Consensus"
authors: [Rongji Huang, Xiangzhe Wang, Xiaofeng Yan, Lei Fan, Guangtao Xue, Shengyun Liu]
venue: ATC
year: 2025
tags: [byzantine-consensus, bft, dag, blockchain, consensus]
source_pdf: "[[atc2025-huang-rongji.pdf]]"
source_md: "[[atc2025-huang-rongji]]"
---

# Chitu: Avoiding Unnecessary Fallback in Byzantine Consensus (ATC 2025)

> **一句话总结**：基于 Fair-Fallback 框架的异步 DAG-based BFT 协议，最佳情况下 4 个 message delay 提交、绕过 leader/random coin 等 fallback，相比 Tusk 端到端延迟降低最多 82.5%。

## 问题

BFT 共识两条主流路径都有缺陷：1) 部分同步协议（PBFT、HotStuff、BullShark）依赖单一 leader 与同步假设，leader 故障要走昂贵的 view change，WAN 上网络抖动可能陷入连环换主；2) 异步协议（Tusk、DAG-Rider、Honeybadger）靠随机硬币（threshold signature）保证概率 termination，但 coin-flipping 永远在关键路径上，比同步对应物多几轮通信。一次提议是否需要 fallback（leader/coin）应当取决于运行时——若 correct nodes 对某 proposal 已无分歧，就不该走 fallback。

## 核心方法

- **Fair-Fallback 框架**：correct nodes 先尝试纯消息交换达成共识（fast path 无 leader、无同步假设），仅当对某 proposal 出现分歧时才回退到 leader 选举或 random coin。fast path 与 fallback 在统一的 DAG 上并发推进，无显式切换。形式化两个 invariant 保证 fast path 与 fallback 的提交集合一致。
- **Chitu 协议**：基于 Tusk/DAG-Rider 的 DAG，每节点每 round 提议一个 vertex 经 BRB（Byzantine Reliable Broadcast，2 阶段）分发，每个 vertex 连 ≥$n-f$ 条边到上一 round。一个 round-r vertex u 的状态：被 round $r+1$ 中 ≥$n-f$ 个 vertex observe → 1-valent；被 ≥$n-f$ 个不 observe → 0-valent；中间 → bivalent。Fast path：若 round r 所有 vertex 都已 univalent，立即 commit 1-valent 集合，比 Tusk 节省至少 4 轮。Normal path：用 random coin 在偶数（奇数）round 选 leader vertex 决定之前未决 round。
- **Adaptive wait 机制**：节点在 deliver $n-f$ 个 vertex 后不立即进入下一 round，而是继续等待 pre-accepted（被 $f+1$ 个节点收到）的 vertex 到达，并主动转发其 VAL/PREPARE 消息。这增加 round 间边的数量，让更多 vertex 落入 1-valent 区间，大幅提升 fast path 命中率。

实现：Golang，BLS 阈值签名做随机硬币。深度细节回 [[atc2025-huang-rongji]]。

## 关键结果

- AWS EC2 跨 5 区域，n=4 时端到端延迟比 Tusk 降低 82.5%（440ms vs 2519ms），n=10 降低 82.2%
- 最优情况 4 message delays 提交（Tusk 14.5）；正常 9 个、最坏 15 个；期望复杂度仍 $O(1)$
- n=4 fault-free 下 99.5% vertex 走 fast path（无 wait 机制只有 12%）
- crash fault 下仍稳定走 fast path，BullShark 性能受影响显著
- 即便强制走 random coin，性能 graceful degrade
- 局限：fast-path 命中率随节点数 $p^n$ 衰减
- 开源：https://github.com/Decentralized-Computing-Lab/ChituBFT

## 相关

- **相关概念**：[[Byzantine-Fault-Tolerance]]、[[Consensus]]、[[DAG-BFT]]、[[Blockchain]]、Threshold Signature
- **同类系统**：Tusk、DAG-Rider、BullShark、HotStuff、Red Belly、MyTumbler
- **同会议**：[[ATC-2025]]
