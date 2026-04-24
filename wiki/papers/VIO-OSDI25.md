---
type: paper
name: VIO
full_title: "To PRI or Not To PRI, That's the question"
authors: [Yun Wang, Liang Chen, Jie Ji, Xianting Tian, Ben Luo, et al.]
venue: OSDI
year: 2025
tags: [virtualization, iommu, io-passthrough, memory-overcommit, cloud]
source_pdf: "[[osdi25-wang-yun.pdf]]"
source_md: "[[osdi25-wang-yun]]"
---

# To PRI or Not To PRI, That's the question (OSDI 2025)

> **一句话总结**：VIO 在 VirtIO 数据面做 IOPA-snoop 预先消灭 I/O page fault，再配合 IOPS-aware 弹性 passthrough 切换，在阿里云 300K 台 VM 规模上每天回收等价 30K 台 VM 的内存，且不牺牲 SLO。

## 问题

云上 SR-IOV + device passthrough 能给 VM 近裸机的 I/O 性能，但 passthrough 要求 VM 内存静态 pin，和 CSP 赖以降本增效的 memory oversubscription 天然冲突。PCI-SIG 2009 年就提出了 PRI（Page Request Interface）让 device 能触发 I/O page fault 由 OS 处理，但 14 年后仍未广泛部署：除了高端 GPU，主流 NIC/存储设备都没支持，Intel 到 2023 Sapphire Rapids 才在 IOMMU 里加 PRI。

PRI 本身也有硬伤：IOPF 落在 DMA 关键路径上，设备缓冲区有限，fault 处理延迟会触发 TCP/RDMA 重传风暴，端到端延迟放大 100×。且 2TB 内存 + 4KB 页的 on-device page table 同步要耗 500MB，DevTLB miss 开销高。而阿里云 80% 的长期运行 legacy VM 不支持 PRI，cold page 占 34%，迁移不现实。

## 核心方法

VIO 的核心是 **IOPA-Snoop**：在 VirtIO 的 virtqueue 上拦截 kick 通知，在 device 真正读 descriptor 之前就扫描即将被 DMA 的 buffer，提前把被换出的页 swap in。具体实现引入 shadow available ring——device 看到的是老索引（指向旧地址），hypervisor 的 IOPA-Snoop 线程检测到 available index 更新后 snoop buffer、确保所有页已映射、再更新 shadow available index 让 device 继续。这样 IOPF 从 DMA 关键路径彻底移除。

**IOPS-aware 弹性 passthrough**：低 IOPS 时走 snoop 模式换取内存回收；高 IOPS（比如 > 100K IOPS）时 hypervisor 原子地把 IOMMU IOPT 重新指向原生 available ring，切回纯 passthrough 模式避免 snoop 开销（每次 snoop 约 4µs）。切换前先把 swap 出的页预取回来，transition 时关键路径零 IOPF。配合 QEMU live upgrade（Orthus），legacy VM 无需重启就能享受 VIO。

**Adaptive Lockpage**：通过 IOPA-snoop 采集访问 pattern，把热 I/O 页加入 lockpage bitmap 锁住避免反复 swap-in/out；静态 lockpage 把连续的 VirtIO RX 队列整块固定。

关键：所有改动都在 hypervisor 侧，guest OS 完全不变，对所有硬件通用，不依赖 PRI 或专用 NIC。

## 关键结果

- 部署在全球某领先 CSP 的 300K 台 VM 上（legacy + 新实例）
- 每天回收约 120GB/node 内存，相当于每天腾出 30K 台 VM (2C/4GB) 的资源
- 生产环境每日内存降低最多 10%，且满足用户 SLO
- 300 节点生产集群中，legacy VM 占 800GB 内存、cold page 34%，代表巨大可回收空间
- IOPA-snoop 单次约 4µs，高 IOPS 下自动切回 passthrough 不影响性能

## 相关

- **相关概念**：[[VirtIO]]、[[IOMMU]]、[[SR-IOV]]
- **同会议**：[[OSDI-2025]]
