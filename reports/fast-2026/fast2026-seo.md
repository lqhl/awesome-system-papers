# DPAS: A Prompt, Accurate and Safe I/O Completion Method for SSDs

**作者**：Dongjoo Seo (UC Irvine / Samsung Semiconductor), Jihyeon Jung (Kookmin University / grepp.co), Yeohwan Yoon (Kookmin University / FADU Inc.), Ping-Xiang Chen (UC Irvine), Yongsoo Joo (Kookmin University, 通讯作者), Sung-Soo Lim (Kookmin University), Nikil Dutt (UC Irvine)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/seo
**源文件**：[[fast2026-seo.pdf]]

---

## 一、背景

现代 SSD 的 I/O 延迟已降至微秒级，传统中断（interrupt）机制的上下文切换、cache 污染和 CPU 电源状态转换等隐性开销变得不可忽略。经典轮询（classic polling）消除了这些开销，但会独占 CPU，在 CPU 竞争环境下性能急剧下降。混合轮询（hybrid polling）试图折中——先让 CPU 睡眠一段时间，再轮询等待 I/O 完成——但其效果高度依赖于睡眠时长的准确预估。

Linux 内核的混合轮询实现（LHP）使用基于 epoch 的统计（每 100ms 更新一次），以均值的 50% 作为睡眠时长。后续工作 EHP 用最小值替代均值并缩短 epoch，HyPI 对不同 I/O 大小使用不同衰减率。这些方法都存在三个共性缺陷：对延迟突变响应慢（epoch 边界锁定）、安全裕度与精度的权衡难以兼顾、以及无法区分设备延迟变化与预测误差导致的过度睡眠（oversleep），从而引发"延迟搁浅"（latency shelving）问题。

---

## 二、要解决的问题

1. **响应延迟（Promptness）**：epoch-based 方法在延迟突变时需等到下一个 epoch 才能更新睡眠时长，存在系统性滞后。
2. **精度不足（Accuracy）**：固定 50% 衰减率在延迟稳定时过于保守（大量 undersleep 浪费 CPU），在延迟剧烈波动时又不够安全（仍可能 oversleep）。
3. **安全性缺失（Safety）**：现有方法仅使用测量到的总 I/O 时间，无法区分设备真实延迟增加与 OS 调度引起的过度睡眠。误判导致睡眠目标被持续抬高（latency shelving），需多个 epoch 才能恢复。
4. **CPU 竞争下的退化**：hybrid polling 在 CPU 高负载时，OS 调度器无法按时唤醒线程，导致严重 oversleep。PAS 会把睡眠时长压到零（timer failure），退化为高开销的 busy-wait 循环。
5. **并发 I/O 的干扰**：多核/多线程并发 I/O 时，per-device 模式下控制变量的共享和锁竞争导致性能下降，且过时的睡眠结果会引起指数级睡眠增长。

---

## 三、洞察与设计

**关键洞察**：I/O 完成检测的睡眠结果只有两种（undersleep 或 oversleep），利用最近两次 I/O 的二元结果对（而非精确延迟测量），就能以极低开销实时跟踪延迟下包络线，同时天然地区分设备延迟变化与预测误差——无需依赖 epoch 统计。

### PAS（Prompt, Accurate and Safe）

PAS 的核心是一个乘法自适应控制器，使用最近两次 I/O 的睡眠结果对 `(sr_pnlt, sr_last)` 来调整睡眠时长：

- **(UNDER, UNDER)**：睡眠仍然太短，累加增量 UP 加速增长
- **(OVER, OVER)**：睡眠仍然太长，累减 DN 加速收缩
- **(UNDER, OVER)**：刚从下方穿越延迟包络线，微减 DN（过冲修正）
- **(OVER, UNDER)**：刚从上方穿越延迟包络线，微增 UP

通过仿真确定 DN/UP = 10:1（UP=0.01, DN=0.1）的基线配置，确保快速收敛于下包络线且 oversleep 极少。

**动态灵敏度调整**：引入 HEATUP 和 COOLDN 参数，当连续同向结果出现时放大 UP/DN（加速响应），方向切换时缩小 UP/DN（减少振荡）。经验值设为 (HEATUP=0.05, COOLDN=0.1)。

**并发 I/O 支持**：从 per-device 切换到 per-core 模式，每个 CPU 核心维护独立的 PAS 变量。同一核心的多线程共享时，仅第一个完成的 I/O 提交睡眠结果，仅第一个看到新结果的 I/O 更新睡眠时长。

### DPAS（Dynamic PAS）

DPAS 在 PAS 基础上增加 per-core 动态模式切换，在四种状态间转换：

1. **Classic polling**：队列深度 QD=1 时切换，最大化单线程 IOPS
2. **PAS normal**：常规混合轮询，默认状态
3. **PAS overloaded**：检测到 timer failure 后进入，重新评估 QD
4. **Interrupt**：QD 超过阈值 θ 时切换（NAND SSD: θ=1, 3D XPoint: θ=3）

切换参数：N_PAS=100, N_CP=1000, N_INT=10000，经灵敏度分析确定。

---

## 四、实现细节

- 在 Linux 5.18 内核的多队列块层（multi-queue block layer）中实现
- 每个 PAS bucket entry 占 37 字节（adjust, duration, UP, DN, sr_pnlt, sr_last 等变量），16 个 bucket/核心，PAS 共 592 字节/核心
- DPAS 模式切换逻辑额外增加 104 字节/核心，全局变量 100 字节/核心
- 修改 9 个源文件，新增 1,224 行代码，删除 30 行
- DPAS 为每个 CPU 分配两个设备队列：一个用于 polled I/O，一个用于 interrupt I/O
- 使用 hrtimer（高精度定时器）实现睡眠控制
- 通过修改内核 poll 函数获取二元睡眠结果（无需设备端信号）
- 开源代码：https://github.com/DongDongJu/DPAS_FAST26

---

## 五、实验结果

**实验平台**：Intel Xeon Gold 6230 (20 cores, 2.10 GHz), 192 GB DDR4, Ubuntu 18.04, Linux 5.18。三种 SSD：Intel Optane DC P5800X (3D XPoint), Samsung 983 ZET (Z-NAND), SK hynix P41 (TLC NAND)。关闭超线程。

### 微基准测试（FIO, 4KB 随机读）

| 指标 | PAS vs LHP | DPAS vs INT |
|------|-----------|-------------|
| CPU 使用率降低 | 平均降低 21 个百分点 | — |
| IOPS（无竞争） | 与 CP/DPAS 相当 | 接近 CP 水平 |
| 大 I/O (128KB) | 优势减小 | P41 上略低于 INT (~1%) |

### 宏基准测试（YCSB on RocksDB）

| 场景 | DPAS vs INT |
|------|-------------|
| 无 CPU 竞争 (线程=CPU) | Optane 上 5-8% OPS 提升 |
| CPU 竞争 (4 CPU, 2-32 线程) | 低线程优势明显，高竞争时也不退化 |
| I/O 干扰 + CPU 竞争 | Optane +9%, ZSSD +7%, P41 +5% |

### 关键对比

- **PAS vs LHP/EHP**：PAS 在延迟跟踪精度上显著优于 epoch-based 方法，尤其在 I/O 延迟突变和干扰场景下保持稳定
- **DPAS vs CP**：CP 在 CPU 竞争下性能骤降（尾延迟增大 17-30×），DPAS 通过动态切换避免了这一问题
- **DPAS 跨设备泛化**：在 8 种额外 NAND SSD 和 1 种额外 3D XPoint SSD 上验证，无需逐设备调参，除 SN850X 外均优于其他方法
- **能耗**：CP 在高竞争下能耗最高（执行时间更长），DPAS 接近 INT 水平

---

## 六、批判性分析

1. **实验平台单一且老旧**：所有实验在单一 CPU（Xeon Gold 6230）和 Linux 5.18（2022 年）上进行。现代内核（6.x）的调度器、io_uring、NVMe 多队列等改进可能显著改变 hybrid polling 的行为，论文未讨论跨内核版本的适用性。

2. **θ 阈值并非真正免调参**：论文声称 DPAS 无需 per-device tuning，但实际上 θ 对 3D XPoint 和 NAND SSD 使用了不同值（3 vs 1）。这意味着在新型存储介质（如 CXL 内存、新一代 ULL SSD）上仍需经验调优。

3. **并发 I/O 设计的信息损失**：per-core 模式下，同一 CPU 的多线程并发时仅允许第一个完成的 I/O 提交结果，其余 I/O 的睡眠反馈被丢弃。在高并发场景下，PAS 实际上只使用了很小一部分采样，论文未分析采样率下降对跟踪精度的量化影响。

4. **尾延迟问题被轻描淡写**：Figure 19 显示 DPAS 在 ZSSD 上的 P99.99 和最大延迟仍高于 INT，因为其 90% 的 I/O 运行在 CP 模式。论文承认了这一点但未给出解决方案，而尾延迟恰恰是生产环境最关心的指标之一。

5. **缺少 io_uring 对比**：io_uring 的 polling 模式（IORING_SETUP_IOPOLL）在现代存储栈中已广泛使用，论文完全基于 pvsync2 接口测试，缺少与当前主流 I/O 框架的对比。

6. **I/O 干扰模型过于规则**：论文使用的 pulse generator（固定大小、固定 IOPS、固定间隔的脉冲式 I/O）是高度人工化的干扰模式，真实生产环境中的干扰更复杂（多租户、不同大小混合、突发模式等），DPAS 在这些场景下的表现未知。

7. **双队列开销未充分讨论**：DPAS 为每个 CPU 分配两个设备队列（poll + interrupt），在 CPU 数量远多于设备队列时需共享 interrupt 队列。论文承认这可能降低性能，但仅提到"可通过 OS 改进缓解"，未量化影响。

---

## 七、总结

DPAS 提出了一种实用的 SSD I/O 完成方法，核心创新在于用二元睡眠结果对替代 epoch-based 延迟统计来跟踪 I/O 延迟下包络线（PAS），并在此基础上动态切换 polling/hybrid polling/interrupt 三种模式（DPAS）。该方法在三种不同介质的 SSD 上表现稳健，尤其在 CPU 竞争和 I/O 干扰并存的场景下优于所有现有方法。主要局限在于实验平台和内核版本较老、θ 参数仍需按存储介质类型设置、以及在高并发和尾延迟方面仍有改进空间。
