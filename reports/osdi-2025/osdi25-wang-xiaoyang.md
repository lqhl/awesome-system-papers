# FineMem: Breaking the Allocation Overhead vs. Memory Waste Dilemma in Fine-Grained Disaggregated Memory Management

## 论文基本信息

- **标题**: FineMem: Breaking the Allocation Overhead vs. Memory Waste Dilemma in Fine-Grained Disaggregated Memory Management
- **作者**: Xiaoyang Wang, Yongkun Li (USTC); Kan Wu (Google); Wenzhe Zhu, Yuqi Li, Yinlong Xu (USTC)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/wang-xiaoyang

## 研究背景与动机

随着超大规模云服务商对降低内存成本的需求不断增长，内存解聚（Memory Disaggregation）作为一种有吸引力的架构方案在系统研究中日益重要。RDMA 驱动的内存解聚使计算节点能够通过单边 RDMA 操作直接读写远程内存节点的数据，无需远程内存节点的 CPU 介入。然而，RDMA 在内存分配和释放方面存在显著挑战：注册内存区域（MR）代价高昂（注册 4MB 内存区域需要超过 480µs），而现有的解聚内存系统为了规避这一开销，采用粗粒度分配（GB 级别），导致严重的内存浪费。

**两难困境**: 要么承受高昂的分配开销（细粒度分配），要么容忍巨大的内存浪费（粗粒度分配）。这是一个尚未解决的核心问题。

## 要解决的核心问题

1. **MR 注册延迟**: 运行时 MR 注册代价高昂（480µs/4MB），频繁分配场景下不可接受
2. **细粒度分配的并发可扩展性**: 现有单边 RDMA 分配方案存在不可预测的网络往返延迟（由于 CAS 重试导致的元数据争用）
3. **多 DM 系统间的内存隔离**: 多个解聚内存应用共享同一远程内存池时的安全隔离问题
4. **计算节点故障时的元数据一致性**: 细粒度分配系统中的崩溃一致性问题

## 主要贡献

1. **FineMem: 首个高性能细粒度 RDMA 内存解聚内存管理系统**: 支持 4KB、2MB 等细粒度分配，分配延迟降低最高达 95%
2. **消除 MR 注册开销**: 通过每个计算节点预注册整个远程内存空间，同时使用内存窗口（MW）和可信分配服务确保隔离
3. **两层位图树结构**: 显著减少细粒度分配的 RDMA 往返次数，并通过内嵌的争用控制信息减少 CAS 重试次数
4. **计算节点故障的崩溃一致性**: 基于紧凑的临时 redo-log 和提交点元数据的锁-free 崩溃一致性机制
5. **广泛适用性**: 已在 jemalloc、mimalloc、FastSwap 和 DM-native KV store 上验证

## 研究方法与设计

### 架构概述

FineMem 集成了内存节点和计算节点的组件：

**内存节点端**:
- 两层位图树结构（Section/Span 两级）追踪可用内存
- MW 能力表管理每个 chunk 的 RDMA rkey
- 临时 redo-log 和 full redo-log 记录分配信息

**计算节点端**:
- 每个计算节点运行分配服务（Allocation Service）
- 启动时预映射整个远程内存池
- 提供 malloc(size) 和 free(addr) 简单 API

### 1. 消除 MR 注册开销的隔离方案

**朴素预注册方案的隔离问题**: 预注册整个远程内存空间为单一 MR，任何持有 rkey 的系统可访问整个 MR，导致严重的隐私和安全风险。

**解决方案: MW + 可信分配服务**:
- **MW（内存窗口）快速生成 rkey**: ConnectX-6 RDMA NIC 支持 MW rkey 生成只需约 1µs（vs MR 注册 480µs）
- **内存节点预绑定**: 内存节点预绑定 MW 到每个 chunk，异步生成新 rkey（后台线程）
- **分配/释放时的单边 MW 操作**: 获取/失效 rkey，无需 MW 绑定的 RPC 调用
- **可信分配服务**: 仅分配服务持有访问分配元数据区域（索引、redo-log）的 rkey，DM 系统通过 IPC 与分配服务交互

### 2. 两层位图树结构（Section/Span 两级）

**结构设计**:
- **Section**: 16 个连续的 Span，每个 Span = 128KB
- **Section 头**: 32 位位图（追踪 16 个 Span 的 fullness 和争用状态）+ 32 位保留字段（用于争用控制和日志）
- **Span 头**: 32 位位图（追踪 32 个 chunk 的分配状态）+ 剩余位用于争用控制

**分配流程（不同大小)**:
- **>128KB**: 直接 CAS 修改相关 Span 状态为"full"（11）
- **≤128KB, >4KB**: 在 Section 级搜索空闲 Span → 在该 Span 内搜索空闲 chunk（两级 CAS）
- **≤4KB**: 同上流程，通过 Span 内位图定位空闲 chunk

**争用控制**:
- 每个分配头追踪连续分配失败次数
- 超过高阈值（如 10 次）→ 标记 Section/Span 为"争用"（10）
- 低于低阈值（如 3 次）→ 重置为"正常"（01）
- 分配器优先选择 normal > empty > contended 的 Section/Span

**元数据缓存**:
- 每个计算节点缓存 64 个 Section/Span 的元数据（512 字节）
- 批量读取位图以摊销往返成本

### 3. 计算节点故障的崩溃一致性

**两阶段提交点设计**:
- **提交点**: CAS 成功更新 bitmap（分配状态从 free→used 或 used→free）
- **临时 redo-log**: 内嵌于 Section/Span 头的 32 位保留字段，包含：最后分配 chunk 偏移（5 位）+ size（3 位）+ timestamp（7 位）+ user ID（14 位）
- **Full redo-log**: 每 chunk 一个，位于 chunk 本身

**一致性保证**:
- 分配成功后标记临时 redo-log → 任意线程可将临时 redo-log flush 到 full redo-log
- 通过 timestamp 比较确保只 flush 最新的日志
- 检测临时/完整日志是否属于不同层（Span vs. Section），通过 Span 的 in_use 位确定最近状态

**时间戳增量策略**:
- 相邻 Span/ Section 内的连续分配可能共享同一 timestamp
- 仅当操作类型改变（分配→释放 或 释放→分配）时才递增 timestamp
- 支持约 64 个时间戳窗口（每个约 20µs，共约 1ms）

## 关键实现细节

### MW 与 MR 注册开销对比

| 操作 | MW | MR |
|------|-----|-----|
| 1×100GB 生成 | 1.33µs | 456.1µs |
| 25K×4MB 生成 | 1.34µs | 485.5µs |
| 25K×4MB 失效 | 1.33µs | 21.9µs |
| 25K×4MB 重新生成 | 2.37µs | 46.5µs |

### 虚拟函数扩展
- ConnectX-6 单 NIC 支持最多 16M MW 条目（64GB for 4KB chunks）
- 通过生成多个 Virtual Functions（最多 128 个 VF）扩展到更大的内存池

## 实验结果与分析

### 分配基准测试
- **分配延迟**: FineMem 比现有最先进设计降低 95% 分配延迟（细粒度分配场景）
- **并发可扩展性**: 128 线程下，FineMem 的吞吐量是 CXL-SHM 的 4.7×

### 端到端应用
- **内存系统（基于 mimalloc）**: 内存利用率提升 2.25×-2.8×（vs 粗粒度分配），额外开销仅 2.5%-4.1%
- **KV Store（FastSwap）**: 内存浪费显著减少，同时保持高吞吐量
- **Swap 系统**: 在内存压力下表现出更好的整体吞吐量

## 潜在问题与局限性

1. **仅支持 power-of-2 对齐的分配**: FineMem 的设计基于 2 的幂次分配粒度，可能不适用于需要非对齐分配的特定应用
2. **ConnectX 系列硬件依赖**: MW 的快速 rkey 生成是 ConnectX 系列特定功能，移植到其他 RDMA NIC 可能面临不同性能特征
3. **多 VF 的复杂性**: 生成 128 个 VF 来扩展 MW 空间可能带来额外的系统管理复杂性
4. **最大虚拟函数数量**: ConnectX-6 最多 128 VF，但论文未讨论超过此限制时的扩展策略
5. **崩溃一致性的时间窗口**: redo-log 的 timestamp 机制有约 1ms 的不一致检测窗口（64 × 20µs），在极高分配频率下可能出现边缘情况

## 未来工作方向

1. 探索非 power-of-2 对齐分配的支持
2. 与 CXL 内存解聚的集成
3. 支持更大的多 VF 配置

## 个人评注

### 优点
1. **问题定义精准**: "分配开销 vs 内存浪费"的两难困境是 RDMA 解聚内存领域的核心痛点，FineMem 首次系统性地解决这一问题
2. **设计的层次清晰**: 三层设计（MR 注册消除 → 高效分配 → 崩溃一致性）层层递进，每层都有明确的技术选择和权衡
3. **与现有系统的广泛集成**: 在 jemalloc、mimalloc、FastSwap、DM KV store 上的验证充分说明了其通用性
4. **MW rkey 快速生成的量化数据**: 提供了令人信服的 Microsecond 级别 MW rkey 生成数据，与 MR 注册的数百微秒形成鲜明对比

### 潜在问题
1. **128 个 VF 的实际可行性**: 生成 128 个 Virtual Functions 是 NIC 级别的重大配置改变，在生产环境中实施可能面临管理员接受度和系统稳定性的挑战，论文未充分讨论工程可行性
2. **"最高 95%"的具体场景**: 这个 95% 的降低是在与谁比较时的数字？论文的基准是"现有最先进设计"，但具体是和 FUSEE-on-demand 还是其他系统对比？需参考具体实验设置
3. **两层位图树的额外内存开销**: 为了减少 CAS 重试，FineMem 在每个 Section 头中嵌入了争用控制字段，这增加了元数据开销。以 128KB Section 为例，32 位的争用控制字段 + 32 位保留字段（用于 redo-log）的空间开销在大内存池中可能相当可观
4. **临时 redo-log 的 7-bit timestamp 限制**: 64 个时间戳窗口在极高分配频率（< 20µs/操作）下可能不足以覆盖整个不一致检测窗口，论文提及会"减速时间戳增量"，但未给出具体的策略细节
5. **"2.25×-2.8× 内存利用率提升"的基数**: 这个数字相对于什么基线？是与 1GB 分配粒度还是其他粒度对比？理解这个基线对评估绝对收益至关重要
