# Mirage: A Multi-Level Superoptimizer for Tensor Programs

**作者**：Mengdi Wu, Xinhao Cheng (Carnegie Mellon University)；Shengyu Liu, Chunan Shi (Peking University)；Jianan Ji, Man Kit Ao (Carnegie Mellon University)；Praveen Velliengiri (Pennsylvania State University)；Xupeng Miao (Purdue University)；Oded Padon (Weizmann Institute of Science)；Zhihao Jia (Carnegie Mellon University)
**会议**：OSDI 2025（第 19 届 USENIX Symposium on Operating Systems Design and Implementation），2025 年 7 月 7–9 日，Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/wu-mengdi
**源文件**：[osdi25-wu-mengdi.pdf](../../papers/osdi-2025/osdi25-wu-mengdi.pdf)

---

## 一、背景

深度神经网络（DNN）在 GPU 上的高效执行依赖于 tensor programs——以有向无环图（DAG）表示的张量代数计算。现有 DNN 框架（PyTorch、TensorFlow）通过人工设计规则，将 tensor program 映射到专家写成的 GPU kernel。这一流程需要大量工程投入，且容易遗漏优化机会。

为此，研究界提出了两类自动优化方法：

1. **Schedule-based 优化器**（TVM、Ansor、Triton）：固定算法，搜索最优调度（schedule）策略。
2. **代数变换（superoptimization）方法**（TASO、PET、Tensat）：搜索等价的代数变换，但不改变 kernel 级别的实现结构。

然而，FlashAttention 等最优 kernel 的发现需要*同时*进行代数变换、调度变换，并生成全新的自定义 kernel——这超出了现有任何自动方法的能力范围，只能由人工完成。

---

## 二、要解决的问题

**核心 gap**：现有所有自动优化方法仍要求程序员手工指定 kernel（每个 kernel 定义一个张量函数），再在代数变换或调度变换空间中搜索。这意味着：

- **代数变换方法**受限于人工提供的 kernel 实现质量，无法发现需要跨层协作才能表达的优化。
- **调度优化方法**固定算法，无法探索等价但算法不同的计算路径。
- 两类方法均工作在单一层级（kernel 级），无法对 GPU 计算层次（kernel → thread block → thread）做跨层联合优化。

典型例子：FlashAttention 的优化同时涉及算法层重排序（代数变换）、跨 kernel 的计算重组（新自定义 kernel）、每个 kernel 内部并行化策略调整（调度变换），现有方法无法自动发现。

---

## 三、核心设计

Mirage 的核心是 **µGraph**，一种统一表示 tensor program 在 GPU 三个层次（kernel / thread block / thread）的分层图表示。

### 3.1 µGraph 层次结构

- **Kernel graph**：每个节点是一个 kernel（运行在整个 GPU 上），节点间 tensor 存储于 device memory。节点可以是预定义 kernel（cuDNN、cuBLAS），也可以是由 block graph 定义的自定义 kernel operator。
- **Block graph**：描述单个 thread block 内的计算，节点为 block operator，tensor 存储于 shared memory。Block graph 通过 imap/omap/fmap 指定输入 tensor 如何跨 block 分区（partition）或复制（replicate），以及输出如何拼接。支持 for-loop body 以处理超出 shared memory 容量的输入。
- **Thread graph**：描述单个 thread 的计算，是最底层图，tensor 存储于 register file，包含预定义 thread operator。

三个层次使用统一的图语言描述，使 Mirage 能够同时搜索代数变换、调度变换和新 kernel 生成。

### 3.2 Expression-Guided µGraph Generator

Mirage 对输入 tensor program 做 **LAX fragment 分割**（LAX = Linear + dIvision + eXponentiation），将其拆分为只包含多线性算子、除法、最多一次指数运算的子程序。

对每个 LAX 子程序，Mirage 用**抽象表达式（abstract expression）**对候选 µGraph 前缀进行剪枝：通过 SMT solver（Z3）检查候选前缀的抽象表达式是否是目标程序抽象表达式的子表达式（subexpr）。这一剪枝保证了理论上的最优性：只要目标 µGraph 的抽象表达式与输入等价，就不会被剪掉。

### 3.3 Probabilistic Equivalence Verifier

利用多项式恒等测试（PIT）理论，Mirage 将 LAX µGraph 的等价性检验转化为在有限域 Z_p、Z_q 上的随机测试。对于非等价 µGraph，错误接受概率可以任意降低。有别于一般程序的随机测试（无理论保证），LAX 限制使等价性问题可规约为多项式恒等测试，从而提供严格概率保证。

### 3.4 µGraph Optimizer

对每个验证通过的 µGraph，Mirage 进一步做三类后优化：

- **Layout optimization**：用 ILP（Z3 求解）选择 kernel/block/thread 各级张量的最优内存布局。
- **Operator scheduling**：动态规划最小化 CUDA `__syncthreads()` 次数。
- **Memory planning**：穷举 shared memory / register file 中间 tensor 的内存偏移分配方案。

---

## 四、实现细节

- **代码规模**：30K 行 C++、CUDA、Python。
- **Kernel 实现**：kernel operator 用 cuDNN / cuBLAS；block / thread operator 用 cuTLASS 和 CUDA PTX。
- **JIT 编译**：Mirage 自动生成 CUDA 源码并编译为二进制，生成的 kernel 可通过少量代码改动集成进 PyTorch 程序。
- **SMT / ILP solver**：使用 Z3 4.12.6。
- **搜索窗口**：默认允许 kernel graph 最多 5 个算子、block graph 最多 11 个算子；在 10 小时搜索窗口内完成。
- **有限域参数**：随机测试使用最大满足 16-bit 乘积约束的素数 p=227、q=113，在 GPU 上加速计算。
- **可扩展性**：支持添加新线性算子，需提供浮点实现、模运算实现、抽象表达式扩展三项内容。

---

## 五、实验结果

**实验平台**：NVIDIA A100 (40GB) 和 H100 (40GB)，半精度浮点，每组实验重复 1000 次取均值。

**基线**：PyTorch (torch.compile + FlashAttention), TensorRT, TensorRT-LLM, FlashAttention, FlashDecoding, Triton, TASO/PET。

### 微基准（6个DNN算子）

| 基准 | 架构来源 | A100 最大加速比 | H100 最大加速比 |
|------|---------|--------------|--------------|
| GQA  | LLaMA-3-70B | 1.8× | 2.2× |
| QKNorm | Chameleon-7B | 1.4× | 1.4× |
| RMSNorm | LLaMA-2-7B | 1.2× | 1.9× |
| LoRA | GPT-3-7B | 1.1× | 2.4× |
| GatedMLP | Falcon-7B | 3.2× (BS=1) | 2.7× |
| nTrans | nGPT-1B | 0.3× (差于基线) | 0.4× (差于基线) |

注：nTrans 因包含超出 LAX fragment 的算子（LAX 外部分无法优化）而不占优势。

### 端到端 DNN 推理

| 模型 | 最大加速比 |
|------|---------|
| Chameleon-7B | 1.9× |
| LLaMA-3-8B | 1.5× |
| GPT-3-7B-LoRA | 1.4× |
| nGPT-1B | 1.4× |

### 消融实验（A100，GQA，BS=1）

| 禁用项 | 相对性能 |
|-------|---------|
| Thread graph construction | 0.95× |
| Layout optimization | 0.82× |
| Operator scheduling | 0.4× |
| Memory planning | 0.3× |

---

## 六、批判性分析

**1. LAX fragment 限制被低调处理**

论文将 nTrans 的 0.3–0.4× 性能（差于所有基线）归因于 nTrans 包含不属于 LAX fragment 的算子，但对这一关键局限几乎没有定量分析——LAX fragment 对实际 DNN 的覆盖率有多高？作者提到了 solver-based verifier 作为后备，但称其细节"超出本文范围"，未提供任何评估数据。

**2. 微基准 ≠ 端到端收益，两者差距有待解释**

微基准最高达 3.3×，但端到端仅 1.4–1.9×。这种差距是由于非 LAX 算子占运行时间的比例导致，还是有 Amdahl 以外的开销？论文缺乏对此差距的系统分析。

**3. 搜索时间开销被轻描淡写**

10 小时的搜索窗口对于生产部署是严重障碍。论文提及搜索时间但未系统报告不同 DNN 的搜索耗时分布，也未讨论增量重用（如某一算子已搜过是否可复用）。实际上，文中 RMSNorm 需要 11 个 block graph 算子的 µGraph，已超出默认上限 6，需特殊配置。

**4. 实验规模偏小（单 GPU）**

所有实验均在单 GPU 上进行，GQA 虽然用了 4 GPU tensor parallelism，但只是评估多 GPU 场景下的吞吐，而非搜索。随着模型规模扩大，Mirage 如何与分布式执行框架集成？

**5. 概率验证的"实践等价"依赖假设**

作者承认随机等价测试理论上存在误报风险，但称"实践中从未观察到"——这一表述缺乏系统性测试依据。对于安全关键的生产系统，此处的理论保证与工程实践之间存在明显缺口。

---

## 七、AI Infra / MLSys 视角

Mirage 是 AI Infra 领域极具分量的工作，从多个维度提供了可借鉴的洞见：

**设计思路的迁移价值**：
- µGraph 的分层统一表示（kernel/block/thread）为 compiler IR 设计提供了新范式。现有 tensor compiler（TVM TensorIR、Triton、Welder/ASPEN）均在某一层面进行抽象，Mirage 的跨层表示使"联合优化"从理论走向实践。
- 概率等价验证（PIT over finite fields）是在 superoptimizer 搜索中进行正确性保障的优雅方案，其 LAX fragment + 理论保证的组合可作为后续 tensor compiler 正确性验证的参考模板。

**可直接跟进的研究方向**：
1. **LAX fragment 扩展**：支持更多 DNN 算子（如 ReLU、LayerNorm 的 backward 等）的概率等价验证，或为 non-LAX 算子设计高效的 solver-based 验证，是最直接的延伸。
2. **搜索时间 vs. 优化质量 tradeoff**：当前 Mirage 搜索时间长（10 小时），研究如何用学习方法（强化学习、beam search + learned cost model）加速搜索空间导航，同时保持发现 FlashAttention 级别优化的能力。
3. **多 GPU / 分布式 tensor program 的 µGraph 扩展**：现有 µGraph 仅覆盖单 GPU，扩展至 tensor/pipeline/data parallelism 场景，探索跨设备级别的联合优化，对超大规模训练具有重要价值。
4. **跨 workload 的 µGraph 复用**：不同 DNN 中结构相同的算子（如 attention variants）可共享已发现的最优 µGraph，降低部署时搜索开销。

---

## 八、总结

Mirage 提出了首个多层次 tensor program superoptimizer，通过 µGraph 统一表示、基于抽象表达式的剪枝、有限域上的概率等价验证，自动发现并验证了跨代数变换、调度变换和新 kernel 生成的联合优化。在 A100/H100 上对广泛使用的 LLM 算子（GQA、RMSNorm、LoRA、GatedMLP 等）达到最高 3.3× 的微基准加速，端到端模型推理加速 1.4–1.9×。主要局限在于 LAX fragment 覆盖率有限（nTrans 甚至性能退步）、10 小时搜索时间对生产部署构成障碍，以及对 non-LAX 算子的优化路径尚不完善。
