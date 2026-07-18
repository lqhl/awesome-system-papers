---
type: paper
name: FluxMoE
full_title: "FluxMoE: Decoupling Expert Residency for High-Performance MoE Serving"
authors: [Qingxiu Liu, Cyril Y. He, Hanser Jiang, Zion Wang, Alan Zhao, Patrick P. C. Lee]
venue: arXiv
year: 2026
tags: [moe, llm-inference, kv-cache, expert-offloading, memory-management, lossless-compression]
source_pdf: "[[arxiv26-liu-fluxmoe.pdf]]"
source_md: "[[arxiv26-liu-fluxmoe]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# FluxMoE: Decoupling Expert Residency for High-Performance MoE Serving (arXiv 2026)

> **一句话总结**：FluxMoE 把 [[MoE]] expert 权重从 GPU 常驻 state 改成按层流式 materialize 的 transient state，用 PagedTensor + 压缩 GPU backend + CPU offload 在高 batch / 4K context 的 decode-like 场景里把 HBM 让给 [[KV-Cache]]，在 4×L40 上对 Qwen3-Next-80B-A3B-Instruct 相比 [[vLLM]] 最高达到 3.0× 吞吐，但收益强依赖“KV cache 是主瓶颈、expert I/O 能被层间计算隐藏、PCIe/压缩开销可控”这一组假设。

## 问题与动机

论文要解决的是大规模 MoE 推理里的 GPU 内存错配：MoE 通过把 dense FFN 换成大量 expert 来扩容量，但现有 serving 系统通常把所有权重当作会话期间必须常驻 GPU 的静态 state。实际 decode 时，层按顺序执行，任一时刻只会消费当前层的 expert 权重；绝大多数 expert 在当前 step 里是 idle 的，却仍然长期占据 HBM。

这与 LLM serving 的另一个事实冲突：[[KV-Cache]] 容量直接决定 batch size、context length 和是否触发 CPU-GPU swap。论文在 Mixtral-8×7B 上给出动机测量：把 KV budget 从 20 GiB 扩到 60 GiB，在 batch size 128、context 4096 时吞吐提升 58.8%；固定 20 GiB 时 context 从 1024 拉到 4096 使吞吐下降 66.7%，而 60 GiB 配置把这部分损失显著压低。作者由此把瓶颈归因到“冷 expert 权重挤占热 KV cache”。

FluxMoE 的核心 claim 不是减少 MoE 计算量，也不是预测哪些 expert 会被 router 选中，而是重新定义权重 residency：expert 参数可以像 OS page 一样按需映射，GPU 只保留当前层和下一层附近的 working set，把更多 HBM 交给 KV cache 和 activation buffer。论文尤其把目标放在 [[Disaggregation|prefill/decode disaggregation]] 中的 decode 侧，因为 decode 更 memory-bound，KV cache 增长更直接限制持续吞吐。

## 关键观察 / 隐含假设

- **观察 1：MoE expert 权重体积大且时间局部性强。** Mixtral-8×7B-Instruct 的 47B 参数约 94 GB，是 Mistral-7B 的 6.7×；Qwen3-Next-80B-A3B-Instruct 的 80B 参数约 160 GB，是 Qwen2.5-14B 的 5.4×。同时，decode 的 layer execution 是顺序的，当前 kernel 只需要当前层的 expert tensors。
  - **依赖假设**：模型结构要有大量 expert 参数，且 expert weight access 能按 layer 划出稳定 working set；FluxMoE 实际加载的是整层 experts，而不是只加载 router top-k，因此它依赖“整层 expert 体积仍可在前一层计算窗口内搬完”。
  - **可能失效场景**：小 MoE、dense 模型、expert 数少的模型、或强 [[Quantization]] 后权重已不再是主要 HBM 消耗时，paging 的收益会被 VMM/remap/decompression overhead 吃掉。论文也显示 batch size 32 时 FluxMoE 只有 vLLM 吞吐的 63.9%。

- **观察 2：在 memory-intensive decode 场景中，KV cache 比 expert 常驻更 performance-critical。** 论文用 KV budget sweep 说明更大的 KV cache 可以减少 CPU-GPU swapping，并在 Qwen3-Next-80B 的 batch/context sweep 中展示 vLLM 在 batch 128 之后负 scaling：batch 从 128 到 256 时吞吐下降 32.2%。
  - **依赖假设**：目标 workload 是高 batch、较长 context、持续生成，且系统瓶颈主要来自 KV swap 或 KV 容量不足，而不是 attention compute、scheduler overhead、network all-to-all、或 tokenizer/采样等外围成本。
  - **可能失效场景**：交互式低 batch、短输出、prefill-heavy、或已有足够 HBM/NVLink 的部署中，KV pressure 不一定压过 weight materialization overhead。

- **观察 3：BF16 expert 权重的 exponent bits 低熵，适合无损压缩。** Figure 5 显示 Mixtral 和 Qwen3-Next 的 expert 权重 exponent 分布集中，而 mantissa 接近均匀；FluxMoE 因此只对 exponent 做 selective Huffman coding，sign 和 mantissa 保持原样，约节省 20% expert storage。
  - **依赖假设**：模型权重格式主要是 BF16，且无损压缩带来的 20% HBM 回收足以改变 KV cache 容量边界；decompression kernel 的吞吐也必须高到能藏在 layer compute 后面。
  - **可能失效场景**：FP8/FP4/QAT 模型、per-expert quantization、或本来就以低 bit 权重部署的 MoE，exponent-only Huffman 的边际空间会变小。

- **假设 1：专家加载延迟可以被层间计算隐藏。**
  - **证据强度**：中。Figure 6 和 Exp#3 支持在作者的 4×L40、Qwen3/Mixtral、batch/context 设置下存在可隐藏窗口，但没有覆盖更快 GPU、更细 MoE 层、更长 context、动态 arrival、或 PD 分离后的 PCIe/KV 竞争。

- **假设 2：VMM remapping 可以作为 serving fast path 的可靠抽象。**
  - **证据强度**：中偏弱。Exp#4 显示 PagedTensor 在所有 expert uncompressed resident 时峰值吞吐 overhead 约 3.0%，但论文没有讨论 CUDA VMM 在多租户、fault recovery、CUDA graph、异构 kernel、或长时间运行中的可观测性和故障语义。

## 核心方法

FluxMoE 的抽象是 **expert paging**：把 MoE 模型看成静态 compute graph 加流式 expert 参数。执行第 i 层时，当前层 experts 必须 resident；第 i-1 层可以释放；第 i+1 层异步 prefetch。系统维持两层滑动窗口 $R_i \subseteq \mathcal{E}_i \cup \mathcal{E}_{i+1}$，把强制 expert footprint 从全模型压到约 $2/N$ 层的 expert 工作集。这个设计回应观察 1：MoE 权重不必以“全模型常驻”的方式占 HBM。

**PagedTensor** 是 expert paging 的地址抽象。每个 expert 有 fused gate/up-projection 和 down-projection 两类 tensor；系统为每个 logical tensor 预留稳定 GPU virtual address，使用 CUDA VMM 的 `cuMemMap` / `cuMemUnmap` 把少量 physical tensor buffers 动态映射到这些 virtual pages。对 PyTorch/Triton kernel 来说，tensor 地址稳定且连续，因此不需要修改 kernel。它和 [[PagedAttention]] 的区别很关键：PagedAttention 因为每个 request 的 KV page 集合不同，必须在 attention kernel 内做 block lookup；PagedTensor 利用 expert weight 在 kernel launch 前已知且共享的特点，把 virtual-to-physical mapping 移到 kernel 前异步完成。

PagedTensor 的 correctness 依赖四个 invariant：virtual address 稳定、每个 page 同时最多映射一个 physical block、block reuse 前等待所有读它的 kernel 完成、以及固定 block pool 被循环复用。实现上用 loading streams 和 compute stream 之间的 CUDA events 维护 WAR / RAW：不能覆盖仍被 compute 读取的 block，也不能让 compute 在权重未 load 完成前启动。这回应假设 2，同时把复杂性压在内存映射与 stream synchronization 里，而不是扩散到每个 kernel。

**Expert storage hierarchy** 解决“权重从哪里来”。FluxMoE 把 expert 参数分到 compressed GPU backend 和 CPU offload backend。理论模型把每个 backend 的有效带宽记为 $B_k$，按 $x_k = B_k / \sum_\ell B_\ell$ 分配参数比例，让各 backend 在同一个 streaming window 内同时完成加载。这个带宽比例策略比“整层在 GPU / 整层 offload”的粗粒度切分更细，回应的是观察 2 的资源竞争：offload 不能只是腾 HBM，还要避免把 PCIe 变成新的瓶颈。

Compressed GPU backend 只压 expert 参数，因为论文声称 expert 超过 evaluated models 参数体积的 90%；非 expert weights 保持 uncompressed GPU-resident，避免 attention projection 等 critical path 多一层解压。CPU backend 使用 pinned host DRAM 和 asynchronous DMA，通过 layer i compute 与 layer i+1 prefetch overlap 提供容量 tier。这个组合有一个简单但重要的取舍：FluxMoE 不做 router prediction，所以不会因 expert prediction miss stall；代价是每层要 materialize 全部 experts，对 storage bandwidth 的要求更高。

**Budget-aware residency planner** 是运行时控制器。它维护 expert residency level $\alpha$，用 $\rho = \tau_{\text{comp(theory)}} / \tau_{\text{load}}$ 判断当前是 compute-bound 还是 I/O-bound。若 $\rho > 1$，说明计算窗口足以隐藏加载，就降低 $\alpha$，把 HBM 还给 KV cache；若 $\rho < 0.9$，说明加载开始拖慢 compute，就提高 $\alpha$，让更多 expert 留在 GPU；$[0.9, 1.0]$ 是 dead zone，减少 PCIe burst 导致的振荡。硬约束始终是 $C_{\exp}(\alpha) \le C_{\text{gpu}} - C_{\text{kv}}$，即 expert residency 不能挤掉 KV cache。

实现规模相对克制：论文称基于 [[vLLM]] v0.10.2，核心约 3.1K LoC C++ 和 2.1K LoC Python，只需约 20 LoC 改动接入 vLLM。这个实现口径支撑了“middleware rather than full serving stack rewrite”的 claim，但也意味着 evaluation 主要继承 vLLM 的 batching、KV allocation 和执行模型边界。

## 设计取舍

- **用全层 expert paging 换掉 router prediction。** 好处是逻辑简单、没有 prediction miss；代价是 materialization volume 按整层 expert 计算，低 batch 或薄层 compute 时更容易 I/O-bound。
- **用 CUDA VMM 保 kernel 兼容。** 好处是不改 PyTorch/Triton kernels，抽象边界清楚；代价是 correctness 依赖 mapping lifecycle 和 stream event ordering，debug/failure handling 比普通 tensor residency 更隐蔽。
- **用 lossless exponent compression 换取模型 fidelity。** 好处是理论上不改变权重值，适合 precision-sensitive deployment；代价是压缩率只有约 20%，远低于 lossy quantization，对已经 FP8/FP4 化的模型帮助有限。
- **优先 KV cache 而不是 expert residency。** 好处是在 memory-intensive decode 中提高 batch/context capacity；边界是如果 KV cache 不再是瓶颈，FluxMoE 会暴露 decompress/offload/remap overhead。
- **以 throughput 为主 metric。** 这符合 capacity-bound serving，但没有覆盖 TTFT、TPOT、tail latency、deadline/SLO、动态 arrival、multi-tenant isolation 等 production serving 关心的面。

## 实验与结果

- **测试床**：单节点 4×NVIDIA L40 PCIe GPU，每卡 48 GB GDDR6；Intel Xeon Platinum 8358，2 TiB host DRAM；TP=4 或 TP=2。模型为 Mixtral-8×7B-Instruct（32 层，47B 参数）和 Qwen3-Next-80B-A3B-Instruct（48 层，80B 参数）。workload 来自 ShareGPT，context length 1024-4096，batch size 32-256。
- **Exp#1，performance-bound Qwen3-Next-80B TP=4**：FluxMoE 只用 compressed GPU backend 保持所有 experts 在 GPU compressed form。batch size 256、context 4096 时，FluxMoE 吞吐比 vLLM 高 3.0×、比 vLLM-O 高 3.7×。vLLM batch 从 128 到 256 后吞吐下降 32.2%，作者归因为 KV cache swap；FluxMoE 因释放 HBM 给 KV cache 而继续 scale。
- **低 batch 反例**：batch size 32 时，FluxMoE 只有 vLLM 吞吐的 63.9%，因为 GPU memory 尚不紧张，on-the-fly decompression 变成纯 overhead。这是论文最重要的适用边界之一。
- **Context scaling**：batch size 固定 256、context 从 1024 增到 4096 时，vLLM 吞吐下降 45.3%，FluxMoE 下降 20.5%。这支持“KV cache pressure 越大，FluxMoE 越有利”的方向。
- **Exp#2，capacity-bound Mixtral TP=2**：vLLM 初始化 OOM；vLLM-O 通过 offload 可跑但在 batch 256、context 4096 时只有 3.7 tokens/s。FluxMoE 在相同 12.5% expert offload 约束下，相比整层粒度的 FluxMoE-H，在 batch 256 时对 context 1024/4096 分别提升 28.5%/22.9%，证明 bandwidth-balanced placement 优于粗粒度 layer placement。
- **Exp#3，runtime adaptation**：Qwen3-Next-80B TP=4、batch 256、context 4096 下，iteration 2700 后 planner 每 300 iterations offload 48 compressed experts per rank；7 次调整累计释放 48×4×7 compressed experts，约 5.3 GB GPU memory。带 I/O balance 的动态 $\alpha$ 吞吐不低于固定 $\alpha=1.0$ baseline；不做 I/O balance 的版本在调整阶段出现明显吞吐下降。
- **Exp#4，PagedTensor overhead**：当所有 expert 都 uncompressed 且 resident，消除 decompression 和 PCIe transfer 后，PagedTensor 相比 vLLM native allocation 的峰值 overhead 为 3.0%（batch 64，context 4096）。这说明地址虚拟化本身不贵，主要风险在 I/O/压缩策略。

## Critical Analysis

### 论证链条

论文的主链条在“memory-constrained decode throughput”这个窄目标上基本闭合：先测 MoE 权重与 KV cache 的 HBM 竞争，再把 expert residency 改成 paging，随后用 compressed GPU storage 和 CPU offload 控制 loading bandwidth，最后在高 batch / 4K context 下展示 vLLM 因 KV swap 崩塌而 FluxMoE 继续 scale。Observation → design → result 的对应关系清楚。

真正的跳步在 claim 的外延。论文动机里强调 disaggregated serving 的 decode 侧，但 evaluation 仍在 vLLM 风格 co-located setup 上报告 aggregate throughput，没有真实 PD 分离、KV store、prefill/decode routing、或 dynamic arrival trace。它证明的是“在 vLLM 单节点高 batch 实验中，把 expert 权重挪出 HBM 可缓解 KV swap”，而不是完整证明“现代生产 MoE decode 集群应该用 expert paging”。

另一个跳步是把“lossless compression”近似等同于“without compromising model fidelity”。理论上 sign/mantissa 不变、exponent 可逆编码应 bit-exact，但系统论文仍应给出解压后权重一致性检查或 lm-eval/mathematical reasoning 表。当前 markdown 中没有看到 accuracy benchmark；这个 claim 主要靠方法性质支撑，而不是实验表支撑。

### 假设压力测试

FluxMoE 最核心的压力点是 $\tau_{\text{load}}$ 是否长期小于可隐藏的 compute window。这个假设在 batch 256、context 4096、L40 PCIe 上成立，但在 batch 32 已经不划算；在 H100/H200/GB200 这类 compute 更强、interconnect 不同、HBM 更大的硬件上，compute window、HBM pressure 和 PCIe/NVLink tradeoff 都会变。L40 的 PCIe+48GB 组合天然放大“HBM 紧、offload 慢、但压缩能救”的窗口。

Workload 上，论文只覆盖 context 1024-4096。对 2026 年长上下文模型，4K 更像中短 context；当 context 进入 64K、256K 或 1M，attention/KV bandwidth、prefix reuse、KV compression、sparse attention、PD 分离的 KV movement 都会改变瓶颈结构。FluxMoE 可能仍有价值，但必须重新证明 expert loading 不会和 KV movement 争抢同一条 host/GPU I/O path。

模型侧也有压力。若新 MoE 默认使用 FP8/FP4 expert weights、[[Quantization]] 或更激进的 KV compression，FluxMoE 的 exponent-only lossless compression 回收空间会缩小；反过来，如果模型的 expert 层更轻、shared expert/attention 占比更高，按层加载全部 expert 的策略就更难 amortize。

### 实验可信度

实验的优点是 ablation 比较清楚：vLLM、vLLM-O、FluxMoE-H、PagedTensor-only overhead 分别拆出了 KV swap、offload penalty、bandwidth-balanced placement 和 address virtualization overhead。ShareGPT 也是 serving 论文常用 workload，batch/context sweep 能直接呈现 capacity-bound 行为。

短板是 baseline 覆盖不足。论文 related work 中提到 MoE-Lightning、[[KTransformers-SOSP25|KTransformers]]、[[MOE-INFINITY-arXiv24|MoE-Infinity]]、Diff-MoE 等 MoE offloading / hybrid inference 系统，但主实验没有把这些系统拉到同一硬件同一模型上比较。vLLM-O 和 FluxMoE-H 是作者实现的 internal baselines，适合做机制分解，但不足以代表外部 SOTA。

Metric 也偏窄。只报告 aggregate tokens/s，基本不覆盖 interactive serving 的 TPOT、TTFT、P99 latency、request completion time、SLO miss rate、scheduler fairness、或 mixed prompt/output length。对于一个要改 residency planner 的 serving 系统，动态 request arrival 和 tail behavior 是关键证据缺口。

### 系统性缺陷

论文没有充分讨论故障恢复和可观测性。PagedTensor 的抽象把“tensor logical identity”和“physical storage”解耦，debug 时必须能回答某个 expert 当前在 compressed GPU、CPU DRAM、还是 physical buffer 中，以及对应 CUDA event 是否完成；这些状态若出错，可能表现为 silent wrong output、illegal memory access、或 intermittent stall。论文列出 invariants，但没有 production diagnostics。

多租户隔离也只是间接出现。Exp#3 说释放的 5.3 GB 可用于 co-locate other tasks，或未来给 dynamic KV cache resizing 使用；但当前 vLLM/SGLang 通常静态分配 KV cache，论文没有实现端到端的 dynamic KV reallocation，也没有测 co-tenant 干扰下 planner 的稳定性。

最后，FluxMoE 把系统复杂度集中在 GPU virtual memory、compression/decompression、pinned host memory、PCIe DMA、stream pool 和 planner 控制环。这个复杂度是否值得，取决于用户是否真的处在“模型能跑但 KV cache 被 expert 权重挤爆”的区域。论文给出了这个区域的强 positive case，也给出了低 batch negative case，但还没有给出足够完整的 phase diagram。

## 局限与 Future Work

- **局限 1：部署范围偏窄。** 当前证据集中在单节点 4×L40、TP=2/4、context 1K-4K、batch 32-256。需要在 H100/H200/GB200、NVLink、PCIe Gen5、以及 CXL/host-memory tier 上重画吞吐和内存 phase diagram。
- **局限 2：没有真实 PD 分离评估。** 论文动机面向 decode cluster，但没有在 [[Disaggregation|prefill/decode disaggregation]] 系统中测 KV movement、decode queueing、和 expert paging 的相互影响。
- **局限 3：fidelity claim 缺实验表。** 无损压缩理论上应 bit-exact，但仍需要报告 decompression correctness、端到端 benchmark accuracy、以及长时间运行下的 numerical consistency。
- **局限 4：baseline 不足。** 需要和 [[KTransformers-SOSP25]]、[[MOE-INFINITY-arXiv24]]、MoE-Lightning、Diff-MoE、ZipMoE 等在相同模型/硬件/metric 下比较。
- **Future work 1：建立 expert paging 的 phase diagram。** 系统扫 batch、context、expert count、layer compute time、HBM size、PCIe/NVLink bandwidth、compression ratio，输出什么时候 paging wins、什么时候 resident/quantized wins。
- **Future work 2：把 planner 接入动态 KV cache resizing。** 让 $\alpha$ 调整真正反馈到 KV allocator，而不是只证明释放 HBM 后“未来可用”；metric 应包括吞吐、TPOT、P99、SLO miss 和 fragmentation。
- **Future work 3：做 PD 分离 replay。** 用 Mooncake/DistServe 类架构或公开 serving trace，测 expert weight streaming 与 KV transfer 是否抢占同一 I/O budget。
- **Future work 4：验证 VMM lifecycle 的可运维性。** 增加 per-expert residency trace、event wait diagnostics、illegal remap detection、fault injection 和 long-run soak test。

## 相关

- **相关概念**：[[MoE]]、[[KV-Cache]]、[[PagedAttention]]、[[Disaggregation]]、[[Quantization]]
- **基础系统**：[[vLLM]]、[[SGLang]]
- **同类系统 / 论文**：[[KTransformers-SOSP25]]、[[MOE-INFINITY-arXiv24]]、MoE-Lightning、Diff-MoE、ZipMoE、ZeRO-Infinity、FlexGen
- **相邻方向**：[[OPKV-MLSys26]]、[[CacheGen-SIGCOMM24]]、[[NSA-ACL25]]、[[DeepSeek-V4-arXiv26]]
- **源码材料**：[[arxiv26-liu-fluxmoe]]、[[arxiv26-liu-fluxmoe.pdf]]
