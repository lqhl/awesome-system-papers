# Tiered Memory Management Beyond Hotness

**作者**：Jinshu Liu, Hamid Hadian, Hanchen Xu, Huaicheng Li（Virginia Tech）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/osdi25/presentation/liu
**源文件**：[osdi25-liu.pdf](../../papers/osdi-2025/osdi25-liu.pdf)

---

## 一、背景

随着图处理、机器学习等内存密集型工作负载的增长，集成 fast-tier（如 DRAM）和 slow-tier（如 CXL 内存）的分层内存架构（tiered memory）正成为云数据中心的标准配置。两层之间存在 2–3× 的性能差距，因此有效的数据分层（data tiering）至关重要。

现有分层内存管理系统几乎全部基于"hotness"（访问频率）来指导数据放置：频繁访问的"热"数据放在 fast-tier，冷数据放在 slow-tier。这一假设在直觉上合理，但忽略了现代乱序 CPU 中的关键因素 ——**memory-level parallelism (MLP)**。MLP 使得并发内存请求可以掩盖 slow-tier 的延迟惩罚，导致"热"数据并不一定是"性能关键"数据。

---

## 二、要解决的问题

1. **Hotness ≠ Performance-criticality**：高访问频率的数据（如顺序遍历数组）通常具有高 MLP，其 slow-tier 延迟大部分被掩盖；低频率但串行化的访问（如 pointer-chasing）反而对性能影响更大。微基准测试表明，将热页面放在 fast-tier 反而比将冷页面放在 fast-tier 性能差 34%。

2. **次优的数据放置**：现有粗粒度的 first-touch 分配策略无法识别真正性能关键的数据，导致性能关键数据被频繁迁移或错误放置。

3. **过度迁移开销**：现有系统采用激进的页面迁移策略，频繁搬迁非性能关键的页面。每次页面迁移平均耗时 12µs 且会阻塞应用线程，这些开销可能抵消甚至超过分层带来的收益。在 CXL 环境中，fast/slow-tier 延迟差距缩小，迁移开销相对更加突出。

4. **缺乏 MLP 感知的性能指标**：尽管 MLP 是体系结构领域的成熟概念，但在分层内存管理中被严重忽视。现有的热度采样和迁移机制缺乏一个有原则、准确、MLP 感知的性能度量。

---

## 三、核心设计

### AOL（Amortized Offcore Latency）指标

核心创新是提出 AOL = Latency / MLP，一个结合内存访问延迟和 MLP 的新性能指标。AOL 准确量化内存访问的真实性能影响：
- **高 AOL**（高延迟或低 MLP）→ 访问对性能影响大，应优先放在 fast-tier
- **低 AOL**（低延迟或高 MLP）→ 延迟被并行掩盖，放在 slow-tier 影响小

基于 AOL 构建的 slowdown 预测模型：S = P × K，其中 P = s_LLC / c（基础预测器，基于 LLC-Stalls），K = f(AOL) = 1/(a + b/AOL) 是 MLP 修正因子。模型仅需 4 个硬件性能计数器，且 a、b 是硬件相关但工作负载无关的常量，可通过两个极端微基准一次性标定。Pearson 相关系数达到 0.951（56 个工作负载验证）。

### Soar（Static Object Allocation based on Ranking）

基于 AOL 的 profiling-guided 静态对象分配策略：
1. **对象级性能 profiling**：通过 LD_PRELOAD 追踪对象分配/释放元数据，PEBS 采样 LLC miss，AOL 预测器估算时序性能。三条数据流融合后为每个对象计算累积性能贡献分数。
2. **对象排名与分配**：按单位分数（score/size）降序排列对象，将 top-N 对象放在 fast-tier，实现近最优初始放置，**消除运行时迁移开销**。

### Alto（AOL-based Layered Tiering Orchestration）

基于 AOL 的自适应页面迁移调节策略：
- 运行时周期性采样 AOL（默认 1s），用 AOL_low 和 AOL_high 两个阈值调节迁移强度
- AOL < AOL_low → 禁止页面提升（高 MLP，迁移无意义）
- AOL > AOL_high → 正常迁移（低 MLP，迁移有价值）
- 中间区域 → 按阶梯函数渐进调节
- 无缝集成到 TPP、NBT、Nomad、Colloid 四个现有系统，内核仅需 ~30 LOC 修改

---

## 四、实现细节

- **硬件计数器**：仅需 4 个 Intel PMU 计数器（OFFCORE_REQUESTS_OUTSTANDING.CYCLES_WITH_DEMAND_DATA_RD、OFFCORE_REQUESTS_OUTSTANDING.DEMAND_DATA_RD、OFFCORE_REQUESTS.DEMAND_DATA_RD、CYCLE_ACTIVITY.STALLS_L3_MISS）加上 CPU_CLK_UNHALTED.THREAD
- **Soar profiler**：使用 LD_PRELOAD 拦截 malloc/free/mmap/munmap，通过 backtrace() 按调用链分组相同类型对象；PEBS 低采样率（3000）追踪 LLC miss 的时间和地址分布；对象分配使用 libnuma 的 numa_alloc()，支持 C/C++/Python，无需修改应用代码
- **Alto 实现**：用户态通过 Linux perf 周期性采集计数器计算 AOL；内核态 ~30 LOC 修改页面迁移策略（限制 PAGE_NONE 标记数量或 promotion 候选页面数量）
- **AOL 阈值标定**：两个极端微基准（顺序访问 vs pointer-chasing）即可标定平台特定的 a、b 常量和 AOL_low/AOL_high 阈值
- **Algorithm 1**（对象评分）：根据对象访问比例 R、预测性能 p、AOL l 计算分数。低 MLP 对象（R < R_min, l < L_0）score = R×p×factor；高 MLP 对象（R > R_max, l < L_0）score = R×p/factor；其余 score = R×p。factor 默认为 8
- **开源**：https://github.com/MoatLab/SoarAlto

---

## 五、实验结果

**平台**：
| 平台 | CPU | DRAM | CXL | Fast/Slow 延迟 | Fast/Slow 带宽 |
|------|-----|------|-----|---------------|---------------|
| SKX（CloudLab） | 双路 Intel Skylake 10 核 | 96 GB DDR4/socket | 模拟 | 90/190 ns (2.1×) | 49/17 GB/s |
| SPR（本地） | Intel Sapphire Rapids 32 核 | 192 GB DDR5 | ASIC 128 GB CXL | 114/271 ns (2.4×) | 218/26 GB/s |

**工作负载**：GAPBS 图分析、GPT-2 推理、Redis 缓存、SPEC CPU 2017 HPC

### Soar 结果（50% slow-tier ratio）

| 工作负载 | Soar | Colloid | NBT | Nomad | TPP | NoTier |
|---------|------|---------|-----|-------|-----|--------|
| microbench | 34% | 60% | 58% | 58% | 58% | 46% |
| bc-urand | 16% | 58% | 68% | 123% | 875% | 67% |
| bc-twitter | 7% | 26% | 13% | 61% | 495% | 63% |
| bc-kron | 18% | 40% | 59% | 105% | 792% | 55% |
| sssp-kron | 14% | 25% | 18% | 29% | 760% | 39% |
| tc-twitter | 7% | 6% | 11% | 24% | 38% | 9% |
| 603.bwaves | 4% | 43% | 13% | 18% | 1246% | 9% |

- Soar 在 bc-urand 上即使 90% slow-tier 仍维持 <20% slowdown
- 在 CXL 真实平台上趋势一致

### Alto 结果
- Alto+TPP 比 TPP 提升 2–471%
- Alto+NBT 比 NBT 提升 1–23%
- Alto+Nomad 比 Nomad 提升 -2–35%
- Alto+Colloid 比 Colloid 提升 0–18%
- 页面迁移数量减少最高 127.4×
- 在 5/182 个配置中 Soar/Alto 略低于基线（最多 3%）

### 带宽竞争下
- Soar 在带宽竞争下仍优于所有基线 4–41%
- Alto 在中等竞争下有效，极端竞争（2× 延迟膨胀）下收益减弱

---

## 六、批判性分析

1. **微基准驱动的叙事过于理想化**：论文的核心论证（hotness ≠ performance）基于一个精心构造的双线程微基准（一个顺序、一个 pointer-chasing），但这代表了最极端的 MLP 差异场景。实际工作负载中 MLP 变异通常更微妙。虽然论文后续在真实工作负载上验证了收益，但改善幅度在某些负载上很小（如 tc-twitter 仅比 Colloid 差 1%），说明"hotness 失效"的程度高度依赖工作负载特性。

2. **Soar 的 profiling 假设值得推敲**：Soar 假设工作负载的内存访问模式在 profiling run 和实际运行之间一致。对于输入敏感的工作负载或有相变行为的长期运行服务，这一假设可能不成立。论文承认可扩展到在线 profiling，但未实现。

3. **AOL 阈值调优在带宽竞争下的局限性被低估**：实验清楚表明，默认 AOL 阈值在高带宽竞争下失效（AOL 范围从 30–140 膨胀到 95–270），需要手动调高阈值。论文将 auto-tuning 留作未来工作，但这恰恰是生产环境中最关键的场景——带宽竞争在多租户数据中心几乎是常态。

4. **对象内均匀访问假设**：Soar 假设对象内部的内存访问均匀分布。对于大型对象（如 17 GB 的图结构 O_8），不同区域可能有非常不同的访问模式和 MLP 特征。这一限制可能导致大对象的排名不准确。

5. **Alto+Nomad 的负面结果未充分解释**：Alto+Nomad 在 bc-twitter、bc-urand 和 gpt-2 上比 Nomad 差最多 2%，论文坦承"the underlying reasons are not yet clear to us"——这种未解释的性能退化暗示 AOL 调节机制与 Nomad 的非独占迁移策略之间存在未理解的交互。

6. **实验规模和负载多样性**：虽然涵盖了图处理、HPC、GPT-2 和 Redis，但缺少数据库（OLTP/OLAP）、KV 存储等重要的内存密集型工作负载类型。GPT-2 推理作为唯一的 ML 工作负载也偏小。

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理中的 KV Cache 分层**：AOL 的思想可直接迁移到 LLM 推理场景。KV cache 管理面临类似的热度 vs 性能关键性矛盾——高频访问的 KV 块未必是瓶颈（如 prefill 阶段高 MLP），而低频的 decode 阶段 pointer-chasing 式访问反而更关键。AOL 可用于指导 KV cache 在 GPU HBM / CPU DRAM / CXL 之间的分层放置。

2. **分布式训练中的内存管理**：大模型训练中（如 ZeRO、FSDP）涉及参数、梯度、优化器状态在 GPU 显存和 CPU 内存之间的 offloading。当前的 offloading 策略主要基于张量大小和访问时序，未考虑 MLP 效应。AOL 类指标可以更精确地指导哪些张量适合 offload。

3. **GPU 内存层级**：现代 GPU 有 HBM/L2/Shared Memory 等多级存储。虽然 AOL 的具体硬件计数器不适用于 GPU，但"延迟 / 并行度"的核心思想可以用 GPU 的 warp occupancy 和 memory coalescing 程度来类比，指导 GPU 内存管理策略。

4. **可跟进的研究方向**：
   - 将 AOL 指标适配到 GPU/NPU 等 AI 加速器上，研究 AI 专用硬件上的 MLP 感知内存管理
   - AOL 驱动的 KV cache 分层放置和 eviction 策略
   - 在混合精度训练中，利用 AOL 思想决定不同精度张量的放置层级
   - AOL auto-tuning 机制，使其适应数据中心动态负载变化

---

## 八、总结

本文挑战了分层内存管理中"热度即性能关键性"的核心假设，提出 AOL（Amortized Offcore Latency）指标，将内存访问延迟和 MLP 统一建模。基于 AOL 设计了两个互补的机制：Soar 通过 profiling-guided 的对象级静态分配实现近最优数据放置（消除迁移开销），Alto 通过自适应调节页面迁移强度过滤非必要迁移。两者在 NUMA 模拟和真实 CXL 平台上全面优于 TPP、Nomad、NBT、Colloid 等现有方案。主要局限在于 Soar 依赖离线 profiling、AOL 阈值在高带宽竞争下需手动调优，以及对象内均匀访问假设可能影响大对象的排名准确性。
