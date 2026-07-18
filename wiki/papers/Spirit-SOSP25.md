---
type: paper
name: Spirit
full_title: "Spirit: Fair Allocation of Interdependent Resources in Remote Memory Systems"
authors: [Seung-seob Lee, Jachym Putta, Ziming Mao, Anurag Khandelwal]
venue: SOSP
year: 2025
tags: [remote-memory, fairness, resource-allocation, rdma, swap]
source_pdf: "[[3731569.3764805.pdf]]"
source_md: "[[3731569.3764805]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Spirit: Fair Allocation of Interdependent Resources in Remote Memory Systems (SOSP 2025)

> **一句话总结**：swap-based [[Remote-Memory]] 中本地 cache 与 [[RDMA]] 带宽可互换达到相同吞吐（如 Stream ⟨100% cache,75% BW⟩ ≈ ⟨40% cache,100% BW⟩），[[DRF]] 固定需求假设失效；Spirit 用 Symbiosis 拍卖 + PEBS 运行时估计，最多 **+21.6%** 性能且满足 envy-freeness 等性质。

## 问题与动机

[[Remote-Memory]] 用本地 DRAM 作 cache、远端作 backing，多应用共享 cache 与网络带宽。与 CPU/内存/磁盘不同，**cache 与 bandwidth 强互依**且关系因应用而异（Memcached cache-sensitive vs STREAM bandwidth-sensitive）。swap 方案要求**透明**（不能改应用报需求），经典 [[DRF]] 需预先固定各资源需求，导致用户夸大需求→静态分区，性能次优。

## 关键观察 / 隐含假设

- **观察 1**：同一吞吐目标下，存在多条 (cache, bandwidth) 等效分配曲线，应用特异（Figure 1）。
  - **依赖假设**：吞吐可用 memory access rate 代理；PEBS 采样足够代表局部性。
  - **可能失效场景**：compute-bound（DLRM <3% 变化）时 allocator 无杠杆。
- **观察 2**：需求是「光谱」而非标量，离线难估，随 workload 漂移。
  - **依赖假设**：梯度下降回归 + 周期性拍卖可在 **~140ms** 收敛。
  - **可能失效场景**：剧烈流量突变时价格调整滞后。
- **假设 1**：性能公平（data access throughput 均衡）比 dominant share 公平更符合 remote memory 用户意图。
  - **证据强度**：中；理论证明 Pareto/ envy-free / sharing incentive + 实证。

## 核心方法

**Symbiosis 算法**（微观经济学拍卖）：均等初始分配 + 等额预算；应用按边际收益「购买」cache 或 bandwidth；价格随总需求调整，binary search 定价。

**运行时估计**：透明监控 swap/cache 交互，Intel [[PEBS]] 采样 + 回归得 performance(cache,bw) 曲面。

部署：多应用共享 RDMA remote swap；开源 https://github.com/yale-nova/spirit 。

## 设计取舍

- **取舍 1**：拍卖非 strategy-proof——靠系统侧估计而非用户申报规避撒谎。
- **取舍 2**：聚焦 swap-based 透明路径，非应用内定制 cache pin。
- **边界条件**：24 实例以内评测；DLRM 几乎不受资源分配影响。

## 实验与结果

- vs 传统多资源分配：**最高 +21.6%**（STREAM/Memcached/SocialNetwork/DLRM 组合）
- Symbiosis 理论：Pareto-optimal、envy-free、sharing incentive
- 平均收敛 **~140ms**
- 工作负载：Meta KV trace Memcached、DeathStarBench SocialNetwork、DLRM 等

## Critical Analysis

### 论证链条

互依曲线实证 →  reformulate 公平目标 → Symbiosis + 估计 → 性能与公平性质，逻辑闭合。从 swap 透明系统到「所有 remote memory 语义（如 kernel RDMA paging）」外推需验证页故障路径是否同样可观测。

### 假设压力测试

- **估计误差**：PEBS 稀疏采样在冷启动或 mmap 风暴时曲面失真。
- **多租户恶意**：应用通过 access pattern 博弈操纵估计——论文依赖透明监控，对抗模型未建。
- **带宽上限**：RDMA 拥塞时 price 机制是否仍收敛未详述。

### 实验可信度

真实 trace + 理论证明兼备；DRF/DRFQ 基线合理。规模限于 24 instances；缺与 hypervisor 级 global scheduler 对比。

### 系统性缺陷

Spirit 控制面故障时的 fallback 分配、与 OS swap 策略交互、tail latency 公平论文未讨论。

## 局限与 Future Work

- **局限 1**：compute-bound 应用几乎不受益。
- **局限 2**：拍卖收敛与 workload 突变 trade-off。
- **Future work 1**：与 [[Demeter]] 类 tiered memory 联合，测量 cache+远端分层+带宽三维公平。
- **Future work 2**：生产 RDMA 拥塞下 P99 throughput 公平验证。

## 相关

- **相关概念**：[[Remote-Memory]]、[[DRF]]、[[RDMA]]、[[Swap]]、[[PEBS]]
- **同类系统**：Infiniswap、Fastswap、LegoOS
- **同会议**：[[SOSP-2025]]
