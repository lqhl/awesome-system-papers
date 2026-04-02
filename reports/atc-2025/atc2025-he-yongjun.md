# Resource Multiplexing in Tuning and Serving Large Language Models

**作者**：Yongjun He, Haofeng Yang (ETH Zürich); Yao Lu (National University of Singapore); Ana Klimović, Gustavo Alonso (ETH Zürich)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/he-yongjun
**源文件**：[[atc2025-he-yongjun.pdf]]

---

## 一、背景

LLM 的部署成本高昂，GPU 是主要的计算资源瓶颈。然而，即使是资源密集型的 LLM 工作负载也难以让 GPU 保持高利用率——例如 Llama 3-8B 在 A100 上做 decoding 时，GPU 计算利用率不到 10%。与此同时，PEFT（参数高效微调）需求持续增长，2024 年仅 HuggingFace 上就上传了超过十万个 LoRA adapter。在实际部署中，微调和推理往往竞争同一组有限的 GPU 资源，尤其是在 on-premise 场景下，推理负载又存在巨大的分钟级波动（如 BurstGPT 和 Chatbot Arena 的真实 trace 所示），导致 GPU 在低峰时严重闲置。

---

## 二、要解决的问题

现有方案无法在共享 GPU 执行 PEFT 和 LLM 推理时同时满足**高利用率**和**低延迟 SLO**：

1. **时间复用（Temporal Multiplexing）**：如 FineInfer 的 Deferred Continuous Batching，PEFT 和推理交替执行。当 PEFT 的单步延迟超过 TTFT SLO（随模型规模和序列长度增长），推理请求会被严重阻塞，且 decoding 阶段的计算资源被浪费。
2. **空间复用（Spatial Multiplexing）**：如 NVIDIA MPS，在启动时静态划分 SM 资源。低负载时 PEFT 分得的资源被限制，高负载时又可能违反 SLO。且无法动态调整。
3. **Chunked-training**（FlexLLM）：将 PEFT 输入序列切分为小 chunk 逐步执行。但小 chunk 无法充分利用 GPU 计算能力，且产生额外的 HBM→SRAM 数据搬运开销（模型需被加载 2N 次）。
4. **上下文切换开销**：不同模型/任务间的切换需要秒到分钟级的模型加载和引擎初始化时间。
5. **基模型独占**：现有方案（vLLM + torchtune）无法共享基模型，单个 LLM 就可能耗尽全部 GPU 显存。

---

## 三、洞察与设计

**关键洞察**：LLM 微调和推理具有互补的资源使用模式——decoding 阶段是 memory-bound（MFU < 5%，每步仅计算一个 token 但需加载整个模型），而 PEFT 的 forward/backward 是 compute-bound。通过在迭代级别对这两类任务进行空间 batching 和时间重排，可以同时实现可控的进程间干扰、快速上下文切换、最大化 PEFT 吞吐量，以及在 SLO 范围内完成推理。

LLMStation 的核心设计：

1. **迭代级多任务调度（Iteration-level Multitasking Scheduling）**：在每个 decoding iteration 之前，调度器根据延迟预测器的估算，动态决定当前迭代可以与多少个 PEFT tasklet 并行执行，确保不违反 SLO。调度目标是最大化 PEFT tasklet 数量 $N_p$，约束条件为 decoding 延迟不超过 SLO。

2. **可挂起的自动微分引擎（Suspendable Autograd Engine）**：将 PyTorch Autograd 的 backward pass 中的嵌套函数转换为 C++ stackless coroutine，使得 backward pass 可以在任意层边界处自愿挂起（suspend）和恢复（resume）。这使得调度器能够精确控制每次与 decoding 共同执行的 backward tasklet 数量。

3. **Fusion Engine**：当 PEFT 处于 forward pass 时，将推理 decoding 和 PEFT forward 的计算融合——将两者的输入 tensor 在 batch 维度拼接后送入同一个线性层（QKV projection、MLP 等），仅在 self-attention 处分开计算（因 KV cache 不同），从而摊平 kernel launch、数据搬运和通信开销。

4. **内存管理**：基模型、adapter 和推理状态在 PEFT worker 和推理 worker 之间共享，仅微调状态（optimizer state）独占。支持 GPU↔CPU 的 tensor swap。

---

## 四、实现细节

- **代码规模**：约 3k 行代码。
- **Autograd Engine**：基于 PyTorch Autograd 的 C++ 实现修改，使用 C++ stackless coroutine（ISO 标准）实现 backward pass 的 suspend/resume。用 `co_await` 替代普通函数调用，`co_return` 替代 `return`。单 GPU 上 coroutine 挂起/恢复的额外延迟 < 0.5%；多 GPU 场景下由于进程间同步放大，overhead 可达 18%。
- **推理引擎**：基于 vLLM 构建，复用其 PagedAttention 和 KV cache 管理。
- **Fusion Engine**：基于 FineInfer 构建，支持 tensor model parallelism（列切分 QKV/GateUP，行切分 AttnOutput/Down），跨 GPU 使用 all-reduce 通信。
- **延迟预测器**：三层结构——(1) 缓存的运行时记录（精确命中）；(2) profiling 结果；(3) 学习的线性回归模型。输入特征包括 batch size、序列长度、硬件/模型配置。缓存组织为嵌套索引：顶层 key 为 (hardware, model, adapter)，内层 key 为 (decode batch size, PEFT input length)。R² score 约 0.69-0.73，但由于系统运行几个 iteration 后即以缓存为主，对性能影响有限。
- **调度器延迟**：planner + latency predictor 平均 18μs/iteration；有缓存时 < 1μs。
- **分布式支持**：目前仅支持 Tensor Parallelism（TP），不支持 Pipeline Parallelism（PP）。

---

## 五、实验结果

**硬件配置**：

| 模型 | GPU | 层数 | TP 度 |
|------|-----|------|-------|
| Llama-3.1-8B | 2× RTX 3090 | 32 | 2 |
| Llama-2-13B | 4× RTX 3090 | 32 | 4 |
| Llama-3.1-70B | 2×4 H100 | 80 | 4 |

**基线**：FineInfer（temporal）、vLLM + torchtune（spatial via MPS）、chunked-training（FlexLLM）

**主要结果**：

| 场景 | vs FineInfer | vs vLLM+torchtune | vs chunked-training |
|------|-------------|-------------------|---------------------|
| 合成负载 PEFT 吞吐 | 2.38–8.17× | 2.53–14.77× | 1.57–2.18× |
| 真实负载 PEFT 吞吐 | 最高 2.98× | 最高 2.41× | 最高 1.74× |
| Llama-8B P99 TTFT | 33.13× 更低 | 52.64× 更低 | 1.4× 更低 |
| Llama-8B P99 TPOT | 2.29× 更低 | 362.49× 更低 | 1.29× 更低 |
| Llama-70B P99 TTFT | 180.48× 更低 | — | 1.23× 更低 |

**微基准**：
- Autograd 挂起开销：单 GPU < 0.5%，多 GPU ≤ 18%
- 调度器开销：< 18μs/iteration（无缓存），< 1μs（有缓存）
- GPU 利用率 case study：LLMStation 在大部分时间段保持高 SM Active、高 Compute Warps in Flight 和高 DRAM Write Bandwidth

---

## 六、批判性分析

1. **吞吐提升数字跨度过大（1.38×–14.77×）**：最高的 14.77× 来自与 vLLM + torchtune 在低请求率下的比较，而 vLLM + torchtune 本身因无法共享基模型、需静态划分资源而天然劣势显著，属于"弱基线"。与更强的 chunked-training 对比，提升仅 1.38×–2.18×，说明真正的核心优势相对有限。

2. **多 GPU Autograd overhead 被轻描淡写**：多 GPU 场景下 coroutine 挂起带来高达 18% 的额外延迟，但论文仅在 microbenchmark 中一笔带过，未分析这对端到端吞吐和延迟的影响。对于实际部署中普遍采用多 GPU 的大模型场景（如 70B），这个 overhead 可能比论文呈现的更显著。

3. **SLO 定义与实际不一致**：论文自己承认其 "decoding SLO" 与常用的 TPOT SLO 定义不同（前者是单步延迟，后者是端到端平均），仅在 disaggregated serving 下等价。但实验中并未使用 disaggregated serving，这意味着报告的 "SLO 达标" 可能存在歧义——实际用户感知的 TPOT 可能不同于论文声称的保证。

4. **仅支持 TP，不支持 PP**：对于跨节点部署的超大模型（如需要多机的 70B+ 模型），仅有 TP 的限制使得系统的实际适用范围受限。论文将此作为 future work 提及，但这是实际部署中的关键需求。

5. **Adapter 场景有限**：实验仅覆盖 LoRA（rank 8/16/32），未涉及 QLoRA、DoRA 等其他主流 PEFT 方法。Fusion Engine 的 composite/split 策略是否适用于其他 adapter 架构未得到验证。

6. **缺少收敛性/精度验证**：论文仅提到"与 HuggingFace PEFT 对齐了微调结果"，但未给出具体的 loss curve 或 downstream task accuracy 对比，无法确认 coroutine 式 suspend/resume 是否引入数值偏差。

---

## 七、AI Infra / MLSys 视角

1. **迭代级调度粒度的启示**：LLMStation 的核心贡献在于将 GPU 复用的调度粒度从 request-level / job-level 下沉到 iteration-level，这个思路对 AI Infra 有广泛的借鉴价值——不仅限于 PEFT + serving，也可扩展到 prefill-decode disaggregation、多模型共置、甚至 training + serving 混合部署。

2. **Coroutine-based backward 可挂起执行**：将 PyTorch Autograd 的 backward pass 改造为 coroutine 是一个有启发的工程实践。这为"可抢占训练"提供了一条轻量级路径——比 checkpoint-restart 开销小得多。可以考虑将此技术用于：
   - 训练任务间的优先级抢占（如紧急 fine-tuning 中断低优先级训练）
   - 在 GPU 集群调度中实现更细粒度的弹性资源分配

3. **值得跟进的方向**：
   - **LLMStation + disaggregated serving**：将 prefill 和 decode 分离到不同 GPU 后，decode GPU 上的空闲计算资源更加集中且可预测，与 PEFT 的共置调度可能更高效。
   - **多 adapter serving + continuous fine-tuning**：论文的 adapter 访问分布实验表明，当 adapter 数量增多且分布均匀时性能急剧下降，如何在大规模 adapter 场景下优化是开放问题。
   - **将 iteration-level scheduling 扩展到 PP 场景**：流水线并行下每个 stage 的空闲 bubble 是天然的 PEFT 执行窗口，可结合 LLMStation 的调度思路进一步优化。

4. **最有价值的切入点**：将 coroutine-based suspendable backward 与现有的 GPU 集群调度器（如 Lucid、AntMan）结合，在集群级别实现 training/serving 混合负载的弹性调度，从"单 GPU 复用"扩展到"集群级复用"。

---

## 八、总结

LLMStation 提出了一种迭代级空间-时间混合复用系统，通过可挂起的 Autograd 引擎（C++ coroutine）、Fusion Engine（合并 compute-bound PEFT forward 和 memory-bound decoding）以及延迟感知的自适应调度器，在单 GPU/多 GPU 上实现了 PEFT 和 LLM 推理的高效共置。系统在保证推理 SLO 的前提下，PEFT 吞吐达到 SOTA 基线的 1.38×–14.77×。主要局限在于仅支持 TP 不支持 PP、多 GPU 下 coroutine overhead 显著、以及 SLO 定义与实际 TPOT 存在差异。适用于 on-premise 部署中推理负载波动较大、需要持续微调 adapter 的场景。
