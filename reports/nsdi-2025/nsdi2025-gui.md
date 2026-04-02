# Accelerating Design Space Exploration for LLM Training Systems with Multi-experiment Parallel Simulation

**作者**：Fei Gui (清华大学/BNRist/清华深圳国际研究生院), Kaihui Gao (中关村实验室), Li Chen (中关村实验室), Dan Li (清华大学), Vincent Liu (宾夕法尼亚大学), Ran Zhang (中关村实验室), Hongbing Yang (中关村实验室), Dian Xiong (清华大学)
**会议**：NSDI 2025
**链接**：https://www.usenix.org/conference/nsdi25/presentation/gui
**源文件**：[[nsdi2025-gui.pdf]]

---

## 一、背景

LLM 的规模持续增长，推动企业构建包含数万至数十万 GPU 的大规模训练集群。训练系统的设计空间随之急剧膨胀，涵盖并行化策略（TP/PP/DP 的 group size）、集合通信参数、拥塞控制算法、网络拓扑等多个维度。在实际生产中，探索最优拓扑可能需要超过 10k 次仿真实验，而并行 group size 优化也需要约 100 次实验。设计空间探索不充分会导致严重的性能损失——例如，选用次优拓扑可能导致训练迭代时间增加 3.4 倍。

仿真器是设计空间探索的核心工具，因其成本远低于物理测试平台、精度高于解析模型。然而，现有仿真器在处理大规模多实验并行时效率不足，成为制约探索效率的瓶颈。

---

## 二、要解决的问题

1. **多实验并行效率低**：现有方法主要采用 Multi-Process 方式并行运行多个仿真实验，但进程间同步开销大、上下文切换频繁，MPSE 和 MPME 策略在 500 个实验时需要约 2000 小时。

2. **单进程多实验（SPSE）的 cache miss 问题**：UNISON 和 DONS 等先进仿真器在 SPSE 模式下，naive 地为每个实验启动独立仿真副本，导致严重的 CPU cache miss 和亚线性扩展。

3. **CPU 并行度受限**：即使采用 SPME（Single-Process Multi-Experiment）策略在 CPU 上已展现优势，但受限于 CPU 核心数量，仍不足以应对当前 AI 集群规模的仿真需求（例如 DONS+SPME 完成一个 use case 需约 370 小时）。

4. **服务器内通信仿真不准确**：现有 AI 训练仿真器使用静态参数的解析模型模拟 NVLink/PCIe 通信，误差高达 20%-72%，因为未能捕捉 NCCL 软件栈引入的开销变化。

---

## 三、洞察与设计

**关键洞察**：设计空间探索中的多个仿真实验是 embarrassingly parallel 的，且这些实验执行相同的仿真逻辑、操作同构的数据结构。这种「单指令、多数据」的特征天然契合 GPU 的 SIMD 执行模型。通过 Data-Oriented Design（DOD）将仿真逻辑与数据分离，可以在单进程内跨实验批量处理同类操作，充分利用 GPU 的大规模并行核心。

基于此洞察，论文提出 **Multiverse**——首个基于 GPU 的 AI 训练仿真器，核心设计包括：

1. **SPME + DOD 执行策略**：在单个仿真进程内同时运行多个实验，通过 DOD 原则识别跨实验的批处理和并行化机会。相比多进程方案，消除了进程调度开销和重复内存占用。

2. **ECS（Entity-Component-System）建模**：用 ECS 架构对 AI 训练系统建模——Entity 包括 Task、Flow、Switch Port 等；Component 存储状态数据；System 定义仿真逻辑。跨实验的同类 Entity 共享一张 column store 表，保证内存访问的连续性和 cache 友好性。

3. **GPU 全托管执行**：所有仿真逻辑编译到 GPU 上执行。每个 ECS System 调用映射为 GPU 线程，利用 SIMT 模型对所有实验的同类 Entity 并行处理。通过隐式 ExpID 组件区分不同实验的状态。

4. **System Execution Graph**：定义每个仿真步的 8 个 ECS System 执行顺序（Schedule → AnalyticalSys → SendSys → NICSndSys → ForwardSys → TransmitSys → NICRcvSys → ACKSys），运行时据此调度 GPU 核心。

---

## 四、实现细节

**三项 GPU 优化技术**：

1. **Pull-based Synchronization**：针对网络仿真中常见的 many-to-one 写冲突（如多个 ingress port 向同一 egress port 转发），将 forward 系统拆分为 `set_forward_plan`（源端标记待发包到 bitmap to-do list）和 `forward`（目标端主动从源端拉取数据）两阶段，实现无锁并行，带来 3.2-5.4× 加速。

2. **Intra-server Communication Analytical Model**：通过大量实测校准 `y = α + comm_size/β` 模型的参数，针对不同集合通信算子、不同 GPU 型号（A100/H100）和不同通信规模分别拟合 α 和 β。校准后误差从 ASTRA-sim 的 20%-72% 降至 0.7%-1.2%。还支持通信-计算 overlap 的建模。

3. **Megakernel 技术**：将所有 ECS System 及组件管理代码编译为单个 CUDA megakernel，每个 batch simulation step 只需一次 CPU→GPU 启动，消除了逐 System 启动 kernel 的同步开销，减少 16.6%-18.6% 仿真时间。

**实现规模**：基于 Madrona 框架，核心代码约 13k 行 C++。支持 TP/DP 并行策略、Ring Allreduce/Allgather/Reducescatter 集合通信、DCQCN/HPCC/DCTCP 拥塞控制、ECMP 和 packet spraying 负载均衡。

**多 GPU 支持**：当单 GPU 内存不足以容纳所有实验时，Multiverse 自动将独立实验分配到多个 GPU 并进行负载均衡。

---

## 五、实验结果

**实验平台**：1 × NVIDIA H100 GPU + 80 核 Intel CPU + 256GB 内存。准确性验证使用 128 台服务器（各 8× H100 GPU + 8× ConnectX-7 NIC）的真实集群。

**四个 Use Case**：

| Use Case | GPU 规模 | 拓扑 | 模型 | 实验数量 |
|---|---|---|---|---|
| #1 拓扑优化 | 128 GPUs | Fattree-like | GPT-3 13B | 10,000 |
| #2 集合通信优化 | 1,024 GPUs | Fattree k=16 | LLaMA 65B | 500 |
| #3 TP/DP/PP Group Size | 8,192 GPUs | Fattree k=32 | GPT-3 175B | 100 |
| #4 拥塞控制算法比较 | 54,000 GPUs | Fattree k=60 | GPT-dense 175B | 4 |

**仿真速度**（相比 state-of-the-art 加速比）：

| 对比方法 | Use Case #1 (128 GPU) | Use Case #2 (1k GPU) | Use Case #3 (8k GPU) |
|---|---|---|---|
| vs ASTRA-sim+UNISON(SPSE) | 73.2× | 67.6× | 57.4× |
| vs ASTRA-sim+DONS | 25.1-47.2× | — | — |
| vs Multiverse(SPSE) | 7.3× | 2.4× | 1.7× |

**最大仿真规模**：单 GPU 可仿真最多 54k GPU、4.5k 交换机、162k 链路的集群，此时仍比 CPU 方案快 28.6-43.1×。

**并行实验容量**（单 GPU）：128 GPU 集群可并行 520 实验、1,024 GPU 集群可并行 70 实验、8,192 GPU 集群可并行 5 实验。

**仿真精度**：

| 指标 | Multiverse 误差 | ASTRA-sim 误差 |
|---|---|---|
| 服务器内通信（小消息） | 1.0-1.2% | 最高 72.1% |
| 服务器内通信（大消息） | < 0.8% | > 22.0% |
| 端到端迭代时间（1,024 GPUs） | < 3.0% | > 20.0% |

**Ablation Study 贡献分解**：
- Analytical model：1.7-1.8× 加速
- Pull-based synchronization：3.2-5.4× 加速
- Megakernel：减少 16.6%-18.6% 仿真时间

---

## 六、批判性分析

1. **并行策略支持不完整**：当前仅支持 TP 和 DP，不支持 PP（Pipeline Parallelism）。然而 use case #3 声称探索 TP/DP/PP group size，这在实现层面存在矛盾。论文对此未做解释。

2. **准确性验证规模有限**：精度验证仅在 1,024 GPU 集群上进行，而性能测试声称可仿真 54k GPU。大规模仿真的准确性缺乏真实对照验证——这恰恰是论文最需要证明的能力区间。

3. **拓扑和模型覆盖面窄**：仅测试了 Fattree 系列拓扑，未验证 Dragonfly、Torus、BCube 等论文背景中提到的拓扑。模型仅覆盖 GPT-3 和 LLaMA，缺少 MoE 等非稠密架构的验证。

4. **通信-计算 overlap 建模依赖经验参数**：overlap ratio 和计算时间延长的建模采用经验方法，依赖 GPU 类型和模型类型的先验知识。论文未说明这些经验参数如何获取、泛化性如何。

5. **单 GPU 内存成为瓶颈**：54k GPU 集群仅能运行 1 个实验，实际上无法实现多实验并行——而多实验并行正是论文的核心卖点。论文未深入讨论多 GPU 扩展的效率。

6. **缺少与搜索算法的集成评估**：论文假设设计空间探索是暴力搜索（10k 次实验），但实际工程中通常结合 Bayesian optimization 或遗传算法等智能搜索。Multiverse 的价值在结合智能搜索后可能被稀释，论文未讨论此场景。

---

## 七、AI Infra / MLSys 视角

**启发与借鉴**：

1. **仿真驱动的系统设计闭环**：Multiverse 展示了「仿真→探索→决策」在 AI 集群设计中的可行路径。对于 AI Infra 团队，在部署前通过高速仿真筛选最优配置（拓扑、并行策略、CC 算法），可大幅降低试错成本。

2. **ECS 架构的通用性**：ECS 的 data-oriented 设计不仅适用于网络仿真，也可迁移到其他 AI Infra 仿真场景——如调度器仿真、内存管理策略评估、集群故障注入测试等。

3. **GPU 加速仿真的范式**：论文将仿真计算从 CPU 迁移到 GPU 的思路（SPME + DOD + megakernel）为其他 batch simulation 任务提供了参考模板。

**值得跟进的方向**：

- **扩展到推理系统仿真**：当前 Multiverse 聚焦训练仿真。推理系统（如 continuous batching、speculative decoding、KV cache 管理）的设计空间同样庞大，且对延迟更敏感，值得将 Multiverse 框架扩展至推理场景。
- **与自动搜索算法集成**：将 Multiverse 作为 fast oracle 嵌入 Bayesian optimization 或 reinforcement learning 驱动的自动配置搜索系统中，构建端到端的 auto-tuning 方案。
- **MoE 和异构集群支持**：当前缺少对 MoE 架构（Expert Parallelism、all-to-all 通信模式）和 CPU/GPU/NPU 异构集群的仿真支持，这是实际 AI Infra 的重要需求。

---

## 八、总结

Multiverse 是首个基于 GPU 的 AI 训练仿真器，通过 SPME 执行策略结合 ECS/DOD 建模和 GPU 加速（pull-based synchronization、校准的解析模型、megakernel），实现了对 LLM 训练系统设计空间的高效探索，相比 CPU 方案取得 43.1-73.2× 加速，同时保持 < 3.0% 的仿真精度。该系统适用于需要大规模仿真实验的集群设计场景（拓扑搜索、并行策略选择、通信优化等），但在并行策略覆盖、大规模准确性验证和智能搜索集成方面仍有提升空间。
