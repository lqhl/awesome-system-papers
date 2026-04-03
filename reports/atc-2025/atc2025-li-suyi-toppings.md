# TOPPINGS: CPU-Assisted, Rank-Aware Adapter Serving for LLM Inference

**作者**：Suyi Li, Hanfeng Lu, Tianyuan Wu (HKUST); Minchen Yu (CUHK-Shenzhen); Qizhen Weng (TeleAI, China Telecom); Xusheng Chen, Yizhou Shan (Huawei Cloud); Binhang Yuan, Wei Wang (HKUST)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/li-suyi-toppings
**源文件**：[[atc2025-li-suyi-toppings.pdf]]

---

## 一、背景

LoRA（Low-Rank Adaptation）已成为 LLM 领域最流行的参数高效微调方法，通过在 Transformer 各层添加低秩分解矩阵 A、B 来适配下游任务，无需修改基座模型参数。在多租户云环境中，一个基座 LLM 需要同时服务数百甚至上千个不同的 LoRA adapter，这要求系统高效地进行 LLM multiplexing——共享一个基座模型，动态加载不同 adapter 进行推理。

现有系统（如 S-LoRA、dLoRA、Punica）虽然支持 LLM multiplexing 和 continuous batching，但在大规模多租户 LoRA 服务中仍面临显著的性能瓶颈。同时，LLM 推理集群中 GPU 利用率高达 99%，而 CPU 利用率通常低于 10%，存在大量闲置计算资源。

---

## 二、要解决的问题

**问题一：累积的 decoding-interruption 开销。** 在 continuous batching 模式下，每当新请求到达时，系统需要中断正在进行的 decoding，从 host memory 加载对应的 LoRA adapter 到 GPU，再执行 prefill。这个加载延迟（几毫秒到几十毫秒）不仅影响新请求的 TTFT，还会累积性地延迟所有 inflight 请求的 token 生成——在 RPS=9 的实验中，cumulative decoding-interruption 平均占请求总服务时间的 29%。

**问题二：异构 LoRA rank 的集群级调度。** 不同用户请求的 LoRA adapter rank 各异（如 32、64、128、256），而现有 LoRA 计算 kernel（BGMV 需要 padding 到最大 rank、MBGMV 依赖 rank 之和）对异构 rank 的 batch 性能差异显著——同一 batch size 下，rank 异构性可导致 decoding 延迟增加 28%。现有系统的调度策略对 rank 无感知，无法在集群级别保障 SLO。

---

## 三、洞察与设计

**关键洞察**：LoRA 计算本身极其轻量（约 1 GFLOPs），完全可以在 CPU 上执行，而推理集群中 CPU 大量闲置（75% 节点 CPU 利用率低于 10%）。因此，可以利用 CPU 在 adapter 从 host memory 加载到 GPU 期间提前启动 prefill 的 LoRA 部分计算，将 cold-start 延迟隐藏在计算之后。此外，异构 LoRA batch 的 decoding 性能可以用 rank 组合的简单线性模型精确预测（R²=0.96），为 rank-aware 调度提供基础。

TOPPINGS 围绕这两个洞察设计了两个核心机制：

1. **CPU-Assisted LoRA Serving**：当新请求到达且 adapter 不在 GPU 上时，系统并行执行两个操作——在 CPU 上计算 LoRA adaption（xAB），同时将 adapter 权重加载到 GPU。通过 pipeline loading 将 adapter 分为 M 个 layer group，第一个 group 用 CPU 计算，从第二个 group 开始建立 GPU loading 和 GPU computation 的流水线。adapter 加载完成后切换到 GPU 继续剩余计算和 decoding。

2. **Rank-Aware Scheduling**：基于 kernel profiling 建立性能模型——BGMV 延迟与 `|S| × max_rank` 线性相关，MBGMV 延迟与 `sum(ranks)` 线性相关。调度器收到新请求时，对每个候选 server 计算 cost score（包含对 ongoing 请求的额外延迟和 SLO 违反风险），选择 cost 最小的 server。

---

## 四、实现细节

TOPPINGS 基于 LightLLM 推理框架实现，GPU LoRA 计算适配 Punica 的 BGMV kernel。CPU LoRA 关键优化包括：

- **Sync-free CPU LoRA 调用**：自定义 CUDA operator 将异步 MemCpy 和 CUDA signaling kernel 融合为一个异步操作 [F'₂, F'₃]，通过 host shared memory 中的 semaphore 变量实现信号传递，消除了 native PyTorch 实现中的显式 GPU 同步阻塞，prefill 延迟降低 10%–15%。

- **Shared memory 数据传输**：base LLM 进程与多个 CPU LoRA 进程通过 host DRAM 中的共享内存块传递输入张量 x 和输出 xAB，避免数据拷贝和序列化/反序列化，延迟低于 1ms，远优于 UNIX domain socket。

- **Profiling-guided 多 CPU 并行化**：预先 profiling 单核 CPU 的 LoRA 计算吞吐，每个请求分配 ⌈L/c⌉ 个 CPU 核（L 为 token 数，c 为单核可处理 token 上限），每个核运行独立进程绑定物理核，相比 PyTorch native multi-threading 提升 1.4×。

- **Pipeline loading**：将 N 层 adapter 分为 M 个 layer group，CPU 计算第 1 个 group 的同时 GPU 加载第 2 个 group，后续 GPU 计算第 m 个 group 的同时加载第 m+1 个。可根据运行时延迟动态决定每层在 CPU 还是 GPU 上执行。

调度器用 Python Flask 实现，全局 LoRA registry 用 SQLite，支持 tensor parallelism（多 GPU 分片 LoRA weight B 矩阵）。整套 CPU LoRA 通过 PyBind11 作为 PyTorch Extension 实现。

---

## 五、实验结果

**硬件**：NVIDIA A100 GPU，Intel Platinum 8369B CPU。模型：Llama2-7B（单卡）、Llama2-70B（4 卡 tensor parallel）。

### 单服务器性能（Scaled MAF 生产负载）

| 指标 | 512 adapters, rank=64 | TOPPINGS vs S-LoRA | TOPPINGS vs CACHED |
|------|------|------|------|
| TTFT | — | 加速 1.25× | 仅增加 9% |
| TPT | — | 加速 1.29× | 仅增加 7% |
| E2E | — | 加速 1.28× | 仅增加 7% |

dLoRA 在 512 adapters 时 GPU OOM 无法运行。

### 合成负载（S3: 200 adapters, rank=64, RPS=9）

| 系统 | TTFT 增幅 (vs CACHED) | TPT 增幅 | E2E 增幅 |
|------|------|------|------|
| S-LoRA | +82% | +80% | +81% |
| dLoRA | +29% | +58% | +57% |
| TOPPINGS | +6% | +6% | +7% |

### 70B 模型（S6: rank=64, RPS=3）

TOPPINGS 相比 S-LoRA：TTFT 加速 1.6×，TPT 加速 1.5×，E2E 加速 1.4×。dLoRA 因 GPU OOM 无法运行。

### 集群调度（60 实例大规模仿真，MAF trace, ~340 RPS）

TOPPINGS rank-aware scheduler 相比 dLoRA/Random/FirstFit，TPT 分别加速 22%/23%/57%，SLO 达成率 99%。

### 资源利用率（S3）

| 系统 | GPU 利用率 | CPU 利用率 |
|------|------|------|
| S-LoRA | 46% | 4% |
| dLoRA | 81% | 4% |
| TOPPINGS | 56% | 46% |

---

## 六、批判性分析

1. **基线公平性存疑**：S-LoRA 和 dLoRA 使用各自的 kernel（MBGMV 和 GEMM），而 TOPPINGS 和 CACHED 使用 BGMV kernel，且所有系统均基于 LightLLM 重新实现（S-LoRA 适配，dLoRA "emulate"）。这种非原生实现的基线可能无法完全反映原系统的最优性能，尤其是 dLoRA 的 merge/unmerge 策略在 vLLM 上的原生实现可能有不同表现。

2. **CPU 资源假设过于乐观**：论文假设推理集群 CPU 大量空闲，但实际生产环境中 CPU 常用于数据预处理、tokenization、KV cache 管理、网络处理等任务。随着 prefill disaggregation 和 speculative decoding 等技术普及，CPU 资源竞争可能加剧。论文虽有 reduced CPU 实验（4× 更多 token per core），但测试范围有限。

3. **LoRA rank 规模的时效性**：论文主要评估 rank=32/64/128/256，但当前实践中越来越多使用全量微调或更大规模的 adapter（如 DoRA、rsLoRA、高 rank LoRA），高 rank 下 LoRA 计算的 "轻量" 假设可能不再成立，CPU 可能成为瓶颈。

4. **性能模型的鲁棒性**：线性回归模型 R²=0.96 是在特定硬件/模型/rank 组合下 profiling 得到的，当硬件或模型变更时需要重新 profiling。论文未讨论模型在 mixed precision、quantized adapter（如 QLoRA）等场景下的适用性。

5. **缺少吞吐量评估**：论文关注延迟指标（TTFT、TPT、E2E），但未报告系统吞吐量（tokens/s 或 requests/s）。CPU-assisted 方案是否在高吞吐场景下仍能保持优势需要进一步验证。

6. **Continuous batching 之外的调度范式**：论文假设 continuous batching 是标准范式，但 chunked-prefill（Sarathi-Serve）和 prefill-decoding disaggregation 等新方案改变了 decoding interruption 的模式。在 disaggregated 架构下，prefill 和 decoding 在不同 GPU 上执行，C1 问题（cumulative loading interruption）本身可能大幅缓解。

---

## 七、AI Infra / MLSys 视角

**启发与借鉴价值**：
- **CPU-GPU 异构协作的新范式**：TOPPINGS 证明了在 LLM 推理中利用闲置 CPU 做轻量计算是可行的。这一思路可推广到其他场景：speculative decoding 的 draft model 计算、KV cache 压缩/量化、attention mask 预处理等轻量操作都可考虑 offload 到 CPU。
- **Sync-free GPU-CPU 协调技术**：融合异步 MemCpy 和 CUDA signaling 的自定义 operator 设计思路通用性强，可应用于任何需要 GPU-CPU 层级同步的场景。

**可迁移的技术**：
- Pipeline loading 的 layer group 划分策略可用于 prefetch 大型模型权重（如 MoE expert loading）。
- Rank-aware 性能建模思路可迁移到 MoE 推理中的 expert 调度——不同 expert 的计算负载不均匀，类似于 LoRA 的 rank 异构性。

**值得跟进的研究方向**：
- **CPU-assisted serving + Disaggregated architecture**：在 prefill-decoding 分离架构下，CPU-assisted 方案如何与 prefill server 的 batch 策略协同？
- **动态 adapter 缓存策略**：结合 CPU-assisted serving，研究 GPU adapter cache 的最优驻留策略——哪些 adapter 应常驻 GPU，哪些应按需加载并用 CPU 补偿。
- **异构 adapter 类型的统一调度**：将 rank-aware 调度扩展到支持 LoRA、DoRA、Adapter、Prefix-tuning 等不同 PEFT 方法混合服务的场景。

---

## 八、总结

TOPPINGS 通过 CPU-assisted LoRA serving 和 rank-aware scheduling 两个互补设计，有效解决了多租户 LoRA 服务中的 cumulative decoding-interruption 开销和异构 rank 调度问题。系统利用推理集群中闲置的 CPU 资源在 adapter 加载期间提前执行 LoRA 计算，配合一系列 GPU-CPU 协调优化（sync-free invocation、shared memory IPC、pipeline loading），将请求服务延迟降低最高 1.7×，SLO 达成率达到 99%。其核心局限在于对 CPU 资源可用性的依赖、在新型推理架构（如 disaggregated serving）下 C1 问题本身可能弱化，以及性能模型在硬件/模型变更时需要重新 profiling。
