---
type: paper
name: Arca
full_title: Continuation-Centric Computing with Arca
authors: [Akshay Srivatsan, Yuhan Deng, Katherine Mohr, Emma Sudo, Sebastian Ingino, Francis Chua, Keith Winstein]
venue: OSDI
year: 2026
tags: [serverless, continuations, isolation, operating-systems, fine-grained-scheduling]
source_pdf: "[[osdi26-srivatsan.pdf]]"
source_md: "[[osdi26-srivatsan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-24
---

# 面向延续的计算与 Arca（OSDI 2026）

> **原题**：Continuation-Centric Computing with Arca

> **一句话总结**：论文观察到，细粒度 serverless 工作负载常在计算与外部 I/O 之间反复切换；Arca 把“捕获程序剩余执行状态”做成内核原语，使 I/O 边界自动形成可迁移的纯计算 funclet，捕获并原地恢复只需 2.55 µs，并在跨节点图像缩略图实验中将吞吐从 9.42 提高到 557.3 requests/s。

## 问题与动机

现有 serverless 系统在兼容性与调度粒度之间取舍。容器和 MicroVM 能运行更广泛的程序，但创建、销毁和快照成本高；WebAssembly 等轻量隔离方式更快，却要求程序遵守更窄的接口。另一条路线要求开发者预先把程序拆成纯计算函数和 I/O 操作，才能让调度器看到细粒度依赖。

论文提出 continuation-centric computing：程序在 I/O 边界捕获“从当前位置继续执行所需的状态”，把它作为新的可暂停、复制和迁移函数。这样，开发者仍可按逻辑任务编写程序，运行时则能按更小的计算单元调度。Arca 是验证这一想法的研究型操作系统，面向状态主要位于内存和寄存器、外部副作用通过 effect handler 表达的程序。

## 关键观察 / 隐含假设

- **观察 1：传统进程或虚拟机快照不适合高频 I/O 边界。** Linux CRIU 和 Firecracker 的快照/恢复成本随状态规模增长，基线还包含较大的地址空间和全局 OS 状态；论文在图 3 中测得 Arca 原地捕获与恢复为 2.55 µs。
  - **依赖假设**：大多数 continuation 可以在同一节点上直接恢复，或者其复制、压缩和网络传输成本小于传输原始数据的成本。
  - **可能失效场景**：continuation 很大、需要频繁迁移，或包含无法序列化的外部状态时，Arca 的优势会下降。
- **观察 2：细粒度 serverless 任务的资源需求随时间变化，数据位置可能比代码位置更重要。** 图像缩略图实验中，传统方案 98% 的时间花在跨节点传输图像，continuation-centric 方案只花 9% 的时间传输 continuation，并在目标数据节点执行计算。
  - **依赖假设**：任务的计算状态明显小于其输入数据，且 effect handler 能把 continuation 放到数据所在节点。
  - **可能失效场景**：输入很小、计算状态很大，或数据无法迁移/访问时，移动 continuation 未必优于移动数据。
- **假设 1：程序可以被限制为无共享可变内存、有限 POSIX 接口和显式外部副作用。** 论文实现的 Arca 不支持共享内存线程、`mmap`、`shm_open` 和 `clone`；网络 socket 也会限制完整迁移。
  - **证据强度**：强。限制直接出现在系统调用支持表、兼容性实验和局限性章节中。

## 核心方法

Arca 将进程状态表示为页表、寄存器文件和 value descriptor table。descriptor 中保存 blob、tuple、page、page table 或 funclet 等值，而不是 Unix 文件描述符指向的隐含内核对象。funclet 通过参数消费值、返回值或 effect，与传统进程依靠文件描述符和共享状态通信不同。

`call_cc` 是核心系统调用。它捕获当前地址空间的执行状态，并在通常的回调场景中保留 continuation 的内存表示，避免无谓复制。捕获发生在 libc 的 I/O 实现内部，因此普通 C/POSIX 程序不需要显式写 continuation-passing style。I/O 请求以 effect 返回给父进程或 effect handler；handler 完成操作后再调用保存的 continuation。

Arca 的 effect handler 还承担 API 适配职责。WASI 程序可经 `wasm2c` 转成 C，再链接 Arca 版 musl；WASI 的文件和网络调用转化为 POSIX 调用，最终变成 provider-specific effect。论文用 FFmpeg WASI 二进制验证了这一机械转换路径，移植 WASI shim 约需一名开发者两周的兼职工作。

隔离方面，Arca 使用硬件内存保护，当前以内核在 KVM 中半虚拟化运行。它禁止高精度计时器访问，并让程序只能通过显式 effect 产生副作用。这个模型接近 Cloudflare Workers 的沙箱约束，但把 continuation 捕获提升为 OS 服务。

## 设计取舍

- **放弃部分 POSIX 兼容性以换取可捕获状态。** 文件 I/O 和部分网络 I/O 可支持，但共享可变内存、共享内存线程和依赖持久 socket 状态的程序无法完整迁移。论文支持的 FFmpeg 说明兼容性可做，但不能代表任意 Linux 应用。
- **用 continuation 迁移代码状态以换取数据局部性。** 图像实验显示了明显收益，但迁移成本依赖 continuation 大小、压缩成本和目标节点恢复成本。
- **依赖不可变/线性值语义降低复制成本。** “functional but in-place” 优化在值唯一时原地修改，否则执行复制；这简化了状态管理，却把性能依赖放在别名和共享状态受控的前提上。
- **采用过程式 OS 抽象而非传统消息式抽象。** 函数调用与返回值使 funclet 组合自然，但长生命周期调用栈、复杂调试和现有进程间通信语义不再直接存在。

## 实验与结果

- 在 2×64-core AMD EPYC 7702、128 个物理核的机器上，Arca 原地 snapshot+resume 固定为 2.55 µs；复制 continuation 时随内存规模线性增长，但仍比 Linux CRIU 和 Firecracker 快一个数量级以上（图 3，§6.1）。
- 在 sandbox 创建/销毁测试中，单线程 Arca 约 5 µs；256 路并行时约 30 µs，而 Wasmtime 约 200 µs、Linux process 约 6 ms、每次创建 MicroVM 的 FCKVM 约 30 ms（图 4，§6.2.1）。
- 在 128×128 整数矩阵乘、32 路并行的开放负载测试中，Arca 可稳定支撑约 17,000 requests/s，接近无隔离基线的 18,000；Wasmtime 为 15,000，DKVM 为 10,000，Linux process 为 1,000（图 5，§6.2.2）。
- 在 AWS c6a.metal 跨节点图像缩略图实验中，continuation-centric 方案吞吐为 557.3 requests/s，传统方案为 9.42 requests/s；一半请求需要远端数据时，结果分别为 889.62 和 18.21 requests/s（图 6，§6.3）。
- 在静态 HTTP 服务中，Arca 的 pooled 模式与 Apache 延迟相近；individual 模式相对 Apache CGI 的请求延迟约低四倍（表 4，§6.4）。但该结果使用简单的 `hello, world` 响应，不能代表复杂应用。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| continuation 可作为高频 OS 原语使用 | Arca 原地 snapshot+resume 为 2.55 µs（图 3） | 单线程循环、x86_64、KVM 内 Arca；复制和迁移成本另行增长 | 强 |
| Arca 是高并发轻量隔离机制 | 256 路创建/销毁约 30 µs，矩阵乘稳定吞吐 17,000 requests/s（图 4–5） | 特定硬件、短计算任务；长任务会改变创建开销占比 | 中 |
| 移动 continuation 能改善数据局部性 | 跨节点缩略图吞吐 557.3 对 9.42 requests/s（图 6） | 输入图像远大于 continuation，单线程节点循环，Arca provider-native API | 中 |
| 现有 WASI 软件可迁移到 Arca | FFmpeg WASI 二进制成功转码，shim 约两周兼职开发（§6.5） | 单个 compute-heavy 程序；未覆盖共享内存和复杂网络应用 | 中 |

## 批判性分析

### 论证链条

论文的主要链条是闭合的：快照系统包含大量难以迁移的 OS 状态，Arca 将进程限制为可描述的值和内存状态，因而能低成本捕获；I/O 被改写为 effect 后，continuation 既可以作为回调，也可以随数据位置迁移。微基准、隔离负载和跨节点应用分别验证了这三段链条。

但跨节点实验同时改变了数据传输方向和执行位置，结果不能单独证明 continuation 在一般工作负载中优于数据移动。实验刻意选择 continuation 小于图像的场景，论文也承认这是 extreme case。Arca 的调度器、租户隔离策略、故障恢复和计费系统尚未实现，因此“serverless 系统”的结论主要是 substrate 可行性，而不是完整平台结论。

### 假设压力测试

最强假设是 continuation 状态保持小且可序列化。共享内存线程、socket 缓冲区、DMA、kernel bypass 和大型持久状态都会破坏这一点。若应用使用线程池并行，直接移植可能退化为单线程；若改用 provider 并行原语，则需要额外重构。

Arca 的安全模型依赖所有副作用经过 provider 控制。任意网络访问可能重新引入高精度计时器或数据外泄通道。论文描述了风险，但没有给出恶意 workload 下的隔离攻击评测。

性能结果也依赖短任务和高并发。图 4 的 noop 测试能突出创建开销，却不代表长时间运行时的内存分配、调度和 effect handler 争用。图 5 只使用矩阵乘，未覆盖多租户、尾延迟、内存压力和失败重试。

### 实验可信度

基线覆盖了共享对象、Wasmtime、进程和虚拟化，能定位隔离开销的数量级差异；Arca 与 Wasmtime 的比较尤其有意义，因为二者都追求轻量隔离。不过，Arca 在 KVM 内运行、其他系统多在 Linux 直接运行，虚拟化路径可能影响绝对延迟和方差。论文给出多个硬件平台和稳定性判据，但没有提供云平台价格、内存占用、故障恢复或长期运行数据。

### 系统性缺陷

论文未实现完整的调度和放置运行时、访问控制、监控、资源分配、计费与用户界面。调试组合后的 logical function 更困难，因为内核不维护长期调用栈。网络 socket 只在固定机器上恢复，削弱了迁移收益。论文也未讨论 continuation 泄漏、版本兼容、压缩失败、节点故障期间的重试语义和跨租户缓存隔离。

## 局限与后续工作

- **局限 1：共享可变内存线程不受支持。** 需要测量将线程池改写为 provider-level 并行后，对同步、尾延迟和开发成本的影响。
- **局限 2：Arca 仍是 OS 原型而非生产 serverless 平台。** 后续实现应给出可复现实验的调度器、租户资源配额、失败恢复和计费路径，并报告 p99 延迟与内存成本。
- **局限 3：continuation 复制和迁移的成本只被部分覆盖。** 应在 continuation 大小、压缩算法、网络带宽和数据大小的二维矩阵上寻找移动 continuation 与移动数据的交叉点。
- **局限 4：长期服务和持久状态支持不足。** 可将 continuation 与微服务结合，测量持久连接、增量状态检查点和故障恢复对迁移收益的影响。

## 相关

- **相关概念**：[[Continuations]]、[[Serverless Computing]]、[[WebAssembly]]、[[I/O-Compute Separation]]
- **同类系统**：[[Fix]]、[[Dandelion]]、[[Wasmtime]]、[[Firecracker]]、[[SigmaOS]]
- **同会议**：[[OSDI-2026]]
