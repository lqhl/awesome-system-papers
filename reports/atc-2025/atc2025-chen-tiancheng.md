# CrossPipe: Towards Optimal Pipeline Schedules for Cross-Datacenter Training

**作者**：Tiancheng Chen, Ales Kubicek, Langwen Huang, Torsten Hoefler（ETH Zurich）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/chen-tiancheng
**源文件**：[atc2025-chen-tiancheng.pdf](../../papers/atc-2025/atc2025-chen-tiancheng.pdf)

---

## 一、背景

随着 LLM 规模的指数级增长，单个数据中心已难以满足训练所需的算力和能源需求。Microsoft、Google、Amazon 等公司正转向核能等新能源方案为 AI 数据中心供电，但单一数据中心的扩展面临功率限制和故障脆弱性等挑战。业界趋势表明，部署多个较小设施比扩展单一大型设施更为实际。同时，在云环境中，一个区域内分配大量 GPU 往往不可行，跨区域 GPU 获取成为实际选择。然而，跨数据中心的地理分布引入了显著的通信低效问题（高延迟、低带宽），必须加以解决才能支持高效分布式训练。

---

## 二、要解决的问题

1. **静态调度在跨 DC 场景下失效**：现有的 pipeline parallelism 调度（如 1F1B、ZBV 等）假设通信开销可忽略（即单 DC 设置），直接应用到跨 DC 训练时，高通信延迟导致"bubble strides"——气泡在 pipeline 中沿关键路径成倍累积（1F1B schedule 的关键路径包含 O(n_mb) 次跨 DC 通信），严重降低训练吞吐。

2. **静态通信编排引入隐式同步**：Megatron-LM 等框架将 pipeline 通信操作分组（如 GPU0 同时向 GPU1 发送和接收），引入隐式同步。Send/Recv 的 rendezvous 协议要求双方同步，当 stage 执行时间存在差异时，接收端未能及时 post receive，导致发送端等待，气泡在 pipeline 中传播。

3. **跨 DC 并行维度选择不明确**：TP/SP/EP 因层级频繁通信不适合跨 DC；PP 和 DP 是跨 DC 流量的主要候选，但两者在不同网络条件下的性能权衡缺乏系统分析。

---

## 三、洞察与设计

**关键洞察**：在跨 DC 训练中，静态 pipeline schedule 的关键路径上跨 DC 通信次数与 microbatch 数量成线性关系（O(n_mb)），导致延迟被成倍放大；而通过动态重排 pipeline block 的执行顺序，可以将跨 DC 通信从关键路径上移除或减少，在不增加 peak memory 的前提下显著降低气泡率。

基于此洞察，CrossPipe 框架设计了以下核心组件：

1. **性能模型**：建立延迟-带宽感知的 pipeline 性能模型，将通信操作（含 latency 和 bandwidth delay）提升为与计算操作同等重要的一等公民，支持对 PP 和 DP 通信的统一建模。

2. **最优调度（Solver-based）**：将 pipeline scheduling 建模为约束优化（Constraint Optimization）问题，决策变量为每个操作的开始时间和共享设备/链路上的执行顺序，约束包括数据依赖、资源不重叠、设备内存容量限制和 microbatch 顺序。目标函数为最小化 makespan。

3. **贪心调度（Greedy）**：针对 solver 的可扩展性瓶颈，引入基于 sub-block splitting 的贪心算法（CrossUDSub）：将每个计算 block 拆分为 n_sub 个子块，以更细粒度填充气泡。调度循环包含 stage 选择（选择最早可调度的 stage）、操作选择（基于 warm-up/steady/tear-down 三阶段的启发式优先级）、操作调度（带宽占用模型处理链路争用）。

4. **两层抽象执行引擎**：将 block scheduling（高层调度逻辑）与 communication arrangement（底层通信编排）解耦。通信编排使用 4 个独立 GPU stream（Send/Recv × Next/Prev），避免死锁和干扰；基于 profiling 提前 post Recv 操作以最大化 overlap。

---

## 四、实现细节

- **基础框架**：基于 Megatron-LM 实现，CrossPipe 作为模块集成，主要用 Python 实现，C++ 组件用于延迟/带宽注入。
- **System Profiling**：单次迭代轻量级 profiling，收集 F/D/W block 的运行时间和内存使用量，以及通信延迟参数（α, β）。模型分割策略沿用 Llama 3，将 embedding 和 output 层视为 Transformer 层以确保负载均衡。
- **Schedule Selection**：静态 schedule 适合单 DC，动态 schedule 适合跨 DC；支持训练过程中 hot-swap 切换调度。
- **Execution Plan**：将选定的 pipeline schedule 转化为执行计划，插入非阻塞通信操作。使用 NCCL 作为通信后端，4 个专用 GPU stream 处理双向 PP 通信。Recv 操作基于 profiling 估计提前调度以减少同步等待。
- **延迟/带宽注入**：扩展 PyTorch ProcessGroup NCCL C++ 后端，在 receiver 端注入 latency delay（通过 host-side spinning），在 sender/receiver 双侧注入 bandwidth delay（通过 spinning kernel 占用通信 stream），用于在同质集群上模拟跨 DC 网络条件。
- **Solver**：CO solver 使用 CPLEX，MILP solver 使用 Gurobi；CO solver 在扩展性上优于 MILP（MILP 在 32+ stages 时 OOM）。
- **支持的 schedule 类型**：1F1B、IV1F1B（Interleaved 1F1B）、ZBH1、ZBV（静态），CrossUD、CrossUDSub、CrossWave（动态）。

---

## 五、实验结果

**平台**：Alps supercomputer，每节点 4 × GH200 Grace Hopper Superchip（96GB HBM3），NVLink 4.0（200 Gb/s/link/dir），HPE Cray Slingshot-11 Dragonfly 互连。

**模型**：Llama 风格 Transformer，M8（~8B，hidden=4096，30+2 层）和 M70（~70B，hidden=8192，62+2 层）。

| 实验 | 配置 | 关键结果 |
|------|------|----------|
| 延迟/带宽影响（M8/M70） | 2 DC, T_lat/T_F 和 T_bw/T_F ∈ {0, 0.5, 1.0, 2.0} | CrossPipe 最高降低 33.6%（vs 原始静态）或 21.9%（vs 优化后静态）的运行时间 |
| PP vs DP（Llama 3 405B 仿真） | 2 DC, 带宽 4-1024 GB/s, 延迟 4-128ms | Cross-DC PP 在 4 GB/s 带宽下比 cross-DC DP 快 3.05×；64 GB/s 时仅比理想单 DC 慢 1.3× |
| 进一步降低 bubble（M70） | 2 DC, 不同 GBS 和 memory budget | 放宽内存约束后，CrossPipe 可接近无延迟场景下的 ZBV 性能 |
| 4 DC 扩展 | M70, 4 DC, 2 stages/DC | CrossPipe 仍优于静态 schedule；(2,2) 延迟下 Case 3 的 CrossUD 为 0.178s/mb，仅比 2 DC 慢 22.8% |
| PP/DP 权衡 | M70, 2 DC, n_PP ∈ {4,8,16}, 固定 GBS | CrossPipe 的效率在不同 PP/DP 配置间基本不变 |

**性能模型准确性**：模拟预测值与实测在大多数配置下高度吻合。

---

## 六、批判性分析

1. **同质假设的局限性**：所有实验在同质集群上通过延迟/带宽注入模拟跨 DC 场景，而非真实的地理分布多数据中心。真实环境中的网络抖动、路由变化、异构硬件等因素未在实验中验证。作者在 Discussion 中承认了异构 DC 的问题，但未提供实验支撑。

2. **延迟注入的精度局限**：spinning kernel 的精度依赖 GPU 时钟精度和 host CPU 同步开销，在高延迟场景下误差较小，但在低延迟（几毫秒级）时相对误差可能更大。虽然 Figure 17 展示了验证结果，但仅针对单一消息大小（4GB）。

3. **Solver 方案的实用性存疑**：CO solver 在 8-16 stages 时需要数十秒到数百秒求解，16 stages 以上的收敛时间进一步增长。对于需要动态适应网络变化的场景，solver 的实时性不足。贪心算法虽然更快，但缺乏全局最优保证，论文仅通过 empirical comparison 论证其接近最优。

4. **DP 通信 overlap 假设过于简化**：实验中 n_DP=1（无跨 DC DP 通信），cross-DC DP 的建模假设 Allreduce/Reduce-Scatter 完全不 overlap。实际大规模训练（n_DP=64+）中 DP 通信的 overlap 和调度远比此复杂。

5. **缺乏端到端训练收敛验证**：所有实验仅测量 iteration time，未验证 CrossPipe 在实际训练（数千步以上）中的稳定性、收敛行为和数值正确性。

6. **模型规模有限**：最大测试模型为 M70（~70B），与当前 405B-1T 参数规模的实际训练有显著差距。虽然 Llama 3 405B 的仿真分析提供了方向性结论，但仿真与实际系统行为可能存在偏差。

---

## 七、AI Infra / MLSys 视角

1. **跨 DC 训练的系统化框架**：随着 LLM 规模超越单 DC 容量，跨 DC 训练将成为常态。CrossPipe 提供了第一个系统化的、延迟-带宽感知的 pipeline scheduling 框架，其性能模型和两层抽象设计（调度逻辑 vs 通信编排的解耦）对后续工作有重要参考价值。

2. **PP > DP 在跨 DC 场景的结论**：论文给出了有力证据表明 cross-DC PP 优于 cross-DC DP（尤其在带宽受限时），这对 AI Infra 的集群网络规划和并行策略设计有直接指导意义。特别是对于 MoE 模型（extra DP 通信量），PP 的优势更明显。

3. **可迁移的技术思路**：
   - Sub-block splitting 思想可应用于其他调度场景（如 EP 通信调度、heterogeneous pipeline 等）
   - 将通信操作建模为约束优化中的一等公民，而非事后优化，是一种值得借鉴的设计范式
   - 延迟/带宽注入技术为在同质集群上评估异构网络场景提供了低成本方法

4. **值得跟进的方向**：
   - **异构 DC + 异构 GPU 的联合调度**：不同 DC 使用不同代际 GPU（如 H100 vs GH200），需要同时优化层分配、recomputation 策略和 pipeline schedule
   - **与 EP/CP 的联合优化**：当前框架仅考虑 PP+DP，MoE 模型还需考虑 EP 的跨 DC 调度
   - **动态网络条件下的在线调度**：当前 hot-swap 需要 re-profiling，探索基于预测的 proactive schedule switching 可能更高效
   - **与 DiLoCo 等异步训练方法的结合**：CrossPipe 假设同步训练，与异步/半同步训练方法的对比和混合使用值得探索

---

## 八、总结

CrossPipe 是首个针对跨数据中心 LLM 训练的 pipeline parallelism 优化框架，通过延迟-带宽感知的性能模型和动态调度算法（solver-based 最优 + greedy 近最优），在相同内存约束下将跨 DC 训练时间降低最多 33.6%。其两层抽象执行引擎将调度逻辑与通信编排解耦，提供了良好的可扩展性和灵活性。主要局限在于实验仅通过延迟注入模拟跨 DC 场景，未在真实多 DC 环境中验证，且模型规模和 DP 配置相对保守。该工作为跨 DC 训练提供了系统化的理论分析和实用工具，随着多 DC 训练需求的增长，其方法和框架具有重要的实践价值。
