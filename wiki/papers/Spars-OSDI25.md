---
type: paper
name: Spars
full_title: "OS Rendering Service Made Parallel With Out-of-Order Execution and In-Order Commit"
authors: [Yuanpei Wu, Dong Du, Chao Xu, Yubin Xia, Yang Yu, Ming Fu, Binyu Zang, Haibo Chen]
venue: OSDI
year: 2025
tags: [mobile-os, rendering, parallelism, gpu, openharmony]
source_pdf: "[[osdi25-wu-yuanpei.pdf]]"
source_md: "[[osdi25-wu-yuanpei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-17
---

# OS Rendering Service Made Parallel With Out-of-Order Execution and In-Order Commit (OSDI 2025)

> **一句话总结**：Spars 以多 worker 并行执行并按 overlap 关系提交图形任务。42 个 adapted smartphone scenarios 中，Spars-5 平均 frame rate 为 Sequential 的 **1.76×**；Kirin9010 的 2–6 virtual-screen 试验中为 **1.91×**，两者不是同一设备/工作负载结果。

## 问题与动机

智能手机 OS 渲染（render tree + CPU tessellation + Vulkan）占帧时间 **82%** CPU；折叠/三折叠/车载多屏像素与图元激增，厂商被迫降刷新率或像素密度。现有 inter-frame、multi-window 并行粒度粗、负载不均或不适配单窗口多区块 UI。

## 关键观察 / 隐含假设

- **观察 1**：约 **76%** 渲染步骤可做成自包含任务，只要状态预解耦、输出保序。
  - **依赖假设**：dry-run 可提取绝对变换/裁剪而不做真实光栅化。
  - **可能失效场景**：强状态依赖、全局单 canvas 特效占比上升时并行比例下降。
- **观察 2**：render thread 占单核 **80%**，9/12 核空闲（Mate X5 Lifestyle 场景）。
  - **依赖假设**：瓶颈在 CPU 2D 准备而非 GPU raster（2D 场景 <1000 三角形）。
  - **可能失效场景**：重度 GPU shader 或 3D 游戏不在目标范围。
- **假设 1**：保留上层 Skia/Drawing 有状态 API，底层 Spade2D 无状态并行。
  - **证据强度**：强——C3 接口兼容设计明确。

## 核心方法

三阶段：**in-order preparation**（dry-run 生成 self-contained tasks + overlap 元数据）→ **out-of-order execution**（worker 池跑 Spade2D）→ **in-order commit**（commit thread 按 z-order/overlap 提交 Vulkan command）。

双阶段 API：stateful 阶段兼容应用；stateless 阶段可扩展。

## 设计取舍

- **取舍 1**：额外准备与 commit 阶段略增总工作量，换多核扩展。
- **取舍 2**：Vulkan 约束（command buffer 粒度、secondary buffer render pass 一致）限制极端拆分。
- **边界条件**：OpenHarmony 5.0、42 场景、华为 Mate 系列与 12 种一芯多屏配置。

## 实验与结果

**指标、基线与边界**：frame rate、whole-device power、graphics primitives；Spars-5 vs Sequential rendering；42 adapted smartphone scenarios on Mate70/X5/XT 或 Kirin9010 virtual screens（§6）。

- 42 scenarios 中，Spars-3/Spars-5 平均 frame-rate gains 为 **1.38×/1.76×**；Spars-5 使 Sequential CPU frame-rendering time 降 **43.2%**，42 个场景均稳定 120 Hz（§6.3，Fig.11）。
- Kirin9010 的 2–6 virtual 2K screens 中，Spars-3/Spars-5 平均为 **1.34×/1.91×**；6/5 desktops 为 **2.16×/1.94×**（§6.3，Fig.13）。
- Mate XT 同 configured frame rate 的 whole-device power 为 Sequential 的低 **2.7%/3.0%**；120 Hz/8.33 ms random primitives 中 Spars-3/5 为 **1.62×/2.31×**（§6.5–6.6，Fig.15）。

## Claim–Evidence Map

| Claim | Evidence | Metric / baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| 常见 smartphone 场景的 frame rate 提升 | Spars-3/5 1.38×/1.76×；Spars-5 120 Hz in 42 scenarios | Mate70/X5/XT、adapted real-app layouts、3/5 medium-core workers | §6.3，Fig.11 | high |
| 核/clock 配置影响收益但未证明跨 SoC 通用 | Spars-5 medium core 1.76×/1.89× at low/high clocks | scenario average、homogeneous core configurations | §6.3，Fig.12 | high |
| 多虚拟屏试验是独立边界 | 1.34×/1.91%，重配置时 2.16×/1.94× | Kirin9010、2–6 virtual 2K screens；非物理多设备 | §6.3，Fig.13 | high |
| 同帧率 power 和 primitive budget 有明确测试条件 | -2.7%/-3.0%；1.62×/2.31× | Mate XT battery counters 或 120 Hz random primitives；无 batching lower bound | §6.5–6.6，Fig.15 | high |
| 并行机会与瓶颈来自特定设备分析 | 76% potentially parallelizable；80% one core；CPU 82% frame time | Lifestyle/MateX5 或 commercial OS profiling，不泛化所有 UI | §1–2.2 | high |

## Critical Analysis

### 论证链条

产业 trace 证明 CPU 瓶颈与核闲置 → OoO 类比 → 三阶段 pipeline → 真机帧率/功耗，链条清晰。76% 并行比例来自内部剖析，外部复现依赖相同 UI 分布。

### 假设压力测试

120Hz 全场景、复杂动画转场、视频叠加时 commit 压力？与 GPU driver 版本耦合。非华为/OpenHarmony 移植成本未评估。

### 实验可信度

商用机实测说服力强；baseline 为同版本 OH 顺序路径，公平。对比 iOS/Android 仅 related work 层面对照。

### 系统性缺陷

论文未讨论帧延迟 tail、jank 分布；恶意应用巨型 render tree 对 worker 池的 DoS 未讨论。

## 局限与 Future Work

- **局限 1**：聚焦 2D OS GUI，非通用 3D 引擎。
- **Future work 1**：与 D-VSync 等结合在波动负载下的帧预测策略。
- **Future work 2**：跨厂商 Skia/Impeller 后端的可移植验证。

## 相关

- **同会议**：[[OSDI-2025]]
