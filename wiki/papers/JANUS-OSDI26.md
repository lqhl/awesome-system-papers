---
type: paper
name: JANUS
full_title: "JANUS: Cross-World, Cooperative Nested Virtualization for Secure Containers"
authors: [Jiangshan Lai, Hang Huang, Quan Xu, Zhen Ren, Wenlong Hou, Wei Guo, Jia Rao, Hui Lu, Weidong Han, Jiesheng Wu, Jiang Liu, Naixuan Guan, Yibin Shen, Feng Yu, Xu Wang, Shiqiang Zhang, Zhiheng Tao, Yisheng Xie, Song Wu, Hai Jin]
venue: OSDI
year: 2026
tags: [nested-virtualization, secure-container, memory-virtualization, live-migration, cloud]
source_pdf: "[[osdi26-lai.pdf]]"
source_md: "[[osdi26-lai]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向安全容器的跨层协作嵌套虚拟化（OSDI 2026）

> **原题**：JANUS: Cross-World, Cooperative Nested Virtualization for Secure Containers

> **一句话总结**：云虚拟机里的安全容器同时遇到 L0、L1、L2 三层地址空间，但硬件只有两级地址转换；JANUS 不再让同一层同时维护 CPU 切换和中间页表，而是让 L1 的软件 switcher 处理 L1↔L2 切换、L0 直接维护 EPT0→2，并用 VMFUNC、shadow root、#VE 和 GPA 分区保护协作路径，在八个内存应用上平均比 PVM/KVM 提升 144%/28.6%，生产 Flink 相对 RunC 开销少于 5%，代价是依赖特定 Intel 功能以及 L0、L1、L2 三处内核修改。

## 问题与动机

[[Secure-Containers|安全容器]]把每个容器放进轻量 VM，以硬件边界隔离不可信代码。当云用户本身租用的是 VM 时，容器 microVM 就成为嵌套客体：L0 是云主机，L1 是租户 VM，L2 是容器 VM。CPU 只有 root/non-root 两种虚拟化模式，MMU 也只有“客体页表 + EPT”两级硬件地址转换，却要表达 L2 虚拟地址、L2 物理地址、L1 物理地址和主机物理地址之间的关系（图 1–3、§2）。

[[KVM]] 的 EPT-on-EPT 方案让 L2 自己维护一级页表，但 L0 还要根据 L1 的 EPT1→2 合成 EPT0→2。一次缺失映射会在 L2、L1、L0 间多次退出、模拟和同步。[[PVM]] 用 L1 内的软件 switcher 缩短 CPU world switch，却采用 SPT-on-EPT：L1 为每个 L2 进程维护 shadow page table，L2 每次改页表都可能让 L1 同步，进程越多锁竞争越严重（图 2、图 4）。

两种方案恰好在不同情况下变慢。论文反复 `mmap`、访问、`munmap` 32 GB 内存：访问从未建立底层映射的 inactive memory 时，KVM EPT-on-EPT 接近 PVM 的两倍时间；访问已有底层映射的 active memory 时，KVM 只需少量退出，PVM 却仍要同步 L2 页表和 SPT。真实应用混合两种内存，所以 JANUS 的目标不是只优化一种缺页，而是重新划分 L0/L1 的职责（图 5、§3.1）。

## 关键观察 / 隐含假设

- **观察 1：CPU world switch 与内存虚拟化的最佳管理层不同。** L1 最接近 L2 的 syscall、interrupt 和 exception，适合本地切换；L0 掌握真正的 HPA 和资源回收，适合维护最终 EPT。把两项职责强绑在 L0 或 L1，才产生重复同步（图 2、§3.1）。
  - **依赖假设**：L0 与 L1 可以通过小而稳定的 hypercall ABI 协作，并且职责拆分后的跨层状态仍能保持一致。
  - **可能失效场景**：L0/L1 版本不匹配、映射更新丢失、回收与缺页并发，或 hypercall 被恶意 guest 高频调用时，分布式页表状态更难诊断。
- **观察 2：真实内存负载同时含 active 与 inactive 物理页。** KVM 在新建 EPT0→2 时付出高成本，PVM 在反复修改进程页表时持续付出 SPT 成本；单独优化其中一端不能覆盖 Redis、编译和分析任务（图 5、§3.1）。
  - **依赖假设**：应用瓶颈确实来自映射建立与同步，而不是设备仿真、存储、网络或 L2 内核自身。
  - **可能失效场景**：纯 CPU 计算、长时间不改映射，或者 I/O 后端主导时，JANUS 的页表快路径贡献会缩小。
- **观察 3：现有 Intel 功能可以拼出“非 root 模式内切 EPT、客体内接收 EPT fault、硬件记脏页”的路径。** VMFUNC 做无 VM-exit 的 EPTP switch，#VE 把指定 EPT violation 交给 guest，PML 记录写入的 GPA（§3.2）。
  - **依赖假设**：云 CPU 暴露 VMFUNC、#VE、PML 和 VMCS shadowing，且它们的组合语义能被 L0 安全配置。
  - **可能失效场景**：AMD、Arm、旧 Intel，或公有云不向嵌套 guest 开放这些功能时，需要另一套慢路径。
- **观察 4：把 L2 GPA 放进独立区间后，PML 记录才可区分 L1 与 L2 写入。** L0 可按地址范围识别 L2 dirty page，再反查其 L1 backing page，而不用把 EPT0→2 全部写保护（图 10、§4.4.2）。
  - **依赖假设**：GPA 分区长期不重叠，reverse mapping 在迁移和回收期间始终完整。
- **假设 1：安全目标是保持传统单层虚拟化的边界，而不是抵御恶意 L0。**
  - **证据强度**：强。论文信任 VMX、ring、页表与 EPT 硬件；它防恶意 L2 越界到 L1/其他 L2，也让 L0 检查恶意 L1 请求是否超出其 HPA。L1 本来就是其 L2 的 hypervisor，论文不保护 L2 免受 L1 控制，也不覆盖侧信道或已被攻陷的 L0。

## 核心方法

**1. 把 CPU 与内存虚拟化拆开。** L1 中的 JANUS CPU virtualization 复用 PVM switcher，让 L2 的 syscall、page fault、interrupt 和 privileged instruction 先回到 L1，不经过 L0；L0 中的 JANUS memory virtualization 则直接维护 EPT0→2，把 L2 GPA 映射到 HPA。硬件用 L2 自己的 GPT 做第一级、EPT0→2 做第二级，不再维护 L1 SPT 或 EPT1→2（图 6、§4.1）。

**2. switcher 同时切 CR3 和 EPTP。** L2 kernel/user 都在 non-root ring 3，switcher 在 non-root ring 0。进入 L2 时，它保存 L1 状态、把 CR3 换成 L2 shadow-root，再调用 `VMFUNC(0,index)` 切到该 L2 的 EPT0→2，最后用 IRET 恢复 L2；退出时按相反顺序回到 EPT0→1 和 L1。整个常见 CPU world switch 不触发 L0 VM exit（表 1、算法 1）。

**3. shadow root 保护跨地址空间执行。** switcher 必须在 L1 和 L2 的同一虚拟地址可见，但恶意 L2 不能改写它。JANUS 只 shadow 顶层 PGD：固定指向 switcher 所在 PUD 的 PGD entry，其他 PGD 更新需经 L1 验证后同步，PUD/PMD/PTE 等低层更新仍由 L2 直接完成。每个 shadow root 只在对应 EPT 中可见；L2 若擅自 VMFUNC 到别的 EPT，会因找不到根映射而 fault，L1 随即终止它（图 7–8、§4.2）。

**4. GPA 分区和 V-bit 约束直接页表。** EPT0→2 把只读 shadow-root/switcher 区与普通 L2 GPA 区分开，L2 可写自己的 GPT，但不能借它覆盖特权区。半虚拟化 L2 kernel 在合法 PTE 中设置软件 V-bit；L1 处理映射请求时检查 V-bit，L0 再验证目标 GPA_L1 的边界、长度和 stale mapping，避免 L1 请求映射到不属于自己的 HPA（图 8–9、§4.3）。

**5. #VE 把 EPT fault 缩成一次协作。** L2 的普通 GPT fault 由 switcher 直接把 `#PF` 注入 L2 kernel，L2 修自己的页表；若缺的是 EPT0→2，硬件产生 #VE，由 L1 读取 faulting GPA、遍历 L2 GPT 得到对应 L1 GPA，再调用一次 `KVM_HC_JANUS_OPS/JANUS_MAP`。L0 解析 HPA 并填 EPT0→2，不再先构造 EPT1→2、写保护、模拟写入后再次 fault（图 9、表 2、§4.3）。

**6. 回收和迁移继续由 L0 控制。** L0 为 EPT0→2 维护按 L1 GPA 索引的 reverse map，host 回收内存时可失效所有派生映射；L1 收到 `mmu_notifier` 后用 `JANUS_UNMAP` 转发自己的失效，并更新本地 dirty/access 属性。迁移时，GPA 分区让 PML 中的 L2 写入可被识别，再通过 reverse map 标记 L1 dirty bitmap，不必写保护全部 EPT0→2（图 10、§4.4）。实现为此修改 L0 KVM 1662 行、L1 PVM hypervisor 3702 行、L2 PVM kernel 264 行；host 改动相对有限，但整体不是未修改 guest 可直接使用的透明方案（§5）。

## 设计取舍

- **少同步换跨层协议。** 删除中间页表能显著减少快路径退出，却把 map、unmap、回收、dirty bit 和 reverse map 的一致性分散到 L0/L1。
- **低 CPU 切换成本换半虚拟化客体。** switcher 很快，但要求修改 L1 hypervisor 与 L2 kernel，并让 L2 kernel/user 都运行在 non-root ring 3。
- **VMFUNC 性能换硬件和安全约束。** 非特权 EPTP switching 不退出，却必须用每 L2 shadow root、EPT 可见性和异常终止来阻止越权。
- **直接 GPT 更新换顶层 shadow。** 常见低层 PTE 修改不陷入 L1，PGD 更新仍需 hypercall；极端地址空间创建/销毁 workload 仍可能打到该慢路径。
- **PML 迁移性能换固定 GPA 布局和 rmap。** 它避免写保护，但增加映射元数据，并要求迁移、回收与重配置时正确清理 stale entry。
- **适用边界。** 受控 Intel 云栈、可修改 Kata/PVM kernel、内存映射频繁的工作负载最合适；任意未修改 VM、跨架构云或设备/I/O 主导应用不在已证明范围。

## 实验设置

- 受控机器使用 Intel Xeon Platinum 8475B、192 个物理 CPU、384 GB RAM；L0、L1、L2 都运行 Linux 5.10.134。KVM 打开 `tdp_mmu`、VMCS Shadowing，L1 打开 THP（§5）。
- 基线是 Kata-KVM（硬件嵌套 EPT-on-EPT）、Kata-PVM（软件 switcher 加 SPT-on-EPT）和 Kata-JANUS。实验硬件、kernel 与容器框架相同，但 JANUS/PVM 需要各自的 guest 修改。
- 端到端 workload 包括四个多进程程序、四个多线程程序、32 GB stress-ng 内存访问、Redis、Memcached，以及生产 PaaS 的 17 个 Flink 查询；微基准覆盖一百万次 world switch、映射建立和 dirty tracking。
- 论文只给平均吞吐或总查询时间，没有 P95/P99、逐个 Flink query、端到端迁移停机时间、长期内存回收抖动、跨架构或多台硬件结果。

## 实验与结果

- **生产 Flink**：相对 RunC，PVM 安全容器让 17 个查询的总时间在 C++/Java engine 上约增加 30%/20%，JANUS 的额外开销都少于 5%。这是实际部署证据，但论文没有披露查询、资源配置或尾延迟明细（§5 Real-world adoption）。
- **八个内存应用**：摘要汇总 JANUS 相对 PVM/KVM 的平均性能提升为 144%/28.6%。细分到 8 vCPU，多进程 workload 相对 PVM/KVM 提升 339.7%/51.8%，多线程 workload 提升 37%/13.3%，说明最大收益来自多个进程各自维护页表的场景（图 11、§5.1）。
- **内存键值服务**：Redis 吞吐相对 PVM/KVM 平均提高 9.7%/45.1%，Memcached 提高 4.4%/48.2%。JANUS 对 KVM 的收益很大，对已经有轻量 switcher 的 PVM 只剩个位数，体现了工作负载边界（图 13、§5.2）。
- **world switch 与首个映射**：一百万次 hypercall 的完整切换成本为 KVM 16002、PVM 2681、JANUS 2700 cycles；额外 VMFUNC 只比 PVM 多 19 cycles。建立初始映射时，KVM/PVM/JANUS/#VE-JANUS 总成本为 57840/19266/28100/26960 cycles：JANUS 比 KVM 快，但第一次映射仍比 PVM 慢，之后才避免 PVM 持续同步 SPT（表 3–4、§5.3）。
- **dirty tracking**：打开追踪后，KVM 的内存修改时间平均增加 175.5%；例如 8 GB 测试从 2.38 s 增到 6.49 s，而 JANUS 从 2.36 s 到 2.97 s，接近 L1 原生的 2.29 s 到 2.93 s。该实验只测写入开销，没有测完整迁移轮次、网络流量或 downtime（表 5、§5.3）。
- **恶意调用压力**：作者把共置的恶意 guest 从 0 增到 8，压力测试 JANUS hypercall，对 host/guest 中 Redis、Memcached 的影响称为可忽略；这支持性能隔离的一小部分，却不是越权映射、VMFUNC 攻击或形式化安全验证（§5.2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CPU/内存职责分离能覆盖 active 与 inactive memory 的互补瓶颈 | 图 11、摘要：八个应用平均优于 PVM/KVM 144%/28.6% | 单台 Intel 主机、八个内存密集 workload | 强 |
| VMFUNC 没有破坏 PVM 的 CPU 快路径 | 表 3：JANUS 2700 cycles，PVM 2681，KVM 16002 | 一百万次纯 hypercall world switch | 强 |
| #VE 和直接 EPT0→2 显著降低首次映射成本 | 表 4：#VE-JANUS 26960 cycles，KVM 57840 | 合成映射微基准；仍慢于 PVM 的 19266 | 强 |
| GPA 分区让 PML 避免迁移期写保护 | 表 5：KVM 开启后平均增加 175.5%，JANUS 接近不开启时 | 内存写微基准，没有端到端迁移 | 中到强 |
| JANUS 在生产中接近原生容器 | §5：17 个 Flink 查询相对 RunC 开销少于 5% | 单一未公开 PaaS 配置，只给总时间 | 中 |

## 批判性分析

### 论证链条

论文先用 active/inactive memory 说明 KVM 与 PVM 各自只擅长一半，再把 CPU 事件和物理映射交给更合适的层；world switch、映射、应用与生产结果从机制到端到端基本闭环。PML 部分的证据链只走到“写入成本”，没有走到迁移完成时间，因此能证明 dirty tracking 快，不能证明整次 live migration 更快。安全机制也主要是设计论证，性能压力测试不能代替攻击验证。

### 假设压力测试

VMFUNC、#VE、PML、VMCS shadowing 缺一项都可能让快路径重新出现 VM exit；论文没有 AMD/Arm fallback。shadow root 假设 PGD 更新稀少，但容器内极端地址空间 churn 可能放大顶层同步。L0/L1 共同管理映射也要求 version、回收、migration 和 crash 顺序一致；只要一次 stale EPT 或 rmap 丢失，就可能变成隔离或数据损坏问题，而不仅是性能问题。

### 实验可信度

KVM、PVM、JANUS 同机同 kernel，覆盖多进程、多线程、Redis/Memcached、微基准和生产 Flink，基线与设计对应得很好。局限是只有一代 Intel 服务器、平均值多于分布、生产配置不公开；没有与 CKI/HyperTurtle 的量化比较，没有端到端 migration/reclamation，没有真实攻击、安全审计或故障注入。摘要的 144% 是八个异质应用的汇总，也不应被解释为每个应用都提高 2.44 倍。

### 系统性缺陷

JANUS 在三层分别修改 1662、3702、264 行代码，还新增 EPT0→2 生命周期、reverse map、V-bit、shadow root 和 hypercall ABI。kernel 升级、Kata/PVM 版本漂移与迁移到不同 host 代际时，维护和兼容成本都高。论文没有讨论 EPT 数量耗尽、恶意 guest 制造 #VE/map-unmap storm、host crash 中的映射恢复、observability 或 rollback；未经正式验证的非特权 VMFUNC 路径也可能有 speculative/side-channel 风险。

## 局限与后续工作

- **局限 1**：依赖特定 Intel 虚拟化扩展，未覆盖 AMD、Arm、旧 Intel 或云平台不暴露 VMFUNC/#VE/PML 的情况。
- **局限 2**：需要修改 L0 KVM、L1 PVM 和 L2 kernel，不是对任意 Kata 或未修改 nested VM 透明的部署。
- **局限 3**：安全论证没有形式化验证、真实 exploit、fuzzing 或 side-channel 测试；恶意 guest 实验只报告性能影响。
- **局限 4**：memory reclamation 与 live migration 只验证局部机制，没有端到端 downtime、迭代次数、网络字节和 P99 service latency。
- **后续工作 1**：对 MAP/UNMAP/CREATE、V-bit、未授权 VMFUNC 和 GPA 边界做 stateful fuzzing，并用 invariant checker 验证任意时刻 EPT0→2 都不能越出 L1 所属 HPA。
- **后续工作 2**：注入 L0/L1 crash、重复 hypercall、丢失 invalidation 和并发 reclaim，检查 stale EPT、rmap 泄漏、数据损坏与安全回退。
- **后续工作 3**：在真实跨机 live migration 中报告 pre-copy 轮数、总字节、downtime、Redis P99 和收敛失败率，并与写保护 KVM/PVM 比较。
- **后续工作 4**：实现 AMD/Arm 或无 #VE 的降级路径，按相同 workload 比较功能覆盖、world-switch cycles 和映射成本；同时评估论文提出的 HLAT 替代 shadow root。

## 相关

- **相关概念**：[[Nested-Virtualization]]、[[Secure-Containers]]、[[Extended-Page-Table]]、[[Live-Migration]]
- **同类系统**：[[KVM]]、[[PVM]]、[[Kata-Containers]]、[[HyperTurtle]]、[[CKI]]
- **同会议**：[[OSDI-2026]]
