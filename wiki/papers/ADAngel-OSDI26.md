---
type: paper
name: ADAngel
full_title: "ADAngel: Accelerating Arbitrary-Precision Quantized LLMs with Adaptive Computing Mapping"
authors: [Yao Liu, Wenjie Wang, Yifei Feng, Bo Peng, Jianguo Yao, Haibing Guan]
venue: OSDI
year: 2026
tags: [llm-inference, quantization, mixed-precision, gpu-kernel]
source_pdf: "[[osdi26-liu-yao.pdf]]"
source_md: "[[osdi26-liu-yao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# ADAngel：用自适应计算映射加速任意精度量化 LLM（OSDI 2026）

> **原题**：ADAngel: Accelerating Arbitrary-Precision Quantized LLMs with Adaptive Computing Mapping

> **一句话总结**：ADAngel 发现 W4A8 等不对称精度矩阵乘的最佳实现会随 prefill/decode、矩阵形状和 bit-width 改变，于是用 DPR 模型统一表达并构造 Padding、Split、Bitwise 三类 kernel，再为指定模型和 GPU 离线穷举建表；Llama-3-8B 在 Jetson AGX Orin 上相对 llama.cpp 的 W4A8 decode 吞吐最高提高 5.10×，相对 TensorRT-LLM 的 prefill TTFT 加速 1.17×–2.38×，代价是部署专用 profile 和多份权重布局占用。

## 问题与动机

在边缘设备上部署 [[LLM]] 时，[[Quantization|后训练量化]]（Post-Training Quantization，PTQ）会降低权重和 activation 的 bit-width。论文把任意权重—activation 精度组合称为 Arbitrary-Precision Quantization（APQ），例如 W4A8 表示 4-bit 权重和 8-bit activation。这样通常比同时把两者压到很低精度更容易保住模型质量，但把标准 GEMM/GEMV 变成两个输入精度不同的 mixed-precision GEMM（mpGEMM）。

现有 GPU 的 [[Tensor-Core|Tensor Core]] 只原生支持少量对称精度组合，不能直接执行任意 W4A8、W3A8。软件通常选择一种静态映射：Padding 把低 bit 权重扩到 activation 精度，能用高吞吐 INT8 Tensor Core，却增加计算和带宽；Bitwise 把两边拆成 1-bit bitplane，保留紧凑权重，却产生大量 partial product 和重建开销；LUT 则需要很大的查找表。

论文的关键发现是，同一种静态方案不会一直最好。prefill 的长序列更接近 compute-bound，Padding 往往占优；decode 的小 batch 更接近 memory-bound，Bitwise 更省权重流量。即使在同一阶段，prompt length、batch size、`M/N/K` 和量化 bit-width 变化也会让最佳方案交叉。ADAngel 因而不是再设计一个固定 kernel，而是为每个目标模型和 GPU 构造一个可按任务切换的 mpGEMM core。

## 关键观察 / 隐含假设

- **观察 1：prefill 与 decode 的瓶颈不同。** 在 Jetson AGX Orin 上运行 Llama-2-7B W4A8 时，Padding 的 prefill TTFT 更低，Bitwise 的 decode TBT 更低（§3，图 4a）。
  - **依赖假设**：prefill 主要受计算限制、低 batch decode 主要受权重带宽限制。
  - **可能失效场景**：更强的内存系统、更弱的整数 Tensor Core、很大的 decode batch，或 [[Attention|attention]]/[[KV-Cache|KV cache]] 成为主要瓶颈。
- **观察 2：同一阶段内部也有明确的策略交叉。** 该动机实验中，prefill length 为 8 时两种方案交叉；decode batch 为 16 时再次交叉（图 4b–c）。作者明确说明这些阈值不是通用常数，会随模型、bit-width 和 batch 改变。
  - **依赖假设**：系统按完整任务形状选择 kernel，而不是把阈值硬编码为只看 `M` 的规则。
  - **可能失效场景**：训练得到的 workload 不覆盖运行时形状，或并发、温度和 DVFS 使离线测得的交叉点漂移。
- **观察 3：目标模型的 `N/K` 组合很少。** Llama-3-8B 在 FasterTransformer 中只有约 4 种不同的 `(N,K)`，动态部分主要是 `M`；因此扫过 `M=1..8192` 的查找表只有约 256 KB（§4.4）。
  - **依赖假设**：模型结构、GPU、量化配置和 kernel 版本在部署期稳定。
  - **可能失效场景**：频繁更换模型、动态 [[MoE|MoE]] expert shape、per-layer/per-group precision，或输入长度超过 profile 范围。
- **假设 1：上游量化已经决定并验证模型质量。** ADAngel 优化的是量化后算子的执行，不重新选择 scale 或 bit-width，也没有报告 accuracy/perplexity。
  - **证据强度**：强；§2 将质量问题交给现有 APQ 方法，§6 只测 TTFT、TPS 和资源。

## 核心方法

### DPR：把不对称计算拆成硬件可执行的对称计算

DPR 是 Decomposition–Partial Product–Reconstruction 的缩写。给定 activation `X` 和权重 `W`，它先按 bit significance 把每个值逻辑分成若干块；每种 partition 都精确表示原值的加权和，因此矩阵乘也能写成各块乘积的加权和。

逻辑块的精度可能仍不受硬件支持。DPR 的 hardware-aware promotion 会找出所有块中的最大 bit-width，再提升到能够容纳它的最小原生精度，例如目标平台上的 INT1、INT4 或 INT8。所有块随后用同一种对称精度进入 Tensor Core。物理张量连续存放，以便合并多个 partial product 并减少 kernel launch。

如果 `X` 被分成 `m` 块、`W` 被分成 `n` 块，系统会计算 `m×n` 个 INT32 partial product，最后按每块的 bit 权重求和并 dequantize。分得越细，原始权重越紧凑，但 INT32 中间结果越多，共享内存压力也越大。DPR 的价值不是一个新公式，而是用同一个坐标系描述不同计算—带宽取舍。

### 三类计算策略

- **Padding** 使用不分块的 trivial partition，把较窄输入提升到足以容纳较宽输入的原生精度。它最接近硬件峰值吞吐，适合大 `M` 的 compute-bound 区间，但会扩大权重表示。
- **Bitwise** 把每个输入分成 1-bit bitplane，用 BMMA 计算大量 1-bit partial product。它不必读取扩展到 8-bit 的权重，适合小 `M` 的 memory-bound 区间，但重建指令和共享内存很多。
- **Split** 是论文提出的中间点。在支持 INT4 的 GPU 上，W4A8 可把 activation 拆成两个 4-bit 块，权重保持或提升到 4-bit，用一次形状为 `(2M,N,K)` 的 CUTLASS GEMM 计算，再由轻量 merge kernel 重建。W4A8 的 Bitwise 需要 32 个 INT32 partial product，Split 只需 2 个，中间结果空间少 16×。实现只在权重不超过 4 bit 时使用 Split，因为 W5 及以上不再比 Padding 节省权重流量。

Padding 和 Split 基于 CUTLASS 3.1.0，Bitwise 是继承 ABQ-LLM 权重布局的自定义 BMMA kernel。实现还融合 activation quantization 与 decomposition，并使用异步 global-to-shared-memory pipeline。整个系统约 15k 行 C++/CUDA 12.6，作为 mpGEMM backend 接入 FasterTransformer。

### 离线 Oracle Policy Map 与在线查表

对指定模型、GPU 和量化配置，离线脚本先找出有限的 `(N,K)` 类型，再对每个 `M` 实测三类 kernel，充分 warm-up 后用 CUDA event 记录平均 latency。每个点只保存最快 kernel 的 function pointer，组成 Oracle Policy Map。这里的“oracle”只表示在已测候选策略和 profile 条件下最快，不是对任意运行环境的理论全局最优。

运行时 dispatcher 用任务形状直接索引 function pointer 并调用 kernel，不做在线搜索。Llama-3-8B W4A8 在 Orin 上扫描 4 种 `(N,K)` 和 `M=1..8192`，一次建表约需 5.7 小时、峰值内存约 1.7 GB；最终表约 256 KB。同模型或共享 shape 的 layer 可以复用已有条目。

## 设计取舍

- **离线穷举换取低运行时开销**：部署后只查表，消融中总 dispatch 开销少于 3 ms；换模型、GPU、precision 或 kernel 后则要重建 profile。
- **多策略换取覆盖面**：Padding、Split、Bitwise 覆盖计算受限、中间区间和带宽受限任务，但要维护三套高度优化且数值一致的 CUDA 实现。
- **预物化布局换取速度**：多种分解权重提前放在 global memory，避免在线转换，却明显增加模型内存。
- **实测最优换取迁移性**：查表能捕捉难建模的 tiling 交叉点，但无法自动适应多租户干扰、频率变化或新 shape。
- **边界条件**：ADAngel 最适合固定模型、固定 GPU、长期运行且 shape 空间有限的 [[LLM-Inference|LLM 推理]]服务；临时任务和频繁更新的部署较难摊销 5.7 小时 profile。

## 实验与结果

- 主实验使用 50 W 模式的 Jetson AGX Orin 64 GB、CUDA 12.6 和 Llama-3-8B，覆盖 W2A8、W3A8、W4A8、W5A8。基线为 ABQ-LLM、llama.cpp 和 [[TensorRT-LLM]]；Orin 版 TensorRT-LLM 不支持 W4A8，因此比较的是 W8A8 SmoothQuant 和 W4A16 AWQ，并非完全相同的数值格式（§6.1）。
- W4A8 prefill 中，ADAngel 相对 TensorRT-LLM 的 TTFT 加速为 1.17×–2.38×。batch 1、prompt 32 时，它把 llama.cpp 的 126 ms 降到 43 ms。batch 8、prompt 1024 时，ABQ-LLM 因 INT32 partial product 撞上 Shared Memory Wall，耗时约 39.4 分钟；ADAngel 为 5.27 秒，形成 448.69× 的病理性大比值（§6.2，图 8）。
- W4A8 decode 中，论文摘要报告相对 llama.cpp 的吞吐最高提高 5.10×。相对 TensorRT-LLM W8A8，batch 1 时提高 1.95×；batch 2–8 时平均提高 1.82×。作者把收益归因于避免 8-bit 权重带宽，以及 `M=1` 映射到典型 `M=16` INT8 tile 时 15/16 计算槽被零填充浪费（§6.2，图 9）。
- 跨精度实验中，W2A8/W3A8/W5A8 的 prefill TTFT 相对 llama.cpp 平均加速 3.43×，相对 ABQ-LLM 最高 200×；decode TPS 相对 llama.cpp 最高 7.35×。W5A8 已不使用 Split，说明三策略并非每种精度都适用（§6.3，图 10–11）。
- 在 A100 80 GB 上重新生成专用 engine 后，ADAngel 相对 QServe W4A8KV4 的 TTFT 和 TPS 分别提高 2.12×、1.72×，也继续领先论文测试的 llama.cpp、TensorRT-LLM 和 ABQ-LLM 设置。它证明方法可移到数据中心 GPU，但仍只测试 Llama-3-8B（§6.4，图 12–13）。
- 消融中，只按 `M` 使用固定阈值的 ADAngel-R 在 decode batch 2–4 落后，因为忽略 `N/K`；移除 Split 会损失 prompt 16–64 和 decode batch 2–4 的机会；固定 Bitwise 在长 prefill 中严重退化。资源方面，batch 8、prompt 1024、每序列生成 128 token 时峰值 18.80 GiB，其中权重 14.96 GiB、KV cache 1.125 GiB、ADAngel workspace 896 MiB（§6.2、§6.5，图 14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 按完整 shape 动态选策略优于固定 kernel 或只看 `M` 的规则 | ADAngel-R、w/o-Split 和三种静态策略消融（§6.5，图 14） | Llama-3-8B W4A8、Orin；没有与在线 autotuner 比较 | 强 |
| 自适应策略能改善边缘端 W4A8 的 prefill 和 decode | TTFT 相对 TensorRT-LLM 1.17×–2.38×；decode 相对 llama.cpp 最高 5.10×（§6.2） | TensorRT-LLM 使用 W8A8/W4A16，不是等精度 W4A8 | 中 |
| DPR 策略组合能避免 Bitwise 的长序列资源墙 | ABQ-LLM 约 39.4 分钟，ADAngel 5.27 秒；Split 将 W4A8 中间结果从 32 份降到 2 份（§4.3、§6.2） | 448.69× 主要来自基线在该点病理退化 | 强 |
| 方法可扩展到其他 bit-width 和服务器 GPU | W2/W3/W5 与 A100 实验均领先对应基线（§6.3–§6.4） | 仍是一个模型、两个 NVIDIA Ampere GPU；未覆盖其他 ISA | 中 |
| 离线表足够小，但专用化并非免费 | 256 KB dispatch table；一次 profile 5.7 小时、峰值 1.7 GB；运行峰值 18.80 GiB（§4.4–§6.2） | 成本只针对一组模型、硬件和 precision | 强 |

## 批判性分析

### 论证链条

论文先用四组测量展示策略随阶段、prompt、batch 和 bit-width 交叉，再用 DPR 把策略空间统一起来，最后通过完整查表、只看 `M`、移除 Split 和固定策略的消融证明“可选策略要丰富，选择粒度也要细”。从观察到设计再到消融，链条比较完整。

需要避免把 Oracle Policy Map 理解成普遍最优。它只在给定候选 kernel、给定 GPU 状态和离线输入形状上选出平均 latency 最低者。完整 ADAngel 的优势还包含 CUTLASS/BMMA 实现、异步 pipeline 和 fusion；虽然静态 ADAngel-* 消融尽量隔离 kernel 工程收益，论文仍没有与成熟在线 autotuner 或可迁移 cost model 比较。

### 假设压力测试

多租户共享 GPU、动态 [[Continuous-Batching|continuous batching]]、功耗限制和温度变化都会改变离线测得的最佳 kernel。若运行时出现 `M>8192`、新的 `(N,K)`、MoE expert 或 per-layer mixed bit，表中可能没有对应项；论文没有说明 miss 的回退与在线校准。频繁升级模型的边缘产品也未必能摊销每组配置约 5.7 小时的搜索。

ADAngel 把量化质量视为输入条件，但 baseline 的精度并不统一。W4A8 ADAngel 与 TensorRT-LLM 的 W8A8/W4A16 在算术吞吐、权重带宽和模型质量上都不同；A100 上 QServe 还使用 KV4。性能领先成立于这些公开配置，不能直接推出“同等 accuracy 和 memory budget 下”仍领先。

### 实验可信度

实验覆盖 prefill、decode、多个 prompt/batch、四种权重精度、Orin/A100、多类 baseline、内存分解和有针对性的消融，指标也采用端到端 TTFT/TPS，而不只报 microkernel。作者主动解释 448.69× 来自 ABQ-LLM 的 Shared Memory Wall，并给出绝对时间，这一点很重要。

外推范围仍窄：主模型只有 Llama-3-8B，动机使用 Llama-2-7B；硬件只有两个 NVIDIA Ampere 平台。结果是 warm-up 后多次运行的平均值，没有方差、p95/p99、能耗或长时间热稳定性。不同端到端框架自身开销不同，论文也承认 ADAngel 相对 TensorRT-LLM 的部分收益来自较轻的 FasterTransformer testbed，而非 mpGEMM 映射本身。

### 系统性缺陷

系统以多份权重表示换速度。Llama-3-8B 的量化权重在测量中占 14.96 GiB，远高于只保存一份紧凑 W4 权重的直觉大小；再加 workspace 和 KV cache 后峰值 18.80 GiB。论文的 Orin 有 64 GB 内存，但许多真正的边缘设备只有 8–16 GB，这些设备可能根本放不下当前策略集合。

三套 kernel 必须在所有 shape、符号位、量化 scale 和 overflow 边界上保持数值一致，维护负担会随新 ISA 和新 precision 增长。论文用 DPR 说明数学重建，但没有报告独立数值一致性测试或故障处理。profile 数据、驱动升级后的失效检测、查表 miss、kernel crash 和降级路径也未讨论。

## 局限与后续工作

- **局限 1**：一次专用建表约需 5.7 小时，模型、GPU、precision 或 kernel 变化后可能重做；当前 map 只覆盖观测到的 `(N,K)` 和 `M=1..8192`。
- **局限 2**：峰值 18.80 GiB 和 14.96 GiB 多布局权重不适合许多 8–16 GB 边缘设备；论文没有给出按内存预算裁剪策略集合的结果。
- **局限 3**：评测只有 Llama-3-8B、Orin 和 A100，未测模型质量、energy/token、tail latency、多租户干扰或非 NVIDIA 硬件。
- **后续工作 1**：在同一 GPU 上加入并发请求、DVFS 和热稳态实验，比较静态表、在线校准和 cost model 的 p99 TTFT、TPS 与 profile 成本。
- **后续工作 2**：给定 8 GB、16 GB、32 GB 三档内存预算，自动选择需要保留的权重布局，以端到端性能损失和峰值内存验证 Pareto 曲线。
- **后续工作 3**：扩展至少两种不同结构模型和一种非 NVIDIA ISA，并对每个 shape 做逐元素数值对照，公开查表 miss 和安全回退行为。

## 相关

- **相关概念**：[[Quantization]]、[[Tensor-Core]]、[[LLM-Inference]]、mixed-precision GEMM、GPU kernel autotuning
- **同类系统**：[[TensorRT-LLM]]、QServe、ABQ-LLM、llama.cpp
- **同会议**：[[OSDI-2026]]
