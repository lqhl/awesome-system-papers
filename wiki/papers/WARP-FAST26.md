---
type: paper
name: WARP
full_title: "Characterizing and Emulating FDP SSDs with WARP"
authors: [Inho Song, Shoaib Asif Qazi, Javier González, Matias Bjørling, Sam H. Noh, Huaicheng Li]
venue: FAST
year: 2026
tags: [ssd, fdp, write-amplification, emulator, nvme]
source_pdf: "[[fast2026-song.pdf]]"
source_md: "[[fast2026-song]]"
---

# Characterizing and Emulating FDP SSDs with WARP (FAST 2026)

> **一句话总结**：首个跨 vendor 商用 FDP SSD 系统评测揭示：RUH 与 object lifetime 对齐时 WAF 可逼近 1.0，但 misclassification、RUH 干扰与 adversarial invalidation 下收益崩塌；基于 [[FEMU]] 的开源 emulator WARP 复现硬件 WAF 趋势并暴露 per-RUH 动态，发现 Noisy RUH 与 Save Sequential 两类未报道现象，并证明 PI 仅在 OP≥7–9% 时才优于 II，CacheLib kvcache 上 FDP 把 40% SOC 的 WAF 从 1.85 降到 ~1.0 且不损 hit ratio。

## 问题与动机

[[NVMe]] Flexible Data Placement（FDP，TP4146）是 Google/Meta 等 hyperscaler 推动的标准接口：host 通过 Reclaim Unit Handle（RUH）给 write 打 placement hint，让生命周期相近的数据进入同一 Reclaim Unit（RU），理想情况下 [[Garbage-Collection|GC]] 时 WAF 逼近 1.0。与 OpenChannel、[[ZNS]] 不同，FDP 保留 block 接口兼容性，GC 仍完全由 device firmware 管理——因此 FDP 是 **best-effort** 而非保证。

商用 FDP SSD 已上市，但同一 NVMe 接口下各 vendor 在 RU size、over-provisioning（OP）比例、RUH 数量、Initially Isolated（II）vs Persistently Isolated（PI）等 firmware 选择上差异巨大，且对 host 不透明。结果是：同一 workload 在一台设备上 WAF≈1.0，在另一台上可能崩溃到 3.5×+，社区仍缺乏 **何时起效、何时失败、为何跨设备差异巨大** 的系统理解。既有工作（如 CacheLib + FDP）多在单栈报喜，无法解释黑盒 firmware 行为，也无法探索替代 GC 策略。

论文提出 WARP，把 **跨设备 characterization** 与 **可配置开源 emulator** 结合，把 FDP 研究从 anecdotal demonstration 推进到可复现、可机制解释的基础平台。

## 关键观察 / 隐含假设

- **观察 1**：RUH 物理隔离能屏蔽 heterogeneous stream 间的 GC 干扰——两路 sequential/random 混合写时 FDP 全程维持 WAF≈1.0，NoFDP 在 50:50 混合下飙到 2.4×；纯 sequential stream 本身已接近理想 WAF，FDP 增益主要体现在 mixed workload。
  - **依赖假设**：host 能为不同访问模式（sequential vs random、不同 block size）分配独立 RUH，且 firmware 尊重 RUH→RU 映射。
  - **可能失效场景**：static RUH 分配无法跟踪数据温度变化；多 stream 被错误映射到同一 RUH（MixedFDP）时，强 Zipf 仍可受益，80/20 分布则迅速退化到 NoFDP。
- **观察 2**：FDP 收益高度依赖 workload skew 与 RUH 分类准确度——三 stream（sequential + random + overwrite）下，Zipf(2.2) 时 FDP WAF≈1.0–1.3，80/20 分布下 SSDB 飙到 3.12×；misclassified RUH（overwrite 与 sequential 共 RUH）在 80/20 下 WAF 介于 FDP 与 NoFDP 之间。
  - **依赖假设**：生产 workload 呈现足够强的 hot-cold 偏斜，且应用层（如 CacheLib SOC/LOC 分离）能提供与内部写模式匹配的 RUH 映射。
  - **可能失效场景**：uniform random invalidation 等 adversarial 模式使 FDP/NoFDP 趋同（SSDA ~2.6×，SSDB 4.5×）；F2FS 将 99% 用户数据标为 WARM → 单 RUH，FDP 对 Fileserver/OLTP 完全无效（WAF ~2.3–2.5，与 NoFDP 相同）。
- **观察 3**：CacheLib 类 cache workload 是 FDP 的 sweet spot——kvcache trace 上 NoFDP 在 20%/40% SOC 时 WAF 升至 1.64/1.85，FDP 维持 1.0–1.08；hit ratio 从 61%（4% SOC）升至 82% 的同时 WAF 不升，打破传统 hit ratio vs endurance trade-off；多租户场景 NoFDP WAF 从 1.28 升至 ~3.0，FDP 最高仅 2.6。
  - **依赖假设**：SOC（BigHash，4KB bucket 全量重写）与 LOC（BlockCache，16MB sequential append）写模式差异足够大，映射到不同 RUH 即可隔离；cache 占用 device 容量主体，neighbor noise 可被 RUH 隔离。
  - **可能失效场景**：SOC 比例极高且 RU 配置不当时出现 Noisy RUH（见下）；cdn/twitter 等已 device-friendly 的 trace 上 FDP 无增益但也无回退。
- **观察 4（机制层，via WARP）**：**Noisy RUH**——一个 RUH 的 invalidation 通过共享 GC 压力间接抬高其他 RUH 的 WAF（80/20 下 RUH 1 贡献 26%、RUH 2 贡献 14% 总 amplification，尽管各自流量仅 5–6%）；**Save Sequential**——容量主导的 sequential stream（RUH 0 吸收 88% 写）反而贡献最多 WAF，因有限 OP 与 GC heuristic 导致过早 reclaim。
  - **依赖假设**：商用 FDP 实现存在跨 RUH 资源共享（OP pool、GC 调度），II 模式下 GC copy 进入共享 GC-RUH 进一步打破隔离语义。
  - **可能失效场景**：PI + 充足 OP 可缓解，但 PI 在 OP<7% 时 WAF 反而高于 II（256MB RU、80/20 workload：II 2.18 vs PI 2.37 @5% OP）。
- **假设 1**：WAF 是衡量 FDP 价值的一阶 metric，且 steady-state WAF plateau 主要由 vendor geometry + GC policy 决定（单 stream random write：SSDA ~2.0×，SSDB ~3.5× plateau）。
  - **证据强度**：**强**——多块商用设备 + 多类 workload 一致呈现；但论文未系统评估 tail latency SLO、读性能或 endurance 寿命的端到端影响。

## 核心方法

### Cross-device characterization

在两块 PCIe Gen5、NVMe 2.1、8-RUH 商用 FDP SSD（SSDA 7.68TB U.3、SSDB 3.84TB E1.S）上，Linux 6.8 + Samsung FDP driver patch（NVMe I/O passthrough 传 RUH hint）跑三类 workload：
1. **合成 FIO**：1–3 stream，控制 sequential/random/overwrite 比例与 skew（Zipf 1.2/2.2、80/20）
2. **Production trace**：CacheLib（kvcache、cdn、twitter），SOC/LOC 映射不同 RUH
3. **文件系统**：[[F2FS]] + Filebench（Fileserver 200 线程、OLTP 10 线程），依赖 F2FS data classification hint

核心 metric 为 WAF = media bytes written / host bytes written；对比 FDP、NoFDP（无 RUH hint）、MixedFDP（故意 misclassify）三种模式。

### WARP emulator

WARP 扩展 [[FEMU]]，首个同时支持 II 与 PI 语义的开源 FDP emulator，upstream 至 MoatLab/FEMU。设计契约：
- **确定性 RUH 映射**：每个 host tag 固定解析到同一 RU
- **可配置 geometry**：RU size（128/256/512MB）、OP ratio（1–28%）、RUH 数量
- **RUH-aware GC**：两层决策——选 victim RUH（greedy / pressure-based）+ 选 victim RU（greedy / cost-benefit）；支持 lazy GC（5–10% valid 阈值）、background/foreground GC 分界、block remapping
- **三层可观测性**：device 级 WAF、RUH 级 host/GC/remap 统计、per-GC-event 结构化日志

校准默认：RU=256MB、OP=10%、lazy threshold=5%、block remapping on、8 RUH。通过调 geometry 使 WARP 配置族 WAF 落在 2.0–3.5× 区间，覆盖两 vendor 的 steady-state spread。

### Design space exploration

用 WARP 系统探索 II vs PI 在 OP/RU size 下的 crossover（80/20 stress workload）：256MB RU 时 crossover 在 OP 7–9%；128MB RU 需更高 OP PI 才追上 II。进一步在 CacheLib kvcache 40% SOC 上试验 **small-RU for SOC RUH**（单 channel mapped RU），FDP+优化把 WAF 从 1.37 再降到 1.16。

## 设计取舍

- **取舍 1**：选择 [[FEMU]]/QEMU 用户态仿真而非 cycle-accurate hardware model——换取可配置性、per-RUH 全透明日志与快速迭代，代价是 NAND timing/并行度与真实 ASIC 仍有 gap（4KB QD=1 read：335K IOPS vs SSDA 460K；p99.999 tail 457µs vs 967µs）。
- **取舍 2**：characterization 依赖 NVMe passthrough 而非 block layer 透明集成——反映当前生态现实（Linux FDP 支持仍早期），但结论对「未来透明集成后的默认行为」外推需谨慎。
- **取舍 3**：emulator 把 vendor 不透明 policy 显式化（II/PI、GC heuristic 等）——研究价值高，但 calibrated 配置是 **fit-to-hardware** 而非 ground-truth firmware 复刻，绝对 WAF 误差可达 0.2–0.3。
- **边界条件**：FDP 在 **应用已做 lifetime-aware 分类**（CacheLib SOC/LOC）且 **workload 非 adversarial** 时最优雅；F2FS 式粗粒度 hint、uniform invalidation、OP 紧张 + PI 模式下会变脆；SSDB 因过度写入在评测中失效，部分结果仅来自 SSDA。

## 实验与结果

- **Baseline plateau**：单 stream 128KB random write，SSDA WAF 稳 ~2.0×，SSDB ~3.5×；WARP 调参后配置族覆盖该区间
- **Mixed stream**：两 stream sequential+random，FDP 全 mix 比例维持 WAF≈1.0；NoFDP 50:50 达 2.4×
- **三 stream + skew**：SSDA FDP Zipf2.2/1.2 WAF 1.03–1.04，80/20 升至 1.69；SSDB FDP 在 80/20 达 3.12×
- **CacheLib kvcache**：NoFDP WAF 1.10→1.64→1.85（SOC 4%/20%/40%）；FDP 维持 1.0–1.08；hit ratio 61%→82% 无 WAF 惩罚
- **Multi-tenant**：kvcache + 4K random neighbor，NoFDP WAF ~3.0，FDP ≤2.6（约 50% 降幅）
- **F2FS**：Fileserver/OLTP 上 FDP 与 NoFDP 曲线重合（~2.3–2.5 WAF），eBPF 显示 99% 用户数据为 WARM hint
- **WARP validation**：CacheLib 与三 stream workload 上 qualitative ordering（FDP < Mixed < NoFDP）与绝对值均与硬件对齐（Table 2）；WARP 在 40% SOC 复现 2.00→1.37 的 WAF 改善方向
- **II vs PI（WARP）**：256MB RU、80/20 @5× rHMW——OP 5% 时 II 2.18 vs PI 2.37；OP 10% 时 II 1.34 vs PI 1.18
- **WARP optimization**：kvcache 40% SOC，NoFDP 2.0 → FDP 1.37 → FDP+small-RU 1.16
- **Latency**：调优后（disable NVMe doorbell MMIO）WARP p50/p99 70–77µs 接近 SSDA，IOPS 335K vs 460K

## Critical Analysis

### 论证链条

论文链条为 **跨设备现象刻画 → 黑盒行为假设 → WARP 机制验证 → design space 推导 → 优化示范**，逻辑闭合度在 storage characterization 类工作中属上乘。最强环节是用 WARP per-RUH telemetry 把 Noisy RUH / Save Sequential 从「观察到的 WAF 异常」推进到「可测机制」；II/PI crossover 实验直接回应 vendor 默认选择问题。

潜在跳步：(1) **two-device study** 外推为「FDP 普遍行为」——vendor 样本极小，SSDB 还中途失效；(2) WARP validation 以 **trend matching** 为主，部分配置需手动 fit geometry，未证明唯一正确 firmware 模型；(3) CacheLib 成功被部分推广为「FDP 适合 cloud cache」，但 F2FS 负面结果说明 **host 分类质量** 才是 bottleneck，论文虽指出却未量化「多少 hint 准确度才够」。

### 假设压力测试

- **Workload 漂移**：从 cache（skewed overwrite）转向 OLTP/日志追加或 uniform random update，FDP 收益迅速消失——论文已在 F2FS 与 adversarial microbench 验证，production 中间态（弱 skew + 动态 lifetime）覆盖不足。
- **硬件代际**：仅 Gen5、8-RUH、两块 enterprise SSD；RUH 数增多、QLC、或不同 OP 默认会改变 II/PI crossover 与 Noisy RUH 严重度——WARP 可探索但论文未系统扫参。
- **多租户与 QoS**：FDP 隔离 WAF 但不保证 IOPS/latency 隔离；Noisy RUH 暗示 **GC 带宽争用** 可跨 RUH 泄漏，论文未测 tail latency 在多租户下是否恶化。
- **分类成本**：CacheLib 的 SOC/LOC 分离是手工工程；自动 lifetime 推断错误率与 WAF 的 sensitivity curve 论文未给出。

### 实验可信度

- **Benchmark 代表性**：CacheLib Meta production trace 代表性强；FIO microbench 控制变量好；F2FS Filebench 揭示真实集成痛点（hint 粒度），但 OLTP/Fileserver 与 hyperscaler cache 场景距离较远。
- **Baseline 公平性**：NoFDP/MixedFDP/FDP 对照清晰；缺少与 [[ZNS]]、multi-stream SSD 等 **替代降 WAF 接口** 的 head-to-head——FDP 的卖点是兼容性，但兼容性优势未量化运维/迁移成本。
- **Ablation**：WARP 侧 II/PI、OP、RU size ablation 充分；硬件侧无法 ablate firmware knob，属问题本质而非论文缺陷。
- **Metric 覆盖**：聚焦 WAF，latency 仅单点 QD=1 read；**endurance 寿命模型、能耗、读放大、故障恢复** 论文未讨论。

### 系统性缺陷

- **可部署性**：依赖 NVMe passthrough + 应用级 RUH 赋值，距 Linux block layer 透明 FDP 仍有距离；论文未讨论升级/回滚与 non-FDP 设备混部。
- **隔离语义**：II 模式下 GC copy 进入共享 GC-RUH，**spec 层面的 isolation 与实测 isolation 不一致**——对安全/多租户强隔离需求可能不够。
- **可观测性**：商用设备几乎无 per-RUH 统计，生产 debug 困难；WARP 补研究空白但不解决部署可观测性。
- **动态适应**：论文提出 adaptive RU sizing 方向，未实现闭环 controller；静态 RUH 在 lifetime 漂移时脆弱性已证明，工程缓解方案未验证。

## 局限与 Future Work

- **局限 1**：仅两块商用 FDP SSD、SSDB 部分实验不完整；vendor firmware 不可复现，WARP 是近似模型而非 bit-accurate clone。
- **局限 2**：F2FS 集成失败根因已定位（hint 粗粒度），但未提出并验证修复后的 end-to-end 收益。
- **局限 3**：优化实验（small-RU for SOC）仅在 WARP 上示范，未在真实 hardware 上确认。
- **Future work 1**：建立 **hint accuracy vs WAF** 的量化曲线（含 misclassification 率、动态重映射策略），指导 OS/FS 应投入多少分类复杂度。
- **Future work 2**：基于 WARP per-RUH telemetry 设计 **FDP-aware GC scheduler / adaptive II↔PI / dynamic RU sizing** 闭环，并在 production trace 上测 WAF–latency–throughput Pareto frontier。
- **Future work 3**：扩展 characterization 至更多 vendor、更多 RUH 数、与 [[ZNS]]/multi-stream 的 TCO 对比，并评估 CXL/解聚存储场景下 FDP 是否仍 relevant。

## 相关

- **相关概念**：[[NVMe]]、[[Garbage-Collection]]、[[Write-Amplification]]、[[FEMU]]、[[F2FS]]、[[ZNS]]、Reclaim-Unit-Handle、Flexible-Data-Placement
- **同类系统**：[[FEMU]]、CacheLib、[[DOGI-FAST26|DOGI]]（[[ZNS]] 数据放置）、OpenChannel SSD、Multi-stream SSD
- **同会议**：[[FAST-2026]]
- **对比**：FDP vs [[ZNS]]（兼容性 vs 强制顺序语义）、FDP vs multi-stream（物理隔离保证 vs 仅 hint）