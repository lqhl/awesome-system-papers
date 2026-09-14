# Compaction-Free Memory Defragmentation for Virtualization via Infinite Guest Physical Address Space

> **论文**：Peixin Zeng, Hao Huang, Yanqi Pan, Wen Xia, Darong Yang, Jiahao Chen, Nan Zhang；OSDI 2026
>
> **一句话总结**：INFINIDEFRAG 把 GPA 当作近似无限的虚拟地址空间，在虚拟机需要连续区域时扩展 GPA 并重映射 HPA，绕开 guest-side compaction；在极端碎片化下，它将整理带宽从 Linux THP 的 0.91 GB/s 提高到近 20 GB/s（约 19×），并在 YCSB-Redis 上取得接近无碎片上界的性能。

## 问题与动机

虚拟化中的 huge page 能同时减少 guest 页表和 GPA→HPA 的二级地址转换开销，但它要求 guest physical address（GPA）中存在连续区域。长期运行的 VM 会因页分配和回收产生外部碎片。Linux THP 通过页迁移和 compaction 恢复连续空间，却把复制、页表更新和 TLB shootdown 放到分配路径或后台执行，可能干扰前台请求。

论文在 YCSB-Redis 的极端碎片化设置下发现，LLFREE 和 Linux THP 只有无碎片 THP 基线吞吐的 49%–72%，延迟增加 30%–102%（图 3）。作者的核心判断是：guest OS 把 GPA 当作固定的物理内存，因此被迫整理；虚拟化层实际上可以利用 GPA→HPA 间接层，在不移动仍在使用的数据的情况下换一个连续的 GPA 区域。

## 关键观察 / 隐含假设

- **观察 1：huge page 的收益主要来自降低地址转换成本。** 在随机访问工作负载中，INFINIDEFRAG 的吞吐与 PTW cycles 变化高度相关（图 17）。
  - **依赖假设**：工作负载的 TLB 局部性不足，二级页表遍历确实是主导开销。
  - **可能失效场景**：计算、网络或锁竞争占主导时，连续 GPA 可能不能转化为端到端收益。
- **观察 2：compaction 得到的 huge page 不足以抵消其干扰。** THP 虽然能分配更多 huge page，但同步 compaction 增加 page-fault 时间，后台迁移则造成运行期延迟尖峰（图 5、图 15）。
- **假设 1：GPA 空间在 VM 生命周期内可视为近似无限。** 论文以 57-bit 物理地址空间和约 32 MB/s 的 dirty rate 估算，地址空间耗尽需数十年至一个多世纪；但该估算依赖 workload 的写入率和硬件地址宽度，证据强度为中。
- **假设 2：可回收的碎片 GPA 页足以支撑扩展。** 仍在使用、被 pin、共享或设备映射的页不能直接回收；在回收页不足时系统退回常规 compaction。

## 核心方法

INFINIDEFRAG 由三个组件组成。Infinite Address Manager 在 huge-page 分配失败时，从 guest buddy allocator 中找出空闲碎片页，并以 1 GB memory block 粒度扩展 GPA。回收的 4 KB 页与扩展区域进行 memory trade，避免迁移有效页。异步执行时，分配器暂时退回 base-page 分配。

Guest Reclaimer 用 bitmap 追踪页状态，并以 Fast Reclaim 绕过 buddy allocator 的 zone lock 和复杂 free-list bookkeeping。普通分配和回收仍走 buddy allocator，只在 bitmap 上做一致性更新。多线程下，order ≤ 6 的请求使用原子 compare-and-exchange；更大请求按 order-6 子页事务式分配并在失败时回滚。

Host Memory Guard 维护新旧 GPA–HPA 映射并控制 VM 的 HPA 配额。host 使用 base pages 时，self-hosted remap 将回收的 HPA 页直接登记为新 GPA 区域的缺页来源，跳过 host buddy allocator。为解决多线程 remap 的锁和 TLB shootdown，论文采用 in-kernel remap 与 delayed TLB flush，因为被回收的 GPA 页已在 guest 中逻辑不可访问。

host 使用 huge pages 时，论文采用 batch unmapping 和 hybrid paging。连续范围合并后再发起 unmap；新扩展 GPA 区域尽量使用 host huge pages，无法回收的旧碎片页保留为 base-page 映射，并让后台 compaction 处理冷数据。该设计把 guest-side compaction 从关键路径移除，但没有消除 host-side compaction。

## 设计取舍

- **地址空间换整理成本**：扩展 GPA 避免了数据复制和 guest compaction，却增加了 EPT 管理、memory hotplug、页 bitmap 和 per-page metadata 的成本。
- **host base pages 与 huge pages 的取舍**：base pages 便于精细回收和 remap，但可能把一个 guest 2 MB 区域拆成最多 512 个 EPT 条目；host huge pages 提供更好的转换性能，却需要 hybrid paging 和后台整理。
- **预留区域换运行期开销**：启动时预留 96 GB offline memory region，准备耗时少于 1 s，减少频繁 hotplug；代价是预留资源和元数据可能长期占用。

## 实验与结果

- 测试平台为双路 28-core Intel Xeon Gold 6330、256 GB DRAM，QEMU 8.2.94、Linux 6.10.0，VM 配置为 16 vCPU、64 GB。工作负载包括 YCSB-Redis、GUPS、Graph500、SPECjbb、XSBench 等（§6.1）。
- 极端碎片化下，INFINIDEFRAG 在 host huge-page 和 host base-page 两种配置中都取得最高吞吐（图 12）；YCSB-Redis 相对 LLFREE、Linux THP 和 Linux 4 KB 的吞吐提升为 21%–105%。
- 中度碎片化下优势缩小，因为仍有 512 KB 或 1 MB 的可合并区域，THP 更容易恢复 huge page（图 13）。无碎片时各方案性能接近，说明收益集中于高碎片场景。
- 整理带宽从 Linux THP 的 0.91 GB/s 提高到 INFINIDEFRAG 的近 20 GB/s，约 19×（图 16）。INFINIDEFRAG 的 huge-page 数量接近工作集上界，而 CBMM/LLFREE 在多个负载中无法分配 huge page（图 18）。
- 优化后的内核 remap 在 16 线程下接近普通匿名缺页的开销，优于 mremap、userfaultfd 和未延迟 TLB flush 的内核实现（图 10、图 22b）。多 VM 测试中三个 VM 间没有明显吞吐干扰（图 21）。
- Fast Reclaim 使用每页 2 bit bitmap；GPA 扩展的 per-page metadata 为每个 4 KB 页 64 B，约占其容量的 1.6%（§6.8）。实现涉及 guest kernel、host kernel 和 QEMU/KVM，修改约 7K LoC（§5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 避免 guest compaction 能恢复 huge-page 带来的地址转换收益 | PTW cycles 与吞吐对比，图 12、图 17 | 主要是随机访问、2 MB 页、单 VM/有限多 VM | 强 |
| INFINIDEFRAG 的整理路径比 compaction 更快 | 0.91 GB/s 对近 20 GB/s，图 16 | 无前台应用、host base pages、极端碎片化 | 强 |
| 异步 reclaim/remap 能降低前台延迟 | YCSB-Redis 实时延迟，图 15；remap breakdown，图 22 | 64 GB VM、16 vCPU、给定 QEMU/KVM 实现 | 中 |
| 方案能扩展到多线程和多 VM | 图 20、图 21 | 多线程工作负载与三个 VM，未覆盖更大租户规模 | 中 |

## 批判性分析

### 论证链条

“连续 GPA 足够降低转换成本”这一链条由图 17 支持；“扩展 GPA 比迁移页便宜”由整理带宽、page-fault 和 remap 微基准支持。论文的性能上界主要使用 NoFrag，并将 host base 与 host huge 配置统一归一化，便于比较但也掩盖了真实部署中 host huge page 供给不足的成本。方案在 host base pages 下仍有明显上界差距，因为 EPT 无法形成 2 MB 映射。

### 假设压力测试

极端碎片化是有意构造的压力场景，能突出方案优势，但不等同于生产 trace。论文只评估 2 MB huge page；1 GB 页的可行性停留在讨论层面。GPA 扩展依赖回收空闲页，若 VM 工作集接近配额、页 cache 很少或大量页被 pin，扩展速度和成功率可能下降。57-bit 地址空间的“世纪级”估算也没有覆盖迁移、快照、地址空间保留策略等实际约束。

### 实验可信度

基线包括 Linux THP 多种策略、Linux 4 KB、CBMM 和 LLFREE，覆盖了同步 compaction、后台 compaction 与 anti-fragmentation。消融分析覆盖 Fast Reclaim、self-hosted remap、hybrid paging。缺少真实云平台长期 trace、不同 VM 内存配额、NUMA 亲和性、live migration、KSM/内存超卖和故障恢复实验，因此生产运维结论仍有限。

### 系统性缺陷

实现跨 guest kernel、host kernel 和 QEMU/KVM，约 7K LoC，升级和维护成本不低。延迟 TLB flush 依赖“被回收 GPA 不会再访问”的不变量；其与并发 guest 行为、错误恢复和 VM checkpoint 的交互需要额外验证。host huge-page 模式仍依赖后台 compaction，且可能牺牲 KSM 等细粒度页级机制。论文未报告安全隔离、热迁移期间的元数据同步和异常中止路径。

## 局限与后续工作

- **地址空间与元数据增长**：per-page metadata 随 GPA 线性增长；可回收并复用已释放页的元数据，或采用稀疏元数据结构。
- **回收能力有限**：页 cache、pinned/shared/device-mapped 页会降低 memory trade 的供给；应测量不同不可移动页比例下的退化曲线。
- **host-side碎片化**：hybrid paging 没有完全取消 host compaction；需要在多 VM、超卖和 NUMA 场景下量化 compaction 的 CPU、带宽和尾延迟。
- **正确性与运维**：应验证 live migration、快照恢复、guest crash、EPT stale TLB 和配额动态调整，明确回滚与故障注入后的安全边界。

## 相关

- **相关概念**：[[Huge Pages]]、[[Memory Fragmentation]]、[[Memory Compaction]]、[[EPT]]、[[TLB Shootdown]]
- **同类系统**：[[LLFree]]、[[CBMM]]、[[Ingens]]、[[vMitosis]]
- **同会议**：[[OSDI-2026]]
