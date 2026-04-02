---
status: deprecated
date: 2026-04-01
keywords:
  - RDMA
  - Context Parallelism
  - LLM Training
  - P2P Communication
---

# P2P RDMA 驱动的动态 Context Parallelism

---

## 一、出发点

### 两个开源项目的交叉

- **TransferEngine**（Perplexity AI）：基于 Unordered Reliable Datagram 语义的 RDMA P2P 通信库，同时支持 NVIDIA ConnectX-7 和 AWS EFA。核心原语是 `WriteImm` + `ImmCounter`（无序完成通知）和 `submit_paged_writes`（非连续页面传输）。已在推理侧验证（disaggregated inference KV transfer、MoE routing、RL weight sync），MoE decode kernel 在 ConnectX-7 上甚至比 DeepEP 更快。
  - 论文：[[2510.27656v1|RDMA Point-to-Point Communication for LLM Systems]]（arXiv 2510.27656）
  - 代码：github.com/perplexityai/pplx-garden
  - 博客：abcdabcd987.com/2025/11/09/rdma-p2p-for-llm/

- **DCP**（HKU + AWS）：动态 Context Parallelism 框架，将 attention 计算分解为细粒度 block，通过超图划分为每个 batch 动态生成并行配置，解决变长序列和稀疏 attention mask 下的冗余通信和负载不均衡问题。
  - 论文：[[3731569.3764849|DCP: Addressing Input Dynamism In Long-Context Training via Dynamic Context Parallelism]]（SOSP 2025）
  - 代码：github.com/chenyu-jiang/dcp

### SOSP 2025 相关论文

| 论文 | 相关性 |
|------|--------|
| [[3731569.3764798\|Mercury: Unlocking Multi-GPU Operator Optimization via Remote Memory Scheduling]] | CommIR 的 shift 原语天然映射到 P2P 通信模式——编译器分析 shift offset 确定 sender/receiver rank 并生成 P2P send/recv。本工作的动态通信调度可视为 Mercury 静态编译方法在 per-batch 动态场景的延伸 |
| [[3731569.3764815\|Aegaeon: Effective GPU Pooling for Concurrent LLM Serving]] | Token 级抢占式自动扩缩容需要动态 GPU 分组，与方案 C（Elastic CP）的"CP group 大小随 batch 动态变化"直接相关——两者共同需要无 world 约束的通信原语 |
| [[3731569.3764848\|Mycroft: Tracing Dependencies in Collective Communication]] | P2P 通信缺乏 NCCL 集合操作的隐式全局同步，故障传播更隐蔽。Mycroft 的 chunk 级追踪方法论可迁移为 P2P transfer 的 per-write 级可观测性设计 |

### Context Parallelism 相关工作

| 方法 | 通信原语 | 模式 | 动态性 |
|------|---------|------|--------|
| Ring Attention（arXiv 2310.01889） | NCCL P2P send/recv | 固定环拓扑 | 无 |
| Striped Attention | NCCL P2P send/recv | 重排序环拓扑 | 无 |
| DeepSpeed Ulysses（arXiv 2309.14509） | NCCL AlltoAll | 全对全，head 维度划分 | 无 |
| USP（arXiv 2405.07719） | AlltoAll + P2P | 2D mesh（Ulysses + Ring） | 无 |
| NVIDIA Megatron Dynamic-CP | NCCL 多种 | 动态选择 CP 大小（2 的幂） | batch 级（粗粒度） |
| DCP（SOSP 2025） | NCCL all_to_all_single | 超图划分驱动 | block 级（细粒度） |
| **本工作（提议）** | TransferEngine P2P write | 超图划分驱动 | block 级 + 弹性 group |

---

## 二、问题分析：DCP 通信层的结构性瓶颈

DCP 的超图划分产出的是 **per-batch 的稀疏 P2P 通信图**，却被迫通过 `all_to_all_single` 这个稠密集合操作来实现。具体有三个瓶颈：

### 瓶颈 A：全员参与的浪费

`all_to_all_single` 要求所有 rank 同步参与，即使部分 rank 对之间无数据交换。DCP 作者不得不 fork PyTorch 支持 zero-byte send/recv 来绕过此限制（`chenyu-jiang/pytorch` 的 `alltoallv` 分支）——这本身说明 NCCL 语义不匹配。

> **待验证**：DCP 超图划分的目标是负载均衡，均衡划分下通信矩阵的稀疏度可能不高。需要在 Phase 0 用实际 partition 输出统计不同规模/mask 下的通信矩阵稀疏度（非零 rank 对占比），量化"浪费"的程度。如果稀疏度 <50%，此瓶颈的实际影响有限。

### 瓶颈 B：全局 barrier 阻碍 overlap

`all_to_all_single` 的完成语义是"所有数据全部到达后才能继续"。DCP 的 division 流水线试图重叠通信和计算，但每个 division 的通信必须等前一个 all_to_all 完成。

> **归因需谨慎**：DCP 论文分析 causal mask 端到端 0.94x 回退时，指出 causal mask 的三角结构导致**计算本身就不均衡**（靠后的 block 计算量更大），这是划分层面的问题。因此 0.94x 回退是通信开销 + 计算不均衡的叠加效应，P2P 替换只能解决前者。需要在 Phase 0 做时间分解，区分两个因素各自的贡献。

### 瓶颈 C：通信量未真正最小化

即使超图划分最小化了跨设备 block 数，all_to_all 仍需所有 rank 建立连接并交换控制信息。64 GPU 规模下，每个 rank 向 63 个 peer 发送/接收元数据（大多数 zero-byte）。

### TransferEngine P2P 为什么是正确的原语

| DCP 需求 | NCCL `all_to_all_single` | TransferEngine P2P |
|----------|--------------------------|-------------------|
| 稀疏通信 | 所有 rank 必须参与 | 只在有数据的 rank 对间发送 |
| 每 batch 拓扑不同 | 需要相同 communicator world | 无 world 概念，任意 peer 间随时通信 |
| 流水线 overlap | all_to_all 是同步点 | 每个 write 独立异步，ImmCounter 细粒度通知 |
| Block buffer 非连续内存 | 需打包为连续 buffer | `submit_paged_writes` 原生支持 |
| 完成通知 | all_to_all 返回即完成 | ImmCounter 精确计数，可触发 GPU-visible flag |

---

## 三、学术创新性评估

### 当前方案（DCP + TransferEngine 集成）的不足

如果只是"把 all_to_all 换成 P2P write"，reviewer 可能会说：

> "Sparse P2P communication is more efficient than dense all-to-all for sparse workloads — this is unsurprising. The contribution is primarily engineering integration."

具体问题：

1. **叙事太弱**：核心是 integration work，两个系统都已存在，API 映射自然
2. **提升增量**：causal mask 0.94x → ~1.1x（修复回退），sparse mask 3.77x → ~4.5x（~20% 改进）
3. **场景偏窄**：仅限长上下文训练的 context parallelism

### 升维方案

要达到 OSDI/SOSP 级别，需要从"优化 DCP 通信层"升维为更大的故事。

#### 方案 A：通用"动态稀疏通信"框架（工程量大，适合 OSDI）

提出 general-purpose 的动态通信调度框架，覆盖所有"每 batch 通信拓扑不同"的场景：

| 场景 | 动态性来源 | 当前做法 | 本框架 |
|------|-----------|---------|--------|
| Context Parallelism (DCP) | 序列长度方差 + 稀疏 mask | all_to_all（稠密） | 超图划分 → P2P plan |
| MoE routing | 每 token 路由不同 expert | all_to_all（最坏情况 buffer） | 路由表 → P2P scatter |
| Dynamic batching inference | 请求长度不同 | padding 到最大长度 | 按需 P2P KV transfer |
| RL post-training | 异步 weight sync | 全局 broadcast | 选择性 P2P write |

**叙事**：*"Collective communication was designed for static, uniform workloads. Modern ML workloads are dynamic and sparse. We propose X..."*

**评估**：有机会上 OSDI/SOSP，但需要 3-4 个场景完整实现。工程量 ~6 月 2-3 人。

#### 方案 B：通信-计算联合编译（技术深度高，适合 OSDI）

将 P2P 传输的延迟/带宽作为超图划分的约束条件：

- 将 multi-NIC 拓扑、NVLink/RDMA 异构带宽纳入划分目标函数
- 生成的不是 partition assignment，而是直接可执行的 P2P 调度序列（包含 overlap 时机）
- 本质上把 [[3731569.3764798|Mercury]] CommIR 的编译器思想用于动态场景

**风险**：编译器 cost model 难以准确，可能需要 profiling-guided 方法。

#### 方案 C：Elastic Context Parallelism（capability story，最适合 SOSP）

改变问题定义——不只是动态通信，而是 **动态并行度**：

- CP group 大小也是动态的：长序列用 16-way CP，短序列用 2-way CP，释放的 GPU 做 DP
- 训练过程中 GPU 可以加入/退出 CP group（弹性训练）
- CP 和 MoE 共享同一组 GPU 的通信资源（联合调度）

**核心论点**：NCCL 的 world 模型使这种弹性的实现代价极高——虽然 NCCL 2.19+ 的 `ncclCommSplit` 和动态 communicator 创建使其并非"根本不可能"，但每次 group 变化都需要昂贵的 communicator 重建，且无法避免全局同步。TransferEngine 的无 world P2P 天然支持任意 peer 间通信，无需 communicator 管理开销。这把"换通信库"变成"**P2P 大幅降低了动态并行策略的实现复杂度和运行时开销——这类策略在集合通信范式下虽非不可能，但代价过高以至于不实用**"。

这是 practical feasibility 层面的差异——从"理论上可行但工程上不可行"到"高效可行"。需要用实验量化 NCCL 动态 communicator 的开销作为 baseline，证明差距足够大。

### 方案评估矩阵

| 目标会议 | 当前方案（集成） | 方案 A（通用框架） | 方案 C（Elastic CP） |
|---------|------|------|------|
| **OSDI / SOSP** | 不够 | 有机会 | 最有机会 |
| **EuroSys** | 有机会 | 合适 | 合适 |
| **MLSys** | 合适 | 偏大 | 合适 |
| **ATC** | 合适 | 偏大 | 偏大 |
| 工作量 | ~11 周 1-2 人（Phase 0-3） | ~6 月 2-3 人 | ~5 月 2-3 人 |

---

## 四、技术可行性

### 4.1 API 映射

DCP 的 block buffer 与 TransferEngine 的 paged writes 之间存在自然映射：

```
DCP Block Buffer:                    TransferEngine Paged Write:
┌──────────────────────┐             ┌──────────────────────┐
│ contiguous buffer    │             │ src_mr / dst_mr      │
│ block_table[i] →     │     ═══>   │ page_indices[i] →    │
│   offset in buffer   │             │   offset in MR       │
│ block_size = B × D   │             │ length = page_size   │
│ stride = B × D       │             │ stride               │
└──────────────────────┘             └──────────────────────┘
```

- DCP `Q_buffer`, `KV_buffer`, `O_buffer` → TransferEngine registered MR
- DCP `block_table` offset → TransferEngine `page_indices`
- DCP block size `[1, B, D]` → TransferEngine `length = B × D × sizeof(dtype)`
- 超图划分结果 "block X: rank A → rank B" → `submit_paged_writes(src=A_mr, dst=B_mr_desc, pages=[X])`

### 4.2 完成通知映射

ImmCounter 替代 NCCL barrier：

```python
# 每个 division 分配一个 imm 值
imm_div_0 = 0x0100

# 发送方：每个 paged write 携带 division imm
engine.submit_paged_writes(..., imm_data=imm_div_0, ...)

# 接收方：等待该 division 所有 block 到达
engine.set_imm_count_expected(
    imm=imm_div_0,
    expected_count=num_blocks_in_div_0,
    on_reached=lambda: launch_div_0_compute()
)
```

无序到达也能正确触发——FlashAttention 的 online softmax 支持增量计算，block 到达顺序不影响结果。

### 4.3 细粒度 Overlap

P2P 语义允许比 DCP 更细粒度的 overlap：

```
当前 DCP (all_to_all):
  Div 0: [===== all_to_all =====][===== compute =====]
  Div 1:                         [===== all_to_all =====][===== compute =====]

P2P 细粒度 overlap:
  Div 0: [wr_1][wr_2][wr_3]...
         [compute_1 ← block arrived]
                [compute_2 ← block arrived]
                       [compute_3 ← block arrived]
  Div 1: [wr_4][wr_5]...    ← 可与 Div 0 计算重叠
```

Per-block ImmCounter：每个 block 到达即触发其 blockwise attention 计算。

### 4.4 与 DCP 代码的集成

DCP 开源 14K LOC Python + 300 LOC C++，需修改的模块：

| 模块 | 当前实现 | 修改 | 量级 |
|------|---------|------|------|
| Executor | `dist.all_to_all_single()` | TransferEngine P2P writes | 中 |
| Comm Launch/Wait | NCCL stream 同步 | ImmCounter + GDR counter | 中 |
| Block buffer 内存 | PyTorch tensor | 注册为 TransferEngine MR | 小 |
| Planner output | partition assignment | 转换为 P2P transfer plan | 小 |
| 自定义 PyTorch fork | zero-byte all_to_all | **完全不再需要** | 消除 |

### 4.5 风险

| 风险 | 等级 | 应对 |
|------|------|------|
| 小 block P2P 延迟高于 all_to_all | 中 | TransferEngine 8KB page 达 320 Gbps；DCP block 远大于 8KB |
| 大量并发 P2P 的 NIC 拥塞 | 中 | Multi-NIC sharding + DomainGroupRouting |
| Backward pass 正确性 | 低 | 与 forward 对称，反转 src/dst 即可 |
| TransferEngine 训练场景可靠性 | **中** | TransferEngine 目前仅在推理侧验证，训练的双向通信、梯度同步、长时间稳定性均未验证。Phase 1 需做 24h+ 稳定性测试 |
| 训练精度确定性 | 低 | 无序不影响 online softmax（加法交换律） |
| 与 TP 交互 | 低 | DCP 的 TP 正交设计不依赖通信原语 |

---

## 五、实现路线图

### Phase 0：环境搭建与关键假设验证（3 周）

> **Phase 0 是 go/no-go 决策点。** 以下三个数字决定这个方向的天花板，必须在投入更多时间之前拿到。

- [ ] 搭建 DCP 环境（Zenodo Docker image）
- [ ] 复现 DCP 原始 attention 微基准（Table 2）
- [ ] 安装 TransferEngine 并验证 P2P 吞吐基线

**关键测量（go/no-go 指标）：**

- [ ] **通信矩阵稀疏度**：在目标规模（16/32/64 GPU）和不同 mask（causal, sparse）下，统计 DCP partition 输出的通信矩阵中非零 rank 对占比。若稀疏度 <50%，瓶颈 A 影响有限
- [ ] **Causal mask 端到端时间分解**：profile DCP causal mask 端到端执行，分解为通信时间 / 计算时间 / 同步等待 / 划分不均衡空闲。量化通信层改进的理论上界
- [ ] **通信占比 roofline**：计算通信时间占总迭代时间的比例。若通信仅占 15%，即使完全消除通信开销也只提升 ~18%，整个方向天花板太低

**判断标准：**
- 通信矩阵稀疏度 >60% 且通信占比 >25% → 继续 Phase 1
- 通信占比 <15% 或 causal mask 回退主要由计算不均衡导致 → 重新评估方向

### Phase 1：通信层替换原型（3 周）

- [ ] 实现 P2P Transfer Plan Generator（partition_map → P2P transfer list + ImmCounter config）
- [ ] 实现 DCP P2P Executor（注册 MR、交换 descriptor、替换 Comm.Launch/Wait）
- [ ] 消除自定义 PyTorch fork 依赖
- [ ] 验证 forward pass 数值正确性（与 DCP 原始 bit-exact）

### Phase 2：Backward + 端到端训练（2 周）

- [ ] 实现 backward pass P2P 传输（dO, dQ block 交换）
- [ ] 验证梯度正确性（loss 曲线一致）
- [ ] 端到端训练：GPT-8B, causal + sparse mask
- [ ] 收集性能指标

### Phase 3：细粒度 Overlap 优化（3 周）

- [ ] 实现 per-block ImmCounter（block 到达即计算）
- [ ] 优化 division 调度算法（P2P 模式下放松通信量约束）
- [ ] Planner 加入 RDMA 带宽约束（multi-NIC 拓扑、NVLink vs RDMA）
- [ ] 重点攻克 causal mask 场景（DCP 弱项 0.94x → 目标 >1.1x）

### Phase 4：扩展（视目标会议选择）

**若冲 MLSys/EuroSys**（+2 周）：
- [ ] 跨硬件验证（ConnectX-7 + EFA）
- [ ] 与 Megatron Dynamic-CP 对比
- [ ] Ablation study

**若冲 OSDI/SOSP — 方案 C Elastic CP**（+8 周）：
- [ ] 实现动态 CP group 大小（per-sequence 选择 CP degree）
- [ ] 实现 GPU 在 CP/DP 间动态切换
- [ ] 证明弹性 CP 在集合通信下不可行
- [ ] 端到端评估 MFU 提升

---

## 六、实验设计

### 硬件

| 配置 | 规格 |
|------|------|
| 硬件 A | 4× p4de.24xlarge（8×A100, 4×100Gbps EFA）——与 DCP 原始一致 |
| 硬件 B | 4× 8×H200 + ConnectX-7 400Gbps（如果可获得）|
| 最小验证 | 2 节点 × 8 GPU + RDMA NIC |

### Baseline

- DCP-original（NCCL all_to_all_single）
- Ring Attention
- USP
- NVIDIA Megatron Dynamic-CP
- 标准 DP（无 CP，作为上界参考）

### 模型与数据

- GPT-8B（匹配 Llama 3-8B），4-way TP + 16-way CP
- LongDataCollections, LongAlign（与 DCP 原始一致）
- Attention mask：Causal, Lambda-shaped, Blockwise causal, Shared question

### 关键指标

- 通信冗余率：`(实际字节 - 最小必要字节) / 最小必要字节`
- 通信-计算 overlap 率：`1 - (非重叠通信时间 / 总迭代时间)`
- MFU (Model FLOPs Utilization)
- 迭代时间分解：规划 / 通信 / 计算 / 同步

### 预期结果

> **注意**：以下 DCP-P2P 预期数字为初步估计，需在 Phase 0 完成 roofline 分析后用定量模型重新推导。

| 场景 | DCP 原始 | DCP-P2P 预期 | 推导依据 |
|------|---------|-------------|---------|
| Causal mask FW+BW（微基准） | 1.19-2.45x vs baseline | 待 Phase 0 数据 | 取决于通信占比和 overlap 空间 |
| Sparse mask FW+BW（微基准） | 2.15-3.77x vs baseline | 待 Phase 0 数据 | 稀疏度越高，P2P 收益越大 |
| Causal mask 端到端 | 0.94-1.16x | 待 Phase 0 数据 | **关键风险**：回退可能主要由计算不均衡导致，P2P 无法解决 |
| Sparse mask 端到端 | 1.00-1.46x | 待 Phase 0 数据 | 最可能受益的场景 |

---

## 七、务实路径建议

1. **Phase 0 是第一个决策点**（3 周）：拿到通信稀疏度、时间分解、通信占比三个关键数字
   - 如果数据支持继续 → 进入 Phase 1-2（~5 周），总计 ~8 周拿到完整系统和性能数据
   - 如果数据不支持（通信占比低、回退主因是计算不均衡） → 及时止损或转向
2. Phase 2 完成后，根据数据决策：
   - sparse mask 场景收益显著 + causal mask overlap 有改进 → extend 到方案 C（Elastic CP）冲 OSDI/SOSP
   - 仅 sparse mask 有改进 → 聚焦稀疏 attention 场景，投 MLSys / EuroSys
   - 改进有限 → 停止
3. 最关键的验证点（按优先级）：
   - **Phase 0**：通信时间占总迭代时间的比例 —— 这决定了整个方向的天花板
   - **Phase 0**：causal mask 0.94x 回退中通信 vs 计算不均衡各贡献多少
   - **Phase 2**：端到端替换后的实际加速比
