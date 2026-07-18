---
type: paper
name: Trochilus
full_title: "Learning-Enhanced High-Throughput Pattern Matching Based on Programmable Data Plane"
authors: [Guanglin Duan, Yucheng Huang, Zhengxin Zhang, Qing Li, Dan Zhao, Zili Meng, Dirk Kutscher, Ruoyu Li, Yong Jiang, Mingwei Xu]
venue: ATC
year: 2025
tags: [network-security, pattern-matching, programmable-switch, knowledge-distillation, p4, tcam]
source_pdf: "[[atc2025-duan-guanglin.pdf]]"
source_md: "[[atc2025-duan-guanglin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Learning-Enhanced High-Throughput Pattern Matching Based on Programmable Data Plane (ATC 2025)

> **一句话总结**：Trochilus 将 pattern 先 modelize 为 BRNN，再经学习/蒸馏生成数据面模型；最终 classifier 并非端到端 exact regex equivalence。3500 multi-string patterns 中，T-MSM-4/8/12 相对 BOLT 降 **97.8%/95.6%/93.4%** TCAM；Trochilus-12 的 **2.8×** 吞吐为受发包器限制的理论上限模拟。

## 问题与动机

网络安全应用里的 pattern matching 同时要处理吞吐、准确率和维护成本。传统 CPU 方案即使做了算法优化也难到 70 Gbps；GPU/FPGA/NPU 能提高并行度，但论文认为 state-of-the-art 单机 IPS 仍大约在 100 Gbps 量级，并且硬件编程、PCIe 带宽和规则更新都增加了部署成本。对大规模 NIDS/NIPS、WAF、应用识别或审查系统来说，这个瓶颈会卡在汇聚点的 multi-hundred Gbps 到 Tbps 链路上。

[[Programmable-Switch]] 提供另一条路：PISA/Tofino 这类 ASIC 本来就能线速处理 Tbps 流量，成本和功耗接近普通交换机。但它只有有限 MAU stages、SRAM/[[TCAM]]，不支持复杂浮点、乘除和通用内存访问。此前 switch-based pattern matching 主要做 multi-string matching，把 automaton 状态转移串行化到 match-action pipeline；当 pattern 变长、数量变多，或从字符串扩展到 PCRE 正则语法时，状态和 TCAM 需求会爆炸。

论文的第二个动机是 manageability。Snort/Suricata 这类系统依赖专家维护 signature/rule set，面对新攻击或新应用流量时需要人工分析流量再提取规则。Trochilus 的目标不是只把现有规则跑得更快，而是把规则系统变成可训练模型：初始状态继承专家规则，运行中用新 labeled data 更新模型，再把更新后的模型重新转成数据平面表项。

## 关键观察 / 隐含假设

- **观察 1：PISA switch 的吞吐充足，瓶颈是表达能力与 TCAM/MAU 资源，而不是 packet I/O。** 论文用 Tofino 1 的 12 stages、每 pipeline 120 MB SRAM / 6.2 MB TCAM 作为硬件边界；BOLT 这类 automaton-based 方案在模式数量和平均长度增加时状态转移线性增长，难以覆盖复杂 PCRE 语法。
  - **依赖假设**：目标功能可以被降解成固定宽度的 binary/ternary feature matching 和少量 aggregation，且不会占光交换机上还要服务 ACL/routing/telemetry 的资源。
  - **可能失效场景**：同一台 switch 还承载大量其他 network functions、pattern set 大到单机模型放不下、或者 payload 需要复杂 parsing / normalization 时，match-action pipeline 的资源会先于链路带宽成为硬约束。

- **观察 2：规则库可以作为冷启动知识，而 labeled traffic 只用于增量改善。** Trochilus 把 PCRE pattern 先转 DFA，再利用 DFA forward computation 与 RNN forward 的等价性生成 byte-level RNN (BRNN)。实验中 BRNN 在 0% training data 下与 TPS 一样约 85.2% accuracy；10% training data 后提升到 96.3%，full training 到 98.5%。
  - **依赖假设**：DFA extractor 支持的 PCRE 子集足以覆盖真实规则；规则语义和数据标签是可信的；新攻击样本能被离线标注并定期喂给模型。
  - **可能失效场景**：复杂 PCRE feature、协议语义、编码规范化、跨包状态或加密流量不能被 byte-level payload window 表达时，BRNN 继承到的「专家知识」会变窄。

- **观察 3：SMF 转出的 ternary entries 极度稀疏，因此可以通过 entry clustering 省 TCAM。** 论文统计模型表项里超过 90% mask bits 为 0；entry cluster 在 k=2 到 9 时把 TCAM 需求降低 80.9%-92.5%，multi-string setting 下 T-MSM-4/8/12 相比 BOLT 降低 97.8% / 95.6% / 93.4% TCAM。
  - **依赖假设**：SDT/SMF 的路径条件在真实 pattern sets 上持续稀疏，且增加 k 张表带来的 pipeline/table 管理复杂度可接受。
  - **可能失效场景**：如果新模型需要更深 tree、更多 SDT、更宽 feature，或 pattern 对大量 byte positions 都敏感，entry cluster 的收益会下降。

- **假设 1：明文 payload inspection 仍是足够重要的目标场景。**
  - **证据强度**：中。论文明确假设 Ethernet/IP/TCP 或 UDP header + payload，采用 ASCII one-byte encoding，且主要处理 plain text payload；encrypted traffic 只说可结合 decryption mechanisms。这个假设对传统 IDS/WAF 场景合理，但在 TLS/QUIC 普及后外推到全网流量需要更多论证。

- **假设 2：论文数据集能代表真实更新压力。**
  - **证据强度**：中偏弱。534 GB trace 来自大型公有云网关，规模可信；但主实验用一周内不同时段的 10 分钟 trace，30-day 实验还人工在第 10/20 天注入 zero-day traffic。它能说明机制方向，但不能完全覆盖长期 concept drift、label delay、label poisoning 和业务协议变化。

## 核心方法

Trochilus 的核心路线是把 pattern matching 拆成两个世界：离线控制平面负责把规则和数据训练成模型，在线数据平面只做 switch 能承受的 table lookup 与投票。

第一步是 **pattern modelization**。系统从 Snort/Suricata 规则里提取 PCRE pattern，先用 Thompson construction 转 NFA，再 powerset construction 转 DFA，并做 DFA minimization。随后把 DFA 的 transition weight、initial weight、final weight 参数化为 BRNN 的权重；在 identity activation、无 input embedding bias 的设定下，DFA 的 forward score 可以写成 recurrent form。这个设计回应观察 2：cold start 时 BRNN 近似保留原始规则语义，有 labeled data 后又可以像模型一样训练。

第二步是 **SSKD + SMF**。BRNN 不能直接部署到 [[P4]] / [[Tofino]] 数据平面，因为它需要浮点和大量状态。Trochilus 用 semi-supervised [[Knowledge-Distillation]]：BRNN 对 labeled/unlabeled data 产生 soft labels；labeled data 的 hard label 和 soft label 按 β 混合，unlabeled data 的 hard label 来自 BRNN prediction；再用混合标签训练 soft multi-view forest (SMF)。SMF 由多个 soft decision tree (SDT) 组成，每轮训练后提高 misclassified samples 的权重，并过滤低权重样本，让多个 SDT 学到不同视角。

第三步是 **model representation**。SDT 使用 binary features，树上每条 root-to-leaf path 可以编码成一个 ternary match entry；每个 SDT 对应一组 model tables，多个 SDT 的结果再由 aggregation table 做 majority vote，最后 decision table 执行 drop/pass/alert/forward 等动作。这里 Trochilus 避开了 decimal feature range matching 的 prefix expansion 问题，把模型推理压成 match-action。

第四步是 **entry cluster**。由于大多数 tree entries 的 mask 很稀疏，Trochilus 不用一张全宽表匹配所有 features，而是把 entries 按 Jaccard distance 聚成 k 个 subset，每个 subset 只匹配自己需要的 feature positions。这个优化问题本身 NP-hard，论文给出 k-medoids 风格启发式；最坏情况下不比原始 SMF 更省，但在实验 pattern set 上显著降低 TCAM。

第五步是 **sliding window**。Tofino 1 单个 ternary table key 宽度有限，论文固定 win=64 bytes，并用 step s 在 payload 上滑窗；若最大 pattern 长度 L 满足 L <= win - s，则任意 pattern 都能落进至少一个 window。超过单 pipeline 可检查深度时，Trochilus 通过 recirculation 丢弃已检查部分继续处理。这回应观察 1，但也把吞吐和安全性绑定到 payload length distribution。

更新流程是离线完成的：每天或周期性收集新的 labeled attack traffic，增量训练 BRNN/SMF，重新生成表项并安装到 switch。论文声称这种更新不影响在线服务，但没有深入展开 control-plane 安装延迟、双版本切换、回滚或 poisoning 防御。

## 设计取舍

- **用 learned classifier 换可更新性。** Trochilus 从传统「规则是否匹配」转为「模型是否判为某类」，收益是可用 labeled data 自动吸收新模式；代价是 false positive/false negative、可解释性和 adversarial robustness 变成系统问题。
- **用 switch line rate 换 payload coverage 的复杂度。** 64-byte sliding window 适合论文中 95% matched segment length < 50 bytes 的 workload；长 payload 依赖 recirculation，吞吐随 payload length 下降，并暴露 jumbo-frame throughput exhaustion 面。
- **用 entry cluster 换表管理复杂度。** k 越大 TCAM 越省，实验从 80.9% 提升到 92.5%；但每个 cluster 需要单独 table，管控复杂度和 pipeline 资源压力增加。
- **用 PCRE 子集和 byte-level view 换实现简单。** DFA→BRNN 的漂亮之处在于语义桥接简单，但协议语义、编码变体、跨包状态、压缩和加密都被推到边界之外。
- **用离线更新保持数据平面简单。** 表项安装可以不打断 packet processing，但模型训练、label collection、canary、rollback、版本一致性都转移到控制平面，论文没有把这套运维闭环讲透。

## 实验与结果

**指标、基线与边界**：classifier accuracy、TCAM usage、theoretical throughput；Trochilus vs TPS/BOLT/SRF；Snort/Suricata rule categories、multi-string patterns≤3500、Tofino but 40Gbps generators（§6）。

- **数据集与规则集**：使用 Snort 2.9.7.0 和 Suricata 5.0 / ET-OPEN 规则，覆盖 info、web specific app、malware、sql、exploit 五类，约 4000 patterns；534 GB packet traces 来自大型公有云网关，train/test = 7:3。论文统计 matched segment length 中 95% 小于 50 bytes，这支撑 win=64 的滑窗设定。
- **实现**：数据平面约 2000 行 P4_16，控制平面约 4000 行 Python；部署在 12-stage、6.4 Tb/s EdgeCore Wedge 100BF-65X Tofino switch 上，发包由两台 40 Gbps Dell R230 + DPDK Pktgen 负责。
- **Teacher model accuracy**：BRNN 在 zero-shot 下与 TPS 同为约 85.2%；10% training data 后平均 96.3%；full training 后约 98.5%。LSTM/CNN/GRU 在 zero-shot 约随机猜测，full training 约 93%，DAN 明显更低。
- **Student model accuracy**：SMF zero-shot 约 83.7%，接近 TPS；few-shot 下比非蒸馏 tree-based models 高 12% 以上，比 SRF 高约 5%；full training 后超过 97.1%，相对 TPS 可提升 11% 以上。
- **Multi-string 对比**：T-MSM-12 在 zero-shot 下比 BOLT 高约 2%，few-shot/full training 下比 BOLT 高 15% 以上、比 TPS 高 10% 以上；BOLT 仍停在约 82%，因为 automaton 不能从数据里学习新模式。
- **TCAM**：在 3500 multi-string patterns 上，T-MSM-4/8/12 分别比 BOLT 降低 97.8% / 95.6% / 93.4% TCAM；full pattern matching 比 multi-string 约多 15% TCAM，但仍显著低于 BOLT 的 multi-string 设置。
- **Throughput**：受 traffic generator 限制，论文用类似 BOLT 的方法模拟理论上限。payload 越长，recirculation 越多，吞吐下降；Trochilus-8 和 Trochilus-12 分别达到 BOLT 的 2.3× 和 2.8×，在短 payload 下接近 6.4 Tbps switch 上限。
- **Long-running update**：30-day 实验中第 10/20 天注入 zero-day traffic，Snort accuracy 分别下降约 4%/6% 并持续走低；Trochilus 第 10/20 天下降约 3%/4%，次日通过 labeled data 更新后回到约 97%。

## Claim–Evidence Map

| Claim | Evidence | Metric / baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| BRNN 准确率随标签量提升且类别相关 | Snort info 84.368/98.254/99.17% (0/10/100%) | vs TPS/LSTM/CNN/GRU/DAN；该 rule category/split | §6.1，§6.4 Tables4–6 | high |
| SMF 结果不代表全类别统一96% | web specific app 85.02/96.34/96.73%；SRF10%90.83% | specified category；vs TPS/DT/RF/MF/SDT/SRF | §6.4，Table5 | high |
| TCAM 数字只适用 multi-string | 97.8/95.6/93.4% | vs BOLT、patterns≤3500；full pattern约多15% | §6.5，Fig.9 | high |
| 吞吐是模拟上界而非6.4Tb/s实测 | 2.3×/2.8× | 40Gbps traffic generators、recirculation/payload effect；vs BOLT | §6.3、§6.5 Fig.10 | high |
| 更新实验为人工注入/离线标签 | day10/20 -3/-4%，next day~97% | 30-day replay、10% injected zero-day、daily offline update | §6.7，Fig.13 | high |

## Critical Analysis

### 论证链条

论文的主链条基本闭合：PISA switch 有吞吐但不能直接跑 regex automata；DFA→BRNN 给 cold-start 和可训练性；SSKD/SMF 把 teacher 压成 binary tree ensemble；tree encoding + entry cluster 把 SMF 压进 match-action tables；sliding window 处理 arbitrary payload offset。每个设计都能回到一个明确瓶颈。

最需要小心的是「complete pattern matching」这个 claim。Trochilus 支持比 multi-string 更完整的 PCRE 子集，并能部署到 switch，但最终在线路径是 learned SMF classifier，不是传统意义上逐条规则精确判定的 automaton executor。论文说 SMF 到 table entries 是 lossless，指的是模型表示到数据平面表项的转换无损，不等于 BRNN/SMF 对原始 pattern 语义永远无损。这个区别决定了它更像 learning-enhanced IDS classifier，而不是简单替代所有 regex engine。

### 假设压力测试

最脆的 workload 假设是 plaintext byte-level payload。TLS/QUIC、压缩、HTTP/2 framing、非 ASCII encoding、跨包重组、应用层 normalization 都可能让 64-byte window 看到的 feature 不再代表安全语义。论文提到可结合 decryption mechanisms，但这会重新引入昂贵或复杂的前处理系统，削弱「低成本 switch-native」的整洁性。

另一个压力点是 update trust。自动从 labeled traffic 学新规则，听上去解决了专家维护成本；但真实部署会遇到 label delay、label noise、attack traffic contamination 和 model poisoning。论文的 30-day 实验说明模型能从注入的新攻击恢复，但没有证明在对抗性数据或弱标签条件下仍能安全更新。

资源外推也需要保留。实验 pattern set 约 4000，paper 承认单 switch 存不下时需要分布到多个 switches。多 switch 分布会引入转发路径、intermediate result coordination、failure recovery 和一致性问题，这些都没有实现。

### 实验可信度

实验有几个强点：使用 Snort/Suricata 真实规则、云网关 trace、真实 Tofino prototype，并且同时报告 accuracy、TCAM、throughput 和 maintenance。相比只做仿真的 in-network ML 工作，这个系统落地感更强。

但也有三处边界。第一，throughput 主结果不是完全由 testbed 打满验证，而是因为 40 Gbps traffic generator 不足以覆盖 6.4 Tbps，用 BOLT-style 方法模拟理论上限。第二，accuracy 的 ground truth 来自数据中心已有 advanced attack detection / application identification system；这套 labeler 的误差会传递到训练和评估。第三，baseline 在「完整 regex pattern matching on switch」上没有同类系统，只能拿 BOLT 的 multi-string 方案、TPS 和常见 ML/tree models 分别比较，因此每个比较只覆盖主张的一部分。

### 系统性缺陷

论文自己讨论了两类攻击：jumbo frames 触发大量 recirculation 的 throughput exhaustion，以及 adversarial perturbation 导致 misclassification。它提出用 network measurement 检测异常 recirculation、用 fuzzy matching 提升鲁棒性，但这些都还不是原型的一部分。

论文未充分讨论 tail latency、误报/漏报的安全成本、模型更新回滚、表项安装期间的一致性、与现有 ACL/routing/telemetry 共存时的资源隔离，以及模型决策的可观测性。对安全系统来说，这些工程细节会直接影响是否能上线。

## 局限与 Future Work

- **局限 1：明文和 byte-window 假设较强。** Future work：在 TLS termination 后流量、QUIC/HTTP2、压缩 payload、UTF-8/二进制协议上分别测量 pattern coverage、false positive/false negative 和 recirculation 开销。
- **局限 2：更新链路缺少安全闭环。** Future work：构建带 label delay、label noise、poisoning traffic 的 30-day replay，量化 accuracy recovery time、错误更新率、rollback latency 和 table version consistency。
- **局限 3：吞吐验证依赖理论上限模拟。** Future work：用足够多端口或硬件流量发生器打满 6.4 Tbps，按 payload length mix、jumbo ratio、window step s 和 recirculation count 给出真实 throughput/tail latency 曲线。
- **局限 4：learned matching 的语义可解释性弱于规则引擎。** Future work：对每次 alert 输出触发的 windows、SDT paths、近似对应规则或 top-k pattern explanations，评估是否足以支持安全运营排障。
- **局限 5：单 switch capacity 之外仍是草图。** Future work：实现 multi-switch model sharding，测量跨 switch forwarding overhead、failure recovery 和与生产 routing policy 的冲突。

## 相关

- **相关概念**：[[Programmable-Switch]]、[[Pattern-Matching]]、[[DFA]]、[[Knowledge-Distillation]]、[[TCAM]]、[[P4]]
- **同类系统**：[[BOLT]]、[[Hyperscan]]、[[Snort]]、[[Suricata]]、[[Pigasus]]、[[DeepMatch]]
- **同会议**：[[ATC-2025]]
- **对比**：本文主要与 BOLT 的 programmable switch multi-string matching、TPS 的传统规则匹配，以及 DT/RF/MF/SDT/SRF 等 data-plane-friendly ML baselines 对照；尚未有独立 comparison 页。
