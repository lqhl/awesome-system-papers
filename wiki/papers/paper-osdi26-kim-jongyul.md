---
type: paper
name: Oxbow
full_title: "Oxbow: A Coordinated Architecture for Multi-component File Systems"
authors: [Jongyul Kim, Jaehwan Lee, Inhoe Koo, Peizhe Liu, Jiyuan Zhang, Junho Ahn, Tianyin Xu, Youngjin Kwon]
venue: OSDI
year: 2026
tags: [file-system, user-level-io, computational-storage, journaling, kernel-interoperability]
source_pdf: "[[osdi26-kim-jongyul.pdf]]"
source_md: "[[osdi26-kim-jongyul]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-17
---

# 面向多组件文件系统的协同架构（OSDI 2026）

> **原题**：Oxbow: A Coordinated Architecture for Multi-component File Systems

> **一句话总结**：Oxbow 观察到高速 SSD 让内核路径和主机 CPU 成为瓶颈，于是把读操作留在内核 page cache、写操作放到用户态旁路路径，并将后台 journaling offload 到 CSD；在单机实验中写吞吐最高比 Ext4 高 4.8×、比 µFS 高 86%，但读路径仍受跨组件切换和额外拷贝约束。

## 问题与动机

高速 SSD、用户态文件系统和 computational storage device（CSD）分别优化了吞吐、开发速度或主机 CPU 消耗，却把文件系统拆散到应用库、内核和设备端。用户态方案失去 page cache、权限检查、进程间共享和 `sendfile()`；纯内核方案在高速设备上受软件栈和 journaling 开销限制；设备端方案则承受 PCIe 往返和较弱处理器的延迟。

Oxbow 不把三种位置视为互斥选择，而是按操作性质分配职责：内核负责缓存、保护与共享，用户态负责前台文件系统逻辑和快速写路径，CSD 负责可异步执行的 crash consistency 工作。

## 关键观察 / 隐含假设

- **观察 1：读和写从内核获得的收益不对称。** 读依赖 page cache 和 readahead，写则更容易受 system call、内核 block layer 和 journaling 影响（§2.2、§3）。
  - **依赖假设**：应用读写都能通过 `mmap` 访问共享 page-cache 页面，且工作负载能从 readahead 获益。
  - **可能失效场景**：随机读、内存压力高或工作集远超缓存时，额外的 kernel–H-Server 切换和拷贝会暴露出来。
- **观察 2：journaling 是适合设备 offload 的后台工作。** CSD CPU 比主机 CPU 弱，但 journaling、checkpointing 等工作可批处理并异步执行（§2.3）。
  - **依赖假设**：后台提交能在下一次 `fsync` 前推进，并且设备与主机能安全共享 SSD namespace。
  - **可能失效场景**：I/O 带宽饱和、并发 fsync 形成突发，或设备端计算资源不足时，前台路径可获得的收益会缩小。
- **假设 1：组件间共享状态可以按字段划分为单写者。** 例如 kernel 维护 `uid/gid`，oxLib 维护文件大小和时间戳（§4.2）。
  - **证据强度**：中。元数据基准支持该结构，但更复杂的 POSIX 语义和异常路径覆盖有限。

## 核心方法

Oxbow 由四个组件组成：应用内的 oxLib、可信用户态文件服务器 H-Server、连接 VFS 的内核 shim illuFS，以及运行在 CSD 上的 D-Server（图 3）。H-Server 使用 lwext4 实现布局、分配和索引逻辑；illuFS 使系统继续使用内核 VFS、page cache、权限检查和 readahead。

读路径从 `mmap` 页面缺页开始，经 illuFS 请求 H-Server，再由 H-Server 通过用户态驱动读取并填充 page cache。写路径直接修改映射页面，由 oxLib 维护 dirty-page 和 page-lock bitmap；`fsync` 时 H-Server 解析脏页并写入 staging area。该分工对应观察 1：保留内核读服务，同时绕过内核写入持久化路径。

Split Journaling 将前台 `fsync` 与后台 commit 解耦。H-Server 把当前文件的数据和 inode 写入持久化 staging area，staging transaction 记录最近已提交的 journal ID，因此 `fsync` 不必等待设备端提交。后台事务由 H-Server 复制到连续 DMA buffer，D-Server 经 DMA 拉入设备内存并写 journal。DMA buffer 同时充当 page-cache 的 shadow copy，页面只在复制期间短暂锁定（图 7、图 8）。

共享元数据采用单写者、多读者布局，减少跨组件锁和失效。D-Server 只理解 block address、extent 和事务描述符，不解释文件语义，因此 journaling 可独立于 H-Server 的文件系统逻辑运行。

## 设计取舍

- **内核互操作性换取额外拷贝。** Oxbow 获得 page cache、readahead、权限和 `sendfile()`，但写入包含应用到 page cache、page cache 到 SPDK buffer 的额外拷贝；µFS 在延迟基准中最高快 43%。
- **后台 offload 换取设备与恢复复杂度。** staging area、journal area、DMA snapshot 和跨主机/设备恢复共同维护 durability invariant；论文假设组件 fail-stop，设备计算失效时才提供主机 fallback。
- **用户态轮询换取吞吐。** H-Server worker 会 busy-wait，10 客户端 append 时消耗 5.4 个主机核心；D-Server journaling 仅约 0.1 个核心。

## 实验与结果

- 双路 Xeon Gold 5218、128GB DRAM、Samsung PM1735 NVMe，BlueField-2 作为 CSD 代理；对比 Ext4、µFS 和 OmniCache（§6.1）。
- 写吞吐最高比 Ext4 高 4.8×，比 µFS 高 86%；吞吐/主机 CPU 周期最高是 µFS 的 3.9×、Ext4 的 4.7×（图 10、图 11）。
- 单客户端 `fsync` 时间比第二名低 16.8–19.2×；10 客户端时优势降为 2.0–2.2×，因为带宽饱和限制后台提交（表 1）。
- 顺序读吞吐比 µFS 高 10.5–18.5×，但比 Ext4 低最多 24%；把 readahead window 从 32 页增至 128 页后可超过 Ext4（图 10）。
- LevelDB YCSB 中，工作负载 B/C 比 µFS 高 83%/89%（单进程）；工作负载 E 比 Ext4 高 41%（单进程）。RAG 的 I/O 延迟比 Ext4 低 50%，LLM checkpoint 吞吐高 58%（表 2、表 3、图 14）。
- Nginx 启用 `sendfile` 后吞吐是关闭时的 3.3×，证明 Oxbow 能复用内核接口（图 15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 半内核旁路能同时保留内核服务和快速写入 | 写吞吐最高比 Ext4 高 4.8×，`sendfile` 吞吐提升 3.3×（图 10、图 15） | 单机、特定 NVMe、BlueField-2 代理 CSD | 强 |
| Split Journaling 降低前台持久化等待 | 单客户端 `fsync` 快 16.8–19.2×，无 staging 时延迟约为默认配置 7.8×（表 1、图 13） | 后台提交有可用带宽；并发升高后优势下降 | 强 |
| 设备 offload 降低主机 CPU 效率成本 | 吞吐/CPU 周期最高为 µFS 的 3.9×（图 11） | µFS busy-wait 通信周期被排除，比较对 µFS 有利 | 中 |
| 内核 readahead 对读性能有决定作用 | 顺序读比 µFS 高 10.5–18.5×，扩大 window 后超过 Ext4（图 10） | 依赖顺序性和 page-cache 行为 | 中 |

## 批判性分析

### 论证链条

观察、设计和微基准之间的对应关系清晰：读复用 readahead，写绕过内核，后台 journaling 放到设备端。Split Journaling 的 self-contained staging transaction 也直接解释了 `fsync` 不等待旧 journal commit 的原因。论文把“低 CPU 消耗”定义为吞吐/CPU 效率时较有说服力，但绝对 CPU 消耗并不总是最低；Oxbow 在高并发下仍受 H-Server 轮询限制。

### 假设压力测试

结果依赖特定的 SR-IOV/NVMe namespace sharing 和 BlueField-2 代理环境。真实 CSD 的内部存储控制器、DMA 路径和 CPU/带宽比例变化后，后台提交能否持续领先需要重新测量。`mmap` 写路径还把正确的 dirty tracking 和 page-lock 语义交给 oxLib；恶意或崩溃的客户端虽被权限和字段所有权限制，但异常退出、信号和多进程写入的覆盖范围仍小于成熟内核实现。

### 实验可信度

基线包含 Ext4、µFS 和 OmniCache，覆盖微基准、LevelDB、RAG、LLM checkpoint 与 Nginx，且有 staging、后台 journaling 和主机 journaling 消融。局限在于测试规模最多 32 个写客户端、64 个读客户端，µFS 最多支持 10 个客户端；长期运行、混合租户隔离、故障恢复时间和真实生产 trace 未展示。

### 系统性缺陷

Oxbow 约 53K 行代码，另依赖修改后的内核、lwext4、用户态驱动和 CSD 固件。多组件部署增加升级、监控和故障诊断面。论文给出 fail-stop 恢复协议，但未量化恢复时间、staging/journal 空间放大、设备端日志磨损或部分 PCIe/SSD 故障下的运维行为。

## 局限与后续工作

- **局限 1**：读路径仍比 Ext4 长；顺序读需要调大 readahead window 才能弥补跨组件开销。
- **局限 2**：CSD offload 的收益随并发和带宽饱和下降；后台提交不能无限领先 `fsync`。
- **局限 3**：实验依赖 BlueField-2、特定 SR-IOV SSD 和定制环境，尚未证明跨 CSD 代际与多租户隔离下的结论。
- **后续工作 1**：在真实 CSD、不同 PCIe 拓扑和 100+ 客户端下测量 `fsync`、P99、恢复时间与 host/device CPU 分解。
- **后续工作 2**：评估客户端崩溃、D-Server 重启、SSD 部分故障及 journaling 空间压力下的可恢复性和写放大。

## 相关

- **相关概念**：[[Page Cache]]、[[Crash Consistency]]、[[Computational Storage]]
- **同类系统**：[[Ext4]]、[[µFS]]、[[OmniCache]]
- **同会议**：[[OSDI-2026]]
