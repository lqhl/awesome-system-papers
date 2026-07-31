---
type: paper
name: Spain
full_title: "Spain: Succinct proofs for numerical computations"
authors: [Zachary DeStefano, Noah Golub, Zile Huang, Julius Zhang, Sam Frank, Michael Walfish]
venue: OSDI
year: 2026
tags: [succinct-proofs, numerical-computing, cryptography, verification, machine-learning]
source_pdf: "[[osdi26-destefano.pdf]]"
source_md: "[[osdi26-destefano]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 数值计算的简洁证明（OSDI 2026）

> **原题**：Spain: Succinct proofs for numerical computations

> **一句话总结**：Spain 观察到数值程序本就接受有界近似误差，因而不必把每个 floating/fixed-point 操作精确 bit-blast 到有限域；它以 approximate rational constraints、新 proof backend 和单约束 division/sqrt 等 arithmetization，把约束数降低 32–17,000 倍、通用 prover 加速 8–2,700 倍，并在部分大问题上首次使 verifier 比 native execution 更便宜。

## 问题与动机

[[Succinct-Proof|succinct proof]] 可让 verifier 确认不可信 prover 执行了约定程序而不重算，但程序必须先变成有限域上的 R1CS。finite field 没有负数、顺序或真实数近似语义，一个比较就要按 bit 展开；division、square root 和 transcendental function 更昂贵。传统 prover 因而常比 native 慢 10^5–10^6 倍，数值计算几乎不可用。

Spain 的目标是通用 backend、不依赖特定应用数学；verifier 比 native execution 便宜；prover overhead 尽量不超过 10^3。它不追求 zero knowledge，而追求 execution integrity，覆盖 linear program、ML primitive/GPT-2、fluid simulation 和 geolocation。

## 关键观察 / 隐含假设

- **观察 1：数值程序的规范本来就是“结果在误差界内”，exact finite-field equality 是错误抽象。** Spain 直接证明 R1CS residual norm 小于阈值，而不是逐项显式编码 rounding（§3–4）。
  - **依赖假设**：用户能证明 approximate constraints 与目标 floating/fixed-point implementation 之间的 translation fidelity。
  - **可能失效场景**：要求 IEEE-754 exact rounding mode、NaN/Inf/exception 或 bit-reproducibility 的应用。
- **观察 2：bit-level range/order enforcement 是约束爆炸主因。** approximate sqrt 可紧凑表达 comparison、range、min/max，division 让 rational approximation 比高阶 polynomial 更快收敛（§5）。
  - **依赖假设**：输入 domain、denominator/numerator bound 和 error budget 已知，不跨越不连续点或 singularity。
- **观察 3：verifier 有较大 fixed cost，batch 可摊薄。** GPT-2 passes 增大时 verifier work 亚线性，16 passes 时甚至略优于专用 zkGPT（§7.3）。
  - **依赖假设**：应用能形成同步 batch；latency-sensitive 单请求无法获得该收益。
- **假设 1：允许 L2 aggregate residual 不会让 prover 在个别操作上集中大误差。**
  - **证据强度**：中；协议 soundness 有严格证明，但应用级语义仍依赖用户选择 norm 与每项 error analysis。

## 核心方法

front-end 在有理数域上生成 approximate R1CS，使每条 constraint 允许 bounded residual。Spain 将 assignment/error norm commitment 后，通过基于 Spartan/Zaratan 的 sum-check 证明 aggregate residual，使用改造 DARK polynomial commitment 处理大整数/有理数承诺，并随机选 prime 防止 prover 对 norm 撒谎（图 2、附录 B）。

其 arithmetization 不把 operand 拆成 bits：加乘自然表示，division 与 sqrt 各可用单个或少量 approximate constraint；sqrt 进一步构造 order/range/piecewise operation。`exp` 等 transcendental function 采用 Remez/rational approximation，因为 division 在 Spain 中几乎无额外成本。GPT-2 matrix multiplication 使用 approximate Freivalds checker 与 I-R1CS，避免为每个乘加生成完整 constraint。

backend 支持 SIMD batching 和 just-in-time R1CS；实现用 double/quad precision 生成 witness，再以 256/512/786-bit integer 为 DARK commitment 精确处理 scaled rational。关键不同是误差“内建进约束”，但用户必须额外给出 translation soundness/completeness 证明。

## 设计取舍

- **紧凑性换语义责任**：front-end 大幅省约束，却要求开发者证明 approximation 与原程序一致；这不是自动 compiler guarantee。
- **通用性换专用性能**：Spain 明显快于通用 baseline，但 GPT-2 上仍慢于专用 zkGPT。
- **非零知识换效率/目标收缩**：系统只保证 execution integrity，不隐藏 witness。
- **batch throughput 换等待时间与内存**：GPT-2 `seq=32, passes=16` prover 需约 267 GB；同步积累 batch 会增加端到端 latency。
- **边界条件**：大计算、小 input/output、可容忍近似且可 batch 时 verifier 容易 break even；小 computation 或巨大 public I/O 时 variable cost 本身可能超过 native。

## 实验与结果

- linear programming、Softmax/LayerNorm/GELU/GPT-2、8×8/16×16 10-step fluid simulation 与 geolocation 上，Spain constraint count 较 baseline 少 32–17,000 倍（图 4、§7.4）。
- 约束缩减使通用 prover 加速 8–2,700 倍，prover/native overhead 降到 10^3–10^5；多数 verifier/prover 较 baseline 至少快一个数量级（图 4）。
- Spain 仍慢于 GPT-2 专用 zkGPT；ZKLP verifier 快 4–5 倍，但其 fixed setup 成本超过单实例 verifier work 50,000 倍（§7.1、7.3）。
- 最大 linear program `scsd8` 上 verifier 比 native execution 更便宜；多数单实例仍未 break even，batch 后 GPT-2 verifier 增长亚线性，`seq=32, passes=16` 略快于 zkGPT verifier（图 4、6）。
- 内存是 prover 主 bottleneck：GPT-2 `seq=32, passes=1` 约 41 GB，`passes=16` 约 267 GB；setup cost 为 negligible 到单实例 verifier 的 5 倍（§7.2–7.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| approximate arithmetization 消除主要约束爆炸 | 图 4：constraint 少 32–17,000 倍 | 四类 benchmark、论文 front-end 与自然 baseline | 强 |
| Spain 是更快的通用 numerical prover | 图 4：prover speedup 8–2,700 倍 | 不包括更快但只支持 GPT-2 的 zkGPT | 强 |
| verifier 可在合理规模下胜过重算 | `scsd8` 与 batch GPT-2 结果（§7.3） | 只在部分大实例/batch；多数单实例未 break even | 中 |
| prover overhead 达到目标 regime | §7.4：部分为 native 的约 10^3 倍 | 其他实例仍为 10^4–10^5，硬件不同 | 中 |

## 批判性分析

### 论证链条

“数值计算已近似→约束也应近似→bit decomposition 可省”是反直觉但闭合的核心链条，constraint count 与 backend-per-constraint 反而较慢的结果进一步证明收益来自新抽象而非实现调参。最关键的边界是 Spain 证明了某个 approximate constraint system，而该 system 是否忠实描述用户代码仍需额外数学分析。

### 假设压力测试

误差在深网络/迭代模拟中可能放大；aggregate norm 允许误差分配方式与逐操作 IEEE bound 不同。近 singularity 的 division、branch boundary、NaN/overflow 和 chaotic simulation 都会使“小局部 residual”不保证最终语义接近。恶意 prover 可能利用 front-end 给出的过宽 domain，而非攻破 backend soundness。

### 实验可信度

应用跨度大、同时报告 native/prover/verifier/constraint/proof size，且区分专用 zkGPT 与通用 baseline，比较较透明。ZKLP-FE 的 GPT-2 结果因无法运行而线性外推；部分 break-even 依赖 batch 和不同 prover/verifier hardware。流体网格仅 8/16，离实际 GPU-scale simulation 很远。

### 系统性缺陷

41–267 GB 内存和 10^3 以上 prover overhead 仍限制部署。Spain arithmetization 绑定自有 backend，不能直接获得其他 proof system 的 non-interactivity/zero knowledge/fast verify 属性。用户还需维护 error parameters、range proof 与 approximation coefficient，错误配置可能产生形式上 sound、语义上无用的证明。

## 局限与后续工作

- **局限 1**：多数单实例 verifier 尚未比 native 快，prover 即使改善后仍慢 3–5 个数量级。
- **局限 2**：不提供 zero knowledge，且新 arithmetization 暂不能移植到其他 backend。
- **后续工作 1**：对 IEEE-754 exception、branch boundary 和 iterative error amplification 建自动 translation-fidelity checker，并以 differential test 验证。
- **后续工作 2**：将 SPARK 类 delegation 或更快 rational/integer commitment 接入，以 verifier time、proof size 和 prover memory 测量收益。
- **后续工作 3**：在 GPU-scale fluid/[[LLM|LLM]] workload 上探索 streaming commitment，使 peak memory 低于 64 GB并测出实际 batch break-even latency。

## 相关

- **相关概念**：[[Succinct-Proof]]、[[Zero-Knowledge-Proof]]、[[R1CS]]、[[Approximate-Computing]]
- **同类系统**：[[Spartan]]、[[DARK]]、[[zkGPT]]、[[Zaratan]]
- **同会议**：[[OSDI-2026]]
