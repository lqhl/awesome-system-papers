# NanoFlow: Towards Optimal Large Language Model Serving Throughput

## 论文基本信息

- **标题**: NanoFlow: Towards Optimal Large Language Model Serving Throughput
- **作者**: Kan Zhu, Yufei Gao, Yilong Zhao, Liangyu Zhao, Gefei Zuo, Yile Gu, Dedong Xie, Tian Tang, Qinyu Xu, Zihao Ye, Keisuke Kamahori, Chien-Yu Lin, Ziren Wang, Stephanie Wang, Arvind Krishnamurthy, Baris Kasikci（University of Washington / Tsinghua University / UCBerkeley / University of Michigan）
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/zhang-dingyan

## 研究背景与动机

LLM 推理即服务系统正面临巨大的算力压力：每周超过 2 亿 ChatGPT 用户，API 调用量持续翻倍。在 GPU 稀缺的情况下，**最大化硬件利用率**成为核心挑战。吞吐量（tokens/s/GPU）是衡量服务质量的关键指标。

**传统观点**：LLM 服务是**内存带宽受限**（memory-bound）的，因为：
- 模型参数巨大（GPT-3 175B 参数需要 5 张 A100 80GB）
- 自注意力机制的 KV-cache 随上下文长度二次增长

## 要解决的核心问题

如何在端到端 LLM 推理中实现**接近最优的理论吞吐量**，通过揭示和利用**设备内并行性**（intra-device parallelism）重叠异构操作？

## 主要贡献

1. **揭示现代 LLM 工作负载的 compute-bound 特性**：通过详细的成本模型和实验验证，证明批处理后大多数 LLM 服务实际上是计算受限的（而非内存受限）
2. **NanoFlow 框架**：将输入分成小 nano-batches，将操作复制到 nano-operations，通过流水线重叠不同资源类型的操作
3. **Auto-search 引擎**：两阶段 MILP 算法自动计算最优 nano-batch 数量、大小、顺序和 GPU 资源分配
4. **68.5% 接近最优吞吐量**：相比 vLLM/DeepSpeed-FastGen/TensorRT-LLM 平均提速 1.91 倍，达到理论最优吞吐量的 68.5%

## 研究方法与设计

### 关键发现：LLM 服务是 compute-bound 的

通过成本模型分析，论文得出了反直觉的结论：

对于批处理的预填充和解码请求：
- **GEMM 操作**（KQV 生成、O 投影、FFN）：compute-bound
- **KV-cache 加载**：memory-bound，但 GQA（Grouped Query Attention）显著降低了其负担
- **网络通信**（tensor parallelism 下）：network-bound，但现代数据中心 GPU 的 compute/network 比极高（200-300），通常不构成瓶颈

**验证**（LLaMA-2-70B，8×A100）：
- 实测 T_compute ≈ 114ms，T_memory ≈ 45ms，T_network ≈ 31ms
- **总时间受 compute 限制**，T_compute / T_total ≈ 55%

### 为什么现有系统离最优远？

现有系统（如 vLLM、SGLang）在设备内**顺序执行**不同类型的操作：

```
[DecAttn] → [KQV] → [PF] → [O] → [UGD] → [AG] → [O.AR] → ...
每个阶段：计算密集型 ←→ 内存密集型 ←→ 网络密集型
                                                    ↑
                                              "WASTED" 气泡
```

这种顺序执行导致**最受限资源（compute）被浪费**：当执行内存密集型操作时，计算资源空闲。

### NanoFlow：设备内并行

**核心思想**：将操作分成 nano-operations，让它们在不同 nano-batches 上**并行执行**：

```
Layer i:  DecAttn₁ (R=0.4)  ════════════════════════▶
          KQV₂ (R=0.4)      ════════════════════════════════▶
          UGD₁ (R=0.8)       ════════════════════════════════════════▶
          O₁ (R=0.9)         ══════════════════════════════════════════════▶
          AG₁ (R=0.2)        ═══════▶
          ...
```

每个 nano-operation 仅使用部分 GPU 资源（R=资源利用率），多种 nano-operations **同时运行**，最大化每种资源的利用率。

### Auto-search：自动计算最优流水线

两阶段 MILP 算法：

**Stage I**：忽略内核干扰，搜索初始流水线结构（数量、大小、顺序）

约束：
- 至少两个 nano-operations 才能重叠
- batch size 来自 profiling 数据
- 依赖关系从 PyTorch 实现推导

**Stage II**：加入内核干扰模型（来自 profiling 的 R→P 映射表），细化资源分配

**干扰建模**：
- 实测每对（GEMM 实现, GEMV 实现）的性能
- 构建 R→P 查找表（资源利用率 → 实际性能）

### NanoBatch 调度

- **批内优先级**：优先调度未完成的解码请求，按 token 粒度填充
- **异步调度**：GPU 执行与 CPU 端调度并行（下一 iteration 的批在当前 iteration 执行时形成）
- **KV-cache SSD Offloading**：多轮对话的 KV-cache 通过分层缓存（CPU 内存 + SSD）管理

## 关键实现细节

### LLaMA-2-70B 流水线示例（Auto-search 生成）

- **第一部分**（重叠 KQV₁₋₄）：4 个 nano-operations，decode attention 利用率 R=0.4（节省 40% GEMM 性能换取 80% attention 性能）
- **第二部分**（重叠 GEMM + 网络）：仅 2 个 nano-operations，优先 GEMM
- **资源利用率总和约束**：任意时刻 ΣR ≤ 1.0

### Profiling 数据

在 A100 上对约 100 个 GEMM-GEMV 实现对进行干扰 profiling，简化搜索空间（排除效率低的实现对）。

## 实验结果与分析

### 吞吐量对比（LLaMA-2-70B, 8×A100 DGX）

| 系统 | 相对吞吐量 | 占最优比例 |
|------|-----------|-----------|
| vLLM | 1.0× | 22.0% |
| DeepSpeed-FastGen | 1.04× | 22.9% |
| TensorRT-LLM | 1.72× | 37.8% |
| **NanoFlow** | **1.91×** | **68.5%** |

NanoFlow 平均提速 1.91×，达到理论最优的 68.5%。

### 其他模型

| 模型 | NanoFlow 吞吐量提升 vs vLLM |
|------|--------------------------|
| LLaMA-3-70B | 2.66×（72% 最优） |
| LLaMA-3-8B | 2.66×（50% 最优） |
| DeepSeek-67B | 2.66×（72% 最优） |
| Qwen2.5-72B | 2.66×（72% 最优） |
| Mixtral 8×7B | 2.66×（70% 最优） |

### Auto-search 效率

- 约 10 分钟生成最优流水线（vs 数天的穷举搜索）
- 流水线可复用至数周的部署时长

## 潜在问题与局限性

1. **调度复杂性**：nano-batching 增加了调度器复杂性，实际部署中的 corner case 需要充分测试
2. **KV-cache 管理**：SSD offloading 的延迟管理、NUMA 优化等细节在论文中未充分展开
3. **Profiling 开销**：Auto-search 需要大量 profiling 数据（100+ 个 kernel 对），对新硬件/新模型的适配成本较高
4. **模型特异性**：流水线针对特定模型架构（LLaMA-2-70B）生成，换模型需要重新搜索
5. **理论最优推导的假设**：假设 GPU compute 是唯一瓶颈，但实际系统中 CPU 调度、内存分配等也可能成为瓶颈
6. **实验仅在 NVIDIA A100 上验证**：在 AMD、Intel、HBM 带宽差异大的硬件上表现未知
7. **多实例调度**：Auto-search 假设单个实例有充足请求，跨实例的负载均衡未讨论

## 未来工作方向

- 自适应流水线（在线调整 nano-batch 配置）
- 跨设备（多 GPU 节点）的扩展
- 与现有 serving 框架（vLLM、TGI）集成
- Learned cost model 加速 profiling

## 个人评注

1. **核心洞察反直觉且有说服力**：大多数 LLM 服务是 compute-bound 而非 memory-bound 是反直觉的，但成本模型分析和实验数据都有说服力。这个发现对系统设计有重要影响。

2. **Auto-search 的两阶段分解实用**：将 MILP 搜索空间分为"无干扰结构搜索"和"干扰感知资源分配"两阶段，显著减少了优化复杂度（约 10 分钟 vs 数天）。

3. **R→P 干扰模型的精度**：通过约 100 个 kernel 对的 profiling 构建查找表，并声称标准差在 5% 以内。但这个 5% 是对哪些 benchmark 而言？论文未明确，可能在某些极端场景下误差更大。

4. **轻微夸大**：
   - "reaches 68.5% of the theoretically optimal throughput"——但这个最优值本身是基于模型假设（如 compute 是唯一瓶颈）的理论推导，实际情况可能更复杂
   - "1.91× average throughput gain"是相对 vLLM 的相对提升，但 TensorRT-LLM 已经达到 1.72×，NanoFlow 的绝对增量约 11%

5. **与 BLITZSCALE 的潜在协同**：NanoFlow 优化单 GPU 设备内的操作重叠，BLITZSCALE 优化多实例间的扩缩容——两者在 LLM serving stack 中处于不同层次，可以正交结合。

6. **工程细节严谨**：MILP 公式完整，内核 profiling 方法论清晰，图 5 的干扰特性分析（GEMM-GEMV 性能权衡曲线）尤其有价值。
