---
type: paper
name: LatencyOptimal-MoELB
full_title: "Latency-Optimal Load Balancing for Distributed MoE Inference"
authors: [Venkata Pavan Kumar Miriyala, German Sviridov, Bingxu Chen, Haris Javaid]
venue: INET4AI
year: 2025
tags: [moe, load-balancing, expert-parallelism, ilp, deepseek-v3, amd]
source_pdf: "[[3769695.3771675.pdf]]"
source_md: "[[3769695.3771675]]"
---

# Latency-Optimal Load Balancing for Distributed MoE Inference (INET4AI / CoNEXT Workshop 2025)

> **一句话总结**：发现 EPLB（DeepSeek-V3 提出的 LB 算法）单次平衡要搬运 13036 个 expert，引入的延迟是其收益的 ~10×。提出 ILP 公式 + heuristic 算法**联合优化负载均衡和搬运代价**，搬运量降到 2440（−57%），LB 频率提升 2×，MoE 总延迟下降 12.5%。

## 问题

[[MoE]] 的 expert parallelism 推理面临 expert load imbalance：少数热 expert 让所在 GPU 成为 straggler。

主流 system-level 方案是 **expert-to-device (E2D) 重分配**，其中 SOTA 是 DeepSeek-V3 提出的 **EPLB**——周期性把热 expert 复制到多 GPU、冷 expert 配平。然而 EPLB 只优化「分布有多均衡」，**完全忽略均衡过程本身的搬运代价**。

cost-benefit 分析显示：
- 一次 EPLB 调用搬运 ~13036 个 expert（每 GPU 平均换 28/32 个 expert）
- 总 LB 延迟比理想均衡带来的收益**大 ~10×**
- 因此只有当 expert 分布在 ≥ 10 个连续 forward pass 内稳定，LB 才划算
- 而 OpenOrca/MBXP/GSM8K 三个 dataset 在 DeepSeek-V3 不同 layer 都显示 expert 分布快速漂移

## 核心方法

**关键洞察**：负载均衡的核心目标不是「最优分布」而是「最低端到端延迟」——必须把搬运代价、算法运行代价和 forward pass 延迟一起放进目标函数。

**ILP 公式**：决策变量 `p_kv ∈ {0,1}` 表示 expert k 是否放在 GPU v 上。目标：

$$\min(c^{(a)} + \max_v c^{(s)}_v + \max_v c^{(m)}_v)$$

- `c^{(s)}_v`：GPU v 处理 token 的成本（kernel 启动 + per-token 处理）
- `c^{(m)}_v`：GPU v 的搬运成本，用 weighted Hamming distance 计算（只算 0→1 的转入，1→0 不计成本）
- `c^{(a)}`：算法本身运行时间

约束：每 GPU expert 数上限 + 每 expert 总服务能力 = demand。

ILP 给出的解是 LB 收益 + 搬运代价的全局最优，但 runtime > 100s，不可在线用。

**Heuristic 算法**：
1. GPU 按当前负载排序
2. 从最忙 GPU 选最热 expert，与最闲 GPU 之间换 expert pair（用 binary search 在两 GPU 上找最优 swap pair）
3. 若 swap 后总成本降低则接受，否则回滚
4. 重复直到平衡或达到最大移动数

复杂度 O(E² log E)，runtime 0.17s（vs ILP 100s+，EPLB 0.26s）。

## 关键结果

实验：8×AMD MI300 + DeepSeek-V3 + SGLang 0.4.7

| 指标 | Baseline | EPLB | Heuristic | ILP |
|---|---|---|---|---|
| Mean/Max load | 0.650 | 0.998 | 0.996 | 0.999 |
| Mean Norm StdDev | 0.351 | 0.001 | 0.003 | 0.001 |
| Algorithm runtime | 0 | 0.26s | 0.17s | > 100s |
| Experts moved | 0 | 13036 | 2440 | 2223 |

- **搬运量 −57%**：13036 → 2440
- **LB 总延迟 ~减半**：rebalancing latency −57%、algorithm runtime −31%
- **可 LB 2× 频繁**：原 EPLB 每 1000 iters 才划算，本方法每 500 iters
- **MoE 总延迟 −12.5%**（vs no-LB baseline）
- **自适应不 LB**：当 cost > benefit 时算法选择不做 LB；EPLB 没这个机制，每 1 iter LB 反而 −73%

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[Load-Balancing]]、[[ILP]]
- **同类方法 / 对比对象**：EPLB（DeepSeek-V3）、FasterMoE、FlexMoE、Tutel、Prophet、HarMoEny
- **同期工作**：[[Libra-arXiv26|Libra]]（同期 MoE LB 工作，互补——Libra 关注「复制什么到哪里 + 隐藏开销」，本文关注「最小化搬运代价 + 自适应跳过 LB」）；[[TransferEngine-arXiv25|pplx-garden]]（提供底层跨厂商 P2P RDMA 通信能力，可作为 LB 数据搬运的高效底层）
- **底层框架**：[[SGLang]]、AMD ROCm
- **评估模型**：DeepSeek-V3
- **数据集**：OpenOrca（对话）、MBXP（代码）、GSM8K（数学）
