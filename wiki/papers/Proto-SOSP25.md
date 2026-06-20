---
type: paper
name: Proto
full_title: "Proto: A Guided Journey through Modern OS Construction"
authors: [Wonkyo Choe, Rongxiang Wang, Afsara Benazir, Felix Xiaozhu Lin]
venue: SOSP
year: 2025
tags: [os-education, instructional-os, arm, unikernel]
source_pdf: "[[3731569.3764811.pdf]]"
source_md: "[[3731569.3764811]]"
---

# Proto: A Guided Journey through Modern OS Construction (SOSP 2025)

> **一句话总结**：教学 OS 长期偏终端小程序难激发动机；Proto 用 5 个 incremental prototype（每阶段为 DOOM/视频/音乐等目标应用引入 per-app 地址 space、USB、DMA、multicore 等），内核核心 **<10K SLoC**，在廉价 ARMv8 上 DOOM **~60 FPS**、视频 **~26 FPS**，功耗 **<4W** 级。

## 问题与动机

本科 [[Operating-Systems]] 课程兴趣下滑（顶尖校 20/30 不再必修），部分因 instructional OS（如 [[xv6]]）难连接学生日常体验的应用。历史 UNIX/TeX/WWW 源于「为自己做系统」的动机，现教学常止于 shell/printf。Proto 回应：**P1 吸引人应用**、**P2 真机可演示**、**P3 增量原型**、**P4 最小可行实现**（每机制服务具体 app）。

## 关键观察 / 隐含假设

- **观察 1**：以 framebuffer/USB/audio 为先类外设，可早期支撑游戏与媒体，比「先完成完整 POSIX」更能维持 17 周/150h 内进度。
  - **依赖假设**：学生具备 CSO + AI 工具辅助；ARMv8 廉价板足够。
  - **可能失效场景**：无硬件供应或评分只认 x86/QEMU 时 P2 受阻。
- **观察 2**：增量 self-contained prototype 比 big-bang 更易 baseline 与 debug（Ford 747/SpaceX 类比）。
  - **依赖假设**：每阶段作业可独立验收运行。
  - **可能失效场景**：后期 prototype 依赖前期代码质量，差生可能卡在 P2。
- **假设 1**：<10K SLoC 内核仍可涵盖现代概念（per-app AS、thread、FS、USB、DMA、multicore、WM）。
  - **证据强度**：中强；功能列表与 Figure 1 演示充分。

## 核心方法

五个 prototype（表 1）：从 3D 动画 → 游戏 → 视频/音乐 → 网络/区块链等，逐步引入机制。

特性：per-app address spaces、commodity FS、USB、DMA、multicore、self-hosted debug、window manager。

代码：https://github.com/fxlin/uva-os-main 。

## 设计取舍

- **取舍 1**：娱乐/媒体 app 动机 vs 传统 syscall/调度深度——部分经典专题可能变浅。
- **取舍 2**：ARM 真机优先 vs x86 教材生态。
- **边界条件**：多数 microbench 与 xv6 同级 overhead，非全面超越 Linux。

## 实验与结果

- 内核核心 **<10K SLoC**（与 xv6 同级量级）
- DOOM **~60 FPS**；视频 **~26 FPS**（与 Linux/FreeBSD 同硬件同级）
- 手持设备 **<4W**，数小时电池
- 用户研究：多数学生认为 P1–P4 提升学习热情

## Critical Analysis

### 论证链条

教育痛点 → 原则驱动分解 → 可演示现代 OS，论文类型偏系统教育非生产 OS。到「恢复 OS 必修吸引力」的因果需长期 enrollment 数据——user study 是短期调查。

### 假设压力测试

- **公平性**：有游戏/多媒体背景学生可能优势不均。
- **安全**：教学 WM/USB 栈安全深度 vs 速度 trade-off。
- **维护**：5 prototype 分支长期与主线内核同步成本。

### 实验可信度

UVA 课程用户研究样本有限；性能对比 Linux/FreeBSD 同 app 有说服力。缺与其他 instructional OS（OS161、Pintos）学习成效对照实验。

### 系统性缺陷

非研究 OS；安全性、虚拟化、容器等现代云主题覆盖有限。论文未讨论学术诚信（AI Copilot 写 OS 作业）边界。

## 局限与 Future Work

- **局限 1**：150h 预算限制机制深度。
- **局限 2**：ARM 为主，x86 实验室需额外移植。
- **Future work 1**：多校部署前后测标准 OS 概念掌握度与选修率。
- **Future work 2**：将 [[Proto]] P5 网络栈与 [[Dandelion]] 云原生模块对比教学路径。

## 相关

- **相关概念**：[[Operating-Systems]]、[[xv6]]、[[Unikernel]]、[[DMA]]、[[Multicore]]
- **同类系统**：xv6、OS161、Pintos、teaching unikernels
- **同会议**：[[SOSP-2025]]