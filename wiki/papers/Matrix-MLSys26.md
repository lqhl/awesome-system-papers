---
type: paper
name: Matrix
full_title: "Matrix: Peer-to-Peer Multi-Agent Synthetic Data Generation Framework"
authors: [Dong Wang, Yang Li, Ansong Ni, Ching-Feng Yeh, Youssef Emad, "et al."]
venue: MLSys
year: 2026
tags: [multi-agent, synthetic-data, distributed-systems, p2p, ray]
source_pdf: "[[f4b9ec30ad9f68f89b29639786cb62ef.pdf]]"
source_md: "[[f4b9ec30ad9f68f89b29639786cb62ef]]"
---

# Matrix: Peer-to-Peer Multi-Agent Synthetic Data Generation Framework (MLSys 2026)

> **一句话总结**：Meta FAIR 的 Matrix 用 peer-to-peer、message-driven 调度替代中心化 orchestrator，把 agent workflow 的 control/data flow 序列化到 orchestrator message 中，在 31 节点 248 GPU 上跑 12,400 并发任务，相比 Coral baseline 吞吐 **6.8×**（广义 2–15×），同质量。

## 问题

多 agent 合成数据（code synthesis、instruction/dialogue generation、multi-modal）已成 LLM 训练主流，但现有框架：

- **通用 agent 框架**（AutoGen、LangGraph、CrewAI）面向 chatbot/web agent，非 scale-out 数据生成优化
- **专用数据生成框架**（AgentInstruct、SWE-Agent、TaskCraft、AgentSynth）把 orchestration 硬编码到特定领域；要扩大规模只能起多 workflow 实例 + 外部 Kubernetes/Airflow
- **中心化 orchestrator** 成为 10k+ 并发 workflow 下的瓶颈——单点调度、batch-level synchronization 造成 GPU idle

## 核心方法

**P2P agent 架构**：
- 每个任务封装为一个 `Orchestrator` 对象，内含 control flow（state machine）+ data flow（conversation history）
- Driver 仅启动任务：把 orchestrator 发给第一个 agent，随后完全 P2P 流转
- Agent 是 **stateless Ray Actor**，弹性水平扩展；各自 event loop 从 queue 取 orchestrator，process 后 forward 给下一个 agent，`_sink` 终结

**行级调度（row-level scheduling）**：
- 相比 Ray Data / Spark 的 batch-level scheduling，Matrix 每个任务独立流过 P2P 网络，消除 batch barrier 的 idle bubble

**分布式服务**：
- LLM 推理用 gRPC 直连 worker 节点（Ray head 会变网络瓶颈）
- Stateful service（Apptainer 容器）用 resource pool + registry 按 container ID 路由
- 支持 [[vLLM]] / [[SGLang]] / FastGen

**容错 + 网络优化**：
- Agent 跑在 permanent node，LLM 推理可跑 opportunistic/spot 节点
- **Message offloading**：大 conversation content 存 Ray distributed object store，orchestrator 只带 object ID——避免 Redis 方案导致的 2× 网络流量

## 关键结果

**Coral（协作推理）**：31 节点 248 GPU、Llama-3.1-8B-Instruct，Matrix 12,400 并发 vs Coral 5,000（其最优）：
- Runtime 4h17m vs 9h03m → 吞吐 **6.8×**（129,833 vs 18,917 tokens/s）
- Agreement correctness 0.4778 vs 0.4732（完全持平）
- 2B tokens vs 617M tokens in 4 hours

**NaturalReasoning**：32 节点 A100，处理 25M DCLM web 文档，5.45% 通过筛选得到 1M 高质量 QA。3B classifier + 70B scorer/question generator 并行

**Tau2-bench**：工具使用 trajectory 生成

广义 **2–15×** 吞吐提升；开源 (github.com/facebookresearch/matrix)，基于 SLURM + Ray + Apptainer + vLLM/SGLang + Hydra。

## 相关

- **相关概念**：P2P Orchestration、Row-Level Scheduling、Multi-Agent Systems
- **同类系统**：AutoGen、LangGraph、CrewAI、AgentInstruct、SWE-Agent、TaskCraft、Ray Data、[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]
