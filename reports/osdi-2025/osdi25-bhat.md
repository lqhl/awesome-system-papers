# SpecLog & Belfast: Low End-to-End Latency atop a Speculative Shared Log with Fix-Ante Ordering

## 论文基本信息

- **标题**: Low End-to-End Latency atop a Speculative Shared Log with Fix-Ante Ordering
- **作者**: Shreesha G. Bhat, Tony Hong, Xuhao Luo, Jiyu Hu, Aishwarya Ganesan, Ramnatthan Alagappan (UIUC)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/bhat
- **开源**: https://github.com/nicdrp/belfast

---

## 研究背景与动机

共享日志（Shared Log）在现代数据驱动应用中扮演核心角色：高速交易、实时搜索、IoT 分析、欺诈检测等。共享日志提供容错的有序记录序列，多客户端可同时追加和读取。

### 现有共享日志的两大类

**早期设计（Order-first，如 Corfu）**：
- 客户端先从排序器获取位置，再写入对应分片
- 问题：添加/删除分片困难（需要全局映射一致）、数据放置不灵活、排序器成为瓶颈

**现代设计（Durability-first，如 Scalog）**：
- 客户端先将记录写入所选分片（ durability-first）
- 分片批量、定期联系排序层确定全局顺序
- 优势：弹性伸缩、灵活数据放置、高可扩展性
- **核心问题**：高交付延迟（Delivery Latency）

### 高交付延迟的根本原因

在 Scalog 中，分片必须先批量报告本地日志长度 → 排序层计算全局切点 → 将切点分发回分片 → 分片才能交付记录给下游。这要求多次协调和等待，最小化也有 1 个ordering interval（~1ms）的批量延迟。下游计算只能在此之后开始，导致端到端延迟居高不下。

### 应用需求

35% 的 RedPanda 调查用户将"交付延迟"列为最关键指标。欺诈检测需要毫秒级 flagging、高频交易毫秒级决策、实时分析尽快获得洞察。

---

## 要解决的核心问题

如何让 durability-first 共享日志在保持弹性、灵活性和可扩展性的同时，实现低端到端延迟？

---

## 主要贡献

1. **SpecLog 抽象**：新的共享日志抽象，通过预测全局顺序来投机交付记录，允许下游计算与全局协调重叠
2. **Fix-Ante Ordering 机制**：预定义全局顺序，让分片准确预测其记录在总顺序中的位置
3. **Belfast 实现**：SpecLog 的完整实现，处理速率匹配、突发处理、分片动态增删、落后者缓解等问题
4. **三个真实应用**：入侵检测、欺诈监控、高频交易

---

## 研究方法与设计

### SpecLog 抽象

**核心思想**：共享日志先按预测顺序交付记录，稍后确认或失败预测是否正确。预测正确时应用实现低延迟；预测失败时通知应用重新计算。

**接口**：
```
append(r, shard) → log position
deliver(r, pos, is_spec)        # 回调
confirm_spec(k) / fail_spec(k)  # 确认/失败通知
subscribe(i, opt_pred) / trim(i)
```

**关键属性**：
- SpecLog 保持与 Scalog 相同的弹性（分片可无缝增删）、灵活放置（客户端选分片）、可扩展性（批量通信）
- SpecLog 与顺序无关的应用完全兼容；与顺序相关的应用需要等待 confirm 后才能外部化输出（交易告警等）

### Fix-Ante Ordering

**问题**：Durability-first 设计中，分片可自由决定每批次报告多少记录（free-will），因此很难预测自己记录在总顺序中的位置。

**Fix-Ante Ordering 解决方案**：
1. 预定义一系列全局切点 $P_1, P_2, P_3, ...$（如 ⟨2,3,2⟩, ⟨4,6,4⟩, ...）
2. 每个切点决定每个分片的配额（quota）：$q_{ij} = d_{ij} - d_{(i-1)j}$（第 j 个分片在第 i 个切点应包含的记录数）
3. 分片通过精确满足配额来遵守切点：
   - 记录数 = 配额：直接报告所有记录
   - 记录数 < 配额：补充 no-op 记录
   - 记录数 > 配额：延迟多余记录到下一批次
4. 所有分片都精确报告配额时，实际切点与预定义切点一致，预测始终正确

**追加线性化（Append Linearizability）**：即使切点是预定义的，追加仍不能立即确认（否则可能违反线性化）。必须等待实际切点确认后，才向客户端确认追加。

### Belfast 实现细节

#### 速率配额（Rate-based Quotas）

配额必须"合适"：过高导致大量 no-op，过低导致记录延迟。Belfast 根据每个分片的摄取速率预定义配额。速率稳定时自然满足配额；短期变化通过 no-op 填充或记录延迟处理。

#### Lag-Fix 机制

**突发处理**：分片遇到突发时若将多余记录延迟到后续批次，会增加追加和确认延迟。Belfast 让分片立即报告，排序层检测到突发后通知落后分片补发 no-op。

**速率下降处理**：分片速率下降时持续填充 no-op 成本高，Lag-Fix 允许分片一次性填充多个切点的 no-op 并批量报告。

#### Speculation Lease Window

长期速率变化需要调整配额。但如果分片 A 在旧配额下已交付了位置 10-12 的记录，分片 B 在新配额下分配了位置 8-9 给 A 的记录，就会产生 misspeculation。

**解决方案**（Speculation Lease Window）：
- 将预定义切点组织为窗口（W 个切点构成一个 lease）
- 窗口内所有分片使用相同的预定义切点做预测
- 配额变化只在窗口边界生效
- 所有分片在新窗口开始时统一切换到新切点

实现为按切点数量（而非时间）测量窗口：`W=100` 个切点，`T_ord=1ms`。

#### 分片动态增删

分片加入/离开只能在窗口边界进行。离开的分片继续满足配额直到窗口结束；加入的分片获得新配额在下一窗口生效。

#### 落后分片（Straggler Shards）缓解

分片可能因网络延迟或线程调度而落后。Belfast 通过 Staggered Cuts（错开切点）机制处理：排序层不是等待所有分片满足每个切点，而是让切点等待不同分片子集（按分组轮询）。这在分片数量多时显著减少等待时间。

#### 故障处理

- **分片内部副本失败**：无影响（primary-backup 容错）
- **整个分片失败**（罕见）：执行 view change，排序层将失败分片的位置填充 no-op，存活分片继续交付，客户端重新路由到存活分片接收确认

---

## 关键实现细节

- 基于开源 Scalog 修改
- 新增 1 个额外 RPC（分片向排序层注册）
- 其他机制（Lag-fix、配额变更）通过 piggybacking 实现
- 排序层通过 Paxos 保证切点容错
- Staggered Cuts 在分片数 > 6 时启用
- 分片在最后一次报告后 1.5×T_ord 开始填充 no-op

---

## 实验结果与分析

### 实验配置

- 10 个分片（2 副本），Ordering interval 1ms，Lease window = 100 切点
- 合成工作负载 + 真实追踪

### 端到端延迟

- **交付速度**：Belfast 比 Scalog 早交付记录约 **3 倍**
- **E2E 延迟**：Belfast 比 Scalog 低 **1.6 倍**
- 在不同下游计算时间下（1ms 到 10ms），Belfast 均显著优于 Scalog
- 追加延迟开销：仅比 Scalog 高 5.8%（10 分片时）

### 处理突发和速率变化

- 突发处理：Lag-Fix 有效减少突发记录的追加和确认延迟
- 长期速率变化：配额调整后恢复稳定吞吐量
- Straggler 处理：Staggered Cuts 保证在 20 分片下仍维持低延迟

### 弹性与可扩展性

- 分片增删：无停机、无 misspeculation（通过 lease window 边界切换）
- 吞吐量随分片数量线性扩展

### 应用验证

三个应用（入侵检测、欺诈监控、高频交易）在 Belfast 上均实现了 **1.4x-1.6x 更低的 E2E 延迟**，同时保持了弹性特性。

---

## 潜在问题与局限性

1. **Misspeculation 的实际影响**：论文承认在"整个分片失败或无法联系排序层"时会 misspeculation。但未量化这种场景在实际系统中的频率和影响范围。
2. **追加延迟开销**：虽然 E2E 延迟降低，但追加确认延迟比 Scalog 高（等待实际切点以满足 append linearizability）。论文报告 5.8% 的追加延迟增加。
3. **Lease Window 粒度**：W=100 切点 = 约 100ms 的窗口（假设 T_ord=1ms）。在此期间配额变化不会生效，可能影响快速变化的负载。
4. **多副本场景未详细评估**：仅描述了 primary-backup 机制，未评估 3+ 副本或 Raft 组的影响。
5. **复杂性增加**：Fix-Ante Ordering 引入的新机制（配额、no-op、Lag-Fix、Lease Window、Staggered Cuts）显著增加了系统复杂度。

---

## 未来工作方向

- 更灵活的切点分配策略（动态而非固定分组）
- 减少 no-op 开销（合并连续 no-op 到单条日志项）
- 性能监控和自适应配额调整

---

## 个人评注

### 优势

1. **问题定义精准**：清晰地识别出现代 durability-first 共享日志中"批量协调 → 高延迟"的根本矛盾
2. **Fix-Ante Ordering 的概念创新**：将"预测"和"遵守"分离，通过配额机制确保预测准确性——这是一个优雅的分布式协调技巧
3. **全面的实现细节**：Lag-Fix、Lease Window、Staggered Cuts 等机制解决了将抽象落到工程的所有细节问题
4. **端到端视角**：从 E2E 延迟（而非仅交付延迟）评估，对应用更有意义

### 潜在问题

1. **Misspeculation 的真实影响**：论文强调 misspeculation 仅在"非常罕见"情况下发生，但未给出具体概率或频率数据。应用开发者需要仔细评估 misspeculation 对其计算的影响（是否需要昂贵的回滚？）
2. **摘要与正文数字不一致的风险**：摘要说"records ~3× earlier than Scalog, reducing E2E latency by 1.6×"——这个 ~3× 是交付速度而非延迟 reduction，需注意区分
3. **Lease Window 固定为 100 切点**：这对所有场景是否最优？高摄取速率（每分片 >> 1ms）和低摄取速率场景下，100 切点意味着不同的实际窗口时间，可能不适合所有工作负载
