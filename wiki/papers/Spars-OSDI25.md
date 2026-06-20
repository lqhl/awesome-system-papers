---
type: paper
name: Spars
full_title: "OS Rendering Service Made Parallel With Out-of-Order Execution and In-Order Commit"
authors: [Yuanpei Wu, Dong Du, Chao Xu, Yubin Xia, Yang Yu, et al.]
venue: OSDI
year: 2025
tags: [mobile-os, rendering, parallelism, gpu, openharmony]
source_pdf: "[[osdi25-wu-yuanpei.pdf]]"
source_md: "[[osdi25-wu-yuanpei]]"
---

# OS Rendering Service Made Parallel With Out-of-Order Execution and In-Order Commit (OSDI 2025)

> **一句话总结**：折叠屏/多屏使像素量增 70–117% 但 OS 渲染仍单线程占 80% 单核，其余核闲置；Spars 借鉴 OoO+in-order commit，in-order 准备自包含任务 → 多核并行执行 → 按重叠关系 in-order 提交 GPU，Mate 70/X5/XT 上帧率 **1.76–1.91×**，功耗 **-3%** 或图元预算 **2.31×**。

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

- 相对 OpenHarmony 顺序渲染：平均帧率 **1.76–1.91×**。
- 同帧率下功耗 **-3.0%** 或图元数 **2.31×**。
- 表 1：相对 inter-frame/multi-window/D-VSync 在 constant heavy load 上唯一 high frame rate。

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