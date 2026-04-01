# Tiered Memory Management Beyond Hotness

**作者**：Jinshu Liu, Hamid Hadian, Hanchen Xu, Huaicheng Li (Virginia Tech)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/liu
**源文件**：[osdi25-liu.pdf](../../papers/osdi-2025/osdi25-liu.pdf)

---

## 一、背景

随着内存密集型工作负载（图处理、机器学习等）需求的增长，集成 fast-tier（如 DRAM）和 slow-tier（如 CXL 内存）的分层内存架构正在成为云数据中心的标准配置。两层之间存在 2-3× 的性能差距，因此有效的数据分层（tiering）策略对系统性能至关重要。

现有分层系统的核心假设是：频繁访问的"热"数据比"冷"数据更关键，应优先放在 fast-tier。这一假设驱动了大量围绕 hotness tracking、内存分配和页面迁移的研究工作。然而，这个假设忽略了现代乱序 CPU 中 memory-level parallelism (MLP) 的延迟掩盖效应——并非所有内存访问对性能的贡献都相同。

---

## 二、要解决的问题

1. **Hotness ≠ 性能关键性**：高 MLP 的顺序访问模式虽然"热"（访问频率高），但其延迟被并行请求掩盖，放在 slow-tier 对性能影响很小；而低 MLP 的 pointer-chasing 访问虽然"冷"，却对性能高度敏感。现有基于 hotness 的策略可能做出完全相反的放置决策。

2. **次优的数据放置**：现有粗粒度分配策略优先将新分配的数据放在 fast-tier，但在 fast-tier 压力下，性能关键数据被挤到 slow-tier，后续需要昂贵的迁移来纠正。

3. **过度的迁移开销**：现有系统采用激进的迁移策略，频繁迁移非关键页面，迁移本身的开销（单次约 12µs，期间阻塞应用线程）可能侵蚀甚至抵消分层带来的收益。实验中多个 state-of-the-art 系统甚至不如不做任何迁移的 NoTier 基线。

---

## 三、洞察与设计

**关键洞察**：内存访问对性能的实际影响取决于访问延迟和 memory-level parallelism (MLP) 的综合效果——高 MLP 访问的延迟惩罚被并行请求大幅掩盖，而低 MLP 访问直接暴露延迟。因此，将延迟除以 MLP 得到的 Amortized Offcore Latency (AOL) 才是衡量内存访问性能影响的准确指标。

基于这一洞察，论文提出了 AOL 指标及两个分层机制：

### AOL 指标

AOL = Latency / MLP，通过 4 个硬件性能计数器（Intel PMU）轻量测量。结合 CPU stall 信息，构建性能预测模型：S = P × K，其中 P = s_LLC/c（基础预测器），K = f(AOL) = 1/(a + b/AOL)（AOL 修正因子）。该模型在 56 个 SPEC CPU 2017 和 GAPBS 工作负载上达到 0.951 的 Pearson 相关系数。

### Soar（Static Object Allocation based on Ranking）

Profile-guided 的静态对象分配策略：
- 通过 LD_PRELOAD 拦截内存分配，跟踪对象生命周期
- 用 PEBS 采样 LLC miss 的时空分布
- 用 AOL 预测器估算性能影响，按 Algorithm 1 将 CPU stall 按 MLP 加权分配到各对象
- 按 unit score（score/size）排序，将 top-N 对象放入 fast-tier
- 只需在 fast-tier 上运行一次 profiling，无需修改应用代码

### Alto（AOL-based Layered Tiering Orchestration）

轻量级动态页面迁移调节策略：
- 周期性（默认 1s）监测 AOL
- AOL 低（高 MLP）时限制或禁止页面提升——此时迁移收益小
- AOL 高（低 MLP）时允许全速迁移——此时迁移确实有益
- 使用两个阈值 AOL_low 和 AOL_high 控制迁移强度，中间区域用阶梯函数渐变
- 可无缝集成到 TPP、NBT、Nomad、Colloid 四种现有分层系统，内核改动仅约 30 行

---

## 四、实现细节

**AOL 测量**：基于 4 个 Intel PMU 计数器——OFFCORE_REQUESTS_OUTSTANDING.CYCLES_WITH_DEMAND_DATA_RD（A1）、OFFCORE_REQUESTS_OUTSTANDING.DEMAND_DATA_RD（A2）、OFFCORE_REQUESTS.DEMAND_DATA_RD（A3）、CYCLE_ACTIVITY.STALLS_L3_MISS（s_LLC）。Latency = A2/A3，MLP = A1/A2（近似），AOL = A1/A3。

**Soar profiling**：三条数据流——对象流（通过 LD_PRELOAD 拦截 malloc/free/mmap/munmap，按 backtrace 分组）、内存访问流（PEBS 采样 LLC miss，采样率 3000）、性能流（定期采样 AOL 预测器）。三流按时间戳和地址范围融合，生成每对象时间序列 profile。

**Soar 对象评分（Algorithm 1）**：
- MLP=1 时，按访问比例 R 线性分配 slowdown
- 高 MLP + 高访问频率对象：score = R × p / factor（除以 8，消除 MLP 掩盖效应）
- 低 MLP + 低访问频率对象：score = R × p × factor（放大真实性能贡献）
- 排序后用 numa_alloc() 绑定到对应 tier

**Alto 集成**：
- Alto+TPP：按 AOL 比例限制候选提升页面数
- Alto+NBT/Nomad/Colloid：限制 PAGE_NONE 标记的页面数，从而控制 hinting fault 触发的迁移量
- 用户态通过 Linux perf 采集计数器，内核态仅 ~30 LOC 修改

**模型校准**：a、b 两个常数仅依赖硬件（CPU + 内存），通过两个极端微基准（顺序 vs pointer-chasing）离线校准一次即可，无需对每个工作负载重复。

---

## 五、实验结果

**平台**：
| 平台 | CPU | 内存 | 延迟比 | 带宽 |
|------|-----|------|--------|------|
| SKX/NUMA (CloudLab) | 2×10-core Skylake | 96GB DDR4/socket | 90/190ns (2.1×) | 49/17 GB/s |
| SPR/CXL (本地) | 32-core Sapphire Rapids | 192GB DDR5 + 128GB CXL | 114/271ns (2.4×) | 218/26 GB/s |

**工作负载**：GAPBS 图分析、SPEC CPU 2017、GPT-2、Redis 等，8 线程，RSS 8-35GB。

### Soar 主要结果

| 工作负载 | Soar | Colloid | NBT | Nomad | TPP | NoTier |
|----------|------|---------|-----|-------|-----|--------|
| microbench | 34% | 60% | 58% | 58% | 58% | 46% |
| bc-urand | 16% | 58% | 68% | 123% | 875% | 67% |
| bc-twitter | 7% | 26% | 13% | 61% | 495% | 63% |
| bc-kron | 18% | 40% | 59% | 105% | 792% | 55% |
| sssp-kron | 14% | 25% | 18% | 29% | 760% | 39% |
| 602.gcc | 7% | 6% | 11% | 24% | 38% | 9% |
| 603.bwaves | 4% | 43% | 13% | 18% | 1246% | 9% |

（50% slow-tier ratio，数值为 slowdown %，越低越好）

- Soar 在 bc-urand 上即使 90% slow-tier 也保持 <20% slowdown
- 在 CXL 上趋势一致，Nomad 最高达 588% slowdown

### Alto 主要结果

- Alto+TPP 比 TPP 提升 2-471%
- Alto+NBT 比 NBT 提升 1-23%
- Alto+Nomad 比 Nomad 提升 -2-35%
- Alto+Colloid 比 Colloid 提升 0-18%
- 页面提升次数减少最高达 127.4×

### 带宽争用

- Soar 在带宽争用下仍优于次优方案 4-41%
- Alto 在中等争用下有效（减少 51% 页面迁移），极端争用下收益减小
- 调高 AOL 阈值可在高争用场景恢复收益

---

## 六、批判性分析

1. **Soar 依赖离线 profiling 的局限性被低估**：Soar 需要在 fast-tier 上完整运行一次工作负载，这对于输入数据分布变化大的应用（如不同查询模式的数据库、不同用户行为的 web 服务）可能产生与实际运行不匹配的 profile。论文虽提到可扩展到在线 profiling，但未实现也未评估。

2. **对象内均匀访问分布假设**：Soar 假设每个对象内部的访问分布是均匀的，但实际中大对象（如 17GB 的图数据结构 O8）内部可能有热点和冷区。论文承认了这一点但没有评估其影响。

3. **AOL 阈值需要手动调优**：虽然论文声称阈值对硬件通用、对工作负载无关，但在带宽争用场景下需要根据争用程度调整阈值（从 40/100 调到 90/270）。auto-tuning 被留作 future work，这削弱了"易部署"的说法。

4. **Alto+Nomad 的负面结果缺乏解释**：论文坦承 Alto+Nomad 在部分工作负载上有最高 2% 的性能下降，但明确表示"原因尚不清楚"，这对一篇系统论文来说不够充分。

5. **实验设置对基线不利**：TPP 的表现异常差（最高 1246% slowdown），这可能与实验配置有关（如 fast-tier 不饱和时 Colloid 的策略也失效）。论文虽解释了原因，但如此极端的数字可能反映了配置未对准基线的最佳使用场景。

6. **MLP 建模的简化**：将复杂的 MLP 行为简化为 AOL = Latency/MLP 的简单比值，并用 Michaelis-Menten 动力学曲线拟合 K = f(AOL)，虽然经验上有效（0.951 相关系数），但缺乏理论根基。论文中也存在一个明显的 outlier（Figure 2e 右下角），且模型改进被留作 future work。

---

## 七、AI Infra / MLSys 视角

1. **对 LLM 推理的启示**：LLM 推理中的 KV cache 管理面临类似的分层存储问题（GPU HBM vs CPU DRAM vs SSD）。AOL 的核心思想——区分 MLP 掩盖下的"虚假热度"和真实性能关键性——可以迁移到 KV cache 的分层管理中。例如，prefill 阶段的注意力计算有高度并行性（高 MLP），对 KV cache 延迟不敏感；而 decode 阶段是逐 token 串行的（低 MLP），对延迟高度敏感。

2. **分布式训练的梯度/参数放置**：在异构内存的训练系统中（如 ZeRO-Offload），AOL 类指标可以指导哪些参数/梯度值得从 CPU 迁移到 GPU——不是简单按访问频率，而是按实际对训练吞吐的影响。

3. **Profile-guided 对象分配的通用性**：Soar 的思路（一次 profiling → 对象级性能排名 → 静态分配）适合 AI 推理等重复执行相似模式的工作负载。可以考虑将其扩展到 GPU 显存管理中，对 tensor 按实际性能贡献排序，决定哪些放在 HBM、哪些放在 GDDR 或 host memory。

4. **可跟进的研究方向**：
   - 将 AOL 概念推广到 GPU 异构内存层次（HBM/GDDR/host），需要找到 GPU 上的等价硬件计数器
   - 在 CXL 内存池化场景中，将 AOL 与多租户资源隔离结合，实现 performance-aware 的内存池分配
   - 为在线推理服务设计 AOL-aware 的动态内存管理——不同请求的 MLP 特征可能随 batch size 和 sequence length 变化

---

## 八、总结

本文揭示了分层内存管理中"热度等于性能关键性"这一长期假设的根本缺陷，提出 AOL（Amortized Offcore Latency）指标来准确量化内存访问的真实性能影响。基于 AOL 设计的 Soar（静态对象分配）和 Alto（动态迁移调节）分别从分配和迁移两个维度改进分层策略，在 NUMA 和真实 CXL 平台上显著优于 TPP、Nomad、NBT、Colloid 四种 state-of-the-art 系统。主要局限在于 Soar 依赖离线 profiling、AOL 阈值在高带宽争用下需要手动调整、以及对象内均匀访问假设。总体而言，AOL 提供了一个简洁有效的新视角，有望推动分层内存管理从"热度驱动"转向"性能驱动"。
