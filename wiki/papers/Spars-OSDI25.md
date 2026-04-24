---
type: paper
name: Spars
full_title: "OS Rendering Service Made Parallel with Out-of-Order Execution and In-Order Commit"
authors: [Yuanpei Wu, Dong Du, Chao Xu, Yubin Xia, Yang Yu, et al.]
venue: OSDI
year: 2025
tags: [os, rendering, parallelism, mobile, gpu]
source_pdf: "[[osdi25-wu-yuanpei.pdf]]"
source_md: "[[osdi25-wu-yuanpei]]"
---

# OS Rendering Service Made Parallel with Out-of-Order Execution and In-Order Commit (OSDI 2025)

> **一句话总结**：Spars 把 CPU 乱序执行 + 顺序提交的思想搬到智能终端 OS 的 2D 渲染服务里，用「in-order 预解状态 → out-of-order 执行渲染任务 → in-order commit 保证绘制顺序」的三段式流水，在华为 Mate 70/X5/XT 等单屏、双折、三折手机及一芯多屏配置下平均提升帧率 **1.76×–1.91×**，同帧率下降功耗 3% 或让图元数量扩大 **2.31×**。

## 问题

iOS/Android/OpenHarmony 的 OS 渲染服务是顺序执行模型：深度优先遍历 render tree，2D 引擎把 draw command 翻译成 GPU object，然后 GPU 光栅化。折叠屏 / 多屏场景下要渲染的像素量比单屏多 70–117%，但芯片 SoC 没变，实测 render 线程独占单核 80% 利用率，其余 9/12 核空闲，导致厂商要么降像素密度要么降帧率。

顺序模型难以并行化的三大依赖：(C1) **状态依赖**——render tree 只存相对信息，必须深度优先才能累出绝对状态；(C2) **绘制顺序依赖**——重叠图元必须严格 back-to-front；(C3) **接口依赖**——2D 引擎对外暴露的是有状态 API (Skia Canvas)，还依赖 state-based batching 等优化。已有 inter-frame 并行（受最慢阶段瓶颈）和 multi-window 并行（粒度粗、负载不均）都不能细粒度扩展。

## 核心方法

关键洞察：76% 的渲染过程可被解耦成 self-contained 任务，核心渲染逻辑本身没有状态依赖。Spars 借 CPU 乱序执行 + 顺序提交范式：

- **In-order preparation（主线程）**：做一次 dry-run 深度遍历 render tree，计算每个节点的绝对变换/裁剪信息 $A_i$ 而不触发真正 2D 渲染，产出 self-contained 任务投入 SPMC 池；同时记录任务间的 AABB 重叠关系供 commit 阶段使用。
- **Out-of-order execution（多个 worker 线程）**：worker 从池里取任务，调用新设计的 **Spade2D** 无状态 2D 引擎把图元翻译成 mesh/texture/pipeline。Spade2D 解耦了 state layer (保留兼容性) 和 stateless drawing layer (纯并行)，并保留 command batching 这类状态优化。
- **In-order commit（commit 线程）**：从 MPSC 池读取完成任务，按 AABB 重叠关系决定是否能提交，未重叠就不用等前驱。Vulkan 等现代无状态 GPU API 使得并行录制命令缓冲成为可能，但 Spars 仔细处理了 secondary command buffer 与 render pass 的约束。

## 关键结果

- Spars-5 配置在 42 个场景、Mate 70/X5/XT 及 12 种一芯多屏配置下平均帧率提升 **1.76×–1.91×**，重载多窗/画中画场景最高 **2.07×**
- 单芯六屏 2K 配置下帧率提升 **2.16×**
- 同帧率下整机功耗下降 **3.0%**；同帧率下图元预算提升 **2.31×**
- 最高利用率单核从 80% 降到 45%（Spars-5）甚至 37%（异构核）
- 额外内存开销 < 50 MB，总 overhead（任务封装/分发/收集）< 2%

## 相关

- **相关概念**：[[Out-of-Order-Execution]]、[[Tomasulo]]（CPU 架构类比）
- **同类系统**：Skia Graphite、D-VSync、iOS CA、Android HWUI
- **同会议**：[[OSDI-2025]]
