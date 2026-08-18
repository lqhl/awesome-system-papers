---
type: concept
aliases: [LLM inference, LLM serving, llm-inference, large language model inference, model serving]
parent: "[[LLM]]"
last_updated: 2026-08-18
tags: [llm-inference, serving, systems]
---

# LLM-Inference

> 大语言模型推理（LLM inference）是把模型变成在线或批处理服务的完整系统过程；它要在模型质量不越界的前提下，协调 prefill、decode、状态存放、并行、调度和数据移动，并满足延迟、吞吐、成本、能耗与可靠性目标。

## 核心思想

一个普通文本生成请求先做 **prefill**：一次处理全部输入 token，并为各层生成 [[KV-Cache|KV cache]]；之后做 **decode**：反复读取已有 KV，每步生成一个或少量 token。Prefill 通常计算密集，decode 通常更受权重与 KV 的容量、内存带宽限制，但这只是常见工作区间，不是永远成立的定律。batch 大小、context 长度、attention 形式、量化格式和硬件互连都会移动瓶颈。单 token 输出服务主要只有 prefill，视觉语言模型还可能多出 encode 阶段。

因此，服务端不能只优化一个 kernel。它还要决定请求何时进入、哪些请求组成 batch、长 prompt 是否分块、采用 [[Tensor-Parallelism|张量并行]] 还是 [[Pipeline-Parallelism|流水线并行]]、prefill 和 decode 是否 [[Disaggregation|解聚]]、KV 放在 HBM/主机 DRAM/NVMe 的哪一层，以及失败时由谁继续持有请求和状态。[[Continuous-Batching|连续批处理]]、[[Chunked-Prefill|分块 prefill]]、[[Prefix-Caching|前缀缓存]]和 [[PagedAttention]] 都是在这个控制环里解决不同局部问题。

衡量结果至少要同时报告首 token 延迟（TTFT）、逐 token 延迟（TPOT 或 ITL）、尾延迟、SLO 达成率或 goodput、吞吐、模型质量、每请求能耗与成本。单独提高 tokens/s 可能靠牺牲排队尾延迟、低频请求、公平性或输出质量取得，不能直接推出线上服务更好。

## 为什么重要

LLM 服务的工作集由权重、临时激活和按请求增长的 KV 共同组成。长 context 与高并发会让 KV 先挤满 HBM；低请求率的多模型服务则可能由权重驻留成本主导。把状态移到 CPU 或 NVMe 可以扩大容量，却把 PCIe、NVLink-C2C、NUMA 和网络带宽放进关键路径。[[DirectKV-OSDI26]]、[[ECHO-OSDI26]] 与 [[Strata-OSDI26]] 都做分层存储，但其可成立的硬件和流量条件不同，不能把一个平台上的收益直接外推到另一个平台。

调度同样取决于工作负载分布。prefix reuse、prompt/output 长度相关性、到达突发、取消率、模型冷热度和 SLO 组合，都会改变最优策略。[[KVCacheInTheWild-ATC25]] 与 [[StriaTrace-OSDI26]] 的价值在于给出生产 trace，而 [[DCP-OSDI26]]、[[EcoServe-OSDI26]] 和 [[TriInfer-MLSys26]] 主要在受控或回放环境中验证设计；这些证据互补，但强度和外推范围不同。

最后，低层优化必须保留模型语义。[[Quantization|量化]]、[[Sparse-Attention|稀疏注意力]]、KV 压缩和 [[Speculative-Decoding|推测解码]]都能减少计算或传输，却分别引入精度、召回、接受率和特殊 kernel 约束。论文若只报告系统速度而没有任务质量，就不能证明部署可无损替换。

## 关键观察 / 隐含假设

- **阶段异质性是真实的，但“完全解聚一定更好”不成立。** [[EcoServe-OSDI26]] 在 L20/A800/H100 和 10/25 GbE 等环境里发现，完整 prefill/decode 解聚的 KV 传输与负载不均可能抵消隔离收益；它用部分解聚在共置和完全解聚之间折中。实验使用公开数据集和合成到达、最大到 72B dense model，不是某个超级应用的原始生产 trace。
- **流水线并行的结论受互连约束。** [[DCP-OSDI26]] 在 4×A100 PCIe、Qwen2.5-14B/32B 上，用动态分块 prefill 和 delay scheduling 控制 stage bubble，在设定的 P90 TTFT 2 秒、P90 TPOT 200 毫秒条件下让流水线并行取得较高 goodput。这个结果不能直接推广到 NVLink 域；delay scheduling 还可能让 P99 TPOT 变差约 15%。
- **KV 容量问题与 KV 复用问题不同。** [[DirectKV-OSDI26]] 让 GH200 GPU 经 NVLink-C2C 直接读取 CPU KV，重点是取消 HBM staging；[[ECHO-OSDI26]] 利用原生稀疏注意力减少主机到 GPU 的 KV 搬运；[[Strata-OSDI26]] 则依靠 prefix reuse 管理 DRAM/NVMe 层级。前两者不自动提高 prefix hit，后一种在无复用流量中可能只有额外元数据与 I/O 成本。
- **生产 KV 生命周期并不能由平均 context 长度代替。** [[KVCacheInTheWild-ATC25]] 在 Alibaba trace 中观察到高比例的短生命周期和单轮可复用 KV，并以 trace replay 证明新策略可降低排队 TTFT；但该分布属于所测产品、日期与路由方式，不是通用常数。
- **离线吞吐和在线 SLO 是两类证据。** [[MPK-OSDI26]] 在固定 64-token prompt、1,024-token decode 的离线 batch 上展示 persistent mega-kernel 吞吐，却没有线上 arrival、P99、编译成本和多租户共存数据。相反，[[LMetric-OSDI26]] 和 [[StriaTrace-OSDI26]] 直接观察生产实例，但结论又绑定其部署的模型、硬件与 trace。
- **生产可观测性必须识别“慢”是否只是正常生成差异。** [[StriaTrace-OSDI26]] 覆盖 Alibaba 1,700 多实例、每日约 1.8 亿请求的六个月数据，用 token 数条件化的经验 P99 roofline 区分慢路径；完整 trace 的开销约 2.7%–5.2%，所以高并发实例只采样 0.6% 或 0.8%。它擅长强故障类别，但采样、只持久化异常和约 7% 的自然波动标记都会限制召回与自动处置。
- **编译和静态特化都假设形状或控制流有足够稳定性。** [[ADAngel-OSDI26]] 对固定模型、GPU、shape 和精度做约 5.7 小时离线 profile，并保存多种权重布局；[[EventTensor-MLSys26]] 把动态 shape 和数据依赖表示成事件张量；[[MoonBright-OSDI26]] 加速 GPU 映射建立。三者优化的层次不同，不能用微基准倍数替代端到端 SLO。
- **端侧不是缩小版数据中心。** [[HeteroInfer-SOSP25]] 的 Snapdragon 8 Gen 3 NPU+GPU 共享内存结果受移动 SoC、厂商 runtime、功耗与温控影响；[[ADAngel-OSDI26]] 的 Jetson Orin 结果受任意精度格式和额外权重布局影响。它们证明异构执行有价值，不证明同一策略能直接搬到服务器 GPU。
- **特化 workload 可以获得很大收益，但适用面会缩小。** [[PrefillOnly-SOSP25]] 针对单 token 输出服务去掉 decode 路径；[[TriInfer-MLSys26]] 把多模态请求拆成 encode/prefill/decode；[[Aegaeon-SOSP25]] 只池化低请求率冷模型的 decode。它们的好处来自明确限制 workload，而不是一个适用于所有生成服务的统一调度器。

## 设计空间与取舍

- **请求调度与 batching**：连续批处理提高设备利用率；分块 prefill 限制长 prompt 对 decode 的阻塞；delay scheduling、长度分桶和 SLO admission 能改善某些分位数，却可能推迟被选中的请求。公平性必须作为显式指标，而不是吞吐优化后的副产品。
- **并行与阶段放置**：张量并行需要频繁 collective，流水线并行承担 stage bubble，prefill/decode 解聚要搬 KV。[[DCP-OSDI26]]、[[EcoServe-OSDI26]] 与 [[TriInfer-MLSys26]] 表明，最佳选择由互连、模型大小、请求阶段比例和 SLO 联合决定。
- **KV 管理**：可以做前缀复用、分页、分精度压缩、稀疏读取、CPU/NVMe 卸载或主动备份。[[DiffKV-SOSP25]] 以 token/层差异化压缩换容量和吞吐；[[DirectKV-OSDI26]]、[[ECHO-OSDI26]]、[[Strata-OSDI26]] 分别减少 staging、传输或重复计算。压缩要核对质量，缓存要核对 hit distribution，卸载要核对链路带宽。
- **权重驻留与冷模型池化**：[[Aegaeon-SOSP25]] 用 token 级抢占把多个 6B–14B 冷模型放进共享 decode pool；[[CrossPool-arXiv26]] 在 5×A100 40GB NVLink 上把 MoE 权重池和 KV 池分离。前者的生产 beta 有 47 个模型，后者是低 RPS、decode-only、三模型实验；CPU/SSD 与异构 PCIe 仍是未覆盖区域。
- **量化、编译与 persistent kernel**：量化减少权重和带宽，编译器融合减少中间张量与 launch，persistent kernel 允许跨算子流水。[[ADAngel-OSDI26]] 和 [[MPK-OSDI26]] 展示了专用化上限，也带来 profile、代码体积、调试、故障隔离和硬件可移植性成本。
- **分层内存**：CPU DRAM、统一内存、NVMe 都能扩大有效容量，但“可访问”不等于“足够快”。[[DirectKV-OSDI26]] 依赖 GH200 的 NVLink-C2C，[[Strata-OSDI26]] 的主结果使用 8×H200、约 1.6 TB DRAM，另测 H20+NVMe 与 GH200；容量、NUMA、链路竞争和多租户隔离必须一起报告。
- **可观测性、可编程性与恢复**：tracing 要把 queue、batch、kernel、collective 和 token 进度关联起来；恢复还要明确 request、KV 和已流式输出的所有权。[[StriaTrace-OSDI26]] 解决定位，[[LithOS-SOSP25]] 用 thread-block 级控制和 DVFS 管理尾延迟，[[Pie-SOSP25]] 用 Wasm inferlet 暴露 KV、I/O 与生成控制流；灵活性会增加配额、调试和多租户隔离负担。

## 引用本概念的论文

- [[FlashInfer-MLSys25]]、[[APE-ICLR25]]、[[MagicDec-ICLR25]] — 分别从 attention/KV kernel、并行 context encoding 与 compressed-KV speculation 优化 prefill/decode；收益依赖 shape、reuse、acceptance 和硬件 FLOPS/bandwidth。
- [[XGrammar-MLSys25]]、[[XGrammar2-CAIS26]]、[[Multiverse-NeurIPS25]] — 将结构约束和模型生成的并行控制流纳入 serving runtime；语法/执行加速不等于 agent 语义正确。
- [[Miao-LLMServingSurvey-CSUR26]] — 汇总算法、kernel、runtime 与 distributed serving taxonomy；跨论文数字仍需回原始 workload 核对。
- [[NEO-MLSys25]] — 把部分 decode attention 与 KV 放到本机 CPU；收益随 GPU/CPU bandwidth 比例显著变化。
- [[MoE-Lightning-ASPLOS25]] — 在显存受限 GPU 上联合流水 CPU attention、GPU expert 与权重传输。
- [[LLMQueryReordering-MLSys25]] — 从应用层重排行与字段来扩大 prefix reuse，不改变模型执行语义。
- [[SuperServe-NSDI25]] — 用可即时切换的 SuperNet 子模型处理 burst 下的 latency–accuracy 取舍。
- [[SkyServe-EuroSys25]]、[[SkyWalker-EuroSys26]] — 分别利用跨 failure domain 的 spot 与跨 region 日周期错峰降低 serving 成本。
- [[BlendServe-ASPLOS26]] — 在离线 batch 中联合优化 prefix sharing 与 compute-memory overlap。
- [[Agentix-NSDI26]] — 将调度目标从单 request 提升到完整 agent program 的完成时间。

### OSDI 2026

- [[ADAngel-OSDI26]] — 为 W4A8 等任意精度格式按模型、shape 与 GPU 选择 mpGEMM；Jetson Orin 与 A100 结果不能脱离精度和 profile 成本比较。
- [[DirectKV-OSDI26]] — 在 GH200 上用 NVLink-C2C zero-copy 读取 CPU KV，GPU 内存降到 47 GB；主机链路较弱时结论不成立。
- [[ECHO-OSDI26]] — 为原生稀疏 attention 设计 host KV offload，减少无需读取的 KV；论文没有覆盖大规模多租户 NUMA/PCIe 争用。
- [[ECO-OSDI26]] — LLM 是其代码优化流水线中的模型组件，并非 serving 论文；它只把推理服务作为整个生产系统的一段成本和延迟。
- [[EcoServe-OSDI26]] — 在普通以太网集群上联合实例放置、阶段路由和部分解聚，边界是公开数据/合成到达、L20/A800/H100 与最大 72B dense model。
- [[MoonBright-OSDI26]] — 通过 GPU page-table construction 与 always-fresh VA 降低映射延迟；LLM 应用只在单 A100、7B/8B 模型上测，8.2 倍 TTFT 来自 prefix-cache 场景，无 prefix 时约 5%。
- [[Murakkab-OSDI26]] — 联合选择 workflow 参数、模型、工具、并行与实例；24 小时到达是由 Azure LLM trace 映射出的双 workflow replay，不是原生 agent 平台 production trace。
- [[Spain-OSDI26]] — 让数值程序输出可被简洁证明；LLM inference 只是潜在被验证 workload，核心证据来自数值 kernel 与证明开销，而非在线服务 SLO。
- [[Strata-OSDI26]] — 用 HBM、主机 DRAM 和 NVMe 的层级 context cache 服务前缀复用；主结果在 8×H200，收益取决于复用和 decode bubble 是否足以隐藏 I/O。
- [[StriaTrace-OSDI26]] — 提供 always-on tracing、token 条件化 roofline 和根因分类；覆盖大规模生产部署，但高并发采样和强故障类别限制了未知问题召回。

### 其他会议与预印本

- [[Aegaeon-SOSP25]] — 为低请求率模型池化 decode GPU并做 token 级抢占；实验室配置为 16×H800、6B–14B 模型，生产 beta 是 47 个 H20 模型实例。
- [[CrossPool-arXiv26]] — 对低 RPS MoE 做跨模型权重/KV 池化；证据限于 5×A100 40GB NVLink、三个冷模型和 decode-only。
- [[DiffKV-SOSP25]] — 按层和 token 重要性差异化压缩 KV，报告 2.7–5.7 倍压缩与 1.9–5.4 倍吞吐；线上评分、compaction 开销与长尾质量仍需单独验证。
- [[EventTensor-MLSys26]] — 用事件张量表达动态跨 kernel 依赖；在 8×B200 环境中低 batch decode 相对 vLLM 最高 1.48 倍，但多 GPU TP 端到端只与 vLLM 持平且未评测 P99。
- [[HeteroInfer-SOSP25]] — 在 Snapdragon 8 Gen 3 的 GPU+NPU+统一内存上协同执行十亿参数级模型，属于移动端高精度 regime。
- [[KVCacheInTheWild-ATC25]] — 用 Alibaba trace 测量 prefix hit、KV 生命周期和排队，并验证 cache policy；结论应按所测产品和 replay 比例解释。
- [[LLMSteer-NeurIPSW24]] — 以 2×A40、Llama-3.1-8B 和不超过 10K context 研究 attention steering；假设输入 KV 已预计算并驻留 GPU，且是 workshop 规模证据。
- [[LithOS-SOSP25]] — 以 thread-block atomization、调度和 DVFS 控制 inference 隔离与尾延迟；依赖 NVIDIA 执行细节和逆向接口。
- [[Pie-SOSP25]] — 用 Wasm inferlet 编排 KV、sampling、tool I/O 和生成控制流；Llama-3 1B/3B/8B 普通 completion 的 TPOT 比 vLLM 高 2.39%–11.41%，复杂 workflow 的收益来自应用可表达性。
- [[PrefillOnly-SOSP25]] — 针对单 token 输出的 prefill-only 服务去掉通用 decode 开销，不能代表聊天式长输出。
- [[TriInfer-MLSys26]] — 在 32×H20 上拆分多模态 encode/prefill/decode，90% SLO 下最高 2.4 倍；使用 7B 模型、固定输出长度，并关闭 prefix cache 与 CUDA Graph。

## 已知局限 / 开放问题

- 建立同时报告 P50/P99 TTFT、TPOT、goodput、质量、能耗和 GPU 成本的统一实验协议，并公开 prompt/output、到达、取消与 prefix reuse 分布。
- 在 burst、扩缩容、故障和请求取消下定义 request、KV 与已输出 token 的一致性和接管协议；“服务恢复”不能只等同于重新加载权重。
- 自动识别当前 hardware/workload regime，再在共置、完全解聚、部分解聚、TP 和 PP 之间切换；切换本身的状态迁移成本必须计入 SLO。
- 为量化、稀疏和 KV 压缩建立分任务、分模型的尾部质量守护，而不是只比较平均 perplexity 或少量 benchmark。
- 建设可共享、可匿名化的 production trace 与根因 corpus，同时量化采样造成的漏报、自然生成波动和自动处置误伤。
- 验证新 GPU、CXL/统一内存、异构加速器与慢存储组合下的性能模型是否仍准确；单一 superchip 或单机实验不足以推导多租户集群行为。
