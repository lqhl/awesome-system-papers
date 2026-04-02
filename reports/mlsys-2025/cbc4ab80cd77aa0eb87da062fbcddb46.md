# Seesaw: High-Throughput LLM Inference via Model Re-Sharding

**作者**：Qidong Su (University of Toronto / Vector Institute / CentML), Wei Hao (Stanford University / CentML), Xin Li (CentML), Muralidhar Andoorveedu (CentML), Chenhao Jiang (University of Toronto / Vector Institute), Zhanda Zhu (University of Toronto / Vector Institute / CentML), Kevin Song (University of Toronto / Vector Institute), Christina Giannoula (University of Toronto / Vector Institute / CentML), Gennady Pekhimenko (University of Toronto / Vector Institute / CentML)
**会议**：MLSys 2025
**链接**：Proceedings of the 8th MLSys Conference, Santa Clara, CA, USA, 2025
**源文件**：[cbc4ab80cd77aa0eb87da062fbcddb46.pdf](../../papers/mlsys-2025/cbc4ab80cd77aa0eb87da062fbcddb46.pdf)

---

## 一、背景

随着 LLM 规模不断增长，单个 GPU 的显存已无法容纳完整模型，分布式并行推理成为必需。现有的并行策略主要包括 tensor parallelism (TP) 和 pipeline parallelism (PP)，它们在通信开销、显存效率和计算效率之间存在不同的 trade-off。

除了交互式聊天场景，LLM 在离线 throughput-oriented 任务（如信息抽取、数据库查询、知识图谱处理）中的应用日益广泛。这类任务不关注延迟，而追求最大化吞吐量。MLPerf 也专门为此开发了基准测试。

LLM 推理分为 prefill 和 decode 两个阶段，二者的计算特性截然不同：prefill 同时处理大量 input token，compute/communication bound；decode 每步仅生成一个 token，weight loading bound。这种差异使得单一静态并行策略无法同时优化两个阶段。

---

## 二、要解决的问题

1. **单一并行策略次优**：TP 在 prefill 阶段因频繁 all-reduce 通信开销严重（尤其在 PCIe 等低带宽互连环境下），而 PP 在 decode 阶段因 micro-batching 导致权重重复加载开销大。没有一种静态配置能同时优化两个阶段。

2. **Disaggregated prefill-decode 方案受限**：DistServe 等方案将 prefill 和 decode 分配到不同 GPU 实例上，但在资源受限环境下搜索空间极小（如 70B 模型在 8 张 40GiB GPU 上只有一种分配方式），容易造成严重的阶段间吞吐量不匹配（prefill 吞吐量可达 decode 的 6 倍以上），且模型权重重复占用显存。

3. **动态切换的 transition overhead**：如果要在 prefill 和 decode 之间切换不同并行策略，需要 re-shard 模型权重和 KV cache。结合 continuous batching 的 prefill-prioritizing 调度，频繁切换会引入巨大开销；而 decode-prioritizing 调度虽减少切换，但 batch size 小导致 decode 吞吐量低。

---

## 三、洞察与设计

**关键洞察**：Prefill 阶段处理大量 token，通信开销（all-reduce）占比大，因此 PP（低通信开销）更优；Decode 阶段每步仅处理一个 token，权重加载开销占比大，因此 TP（权重分片并行加载）更优。两个阶段对并行策略的偏好存在根本性差异，值得为每个阶段分别选择最优并行策略并动态切换。

基于这一洞察，Seesaw 提出 **动态模型 re-sharding** 技术：

- **Model re-sharding**：在 prefill 和 decode 阶段之间动态重新分配模型权重和 KV cache，为每个阶段使用各自最优的并行配置（如 prefill 用 PP，decode 用 TP）。权重通过从 CPU 内存重新加载所需的 shard 完成 re-shard，KV cache 通过 OS 共享内存在 GPU 间重新分配。

- **Tiered KV cache buffering**：利用 CPU 内存作为 KV cache 的辅助存储。Prefill 阶段生成的 KV cache 先 offload 到 CPU，释放 GPU 显存以连续处理更多 prefill 请求；decode 阶段再从 CPU swap-in KV cache，保持 GPU KV cache 满载以最大化 decode batch size。

- **Transition-minimizing scheduling**：控制阶段切换仅在 CPU KV cache 存满或清空时发生。Prefill 持续运行直到 CPU KV 存储填满后才触发 re-shard 切换到 decode；decode 持续运行直到 CPU KV cache 全部传入 GPU 后才切回 prefill。这大幅减少了切换频率，同时保持 decode 阶段的最大 batch size。

---

## 四、实现细节

**架构**：单 scheduler + 多 worker 设计。Scheduler 管理所有生成请求，组织 batch 并通过共享队列发送指令给 worker。每个 worker 控制一个 GPU。

**异步流水线**：
- **Swap-out 与计算重叠**：Prefill 阶段生成的 KV cache 不会立即被使用，因此 swap-out 到 CPU 可以与后续 prefill 计算重叠。由于共享内存无法 pin，实际分两步：GPU → pinned memory（与计算重叠）→ shared memory（CPU 端操作，与 GPU kernel 并发）。
- **异步 swap-in**：每个 worker 有独立的 prefetcher 后台线程，由 scheduler 控制。当 GPU KV store 有空闲 slot 时创建 prefetch 任务，完成后通过共享队列通知 scheduler 安排 decode。

**KV cache 数据布局**：采用 HND 布局 `(num_heads, seq_len, head_dim)` 而非 NHD，因为 TP 沿 head 维度分片，HND 布局使得分片后的内存访问更连续，提高带宽效率。

**KV cache re-sharding**：通过 OS 共享内存实现。Swap-out 时各 GPU 按 prefill 并行配置 $c_p$ 将各自的 KV shard 写入共享 CPU 存储；swap-in 时各 GPU 按 decode 并行配置 $c_d$ 从共享存储取回所需的 KV shard。

**模型实现**：基于 vLLM 的模型实现构建，使用 float16 数据类型。

---

## 五、实验结果

**硬件配置**：

| GPU | 显存 | 显存带宽 | FLOPS | NVLink |
|-----|------|----------|-------|--------|
| A10 | 24 GiB | 600 GiB/s | 125 TFLOPS | 无 |
| L4 | 24 GiB | 300 GiB/s | 121 TFLOPS | 无 |
| A100 | 40 GiB | 1,555 GiB/s | 312 TFLOPS | 有 |

PCIe 4.0 x8 互连，16 GiB/s 带宽。每 GPU 分配 80 GiB CPU 内存。

**模型**：LLaMA3-15B、CodeLLaMA-34B、LLaMA2-70B（均使用 GQA）。

**数据集**：ShareGPT（对话，输入输出长度相当）、arxiv-summarization（摘要，输入远长于输出）。

**主要结果**：

| 平台 | 平均加速比 | 最大加速比 |
|------|-----------|-----------|
| A10 (PCIe) | 1.45× | 1.78× |
| L4 (PCIe) | 1.29× | 1.52× |
| 总体平均 | 1.36× | 1.78× |
| A100 PCIe (arxiv-sum) | 1.46× | — |
| A100 PCIe (ShareGPT) | 1.30× | — |
| A100 NVLink (ShareGPT, 70B) | 1.13× | — |

- A10 加速更显著，因为 A10 单卡性能较强但 PCIe 互连带宽与 L4 相同，通信开销占比更高。
- Seesaw 将 A100 PCIe 版本的性能提升至 A100 NVLink 版本的 82%–89%（vLLM 仅约 60%）。
- 在 NVLink 高带宽环境下（A100 SXM），TP 的 all-reduce 开销大幅降低，但 Seesaw 仍能提供 13% 的加速。

**敏感性分析**：
- Seesaw 在所有 input/output 长度比例下均优于任何单一固定并行策略。
- 在 0.1×–50× PCIe 带宽范围内，Seesaw 吞吐量均优于固定策略，主要适用于资源受限、互连带宽较低的部署场景。

---

## 六、批判性分析

1. **基线选择较为有限**：仅与 vLLM 0.5.4 对比，排除 SGLang 和 DeepSpeed-FastGen（不支持 PP）以及 TensorRT-LLM（理由是调度策略类似 vLLM），但这些系统各有不同的优化（如 SGLang 的 RadixAttention），排除它们使得结论的普适性打折。

2. **硬件环境偏向性**：实验主要在 PCIe 互连的中低端 GPU（A10、L4）上展示显著加速，而在 NVLink A100 上仅 13%。论文坦承 Seesaw 主要适用于 "resource-constrained deployments with relatively slower interconnections"，但当前生产环境大量使用 NVLink/NVSwitch 互连的高端 GPU（H100/H200/B200），Seesaw 在这些环境下的价值存疑。

3. **CPU 内存假设较宽松**：每 GPU 分配 80 GiB CPU 内存用于 KV cache buffering，这在云实例上可能与其他服务竞争内存资源，论文未讨论 CPU 内存不足时的性能退化。

4. **未充分评估 re-sharding 开销**：虽然提出了异步流水线来掩盖开销，但缺乏对 re-sharding 自身耗时的独立测量和分析（如权重重新加载时间、KV cache 传输时间占总推理时间的比例）。

5. **模型规模和架构有限**：仅测试 15B/34B/70B 三个模型，且均为 GQA 架构。未测试 MoE 模型（如 Mixtral），也未测试更大规模模型（如 405B），这些场景下的并行策略选择可能有很不同的 trade-off。

6. **离线场景限定性**：Seesaw 明确限于 throughput-oriented offline inference，不考虑延迟。但实际许多"离线"任务也有 SLA 时间约束，transition-minimizing scheduling 会导致部分请求的 time-to-first-token 显著增加，论文未讨论这一影响。

---

## 七、AI Infra / MLSys 视角

1. **阶段感知的并行策略选择**：Seesaw 提出的核心思想——prefill 和 decode 阶段应使用不同并行策略——是对 LLM 推理系统设计的重要洞察。即使不做完整的 re-sharding，这一分析框架也可指导推理系统在 chunked prefill 粒度上做更精细的并行配置选择。

2. **与 Disaggregated Serving 的互补**：Seesaw 的时间维度切换（temporal disaggregation）与 DistServe 的空间维度切换（spatial disaggregation）是正交的。在大规模集群中，可以探索两者的结合——同一组 GPU 内做 re-sharding，不同组 GPU 间做 disaggregation——这是一个有价值的研究方向。

3. **Tiered KV cache buffering 思路可推广**：利用 CPU 内存做 KV cache 的分层缓存管理，配合异步 swap，这一思路可以推广到 long-context 推理、speculative decoding 等场景中，用于缓解 KV cache 显存压力。

4. **新硬件互连下的研究机会**：随着 CXL、NVLink-C2C 等新互连技术的发展，CPU-GPU 数据移动的带宽和延迟特性将显著改变，re-sharding 和 tiered buffering 的 cost-benefit 分析需要重新评估。这是一个值得跟进的研究点。

5. **可操作的研究切入点**：
   - 将 re-sharding 与 speculative decoding 结合：draft model 和 verify model 可能偏好不同的并行策略
   - 探索 MoE 模型下的动态 re-sharding：expert parallelism 引入新的维度
   - 在 multi-tenant 场景下，不同请求的 prefill/decode 比例不同，可以探索更细粒度的请求感知 re-sharding 策略

---

## 八、总结

Seesaw 提出了动态模型 re-sharding 技术，通过在 LLM 推理的 prefill 和 decode 阶段之间动态切换并行策略（prefill 用 PP、decode 用 TP），配合 tiered KV cache buffering 和 transition-minimizing scheduling 来减轻切换开销，在 PCIe 互连的中低端 GPU 集群上实现了相对 vLLM 平均 1.36×、最高 1.78× 的吞吐提升。其主要适用于资源受限、低带宽互连的离线推理场景，在高端 NVLink 互连环境下收益有限。
