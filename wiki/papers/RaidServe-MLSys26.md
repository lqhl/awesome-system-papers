---
type: paper
name: RaidServe
full_title: "RAIDSERVE: HIGH-PERFORMANCE RESILIENT SERVING"
authors: [Ziyi Xu, Zhiqiang Xie, Swapnil Gandhi, Christos Kozyrakis]
venue: MLSys
year: 2026
tags: [llm-serving, fault-tolerance, tensor-parallel, kv-cache, resilience]
source_pdf: "[[f033ab37c30201f73f142449d037028d.pdf]]"
source_md: "[[f033ab37c30201f73f142449d037028d]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# RAIDSERVE: HIGH-PERFORMANCE RESILIENT SERVING (MLSys 2026)

> **一句话总结**：RaidServe 用 proactive [[KV-Cache]] backup、on-demand weight loading、cyclic KV placement、hybrid attention 和细粒度 routing 支持不规则 [[Tensor-Parallelism|TP]]；在 8×H100 的 Mooncake workload 中，它在固定 TTFT/TBT SLO 下比 Standard-TP4 最高多 2× throughput，而 Full recovery 将 GPU-state recovery 从 22 秒降至 120 毫秒（183×，§4.2–4.3，Fig. 10/13，Table 3）。

## 问题与动机

生产 [[LLM]] [[TP]] 推理面临不规则 GPU 可用性（故障、抢占、维护）。传统恢复引发灾难性延迟尖峰；备份 everything 又太贵。需在性能与 resilience 间做系统级 co-design。

## 关键观察 / 隐含假设

- **观察 1：恢复开销是 online serving 的关键项；host KV backup 与 on-demand weight loading 共同将 GPU-state recovery 从 22 秒降至 120 毫秒（§4.3.3，Table 3）。**
  - **依赖假设**：host memory 与 PCIe 带宽足以承载异步 backup/recovery。
  - **可能失效场景**：频繁故障时 backup 带宽本身成为瓶颈。

- **观察 2：故障后幸存 GPU 间 memory/compute 失衡；cyclic KV placement 与 hybrid attention 以精确的混合 TP/DP 执行重平衡利用率（§3.3–3.4）。**
  - **依赖假设**：剩余 GPU 与 NVLink 健康，且单节点仍能容纳模型与 KV state。
  - **可能失效场景**：driver/interconnect failure 或跨节点恢复不在论文 fault model 内。

- **观察 3：固定七张可用 GPU 时，细粒度 load-aware router 与 memory/compute balancing 在 10 秒 TTFT 或 40 毫秒 TBT SLO 下，比 Standard-TP4 最高达到 2× throughput（§4.2，Fig. 10）。**
  - **依赖假设**：router 可见实时卡健康与 KV 布局。
  - **可能失效场景**：跨节点 IB 分区时 router 决策滞后。

- **假设 1**：TP serving 是主要目标并行形态（非 EP/PP 混合）。
  - **证据强度**：**中**——与主流云 TP 部署一致，但未覆盖 disaggregated。

## 核心方法

**Proactive KV backup**：关键状态预复制，降恢复冷启动。

**On-demand weight loading**：与 proactive host backup 组合，避免全量 recompute 与冗余传输；183× 是 Full GPU-state recovery 相对 Recompute 的端到端 recovery 倍数，不是该组件单独的倍数（§3.2、§4.3.3）。

**Cyclic KV placement**：故障后重分布 KV 减碎片与热点。

**Hybrid attention + load-aware router**：算力/内存再平衡与请求路由。

## 设计取舍

- **Proactive backup vs 存储/带宽成本**：换两个数量级更快恢复。
- **Hybrid attention vs uniform TP**：通过混合 TP/DP placement 消除不规则 head 分配造成的 straggler；论文未引入近似 attention 或质量损失。
- **复杂度 vs stock [[vLLM]]**：工程集成成本高。
- **边界条件**：单个 8×H100 NVLink 节点上的 tensor-parallel inference；随机单 GPU fail/recover，幸存 GPU/NVLink 健康，不覆盖 driver/interconnect failures。

## 实验与结果

- **Fault-trace throughput**：相对 Standard TP，LLaMA-3.1-70B 与 Mixtral-8x22B 的 average token throughput 分别为 1.28× 与 1.71×，达到 Fault-scaled upper bound 的 95% 与 92%；相对 Non-Uniform TP 为 20% 与 17%（§4.1，Fig. 6–9；OpenThoughts-114k，GCP trace 缩放至 64 GPUs，在单台 8×H100 上仿真八个 8-GPU nodes）。
- **Online goodput**：固定七张可用 GPU、3,000 个 Mooncake requests 下，LLaMA prefill 在 10 秒 TTFT SLO 下比 Standard-TP4 / NonUniform-TP7 最高为 2× / 1.28×；decode 在 40 毫秒 TBT 下为 2× / 1.60×。Mixtral 相对 NonUniform-TP7 为 1.14× / 1.85×（§4.2，Fig. 10；无 runtime reconfiguration）。
- **Imbalance scaling**：LLaMA-3.1-70B 在 TP5/6/7 下，相对 NonUniform-TP 的 prefill peak-throughput 增益为 0%/16%/25%，decode 为 16%/51%/78%；TP4/TP8 时两者相同（§4.3.1，Fig. 11；Mooncake trace，4–8 H100）。
- **Balancing ablation**：LLaMA-70B TP7 上，compute balancing 将 prefill peak throughput 提高 25%；decode 中 cyclic memory placement 先提高 34%，compute balancing 再增 43%（§4.3.2，Fig. 12；增益为累积组件的增量）。
- **Recovery**：Recompute、RaidServe-Host、RaidServe-Full 与 Oracle 的 GPU-state recovery 分别为 22 秒、530 毫秒、120 毫秒和 15 毫秒；Full 相对 Recompute 为 183×。Host backup 将 P90/P99 max-TBT 从大于 10 秒降至少于 1 秒，on-demand loading 再将 P99 从 572 毫秒降至 229 毫秒（§4.3.3，Table 3，Fig. 13；单次 TP8→TP7 injected failure）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| RaidServe 在 fault-trace emulation 中提高 average token throughput | §4.1, Fig. 6–9 | OpenThoughts-114k；GCP trace scaled to 64 GPUs；单台 8×H100 仿真；简化单-GPU fault model | medium |
| RaidServe 在固定 TTFT/TBT SLO 下比 Standard-TP4 最高达到 2× throughput | §4.2, Fig. 10 | 3,000 Mooncake requests；7×H100 available；无 runtime reconfiguration | strong |
| Memory/compute balancing 的收益随 irregular TP imbalance 增长 | §4.3.1–4.3.2, Fig. 11–12 | LLaMA-3.1-70B；Mooncake；4–8 H100；peak throughput | strong |
| Full recovery 将 GPU-state recovery 从 22 秒降至 120 毫秒 | §4.3.3, Table 3, Fig. 13 | LLaMA-70B；TP8→TP7；request 250 后 100ms 注入单次 failure | strong |

## Critical Analysis

### 论证链条

故障→延迟尖峰+失衡是已知痛 → 备份+布局+路由组合 → 大幅改善。183× 是 GPU-state recovery 的子系统延迟，而用户可见影响由 max-TBT 实验单独刻画；论文的 hybrid attention 是精确计算，不涉及质量 SLO 牺牲。

### 假设压力测试

MoE EP、[[PD-Disaggregation]] 多池故障模式更复杂。异步 backup 在满载 GPU 时的长期开销未被独立量化。

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

- **相关概念**：[[KV-Cache]]、[[Tensor-Parallelism|Tensor-Parallel]]、[[Fault-Tolerance]]、[[LLM-Serving]]
- **同类系统**：[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]
- **对比**：[[Guard]]（训练 straggler）
