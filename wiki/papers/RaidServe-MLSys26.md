---
type: paper
name: RaidServe
full_title: "RAIDSERVE: HIGH-PERFORMANCE RESILIENT SERVING"
authors: [RaidServe authors]
venue: MLSys
year: 2026
tags: [llm-serving, fault-tolerance, tensor-parallel, kv-cache, resilience]
source_pdf: "[[f033ab37c30201f73f142449d037028d.pdf]]"
source_md: "[[f033ab37c30201f73f142449d037028d]]"
---

# RAIDSERVE: HIGH-PERFORMANCE RESILIENT SERVING (MLSys 2026)

> **一句话总结**：[[Tensor-Parallel]] serving 遇 GPU 掉线时恢复慢且 KV/算力失衡；RaidServe 用 proactive [[KV-Cache]] backup、on-demand weight recovery（**183×** 加速恢复）、cyclic KV placement、hybrid attention 与细粒度 load-aware router，吞吐最高 **2×**、恢复比标准方案快 **两个数量级**。

## 问题与动机

生产 [[LLM]] [[TP]] 推理面临不规则 GPU 可用性（故障、抢占、维护）。传统恢复引发灾难性延迟尖峰；备份 everything 又太贵。需在性能与 resilience 间做系统级 co-design。

## 关键观察 / 隐含假设

- **观察 1：恢复开销是 online serving 致命项——需 proactive backup + 按需权重恢复压缩恢复时间。**
  - **依赖假设**：183× recovery acceleration 可换算为 TTFT/尾延迟不被 spike。
  - **可能失效场景**：频繁故障时 backup 带宽本身成为瓶颈。

- **观察 2：故障后幸存 GPU 间 memory/compute 失衡；cyclic KV placement + hybrid attention 重平衡利用率。**
  - **依赖假设**：hybrid attention 在降级模式精度可接受（论文需以实验支撑 claim）。
  - **可能失效场景**：极端少卡存活时质量/延迟仍不可服务。

- **观察 3：细粒度 load-aware router 在不稳定拓扑下维持吞吐，最高 **2×** vs 标准 fault handling。**
  - **依赖假设**：router 可见实时卡健康与 KV 布局。
  - **可能失效场景**：跨节点 IB 分区时 router 决策滞后。

- **假设 1**：TP serving 是主要目标并行形态（非 EP/PP 混合）。**
  - **证据强度**：**中**——与主流云 TP 部署一致，但未覆盖 disaggregated。

## 核心方法

**Proactive KV backup**：关键状态预复制，降恢复冷启动。

**On-demand weight recovery**：比全量 reload 快 **183×**。

**Cyclic KV placement**：故障后重分布 KV 减碎片与热点。

**Hybrid attention + load-aware router**：算力/内存再平衡与请求路由。

## 设计取舍

- **Proactive backup vs 存储/带宽成本**：换两个数量级更快恢复。
- **Hybrid attention vs 精确 attention**：换可用性与吞吐。
- **复杂度 vs stock [[vLLM]]**：工程集成成本高。
- **边界条件**：tensor-parallel LLM inference；fault 模型需读全文细节。

## 实验与结果

- Recovery：**183×** faster vs standard path（作者 claim）。
- Throughput：up to **2×** under irregular GPU availability。
- vs 标准 fault handling：两个数量级恢复加速 + 更高吞吐。

## Critical Analysis

### 论证链条

故障→延迟尖峰+失衡是已知痛 → 备份+布局+路由组合 → 大幅改善，需确认精度 SLO 未牺牲。183× 可能指权重恢复子阶段，非端到端用户感知。

### 假设压力测试

MoE EP、[[PD-Disaggregation]] 多池故障模式更复杂。与 [[RaidServe]] 名类似的 erasure coding 开销在满载 GPU 时未长期压测。

### 实验可信度

系统指标吸引人；缺：公开 trace、quality under hybrid attention、与 [[Guard]] 预防性维护协同。

### 系统性缺陷

论文未讨论 backup 一致性、脑裂、多副本成本会计。合规/租户隔离下 KV 备份风险未谈。

## 局限与 Future Work

- **局限 1**：TP-centric，异构并行扩展未充分验证。
- **局限 2**：hybrid attention 质量边界需更清晰。
- **Future work 1**：与 PD disaggregated pools 联合 fault drill。
- **Future work 2**：自动化 backup 频率 vs $/reliability Pareto 测量。

## 相关

- **相关概念**：[[KV-Cache]]、[[Tensor-Parallel]]、[[Fault-Tolerance]]、[[LLM-Serving]]
- **同类系统**：[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]
- **对比**：[[Guard]]（训练 straggler）