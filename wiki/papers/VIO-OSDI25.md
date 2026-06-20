---
type: paper
name: VIO
full_title: "To PRI or Not To PRI, That's the question"
authors: [Yun Wang, Liang Chen, Jie Ji, Xianting Tian, Ben Luo, et al.]
venue: OSDI
year: 2025
tags: [virtualization, virtio, iommu, memory-oversubscription, sriov]
source_pdf: "[[osdi25-wang-yun.pdf]]"
source_md: "[[osdi25-wang-yun]]"
---

# To PRI or Not To PRI, That's the question (OSDI 2025)

> **一句话总结**：SR-IOV passthrough 需静态 pin 内存阻碍超售，PRI 在 NIC 上普及慢且 IOPF 在关键路径延迟高；VIO 在 hypervisor 用 VirtIO shadow available ring 做 IOPA-Snoop 消除 IOPF，IOPS 低时回收冷页，高时弹性切回 passthrough，300K VM 部署日 reclaim 等价 30K 台 2C/4GB VM 内存且满足 SLO。

## 问题与动机

云上大比例 legacy VM（>1 年）无 PRI，单 VM 可达 ~800GB 内存、冷页 >34%，但 passthrough 不能 page fault。PRI 延迟高（PCIe 路径）、DevTLB/同步开销大，不适配高密度 SR-IOV。纯 vIOMMU/IOGuard 等需改 guest 或性能差。

## 关键观察 / 隐含假设

- **观察 1**：73.14% VM IOPS <1000，仅 <3.57% 超 30K IOPS；低 IOPS 占主导，snoop 开销（~4µs/次）可接受。
  - **依赖假设**：生产 IOPS 分布长期保持长尾；SLO 对高 IOPS VM 更敏感。
  - **可能失效场景**：AI/LLM 等中高 IOPS VM 比例上升时 reclaim 收益下降。
- **观察 2**：IOPF 在 DMA 关键路径会导致设备丢包，重传延迟可达数百 ms，远大于 IOPF 本身。
  - **依赖假设**：在设备 DMA 前由 hypervisor 同步 fault-in 页面即可避免关键路径 IOPF。
  - **可能失效场景**：极高 IOPS 下 snoop 累积成为瓶颈，需切 passthrough（论文已设计）。
- **假设 1**：仅改 host hypervisor、不改 guest，才能覆盖数十万 long-running VM。
  - **证据强度**：强——表 1 对比 IOGuard/balloon 等 guest 依赖方案。

## 核心方法

**IOPA-Snoop**：guest 更新 available index 后，设备见 shadow index；snoop 线程 EPT fault-in 页面再推进 shadow index，中断仍 passthrough。

**Elastic passthrough**：IOPS 超阈值（生产 ~100K）切 native available ring + 预 swap-in；低 IOPS 回到 snoop 模式回收。

**Lockpage**：静态锁 RX queue；自适应 LRU 锁热页减重复 fault。

**部署**：Orthus VMM live upgrade 热启用 VIO。

## 设计取舍

- **取舍 1**：shadow ring + IOMMU IOPT 重映射换零 guest 改动，切换时 ~10µs ring 拷贝。
- **取舍 2**：高 IOPS 放弃 reclaim，保证 near-native 性能。
- **边界条件**：VirtIO 1.0、x86 AMD/Intel；legacy 与新建 VM。

## 实验与结果

- 300 节点生产：VIO 启用后 **~120GB/天** 可回收（≈30K 台 2C/4GB VM），SLO 满足。
- 相对传统 passthrough：**10%** 日内存降低潜力（实验）。
- PRI 相对 CPU page fault：**3×–80×** 更高延迟（背景）。

## Critical Analysis

### 论证链条

IOPF 在关键路径有害 → hypervisor 预映射 → 弹性策略匹配 IOPS 分布 → 生产 reclaim 数据，工程闭环强。正确性依赖 VirtIO 语义与 EPT/IOMMU 一致性，论文有机制描述但形式化少。

### 假设压力测试

RDMA/VirtIO-offload 混合路径是否全覆盖？多队列多设备并发 snoop 线程竞争？阈值 100K IOPS 随硬件代际变化需重标定。

### 实验可信度

30 万 VM 规模生产数据说服力强；对照 PRI/IOGuard 多来自文献与实验而非同等规模 A/B。

### 系统性缺陷

论文未讨论 malicious guest 通过 virtqueue 行为攻击 snoop 线程；可观测性（每 VM reclaim 归因）未详述。

## 局限与 Future Work

- **局限 1**：snoop 路径在 medium IOPS 区间收益与开销权衡依赖阈值手工调参。
- **Future work 1**：随 PRI 普及的混合路径（PRI + VIO）是否更优。
- **Future work 2**：在 LLM 推理等高 IOPS VM 增长后的 reclaim 率跟踪。

## 相关

- **同会议**：[[OSDI-2025]]