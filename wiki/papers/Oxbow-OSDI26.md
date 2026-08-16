---
type: paper
name: Oxbow
full_title: "Oxbow: A Coordinated Architecture for Multi-component File Systems"
authors: [Jongyul Kim, Jaehwan Lee, Inhoe Koo, Peizhe Liu, Jiyuan Zhang, Junho Ahn, Tianyin Xu, Youngjin Kwon]
venue: OSDI
year: 2026
tags: [file-system, computational-storage, kernel-bypass, journaling, crash-consistency]
source_pdf: "[[osdi26-kim-jongyul.pdf]]"
source_md: "[[osdi26-kim-jongyul]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Oxbow：面向多组件文件系统的协同架构

> **原题**：Oxbow: A Coordinated Architecture for Multi-component File Systems

> **一句话总结**：Oxbow 不强迫文件系统在内核、用户态和计算存储设备之间三选一，而让读取复用内核页缓存，让写入绕过内核，再把日志与检查点放到设备后台执行；它用更复杂的四组件协议，换来了高写吞吐、较短的前台 `fsync` 和较高的主机 CPU 效率。

## 问题与动机

高速 [[NVMe]] SSD 已经把一部分瓶颈从设备转移到主机软件路径。把文件系统移到用户态可以缩短路径，也方便快速开发，但会失去 VFS、页缓存、预读、`sendfile`、权限检查和进程间共享等成熟内核能力。把整个文件系统放进计算存储设备（computational storage device，CSD）又会让前台请求跨越 [[PCIe]]，并受设备端弱 CPU 限制。

论文的出发点是：读取、写入、元数据管理和持久化后台任务需要的能力不同，不应该被迫放在同一个执行域。目标同时包括四点：接近用户态文件系统的前台性能，保留 Linux 内核接口，减少主机 CPU 消耗，并允许核心文件系统逻辑在用户态快速迭代（§2.4）。

## 关键观察 / 隐含假设

- **读取和写入对内核的需求不对称。** 读取很依赖页缓存和预读；普通写入的内核块层、事务拼装和额外切换反而可能成为开销。Oxbow 因此让读走内核，让写走半内核旁路（semi-kernel-bypass）（§3、§4.3）。
- **共享元数据不一定要由所有组件共同写。** 把每组 inode 字段交给唯一写者，就能通过共享内存读取最新值，减少热路径上的同步。论文示例中，内核维护 `uid/gid`，oxLib 更新 `size/mtime`，H-Server 读取并验证这些字段（§4.2）。
- **`fsync` 的“本次数据已经持久化”不等于“完整日志已经在设备端合并完成”。** 若先把自包含事务写到持久化 staging area，就能让调用返回，再由设备后台写日志和做检查点（§4.4）。
- **设备侧最适合连续、后台、计算较重的工作。** 日志合并和 checkpoint 可以批量进行；细碎的前台元数据请求仍留在主机，避免频繁跨设备边界（§3）。
- **正确性依赖明确的信任与故障模型。** oxLib 位于应用进程内，不能被完全信任；内核、H-Server 和 D-Server 被信任。论文采用 fail-stop 故障模型，并假设底层存储仍能提供可靠持久化和 DMA（§4.2、§4.5、§4.6）。

## 核心方法

### 1. 四个组件各管一类工作

- **oxLib** 链接进应用，截获 POSIX 调用，并用 `mmap`、脏页位图和页锁位图管理应用可访问的数据页。
- **illuFS** 是薄内核文件系统，连接 VFS、页缓存、预读和权限检查。它不承担完整文件系统逻辑。
- **H-Server** 是可信用户态服务，拥有设备、块分配和核心文件系统逻辑，并通过用户态驱动发 I/O。它也负责准备前台持久化事务。
- **D-Server** 运行在 CSD 上，只处理后台数据日志和检查点。它不理解完整文件语义，因此设备端代码保持较小（图 3、§4.1）。

这种划分的关键不是简单“卸载”：H-Server 仍在主机上做复杂、延迟敏感的逻辑，D-Server 只接管适合批处理的持久化工作。

### 2. 读走内核，写走旁路

读取或缺页时，应用进入 illuFS，继续使用 VFS、页缓存和内核预读；H-Server 负责解析块位置并通过用户态驱动读取 SSD，数据最终进入页缓存。路径比 [[Ext4]] 更长，但保留了内核已有的读取优化。

写入时，应用先改 `mmap` 页面并设置脏位。`fsync` 到来后，H-Server 找出脏页，把它们复制到稳定缓冲区并发持久化 I/O，绕过内核块层。与零拷贝的 µFS 相比，Oxbow 为应用透明性和 VFS 兼容性付出两次额外复制：应用缓冲区到页缓存，以及页缓存到 [[SPDK]] 缓冲区（§4.3、§6.2.1）。

### 3. 用单写者和共享页状态协调组件

元数据按字段组分配唯一写者，其他组件通过受保护的共享内存读取。应用内的 oxLib 不能任意修改 H-Server 或内核拥有的区域；H-Server 还会验证来自 oxLib 的字段。数据页另有逐页脏位和锁位，避免应用写入与 H-Server 快照复制同时发生（§4.2、§4.6）。

这个协议把“共享同一份状态”与“多人都能修改”分开：共享减少复制，单写者减少冲突。但 `rename`、`truncate` 等跨字段、跨 inode 操作仍需要额外协调。

### 4. Split Journaling 把前台持久化与后台日志分开

`fsync` 时，H-Server 生成一个自包含 staging transaction，其中包括文件数据、inode 状态和最近已提交的日志事务编号。该事务写入 SSD 上的 staging area 并持久化后，`fsync` 就可以返回。D-Server 随后通过 DMA 拉取连续缓冲区，在后台把变化提交到日志并做 checkpoint（图 6、§4.4）。

为了不在设备 I/O 的整个过程锁住应用页面，H-Server 只在主机复制时短暂加锁，生成 shadow copy 后立刻解锁。事务按文件组织，不使用 Ext4/JBD2 的全局块级事务拼装，从而减轻并发竞争。

### 5. 恢复依赖 journal、staging 和扫描重建

恢复先重放已经提交的 journal，再处理仍留在 staging area 的事务。因为分配位图的快照可能落后于最近分配，Oxbow 还要扫描 extent，重建空闲空间信息。检查点先处理 staging transaction，最后再处理 journal，以保持恢复顺序（§4.5）。

主机端 H-Server 崩溃时可重启并重新连接；D-Server 故障则需要重启相关组件并恢复。如果 CSD 的计算单元失效而块设备仍可访问，D-Server 也可以退回主机运行。论文给出了协议和恢复顺序，但没有用故障注入测恢复正确性或恢复时间。

## 设计取舍

- **兼容性换额外路径与复制。** 内核预读和 `sendfile` 很有价值，但 Oxbow 读取要在内核与 H-Server 之间切换，写入也比 µFS 多两次复制。
- **低前台延迟换 staging 空间与后台债务。** D-Server 足够快时，后台可以跑在 `fsync` 前面；若 staging 接近占满或设备长期落后，前台仍会重新受设备吞吐限制。
- **主机 CPU 卸载换设备资源。** 论文重点计算主机 CPU，不计算 BlueField/DPU 的 CPU 与能耗，因此不是总系统成本比较。
- **单写者换跨组件协议。** 普通字段更新更简单，但复杂命名空间操作、并发 `mmap` 与 `truncate` 会放大协议状态空间。
- **四个组件换开发灵活性。** 核心逻辑可以在用户态迭代，但部署、调试、升级和故障恢复需要同时管理 oxLib、内核模块、H-Server 和 D-Server。

## 实验设计

原型约 53K 行 C/C++，不含改造后的 lwext4。实验机是双路 Xeon Gold 5218、128 GB 内存和 3.2 TB Samsung PM1735 SSD；最大读写带宽分别为 6.1/3.6 GB/s。论文没有使用集成式 CSD，而是用 BlueField-2（8 个 2.0 GHz ARM A72 核、16 GB 内存）加共享 SSD来模拟，BlueField 经 100 Gbps [[RDMA]]/NVMe-oF 访问设备（§5、§6.1）。

基线包括 Ext4、用户态 µFS 和设备侧 OmniCache。µFS 使用性能最好的自定义分配器零拷贝模式，并把 server thread 数设为 client 数；这有利于 µFS 性能，但接口不再完全透明。Ext4 使用 data journaling，并扩大日志以避免耗尽。评测包含微基准、消融、LevelDB/YCSB、[[RAG]] 检索、[[LLM|LLM]] checkpoint、Nginx/`sendfile` 和附录中的元数据测试。

## 实验与结果

- **前台延迟、吞吐与 CPU 效率。** 写延迟相对 Ext4 分别降低 2.1–3.5×（append）、1.2–1.8×（sequential）和 1.2–1.9×（random）；µFS 的零拷贝使其延迟仍可比 Oxbow 低 43%。写吞吐相对 Ext4 为 1.3–4.8×，相对 µFS最高高 86%。每 CPU cycle 处理的字节数相对 µFS 为 1.8–3.9×，相对 Ext4 为 1.3–4.7×；但 10 client append 时，Oxbow 仍使用 5.4 个主机核，Ext4 为 2.9 个，说明“效率更高”不等于“绝对 CPU 最少”（图 9–11、§6.2）。
- **读取体现保留内核服务的收益和代价。** 4 KB 顺序读延迟比 µFS 低 18.2×，主要来自内核预读；但 Ext4 仍低 3%–29%，因为 Oxbow 多了切换和复制。顺序读吞吐比 µFS 高 10.5–18.5×，却比 Ext4 低 0.2%–24%；把预读窗口从 32 页增到 128 页后，Oxbow 才在所有测试点超过 Ext4。4 KB 随机读延迟则比 Ext4 和 µFS 分别低 5.5×、7.7×（§6.2.1–§6.2.2）。
- **Split Journaling 主要缩短 `fsync` 前台等待。** 单 client 下，Oxbow 的 `fsync` 时间相对第二名 µFS 低 16.8–19.2×，相对 Ext4 低约 28.7–34.2×；10 clients 时，对 µFS 的差距缩到 2.0–2.2×，因为 SSD 带宽饱和，后台很难继续领先。消融中，把 D-Server 放回主机会使吞吐最高低 21%、主机 CPU 最高多 44%；去掉 staging 后延迟约为默认版 7.8×；去掉后台日志后吞吐最高低 33%，`fsync` 最多慢 8.8×（表 1、图 12–13、§6.3）。
- **应用结果有明显收益，也有反例。** LevelDB YCSB B/C 中，Oxbow 在 1 process 时比 µFS 高 83%/89%，8 processes 时高 34%/37%；YCSB E 比 Ext4 高 41%/17%。但 YCSB D 的 8-process 情况比 µFS 低 20%，原因是多数读取命中缓存，µFS 的零拷贝更占优。4 GB×5 的 LLM checkpoint 中，Oxbow 为 316.72 MB/s、平均 12.93 s；Ext4 为 200.47 MB/s、23.87 s，即吞吐高 58%、延迟低 46%。400-client RAG 的端到端平均延迟同为约 40 ms，但单次 probe 的 Oxbow 平均延迟为 61 µs，Ext4 为 122 µs（图 14–16、§6.4）。
- **内核互操作不是装饰性功能。** Nginx 开启 `sendfile` 后，Oxbow 吞吐相对自身关闭时提高 3.3×，Ext4 提高 3.6×。首次读取之后数据进入页缓存，两者差距收窄。附录的只读元数据操作也能扩展：10 clients 下 `stat/statall` 相对 µFS 最高为 19×/10×；但 `create/unlink` 等修改操作受内核与 H-Server 协调限制，仍可能落后 Ext4，共享目录上的父目录锁也阻止扩展（§6.5、附录 B）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 按工作性质跨内核、主机用户态和设备分工，可以同时提高写性能与主机 CPU 效率 | 图 10–11：写吞吐相对 Ext4 为 1.3–4.8×，bytes/cycle 相对 µFS 为 1.8–3.9× | BlueField-2 加 SSD 模拟 CSD；不含设备 CPU 与能耗 | 强 |
| Split Journaling 把大部分持久化工作移出 `fsync` 前台 | 表 1、图 12–13：单 client 对 µFS 低 16.8–19.2×；三项消融均出现退化 | 日志空间充足，工作负载能让后台提前运行 | 强 |
| 保留内核预读与 `sendfile` 能带来真实收益 | 顺序读对 µFS 高 10.5–18.5×；Nginx `sendfile` 带来 3.3× | Oxbow 仍可能落后 Ext4；预读窗口经过调优 | 强 |
| fail-stop 故障后可以按 journal 与 staging 顺序恢复 | §4.5 给出恢复协议和空间重建方法 | 没有 crash/fault-injection 实验，也没有恢复时间 | 中偏弱 |

## 批判性分析

### 论证链条

论文最有说服力的地方，是把“不同层各自擅长什么”变成可单独验证的设计。读取实验和 Nginx 支持保留内核服务；写吞吐支持半旁路；host-journaling 消融支持设备卸载；no-staging 与 no-background-journaling 消融支持双路径日志。证据不是只有一个总吞吐数字。

不过，论文把崩溃一致性作为核心贡献之一，相关证据却停在设计推理。§4.5 解释了恢复顺序，但 §6 没有断电、进程崩溃、重复恢复、staging 损坏或 journal/staging 交错故障实验。因此可以说“协议意图保证已 `fsync` 数据恢复”，不能说“实验验证了所有崩溃情况”。

### 假设压力测试

单写者拆分在 `uid/gid/size/mtime` 等字段上容易理解，但 POSIX 语义常跨越字段和对象：`rename` 同时改变两个目录，`link/unlink` 影响链接计数，`truncate` 会与并发 `mmap`、写回和空间回收交错。协议越多，越需要形式化不变量或系统故障注入；论文尚未给出。

Split Journaling 还假设 D-Server 平均能追上前台。若大量 client 同时 `fsync`、设备端算力不足或 checkpoint 被长时间推迟，staging 会积累，前台与设备瓶颈重新耦合。实验特意配置了足够大的 journal 并避免空间耗尽，没有展示这一压力点。

### 实验可信度

基线横跨内核、用户态和设备端三类文件系统；微基准、四类应用、消融和元数据测试也比较完整。论文还明确让 µFS 使用最快的零拷贝模式，并报告 Oxbow 在 YCSB D、顺序读和部分元数据操作上的负面结果，这增强了可信度。

最大的外部有效性问题是“CSD”由 BlueField-2、100 Gbps 网络和共享 NVMe SSD 模拟。真实集成设备的 PCIe 往返、DMA、缓存一致性、设备 CPU、固件和故障行为可能不同。OmniCache artifact 也经过作者改造，无法完全排除实现质量差异。CPU 指标只看主机端，因此不足以证明总能耗或总算力成本更低。

### 系统性缺陷

Oxbow 约 53K 行代码，跨应用库、内核模块、可信主机服务和设备服务，故障面与升级面都比单体文件系统大。应用内 oxLib 负责部分元数据和页状态，即使共享区有权限与验证，恶意或出错应用对协议边界的压力仍需要更强安全测试。

论文展示的是原型级 POSIX 兼容性，不等同于 Ext4 的完整语义、工具链和长期运维成熟度。复杂 `mmap`、direct I/O、quota、长期空间碎片、staging 回收、在线升级和多点故障都缺少系统证据。它解决了性能分工问题，但把一部分复杂度转移成跨组件一致性与运维问题。

## 局限与后续工作

- 在真实集成式 CSD 和不同 DPU/SSD 组合上复现，分别报告主机 CPU、设备 CPU、总能耗和成本。
- 对 H-Server、D-Server、内核和设备的不同崩溃时序做故障注入，测已 `fsync` 数据正确性、恢复时间与重复恢复幂等性。
- 压满 staging 和 journal，测后台落后时的 tail `fsync`、backpressure 与空间回收行为。
- 扩展并验证复杂 POSIX 语义，包括共享目录 `rename/link/unlink`、并发 `mmap/truncate`、direct I/O 和 quota。
- 用长期写密集负载测 extent 碎片、checkpoint lag、元数据扫描成本和设备磨损。

## 相关

- **相关概念**：内核旁路、计算存储、崩溃一致性、日志、VFS、[[NVMe]]、[[PCIe]]、[[RDMA]]
- **相关系统**：[[Ext4]]、µFS、OmniCache、[[SPDK]]
- **同会议**：[[OSDI-2026]]
