---
type: paper
name: ZUFS
full_title: "Unleashing Zoned UFS: Cross-Layer Optimizations for Next-Generation Mobile Storage"
authors: [Jungae Kim, Jaegeuk Kim, Kyu-Jin Cho, Sungjin Park, Jinwoo Kim, et al.]
venue: FAST
year: 2026
tags: [zoned-storage, mobile-storage, ufs, f2fs, android, garbage-collection]
source_pdf: "[[fast2026-kim-jungae.pdf]]"
source_md: "[[fast2026-kim-jungae]]"
---

# Unleashing Zoned UFS: Cross-Layer Optimizations for Next-Generation Mobile Storage (FAST 2026)

> **一句话总结**：观察到手机 [[UFS]] 容量十年涨 30× 但片上 SRAM 仍 ~1 MB，导致 [[L2P-Mapping]] cache miss 与 [[F2FS]] 碎片化双重拖垮 I/O；作者把 [[ZNS]] 式 zone 语义落地为 JEDEC ZUFS，并以设备端 ZABM 动态写缓冲 + 端到端写序修补 + 主动 GC 三套跨层改造，在 Pixel 10 Pro 量产机上实现碎片化场景写吞吐 >2× CUFS、Genshin Impact 校验加载快 14%、相册 jank 率 0.60%→0.26%。

## 问题与动机

智能手机已是默认计算平台，存储直接决定启动、游戏加载、相册滑动等体验。[[UFS]] 取代 eMMC 后带宽与队列深度大幅提升，但 **容量指数增长与片上 SRAM 停滞** 形成根本矛盾：商用 UFS 设备 L2P 映射表专用 SRAM 自 2017 年起基本停在 1 MB 以下，而容量已从 32 GB 涨到 1 TB（Figure 1）。page-level [[L2P-Mapping]] 在随机读范围扩大时频繁 map cache miss，读延迟方差剧增。

与此同时，Android 默认 [[F2FS]] 在真实手机上长期碎片化。作者对 10,000 部上一代旗舰（128 GB CUFS）的 telemetry 显示：约 **30% 设备 fragmentation level > 0.7**，且低利用率设备也大量高碎片化；写延迟 99 分位达 **678 ms/MB**，最差接近 2 s/MB。碎片化直接触发 foreground [[Garbage-Collection]]，与用户 I/O 争用。

JEDEC 2023 标准化 **Zoned UFS (ZUFS)**：zone 内强制顺序写，L2P 退化为 zone 粒度（1 TB 设备 Zone Mapping Table 仅 **8 KB** vs CUFS ~1 GB），并与 [[F2FS]] log-structured 设计天然对齐。论文 claim 的边界是：**规范本身不够**，商用手机要跨 Android framework → [[F2FS]] → block layer → SCSI/UFS driver → device firmware 全栈协同，否则 ZUFS 的理论收益无法兑现。深度背景见 [[fast2026-kim-jungae]]。

## 关键观察 / 隐含假设

- **观察 1：真实手机 F2FS 碎片化普遍且与利用率弱相关，直接恶化读写尾延迟。** 10,000 设备统计显示 fragmentation level 与 utilization 相关系数 r≈0.74，但大量低利用率设备仍严重碎片化；fragmentation > 0.4 后读延迟方差显著上升，> 0.8 后写吞吐断崖下跌。
  - **依赖假设**：telemetry 来自已上市约一年的单一代旗舰机型，F2FS 默认配置与 SSR 等行为代表当前 Android 主流栈。
  - **可能失效场景**：不同 OEM 调参、非 F2FS 文件系统、或用户极少写入的「干净」设备；telemetry 未覆盖低端机/小容量 UFS。
- **观察 2：ZUFS 规范要求至少 6 个并发 open zone，与 F2FS 默认 6 open zone 热冷分离一致，但静态 superpage 写缓冲在移动 SRAM 预算下不可行。** 评估设备每 zone 需 768 KB superpage 缓冲，6 zoned zone + 1 conventional LU 共需 **7×768 KB ≈ 5.4 MB**，远超控制器 SRAM。
  - **依赖假设**：F2FS 继续用多 open zone 分离 data/metadata 热度；zone 对齐 superblock（本设备 1,056 MB/zone）以消除 device-level GC。
  - **可能失效场景**：文件系统改为更少 open zone 或不同 section 布局；更小 die/plane 配置改变 superpage 尺寸与缓冲需求。
- **观察 3：移动端 UFS clock gating 的 requeue 路径会无声破坏 zoned 写序，而 datacenter [[ZNS]] 论文很少面对这一电源管理交互。** baseline Linux UFS 在 clock gated 时把请求 requeue 到 SCSI mid-layer，对 CUFS 无害但对 ZUFS 可导致 zone write pointer 错位。
  - **依赖假设**：手机 SoC 持续使用激进 UFS 省电策略；[[mq-deadline]] + Zone Write Locking (ZWL) 是 zoned 设备默认 I/O 调度路径。
  - **可能失效场景**：未来 UFS 规范/固件改为保序 ungate；或平台禁用 clock gating 换取正确性（能耗代价未测）。
- **观察 4：大 zone 消除 device-level GC 的同时，把 GC 成本上移到 F2FS section 粒度，单次 victim section 需迁移大量有效数据，更易触发 foreground GC。** 本设备 zone/section 为 1,056 MB，可用 section 总数减少，free section 池更快耗尽。
  - **依赖假设**：F2FS 以 section=zone 运行且禁用 IPU（ZUFS 不允许 overwrite）；背景 GC 可在用户读 I/O 时暂停。
  - **可能失效场景**：更小 zone 设备上 proactive GC 阈值需重调；极端写密集 workload 仍可能压过背景回收。
- **假设 1：F2FS strict LFS 模式 + [[Zoned-Block-Device]] 抽象足以让现有 Android 栈「最小改动」接入 ZUFS，无需像 ZMS 那样在 host 侧做 I/O reshaping。**
  - **证据强度**：中。论文展示 vold/fsmgr、ZBD 探测、LFS mode 挂载路径，但 IPU/Write-Booster 等 CUFS 优化路径被放弃，对小同步写场景的影响主要靠间接论证（SQLite atomic_write 等）。
- **假设 2：设备端 ZABM 优于 host-side IOTailor（ZMS 路线），因不依赖 JEDEC 未暴露的几何/flush 元数据，且避免 per-file encryption 下的跨文件合并限制。**
  - **证据强度**：中偏弱。ZMS 对比为**模拟** IOTailor 行为（固定 chunk 直写设备），非跑 ZMS 源码；真实生产 ZMS 可能有未建模优化。

## 核心方法

ZUFS 全栈改造横跨 device firmware、SCSI/UFS driver、block layer、[[F2FS]] 与 Android framework；评估硬件为 512 GB ZUFS（TLC NAND，16 KB page，zone 1,056 MB），对照组为同硬件 conventional LU  spanning 全卷的 CUFS。Pixel 10 Pro + Android 16 + kernel 6.6。

### 设备架构：ZMT/ZML 与 zone 粒度映射

ZUFS 用 **Zone Mapping Table (ZMT)** 替代 page-level [[L2P-Mapping]]：每 zone 一条 8 B 记录（起始物理地址 + 有效长度），配合 **Zone Mapping Log (ZML)** 批量 checkpoint，读 reclaim/wear-leveling 时临时记录 remapping。整表可常驻 SRAM，随机读不再受 map cache miss 惩罚——这是 ZUFS 在宽范围随机读上稳定吞吐的基础（§5.3）。

### Zone-Aware Buffer Management (ZABM)

回应观察 2。**Scatter-Gather Buffer Manager (SGBM)** 把 SRAM 切成 **4 KB slot**，每 open zone 维护线性 slot table（顺序写语义使索引可退化为 append-only 列表）。数据攒够单 die program unit（192 KB）即 flush；跨 die 凑满 superpage 则并行编程。相比为每 zone 固定 768 KB 缓冲：

- 多 zone 可共享 slot 池，重负载 zone 动态多占 slot；
- 细粒度 flush 允许 host 写与 NAND 编程 pipeline（Figure 8：192 KB chunk 比模拟 ZMS 768 KB 吞吐高 **26%**）；
- 硬件仅占控制器面积 **0.4%**，无需 host 侧 IOTailor 模块。

### 端到端写序保证

回应观察 3。修补点包括：

1. **UFS driver**：clock gating requeue 改为 **同步 ungate**——新 I/O 到达时等待时钟恢复再下发，避免 requeue 重排（已上游）。
2. **mq-deadline / block layer**：修复 `next_rq` stale 导致 zone 内乱序、FUA 请求绕过 ZWL、以及 `ionice`/`blk-ioprio` 优先级破坏顺序写等角落 case。

这些修改与 [[Zoned-Block-Device]] 语义绑定：F2FS 虽生成顺序写，block layer 与 UFS 省电路径仍可能打碎顺序性。

### Proactive Garbage Collection

回应观察 4。F2FS 新增 7 个 zoned sysfs knob（Table 1），按 free section 比例切换三阶段：

| 阶段 | 触发条件（默认） | 行为 |
|------|------------------|------|
| No-GC | free sections > 60% | 关闭背景 GC，优先响应 |
| Normal-GC | 25%–60% | cost-benefit 选 victim，按 `migration_window_granularity=3` segments 扫描 |
| Boosted-GC | free sections < 25% | 窗口 ×5 + greedy 算法加速回收 |

另引入 **`reserved_segments=6336`**（约为 6 open zone 所需 segment 数 2×）做细粒度 OP，并回收 CUFS 时代留给 device-level GC 的 OP 给文件系统。背景 GC 遇用户 **read** 立即暂停，保护读尾延迟。

## 设计取舍

- **设备端 ZABM vs host-side reshaping（ZMS/IOTailor）**：把复杂度锁在固件，避免 kernel 中间层、设备几何依赖和加密下合并限制；代价是控制器硬件面积（虽小）和 SK hynix/Google 联合实现的供应链绑定。
- **大 zone（1 GB 级）vs 小 zone**：大 zone 换 device parallelism 与零 device GC，但放大 F2FS 单次 GC 迁移量；用 proactive 三阶段 GC 换 foreground 停顿，阈值需 per-device 调校。
- **strict LFS vs IPU**：遵守 JEDEC 不可覆盖语义，放弃 F2FS IPU 对小同步写（fsync/SQLite）的优化；依赖 atomic_write + UFS Write-Booster 等既有路径，ZUFS 本身不加速这类写。
- **Conventional LU + Zoned LU 双 LU**：metadata 随机更新走 conv LU，用户数据走 zoned LU；增加栈复杂度但避免 metadata 破坏 zone 语义。
- **边界条件**：碎片化、宽范围随机读、游戏/相册类读密集 aged workload 上收益最大；干净设备顺序/随机读写与 CUFS 接近（GC 未触发时）。论文未讨论多租户、可拆卸存储或 UFS 4.x 新特性组合。

## 实验与结果

- **平台**：Google Pixel 10 Pro，12 GB LPDDR5X，512 GB ZUFS；CUFS baseline 为同硬件 conventional LU 占满卷；F2FS LFS mode（ZUFS）vs 标准模式（CUFS）。
- **干净设备吞吐（fio）**：顺序/随机读写 ZUFS 与 CUFS 相当（碎片化与 GC 未介入）。
- **宽范围随机读（4 GB–256 GB）**：CUFS 随范围扩大吞吐下降（map cache miss）；ZUFS 全程稳定。256 GB 文件、4 KB–512 KB block size：ZUFS 在 <128 KB 块显著领先，大块时差距缩小。
- **ZABM vs 模拟 ZMS**：单 zone 合成写，ZUFS 192 KB chunk 比模拟 ZMS 768 KB 高 **26%**；ZUFS 内 192 KB vs 768 KB chunk 几乎无差别，验证 die-level flush 不损吞吐。
- **渐进碎片化（32,768×128 KB 文件隔删 + 1 GB 测试文件）**：~90 轮后 CUFS 写吞吐跌至 ~100 MB/s、读降 ~35%；ZUFS 写持续 **>200 MB/s**（40/80 轮有 dips），读吞吐稳定。Figure 10 显示 ZUFS 靠 Normal/Boosted GC 维持 free section 池。
- **Genshin Impact（~40 GB 资源校验 + 加载，aged 设备）**：ZUFS **30 s** vs CUFS **35 s**（**14%**）；ZUFS 读请求多数 >512 KB，CUFS 因 SSR 66.3% 请求在 4–8 KB。
- **相册滑动（1,300 张照片，aged）**：jank rate **0.60%→0.26%**；每文件平均 fragment 数 **46.29→2.31**，平均 fragment 长度 **99 KB→1,979 KB**；p99 frame time **16 ms→11 ms**。
- **映射与硬件开销**：1 TB ZMT **8 KB** vs CUFS page table ~1 GB SRAM 需求；ZABM **0.4%** 控制器面积。
- **部署**：改动已上游 Linux kernel 与 Android；Pixel 10 Pro 系列 2025 量产，作者称首个商用旗舰 zoned storage 部署。

## Critical Analysis

### 论证链条

**碎片化 → ZUFS zone 映射 + 顺序写 → 稳定读 & 更高写下限** 链条在 microbenchmark 与两个 app workload 上较闭合。10k 手机 telemetry 支撑「碎片化是生产问题」；宽范围随机读实验直接验证 ZMT 消除 map cache miss；碎片化迭代实验把吞吐曲线与 F2FS segment 统计、GC 阶段切换对齐，解释力强。

较弱环节是把 **2× 写吞吐** 与 **14% 游戏加载** 外推为「ZUFS 全面优于 CUFS」。干净设备上二者持平说明收益高度依赖 aged/碎片化状态；游戏实验只覆盖 Genshin 校验路径（读密集、顺序化受益），未覆盖写入型 AI on-device、OTA 大包下载等。论文强调 cross-layer 必要性，但 ablation 未独立关掉 ZABM / 写序修补 / proactive GC 三组件量化各自贡献。

### 假设压力测试

**Workload 漂移**：若 Android 未来减少 SSR 或改变 F2FS segment 布局，CUFS 的小块读劣势可能减弱；反之，更多 on-device LLM checkpoint/embedding 随机写可能放大 ZUFS 的 strict LFS 与 large-zone GC 压力——论文未测这类新兴负载。

**硬件代际**：评估基于单一 SK hynix 512 GB 设备与 1,056 MB zone。不同 NAND 几何、更少 open zone 规格、或 UFS 4.x 功耗/队列特性可能改变 ZABM slot 数与 GC 阈值最优值；§4.4 承认 knob 需 integrator 调校，但未给 sensitivity study。

**ZMS 对比公平性**：ZMS 为模拟而非开源复现，且 ZMS 的 spec-violating IPU 被论文明确排除——对比偏向「合规 ZUFS vs 需 host 重塑的替代方案」，对「host-side FTL」（Yan et al. CCGrid'24）仅讨论未 benchmark。

**正确性 vs 性能**：写序修补依赖多条 kernel 角落 case 修复；论文证明部署于量产机，但未提供 formal 测试矩阵或断电恢复压力测试统计，长期 corner case 回归风险需依赖上游 CI。

### 实验可信度

**强项**：真实商用手机（非模拟器）、与 CUFS 同硬件对照、10k 设备 field data、上游开源 artifact、micro + app 两层评估、碎片化过程与 GC 阶段可观测。

**不足**：机型单一（Pixel 10 Pro + 上一代 128 GB telemetry 机型不一致）；缺少能耗/WAF/endurance 长期测试（ZUFS 理论降 WAF 但实验未报 device WAF 数字）；tail latency 以 block layer 平均/分位为主，缺少全系统 p99.9 或 power-state 切换期间延迟；SQLite/数据库小同步写场景无直接对比。

### 系统性缺陷

- **尾延迟与功耗**：背景 GC 虽在读时暂停，Boosted 阶段仍可能与写流量争用；clock gating 同步 ungate 对空闲唤醒延迟和能耗的影响论文未量化。
- **故障恢复**：ZML/ZMT checkpoint 与 open zone write pointer fsck 有描述，但突然掉电、固件 OTA、跨版本 kernel 升级的恢复测试未展开。
- **可观测性 / 运维**：sysfs GC knob 暴露给 integrator，但普通开发者如何诊断「ZUFS 进入 Boosted GC」的生产工具链论文未讨论。
- **多应用干扰与加密**：Android per-file encryption 限制 host 合并——ZABM 在设备侧规避了这点，但多 app 并发写不同 zone 时的 fairness 未测。
- **兼容性**：strict LFS 放弃 IPU；依赖 conv LU 存 metadata——双 LU 配置错误时的失败模式论文未讨论。

## 局限与 Future Work

- **局限 1**：评估集中在单一旗舰平台与 F2FS/Android 栈，结论对其它 OEM、容量档位、workload 的外推需谨慎。
- **局限 2**：大 zone 下 F2FS GC 仍是非零成本，proactive 策略减轻但未消除 foreground GC 可能；极端空间压力下表现未充分刻画。
- **局限 3**：ZMS/host-side 方案对比不完整，缺少与 Yan et al. host-side FTL 或合规版 ZMS 的端到端 benchmark。
- **局限 4**：能耗、WAF、flash endurance 等 ZUFS 理论优势未在长时间 field study 中验证。
- **Future work 1**：在多样 NAND 几何与 zone 尺寸上系统扫描 GC knob sensitivity，建立 integrator 自动调参或 workload-aware 策略。
- **Future work 2**：测量 on-device AI、大模型缓存、持续同步写等新兴 mobile workload 下 strict LFS 的写放大与尾延迟，并与 Write-Booster/atomic_write 路径做联合优化。
- **Future work 3**：跨机型 field telemetry 复现 fragmentation→latency 因果，验证 proactive GC 在生产环境的 foreground GC 触发率下降幅度。
- **Future work 4**：形式化或大规模混沌测试写序 + 断电恢复，覆盖 UFS 省电状态机与 kernel 升级回归。

## 相关

- **相关概念**：[[ZNS]]、[[Zoned-Block-Device]]、[[UFS]]、[[F2FS]]、[[L2P-Mapping]]、[[Garbage-Collection]]、[[Write-Amplification]]、[[Log-Structured-File-System]]
- **同类系统**：ZMS（ATC'24 host-side IOTailor）、Yan et al. host-side ZUFS FTL（CCGrid'24）、[[ZNS+]]、[[eZNS]]、[[ZNSwap]]、[[DOGI-FAST26]]
- **同会议**：[[FAST-2026]]
- **对比**：相对 ZMS，ZUFS 坚持 JEDEC 合规、设备端 ZABM、无 host reshaping；相对 datacenter [[ZNS]]，ZUFS 直面 mobile SRAM/clock gating/F2FS large-section GC 三重约束