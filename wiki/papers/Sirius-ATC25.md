---
type: paper
name: Sirius
full_title: Colocating ML Inference and Training with Fast GPU Memory Handover
authors: [Jiali Wang, Yankui Wang, Mingcong Han, Rong Chen]
venue: ATC
year: 2025
tags: [gpu-sharing, ml-inference, ml-training, colocation, memory-management, kv-cache, area/ai-infra]
source_pdf: "[[atc2025-wang-jiali.pdf]]"
source_md: "[[atc2025-wang-jiali]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Sirius：通过快速 GPU 内存切换并置 ML 推理和训练（ATC 2025）

> **原题**：Colocating ML Inference and Training with Fast GPU Memory Handover

> **一句话总结**：SIRIUS 的核心判断是 inference 显存需求波动大、training 中间态显存可弹性收缩；它用 GC/MU 分阶段丢弃 batch（平均 5 ms 调整）+ VMM 共享池显式回收 + SLO-aware watermark 粗粒度重分配，在单卡 V100 上让 inference+training 空间共址时 SLO 合规率平均 +57%（最高 +97%）、训练吞吐 2.2×（最高 13.7×），并达到 inference-alone 的 95.3–98% SLO 合规。

## 问题与动机

MLaaS 推理为守住毫秒级 latency SLO（常见 100 ms 量级），通常超额预留 GPU；但 burst 可达平均负载 50×，导致推理 GPU 利用率常低于 15%。工业界（GKE mixed workloads、Tencent qGPU）和研究（PipeSwitch、Lyra 等）都在尝试把高优先级 inference 与低优先级 training 共址，以提高利用率。

现有共址路线各有硬伤。**Temporal sharing**（如 [[PipeSwitch]]、Lyra）要在 inference 与 training 间切换整卡显存，模型重载与上下文切换可达数秒，既难保 SLO，也无法在 inference 服务期间利用空闲算力。**Static partition** 把显存固定切分，无法跟随 inference 从 1.8 GB 到 10.3 GB 的动态需求；低配 inference 会 cold start，高配 training 又吃不饱。**Dynamic swapping**（Unified Memory + MPS）把溢出页走 PCIe，论文报告 inference SLO 合规可掉 93%，LIGHT 负载下 UM+MPS 仅 7% SLO 合规。

作者 claim 的边界是：在同一 GPU 上做 **spatial sharing**——inference 优先占满所需显存与 SM，training 吃剩余资源；关键瓶颈不是算力隔离（SM mask 已能在 1 ms 内切分），而是 **training→inference 的显存交接太慢**。朴素交接要等当前 training batch 结束（~250 ms）、再经 framework cache 与 `cudaMalloc` 分配（~34 ms）、最后初始化 inference 内存，整体远超 SLO 预算。

## 关键观察 / 隐含假设

- **观察 1：inference 显存“预留”远大于“实需”，且峰值随模型数与 [[KV-Cache]] 波动。** MAF trace 上 64 模型 serving 时，总部署显存 11.9 GB，实际服务只需平均 4.4 GB；需求在 1.8–10.3 GB 间变化。DistilGPT2 的 model load（26.6 ms）是 execution（5.0 ms）的 5.3×，cold start 会直接进 critical path。
  - **依赖假设**：多模型/多租户 serving、模型不在 GPU 常驻、或 LLM KV 动态增长是主要场景；负载波动足够大，以至于静态 partition 必然 either 浪费 or 违约。
  - **可能失效场景**：单一大模型常驻、prefix 极高复用、或 disaggregated serving 把 KV 放到远端时，显存弹性收益下降；模型极小、load 可忽略时，handover 优化边际变小。

- 观察 2：training 显存大头是 batch 中间态，可用 batch size + gradient accumulation 保持 effective batch 不变。 Swin-T（batch 80）中间态占 91%；减 batch size 可近似线性缩显存。但 PyTorch caching allocator 会让“逻辑减 batch”后物理显存仍被占住，training 释放的内存对 inference 不可见。
  - **依赖假设**：训练任务支持动态 batch/gradient accumulation，且丢弃偶发 batch 不破坏收敛；DP 是主要并行形态。
  - **可能失效场景**：pipeline/tensor parallelism、ZeRO sharding、或 optimizer state 已顶满显存时，可调空间变小；丢弃 batch 对收敛敏感的任务（小数据集、高学习率）可能不稳。

- **观察 3：training batch 可拆成 GC（gradient compute，>95% 时间、参数不变）与 MU（model update，<10 ms、需原子）。** ResNet-152 上 GC 323.7 ms vs MU 9.6 ms。因此在 GC 阶段丢弃当前 batch 是“安全且快”的显存回收点；若在 MU，短等即可。
  - **依赖假设**：绝大多数调整请求落在 GC；software queue + 少量 in-flight kernel 等待可在毫秒级完成；多 GPU 下可通过 NCCL abort flag 避免 AllReduce deadlock。
  - **可能失效场景**：极短 batch、自定义 op 打破 GC/MU 边界、或 NCCL 状态复位失败时，调整延迟会回到百毫秒级；论文未覆盖 PP/TP 下的 stage 重切分。

- **假设 1：inference SLO 比 training 吞吐更硬，training 可被抢占、丢 batch、降 batch。**
  - **证据强度**：强。全文设计、SM 分配、watermark 都服务 inference-first；实验 SLO 设为 standalone 执行时间 4×，且对比 Infer-Only 可达 95–98% 合规。

- **假设 2：共享 VMM 池 + 显式所有权管理可避免 data pollution，且比 framework cache + `cudaMalloc` 更快。**
  - **证据强度**：中。单卡实验显示 allocation 0.8 ms（含 zero-fill），比 naive 快 89.2×；但 pollution 分析基于训练 op 异步 alloc/free 模式，未在多 stream、多租户、LLM 复杂 allocator 下压力测试。

## 核心方法

SIRIUS 在每张 GPU 上跑 inference engine（自研 C++ server，DNN 用 TVM、LLM 用 [[vLLM]]）与 PyTorch training plugin，通过 `REQUIRE(M)` / `RELEASE(M)` 做动态显存 handover；算力侧用 SM mask 让 inference 请求期间抢占 training 的 SM，结束后归还。

**Instant Memory Adjustment（回应观察 2/3）**：training 不再直接把 op launch 到 GPU，而是先入 host 侧 software queue，仅少量 kernel in-flight。Host 作为 oracle 识别 GC/MU；调整时停止入队、等 in-flight 完成、丢弃队列剩余 op，并遍历计算图释放中间 tensor。多 GPU DP 下各卡同步发起调整；若 AllReduce 不一致，设置 NCCL abort flag 退出 collective 但保留 communicator，下一轮前 reset counter。为缓解跨卡显存不平衡，按在线 profiling 动态 **batch distributing**，把更多 sample 分给更快 GPU，但保证要么所有卡 batch>0，要么全体暂停。

**Safe Memory Handover（回应观察 2 + 假设 2）**：用 CUDA VMM 建 inference/training 共享池；inference 直接切 contiguous 区域，training 把非连续 page map 成连续区。训练 framework 的“launch 后即 free 到 cache”会让 inference 误以为内存可用——SIRIUS 维护 **ownership**，只有 adjustment 完成、无 in-flight training op 时才把页交给 inference；否则页仍属 training。交接时 zero-fill 防隐私泄漏；unmap 延迟到下次 training alloc，把 unmap 移出 critical path。

**SLO-aware Reallocation（回应观察 1）**：idle model 与闲置 [[KV-Cache]] 不立刻还给 training。`InferRelease` 用 liveness time `T_idle` 判断模型是否够冷；释放先进入 reserved pool，直到 `M_rsv ≥ 2W` 才 coarse-grained 释放到 watermark `W`，减少 training 抖动。`InferRequire` 优先吃 reserved；不够则 `AdjustTrainingTask(adjust_sz = need + W)` 一次多要一点；training 已到 batch=0 则 fallback 到 host swap + pipeline load。`T_idle` 与 `W` 由 **M/G/1 排队模型**（同质模型、Poisson 到达、cold start 比例 α≈1−W/Σmodel_sz）搜索，目标平均 SLO 合规 90%。

## 设计取舍

- **丢 batch 换毫秒级显存回收**：平均只浪费 1.4% training 计算，但逻辑上牺牲了一次梯度样本；CIFAR-100 上 Swin-T 收敛 epoch 210.6 vs 206.2，差异小，却未覆盖 LLM 长训、小 batch 敏感任务。
- **inference-first 换 training 峰值吞吐**：training 永远吃“剩余显存+剩余 SM”；高负载 inference 可把 training batch 打到 0 并触发 swap，此时 training 吞吐急剧下降——这是设计意图，不是意外。
- **共享内存池换实现复杂度**：绕过 PyTorch allocator 与 `cudaMalloc`，但要自己管 ownership、碎片、VMM map/unmap；与现有 training stack 深度耦合（~5000 行 Python/C++ plugin + ~6000 行公共内存组件）。
- **粗粒度 watermark 换稳定**：一次调整多要 W 显存，降低 adjustment 频率（单卡平均间隔 10.3 s），但低负载时 training 可能长期吃不饱。
- **边界条件**：单卡、DP、中小模型（V100 16 GB）上设计最优雅；多节点 PP/TP、80 GB 单模型顶满、或 NVLink/PCIe 异构拓扑下，论文只讨论方向、未给完整实现。

## 实验与结果

- **平台**：80 核 Xeon、503 GB DRAM、4× V100 16 GB（NVLink）；LLM 实验另用 A100 80 GB。Ubuntu 20.04、CUDA 11.6、PyTorch 2.1.2。
- **Workload**：LIGHT/HEAVY/BURST/SKEWED 四类合成 trace + MAF 真实 trace；6 个 TVM DNN 模型复制到 56 实例；训练 Swin-T。LLM：Llama2-13B inference + Qwen2-0.5B training，BurstGPT trace，10 req/s。
- **主结果（单 GPU）**：相对 TaskSwitch、SP-50、SP-75、UM+MPS，SLO 合规平均 +57.0%（最高 +97.0%），训练吞吐平均 2.2×（最高 13.7×）。相对 Infer-Only 平均 95.3% SLO 合规（最高 98%）。TaskSwitch 在 MAF 上训练吞吐比 SIRIUS 低 13.7×；UM+MPS LIGHT 下仅 7% SLO 合规。
- **Handover 分解**：training adjustment 平均 <5 ms（P99 11.4 ms），比等 batch 结束快 121×；memory alloc 0.8 ms，快 89.2×；pipeline load 使模型加载等待降 3.7×。
- **多 GPU（4 卡 LIGHT）**：P99 latency 平均改善 558.4×，SLO 合规 +43.0%，训练吞吐 6.1×；达 Infer-Only 89.0% SLO 合规。
- **Ablation**：`T_idle` 增大降 cold start 但占显存、training 吞吐先升后降；`W` 增大降 load 与 discard 浪费，但过大 watermark 会压缩 training 空间。
- **LLM（A100）**：相对 SP-50，TTFT/TBT SLO 合规 +40%/+7%；相对 SP-75 训练吞吐 1.5×；相对 Infer-Only 为 89%/91%。

## 批判性分析

### 论证链条

主链条清晰：**inference 显存弹性需求** + **training 中间态可缩** → 必须毫秒级 handover → GC/MU 丢弃 + VMM 池 + SLO-aware 粗调 → spatial colocation 同时改善 SLO 与 training 吞吐。Figure 3(d) 与 Figure 13 把“慢交接”问题钉死在 measurement 上，ablation 也支持 watermark/liveness 的必要性。

薄弱处在于 **最强 baseline 是否公平**。TaskSwitch 基于 SIRIUS 改写而非原版 PipeSwitch；SP 基线用 Triton，论文承认 cold start 可达 2 s，可能放大静态分区劣势。Infer-Only 也基于 SIRIUS engine，缺少与独立 [[vLLM]]/Triton-only 的对照。论证能证明“SIRIUS 优于这几类 sharing 策略”，但未必证明“每个组件都不可替代”。

### 假设压力测试

**负载形态**：M/G/1 模型假设模型同质、请求独立；SKEWED（Zipf）只部分缓解。若业务是少量超大 LLM + 长尾小模型，或 KV 主导且 TTFT/TBT SLO 分离权重不同，offline 搜出的 `T_idle=5s, W=1GB` 可能失效——Figure 14 已显示参数敏感。

**训练形态**：实验主要是 Swin-T DP；LLM 训练只到 Qwen2-0.5B。PP/TP、FSDP、Megatron 类训练一旦启用，丢弃 batch + NCCL abort 的语义更复杂，论文 §7 明确留作 future work。把结论外推到“所有 cloud training job 可 colocate”过猛。

**硬件规模**：4×V100 16 GB 与生产多租户集群差距大。显存顶满时 fallback swap 路径的行为（Figure 16）说明系统仍有 PCIe 瓶颈尾巴；A100 80 GB 只测单模型 LLM，未测多租户 KV 争抢。

### 实验可信度

可信点：handover microbenchmark（5 ms vs 250 ms）与 component ablation 较扎实；MAF + BurstGPT 引入真实 trace；收敛实验至少证明“动态 batch 不明显伤 Swin-T on CIFAR-100”。

不足：缺少与 Orion、AntMan、Salus、MuxFlow 等 **同期 GPU sharing** 工作的直接对比；tail latency 多报 P99 与 SLO 合规率，未系统报告 multi-tenant fairness；故障恢复、NCCL abort 后长期稳定性、内存碎片随运行时间增长等 **论文未讨论**。

### 系统性缺陷

- **运维复杂度**：自研 inference engine + training hook + VMM 池，对 PyTorch/CUDA 版本敏感；升级框架可能破坏 ownership 与 queue 语义。
- **可观测性**：论文未描述 adjustment 事件、discard rate、reserved pool 占用、fallback swap 比例的监控与告警。
- **隔离与安全**：zero-fill 处理隐私，但未讨论多租户恶意模型、side channel、或 inference/training 同进程故障爆炸半径。
- **尾延迟**：inference-first + coarse adjust 在 burst 边界可能连续触发 REQUIRE；虽然 watermark 缓解 thrashing，极端 burst（50×）下与 Infer-Only 的 2–5% SLO gap 是否可接受，生产需按业务重测。

## 局限与后续工作

- **局限 1**：仅完整支持 **data parallelism**；pipeline/tensor parallelism 需 reshard/reshape，论文未实现。
- **局限 2**：多节点 inference/training 的 handover 需全卡同步通知，§7 只有方向性描述，无性能数据。
- **局限 3**：training batch 打到 0 后走 host model swap，性能回到 Figure 3(c) 类 PCIe 受限路径；极高模型数场景仍是硬顶。
- **Future work 1**：在 PP/TP 训练上测量“discard batch + NCCL abort + stage 重切分”的端到端延迟与收敛影响，明确哪些并行策略可与 inference colocation 共存。
- **Future work 2**：用生产级 trace 做 **online** `T_idle`/`W` 自适应，并报告与 offline M/G/1 搜参的漂移误差对 P99 latency 的影响。
- **Future work 3**：与 [[Disaggregation|PD-disaggregation]]、独立 KV 层（如 Mooncake/LMCache 路线）组合时，重新测量 GPU 显存 handover 是否仍是瓶颈，还是网络/KV 转移主导。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Pipeline-Parallelism]]、[[Chunked-Prefill]]
- **同类系统**：[[PipeSwitch]]、[[vLLM]]、NVIDIA Triton、NVIDIA MPS、Lyra、AntMan、Orion、Zico、Salus
- **同会议**：[[ATC-2025]]
- **对比**：spatial sharing（SIRIUS）vs temporal sharing（PipeSwitch）vs static partition vs Unified Memory swapping
