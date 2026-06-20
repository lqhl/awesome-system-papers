---
type: paper
name: SoarAlto
full_title: "Tiered Memory Management Beyond Hotness"
authors: [Jinshu Liu, Hamid Hadian, Hanchen Xu, Huaicheng Li]
venue: OSDI
year: 2025
tags: [tiered-memory, cxl, memory-management, page-migration, performance-prediction]
source_pdf: "[[osdi25-liu.pdf]]"
source_md: "[[osdi25-liu]]"
---

# Tiered Memory Management Beyond Hotness (OSDI 2025)

> **一句话总结**：hotness 不等于 performance-critical——AOL = Latency/MLP 量化页级性能贡献；profile-guided 静态分配 Soar + 动态迁移调节器 Alto 在 NUMA/真 CXL 上相对 TPP/Nomad/NBT/Colloid 最高加速 12.4×，182 案例中仅 5 例变慢（≤3%）。

## 问题与动机

DRAM + CXL 分层内存已成云数据中心标配，但主流 tiering 默认「热页放 fast tier」。现代乱序 CPU 的 MLP 会掩盖高 MLP「热」访问的慢层延迟，而低 MLP pointer-chasing 等「冷」页每次 miss 都真实 stall CPU。作者 microbench 显示：按 hotness 把 seq 页放 DRAM、pc 页放 CXL 反而比反过来慢 34%；Colloid/Nomad/TPP 甚至不如无迁移的 NoTier（慢 12–14%）。

## 关键观察 / 隐含假设

- **观察 1**：LLC-Stalls 与 slow-tier slowdown 强相关（56 workload 误差 <4%），但 base predictor P=s_LLC/c 对高 MLP workload 高估 slowdown（Pearson 0.869 vs 实际）；每 LLC-miss stall 跨 workload 差 4×。
  - **依赖假设**：Intel PMU 四类 counter（Table 1）可在线近似 AOL；K=f(AOL) 双参数曲线用 seq vs pc microbench 标定后可跨 workload 复用。
  - **可能失效场景**：带宽争用抬高 latency→AOL 膨胀，增益减弱；非 Intel PMU 平台需重标定。
- **观察 2**：Soar 对象级打分用 access ratio × predicted slowdown × MLP 缩放因子，一次 fast-tier profile 即可近最优初分配，消除运行时迁移。
  - **依赖假设**：malloc/mmap 拦截 + PEBS LLC-miss 采样（rate≈3000）能代表对象性能贡献；对象内访问均匀。
  - **可能失效场景**：异构页内访问、短生命周期对象、非 glibc/memkind 分配路径。
- **假设 1**：Alto 作为 plug-in 调节器可无缝叠在 TPP/Nomad/NBT/Colloid 上，只抑制「非 performance-critical」迁移。
  - **证据强度**：中；4 个代表系统上 ablation 一致，但 Alto 不解决初分配错误。

## 核心方法

**AOL 预测器**：Latency=A₂/A₃，MLP=A₂/A₁，AOL=A₁/A₃；S ≈ (s_LLC/c) × 1/(a+b/AOL)。

**Soar**：LD_PRELOAD 跟踪对象生命周期；PEBS 关联访问；AOL 时间序列预测 workload slowdown；Algorithm 1 按 MLP/频率给对象打分排序，numa_alloc 绑定 top-k 对象到 fast tier。

**Alto**：在现有 tiering 迁移决策前用 AOL 阈值过滤非关键页 promotion，减少无效迁移开销。

## 设计取舍

- **取舍 1**：Soar 需一次完整 fast-tier profile run——换 datacenter profile-guided optimization 范式，不适合极短 job。
- **取舍 2**：对象级（非页级）打分启发式——实现简单但牺牲页内热点精度。
- **边界条件**：高带宽争用需 contention-aware AOL 阈值；CXL 真机 + NUMA 双平台验证，ARM/非 x86 未覆盖。

## 实验与结果

- Microbench：Hot-on-DRAM 仅 52.4% All-on-DRAM；Cold-on-DRAM 比 hotness 策略快 34%。
- 56 SPEC+GAPBS：AOL 预测 Pearson 0.951；tc-twitter 时间序列预测贴近实测。
- Soar vs Nomad/NBT/Colloid/TPP：+14–547% / +4–79% / -1–68% / +31–1242%；Alto：-2–81% / +1–31% / -3–18% / +2–471%。
- 5/182 案例 Soar/Alto 略慢于 baseline（≤3%）；开源 https://github.com/MoatLab/SoarAlto。

## Critical Analysis

### 论证链条

「hotness 失效 → AOL 度量 → Soar 静态 + Alto 动态」逻辑自 microbench 到 56 workload 再到真实 graph/cloud/HPC 闭合。把 MLP 从架构社区概念落到 tiering policy 是清晰贡献；但 object-level 启发式与 workload-level AOL 之间的语义 gap 靠 frequency 比例分摊，理论保证弱。

### 假设压力测试

- **已证明**：在测试 NUMA/CXL 平台上 hotness-based tiering 常伤害性能；AOL 优于 LLC-miss 计数 alone。
- **可能失效**：内存带宽饱和时 AOL 与真实 slowdown 偏离；云混部 workload 与 SPEC/GAPBS 差异大。
- **论文未覆盖**：与 OS 默认 first-touch + reclamation 的长期交互；profile 与 production 数据漂移。

### 实验可信度

Baseline 覆盖 TPP/Nomad/NBT/Colloid/NoTier；负例 5/182 诚实报告。CXL 真机加分。缺与 Linux MGLRU/AutoNUMA 等主线方案对比；Soar profile 开销未 production 量化。

### 系统性缺陷

依赖 Intel PMU 与 LD_PRELOAD；Alto 需改 tiering 系统源码；高争用需手工调阈值；论文承认 AOL 建模非完美（Figure 2e 有 outlier）。

## 局限与 Future Work

- **局限 1**：对象内异构访问未建模；Soar 单次 profile 对长运行 workload 可能过时。
- **局限 2**：带宽争用下 AOL inflation，需 contention-aware tuning。
- **Future work 1**：在线/增量 profile 与 AutoNUMA 协同的 production 测量。
- **Future work 2**：非 Intel 平台 AOL 曲线标定与 ARM MLP 行为验证。

## 相关

- **相关概念**：[[CXL]]、[[NUMA]]
- **同类系统**：TPP、Nomad、Colloid、NBT
- **同会议**：[[OSDI-2025]]