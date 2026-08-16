---
type: paper
name: StriaTrace
full_title: "StriaTrace: Efficient Tracing and Diagnosis for Online LLM Inference (Operational Systems)"
authors: [Haonan Wu, Yanqing Chen, Kun Qian, Xue Li, Jingbo Xu, Erci Xu, Ennan Zhai, Wenyuan Yu, Guangtao Xue, Jingren Zhou]
venue: OSDI
year: 2026
tags: [llm-inference, distributed-tracing, performance-diagnosis, observability, production-system]
source_pdf: "[[osdi26-wu-haonan.pdf]]"
source_md: "[[osdi26-wu-haonan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# StriaTrace：在线 LLM 推理的低开销追踪与诊断（OSDI 2026）

> **原题**：StriaTrace: Efficient Tracing and Diagnosis for Online LLM Inference (Operational Systems)

> **一句话总结**：在线 [[LLM-Inference|LLM 推理]]的偶发慢 token 既难复现，又不能承受 full profiler 的持续开销；StriaTrace 只埋同步边界和语义关键路径，只记录 GPU kernel/memory-copy，并用按 token 数拟合的 P99 roofline 只保留异常 step 的完整 trace，在高并发下把完整 tracing 的 median TPOT/TTFT overhead 压到 0.6%/0.8%，且已连续 6 个月覆盖 1700 多个实例、每天 1.8 亿次请求，辅助定位 19 类根因。

## 问题与动机

在线生成既看首 token 时间（Time To First Token，TTFT），也看逐 token 时间（Time Per Output Token，TPOT）。论文所在平台常用的 SLO 约为 TTFT 5–10 s、TPOT 50–100 ms。一次 request 又可能经过 distributed prefix cache、prefill/decode disaggregation、[[Tensor-Parallelism]] 和 [[Expert-Parallelism]]；一个 rank 的 CPU stall、KV I/O、collective 或 GPU kernel 变慢，都可能让整次输出越过 SLO（§1–§2、图 1）。

作者先分析一个超过 2000 个 instance、每天 1400 万次 request 的 commercial chatbot。大多数 request 的平均 TTFT 为 3.06 s、TPOT 为 24.83 ms，但 P99 波动大并持续越过 10 s/100 ms；5.34% request 违反 TTFT SLO，1.18% token 违反 TPOT SLO（§1、§3.1、图 2）。这里的异常不是“prompt 更长所以更慢”，而是在 token count 等实际计算量相同后，仍明显偏离历史 latency 分布的 system-induced stall。

现有工具卡在两个方向。Nsight Systems、[[PyTorch|PyTorch]] Profiler、Neutrino 等能给细 trace，却会订阅大量 CPU/CUDA API 和 GPU event，持续在线使用的 latency、bandwidth 与存储成本过高。Aegis、Mycroft、Minder、PerfTracker 等训练诊断系统则依赖固定 batch、静态 graph、BSP peer comparison 或秒/分钟级持续 straggler；它们很难抓住异步 inference 中只出现一次的慢 token（§3.2、表 1）。

StriaTrace 的目标不是自动修复，也不是宣称单凭一个 classifier 就给出唯一根因。它要成为 always-on 的 flight recorder：常态只付很小成本，异常发生时保留能让 SRE 从 request 一直下钻到 Python line 或 CUDA kernel 的上下文。

## 关键观察 / 隐含假设

- **观察 1：决定请求推进的同步边界远少于实际函数调用。** Qwen2.5-0.5B 的一个 step 中，EngineCore 有 182 类、超过 10000 次 function call；prefill/decode worker 分别有 493/284 类、3588/953 次 call。StriaTrace 只需 13 个 EngineCore span 与 32 个 worker span（§5.2.1、表 2）。
  - **设计含义**：先埋 EngineCore↔GPUWorker RPC、external KV connector 等必须等待的边界，再把边界间的 `schedule`、`execute_model`、`sample_tokens` 分成少量 semantic span。
  - **可能失效场景**：真正的 stall 若发生在未埋点的 non-critical background path，却通过共享 lock、memory pressure 或 queue 间接影响主路径，只看边界只能看到结果，未必直接看见原因。
- **观察 2：GPU kernel 的时间密度已经能区分 CPU-bound 与 GPU-bound。** Kernel 稀疏、有 bubble，说明 CPU 没能及时 launch；kernel 紧密相连，说明 GPU execution 在 critical path。因而可以不记录每个 CUDA Runtime/Driver API（§5.3.1、图 6）。
  - **依赖假设**：Inference execution 的 host→kernel dependency 足够确定，且 non-critical stream、asynchronous memcpy、multi-stream overlap 不会让 bubble 的含义模糊。
- **观察 3：完整 GPU trace 很大，但真正要长期保留的异常很少。** Qwen3-Coder-30B 的每个 worker 每 step 约 1600 个 kernel record；12 ms/step、8 GPU 时 raw trace 达 3.54 GiB/min，若扩到 10000 GPU 约需 590 Gbps（§5.3.2）。
  - **设计含义**：本地先记录，normal step 只留 aggregate，roofline 判成 outlier 时才保存 full-fidelity trace；传输量约为 raw stream 的 1.6%。
  - **风险**：若 detector 漏报，最关键的 trace 会被永久丢弃；论文只测两类 injected fault 的 recall，没有 production false-negative 估计。
- **观察 4：同一 serving instance 内，step latency 与处理 token 数高度相关。** 生产数据上 P99 boundary 的 linear fit 达到 `R²=0.98`，比固定 latency threshold 更能区分“工作多”与“系统异常”（§5.4.1、图 7）。
  - **依赖假设**：Token count 是主解释变量；batch composition、prefix hit、MoE routing、speculative acceptance、parallel topology 和背景争用的剩余影响不会经常越过边界。
- **观察 5：Correlation 的价值是缩小搜索空间，不是自动证明因果。** 生产表 4 的一些问题能精确到 Python line/kernel，另一些只到 general GPU、random CPU；持续退化甚至可能被 roofline 当成新常态（§6.4）。
  - **证据强度**：强。作者明确把 StriaTrace 定位为 rapid triage，而不是 end-to-end root-cause oracle；约 7% 被 flag 的生产异常最后被判为自然 workload variance。

## 核心方法

### 1. Instance-local collector 与集中分析

每个 serving instance 是一个多 GPU 的 [[vLLM]] process group，包含 EngineCore 与多个 GPUWorker。StriaTrace 在每个 instance 同机运行 collector，采集三类信息：CPU semantic span、GPU kernel/memory transfer，以及 request ID、经过的 instance ID 等 causal metadata。异常 trace 发送到集中 backend，按 request 重建跨 prefill/decode instance 的执行链，再生成给 SRE 的报告（§5.1、图 4）。

### 2. CPU 侧：同步点、语义 span 与按需下钻

粗粒度 instrumentation 先覆盖两类 barrier：inference engine 内 API server、EngineCore、GPUWorker 之间的 cross-process RPC；主 event loop 对 distributed [[KV-Cache]] 等外部 component 的 synchronous call。两个 barrier 之间再用少量 span 表示 scheduler、model forward、sampling，并附 batch request 数、token status、KV allocation 等 context（§5.2.1、表 5）。

粗 span 只能说“`model_forward` 慢了”。StriaTrace 同时用 py-spy 每 10 ms 非阻塞读取 Python process memory，取得 thread stack 与 GIL owner；把长 span、GPU bubble 和 stack sample 对齐后，可以区分主线程在计算、被 background thread 抢 GIL，还是停在具体 Python function（§5.2.2、图 5）。10 ms sampling 适合持续几十毫秒的 long tail，但可能漏掉短而频繁的 micro-stall。

作者试过标准 OpenTelemetry Python exporter，发现 background thread 在 batch serialization 时持 GIL，可让主 inference thread 停顿超过 100 ms。StriaTrace 改在 CPU launch 完异步 kernel、等待 GPU 的窗口主动 flush，尽量把 serialization/I/O 藏在 GPU execution 后面（§5.2.3）。

### 3. GPU 侧：只保留硬件执行区间

通过 CUPTI，系统只订阅 GPU kernel 与 memory transfer 的 start/end timestamp，不采 CUDA Runtime/Driver API。Kernel 间 bubble 与 CPU semantic span 对齐后可判断 host starvation；packed kernel 则可把异常进一步归到某个 kernel、collective 或 copy。Kernel mangled name 也被保留，因此能比较 template instantiation，而不只是一个模糊的 operator name（§5.3、图 6）。

每个 step 完成后，本地 detector 决定数据命运：normal step 丢弃完整 kernel record，只保留 aggregate；outlier 才把 full trace 持久化并上传。这个设计减少的是传输/存储，不代表正常 step 完全没有本地采集成本。

### 4. 每个 instance 自适应的 P99 roofline

系统在 serving 初期收集 `(processed_tokens, step_latency)`，对每个 token count 求 minimum、median 和 P99，再用 robust linear regression（例如 RANSAC）拟合 P99 line。Line 上方是 outlier zone。模型在运行中周期重训；prefill 和 decode 各自使用同样的 collect-fit-update 流程（§5.4.1、图 7）。

这不是传统按 FLOPS/bandwidth 算出的 theoretical roofline，而是经验 latency 上界。优点是不必为每个 model、GPU、TP/EP 和 P/D topology 手工建模；缺点是 baseline 从历史数据学习，若启动时已经慢，或长期 regression 被逐渐纳入 retraining，模型可能不报警。

### 5. 三层时间线与 suspect correlation

异常报告在 Perfetto 中提供三层 timeline：Request layer 看排队、TTFT/TPOT 与跨 instance 生命周期；Framework layer 看 vLLM scheduler、KV block、worker coordination；Kernel layer看 GEMM、[[Attention|Attention]]、[[PCIe|PCIe]]/NVLink transfer（§5.4.2、图 8）。

Analyzer 找 latency 占比最大的 semantic span，把它和 py-spy stack/GIL status 对齐，并标出时间异常的 GPU kernel。系统因此给 SRE 一组 primary suspects 与完整现场，而不是只给“GPU utilization 下降”的 metric，也不会自动替人完成最后的因果确认。

## 设计取舍

- **关键路径 coverage 换低 overhead。** CPU 静态 span 数不到单个 step 中 function call 数的 1%，GPU 不记录 CUDA API；这足以看论文目标中的 long stall，却可能漏掉非关键 thread、driver/runtime API 与短 micro-stall。
- **10 ms sampling 换较低 GIL/CPU 干扰。** Sustained stall 容易抓到，短事件可能落在 sample 之间；持续 regression 可离线加点，但不是一次 trace 就必然定位。
- **异常保留换 storage 可控。** 只上传 outlier 把数据降到 raw 的约 1.6%，代价是 detection 与 evidence preservation 强绑定；false negative 无法事后补采。
- **经验 roofline 换配置通用性。** 自动 fit 省掉分析模型，却会受 cold start、concept drift、稀少 token bucket 和异常污染；持续 degradation 还能被吸收成 baseline。
- **Correlation 换人工可审计。** 报告能指出 dominant span/kernel，但多个共同原因可能同时相关；最终 root cause 和 mitigation 仍由 SRE 确认。
- **vLLM 深度集成换移植成本。** py-spy 与 CUPTI 较通用，几十个 CPU span 随 framework critical path 变化而维护。作者称 6 个月里只遇到一次 major shift，但这仍是版本绑定的工程工作（§8）。
- **NVIDIA 生态换当前可部署性。** GPU tracing 依赖 closed-source CUPTI；论文讨论 ROCTracer port，但没有 AMD 实现或实验。

## 实验设计

受控实验在一台 production-grade server 上进行：双路 160-core Xeon、1.3 TiB DDR5、8×NVIDIA H20-3e 144 GiB、NVLink，Ubuntu 24.04、Python 3.12.3、PyTorch 2.7.0、CUDA 12.8。模型是 Qwen3-Coder-30B-Instruct-[[Quantization|FP8]] [[MoE]]；两个 TP=8 的 prefill/decode instance 通过 distributed KV cache 相连。vLLM benchmark 用固定 input/output length、Poisson arrival 8 req/s，并把 max concurrency 从 8 扫到 256（§6.1–§6.2）。

Baseline 是无 instrumentation 的 vLLM。比较对象包括关闭 CPU backtrace 的 Nsight Systems（NSys）、vLLM 内置 PyTorch Profiler（TProf）、10/100 ms sampling 的 Scalene，以及 Stria-C（CPU only）、Stria-G（GPU only）和完整 StriaTrace。TTFT 在 prefill instance 测，TPOT 在 decode instance 测。

## 实验与结果

- **CPU-only 的 TPOT overhead 在所有设置都低于 1%，full system 在低并发并非如此。** Concurrency 8 时，TProf 让 median/P99 TPOT 增加 83.6%/84.1%，NSys 增加 34.3%/32.0%，Scalene 10 ms 增加 21.4%/111.8%；Stria-C 的 median/P99 TPOT 在所有 concurrency 都严格低于 1%（§6.2、图 9a）。正文没有对 Stria-C 的 TTFT 给出同样的逐点百分比结论。
- **GPU instrumentation 需要吞吐摊销。** 完整 StriaTrace 的 median TPOT overhead 从 concurrency 8 的 5.2% 降到 concurrency 256 的 0.6%；median TTFT 从 2.7% 降到 0.8%。同一低并发点，TProf 让 median/P99 TTFT 达 baseline 的 3.0×/3.2×，NSys 增加 4.7%/6.3%（图 9）。因此论文摘要“consistently below 1%”只符合高并发或 CPU-only 结果，不符合 full StriaTrace 的低并发点。
- **Trace footprint 比 full profiler 小一到三个数量级。** 8 req/s 下，完整 StriaTrace 的 prefill/decode 生成率为 3.19/2.75 GiB/h；NSys 为 123.7/1003.2，TProf 为 489.2/274.9 GiB/h。Decode 上 NSys/TProf 至少是 StriaTrace 的 38×；正常 step 丢弃 full kernel trace 后，传输量约为 raw stream 的 1.6%（§5.3.2、§6.2、表 3）。
- **两类 fault injection 的 recall 是 100%，但没有完整 accuracy。** TP=4 cluster 稳定 fit 后，作者随机暂停一个 worker（SIGSTOP）或注入高优先级 kernel 占满 GPU SM；两类 injected step 都越过 roofline，recall 100%（§6.3、图 10）。实验没有报告 injected sample 数、detection delay、precision 或弱故障阈值；production flag 中约 7% 后来属于自然 variance（§6.4）。
- **生产规模支持“always-on 可用”，但 diagnosis 深度不一。** StriaTrace 连续 6 个月监控两个 flagship service 的 1700 多个 instance，每天处理超过 1.8 亿 request，覆盖 TP/[[Data-Parallelism|DP]]、monolithic 和 P/D disaggregated deployment；累计诊断数百个异常，归为 6 类 hardware、5 类 configuration、8 类 code root cause，共 19 类。表 4 中多数能 precise localization，GPU clock/temperature、CPU frequency、HugePage/CUDA Graph 等只能到 general/random CPU/GPU（§6.4、表 4）。
- **Case study 证明 trace 能越过 CPU/GPU 边界。** Case 13 中，稳定 decode step 偶发从 75 ms 跳到超过 160 ms，rank 1 出现约 80 ms kernel bubble；py-spy 找到 `make_ndarray_with_pad` 的 Python list/NumPy allocation，C++ preallocated operator 把该 function 的 P99 从 110 ms 降到 43 ms。Case 17 从一周 400 多个 commit 中找出 [[Flash-Attention]] build 漏编 `(64,128,128)` tile、退回 `(128,128,128)`；在 H20、只剩 30% SM 可用时 kernel 为 147.7 µs 对 216.8 µs。系统还借 batch metadata 找到 [[Speculative-Decoding|speculative decoding]] 中被额外送去 verify 的 “ghost token”（§7、附录 C）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 只追踪同步点和 hardware event 能显著降低 tracing cost | 表 2、图 9：CPU-only 的 TPOT 少于 1%；full system 高并发 TPOT/TTFT 为 0.6%/0.8% | 单台 8×H20、Qwen3-Coder-30B、固定长度与 8 req/s | 强 |
| Anomaly retention 使 full-fidelity trace 可持续存储 | §5.3.2、表 3：full Stria 2.75–3.19 GiB/h，normal-step filtering 留 raw 的约 1.6% | 异常率与 production distribution 相关；backend peak 未压测 | 强 |
| Token-conditioned P99 roofline 能检测突发 CPU/GPU stall | 图 7、图 10：`R²=0.98`，两类 injection recall 100% | 两种强 synthetic fault、TP=4；没有 false-negative/弱故障 sweep | 中到强 |
| Cross-layer correlation 能把部分异常定位到代码/kernel | §7、附录 C：sampling P99 110→43 ms，FA tile mismatch，ghost token | 三个深描案例；最终确认仍依赖 SRE/offline reproduction | 强 |
| 系统能在大规模生产持续运行 | §6.4、表 4：6 个月、1700+ instance、1.8 亿 request/day、19 类 root cause | 两个 Alibaba service、vLLM/NVIDIA stack；无外部 trace/artifact | 中到强 |

## 批判性分析

### 论证链条

三条原则与三类成本一一对应：同步点/semantic span 减 CPU event，hardware-only 减 CUPTI event，roofline filtering 减 network/storage；图 9 和表 3分别验证 latency 与 data volume。Fault injection 再证明 detector 能保住明显的 host/device stall，生产案例说明保存下来的上下文确实能缩小根因范围，机制—证据链完整。

Headline 需要更精确。摘要与结论称 tracing overhead “consistently below 1%”并比 alternative 少 97.8%，但 §6.2 明确给出 full StriaTrace 在 concurrency 8 的 median TPOT 5.2%、median TTFT 2.7%；严格低于 1%的是 Stria-C，或高 concurrency 下摊销后的 full system。论文也没有把“97.8%”绑定到一个固定 baseline、metric、percentile 和 concurrency，读者不应把它当成所有部署点的统一保证。

### 假设压力测试

Linear P99 roofline 只用 processed token count。Prefill 的 cache hit/miss、decode batch shape、MoE expert skew、speculative acceptance、quantization kernel、TP/EP collective 与 multi-tenant interference 都会让相同 token 数有不同合法 latency。Per-instance fit 与周期更新能吸收常态差异，却也可能增加 false positive，或把慢慢发生的 regression 学成新 baseline。论文自己指出 CUDA Graph 从启动就被误关时不会报警。

“Kernel bubble=CPU bottleneck”在单 main stream 很直观；multi-stream overlap、async copy、host callback、GPU scheduling/preemption 或 driver queueing 下，bubble 可能有多种原因。不记录 CUDA API 是必要取舍，但也意味着 driver/runtime anomaly 只能靠时间关系推断，不能直接观察。

Anomaly-only persistence 把正确性压在 detector 上。强 SIGSTOP/SM saturation 的 100% recall 不代表短 GIL pause、intermittent PCIe retry、单 collective rank jitter 或刚好位于 roofline 下方的 SLO violation也会被保留。需要 shadow sampling 或随机保留 normal trace，才能估计 production false negative。

### 实验可信度

H20、30B MoE、TP=8、P/D disaggregation、Poisson load、median/P99、CPU/GPU-only split、六种 profiler config、data volume、fault injection 和 6 个月 production evidence，覆盖面很强。作者还公开 7% natural-variance flag 和持续 degradation 漏报机制，负面结果有价值。

但 controlled test 只有一个 model、一个 8-GPU node、固定 input/output length 和固定 8 req/s。Concurrency sweep 会同时改变 throughput 与 queue behavior，所以“overhead amortizes”不能直接外推到不同 arrival rate、dynamic length 或 SLO saturation point。没有 A100/H100、不同 TP/EP、prefix hit ratio、monolithic vs P/D 的 overhead matrix。

Detection 只测两类很强的 synthetic anomaly，并只报 recall；没有 injection count、fault duration/intensity sweep、time-to-detect、precision、root-cause top-k accuracy 或和其他 detector 的比较。Production 的“数百异常/19类”是有力经验，但没有总 alert 数、false negative audit、MTTD/MTTR 改善和 incident severity distribution。

### 系统性缺陷

CPU semantic span 深度绑定 vLLM internal critical path。作者认为埋点只有几十个且 6 个月仅一次 major shift，但 async scheduler、connector API、custom sampler 与 downstream fork 都可能改变路径；埋点遗漏不会像 compile error 一样明显。论文没有自动 coverage test、版本兼容矩阵或 trace-schema migration。

集中 backend 要接收跨 instance 异常 trace、做 correlation 并存储 Perfetto timeline。论文给单 instance GiB/h，却没有 alert storm、cluster partition、backend outage、backpressure、retention policy 或 query latency。若事故同时影响大量 GPU，1.6% 的常态比例可能瞬间失效。

Trace 含 request ID、token/batch status、stack、kernel name 和跨 instance route。生产系统需要访问控制、脱敏、retention 与 tenant isolation，论文没有讨论隐私和安全边界。Py-spy 读取 process memory、CUPTI attachment 和 instrumentation 本身也扩大了权限面。

## 局限与后续工作

- **局限 1**：Full StriaTrace 在低 concurrency 的 overhead 为 2.7%–5.2%，并非所有点都低于 1%；97.8% headline 没有统一分母。
- **局限 2**：Roofline 主要用 token count，production 约 7% flag 是自然 variance，持续 regression 还可能不触发。
- **局限 3**：Fault injection 只有 SIGSTOP 与 SM contention，且只报 recall；没有 production false-negative、precision 与 detection latency。
- **局限 4**：受控实验只有 Qwen3-Coder-30B、H20、vLLM、固定长度和单节点；AMD/SGLang portability 只在讨论中提出。
- **局限 5**：集中 backend 的 alert-storm scaling、故障恢复、trace privacy 和 retention policy 未评估。
- **后续工作 1**：让 roofline 加入 prefill/decode、batch shape、prefix hit、expert load、speculative acceptance 和 topology feature，并与 token-only model 比较 precision/recall。
- **后续工作 2**：随机保留少量 normal step 作为 audit sample，回放生产 incident，估计 false negative 与被 retraining 吸收的 slow drift。
- **后续工作 3**：扫描 fault type、duration、intensity 和 affected rank 数，报告 MTTD、top-k suspect accuracy、SRE MTTR 与自动 mitigation 的误触发率。
- **后续工作 4**：在 A100/H100/AMD、[[SGLang]]、不同 TP/EP、dynamic sequence 和多租户 load 上重测 overhead 与 detector calibration。
- **后续工作 5**：压测 simultaneous anomaly storm，并给 backend 加 backpressure、durable local buffer、tenant-level access control 与可审计 retention。

## 相关

- **相关概念**：[[LLM-Inference]]、[[KV-Cache]]、[[Prefix-Caching]]、[[Disaggregation]]、[[CUDA-Graph]]、[[Flash-Attention]]、[[Speculative-Decoding]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Nsight Systems、PyTorch Profiler、PerfTracker
- **同会议**：[[OSDI-2026]]
