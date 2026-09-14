---
type: paper
name: Espresso
full_title: "Espresso: Constructing Cost-Efficient CXL JBOF via Inter-SSD Computing Resource Sharing"
authors: [Shushu Yi, Yuda An, Li Peng, Xiurui Pan, Qiao Li, et al.]
venue: OSDI
year: 2026
tags: [cxl, jbof, ssd, resource-harvesting, storage]
source_pdf: "[[osdi26-yi.pdf]]"
source_md: "[[osdi26-yi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Espresso：用 SSD 间计算资源共享构建低成本 CXL JBOF（OSDI 2026）

> **原题**：Espresso: Constructing Cost-Efficient CXL JBOF via Inter-SSD Computing Resource Sharing

> **一句话总结**：JBOF 中 I/O burst 的时间错位使 SSD 内置 ARM 核和 DRAM 长期闲置；Espresso 将 SSD 拆成 compute-end 与 data-end，借助 CXL 让空闲 SSD 的处理器和 DRAM 协助繁忙 SSD 处理元数据，在每块 SSD 只保留一半计算资源的情况下达到接近完整配置的性能，资源利用率提高 50.4%，BOM 成本下降 19.0%。

## 问题与动机

现代 enterprise SSD 将 ARM 处理器和约 1 GB/TB 的 DRAM 放在盘内，以处理命令解析、地址转换和 FTL 元数据缓存。JBOF 把多块 SSD 聚合起来，但不同租户的 burst 通常不同步，导致一部分盘忙于 flash I/O，另一部分盘的计算资源空闲。论文引用 Tencent 25-drive 服务器的 trace：94.6% 的时间至少有 20 块盘的带宽利用率低于 75%。因此，为峰值购买的盘内计算资源没有被充分利用。

现有 harvesting 通常把 SSD 当成不可分割的黑盒。它可以把写请求重定向到空闲盘，却无法利用“写入受限但处理器空闲”的 SSD，也不能有效帮助读请求，因为目标数据仍在 borrower 的 flash 上。回收 lender 时还要把数据 copyback，增加写放大；集中式 hypervisor 管理也会消耗 host CPU。

## 关键观察 / 隐含假设

- **观察 1：不同 I/O 类型压在 SSD 的不同资源上。** 4 KB 顺序读消耗 96% 的处理器时钟，却只占用 39% 的 flash 时钟；4 KB 顺序写占用 99% 的 flash 时钟，处理器仅 27%（§3.1，图 4）。
  - **依赖假设**：同一 JBOF 中这些资源压力会随租户和请求类型错峰。
  - **可能失效场景**：所有租户同时进行 processor-heavy 或 flash-heavy 操作时，没有可借资源，Espresso 退化为缩减配置的 SSD。
- **观察 2：传统写请求 harvesting 对读主导负载帮助很小。** Tencent 和 Alibaba 负载上的吞吐提升仅为 0.5% 和 0.8%（§3.1）。
  - **设计含义**：应共享处理元数据的无状态计算资源，而不是搬运数据。
- **观察 3：FTL 映射表的 DRAM 需求具有明显的工作负载差异。** 某个生产负载只需 0.001 GB/TB DRAM 就达到 25% miss ratio，另一个需要 0.17 GB/TB（图 4c）。
  - **依赖假设**：可以在线估计 miss-ratio curve，并在 DRAM 借用期间维持可接受的性能与一致性。
- **假设 1：CXL 3.0 的 cache-coherent、peer-to-peer 内存访问足够快且可部署。** 论文主要依靠 SimpleSSD 与 Xerxes 模拟器验证；公开可用的 CXL 3.0 硬件尚不存在，因此真实硬件的协议、拓扑和故障行为仍是外推。
- **假设 2：SSD 同质化。** 默认所有 SSD 拥有相同硬件和 firmware。异构场景需要 TEE、可执行 firmware 以及更一般的负载指标，论文只给出设计讨论（§6）。

## 核心方法

Espresso 把 SSD 按功能拆为 compute-end 和 data-end。compute-end 包含 ARM 核、DDR 控制器和 DRAM，负责 firmware 执行；data-end 包含 flash controller、flash backbone、DMA engine 和数据缓冲区，负责数据传输与 flash I/O。CXL Type-2 controller 将部分 DRAM 注册为全局 fabric-attached memory，并让 peer SSD 通过 load/store 访问共享元数据。data-end agent 则把 lender 处理器发来的 DMA/flash 操作放入 borrower 的消息队列，由 borrower 的 data-end 执行。

每块 SSD 在 DRAM 中维护 idle resource table。资源描述符记录资源类型、借用者、可用量、映射表目录和 NVMe queue 信息。SSD 通过 reader-writer lock 读写这些描述符，使用 best-fit 选择 lender；资源的发现、借用和归还由各 SSD 自治完成，避免 hypervisor 成为 host CPU 瓶颈（对应观察 1 和观察 3）。

处理器 harvesting 通过修改 Linux v5.15 NVMe driver 实现。每个 SSD 预留 shadow queue pair；host 将 borrower 的部分命令送入 lender 的 shadow SQ，lender 处理 borrower 的映射表，再把 DMA 和 flash 操作发回 borrower 的 data-end。NVMe weighted round-robin 限制 lender 的份额，结合两端处理器利用率计算重定向比例，使 lender 保留自己的服务能力。该路径只移动命令处理，不移动用户数据，因此读写都能受益且不需要 copyback。

DRAM harvesting 将映射表按 2 MB segment 管理，用 SHARDS 在线预测 LRU miss-ratio curve。borrower 借入足够 DRAM，把 miss ratio 压到阈值（默认 10%）；lender 则借出预计不会降低自身 miss ratio 的空闲 segment。由于 off-site dirty metadata 不受 borrower 的 PLP 直接保护，Espresso 为每个 segment 保留本地 4 KB redo-log page。修改远端元数据时先写日志并 flush；segment 满后刷回 borrower 的 flash。lender 故障时，host 让 borrower 重放本地日志并重新提交 shadow queue 中的请求。

## 设计取舍

- **共享无状态计算而非 flash 空间**：避免了写数据 copyback和 SSD 寿命损失，但 borrower 仍必须拥有目标数据；方案不能把闲置 flash 容量本身变成通用缓存。
- **CXL 一致性换取简单共享语义**：远端 load/store 和硬件 coherence 简化元数据访问，却引入 CXL controller、目录和新故障域。默认每块盘用 1K directory entries 跟踪 64 KB cache，并非整个映射表。
- **去中心化管理换取盘内 firmware 复杂度**：host 负担较小，但 lender、borrower 和 driver 需要周期性同步。10 ms 同步周期过长会使停止借用延迟，造成短暂资源争用。
- **性能隔离限制可借资源**：WRR 保证 lender 自己的请求优先，但可借资源随 lender 负载变化，borrower 的吞吐上限依赖 JBOF 中恰好存在足够的空闲盘。

## 实验与结果

- 在 12-SSD、DPU host 的模拟 JBOF 中，Espresso 每盘仅配置 Conv 一半的 ARM 核和 DRAM。在 64–256 KB、QD64 微基准中，Espresso 与完整配置 Conv 性能相近；Shrunk 平均吞吐低 29.2%，而 Espresso 的处理器利用率比 Shrunk 高 50.4%（§5.2，图 10）。
- 在 QD1 的 4 KB 随机读写中，Shrunk 的映射表 miss ratio 导致随机读延迟比 Conv 高 24.7%；DRAM harvesting 后 Espresso 延迟仅平均增加 3.4%（§5.2、§5.4，图 11、图 17）。
- 在多组生产 trace 上，Espresso 比 Shrunk 和有 copyback 的 VH 分别高 19.2% 和 20.0% 吞吐；VH 仍比 Conv 低 14.0%，说明写数据搬运的收益会被回收成本抵消（§5.2，图 12）。
- BOM 模型显示，2 TB SSD 的 Espresso 比 Conv 低 19.0%；当 CXL controller 和 DRAM 的额外成本不超过 Shrunk 的 40% 时，Espresso 的成本效率仍优于 OCSSD 方案（§5.2，图 13）。
- lender 的吞吐平均仅下降 1.3%，borrower 在 lender 为轻负载时提升 15.5%–30.0%；远端访问带来的 inter-SSD 延迟开销最高 2.9%，每个 I/O 的 host load-balance 计算约增加 20 ns（§5.3，图 14–15）。
- 复杂场景中 12 块 SSD 各自运行不同 Tencent workload，Espresso 峰值吞吐达到 12.3 GB/s，Shrunk 为 8.1 GB/s；最长完成时间缩短 34.3%（§5.5，图 18）。在两 socket NUMA 模拟的 Ext4/filebench 与 RocksDB/db_bench 测试中，Espresso 比 Shrunk 高 24.8%，接近 Conv（§5.6，图 19）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 共享盘内处理器和 DRAM 能弥补缩减的 SSD 资源 | 微基准中接近 Conv；生产 trace 比 Shrunk 高 19.2%（§5.2，图 10、12） | 主要为 SimpleSSD/Xerxes 模拟，12 SSD、固定拓扑 | 强 |
| 只共享计算资源可以同时帮助读写并避免 copyback | VH 在读负载提升 0.5%–0.8%，Espresso 接近 Conv（§3.1、§5.2） | 数据仍固定在 borrower flash；未验证跨厂商真实 CXL SSD | 中 |
| 去中心化管理和负载均衡能够保护 lender | lender 平均吞吐损失 1.3%，每 I/O host 额外约 20 ns（§5.3） | 特定 workload、WRR 和 10 ms 同步周期 | 中 |
| 方案具有成本收益 | BOM 比 Conv 低 19.0%，CXL 额外成本不超过 40% 时成本效率优于 OC（图 13） | 成本来自市场价格和模拟假设，未计入 CXL 生态与运维成本 | 中 |

## 批判性分析

### 论证链条

论文的主链条较完整：生产 trace 说明盘间 burst 错位，微基准说明 SSD 内部资源压力分离，架构拆分使这些资源可独立借用，模拟结果再验证缩减配置的性能恢复。DRAM harvesting 还补上了传统写 harvesting 无法处理的读路径。

但“可部署的 CXL JBOF”仍有一步没有被真实硬件证明。核心 firmware 在 DaisyPlus PCIe OpenSSD 上实现，CXL 行为由 Xerxes 建模；两者无法覆盖真实 Type-2 SSD 的一致性实现、链路拥塞、热插拔和电源故障。

### 假设压力测试

当多数 SSD 同时忙于 I/O，Espresso无法产生足够 lender，论文的收益会消失。敏感性实验显示，borrower:lender 为 1:11 时继续增加 lender 也不能提升吞吐，受到 flash backbone 和同步开销限制（§5.4，图 16）。这说明“有足够闲置盘”是收益成立的必要条件，而不是普通部署细节。

远端 DRAM 的日志机制处理了 lender 永久掉电，但日志页、刷回时机和 borrower/lender 双方状态更新仍扩大了恢复状态机。论文未给出多块 lender 同时失效、CXL fabric manager 失效或 host 重启期间的完整恢复评测。

### 实验可信度

论文使用 Alibaba、Tencent、Fujitsu、Windows 等生产 trace，并同时覆盖微基准、复杂混合负载、Ext4 和 RocksDB；基线包含 Conv、OC、Shrunk、VH、VH(ideal) 和 ProcH，能够分离处理器 harvesting、DRAM harvesting 与 copyback 的影响。局限是大多数结果来自模拟器，NUMA emulation 只有两 socket，不能复现 12 块真实 SSD 的 CXL 竞争和拓扑行为。BOM 结果也没有呈现 CXL controller 开发、固件验证、散热、升级和故障运维成本。

### 系统性缺陷

Espresso 要求 SSD 暴露 firmware 可操作的元数据布局、shadow queue 和一致性协议，超出了现有 NVMe 黑盒接口。论文提出用标准化 telemetry 暴露状态，但 telemetry 并不能自动解决跨设备执行 firmware 的安全与 ABI 兼容问题。异构 SSD 的 TEE 方案只停留在讨论层面。

方案还把新的资源调度决策放进 SSD firmware。错误的 watermark、过期 descriptor 或 CXL 拥塞可能导致 lender 自身尾延迟升高。论文主要报告平均吞吐和平均延迟，对 P99、租户隔离、QoS 违约和在线重配置期间的尾延迟覆盖不足。

## 局限与后续工作

- **局限 1：缺少真实 CXL 3.0 硬件验证。** 后续应在至少 8–12 个真实 CXL Type-2 设备上测量链路拥塞、coherence 目录容量、远端访问尾延迟和 fabric manager 故障恢复。
- **局限 2：收益依赖 workload 错峰和 lender 数量。** 应使用连续生产 trace 做在线实验，报告不同 borrower:lender 比例下的 P99、SLO 违约率和资源借还震荡。
- **局限 3：异构 SSD 与 firmware 安全尚未实现。** 应定义不暴露内部布局的标准资源描述符，并在不同 ARM 性能、DRAM 容量和 flash 并行度下验证负载均衡与隔离。
- **局限 4：成本模型没有包含系统级投入。** 应把 CXL switch、固件开发验证、PLP、电源、散热、升级和失效备件纳入 TCO，而不只比较 controller、DRAM 和 NAND 的 BOM。

## 相关

- **相关概念**：[[CXL]]、[[Flash Translation Layer]]、[[Storage Virtualization]]、[[Cache Coherence]]
- **同类系统**：[[XHarvest]]、[[BlockFlex]]、[[FleetIO]]、[[JBOF]]
- **同会议**：[[OSDI-2026]]
