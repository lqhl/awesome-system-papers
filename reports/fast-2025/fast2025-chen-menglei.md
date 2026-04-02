# GPHash: An Efficient Hash Index for GPU with Byte-Granularity Persistent Memory

**作者**：Menglei Chen, Yu Hua*, Zhangyu Chen, Ming Zhang, Gen Dong（华中科技大学 武汉光电国家研究中心 计算机学院）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/chen-menglei
**源文件**：[[fast2025-chen-menglei.pdf]]

---

## 一、背景

GPU 凭借高并行计算能力被广泛应用于深度学习训练/推理、数据库和科学计算等场景。这些应用需要管理大规模数据（如推荐系统中 TB 级别的 embedding 向量），但 GPU 显存容量有限且断电即失，因此数据通常存储在持久化存储设备上。

传统方案依赖 CPU 辅助管理存储中的数据（CPU-assisted data management），这引入了 GPU-CPU 之间耗时的数据传输开销以及额外的 CPU 资源消耗。NVIDIA GDS 技术虽然提供了 GPU 到块存储的直通路径，但只支持块级接口，无法满足 hash index 等数据结构对字节粒度访问的需求。

GPU with Persistent Memory（GPM）模型利用持久性内存（PM）的字节可寻址特性，通过 UVA 技术将 PM 映射到 GPU 虚拟地址空间，使 GPU 应用能够直接以字节粒度访问 PM，无需 CPU 参与。Hash index 作为高效的数据管理结构，是 GPM 系统中的关键组件。

---

## 二、要解决的问题

将现有 hash index 移植到 GPM 系统面临三大挑战：

1. **Warp-agnostic 执行导致性能下降**：传统 hash index 让每个线程独立执行操作，不感知 GPU 的 warp 执行特性。同一 warp 内线程执行不同路径时产生严重的 warp divergence；线程并行访问分散地址的 key 时导致 uncoalesced memory access。此外，lock-based 设计在数千并发 GPU 线程下加剧争用甚至造成死锁。

2. **Crash consistency 保障开销高**：PM 上原子写入单元受限于内存总线宽度（64位 CPU 上为 8 字节），超过此大小的写入在 crash 时可能导致数据不一致。传统 logging 和 CoW 技术虽能保证一致性，但引入大量额外 PM 写入。

3. **PM 与 GPU 之间巨大的带宽鸿沟**：GPU 显存带宽可达 900 GB/s（V100），而 PM 读带宽仅约 39.6 GB/s（6 块 Optane PMM），差距超过 20 倍。大量并发索引操作时，PM 有限带宽成为瓶颈，无法充分利用 GPU 并行能力。

---

## 三、洞察与设计

**关键洞察**：GPU warp 中 32 个线程天然可以协同工作——如果将 hash table 的 bucket 结构设计为恰好 32 个 slot，就能用一次 warp 级并行访问（one-shot warp access）完成对所有候选 slot 的探测；同时，利用 CAS 原语的 8 字节原子性恰好匹配 PM 的原子写入宽度，可以用 slot state 实现 log-free 操作，将 crash consistency 的开销降到接近零。

基于这一洞察，GPHash 的整体设计包含三个核心组件：

### 1. GPU-conscious & PM-friendly Hash Table 结构

- **Slot associativity**：每个 bucket 包含多个 slot，可处理多次 hash 冲突而无需数据迁移
- **Inter-level sharing**：多级 hash table 中低层 bucket 被高层多个 bucket 共享，提升负载均衡和内存效率
- **Multiple hash locations**：使用多个 hash 函数为每个 key 计算多个候选位置，指数级提升内存效率
- **One-shot warp access**：合理配置下（如 2 hash locations × 2-level × 8-way = 32 slots），一个 warp 的 32 个线程一次并行访问所有候选 slot
- **In-place key placement**：直接在 slot 中存储 key（而非指针），使同一 bucket 的 key 在连续内存中，促进 coalesced memory access

### 2. Lock-free Concurrency Control with Crash Consistency

- **Warp-cooperative execution**：所有索引操作以 warp 为粒度执行。使用 `ballot` 指令找到待处理线程，用 `shfl` 指令广播 key，32 线程协同完成一个操作
- **Lock-free & Log-free operations**：利用 CAS 原语和 slot state（EMPTY / INSERT / hash value）实现无锁无日志操作。插入时 CAS 将 state 从 EMPTY 改为 INSERT，写入数据后设置 fingerprint。Crash 恢复时只需检查 INSERT 状态的 slot 并清除
- 支持 duplicate items 容忍机制（valid item 规则）和 "no lost key" 并发正确性条件

### 3. Frozen-based Bucket Cache (BktCache)

- **Bucket 粒度缓存**：由于 one-shot warp access 总是访问整个 bucket，以 bucket 为粒度缓存比 item 粒度更自然，且元数据开销更小
- **Frozen-based 设计**：周期性加载热 bucket 到 GPU 显存，两次加载之间缓存成员不变（frozen phase），避免大量线程争用缓存管理数据结构
- **Concurrent loading**：使用独立 GPU stream 并行 fetch bucket，利用引用计数和映射关系的 CAS 更新保证并发正确性

---

## 四、实现细节

- **平台**：Linux 服务器，2× Intel Xeon Gold 6230R CPU，NVIDIA Tesla V100 GPU，192 GB DDR4 DRAM，768 GB Intel Optane DC PMM（6×128 GB，AppDirect 模式，ext4-DAX）
- **默认配置**：2L-2H-8S（2 hash locations，2-level buckets，8-way associativity = 32 slots/warp）
- **Slot 结构**：固定长度小 key（≤8 bytes）时存储 key + state + value pointer；大 key 时存储 fingerprint + state + key（in-place）+ value pointer；变长 key 时存储 fingerprint + state + KV pair pointer
- **Fingerprint**：使用 hash 值的一部分作为 16-bit fingerprint 快速比较，减少不必要的全 key 读取
- **State 编码**：在 fingerprint 值域中保留 `0xFFFFFFFFFFFFFFFF`（EMPTY）和 `0xFFFFFFFFFFFFFFFE`（INSERT）两个特殊值
- **Resizing**：分配新的 top level，GPU 线程并行 rehash bottom level items，利用 CAS 原子性容忍 crash
- **Recovery**：映射 PM 到 GPU 虚拟地址空间 → 检查 INSERT 状态 slot 并清除 → 若 `is_resizing` 标记为 true 则继续 rehash
- **BktCache 加载**：LFU 算法识别热 bucket，concurrent fetching 使用独立 GPU stream，引用计数控制并发安全
- **开源代码**：https://github.com/LighT-chenml/GPHash

---

## 五、实验结果

### 对比方案

| 类型 | 方案 |
|------|------|
| CPU-assisted | Clevel, Dash, SEPH |
| GPM（naive porting） | Clevel-GPM, SlabHash-GPM |
| GPM（本文） | GPHash |

### 主要结果

| 指标 | GPHash vs CPU-assisted | GPHash vs GPM indexes |
|------|----------------------|---------------------|
| 最大吞吐量提升 | 27.62× | 17.42× |
| YCSB 综合 | 各 workload 均显著领先 | 各 workload 均显著领先 |
| Real-world (DLRM, PageRank) | 最高 7.09× 吞吐量提升 | 最高 7.91× 延迟降低 |

### Factor Analysis（各技术贡献）

| 技术 | 吞吐量提升 |
|------|-----------|
| Warp-cooperative execution | 最高 104.1% |
| In-place key placement | 最高 13.7% |
| BktCache（skewed workload） | 最高 40.9% |

### 其他关键数据

- **Load factor**：最高可达 92%，远超 Clevel-GPM（~60%）和 SlabHash-GPM
- **Key size 敏感度**：8→128 bytes 时 GPHash 仅下降 13.1%，SlabHash-GPM 下降 38.6%
- **Resizing 时间**：数百毫秒级（GPU 并行 rehash）
- **Recovery 时间**：数百毫秒级（>99% 时间消耗在 GPM 初始化，即 PM 映射）
- **BktCache 最佳缓存比例**：~20%，兼顾性能和 GPU 显存占用

---

## 六、批判性分析

1. **硬件平台局限性**：实验仅在 Intel Optane DC PMM + NVIDIA V100 上进行。Optane PMM 已停产，V100 也是较老的 GPU 架构。论文虽声称设计可迁移到 CXL-based GPM 系统，但未提供任何 CXL 实验验证。CXL 设备的延迟特性、带宽特性与 Optane PMM 有显著差异，one-shot warp access 等设计在 CXL 上是否同样有效存疑。

2. **对比基线不够公平**：Clevel-GPM 和 SlabHash-GPM 是作者自行实现的 naive porting，并非专门为 GPM 优化的方案。用"直接移植"的弱基线来衬托 GPHash 的优势，说服力有限。真正有意义的对比应该是与同样针对 GPM 场景做了认真优化的方案进行比较。

3. **不支持并发 resizing**：论文在 Discussion 中承认不支持 concurrent resizing，且认为"社区普遍接受只支持 static resizing"。但在实际动态工作负载中，resizing 期间停服或性能骤降是严重问题。对于推荐系统等需要在线扩容的场景，这一局限可能是部署障碍。

4. **Variable-length key-value 支持不完善**：论文明确将 variable-length KV 的高效支持留作 future work，称"不是本工作的主要设计目标"。但实际应用中（如推荐系统的 feature key），变长 KV 是常见需求。

5. **BktCache 对 uniform workload 收益有限**：实验显示对均匀负载（YCSB D/LOAD）BktCache 仅有 7.6% 提升，而 BktCache 的设计和实现复杂度不低。论文对此轻描淡写，但均匀负载在生产环境中并不罕见。

6. **27.62× 的 headline 数字需要审慎看待**：这个最大提升是与 CPU-assisted 方案比较得来的，而 CPU-assisted 方案本身就包含 GPU-CPU 数据传输开销，并非一个公平的 apple-to-apple 对比。与同为 GPM 的 Clevel-GPM 相比，最大提升为 17.42×，但 Clevel-GPM 本身就是 naive porting。

---

## 七、AI Infra / MLSys 视角

1. **推荐系统 embedding lookup 加速**：论文明确提到 GPHash 可用于加速 DLRM 等推荐系统中的 embedding vector lookup（embedding_lookup）。在大规模推荐系统中，embedding table 可达 TB 级，传统方案依赖 CPU 管理 SSD/PM 上的 embedding 并传输给 GPU。GPHash 展示了 GPU 直接以字节粒度访问 PM 上 embedding 的可行路径，省去 CPU 中间环节。

2. **CXL 时代的 GPU 近存储计算**：随着 CXL 内存池化和 CXL-attached PM/NVM 设备的发展，GPHash 的设计思路（GPU 通过统一虚拟地址直接访问远端持久化存储）与 CXL disaggregated memory 架构高度契合。未来可探索 GPU 通过 CXL 访问远端 NVM 上的 KV store/embedding table。

3. **Warp-cooperative 执行模式的可迁移性**：GPHash 将 warp 内 32 线程协同执行一个操作的模式，可推广到 GPU 上的其他数据结构（B-tree、skip list、learned index 等）。对 GPU-based inference serving 中的 KV cache 管理、PagedAttention 的 page table 查找等也可能有借鉴意义。

4. **Frozen-based caching 的设计思想**：BktCache 的 frozen-based 设计（周期性更新缓存成员，中间阶段不变）对 GPU 上任何需要缓存管理的场景都有参考价值——核心思想是用略微过时的缓存换取零管理开销。这在 GPU inference 中的 KV cache prefetching、model weight offloading 等场景可能适用。

5. **值得跟进的方向**：
   - GPU 上的 variable-length KV store（结合高效 GPU allocator）用于动态 embedding table
   - CXL-based GPM 系统上的 hash index 实验验证和优化
   - 将 warp-cooperative + log-free 思路应用于 GPU 上的 learned index 或 LSM-tree

---

## 八、总结

GPHash 是首个专门为 GPU with Persistent Memory 系统设计的 hash index。其核心贡献在于三个层面的协同设计：GPU-conscious hash table 结构实现 one-shot warp access、CAS + slot state 实现 lock-free 且 log-free 的 crash consistency、frozen-based bucket cache 缓解 PM 带宽瓶颈。在 YCSB 和实际工作负载上，GPHash 比 CPU-assisted 方案和 naive GPM hash index 分别提升最高 27.62× 和 17.42×。主要局限在于实验平台依赖已停产的 Optane PMM，不支持 concurrent resizing 和高效的 variable-length KV，且 CXL 兼容性仅停留在理论分析层面。
