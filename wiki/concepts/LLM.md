---
type: concept
aliases: [LLM, large language model, Large Language Models, foundation model, LLMs]
last_updated: 2026-07-25
tags: [llm-inference, llm-training, foundation-model, agents, serving]
---

# LLM

> **Large Language Model（LLM）** 是以 Transformer 为核心的自回归语言模型，在系统论文中既是 **工作负载对象**（训练/推理/serving 的资源与 SLO 约束），也是 **系统组件**（代码生成、规划、检索、验证的算子）。本 wiki 中引用 [[LLM]] 的论文横跨 serving runtime、分布式训练、agentic AI、auto-research 与形式化/可验证系统——几乎构成 MLSys/OSDI/SOSP 近年系统创新的共同锚点。

## 核心思想

从 **workload** 视角，LLM 把系统瓶颈从「单次 matmul」推进到 **长序列、大状态、异构阶段** 的组合问题：训练侧是 [[Tensor-Parallelism]]/[[Pipeline-Parallelism]]/[[Data-Parallelism]]/[[Expert-Parallelism]] 混合并行下的通信与 bubble；推理侧是 [[KV-Cache]] 主导的内存、[[Continuous-Batching]] 下的调度、prefill/decode 两阶段算力特征差异（[[Disaggregation]]）。模型规模从 7B 到 671B、context 从 4K 到 1M，使 **内存层次、网络带宽、尾延迟** 成为一等公民，而非 GPU FLOPs alone。

从 **component** 视角，frozen 或 API 调用的 [[LLM]] 被嵌入更大系统：[[SysSpec-FAST26|SysSpec]] 用其生成文件系统实现；[[FunSearch-Nature24|FunSearch]] 将其当进化算子；[[AgenticCache-MLSys26|AgenticCache]]、[[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] 缓解 agent 规划/记忆瓶颈；[[METIS-SOSP25|METIS]] 用 profiler LLM 剪枝 [[RAG]] 配置。这些论文共同假设：**LLM 的延迟、成本与非确定性不是应用层细节，而是系统架构的硬约束**。

适用边界：本概念页聚合的是 **系统论文语境下的 LLM**——训练栈、serving 栈、agent 栈、科学发现管线——而非模型算法本身（架构搜索、对齐、能力评测）。当论文仅把 LLM 当黑盒 API 时，系统贡献往往在缓存、调度、并行或验证层。

## 为什么重要

LLM 是近年系统会议论文密度最高的 workload 类别之一（本 wiki 当前有 **70 个 paper 页**直接引用该概念）。原因有三：

1. **资源形态新**：单请求 [[KV-Cache]] 可达 GB–TB；MoE 引入 [[Expert-Parallelism]] 与权重 paging；MLLM 双组件结构制造 48% 级 pipeline bubble（[[Optimus-ATC25|Optimus]]）。传统「算力优先」调度失效。
2. **部署形态碎**：从 hyperscale GPU 集群（[[Greyhound-ATC25|Greyhound]] 10K+ GPU）到 consumer GPU TTC/beam search（[[LocalityAwareBeamScheduling-MLSys26]]）、移动端 [[llama.cpp]]（[[CORE-MLSys26|CORE]]），同一抽象需跨 orders-of-magnitude 的资源与 SLO。
3. **正确性与信任**：分布式训练 silent bug（[[TrainVerify-SOSP25|TrainVerify]]）、Tensor Core 非确定性（[[Hawkeye-MLSys26|Hawkeye]]）、LLM 幻觉与 evaluator 过滤（[[FunSearch-Nature24|FunSearch]]）把 **可验证性、可复现性** 推入系统议程。

这些论文共同假设：LLM 生命周期（pre-train → SFT → serve → agent loop）的每一环都有独立系统问题，且 **inference serving 与 training 的最优并行/内存策略不可互换**（[[Meta-LLM-Deploy-MLSys26]]、[[FlexTrain-MLSys26|FlexTrain]] 的 PP-vs-DP 弹性取舍即为例证）。

## 关键观察 / 隐含假设

- **观察 1：LLM 推理/memory 对象（KV cache、权重、agent 记忆）往往先于算力成为吞吐与 SLO 瓶颈。** [[SuperInfer-MLSys26|SuperInfer]] 测得 GH200 上 PCIe offload 仅用到 NVLink-C2C <5% 峰值；[[AgenticCache-MLSys26|AgenticCache]] 显示具身 agent 中 LLM 查询占仿真 **>70%** 延迟；[[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] 报告 agent 记忆检索占端到端 **47–85%**。
  - **依赖假设**：自回归 decode 或离散 plan 循环使 **单次 forward 成本 × 调用次数** 主导；batch 并发或缓存命中可摊薄但无法消除 API/内存墙。
  - **可能失效场景**：极小模型本地亚秒级推理、或 workload 已高度 batch 化且 prefix 共享极高时，算力或网络再次成为主瓶颈。

- **观察 2：LLM 作为系统组件时，「生成质量」必须靠外部约束（spec、evaluator、profiler）闭环，不能假设单次 forward 可信。** [[SysSpec-FAST26|SysSpec]] 用 Hoare logic + rely-guarantee spec 约束生成；[[FunSearch-Nature24|FunSearch]] 用可执行 evaluator 过滤幻觉程序；[[METIS-SOSP25|METIS]] 用 profiler LLM 估计 query 复杂度再剪枝 RAG 配置。
  - **依赖假设**：存在可形式化或快速打分的任务边界（文件系统语义、数学构造、QA 质量）；frozen LLM 足够当 **变异/估计算子**。
  - **可能失效场景**：开放域创意任务无可靠 evaluator；spec 错误被放大为系统性缺陷（[[SysSpec-FAST26|SysSpec]] 承认 debug 需回溯 spec）。

- **观察 3：LLM 训练/推理的并行与弹性策略对数值一致性敏感——DP 扩缩与 PP 扩缩不可等价。** [[FlexTrain-MLSys26|FlexTrain]] 指出 DP 扩缩破坏 gradient 累加顺序，PP 扩缩可保 bitwise 一致；[[DreamDDP-MLSys26|DreamDDP]] 在 geo-DDP 上用 partial parameter sync 换通信重叠，收敛率需单独论证。
  - **依赖假设**：同步训练、固定 global batch 语义下，operator 顺序与 collective 拓扑是正确性的一部分。
  - **可能失效场景**：故意异步（Local SGD、DiLoCo）或弹性 DP 被接受为算法 trade-off 时，系统目标从「bitwise 一致」转向「统计等价」。

- **观察 4：LLM workload 的非确定性（硬件 + 软件）阻碍可验证 serving/training。** [[Hawkeye-MLSys26|Hawkeye]] 显示同输入在不同 GPU 上 Tensor Core MMA 可 bit 不同；[[TrainVerify-SOSP25|TrainVerify]] 针对 parallelization plan 的 silent bug 提供等价性验证，但不覆盖 runtime NCCL 行为。
  - **依赖假设**：审计粒度可落在 MatMul/MMA 或 execution plan 层；知道目标 GPU 架构足以选模拟语义。
  - **可能失效场景**：完整 PyTorch/[[vLLM]] 栈的融合 kernel、分布式 [[Tensor-Parallelism]] all-reduce 顺序使端到端 bit-exact 仍开放。

- **观察 5：LLM 部署存在 routing × placement 的 circular dependency，需联合优化。** [[BOUTE-MLSys26|BOUTE]] 在 GSM8K 上分离优化 routing 与 deployment 可差 **10%+ P95**；[[MixLLM-MLSys26|MixLLM]]、[[RaidServe-MLSys26|RaidServe]] 等从 serving 侧处理异构模型与容错。

## 设计空间与取舍

- **路线 1：Serving runtime 优化（内存/调度/kernel）**——[[PagedAttention]]、[[Continuous-Batching]]、[[Speculative-Decoding]]、[[Disaggregation]]；牺牲实现复杂度，换 batch 并发与 tail latency。代表：[[vLLM-SOSP23|vLLM]]、[[SuperInfer-MLSys26|SuperInfer]]、[[MorphServe-MLSys26|MorphServe]]。
- **路线 2：训练并行与弹性**——3D 并行 + bubble 调度 + 跨 DC/异构 planner；牺牲工程与验证成本。代表：[[CrossPipe-ATC25|CrossPipe]]、[[FlexTrain-MLSys26|FlexTrain]]、[[Sailor-SOSP25|Sailor]]、[[Optimus-ATC25|Optimus]]。
- **路线 3：LLM-as-component（agent / RAG / codegen）**——用缓存、异步、profiler 绕过同步 LLM 调用；牺牲任务覆盖或需人工 skeleton/spec。代表：[[AgenticCache-MLSys26|AgenticCache]]、[[METIS-SOSP25|METIS]]、[[SysSpec-FAST26|SysSpec]]、[[FunSearch-Nature24|FunSearch]]。
- **路线 4：可验证与形式化**——equivalence checking、GPU 模拟、spec-guided 生成；牺牲 upfront 成本与覆盖范围。代表：[[TrainVerify-SOSP25|TrainVerify]]、[[Hawkeye-MLSys26|Hawkeye]]。
- **路线 5：端侧/消费级部署**——DVFS、beam scheduling、量化；牺牲模型规模与多租户能力。代表：[[CORE-MLSys26|CORE]]、[[Kitty-MLSys26|Kitty]]、[[LocalityAwareBeamScheduling-MLSys26]]。

## 引用本概念的论文

- [[SysSpec-FAST26|SysSpec]] — spec-guided [[LLM]] 零人工干预生成/演化 FUSE 文件系统，Gemini-2.5-Pro 45 模块 100% 生成准确率
- [[FunSearch-Nature24|FunSearch]] — frozen LLM + evaluator + island 进化在 cap set、bin packing 上产出可验证 SOTA
- [[TrainVerify-SOSP25|TrainVerify]] — 验证 Llama3 405B / DeepSeek-V3 671B 分布式训练 parallelization equivalence
- [[METIS-SOSP25|METIS]] — profiler LLM + joint scheduler 做 quality-aware [[RAG]]，延迟 1.64–2.54× 且不降质量
- [[AgenticCache-MLSys26|AgenticCache]] — 2-gram 计划缓存 + 异步 LLM Updater，具身 agent SR +22%、延迟 -65%
- [[HIPPOCAMPUS-MLSys26|HIPPOCAMPUS]] — compression-native agent 记忆，检索延迟最高 31×、token -14×
- [[Hawkeye-MLSys26|Hawkeye]] — CPU 上 bit-exact 复现 Tensor Core MMA，支撑可验证 LLM 训练/推理审计
- [[FlexTrain-MLSys26|FlexTrain]] — 弹性 LLM 训练以 PP 为主轴保 bitwise 精度，JCT 最多 1.73×
- [[Optimus-ATC25|Optimus]] — MLLM 训练利用 LLM backbone 48% bubble 塞 encoder 计算，3072 GPU 上 20.5–21.3% 加速
- [[Greyhound-ATC25|Greyhound]] — 10K+ GPU 生产集群 fail-slow 表征，DP micro-batch 重分配缓解 straggler
- [[BOUTE-MLSys26|BOUTE]] — 联合 LLM routing 与 GPU deployment 优化
- [[SuperInfer-MLSys26|SuperInfer]] — 异构内存层次上 LLM serving 的 KV rotation 与带宽修复
- [[BatchLLM-MLSys26|BatchLLM]] — LLM batch 推理调度
- [[Charon-MLSys26|Charon]] — 注入 TP/PP/DP/FSDP/ZeRO/EP 通信算子做 LLM 训练端到端仿真
- [[Chakra-MLSys26|Chakra]] — 标准化 LLM 分布式训练 execution trace 供 co-design
- [[Auto-Research-arXiv25|Auto-Research]]、[[AlphaEvolve-arXiv25|AlphaEvolve]]、[[RD-Agent-Quant-arXiv25|RD-Agent-Quant]] — LLM 驱动科研/量化搜索管线
- [[DeepScientist-ICLR26|DeepScientist]]、[[Co-Scientist-Nature26|AI co-scientist]]、[[SR-Scientist-ICLR26|SR-Scientist]] — 以 LLM 组织假设生成、实验执行、反馈与迭代的闭环研究系统
- [[AstaBench-ICLR26|AstaBench]]、[[InnovatorBench-ICLR26|InnovatorBench]]、[[RE-Bench-ICML25|RE-Bench]]、[[PaperBench-ICML25|PaperBench]] — 从科研助理能力、开放式创新、限时研究工程到论文复现，评测 LLM agent 的不同研究阶段
- [[HeurekaBench-ICLR26|HeurekaBench]]、[[DDR-Bench-ICML26|DDR-Bench]] — 分别用可验证算法发现与深度数据研究任务检验 LLM 研究 agent 的 grounding、novelty 与端到端可靠性
- [[ByteRobust-SOSP25|ByteRobust]]、[[DreamDDP-MLSys26|DreamDDP]]、[[HetRL-MLSys26|HetRL]] — 大规模 LLM 训练容错与 geo-DDP
- [[HeteroInfer-SOSP25|HeteroInfer]]、[[MixLLM-MLSys26|MixLLM]]、[[RaidServe-MLSys26|RaidServe]] — 异构 LLM 推理 serving
- [[Kitty-MLSys26|Kitty]]、[[OPKV-MLSys26|OPKV]]、[[FlexiCache-MLSys26|FlexiCache]] — KV/权重压缩与 LLM 推理内存优化
- [[CORE-MLSys26|CORE]] — 移动 LLM 上 CPU/GPU 联合 DVFS
- [[GCR-FAST26|GCR]] — 系统级 GPU C/R 覆盖 LLM [[KV-Cache]] 级 state
- [[NewsShock-NBER26|NewsShock]] — LLM 时代信息冲击的经济/系统含义（跨学科引用）

## 已知局限 / 开放问题

- **Inference vs training 工具链分裂**：prefill/decode 最优并行、内存策略缺乏开源统一 planner（[[Meta-LLM-Deploy-MLSys26]] 模拟器未开源）
- **可验证 LLM 栈不完整**：MMA oracle（[[Hawkeye-MLSys26|Hawkeye]]）与 plan verification（[[TrainVerify-SOSP25|TrainVerify]]）尚未闭合到端到端 serving/training bit-exact
- **Agent 栈成本模型**：profiler/Updater/记忆索引的额外 LLM 调用如何在 query rate 增长下保持净收益（[[METIS-SOSP25|METIS]]、[[AgenticCache-MLSys26|AgenticCache]]）
- **弹性训练一致性**：DP 扩缩与 partial sync 的收敛保证 vs 吞吐收益仍依赖 workload 实证（[[FlexTrain-MLSys26|FlexTrain]]、[[DreamDDP-MLSys26|DreamDDP]]）
- **多租户与路由联合优化**：routing × placement × KV 共享的安全与 SLO 隔离（[[BOUTE-MLSys26|BOUTE]]）仍是生产开放题
