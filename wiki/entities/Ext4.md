---
type: entity
kind: tool
aliases: [EXT4, Fourth-Extended-Filesystem]
status: active
last_updated: 2026-08-14
tags: [filesystem, linux, storage]
---

# Ext4

> Ext4 是 Linux 成熟的 journaling 文件系统，也是新文件系统、内核旁路、缓存、完整性和解聚存储工作最常使用的兼容性与性能基线。

## 是什么

Ext4 通过 extent 管理文件块，用 JBD2 journal 保护 metadata 更新，并深度集成 VFS、page cache、readahead、`mmap`、`sendfile` 和 Linux 工具生态。它不是为最新 NVMe、CXL 或远程 SSD 专门设计的，但部署广、语义稳定，因此特别适合回答一个问题：新系统为了更快，到底绕过了哪些成熟能力？

论文对 Ext4 的使用大致分三类：把它当作传统内核基线；保留 Ext4 的 metadata/control plane，只替换数据路径；从真实 commit 和 bug 历史中研究复杂文件系统为何难以维护。比较 Ext4 时必须明确 mount 选项、buffered/direct I/O、journal mode、设备和 workload，单个吞吐倍数不能代表完整文件系统能力。

## 关键观察 / 隐含假设

- **高速设备会把软件路径变成瓶颈。** [[WSBuffer-FAST26]] 发现 page-cache 管理和 `xa_lock` 会压过高带宽 NVMe；[[UnICom-FAST26]] 则表明 polling/interrupt 的选择会随 CPU 负载改变。
- **内核路径的价值不只在数据搬运。** [[Oxbow-OSDI26]] 的读取继续利用 VFS、page cache 和 readahead，写入才绕过内核；保留这些能力会增加组件协议，但避免从头重做成熟读取路径。
- **远程块设备会放大锁与层次开销。** [[CetoFS-FAST26]] 在 NVMe-oF 上测得传统内核路径占明显延迟，并让 inode lock 串行等待网络 RTT；它保留 Ext4 metadata 管理，把数据 read/write 与部分权限、并发控制下沉到 target。
- **设备功能只有被文件系统使用才有价值。** [[FS-PI-FAST26]] 指出 Ext4 能校验 metadata，却没有自然利用设备 PI 为用户数据提供端到端校验；block-layer 支持本身不等于文件系统语义完整。
- **兼容 Ext4 metadata 会限制 userspace cache。** [[uCache-FAST26]] 的 MiniFS 让 Ext4 提供打开与 LBA 查询，但只支持预分配、非 sparse、打开期间不变的文件；高性能来自缩小语义范围。
- **复杂度和稳定化成本是真实设计约束。** [[SysSpec-FAST26]] 统计 Ext4 长期 commit，发现大量工作是 bug fix 和维护；生成一个功能与把它安全合入成熟内核不是同一个问题。

## 演进时间线

- **成熟 Linux 基线**：Ext4 以 extent、JBD2 和完整 VFS 集成承担通用本地文件系统角色。
- **2026 FAST 数据路径重构**：[[WSBuffer-FAST26]]、[[UnICom-FAST26]]、[[uCache-FAST26]] 分别从 buffered write、poll/interrupt 和 userspace cache 重审 Ext4 路径。
- **2026 FAST 远程与完整性**：[[CetoFS-FAST26]] 将 Ext4 control plane 与远程 userspace data plane 组合；[[FS-PI-FAST26]] 用 Ext4 的缺口说明文件系统尚未完整接入设备 PI。
- **2026 OSDI 组件化**：[[Oxbow-OSDI26]] 按读、写、日志和设备工作拆分职责，既以 Ext4 为性能对照，也保留其内核生态。
- **维护性研究**：[[SysSpec-FAST26]] 用 Ext4 的二十年演化说明文件系统 feature 的长期修复成本，并探索 specification-driven generation。

## 相关概念

- 日志（journaling）
- 虚拟文件系统（VFS）
- 页缓存（page cache）
- 崩溃一致性（crash consistency）
- 内核旁路（kernel bypass）

## 相关论文

- [[Oxbow-OSDI26]] — 将读取留在内核、写入旁路并把日志工作下沉设备。
- [[CetoFS-FAST26]] — 在 NVMe-oF 上保留 Ext4 metadata/control plane，重做远程数据路径。
- [[WSBuffer-FAST26]] — 量化 Ext4 等文件系统的 page-cache 写入瓶颈。
- [[UnICom-FAST26]] — 在内核中协调 polling 与 interrupt，并以 Ext4 为基线。
- [[uCache-FAST26]] — 复用 Ext4 metadata 的轻量 userspace cache/file path。
- [[FS-PI-FAST26]] — 讨论 Ext4 用户数据缺少设备 PI 保护的系统边界。
- [[SysSpec-FAST26]] — 从 Ext4 commit 历史研究维护成本和 specification-driven generation。

## 已知局限 / 开放问题

- 新路径要明确保留或放弃哪些 POSIX、mmap、sendfile、稀疏文件、权限和 crash semantics。
- NVMe-oF、计算存储和 userspace bypass 把 trust boundary 移到 target/runtime，需要故障注入和安全审计。
- 只在预分配、低碎片文件上的 extent/LBA cache 结果不能外推到长期运行的通用文件系统。
- Ext4 feature 的生成或移植仍要面对并发、恢复、升级和数年维护，短 benchmark 不能替代这些证据。
