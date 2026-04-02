# Para-ksm: Parallelized Memory Deduplication with Data Streaming Accelerator

**作者**：Houxiang Ji (University of Illinois Urbana-Champaign), Minho Kim, Seonmu Oh (Daegu Gyeongbuk Institute of Science and Technology), Daehoon Kim (Yonsei University), Nam Sung Kim (University of Illinois Urbana-Champaign)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/ji
**源文件**：[[atc2025-ji.pdf]]

---

## 一、背景

内存技术缩放停滞、制造成本持续上升，使得内存占服务器总硬件成本的 30–50%。与此同时，虚拟化技术（VM、容器）在超大规模数据中心广泛部署，但不同 VM/容器间存在大量重复内存页（11%–86%），造成内存浪费。Linux 内核的 Kernel Same-page Merging (ksm) 是目前最主流的内存去重方案，Meta 等公司已在生产环境中部署。然而 ksm 带来的 datacenter tax 非常显著——消耗 14–65% 的 CPU 周期并污染 cache 层级，严重降低同机运行应用的性能。

另一方面，Intel 从第四代 Xeon 开始在片上集成了多种加速器，其中 Data Streaming Accelerator (DSA) 专门用于加速数据搬移和变换操作（memcpy、memcmp、CRC 等），具备虚拟内存支持、低延迟等优势。

---

## 二、要解决的问题

1. **ksm 的 datacenter tax 过高**：memcmp（页比较）和 xxhash（校验和计算）两个函数合计消耗 ksm 38% 的 CPU 周期，并导致严重的 cache 污染，使同机应用性能下降 1.6×–5.8×。
2. **朴素 DSA offload (DSA-ksm) 去重率大幅下降**：直接将 memcmp/xxhash 替换为 DSA 异步实现后，虽然 CPU 占用降低 85%，但由于片上 PCIe 通信开销，单次 offload 延迟是 CPU 的 2.6×–2.7×，导致去重速率仅为 CPU-ksm 的 5%–65%。
3. **ksm 的串行算法阻碍 batch 处理**：DSA 支持 batch descriptor 以摊销 offload 延迟（batch size=8 时延迟降低 81–83%），但 ksm 固有的串行设计——每次只选一个 candidate page、RB 树搜索中每次比较依赖上一次结果——使其无法利用 DSA 的 batch 能力。

---

## 三、洞察与设计

**关键洞察**：RB 树的 rebalancing 操作不会改变已有节点的 predecessor/successor 关系（性质 P1），且同一 batch 中不同 candidate page 要么共享相同的 (predecessor, successor) 对，要么拥有完全不相交的对（性质 P2）。因此可以安全地将多个 candidate page 的搜索和插入解耦、并行化，而不破坏 RB 树的正确性。

基于此洞察，论文提出 **Para-ksm**，重新设计 ksm 以支持并行处理：

- **Para-ksmC（Candidate Page Batching）**：一次选取 256 个连续 candidate page 组成 batch。搜索阶段，所有 candidate page 同时从 RB 树根节点开始搜索，每层生成一个 batch descriptor offload 到 DSA；搜索完成后，利用 hash table 按 predecessor 分组，组内排序后顺序插入。通过 `search_result` 结构追踪每个 candidate page 的 predecessor/successor，确保树 rebalancing 不影响其他 page 的插入位置。
- **Para-ksmT（Tree Page Batching）**：对单个 candidate page，投机性地与多层树节点并行比较。但由于 2^M - 1 次比较中只有 M 次有效，DSA 资源浪费严重，去重率仅为 CPU-ksm 的 9.2%，论文最终聚焦于 Para-ksmC。

---

## 四、实现细节

- **内核空间 DSA 库**：基于 IDXD 驱动的 API 构建内核态 DSA 函数库，封装 memcmp（DSA Comparison 操作）和 xxhash（DSA CRC Generation 操作），支持异步模式（提交后 sleep 让出 CPU，DSA 完成后中断唤醒）。
- **Work Descriptor / Batch Descriptor**：每个 WD 64B，包含操作类型、源地址、传输大小、completion record 地址等。BD 指向 WD 数组，单次 PCIe 事务提交多个 WD。
- **search_result 结构**：每个 candidate page 对应一个 search_result，记录 candidate page 地址及其在 RB 树中的 predecessor/successor 地址，搜索过程中动态更新。
- **Hash table 分组插入**：搜索完成后按 predecessor 地址哈希分组。组内多个 candidate page 按内容降序排序（CPU 端 memcmp），合并重复页后逐一插入，每次插入后更新组内后续 search_result 的 successor。
- **Batch size = 256**：经参数搜索确定，BD 利用率在 batch size ≤ 16 时 > 90%，256 时去重效率最优（效率提升 2.2×），更大 batch 因 comparison skewness 和 DSA 处理能力瓶颈而收益递减。
- **代码规模**：Para-ksm 约 300 行内核修改（对比 STYX 的 ~1300 LoC），利用 DSA 虚拟内存支持，无需 memory pinning 和地址转换。

---

## 五、实验结果

**实验平台**：Intel Xeon 8460Y+（40 核 @ 2.0GHz，HT 禁用），256GB DDR5-4800，1 组 DSA（1 个 64-entry WQ + 4 PE），40 个 VM（各 1 vCPU + 6GB RAM），Linux 6.2.15。

| 指标 | CPU-ksm | DSA-ksm | STYX | Para-ksmC |
|------|---------|---------|------|-----------|
| 性能退化（geomean，相对 no-ksm）| 3.3× | 1.3× | 1.4× | 2.1× |
| CPU 利用率（geomean）| 48.2% | 7.3% | 5.5% | 31.0% |
| LLC miss rate（geomean）| 30.5% | 22.1% | 21.9% | 25.0% |
| 去重效率（相对 CPU-ksm）| 1.0× | 0.05–0.65× | — | 1.3–1.5× |
| 去重效果（200s 内存节省）| 基准 | 12%@20s | 略低于 DSA-ksm | ~80%@100s，>99%@200s |

- **性能退化**：Para-ksmC 将应用性能退化从 CPU-ksm 的 1.6–5.8× 降至 1.3–2.7×。DSA-ksm 性能退化最低（1.0–1.6×），但去重效果差。
- **去重效率**：Para-ksmC 每千 CPU 周期的内存节省比 CPU-ksm 高 31–50%，是唯一同时改善去重效率和降低性能退化的方案。

---

## 六、批判性分析

1. **性能退化仍较高**：Para-ksmC 的 geomean 性能退化为 2.1×，而 DSA-ksm 仅 1.3×。论文强调 Para-ksmC 的去重效率优势，但在对延迟敏感的场景（如 Redis p99），2.1× 的退化可能仍不可接受。实际部署中 DSA-ksm 可能更实用（以去重速度换性能）。

2. **CPU 利用率下降有限**：Para-ksmC 的 CPU 利用率为 31%（vs CPU-ksm 48%），仅降低 36%，远逊于 DSA-ksm 的 85% 降幅。这是因为组内排序、successor 更新等操作仍在 CPU 上执行——即 Para-ksmC 为了提升去重率引入了额外 CPU 开销，部分抵消了 offload 收益。

3. **单一 DSA 配置**：实验仅使用 1 组 DSA（4 PE），未探索多组 DSA 或不同 PE 数量对性能的影响。Xeon 8460Y+ 支持更多 DSA 资源，扩展性分析缺失。

4. **Para-ksmT 几乎无效但占了大量篇幅**：Para-ksmT 去重率仅为 CPU-ksm 的 9.2%，论文自己也承认其不实用，但仍花费了一整节描述，设计空间探索的负面结果报告得过于详细。

5. **Comparison skewness 问题未根本解决**：batch size > 256 后 BD 利用率急剧下降（< 60% @512），但论文仅通过经验选择 batch size=256 规避问题，未提出自适应调整机制。

6. **与 STYX 的比较不完全公平**：STYX 使用 off-chip SmartNIC（BF-3），延迟天然更高。论文的核心贡献在于利用 on-chip DSA 的 batch 能力，但 on-chip vs off-chip 本身就是硬件代际优势，并非纯算法贡献。

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理中的 KV cache 去重**：当前 vLLM 等推理框架中多请求共享 prefix 时存在大量重复 KV cache page，ksm 的 page-level 去重思路可迁移。Para-ksm 的 batch 化 RB 树搜索设计对高吞吐 KV cache 共享检测有借鉴价值。

2. **DSA 在 AI 系统中的应用**：DSA 的 batch descriptor 机制不仅适用于内存去重，也适用于推理 serving 中的 tensor 搬移（host-to-device staging）、checkpoint 写入时的 CRC 校验等场景。论文中的 kernel-space DSA 库封装可直接复用。

3. **GPU 显存去重**：GPU 显存昂贵且容量有限，多租户 GPU 推理场景下模型权重/KV cache 的重复数据问题类似。将 Para-ksm 的并行化去重思路移植到 GPU 内存管理（配合 NVLink/CXL）是值得探索的方向。

4. **可操作的研究方向**：
   - 将 Para-ksm 的 candidate batch + 延迟插入思路应用于 PagedAttention 的 block table 管理
   - 利用 CXL Type-2 设备的计算能力替代 DSA 做更复杂的相似性检测（如近似去重）
   - 结合 application-level hint（如推理框架知道哪些请求共享 prefix）加速去重，避免盲扫

---

## 八、总结

Para-ksm 通过重新设计 Linux ksm 的串行算法，利用 RB 树 predecessor/successor 在 rebalancing 后不变的性质，实现了 candidate page 的批量化搜索与插入，从而充分利用 Intel DSA 的 batch descriptor 能力。相比 CPU-ksm，Para-ksm 在去重效率上提升 31–50%，同时将应用性能退化从 1.6–5.8× 降至 1.3–2.7×。其核心价值在于证明了 on-chip 加速器的有效利用需要算法层面的协同重设计，而非简单的函数替换。主要局限在于 CPU 利用率降幅有限、batch size 扩展性受 comparison skewness 制约，且实验仅覆盖单一 DSA 配置。
