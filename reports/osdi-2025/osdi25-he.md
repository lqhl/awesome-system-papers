# WaferLLM: Large Language Model Inference at Wafer Scale

**作者**：Congjie He, Yeqi Huang, Pei Mu (University of Edinburgh); Ziming Miao, Jilong Xue, Lingxiao Ma, Fan Yang (Microsoft Research); Luo Mai (University of Edinburgh)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/he
**源文件**：[[osdi25-he.pdf]]

---

## 一、背景

LLM 推理是一个快速增长的工作负载，分为 prefill（GEMM 主导）和 decode（GEMV 主导）两个阶段。Decode 阶段需要反复将整个模型权重从外部存储器加载到片上内存，因此受限于内存带宽。即使使用多 GPU tensor parallelism 也只能增加并发查询吞吐，无法降低单请求的 TPOT（Time Per Output Token）。

为突破内存带宽瓶颈，AI 加速器正在向 system-on-wafer 集成方向发展。Cerebras WSE-2 集成了 85 万个核心、40GB 片上 SRAM、22 PB/s 内存带宽，分别是 GPU 的 1,000 倍和 7,000 倍。TSMC 预测 wafer-scale 集成将在 2027 年广泛普及。Mistral、Perplexity、G42 等公司已在生产环境部署 wafer-scale 芯片。

---

## 二、要解决的问题

Wafer-scale 加速器采用 mesh-based Network-on-Chip (NoC) 将百万级核心通过分布式本地内存互连，与 GPU 的共享内存架构有本质区别。现有 LLM 推理系统（vLLM、SGLang、TensorRT-LLM）以及 DNN 编译器（Ladder、T10）直接应用于 wafer-scale 设备时性能极差，具体问题包括：

1. **共享内存假设不成立**：Ladder 等编译器假设均匀内存访问延迟，无法容忍 wafer-scale mesh 中高达 1,000 倍的延迟差异；对数据分区优化不足，导致大量数据重复存储，违反本地内存约束。
2. **分布式内存系统假设不匹配**：T10 假设片上 crossbar 互连（常数延迟），无法处理 mesh NoC 中随跳数变化的非均匀延迟，且仅扩展到数千核心而非百万级。
3. **GEMM/GEMV 算法不适配**：传统 allgather GEMM、SUMMA、Cannon 等分布式算法在 mesh 上的路由资源消耗和通信延迟均无法满足 wafer-scale 硬件约束。
4. **KV cache 管理不适配**：GPU 上基于 concatenation 的 KV cache 管理在分布式内存架构上导致核心利用率严重倾斜。

---

## 三、洞察与设计

**关键洞察**：Wafer-scale 加速器的硬件特性可以用四个关键属性（PLMR）统一刻画——百万级并行核心 (P)、高度非均匀的内存访问延迟 (L)、受限的单核本地内存 (M)、有限的硬件路由资源 (R)。任何有效的 wafer-scale LLM 推理系统设计都必须同时满足这四个约束，现有系统的失败根源在于违反了其中的一个或多个属性。

基于 PLMR 模型，WaferLLM 的核心设计包括：

### Wafer-Scale LLM Parallelism

- **Prefill 阶段**：对输入激活和权重矩阵的两个维度分别沿 mesh 的 X 轴和 Y 轴做细粒度分区，实现百万核并行。使用 transposed distributed GEMM (dist-GEMM-T) 计算 Q@K^T，避免代价高昂的 mesh 上矩阵转置。
- **Decode 阶段**：当 tensor 维度不足以支撑高并行度时，对序列维度做细粒度复制（而非分区），同时保持负载均衡且无需额外 allreduce。预优化模型权重布局以消除 decode 过程中的矩阵转置。

### MeshGEMM

一种 PLMR 兼容的分布式 GEMM 算法，核心操作为：
- **Cyclic shifting**：限制通信只发生在两跳邻居之间，满足 M 和 R 约束。
- **Interleaving**：通过 INTERLEAVE 操作重新映射逻辑到物理核心，将每步通信的关键路径限制在常数 2 跳（O(α) 延迟），满足 L 约束。数学证明了 2 跳是这种循环排列下的最小距离。

### MeshGEMV

一种 PLMR 兼容的分布式 GEMV 算法，使用 K-tree allreduce 替代传统的 pipeline/ring allreduce：
- 将 reduce-add 路径组织为平衡 K 叉树，K 个 phase 的分组并行规约。
- 关键路径从 O(N) routing stages 降低到 O(K·N^(1/K)/2)，大幅减少通信延迟。
- 当前实现选择 K=2，在路由资源和延迟之间取得平衡。

### Shift-based KV Cache Management

用 shift 操作替代 concatenation：每行核心将最旧的 KV cache 向上一行转移，新 KV 数据填充到底部，确保所有核心的 KV cache 均匀分布，满足 P 和 M 约束，且只涉及相邻核心间的数据移动（满足 L）。

---

## 四、实现细节

- 使用约 7,000 行 CSL（C-like programming language）实现 LLM parallelism、MeshGEMM、MeshGEMV。
- 使用约 2,000 行 Python 用于加载 LLM checkpoints、启动推理和执行并行策略。
- 在 Cerebras WSE-2 上实现，WSE-2 拥有 850,000 个核心，每核 48KB SRAM，总共 40GB 片上 SRAM，核心时钟频率最高 1.1GHz。
- 每个核心每周期可从 SRAM 读取两个 32-bit 操作数，执行一次乘加运算，并写回 SRAM。每核有一个 fabric router 支持单周期 32-bit 消息收发。
- Prefill 和 decode 使用不同的核心配置（离线自动调优），阶段切换时通过高带宽 NoC 快速 reshuffle KV cache 和权重。
- 支持 Grouped Query Attention、Multi-head Attention、Multi-query Attention。

---

## 五、实验结果

**实验平台**：Cerebras WSE-2（7nm）vs. NVIDIA A100 GPU（7nm，公平对比）最多 16 卡（2×8，NVLink + InfiniBand）。GPU 端使用 SGLang。

**评估模型**：LLaMA3-8B、LLaMA2-13B、CodeLLaMA-34B、QWen2-72B。

### 端到端推理吞吐 (TPR, tokens/s)

| 模型 | 设备 | 2048/128 | 4096/128 | 2048/2048 | 4096/4096 |
|------|------|----------|----------|-----------|-----------|
| LLaMA3-8B | WaferLLM (WSE-2) | 764.4 | 604.4 | 2370.3 | 2459.0 |
| | T10 (WSE-2) | 4.6 | 4.5 | 58.3 | 94.6 |
| | SGLang 1×A100 | 34.8 | 31.1 | 36.5 | 78.4 |
| | SGLang 8×A100 | 117.2 | 109.0 | 128.4 | 256.1 |
| LLaMA2-13B | WaferLLM (WSE-2) | 473.9 | 414.0 | 1690.3 | 1826.0 |
| | SGLang 1×A100 | 20.4 | 17.1 | 21.1 | 47.9 |
| | SGLang 8×A100 | 79.6 | 70.5 | 86.9 | 172.4 |

### 关键数字

| 对比维度 | 加速比 |
|----------|--------|
| WaferLLM vs. T10（端到端） | 36-180× |
| WaferLLM vs. Ladder（端到端） | 312-677× |
| WaferLLM vs. SGLang 单 A100（端到端） | 30-40× |
| WaferLLM vs. SGLang 最优多 GPU（端到端） | 10-20× |
| MeshGEMM vs. SUMMA/Cannon | 2-3× |
| MeshGEMV vs. Cerebras baseline GEMV | 4-8× |
| MeshGEMV vs. 单 A100 GEMV | 280-606× |
| Shift-based vs. Concat-based KV cache 容量 | 360-385× |
| 能效（WSE-2 vs. 最优 GPU 集群） | 2.5× |

---

## 六、批判性分析

1. **实验公平性存疑**：选择 7nm A100 与 7nm WSE-2 对比看似公平，但 WSE-2 芯片面积是 A100 的 47 倍、功耗和成本是 37 倍。10-20× 的端到端加速换来 37× 的功耗/成本开销，论文虽然声称有 2.5× 能效优势，但这一数字仅在 decode 最优情况下成立，prefill 阶段的能效比甚至远低于 1（Table 7 中 A100/WSE-2 能效比仅 0.05-0.84）。论文对此轻描淡写。

2. **无法跑完整大模型**：CodeLLaMA-34B 和 QWen2-72B 因单片 WSE-2 内存不足，只能跑部分层再线性外推。这种外推假设了完美的线性 scaling，忽略了层间通信、KV cache 增长等实际开销，结果的可信度有限。

3. **缺乏 batch 推理评估**：全文只关注单请求 TPR（Throughput per Request），完全没有 batch serving、多请求并发场景的评估。这是 LLM 推理系统的核心场景——实际部署中吞吐量和成本效益才是关键。单请求延迟虽然重要，但不能代表系统的经济价值。

4. **与 H100/H200 缺乏对比**：论文以"无法获取 WSE-3"为由只对比 A100，但 H100/H200 的 HBM 带宽和算力已大幅提升（H100 HBM 带宽 3.35 TB/s vs A100 2 TB/s），且 SGLang/vLLM 在新硬件上有显著优化。不与当代硬件对比削弱了论文的说服力。

5. **K-tree allreduce 的 K=2 选择缺乏充分论证**：论文声称 K 的选择取决于 N 和 R 约束，但实际只评估了 K=2，没有展示不同 K 值的性能对比和 sensitivity analysis。

6. **软件/硬件限制被过度归因于"未来可解决"**：论文多次提到 MeshGEMV 未达到理论 7,000× 加速，将原因归于 WSE-2 的硬件限制（无法完全 overlap、边缘核心利用不足等），并乐观地预期未来硬件改善。但这些限制是系统层面的根本性问题（如 pipeline parallelism 导致 5× 利用率下降），WSE-3 的改进是否足够并无证据。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴

1. **PLMR 设备模型的通用性**：PLMR 不仅适用于 Cerebras WSE，也适用于 Tesla Dojo、Tenstorrent 等 mesh-based 架构。随着芯片设计趋向更大规模的 NoC 互连（即使在非 wafer-scale 芯片上），PLMR 的约束分析方法论可以迁移到更广泛的 AI 加速器优化场景。

2. **通信-计算 overlap 的新范式**：MeshGEMM 的 interleave 通信模式和 MeshGEMV 的 K-tree allreduce 提供了在大规模非均匀内存架构上做通信优化的新思路。这些技术原理可以应用于大规模 GPU 集群（如 NVLink domain + IB 跨节点的多级非均匀拓扑）的 collective 优化。

3. **KV cache 管理的分布式视角**：Shift-based KV cache 管理启发了一种新的思考方式——在分布式内存系统中，数据管理应关注负载均衡和数据局部性，而非简单的 append 操作。这对多 GPU KV cache offloading/migration 场景有参考价值。

### 值得跟进的方向

1. **Batch serving 和 continuous batching 的 wafer-scale 实现**：论文完全未涉及多请求并发场景，这是将 WaferLLM 推向实际部署的必经之路。如何在 PLMR 约束下实现高效的 request scheduling 和 batch GEMM/GEMV 是一个开放问题。
2. **MoE 模型的 wafer-scale 推理**：论文提到支持 MoE 但未做评估。Expert routing 的动态性和 all-to-all 通信在 mesh NoC 上的实现是一个有价值的研究问题。
3. **Prefill-decode disaggregation 在 wafer-scale 上的应用**：论文已展示 prefill 和 decode 需要不同的核心配置，自然引出 DistServe 式的 prefill-decode 分离架构在 wafer-scale 上的实现问题。
4. **异构 wafer-scale 架构设计**：论文揭示了当前 WSE-2 每核 48KB SRAM 导致必须使用 pipeline parallelism 的根本限制。面向 LLM 推理的异构 wafer-scale 芯片（不同核心配置不同大小的本地内存）是一个值得探索的 co-design 方向。

---

## 八、总结

WaferLLM 是首个 wafer-scale LLM 推理系统，提出了 PLMR 设备模型来刻画 wafer-scale 加速器的核心硬件特性，并据此设计了 wafer-scale LLM parallelism、MeshGEMM、MeshGEMV 和 shift-based KV cache 管理四个关键组件。在 Cerebras WSE-2 上实现了相比单 A100 30-40× 和最优多 GPU 集群 10-20× 的端到端加速。论文的核心价值在于为新兴的 wafer-scale 计算建立了系统化的设计方法论（PLMR 模型），但其实际价值受限于缺乏 batch serving 评估、无法运行完整大模型、以及与当代 GPU 硬件（H100/H200）的对比缺失。
