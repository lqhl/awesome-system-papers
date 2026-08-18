---
type: paper
name: ProfInfer
full_title: "ProfInfer: An eBPF-Based Fine-Grained LLM Inference Profiler"
authors: [Bohua Zou, Debayan Roy, Dhimankumar Yogesh Airao, Weihao Xu, Binqi Sun, Yutao Liu, Haibo Chen]
venue: MLSys
year: 2026
tags: [profiling, ebpf, llm-inference, edge, llama-cpp, observability, area/ai-infra]
source_pdf: "[[6ea9ab1baa0efb9e19094440c317e21b.pdf]]"
source_md: "[[6ea9ab1baa0efb9e19094440c317e21b]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# ProfInfer：基于 eBPF 的细粒度 LLM 推理分析器（MLSys 2026）

> **原题**：ProfInfer: An eBPF-Based Fine-Grained LLM Inference Profiler

> **一句话总结**：ProfInfer 以 eBPF uprobe 挂接 llama.cpp/GGML 的 token、graph、operator 三层，并用 PMC 与三种视图诊断执行。在评测的 Orange Pi 全量 operator tracing 下，decode speed degradation 为 BCC **2.8%–4%**、libbpf **1.7%**；结论不外推为其他 inference engine 的通用开销。

## 问题与动机

论文要解决的是 on-device / edge LLM 推理的**可观测性真空**。与 ONNX Runtime、TensorRT 等通用 ML 引擎不同，面向 [[llama.cpp]] 这类 LLM inference engine（IE）几乎不提供 operator-level、非侵入式 profiler：现有方案要么要求重编译或 runtime instrumentation，要么只给 throughput / token rate 这类粗粒度指标，无法暴露动态算子图、per-thread 调度、hardware counter 事件，以及 prefill vs decode 的阶段差异。

这个问题在 mobile 部署下尤其尖锐。Decoder-only LLM 推理分 prefill（通常 compute-bound）和 decode（常 memory/bandwidth-bound）两阶段；设备又受功耗、内存、散热和能耗约束。开发者连「当前 workload 是 memory-bound 还是 compute-bound」这类基础问题都难回答，更谈不上指导 [[Quantization]]、[[KV-Cache]] 复用、accelerator offloading 或带宽受限下的调度优化。

近期 eBPF 已被用于深度学习 tracing（eInfer、eGPU 等），但论文指出这些工作**与 LLM 执行语义脱节**：很少把低层 hardware metrics 与高层 operator 语义对齐，也未针对 mobile/edge 上更严格的 overhead 约束和动态执行行为（[[MoE]] routing、[[Speculative-Decoding]]）做适配。ProfInfer 的目标是在不改源码、不重编译的前提下，为 llama.cpp 类 runtime 提供 token / graph / operator 三层细粒度 profiling，并把结果转成可诊断瓶颈的可视化。

## 关键观察 / 隐含假设

- **观察 1：LLM IE 的 profiling 缺口主要在「语义对齐 + 非侵入 + 低开销」三角。** 论文对比 llama.cpp 内置 `ggml_graph_dump_dot`（13% overhead，且无性能数据）和 ONNX Runtime profiler（~8%），说明即便有 profiler，要么侵入性强，要么粒度不够细。
  - **依赖假设**：开发者真正需要的是 operator 类型、tensor 维度、计算 DAG 与 hardware counter 的关联，而不是 aggregate latency  alone。
  - **可能失效场景**：若团队只关心 end-to-end TTFT/TPOT 且已有足够强的 A/B 测试基础设施，细粒度 profiler 的边际价值会下降。
- **观察 2：llama.cpp / GGML 的 C 函数边界天然适合 eBPF uprobe 分层挂钩。** `llama_decode` 覆盖 token 级；`ggml_backend_graph_compute_async` 覆盖 graph 级；`ggml_compute_forward` 覆盖 operator 级——三层函数与 IE 内部调度结构一一对应。
  - **依赖假设**：目标 IE 保持类似 GGML 的显式 graph compute API，且 probe 点在未来版本里相对稳定；论文主要验证 llama.cpp，但声称架构可推广到类似 runtime。
  - **可能失效场景**：Python-first IE（[[vLLM]]、[[SGLang]]）、JIT/AOT 编译后内联的 kernel、或频繁重构的 runtime ABI 会让 uprobe 维护成本陡增。
- **观察 3：decode 阶段 MatMul 主导且呈 memory-bound，线程数存在 sweet spot。** 评估显示 MatMul 占 TTFT/TPOT 的 >97%；Cortex-A76 上 2 线程显著快于 1 线程，但 4 线程会带来 >80% stalled backend cycles，说明 bandwidth 瓶颈先于 compute 饱和。
  - **依赖假设**：on-device 推理以 batch=1、dense 或 moderate [[MoE]] 模型为主；PMC（`l3d_cache_refill` 等）能代表 DRAM 流量。
  - **可能失效场景**：大 batch serving、prefill-heavy workload、或 NPU/GPU 主导 backend 时，CPU PMC 与端到端瓶颈的对应关系会变弱。
- **观察 4：[[MoE]] 在内存不足设备上的瓶颈常是 disk I/O，而非算力。** Qwen1.5-MoE-A2.7B 在 Orange Pi 上 mmap 运行时，operator 耗时与连续两次激活同一 expert 的「平均距离」近似成正比；page fault 和 memory access 指向存储加载，而非 HBM 带宽。
  - **依赖假设**：expert 权重无法全部驻留 DRAM，gating 的 top-k 激活模式导致频繁 cold expert load。
  - **可能失效场景**：expert cache 足够大、权重预取做得好、或 expert 高度复用时，距离-延迟相关性会减弱。
- **假设 1：eBPF tracing overhead 可通过 QoS-aware 动态开关 probe 控制在可接受范围。** 当 decode speed 低于 QoS（如 5 tokens/s）时，user-space tracer 写回 BPF map 关闭不必要 probe。
  - **证据强度**：中强。全量 operator tracing 时 BCC 2.8–4%、libbpf 1.7%；仅 token+graph 时 0.1%。但 QoS 策略本身未做系统化 ablation。
- **假设 2：Chrome Trace / Perfetto 生态足以承载 LLM 推理 timeline 分析。** ProfTime 把 sched_switch / sched_wakeup 与 operator 事件转成 Chrome Trace Event Format。
  - **证据强度**：中。对单进程 llama.cpp 有效；多进程 serving、RPC 层、disaggregated prefill/decode 需要额外关联逻辑，论文未覆盖。

## 核心方法

ProfInfer 分 **Tracer**（在线采集）和 **Analyzer**（离线分析）两阶段，围绕 llama.cpp + GGML 栈实现。

**User-space tracer** 负责编译/加载 BPF 程序、按配置文件设置 flag、attach uprobe/uretprobe/tracepoint，并轮询 kernel ring buffer 或 perf buffer。收到事件后异步处理，并可写回 BPF map 动态控制 probe——例如在 decode speed 跌破 QoS 时关闭 operator structure tracing 或 PMC 读取，把 overhead 换回去。

**Kernel-space probe handlers** 记录 thread ID、CPU ID、timestamp；部分 handler 解析 C struct 参数（如 `ggml_tensor`）提取 operator 类型、name、tensor 维度与 source 指针，从而重建计算图拓扑。Ring buffer 更高效但可能丢事件；perf buffer 可感知 missing events，代价是更高内存开销。

**多粒度 tracing**：
- **Token 级**：probe `llama_decode` 的 enter/return，差值得 prefill 的 TTFT 与 decode 的 TPOT；也作为 QoS 反馈信号。
- **Graph 级**：probe `ggml_backend_graph_compute_async`，度量每个 backend graph 的执行时间，并提取 16 位 `guid` 识别 backend（CPU / GPU / NPU 分区）。
- **Operator 级**：probe 各 backend 的 `ggml_compute_forward` 变体（CPU、OpenCL、自研 Rockchip NPU），得 per-op 耗时与 tensor metadata。
- **Scheduler 级**：`sched_switch` / `sched_wakeup` tracepoint，过滤 inference 线程，识别抢占与干扰 workload。
- **MoE 级**：probe `ggml_compute_forward_mul_mat_id`，通过两级指针解引用读取 top-k expert ID。

**PMC 集成**：user-space 用 `perf_event_open` 为每线程打开 counter（如 `l3d_cache_refill`、`mem_access`、`stall_backend`），在 operator uprobe/uretprobe 间读差值，把 DRAM 流量、cache miss、stall ratio 绑到单个 operator 上。

**三种 Analyzer 视图**：
- **ProfDAG**：按 thread 排序 raw trace，重建 operator DAG，边来自 tensor source 地址依赖；节点可着色为 execution time、memory bandwidth 等。
- **ProfTime**：导出 Chrome trace，展示 token/graph/operator 时间线与线程调度；支持 Perfetto 可视化 multi-backend 分区与 OpenCL kernel 叠加。
- **ProfStat**：跨 token 长度、per-operator type、MoE expert 激活模式做统计——例如 KQ/KQV 随 context 增长的 step-wise 延迟上升，或 MatMul 复杂度与 runtime 的线性关系。

实现上，Ubuntu 用 BCC（Python 快速原型），OpenHarmony 用 libbpf（C，无 Python 环境）；BCC 与 libbpf 共用同一套 probe 设计。

## 设计取舍

- **非侵入 uprobe 换来 runtime 耦合与可移植性风险**：无需重编译 llama.cpp，但 probe 函数名/参数布局绑定特定 GGML 版本；backend 扩展目前只覆盖 CPU、OpenCL、Rockchip NPU，CUDA/Vulkan 等标为 future work。
- **Kernel-space 解析 struct 降低 user-space 开销，但提高 BPF 程序复杂度**：在 probe handler 里遍历 `ggml_tensor` 能减拷贝，但 eBPF 指令数和 verifier 限制会卡住更深层字段解析。
- **QoS-aware 动态降采样保护 decode 吞吐，但可能丢失瓶颈窗口**：低速率时关 probe 会错过恰好需要细粒度数据的退化区间；论文把「先保 SLO 再保观测」作为明确优先级。
- **PMC per-operator 读数精度高，但语义解释依赖架构手册**：`l3d_cache_refill × 64B` 估算 DRAM 流量在 Cortex-A76 上合理，换 Apple NPU、Adreno GPU offload 或不同 PMU 事件后需要重新校准。
- **可视化生态借 Perfetto/NetworkX，分析逻辑仍在离线 Python**：适合诊断与论文式 case study，离 continuous production observability（告警、SLO dashboard、自动 root-cause）还有距离。

## 实验与结果

**指标、基线与边界**：decode speed degradation；ProfInfer libbpf/BCC，并参照 llama.cpp graph dump 与 ONNX Runtime profiler；Orange Pi 5 Plus/Pro 的全量 operator tracing（§5.1，Table 5）。

- **平台**：Orange Pi 5 Pro / Plus / Ultra（Cortex-A76）、Ubuntu + OpenHarmony、Rubik Pi（Adreno GPU）；模型含 LLaMA3.2-1B、Qwen2.5-1.5B、Gemma2-2B、Qwen1.5-MoE-A2.7B 等。
- **Overhead**：全量 operator tracing 时 decode speed 下降 BCC **2.8%–4%**、libbpf **1.7%**；仅 token+graph tracing 时下降 **0.1%**，该评测中 prefill 无影响。llama.cpp graph dump 为 13%，ONNX Runtime profiler 约 8%，但不是同 engine 的 head-to-head 比较（§5.1，Table 5）。
- **ProfDAG**：三款 dense 模型的 self-attention 子图结构差异可视化；同一中间 tensor 的 MatMul 并不连续执行，揭示 GGML 调度顺序；MatMul 通常是 self-attention 最重算子。
- **ProfTime**：在 LLaMA3.2-1B-F16、llama.cpp、Orange Pi5 Ultra、4 CPU threads 的 timeline 中，MatMul 占 TTFT/TPOT 的 >97%，并显示 intra-operator 而非 inter-operator 并行；该观察不泛化为其他 backend（§5.2.2，Fig.5）。
- **ProfStat / PMC**：Cortex-A76 decode MatMul 中，2 threads 相对 1 thread 显著加快，4 threads 的 stalled backend cycles 超过 **80%**；BLIS 在 4 Cortex-A76 的 prefill 中使 memory access 低 **75%**、速度 **2×**（§5.2.3）。Qwen1.5-MoE-A2.7B-Q4 在 Orange Pi5 Ultra 无法容纳全部 **8.9 GB** 权重、以 mmap 运行时，expert reactivation distance 与耗时近似相关，fault/memory-access 证据指向 disk I/O（§5.2.3）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| decode tracing 开销在被测设置中较低 | BCC 2.8%–4%，libbpf 1.7%，token+graph-only 0.1% | Orange Pi5 Pro/Plus、全量 operator tracing；decode speed degradation | §5.1，Table 5 | high |
| 与两种既有 profiler 的开销对照仅为初步比较 | graph dump 13%，ONNX Runtime 约 8% | graph dump 单 forward 且无 performance data；非同 engine head-to-head | §5.1 | high |
| 一个 llama.cpp CPU timeline 中 MatMul 主导 | TTFT/TPOT 超过 97%；ops 顺序执行、单 op 可多线程 | LLaMA3.2-1B-F16、Orange Pi5 Ultra、4 CPU threads | §5.2.2，Fig.5 | high |
| decode thread scaling 受 memory bandwidth 限制 | 4 threads stalled backend cycles >80%，更多 threads 收益很小 | Cortex-A76、decode MatMul；不泛化为 NPU/GPU | §5.2.3，Fig.11 | high |
| 两个 case study 的诊断有明确边界 | BLIS prefill 2×/75% memory access；mmap MoE 的 I/O 证据 | 4 Cortex-A76 prefill；或 8.9 GB Qwen MoE、Orange Pi5 Ultra、4 active/60 experts | §5.2.3 | high |

## 批判性分析

### 论证链条

论文链条清晰：**measurement 缺口**（LLM IE 缺细粒度非侵入 profiler）→ **eBPF 分层 probe 设计**（对齐 token/graph/operator 语义）→ **PMC + 三视图分析**（把 hardware behavior 绑回算子）→ **case study 证明可诊断真实瓶颈**（KV 增长、线程不均、MoE mmap、backend 选择）。Observation 与 design 的映射直接，evaluation 也围绕这些 claim 展开，而不是堆 unrelated benchmark。

外推风险在于把「llama.cpp on Linux mobile boards」推广为「现代 LLM inference 可观测性通用方案」。论文在 related work 里承认 eInfer 等已做 distributed LLM tracing，但 ProfInfer 的差异化在 operator 语义 + PMC + edge/mobile；它还没有证明同一框架能无缝覆盖 [[vLLM]]/[[SGLang]] 的 continuous batching、[[PagedAttention]] KV 管理、或 cloud-scale multi-tenant serving。

### 假设压力测试

**IE 栈假设**是最脆弱的。ProfInfer 深度绑定 GGML 函数符号与 struct 布局；llama.cpp 版本升级、operator fusion、新 backend 抽象都可能让 probe 失效。论文把「applicable to similar runtime architectures」作为愿景，但实验只严格验证 llama.cpp。

**Batch=1 edge 假设**也限制结论外推。所有 MatMul 分析默认 decode 时 \(M=1\) 的 matrix-vector 形态；若迁移到 batch serving 或 [[Continuous-Batching]]，operator 耗时分布、线程均衡和 memory-bound 判断都会变。ProfTime 观察到的「无 inter-operator 并行」是 llama.cpp 调度特性，不是 LLM 推理普遍规律。

**PMC 解释在 heterogeneous offload 下会断裂**。OpenCL backend 需要额外开启 `GGML_OPENCL_PROFILING` 并与 eBPF 时间线手工对齐，因为 kernel 异步入队；NPU backend 的 operator 耗时来自 tracer，但 NPU 内部 PMU 未集成。论文证明了「能看分区」，尚未证明「能统一比较所有 backend 的真实瓶颈」。

**MoE 结论依赖极端 memory pressure**。Qwen1.5-MoE 8.9GB 权重 + mmap 是合理的 edge stress test，但 expert distance ↔ latency 规律在 SSD 更快、expert cache 更大或 routing 更稳定的部署里未必成立。

### 实验可信度

优点：overhead 测量用 bpftool 分 probe 成本，区分 BCC/libbpf、ring vs perf buffer、structure tracing vs PMC 等 flag，不是只报一个端到端数字。诊断案例覆盖架构差异、线程干扰、KV 增长、线程数 sweep、BLIS prefill 优化、GPU selective offload、MoE disk I/O——展示 profiler 的「能回答什么问题」，而不只是「能跑起来」。

短板：缺少与 eInfer 等 eBPF LLM tracer 的直接 head-to-head；baseline 主要是「无 profiler」和内置粗粒度工具，而非最强的 commercial / server-side observability stack。平台以 ARM SBC 为主，对主流 Android/iOS on-device 栈（NNAPI、CoreML、ExecuTorch delegate 等）没有端到端验证。ProfStat 的「decode 速度可预测」结论来自特定 hyperparameter 下 MatMul 线性拟合，未测试长上下文、[[Speculative-Decoding]] 或 dynamic batching 下的预测误差。

### 系统性缺陷

论文未讨论 **production 运维面**：trace 存储量、长时间 profiling 的 ring buffer 背压、多租户下 eBPF 权限、probe 误开导致 QoS 违反的 blast radius、以及 analyzer 流水线自动化。QoS-aware probe 切换逻辑是亮点，但没有 eval「切换阈值如何设定才不误关关键事件」。

**正确性与安全**也未展开：uprobe 挂在热路径上，BPF verifier 失败或 handler bug 可能拖垮 inference；论文只报 overhead，未测 fault isolation。

**可扩展 backend** 仍处早期：仅 CPU/OpenCL/Rockchip NPU；对 CUDA、Metal、Vulkan、专用 NPU 驱动的通用 probe 策略未给出。OpenHarmony libbpf 版本「部分 feature 仍不支持」，说明跨 OS 一致性尚未完成。

## 局限与后续工作

- **局限 1：runtime 绑定 llama.cpp/GGML。** 换 IE 或大幅重构 GGML API 后需重做 probe 选点与 struct 解析；论文未提供自动化 discover/probe 生成机制。
- **局限 2：heterogeneous backend 的观测不统一。** OpenCL 依赖 built-in profiling flag；NPU/GPU 内部 counter 未纳入统一 PMC 模型，跨 backend 比较仍半手工。
- **局限 3：分析偏 offline case study。** ProfDAG/ProfTime/ProfStat 适合工程师手工诊断，不是 continuous profiling + alerting 平台；长 trace 的存储、查询、版本化论文未讨论。
- **Future work 1**：基于 operator-level 结果做 decode 阶段 **inter-tensor parallelism** 的 graph partitioning，跨 heterogeneous backend 挖掘 llama.cpp 当前缺失的并行度。
- **Future work 2**：结合 memory bandwidth benchmark（Mempol 类工具）标定 hardware performance limit，把 ProfStat 的「可预测 decode 速度」从拟合外推升级为 bound-aware 预测。
- **Future work 3**：用 token-level TTFT/TPOT 反馈做 **runtime resource allocation**（多并行 workload 下的 CPU/NPU 绑定），而不只是关闭 probe。
- **Future work 4**：扩展到 [[Speculative-Decoding]]、dynamic pruning（PowerInfer 类）等动态 workload，验证 probe 切换策略是否跟得上执行路径抖动。

## 相关

- **相关概念**：[[KV-Cache]]、[[MoE]]、[[Speculative-Decoding]]、[[Quantization]]、[[Attention]]、eBPF、PMC、on-device inference
- **同类系统**：ONNX Runtime profiler、TensorRT profiler、eInfer、eGPU、MNN、llama.cpp built-in graph dump
- **相邻系统**：[[vLLM]]、[[SGLang]]、ExecuTorch、MNN-LLM、mlc-llm
- **同会议**：[[MLSys-2026]]
