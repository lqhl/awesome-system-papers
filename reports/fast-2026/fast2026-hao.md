# Fast Cloud Storage for AI Jobs via Grouped I/O API with Transparent Read/Write Optimizations

**作者**：Yingyi Hao (上海交通大学), Ting Yao (华为云, 通讯作者), Xingda Wei (上海交通大学, 通讯作者), Dingyan Zhang, Tianle Sun (上海交通大学), Yiwen Zhang, Zhiyong Fu, Huatao Wu (华为云), Rong Chen (上海交通大学)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/hao
**源文件**：[[fast2026-hao.pdf]]

---

## 一、背景

大规模 AI 模型（GPT、LLaMA 等）的训练和推理工作负载正在深刻改变云存储的带宽需求。在华为云中，AI 作业已经消耗了本地数据中心超过 10% 的云存储带宽。训练中的 checkpoint 写入（周期性保存模型参数和优化器状态以实现容错）、推理中的 checkpoint 读取（用于自动扩缩容）、以及 KV Cache 读取（用于加速 LLM 推理），都涉及到数十 MB 到数百 GB 级别的大块顺序 I/O，对存储带宽要求极高。

现代云基础设施普遍采用计算-存储分离（disaggregated）架构：计算服务器（挂载 GPU/NPU 等 XPU）和存储服务器通过独立的网络互联。XPU 之间的计算网络（compute fabric）带宽高（如 200 Gbps/XPU），而连接存储的网络（storage fabric）带宽低（如 100 Gbps/节点，多个 XPU 共享）。这种架构使得提升存储带宽面临硬件限制和成本问题。

---

## 二、要解决的问题

1. **存储带宽受限且扩展成本高**：在分离式架构下，提升后端存储带宽需要增加存储服务器数量，成本按比例增长（华为云数据：带宽从 1.6 GBps 提升到 80 GBps，单位 GB 成本增加 16×）。即使后端带宽充足，前端带宽（S-NIC）也是硬瓶颈。

2. **应用层优化负担重且不通用**：当前优化存储 I/O 的责任主要在应用框架层面。例如 Megatron 用四分之一的代码量来优化 checkpoint 读写，但仍因不了解底层存储架构而性能次优。不同 AI 框架（Megatron、OpenSora、Mooncake）需要各自实现优化，工程成本高且难以通用。

3. **Grouped I/O 中的重复数据未被有效利用**：AI 作业天然具有 grouped I/O 模式——多个 XPU 同时进行 I/O 操作。数据并行训练中 checkpoint 存在跨节点重复；推理 autoscaling 中多个作业读取同一模型；Agent 工作负载中多个请求共享相同的 KV Cache。这些重复数据的去重和负载均衡需要全局视角，单个应用难以实现。

---

## 三、洞察与设计

**关键洞察**：AI 作业中主机 DRAM 和高带宽 compute fabric 在大部分时间是空闲的（因为 AI 集群为不同内存和网络需求的作业共用硬件），可以被存储系统作为快速中转缓冲区使用；同时，通过一个简单的 grouped I/O API，存储层可以获得足够的 I/O 语义信息，自动推导出优于应用层手动优化的去重和负载均衡 I/O 计划。

基于这两个洞察，AITURBO 的核心设计包括：

1. **Grouped I/O API**：受 AI 中 group communication 启发，扩展标准 `getfile`/`putfile` 为 `group_getfile`/`group_putfile`，让存储层知道哪些客户端在同时进行 I/O。API 还暴露两个 future：`future_0`（数据已写入 DRAM buffer）和 `future_1`（数据已持久化到存储），便于异步 I/O。

2. **Job Controller**：全局协调 grouped I/O 操作，包含三个核心功能：
   - **去重（Dedup）**：收集各 XPU 的 checksum 元数据，识别跨节点重复的 chunk，生成去重后的 I/O 计划。使用 BLAKE3 checksum，支持 XPU 加速计算。去重元数据在作业生命周期内缓存复用。
   - **负载均衡写计划**：将写入分为两步——先写入 host DRAM buffer，再 writeback 到存储服务器。将计划生成建模为双线性规划问题（bilinear programming），通过 branch and bound 算法求解，最大化带宽利用率。
   - **负载均衡读计划**：先从存储拉取去重后的数据到部分节点，再通过 compute fabric 广播到所有需要的节点。

3. **Staging Buffer**：利用空闲的 host DRAM 作为中转缓冲，通过 compute fabric（而非 storage fabric）在节点间传输数据，突破 storage fabric 的带宽限制。

---

## 四、实现细节

- **Tensor-native 文件类型**：将 tensor 的元数据（shape、type）和实际数据分离，避免 XPU-CPU-存储之间的序列化/反序列化开销。

- **BLAKE3 Checksum 加速**：在 XPU 上实现优化的 checksum 内核，1 GB 文件的 checksum 时间从 CPU 上的 35.6 ms 降至 V100 GPU 上的 7.8 ms。

- **写计划建模**：6 个约束条件的双线性规划——(1) 总传输量约束、(2) 源节点数据归属约束、(3) 目标节点去重约束、(4)(5) 出入向带宽约束、(6) 链路带宽约束、(7) 缓冲区容量约束。利用 t 的上下界做 branch and bound，在 38B 模型 64 XPU 场景下用未优化的 Python solver 4 秒内求解。

- **计划缓存和流水线**：由于 AI 作业的 I/O 模式在迭代间稳定，第一次生成的计划可以缓存复用。写入采用流水线：chunk 写入 DRAM 后立即开始 writeback，overlap 两个阶段。

- **P2P 网络连接**：不使用 NCCL 等库的完整 group communicator 初始化（耗时数秒到数分钟），而是直接建立 P2P RDMA 连接（QP），建连仅需 15 ms，且可与存储初始化 overlap。

- **性能隔离**：使用 RoCE QoS 机制，将 AITURBO 的 compute fabric 流量设为最低优先级，best-effort 使用计算网络，避免干扰 AI 计算通信。

- **已部署于华为生产云**，支持训练作业的 checkpoint 读写，推理支持正在开发中。

---

## 五、实验结果

**实验平台**：两个集群——Ascend 910B NPU（类似 A100）和 NVIDIA A800 GPU，每节点 8 XPU、192 CPU 核心、1.5 TB DRAM。Compute fabric 200 Gbps/节点，Storage fabric 100 Gbps/节点，后端存储最高 30 GBps。

### Checkpoint 写入

| 模型 | 配置 | SFSTURBO | Gemini | AITURBO | 加速比 (vs SFSTURBO) | 加速比 (vs Gemini) |
|------|------|----------|--------|---------|---------------------|-------------------|
| 1.5B | 无 ZeRO | 最慢 | 中等 | 最快 | 最高 58.8× | 最高 5.9× |
| 13B | TP=8 | 最慢 | 中等 | 最快 | 显著提升 | 显著提升 |
| 38B | TP=8, PP=4 | 最慢 | 中等 | 最快 | 3.9×+ | — |

### Checkpoint 读取

| 场景 | AITURBO 表现 |
|------|-------------|
| Qwen 72B, 64 XPU, 缓存命中 | 2.25 秒完成部署 |
| Qwen 72B, 8 XPU, 1 GBps 后端 | 173 秒（与 ServerlessLLM 持平，受存储带宽限制） |
| 多实例扩展 | 读取时间几乎不随 XPU 数量增长（compute fabric 广播） |

### KV Cache 读取（Mooncake 集成）

- 使用 Qwen-Bailian 真实 trace 回放，Mooncake+AITURBO 相比 Mooncake+SFSTURBO，TTFT 降低 23%，最高 1.28× 加速。

### 工程成本

| 系统 | 代码量 (LoC) |
|------|-------------|
| Megatron checkpoint 优化 | 2,228 |
| AITURBO Megatron 集成 | 286 |
| AITURBO Mooncake 集成 | 44 |

### 协调开销

- 64 XPU 规模下 group 协调开销最大仅 45 ms，可忽略不计。

---

## 六、批判性分析

1. **"透明"的程度被夸大**：论文反复强调 "transparent optimization without application modifications"，但实际上仍需要应用端修改代码调用 grouped I/O API（Megatron 286 LoC、Mooncake 44 LoC）。虽然比应用层自己实现优化少得多，但并非真正的零侵入。

2. **实验基线不完全公平**：与 Gemini 的对比中，论文承认 Gemini 是闭源的，只能在 Megatron 上"实现其主要技术"进行比较。这种 reimplementation 很可能无法完全还原 Gemini 的优化效果，导致对比偏向 AITURBO。

3. **Compute fabric 带宽借用的影响评估不足**：论文仅使用 RoCE QoS 的最低优先级来隔离存储流量，并承认在极端情况下可能干扰 AI 计算，但没有给出任何量化实验证明这种干扰在实际训练中的影响有多大。仅说 "hardware solution works fine in all our cases" 缺乏说服力。

4. **规模受限**：所有实验最多 64 XPU（8 节点），而实际大规模训练通常涉及数百甚至数千 XPU。双线性规划的求解时间和 job controller 的协调开销在更大规模下是否仍然可控，缺少论证。论文提到 Python solver 在 64 XPU 下需要 4 秒，但 1000+ XPU 场景下的可扩展性未被验证。

5. **KV Cache 场景的评估深度不足**：KV Cache 读取的实验仅在 8 XPU 上进行，且没有使用 grouped API（因为推理实例难以同步），这意味着 AITURBO 在推理场景中的核心设计（grouped I/O）其实并未被充分验证。

6. **容错设计简化处理**：论文将 checkpoint 写入 DRAM buffer 后即视为"完成"，将持久化推迟到后台。如果多个 DRAM 副本同时失效（如整机架故障），数据会丢失。论文虽然提到了 DRAM 复制，但对复制策略和故障概率分析非常简略。

---

## 七、AI Infra / MLSys 视角

1. **Compute fabric 作为存储加速通道的通用性**：AITURBO 证明了在计算-存储分离架构下，利用空闲的 compute fabric 和 host DRAM 做存储中转是一种低成本且高效的设计范式。这个思路可以推广到更多 AI 系统场景，如分布式推理中的模型权重预加载、多任务训练中的数据共享等。

2. **Grouped I/O 语义的价值**：论文展示了一个关键洞察——将 AI 作业的 group 语义暴露给存储层，能让存储层做出比应用层更好的优化决策。这启发我们思考：是否可以将更多的 AI 训练/推理语义（如 pipeline stage 信息、gradient accumulation 步数、prefill/decode 阶段标识）暴露给基础设施层，实现更深层次的协同优化？

3. **值得跟进的研究方向**：
   - **大规模场景下的 I/O 计划求解**：当前的双线性规划方法在千卡规模下的可扩展性存疑，是否可以用近似算法或学习方法加速求解？
   - **训练-推理混合部署场景**：论文仅分别考虑了训练和推理，但在混合部署场景下 compute fabric 的争用更复杂，需要更精细的隔离和调度机制。
   - **与 disaggregated memory 系统的融合**：将 AITURBO 的 staging buffer 思路与 CXL 等新型互连技术结合，可能进一步扩展缓冲区容量和带宽。

4. **最佳切入点**：将 grouped I/O API 思想迁移到开源存储系统（如 3FS）并与主流训练框架（DeepSpeed、Megatron）集成，在更大规模和更多样化的硬件配置下验证其通用性。

---

## 八、总结

AITURBO 是一个面向 AI 工作负载的云存储系统，通过两个核心设计——利用空闲 compute fabric 和 host DRAM 作为存储中转缓冲、以及引入 grouped I/O API 实现透明的去重和负载均衡 I/O 计划——在不增加存储成本的前提下显著提升了 checkpoint 读写和 KV Cache 读取的性能。在 checkpoint 写入上比通用云存储快 3.9–58.8×，比 Gemini 快最高 5.9×；在 KV Cache 读取上比 Mooncake 快最高 1.28×。系统已部署于华为生产云。主要局限在于实验规模有限（最多 64 XPU）、compute fabric 借用的干扰影响未充分量化、以及推理场景中 grouped API 的适用性尚未充分验证。
