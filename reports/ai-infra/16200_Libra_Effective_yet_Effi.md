# Libra: Effective yet Efficient Load Balancing for Large-Scale MoE Inference

**作者**：Jaehoon Yang, Yushin Kim, Seokwon Moon, Yeonhong Park, Jae W. Lee（Seoul National University）
**会议**：ICLR 2026
**链接**：https://github.com/SNU-ARC/Libra
**源文件**：[[16200_Libra_Effective_yet_Effi.pdf]]

---

## 一、背景

MoE 架构（DeepSeek-V3、Qwen3MoE、GLM-4.5）通过稀疏激活实现了大规模参数扩展，但推理时面临严重的 expert 负载不均（load imbalance）问题。近年来模型趋势是放弃训练时的 auxiliary load-balancing loss 以换取更强的 expert specialization，导致推理时负载不均进一步恶化（Qwen3MoE 的 imbalance ratio 高达 2.5-2.75，远超 Qwen2MoE）。

在 Expert Parallelism（EP）部署下，负载不均导致 straggler effect：最慢的 GPU 决定整体延迟。

---

## 二、要解决的问题

现有系统级负载均衡方案存在 effectiveness 和 efficiency 的矛盾：

- **EPLB**（DeepSeek）：基于历史统计周期性复制 expert，但预测不准（过去不代表未来），token sharding 随机分配，效果差
- **Lina**（ATC'23）：基于 expert-selection-path lookup table 预测，预测精度低（Qwen3MoE 43.7%，GLM-4.5 11.8%），token sharding 均匀分配无视实际负载
- **HarMoEny**：基于精确 routing 结果做复制和 sharding，效果好但开销大（复杂算法在 GPU 上同步执行，延长关键路径）

核心矛盾：effective 的方案（基于精确信息）引入大开销；efficient 的方案（基于粗粒度预测）效果不佳。

---

## 三、洞察与设计

### 核心洞察

Transformer 中相邻层的 hidden states 变化缓慢，因此可以用当前层的 hidden states **投机执行**下一层的 gating function，以 70-80% 的准确率预测 expert 激活（远高于 Lina 的 20-30%）。

### 系统设计：Two-Stage Locality-Aware Execution

Libra 将 MoE 计算拆分为两阶段：

1. **MoE_local**：处理路由到本地 GPU 上 expert 的 token（无需通信，可立即开始）
2. **MoE_remote**：处理需要发往其他 GPU 的 token（依赖 token sharding 结果）

关键：MoE_local 不依赖 token sharding，可以与 token sharding + dispatch 并行执行，创造时间窗口隐藏开销。

### 三个核心机制

**1. Lookahead Predictor（预测器）**
- 用当前层 hidden states 投机执行下一层 gating function
- 准确率 70-90%（Table 1），远优于 Lina
- 预测开销极低（~0.03ms，Table 2）

**2. Locality-Aware Expert Replication Planning（复制规划）**
- 两阶段规划：
  - Phase 1：每个 GPU 复制本地 token 最频繁请求的远端 expert（增大 MoE_local 窗口）
  - Phase 2：迭代均衡——从最过载 GPU 取最热 expert 复制到最空闲 GPU
- 在 CPU 上执行，不占 GPU 关键路径
- 用双缓冲区（even/odd buffer）pipeline 化，复制开销完全隐藏

**3. Adaptive Token Sharding（自适应 token 分配）**
- 仅对 remote token 做分配（local token 已在 MoE_local 处理）
- 迭代贪心算法：每轮找最过载 GPU 的最热远端 expert，将 token 转移到持有该 expert 副本的最空闲 GPU
- 在 CPU 上执行，与 MoE_local 并行
- 用 AllGather 替代 All2All 做 dispatch，移除对 token sharding 的依赖

---

## 四、主要贡献

1. **首次同时实现 effective 和 efficient 的 MoE 负载均衡**——通过投机执行获得高精度预测，通过执行流重构隐藏所有开销
2. **Two-Stage Locality-Aware Execution** 新范式——将 MoE 计算按 token locality 拆分，创造并行窗口
3. **实测 19.2% prefill throughput 提升**（8× H200 GPU，Qwen3MoE + GLM-4.5）

---

## 五、关键实验结果

- **模型**：Qwen3MoE (235B)、GLM-4.5 (355B)
- **硬件**：8× NVIDIA H200-SXM5 (141GB HBM3e)，NVSwitch 900GB/s
- **场景**：Prefill（明确聚焦 prefill phase）

| 指标 | 结果 |
|------|------|
| Prefill throughput 提升 | 最高 19.2%（vs SGLang baseline） |
| 预测精度 | 70-90%（vs Lina 11-47%） |
| Imbalance ratio | 接近 1.0（vs baseline 1.5-2.5） |
| 预测开销 | 0.03ms（可忽略） |
| MoE 层总延迟 | 9.07ms（vs Lina 11.33ms, SGLang 13.61ms） |

端到端延迟（Table 4-13）：在大 batch + 长 context 场景下优势最大，TTFT 降低最高 27%（Qwen3MoE）和 12.7%（GLM-4.5）。

---

## 六、局限性

1. **仅评估 prefill 阶段**——明确采用 prefill-decode disaggregation 设定，decode 场景未评估
2. **单节点 8 GPU**——未验证多节点场景，NVSwitch 900GB/s 的高带宽是 Two-Stage Execution 有效的前提
3. **MoE_local 窗口依赖 batch size**——decode 小 batch 时 MoE_local 时间短，可能不足以隐藏 token sharding 开销
4. **投机执行假设隐状态缓慢演变**——在某些模型架构或特殊输入分布下可能不成立

---

## 七、个人评注

Libra 的核心洞察很漂亮：用 speculative gating execution 获得高精度预测，再用 locality-aware two-stage execution 隐藏所有开销。这解决了之前工作在 effectiveness 和 efficiency 之间的两难。

但其适用范围有明确边界：**prefill + 单节点 + 高带宽互联**。对于 decode 场景（小 batch、低 MoE_local 窗口）和多节点场景（跨节点带宽比 NVSwitch 低 18x），Libra 的设计假设不成立。这为 decode-focused、multi-node 的负载均衡方案留下了空间。

INET4AI'25 的 latency-optimal LB 算法（最小化搬运次数的 ILP/heuristic）与 Libra 的 replication planning 互补：Libra 优化 "复制什么到哪里"，INET4AI 优化 "如何最小化搬运代价"。
