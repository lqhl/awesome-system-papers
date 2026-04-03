# Towards Optimal Rack-scale µs-level CPU Scheduling through In-Network Workload Shaping

**作者**：Xudong Liao, Han Tian, Xinchen Wan, Chaoliang Zeng, Hao Wang, Junxue Zhang, Mengyu Ma, Guyue (Grace) Liu, Kai Chen（香港科技大学 iSINGLab、中国科学技术大学、BitIntelligence、浪潮、北京大学）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/liao
**源文件**：[[atc2025-liao.pdf]]

---

## 一、背景

现代数据中心部署了大量面向用户的在线服务（如 key-value store、交互式分析、搜索排序、FaaS），这些服务通常要求在几十到几百微秒内提供高吞吐和低尾延迟。为了突破单机瓶颈，rack-scale CPU 调度应运而生——通过 ToR 可编程交换机在机架内多台服务器之间协调请求分发。

先驱工作 RackSched 提出了两层调度架构：交换机层做 inter-server 负载均衡（基于 JSQ），服务器层做 intra-server 调度（如 Shinjuku）。然而 RackSched 的 **application-agnostic** 设计存在根本缺陷：它对请求的 CPU 开销一无所知，导致负载均衡不准确，且每台服务器不得不面对混合长短请求带来的 Head-of-Line (HoL) blocking 问题。

---

## 二、要解决的问题

RackSched 在多样化工作负载下无法提供稳定的低尾延迟，原因有二：

1. **Inter-server 负载不均衡**：JSQ 仅根据队列长度分发请求，不感知每个请求的实际 CPU 开销。当长短请求混合时，相同队列长度对应截然不同的实际负载。加之 µs 级负载动态变化快，一个 RTT (~10µs) 的信息延迟就会导致调度决策基于过时数据。

2. **Intra-server HoL blocking**：由于交换机将长短请求混合分发给每台服务器，服务器必须自行解决 HoL 问题。实验表明，现有的 intra-server 调度算法（cFCFS、Time Sharing、DARC）在混合工作负载下均无法接近理想性能——与 Processor Sharing 理想方案相比，slowdown 可达 ~50×。

核心矛盾在于：**混合工作负载的调度本质上很难做好，而现有系统把这个难题留给了每台服务器**。

---

## 三、洞察与设计

**关键洞察**：虽然为每台服务器调度混合工作负载（长短请求并存）非常困难，但调度同质工作负载却很容易——当请求执行时间相近时，简单的 cFCFS 即可达到最优尾延迟。这从理论上也有支撑：M/G/K 排队问题可分解为多个 M/D/K 子问题，而 FCFS 对确定性轻尾工作负载是 tail-optimal 的。

基于此洞察，Pallas 提出 **in-network workload shaping**：在网络层（ToR 交换机）将混合工作负载主动变换为多组同质工作负载，而非被动地将难题留给服务器。这依赖两个现实条件：(1) 数据中心应用可通过包头暴露请求类型（如 Memcached 的命令类型、Redis 的协议字段、RPC 的 protobuf 类型），相同类型请求通常具有相似执行时间；(2) 可编程交换机可在数据平面解析包头并执行高级调度逻辑。

**Pallas 三层调度架构**：

- **Workload Shaper（ToR 交换机）**：根据请求类型将混合工作负载分组（shaping），每组内请求的 CPU 需求高度同质。
- **Intra-group Load Balancer（ToR 交换机）**：在组内服务器之间用 Weighted Round-Robin (WRR) 按预配计算能力分发请求，实现精确负载均衡。
- **Intra-server Scheduler（服务器端）**：对同质工作负载使用简单高效的 cFCFS；仅少数需处理多组请求的服务器使用 DARC。

**调度策略生成**（离线）：
- 用定制 k-means 聚类生成多个分组映射候选
- 通过离线模拟评估各候选的 P99 延迟
- 选择最优候选，按各组 CPU 需求比例分配服务器资源（核级粒度）

**长期工作负载变化适应**：
- 交换机控制面每 10ms 监控工作负载变化
- 当各组实际需求与分配资源偏差超过阈值 δ 时触发策略重配
- 增量更新策略表，最小化重配影响
- **Request Bouncing**：当服务器从处理长请求组转为短请求组时，将队列中的长请求弹回交换机重新调度，优先处理短请求，避免过渡期 HoL blocking

**短期突发处理**：
- 以 20µs 粒度检测单组请求速率突发
- **No-regret Request Cloning**：将突发组的请求克隆到空闲组的服务器处理；若目标服务器无空闲核则直接丢弃克隆，保证不会恶化性能（no-regret guarantee）
- 通过全局唯一请求 ID 过滤重复响应

---

## 四、实现细节

- **交换机数据面**：763 行 P4 代码，编译到 Intel Tofino ASIC，占用 2.8% SRAM 和 10.4% Stateful ALU
- **交换机控制面**：1067 行 Python 代码，通过 switch SDK 读取数据面寄存器统计并更新策略表
- **服务器端**：基于 Perséphone 扩展，增加 Pallas 包头支持、请求执行时间测量与响应编码、agent 接收调度策略、request bouncing 机制
- **客户端**：C 语言实现，使用 DPDK 进行高速用户态网络
- **包头格式**：8-bit Type + 8-bit Flag + 32-bit Index + 32-bit Time，分别用于分组、克隆标记、请求 ID 和执行时间记录
- **WRR 实现**：每组一个 P4 寄存器计数器，通过 ALU 操作递增并按权重范围确定目标服务器
- **工作负载监控**：两个 P4 寄存器——累计请求计数和 EWMA 执行时间（EWMA 因子 0.125，用位移实现除法）
- 当前假设每个请求包含在单个数据包中

---

## 五、实验结果

**实验平台**：10 台机器通过 Intel Tofino 交换机连接，每台双路 12 核 Xeon E5-2630 v2、64GB 内存、ConnectX-4 100G NIC、Ubuntu 18.04。8 台为服务器（每台 10 worker 线程），2 台为客户端。

**对比基线**：RS-DARC（RackSched + Perséphone DARC 调度）

### 合成工作负载

| 工作负载 | Pallas 优势 |
|---------|-------------|
| Normal Bimodal (90%短/10%长) | P99 延迟降低 16× @1.9Mrps；吞吐提升 1.5× @250µs 目标 |
| Port Bimodal (50%/50%) | P99 延迟降低 8.5× @0.7Mrps；吞吐提升 1.4× @300µs 目标 |
| Trimodal (33%/33%/33%) | 吞吐提升 2.0× @1200µs 目标；延迟降低 2.3× @0.18Mrps |
| TPC-C (5 种事务) | 吞吐提升 1.7× @200µs 目标 |

### RocksDB 真实应用

| 工作负载 | Pallas 优势 |
|---------|-------------|
| Normal RocksDB (90% GET/10% SCAN) | 稳定处理至 1Mrps 无延迟上升 |
| Port RocksDB (50%/50%) | P99 延迟降低 5.5×；高负载下降低两个数量级 |

### 动态工作负载

- Pallas 能快速适应工作负载分布变化（Port→Normal），通过 burst handling + request bouncing 将过渡期延迟尖峰有效控制
- 无策略重配的 Pallas 在工作负载变化后出现严重延迟膨胀

### 组件有效性

- **Workload Shaping**：高负载下实现跨服务器均衡负载，per-server slowdown 降低 7×
- **Request Bouncing**：有效抑制策略切换过渡期短请求的尾延迟波动
- **Burst Handling**：负载超过 1.9Mrps 后，Pallas 比无 burst handling 版本延迟降低 6.1×

### 与其他方案对比

在 Port Bimodal 下，Pallas 显著优于 R2P2、Horus、Draconis 和 RS-DARC，因为这些方案仍将混合工作负载分发至服务器。

### 可扩展性

吞吐几乎随服务器数量（2/4/8）线性扩展。

---

## 六、批判性分析

1. **请求类型与执行时间的关联假设过强**：Pallas 核心依赖"相同类型请求具有相似 CPU 执行时间"，但论文自己承认 Lucene 等复杂应用不满足此假设。Discussion 中提到可用 ML 模型解决，但这会引入额外延迟和复杂性，与 µs 级调度目标矛盾。

2. **实验规模受限**：仅 8 台服务器、10 worker/server 的 testbed 远小于生产环境。虽然附录展示了线性扩展性，但 workload shaping 的分组数随规模增长如何变化、策略生成的离线模拟开销是否可控均未讨论。

3. **单包假设是硬限制**：论文假设每个请求包含在单个数据包中，对大请求（如大 value 的 GET/PUT）不适用。虽然提到可复用 RackSched 的 request affinity 机制，但未验证整合后的资源开销和性能。

4. **基线选择不够严格**：RS-DARC 实际上是对 RackSched 的改造版本（用 Perséphone 替换了 Shinjuku，因硬件兼容性），而非原始 RackSched。这使得对比的公平性存疑——真正的 RackSched+Shinjuku 在某些场景下可能表现不同。

5. **工作负载变化检测粒度粗**：10ms 监控间隔对 µs 级服务来说相当粗糙。虽然 burst handling 覆盖了 sub-ms 突发，但两者之间（ms 级变化）存在盲区。

6. **资源碎片化问题被轻描淡写**：分组策略将服务器绑定到特定请求组，降低了资源复用灵活性。论文仅在 Discussion 中一笔带过多资源复用问题。

7. **缺乏与 DARC 单机优化的公平对比**：Perséphone 的 DARC 算法在单机上已能通过 core reservation 隔离长短请求。如果给 DARC 更多核或更好的参数调优，差距是否缩小？论文未探讨。

---

## 七、AI Infra / MLSys 视角

1. **推理服务调度的启发**：LLM 推理服务中 prefill 和 decode 请求具有显著不同的计算特征（类似本文的长短请求），disaggregated serving（如 DistServe、Splitwise）已采用类似的"按请求类型分流"思路。Pallas 的 in-network shaping 思路可进一步扩展：用可编程交换机在网络层根据请求 token 长度（可从包头的 metadata 推断）将 prefill/decode 请求分流到专用 GPU 集群，避免服务端的 scheduling 复杂性。

2. **MoE 路由的类比**：Workload shaping 的核心是"将异质负载变为同质负载再调度"，这与 MoE 模型中 expert 负载均衡有概念相似性。Pallas 的 k-means 聚类 + 微基准测试选择最优策略的方法论可迁移到 MoE routing 策略优化。

3. **Request cloning 在推理场景的应用**：Pallas 的 no-regret cloning 机制（克隆到空闲组、无空闲核则丢弃）对推理服务的冗余请求策略有借鉴意义——可在检测到推理请求排队突发时，将请求克隆到低负载 GPU，若目标 GPU 繁忙则放弃克隆，保证不增加额外延迟。

4. **可操作的研究方向**：
   - 将 workload shaping 扩展到 GPU 推理集群：用 SmartNIC 或可编程交换机根据请求特征（prompt 长度、batch size hint）做请求分流
   - 结合 KV cache 状态感知：让交换机感知各 GPU 的 KV cache 命中率，做更智能的 prefix-aware 路由
   - 多机架扩展：论文的 hierarchical shaping 思路（core switch + ToR switch）天然适用于大规模推理集群的多层调度

---

## 八、总结

Pallas 提出了一种 application-aware 的 rack-scale µs 级 CPU 调度方案，核心创新在于将调度问题转化为网络层的工作负载整形问题：通过 ToR 可编程交换机将混合工作负载分组为同质负载，使服务器端仅需简单的 cFCFS 即可达到近最优尾延迟。配合 request bouncing 和 no-regret cloning 机制应对动态变化和突发，Pallas 在合成和真实工作负载下均大幅优于 RackSched（尾延迟降低 5-100×）。其局限在于依赖请求类型与 CPU 开销的强关联假设、单包请求限制，以及仅验证了单机架小规模部署。
