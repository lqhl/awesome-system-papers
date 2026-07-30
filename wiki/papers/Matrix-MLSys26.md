---
type: paper
name: Matrix
full_title: "Matrix: Peer-to-Peer Multi-Agent Synthetic Data Generation Framework"
authors: [Dong Wang, Yang Li, Ansong Ni, Ching-Feng Yeh, Youssef Emad, et al.]
venue: MLSys
year: 2026
tags: [synthetic-data, multi-agent, distributed-systems, llm-agents]
source_pdf: "[[f4b9ec30ad9f68f89b29639786cb62ef.pdf]]"
source_md: "[[f4b9ec30ad9f68f89b29639786cb62ef]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Matrix：点对点多智能体合成数据生成框架（MLSys 2026）

> **原题**：Matrix: Peer-to-Peer Multi-Agent Synthetic Data Generation Framework

> **一句话总结**：Matrix 用 message-carried state、stateless Ray actors、row-level scheduling 和 distributed services 去掉合成数据 workflow 的中心 orchestrator；在相同硬件上，相对 Coral、Ray Data 和 Tau2-agent 分别达到 6.8×、2.1×、15.4× token throughput，并在论文所测 agreement correctness / reward 上保持接近（§5.1–5.3，Table 1/4/5）。

## 问题与动机

[[LLM]] agent 合成数据流水线（多角色、多步、分支）并发可达万级。中心化 controller 限制扩展；需要模块化、可配置、高吞吐的 distributed orchestration。

## 关键观察 / 隐含假设

- **观察 1：中心 orchestrator 同时承担调度、状态与数据流，会在数千 workflow concurrency 下形成控制面瓶颈。** Matrix 将 task state 序列化进消息，并让 stateless agents 直接转发控制（§3.1–3.2，Algorithm 1）。
  - **依赖假设**：P2P 路由不引入难调试的全局状态。
  - **可能失效场景**：强全局事务/严格顺序 workflow 需额外同步层。

- **观察 2：heterogeneous workflow 的 batch-level barrier 会产生 bubble，row-level scheduling 可在单 row 完成后立即推进。** NaturalReasoning 中相对 Ray Data 的 token throughput 提升 2.1×（§4.4、§5.2.2，Table 4）。
  - **依赖假设**：任务之间独立，允许以 row 为粒度推进和重试。
  - **可能失效场景**：需要跨 row transaction 或全局同步的 workflow。

- **观察 3：瓶颈会在 input partitions、agent actors 和 distributed inference services 之间迁移。** 固定总 concurrency 时，将 NaturalReasoning input partitions 从 1 增至 20 可带来 1.61× throughput，而只增加 agent replicas 收益很小（§5.2.1，Table 3）。
  - **依赖假设**：Ray placement 与 queue backpressure 能反映真实资源瓶颈。
  - **可能失效场景**：跨 region queue latency 或 shared object-store saturation。

## 核心方法

**P2P messaging**：task state 随 serialized message 传递，Ray actor 近似 stateless，避免集中式 workflow state（§3.2）。

**Distributed services**：LLM inference、retrieval 和 container execution 通过直接 service routing 独立扩缩（§4.2）。

**Row-level scheduling**：每个 completed row 独立触发下一 agent，避免 batch straggler 阻塞（§4.4）；大消息通过 Ray Object Store offload，减少 queue copy（§4.6，Fig. 9）。

## 设计取舍

- **P2P vs 中心化**：扩展性换调试与一致性复杂度。
- **通用框架 vs 专用 pipeline**：灵活但最优性能需调参。
- **Message-carried state vs 网络流量**：去中心化状态简化调度，但大 conversation/history 会增加 queue 与 object-store 压力，需 offload threshold。
- **边界条件**：synthetic data 生成，非在线 serving。

## 实验与结果

- **Collaborative Reasoner**：MMLU-Pro、LLaMA-3.1-8B-Instruct、31 个 A100 节点下，Matrix 为 129,833 tokens/s，Coral 为 18,917 tokens/s，即 6.8×；agreement correctness 为 0.4778 vs 0.4732（§5.1，Fig. 4，Table 1）。
- **NaturalReasoning**：DCLM、相同 GPU resources、14k concurrent tasks 下，row-level Matrix 为 5,853 tokens/s，Ray Data batch baseline 为 2,778 tokens/s，即 2.1×（§5.2.2，Table 4）。
- **Tau2-bench**：gpt-oss-120b、13 个 H100 节点、1,500 containers 下，Matrix 为 41,003 tokens/s，Tau2-agent 为 2,654 tokens/s，即 15.4×；average reward 为 0.5921 vs 0.5918（§5.3，Fig. 7，Table 5）。
- **Input scaling ablation**：500k DCLM subset、32 个 8-GPU A100 节点下，将 partitions 从 1 增至 20、保持总 concurrency 14k，可获得 1.61× normalized throughput（§5.2.1，Table 3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 相对 Coral 达到 6.8× token throughput，agreement correctness 接近 | §5.1, Fig. 4, Table 1 | MMLU-Pro；LLaMA-3.1-8B；31×A100 nodes；12,400 concurrency | strong |
| Row-level scheduling 相对 Ray Data 达到 2.1× token throughput | §5.2.2, Table 4 | DCLM；14k tasks；相同 GPU resources | strong |
| 相对 Tau2-agent 达到 15.4× token throughput，average reward 接近 | §5.3, Fig. 7, Table 5 | Tau2；gpt-oss-120b；13×H100 nodes；1,500 containers | strong |
| 增加 input partitions、保持总 concurrency 不变可获得 1.61× throughput | §5.2.1, Table 3 | 500k DCLM；32×8 A100；14k tasks | strong |

## 批判性分析

### 论证链条

中心化瓶颈 → P2P+服务化 → 吞吐大幅提升，系统逻辑直接。质量保持需明确评测维度（多样性/毒性/下游 utility）。

### 假设压力测试

超十万 agent 时消息风暴、循环检测、失败重试成本。与 [[MorphServe]]/serving 无直接关系。

### 实验可信度

倍数区间宽，依赖 workload。缺：fault tolerance、straggler agent 处理公开数据。

### 系统性缺陷

论文未讨论数据治理、PII 过滤、成本$/sample。§4.5 描述了 task retry、actor restart 等 fault-tolerance 机制，但没有故障注入或恢复开销实验；P2P 安全模型也未展开。

## 局限与后续工作

- **局限 1**：P2P 运维与 debug 难。
- **局限 2**：质量评估维度可能不够生产级。
- **Future work 1**：multimodal synthetic data 扩展（作者计划）。
- **Future work 2**：on-policy continuous synthesis 闭环测下游 model utility。

## 相关

- **相关概念**：[[Synthetic-Data]]、[[Agentic-AI]]、[[LLM-Agents]]
- **同类系统**：中心化 agent orchestrator
- **同会议**：[[MLSys-2026]]
