# On Scalable Integrity Checking for Secure Cloud Disks

**作者**：Quinn Burke, Ryan Sheatsley, Rachel King, Owen Hines, Michael Swift, Patrick McDaniel（University of Wisconsin–Madison）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/burke
**源文件**：[fast2025-burke.pdf](../../papers/fast-2025/fast2025-burke.pdf)

---

## 一、背景

云存储安全是现代云基础设施的核心挑战。随着针对云服务的攻击日益增多，可信云存储系统——通过硬件访问控制和密码学证明系统保障数据机密性和完整性——成为研究热点。Merkle hash tree 是保护存储数据完整性和新鲜性的标准方法，已广泛应用于 Linux dm-verity（Android 验证启动）、Intel SGX 安全内存等场景。

然而，hash tree 在 I/O 关键路径上引入了额外的计算（哈希）和 I/O（元数据获取）开销。对于高性能 NVMe 存储设备（访问延迟可低至 60µs），hash tree 的开销可能达到数百微秒，严重削弱设备性能。此前的研究主要集中在安全内存（volatile memory）场景，而 hash tree 在云块存储中的性能影响尚未被充分量化。

---

## 二、要解决的问题

1. **扩展性问题**：随着磁盘容量增大，平衡二叉 hash tree 的高度对数增长，导致每次读写需要计算的哈希数量增加。实验显示，1TB 磁盘上平衡二叉树的吞吐量损失可达 75%。

2. **CPU 哈希计算是瓶颈**：根因分析表明，hash tree 开销主要来自 CPU 哈希计算（而非元数据 I/O），因为 hash cache 命中率很高（>99%），但写操作仍必须遍历整条从叶到根的路径。

3. **高阶树并非解决方案**：安全内存领域广泛使用的 64-ary 树虽然降低了树高，但每个节点需要哈希更多内容，实际哈希成本反而最高，性能最差。

4. **静态平衡结构无法利用工作负载特征**：真实存储工作负载呈高度偏斜的 Zipfian 分布（少量块被频繁访问），但平衡树对所有块一视同仁，无法利用这种偏斜性。

---

## 三、洞察与设计

**关键洞察**：真实云存储工作负载的访问模式高度偏斜（Zipfian 分布），少量热数据块占据绝大多数访问。在最优 hash tree 中，这种偏斜会导致树极度不平衡——热数据的路径远短于冷数据（高度差可达 3×）。因此，寻找最优 hash tree 的问题可以归约为寻找最优前缀编码（Huffman coding）的问题：将访问频率视为符号权重，构造 Huffman 树即可最小化期望哈希计算次数。

基于这一洞察，论文提出了 **Dynamic Merkle Trees (DMTs)**：

- **理论基础**：证明了以 Huffman 编码构造的 hash tree 在已知 i.i.d. 访问分布下是最优的（最小化期望哈希计算次数），并建立了 **Optimal Tree Oracle (H-OPT)** 作为性能上界基准。

- **在线自适应设计**：由于实际中无法预知工作负载，DMTs 借鉴 splay tree 的思想，通过在线自调整逼近最优树。核心机制包括：
  - **随机化 splaying**：以较低概率（1%）对访问的节点执行 splay 操作，将热数据逐步提升至靠近根的位置
  - **热度分析**：每个节点附加热度计数器，splay 距离与热度成正比——热节点快速上升，冷节点缓慢移动
  - **三个启发式参数**：splay window flag（是否启用）、splay probability（触发概率）、splay distance（最大提升层数）

---

## 四、实现细节

- 使用 **BDUS** 框架实现自定义块设备驱动，在用户态拦截读写操作并执行 hash tree 逻辑，代码量约 5K 行 C++。

- **维护 hash tree 不变量的三个关键修改**：
  1. splay 操作作用于被访问叶节点的**父节点**（而非叶本身），确保叶节点始终是叶、内部节点始终是内部节点
  2. 传播子节点状态（左/右）到 splay 操作，必要时交换子节点，保持树结构合法
  3. splay 引入的不一致性通过预取并认证所有兄弟哈希来处理，旋转后立即重新计算从旋转点到根的所有父哈希

- **密码学配置**：数据块使用 AES-GCM 128-bit 加密，MAC 作为叶节点；内部节点使用 SHA-256 with 256-bit key。

- **缓存策略**：标准 LRU 替换策略，热度计数器在节点被缓存时初始化为零、被驱逐时重置。

- 开源代码：https://github.com/MadSP-McDaniel/dmt

---

## 五、实验结果

**实验环境**：AWS EC2 i4i.8xlarge（32 核，256GB 内存，本地 NVMe SSD）。

| 实验维度 | DMTs 表现 | 对比基线 |
|---------|----------|---------|
| 容量扩展（16MB–4TB） | 始终 >85% 最优吞吐量 | 二叉树在 4TB 损失 75%，64-ary 更差 |
| 吞吐量提升 | 最高 **2.2×** 优于 dm-verity | 随容量增大优势增大（1.3×→2.2×） |
| 延迟（P50/P99.9） | 显著低于所有平衡树 | 中位数和尾延迟均有同比例改善 |
| 工作负载偏斜度 | 高偏斜（Zipf θ≥2.0）下优势最大 | 均匀负载下仅有 6% 额外开销 |
| Cache 大小 | 0.1% cache 即优于二叉树 1% cache | 每单位 cache 内存的性价比更高 |
| Alibaba 真实 trace（4TB） | 1.3× 优于 dm-verity | 64-ary 损失 88% 吞吐量 |
| Filebench OLTP | 读 1.8×、写 1.7× 优于 dm-verity | 驱动层改善直接反映到应用层 |
| 动态负载切换 | 数秒内适应新 Zipfian 分布 | 在均匀阶段性能与二叉树持平 |

**存储/内存开销**：DMTs 需要额外存储父子指针和热度计数器（叶节点 0.44× 额外内存 / 0.29× 额外存储，内部节点 0.80× / 0.75×），但由于更高的 cache 效率，实际性价比更优。

---

## 六、批判性分析

1. **均匀负载下的退化**：DMTs 在均匀访问模式下有 6% 性能损失，且 4-ary/8-ary 平衡树在均匀场景下比 DMTs 高 25%。论文承认了这一点但并未提出解决方案，仅建议将 DMT 扩展到 4-ary 树——这是个明显的 future work 缺口。

2. **Splay 参数的敏感性未充分分析**：论文固定 splay probability p=0.01，但未系统分析不同 p 值对不同工作负载的影响。热度计数器的简单整数递增/递减方案（splay distance = hotness counter 值）缺乏理论支撑，论文也承认可用更复杂的 sketching 或 ML 方法，但未探索。

3. **并发模型的局限**：论文指出现有方案依赖全局树锁串行化更新，DMTs 也未解决这一问题。对于高并发写场景，这是一个根本性瓶颈。论文仅以单线程即可饱和设备带宽为由回避了这个问题，但未来更快的设备将使并发成为必须。

4. **最优性定义的局限**：H-OPT 基于 i.i.d. 假设，对非 i.i.d. 工作负载（如 Alibaba trace）可能低估上界。论文在 Alibaba 实验中 DMTs 甚至超过 H-OPT 正说明了这一点，但论文对此仅轻描淡写。

5. **安全性分析不够深入**：splay 操作改变了树结构，论文声称通过预取兄弟哈希和即时重新计算保持一致性，但缺乏对 crash consistency 的讨论——如果 splay 过程中系统崩溃，树的一致性如何恢复？

6. **实验基线选择**：只与自己实现的 dm-verity 风格二叉树和高阶树比较，未与其他已有的自适应或分层 hash tree 方案对比。

---

## 七、总结

本文系统分析了 Merkle hash tree 在云块存储中的性能开销，证明 CPU 哈希计算（而非 I/O）是主要瓶颈，并揭示了寻找最优 hash tree 与 Huffman 编码问题的等价性。基于此洞察，提出了 Dynamic Merkle Trees (DMTs)——一种基于 splay tree 的自适应非平衡 hash tree，通过学习工作负载模式在线逼近最优结构。DMTs 在偏斜工作负载下实现最高 2.2× 的吞吐量提升，适用于写密集型云存储场景。主要局限在于均匀负载下的小幅性能退化、全局锁的并发瓶颈、以及 crash consistency 等工程问题尚未解决。
