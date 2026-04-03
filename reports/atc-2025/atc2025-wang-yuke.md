# GMI-DRL: Empowering Multi-GPU DRL with Adaptive-Grained Parallelism

**作者**：Yuke Wang (Rice University), Boyuan Feng (UC Santa Barbara), Zheng Wang (UC San Diego), Guyue Huang (UC Santa Barbara), Tong (Tony) Geng (University of Rochester), Ang Li (Pacific Northwest National Laboratory), Yufei Ding (UC San Diego)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wang-yuke
**源文件**：[[atc2025-wang-yuke.pdf]]

---

## 一、背景

深度强化学习（DRL）结合了传统 RL 算法与深度神经网络，在机器人、工业控制、自动驾驶等领域展示出超人水平的决策能力。最引人注目的应用包括 OpenAI ChatGPT（通过 RLHF 训练）。由于真实世界的成本、效率和安全问题，DRL 训练通常在模拟环境中进行，然后将预训练策略迁移到现实场景。

现代 DRL 应用为应对复杂动态场景（如电网控制、机器人），需要数百万/数十亿交互步才能收敛，因此亟需在多 GPU 平台（如 NVIDIA DGX-A100/H100）上进行大规模扩展。然而，DRL 计算具有独特的异构性：它交替执行三个组件——环境模拟器（物理仿真）、Agent（策略模型推理）和 Trainer（策略模型训练），它们的计算模式截然不同，且存在复杂的组件间交互。

---

## 二、要解决的问题

1. **GPU 利用率低下**：在 DGX-A100 上用 Isaac Gym 进行 PPO 训练时，GPU 利用率在时间维度（间歇性 DNN 推理/训练）和空间维度（计算/内存需求无法填满整个 GPU）上都很低。

2. **Fine-grained parallelism 遇到瓶颈**：传统做法通过增大 batch size 来利用更多 GPU 资源，但当 batch size 超过某个阈值后，不同 DRL 组件争抢固定 GPU 资源，导致性能先升后降、GPU 利用率也无法持续提高。

3. **缺少 sub-GPU 级别的通信支持**：现有高性能 GPU 通信库（如 NCCL）不支持 sub-GPU 粒度的通信，而 DRL 的异构任务之间存在大量跨组件数据交换，这成为性能瓶颈。

4. **资源-工作负载映射非平凡**：DRL 的三个组件具有不同的计算特性和资源需求，如何在 sub-GPU 上进行最优映射和配置是开放问题。

---

## 三、洞察与设计

**关键洞察**：与其将计算适配到固定硬件资源（增大 batch size 的 fine-grained parallelism），不如将硬件资源适配到计算需求——将一个大 GPU 拆分为多个大小可调的 sub-GPU（GPU Multiplexing Instance, GMI），为 DRL 的异构任务分别分配合适的资源量，从而在同一 GPU 上并行运行多个 DRL 组件实例，最大化资源利用效率。

基于此洞察，GMI-DRL 系统包含三个核心模块：

### 1. Adaptive Coordinator（自适应协调器）

**Task-aware GMI Mapping**：针对 DRL Serving 和 Training 两种场景，系统性探索了 DP-MP、MP-DP、DP-only 三种映射策略。通过资源-性能分析模型量化各方案的资源消耗和通信开销，选出最优映射。核心发现：
- DRL Serving 场景下，DP-only（模拟器和 Agent 共置于同一 GMI）最优，因为避免了频繁细粒度跨 GMI 通信
- Sync. DRL Training 场景下，DP-MP (EA-T)（经验收集与 Trainer 共置）最优

**Workload-optimized GMI Configuration**：通过 Saturation 指标检测单个 GMI 实例的吞吐饱和点，结合内存投影模型预测内存占用，联合优化每个 GPU 上的 GMI 数量和每个 GMI 的环境数量。

### 2. Specialized Communicator（专用通信器）

**Collective Composition**：针对跨 GMI 的模型梯度同步，设计了 Inter-process Primitive (IP) 和 Ring Primitive (RP) 的混合组合方案。通过一次性 profiling 基础通信原语的开销，自动搜索最优的 IP+RP 组合。

**Channel-based Experience Sharing**：针对 model-parallel DRL 中异构数据（状态向量、动作/奖励标量等）的传输问题，借鉴计算机网络中的 channel 概念，将不同类型数据按形状分组打包，通过最大化传输带宽利用率的代理指标 TOP_mov 优化分组策略。

### 3. GMI-centric Programming Support

提供基于进程的编程抽象，用户只需定义 GMI 上下文配置和 GMI 运行逻辑，系统自动处理资源分配、通信和调度。支持 MPS（训练场景，灵活通信）和 MIG（serving 场景，强隔离）两种 GPU 空间复用技术。

---

## 四、实现细节

- 基于 NVIDIA MPS 和 MIG 实现 GPU 空间复用，MPS 用于训练（通信灵活），MIG 用于 serving（隔离性好）
- 使用 PyTorch 构建策略模型，NCCL 和 Gloo 构建 GMI 间通信层
- Collective Composition 的搜索空间为 O(m) 级别（m 为每 GPU 的 GMI 数），通过 one-time profiling 两个基础组合的开销来估算所有候选方案的性能
- Channel-based Experience Sharing 的分组优化通过枚举组合学 + 回溯搜索（包类型数 n_t ≤ 10，评估成本低）
- 内存投影模型（Equation 4）可预测给定环境数量下的内存占用
- 设计可泛化至 Kepler、Pascal、Volta、Hopper、Blackwell 及桌面 GPU
- 代码开源：https://gitlab.com/YK-Wang96/gmi-drl-ae.git

---

## 五、实验结果

**平台**：NVIDIA DGX-A100（8× A100 GPU，双 AMD Rome 7742 CPU，共 128 核）

**基线**：Isaac Gym + MSRL PPO (IG(PPO))、IG(PPO)+NCCL、IG(PPO)+Horovod、IG(A3C)、Ray RLLib

**Benchmark**：6 种 DRL 环境（Ant、Anymal、BallBalance、FrankaCabinet、Humanoid、ShadowHand）

| 场景 | 对比基线 | 吞吐提升 | GPU 利用率提升 |
|------|---------|---------|---------------|
| DRL Serving | Isaac Gym | 最高 2.62×，平均 2.08× | 最高 45.7%，平均 27.9% |
| Sync. Training | IG+NCCL | 最高 2.07×，平均 1.69× | 最高 40.8%，平均 31.8% |
| Sync. Training | IG+Horovod | 最高 2.34×，平均 1.72× | — |
| Async. Training | IG(A3C) | 平均 1.88× PPS，1.65× TTOP | — |
| vs Ray RLLib | Ray PPO | 最高 62% 吞吐提升 | — |

**多节点扩展**：在 1-8 节点（1-2 GPU/节点）配置下，达到理想线性扩展的平均 83%。

**Mapping 分析**：DP-only serving 比 DP-MP 平均吞吐提升 110%（内存多用 9.5%）；DP-MP(EA-T) training 比替代方案平均吞吐提升 287.5%（内存多用 6.5%）。

---

## 六、批判性分析

1. **实验规模局限**：所有实验基于 DGX-A100（单节点 8 GPU），多节点实验仅扩展到 8 节点。对于 DRL 最前沿的大规模应用（如 RLHF for LLM），通常需要数百 GPU，系统在更大规模下的表现不明确。

2. **DRL 算法覆盖有限**：仅评估了 PPO（同步）和 A3C（异步）两种算法。现代 DRL 中广泛使用的 SAC、TD3、IMPALA 等算法未涉及，且这些算法的通信和计算模式可能与 PPO/A3C 显著不同。

3. **策略模型过于简单**：评估使用的策略网络都是小型 MLP（最大为 211:512:512:512:256:20），与当前 RLHF 场景中使用的数十亿参数 Transformer 模型相去甚远。当策略模型变大时，计算瓶颈会从模拟器转移到 Trainer，GMI 的资源分割方案是否仍然有效存疑。

4. **与 RLHF 的关联被高估**：论文在引言中提及 ChatGPT/RLHF 作为 DRL 的重要应用来吸引关注，但整篇论文实际处理的是物理仿真驱动的 DRL（locomotion、robotics），与 LLM RLHF 的计算特性差异巨大。

5. **MPS 的干扰问题被轻描淡写**：论文承认 MPS 不提供资源隔离，但在训练场景中仍选择 MPS。当多个 GMI 同时运行计算密集的模拟器和 GEMM 密集的训练任务时，cache thrashing 和内存带宽竞争的实际影响缺乏深入分析。

6. **通信优化的增量贡献**：Channel-based Experience Sharing 仅贡献了 24% 的整体性能提升，而 Collective Composition 在部分配置下提升不到 1%（如 AT 在 2G3T 下仅 0.4%）。这些组件的工程复杂度与性能收益不成正比。

---

## 七、AI Infra / MLSys 视角

1. **Sub-GPU 资源管理的思路可借鉴**：GMI 将 GPU 视为可调粒度的资源池而非固定单元，这一思路对 LLM 推理系统有启发价值。例如，在 LLM serving 中，prefill 和 decode 阶段的计算特性差异类似于 DRL 中模拟器与 Trainer 的差异，可探索类似的 sub-GPU 资源分配策略（与 Splitwise/DistServe 的 disaggregation 思路互补）。

2. **异构任务混合调度**：LLM 训练流水线中也存在异构阶段（前向/反向/通信/优化器更新），GMI-DRL 的 task-aware mapping 和 resource-performance analysis 方法论可迁移到流水线并行的阶段调度中。

3. **通信原语组合优化**：Collective Composition 中 IP + RP 混合的思路，对设计跨 NVLink/PCIe/InfiniBand 混合拓扑下的自适应通信策略有参考价值，尤其在 MoE 模型的 All-to-All 通信优化中。

4. **值得跟进的方向**：
   - 将 adaptive-grained parallelism 扩展到 LLM RLHF 场景，处理大策略模型 + 环境交互的混合工作负载
   - 探索在 H100/B200 的更细粒度 MIG 支持下，sub-GPU 资源分配对 LLM serving 多租户场景的优化

---

## 八、总结

GMI-DRL 是首个通过 adaptive-grained parallelism 在多 GPU 平台上扩展 DRL 训练和 serving 的系统。其核心创新在于 GPU Multiplexing Instance (GMI) 概念——将 GPU 拆分为大小可调的 sub-GPU 单元，配合 task-aware mapping、collective composition 和 channel-based experience sharing，在 DGX-A100 上实现了最高 2.34× 的训练吞吐提升和 40.8% 的 GPU 利用率改善。主要局限在于仅验证了小型策略模型和物理仿真 DRL 场景，能否泛化到大模型 RLHF 等计算密集场景有待验证。
