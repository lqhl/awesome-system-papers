# Characterizing and Emulating FDP SSDs with WARP

**作者**：Inho Song, Shoaib Asif Qazi (Virginia Tech); Javier González (Samsung Electronics); Matias Bjørling (Western Digital); Sam H. Noh, Huaicheng Li (Virginia Tech)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/song
**源文件**：[[fast2026-song.pdf]]

---

## 一、背景

Flash 存储已成为当今数据密集型应用（缓存、分析等）的基础设施，但可持续扩展面临严峻挑战。设备层面的核心问题是写放大（Write Amplification Factor, WAF）——垃圾回收（GC）触发的额外闪存写入。高 WAF 缩短 SSD 寿命、增加替换成本、加大存储集群的碳排放。在超大规模数据中心，WAF 哪怕降低个位数百分点，就能带来数百万美元的成本节省和显著的设备寿命延长。

为此，Google 和 Meta 等超大规模厂商推动了 Flexible Data Placement (FDP) 接口，已纳入 NVMe 标准。FDP 允许主机通过 Reclaim Unit Handle (RUH) 提示引导写入分组，使生命周期相似的数据被一起回收，从而使 WAF 趋近 1.0。与之前的 Open Channel SSD 和 ZNS 不同，FDP 保持了块接口的向后兼容性，无需侵入式应用修改。然而，FDP 是一个"尽力而为"的接口，GC 完全由设备管理，回收策略对主机不透明且因厂商而异。

---

## 二、要解决的问题

1. **FDP 效果不可预测**：同一工作负载在不同厂商的 FDP SSD 上可能表现截然不同——一个设备接近理想 WAF，另一个则完全失效，但两者都宣称"支持 FDP"。
2. **规范与实践之间存在巨大鸿沟**：商用 FDP SSD 的内部参数（RU 大小、OP 比例、RUH 数量、II/PI 模式）由厂商固化，对主机不透明，无法解释 WAF 差异的根因。
3. **缺乏系统性研究**：现有研究仅关注单一应用栈（如 CacheLib），未跨设备、跨工作负载进行表征，也无法揭示 FDP 何时有效、何时失效及其原因。
4. **无开放研究平台**：商用设备不暴露内部动态，研究者无法探索替代固件策略或进行可复现的全栈 FDP 研究。

---

## 三、洞察与设计

**关键洞察**：FDP 的 WAF 收益不是接口本身的固有属性，而是工作负载生命周期与 RUH 隔离对齐程度、厂商固件策略（RU 大小、OP 比例、GC 启发式）三者交互作用的涌现结果。当对齐良好时 WAF 接近 1.0，当出现误分类、RUH 间干扰或对抗性失效模式时，FDP 的收益完全消失。

基于这一洞察，作者从两个方向展开工作：

**表征（Characterization）**：对两款商用 FDP SSD（SSD_A 7.68TB 和 SSD_B 3.84TB）进行首次跨设备、跨工作负载的系统性研究，覆盖合成微基准测试（FIO）、生产级 trace（CacheLib kvcache/cdn/twitter）和文件系统工作负载（F2FS FileServer/OLTP）。发现了两个此前未报告的现象：
- **Noisy RUH**：一个 RUH 中的失效流会通过增加 GC 压力间接放大其他 RUH 的 WAF
- **Save Sequential**：容量占主导的长顺序流被过早回收，反而成为 WAF 的主要贡献者

**仿真器（WARP）**：Write Amplification Research Platform，基于 FEMU 构建的首个开源 FDP SSD 仿真器。核心设计：
- 支持 II（Initially Isolated）和 PI（Persistently Isolated）两种隔离语义
- 将 RU 大小、OP 比例、RUH 数量、GC 策略等厂商固化参数暴露为可调旋钮
- 提供设备级、RUH 级、单次 GC 事件级三层遥测数据

---

## 四、实现细节

WARP 在 FEMU 基础上进行扩展，修改涉及接口层和内部策略层：

**接口层**：解析 NVMe 命令中的 FDP placement hint，将带标签的写入映射到 Reclaim Unit (RU)。每个 RUH 维护一个或多个写指针指向活跃 RU。

**放置模型**：
- II 模式：主机写入进入对应 RUH，但 GC 拷贝重定向到共享 GC-RUH，丢弃原始标签
- PI 模式：维护每个 RUH 的 GC 写指针，GC 拷贝保持在源 RUH 内，严格隔离

**GC 架构**，两级决策：
1. 选择从哪个 RUH 回收：支持 greedy（目标压力最大的 RUH）和 pressure-based 策略
2. 选择 RUH 内哪个 RU 回收：支持 greedy（最少有效页）和 cost-benefit（u/(1-u) × age）

**GC 优化**：
- Lazy GC：当 RU 中有效页占比低于阈值（5-10%）才触发回收
- 前台/后台 GC：后台在 ~90% RU 分配时触发，前台在 ~99% 时触发
- Block remapping：全有效 block 直接重映射到目标 RU，无需数据迁移

**可配置几何参数**：RU 大小（128/256/512MB）、OP 比例（1-28%）、RUH 数量均可运行时配置。

**默认配置**：8 channels × 8 dies/channel，4KB 页大小，沿用 FEMU 的 NAND 时序。校准默认值为 RU=256MB, OP=10%, lazy GC=5%, block remapping 启用, 8 RUHs。

代码已上游合并至 FEMU：https://github.com/MoatLab/FEMU

---

## 五、实验结果

### 表征结果（商用 SSD）

| 工作负载 | 指标 | SSD_A (7.68TB) | SSD_B (3.84TB) |
|---------|------|----------------|----------------|
| 单流 128KB 随机写 | 稳态 WAF | ~2.0 | ~3.5 |
| 双流 Seq+Rand 50:50 | NoFDP WAF | 2.4 | — |
| 双流 Seq+Rand 50:50 | FDP WAF | ~1.0 | — |
| 三流 Zipf 2.2 | FDP WAF | 1.03 | 1.29 |
| 三流 80/20 | FDP WAF | 1.69 | 3.12 |
| CacheLib kvcache SOC 20% | NoFDP WAF | 1.64 | — |
| CacheLib kvcache SOC 20% | FDP WAF | 1.07 | — |
| F2FS Fileserver | FDP vs NoFDP | 无改善（~2.3-2.5） | 无改善 |

### WARP 验证

- 单流随机写：通过调节 RU 大小/OP 比例/lazy-GC 阈值，WARP 的 WAF 范围落在 2.0-3.5 之间，与两款商用 SSD 一致
- CacheLib trace：WARP 复现了 FDP 在不同 SOC 比例下的 WAF 方向性改善（NoFDP 2.00 → FDP 1.37 at 40% SOC）
- 三流工作负载：WARP 保持了 FDP < MixedFDP < NoFDP 的层级关系

### II vs. PI 设计空间探索

| 条件 | 结果 |
|------|------|
| OP 有限（3-5%） | II 优于 PI（例如 RU=256MB, OP=3%: II 2.92 vs PI 3.81） |
| OP 充足（>7-9%） | PI 优于 II（例如 RU=256MB, OP=14%: PI 1.06 vs II 1.09） |
| 更小的 RU（128MB） | crossover 点上移，需要更多 OP 才能让 PI 超越 II |

### WARP 引导优化

- CacheLib SOC 40%：为 SOC RUH 分配小 RU → WAF 从 1.37 进一步降至 1.16
- 延迟：WARP 中位延迟 70µs，与真实 SSD_A 一致；p99.999 为 457µs vs 真实 967µs

---

## 六、批判性分析

1. **验证规模差距**：商用 SSD 容量为 3.84-7.68TB，而 WARP 评估仅 240-458GB。虽然作者声称通过归一化数据量来比较，但 GC 行为在不同绝对容量下可能有非线性差异。论文未讨论这一缩放的有效性边界。

2. **II/PI 比较不完全公平**：商用 SSD 都是 II 模式，PI 仅在 WARP 上评估。PI 的表现完全依赖于 WARP 的实现正确性，无法与真实硬件交叉验证。论文将 PI 的理论优势作为重要结论，但这一结论尚未经过硬件验证。

3. **F2FS 实验过于简单**：F2FS 实验仅用了 Fileserver 和 OLTP 两个 filebench 工作负载，且发现 99% 数据被标记为同一 hint。论文将此归咎于 F2FS 的分类不够精细，但未尝试修改 F2FS 策略来验证改善后的效果，使得文件系统层面的结论缺乏正面证据。

4. **SSD_B 在测试中故障**：论文提到 SSD_B 在过度写入后故障，部分微基准测试结果缺失。这限制了跨设备比较的完整性，但论文未充分讨论这一影响。

5. **优化案例有限**：§6 展示的 Small RU 优化仅针对 CacheLib 一个场景，且收益依赖于 SOC 比例较高（40%）；在 4% SOC 下收益微乎其微。论文声称 WARP 能指导优化，但实际展示的优化深度有限。

---

## 七、AI Infra / MLSys 视角

1. **KV Cache 场景的直接借鉴**：LLM 推理系统（如 vLLM）中的 KV cache 管理与 CacheLib 的 SOC/LOC 模式高度相似——小块频繁更新的 attention cache 与大块顺序写入的 model checkpoint。FDP 的 RUH 分离策略可以直接应用于 LLM 推理集群的 SSD cache 层，减少 WAF 并延长 SSD 寿命。

2. **Checkpoint 与 Log 的流隔离**：分布式训练中，checkpoint 写入（大块顺序）与训练日志/梯度通信的临时存储（小块随机）混合时会互相干扰。FDP 可以将这些流分配到不同 RUH，论文的 Noisy RUH 发现提醒我们必须确保分类准确，否则反而可能恶化。

3. **可操作的研究方向**：
   - 动态 RU 大小调整（论文 §6.1 提出但未深入）：根据 AI 工作负载的阶段性特征（训练 vs 推理、prefill vs decode）自适应调整 RU 分配
   - FDP-aware SSD 调度器：将 RUH 信息纳入 I/O 调度决策，特别是在多租户 GPU 集群的共享存储层

4. **WARP 作为 AI 存储研究工具**：AI Infra 研究者可以用 WARP 评估不同 checkpoint 策略、KV cache 淘汰策略对 SSD 寿命的影响，而无需购买昂贵的 FDP SSD。

---

## 八、总结

WARP 是首个开源 FDP SSD 仿真器和系统性研究平台。论文通过跨设备表征揭示了 FDP 的"有条件有效性"：当工作负载生命周期与 RUH 隔离对齐时 WAF 接近理想值，但在误分类、RUH 干扰或对抗性模式下收益完全消失，且不同厂商设备表现差异巨大。WARP 通过暴露 per-RUH 动态和可调设计旋钮，使研究者能够解释这些差异并探索超越当前硬件的固件策略。主要局限在于仿真器验证规模较小（240GB vs 数 TB 商用设备），PI 模式缺乏硬件交叉验证，以及优化案例展示深度有限。
