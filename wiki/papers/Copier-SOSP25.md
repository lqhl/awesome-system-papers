---
type: paper
name: Copier
full_title: "How to Copy Memory? Coordinated Asynchronous Copy as a First-Class OS Service"
authors: [Jingkai He, Yunpeng Dong, Dong Du, Mo Zou, Zhitai Yu, et al.]
venue: SOSP
year: 2025
tags: [memory-copy, async-io, os-service, zero-copy, simd]
source_pdf: "[[3731569.3764800.pdf]]"
source_md: "[[3731569.3764800]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# How to Copy Memory? Coordinated Asynchronous Copy as a First-Class OS Service (SOSP 2025)

> **一句话总结**：memcpy 在应用/OS 中占高达 66% cycles，但 zero-copy 有对齐/TOCTOU/尺寸阈值限制；Copier 把 copy 提升为一等 OS 服务，利用 Copy-Use 窗口异步重叠拷贝与计算，统一调度 AVX+DMA，Redis 延迟 **1.8×** 优于基线、**1.6×** 优于 zIO。

## 问题与动机

[[Memory-Copy]] 贯穿 syscall、[[IPC]]、网络栈、存储，是系统级「性能税」（Google DC 4–5% cycles）。硬件 SIMD 用户态可用但内核因寄存器保存贵；DMA 内核可用但应用难用。zero-copy（sendfile、vmsplice）有 ≥10–16KB 阈值、页对齐、TOCTOU、单副本限制。论文主张：**copy 应像文件系统一样成为 OS 服务**，全局视图 + 异构拷贝单元 + 异步语义。

## 关键观察 / 隐含假设

- **观察 1**：Copy-Use 窗口（拷贝完成到首次使用数据）常为拷贝耗时的 **2–10×**（Protobuf/recv 等），可隐藏延迟。
  - **依赖假设**：应用按块使用数据、存在可插入 `csync` 的同步点。
  - **可能失效场景**：立即消费首字节的 tight loop 几乎无窗口。
- **观察 2**：全局服务可 **absorb** 跨特权级冗余拷贝（syscall trap 作 barrier 指示依赖）。
  - **依赖假设**：依赖追踪开销低于收益；开发者愿用 `amemcpy`/`csync` 或工具链改写。
  - **可能失效场景**：依赖图爆炸的复杂 pipeline。
- **假设 1**：piggyback DMA 到 AVX 任务并行可兼顾小拷贝（融合多任务一轮 piggyback）。
  - **证据强度**：中；Table 1 对比 zIO/Fastmove 全面，但 ≥0.5KB 起收益需看 microbench。

## 核心方法

**队列抽象**：细粒度 segment 状态更新 + 乱序执行 + `csync` 保证与 sync copy 语义等价（形式验证）。

**Piggyback dispatcher**：AVX 与 DMA 并行；跨队列 barrier 用系统事件追踪顺序/数据依赖。

**Layered copy absorption** + lazy copy；**cgroup** 以拷贝长度为资源单位公平调度；proactive fault handling。

**Copier-Linux** 优化 Redis、Protobuf、send/recv、Binder、CoW fault；集成 HarmonyOS 5.0（视频解码延迟 **-10%**）。

## 设计取舍

- **取舍 1**：异步 API vs 编程负担 → 提供 toolchain，但仍需移植。
- **取舍 2**：OS 全局调度 vs 隔离 → cgroup 扩展，多客户端争用 Copier 队列。
- **边界条件**：极小拷贝提交任务开销可能抵消收益（论文用 queue 融合缓解）。

## 实验与结果

- Redis：**1.8×** 延迟 vs baseline；**1.6×** vs [[zIO]]
- HarmonyOS：视频解码延迟最高 **-10%**；多应用 copy 占 **3–49%** cycles
- send/recv、Protobuf、Binder IPC、CoW 等多场景提升
- 支持 cross-privilege/cross-address-space，无页对齐硬性要求（Table 1）

## Critical Analysis

### 论证链条

Copy-Use 测量 → 异步 OS 服务 + 硬件统一调度 → 多应用加速，链条清晰。从 benchmark 到「全 DC 4–5% cycles 回收」的跳步需大规模部署数据；与 zero-copy 共存边界（何时仍应 remap）论文有 Table 1 但未给决策自动化规则。

### 假设压力测试

- **安全**：异步拷贝与 TOCTOU——`csync` 前用户是否可观察 buffer 状态需严格模型；论文强调等价性验证。
- **多核**：Copier 队列本身可能成为新争用点；尾延迟 under overload 未详述。
- **移植**：HarmonyOS 与 Linux 双平台有益，但通用 app 自动改写覆盖率未知。

### 实验可信度

Redis/zIO 对比强；Google cycles 引用为动机非本工作实测。缺与 io_uring 等现代异步 IO 栈的组合评测。

### 系统性缺陷

服务故障/降级路径、与 [[RDMA]]/[[DPDK]] zero-copy 路径集成论文未讨论；运维复杂度（debug 异步 copy 顺序 bug）高于 sync memcpy。

## 局限与 Future Work

- **局限 1**：依赖 Copy-Use 窗口，immediate-use 路径收益有限。
- **局限 2**：工具链成熟度决定 adoption。
- **Future work 1**：生产 DC 随机采样 Copy-Use 分布，量化 Copier 全局 ROI。
- **Future work 2**：与 io_uring linked requests 对比公平性与 CPU 占用。

## 相关

- **相关概念**：[[Memory-Copy]]、[[Zero-Copy]]、[[IPC]]、[[DMA]]、[[SIMD]]
- **同类系统**：[[zIO]]、Fastmove、Linux sendfile、L4 IPC
- **同会议**：[[SOSP-2025]]
