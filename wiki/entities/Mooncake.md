---
type: entity
kind: system
aliases: [Mooncake Store, Mooncake Transfer Engine]
status: active
last_updated: 2026-06-20
tags: [llm-inference, kv-cache, disaggregation, rdma, serving]
---

# Mooncake

> Moonshot AI（Kimi）提出的 **KVCache-centric** disaggregated serving 系统：以「用更多存储换更少计算」为核心，把 [[KV-Cache]] 提升为跨请求、跨实例、跨 prefill/decode 池的一等数据对象，并用 [[RDMA]] Transfer Engine 与分布式 Mooncake Store 支撑高速搬运与池化复用。

## 是什么

Mooncake 是 Moonshot AI 为 Kimi 长上下文 chatbot serving 设计的系统栈，FAST 2025 论文标题即点明设计哲学：**Trading More Storage for Less Computation**（[[Mooncake-FAST25]]）。与 [[DistServe]]、Splitwise 同属最早一批把 [[Disaggregation|prefill-decode disaggregation]] 落到生产的路线之一：prefill 与 decode 分到不同 GPU 集群，中间靠高速网络传 [[KV-Cache]]，而非把两阶段强行 collocate 在同一批 HBM 上。

这些论文共同把 Mooncake 拆成三层能力边界。**Serving 架构层**：KVCache-centric global scheduler 记录集群级 KV 驻留状态，把请求路由到已有 cache 命中的实例（[[KVCacheInTheWild-ATC25]] 在 [[vLLM]] 上复现了该 global scheduler 做跨实例 KV-aware routing）。**传输层**：Mooncake Transfer Engine 提供基于 [[RDMA]] 的 P2P bulk write，支撑 disaggregated inference 中 prefiller→decoder 的层间/分块 KV 迁移；[[fabric-lib-MLSys26]] 将其与 DeepEP、NVSHMEM、NIXL 并列为 LLM P2P 通信候选，并指出 Mooncake Transfer Engine 当时 **尚无 EFA 支持**。**存储层**：Mooncake Store 提供分布式 KV 池化存储，与 DeepSeek 3FS 同类；容量层可走 [[RDMA]] 池化内存而非本地 SSD——[[Bidaw-FAST26]] 据此把 Mooncake 当作「高速容量层」对照，而 Bidaw 刻意聚焦低成本本地 SSD niche。

Mooncake 还贡献了公开 serving trace（`mooncake_trace.jsonl`），被多篇后续工作用作长上下文 benchmark：[[Bidaw-FAST26]] 引用其 workload 特征（平均 query **12k tokens**），与短轮次交互式对话（36/45 tokens）形成鲜明 niche 对比。[[LMCache-arXiv25]] 将 Mooncake 列为 heterogeneous KV backend 之一，说明其已从单一 serving 栈演化为可被第三方 cache layer 集成的存储/传输 substrate。

## 关键观察 / 隐含假设

- **观察 1：KVCache-centric 架构假设「存储 + 网络带宽」比「重复 prefill 计算」更便宜，长上下文与跨实例 prefix 复用是主战场。** [[Bidaw-FAST26]] 把 Mooncake 类 workload 标为超长上下文 niche（平均 query 12k tokens），容量压力形态与短会话交互式对话截然不同；[[AITurbo-FAST26]] 在 Qwen-Bailian trace 上以 Mooncake 为 KVCache read baseline，说明其设计面向 bulk KV I/O 而非小文件随机读。
- **观察 2：RDMA 池化内存作容量层可缩小 host memory 与远端 cache 的带宽差距，使「两层本地存储」路线的调度价值下降。** [[Bidaw-FAST26]] 指出若容量层升级为 [[RDMA]] 池化内存（Mooncake）或 CXL 扩展内存，dual queue 分离与 disk-HRRN 的收益会缩小；论文刻意不与 Mooncake 做端到端对比，暗示两条路线服务不同成本/部署假设。
- **观察 3：Mooncake Transfer Engine 是 ConnectX 生态内的 RDMA P2P 方案，但多云可移植性仍是短板。** [[fabric-lib-MLSys26]] 将 Mooncake 与 DeepEP、NVSHMEM、NIXL 并列，指出 Mooncake/NIXL 的 **EFA 支持滞后或初步**；fabric-lib 用 IMMCOUNTER 抽象可靠无序语义，在 ConnectX-7 与 AWS EFA 均达 **400 Gbps**，并列出与 Mooncake Store、3FS 协同为 future work。
- **观察 4：作为 KVCache-centric serving 栈，Mooncake 与「存储层透明优化」存在正交互补关系。** [[AITurbo-FAST26]] 在 Mooncake 上仅改 **44 LoC**（未用 grouped API）即获 KVCache read 收益：Mooncake+AITurbo TTFT 比 Mooncake+SFSTurbo 降 **23%**，storage miss 时借 compute fabric 使有效 KV 读带宽最高 **1.28×** 于纯 Mooncake——说明 Mooncake 的瓶颈可在存储+fabric 协同层继续挖掘。
- **观察 5：disaggregated inference 开源实现涌现，但大规模生产落地仍少，Mooncake 是论文图谱中的代表性参照系。** [[fabric-lib-MLSys26]] 在 Disaggregation 相关工作中与 [[DistServe]]、Splitwise 并列引用 Mooncake；[[NVIDIA-Disagg-Study-MLSys26]] 亦将 Mooncake 与 NVIDIA Dynamo、[[vLLM]] disagg、[[SGLang]] 并列为开源 disagg 实现，但指出跨框架同硬件 shootout 仍缺。

## 演进时间线

- **2024 arXiv**：Mooncake 预印本提出 Kimi 的 KVCache-centric disaggregated architecture（arXiv:2407.00079），公开 trace 与 Transfer Engine 代码生态（kvcache-ai/Mooncake）。
- **2025 FAST**：[[Mooncake-FAST25]] 正式发表「Trading More Storage for Less Computation」，确立 prefill/decode 分离 + 分布式 KV 池化 + RDMA 传输的完整叙事。
- **2025 ATC**：[[KVCacheInTheWild-ATC25]] 在 [[vLLM]] 上实现 Mooncake 式 global scheduler 做跨实例 KV-aware routing，验证 workload-aware eviction 需与全局路由协同。
- **2025 arXiv**：[[LMCache-arXiv25]] 将 Mooncake 列为 enterprise KV cache layer 的可插拔 backend，与 InfiniStore、Redis、S3 等并列。
- **2026 FAST**：[[AITurbo-FAST26]] 以 Mooncake 为 KVCache read SOTA baseline，展示存储层 grouped I/O 与 Mooncake 栈的轻量集成（44 LoC）。
- **2026 FAST**：[[Bidaw-FAST26]] 以 Mooncake 代表 RDMA 池化高速容量层路线，界定本地 SSD 两层 cache 的互补 niche。
- **2026 MLSys**：[[fabric-lib-MLSys26]] 剖析 Mooncake Transfer Engine 的 EFA 缺口，提出 portable P2P 原语并与 Mooncake Store 互补；[[NVIDIA-Disagg-Study-MLSys26]] 将 Mooncake 纳入 disagg 设计空间讨论，指出远端 KV 层可能引入额外 hop。

## 相关概念

- [[KV-Cache]]
- [[Disaggregation]]
- [[Prefill-Decode-Disaggregation]]
- [[Prefix-Caching]]
- [[RDMA]]
- [[PagedAttention]]

## 相关论文

- [[fabric-lib-MLSys26]] — 将 Mooncake Transfer Engine 与 DeepEP/NIXL 对比，指出 EFA 支持缺口；KvCache 迁移与 Mooncake Store 协同列为 future work
- [[Bidaw-FAST26]] — 以 Mooncake 代表 [[RDMA]] 池化内存容量层与超长上下文 workload niche，对照本地 SSD 双向感知路线
- [[AITurbo-FAST26]] — Mooncake 作 KVCache-centric serving baseline；44 LoC 集成后 KV 读最高 1.28×、TTFT −23%
- [[LMCache-arXiv25]] — 将 Mooncake 列为 heterogeneous KV backend，与 [[vLLM]]/[[SGLang]] connector 生态对接
- [[KVCacheInTheWild-ATC25]] — 复现 Mooncake 式 global scheduler 做跨实例 KV-aware routing
- [[NVIDIA-Disagg-Study-MLSys26]] — 将 Mooncake 纳入开源 disagg 实现版图，讨论远端 KV 层对 rate matching 与传输 hop 的影响