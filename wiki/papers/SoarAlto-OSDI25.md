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

> **一句话总结**：hotness(访问频次)并不等于 performance-critical,作者提出 AOL = Latency/MLP 作为新指标,基于 AOL 的静态分配策略 Soar 和动态迁移调节器 Alto,在 NUMA 与真 CXL 平台上对比 TPP/Nomad/NBT/Colloid 加速最高 12.4×,仅 5/182 个案例反而变慢(≤3%)。

## 问题

DRAM + CXL 分层内存方案中,现有 tiering 基本默认「hot page 就该在 fast tier」。但这个假设在现代乱序 CPU 下不成立:memory-level parallelism (MLP) 会把高 MLP 的「hot」访问延迟隐藏掉,而低 MLP 的「cold」访问(如 pointer chasing)每次 miss 都会真实地 stall CPU。作者用 microbench 展示:把 hot `seq` 页放 DRAM、cold `pc` 页放 CXL(常规 hotness 策略),反而比**反过来放**慢 34%;连 Colloid/Nomad/TPP 等 SOTA 都比单纯 first-touch 的 NoTier 还差 12–14%——大量迁移开销却没命中真正关键的页。

## 核心方法

**Amortized Offcore Latency (AOL)**:用 `Latency / MLP` 结合 CPU stall 周期来度量内存访问对性能的真实贡献。核心公式:slowdown `S ≈ (Δs_LLC)/c`,再乘以随 AOL 变化的修正因子 `K`(高 MLP 工作负载 per-miss stall 只有 60 cycles,低 MLP 高达 240 cycles,差 4×)。作者在 56 个 SPEC CPU 2017 + GAPBS workload 上验证 AOL 模型,预测误差 <4%,并且在细粒度时序预测上也成立。

基于 AOL 的两个机制:

- **Soar(静态 profile-guided allocation)**:离线/初始化阶段按 AOL 对对象打分,累积性能贡献高的对象放 DRAM,低的放 CXL。近最优布置,运行时无需迁移。
- **Alto(动态迁移调节)**:不替换 TPP/Nomad/NBT/Colloid 的迁移策略,而是作为**过滤器插入**——只让 AOL 足够高的页真正被 promote。代码改动很小,可分别嫁接到 4 种 tiering 系统。

两个机制都在 NUMA 仿真与真 CXL 硬件上评测,覆盖图计算、云、HPC workload 与不同 fast:slow 比率、不同带宽竞争。

## 关键结果

- Soar vs. Nomad / NBT / Colloid / TPP:提升 **14–547% / 4–79% / -1–68% / 31–1242%**。
- Alto 嫁接后:-2–81% / 1–31% / -3–18% / 2–471%。
- 总体 182 个场景中只 5 个反而变慢,回退 ≤3%。
- 在高带宽竞争下增益减弱(AOL 被排队延迟膨胀),作者指出需要 contention-aware 的 AOL 阈值调优。
- AOL 预测器在 56 个 workload 上误差 <4%,且可扩展到细粒度时序预测。
- 开源:github.com/MoatLab/SoarAlto。

## 相关

- **相关概念**:CXL memory、memory-level parallelism (MLP)、LLC-Stalls、page migration、NUMA balancing
- **同类系统**:TPP、Nomad、Colloid、Linux NUMA Balancing Tiering (NBT)、VeriBetrKV 的前身 HeMem
- **同会议**:[[OSDI-2025]]
