---
type: paper
name: Spain
full_title: "Spain: Succinct proofs for numerical computations"
authors: [Zachary DeStefano, Noah Golub, Zile Huang, Julius Zhang, Sam Frank, Michael Walfish]
venue: OSDI
year: 2026
tags: [succinct-proofs, numerical-computing, cryptography, verification, approximate-computing]
source_pdf: "[[osdi26-destefano.pdf]]"
source_md: "[[osdi26-destefano]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向数值计算的简洁证明（OSDI 2026）

> **原题**：Spain: Succinct proofs for numerical computations

> **一句话总结**：Spain 抓住“数值程序本来就允许近似误差”这一点，用有理数上的近似 R1CS 和新的证明后端代替逐位模拟浮点逻辑，使约束数比自然基线少 32–17,000 倍、通用 prover 快 8–2,700 倍，并在最大的线性规划实例上让 verifier 的 30 ms 验证低于 300 ms 的原生重算。

## 问题与动机

简洁证明（succinct proof）让 verifier 检查不可信 prover 是否执行了约定程序，却不必自己重算。传统系统先把程序翻译成有限域上的 R1CS。有限域没有负数、大小关系和近似数值语义，因此 division、square root、comparison 等普通数值操作常要拆成几十个甚至按位增长的约束。论文指出，现有通用 prover 的开销通常是原生执行的 \(10^5\)–\(10^6\) 倍（§1–§2）。

这种表示对数值程序尤其不合适。浮点和定点程序的正确含义通常不是“每一步精确相等”，而是“每一步或最终结果落在允许误差内”。如果证明系统仍要求有限域中的精确相等，就必须把 rounding、range 和数字电路全部显式编码，证明成本远大于实际计算。

Spain 要同时争取三个目标：后端不绑定某一种应用；verifier 比原生重算便宜；prover 开销在可行配置下降到原生执行的 \(10^3\) 倍量级。它只验证执行完整性，不提供 zero knowledge。评测覆盖 linear programming、Softmax/LayerNorm/GELU、GPT-2、二维流体模拟和 geolocation（§1、§7）。

## 关键观察 / 隐含假设

- **观察 1：近似误差不是必须消除的实现噪声，而是数值程序规范的一部分。** Spain 因此把“约束残差不超过界限”直接写进 arithmetization，而不是精确模拟 IEEE-754 电路（图 1、§3）。
  - **依赖假设**：应用能给出有意义的误差目标，并能证明约束误差与原程序每个操作的误差之间如何对应。
  - **可能失效场景**：程序依赖特定 rounding mode、NaN/Inf、overflow、exception 或逐位可复现结果时，近似语义不足以代替精确语义。
- **观察 2：约束数和 witness 大小直接控制证明成本，而 comparison/range check 的逐位分解正是主要膨胀源。** Spain 的 division 和 square root 各只需一个近似约束，比较也不再随 bit width 线性增长（§2.2、§5）。
  - **依赖假设**：输入范围已知；division 的 denominator 远离 0；rational approximation 不跨越 singularity 或不连续点。
  - **可能失效场景**：需要严格布尔结果或很强 relative-error guarantee 时，必须混入 exact constraint，紧凑性会下降。
- **观察 3：sum-check 不能直接证明 \(\ell_\infty\) 最大误差，却能证明总平方误差。** 若残差向量的 \(\ell_2^2\) 不超过 \(\epsilon^2\)，每条约束的残差自然不超过 \(\epsilon\)；代价是 honest prover 为保证 completeness，需要把每条残差压到约 \(\epsilon/\sqrt{m}\)（§4.1、附录 D.3）。
  - **证据强度**：强；附录 B、E、F 给出后端 soundness、translation fidelity 与端到端正确性证明。
- **观察 4：verifier 的主要成本中有可按同一 R1CS 结构摊销的固定部分。** SIMD batching 让 GPT-2 的 verifier 时间随 passes 亚线性增长（§4.3、§7.3、图 6）。
  - **依赖假设**：部署能积累同一程序的多个输入，并接受等待 batch 形成；低延迟的单请求不能得到同样收益。

## 核心方法

Spain 的 front-end 把程序翻译成有理数域 \(\mathbb{Q}\) 上的近似 R1CS。传统约束要求残差等于 0，Spain 则允许每条约束有界偏差。它另外定义 translation fidelity：一方面，任何满足约束误差界的 assignment 都必须对应原程序允许的输出；另一方面，足够高精度的诚实执行必须能生成可接受的 assignment（§3、§5、附录 E）。这一步把应用语义与 proof backend 明确分开。

在后端，prover 先用 DARK 对 witness polynomial 作承诺，然后 verifier 才随机选择 prime \(q\)。双方把有理数映射到有限域 \(\mathbb{F}_q\)，并用改造后的 Spartan sum-check 证明所有约束残差的平方和等于 prover 声称的值；verifier 还检查该值不超过 \(\epsilon^2\)（图 2、§4.2）。先承诺、后选 prime，可使不同有理数映射后意外碰撞的概率保持很小。

为让这个映射可证明安全，R1CS 和 assignment 使用以 2 的幂为共同 denominator 的有理数，并限制 numerator、约束数和变量数。论文给出的实现区间是约束数和变量数均不超过 \(2^{32}\)、随机选择 128-bit prime；在这些参数下，后端 soundness error 不超过 \(2^{-40}\)（附录 B.4）。Spain 还利用 verifier 知道 RSA group order 的交互式设定，省掉 DARK 中昂贵的 proof-of-exponentiation（§4.2.3、附录 C）。

front-end 的紧凑性来自新的数值 gadget。division 用 \(y\cdot z\approx x\)，square root 用 \(y\cdot y\approx x\)；approximate square root 又可构造 order、range、max、ReLU 等操作。transcendental function 使用 rational approximation：在 Spain 中 division 很便宜，因此 Padé/Remez 一类分式近似能用相近约束数覆盖比 polynomial approximation 更宽的区间（§5）。

实现提供 gadget、ONNX 和 linear-programming 三种 front-end。ONNX 路径会改写模型以输出辅助 witness，并用自写 executor 执行 double 或 quadruple precision；后端再把值缩放成 256/512/786-bit integer 供 DARK 使用（§6）。GPT-2 的 matrix multiplication 采用 approximate Freivalds checker 和 I-R1CS，避免为每个乘加都生成完整约束；SIMD-R1CS 则负责同结构实例的批处理（§4.3、§7）。

## 设计取舍

- **少约束换更多语义分析**：Spain backend 能证明“给定近似 R1CS 被满足”，但用户仍要选择误差界、输入范围和近似函数，并证明它们忠实描述目标程序。
- **soundness 换 honest prover 精度**：平方和检查能保证任何单条残差不越界，但 completeness 要求 witness 比 verifier 最终承诺的误差界更精确；约束越多，所需精度越高。
- **通用性换专用性能**：Spain 可覆盖多类数值程序，但 GPT-2 上仍显著慢于只为该模型结构设计的 zkGPT。
- **交互式协议和非隐私目标换效率**：当前系统既不是 non-interactive，也不提供 zero knowledge；它不能直接替代需要隐私或离线 proof 的系统。
- **批吞吐换延迟和内存**：batch 可摊销 verifier 固定成本，却需要同步积累任务，并把 GPT-2 prover 的峰值内存推高到数百 GB。
- **后端耦合换新抽象**：approximate R1CS 暂时只能由 Spain backend 证明，不能直接获得 Groth16 等后端已有的快速验证、non-interactivity 或 zero knowledge。

## 实验与结果

- 在 Netlib linear programming、三种 ML primitive、GPT-2、8×8/16×16 且运行 10 个 timestep 的 fluid simulation，以及 Uber H3 geolocation 上，Spain 的约束数比 Otti、ZKLP-derived front-end 等自然基线少 32–17,000 倍（图 4、§7.1、§7.4）。
- 约束缩减带来 8–2,700 倍的 prover speedup；最大值来自 GPT-2 seq=2、passes=1 相对外推的 ZKLP-FE。相对原生执行，linear-programming 实例慢 4–180 倍，而 ML、fluid 和 geolocation 多数仍慢约 \(1.5\times10^3\)–\(1.2\times10^5\) 倍（图 4）。
- 最大 linear-programming 实例 scsd8 上，Spain verifier 用 30 ms，而 verifier 机器上的原生执行用 300 ms，达到约 10 倍的验证收益；多数其他单实例仍未达到 break-even（图 4、§7.3）。
- GPT-2 seq=32、passes=16 时，Spain verifier 为 79 s，略低于专用 zkGPT 的 93 s；但 Spain prover 为 3.3 h，zkGPT 为 1,000 s，且原生执行仅 7.0 s。这个结果说明 batch 主要帮助 verifier，不代表端到端成本已经接近原生（图 4）。
- ZKLP 在 geolocation 上的 verifier 比 Spain 快约 4–5 倍，不过其一次性 fixed cost 超过单实例验证工作的 50,000 倍；Spain 的 setup cost 在这些 benchmark 中从可忽略到单实例 verifier 的 5 倍（§7.3）。
- 全部实验为 CPU 单线程，至少运行 5 次，标准差不超过均值的 11%。GPT-2 seq=32 的 prover 内存从 passes=1 的约 41 GB 增至 passes=16 的约 267 GB；prover 和 verifier 分别运行在 64-core Xeon 8592+ 与较旧的 64-core Opteron 6272 上（§7、§7.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| approximate R1CS 显著减少数值程序的约束数量 | 图 4：少 32–17,000 倍 | 四类 benchmark；ZKLP-FE 结构为 synthetic，GPT-2 时间为外推 | 强 |
| 新抽象而非更快的单约束实现带来主要收益 | §7.1：Spain backend 每条约束反而比基线慢，但总 prover 快 8–2,700 倍 | 论文实现、CPU 单线程 | 强 |
| 后端能把总平方误差界转成逐约束误差保证 | §4.1、附录 B/F；实现参数下 soundness error 不超过 \(2^{-40}\) | \(m,n\) 均不超过 \(2^{32}\)，指定 denominator/numerator bound | 强 |
| verifier 在部分大实例或 batch 中有实际价值 | scsd8 的 30 ms 对 300 ms；GPT-2 batching（图 4、6） | 多数单实例未 break even，public I/O 仍有线性成本 | 中 |
| 系统对多种数值程序具有一定通用性 | LP、ML、fluid、geolocation 均成功翻译（§7） | fluid grid 很小；未覆盖训练、大型 GPU simulation 或异常浮点语义 | 中 |

## 批判性分析

### 论证链条

论文的主链条很清楚：数值程序允许近似 → exact finite-field constraint 造成不必要的逐位展开 → approximate R1CS 大幅减少约束 → 即使 backend 每条约束更慢，总证明仍明显更快。图 4 同时报告 constraint、prover、verifier、proof size 和 native time，能把“抽象变好”与“实现调优”区分开。正确性证明也覆盖了后端、front-end translation fidelity 和两者组合。

仍有一处责任落在系统之外：Spain 证明的是用户给出的近似约束，而不是自动证明这些约束就是原始 ONNX/浮点程序的完整语义。若用户给错 domain、error budget 或 approximation，proof 可以在密码学上 sound，却对应用问题没有意义。

### 假设压力测试

总平方误差检查本身不会允许某条约束集中超过 \(\epsilon\)；真正的压力点是 honest prover 必须达到约 \(\epsilon/\sqrt{m}\) 的更严格精度。模型或 simulation 变大后，\(m\) 增长会迫使 witness generator 使用更高精度。division 接近 0、branch boundary、NaN/Inf、overflow 以及迭代误差放大，也可能使局部近似约束无法代表用户关心的最终误差。论文通过静态分析和高精度执行处理 benchmark，但没有自动化覆盖一般程序。

### 实验可信度

benchmark 类型较广，且论文诚实报告 Spain 的两个主要弱点：zkGPT prover 更快，ZKLP verifier 更快。结果至少运行 5 次并给出波动上界。不过，ZKLP-FE 在 GPT-2 上不能真正运行，只能由 synthetic instance 线性外推；fluid simulation 最大只有 16×16 网格。全部证明实验为单线程 CPU，尚不能说明 GPU 数值 workload 或分布式 prover 的成本。

### 系统性缺陷

267 GB 峰值内存，以及不少 ML、simulation、geolocation workload 上 \(10^3\)–\(10^5\) 量级的 prover overhead，仍让部署范围很窄。交互式 protocol 要求 verifier 在线选 prime，缺少 zero knowledge，也不适合直接发布一次即可离线验证的 proof。DARK 是多数 benchmark 的主要 prover 成本；自写大整数、有限域、RSA group 和高精度 ONNX executor 还增加了实现与审计面积。论文未讨论服务故障恢复、任务取消、batch 排队时间或恶意 prover 的资源消耗控制。

## 局限与后续工作

- **局限 1**：多数单实例 verifier 仍比原生执行贵；除 linear-programming 外，许多 benchmark 的 prover 即使加速后仍慢 3–5 个数量级。
- **局限 2**：当前 approximate constraint 主要给 absolute-error guarantee，不完整支持 relative error、IEEE-754 exception、zero knowledge 和 non-interactivity。
- **局限 3**：translation fidelity 和精度参数需要人工数值分析，错误配置不会由 backend 自动发现。
- **后续工作 1**：为 division singularity、branch boundary、overflow/NaN 和迭代误差生成边界测试；用高精度参考实现检查每个 front-end 的 soundness/completeness 条件。
- **后续工作 2**：把论文提到的新型 integer/rational polynomial commitment 替换 DARK，分别测 prover time、verifier time、proof size 和 peak memory，验证是否达到预计的数量级收益。
- **后续工作 3**：实现 exact 与 approximate constraint 混合模式，在严格布尔比较和 IEEE exception 上测量约束增量及误差保证，避免把所有操作都强制放宽。
- **后续工作 4**：在更大的 [[LLM]] 和 GPU fluid simulation 上测出 batch-size—等待时间—峰值内存曲线，并报告 verifier 真正低于原生重算的最小 batch。

## 相关

- **相关概念**：[[Succinct-Proof]]、[[R1CS]]、[[Approximate-Computing]]、[[Zero-Knowledge-Proof]]
- **相关工作**：Spartan、DARK、Zaratan、Otti、ZKLP、zkGPT
- **相关系统主题**：[[LLM-Inference]]
- **同会议**：[[OSDI-2026]]
