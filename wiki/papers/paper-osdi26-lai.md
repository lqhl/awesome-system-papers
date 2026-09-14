---
type: paper
name: Janus
full_title: "JANUS: Cross-World, Cooperative Nested Virtualization for Secure Containers"
authors: [Jiangshan Lai, Hang Huang, Quan Xu, Zhen Ren, Wenlong Hou, et al.]
venue: OSDI
year: 2026
tags: [nested-virtualization, secure-containers, memory-virtualization, kvm, pvm]
source_pdf: "[[osdi26-lai.pdf]]"
source_md: "[[osdi26-lai]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-24
---

# 面向安全容器的跨层协作嵌套虚拟化（OSDI 2026）

> **原题**：JANUS: Cross-World, Cooperative Nested Virtualization for Secure Containers

> **一句话总结**：现有嵌套虚拟化在活跃与未触碰内存混合的工作负载上反复同步三层页表；JANUS 让 L1 的 switcher 在 non-root 模式内完成 CPU 世界切换，并由 L0 独占管理直接的 EPT0→2，生产 Flink 部署相对 RunC 的额外开销低于 5%。

## 问题与动机

Kata Containers 通过 microVM 为容器提供硬件隔离，但在云 VM 中运行时会形成 L0 主机、L1 云 VM、L2 安全容器三层嵌套。硬件通常只提供两级地址转换，因此系统必须组合三套页表。CPU 密集型负载的影响较小，内存密集型负载在已有系统中可能出现数量级退化（§1）。

PVM 用软件 switcher 降低 L1-L2 世界切换成本，却需要为进程维护 shadow page table；KVM 的 EPT-on-EPT 让 L2 使用自己的页表，但在 EPT 缺页时需要 L0、L1、L2 多次往返。图 5 表明，单独访问活跃或未触碰物理内存时两种设计各有优势，真实应用的混合访问模式却会同时触发两类同步开销。

## 关键观察 / 隐含假设

- **观察 1：嵌套内存转换的主要成本来自跨层同步，而不是页表遍历本身。** EPT-on-EPT 的新映射需要多次退出和 VMRESUME 模拟；PVM 则在页表频繁变化时持续同步 SPT（图 5）。
  - **依赖假设**：云应用会同时产生新内存映射和高频访问已建立映射的内存。
  - **可能失效场景**：工作集完全预热、使用大页，或工作负载几乎不修改页表时，JANUS 的优势可能缩小。
- **观察 2：CPU 世界切换与内存转换可以拆给不同层负责。** PVM 的 switcher 已证明 L1 内局部切换可行；硬件 EPT 则适合由 L0 统一维护。
  - **证据强度**：强；Table 3 显示 JANUS 每次切换约 2,700 cycles，与 PVM 的 2,681 cycles 接近，远低于 KVM 的 16,002 cycles。
- **假设 1：Intel 硬件特性可用。** VMFUNC 的 EPTP switching、#VE、PML、VMCS Shadowing 是设计依赖，而非可选优化。
  - **证据强度**：强；论文在 Intel Xeon Platinum 8475B、Linux 5.10.134 上实现和评测，未证明 AMD 或缺少这些特性的硬件路径。

## 核心方法

JANUS 直接使用 L2 页表作为第一阶段转换，并由 L0 维护 EPT0→2，将 L2 GPA 映射到 HPA。L1 不再维护中间 EPT 或 shadow page table。L2 页表缺页由 switcher 直接注入 L2 内核；EPT 缺页通过 #VE 送到 L1，L1 遍历 L2 页表后发出一次 JANUS_MAP hypercall，请求 L0 更新 EPT。该路径把传统多次世界切换压缩为一次 L1 处理和一次 L0 更新（§4.3）。

Switcher 位于 L1 的 non-root ring 0，并在 L1、L2 地址空间使用相同虚拟地址。进入 L2 时切换 CR3，再用 VMFUNC 切换到对应的 EPT0→2；退出时反向切换 EPT 和 CR3，整个常见路径不进入 L0（算法 1）。

为了防止可写的 L2 页表覆盖 switcher，JANUS 引入 shadow-root。L1 保留受保护的 shadow PGD，仅允许通过 hypercall 验证 PGD 级更新；PUD、PMD、PTE 等低层更新仍可由 L2 直接完成。GPA disaggregation 将 switcher/shadow-root 与 L2 普通内存分离，并用软件 V-bit 标记合法的 L2 映射。若 L2 通过 VMFUNC 选择错误 EPT，所需 shadow-root 不可访问，故障会被 L1 发现并终止该上下文（§4.2–§4.3）。

JANUS 还扩展内存回收和迁移。L0 用 reverse mapping 根据 L1 GPA 找到 EPT0→2 项并失效；L1 的 invalidate_range 通过 JANUS_UNMAP 通知 L0。迁移时，L2 GPA 的专用区间让 L0 能从 PML 日志识别 L2 脏页，再通过 EPT reverse mapping 标记 L1 脏页，避免写保护每次修改（§4.4）。

## 设计取舍

- **减少同步，增加协作接口**：L0 与 L1 必须共同理解 GPA 布局、映射验证、回收和迁移协议。实现包含 1,662 行 L0 KVM、3,702 行 PVM 和 264 行 L2 内核改动。
- **保留 L2 页表灵活性，保护少数根级状态**：shadow-root 只固定 switcher 所在 PGD 范围，降低了全面 shadow paging 的成本，但 PGD hypercall 成为正确性边界。
- **依赖硬件特性换取近 native 性能**：VMFUNC、#VE 和 PML 缺失或语义不同的平台需要另行设计；论文未提供跨硬件实现。

## 实验与结果

- 在八个内存密集型应用上，8 vCPU 时 Kata-JANUS 相对 Kata-PVM 的多进程平均性能提高 339.7%，相对 Kata-KVM 提高 51.8%；多线程应用相对两者分别提高 37% 和 13.3%（图 11）。
- Redis 吞吐相对 Kata-PVM 和 Kata-KVM 平均提高 9.7% 和 45.1%；Memcached 提高 4.4% 和 48.2%（图 13）。
- 纯世界切换为约 2,700 cycles，接近 PVM 的 2,681 cycles，远低于 KVM 的 16,002 cycles（表 3）。
- 开启脏页跟踪后，Kata-KVM 的内存修改开销平均增加 175.5%；JANUS 使用 PML，保持接近未开启跟踪时的性能（表 5）。
- 生产 Flink 的 17 个查询中，PVM 相对 RunC 对 C++ 和 Java 引擎分别增加约 30% 和 20% 总查询时间；JANUS 的额外开销低于 5%（§5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| JANUS 减少嵌套内存映射的跨层同步 | 单次 EPT fault 只需 L1 处理后调用 L0 更新；表 4 | Intel Xeon 8475B，Linux 5.10，Kata 配置 | 强 |
| JANUS 改善混合内存访问和多进程扩展性 | 图 11、图 12；多进程平均相对 PVM 提高 339.7% | 八个内存密集型基准，最高 8 vCPU | 强 |
| JANUS 可用于生产安全容器 | Flink 17 查询，额外开销低于 5%（§5） | 单一云平台、PVM/L1 技术栈 | 中 |
| 迁移期间无需写保护每次 L2 写入 | PML + GPA 区间识别，表 5 | 已建立低层映射的内存写入微基准 | 中 |

## 批判性分析

### 论证链条

论文的链条在实现层面闭合：混合访问触发两类同步，JANUS 分离 CPU 与内存职责，再用 VMFUNC、shadow-root 和 #VE 维持切换安全，图 11–13 和表 3–5 覆盖了性能路径。核心性能结论主要来自特定 Intel 硬件和 PVM 基础设施，不能直接外推到所有云平台。

### 假设压力测试

GPA disaggregation 让 PML 能区分 L2 写入，但这依赖稳定、非重叠的 GPA 区间。动态内存布局、设备直通、共享内存或更复杂的 NUMA 配置可能增加验证和 reverse mapping 成本。论文没有报告大规模多租户下 EPT0→2 元数据的内存占用，也没有测量高频迁移与回收同时发生时的尾延迟。

### 实验可信度

基线包含标准 Kata-KVM 和 PVM，覆盖微基准、内存密集型程序、Redis、Memcached 以及生产 Flink。消融主要以机制路径和对照系统呈现，未分别隔离 VMFUNC、shadow-root、#VE、GPA disaggregation 的独立成本。报告以平均吞吐和执行时间为主，对 P99、隔离错误恢复和 hypercall 拒绝路径覆盖有限。

### 系统性缺陷

L0/L1 协议扩大了 hypervisor 的可信计算基和升级耦合。映射验证、失效传播和迁移状态必须保持一致，故障恢复与调试成本可能高于单层 KVM。论文讨论了边界与长度验证，但未给出恶意 hypercall 压力下的 CPU 消耗、拒绝服务防护或跨 vCPU 并发一致性实验。

## 局限与后续工作

- **局限 1**：当前 L2 kernel/user 隔离依赖 switcher 中的 CR3 切换；频繁上下文切换仍需经过 switcher。
- **局限 2**：实现依赖 Intel VMFUNC、#VE、PML 和 VMCS Shadowing，跨 CPU 厂商的可移植性未验证。
- **后续工作 1**：论文计划使用 EPT 在 L2 kernel/user 间隔离，使上下文切换不再经过 switcher；可用不同进程数、内存映射频率和 P99 延迟验证收益。
- **后续工作 2**：评估 HLAT 是否能移除 shadow-root，并在回收、迁移、恶意 hypercall 并发时测量元数据内存、尾延迟和恢复正确性。

## 相关

- **相关概念**：[[Nested Virtualization]]、[[EPT]]、[[PML]]、[[VMFUNC]]
- **同类系统**：[[PVM]]、[[KVM]]、[[Kata Containers]]
- **同会议**：[[OSDI-2026]]
- **源材料**：[[osdi26-lai.pdf]]、[[osdi26-lai]]
