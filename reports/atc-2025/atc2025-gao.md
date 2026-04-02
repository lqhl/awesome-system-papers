# WEAVER: Efficient Multi-LLM Serving with Attention Offloading

**作者**：Shiwei Gao, Qing Wang, Shaoxun Zeng, Youyou Lu, Jiwu Shu（清华大学）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/gao
**源文件**：[atc2025-gao.pdf](../../papers/atc-2025/atc2025-gao.pdf)

---

## 一、背景

LLM 服务平台（如 HuggingFace、Together.ai、OpenRouter）通常同时托管数十到数百个不同模型，形成 multi-LLM serving 范式。这种场景下，工作负载呈现高度倾斜（skewed）特征：少量热门模型（如 Llama-3、GPT-4）消耗绝大部分请求流量（top 5% 模型消耗 74.8% 的 token），而大量冷门模型虽然请求稀少，但仍需常驻 GPU 以保证低延迟响应。

现有系统在处理这种 hot/cold 混合负载时面临效率困境：专用实例方式导致冷模型 GPU 内存严重浪费（利用率仅 43%），而基于模型并行的复用方式（如 tensor parallelism）引入显著通信开销（高达 26%）。

---

## 二、要解决的问题

1. **冷模型 GPU 内存利用率低**：专用部署下，冷模型的 GPU 内存大量闲置，无法被热模型利用
2. **模型并行复用开销大**：MuxServe 等方案使用 tensor parallelism 共享 GPU，即使在 NVLink 高带宽互联下仍有 17-27% 的吞吐下降
3. **热模型吞吐受限于单 GPU 内存**：热模型的 batch size 受限于单 GPU 的 KV cache 容量，无法充分利用系统中的空闲内存资源

---

## 三、洞察与设计

**关键洞察**：LLM 中的 attention 操作是非参数化的（不依赖模型权重），只需要传输最新 token 的 QKV tensor 即可远程执行，因此可以以极低的通信开销将热模型的部分 attention 计算卸载到正在运行冷模型的 GPU 上，同时利用其空闲内存存储 KV cache。

基于这一洞察，论文提出 **workload weaving** 机制：将热模型的部分 attention 操作 offload 到冷模型实例上执行。Sender（热模型 GPU）发送最新 token 的 QKV tensor 给 receiver（冷模型 GPU），receiver 执行 attention 并返回结果。这样热模型可以借用冷模型的空闲 GPU 内存来扩大 batch size，从而提升吞吐。

然而，workload weaving 面临两个核心挑战：

1. **Pre-issued kernels 阻塞**：现有 LLM serving 系统会预发射数百个 kernel 到 GPU 硬件队列（如 Llama-3-8B 在 vLLM 中每个 iteration 387 个 kernel），offloaded attention 必须等待所有排队 kernel 执行完毕
2. **Long-running kernels 阻塞**：即使能优先执行，GPU 上正在运行的大 kernel（如 LMHead 最长 961µs）也会造成阻塞

WEAVER 通过两项关键技术解决上述问题：

- **GPU-driven dynamic control flow**：将 offload 控制逻辑委托给 GPU，利用跨 GPU 共享内存进行任务分发。Receiver GPU 持续 poll 新任务并立即执行，绕过 GPU 硬件队列中的预发射 kernel
- **Operator splitting**：基于排队论分析，用优先级算法将大 kernel 拆分为小 kernel，使 offloaded attention 最多等待一个小 kernel 完成

---

## 四、实现细节

**GPU-driven dynamic control flow**：
- Sender 通过 CUDA IPC 的 one-sided write 将 QKV tensor 写入共享内存，并原子递增 task counter
- Receiver GPU 运行 polling kernel，检测 counter 变化后立即执行 attention（使用 FlashAttention），写回结果并递增 completion counter
- Polling kernel 被插入到每个预发射 kernel 之后，确保 offloaded attention 只被当前正在执行的 kernel 阻塞

**Operator splitting**：
- 将 receiver 建模为 polling system，分析 offloaded attention 的期望等待时间
- 大 operator 对等待时间的贡献是二次方关系：$W_i = \frac{\max\{T_i - (K-N), 0\}^2}{2T_i}$
- 优先级算法（Algorithm 1）迭代拆分最大 operator，直到等待时间低于阈值（sender 平均 iteration 时间的 5%）
- 参数化 operator 按参数维度拆分，非参数化 operator 按序列维度拆分

**系统实现**：
- 基于 vLLM v0.6.0 实现
- 使用 CUDA IPC 实现跨 GPU 共享内存通信
- 固定 offload ratio（默认 45%），KV cache 统一分配器支持不同模型的不同层数和 KV head 数

---

## 五、实验结果

| 配置 | 平台 | 对比方法 | 热模型最大吞吐提升 | 热模型 TPOT 降低 | 冷模型 TPOT 开销 |
|------|------|---------|-------------------|-----------------|----------------|
| Azure-Conv | A100 (NVLink) | Dedicated | 最高 60% | 最高 39% | 3-5ms |
| Azure-Conv | A100 (NVLink) | MuxServe | 最高 22% | 最高 15% | 略高于 MuxServe |
| BurstGPT | L40S (PCIe) | MuxServe | 最高 77% | — | 3-5ms |
| 长输出(1024) | A100 | MuxServe | 最高 42% | — | 最高 8ms |

**关键数据点**：
- 内存利用率：Dedicated 下热模型 KV cache 利用率 88.9%，WEAVER 降至 46.9%（通过利用冷 GPU 的 36.7%）
- Batch size：Dedicated 最大 batch 118 → WEAVER 最大 batch 231（翻倍）
- Ablation：GPU-driven control flow 贡献 4.83× TPOT 降低，operator splitting 额外降低 9.5%
- 冷模型 P99 TPOT 仅增加 1-2ms

---

## 六、批判性分析

1. **实验规模受限**：所有实验仅使用 4 GPU（2 hot + 2 cold），且只测试单一模型（Llama-3-8B hot + Llama-3-8B cold）。实际 MaaS 平台有数百模型和数千 GPU，论文完全没有讨论 cluster-level 的调度和扩展性问题，仅以"leave for future work"带过

2. **固定 offload ratio 是明显短板**：45% 的固定 offload ratio 在实际场景中过于死板——冷模型突发流量时怎么办？论文在 §4.3 承认需要动态调整但未实现，这严重限制了系统的实用性

3. **模型同构假设**：所有实验中 hot 和 cold 模型都是 Llama-3-8B，回避了异构模型场景下的 KV cache 管理复杂性（不同模型的层数、KV head 数不同）

4. **Prefill 阶段被排除在优化范围外**：论文明确表示只优化 decode 阶段的 TPOT，而 prefill 阶段同样消耗大量资源，特别是 input-heavy 的 Azure-Conv 场景

5. **通信开销在低负载下反而有害**：Figure 4 显示在低 QPS（<5）时 WEAVER 的 TPOT 高于 Dedicated，说明 offloading 机制有固定开销，在冷启动或低负载场景下不适用

6. **Operator splitting 的 profiling 成本未讨论**：K 和 N 需要周期性 profiling 更新，但论文没有说明 profiling 频率、开销和不准确时的影响

---

## 七、AI Infra / MLSys 视角

1. **Attention offloading 作为通用资源调度原语**：WEAVER 验证了利用 LLM 结构特性（attention 非参数化）进行跨 GPU 资源共享的可行性。这个思路可以推广到 prefill-decode 分离（DistServe）之外的更多场景——例如在 MoE 模型中，expert 计算也可以类似地跨 GPU offload

2. **GPU-driven control flow 的启发性**：绕过 CPU 控制流、让 GPU 直接 poll 任务的设计，对任何需要低延迟跨 GPU 协调的系统都有参考价值（如 disaggregated serving 中的 KV cache transfer、pipeline parallelism 中的 micro-batch 调度）

3. **值得跟进的方向**：
   - **动态 offload ratio + cluster scheduler**：结合请求率预测和内存利用率监控，实现自适应的 attention offload 调度
   - **异构模型 workload weaving**：扩展到不同大小的模型之间（如 70B hot + 8B cold），需要解决 KV cache 维度不匹配的问题
   - **Prefill 阶段的 weaving**：将 workload weaving 扩展到 prefill attention，可能需要不同的 splitting 策略
   - **与 KV cache compression 的结合**：offloaded 的 KV cache 可以在冷模型 GPU 上使用量化/稀疏化进一步压缩，增加可服务的 batch size

4. **最佳切入点**：将 WEAVER 的 attention offloading 机制集成到 disaggregated serving 框架（如 DistServe/Mooncake）中，在 decode instance 之间实现 workload weaving，这比论文中的 hot/cold 场景更有实际部署价值

---

## 八、总结

WEAVER 提出了 workload weaving 机制，利用 LLM attention 非参数化的结构特性，将热模型的部分 attention 计算 offload 到冷模型 GPU 上，通过 GPU-driven dynamic control flow 和 operator splitting 两项技术解决了 offloading 引起的阻塞问题。在 A100/L40S 平台上，WEAVER 将热模型最大吞吐提升最高 77%，冷模型仅增加 3-5ms TPOT。主要局限在于实验规模小（4 GPU、同构模型）、固定 offload ratio、以及缺乏 cluster-level 调度，实际部署需要进一步解决动态调整和异构模型支持的问题。
