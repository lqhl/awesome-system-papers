# 3L-Cache: Low Overhead and Precise Learning-based Eviction Policy for Caches

**作者**：Wenbin Zhou (Beijing University of Technology), Zhixiong Niu, Yongqiang Xiong (Microsoft Research), Juan Fang, Qian Wang (Beijing University of Technology)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/zhou-wenbin
**源文件**：[[fast2025-zhou-wenbin.pdf]]

---

## 一、背景

缓存是现代生产系统中的核心组件，能有效降低请求延迟和网络流量。例如 2020 年 Netflix 占跨大西洋电缆总带宽的 1%，其中 95% 的流量直接由缓存服务。缓存的核心在于其**驱逐策略（eviction policy）**，性能通常用两个指标衡量：**object miss ratio**（未命中请求的比例）和 **byte miss ratio**（未命中数据量的比例）。

近年来，学习型驱逐策略从启发式方法（LRU、ARC、SIEVE 等）发展出三大类别：policy-level learning（如 LeCaR、CACHEUS）、group-level learning（如 GL-Cache）和 object-level learning（如 LRB、HALP）。其中 object-level learning 在 miss ratio 上表现最优，但计算开销巨大——LRB 的平均 CPU 开销是 LRU 的 172.5 倍，这使得在生产级 CDN 集群中部署学习型策略在经济上不可行。

---

## 二、要解决的问题

1. **Object-level learning 计算开销过高**：LRB 在小缓存下 CPU 开销为 LRU 的 172×，HALP 为 23×。实时 CPU 开销波动剧烈（峰值可达 300×），按均值部署无法满足峰值需求。
2. **训练存在大量计算浪费**：降低训练频率在一定范围内对 miss ratio 几乎无影响，但现有方法无法自动找到合适的训练频率。
3. **预测开销过高**：LRB 每次驱逐采样 64 个对象只驱逐 1 个（eviction ratio 仅 1.56%），存在极大的预测浪费。
4. **泛化性不足**：不同 trace 和缓存大小下，最优参数差异显著，需要自动适配。

---

## 三、洞察与设计

**关键洞察**：object-level learning 策略中，训练和预测占总计算开销的 70%，但两者都存在巨大的优化空间——训练频率可大幅降低而不影响准确性（将 LRB 训练频率从 2³ 降到 2⁻³ 次/百万请求，CPU 开销降 48% 而 miss ratio 几乎不变）；生产 trace 中 72% 的缓存对象仅被请求一次，意味着 eviction ratio 理论上可以从当前的 1.56%~25% 提升到 72%。

基于此洞察，3L-Cache 设计了四个核心模块：

### 1. 训练数据收集（Training Data Collection）
- **滑动窗口粗粒度调整**：窗口大小动态设为 h_sw × 缓存队列中的对象数，每次增 1 即可扩展一个缓存大小的信息量，避免 LRB 那样需要数十到数百次测试。
- **采样与标签规则**：面向对象采样（而非面向请求），防止训练数据偏向热门对象；已采样对象在收到新请求前不会重复记录；每 M=64K 条标记数据触发一次模型重训。

### 2. 双向采样策略（Bidirectional Sampling）
- **从尾部采样**：缓存队列尾部聚集冷门对象（与 LRU 行为一致），队列前 x% 全部采样，其余部分只采样访问频率 ≤ f 的对象。
- **从头部采样**：新到对象和命中对象混在队列头部，用一个 recorded queue 记录新到对象的 ID，优先采样在缓存中驻留最久的新对象，同时控制新对象占比不超过 Q%。

### 3. 高效对象驱逐（Efficient Object Eviction）
- **Eviction ratio 设为 1/2**：两种采样方式产出约 1:1 的候选，实验证明 1/2 是平衡 miss ratio 和开销的最优点。
- **Max heap + Hash table**：存储所有候选的预测结果，堆顶即为下次访问时间最远的对象，查询 O(1)、插入 O(log n)。堆和哈希表异步更新，以哈希表为准校验堆顶有效性。

### 4. 参数自动调优（Auto-tuning）
- h_sw、f、x、Q、n 五个参数各有触发条件和调整规则，在每轮采样结束时自动更新，开销极低。

---

## 四、实现细节

- **模型**：使用 LightGBM（Gradient Boosting Machine），预测 log(next-arrival-time-interval)。
- **特征**：仅 6 个特征——age、size、frequency、三个最近的 inter-arrival times（不足时填 ∞）。
- **存储开销**：每对象平均 67 bytes（Wikipedia CDN 数据集中，约占缓存空间 0.4%~2.5%）。
- **初始阶段**：模型训练完成前使用 LRU。
- **实现**：基于 libCacheSim 库实现模拟器；原型系统用 Python Flask + urllib 实现，处理真实 HTTP 请求。
- **源码**：https://github.com/optiq-lab/3L-Cache

---

## 五、实验结果

实验使用 8 个公开数据集共 4855 条 trace，涵盖 2015-2023 年的 CDN、KV、块存储等多种工作负载（总计约 2670 亿请求、147 亿对象）。对比 12 种策略（6 启发式 + 6 学习型），在 0.1% 和 10% footprint 两种缓存大小下评估。

| 指标 | 结果 |
|------|------|
| **Byte miss ratio** | 小缓存下 69.8% 的 trace 最优，大缓存下 41.2% 最优（次优 LRB 仅 10.2% / 18.5%） |
| **Object miss ratio** | 优于 ARC、SIEVE、S3-FIFO、TinyLFU、LeCaR、CACHEUS、LRB、HALP |
| **CPU 开销** | 比 HALP 降低 60.9%，比 LRB 降低 94.9%；小缓存仅 LRU 的 6.4×，大缓存仅 3.4× |
| **训练开销削减** | 比 LRB 降 90.9%~92.5%，比 HALP 降 34.7%~46.6% |
| **预测开销削减** | 比 LRB 降 96.5%~98.5%，比 HALP 降 76.1%~85.6% |
| **自动调优** | 小缓存 81.6% trace 最优，大缓存 53.6% trace 最优 |
| **加速 LRB** | 将 3L-Cache 方法应用于 LRB，CPU 开销降 80%，byte miss ratio 降 0.6% |
| **原型 vs 模拟** | Byte hit ratio 差异仅 2%；CPU 开销 3×~6× LRU |

---

## 六、批判性分析

1. **大缓存下 byte miss ratio 优势收窄**：3L-Cache 在大缓存下仅 41.2% trace 最优（小缓存 69.8%），论文承认 GDSF 在大缓存时因评估所有对象权重而更优，这暴露了采样方法在大缓存下的固有局限，但论文未深入讨论何时应回退到非采样策略。

2. **CPU 开销的绝对值仍然不低**：虽然 3L-Cache 相比 LRB/HALP 大幅降低，但仍为 LRU 的 3.4×~6.4×，在大规模 CDN 部署中仍意味着可观的额外成本。论文将此与 LHD（2.6×）对比，但 LHD 是启发式策略且不需训练。

3. **M=64K 的选择缺乏理论依据**：论文只说测试了几个值（16K~512K）发现 [32K, 128K] 范围效果好，就选了 64K。这种 grid search 式的选择在不同规模的工作负载下是否稳健存疑。

4. **原型评估仅用单条 trace**：原型系统仅在 Tencent CBS 的一条 trace 上验证，未在多数据集上进行，且使用 Python 实现（而非 C/C++），性能数据的参考价值有限。

5. **Eviction ratio 1/2 的设定偏粗糙**：论文声称两种采样方式产出约 1:1 的候选所以设为 1/2，但不同 trace 的访问模式差异极大，这个"约 1:1"的假设未给出充分的统计验证。

6. **论文自己提到的关键局限被轻描淡写**：当工作负载不符合 Zipf 分布时（如非典型 web caching），双向采样退化为随机采样。论文在结论中一笔带过，但未量化在这些场景下的性能退化程度。

---

## 七、AI Infra / MLSys 视角

1. **KV Cache 驱逐的启发**：大语言模型推理中的 KV cache 管理面临类似问题——在有限显存中决定保留哪些 token 的 KV 状态。3L-Cache 的双向采样思路（区分"老旧冷门"和"新到冷门"）可以启发 KV cache eviction 策略的设计，尤其是在长上下文推理场景中。

2. **轻量级在线学习的范式**：3L-Cache 证明了用 6 个简单特征 + LightGBM 就能在大规模生产 trace 上达到接近最优的驱逐决策。这种"极简特征 + 轻量模型"的范式对 AI Infra 中各种需要在线决策的场景（如请求调度、prefetch 策略、内存分层）具有借鉴价值。

3. **训练频率自适应**：3L-Cache 的核心发现——"大幅降低训练频率对准确性影响微小"——对 MLSys 中的在线学习系统有普遍意义。在推理服务的动态 batching、autoscaling 等场景中，模型更新频率与系统开销之间的 trade-off 可以采用类似的自适应方案。

4. **可操作的延伸方向**：
   - 将 3L-Cache 的方法迁移到 GPU 显存中的 tensor offloading 决策（哪些 tensor 保留在 GPU、哪些 offload 到 CPU/NVMe）
   - 探索用 3L-Cache 类似的预测机制来优化分布式训练中的 parameter server cache 或 embedding table cache

---

## 八、总结

3L-Cache 是首个在 CPU 开销、object miss ratio 和 byte miss ratio 三个维度上同时表现优异的学习型缓存驱逐策略。通过训练数据过滤、双向采样和自动参数调优三项关键设计，将 object-level learning 的计算开销从 LRU 的数十上百倍降至个位数倍。在 4855 条生产 trace 上的大规模评估展示了其泛化性，且方法可迁移至其他 object-level learning 策略。主要局限在于采样方法在大缓存和非 Zipf 工作负载下的效果收窄，以及原型评估的覆盖面有限。
