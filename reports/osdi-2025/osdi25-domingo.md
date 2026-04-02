# Kamino: Efficient VM Allocation at Scale with Latency-Driven Cache-Aware Scheduling

**作者**：David Domingo (Rutgers University), Hugo Barbalho (Microsoft Research), Marco Molinaro (Microsoft Research), Kuan Liu (Microsoft Azure), Abhisek Pan (Microsoft Azure), David Dion (Microsoft Azure), Thomas Moscibroda (Microsoft Azure), Sudarsun Kannan (Rutgers University), Ishai Menache (Microsoft Research)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/domingo
**源文件**：[[osdi25-domingo.pdf]]

---

## 一、背景

大型云提供商（如 Azure）每秒需要处理数千个 VM 分配请求，将虚拟机映射到物理服务器上。VM 分配系统需要同时满足两个目标：（1）在严格的延迟上限（数十毫秒级别）内完成分配；（2）实现"高质量"分配，兼顾提供商和客户偏好（如服务器利用率最大化以提高 ROI）。这两个目标天然矛盾——高质量分配需要评估大量约束和规则，遍历数十万台服务器的库存，计算密集度高。

为此，现代分配系统采用多个并行的 Allocation Agent（AA）处理请求，并使用层次化的内存缓存加速规则评估。以 Azure 的 Protean 系统为例，每个 AA 维护私有缓存，缓存槽大小可达 10-100MB。然而，现有系统在请求调度层面缺乏缓存感知能力——调度器将请求分配给 AA 时不考虑 AA 的缓存状态和延迟因素。

---

## 二、要解决的问题

1. **缓存命中/未命中延迟差异巨大且异构**：不同请求类型的缓存命中延迟与未命中延迟差异可达 5 倍，且某些类型的命中延迟甚至高于其他类型的未命中延迟，打破了"命中总比未命中快"的传统假设。

2. **缓存无感知调度导致低效**：Protean 等系统使用 Round-Robin、work-stealing 等缓存无感知策略，请求可能被分配到缓存中没有对应数据的 AA，造成不必要的 cache miss 和高延迟。

3. **简单的缓存感知策略不够**：将同类请求固定到同一 AA（request-pinning）或使用 consistent hashing 会在热点请求突发时造成负载不均，排队延迟激增。

4. **AA 扩展受内存瓶颈限制**：每个 AA 需要私有缓存（层次化缓存占用大量内存），节点内存利用率已达约 90%，而 CPU 利用率仅 40-60%。简单地增加 AA 数量、缩减每个 AA 的缓存大小会导致 cache miss 率上升。

---

## 三、洞察与设计

**关键洞察**：在 VM 分配系统中，请求的处理延迟由缓存状态（层次化缓存的命中/部分命中/未命中）和队列等待时间共同决定，且两者高度耦合。仅优化缓存命中率（如 consistent hashing）或仅做负载均衡（如 Round-Robin）都不够，需要将延迟本身作为调度的一等指标——通过估算每个 AA 上的端到端延迟（包括剩余处理时间 + 队列等待时间 + 新请求处理时间），将请求分配给预计延迟最低的 AA。

基于此洞察，Kamino 系统包含以下核心设计：

- **LatCache 算法**：一种延迟驱动、缓存感知的请求调度算法。对每个到达的请求，估算将其分配到每个 AA 后的端到端延迟，选择估计延迟最小的 AA。延迟估算分解为三个分量：
  - **Processing Time**：基于"增广缓存状态"（当前缓存 + 队列中请求的类型）乐观估计新请求的处理时间
  - **Queue Time**：累加队列中所有请求的估计处理时间（入队时加、出队时减估计值，避免误差累积）
  - **Remaining Processing Time**：当前正在处理的请求的剩余时间

- **层次化缓存感知**：LatCache 利用两级缓存结构（top-level fast path 存储完整合并结果，lower-level slow path 存储单条规则评估结果）进行细粒度命中预测，支持"部分命中"场景。

- **理论保证**：LatCache 在完美延迟估计假设下，能保证任意两个 AA 的队列等待时间差距不超过最大请求处理时间（Theorem 1），实现近最优的负载均衡。

---

## 四、实现细节

Kamino 作为 Protean 系统的组件实现，运行在 AA 所在进程内，避免进程间通信开销。主要模块：

1. **Request Classifier**：计算请求的等价类 key（基于规则和请求特征），确定请求类型，用于缓存查找。支持多实例并发。

2. **Agent Selector**：核心调度模块，实现 LatCache 算法。每个 AA 有私有队列，一旦分配不可更改。维护 `<Request type key, Count>` 映射追踪队列中的请求类型。通过探测 AA 缓存和检查队列元数据做出调度决策。调度开销为微秒级，相比请求延迟（数十到数百毫秒）可忽略。

3. **Latency Estimator**：后台任务，跟踪命中/未命中时间并周期性更新估计值的滚动平均。估计值持久化以支持进程重启时的冷启动。

4. **缓存管理**：采用混合驱逐策略——LRU + 基于年龄的驱逐（低负载时主动释放过期缓存，减少内存占用）。

5. **流水线设计**：Request Classifier 和 Agent Selector 等阶段流水线化，支持并发请求处理。

---

## 五、实验结果

### 仿真实验（6 个生产 trace，24 小时，4 AA/节点）

| 算法 | 平均延迟改进 | P90 尾延迟改进 | Top-level 命中率 | 归一化缓存内存 |
|------|------------|--------------|-----------------|--------------|
| Protean (baseline) | — | — | 80.7% | 1.00 |
| Random | ≈-20% | ≈-30% | 81.1% | 0.98 |
| Round-Robin | ≈-20% | ≈-30% | 80.6% | 1.00 |
| Hash+WS | +4.4% | +9.1% | 87.4% | 0.94 |
| LatCache-request | **≈+42%** | **≈+50%** | 93.1% | 0.85 |
| LatCache-rule | **≈+42%** | **≈+50%** | 95.0% | 0.77 |

- 突发负载下 LatCache 可达 **2x 吞吐量**提升
- 命中/未命中事件预测准确率 **99.1%**，选择最优 AA 的比率 **91.9%**
- 对 AA 数量、负载和缓存大小均有良好的鲁棒性

### 生产部署（5 个 Azure 可用区，各数万台节点，部署 LatCache-request）

| 指标 | Protean | Kamino-LatCache | 改进 |
|------|---------|----------------|------|
| 平均延迟 | 185.6±20.4 ms | 146.3±17.4 ms | **21.1%** |
| P90 延迟 | 378.8±90.8 ms | 333.5±64.7 ms | **11.9%** |
| Cache miss 率 | — | — | **减少 33%** |
| 内存使用 | — | — | **减少 17%** |
| CPU 使用 | — | — | **减少 18.6%** |

---

## 六、批判性分析

1. **仿真与生产结果差距明显**：仿真显示 42% 平均延迟改进和 50% 尾延迟改进，但生产环境仅为 21.1% 和 11.9%。论文将此归因于冲突重试等未建模因素，但这恰恰说明仿真器的"high-fidelity"标签值得商榷——遗漏了影响延迟的关键因素。

2. **仅部署了简化版本**：生产中部署的是 LatCache-request（不使用 lower-level cache 信息），而非论文重点分析的 LatCache-rule。论文声称两者性能相近，但在仿真中 LatCache-rule 的缓存内存节省明显优于 LatCache-request（0.77 vs 0.85），这一优势是否在生产中成立未经验证。

3. **基线选择偏弱**：与 Protean 的 work-stealing、Round-Robin、Random 等简单策略比较。论文承认其他大规模 VM allocator（如 Omega、Twine）的调度算法未公开文档，无法比较，但这也意味着 Kamino 的优势可能在更先进的工业系统中不那么显著。

4. **延迟估计的"乐观假设"缺乏鲁棒性分析**：LatCache 假设队列中所有请求处理完后其数据仍在缓存中（"augmented cache state"），论文仅表示"在实践中足够准确"，但未分析在高缓存压力（如大量不同类型请求突发）下这一假设何时失效及其影响。

5. **LSM tree 的扩展实验过于初步**：论文声称 LatCache 原理可推广到 LSM tree、CDN 等场景，但附录中的 LevelDB 实验仅使用单线程、单一 workload，22% 的延迟改进缺乏说服力和实用价值。

6. **缺少对全局调度的讨论**：Kamino 仅解决节点内 AA 的请求调度，节点间的前端 load balancer 如何与 LatCache 协同未做分析。实际系统中，节点间调度质量直接影响节点内调度的有效性。

---

## 七、AI Infra / MLSys 视角

1. **延迟驱动调度的启发**：AI 推理服务（如 vLLM、TensorRT-LLM）面临类似问题——不同请求的 KV cache 命中情况差异巨大，prefix caching 的命中率直接影响 TTFT。LatCache 的"估算端到端延迟再调度"思路可迁移到多实例 LLM serving 的请求路由中，特别是在 prefix caching 场景下，将请求路由到 prefix 命中率最高且队列最短的实例。

2. **层次化缓存感知的借鉴**：LLM 推理中的 KV cache 同样具有层次性——prefix 匹配可以是完全匹配（类似 fast path）或部分匹配（类似 slow path）。LatCache 对部分命中的建模方式值得参考。

3. **可操作的 future work**：
   - 将 LatCache 原理应用于 disaggregated serving 架构（如 prefill-decode 分离），在 prefill 实例间做缓存感知的请求路由
   - 在 MoE 模型推理中，专家缓存（expert cache）的调度与 VM 规则缓存有结构相似性，可探索延迟驱动的专家调度
   - LatCache 的理论框架（在线作业调度 + 缓存耦合）可为 LLM 请求调度提供形式化分析工具

---

## 八、总结

Kamino 是 Azure 生产环境中部署的延迟驱动、缓存感知的 VM 分配请求调度框架。其核心算法 LatCache 通过估算每个 AA 的端到端延迟（融合层次化缓存状态和队列状态）来做出调度决策，具有理论最优负载均衡保证。在生产部署中实现了 21% 平均延迟降低、33% cache miss 减少和 17% 内存节省。该系统的主要价值在于将缓存感知与延迟驱动调度统一在一个框架中，且调度开销可忽略。局限在于仅解决节点内调度、生产改进低于仿真预期、且扩展到其他领域的实验不够充分。
