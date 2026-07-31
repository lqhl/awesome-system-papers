---
type: paper
name: Oxbow
full_title: "Oxbow: A Coordinated Architecture for Multi-component File Systems"
authors: [Jongyul Kim, Jaehwan Lee, Inhoe Koo, Peizhe Liu, Jiyuan Zhang, et al.]
venue: OSDI
year: 2026
tags: [file-system, computational-storage, kernel-bypass, journaling, crash-consistency]
source_pdf: "[[osdi26-kim-jongyul.pdf]]"
source_md: "[[osdi26-kim-jongyul]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向多组件文件系统的协同架构（OSDI 2026）

> **原题**：Oxbow: A Coordinated Architecture for Multi-component File Systems

> **一句话总结**：Oxbow 不在kernel、user space和computational SSD之间三选一，而让read走kernel cache/readahead、write绕kernel、metadata按field单写者分权、crash consistency异步下沉设备；写吞吐最高为Ext4的4.8×、比µFS高86%，host CPU最多少55%。

## 问题与动机

高速SSD让kernel I/O path变成CPU瓶颈；user-level FS绕过kernel得到低latency，却失去VFS/page cache/readahead/sendfile、isolation和全局sharing。device-resident FS节省host CPU，但受PCIe RTT与弱ARM core限制。Oxbow认为问题不是选唯一execution domain，而是将foreground fast path、kernel services与background consistency按各自特性分配，同时避免跨组件shared mutable state。

## 关键观察 / 隐含假设

- **观察 1**：kernel对read价值高（page cache、readahead、sendfile），对write common path则常是额外crossing/copy；读写应采用不同路径（§3–§4）。
- **观察 2**：inode各attribute可按更新者拆分ownership，例如user-level拥有size/mtime、kernel拥有uid/gid；single-writer field避免common-path synchronization。
- **观察 3**：journaling/checkpoint是CPU-intensive background work，适合CSD；但fsync不能等待慢device commit，需独立staging durability path（§4.4）。
- **依赖假设**：metadata fields之间可安全拆分，跨field invariant能通过协议维持；CSD/DPU具有DMA与独立persistent area。

## 核心方法

Oxbow含四组件：application-linked oxLib暴露fast/application-aware API；trusted H-Server执行核心FS logic；thin kernel illuFS接入VFS/page cache与protection；D-Server在CSD上执行journaling/checkpoint。read/page fault走kernel以复用cache/readahead，write由oxLib→H-Server→device绕过kernel（§3–§4.3）。

Shared-ownership metadata把每个field交给唯一writer，降低component coordination。Split Journaling将fsync transaction写入host驱动的on-disk staging area后即可返回；D-Server在background把transaction合并进journal/checkpoint。DMA snapshot把buffer变成shadow copy，让application继续写而device处理稳定版本。核心crash invariant是：每个fsync-ed file都能仅从self-contained staging transaction恢复（§4.4–§4.5）。

实现约53K C/C++，以BlueField-2 DPU和支持SR-IOV SSD模拟CSD；若D-Server不可用，也可在host运行以维持availability（§5）。

## 设计取舍

- **semi-bypass换两套path**：得到read kernel services/write speed，但共享/一致性逻辑比单domain FS复杂。
- **field-level ownership换低同步**：common path更快，跨attribute operation（rename/truncate/permission）需要显式transaction协调。
- **staging换低fsync latency**：增加persistent space、recovery与background [[Garbage-Collection|GC]]；必须保证staging self-contained。
- **device offload换host CPU**：性能受DPU compute与[[PCIe|PCIe]]/DMA行为影响，真实CSD差异大。

## 实验与结果

- 对比Ext4、µFS与OmniCache，CSD由BlueField-2（8×2.0 GHz ARMv8 A72）与SR-IOV SSD模拟（§6.1）。
- microbenchmark写吞吐为Ext4的1.3×–4.8×，最高比µFS高86%；host CPU最多比µFS少55%，bytes-per-CPU效率为µFS的1.8×–3.9×、Ext4最高4.7×（§6.2）。
- 单client下split journaling使fsync time比Ext4低16.8×–19.2×；µFS小写仍可因application直用SPDK buffer而比Oxbow latency低最高43%，显示额外copy代价（表 1、§6.2）。
- LevelDB YCSB read/range-heavy workload相对µFS最高+89%、Ext4最高+41%；8 processes时优势缩至+37%/+17%，体现扩展边界（§6.4）。
- 复用kernel sendfile使Nginx throughput比禁用该路径高3.3×，直接验证保留VFS interoperability的价值（§6.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| coordinated architecture兼得高写吞吐与低host CPU | §6.2 | emulated CSD、microbenchmarks | 强 |
| split journaling解耦foreground fsync | 表 1、ablation | 指定write/fsync patterns | 强 |
| kernel interoperability带来应用收益 | §6.5 | Nginx/sendfile | 强 |
| 真实KV workload优于主要baselines | §6.4 | LevelDB YCSB | 中 |
| crash后所有fsync data可恢复 | §4.5设计与测试 | 指定failure model | 中 |

## 批判性分析

### 论证链条

Oxbow最强的抽象是按operation property而非layer边界分工：read需要kernel ecosystem、write需要bypass、background consistency需要device。sendfile、CPU efficiency与split-journal ablation分别支持三项设计，而不只是给出总吞吐。

### 假设压力测试

metadata single-writer在简单attribute上成立，但rename/link/unlink、quota、mmap、concurrent truncate等跨组件invariant会暴露复杂协调。background journal若长期落后，staging占满后fsync会重新受device吞吐限制。DPU与host/device failure组合会挑战recovery ordering。

### 实验可信度

baseline覆盖kernel/user/device三类，micro、LevelDB、Nginx与checkpoint较丰富；但核心硬件是DPU+SSD模拟CSD，不代表commercial computational SSD latency/bandwidth/coherence。µFS为追求zero-copy暴露SPDK buffer，接口差异也影响公平比较。

### 系统性缺陷

53K LoC和四组件扩大trusted computing base与operational failure surface。论文的POSIX/semantic覆盖并未等同成熟Ext4；没有长期fragmentation、staging GC、multi-process mmap和复杂namespace workload的完整证据。offload节省host CPU，但DPU energy与总系统成本未计入。

## 局限与后续工作

- 在真实CSD与不同DPU/PCIe generation复现实验，并报告总能耗与设备CPU占用。
- 对compound metadata operations、mmap/direct I/O、staging exhaustion和多点crash做model checking/fault injection。
- 长期运行metadata-heavy workload，测fragmentation、checkpoint lag、recovery time与tail fsync。

## 相关

- **相关概念**：[[Kernel-Bypass]]、[[Computational-Storage]]、[[Crash-Consistency]]、[[Journaling]]、[[VFS]]
- **相关系统**：[[Ext4]]、[[µFS]]、[[OmniCache]]、[[SPDK]]
- **同会议**：[[OSDI-2026]]
