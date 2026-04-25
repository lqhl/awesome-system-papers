---
type: paper
name: DPAS
full_title: "DPAS: A Prompt, Accurate and Safe I/O Completion Method for SSDs"
authors: [Dongjoo Seo, Jihyeon Jung, Yeohwan Yoon, Ping-Xiang Chen, Yongsoo Joo, et al.]
venue: FAST
year: 2026
tags: [ssd, io-completion, hybrid-polling, kernel, latency]
source_pdf: "[[fast2026-seo.pdf]]"
source_md: "[[fast2026-seo]]"
---

# DPAS: A Prompt, Accurate and Safe I/O Completion Method for SSDs (FAST 2026)

> **一句话总结**：用「最近两次 I/O 的 under/over-sleep 二元结果」实时调整 hybrid polling 的睡眠时长（PAS），并在 polling/interrupt/PAS 之间动态切换（DPAS），相比 Linux hybrid polling 在 4 KB 随机读上 CPU 占用降 21 个百分点，YCSB 在 3D XPoint SSD 提速 9%、TLC NAND SSD 提速 5%。

## 问题

现代 SSD 延迟极低，传统 [[NVMe]] interrupt 的 context switch、cache pollution、CPU 状态切换开销显著；纯 polling 又在 CPU 争用下严重劣化。Linux hybrid polling（LHP）先 sleep 一段再 poll，理想是醒来正好赶上 I/O 完成，但实际依赖 epoch 内的均值/最小值统计估计 sleep duration，存在三大缺陷：

1. **Promptness**：epoch-based 更新无法跟踪突发 latency 变化；
2. **Accuracy**：固定 50% 衰减系数过于保守，稳定时浪费 CPU；
3. **Safety**：高 variance 下 50% 安全余量仍不够，频繁 oversleep。

更糟的是 LHP/HyPI/EHP 都基于实测 I/O 时长，无法区分「设备真慢」和「自己睡过头」，造成 latency shelving——把自己的预测错误当成设备变慢，sleep 越调越大。

## 核心方法

**PAS（Prompt, Accurate, Safe）I/O latency tracking**：
- 用 modified poll 函数获取每次 I/O 的二元 sleep result：UNDER（醒太早）/ OVER（睡过头）。
- 根据「最近两次」结果对 (sr_pnlt, sr_last) 更新 `adjust` 系数：(UNDER, UNDER) → 加 UP；(OVER, OVER) → 减 DN；穿越 latency 包络（UNDER↔OVER）则 reset adjust = 1 并施加单步反向调整。
- 用 PAS-Sim 在真实 trace 上扫参，得 (UP, DN) = (0.01, 0.1) 为 device-agnostic baseline。
- 引入 dynamic sensitivity：HEATUP/COOLDN 根据 sleep result 一致性自适应放缩 (UP, DN)。
- per-core mode 解决并发 I/O 的统计变量污染。

**DPAS（Dynamic mode switching）**：
- 在 classic polling、PAS normal、PAS overloaded、interrupt 四模式间切换。
- QD = 1 时切 classic polling（独占 CPU 最快）；检测到 timer failure（sleep duration 塌缩到 0，PAS 退化为 busy-wait）则切 PAS overloaded；QD 超阈值 θ 切 interrupt。
- 用 N_PAS=100、N_CP=1000、N_INT=10000 个 I/O 作为 hysteresis window，避免抖动。

## 关键结果

- 4 KB 随机读 CPU 占用比 LHP 低 21 个百分点。
- YCSB 在 3D XPoint SSD 比 interrupt 提速 9%；TLC NAND SSD 提速 5%（同时存在 CPU 争用 + I/O 干扰）。
- 在 Optane SSD 上 classic polling 134 KIOPS vs LHP 129 KIOPS（4% 退化）说明 hybrid polling 的 timer 仍有不可忽略的 cache eviction 代价，DPAS 通过模式切换规避。
- 跨三类 SSD（3D XPoint / Optane / TLC NAND）+ 两类 CPU 验证。

## 相关

- **相关概念**：[[NVMe]]、Hybrid Polling、I/O Completion、Context Switch、CPU Contention
- **同类工作**：LHP（Linux hybrid polling）、HyPI、EHP、LinnOS、Select-ISR、CINT
- **同会议**：[[FAST-2026]]
