---
type: paper
name: FineMem
full_title: "FineMem: Breaking the Allocation Overhead vs. Memory Waste Dilemma in Fine-Grained Disaggregated Memory Management"
authors: [Xiaoyang Wang, Yongkun Li, Kan Wu, Wenzhe Zhu, Yuqi Li, Yinlong Xu]
venue: OSDI
year: 2025
tags: [disaggregated-memory, rdma, memory-management, allocation, isolation]
source_pdf: "[[osdi25-wang-xiaoyang.pdf]]"
source_md: "[[osdi25-wang-xiaoyang]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# FineMem: Breaking the Allocation Overhead vs. Memory Waste Dilemma in Fine-Grained Disaggregated Memory Management (OSDI 2025)

> **一句话总结**：[[RDMA]] DM 因 MR 注册（4MB ~480µs）被迫粗粒度分配导致浪费；FineMem 用 MR 预注册 + Memory Window 隔离 + 计算节点 trusted allocation service + 双层 bitmap 单边分配，分配延迟最高降 95%，利用率提升 2.25–2.8×，应用开销 2.5–4.1%。

## 问题与动机

[[Disaggregation]] 内存池上，远端分配需 MR 注册、pin 页表、更新 RNIC MTT，4MB 注册 ~480µs，迫使 FUSEE/FastSwap 等系统按 GB 级粗粒度抓取，造成碎片与浪费（YCSB-A 上 2MB vs 1GB 块大小吞吐差 17% 但内存省很多）。

## 关键观察 / 隐含假设

- **观察 1**：预注册整池 MR 可去掉分配路径注册，但裸 MR 无法在多 tenant DM 系统间隔离。
  - **依赖假设**：RNIC 支持 Memory Window（MW），可按 chunk 预绑定 rkey；计算节点有 trusted allocation service 保护元数据。
  - **可能失效场景**：无 MW 或 rkey 刷新速率不足时隔离与性能 tradeoff 恶化。
- **观察 2**：单边 bitmap 分配在并发下 CAS 重试导致延迟不可预测（ThreadTest 32 客户端恶化）。
  - **依赖假设**：双层 bitmap（section/span）+ contention 标记可把重试导向低竞争区域。
  - **可能失效场景**：极高并发同一 section 时仍可能热点。
- **假设 1**：共享池上多类 DM 系统（swap、kv、malloc）并存，必须防 cross-tenant 读写元数据与数据。
  - **证据强度**：强——图 3 攻击模型动机明确。

## 核心方法

**隔离**：每 chunk MW + rkey；分配 service 独占元数据 rkey；应用经 IPC 调 `malloc/free`。

**分配**：双层 bitmap tree，section 128KB span、chunk 4KB 起；metadata cache + batch read 降 RTT；contention bit 引导退避。

**崩溃一致性**：64-bit bitmap 嵌 temporary log + timestamp；compute node 失败后 redo log 恢复。

**集成**：FineMem-User（mimalloc）、FastSwap、FUSEE 等端口。

## 设计取舍

- **取舍 1**：trusted per-compute service 增加信任边界与 IPC，换元数据安全与无 memory node CPU 参与。
- **取舍 2**：双层 bitmap 固定粒度层次，极大/非 2 幂分配需多次 CAS。
- **边界条件**：Linux 实现；4KB 对齐；共享池多系统并存。

## 实验与结果

- 分配延迟相对 SOTA **最高降 95%**。
- 内存利用率 **2.25–2.8×** vs 粗粒度管理；端到端开销 **2.5–4.1%**。
- FUSEE YCSB-A：on-demand MR 注册吞吐仅为 Premmap 的 26.7%（64 clients）。

## Critical Analysis

### 论证链条

MR 成本测量 → 预注册+MW 去注册热点 → 单边 bitmap 降 memory node CPU → 微基准与应用闭环，链条完整。崩溃一致性依赖 bitmap+log 工程细节，论文有 fail-slow 讨论。

### 假设压力测试

allocation service 被攻破则整池元数据危险；论文假设 trusted。超大规模池（TB）bitmap 内存与 CAS 扇出需测量。与 CXL 原生内存语义路径的对比论文在 related work 提及 MIND 等但未同条件对决。

### 实验可信度

FUSEE/FastSwap/mimalloc 覆盖 representative DM 系统；生产混合负载组合爆炸仍难穷举测试。

### 系统性缺陷

论文未讨论 allocation service 高可用、跨 compute node 故障风暴时的 log 恢复延迟；tail latency 分布未强调。

## 局限与 Future Work

- **局限 1**：依赖 RDMA MW 与 trusted service 部署模型。
- **Future work 1**：与 Mooncake 等推理 DM  workload 的端到端 tail latency 评估。
- **Future work 2**：CXL/CHI 路径下是否仍需 FineMem 式软件 rkey 管理。

## 相关

- **相关概念**：[[RDMA]]、[[Disaggregation]]
- **同会议**：[[OSDI-2025]]
