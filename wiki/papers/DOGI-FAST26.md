---
type: paper
name: DOGI
full_title: "DOGI: Data Placement with Oracle-Guided Insights for Log-Structured Systems"
authors: [Jeeyun Kim, Seonggyun Oh, Jungwoo Kim, Jisung Park, Jaeho Kim, Sungjin Lee, Sam H. Noh]
venue: FAST
year: 2026
tags: [log-structured-storage, garbage-collection, data-placement, machine-learning, zns, write-amplification]
source_pdf: "[[fast2026-kim-jeeyun.pdf]]"
source_md: "[[fast2026-kim-jeeyun]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# DOGI: Data Placement with Oracle-Guided Insights for Log-Structured Systems (FAST 2026)

> **一句话总结**：先用离线 oracle baseline NoDaP 量化 SOTA 数据放置与 near-optimal [[Garbage-Collection|GC]] 的三处缺口（user-block 预测、GC-block 重定位、group 粒度），再以「Hot Filter 启发式 + 轻量 MLP + PLog 驱动动态分组」组合的 DOGI 在 [[ZNS]] 原型上平均把 WAF 降 15.5%、写吞吐升 9.2%（vs MiDAS），峰值 WAF 降 23.2%、吞吐升 13.3%。

## 问题与动机

[[Log-Structured-Storage|Log-structured]] 系统（[[FTL]]、[[LSM-Tree|LSM]] KV store、分布式 FS）靠把随机小写转成顺序 append 获得高写吞吐，但更新产生大量 invalid block，[[Garbage-Collection|GC]] 搬迁存活数据带来 [[Write-Amplification|write amplification factor (WAF)]]——系统实际写入字节与用户请求字节之比。经典策略是把 invalidation time（从写入到被覆盖之间的 logical block 数）相近的 block 共置到同一 segment，使 victim segment 在 GC 时含更少 valid block。

SepBIT、MiDAS、PHFTL、ML-DT 等 SOTA 已显著降低 WAF，但作者 claim 实践与理论最优（optimal GC, OGC，WAF=1.0）之间仍有宽 gap。OGC 需要预知未来 invalidation time 且 segment 数量「无限」，现实中不可能；更现实的问题是：**现有启发式/ML 放置策略在三个维度上系统性偏离 near-optimal**：

1. **User-written block 放置**：latest-invalidation-time 启发式快（<0.5 µs）但准确率仅 76–82%；ML 模型（GRU/TCN）准确率约 87% 但推理 6.5–173 µs，把峰值写吞吐拖到 571 MB/s（PHFTL）甚至 22.6 MB/s（ML-DT）。
2. **GC-written block 重定位**：age-based 级联（SepBIT/MiDAS/PHFTL）或单一冷组隔离（ML-DT）都未捕捉 GC 阶段 block 实际 invalidation time 的宽分布。
3. **Group 配置**：固定 2–20 个 group，忽略「分组越细 vs 误判惩罚越大」的耦合——NoDaP 的 optimal 配置在 perfect knowledge 下是 7 组，但 ML-DT 照搬该配置反而 WAF 升 52%。

论文目标不是再提一个 heuristic tweak，而是先用 oracle baseline 量化 gap，再设计可在线部署、低开销的 DOGI。

## 关键观察 / 隐含假设

- **观察 1**：User-written block 的 invalidation time 预测准确率直接决定 WAF；在 NoDaP 框架下仅替换 SOTA 的 user-block 策略，WAF 从 near-1 飙到 1.72–1.88（YCSB-A trace，128 GiB、10% OP）。
  - **依赖假设**：Workload 的 overwrite 模式在 logical time 轴上存在可学习的局部规律（LBA、访问频率、latest invalidation time 等与生命期相关）；segment 粒度 GC（256 MiB segment、4 KiB block）使「同 segment 内 block 热冷混合」的搬迁成本主导 WAF。
  - **可能失效场景**：极度动态、相位频繁切换的 trace（Alibaba/Exchange D-type）使在线训练样本迅速 stale，准确率可跌至 56–64%，需 fallback 到粗粒度 2+2 分组。

- **观察 2**：GC-written block 的 invalidation time 分布远比 age 假设更宽；把 NoDaP 的 oracle 重定位策略嫁接到 MiDAS/ML-DT 上，WAF 平均降 **46%**——说明 age-based / live-block isolation 是独立的大瓶颈，而非 user-block 预测的附带问题。
  - **依赖假设**：GC 搬迁时 block 的「剩余 invalidation time」与其写入时的 predicted category 存在统计相关性，可用历史 PLog 估计；segment footer 能持久化 category 元数据。
  - **可能失效场景**：Exchange 等高度动态 workload 上 GC-block 重定位准确率提升有限；多次搬迁仍存活的长寿 block 最终只能 fallback 到 age-based 级联下一组。

- **观察 3**：Optimal group 数量是 prediction accuracy 的函数，而非 workload 的静态属性。ML-DT 在 perfect knowledge 下 6 组最优（WAF 1.96），在自身 ML 精度下 19 组默认配置更合理；强行用 NoDaP 的 7 组配置使 WAF 从 1.69 升到 2.57。组数从 2→3 常降 WAF，但超过拐点后误判惩罚主导（FIO 上 N=10 时 WAF 达最小值的 2.1×）。
  - **依赖假设**：PLog 记录的 `<predicted category, actual invalidation time>` 对足够代表近期 workload；512 种 group merge 配置的 brute-force 搜索（10 秒）可周期性重跑；Markov-chain WAF 模型参数可由 PLog 导出。
  - **可能失效场景**：Workload 突变时 PLog 滞后，MC 模型低估 misprediction ratio；搜索空间固定为 10 个 intermediate group 的 merge 方案，对极端 skew 可能不够。

- **假设 1**：最热 block 可用 latest-invalidation-time 启发式近乎完美分离（HF），仅 ~25% 非热 block 需走 ML，从而兼顾精度与吞吐。
  - **证据强度**：**强**——FIO/Varmail 热块分离准确率 98.27%/99.0%；原型上仅 24.7% user block 进 MLP，总推理均摊 0.39 µs/block。但中间温冷 block 才是最难预测段，论文未单独报告该子集精度。

- **假设 2**：[[ZNS]] 顺序写 zone 设备 + 现有 LSS write buffer 足以通过 batch inference（128 block）和 double buffering 完全隐藏 ML 延迟。
  - **证据强度**：**中**——原型峰值顺序写 1.1 GiB/s，DOGI 推理与 MiDAS 同级；但未测 CPU 核心争用、多 tenant 混合写、或 write buffer 未满时的尾延迟。

## 核心方法

### NoDaP：near-optimal oracle baseline

NoDaP（Near-optimal Data Placement）假设已知每个 block 的精确 invalidation time，在有限容量与 10% OP 下离线 exhaustive 搜索 group 数 N、每组 segment 数、block invalidation time range (BIR)。YCSB-A 上收敛到 7 组（G₁ hottest <200K blocks … G₇ coldest >51M）。放置策略：user/GC block 按 BIR 入组；victim 优先选 residence time 超过 BIR 上界的 expired segment，否则从最冷组选 valid block 最少的 segment。NoDaP 不可在线部署，但把 WAF 压到略高于 1.0，并用于「单变量替换」诊断 SOTA 三大短板（§3.2 的 NoDaP+SeU/MiU/PHU/MLU、+NGC、+NGrp 实验）。

### DOGI 整体架构

DOGI 将空间组织为 **G_hot + N 个 intermediate groups (G₁…G_N) + G_frzn**，N 动态调整。四个在线组件：

**1. Hot Filter (HF) + ML-Alloc（user-written block）**——回应观察 1 的精度-延迟矛盾：

- HF 用 latest invalidation time 与 BIR_hot 比较，快速把最热块送入 G_hot；µ 上界通过固定窗口（每窗 65K block）迭代调节：WAF 下降则扩大 µ，否则回退，5% 以内震荡则保持。
- 非热块由 ML-Alloc 的 **1.6K 参数两层 MLP** 分到 10 个 invalidation time category（c₁–c₁₀），再映射到 intermediate group。特征经 PCC/MI 从 11 个候选筛为 6 个（LBA、prev LBA、frequency、frequency per chunk、recency-weighted frequency、latest invalidation time）。
- **Batch inference**（128 block/batch）把单 block 推理从 10.6 µs 降到 0.9 µs；**double buffer**（两个 4 MiB buffer）与磁盘 flush 流水线重叠，原型均摊 **0.39 µs/block**（HF 0.13 µs + ML 0.94 µs × 24.7% 非热比例）。在线采 300K 样本训练 10 epoch（~30 s），每 26M block（~100 GiB）在专用核重训。

**2. Frozen Filter (FF) + ML-Reloc（GC-written block）**——回应观察 2：

- FF 用 1 bit/block 标记「从未被更新」的极冷块 → G_frzn；clock 算法每 200M write 清 flag 以捕捉突发后沉寂的块。
- 其余 GC-written block 查 **PLog**（训练集里的 predicted category vs actual invalidation time）：按源 category 算 mispredicted 块的平均剩余 invalidation time，再匹配目标 group BIR。最坏情况仍存活则 fallback age-based 下一组。

**3. Prediction accuracy-aware group configuration**——回应观察 3：

- 初始 10 组、BIR 几何倍增；用 PLog 算每组 misprediction ratio，喂入修改版 [[Markov-Chain]] WAF 模型，brute-force 评估 2⁹=512 种 merge 配置（~10 s），选 WAF 最低方案。
- 整体预测准确率跌破阈值（如 10%）时 **fallback**：退回经典 2 user + 2 GC 组（SepBIT/MiDAS 风格），待重训恢复后再切回。

**4. Victim selection**：仿 NoDaP——从 G_hot 到 G_{N-1} 找 expired segment；否则从最冷组选 valid 最少的 segment。主动回收 expired segment 即使仍含少量 live block，避免某组无限膨胀。

原型基于 ZenFS + [[RocksDB]] 插件，Western Digital ZN540 2 TB [[ZNS]] SSD，segment 与 ZoneFile 1:1 映射；核心算法在 trace-driven simulator 与原型间共享实现。

## 设计取舍

- **取舍 1：Hybrid heuristic + ML vs 纯 ML**。DOGI 放弃 ML-DT 式「所有 user block 走 TCN」，换取 66.5× 更低推理延迟和 19.4× 原型吞吐；代价是中间温冷 block 仍依赖有限表达力的 MLP，与 NoDaP 之间保留显著 WAF gap。
- **取舍 2：动态细粒度分组 vs 误判鲁棒性**。D-type workload 主动把 intermediate group 收到 2 个，牺牲细分离换低误判惩罚；S-type（FIO、YCSB）维持最多 7 个有效组（含 G_hot/G_frzn）。收益是跨 workload 稳定优于 MiDAS；边界是准确率骤降时需粗暴 fallback，短暂退回 SOTA 级 WAF。
- 取舍 3：PLog + MC 离线式 group 搜索 vs 运行时开销。512 配置枚举简单可解释、10 秒可完成，但不随容量扩展；内存中 PLog 与 per-block 元数据（HF/FF/ML 共 68 MiB @ 128 GiB）线性随容量增长——64 TiB 设备估算 34 GiB metadata，论文承认可能成为部署障碍。
- **边界条件**：在 skew 稳定、可在线学习的 S-type workload 上收益最大（WAF vs MiDAS −19.7%）；在相位快速变化的 D-type 上靠少分组 + fallback 仍赢 4.9–18.7%，但距 NoDaP 更远。GC relocation 对 Exchange 几乎无效。

## 实验与结果

- **平台**：Simulator（128 GiB、256 MiB segment、4 KiB block、10% OP）+ [[ZNS]] 原型（AMD EPYC Genoa 64 核，ZenFS，峰值顺序写 1.1 GiB/s）。Workload：FIO (Zipf)、YCSB-A/F on MySQL、Varmail、Alibaba cloud traces、Exchange traces（Table 4）。
- **主结果 WAF**（simulator，Fig. 10）：DOGI 平均比所有 workload 最强 baseline 降 **25.1%**；比最强 baseline MiDAS 平均降 **15.5%**，峰值 **23.2%**。相对 NoDaP 仍更高，gap 非平凡。
- **主结果吞吐**（prototype，Fig. 15）：平均写吞吐比 MiDAS 高 **9.2%**（abstract 峰值 **13.3%**）；相对 ML-DT **19.4×**，PHFTL **1.17×**，SepBIT **1.19×**。
- **预测精度**：比 SOTA 高 **0.9–8.1%**；user-block 准确率 S-type 78–84%、D-type 56–64%；热块分离 FIO 98.27%、Varmail 99.0%。
- **Ablation**（Fig. 14）：+User 在 Alibaba/Exchange 上因误判反而恶化 WAF；+Grp 在所有 workload 降 WAF（D-type 收益最大）；+GC 在 +Grp 基础上再降 **8.1%**（FIO GC relocation 准确率比 age-based 高 7.8%）。动态选中的 group 配置红点贴近 WAF 曲线谷底（Fig. 13）。
- **开销**：推理 DOGI 0.39 µs vs SepBIT/MiDAS <0.5 µs；内存 68 MiB（0.05% @ 128 GiB），低于 ML-DT 128 MiB。读延迟 50th/99th 与 MiDAS 相当或略优（Table 5）。
- **可扩展性讨论**：粗粒度 metadata（每 4 block 一条）可省 4× 内存，但准确率降 0.6–5.2%；计算开销（训练 + 512 配置搜索）不随容量增长。

## Critical Analysis

### 论证链条

NoDaP 量化 gap（三大策略各贡献多少 WAF 损失）→ 针对每点设计 HF/ML-Alloc、FF/ML-Reloc、PLog+MC 动态分组 → simulator 验证 WAF/accuracy/ablation → prototype 验证吞吐与推理延迟未损害前台 I/O。链条在「单节点 [[ZNS]]、trace replay、GC 主导 WAF」设定下闭合较好；从 simulator WAF 到 prototype 吞吐的对应关系作者用 Fig. 15 柱顶标注交叉验证。

薄弱跳步：(1) 多数 WAF 结论来自 simulator，原型只覆盖部分 workload 的吞吐/延迟，未在全量 Alibaba/Exchange trace 上跑物理设备；(2) NoDaP 的「near-optimal」无形式化证明，offline search 停止条件为 WAF 改善 <5%，可能非全局最优；(3) 把 PLog 分布外推到 GC-written block 剩余生命期默认 category 语义在搬迁后仍成立，Exchange 上有限改善提示该跳步不总是可靠。

### 假设压力测试

- **容量扩展**：per-block 1-bit flag + 特征 bitmap 线性扩容，64 TiB 需 ~34 GiB RAM——论文给出数量级但未提供 tiered/distributed metadata 方案；可能限制在大型 [[FTL]]/分布式 LSS 的 adoption。
- **Workload 漂移**：D-type 依赖 fallback + 重训；阈值 10% 准确率触发粗粒度模式期间 WAF 优势可能缩小，论文未量化 fallback 占空比与切换抖动。
- **多租户 / 混合介质**：实验为单设备顺序写主导；若与读密集、小 write buffer、或 HDD SMR 等非 [[ZNS]] 场景，batch inference 与 double buffering 假设可能弱化——论文未讨论。
- **ML 可解释性与安全**：MLP 黑盒误分温冷 block 的后果是额外 GC 拷贝，不破坏一致性，但可能被 adversarial access pattern 放大 WAF——论文未讨论。

### 实验可信度

- **Benchmark 代表性**：覆盖合成（FIO）、DB（YCSB）、邮件（Varmail）、云块存储（Alibaba）、企业（Exchange），比单一 YCSB 强；但全部偏 **write-intensive**，读放大、读延迟优化不是重点，与读多写少的生产池有距离。
- **Baseline 公平性**：四类 SOTA 均 reimplement，victim selection 保持原论文策略（cost-benefit / MiDAS FIFO+cost-benefit）；原型比较统一加 double buffering——对 ML-DT 仍无法掩盖 TCN 计算量，公平但凸显 DOGI 设计针对性。
- **Ablation**：+User/+Grp/+GC 递进清晰，支撑三组件必要性；缺少对 HF 单独、PLog 质量、MC 模型误差的分项敏感度分析。
- **Metrics**：WAF、预测准确率、写吞吐、推理延迟、读 tail latency 覆盖较全；**未测** GC 暂停时间分布、recovery after crash（segment footer / PLog 持久性）、训练期间 tail write latency、能耗。

### 系统性缺陷

- **实现复杂度**：Hot/Frozen filter、在线训练、512 配置搜索、segment footer 元数据、fallback 状态机——显著高于 SepBIT/MiDAS 纯启发式；论文未量化工程维护成本。
- **故障恢复**：PLog、模型权重、group configuration 的运行时一致性及 crash recovery 语义——**论文未讨论**。
- **可观测性**：未描述如何监控 misprediction ratio、fallback 触发、各 group 饱和度，运维排障路径不清。
- **资源隔离**：重训占用专用 CPU 核，但未测与 foreground 共用 socket 时的 noisy-neighbor 效应；未讨论多 volume 共享预测模型。
- **与现有系统栈集成**：原型绑定 ZenFS/[[RocksDB]]；移植到 [[F2FS]]、Ceph BlueStore、WAL 型 KV 的 segment 抽象差异——论文未涉及。

## 局限与 Future Work

- **局限 1**：相对 NoDaP 仍有显著 WAF gap，说明 oracle 知识不能完全用轻量 ML 替代；热/冷极端易预测，中间段仍是瓶颈。
- **局限 2**：Metadata 内存随容量线性增长；粗粒度压缩有 0.6–5.2% 精度损失，最优折中未充分探索。
- **局限 3**：D-type workload 预测准确率偏低，依赖少分组与 fallback，平均 WAF 改善（10.3% vs MiDAS）明显弱于 S-type（19.7%）。
- **局限 4**：GC relocation 对 Exchange 等动态 trace 改善有限，PLog 对搬迁后 block 的泛化不足。
- **Future work 1**：在 64 TiB 级设备上测量 metadata 内存与 misprediction 的联合曲线，设计 chunk-level 或 LBA-range 级共享特征，用 production trace 验证 4× 压缩是否可接受。
- **Future work 2**：将 DOGI 的 invalidation time 预测与 victim selection、over-provisioning 比例、[[ZNS]] zone 容量联合优化，而非固定 10% OP + NoDaP 式 victim 规则。
- **Future work 3**：在 workload 相位变化场景下评测 fallback 阈值、重训频率的 Pareto frontier，减少模式切换期间的 WAF 抖动。
- **Future work 4**：对比 Tomer Lange 等可证明 worst-case 界的 offline placement 算法，厘清 DOGI 在线启发式与理论最优的剩余差距来源。

## 相关

- **相关概念**：[[Garbage-Collection]]、[[Write-Amplification]]、[[Log-Structured-Storage]]、[[LSM-Tree]]、[[ZNS]]、[[Markov-Chain]]、[[FTL]]
- **同类系统**：SepBIT、MiDAS、PHFTL、ML-DT、NoDaP（oracle baseline）
- **相关存储栈**：[[RocksDB]]、[[F2FS]]、ZenFS
- **同会议**：[[FAST-2026]]
- **对比**：DOGI 相对 PHFTL/ML-DT 用 hybrid 换推理延迟；相对 SepBIT/MiDAS 用 ML+动态分组换 GC-block 重定位精度；相对 NoDaP 牺牲 oracle 知识换取可在线部署
