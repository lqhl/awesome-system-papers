---
type: paper
name: DPA-Store
full_title: DPA-Store: An Ordered Network Data Path Key-Value Store
authors: [Frederic Schimmelpfennig, Jan Sass, Reza Salkhordeh, Martin Kröning, Stefan Lankes, André Brinkmann]
venue: OSDI
year: 2026
tags: [smartnic, dpu, key-value-store, learned-index, range-query]
source_pdf: "[[osdi26-schimmelpfennig.pdf]]"
source_md: "[[osdi26-schimmelpfennig]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-10
---

# 面向有序网络数据路径的键值存储（OSDI 2026）

> **原题**：DPA-Store: An Ordered Network Data Path Key-Value Store

> **一句话总结**：DPA-Store 将 learned index tree 的遍历放到 BlueField-3 的 DPA 上，借助 NIC 侧缓存和叶级 DMA 同时支持无状态客户端与 RANGE；在 100 Gb/s、50M 级数据集上达到 GET 33 MOPS、RANGE 13 MOPS，但 INSERT 只有 1.7 MOPS，瓶颈是 host-to-DPA 写入路径。

## 问题与动机

远程 KV store 若需要 RANGE，通常依赖有序树。Redis、Memcached 受内核网络栈和 NIC-host 交互限制；SmartNIC 上的哈希表能获得高吞吐，却放弃范围查询；RDMA 树存储则把索引元数据和故障处理部分推给有状态客户端。HONEYCOMB 虽支持有序访问，但遍历主机内存树会产生多次 DMA 往返。

DPA-Store 的目标是在 SmartNIC 数据路径直接处理请求，让客户端只负责发包和重试。论文的核心边界是：BlueField-3 的 DPA 内存容量和访问延迟仍然有限，因此索引放 NIC、值放主机，复杂更新也放主机。

## 关键观察 / 隐含假设

- **观察 1**：DPA 内存访问平均约 465 ns，远慢于普通 CPU DRAM；连续窗口扫描比 B+树节点内多次随机 cache-line 访问更适合 DPA（§2.3、§3）。
  - **依赖假设**：键分布可以由分段线性模型以较小误差拟合。
  - **可能失效场景**：分布突变或 ε 被迫增大时，扫描和元数据开销会削弱 learned index 优势；论文在 osmc 上观察到 B+树可胜过 ε=16 的配置（图 12）。
- **观察 2**：热点访问可避免树遍历和 DMA。每个 traverser 使用 96 项缓存，α=1 的 Zipf 负载下缓存覆盖超过一半请求，但随机准入的实际命中率约 25%（§3.1.2）。
  - **依赖假设**：请求具有稳定偏斜，且按键哈希到固定 home thread 不会造成严重热点线程过载。
- **假设 3**：UDP 丢包由客户端重试即可接受。系统不保存去重状态，因此写请求不提供 exactly-once；冲突写的顺序需由客户端串行化（§3.1.3）。证据强度：强，论文明确给出语义限制。

## 核心方法

DPA-Store 使用 176 个 traverser 线程处理 UDP 请求。NIC 侧 learned index tree 的 inner node 使用 PLA（piecewise linear approximation）模型，默认 ε_inner=4；叶节点使用 ε_leaf=8。模型预测位置后只扫描连续窗口，GET 在叶级通过 DMA 读取主机树副本中的键和值。RANGE 跨叶时重新下降到后继叶，单个响应最多携带 64 个 KV 对（图 3、图 4）。

INSERT、UPDATE、DELETE 先写入叶级 16 项 insert buffer。新值在后续读取中立即可见。buffer 满后，主机 patcher 合并数据、重训受影响子树并完成分裂；DPA stitcher 再以 COPY/CONNECT 命令安装新节点。节点不原地修改，使用 RCU 式指针交换和 epoch reclamation，使 traverser 无锁遍历（§3.2）。

热点缓存由三路 Bloom filter 和按线程拥有的哈希表组成。客户端按键选择 UDP 端口，使同一键通常由同一 traverser 处理，避免缓存失效广播。被重路由到非 home thread 的请求绕过缓存，以换取热点键过载时的吞吐恢复。

## 设计取舍

- **NIC 侧索引、主机侧值副本**：减少树遍历中的 DMA 次数，但每次叶级 miss 仍跨 PCIe；更新需要维护两份结构。
- **主机 patch、DPA stitch**：把模型重训和节点分裂移出数据路径，保持读取无锁；代价是 INSERT 受 host-to-DPA 写带宽限制。
- **UDP + 客户端重试**：适配事件驱动 DPA 的有限上下文，避免实现 TCP 状态机；代价是丢包、重复写和顺序控制交给客户端。

## 实验与结果

- 在 100 Gb/s、BlueField-3 B3140L、50M 级 SOSD 数据集上，GET 达到 33 MOPS，RANGE 达到 13 MOPS，INSERT 仅 1.7 MOPS（摘要、§4）。
- 176 traverser、4 patcher、4 stitcher 是默认配置；继续增加 traverser 后 GET 基本趋于饱和，DPA 硬件调度使 traverser 与 stitcher 共用一个物理核时 INSERT 吞吐下降 14%（图 9）。
- 预取优化使 GET 性能提升 19%；树深从 3 增至 4 时吞吐略降。偏斜负载下热点缓存最多带来约 30% GET 吞吐提升，但尾延迟因线程不均衡上升（图 11）。
- 与 ROLEX 对比，DPA-Store 在 sparse、amzn 的 GET 以及所有 RANGE-only 工作负载中通常更快、延迟更低；ROLEX 在 INSERT 上更快，在 osmc GET 上因更大的 ε 更合适而胜出（图 15）。
- 将假设的 DPA 内存访问延迟降到 100 ns，模型预测 GET 吞吐可超过 62 MOPS；这是硬件前景分析，不是当前系统实测（§4.2.6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| SmartNIC 可以在保持客户端无状态的同时支持有序 RANGE | DPA 结构与跨叶实现（图 3、§3.1） | BlueField-3、UDP、64-bit KV、单服务器 | 强 |
| learned index 适合延迟受限的 DPA 内存 | 与 B+树比较，sparse/sparseBig/amzn 吞吐更高（图 12、§4.2.5） | 特定 SOSD 分布；osmc 的大 ε 配置中 B+树胜出 | 中 |
| 系统对读多写少负载有竞争力 | 与 ROLEX 的 YCSB-D/E 和 RANGE 对比（图 15、§4.3） | 六客户端、100 Gb/s、选定三种数据集 | 强 |
| 写入扩展性受硬件复制路径限制 | bulk load 仅 120 MB/s，INSERT ≤1.7 MOPS（§4.2.7–4.2.8） | B3140L 的 host-to-DPA 路径 | 强 |

## 批判性分析

### 论证链条

从 DPA 内存延迟到连续窗口索引，再到 NIC 侧无锁遍历，论证链条在 GET/RANGE 上较完整。更新路径的关键瓶颈也被单独测量，并用 FlexIO 主动推送实验排除了简单的 stitcher 方向问题。论文将“未来硬件可超过 62 MOPS”作为模型推断，不能等同于现有硬件结果。

### 假设压力测试

系统依赖稳定键分布、读多写少比例和可接受的 UDP 重试语义。极端单键热点会把请求集中到一个 home thread；非 home 重路由虽能缓解，但会失去缓存。大规模多租户场景的端口分配、隔离和拥塞控制没有充分评测。

### 实验可信度

实验覆盖 SOSD 多种分布、YCSB 六类混合负载、B3140L/B3220 两种卡型，并报告重复运行的方差。ROLEX 使用相同硬件配置，有助于公平比较。局限是服务器规模为单节点，真实生产网络中的丢包、重试风暴、故障恢复和多租户干扰未覆盖。

### 系统性缺陷

无 exactly-once 写语义，应用必须承担冲突排序。自适应流控仍是未来工作。epoch 回收、主机与 NIC 双副本的一致维护会增加运维和故障恢复复杂度；论文未给出节点或链路故障下的恢复时间与持久化保证。

## 局限与后续工作

- **局限 1**：INSERT 受 BlueField-3 host-to-DPA 写入路径限制，在写密集工作负载中明显落后 ROLEX。
- **局限 2**：UDP 语义允许重复写，缺少系统级拥塞控制和 exactly-once 保证。
- **后续工作 1**：在真实丢包与突发流量下测量重试放大、尾延迟和队列溢出，并实现可验证的客户端流控策略。
- **后续工作 2**：在多租户、多节点和故障注入环境中评估缓存隔离、epoch 回收与双副本恢复成本。

## 相关

- **相关概念**：[[Learned-Index]]、[[SmartNIC]]、[[RDMA]]、[[RCU]]
- **同类系统**：[[ROLEX]]、[[HONEYCOMB]]、[[MICA]]、[[KV-DIRECT]]
- **同会议**：[[OSDI-2026]]
