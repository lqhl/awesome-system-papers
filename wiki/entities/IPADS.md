---
type: entity
kind: org
aliases: [IPADS, "SJTU IPADS", "Institute of Parallel and Distributed Systems", "上海交通大学并行与分布式系统研究所", "上海交大 IPADS"]
status: active
last_updated: 2026-08-20
tags: [operating-systems, distributed-systems, storage, architecture, ai-infra]
---

# SJTU IPADS

> 上海交通大学并行与分布式系统研究所（Institute of Parallel and Distributed Systems，IPADS）是覆盖操作系统、分布式与数据库系统、体系结构和人工智能系统的研究组织；本 wiki 中可见的共同方法是围绕新介质、新互连和新工作负载重写系统抽象。

## 是什么

[IPADS 官方研究说明](https://ipads.se.sjtu.edu.cn/)把研究范围定义为操作系统、分布式系统和数据库系统，并延伸到体系结构、语言与编译器及人工智能的跨层协同设计。它不是单一项目组；脱氧核糖核酸（deoxyribonucleic acid，DNA）存储、图形处理器（graphics processing unit，GPU）容错、Compute Express Link（CXL）操作系统和智能体技能运行时之间没有一个统一工作负载，组织页的作用是追踪方法和研究路线，而不是把不同论文合并成同一系统。

本仓库当前有两类证据。[[LiqSD-FAST25]]、[[PhoenixOS-SOSP25]] 和 [[SkVM-SOSP26]] 已有全文页，可支持机制和实验判断；[[He-GPUKernelFusion-SOSP26]]、[[ProbeFS-SOSP26]] 与 [[StarfishOS-SOSP26]] 截至各自页面复核日期只有官方题名和接收信息，只能说明研究方向，不能据此补写算法或性能。

## 关键观察 / 隐含假设

- **观察：新硬件的粒度错配会迫使系统重做映射层。** [[LiqSD-FAST25]] 面对 DNA 写、读和擦除粒度相差多个数量级，用两级地址转换与延迟失效维持块接口；[[StarfishOS-SOSP26]] 的题名则表明 CXL 共享内存环境需要重新切分单系统映像的状态。二者共同指向“保留旧接口、重做下层状态组织”的路线，但 StarfishOS 目前没有全文证据。
- **观察：成熟主机处理器抽象可以迁移到 GPU，但必须补齐硬件缺失的可观测性。** [[PhoenixOS-SOSP25]] 用软件推测和二进制验证补上 GPU 缺少脏页位、存在位的问题，再实现并发检查点与恢复；这不是直接复制主机处理器协议，而是先构造等价状态信号。
- **观察：智能体技能的可移植性需要显式目标能力。** [[SkVM-SOSP26]] 发现原始技能在一部分任务上反而降分，于是把模型、智能体框架和执行环境的能力差异编译成目标特定版本。该工作把 IPADS 的系统兼容问题从硬件接口扩展到智能体运行时。
- **观察：研究路线同时覆盖纵向协同与跨领域介质。** DNA 文件系统、GPU 内核融合、CXL 微内核和技能虚拟机共享的是系统设计方法，不共享指标或基线；组织页不能把各论文的局部加速数字合成“IPADS 整体性能”。
- **证据边界：接收信息不能替代全文。** [[He-GPUKernelFusion-SOSP26]]、[[ProbeFS-SOSP26]] 和 [[StarfishOS-SOSP26]] 当前只支持题名级分类。待公开全文后，应重建对应论文页，再更新本页观察与时间线。

## 演进时间线

- 2025 FAST：[[LiqSD-FAST25]] — 以两级地址转换和延迟失效把 DNA 介质包装成块设备，同时暴露当前分钟级绝对延迟的现实边界。
- 2025 SOSP：[[PhoenixOS-SOSP25]] — 用推测—验证机制在 GPU 上软件实现并发检查点、写时复制和按需恢复。
- 2026 SOSP：[[SkVM-SOSP26]] — 把智能体技能视为待编译程序，针对模型、框架和环境能力生成目标版本。
- 2026 SOSP：[[He-GPUKernelFusion-SOSP26]] — 官方题名指向动态 GPU 工作负载下的跨流式多处理器（streaming multiprocessor，SM）内核融合；当前只有元数据。
- 2026 SOSP：[[ProbeFS-SOSP26]] — 从 LiqSD 的 DNA 块接口推进到层级文件系统；当前只有元数据。
- 2026 SOSP：[[StarfishOS-SOSP26]] — 探索 CXL 共享内存机器上的状态分区微内核；当前只有元数据。

## 相关系统

- [[LiqSD-FAST25|LiqSD]]、[[PhoenixOS-SOSP25|PhoenixOS]]、[[SkVM-SOSP26|SkVM]]、[[ProbeFS-SOSP26|ProbeFS]]、[[StarfishOS-SOSP26|StarfishOS]]

## 相关概念

- [[NVMe]]、[[CXL]]、[[LLM]]、[[Long-Horizon-Agents]]、[[Garbage-Collection]]、[[eBPF]]

## 相关论文

- [[LiqSD-FAST25]] — DNA 存储地址转换与块接口。
- [[PhoenixOS-SOSP25]] — GPU 并发检查点和恢复。
- [[SkVM-SOSP26]] — 跨模型、智能体框架和环境的技能运行时。
- [[He-GPUKernelFusion-SOSP26]] — 动态 GPU 工作负载下的内核融合，当前为仅元数据页面。
- [[ProbeFS-SOSP26]] — DNA 层级文件系统，当前为仅元数据页面。
- [[StarfishOS-SOSP26]] — CXL 单系统映像与状态分区微内核，当前为仅元数据页面。
