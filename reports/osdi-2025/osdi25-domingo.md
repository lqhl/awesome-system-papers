# Kamino: Efficient VM Allocation at Scale with Latency-Driven Cache-Aware Scheduling

**作者**：David Domingo (Rutgers University), Hugo Barbalho, Marco Molinaro, Ishai Menache (Microsoft Research), Kuan Liu, Abhisek Pan, David Dion, Thomas Moscibroda (Microsoft Azure), Sudarsun Kannan (Rutgers University)
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation，July 7–9, 2025，Boston, MA）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/domingo
**源文件**：[osdi25-domingo.pdf](../../papers/osdi-2025/osdi25-domingo.pdf)

---

## 一、背景

大型云提供商（如 Microsoft Azure）每天需要处理数以百万计的虚拟机（VM）分配请求。VM 分配系统负责将用户请求映射到物理硬件，是云控制平面的关键路径组件。分配系统的设计目标通常有两个：(1) 在严格的延迟上限内完成分配（通常数十毫秒）；(2) 实现"高质量"分配，即综合考虑服务器利用率、用户偏好等多种约束，以最大化基础设施 ROI。

为了满足这两个相互矛盾的目标，现代 VM 分配系统（如 Azure 的 Protean）采用两种关键技术：(1) 在单个节点内部署多个分配代理（Allocation Agents，AA），利用多核并行性提升吞吐；(2) 使用层次化的内存缓存，将重复或相似的分配请求和规则求值结果缓存起来，避免重复计算数十万台服务器的约束求值。

然而，如何将传入的请求调度到合适的 AA，是一个被长期忽视的问题。现有系统普遍采用 Round-Robin、随机分配或 consistent hashing 等"缓存无感知"策略，这导致了缓存命中率低、延迟高、内存浪费等问题。

---

## 二、要解决的问题

**问题 1：缓存状态与请求调度脱节**

现有 AA 调度器在将请求分配给 AA 时，不考虑目标 AA 当前的缓存状态。若请求类型不在目标 AA 的缓存中，就会触发高代价的缓存缺失（cache miss），延迟可能高达数百毫秒。然而，简单的缓存亲和性策略（如 consistent hashing）又会在热门请求类型上造成严重的队列积压，反而加剧延迟。

**问题 2：VM 分配缓存的高度异构性**

不同于传统数据缓存，VM 分配缓存是层次化的（2 级：fast path + slow path），且每种请求类型的 hit/miss 延迟差异极大（实测达 5x）——甚至某些请求类型的 cache hit 延迟高于另一些类型的 cache miss 延迟。这使得基于命中率的简单优化远远不够。

**问题 3：内存与 CPU 资源不平衡**

由于每个 AA 维护私有缓存以避免锁竞争，增加 AA 数量需要更多缓存内存。实测显示 AA 节点内存使用率高达 90%+ 而 CPU 使用率仅 40-74%，内存瓶颈限制了单节点可运行的 AA 数量，进而限制了吞吐和并发能力。

**问题 4：增加 AA 数量时缓存碎片化**

通过拆分单位缓存内存来增加 AA 数量，会导致每个 AA 的缓存容量下降，缓存命中率随之下降，延迟反升。

---

## 三、核心设计

**Kamino** 是一个延迟驱动的缓存感知请求调度框架，其核心算法称为 **LatCache**（Latency-driven Cache-aware Scheduling）。

### 关键思路

不直接优化缓存命中率，而是将端到端请求延迟（排队时间 + 处理时间）作为优化目标。对每个传入请求，估计将其分配到各 AA 后的预期完成延迟，并将请求分配到预期延迟最小的 AA。

### LatCache 算法的三个延迟分量估计

1. **处理时间（processingTime）**：基于"扩展缓存状态"（augmented cache state）估计，该状态包含 AA 当前缓存内容及其队列中所有待处理请求对缓存的预期影响。对于 2 级层次缓存，分别考虑 fast path（top-level）命中/缺失和 slow path（rule-level）命中/缺失情况，按 Algorithm 2 进行加权求和。

2. **排队时间（queueTime）**：对 AA 队列中每个已排队请求的预期处理时间求和，无需遍历队列——通过在入队/出队时维护增量计数来高效计算，避免误差累积。

3. **当前请求剩余处理时间（remainingProcTime）**：基于 AA 开始处理当前请求的时间戳和估计处理时间推断。

### 层次化缓存结构（LatCache 的 2 级缓存）

- **Top-level（fast path）**：存储等价请求（相同约束组合）的已合并机器列表；
- **Lower-level（slow path）**：按规则存储规则求值结果，不同请求类型可共享同一规则的缓存（支持"partial hit"）；缓存条目大小从 10MB 到 100MB 不等，限制了每个 AA 的缓存槽数量。

### 理论保证

问题被形式化为经典 online job scheduling 的推广版本（处理时间依赖调度决策），证明了 LatCache 在理想情况下的近优性（Theorem 1），为算法设计提供理论基础。

---

## 四、实现细节

Kamino 作为 Protean VM 分配系统的一部分实现，与 AA 运行在同一进程内，避免 IPC 开销。

**三个核心模块：**

1. **Request Classifier**：计算请求的等价类 key，即根据各规则依赖的请求属性子集确定请求类型唯一标识，用于缓存查找和调度决策。支持多实例并发处理。

2. **Agent Selector**：实现 LatCache 核心逻辑，为每个请求选择目标 AA 队列。维护每个 AA 的 `<RequestType, Count>` 映射表，用于快速判断某类请求是否已在队列中（无需遍历队列）。通过探测 AA 的 work item 状态判断其是否繁忙。

3. **Latency Estimator**：后台任务，周期性统计 hit/miss 时间的滑动平均，提供估计值给 Agent Selector。估计值也持久化存储，以便进程重启后快速恢复。

**流水线设计：** Request Classifier 和 Agent Selector 在关键路径上串行执行，Latency Estimator 在非关键路径上异步运行，调度开销约为**微秒级**，相比请求延迟（数十至数百毫秒）可忽略不计。

**缓存淘汰策略：** 混合 LRU + 基于年龄的淘汰（age-based eviction），低负载期间主动释放内存，减少 AA 内存占用。

---

## 五、实验结果

### 仿真实验（使用生产 Trace）

实验基于 6 个不同地理区域高负载 AA 节点的 24 小时生产 Trace，每个 Trace 包含 500–1700 种不同请求类型。

| 算法 | 平均延迟改善 | Tail (p90) 改善 | 缓存命中率 | 归一化缓存内存 |
|------|------------|----------------|-----------|--------------|
| Protean（基线）| 0% | 0% | 80.7% | 1.00 |
| Random | -20% | -30% | 81.1% | 0.98 |
| Round-Robin | -20% | -30% | 80.6% | 1.00 |
| Hash+WS（consistent hashing + work stealing）| +4.4% | +9.1% | 87.4% | 0.94 |
| LatCache-request | >40% | >50% | 93.1% | 0.85 |
| LatCache-rule | >42% | >50% | 95.0% | 0.77 |

关键发现：
- LatCache 通过更高命中率（94–95% vs. 81%）**同时**减少了处理时间和排队等待时间；
- 在突发流量期间，LatCache 相比 Protean 吞吐提升 **2x**；
- 99.1% 的 hit/miss 预测准确率；91.9% 的情况下选到了延迟最优的 AA；即使未选最优，实际延迟差距仅 2.3%；
- 使用完美的 hit/miss 时间预测（替代粗糙均值估计），tail latency 仅额外提升 1.1%——说明准确预测 hit/miss **事件**比精确估计延迟数值更重要。

### 生产部署结果（5 个 Azure 生产 Zone）

部署 LatCache-request（更简单的变体），覆盖数万台节点，部署前后对比 15 天数据：

| 指标 | 改善 |
|------|------|
| 平均延迟 | -21.1% |
| p90 尾延迟 | -11.9% |
| 缓存缺失率 | -33% |
| 每 AA 内存使用 | -17% |
| CPU 使用 | -18.6% |

### 系统参数敏感性

- **AA 数量**：Hash+WS 和 Protean 在 AA 数量增加时因缓存碎片化而性能下降；LatCache 两个变体性能稳定；
- **负载强度**：随负载增加，LatCache 相对 Protean 的优势持续扩大；
- **缓存大小**：即使在缓存极小时，LatCache 依然优于所有基线；缓存增大后优势收窄（locality 重要性降低）。

---

## 六、批判性分析

**1. 生产数据与仿真的差距被轻描淡写**

仿真中 LatCache-rule 取得 42% 平均延迟改善和 >50% tail 改善，而生产实际仅为 21% 和 11.9%。作者将差距归因于"冲突和重试"以及"动态工作负载变化"，但缺乏深入分析——冲突重试对各算法的影响是否公平？生产中 AA 数量、缓存配置是否与仿真相同？这一差距（约 2x）值得更仔细的讨论。

**2. 仅部署了 LatCache-request 而非 LatCache-rule**

论文以 LatCache-rule 作为主要算法推荐，但生产部署使用的是更简单的 LatCache-request，理由是"更容易与当前缓存 API 集成"。这意味着论文最主要的贡献（rule-level 缓存感知）尚未在大规模生产中验证。

**3. 评估场景和基线选择偏窄**

论文仅与 Protean、Random、Round-Robin 和 Hash+WS 对比，且承认"其他大规模 VM 分配器的调度算法没有公开文档"。这种情况下，42% 的改善是否具有普遍意义难以判断——Protean 的 work-stealing 策略作为基线本身也是较强的基线，但缺少对 Protean 不同配置下的对比（例如适当调整缓存大小的 Protean）。

**4. 理论分析较为薄弱**

Theorem 1 的证明（§4.1）仅提供了 LatCache 在某些假设下的定性保证，论文没有给出竞争比（competitive ratio）分析，这对于一个声称"理论上有依据"（theoretically sound）的在线算法来说是明显不足。

**5. LSM 实验为 "proof of concept"，可信度有限**

附录中的 LSM 实验仅使用单线程 LevelDB 原型，22% 的延迟改善基于非常有限的实验规模，且不涉及写路径和混合读写场景，与生产系统差距较大。

**6. 内存减少带来的安全隐患未讨论**

内存减少 17% 理论上允许部署更多 AA，但论文并未展示增加 AA 后的端到端效果——是否实际提高了吞吐、进一步降低了延迟？这是一个自然的延伸实验却被省略了。

---

## 七、AI Infra / MLSys 视角

本文虽然聚焦 VM 分配场景，但其核心思路对 AI 推理系统和分布式服务系统具有较强的启发价值：

**1. 与 LLM 推理调度的相似性**

LLM 推理系统（如 vLLM）中，不同请求的 KV cache 命中情况差异巨大，且 prefix caching 使得相同前缀的请求在同一副本上处理时可以复用 KV cache。这与 VM 分配中"相同等价类请求共享缓存"的场景高度类似。LatCache 的核心思路——"估计将请求路由到各副本的端到端延迟（含队列等待 + 处理时间），选最优"——可以直接迁移到多副本 LLM serving 的请求路由层。

**2. 分层 KV Cache 感知调度**

AI 推理系统也逐渐演进出分层缓存（GPU HBM → CPU DRAM → NVMe SSD），不同层的访问延迟差异（类似 VM 分配中 fast path vs. slow path 的 hit/miss 延迟差异）使得 LatCache 的处理时间估计框架具备直接迁移价值。

**3. 可操作的研究方向**

- 将 LatCache 思路应用于 **prefill-decode 分离架构**下的请求路由：在 prefill 节点的 KV cache 状态感知下，将解码请求路由到最可能复用 KV cache 的 decode 实例；
- 在 **disaggregated KV cache**（如 Mooncake、MemServe）场景中，LatCache 的层次缓存感知框架可用于决定 KV cache 从哪一存储层读取，以最小化 TTFT（time-to-first-token）；
- **多租户推理集群**中，不同 LoRA adapter 或不同模型的请求可以类比不同"请求类型"，LatCache 的等价类分组思路可以指导 adapter-aware 请求调度；
- LatCache 中"hit/miss 时间的在线统计估计"机制，可迁移到推理系统中对批处理时延的自适应预测。

---

## 八、总结

Kamino 提出了一种将延迟估计与层次化缓存感知相结合的 VM 请求调度算法 LatCache，通过将端到端延迟（而非单纯缓存命中率）作为调度目标，在 Azure 生产环境中实现了 21% 平均延迟下降、33% 缓存缺失率下降和 17% 内存节省。其最大贡献在于揭示了"缓存感知调度"与"延迟驱动调度"的本质差别——简单缓存亲和性会造成队列热点，而正确的目标是最小化包含排队等待在内的整体延迟。局限在于：生产改善幅度约为仿真的一半（原因未充分分析），最强变体 LatCache-rule 尚未生产验证，理论分析深度有限。核心思路对 LLM 推理系统的多副本 KV-cache 感知路由具有直接借鉴价值。
