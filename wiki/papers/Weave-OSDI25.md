---
type: paper
name: Weave
full_title: "Weave: Efficient and Expressive Oblivious Analytics at Scale"
authors: [Mahdi Soleimani, Grace Jia, Anurag Khandelwal]
venue: OSDI
year: 2025
tags: [oblivious-analytics, mapreduce, tee, noise-injection, security]
source_pdf: "[[osdi25-soleimani.pdf]]"
source_md: "[[osdi25-soleimani]]"
---

# Weave: Efficient and Expressive Oblivious Analytics at Scale (OSDI 2025)

> **一句话总结**：在 TEE 内 oblivious MapReduce 用 random-shuffle + 采样直方图 + 噪声注入 balanced-shuffle 把访问模式防护开销从 log-linear 压到常数（默认 ~3.1× 带宽），端到端比 Opaque / Shuffle&Balance 快 4–10×，IND-CDJA 下仍支持 median 等非关联 reduce 与自定义分区。

## 问题与动机

云 [[MapReduce]] 即便数据静态/传输加密并在 [[TEE]] 内计算，mapper–reducer 通信量与 enclave 内存访问模式仍随输入 key 分布变化，诚实但好奇的云厂商可推断敏感记录（split-based：按时间切分导致仅部分 mapper 发 COVID 记录；distribution-based：流感 1.5× 哮喘 则 reducer 流量可区分）。Opaque 用 oblivious sort（log-linear、限制非关联 reduce）；Shuffle&Balance 用 Melbourne shuffle + bin-pack（log-linear、破坏 sort/自定义分区）。作者需同时满足：**强 obliviousness**、**大规模常数开销**、**MR 表达力**——并证明一般 Map 若可 emit 任意多条 intermediate，IND-CDJA 安全方案的带宽开销无上界，但常见 job 的 $c \leq 1$ 使常数开销可达。

## 关键观察 / 隐含假设

- **观察 1**：MR shuffle 泄露本质是「worker 对之间可观测流量与 key 分布相关」——load-balancing 骨架 + oblivious storage 式 **noise injection**（只注入刚好抹平分布差的 fake 流量）可达理论最低网络开销，不必全局 oblivious shuffle。
  - **依赖假设**：Map 每输入记录 intermediate 条数上界为常数（通常 $c=1$）；key-value 可固定长度或 padding（长度侧信道 out of scope）。
  - **可能失效场景**：flatMap 等 $c \gg 1$ 需 filler 至 $C$，开销 $\frac{C}{c_{avg}}$ 倍（Word Count $C$ 4→48 时 1.32×→5.34×）。
- **观察 2**：histogram 与 balanced-shuffle 的数据依赖状态可放进 EPC，扫描类访问可留普通内存——EPC 占用相对数据集可 <5%（十亿记录实验 <5% EPC）。
  - **依赖假设**：Azure DC8s v3 级 SGXv2 EPC 充足；AEX-Notify + core isolation 等 proxy 设计可抑制页故障/缓存侧信道（<20% 常数开销）。
  - **可能失效场景**：EPC 耗尽需软件 oblivious 回退（全文版本讨论，主文未实现）；commodity TEE 已知多种侧信道仍依赖缓解而非形式化零泄露。
- **假设 1**：对手已知 job 定义与数据集宏观性质（如疾病相对频率），安全目标是隐藏**具体记录与 key 实例的对应**，而非隐藏 job 类型。
  - **证据强度**：中；与 Opaque/S&B 威胁模型一致，但限制了对 secret job 的 timing 防护。

## 核心方法

**IND-CDJA**：多项式对手观察网络 transcript $\tau^N$ 与内存 transcript $\tau^M$，无法区分同规模两数据集 $D_0/D_1$ 上的执行——比 Opaque「流量完全相等」更实用，比 Shuffle&Balance「strong hiding」不泄露最热 key 计数更强。

**三阶段 shuffle**（替代经典 shuffle）：
1. **Random-shuffle**：mapper 将每条 intermediate 伪随机发往 weaver，消除 split-based 泄露；各 weaver 期望得 $\hat{n}_k/w$ 条 key $k$。
2. **Histogram**：本地直方图 pad 到固定长度后加密广播，聚合成全局 $\hat{h}$；**采样优化**（$\beta=1\%$）只统计 $\beta\hat{n}$ 条，balanced-shuffle 再加 $\delta=5\%$ fake 流量，Chernoff 界保证 IND-CDJA。
3. **Balanced-shuffle**（Algorithm 1）：每 reducer 固定收 `kv_tot = α·n̂/r`（α 下界 $2r/(r+1)$）；贪心分配真实 KV，fake 由共享 PRG 的 w 面骰子决定发送 weaver，使每 weaver→reducer 期望流量同为 `kv_tot/w`。

**扩展**：关联 reduce 可 split boundary key、α=1 无 fake；histogram 键序支持 sort/用户自定义分区；$c>1$ 用 filler + invalid bit。

实现：Apache Spark + 1500 行 Scala；Gramine LibOS + Intel SGX；三真实数据集（Enron 137M、NY Taxi 148M、Pokec 31M）× HistogramCount/Sort/Median/InvertedIndex/PageRank。

## 设计取舍

- **取舍 1**：极高 key skew 时需增大 α 或牺牲正确性（丢弃过热 key 的真实记录并通知用户）——换不泄露「哪个 key 最热」。
- **取舍 2**：采样直方图引入估计误差，用额外 δ 噪声换通信与 EPC 可扩展性。
- **边界条件**：微批/streaming MR 需改造 random-shuffle（§6）；变长 record padding 昂贵；timing 侧信道未处理。

## 实验与结果

- 10 节点 Azure SGX 集群：Weave 端到端为 insecure TEE baseline 的 1.65–2.83×；Opaque 2.8–11.2× 慢于 Weave，S&B 1.5–5.9× 慢。
- Shuffle 开销：Weave 相对 insecure shuffle 1.5–2.7×；S&B Melbourne 3.9–8.3×；Opaque column-sort 7.2–20.2×。
- 关联 reduce 优化：HistogramCount 网络开销再降 ~50%；采样直方图使 InvertedIndex/HistogramCount 再快 18%–30%。
- 扩展性：Weave 与 insecure baseline 随数据量/ worker 数线性；Opaque/S&B 超线性；500M 记录 EPC 开销 <3.6%。
- α 敏感性：max key 热度 4%→99% 时 Median 慢 7.9×；真实社交网 skew <3% 远低于默认 α≈1.85 阈值。

## Critical Analysis

### 论证链条

Theorem 2.1（任意 Map → 无界开销）与 Theorem 3.1–3.2（α 下界与可达性）为 noise injection 方案提供理论护栏；IND-CDJA 游戏 + 归约到 PRG/加密/EPC 构成完整安全叙事。4–10× 加速主要来自把瓶颈从 log-linear shuffle 换成 O(n̂) random-shuffle + 常数因子 fake 流量，论证与测量一致。

### 假设压力测试

- **已证明**：多 workload 下对 Opaque/S&B 的数量级优势；关联 reduce α=1 近 insecure；EPC 占比小。
- **可能失效**：极端 skew 或巨大 $C$ 时常数因子恶化；采样+δ 在中小 $\hat{n}$ 上 ε 需仔细调参；正确性失败路径（过热 key）虽不增泄露但损害可用性。
- **论文未覆盖**：变长 KV padding（Length leakage [68]）；分布式 ML all-reduce 等其它通信模式；形式化验证 TEE 上的部署。

### 实验可信度

自研 Spark 移植与 Gramine 基线公平性通过复现 prior 数字验证；NA 标记暴露 Opaque 不支持 median、S&B 不支持 sort 的功能差异。TEE 本身 1.9–2.8× 开销使所有方案下限抬高，Weave 相对 insecure 的倍数仍有意义。

### 系统性缺陷

仍依赖 honest enclave 代码与 attestation；SGX 侧信道缓解非证明安全；streaming/微批需重新设计；对手若不知 job 则 timing 成洞；$c>1$ 时与任何 IND-CDJA 方案一样难逃 filler 税。

## 局限与 Future Work

- **局限 1**：固定长 record 与无 timing/length 防护；微批 streaming 未支持。
- **局限 2**：极高 popularity key 需调 α 或接受静默错误结果。
- **Future work 1**：oblivious storage 的动态分布适配用于微批 MR；ML collective 通信的 noise-injection。
- **Future work 2**：变长数据高效 padding 与 secret-job timing 防护的统一框架。

## 相关

- **相关概念**：[[TEE]]、[[MapReduce]]
- **同类系统**：Opaque、Shuffle&Balance、Hermetic
- **同会议**：[[OSDI-2025]]