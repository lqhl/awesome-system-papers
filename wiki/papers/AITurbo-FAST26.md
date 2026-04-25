---
type: paper
name: AITurbo
full_title: "Fast Cloud Storage for AI Jobs via Grouped I/O API with Transparent Read/Write Optimizations"
authors: [Yingyi Hao, Ting Yao, Xingda Wei, Dingyan Zhang, Tianle Sun, et al.]
venue: FAST
year: 2026
tags: [cloud-storage, ai-infra, checkpoint, kv-cache, rdma]
source_pdf: "[[fast2026-hao.pdf]]"
source_md: "[[fast2026-hao]]"
---

# Fast Cloud Storage for AI Jobs via Grouped I/O API with Transparent Read/Write Optimizations (FAST 2026)

> **一句话总结**：在 disaggregated 云存储上引入 grouped read/write API，让存储层利用空闲 host DRAM + 高带宽 compute fabric 自动做 deduplication 和负载均衡 I/O 规划；checkpoint 写比 SFSTurbo 快 3.9–58.8×、比 [[Gemini]] 快 5.9×、KVCache 读比 [[Mooncake]] 快 1.28×，已部署在 HUAWEI 云生产环境。

## 问题

云上 AI job（训练 checkpoint 读写、推理 autoscaling、[[KV-Cache]] 读取）已占 HUAWEI 云本地数据中心存储带宽 >10%，文件大（百 MB–几十 GB），bulk + asynchronous + grouped 是核心特征。但 disaggregated cloud storage 难以满足带宽：

1. **加带宽 = 加钱**：1.6 → 80 GBps 的 backend 带宽涨 16× 单 GB 价格；frontend S-NIC 还有硬上限（如 100 Gbps），单加 backend 也无用。
2. **应用级优化复杂**：[[Megatron]] 1/4 代码在做 checkpoint 优化，仍因为不了解 disaggregated 架构而次优；OpenSora 等多模态框架完全没做。Deduplication 模式因 [[ZeRO]] 1/2/3 + DP 组合而多变，应用难穷举。

## 核心方法

AITurbo 基于两个洞察：(i) AI 集群 host DRAM 与 [[NVLink]]/RDMA compute fabric 在训练/推理时常空闲，可作高速 staging buffer；(ii) 一个简单的 **grouped I/O API**（每个 client 不仅指定文件还指定参与 group）就能让存储层从全局视角自动派生最优 I/O plan。

**Grouped API**：`group_getfile / group_putfile`，外加 `future_0`（DRAM staged）和 `future_1`（持久化）两个 future 用于异步。训练 group = 所有训练进程；推理 autoscaling = 所有新拉起的 inference job。

**Job Controller 写计划**（§4.1）三步：
1. **Deduplication**：XPU 在芯片上用 [[BLAKE3]] kernel 算 chunk checksum（V100: 7.8ms/GB vs CPU 35.6ms），controller 据此识别重复（DP > 1 时 parameter 必重复）。
2. **Load-balanced staging**：把去重后 payload 用 bilinear programming 写入 DRAM staging buffer（最小化 t），可被 [[ZeRO]] 风格 sharding 启发式求解。
3. **Persist**：从 DRAM 异步刷到 storage server（应用若不需 durability 可跳）。

**读计划**（§4.2）：从 storage 拉到一个 staging node 后，用 [[Compute-Fabric]] 上的 broadcast（参考 [[NCCL]] 风格）分发到所有 group 内 XPU，避免重复读 storage。

**Communicator**（§4.3）抽象 RDMA 上的多对多传输，配合 staging buffer manager 跨服务器协调闲置 DRAM。失败时检查 future_1 未 ready 则把对应文件标记 broken，留给应用恢复。

## 关键结果

- Checkpoint 写：比 SFSTurbo（3FS 类系统）快 3.9–58.8×；比 [[Gemini]] 快 5.9×。
- KVCache 读：比 [[Mooncake]] 快 1.28×（agent workload 共享 system prompt 的 batched access）。
- 应用代码改动通常仅几百行（vs Megatron 1/4 codebase 做 checkpoint 优化）。
- 已在 HUAWEI 云生产部署，覆盖训练 checkpoint，推理扩展中。
- Limitation：仅加速 bulk transfer；与同 XPU 上 co-located 任务的更精细隔离留作 future work。

## 相关

- **相关概念**：[[Checkpoint]]、[[KV-Cache]]、[[RDMA]]、[[Compute-Fabric]]、[[Deduplication]]、[[Disaggregated-Storage]]
- **同类系统**：[[Gemini]]、[[Mooncake]]、[[Megatron]]、[[3FS]]、[[OpenSora]]
- **同会议**：[[FAST-2026]]
