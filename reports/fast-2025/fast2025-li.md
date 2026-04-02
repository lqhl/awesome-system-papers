# Archer: Adaptive Memory Compression with Page-Association-Rule Awareness for High-Speed Response of Mobile Devices

**作者**：Changlong Li (East China Normal University), Zongwei Zhu (USTC), Chao Wang (USTC), Fangming Liu (HUST & Peng Cheng Laboratory), Fei Xu (ECNU), Edwin H.-M. Sha (ECNU), Xuehai Zhou (USTC)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/li
**源文件**：[[fast2025-li.pdf]]

---

## 一、背景

移动设备内存资源紧张是一个长期存在的问题。随着 AI、AR/VR、Transformer 等内存密集型任务在移动端的部署，内存压力持续加剧。现代移动操作系统（Android、iOS）广泛采用内存压缩技术来缓解这一问题：将最不活跃的内存页压缩，腾出空间给新的内存需求。

当前的内存压缩方案均以页（4KB）为粒度逐页压缩。这在内存需求平稳时表现尚可，但在突发内存需求场景下（如 App 启动、连拍、短视频滑动），频繁的逐页压缩会导致严重的性能退化——App 启动延迟增加 68.7%，连拍速度下降 1.6x，短视频帧率从 50fps 降至 27fps。

---

## 二、要解决的问题

1. **逐页压缩的 CPU 带宽浪费**：每次压缩一个 4KB 页面，频繁被软件栈函数和上下文切换打断，CPU 利用率低（仅约 53.8%），压缩效率差。
2. **直接回收（direct reclaim）的优先级反转**：前台应用的内存分配必须等待后台压缩完成，导致主任务被挂起。
3. **匿名页占比高且全部需要压缩**：93% 的文件页未被修改可直接释放，但所有匿名页都是脏页需要压缩；匿名页与文件页的比例在使用过程中从 1:1 增长到 3:1。
4. **缺乏对页面关联性的感知**：现有系统完全忽略了内存页之间的隐式关联关系，无法利用这种关联进行批量压缩。

---

## 三、洞察与设计

**关键洞察**：移动设备上约 26.3% 的匿名内存页具有高度关联性（>80% 的概率被一起访问），且这种关联呈两极分化——页面之间要么几乎没有关系，要么几乎总是同时被访问。这种关联源于移动应用的使用模式（如 36.2% 的匿名页仅在 App 启动阶段被访问，92.1% 的相机相关匿名页仅在调用相机时被访问）。

基于这一洞察，Archer 提出将关联规则挖掘（Association Rule Mining）引入内存压缩，将高度关联的页面一起压缩，从而在不引入读放大的前提下实现大粒度压缩，提升 CPU 压缩带宽。

系统由三个核心组件构成：

1. **Footprint Stream Generator (FSG)**：实时收集页面访问足迹，使用滑动窗口将访问序列转换为事务（transaction），以半离线方式异步挖掘页面关联。
2. **Frequent-pattern Tree List (FT-List)**：将 LRU 与 FP-tree 协同设计。主链是传统的 inactive LRU list，每个应用对应一棵 FP-tree（以 UID 为根节点），用于高效索引和管理关联页面。利用 app-aware 的关联挖掘（93.1% 的关联页属于同一应用）降低挖掘开销。
3. **Adaptive Compression Region (ACR)**：基于 ZRAM 改造压缩区域，支持任意粒度的压缩存储。将多个关联页合并为一个大 block 压缩后，拆分为多个 object 存储在 slot 中，通过 metadata 和 vhandle 机制索引。

工作流程分为 narrow track（内存压力低时逐页压缩）和 wide track（突发内存需求时批量压缩关联页面）。

---

## 四、实现细节

- **FSG 实现**：利用 Linux 内核已有的页面访问监控接口，使用物理地址标识页面。维护 FIFO 循环队列记录访问历史，滑动窗口宽度 w=32，超时阈值 ΔT=3s。当 CPU 利用率超过 80% 时暂停挖掘任务。
- **FP-Growth 挖掘**：每 3 秒心跳周期触发一次挖掘。队列长度 256，事务缓冲区 128KB。FP-tree 的 confidence=70%，support count=0.2。溢出的事务直接丢弃以限制开销。
- **FT-List**：按 Android Adj 机制排序应用活跃度，越不活跃的应用越靠近链表头部（优先被回收）。当 `_alloc_pages_nodemask()` 的 order 参数 >8 时触发大粒度压缩。
- **ACR**：基于 ZRAM 的 buddy system 分配机制，将大 block 拆分为多个 object 存储。通过 PTE flag 位区分逐页压缩和批量压缩的数据。解压时通过 vhandle 链找到所有 object 并重组，其他预取页保留在 swap cache 中。
- **压缩算法**：使用 lz4，与商用手机默认配置一致。
- **实验平台**：Google Pixel6 Pro (12GB RAM, Android 13)、Pixel3 (4GB RAM, Android 10)、HUAWEI P20 (6GB RAM, Android 9)。

---

## 五、实验结果

### App 启动速度

| 指标 | Pixel6 | Pixel3 | P20 |
|------|--------|--------|-----|
| Cold launch 加速（vs ZRAM） | 37.2% | 32.9% | 30.6% |
| Hot launch 加速（vs ZRAM） | 55.3% | 47.5% | 29.6% |
| Hot launch 加速（vs ASAP） | 16.6% | - | - |

### 连拍与帧率

| 指标 | Pixel6 | Pixel3 | P20 |
|------|--------|--------|-----|
| 连拍速度提升（vs ZRAM） | 1.42x | 1.34x | 1.22x |
| 帧率提升（vs ZRAM） | 1.31x | 1.36x | 1.35x |

### Tail Latency（Pixel6）

- Cold launch tail latency 降低 44.9%
- Hot launch tail latency 降低 60.3%
- 连拍 worst-case 性能提升 1.6x，帧渲染提升 1.3x

### 压缩吞吐

- 4KB 粒度：205.1 MB/s（与 ZRAM 接近）
- ≥512KB 粒度：522.6 MB/s（2.5x 提升）
- App 启动过程中 80.5%（cold）/ 83.2%（hot）的页面被大粒度压缩

### 开销

| 开销类型 | 数值 |
|---------|------|
| 读放大 | ≤1.08（92.6% 的批量解压页面很快被访问） |
| 能耗增加 | 0.69%（12 小时续航下减少约 5 分钟） |
| 内存开销 | ~640KB（mapping table 384KB + queue 1KB + buffer 128KB + compression buffer 128KB） |

### Transformer 推理

在 Pixel6 上，Transformer 推理延迟降低 39.2%。

---

## 六、批判性分析

1. **实验设备过于老旧**：P20（2018 年）和 Pixel3（2018 年）已经非常过时，Pixel6（2021 年）也并非最新。在 2025 年的论文中使用 4-6 年前的设备，难以证明方案在当代硬件上的适用性和必要性——当前旗舰手机已普遍配备 12-16GB RAM，内存压力场景可能有显著变化。

2. **参数敏感性分析不充分**：论文承认 w、ΔT、confidence 等参数对性能有重要影响，并指出"一个设备上的参数不应直接移植到另一设备"，但仅展示了 queue/buffer size 的敏感性分析。这意味着实际部署需要大量调参工作，论文对此未给出有效的自动化方案。

3. **SHSC 基线不够公平**：Static Huge-Size Compression 使用固定大粒度压缩，本质上是 Linux huge page 的简单变体，并非真正的 state-of-the-art 竞争对手。更有意义的对比应该是动态选择压缩粒度的方案。

4. **关联稳定性的验证过于简短**：论文仅提到"继续使用手机两小时后，96.3% 的关联页仍然高度相关"，但两小时的窗口对于真实使用场景远远不够。用户行为模式可能在数天内发生变化（如安装新应用、改变使用习惯），长期稳定性未被验证。

5. **Transformer 推理场景的评估缺乏深度**：仅给出一个 39.2% 的加速数字，没有说明具体模型、输入规模、batch size，也没有与专门的移动端推理优化方案对比。

6. **能耗评估方法粗糙**：使用"两部手机两个人同时操作"来对比能耗，人工操作的差异可能带来显著的测量噪声，且仅评估一小时的场景。

7. **读放大的微基准测试不在目标设备上进行**：论文将移动设备上的内存页收集后传到笔记本电脑上测量解压延迟，这引入了硬件差异，降低了结论的可信度。

---

## 七、AI Infra / MLSys 视角

1. **移动端推理的内存管理启发**：随着大模型端侧部署（如 on-device LLM）的趋势，Archer 揭示的页面关联性特征在 AI 推理场景中可能更加显著——注意力矩阵、KV cache、中间激活值具有天然的访问局部性和关联性。将关联规则挖掘应用于推理引擎的内存管理是一个值得探索的方向。

2. **大粒度压缩思路可迁移到 GPU 显存管理**：GPU 显存 offloading 场景（如 vLLM 的 KV cache offload）同样面临压缩粒度的权衡。Archer 的自适应粒度压缩思路可以应用于 GPU-CPU 之间的数据搬移。

3. **值得跟进的方向**：
   - 针对特定 AI workload（如 Transformer 推理）设计 workload-aware 的内存压缩策略，利用模型结构的可预测性（而非通用的关联规则挖掘）来确定压缩粒度
   - 在边缘设备多模型共存场景下，研究模型间内存页的关联性和调度策略

---

## 八、总结

Archer 提出了首个将关联规则挖掘引入移动设备内存压缩的框架，通过 FSG、FT-List、ACR 三个组件实现了对关联页面的自适应大粒度压缩。在三款真实设备上，App 启动速度平均提升 1.55x，连拍速度和帧率分别提升 1.42x 和 1.31x，尾延迟显著降低，额外能耗和内存开销可忽略不计。主要局限在于参数调优需要按设备定制、实验设备偏旧、关联稳定性的长期验证不足。该工作适用于内存受限的移动设备场景，为突发内存需求下的性能优化提供了新思路。
