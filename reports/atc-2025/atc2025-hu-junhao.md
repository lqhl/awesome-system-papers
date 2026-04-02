# DeepServe: Serverless Large Language Model Serving at Scale

**作者**：Junhao Hu (Peking University / Key Lab of HCST, MOE), Jiang Xu, Zhixia Liu, Yulong He, Yuetao Chen, Hao Xu, Jiang Liu, Jie Meng, Baoquan Zhang, Shining Wan, Gengyuan Dan, Zhiyu Dong, Zhihao Ren, Changhong Liu (Huawei Cloud), Tao Xie (Key Lab of HCST / Peking University), Dayun Lin, Qin Zhang, Yue Yu, Hao Feng, Xusheng Chen, Yizhou Shan (Huawei Cloud)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/hu-junhao
**源文件**：[[atc2025-hu-junhao.pdf]]

---

## 一、背景

随着 ChatGPT 等生成式 AI 平台的兴起，LLM serving 已成为现代数据中心最关键的工作负载之一。Model-as-a-Service (MaaS) 平台需要在云环境中为多租户用户提供高性能、低延迟的推理服务，同时保证 SLO。华为云基于自研 Ascend NPU 芯片（Ascend 910B/910C）构建 AI 集群，面临三大挑战：(1) AI 工作负载时长差异巨大（fine-tuning 数小时 vs. LLM serving 数秒），资源共享困难；(2) LLM serving 日益分布式化和有状态化，单次推理可能跨多个实例并涉及 KV cache；(3) 服务需求高度波动，冷启动延迟成为瓶颈。

---

## 二、要解决的问题

1. **异构工作负载的统一管理**：post-training（fine-tuning）和 model serving 的资源需求和生命周期差异极大，缺乏统一的抽象来管理这些工作负载在共享集群上的调度和资源分配。

2. **PD-disaggregated 与 PD-colocated 的调度决策**：当集群中同时存在 prefill-decode 分离实例和 prefill-decode 共置实例时，如何为每个请求选择最优的实例类型？现有调度器未考虑这种异构 TE 配置。

3. **Prefix caching 与 PD disaggregation 的联合调度**：在同时启用 prefix caching 和 PD disaggregation 的场景下，调度器需要同时权衡 KV cache 复用率、负载均衡和 PD 类型选择，现有方案只考虑其中一个维度。

4. **冷启动延迟**：LLM 模型权重巨大，扩容时需要将模型加载到 NPU 上，传统方式耗时过长（数十秒到分钟级），无法满足 serverless 场景的弹性需求。

---

## 三、洞察与设计

**关键洞察**：PD-disaggregated 和 PD-colocated 实例各有优势区间——长 prefill + 短 decode 的请求更适合 PD-disaggregated，而短 prefill + 长 decode 的请求更适合 PD-colocated。这种优势区间在不同 RPS 下保持稳定，因此可以通过离线 profiling 构建 heatmap 来指导在线调度决策。

基于此洞察，DeepServe 的整体设计包含四个核心组件：

### Serverless 抽象：Request-Job-Task 模型
- **Request**：外部触发（HTTP 调用）
- **Job**：匹配请求类型的处理单元（chat job、fine-tuning job）
- **Task**：Job 内的细粒度操作（prefill task、decode task）
- 架构由 Job Executor (JE)、Task Executor (TE) 和 Cluster Manager 三个核心组件构成

### FlowServe 引擎
基于三个设计原则构建：
- **Microkernel-inspired**：功能解耦为模块化组件，独立扩展和演进
- **NPU-centric execution**：保持 NPU 始终忙碌，异步调度与模型执行并行
- **SPMD-based design**：master-executor 架构，master 负责调度/缓存/网络决策，per-NPU executor 执行

### 调度算法
三层递进式调度：
1. **PD-aware**：基于 heatmap 选择 PD-disaggregated 或 PD-colocated TE 子组
2. **Locality-aware**：在子组内选择 prefix cache 匹配最长的 TE
3. **Load-aware**：当负载不均衡时，优先选择负载最低的 TE

### 快速扩缩容
五步流程（Scaler-Pre → TE-Pre-Load → TE-Load → TE-Post-Load → Scaler-Post），通过 pre-warmed pods/TEs、DRAM pre-loading、NPU-fork 等技术将扩容加速到秒级。

---

## 四、实现细节

### FlowServe 引擎
- 主要用 Python 实现，RTC 和 DistFlow 用 C++ 实现
- **Relational Tensor Cache (RTC)**：统一管理 prefix caching 和 position-independent caching，支持 prefix-token-based 和 ID-based 两种索引机制，内部结合 radix-tree 和 block table
- **DistFlow**：peer-to-peer 和 many-to-many tensor 传输模块，control-plane API（LinkCluster）和 data-plane API（transfer(srcInfo, dstInfo)），在 scaled-out 集群用 HCCL peer-to-peer，在 SuperPod 用 NPU memory copy
- **异步执行**：调度线程与模型执行并行，scheduler 预测下一轮资源需求而不等当前 batch 完成
- **PP 优化**：centralized scheduler 在 PP 第一 stage，统一管理所有 micro-batch，chunked prefill 跨 micro-batch 分配，TTFT 降低 20%+

### 调度算法
- decode 长度预测：使用轻量 LLM（OPT-125M）做分类模型，128 token 粒度的 bucket，84.9% 准确率
- heatmap：离线 profiling 不同 prefill/decode 长度组合下 PD-disaggregated vs PD-colocated 的 JCT 差异，跨 RPS 求和得到 combined heatmap

### 快速扩缩容
- **Pre-warmed TEs**：model-agnostic（同一 TP-8 预热 TE 可跑 Llama3-70B 或 Qwen2-72B）和 parallelism-agnostic（独立的 SPMD-master 和 SPMD-executor pool）
- **NPU-fork**：利用 HCCL broadcast API 从运行中 TE 向多个新 TE 并行传输模型权重
- 每台机器 1.5TB DRAM，可预加载 10 个 70B 模型或 100 个 7B 模型

---

## 五、实验结果

### FlowServe 引擎性能（34B 模型，TP=4）

| 版本 | 优化内容 | 提升 |
|------|---------|------|
| v1 → v2 | 异步调度 + IPC 优化 | TPOT 50ms SLO 下吞吐 2x+ |
| v2 → v3 | 数据结构 + sampling 优化 | ~20% 提升 |

### PD Disaggregation（内部 trace）
- 2P+2D 配置在 TTFT 和吞吐上显著优于 4_PD（colocated），特别是高吞吐区间

### PD-aware 调度（34B，TP=4，4 servers）
- 在中等 RPS（~10 reqs/s）下 PD-aware 调度优于 Round Robin
- 低 RPS 时两者接近（PD-colocated 内 prefill/decode 干扰可忽略）
- 极高 RPS 时 PD-aware 略差于 RR（PD-disaggregated TE 更容易过载），但性能退化不显著

### 扩缩容性能

| 模型 | 优化前总时间 | 优化后总时间 |
|------|------------|------------|
| Llama3-8B TP=1 | ~42s | ~5s |
| CodeLlama-34B TP=4 | ~45s | ~17s |
| Qwen-72B TP=8 | ~47s | ~23s |

### NPU-fork TE-Load 时间

| 模型 | DRAM-miss | DRAM-hit | NPU-fork (HCCS) | NPU-fork (RoCE) |
|------|-----------|----------|-----------------|-----------------|
| Llama3-8B | 11s | 3.3s | 0.15s | 0.53s |
| CodeLlama-34B | ~3.2s | ~0.71s | 0.16s | 0.76s |
| Qwen-72B | ~2.1s | ~0.91s | 0.19s | ~0.53s |

- NPU-fork 可并行扩容到 32+ TE，scaling time 亚线性增长

---

## 六、批判性分析

1. **PD-aware 调度收益有限且场景受限**：论文 Figure 7 显示 PD-aware 调度仅在中等 RPS 下有优势，低 RPS 和高 RPS 下均与 Round Robin 接近甚至更差。在实际生产环境中，RPS 是动态变化的，这使得 PD-aware 调度的实际收益存疑。论文未报告 PD-aware 调度在端到端生产 trace 上的整体收益。

2. **decode 长度预测的鲁棒性存疑**：84.9% 的准确率听起来不错，但论文使用 128 token 粒度的粗分类——如果改用更细粒度，准确率可能大幅下降。更关键的是，这个预测模型在不同业务场景（code generation vs. chat vs. summarization）间的泛化能力未被评估。

3. **heatmap 的静态性与动态环境的矛盾**：heatmap 是离线 profiling 得到的静态结果，但实际集群中 TE 的负载状态、KV cache 驻留情况是动态变化的。论文声称 heatmap 跨 RPS 稳定，但仅在 5-30 RPS 范围内验证，未覆盖真实生产环境的极端情况。

4. **缺乏与开源 baseline 的公平对比**：论文的核心引擎 FlowServe 运行在 Ascend NPU 上，与 vLLM/SGLang 等运行在 NVIDIA GPU 上的系统没有直接可比性。FlowServe 的性能提升中有多少来自系统设计、多少来自硬件特性，无法区分。

5. **扩缩容场景的 NPU-fork 依赖强硬件假设**：NPU-fork 的核心优势依赖 HCCS 高速互联（200GB/s），在 RoCE 网络下性能大幅下降。对于没有 SuperPod 级硬件的场景，NPU-fork 的实用性有限。

6. **容错机制描述过于简略**：论文仅用一段话描述了 fault recovery（5 分钟恢复），对于一个声称已在生产环境运行超过一年的系统，缺乏故障率、恢复成功率、RTC 状态丢失对用户体验的影响等关键数据。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴

1. **Request-Job-Task 抽象的通用性**：这个三层抽象不仅适用于 LLM serving，还可以扩展到 training（一个 training request 分解为 data preprocessing → training → evaluation 的 job 链）。对于构建统一的 AI 平台（training + serving + agent），这种抽象值得借鉴。

2. **PD-aware 调度的方法论**：用 heatmap profiling 来指导异构实例的调度决策，这种方法论可以推广到其他异构场景：例如在混合部署不同 GPU 型号（A100 + H100）的集群中，用类似 heatmap 方法来决定不同类型请求的最优放置。

3. **NPU-fork 对模型加载的启示**：利用高速互联从运行中实例传输模型权重，比从存储加载快一个数量级。这对 GPU 集群同样适用——NVLink/NVSwitch 的带宽远高于 PCIe，可以设计类似的 GPU-fork 机制用于快速扩容。

### 值得跟进的方向

1. **动态 heatmap 更新**：当前 heatmap 是静态的。能否设计一个在线学习机制，基于实际请求的 JCT 反馈动态更新 heatmap？这在模型版本迭代、硬件配置变化时尤其重要。

2. **Agent serving 的调度**：论文提到 DeepServe 支持 agent serving 但未展开。Agent workload 涉及多轮推理、工具调用、长上下文，其调度策略与普通 chat serving 有本质区别，是一个值得深入的方向。

3. **跨代硬件的统一调度**：DeepServe 同时运行 Gen1（scaled-out）和 Gen2（SuperPod）集群，但论文未讨论跨代硬件的统一调度。如何在异构硬件池中做全局最优调度是一个重要且未解决的问题。

---

## 八、总结

DeepServe 是华为云构建的大规模 serverless LLM serving 平台，基于 Ascend NPU 集群，已生产运行超过一年。其核心贡献包括：(1) Request-Job-Task 三层 serverless 抽象统一管理多种 AI 工作负载；(2) FlowServe 引擎采用 microkernel-inspired、NPU-centric、SPMD-based 三大原则实现高效推理；(3) 联合 PD-aware、locality-aware、load-aware 的分布式调度算法处理异构 TE 配置；(4) 通过 pre-warmed pods/TEs、DRAM pre-loading、NPU-fork 等技术实现秒级扩容（最多 64 实例）。论文作为工业系统论文，提供了丰富的生产经验，但部分调度优化的收益在极端场景下有限，且核心性能优势与 Ascend 硬件特性耦合较深。
