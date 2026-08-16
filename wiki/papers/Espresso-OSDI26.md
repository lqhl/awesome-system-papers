---
type: paper
name: Espresso
full_title: "Espresso: Constructing Cost-Efficient CXL JBOF via Inter-SSD Computing Resource Sharing"
authors: [Shushu Yi, Yuda An, Li Peng, Xiurui Pan, Qiao Li, Jieming Yin, Guangyan Zhang, Wenfei Wu, Chenxi Wang, Diyu Zhou, Zhenlin Wang, Xiaolin Wang, Yingwei Luo, Ke Zhou, Jie Zhang]
venue: OSDI
year: 2026
tags: [storage, cxl, ssd, jbof, resource-sharing]
source_pdf: "[[osdi26-yi.pdf]]"
source_md: "[[osdi26-yi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 通过跨 SSD 计算资源共享构建低成本 CXL JBOF（OSDI 2026）

> **原题**：Espresso: Constructing Cost-Efficient CXL JBOF via Inter-SSD Computing Resource Sharing

> **一句话总结**：论文观察到 JBOF 中各 SSD 的突发负载通常不同步，而且一次 I/O 对处理器、DRAM 和闪存的压力并不相同；Espresso 因而用 [[CXL]] 把 SSD 内部拆成计算端和数据端，在盘间借用 ARM 核与 DRAM，使只保留一半计算资源的模拟 SSD 在生产 trace 回放中接近全配置性能，在 256 KB 顺序读模拟中将处理器利用率相对 Shrunk 提高 50.4%，并在论文的物料价格假设下降低 19.0% BOM 成本。

## 问题与动机

企业 SSD 为了应付偶发的 I/O 高峰，会为每块盘配置较强的 ARM 处理器和足以容纳完整 [[FTL]] 映射表的 DRAM。代价是控制器和 DRAM 在 4 TB [[PCIe|PCIe]] 4.0、PCIe 5.0 SSD 的 BOM 中分别合计占 23.2% 和 31.8%，但这些资源在多盘 JBOF 中大部分时间闲置。Tencent 的 25 盘 trace 显示，任意时刻至少 20 块盘带宽利用率低于 75% 的概率为 94.6%；Alibaba、Tencent、Fujitsu 集群的平均盘带宽利用率只有 8.0%、27.8% 和 15.3%（图 3）。

现有方案没有同时解决成本、性能和兼容性。在论文的模拟实验中，把 FTL 放到 host 的 OCSSD 会让 16 核 DPU 在只接 4 块盘时就饱和；整盘虚拟化只能把写入临时导向空闲盘，对以读为主的 trace 仅提高 0.5%–0.8%，回收盘时还要复制数据，trace 回放估算出额外 0.29 DWPD、预计缩短 22.5% SSD 寿命；集中式管理又使 host 成为瓶颈并造成 21.4% 吞吐损失（图 4、§3.1）。

Espresso 的目标不是借用别人的闪存空间，而是只借用相对无状态的处理器和缓存容量。数据仍留在原 SSD，因此既能帮助读，也避免写回搬迁；这要求盘间能够低延迟、保持缓存一致地访问 FTL 元数据，论文选择 [[CXL]] 3.0 作为基础。

## 关键观察 / 隐含假设

- **观察 1：多租户 JBOF 的突发负载通常错开，盘间存在可借用的计算余量。** 除了上述生产 trace，论文还指出 25 盘 Tencent 服务器在 94.6% 的时间里至少有 20 盘未满载（图 3c）。
  - **依赖假设**：同一 JBOF 中的租户负载不会长期同步爆发，并且借出盘仍保有服务自身请求的余量。
  - **可能失效场景**：全盘重建、集中 checkpoint、同一上层服务引发的相关突发，会让借用池同时枯竭。
- **观察 2：SSD 不是单一瓶颈，处理器、DRAM 和闪存压力会随 workload 分离。** DaisyPlus 上 4 KB 顺序读占用 96% 处理器时钟，却只占用 39% 闪存时钟；4 KB 顺序写则分别为 27% 和 99%。两个 workload 将映射缓存 miss ratio 降到 25% 所需的 DRAM 也相差 170 倍，即每 TB 闪存 0.001 GB 对 0.17 GB（图 4b–c）。
  - **依赖假设**：处理器忙时数据端仍有余量，或本地 DRAM 不足时别盘恰有冷缓存空间；PMU、闪存 busy clock 和在线 MRC 能及时反映这种分离。
  - **可能失效场景**：处理器与闪存始终同时饱和、元数据 working set 高度一致，或负载变化快于 10 ms 控制周期时，细粒度共享收益会缩小。
- **观察 3：只远程处理元数据、让数据继续经过 borrower 的 DMA 和闪存，可以同时服务读写并避免数据 copyback。** 这是 Espresso 相对整盘虚拟化的主要收益来源（图 5）。
  - **依赖假设**：I/O 路径中可外借的固件任务主要是命令解析和地址翻译，远程元数据访问与同步开销小于闪存访问时间。
  - **证据强度**：中。OpenSSD 原型验证了本地固件组件，主要端到端数据来自 CXL 3.0 模拟器；没有真实多盘 CXL 3.0 SSD。
- **假设 1：同一 JBOF 的 SSD 同构，并允许 peer SSD 执行彼此的固件路径。** 论文默认硬件和固件一致；异构 SSD、TEE 封装固件只是 §6 的设计讨论，没有实现或评测。
  - **证据强度**：弱。当前实验不能说明跨厂商固件 ABI、安全隔离和升级兼容性。

## 核心方法

Espresso 先把每块 SSD 拆成两个功能域。**计算端（compute-end）**包含 ARM 处理器、DDR 控制器和 DRAM，执行命令解析、地址翻译等固件任务；**数据端（data-end）**包含 DMA、数据缓冲、闪存控制器和闪存介质，负责真正的数据传输。Type-2 CXL 控制器把部分本地 DRAM 注册为全局 fabric-attached memory，使 host 和 peer SSD 能以一致的 load/store 访问元数据（图 6）。

每块盘的 Espresso daemon 每 10 ms 读取 ARM PMU、映射表 miss ratio 和闪存通道 busy clock，并把可借资源写入全局可见的 idle-resource descriptor。Borrower 扫描 peer 表并按 best-fit 选择 lender；描述符由读写锁保护，借用和归还由各 SSD 自治完成，host 不承担集中式资源管理（图 7）。

**处理器借用**通过修改 [[NVMe]] driver 完成。Host 把 borrower 的部分命令从普通 queue pair 重定向到 lender 的 shadow queue pair；lender 的 ARM 直接读写 borrower 的 FTL 映射元数据，再把 DMA 和 flash operation 放入 borrower 数据端的消息队列。数据始终在 host 与 borrower 闪存之间流动，不经过 lender。调度器同时使用 NVMe weighted round-robin 和两盘的实时处理器利用率计算重定向比例，避免 lender 自身请求被挤掉（图 8）。

**DRAM 借用**以 2 MB segment 为单位。每块盘用 SHARDS 在线估计 miss-ratio curve（MRC）：不会再降低本盘 miss ratio 的空间可以借出，borrower 则借到预测 miss ratio 低于 10% 为止。由于 borrower 的脏映射可能暂存在 lender DRAM，Espresso 为每个借入 segment 在 borrower 本地保留一个 4 KB 日志页；更新远端元数据前先把 redo log 刷回 borrower。Lender 故障时，borrower 从本地日志恢复；borrower 故障时，host 通知 lender 清理借出空间（§4.5）。

实现上，host 侧改在 Linux 5.15 NVMe driver，固件侧在 DaisyPlus OpenSSD 上实现；data-end agent 从本地 DRAM 消息队列出队一条操作平均耗时 114.2 ns，在本地 DRAM 中准备并刷写一条 redo log 平均耗时 321.9 ns。这两个数没有包含真实 CXL 盘间传输。因为没有公开的 CXL 3.0 SSD，论文把这些实测值交叉校准到扩展后的 SimpleSSD 与 Xerxes 模拟器，并另用双路 [[NUMA|NUMA]] + NVMeVirt 做应用级仿真验证（§4.6）。

## 设计取舍

- **以细粒度共享换硬件与固件改造**：不搬数据能服务读写、减少写放大，但每块 SSD 都要支持 CXL Type-2、全局一致内存、远程消息队列和新固件协议。
- **以分散自治换全局最优性**：10 ms 轮询和 best-fit 让 host 每条 I/O 只多约 20 ns 调度时间，但控制是滞后的，也没有求解全局最优的 lender/borrower 匹配。
- **以远端缓存换恢复复杂度**：借 DRAM 能降低 FTL miss，但引入跨盘脏元数据和日志恢复；论文没有用故障注入验证断电、拔盘和多盘故障下的完整恢复路径。
- **边界条件**：同构 SSD、非同步突发和快速 CXL fabric 下设计最合适；相关突发、异构固件、强租户隔离或较慢/无一致性的互连会使它变脆。

## 实验与结果

- **设置与基线**：主要实验是 12 SSD 的模拟 JBOF；host 按 BlueField-3 配置为 16 核 2.1 GHz ARM、16 GB DRAM，每个全配置 SSD 为 6 核 1 GHz ARM、每 TB 闪存 1 GB DRAM、14/10 GB/s 读写带宽，互连模拟 CXL 3.0。比较 Conv、OC、Shrunk、VH、无 copyback 的 VH(ideal)、仅借处理器的 ProcH；Espresso 与 Shrunk 都只保留 Conv 一半的 ARM 核和 DRAM。指标覆盖吞吐、平均延迟、利用率、BOM、能耗和 workload 完成时间，workload 包含 microbenchmark 及 Alibaba、Tencent、Fujitsu 等生产 trace 回放（表 2–3、§5.1）。
- **处理器与 DRAM 的组件收益**：I/O depth 64 的 64–256 KB microbenchmark 中，OC 和 Shrunk 相对 Conv 平均损失 27.8% 和 29.2% 吞吐，Espresso 借处理器后在读写中都接近 Conv，并将 256 KB 顺序读的处理器利用率相对 Shrunk 提高 50.4%。I/O depth 1 的 4 KB 随机读中，Shrunk 和 ProcH 因 49.7% 映射 miss 而比 Conv 慢 24.7%；完整 Espresso 借 DRAM 后延迟接近 Conv（图 10–11）。
- **生产 trace 回放**：在 14 个 workload 上，Espresso 与 Shrunk 使用相同的半配置资源，却分别比 Shrunk 和 VH 平均高 19.2% 和 20.0% 吞吐，并接近 Conv；VH 在算入 copyback 后仍比 Conv 低 14.0%（图 12）。这是 trace 驱动模拟，不是线上 JBOF 实测。
- **成本结论依赖价格模型**：论文按 NAND 每 128 GB 4.95 美元、DRAM 每 GB 7.2 美元、控制器 48 美元估算，并假定半配置资源的成本减半、CXL 控制器和 DRAM 比 Shrunk 贵 10%。在此模型下，2 TB Espresso SSD 比 Conv 省 19.0% BOM，Ali-0 的 IOPS/美元比 OC 高 19.7%；只要 CXL 溢价不超过 40%，其成本效率仍高于 OC（图 13）。
- **共享开销与隔离**：借出资源使 lender 吞吐平均下降 1.3%；lender I/O depth 从 32 降到 1 时，borrower 吞吐收益从 15.5% 增至 30.0%。相对 Conv，Espresso 的 inter-SSD 延迟占比最多 2.9%，但能耗高 3.5%；这些是平均值，论文没有报告 P99/P999 尾延迟（图 14–15）。
- **规模与外部验证**：在 12 块盘各跑独立 Tencent workload 的 10 组模拟中，Espresso 峰值 12.3 GB/s、Shrunk 为 8.1 GB/s，完成时间最多缩短 34.3%。双路 NUMA 上的 [[Ext4|Ext4]]/Filebench 与 [[RocksDB|RocksDB]]/db_bench 仿真中，Espresso 比 Shrunk 高 24.8% 并接近 Conv；该平台只有一个 borrower 和一个 lender，不能验证真实多盘 CXL 扩展性（图 18–19）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 盘间借 ARM 与 DRAM 能让半配置 SSD 接近全配置性能 | 图 10–12、§5.2 | 12 盘模拟器；默认 6 borrower、6 idle lender；生产 trace 为回放 | 强 |
| 细粒度共享同时改善读和写，优于整盘虚拟化 | 图 10、图 12 | 论文选择的 microbenchmark 与 14 个 trace；未覆盖同步全盘突发 | 强 |
| Espresso 可节省 19.0% BOM 成本 | 图 13、§5.2 | 市场价格估算；假设半资源成本线性减半、CXL 溢价为 10% | 中 |
| 资源借出对 lender 的影响很小 | 图 14、§5.3 | 平均吞吐下降 1.3%；只测中等压力且省略 src、depth 32 的不可借场景 | 中 |
| 设计可部署在真实 CXL JBOF | OpenSSD 原型、NUMA 仿真、§4.6、图 19 | 没有真实 CXL 3.0 SSD 或 12 盘实机；固件与链路结果来自原型加模型交叉校准 | 弱 |

## 批判性分析

### 论证链条

论文从“盘间负载不同步”和“盘内资源压力分离”推出细粒度共享，再用 ProcH、完整 Espresso 和 VH 的差异拆开处理器、DRAM、避免 copyback 三项收益，逻辑基本闭合。真正的跳步是把“经 OpenSSD/NUMA 校准的 12 盘模拟结果”外推到可量产的 CXL JBOF：CXL coherence、交换机竞争、固件并发和多租户故障域没有在同一真实系统中联合出现。成本结论也不是采购数据，而是建立在资源成本线性缩减和 CXL 溢价假设上的模型。

### 假设压力测试

若 12 块盘同时遇到写回、恢复或 checkpoint，Espresso 不会创造新的处理器和 DRAM，只会退化为 Shrunk；论文的 11:1 到 1:11 敏感性实验表明 lender 不足时收益确实下降。若工作集变化快于 10 ms、远端 FTL cache line 频繁争用，轮询和一致性流量可能放大尾延迟。异构 SSD 还需要可移植固件任务、TEE 和统一负载指标，这些都只停留在讨论。以上是基于设计的推断，不是论文已测结论。

### 实验可信度

基线覆盖全配置、host-managed、缩配、传统虚拟化、理想无 copyback 和单组件版本，且 workload 同时有 microbenchmark、多个生产 trace 和两个应用，设计拆解较完整。硬件边界却很强：绝大多数结果来自 SimpleSSD + Xerxes；真实部分只有单盘 OpenSSD 微操作和双路 NUMA 仿真。论文主要报告吞吐和平均延迟，缺少尾延迟、长时间稳定性、CXL fabric 拥塞、真实功耗和故障注入。所谓 19.0% 成本节省应读作“在论文价格模型下”，不能当作已测采购成本。

### 系统性缺陷

Espresso 把原来单盘内部的 FTL 元数据访问、锁和失败恢复扩展成跨盘协议，故障域和运维复杂度都会增大。论文给出单 lender 失效时的日志恢复流程，却未讨论 CXL switch 故障、多个 lender 同时失效、固件滚动升级、恶意 tenant 或损坏 firmware 的隔离。每盘还需新增 CXL Type-2 控制器和 coherence directory；真实面积、功耗、验证成本及与现有 SSD 保修/PLP 机制的结合均未量化。

## 局限与后续工作

- **局限 1：实机证据不完整。** 在真实 12 盘 CXL JBOF 上复现图 10–18，并报告 P50/P99/P999 延迟、switch 带宽和 coherence traffic，才能验证模拟外推。
- **局限 2：负载相关性覆盖不足。** 可用不同相关系数合成同步突发，测出 lender 比例、10 ms 周期与 SLO 退化的相变点。
- **局限 3：恢复与隔离未验证。** 需要对 lender、borrower、host 和 CXL switch 做断电/拔盘故障注入，客观检查日志恢复时间、数据一致性和未完成 I/O 重放。
- **后续工作 1：异构与安全执行。** 在至少两种控制器/固件上实现受保护的远程任务 ABI，并测 TEE、版本转换和跨厂商调度开销。
- **后续工作 2：校准成本模型。** 用真实 CXL SSD 控制器面积、DRAM、交换机、供电和运维成本替代“10% 溢价”假设，给出不同容量下的总拥有成本。

## 相关

- **相关概念**：[[CXL]]、[[NVMe]]、[[FTL]]、[[JBOF]]、[[Computational-Storage]]
- **同类系统**：BlockFlex、FleetIO、XHarvest
- **同会议**：[[OSDI-2026]]
