# Scaling IP Lookup to Large Databases using the CRAM Lens

**作者**：Robert Chang, Pradeep Dogga (University of California, Los Angeles), Andy Fingerhut (Cisco Systems), Victor Rios, George Varghese (University of California, Los Angeles)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/chang
**源文件**：[nsdi2025-chang.pdf](../../papers/nsdi-2025/nsdi2025-chang.pdf)

---

## 一、背景

IP 查找（IP lookup）是互联网路由的核心操作，已有超过 40 年的研究历史和数百篇论文。然而，传统方案都是**单资源方案**——要么基于 TCAM（ternary content-addressable memory，支持通配符并行查找但面积大、功耗高），要么基于 SRAM/DRAM（便宜但需要额外算法复杂度）。

近年来，两个趋势使得 IP 查找问题需要重新审视：

1. **路由表持续增长**：全球 IPv4 路由表在过去 20 年线性增长，每十年翻一倍，预计 2033 年将达到 200 万条；IPv6 路由表则以指数速度增长，每三年翻一倍。
2. **网络硬件架构变革**：新一代网络 ASIC（Intel Tofino、AMD Pensando、Nvidia BlueField）基于 RMT（Reconfigurable Match-Action Tables）和 dRMT（disaggregated RMT）架构，同时提供大量 TCAM 和 SRAM，但传统单资源算法无法充分利用这两种资源。

---

## 二、要解决的问题

1. **缺乏抽象模型**：现有网络处理器芯片的资源约束（TCAM block 大小、SRAM page 大小、每级内存限制等）非常复杂且芯片特定，算法设计者难以快速评估和比较不同方案的可扩展性。
2. **单资源方案无法扩展**：纯 TCAM 方案在 Tofino-2 上仅支持约 25 万条 IPv4 前缀（仅为当前全球路由表的 27%）；最优 SRAM 方案 SAIL 虽然内存效率高，但其前置成本（upfront cost）使其在 RMT 芯片上不可行。IPv6 方面，最优方案 HI-BST 需要过多流水线级数。
3. **资源浪费**：现代芯片同时拥有 TCAM 和 SRAM（Tofino-2 的 SRAM 是 TCAM 的 19 倍），但现有算法只使用其中一种，导致另一种资源闲置。

---

## 三、洞察与设计

**关键洞察**：现代网络处理器同时提供大量 TCAM 和 SRAM，而 TCAM 擅长压缩含通配符的稀疏数据、SRAM 擅长存储密集数据——通过在算法中**策略性地混合使用两种内存**，可以突破单资源方案的扩展瓶颈，且只需少量 TCAM 就能带来巨大的可扩展性提升（"a little TCAM goes a long way"）。

基于这一洞察，论文提出 **CRAM（CAM+RAM）lens**，包含两部分：

### CRAM 模型
一个形式化的抽象计算模型，扩展了经典 RAM 模型：
- 增加 TCAM 操作（ternary match）
- 用有向无环图（DAG）的 match-action 依赖关系衡量时间复杂度（流水线级数）
- 高阶空间度量：分别计算 TCAM bits 和 SRAM bits
- 高阶时间度量：DAG 最长路径上的步数

### 八条优化 Idiom
1. **I1 - Compress with TCAM**：用 TCAM 压缩含通配符的数据，避免 SRAM 中的前缀展开
2. **I2 - Expand to SRAM**：当展开后数据量 < 3× 原 TCAM 条目时，改用 SRAM（因 TCAM 面积是 SRAM 的 3 倍）
3. **I3 - Compress with SRAM**：用哈希表替代直接索引数组
4. **I4 - Strategic Cutting**：策略性选择切分位置平衡内存与查找深度
5. **I5 - Table Coalescing**：合并稀疏表减少碎片
6. **I6 - Look-aside TCAM**：将少见条目（如超长前缀）移入旁路 TCAM
7. **I7 - Step Reduction**：利用 MAU 并行性合并无依赖的查找
8. **I8 - Memory Fan-out**：将需多次访问的表拆分到多个物理表

### 三个新算法
- **RESAIL**（rethinking SAIL）：改进 IPv4 方案 SAIL，用 look-aside TCAM 处理长前缀、用哈希表替代 next hop 数组、并行化 bitmap 查找
- **BSIC**（Binary Search with Initial CAM）：改进 IPv4/IPv6 方案 DXR，用 TCAM 替代直接索引的初始查找表、将 range table 转为 BST 并 fan-out
- **MASHUP**（CAM+RAM 混合 trie）：对 multibit trie 的每个节点选择 TCAM 或 SRAM 表示，再合并稀疏节点

---

## 四、实现细节

**实验平台**：Intel Tofino-2 RMT 交换芯片，使用 P4 语言编程。

**RESAIL 实现要点**：
- 参数 `min_bmp` 控制最小 bitmap 级别，决定并行度与哈希表大小的权衡
- 哈希表使用 d-left hashing（碰撞率低，80% 负载率下仍可工作，内存开销仅 25%）
- Bit marking 技巧将不同长度前缀统一为 25-bit 定长 hash key，避免每个长度一个哈希表
- 所有 bitmap 查找通过 step reduction 合并为单步并行执行

**BSIC 实现要点**：
- 参数 k 为初始 TCAM 查找表的 slice 宽度（Tofino-2 TCAM block 宽度为 44 bit，远大于 DXR 的 20 bit 限制）
- BST 各层通过 memory fan-out 分布到不同流水线级
- 在 Tofino-2 上每个 BST 层需要 2 个 stage（一个比较、一个 action），导致 IPv6 需 30 个 stage，超过 Tofino-2 的 20 级限制，需通过 recirculation 解决（代价是端口数减半）

**MASHUP 实现要点**：
- 对每个 trie 节点，展开后数据量 < 3× 时选 SRAM，否则选 TCAM
- Table coalescing 用 tag bits 区分合并后的逻辑表
- Stride 选择依据前缀长度分布，IPv4 最佳为 16-4-4-8

---

## 五、实验结果

实验数据集：AS65000 的 IPv4 BGP 路由表（约 94 万条，Sep 2023）和 AS131072 的 IPv6 BGP 路由表（约 19 万条）。

### IPv4 对比（Ideal RMT）

| 方案 | TCAM Blocks | SRAM Pages | Stages |
|------|------------|------------|--------|
| RESAIL (min_bmp=13) | 2 | 556 | 9 |
| SAIL | - | 2313 | 33 |
| Logical TCAM | 1822 | - | 76 |

RESAIL 比 Logical TCAM 减少 911× TCAM blocks，比 SAIL 减少约 4× SRAM 和 stages。

### IPv6 对比（Ideal RMT）

| 方案 | TCAM Blocks | SRAM Pages | Stages |
|------|------------|------------|--------|
| BSIC (k=24) | 15 | 211 | 14 |
| HI-BST | - | 219 | 18 |
| Logical TCAM | 762 | - | 32 |

### 可扩展性

| 方案 | 支持的最大前缀数 | 相对当前路由表 |
|------|---------------|-------------|
| RESAIL on Tofino-2 (IPv4) | ~225 万 | 2.3× |
| RESAIL on Ideal RMT (IPv4) | ~380 万 | 4× |
| BSIC on Tofino-2 (IPv6) | ~39 万 | 2× |
| BSIC on Ideal RMT (IPv6) | ~63 万 | 3.3× |
| 纯 TCAM on Tofino-2 (IPv4) | ~25 万 | 0.27× |

### CRAM 模型预测精度

CRAM 模型的 TCAM/SRAM 预测与 Ideal RMT 仅有小的舍入误差；从 Ideal RMT 到 Tofino-2 实现，SRAM 增加约 1.35×–2×，stages 增加约 1.78×–2×，主要因 Tofino-2 的 SRAM 利用率上限为 50% 及 ALU 限制。

---

## 六、批判性分析

1. **实验平台局限性**：所有实验仅在 Intel Tofino-2 上进行，但 Intel 已宣布不再开发新 Tofino 型号。论文声称结果可推广到 dRMT 和其他架构，但未在 AMD Pensando 或 Nvidia BlueField 上验证，这些平台的资源配比和约束可能不同。

2. **BSIC 的 recirculation 代价被轻描淡写**：IPv6 的 BSIC 在 Tofino-2 上需要 30 个 stage（超限 50%），需 recirculation，直接导致可用端口数减半。这在生产环境中是非常大的代价，但论文仅用一句话带过。

3. **MASHUP 可扩展性未评估**：论文承认 MASHUP 对 Tofino-2 需要过多 TCAM，因此跳过了其可扩展性分析。这意味着三个算法中有一个在目标平台上实际不可用，削弱了"三种算法各有优势"的叙事。

4. **合成数据的代表性**：IPv6 可扩展性使用"multiverse scaling"生成合成数据，假设所有前缀长度均匀扩展。作者自己承认实际中 /48 前缀增长远快于 /24，但将此视为"仅影响 BST 不影响 TCAM"而忽略——这恰恰可能低估了 BST 内存增长，即实际可扩展性可能低于报告值。

5. **缺少延迟和吞吐量评估**：论文完全没有测量实际转发延迟和吞吐量。虽然 RMT 架构理论上是线速的，但 recirculation、哈希冲突处理等可能影响实际性能。

6. **更新性能未充分评估**：路由表的增量更新是实际部署的关键需求。论文将 RESAIL 的更新算法放到了附录中，且未给出更新延迟的定量数据。

---

## 七、总结

本文提出 CRAM lens，一个面向现代网络处理器（同时具备 TCAM 和 SRAM）的算法设计框架，包含形式化模型和八条优化策略。基于 CRAM，设计了三个新 IP 查找算法：RESAIL 使 Tofino-2 支持 225 万条 IPv4 前缀（纯 TCAM 仅 25 万），BSIC 支持 39 万条 IPv6 前缀（纯 TCAM 仅 12 万）。核心启示是"少量 TCAM 配合 SRAM 即可大幅提升可扩展性"。主要局限在于仅在即将停产的 Tofino-2 上验证，且 BSIC 的 IPv6 方案需要 recirculation（端口减半），MASHUP 在目标平台上 TCAM 不足。
