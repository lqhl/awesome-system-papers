---
type: paper
name: JANUS
full_title: "JANUS: Cross-World, Cooperative Nested Virtualization for Secure Containers"
authors: [Jiangshan Lai, Hang Huang, Quan Xu, Zhen Ren, Wenlong Hou, et al.]
venue: OSDI
year: 2026
tags: [nested-virtualization, secure-container, memory-virtualization, cloud]
source_pdf: "[[osdi26-lai.pdf]]"
source_md: "[[osdi26-lai]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# JANUS：面向安全容器的跨世界协作式嵌套虚拟化（OSDI 2026）

> **原题**：JANUS: Cross-World, Cooperative Nested Virtualization for Secure Containers

JANUS 把嵌套虚拟化的 CPU 切换留给 L1 客体，把二级地址转换交给 L0 主机，从而在不牺牲云端隔离边界的前提下，让运行于云虚拟机内的安全容器接近原生容器性能。

## 问题与动机

云上安全容器通常把每个容器放入轻量虚拟机；当用户本身租用的是云虚拟机时，这种结构形成 L0 主机、L1 云虚拟机和 L2 容器虚拟机三层。传统 KVM 嵌套虚拟化将 L2 的 CPU 事件交给 L0 处理，并通过多级 shadow EPT 同步地址映射，导致频繁 world switch 和高昂缺页成本。

PVM 等半虚拟化方案能缩短 CPU world switch，却仍让 L1 同时承担 CPU 切换和内存虚拟化。对于 Redis、Memcached、Flink 等内存密集工作负载，L2 页表变化与内存回收会迅速成为瓶颈。因此，论文要解决的不是单一快路径，而是如何跨 L0/L1 信任域重新划分嵌套虚拟化职责。

## 关键观察 / 隐含假设

### 关键观察

- CPU world switch 和嵌套内存虚拟化不必由同一层 hypervisor 管理。前者依赖 L1 中的局部执行状态，后者需要 L0 掌握真实机器内存，两者天然适合分离。
- 传统嵌套虚拟化的三阶段地址转换和 shadow EPT 同步，是多进程、频繁映射工作负载的主要扩展性障碍；直接建立 EPT0→2 可以消除中间层同步。
- Intel VMFUNC、虚拟化异常（#VE）和 Page Modification Logging（PML）能够分别覆盖无陷阱 EPT 切换、客体内缺页处理和硬件脏页跟踪，从而把多数高频路径留在 L1/L2。

### 隐含假设

- L0 主机与 L1 中的 JANUS/PVM 组件可信，威胁主要来自不可信 L2 安全容器；JANUS 不试图抵御云主机或 L1 管理层被攻陷。
- 平台提供 VMFUNC、#VE、PML 等 Intel 硬件能力，且云环境允许对 L1/L2 内核做半虚拟化修改。
- 生产工作负载的性能损失主要来自虚拟化控制路径与地址转换，而不是设备仿真、网络或存储后端。

## 核心方法

### 跨世界职责分离

JANUS 让 L1 的轻量 switcher 直接执行 L1↔L2 CPU world switch，避免常规 CPU 事件退出到 L0。与此同时，L0 独占管理从 L2 GPA 到机器地址的 EPT0→2，使物理内存分配、回收、隔离和迁移仍处于云主机控制之下。

### 无陷阱的 EPTP 切换

L1 和 L2 分别使用 EPT0→1 与 EPT0→2。进入或退出 L2 时，switcher 通过 VMFUNC 切换 EPTP，不触发 VM exit。受保护的 shadow-root PGD 固定 switcher 所需顶层映射，而低层页表仍可由 L1 正常维护，兼顾切换安全与客体灵活性。

### 受约束的直接映射

JANUS 对 GPA 空间做 disaggregation，将 L1 特权区、switcher 区与 L2 可用区分离。L0 通过 V-bit 标记合法 L2 映射，阻止 L2 借 EPT0→2 访问 L1 或 switcher 的敏感内存。

### 客体内缺页与生命周期管理

EPT 缺页以 #VE 注入 L1；L1 遍历 L2 客体页表后，只通过一次轻量 hypercall 请求 L0 填充 EPT0→2。内存回收仍由 L0 发起，迁移时则利用 EPT0→2 上的 PML 直接记录脏页，避免传统嵌套脏页跟踪的多层同步。

## 设计取舍

- JANUS 用 L1/L2 内核修改换取高频路径的低开销；它不是透明替换，部署门槛高于未经修改的 KVM 客体。
- EPT0→2 提高了性能，也扩大了 L0 与 L1 协议的安全关键面，因此论文加入 GPA 分区、V-bit 检查和受保护 switcher，而不是让 L1 任意管理直接映射。
- 设计紧密依赖现有 Intel 扩展，避免引入新硬件，但也限制了跨架构可移植性。
- L0 保留回收与迁移控制权，牺牲部分 L1 自治性，以满足公有云的资源超售和运维要求。

## 实验与结果

- 在 8 vCPU 的多进程内存密集 benchmark 中，JANUS 吞吐量相比 PVM 提高 339.7%，相比 KVM 提高 51.8%；多线程版本分别提高 37% 和 13.3%，说明主要收益来自进程地址空间与映射操作，而非纯计算路径（§7）。
- Redis 请求吞吐量相比 PVM 提高 9.7%、相比 KVM 提高 45.1%；Memcached 请求吞吐量分别提高 4.4% 和 48.2%，表明直接 EPT0→2 对真实内存服务有效，但相对已有 PVM 的增益明显较小。
- 真实应用集合中，JANUS 平均性能相比 PVM 提高 144%，相比 KVM 提高 28.6%；论文摘要未给出各应用统一的延迟或吞吐指标，平均值应结合逐项结果解读。
- 在生产 PaaS 的 17 个 Flink 查询上，PVM 相比 RunC 使 C++ 与 Java 总查询时间分别增加约 30% 和 20%，JANUS 的额外开销控制在 5% 以内；该结果直接覆盖论文声称的生产部署场景。
- L1↔L2 world switch 的单次成本为 2700 cycles，与 PVM 的 2681 cycles 接近，远低于 KVM 的 16002 cycles，说明职责分离没有破坏 PVM 的 CPU 快路径。
- 启用迁移脏页跟踪后，KVM 的内存修改开销增加 175.5%，JANUS 使用 PML 后与未跟踪配置近似；证据支持 PML 路径，但论文没有报告跨机迁移总停机时间与网络瓶颈。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| 跨层职责分离可同时降低 CPU 与内存虚拟化成本 | L1 switcher 管 CPU，L0 管 EPT0→2 | world switch 为 2700 cycles；真实应用平均优于 PVM 144% | 依赖半虚拟化内核与 Intel VMFUNC/#VE |
| 直接 EPT0→2 对多地址空间工作负载尤其有效 | 消除中间 EPT 与 shadow 同步 | 8 vCPU 多进程 benchmark 相比 PVM 提高 339.7% | 合成 benchmark 的映射强度可能高于一般服务 |
| 设计满足生产安全容器的性能需求 | GPA 隔离、V-bit、受保护 switcher | 17 个 Flink 查询相对 RunC 开销少于 5% | 单一生产平台，未覆盖多租户攻击与故障注入 |
| 硬件 PML 保留云迁移能力 | 在 EPT0→2 上直接记录脏页 | 避免 KVM 脏页跟踪的 175.5% 修改开销 | 未给出端到端迁移完成时间 |

## 批判性分析

### 论证链条

论文从生产 Flink 的嵌套虚拟化损失出发，将性能问题拆成 CPU world switch 与内存映射两条路径，再证明两者可由不同特权层协作完成。机制微基准、内存 benchmark、缓存服务和生产查询构成从局部成本到端到端收益的完整链条，其中多进程与 PML 实验最能直接对应设计的新颖部分。

### 假设压力测试

若平台缺少 VMFUNC、#VE 或 PML，JANUS 的三个关键快路径都需要替代机制，收益与复杂度可能完全改变。若 L1 管理组件进入威胁模型，固定 shadow-root 和 GPA 分区不足以保证安全；论文的“secure containers”更准确地说是保持既有云信任边界，而不是减少可信计算基。

### 实验可信度

实验覆盖微基准、Redis/Memcached、应用集合和生产 Flink，且同时比较 KVM、PVM 与 RunC，基线层次合理。弱点是平均提升掩盖工作负载差异，生产证据来自单一平台；端到端 live migration、安全攻击、内存压力下回收抖动和多租户公平性缺少量化结果。

### 系统性缺陷

JANUS 把原本封装在单一 hypervisor 中的内存协议拆散到 L0、L1 和修改后的 L2 内核，增加了版本兼容、故障定位与安全审计难度。其性能建立在架构专用硬件与半虚拟化 ABI 上，因此更像面向受控云栈的高性能方案，而非可直接推广到任意嵌套虚拟化环境的通用抽象。

## 局限与后续工作

- 在 AMD、Arm 或缺少 VMFUNC/#VE/PML 的 Intel 代际上验证可移植实现与性能边界。
- 量化恶意 L2 对 #VE、hypercall、映射建立和回收路径的拒绝服务风险，并进行系统化安全评估。
- 补充多租户内存超售、持续回收和端到端 live migration 的吞吐、停机时间与尾延迟。
- 评估 L1/L2 内核升级、Kata runtime 集成及 ABI 演化带来的长期维护成本。

## 相关

- [[PVM]]
- [[KVM]]
- [[Nested-Virtualization]]
- [[Secure-Containers]]
