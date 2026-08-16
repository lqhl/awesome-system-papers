---
type: paper
name: Pompe-SRO
full_title: "Equal Opportunity: A Correctness Condition for Ordered Consensus"
authors: [Yunhao Zhang, Haobin Ni, Soumya Basu, Shir Cohen, Maofan Yin, Lorenzo Alvisi, Robbert van Renesse, Qi Chen, Lidong Zhou]
venue: OSDI
year: 2026
tags: [consensus, blockchain, fairness, ordering, verifiable-randomness]
source_pdf: "[[osdi26-zhang-yunhao.pdf]]"
source_md: "[[osdi26-zhang-yunhao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 有序共识中的机会平等

> **原题**：Equal Opportunity: A Correctness Condition for Ordered Consensus

> **一句话总结**：传统有序共识可以满足安全性和 ordering linearizability，却仍让网络更快或地理位置更有利的客户端稳定抢先；论文用 ε-Ordering Equality 和 Δ-Ordering Separation 把“同等请求有近似相同排序机会”写成正确性条件，再以秘密随机预言机（Secret Random Oracle，SRO）改造 [[Pompe]]。当随机窗口取 2 s 时，四组跨城市请求的最坏双请求偏差降到 0.10，吞吐维持约 1,893 cmd/s，但 P50/P99 延迟增至 Pompe 的 1.12×–1.42×。

## 问题与动机

状态机复制（state-machine replication，SMR）保证所有正确节点执行同一全序。有序共识进一步限制 Byzantine 节点怎样影响顺序，但 ordering linearizability 只约束时间区间不重叠的请求；两个几乎同时提交的请求仍可被网络传播顺序稳定区分，而且协议完全不算错。客户端的地理位置、网络设备和节点连接因此会变成隐含优先级。

这不是抽象的“不公平”。论文引用 Ethereum 研究：前序偏差与 front-running 在 32 个月内影响约 8,900 万美元的分配，sandwich attack 同期抽取超过 1.74 亿美元（§2.1）。例如欧洲请求若有 75% 概率先于同时到来的澳大利亚请求，一个 20 万美元机会的期望收益会被分成 15 万与 5 万美元。问题在于现有安全性定义不禁止这种差异，而不是共识没有形成。

论文提出的目标不是识别“好交易”和“坏交易”，而是只根据事先声明的相关特征（relevant features，例如 invocation time 或 fee）排序；identity、geolocation、wealth 和 connectivity 等无关特征不应改变机会。哪些特征算“相关”仍由应用或治理决定，协议本身不能替社会做这个选择。

## 关键观察 / 隐含假设

- **观察 1：安全共识也可以持续有偏。** [[HotStuff]] 的 rotating leader、Pompe 的 median timestamp、Themis 的 batch-order fairness 都能产生合法全序，但在 12 城市实验中，多组同时请求的先后概率严重偏离 50%（§5.1，图 8）。因此公平性需要成为独立正确性条件。
- **观察 2：机会平等可由 impartiality 和 consistency 拆解。** Impartiality 要求交换两个相关特征相同的请求后，preference profile 的概率不变；consistency 要求加入第三个请求不改变原有请求的相对机会。只依赖每个请求相关特征打分、平分时均匀随机的 point system 同时满足两者，但论文没有证明它在 ordered-consensus 模型中是唯一机制（§2.2）。
- **观察 3：随机性必须在排序承诺之后才公开。** 若 leader 预先知道随机数，就可选择请求集合或重试结果。SRO 只有看到至少 $n-f$ 个签名后才 `Reveal`，并提供 uniqueness、secrecy、randomness 和 validity；Pompe-SRO 在 slot 共识完成后才取得种子（§3.1、§3.4，图 4–6）。
- **假设 1：部分同步的时间界成立。** 论文只在 global stabilization time（GST）之后假设消息、处理和时钟误差合计受 $Δ_{net}$ 约束；此前仍保安全，但 ordering equality/separation 与 liveness 不能保证。无限或严重不对称的客户端网络延迟也不在机会平等范围内（§3.5、§5.1）。
- **假设 2：参与者和 stake 已知且至多三分之一恶意。** 原型按 $n=3f+1$ 的 BFT 模型工作，知道成员公钥；PoS 中解释为恶意 stake 至多 33%、quorum 为 67%。它不是 permissionless，也不支持节点动态加入或退出（§4）。
- **假设 3：随机排序足以缓解目标攻击。** 它消除的是网络优势对已纳入请求的排序偏差；censorship、私有 order flow、fee 操纵、故意延迟提交和应用语义攻击仍可存在。

## 核心方法

**两条正确性条件。** 对同一 invocation time 的 $n$ 个请求，ε-Ordering Equality 要求每一种 permutation 的概率与 $1/n!$ 相差至多 $ε(n)$。Δ-Ordering Separation 则要求：若一个请求至少早 Δ 提交，它必须排在后一个请求之前。前者追求平等机会，后者保留“明显更早就应先执行”的时间语义（§2.3）。

**Secret Random Oracle。** `Reveal(k, signatures)` 只有在至少 $n-f$ 个节点签名要求公开时才返回第 $k$ 个随机值；`Generate` 和 `Verify` 提供可验证性。TEE 版本让各 enclave 在初始化时通过共识得到共享 secret seed，此后本地计算 `RAND(seed,k)`；TVRF 版本要求节点在验证 quorum signature 后生成 share，收齐 threshold shares 再 combine。前者快但信任 Intel SGX，后者去掉单一硬件信任但多一轮网络和密码计算（§3.1–§3.3）。

**从 Pompe 到 Pompe-SRO。** Pompe 为每个请求收集 $2f+1$ 个节点 timestamp，取 median 作为 assigned timestamp（ats），并按连续时间区间组成 consensus slot。Pompe-SRO 在 slot $k$ 已达成共识后取得 SRO seed，为每个命令独立采样 $[0,Δ_{noise}]$ 内噪声，按 `ats + noise` 排序。只有最新 finalized slot 的右边界已经超过该值时，命令才稳定进入 ledger，因此噪声也直接增加 finalize 等待（§3.4）。

**公平与时间顺序的硬取舍。** 任意噪声分布都能给出 $Δ=Δ_{net}+Δ_{noise}$ 的 separation；令 $kΔ_{net}≤Δ_{noise}\lt(k+1)Δ_{net}$ 时，$ε(2)$ 的下界为 $1/[2(k+1)]$。在 $0,Δ_{net},…,kΔ_{net}$ 上均匀取离散点能达到该下界。噪声越大，近同时请求越公平，但“更早请求必先执行”需要的时间差也越大；一般 $n$ 的完整证明放在扩展 technical report（§3.5）。

这个下界也限定了实验结论：实验取 $Δ_{noise}=5Δ_{net}$，对应 $k=5$，所以面对最坏的时间戳选择，任何分布都只能保证 $ε(2)\ge 1/12\approx0.083$；图 9 观察到的 $ε(2)=0.05$ 只是该城市延迟矩阵上的经验结果，不是定理保证。定理 3.2 原文还把下界写成对“所有”同时请求都成立，但相同 assigned timestamp 加独立同分布噪声会给出恰好 50/50；其证明实际使用的是“对手可以选择两者的 assigned timestamp 差”，因此正式陈述缺少最坏情况或存在性量词。

## 设计取舍

- **语义无关换取有限保护。** 协议不判断交易是否恶意，所以能用于不同应用并避免审查者偏见；代价是只能降低 attacker 的排序优势，不能保证攻击无利可图。
- **平等机会换取确定的额外等待。** 实验采用 $Δ_{noise}=5Δ_{net}=2$ s，把目标设为 $ε(2)=0.05$；更小偏差需要更大窗口，也让 Δ-Separation 和 tail latency 变差。
- **TEE 性能换取集中信任。** SGX `Reveal` 基础路径约 3 μs，适合端到端原型，但依赖 Intel、enclave confidentiality 和初始化 seed 不泄漏；论文未测 side channel、rollback 或 enclave failure。
- **TVRF 去信任换取通信。** 100/67 节点时生成 share 约 0.4 ms、合并约 6.3 ms；这些数字不含网络收集 share 的时间，论文也没有以 TVRF 跑端到端吞吐，因此不能直接视为完整成本。
- **已知成员 BFT 换取简单 quorum。** Stake-weighted 节点可映射到 $n=3f+1$，但 membership change、permissionless Sybil resistance 和 validator churn 留给未来工作。
- **规范参数换取治理争议。** $ε(2)=0.05$ 借用了就业公平中的 four-fifths rule；把这一法律阈值用于区块链排序是设计示例，不是由系统实验推导出的普遍最优值。

## 实验与结果

- **平台与口径**：12 台 CloudLab `ds430`（Xeon E5-2630、64 GB、Ubuntu 24.04）各映射到一个城市，用 `tc` 重放 WonderNetwork 城市间延迟；SGX 另在 Xeon Silver 4410Y 上测试。论文先按 Ethereum 地理分布构造等价 80-node stake，再让每台城市服务器运行一个进程并持有相应 stake；因此这是 12 个 server process 的 stake-weighted emulation，不是 80 台机器或 80 个进程。设 $Δ_{net}=400$ ms，高于测试中的最大 296 ms（§5）。
- **地理偏差**：HotStuff 在四对城市上的先后概率差为 -0.05、0.83、0.48、0.48；Pompe 四项都为 1，Themis 为 -1、1、1、1。Pompe-SRO 用 400 ms 均匀噪声后变为 0.24、0.31、0.07、0.46，用 2,000 ms 后降为 0.05、0.07、0.01、0.10。这里表中的“差”是两个方向概率之差；0.10 对应 55% 对 45%，刚好满足 $ε(2)=0.05$（§5.1，图 8–9）。
- **Sandwich attack**：合成 AMM 中，攻击者命令比 victim 早 10 ms 到达所有节点。HotStuff、Pompe、Themis 都确定地产生攻击顺序，victim 损失 500 美元、attacker 获利 800 美元；Pompe-SRO 让六种 permutation 等概率后，期望值变成 victim 获利 233 美元、attacker 获利 67 美元，且 attacker 有损失 400 美元的可能。这证明机制改变该示例的期望收益，不代表覆盖真实 MEV 市场（§5.2，图 10）。
- **SRO 微基准**：SGX 进入 enclave 并做 SHA256 的基础成本约 3 μs。TVRF 在 100/67 与 200/133 配置中生成 share 都约 0.4 ms，combine 分别为 6.3/12 ms；验证 200 个 signature 约 20 ms。TVRF 只报告 share generation 和 combine，不含网络收集，也没有参与后续端到端实验（§5.3，图 12）。
- **端到端性能**：最终实验选择 TEE、2 s slot、2 s 噪声并关闭 batching；12 城市各 120 个 closed-loop client 时，Pompe 与 Pompe-SRO 峰值为 1,842/1,893 cmd/s。伦敦 client 的 P50/P99 比 Pompe 高 1.29×/1.42×，堪培拉为 1.31×/1.12×；Pompe-SRO 的 P99-P50 差达 1,672–1,816 ms。吞吐“相同”不应掩盖峰值吞吐附近约 4.7–7.5 s 的 P50/P99 和未启用 batching 的口径；绝对值为图上近似读数（§5.4，图 11）。

## 论断—证据表

| 论断 | 直接证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 现有 ordered-consensus fairness 仍可能产生地理偏差 | HotStuff、Pompe、Themis 的四对城市概率差最高达 1（图 8） | 12 城市延迟仿真、选定 stake 分布；不是公网实测 | 强（该设置） |
| Pompe-SRO 在所测城市延迟上把双请求偏差压到目标范围 | 2 s 噪声下四项差为 0.05/0.07/0.01/0.10，均对应观测到的 $ε(2)$ 不超过 0.05（图 9） | 固定城市延迟矩阵上的经验结果；实验用均匀噪声，且定理 3.2 在该窗口下的最坏情况保证只有 $ε(2)\ge1/12$ | 强（该设置） |
| 随机排序能降低合成 sandwich attack 的期望收益 | attacker 期望收益从 800 美元降至 67 美元，并出现 400 美元损失风险（图 10） | 单一三交易 AMM 示例，没有真实链、mempool 或 adaptive attacker | 中 |
| SRO 几乎不降低 Pompe 峰值吞吐 | 1,893 对 1,842 cmd/s（图 11） | 使用 SGX、关闭 batching、2 s slot；延迟明显增加 | 中强 |
| TVRF 是已证明低成本的端到端替代方案 | 只测本地 share generation/combine 和 signature verification（图 12） | 缺网络收集与全协议结果 | 弱 |

## 批判性分析

### 论证链条

论文最重要的贡献是把“网络偏差虽然合法，但仍应视为错误”说清楚：现有定义留下缺口，impartiality/consistency 给出规范基础，ε/Δ 把它变成可测试条件，SRO 再提供提交后才公开的随机数。理论给出的 ε–Δ 下界说明额外延迟不是实现偶然，而是目标本身的代价。但理论和实验不能混成一个保证：2 s 均匀噪声在图 9 的固定延迟上达到 $ε(2)=0.05$，并不推翻同一窗口下 $1/12$ 的最坏情况理论下界。实验能证明原型在给定边界内降低偏差，却不能证明“机会平等”是所有应用唯一正确的 fairness，也不能把攻击缓解等同于攻击消失。

### 假设压力测试

应让 adversary 同时控制 33% stake、选择性延迟 share、censor victim、在看见 victim 后自适应选择 fee 和提交时间，再观察 ε 是否仍只由 $Δ_{noise}$ 决定。网络测试要跨过 GST，制造长尾大于 400 ms、时钟偏移和区域分区，明确什么时候系统只有 safety、什么时候恢复 equality。还需替换 invocation time 为 fee 等相关特征，检查“相关特征”本身可操纵时 point system 是否把财富优势合法化。

### 实验可信度

论文公开 artifact，清楚给出机器、城市映射、stake、latency bound、baseline 和概率定义；地理偏差、攻击收益、SRO 微基准与端到端性能分别回答不同问题，证据组织较完整。主要弱点是 80-node 只由 12 个加权进程模拟，网络为 `tc`，没有 Byzantine fault injection、membership churn 或公网负载；端到端只用 TEE，TVRF 数字排除了网络；金融实验是合成 AMM。作者还把 1,893 与 1,842 cmd/s 解释为相同吞吐，但没有方差，严格统计依据不可见。

### 系统性缺陷

Pompe-SRO 只随机化已被共识接受的请求，leader 或 validator 仍可拒收、延迟、构造 bundle 或利用私有 order flow。2 s 噪声叠加 2 s slot 造成很大的稳定时间尾部，对交互式或低延迟金融系统可能不可接受；减小它又直接放宽 ε。TEE 版本把秘密种子和公平性集中到硬件信任，TVRF 版本则需要 quorum 在线且成员固定。更根本的是，系统把 fairness 的政治选择外置为“相关特征”和 ε 参数，却没有治理、审计或升级机制；协议正确不代表参数选择公平。

## 局限与后续工作

- 在真实公网、validator churn、网络分区与 Byzantine selective-delay 下验证 ε/Δ，并加入动态 membership。
- 修正定理 3.2 的量词，并把“固定延迟矩阵上的观测 ε”与“对手可选时间戳下的最坏情况 ε”分开报告。
- 用 TVRF 跑完整端到端路径，计入 share 网络收集、丢包、慢节点和重试；同时评测 TEE rollback、side channel 与 seed rotation。
- 把 censorship、bundle、private relay、fee manipulation 和 adaptive timing 纳入 threat model，而不只研究已纳入请求的相对顺序。
- 在真实交易 trace 或 testnet 上报告攻击者净收益、用户 latency SLO 和经济安全，而不只用三交易合成示例。
- 设计可审计的 relevant-feature 与 ε/Δ 治理流程，并研究按 workload 动态调参时的稳定性和可预测性。

## 相关

- **相关概念**：[[Consensus]]、[[Blockchain-Fairness]]、[[Verifiable-Random-Function]]、[[Front-Running]]
- **相关系统**：[[Pompe]]、[[HotStuff]]、Themis
- **同会议**：[[OSDI-2026]]
