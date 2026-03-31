# NanoFlow: Towards Optimal Large Language Model Serving Throughput

**作者**：Kan Zhu, Yufei Gao, Yilong Zhao, Liangyu Zhao, Gefei Zuo, Yile Gu, Dedong Xie, Tian Tang, Qinyu Xu, Zihao Ye, Keisuke Kamahori, Chien-Yu Lin, Ziren Wang, Stephanie Wang, Arvind Krishnamurthy, Baris Kasikci（University of Washington, Tsinghua University, UC Berkeley, University of Michigan）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation），July 7–9, 2025, Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/zhu-kan
**源文件**：[osdi25-zhu-kan.pdf](../../papers/osdi-2025/osdi25-zhu-kan.pdf)

---

## 一、背景

大语言模型（LLM）服务已进入行星级规模，ChatGPT 拥有逾 2 亿周活跃用户，GPT-4o Mini 发布后 API 调用量翻倍。LLM 推理区别于传统 DNN 的核心特征在于：模型规模极大（GPT-3 175B，需 5 张 A100 80GB 存储 FP16 权重）、KV-cache 随上下文长度二次增长、每次 decode 迭代须将完整模型权重与所有 KV-cache 全部加载一次。这些特性使得 LLM serving 长期以来被普遍认为是**内存带宽瓶颈**（memory-bound）。

当前顶级推理系统（vLLM、TensorRT-LLM、DeepSpeed-FastGen）虽然在单个操作上的资源利用率已达约 80%，但端到端实测计算利用率仅约 40%。论文针对这一现象展开量化分析，并提出系统性解法。

---

## 二、要解决的问题

**核心矛盾**：LLM serving 由三类计算资源特性不同的操作构成——

| 操作类型 | 代表操作 | 瓶颈资源 |
|---|---|---|
| Compute-bound | KQV/O/Up/Gate/Down 投影（GEMM） | FP16 算力 |
| Memory-bound | Decode Attention（GEMV） | 显存带宽 |
| Network-bound | AllGather / AllReduce | NVLink 带宽 |

现有系统在单 GPU 内**顺序执行**这三类操作：当计算密集操作在跑时，显存带宽和网络通道空闲；当内存密集操作在跑时，CUDA 计算核心大量浪费。论文将这些浪费称为 pipeline bubbles（"WASTED"）。

进一步地，论文还指出：**LLM serving 整体其实是 compute-bound 的**，这与传统认知相悖。GQA（Grouped Query Attention）大幅减少每 batch 需加载的 KV-cache 量，使 GEMM 成为更主要的瓶颈；随着模型规模增大，P_Model 中 Dense 操作占主导，以至于 T_compute / T_mem > 2（在测试的所有主流硬件和主流 workload 上均成立，除极端长 decode 场景外）。

---

## 三、核心设计

NanoFlow 的核心思想是**intra-device parallelism（设备内并行）**：将一个大 batch 拆成多个互不依赖的 nano-batch，对每个 nano-batch 分别启动 nano-operation，从而使不同资源约束的操作能在同一时刻并行执行。

**关键抽象：nano-batch + nano-operation**
- 对原始 batch size = 2048 的 Up 投影，NanoFlow 可拆成 UP1（batch 0–768）和 UP2（batch 768–2048），二者无数据依赖
- 不同 nano-operation 分配不同比例的 GPU 资源（R：resource utilization），以 GEMM 操作为计算轴，令 memory/network 操作用剩余资源同步执行

**Auto-search**：自动确定 nano-batch 数量、大小、执行顺序、资源分配
- **Stage I**（Pipeline Structure Search）：在不考虑 kernel 互干扰的假设下，用 MILP 求解最优 pipeline，消除 compute bubble；从 2 个 nano-operation 开始迭代增加
- **Stage II**（Pipeline Refinement）：建立 pairwise GEMM-GEMV/GEMM-Network kernel interference profile（R→P 映射表），将干扰量化为吞吐损失，再次用 MILP 在给定 R 分配下最小化执行时间

**Pipeline 示例（LLaMA-2-70B）**：在每层 decode 开头（KQV + DecAttn），三种资源同时活跃，auto-search 自动选择 4 个 nano-operation；其余部分以 2 个 nano-operation 为主，GEMM 优先分配高 R。

---

## 四、实现细节

**Kernel Profiling**
- GEMM：穷举 thread blocks、warps、tile size，输出 `(kernel, batch_size) → 最优实现 + 执行时间`
- GEMV/Network：限制 thread block 数在 8–128（步长 8），排除低效 GEMM 实现；仅做 pairwise 干扰分析（compute-memory 和 compute-network），实测约 ~100 个 GEMM-GEMV pair（A100，GEMM shape 384×4096×4096），约 10 分钟可完成 auto-search

**干扰模型**：R→P 映射在所有 64 个 batch size 组合和所有 GEMM 形状下标准差在均值 5% 以内，可作全局查表使用

**Runtime**
- 多 CUDA stream 并行执行 nano-operation，用 CUDA event 约束依赖顺序
- **异步调度**：batch formation 与 GPU 执行流水，提前一个 iteration 完成调度，隐藏 CPU 调度开销
- **KV-cache 分级 offload**：在 KQV generation 完成后立即将 KV vector offload 至 CPU 内存/SSD，利用 FFN 的 compute-bound 阶段做 device-host copy（GPU 资源占用极低），减少显存压力；LRU 策略管理多级缓存；利用 NUMA-aware thread binding 提升 offload 吞吐
- **内存管理**：基于 PagedAttention 的 KV-cache 页管理；连续 buffer + scatter 机制实现 7–10× host-to-device 带宽提升

**代码规模**：约 10K 行 CUDA + 6K 行 Python

---

## 五、实验结果

**实验平台**：8×A100 80GB SXM NVLink；部分模型单卡测试

**理论最优吞吐（LLaMA-2-70B，8×A100）**：1857 tokens/s/GPU（基于 CUTLASS 实测 280 TFLOPS FP16）

### 离线吞吐（vs 基线）

| 设置 | vs vLLM | vs DeepSpeed-FastGen | vs TensorRT-LLM | vs 理论最优 |
|---|---|---|---|---|
| 固定长度（均值） | 2.62× | 2.78× | 1.73× | — |
| 真实数据集（均值） | 4.18× | 3.45× | 1.91× | 68.5% |
| Splitwise（最佳单点） | — | — | — | 68.5% |

### 延迟（LMSys-Chat-1M 数据集，SLO = 200ms normalized latency）
- 低请求率时延迟与 TensorRT-LLM 相当
- NanoFlow 可承载比 TensorRT-LLM 高 **1.64×** 的请求率仍在 SLO 以内
- P99 延迟仅为均值的 **1.07×**（因固定 dense batch size，稳定性佳）

### Ablation（LLaMA-2-70B，Input 512 / Output 512）
| 变体 | 吞吐（tokens/s/GPU） |
|---|---|
| Non-overlap（无 nano-batch） | ~494 |
| Nano-batch only（仅分批不重叠） | ~432（-13.2%） |
| NanoFlow（分批+重叠） | ~735 |
| NanoFlow + KV offload | ~713（-3.0%） |

Network overlap 带来 1.07× 加速，Network + Memory overlap 带来 1.17× 加速；offload 使 multi-round 场景计算量降低 3.02×。

### 跨模型泛化（8×A100，Input 1024 / Output 512）

| 模型 | NanoFlow vs vLLM | NanoFlow / 理论最优 |
|---|---|---|
| LLaMA-3-70B | 2.20× | 78.5% |
| Qwen2-72B | ~2.2× | 70.6% |
| Deepseek-67B | ~2.1× | 67.4% |
| Mixtral-8×7B | ~2.4× | 59.1% |
| LLaMA-3-8B（1×A100） | ~9.7%→ | 50.4% |

---

## 六、批判性分析

**论文真实贡献清晰，但以下几点值得深究：**

1. **"Compute-bound"结论的适用范围被放大**。论文在 §3.3 中将 LLaMA-3-8B（1×A100）列为 compute-bound 区域，但 Figure 3 的热力图显示其在 512-1024（长 decode）场景的 T_R ≈ 1，处于边界；而 NanoFlow 在 LLaMA-3-8B 上只实现了理论最优的 50.4%，远低于其他模型（70%+），说明 8B 模型本身的 compute-bound 程度远弱于宣称。

2. **Nano-batching 有固有成本被轻描淡写**。论文 §6.4 承认 nano-batch-only 基线较 non-overlap 基线下降 13.2%（weight loading 额外次数带来的内存开销），但后续对各模型的"1.91×"宣传均已包含该 overhead，却没有明确指出：在某些 memory-bound 偏向场景下，nano-batching 是净负收益，NanoFlow 的收益完全来自重叠抵消了该 overhead。

3. **MoE 模型的 baseline 不公平**。Mixtral-8×7B 上 NanoFlow 的优势（59.1% optimal，约 2.4× vs vLLM）看似出色，但论文未说明 vLLM 是否启用了 expert-parallel 或 MoE 专属优化；MoE 的 grouped-GEMM 特性使 vLLM 的 batch 效率天然较低，让 NanoFlow 的相对优势被高估。

4. **单节点实验的局限**。NanoFlow 仅测试了单台 8×A100 DGX 节点，且使用 tensor parallelism（TP=8）。在 multi-node pipeline parallelism 场景下，nano-batch 在 PP stage 间的依赖管理会大幅复杂化，论文没有探讨或评估这一场景，使"planet-scale serving"的宣称缺乏支撑。

5. **Auto-search 的 10 分钟开销在在线场景中是否可接受**。论文声称 search 时间相对部署时间可忽略，但对于 workload pattern 频繁变化的云服务场景，重新触发 search 的条件（"significant changes"）过于模糊，实际工程可用性存疑。

6. **与 SGLang、Dynamo 等新系统的对比缺失**。以 v0.5.3 的 vLLM 和 v0.8.0 的 TensorRT-LLM 作基线，而当时 SGLang、vLLM v0.6+ 以及 NVIDIA Dynamo 等已有更激进的调度优化，选取较旧版本基线会高估提升幅度。

---

## 七、AI Infra / MLSys 视角

**核心 insight 的可迁移性**

NanoFlow 的 intra-device parallelism 思路具有重要的 systems 启发价值：

1. **"Compute as the unified resource"的设计范式**：论文将 GEMM 利用率作为全局优化目标，用 R（资源分配比例）统一度量 compute/memory/network 的交换，这种以最稀缺资源为轴心建模的方式值得在其他 workload（如多模态推理、mixture-of-experts 等）中复现。

2. **Kernel interference modeling 是被低估的工程问题**：pairwise R→P 映射表的思路（profile once，serve everywhere）是一种轻量实用的硬件感知调度框架，可应用于训练中的 all-reduce 与 backward overlap（如 ZeRO-1/2），以及 speculative decoding 中 draft 与 target model 的并行执行。

3. **延伸研究方向**：
   - **跨节点 nano-batch**：在 pipeline parallelism 场景下，nano-batch 能否在 stage 间形成更细粒度的流水？这需要重新建模 stage 依赖和通信 latency，但潜力较大。
   - **动态 workload 下的在线 auto-search**：当前 auto-search 假设 workload 相对稳定，如何做 lightweight incremental re-planning（而非重跑 MILP）是一个实际价值高的开放问题。
   - **与 speculative decoding 的结合**：draft model（小模型，memory-bound）和 target model（大模型，compute-bound）天然是 NanoFlow intra-device overlap 的候选对象，两者的 resource profile 互补。
   - **Disaggregated prefill/decode + nano-batching**：DistServe/Splitwise 做了 prefill-decode 分离，NanoFlow 在统一 batch 内做 overlap；能否在 disaggregated 架构中也引入 intra-device 并行？

---

## 八、总结

NanoFlow 通过量化证明现代 LLM serving 的 compute-bound 本质，并以 nano-batch + intra-device parallelism 弥补了因异构操作顺序执行导致的 GPU 利用率损失。在 LLaMA-2-70B 上实现理论最优吞吐的 68.5%，相比 TensorRT-LLM 提升 1.91×。主要局限在于：MoE/小模型收益有限、单节点实验缺乏规模验证、基线版本偏旧、auto-search 的工程适用性尚待评估。整体而言，NanoFlow 的分析框架和核心抽象对 LLM serving 系统设计有重要参考价值。
