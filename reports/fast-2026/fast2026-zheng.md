# SolidAttention: Low-Latency SSD-based Serving on Memory-Constrained PCs

**作者**：Xinrui Zheng, Dongliang Wei, Jianxiang Gao, Yixin Song, Zeyu Mi, Haibo Chen（上海交通大学 IPADS）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/zheng
**源文件**：[[fast2026-zheng.pdf]]

---

## 一、背景

随着 LLM 日益融入日常工作流，隐私、定制化和部署成本等需求推动了在 AI PC（AIPC）上本地运行 LLM 的趋势。然而，当前主流 PC 硬件配置有限——通常仅 8–16 GB DRAM、集成 GPU 或 6–8 GB VRAM 的入门级独显。随着 128k token 上下文成为标配，即使 8B 参数模型的 KV cache 就需要超过 16 GB 内存（是模型权重的 4 倍以上），远超消费级设备的承载能力。

现有部署方案（如 llama.cpp、Ollama）假设 KV cache 可以完全驻留在内存中，这与实际硬件条件严重脱节。如何在内存受限的 PC 上实现低延迟的长上下文 LLM 推理，成为本地部署的核心瓶颈。

---

## 二、要解决的问题

1. **KV cache 内存开销过大**：128k token 上下文下 KV cache 高达 16 GB，远超消费级设备可用内存。INT4 量化方案虽能减小体积，但显著降低模型精度。

2. **SSD offloading 的带宽利用率低**：动态 attention sparsity 产生细粒度、不规则的随机 I/O 访问模式，与 SSD 偏好粗粒度顺序访问的特性严重冲突，导致 SSD 带宽利用率低下。

3. **吞吐量导向方案在本地场景失效**：FlexGen 等方案通过批处理多请求来 overlap I/O 与计算，但本地部署通常 batch size=1，计算量不足以掩盖 SSD 访问延迟，导致 I/O 成为瓶颈。

4. **Sparse attention 与 SSD 特性的根本矛盾**：现有方案将 attention sparsity 和 storage management 视为独立问题，未考虑两者交互产生的性能惩罚。

---

## 三、洞察与设计

**关键洞察**：sparse attention 计算与 SSD 特性之间存在根本性冲突——SSD 需要粗粒度顺序操作才能达到最优性能，而 sparse attention 的动态不规则访问模式产生大量细粒度随机 I/O。解决方案不是分别优化两者，而是**协同设计** sparse attention 算法和存储管理系统，对齐数据访问粒度并精细编排计算-I/O overlap。

基于此洞察，SolidAttention 包含三个核心组件：

### KV Consolidator（KV 合并器）
- **问题**：增大 block size 可提高 SSD 带宽利用率，但会将过多 token 编码为单个代表向量，导致精度下降（recall rate 随 block size 从 32 增到 256 持续下降）
- **方案**：利用 K 和 V 向量具有相同 shape 的特性，在 token 粒度上将 K/V 交错排列（interleave），形成粗粒度数据单元。这样在不增加 block 内 token 数（不损失精度）的前提下，将传输单元大小翻倍、I/O 操作数减半
- **离线权重预拼接**：将 K/V 投影的权重矩阵预先拼接为统一张量，通过单次矩阵乘法直接生成交错 KV pairs，避免运行时重排开销
- **零额外计算开销**：通过 strided access（步长 2H）逻辑分离 K/V，无需物理重排，延迟开销 ≤2%

### Speculative Prefetcher（投机预取器）
- **观察**：跨层连续迭代间的 block selection 相似度约 81%（在多模型、多 benchmark 上一致成立）
- **方案**：记录历史 selection 结果，投机预取下一层可能需要的 KV blocks。Init blocks 和 local blocks 确定性预加载；selected blocks 基于历史模式投机预取
- **Out-of-Order Overwrite**：利用 self-attention 对 token 顺序无要求的特性，错误预取的 block 直接被正确 block 原地覆盖，无需昂贵的重排操作

### SSD-aware Scheduler（SSD 感知调度器）
- 将 attention 模块分解为 microtasks，构建 DAG 建模数据依赖关系
- 基于 DAG 识别关键路径，通过 Latest Start Time（LST）优先级调度，最大化计算-I/O overlap
- **同步点复用**：将非关键任务（如 CPU→SSD store）与关键路径任务合并同步点，减少同步频率和开销
- 对统一内存架构（如 iGPU）进一步优化，消除显式 CPU-GPU 同步

---

## 四、实现细节

- 基于 llama.cpp 实现，使用 liburing 进行 SSD I/O
- 约 25k 行 C++ 和 CUDA 代码（12k 行 GPU kernel，1k 行 llama.cpp adapter）
- 支持 CUDA 和 SYCL 双后端（NVIDIA GPU + Intel Arc iGPU）
- 验证模型：Llama-3.1-8B、Llama-3.2-3B、Qwen-2.5-7B、Qwen-2.5-14B
- I/O 线程使用 1 个专用 CPU 核处理 I/O 任务，另 1 个核用于 SSD-GPU 协调
- 写放大优化：每层使用 32 KB write buffer 合并写操作
- Block size 默认 32 token；context budget：输入 <4k token 时为 25%，否则为 1k token；一半分配给 init/local blocks，另一半给 selected blocks
- KV cache 以 FP16 存储，模型权重 INT4 量化

---

## 五、实验结果

**硬件平台**：
- CUDA 后端：Intel Ultra 9 185H + NVIDIA RTX 4070 Laptop (8 GB VRAM) + 64 GB DDR5 + 1 TB Samsung 990 PRO
- SYCL 后端：Intel Ultra 7 255H + Intel Arc 140T iGPU + 64 GB DDR5 + 1 TB Samsung 990 PRO

**Baseline**：Offload（全 KV cache offload）、Offload+Sparse（+InfLLM）、FlexGen

### 端到端性能（128k token）

| 模型 | vs Offload+Sparse (CUDA) | vs Offload+Sparse (SYCL) | vs FlexGen (16k) |
|------|--------------------------|--------------------------|-------------------|
| Llama-3.2-3B | 2.8× | 2.1× | — |
| Llama-3.1-8B | 3.1× | 2.5× | 58.9× |
| Qwen-2.5-7B | 2.4× | 1.9× | — |

### 内存节省

KV cache 内存占用减少最高 62.0×（仅需为单层 1k-token context 分配 buffer）。

### 精度

| 模型 | Origin Avg | SolidAttention Avg |
|------|------------|-------------------|
| Llama-3.2-3B | 57.82 | 57.67 |
| Llama-3.1-8B | 65.76 | 65.93 |
| Qwen-2.5-7B | 71.39 | 70.76 |

精度基本持平，显著优于 INT4 KV cache 量化（Qwen-2.5-7B 量化后从 71.39 暴降至 18.63）。

### 消融实验关键数据
- **Speculative prefetcher**：blocking latency 在 CUDA 上减少最高 3.9×，SYCL 上 3.1×
- **KV interleaving**：attention latency 降低最高 22%
- **SSD-aware scheduler**：fine-grained overlap 提升 25%，同步点复用再降 22%
- **vs in-memory（无 SSD offload）**：throughput 仅下降 ≤11%
- **能耗**：3.68 J/token vs llama.cpp 5.37 J/token，节省 46%

---

## 六、批判性分析

1. **64 GB DRAM 的"内存受限"假设值得商榷**：实验平台配备 64 GB DDR5，远超论文声称的 8–16 GB 典型 AIPC 配置。论文限制 DRAM 使用量为 16 GB 进行测试，但未在真正的 8/16 GB 物理内存设备上验证。实际 8 GB 设备上 OS 和其他进程的内存压力、page cache 竞争等问题未被触及。

2. **Batch size=1 的场景限制**：所有实验均在 batch size=1 下进行，这确实是本地场景的典型设定，但也意味着系统无法利用 batching 来摊薄开销。论文未讨论当用户同时开多个对话或运行多任务时的表现。

3. **SSD 性能干扰实验揭示了脆弱性**：在 4 GB/s 背景流量下 throughput 下降 58%，P99 latency 增加 2.9×。论文轻描淡写称"对端到端请求延迟可忽略"，但实际使用中用户 PC 持续有后台 I/O 活动（系统更新、浏览器缓存、应用同步），这可能导致严重的用户体验波动。

4. **81% selection similarity 的普适性存疑**：该数值仅在 LongBench 的 8 个数据集上验证。对于交互式多轮对话、代码生成等实际应用场景，attention pattern 的时间局部性可能差异很大。一旦 similarity 下降，speculative prefetching 的效果会大幅衰减。

5. **Context budget 固定为 1k 的合理性**：§8.5 显示 context budget 达到 4k 时性能急剧恶化。但 1k budget 意味着 128k 上下文中仅保留 <1% 的 token 参与 attention。虽然 LongBench 上精度损失不大，但对于需要全局信息聚合的任务（如长文档摘要、多跳推理），这一极端稀疏率是否仍然安全缺乏充分验证。

6. **未与更多 SSD offloading 方案对比**：缺少与 IMPRESS（FAST'25）、CachedAttention（ATC'24）在相同设置下的定量对比。FlexGen 作为 throughput-oriented 系统在 batch=1 场景下本身就不占优势，作为对比基线说服力有限。

---

## 七、AI Infra / MLSys 视角

1. **存储-计算协同设计的范式启示**：SolidAttention 的核心贡献不仅是具体技术，更是一种方法论——将 attention 算法与存储系统特性进行端到端协同设计。这一思路可迁移至分布式推理场景中的 network-aware attention（如根据 RDMA vs TCP 的不同特性调整 KV cache 分片和传输策略）。

2. **KV Interleaving 对 KV cache 传输的通用启发**：将 K/V 交错以翻倍传输粒度的技巧不依赖 SSD，同样适用于 GPU-GPU、CPU-GPU 之间的 KV cache 传输（如 disaggregated prefill-decode 架构中的跨节点 KV cache 传输）。

3. **Speculative prefetching 与 speculative decoding 的结合**：论文的投机预取思路可以与 speculative decoding 结合——在 draft model 生成 token 的同时，提前预取 target model 所需的 KV blocks，进一步隐藏 I/O 延迟。

4. **DAG-based scheduler 的可扩展性**：microtask 分解 + DAG 调度的框架具有通用性，可扩展到更复杂的推理 pipeline（如 MoE expert loading、LoRA adapter 动态加载等场景）。

5. **值得跟进的研究方向**：
   - 在 PCIe 5.0 SSD（16 GB/s）和 CXL memory 上验证和优化
   - 与 KV cache 量化（AWQ/KIVI）结合，进一步压缩传输量
   - 探索 ZNS SSD 的 zone-aware KV cache placement，利用数据放置控制最大化内部并行度
   - 多模型/多 LoRA 场景下的 SSD 资源调度

---

## 八、总结

SolidAttention 通过协同设计 sparse attention 算法与 SSD 存储管理，解决了内存受限 PC 上长上下文 LLM 推理的核心瓶颈。其三个关键技术——KV interleaving 提升带宽利用率、speculative prefetching 隐藏 I/O 延迟、DAG-based scheduling 最大化计算-I/O overlap——共同实现了最高 3.1× 加速和 98% KV cache 内存节省，且精度几乎无损。系统适用于配备 SSD 的消费级 PC 上的单用户长上下文推理场景，但在多任务并发、SSD 性能波动和极端稀疏率下的鲁棒性仍需进一步验证。
