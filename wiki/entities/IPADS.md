---
type: entity
kind: org
aliases: [IPADS, "SJTU IPADS", "Institute of Parallel and Distributed Systems", "上海交通大学并行与分布式系统研究所", "上海交大 IPADS"]
status: active
last_updated: 2026-08-20
tags: [operating-systems, distributed-systems, storage, architecture, ai-infra]
---

# SJTU IPADS

> 上海交通大学并行与分布式系统研究所（Institute of Parallel and Distributed Systems，IPADS）覆盖操作系统、分布式与数据库系统、体系结构和人工智能系统；本页汇总其官方论文目录中可与仓库对应的 32 篇论文。

## 是什么

[IPADS 官方研究说明](https://ipads.se.sjtu.edu.cn/)把研究范围定义为操作系统、分布式系统和数据库系统，并延伸到体系结构、语言与编译器及人工智能的跨层协同设计。它不是单一项目组；DNA 存储、GPU 容错、CXL 操作系统和智能体运行时之间不共享工作负载，组织页的作用是追踪反复出现的系统方法。

本页以[IPADS 官方论文目录](https://ipads.se.sjtu.edu.cn/pub/publication)为归属依据，并与仓库论文页的完整标题对应；目录中的 Skill VM 在仓库中对应 [[SkVM-SOSP26]]。当前共有 32 篇在库论文。[[He-GPUKernelFusion-SOSP26]]、[[ProbeFS-SOSP26]] 与 [[StarfishOS-SOSP26]] 目前只有元数据页，其余均有全文证据。

## 在库研究版图

### 人工智能基础设施与加速器

- [[BlitzScale-OSDI25]] — 用计算互连转发、全局主机缓存和分层实时扩容降低大模型服务冷启动。
- [[DiffKV-SOSP25]] — 按 K/V、词元和注意力头差异化压缩 KV 缓存，并在 GPU 上并行整理碎片。
- [[HeteroInfer-SOSP25]] — 联合移动端 GPU、NPU 和统一内存执行异构大模型推理。
- [[KVCacheInTheWild-ATC25]] — 从云端生产轨迹刻画真实 KV 复用，并设计工作负载感知淘汰策略。
- [[LMetric-OSDI26]] — 用待处理新词元数与批量大小的乘积统一路由局部性和负载。
- [[SolidAttention-FAST26]] — 为内存受限个人计算机联合设计稀疏注意力、SSD KV 布局和微任务调度。
- [[AITurbo-FAST26]] — 用分组读写接口、主机内存和计算互连加速云端 AI 检查点与 KV I/O。
- [[FlowANN-OSDI26]] — 把图向量搜索的短边留在 GPU、长边放在主机，并延后非关键依赖。
- [[Sereno-OSDI26]] — 以推测解码让出点协调手机前台应用与后台大模型的内存带宽。
- [[Sirius-ATC25]] — 在训练和推理之间快速移交 GPU 内存，维持推理服务目标。
- [[SAVE-ATC25]] — 依据位翻转脆弱性分级放置模型状态，软件实现 GPU 推理容错。
- [[SDCHunter-OSDI26]] — 保存训练执行状态并确定性重放，定位生产集群中的静默数据损坏 GPU。
- [[XSched-OSDI25]] — 用统一抢占队列和分层硬件模型调度多种 XPU。

### 操作系统、运行时与可靠性

- [[Copier-SOSP25]] — 将异步内存复制提升为一等操作系统服务，联合调度向量指令和 DMA。
- [[PhoenixOS-SOSP25]] — 用推测—验证补齐 GPU 页状态可观测性，实现并发检查点与恢复。
- [[Spars-OSDI25]] — 并行执行图形系统服务，并按重叠关系有序提交结果。
- [[jwmalloc-OSDI26]] — 用统一页级 slab 和生命周期回收构建经过验证的移动端内存分配器。
- [[uEFI-ATC25]] — 将不可信 UEFI 模块放入独立地址空间，并透明转发协议调用。
- [[vBPF-OSDI26]] — 对 eBPF hook 做后期绑定，为每个租户提供独立程序和状态视图。
- [[SkVM-SOSP26]] — 把智能体技能视为程序，按模型、框架和环境能力生成目标版本。
- [[He-GPUKernelFusion-SOSP26]] — 题名指向动态 GPU 工作负载下的跨 SM 内核融合；当前只有元数据。

### 存储、解聚内存与文件系统

- [[LiqSD-FAST25]] — 用 SSD 中的一级映射和 DNA 中的二级映射构造超大容量 DNA 块设备。
- [[ProbeFS-SOSP26]] — 从 DNA 块设备推进到层级文件系统和生化并行；当前只有元数据。
- [[SysSpec-FAST26]] — 用 Hoare 逻辑、依赖—保证规约和并发协议指导大语言模型生成并演化 SPECFS。
- [[RASK-FAST26]] — 将连续范围直接编码为键，降低云块存储索引内存并提高吞吐。
- [[FalconFS-NSDI26]] — 面向自动驾驶训练的数百 PB 小文件数据，将路径解析移到服务端。
- [[ODRP-NSDI25]] — 在商品网卡上编排可自修改工作请求，实现按需远程换页。
- [[OneSidedMW-NSDI26]] — 让网卡直接绑定内存窗口，兼顾解聚内存性能、弹性和隔离。
- [[DGC-OSDI26]] — 把垃圾回收标记阶段解聚到共享服务，并错开多个运行时的资源突发。
- [[StarfishOS-SOSP26]] — 题名指向 CXL 单系统映像与状态分区微内核；当前只有元数据。

### 云与无服务器计算

- [[AFaaS-OSDI25]] — 从蚂蚁生产轨迹出发，以资源池化和树形种子优化函数冷启动。
- [[Quark-OSDI26]] — 把长寿命批处理执行器改成任务级按需实例，减少空闲资源和阶段不平衡。

## 关键观察 / 隐含假设

- **观察：新硬件的粒度错配会迫使系统重做映射层。** [[LiqSD-FAST25]] 面对 DNA 写、读和擦除粒度错配，[[OneSidedMW-NSDI26]] 面对网卡内存窗口语义，[[PhoenixOS-SOSP25]] 面对 GPU 缺少页状态；三条路线都先构造新的状态映射，再保留块设备、换页或检查点等上层接口。
- **观察：生产轨迹是 IPADS 多条路线的设计起点。** [[KVCacheInTheWild-ATC25]]、[[LMetric-OSDI26]]、[[AFaaS-OSDI25]]、[[Quark-OSDI26]] 和 [[SDCHunter-OSDI26]] 分别从真实请求、批处理和故障数据提取约束，收益因此依赖原始平台的负载分布和硬件配置。
- **观察：系统正确性需要从“检测结果”前移到“保存执行语义”。** [[SAVE-ATC25]] 按位脆弱性保护模型，[[SDCHunter-OSDI26]] 固定随机数与通信顺序，[[jwmalloc-OSDI26]] 和 [[uEFI-ATC25]] 则缩小可验证状态空间；这些方法都不把一次测试通过当作完整正确性证明。
- **观察：人工智能同时是工作负载和系统构建工具。** [[SolidAttention-FAST26]]、[[DiffKV-SOSP25]] 等优化大模型执行；[[SysSpec-FAST26]] 和 [[SkVM-SOSP26]] 则让大语言模型参与生成文件系统或编译技能。
- **证据边界：接收信息不能替代全文。** [[He-GPUKernelFusion-SOSP26]]、[[ProbeFS-SOSP26]] 和 [[StarfishOS-SOSP26]] 当前只支持题名级分类，不能据此补写机制或性能。

## 演进时间线

- 2025：在库工作覆盖 DNA 存储、远程换页、GPU 容错、异构推理、云端 KV 管理和系统服务并行化。
- 2026 FAST、NSDI：形成生成式文件系统、AI 存储、SSD KV、云块索引、训练文件系统和解聚内存路线。
- 2026 OSDI、SOSP：进一步扩展到生产可靠性、移动端推理、eBPF 虚拟化、CXL 操作系统和智能体技能运行时。

## 相关系统

- [[LiqSD-FAST25|LiqSD]]、[[PhoenixOS-SOSP25|PhoenixOS]]、[[SkVM-SOSP26|SkVM]]、[[SysSpec-FAST26|SysSpec]]、[[FalconFS-NSDI26|FalconFS]]

## 相关概念

- [[KV-Cache]]、[[NVMe]]、[[RDMA]]、[[CXL]]、[[Garbage-Collection]]、[[eBPF]]、形式化方法、[[Long-Horizon-Agents]]

## 相关论文（在库完整集合）

- 人工智能基础设施：[[AITurbo-FAST26]]、[[BlitzScale-OSDI25]]、[[DiffKV-SOSP25]]、[[FlowANN-OSDI26]]、[[HeteroInfer-SOSP25]]、[[KVCacheInTheWild-ATC25]]、[[LMetric-OSDI26]]、[[SAVE-ATC25]]、[[SDCHunter-OSDI26]]、[[Sereno-OSDI26]]、[[Sirius-ATC25]]、[[SolidAttention-FAST26]]、[[XSched-OSDI25]]
- 操作系统与运行时：[[Copier-SOSP25]]、[[He-GPUKernelFusion-SOSP26]]、[[jwmalloc-OSDI26]]、[[PhoenixOS-SOSP25]]、[[SkVM-SOSP26]]、[[Spars-OSDI25]]、[[uEFI-ATC25]]、[[vBPF-OSDI26]]
- 存储与解聚：[[DGC-OSDI26]]、[[FalconFS-NSDI26]]、[[LiqSD-FAST25]]、[[ODRP-NSDI25]]、[[OneSidedMW-NSDI26]]、[[ProbeFS-SOSP26]]、[[RASK-FAST26]]、[[StarfishOS-SOSP26]]、[[SysSpec-FAST26]]
- 云计算：[[AFaaS-OSDI25]]、[[Quark-OSDI26]]
