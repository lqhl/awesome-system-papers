---
type: paper
name: Pompe-SRO
full_title: "Equal Opportunity: A Correctness Condition for Ordered Consensus"
authors: [Yunhao Zhang, Haobin Ni, Maofan Yin, Soumya Basu, Lorenzo Alvisi, Shir Cohen, Robbert van Renesse, Qi Chen, Lidong Zhou]
venue: OSDI
year: 2026
tags: [ordered-consensus, blockchain, fairness, front-running, byzantine-fault-tolerance]
source_pdf: "[[osdi26-zhang-yunhao.pdf]]"
source_md: "[[osdi26-zhang-yunhao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 有序共识中的平等机会（OSDI 2026）

> **原题**：Equal Opportunity: A Correctness Condition for Ordered Consensus

> **一句话总结**：现有有序共识会把网络位置等无关因素带来的接收时间差固化为交易顺序；Pompe-SRO 在 Pompe 的时间戳上加入共识完成后才揭示的随机噪声，以满足 ε-Ordering Equality 与 Δ-Ordering Separation，在 12 城市实验中将地理偏差压到 ε(2)=0.05 以下，但 P50/P99 延迟增加约 1.12–1.42 倍。

## 问题与动机

状态机复制（SMR）只要求副本对请求达成同一总序；在区块链中，顺序本身会改变清算、交易和套利的经济结果。HotStuff、Pompe 和 Themis 等协议限制了领导者或拜占庭节点的影响，却没有区分“应影响顺序”的特征与网络位置、地理距离、连接速度等无关特征。

论文把 front-running 与 sandwich attack 视为顺序偏差的后果。若攻击者能更快地把请求送达节点，它可能系统性地获得有利位置。论文的目标不是识别恶意交易，而是让具有相同相关特征的请求在顺序中获得近似相同的机会。

## 关键观察 / 隐含假设

- **观察 1：接收顺序会放大地理和网络偏差。** 在 12 城市、80 个按权益映射的节点实验中，Pompe 对同时请求产生确定性顺序；HotStuff 中 Munich 请求排在 Tokyo 请求前的概率为 0.74（图 8）。
  - **依赖假设**：请求的相关特征主要是调用时间和费用，客户端地理位置与网络连接不应影响顺序。
  - **可能失效场景**：若费用、优先级或交易语义本来就应改变排序，单纯对时间戳加噪声可能削弱这些政策目标。
- **观察 2：随机化必须在排序决定不可再被影响后才揭示。** 否则拜占庭节点或攻击者可以根据随机值选择偏好的共识输出。
  - **证据强度**：强。SRO 的 Secrecy 保证和 Pompe-SRO 的集成都以共识槽签名达到 quorum 后调用 Reveal 为前提（§3.1、§3.4）。
- **假设 1：部分同步模型中的网络延迟存在已知上界。** 论文假设 GST 之后节点处理请求的时间戳位于真实调用时间后的 `[T, T+Δ_net)` 内（Assumption 3.1）。
  - **可能失效场景**：网络延迟无界、长期分区或成员频繁加入退出时，论文的 liveness 与公平性参数不能直接外推。

## 核心方法

论文先用两个原则刻画平等机会：impartiality 要求相关特征相同的请求对称处理；consistency 要求加入其他请求不改变已有请求的相对顺序。点系统可以为每个请求按相关特征赋分，并对同分请求均匀打散。

由于节点无法精确观察真实调用时间，论文定义两个近似条件。ε-Ordering Equality 要求同一时刻的请求排列概率接近均匀分布；Δ-Ordering Separation 要求相差至少 Δ 的较早请求必定先出现。随机噪声范围越大，ε 越小，但 Δ 至少增加为 `Δ_net + Δ_noise`。定理 3.1–3.3 给出了这一权衡及离散均匀噪声分布的最优性。

Secret Random Oracle（SRO）是延迟揭示、抗拜占庭的随机源。其 `Reveal(k,s)` 只有在收到至少 `n-f` 个有效签名后才返回随机值；`Generate` 和 `Verify` 用于产生和校验证明。论文实现了两种版本：基于 Intel SGX 的 TEE 版本，以及基于 threshold VRF 的密码学版本。前者约束更少、速度更快，但需要信任 Intel；后者避免单一硬件信任点，却需要节点间生成、收集和合并 share。

Pompe-SRO 继承 Pompe 的 assigned timestamp。共识槽完成后，节点用槽编号和 quorum 签名调用 SRO，再为每个命令独立采样 `[0, Δ_noise]` 中的噪声，按 `assigned_timestamp + noise` 排序。噪声可能让已达成共识的命令暂时不能稳定输出，因此公平性直接转化为尾延迟成本。

## 设计取舍

- **随机性与时间顺序**：扩大 `Δ_noise` 能降低同时请求的排序偏差，却增加能保证先后顺序所需的时间间隔 Δ。
- **TEE 与 threshold VRF**：SGX 中生成随机值约 3 μs，但引入对 Intel 的信任；100 节点、67 阈值的 TVRF 生成 share 约 0.4 ms、合并约 6.3 ms，200 节点时合并约 12 ms（图 12）。
- **公平性与尾延迟**：实验选择 `Δ_noise=5Δ_net=2000 ms` 达到目标 ε，但随机扰动和 2000 ms 共识槽共同扩大 P50 到 P99 的差距。

## 实验与结果

- 在 12 城市、80 节点、`Δ_net=400 ms` 的 CloudLab 部署中，Pompe-SRO 使用 `Δ_noise=2000 ms` 将最坏地理偏差控制到 ε(2)=0.05（图 9）。
- 三请求 sandwich attack 中，攻击者比受害者早 10 ms 发送请求时，基线协议均确定成功；Pompe-SRO 让 6 种排列等概率，攻击者期望收益降至 67 美元，受害者期望收益为 233 美元（图 10）。
- 1440 个客户端达到饱和时，Pompe 吞吐为 1842 cmd/s，Pompe-SRO 为 1893 cmd/s；吞吐基本不受影响（图 11）。
- London 客户端的 P50 和 P99 延迟分别变为 Pompe 的 1.29 倍和 1.42 倍；Canberra 客户端分别为 1.31 倍和 1.12 倍（§5.4）。
- 200 个签名校验约需 20 ms；但端到端开销主要来自为降低 ε 而加入的随机等待，而非密码学运算（§5.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 地理位置可造成显著排序偏差 | HotStuff 的城市间概率差异、Pompe 的确定性顺序（图 8） | 12 城市、80 节点、仿真 WAN 延迟 | 强 |
| 延迟揭示的随机噪声能降低 front-running 和 sandwich attack | Pompe-SRO 的偏差与期望收益测量（图 9、图 10） | 人工构造交易与 10 ms 攻击优势 | 中 |
| 公平性可在近似不损失吞吐的情况下实现 | 1842 vs. 1893 cmd/s，延迟增加 1.12–1.42 倍（图 11、§5.4） | CloudLab、固定 2000 ms 槽、TEE 版本 | 中 |
| ε 与 Δ 存在结构性权衡 | 定理 3.1–3.3 | 部分同步、时间戳误差上界成立 | 强 |

## 批判性分析

### 论证链条

从“接收时间包含无关网络偏差”到“用共识后随机噪声打破近似同时请求的平局”，设计链条是闭合的。论文也明确承认无法彻底消除拜占庭影响，只能降低攻击者获得特定排列的概率。实验验证了两请求偏差和一个三请求攻击案例，但对更复杂交易策略、费用竞争和动态攻击者的覆盖有限。

### 假设压力测试

公平性依赖 `Δ_net` 上界。生产链路的延迟分布若长尾明显，固定 `Δ_noise` 只能覆盖选定范围；覆盖更多客户端会进一步推高稳定时间。论文还把调用时间与费用视为相关特征，但没有实验展示费用排序和公平随机化同时存在时的行为。

### 实验可信度

城市分布参考 Ethereum 节点统计，拓扑和权益比例也有现实依据；基线包括 HotStuff、Pompe 和 Themis，能够比较不同公平性定义。另一方面，实验使用 80 个固定成员、固定槽长和人工设置的攻击时差，尚未说明真实 mempool、拥塞、交易撤销、批量策略或动态权益变化下的结果。

### 系统性缺陷

Pompe-SRO 不是 permissionless 协议，节点身份、公钥、`n` 和 `f` 都必须已知；原型不支持成员加入和退出。SGX 版本把安全性的一部分转移给硬件厂商。更大的噪声范围会明显增加 P99 延迟，可能与交易确认 SLO 冲突。论文未讨论随机源初始化失败、硬件回滚、密钥轮换和长期可观测性。

## 局限与后续工作

- **局限 1**：结论依赖部分同步和固定成员集合，不能直接覆盖无界延迟或频繁成员变更的链。
- **局限 2**：ε(3) 的完整证明被放在扩展技术报告中；正文实验只覆盖一个具体 sandwich attack 配置。
- **后续工作 1**：在真实 mempool trace 上测量不同 `Δ_net` 分位数与攻击收益，并报告公平性、确认时间和失败率的联合曲线。
- **后续工作 2**：设计不依赖单一 TEE 厂商的 SRO，比较 TVRF、TEE 与混合方案在成员变更和故障恢复下的端到端成本。

## 相关

- **相关概念**：[[Ordered Consensus]]、[[Byzantine Fault Tolerance]]、[[Threshold VRF]]
- **同类系统**：[[Pompe]]、[[HotStuff]]、[[Themis]]
- **同会议**：[[OSDI-2026]]
