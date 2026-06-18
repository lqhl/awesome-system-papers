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

> **一句话总结**：Meta FAIR 的 Matrix 用 P2P message-driven 调度替代中心化 orchestrator，单行任务独立流过 agent 网络，在 31 节点 248 GPU 上跑 12,400 并发 workflow，相比 Coral baseline 吞吐 **6.8×**（广义 **2–15×**），输出质量持平。

## 问题

多 agent 合成数据已成 LLM 训练主流，但现有框架有两类瓶颈：

- **通用 agent 框架**（AutoGen、LangGraph、CrewAI）面向 chatbot/web agent，非大规模数据生成优化
- **专用框架**（AgentInstruct、SWE-Agent、TaskCraft）把 orchestration 硬编码进领域逻辑；扩容只能堆 workflow 实例 + Kubernetes/Airflow，中心化 orchestrator 在万级并发下成为瓶颈

Ray Data / Spark 的 **batch-level scheduling** 还会因同 batch 内慢任务产生 GPU idle bubble。

## 核心方法

**P2P agent 架构**：
- 每行输入封装为可序列化 `Orchestrator`（control flow + conversation history）
- Stateless Ray Actor agent 通过 async event loop 取消息、处理、转发下一 agent；`_sink` 落盘
- Driver 只负责启动首 agent，无中心调度

**Row-level scheduling**：每个任务完成即释放资源给下一行，消除 batch barrier

**分布式服务**：
- LLM 推理 gRPC 直连 worker replica（绕过 Ray head 网络瓶颈），后端 [[vLLM]] / [[SGLang]] / FastGen
- Apptainer 容器按 ID 路由复用
- **Message offloading**：大 conversation 存 Ray object store，orchestrator 只持 object ref，避免 Redis 方案 **2×** 带宽

Hydra 配置 agent 角色、并发上限（semaphore）、资源需求。

## 关键结果

**Coral**：31×A100（248 GPU）、Llama-3.1-8B、12,400 并发 vs Coral 5,000：
- **6.8×** token 吞吐（129,833 vs 18,917 tok/s）；4h17m vs 9h03m 生成 2B vs 617M tokens
- Agreement correctness **0.4778 vs 0.4732**

**NaturalReasoning**：32 节点、25M DCLM 文档，P2P vs Ray Data batch baseline **2.1×** token 吞吐；Setting (20,700,1) 最优

**Tau2-bench**：相对官方 baseline 随并发持续扩展（baseline ~500 线程饱和）

广义 **2–15×**；开源 github.com/facebookresearch/matrix

## 相关

- **相关概念**：P2P Orchestration、Row-Level Scheduling、Multi-Agent Systems
- **同类系统**：AutoGen、LangGraph、CrewAI、AgentInstruct、Ray Data、[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]