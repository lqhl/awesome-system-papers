---
type: paper
name: FlashAgents
full_title: "FLASHAGENTS: Accelerating Multi-Agent LLM Systems via Streaming Prefill Overlap"
authors: [Taosong Fang, Zhen Zheng, Zhengzhao Ma, Yaojie Lu, Hongyu Lin, Xianpei Han, Le Sun]
venue: MLSys
year: 2026
tags: [multi-agent, llm-serving, sglang, prefill, prefix-cache, latency, area/agent-systems]
source_pdf: "[[b6d767d2f8ed5d21a44b0e5886680cb9.pdf]]"
source_md: "[[b6d767d2f8ed5d21a44b0e5886680cb9]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# FlashAgents：通过流预填充重叠加速多智能体 LLM 系统（MLSys 2026）

> **原题**：FLASHAGENTS: Accelerating Multi-Agent LLM Systems via Streaming Prefill Overlap

> **一句话总结**：多智能体顺序依赖使下游 agent 必须等上游 decode 完成才 prefill，造成 inter-agent 空转；FLASHAGENTS 在 [[SGLang]] 上实现 token 级 streaming + incremental prefill 重叠上游 decode 与下游 prefill，并发时用 intra-turn radix prefix cache 去重；真实 workflow 端到端延迟最高降 **40%**，受控双 agent benchmark **3.5×**（并发 2）。

## 问题与动机

[[LLM]] serving 优化聚焦单请求 prefill/decode 与跨请求 batching；[[Multi-Agent Systems]]（MAS）引入 **inter-agent 顺序依赖**——Agent B 的 prefill 输入是 Agent A 的完整输出，传统系统将每次 agent 调用当独立 request，B 必须等 A 生成结束才开始 prefill，链式/多轮对话中 idle 累积。

Fig. 1 显示同 token 数下 prefill 与 decode 吞吐同量级（如 Qwen3-8B prefill 7644 vs decode 2554 tok/s @ bs32），且下游 prefill 还含 system prompt、tool、history，heterogeneous 部署（8B→32B）进一步放大 overlap 窗口。现有 [[vLLM]]/SGLang 持久 radix prefix cache 仅在 request **完成** prefill 后更新，同 turn 并发下游无法共享进行中 prefix。

## 关键观察 / 隐含假设

- **观察 1：因果 attention 允许对已到达 token chunk 做 incremental prefill，query 仅覆盖新 chunk、key 累积历史 KV，语义与一次性 prefill 等价。**
  - **依赖假设**：chunk 按到达顺序处理；无 position 依赖未决的 tail segment（fan-in 需保守策略）。
  - **可能失效场景**：RoPE 下 position 取决于未 finalize 的上游长度时，部分 suffix 必须延迟 prefill（论文 §4.2 对 outputB∥outputC 的处理）。

- **观察 2：并发多对 A→B 时，共享 instruction template 的 buffered token 可用临时 radix 树一次 materialize 共享节点 KV，避免重复 prefill。**
  - **依赖假设**：同 turn 内 trigger 时批量插入 {Ur}；树深度有序 materialize 保因果。
  - **可能失效场景**：prefix 几乎全异构时 intra-turn cache 收益趋零。

- 观察 3：7B 单并发 overlap 有限（speedup 1.05–1.2×），高并发下 GPU 共 batch + prefix 去重可达 3.52×（240 配置全优于 sequential）。
  - **依赖假设**：下游 incremental prefill 可与常规 workload 共调度；chunk threshold 平衡 overlap 与 incremental 开销。
  - **可能失效场景**：235B 高并发时 aggregate downstream prefill 超过 upstream decode，speedup 平台化甚至略降。

- **假设 1：co-located agent 间 lightweight message-passing 传 token 延迟可忽略。**
  - **可能失效场景**：跨机 MAS、网络隔离部署需额外传输层，论文未测。

## 核心方法

**Inter-agent streaming + incremental prefill（IASIP）**：A decode 每产出 token 写入 BufB；达阈值或 final token 时 B 对 chunk 做 IncPrefill 更新 [[KV-Cache]]；A 结束后处理剩余 buffer，B 立即 decode。延迟从 \(T_A^{dec}+T_B^{pre}+T_B^{dec}\) 变为 \(T_A^{dec}+T_B^{dec}+\max(0,T_B^{pre}-T_{overlap})\)。

**Intra-turn prefix cache**：prefill trigger 时对所有 request 的 unbuffered tokens 建共享 radix 树，仅对新节点做 prefill，沿路径组装各 request KV（Algorithm 2）。与 SGLang 持久 RadixAttention **分离**，不修改核心树。

**拓扑扩展**：线性链 pipelined；fan-out 并行 stream；fan-in 仅 prefill position-stable 段。

**实现**：SGLang 扩展 streaming API、AgentBuffer、scheduler 辅助 radix；[[AutoGen]] 异步 client 关联 producer-consumer request id。

## 设计取舍

- **Incremental prefill 计算开销 vs 延迟**：chunk=128 时相对单次 prefill 最高 **~3×** GPU 时间，chunk=512 约 **1.2×**；靠与 upstream decode overlap 仍净赢 E2E。
- **不改核心 RadixAttention vs 深度集成**：模块化降低 merge 风险，但双树状态增加运维复杂度。
- **保守 fan-in position 策略 vs 激进 overlap**：保正确性，牺牲部分 fan-in 场景 overlap。
- **与 SJF/Kairos 正交**：并发 10 时 FLASHAGENTS+SJF 合计约 **37%** 延迟降幅，可叠 workflow 级调度。

## 实验与结果

**Microbenchmark**（A100-80GB，Qwen2.5-7B / Qwen3-235B，并发 1/2/4/8）：相对 sequential，speedup **1.05–3.52×**；7B 高并发 peak **3.52×@conc=2**；235B 单请求 overlap 更大。

**真实 workflow**（7B upstream + 32B downstream）：Chain N=8 **11.9%**；MapReduce N=1 **40.3%**、N=8 **14.7%**（decode 争用 32B GPU）。PPTAgent 异构双 A800：**24.1%** downstream response 降幅（3.41s vs 4.49s）。

**Ablation**（Qwen3-32B）：conc=8 时 IASIP 5.32s → Full 4.20s，prefix cache 额外 **21%**；全系统 **2.40×**。

**Overhead**：历史 KV 访问使最长 chunk 仅比首 chunk 慢 **4.6–7.9%**。

## 批判性分析

### 论证链条

观察（[[Multi-Agent Systems]] 引入 inter-agent 顺序依赖——下游 prefill 输入是上游完整输出，传统 serving 将每次 agent 调用当独立 request，造成链式 idle 累积；prefill 与 decode 吞吐同量级且下游 prefill 含更长 system/tool/history）→ 设计（IASIP token 级 streaming + incremental prefill 重叠上游 decode 与下游 prefill；intra-turn radix prefix cache 去重同 turn 共享 template）→ 结果（真实 workflow 最高 **40%** 延迟降幅、受控 benchmark **3.5×**@conc=2）链条**闭合良好**。论文明确把 MAS 瓶颈从「单请求优化」改写成 **inter-agent pipeline overlap**，与 [[Continuous-Batching]]、disaggregation、[[BatchLLM]] 等正交，定位清晰。

主要跳步是把 microbenchmark 峰值 speedup（**3.52×**@conc=2）外推到「生产 MAS 普遍收益」。真实 workflow 中 **40%** 出现在 MapReduce N=1 特定配置，Chain N=8 仅 **11.9%**、单请求 Chain 约 **1.8%**——说明收益高度依赖 workload 形态（上游输出长度、下游并发度、异构模型争用）。增量 prefill 本身最高 **~3×** GPU 时间（chunk=128），净赢完全靠 overlap 窗口；短上游输出或 235B 高并发下 aggregate downstream prefill 超过 upstream decode 时 speedup 平台化甚至略降，论文有报告但叙事仍偏乐观。

### 假设压力测试

- **部署拓扑**：假设 co-located agent 间 lightweight message-passing 传 token 延迟可忽略；跨机 MAS、网络隔离部署需额外传输层，论文未测——与 [[KV-Cache]] 跨节点迁移成本问题同类。
- **Position 正确性**：RoPE 下 fan-in 需保守策略，仅 prefill position-stable 段——牺牲部分 fan-in overlap 换正确性；dynamic workflow 无全局图时难与 KVFlow/Teola 的静态图优化直接比。
- **Prefix 异构性**：intra-turn cache 假设同 turn 多下游共享 instruction template；prefix 几乎全异构时收益趋零（MapReduce reviewer、PPT 12 路 generator 是「命中形态」，非默认）。
- **框架集成成本**：依赖 [[SGLang]] streaming API、AgentBuffer、双 radix 树状态与 [[AutoGen]] 异步 client 改造；模块化降低 merge 风险，但运维复杂度上升。
- **Incremental 开销**：chunk threshold 在 overlap 收益与 incremental prefill 开销间权衡；7B 单并发 overlap 有限（**1.05–1.2×**），高并发才释放 batching + prefix 去重红利。

### 实验可信度

- **强项**：microbenchmark 覆盖 Qwen2.5-7B / Qwen3-235B、并发 1/2/4/8，240 配置全优于 sequential；ablation 显示 conc=8 时 IASIP→Full 前缀 cache 额外 **21%**、全系统 **2.40×**；PPTAgent 异构双 A800 **24.1%** downstream response 降幅有真实 workflow 支撑。历史 KV 访问使最长 chunk 仅比首 chunk 慢 **4.6–7.9%**，说明 incremental 开销可控。
- **Baseline 选取**：sequential（现状：等上游 decode 完成再 prefill）是公平对照；与 SJF/Kairos 叠加强调正交性（合计约 **37%**），但未 head-to-head 与 KVFlow/Teola 静态图调度。
- **Metric 缺口**：**40%** 出现在特定 MapReduce N=1，不宜作为 headline 无 qualifier 外推；未报 tail latency、fairness、多租户下 incremental prefill 对共享 GPU 的干扰（future work 已承认）。跨 GPU 部署、与 speculative decoding / disaggregated prefill-decode 组合均未评测。

## 局限与后续工作

- 非生成步骤与 overlap 的 co-design、自适应 chunk/stream 策略。
- 跨机 token streaming 与 [[KV-Cache]] 迁移成本。
- 与 speculative decoding、disaggregated prefill/decode 组合。
- fairness、多租户下 incremental prefill 对共享 GPU 的干扰量化。

## 相关

- **Serving**：[[SGLang]]、[[vLLM]]、RadixAttention、chunked prefill
- **MAS 系统**：KVFlow、Kairos、Teola、AutoGen
- **概念**：prefill-decode 重叠、[[KV-Cache]]、prefix caching
