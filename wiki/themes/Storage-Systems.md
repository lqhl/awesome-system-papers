---
type: theme
topic: Storage-Systems
theme_kind: area
member_tag: area/storage-systems
paper_count: 8
first_generated: 2026-08-17
last_updated: 2026-08-18
tags: [topic-overview, storage, file-systems, disaggregated-memory]
---

# 存储系统与解聚内存综述

> 8 篇论文覆盖脱氧核糖核酸（deoxyribonucleic acid，DNA）存储、云块存储索引、生成式文件系统、人工智能数据存储流水线和由远程直接内存访问网卡管理的解聚内存。共同主线是：让介质、工作负载与数据路径的自然粒度直接进入系统抽象。

## 阅读提示

本页所说的“粒度”是系统一次寻址、分配或传输的数据单位；粒度若与真实工作负载不匹配，就会放大元数据、网络或计算开销。解聚内存（disaggregated memory）把内存节点与计算节点分开，通过远程直接内存访问（Remote Direct Memory Access，RDMA）连接；RDMA 网卡（RDMA Network Interface Card，RNIC）可以代替较弱的内存节点处理部分控制工作。检查点（checkpoint）是训练中用于恢复状态的快照，键值缓存（key-value cache，KV cache）则保存模型推理时可复用的中间状态。

## 核心论文

### 新介质、块存储与文件系统（4 篇）

- [[LiqSD-FAST25|LiqSD]] — 使用双重 DNA 转换层（dual DNA translation layer，dual DTL）、共生元数据和延迟失效机制构造 DNA 块设备。
- [[RASK-FAST26|RASK]] — 直接以连续写入范围作为弹性块存储（Elastic Block Store，EBS）的索引键，减少逐点索引项占用的内存和查询开销。
- [[SysSpec-FAST26|SysSpec]] — 用形式化规格（formal specification，即可由工具检查的系统行为描述）驱动[[LLM|大语言模型]]生成文件系统实现。
- [[ProbeFS-SOSP26|ProbeFS]] — 以生化内容寻址和并行机制构造分层 DNA 文件系统；当前仅公开了元数据，证据仍不完整。

### 人工智能数据与分布式文件系统（2 篇）

- [[AITurbo-FAST26|AITurbo]] — 通过分组输入输出接口、主机动态随机存取内存（Dynamic Random Access Memory，DRAM）和计算互连，加速检查点与键值缓存的批量输入输出。
- [[FalconFS-NSDI26|FalconFS]] — 删除深度学习客户端的元数据缓存，把路径解析和命名空间状态移到元数据服务器。

### 解聚内存管理（2 篇）

- [[ODRP-NSDI25|ODRP]] — 把 4 KiB 远程换页所需的分配、地址转换和访问编排为 RNIC 工作请求链（work request chain，WR chain）。
- [[OneSidedMW-NSDI26|OneSidedMW]] — 由 RNIC 执行二类内存窗口（type-2 memory window，type-2 MW）的绑定与解绑，在保留原生单边访问的同时解耦内存管理。

## 主题综述

DNA 存储路线从 [[LiqSD-FAST25]] 的块设备抽象延伸到 [[ProbeFS-SOSP26]] 的分层文件系统。LiqSD 已明确展示介质读写粒度不对称为何需要双重转换层与延迟失效，但当前单块操作仍需几十分钟；ProbeFS 能否借助生化内容寻址和并行机制改变这条物理边界，还要等全文公开后判断。

[[RASK-FAST26]] 与 [[FalconFS-NSDI26]] 都用生产轨迹推翻通用数据结构的直觉：EBS 写入应按范围而非按点建立索引；深度学习中的随机目录遍历则应删除客户端元数据缓存，而不是继续扩大缓存。[[AITurbo-FAST26]] 同样把检查点和键值缓存的分组批量输入输出暴露给存储层。三者共同说明，系统抽象应服从工作负载的自然粒度。

解聚内存呈现出两代设计。[[ODRP-NSDI25]] 通过页级地址转换实现严格的 4 KiB 分配与 100% 利用率，但每次访问都要经过工作请求链；[[OneSidedMW-NSDI26]] 只把二类内存窗口的控制路径卸载到 RNIC，让读写回到原生单边路径，并支持可变大小的输入输出。

## 设计空间矩阵

| 论文 | 工作负载 | 主要瓶颈 | 核心机制 | 主要资源 | 证据边界 |
|---|---|---|---|---|---|
| [[LiqSD-FAST25]] | 归档型 DNA 块存储 | 元数据与更新放大 | 双重 DNA 转换层与延迟失效 | DNA、固态硬盘 | 模拟器；输入输出耗时为分钟级 |
| [[RASK-FAST26]] | 云块存储 | 索引内存 | 以写入范围作为索引键 | DRAM、存储设备 | 多家供应商的轨迹 |
| [[SysSpec-FAST26]] | 文件系统演化 | 实现维护 | 由形式化规格驱动大语言模型生成 | 大语言模型、验证器 | 选定的模块与功能 |
| [[ProbeFS-SOSP26]] | DNA 文件系统 | 尚未公开 | 生化内容寻址 | DNA | 只有元数据，尚无全文 |
| [[AITurbo-FAST26]] | 检查点与键值缓存输入输出 | 前端与网络 | 分组接口与暂存 | DRAM、RDMA、存储设备 | 华为生产环境 |
| [[FalconFS-NSDI26]] | 深度学习小文件 | 元数据缓存与访问放大 | 无状态客户端 | 元数据服务器、固态硬盘 | 部署于 10,000 个神经网络处理器（Neural Processing Unit，NPU） |
| [[ODRP-NSDI25]] | 远程换页 | 分配所需的处理器开销 | 页级工作请求链 | RNIC、DRAM | 1 个内存节点和 8 个计算节点；4 KiB 页 |
| [[OneSidedMW-NSDI26]] | 远程换页与解聚内存中的键值缓存 | 管理与访问之间的取舍 | 卸载二类内存窗口管理 | RNIC、DRAM | 1 个内存节点和 6 个计算节点 |

## 共同观察

- **粒度错配是首要成本。** DNA 链、存储容器与位置，EBS 写入范围，深度学习目录遍历，人工智能任务的分组输入输出，以及远程内存块，都要求不同于传统逐点索引、固定页和通用缓存的处理单位。
- **控制面开销可能超过数据传输。** [[ODRP-NSDI25]] 与 [[OneSidedMW-NSDI26]] 绕开处理能力较弱的内存节点处理器，[[FalconFS-NSDI26]] 消除路径遍历放大，[[LiqSD-FAST25]] 则把根转换层放入固态硬盘。
- **真实轨迹是选择抽象的关键证据。** [[RASK-FAST26]]、[[FalconFS-NSDI26]] 和 [[AITurbo-FAST26]] 都依赖生产工作负载，而不是只依据硬件峰值带宽设计。

## 假设冲突与脆弱点

- [[ODRP-NSDI25]] 的页级地址转换与 [[OneSidedMW-NSDI26]] 的可变大小访问能力分别优化利用率和访问延迟；两者的优势转折点取决于碎片率、分配频率、队列对与内存窗口容量。
- [[FalconFS-NSDI26]] 假设客户端局部性很弱；通用可移植操作系统接口（Portable Operating System Interface，POSIX）、源代码树和元数据热点工作负载可能仍更适合有状态缓存。
- [[LiqSD-FAST25]] 用访问放大来代表未来介质趋势，但这不能掩盖当前的绝对延迟；[[ProbeFS-SOSP26]] 尚无全文，不能视为已经解决该问题。

## 值得关注的方向

- **自适应远端内存原语**：根据分配与访问次数之比，在线选择 ODRP 的页映射或 OneSidedMW 的能力授权机制。
- **无状态与有状态混合的分布式文件系统**：根据目录复用、数据打包程度和内存压力，在客户端与服务器端路径解析之间切换。
- **DNA 系统实机证据**：在小规模生化实验台上验证元数据、垃圾回收（garbage collection，GC）和内容寻址的错误率、成本与恢复时间。
