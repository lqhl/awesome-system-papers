# WaferLLM: Large Language Model Inference at Wafer Scale

**作者**：Congjie He, Yeqi Huang, Pei Mu（University of Edinburgh）；Ziming Miao, Jilong Xue, Lingxiao Ma, Fan Yang（Microsoft Research）；Luo Mai（University of Edinburgh）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation），2025 年 7 月 7–9 日，Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/he
**源文件**：[osdi25-he.pdf](../../papers/osdi-2025/osdi25-he.pdf)

---

## 一、背景

大语言模型（LLM）推理正在快速增长为主流工作负载。推理分为两个阶段：prefill 阶段处理输入 token（以 GEMM 为主），decode 阶段逐 token 自回归生成（以 GEMV 为主）。由于 decode 阶段需要反复将整个模型权重加载到片上内存，LLM 推理本质上是内存带宽受限的。

为解决内存带宽瓶颈，AI 加速器正在广泛采用 system-on-wafer 集成技术，将芯片面积扩展到整个晶圆（比标准 GPU die 大 100 倍），集成数十万到数百万个 AI 核心，提供数十 GB 的片上内存和 PB/s 级别的内存带宽。代表产品包括 Cerebras WSE-2（850,000 核，40 GB 片上 SRAM，22 PB/s 带宽）和 Tesla Dojo。2025 年 2 月，Mixtral 和 Perplexity 已在生产中使用 wafer-scale 芯片，G42 建设了全套 wafer-scale 数据中心。

然而，现有 LLM 推理系统（如 vLLM、SGLang）均为 GPU 的共享内存架构设计，无法充分发挥 wafer-scale 加速器的潜力。

---

## 二、要解决的问题

Wafer-scale 加速器采用 mesh-based network-on-chip（NoC）架构，与 GPU 的共享内存架构有根本性差异，带来以下挑战：

1. **极端非均匀内存访问延迟**：在百万核规模的 mesh 中，远端核访问延迟可达本地的 1,000 倍（最大跳数可达数千），现有系统完全忽略这一特性。
2. **受限的片上本地内存**：每个核仅有数十 KB 到数 MB 的 SRAM（Cerebras WSE-2 每核 48 KB），计算数据必须精细切分才能放入本地内存。
3. **有限的路由资源**：每个核的路由电路极为有限（WSE-2 每核最多 25 条路由路径），现有分布式 GEMM/GEMV 算法（allgather、ring allreduce）大量消耗路由资源，造成违规。
4. **百万级并行度要求**：百万核的充分利用需要比 GPU tensor parallelism 细粒度得多的分区策略。

现有系统的失败案例：
- **Ladder**（GPU 共享内存编译器）：不理解分布式内存，导致大量数据复制和长距离通信，甚至不如单 A100 运行 SGLang。
- **T10**（为 IPU crossbar 设计的分布式编译器）：考虑了本地内存和路由约束，但不处理 mesh 的非均匀延迟（不满足 L），也不能扩展到百万核（不满足 P）。

---

## 三、核心设计

### 3.1 PLMR 设备模型

论文提出 **PLMR 模型**（发音"Plummer"），捕获 wafer-scale 加速器的四个关键硬件属性：

| 属性 | 含义 |
|------|------|
| **P**（Massive Parallelism） | 百万级并行核，需要极细粒度的计算分区 |
| **L**（non-uniform Latency） | 非均匀内存访问延迟，核间距最大可达 N_w + N_h 跳，延迟 α(N_w+N_h)+βr |
| **M**（constrained Memory） | 每核本地内存严格受限，数据必须精细切片 |
| **R**（limited Routing） | 每核路由路径数有限（WSE-2 最多 25 条），需最小化路由消耗 |

PLMR 模型使系统设计者能定量分析现有方案的合规性，并指导新算法的设计。

### 3.2 Wafer-scale LLM 并行策略

**Prefill 并行**：将输入激活和权重矩阵沿 mesh X 轴和 Y 轴两个维度切分，实现百万核并行（满足 P）。引入 transposed distributed GEMM（dist-GEMM-T）避免 mesh 上代价极高的矩阵转置（满足 L）。

**Decode 并行**：由于 decode 阶段矩阵维度不足以支撑大规模分区，提出**细粒度复制策略**：沿 sequence 维度复制张量，实现最小通信开销下的高并行度。预先优化权重的物理摆放顺序，消除 decode 阶段的矩阵转置操作。

**KV Cache 管理**：提出 **shift-based KV cache 管理**。传统 concatenate 方法（如 PagedAttention）将新 KV 追加到末尾，导致最后一行核成为热点（违反 M 和 P）。shift-based 方法在新 token 到来时触发"向上移位"操作，将旧 KV 数据均匀扩散到所有核上，保持负载均衡。移位操作只涉及相邻核间通信（满足 L），充分利用 NoC 并行带宽（满足 P）。

### 3.3 MeshGEMM

提出 **MeshGEMM**，PLMR 合规的分布式 GEMM 算法，解决 prefill 阶段计算瓶颈。

核心思路：**循环移位（cyclic shifting）+ 交错（interleaving）**。

- **循环移位**：确保算法正确性并将每核本地内存使用控制在 O(1/N²)（满足 M 和 R）。
- **交错（INTERLEAVE）**：通过将逻辑映射重排为跳距为 2 的物理映射，将关键路径从 O(αN) 降至 O(α)（常数 2 跳），满足 L。数学上可证明 2 跳是在 mesh 上维持 PLMR 合规性的最短可达距离。

与现有算法对比：

| 算法 | 路由路径/核 (R) | 关键路径延迟 (L) | 内存/核 (M) |
|------|----------------|-----------------|------------|
| Allgather | O(N) ❌ | O[(α+β)N] ❌ | O(1/N) ❌ |
| SUMMA | O(N) ❌ | O[(α+β)N] ❌ | O(1/N²) ✓ |
| Cannon | O(1) ✓ | O(αN) ❌ | O(1/N²) ✓ |
| **MeshGEMM** | **O(1) ✓** | **O(α) ✓** | **O(1/N²) ✓** |

### 3.4 MeshGEMV

提出 **MeshGEMV**，PLMR 合规的分布式 GEMV 算法，解决 decode 阶段通信瓶颈。

核心思路：**K-tree allreduce**。传统的 pipeline allreduce 关键路径延迟 O(2αN + βN)（违反 L），ring allreduce 同样违反 L。K-tree allreduce 将 reduce-add 路径组织为平衡 K 叉树，关键路径仅需 K√N 轮规约，每核路由路径 O(K)（可调节 K 以满足 R 约束）。实现中取 K=2。

---

## 四、实现细节

- 实现语言：约 7,000 行 CSL（Cerebras C-like language），实现 LLM 并行、MeshGEMM、MeshGEMV；约 2,000 行 Python，负责加载模型 checkpoint、启动推理和并行配置。
- 硬件平台：Cerebras WSE-2（850,000 核，每核 48 KB SRAM，总计 40 GB）。
- **离线 autotuning**：自动为不同模型和 input/output 长度选择最优核数配置，prefill 和 decode 阶段使用不同核数，通过高速 NoC 动态重映射。
- **Prefill/decode 切换**：利用 WSE-2 的高带宽 NoC 在两阶段间快速 reshuffle KV cache 和权重，无需慢速片外内存。
- **非方形 mesh 处理**：取 N_h 和 N_w 的最小公倍数进行逻辑分区，MeshGEMM 可泛化到任意 N≥3 的 mesh。
- 支持 Grouped Query Attention、Multihead Attention、Multi-query Attention 等多种注意力变体。

---

## 五、实验结果

**实验平台**：Cerebras WSE-2 vs. NVIDIA A100（1/8/16 GPU，NVLink + InfiniBand），LLM 推理系统 SGLang。

### 端到端 LLM 推理吞吐（TPR = tokens/s/request）

| 模型 | 输入/输出长度 | WaferLLM (WSE-2) | SGLang (A100 × 2×8) | 加速比 |
|------|-------------|-----------------|---------------------|-------|
| LLaMA3-8B | 2048/128 | 764.4 | 73.7 | ~10× |
| LLaMA3-8B | 4096/4096 | 2459.0 | 162.5 | ~15× |
| LLaMA2-13B | 2048/128 | 473.9 | / | — |
| LLaMA2-13B | 4096/4096 | 1826.0 | 172.4 | ~10× |

### 与 T10 和 Ladder 的对比（WSE-2 上）

- **vs. T10**（分布式片上内存 SOTA）：端到端 160×（均值），prefill 高达 178×，decode 约 6.5×
- **vs. Ladder**（共享内存 SOTA）：prefill 270-450×，decode 200-500×

### MeshGEMM vs. SUMMA & Cannon

- 比 SUMMA 和 Cannon 快 2-3×，在 720×720 核下保持 70%+ 计算效率，而 SUMMA/Cannon 效率下降到 50% 以下

### MeshGEMV vs. A100 GPU

| 矩阵大小 | WSE-2 时间 (ms) | A100×1 时间 (ms) | 加速比 | 能效比 |
|---------|---------------|----------------|-------|------|
| [1,16K]×[16K,16K] | 0.0012 | 0.336 | 280× | 7.47× |
| [1,32K]×[32K,32K] | 0.00203 | 1.231 | 606× | 16.17× |

### KV Cache 容量

| 模型 | concat-based（PagedAttention） | shift-based（WaferLLM） | 提升 |
|------|-------------------------------|----------------------|-----|
| LLaMA3-8B | 382 tokens | 137,548 tokens | 360× |
| LLaMA2-13B | 16 tokens | 6,168 tokens | 385× |

### 能效

- 整体推理能效：比 A100 多 GPU 集群好 2-2.5×（WSE-2 功耗约为 16× A100，但 GEMV 能效好 16×）

---

## 六、批判性分析

**1. 基准选择存在重大问题**

论文将 WaferLLM 与 T10 和 Ladder 的 WSE-2 实现对比，声称 100-200× 的加速。但 T10 是为 GraphCore IPU（crossbar 架构）设计的，被硬移植到 WSE-2 mesh 上；Ladder 为 GPU 共享内存设计，移植到 WSE-2 更是南辕北辙。这两个 baseline 本来就不适合 WSE-2，用它们来对比更像是"拿别人的弱点和自己的优点对比"，而非公平竞争。更合理的 baseline 应该是 Cerebras 官方软件栈的最新版本，但论文的 GEMV 对比仅与"Cerebras demo GEMV"对比，而非其最优化实现。

**2. 端到端结果存在前后不一致**

摘要声称"GEMV 操作快 606×"，端到端 LLM 推理"快 10-20×"。论文承认这一差距，解释为软件栈不成熟、模型 layer 过窄（GPU 优化的 LLaMA 不适合 WSE-2）、以及 pipeline parallelism 带来的 bubble，但这些解释被轻描淡写。若系统存在 5× 的利用率损失，论文却在 abstract 中大书特书 600× 的 microbenchmark，有误导之嫌。

**3. 测试规模受硬件限制严重**

LLaMA2-13B 和 LLaMA3-8B 能完整加载到 WSE-2 40 GB 片上内存，但 CodeLLaMA-34B 和 QWen2-72B 超出容量，实验仅评估"部分层并按比例缩放"。这种"缩放"假设 uniform layer structure，但 Transformer 的注意力层与 FFN 层特性不同，缩放结论可靠性存疑。WSE-2 实际上无法运行 72B 模型的完整推理，这是一个根本性限制，却只在实验细节中一笔带过。

**4. 能效分析不够严谨**

论文报告的能效优势混合了多种场景。在 GEMV microbenchmark 中能效好 16×，但端到端推理只有 2-2.5×。WSE-2 整块芯片功耗高于 16 块 A100，其实际部署成本（TCO）是否真的更低，论文完全没有分析。

**5. 系统假设过于乐观**

PLMR 模型假设 mesh 硬件属性固定，但实际上 Cerebras WSE-2 core 不能完全重叠内存访问与计算（论文自己也承认），边缘 core 利用率低，NoC 长距离通信仍有残余开销。这些被定性为"硬件还未成熟"，但这不是论文能控制的，未来的结论是推测性的。

---

## 七、AI Infra / MLSys 视角

**核心 insight 的迁移价值**：

PLMR 模型的核心贡献在于提供了一套系统化的硬件约束分析框架，这种"先建设备模型、再证合规性、再针对性设计算法"的方法论本身很有价值，可迁移到其他新型加速器（如 Tenstorrent、未来的 TSMC SoW 架构）的系统设计中。

**MeshGEMM/GEMV 的设计思路启发**：

- **两跳 interleave 通信**本质上是在非均匀互联上寻找"最短合规通信路径"，这一思路在任何具有拓扑感知需求的分布式计算（chip-level mesh、datacenter 网络感知调度）中都有借鉴价值。
- **K-tree allreduce** 是 ring/pipeline allreduce 在树形拓扑上的自然推广，调节 K 来平衡延迟和路由资源是一个实用的工程权衡，可应用于其他具有路由约束的 NoC 或网络拓扑。

**Shift-based KV cache 的可迁移性**：

Shift-based KV cache 管理的核心思想是"用数据迁移换负载均衡"，在任何分布式 KV cache 系统（如 disaggregated prefill-decode、长上下文 multi-node 推理）中，如何避免 KV cache 的热点问题都是重要的工程挑战。

**值得跟进的研究方向**：

1. **MoE 模型的 wafer-scale 推理**：论文仅提到 MoE 共享 MeshGEMM/GEMV，但 all-to-all 通信在 mesh 上的优化是未解问题，专家路由与 mesh 拓扑感知的结合是 high-value 方向。
2. **Wafer-scale prefill + GPU decode disaggregation**：WSE-2 在 prefill 上有巨大优势，但 decode 的利用率只有 20%；能否将 prefill 卸载到 WSE，decode 留在 GPU，通过网络协作？
3. **PLMR 框架扩展**：将 PLMR 推广到 chip-to-chip mesh（如 Tenstorrent cardlevel mesh）或 2D torus，验证 MeshGEMM 在这些拓扑下的泛化能力。
4. **自动化并行策略搜索**：当前 autotuning 仅选核数，更细粒度的问题是如何自动化地为任意模型生成 PLMR 合规的并行计划。

---

## 八、总结

WaferLLM 是首个 wafer-scale LLM 推理系统，通过提出 PLMR 设备模型揭示了 wafer-scale 加速器与现有 GPU 优化系统的根本架构差异，并基于此设计了 PLMR 合规的 LLM 并行策略（prefill 细粒度分区 + decode 细粒度复制）、MeshGEMM（常数跳数分布式矩阵乘）、MeshGEMV（K-tree allreduce）和 shift-based KV cache 管理。在 Cerebras WSE-2 上实现了相比 A100 GPU 集群 10-20× 的端到端推理加速和 2.5× 的能效提升。主要局限在于当前软件栈尚不成熟（5× 利用率损失）、单片内存容量限制（无法容纳 34B 以上模型）、以及 baseline 选择偏弱，使部分结论的实际意义需要进一步验证。
