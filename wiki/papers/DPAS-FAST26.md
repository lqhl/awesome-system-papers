---
type: paper
name: DPAS
full_title: "DPAS: A Prompt, Accurate and Safe I/O Completion Method for SSDs"
authors: [Dongjoo Seo, Jihyeon Jung, Yeohwan Yoon, Ping-Xiang Chen, Yongsoo Joo, Sung-Soo Lim, Nikil Dutt]
venue: FAST
year: 2026
tags: [ssd, nvme, io-completion, hybrid-polling, kernel, latency]
source_pdf: "[[fast2026-seo.pdf]]"
source_md: "[[fast2026-seo]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# DPAS：一种快速、准确、安全的 SSD I/O 完成方法（FAST 2026）

> **原题**：DPAS: A Prompt, Accurate and Safe I/O Completion Method for SSDs

> **一句话总结**：观察到 epoch-based hybrid polling 无法区分「设备真慢」与「自己睡过头/调度延迟」（latency shelving），且 polling/interrupt/hybrid 在争用场景下各有硬伤；PAS 用最近两次 I/O 的 UNDER/OVER 二元反馈 per-I/O 调 sleep duration，DPAS 再在 classic polling / PAS / interrupt 间动态切换——4 KB 随机读 CPU 比 Linux hybrid polling 低 21 个百分点，YCSB 在 3D XPoint SSD 提速 9%、TLC NAND SSD 提速 5%（CPU 争用 + I/O 干扰并存）。

## 问题与动机

现代 [[NVMe]] SSD 延迟已低到微秒级，传统 interrupt 完成路径的 context switch、cache pollution、CPU power state 切换开销在总延迟中占比显著上升；纯 polling 可消除这些开销，在 storage-class memory 与 ultra-low latency (ULL) SSD 上已被验证有效，但会独占 CPU，在 CPU contention 下吞吐急剧下降。

**Hybrid polling** 折中：先 sleep 一段再 poll，理想是醒来正好赶上 I/O 完成。Linux hybrid polling（LHP）用 16 个 size/read-write bucket，每 100 ms epoch 更新统计，sleep duration 取上一 epoch 均值的一半（50% 衰减作安全余量）。作者 claim 现有方案在三个维度均不足：

1. **Promptness**：epoch 采样无法跟踪突发 latency 变化，缩短 epoch 只能缓解不能根治；
2. **Accuracy**：固定 50% 衰减在 latency 稳定时过于保守，白白增加 polling 时间；
3. **Safety**：高 variance 时 50% 余量仍不够，频繁 oversleep 抬高应用感知延迟。

更致命的是 LHP、HyPI、EHP 都基于**实测 I/O 总时长**估计 sleep，该时长混合了设备固有延迟与软件 oversleep/调度延迟，无法拆分。CPU contention 下 OS 调度延迟会被误判为「设备变慢」，sleep target 被持续抬高——作者称为 **latency shelving**，需多个 epoch 才能恢复。

论文进一步指出：**polling、hybrid polling、interrupt 各有固有弱点，不存在单一方法在所有场景下最优**。这 motivates DPAS：在 PAS（改进的 hybrid polling latency tracking）之上做 runtime mode switching。

## 关键观察 / 隐含假设

- **观察 1**：Hybrid polling 的 sleep 估计误差可用 wake 后 poll 的**二元结果**（UNDER：I/O 未完成；OVER：I/O 已完成）表达，且最近两次结果的四种组合足以指示 sleep duration 应增、减还是穿越 latency 下包络。
  - **依赖假设**：modified poll 能在无设备显式信号下可靠区分 under/over-sleep；per-I/O 粒度反馈比 epoch 统计更能跟踪突变；优先避免 oversleep（作者明确 oversleep 对性能伤害大于 undersleep）。
  - **可能失效场景**：并发 I/O 时 sleep result 可能 stale 或被覆盖（论文 §3.4 已识别）；hrtimer 精度与 timer 路径自身开销使「二元结果」与真实完成时刻存在系统偏差；大 I/O（≥128 KB）时 polling 优势本身消失，PAS 跟踪价值下降。

- **观察 2**：epoch-based 方法把 OS 调度造成的 oversleep 记入设备 latency，引发 latency shelving；PAS 将 scheduler 延迟识别为 OVER 并**主动缩短** sleep，与 LHP 行为相反。
  - **依赖假设**：持续 CPU contention 时 PAS 会把 sleep duration 压到 0，进入可检测的 **timer failure**（busy-wait 循环反复调用 timer 却不真睡）——这是切换模式的可靠信号，而非需掩盖的噪声。
  - **可能失效场景**：短暂、偶发调度延迟可能触发过度缩短；timer failure 检测与 QD 阈值若不同步，可能在 PAS overloaded 与 interrupt 间抖动；论文未在虚拟化/容器 cgroup 限 CPU 场景验证。

- **观察 3**：低争用时 classic polling 吞吐最高（Optane 上 CP 比 INT 读 IOPS 高 30%），高争用时 interrupt 更稳；QD=1 可作为「单线程独占 CPU」的代理信号，用于在 CP 与 PAS 间切换。
  - **依赖假设**：测试平台禁用 hyper-threading（论文称 HT 使 INT 4 KB 随机读 IOPS 比 CP 低 40%）；foreground 与 background（如 [[RocksDB]] compaction）线程争用可被 timer failure + QD 联合检测；NAND flash SSD 的 QD 阈值 θ=1、3D XPoint θ=3 可跨设备泛化。
  - **可能失效场景**：多租户共享 CPU 时 QD=1 不保证低争用；云 VM 中 timer 与调度行为与裸机不同；θ 仅按介质类型二分，同族 SSD 内部差异（论文在 9 块额外 NAND 上测，SN850X 上 DPAS 未优于其他方法）。

- **假设 1**：(UP, DN) = (0.01, 0.1) 与 HEATUP/COOLDN = (0.05, 0.1) 经 PAS-Sim 与真实 trace 扫参后**device-agnostic**，无需 per-SSD offline profiling（对比 HyPI）。
  - **证据强度**：**中**——在 Optane/ZSSD/P41 + 9 块额外 NAND + 1 块额外 XPoint 上表现稳定，但 SN850X 例外；simulator 用单 bucket 子 trace，未覆盖全 size 分布。

- **假设 2**：Kernel block layer（multi-queue）内实现 PAS/DPAS，每 core 592 B PAS 状态 + 104 B 模式逻辑，改 9 个文件共 1224 行，部署成本可接受。
  - **证据强度**：**强**——有开源 artifact（Linux 5.18）；但每 CPU 双 device queue（poll + interrupt）在 CPU 数远超 device queue 数时会共享 interrupt queue，论文承认可能劣化 I/O。

## 核心方法

### PAS：per-I/O latency tracking（PAS：每I/O延迟跟踪）

回应观察 1 与 latency shelving（观察 2 的前半段）：

- 沿用 LHP 的 16 bucket（8 size × read/write），但 sleep duration 由 **adjust** 系数乘法更新，而非 epoch 均值。
- 每次 I/O 后根据 (sr_pnlt, sr_last) 更新 adjust：(UNDER, UNDER)→+UP；(OVER, OVER)→−DN；穿越包络 (UNDER, OVER) 或 (OVER, UNDER)→reset adjust=1 并单步反向调整。
- 初始 duration=0.1 µs，sr 初始 (OVER, UNDER)，避免首轮 oversleep。
- **Dynamic sensitivity**：连续相同 sleep result 时 UP/DN 乘 (1+HEATUP)；交替 result 时乘 (1−COOLDN)；UP 限制在 [0.001, 0.01]，UP:DN 固定 1:10。
- **并发支持**：per-core PAS 变量 +「仅首个完成 I/O 提交 sleep result、仅首个新 result 后的 I/O 更新 duration」规则，避免 stale/覆盖（Figure 9）。

### DPAS：dynamic mode switching（DPAS：动态模式切换）

回应观察 2 后半段与观察 3——hybrid polling 的 timer 开销与争用下退化：

四模式状态机（Figure 10）：

| 模式 | 触发 / 行为 |
|------|-------------|
| **PAS normal** | 默认；每 N_PAS=100 个 I/O 测平均 QD |
| **Classic polling** | QD=1 → 切 CP，发 N_CP=1000 个 polled I/O 后回 PAS normal |
| **PAS overloaded** | 检测到 timer failure（sleep duration→0）→ 再发 N_PAS 个 I/O 测 QD |
| **Interrupt** | PAS overloaded 且 QD>θ（NAND θ=1，XPoint θ=3）→ 发 N_INT=10000 个 INT I/O 后回 PAS overloaded |

设计意图：低争用吃 CP 的零 context-switch 红利；timer/调度异常时先 PAS overloaded 试探，严重争用才退 interrupt；N_INT≫N_CP 因过早回 PAS 的 busy-wait 代价远高于 interrupt 效率损失。

实现于 Linux multi-queue block layer，与 EHP 类似每 CPU 分配 poll queue 与 interrupt queue；细节见 source_md。

## 设计取舍

- **取舍 1：二元 sleep result vs 连续 latency 测量**。不记录绝对 I/O 时间，避免把 oversleep 混入设备 latency 统计；代价是丧失对「差多少」的细粒度信息，靠 UP/DN 比例与 dynamic sensitivity 逼近。收益是 per-I/O 响应、无 epoch 延迟、从机制上切断 latency shelving。
- **取舍 2：per-core PAS vs per-device PAS**。per-device 在并发 I/O 下统计污染严重（sleep duration 指数膨胀）；per-core 增加内存（≈700 B/core）并需 first-completer 仲裁，但消除锁竞争与 stale result。
- **取舍 3：DPAS 偏 IOPS 最大化 vs CPU 节能**。默认优先切 classic polling 追求吞吐；Discussion 提出可关 CP 路径做「CPU-saving mode」，只保留 PAS+INT，接受略低 IOPS——论文未实现该模式。
- **取舍 4：固定 θ 按介质类型 vs per-device tuning**。仅 NAND/XPoint 两档，9/10 额外 SSD 有效，部署简单；SN850X 失效说明二元分类不够。
- **边界条件**：4 KB 随机读 / 小 I/O trace（Slacker、Systor）收益最大；128 KB 读上 polling 优势消失，P41 上 DPAS 甚至略低于 INT（~1%）且 99.95th 延迟上升；未集成 interrupt coalescing，interrupt 模式下高并发可能 interrupt storm（论文 §5 讨论可用 vIC 类动态 coalescing 扩展）。

## 实验与结果

**平台**：Intel Xeon Gold 6230（20C）、192 GB DDR4、Ubuntu 18.04 + Linux 5.18；Optane P5800X（3D XPoint）、Samsung 983 ZET（Z-NAND）、SK hynix P41（TLC NAND）；禁用 HT。对比 INT、CP、LHP、EHP、PAS、DPAS。

- **Microbenchmark（FIO 4 KB 随机读）**：PAS hybrid 方法中 CPU 最低，比 LHP **低 21 个百分点**；DPAS 主要驻留 CP 模式，IOPS 接近 CP，CPU >90%（除 Optane 20 线程饱和）。
- **Timer 开销**：Optane 上固定 1 µs sleep 的 LHP 129 KIOPS vs CP 134 KIOPS（**4%** 退化），证明 hybrid 并非免费午餐。
- **YCSB + RocksDB**：几何平均 A–F workload；4 CPU + 2–32 线程争用下，DPAS 在 Optane/ZSSD/P41 维持 competitive OPS，PAS 在 16–32 线程 on ZSSD/P41 显著低于 INT。
- **CPU + I/O 干扰**（4 YCSB + 4 个 128 KB pulse generator）：DPAS 平均 OPS 比 INT 高 **9% / 7% / 5%**（Optane / ZSSD / P41）；LHP/EHP/CP 多处低于 INT。
- **Trace replay**（Baleen / Systor / Slacker）：大 I/O 为主的 Baleen 各方法差距小；小 I/O trace 上 PAS CPU 低于 LHP，DPAS 接近最优 IOPS。
- **大 I/O**：≥128 KB 读时 EHP 无 IOPS 增益；P41 128 KB 上 DPAS 略输 INT。
- **扩展 SSD**：Figure 22 上 8 块额外 NAND + 1 块 XPoint，DPAS 除 **SN850X** 外均优于其他方法；θ 未 per-device 调参。
- **能耗**：高争用下 CP 因执行时间长总能耗最高；争用降低后各方法差距收窄。
- **Artifact**：开源于 GitHub `DongDongJu/DPAS_FAST26`，支持 C1–C3 定性复现。

## 批判性分析

### 论证链条

问题（ULL SSD 下 interrupt 开销显著，hybrid polling 估计不准 + latency shelving）→ 观察（二元 under/over 反馈可 per-I/O 跟踪包络；三种完成方式互补）→ PAS（两最近 I/O 状态机 + 动态灵敏度 + per-core 并发）→ DPAS（timer failure + QD 驱动四模式切换）→ FIO / SNIA trace / YCSB / 合成干扰 / 11 块 SSD 验证。

链条在「Linux kernel block path、NVMe polled I/O（pvsync2/hipri）、4 KB 随机读为主」设定下较闭合：Figure 20 trace 直观展示 LHP/EHP 的 epoch 滞后 vs PAS 即时跟踪 vs DPAS 模式切换；ablation 含 PAS-Sim 扫参、N_CP/N_INT 敏感性、DN/UP ratio。

薄弱跳步：(1) 从 microbenchmark IOPS/CPU 到 YCSB OPS 的因果链未隔离「RocksDB 后台线程 + DPAS 模式占比」对各 workload 的差异化影响；(2) 声称「无需 per-application profiling」优于 Select-ISR/CINT，但 YCSB 是固定 synthetic mix，未测真实多应用混部；(3) timer failure 定义为 sleep duration→0，与「hrtimer 精度误差」的边界未量化。

### 假设压力测试

- **虚拟化 / 容器**：全部裸机单 socket；KVM/容器内 hrtimer 与 steal time 可能使 UNDER/OVER 语义失真——**论文未讨论**。
- **io_uring / [[SPDK]] 用户态路径**：工作聚焦 kernel NVMe block layer；用户态轮询栈是否需类似 DPAS 逻辑未知——论文 Related Work 提及但未实验。
- **写路径与 fsync**：评估以随机读、YCSB 为主；写 I/O latency 分布不同，bucket 分离是否足够——写 scalability 图省略，证据弱。
- **HT 开启的生产服务器**：明确禁用 HT 做可重复性；多数云实例默认 HT on，INT vs CP 差距可能缩小，DPAS 切换收益可能变化。
- **长期稳定性**：每次实验 10 s FIO 或固定 op count YCSB，未测 mode thrashing 的小时级行为；N_INT=10000 窗口在突发争用消退慢时可能过长驻留 interrupt。

### 实验可信度

- **Benchmark 代表性**：SNIA IOTTA trace + YCSB/RocksDB 覆盖 latency-sensitive DB 场景；缺少 TPC-C、真实 KV store production trace、ML checkpoint 等 FAST 26 其他论文常用负载。
- **Baseline 公平性**：LHP/EHP 均为同期强 baseline；未与 [[LinnOS]]（OSDI'20 神经网络 fast/slow 预测）、CINT/OSDI'21 动态 interrupt coalescing 直接比延迟尾；Select-ISR 仅用 CP/INT 代表两类应用，非完整复现。
- **Ablation**：PAS-Sim 支持 (UP,DN) 与 HEATUP 选择；DPAS 有 N_CP/N_INT sweep；缺少「仅 PAS 无 DPAS」「固定 θ 错配」「per-device vs per-core」的 macro 级拆分表。
- **Metrics**：重 OPS/IOPS 与 CPU%；YCSB 有 90th/99.99th 分析（Figure 19），但 DPAS 相对 CP 的 tail 改善多归因于模式切换，未给出各模式占比 vs 尾延迟的回归。

### 系统性缺陷

- **尾延迟**：I/O 干扰下 DPAS 90% 时间可在 CP，tail 仍高于 INT 但远低于 CP（ZSSD UPDATE 99.99th：CP 为 INT 的 17×）；interrupt 模式无 coalescing，高 QD 时尾延迟风险——论文承认并指向 future work。
- **资源隔离**：per-core PAS 不解决多 VM 同 core 的公平性；**论文未讨论** cgroup 限速场景。
- **可观测性**：模式切换依赖内部计数，未提 perf/tracepoint 接口供运维诊断 thrashing。
- **故障恢复**：不涉及 SSD 故障或路径降级；纯性能路径优化。
- **部署**：需定制 kernel 5.18 + 双 queue 映射；升级/mainline 合并成本高于用户态 [[SPDK]] 调 poll interval。

## 局限与后续工作

- **局限 1**：hybrid polling 即使无 oversleep，hrtimer/wake 路径仍引入 cache eviction 等间接开销，PAS 无法消除，只能靠 DPAS 切 CP 规避部分场景。
- **局限 2**：128 KB+ 大 I/O 与 DRAM buffer 充足的 consumer SSD（P41）上优势收窄或反转；固定 I/O-size cutoff 类方案（HyPI/EHP）的问题以另一种形式出现——模式切换未能按 I/O size 细分。
- **局限 3**：θ 的两分法在 SN850X 上失效，说明「NAND vs XPoint」不足以预测最优 QD 阈值。
- **Future work 1**：DPAS **CPU-saving mode**——禁用 classic polling，仅 PAS+INT，用可测量 trade-off 刻画 IOPS vs CPU headroom 曲线。
- **Future work 2**：集成**动态 interrupt coalescing**（如 vIC 思路），按 in-flight 数与 I/O rate 调节，使 interrupt 模式可服务 throughput-heavy 负载而不 storm。
- **Future work 3**：单 device queue 同时承载 poll/interrupt I/O，或动态 queue mapper，缓解 CPU 数 ≫ device queue 数时的共享退化。

## 相关

- **相关概念**：[[NVMe]]、[[io_uring]]、Hybrid Polling、I/O Completion、Context Switch、Interrupt Coalescing、Tail Latency
- **同类系统/工作**：LHP（Linux hybrid polling）、EHP、HyPI、[[LinnOS]]、Select-ISR、CINT、[[SPDK]]、[[RocksDB]]
- **同会议**：[[FAST-2026]]
- **对比**：DPAS vs LHP/EHP（epoch hybrid）、DPAS vs Select-ISR/CINT（静态分类/合中断）
