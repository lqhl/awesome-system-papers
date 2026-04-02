# HiDPU: A DPU-Oriented Hybrid Indexing Scheme for Disaggregated Storage Systems

**作者**：Wenbin Zhu, Zhaoyan Shen, Qian Wei (Shandong University); Renhai Chen (Tianjin University & Huawei); Xin Yao (Huawei); Dongxiao Yu (Shandong University); Zili Shao (The Chinese University of Hong Kong)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/zhu
**源文件**：[[fast2025-zhu.pdf]]

---

## 一、背景

存算分离（Disaggregated Storage）架构将计算与存储解耦，实现资源独立扩展，已在数据中心广泛部署。在该架构中，存储服务器通过存储控制器（CPU）将后端 flash array 的物理地址空间映射为统一的逻辑地址空间，暴露给计算服务器。

Data Processing Unit (DPU) 作为一种专用网络/存储处理器，被部署在存储服务器的 PCIe 总线上，可直接访问后端 flash array，绕过 CPU 的额外内存拷贝，显著简化数据路径。然而，DPU 在数据访问前仍需与 CPU 交互进行地址翻译（逻辑地址到物理地址的映射查找），这一过程引入了显著的 CPU 计算开销和系统延迟。

---

## 二、要解决的问题

在 DPU 辅助的存算分离存储系统中，将索引查找完全卸载到 DPU 上面临三大挑战：

1. **DPU 内存资源有限**：DPU 板载内存通常只有 MB 级别，而 PB 级 flash array 的页表索引需要数十 GB 内存（如 1PB/16KB 页 = 64GB），远超 DPU 容量。
2. **DPU 算力受限**：DPU 的 SoC core 是轻量级、低功耗设计，优先吞吐而非计算复杂度，甚至缺少硬件浮点运算单元，无法直接运行复杂的索引计算。
3. **DPU-Host 交互开销高**：DPU 通过 PCIe 访问 host 内存的延迟远高于访问板载内存（18-628 倍），且随并发线程增加，PCIe 带宽争用进一步恶化延迟。实验显示，随客户端数从 1 增至 256，整体延迟从 4 µs 飙升至 5000+ µs，超过企业级 NVMe SSD 延迟。

---

## 三、洞察与设计

**关键洞察**：存储系统中的逻辑-物理地址映射具有不同程度的地址连续性（强连续、弱连续、完全随机），可以根据连续性特征对映射条目进行分段，并为每种连续性模式选择最适配的索引方式——连续段用线性函数精确计算、弱连续段用线性+完美哈希结合、随机段用纯完美哈希——从而在内存效率和查询性能之间取得最优平衡。

基于此洞察，HiDPU 设计了一个多层混合索引架构：

**底层：三种分段索引**
- **Accurate Segment**（强连续）：逻辑地址严格连续，只需存储 first key 和 address，通过线性函数 `LA - first_key + address` 直接定位，零误差。
- **PTHash Segment**（完全随机）：使用 Perfect Hash Table 映射，通过双重哈希保证无冲突，需存储 bucket 的 pilot 值。
- **LPTHash Segment**（弱连续）：创新性地将线性函数与 Perfect Hash 结合，用线性函数 `(LA - first_key) / div` 将连续 LA 分到同一 bucket，使连续 key 共享 pilot 值，提升缓存局部性。

**上层：Learned Inner Index**
- 在所有段之上构建多层 learned index，由线性函数组成的分层模型，用于快速定位目标 LA 所在的段。模型仅基于每段的 first key 训练，体积极小（~23KB）。

**DPU-Host 索引分配**
- DPU 侧：learned model + 段元数据（first key, address, hash 参数）+ Pilot Cache
- Host 侧：底层映射条目 + bucket pilot 数组

**Pilot Cache**：在 DPU 上缓存高频访问的 pilot 值，优先缓存 LPTHash 段的 pilot（因连续 key 共享 pilot，缓存命中率更高），采用分组原子计数器解决多线程并发更新问题。

**自适应分段策略**：初始将 N 个连续 key 段通过迭代合并到 P 个段，合并评分 `s_i = n_i + n_{i+1} + β·d_i` 平衡段大小与 key 距离。

---

## 四、实现细节

HiDPU 在华为 Hi1823 DPU 上实现，该 DPU 有数百个轻量级处理器 core，每 core 支持 4 个物理线程，每线程 4KB 本地内存，共享全局内存 4MB (SM)。

**定点数模型推理**：Hi1823 缺少浮点运算单元。HiDPU 提出 `uint_float` 方法：将斜率 k 乘以大常数 `uint_mask` 转为整数运算，临时扩展到 128 位防止溢出，并在模型训练时就使用 `uint_float` 确保推理精度。

**流水线化本地搜索**：将 learned index 的多次 SM 访问（加载 first key）和比较操作流水线化。BatchLD 将相邻的 first key 合并加载减少 SM 访问次数，下一批次 BatchLD 与当前批次的比较操作并行执行。

**数据复用**：在线程本地内存中缓存 index meta、root model 等元数据，连续查询落在同一段时复用之前加载的段索引数据。

**异步索引更新**：
- 插入操作由 host 侧 cuckoo hash buffer 暂存
- **Local Reconstruction**：buffer 满时触发，将新条目合并到对应段，使用 off-site 方式重建（旧表继续服务查询），通过 version 字段追踪缓存过期
- **Global Reconstruction**：空闲时全局重建，临时阻塞新查询，从底层重新构建索引并清空 DPU 缓存

开源代码：https://github.com/quieoo/lmpthash

---

## 五、实验结果

**平台**：96-core Intel Xeon Platinum 8260 CPU, 512GB DDR4, Huawei Hi1823 DPU, EulerOS Linux 4.18.0

**基线**：D-Page（三级页表）、D-Learned（多层 learned index）

**Workload**：4 个 Microsoft Research Cambridge block I/O trace (wdev/web/prn/proj) + 4 个应用基准测试 (oltp/websrv/tpcds/ycsbc)

| 指标 | HiDPU vs D-Page | HiDPU vs D-Learned |
|------|-----------------|-------------------|
| 吞吐量提升 | 1.1×–5.5× (micro), 1.3×–4.3× (macro) | 1.4×–6.3× (micro), 1.3×–1.5× (macro) |
| 延迟上限 | < 6.47 µs (micro), < 5.76 µs (macro) | D-Learned 最高 41.03 µs |
| 内存节省 | 最高 92% | D-Learned 固定 1.4× 开销 |
| DPU 内存占用 | 仅 23.74 KB（支持 1.2PB 存储） | D-Learned 在 0.04B 页时已无法维护索引 |

**Breakdown 分析**：
- Accurate Segment 引入后吞吐量提升 1.27×
- Pilot Cache 额外提升 1.03×
- LPTHash 将 pilot cache 命中率从 19% 提升至 80%–97%，额外提升 1.1×

**Local Reconstruction 影响**：重建期间缓存命中率平均仅降低 0.15%，延迟增加仅 0.69%。Global Reconstruction 在 1.2PB 数据量下可在 10 分钟内完成。

---

## 六、批判性分析

1. **硬件绑定性强**：实验完全基于华为 Hi1823 DPU，虽然论文声称设计适用于经典 DPU 架构（如 NVIDIA BlueField），但 BlueField 有 16GB 内存和更强算力的 ARM core，HiDPU 的很多设计权衡（如 uint_float 定点推理、极致的内存压缩）在 BlueField 上可能并非必要，反而引入了不必要的复杂性。缺乏在其他 DPU 平台上的验证。

2. **只读性能为主，写路径薄弱**：论文承认 workload 以读为主，但 local/global reconstruction 的设计仅通过一个混合 workload 实验做了简单验证。Global reconstruction 需要阻塞所有新查询，在 1.2PB 规模下需 10 分钟，对于在线服务场景这个停机时间可能不可接受，论文未深入讨论。

3. **Baseline 不够公平**：D-Page 仅将页表第一级放入 DPU（因内存限制），D-Learned 将 learned model 限制在 1MB 以内，这两个 baseline 的资源分配策略是否最优缺乏讨论。此外，与 state-of-the-art LearnedFTL 的比较仅展示了单客户端结果，未展示高并发下的表现。

4. **吞吐量提升范围跨度大**：1.1×–6.3× 的提升范围说明在某些 workload 下（如强连续地址的 proj）HiDPU 的优势不明显，论文未充分分析在什么条件下 HiDPU 的收益最大化。

5. **Pilot Cache 的 1MB 默认大小选择缺乏依据**：论文没有给出 cache size 的敏感性分析，也未讨论在更大规模存储（多 PB）下 1MB cache 是否仍然足够。

---

## 七、AI Infra / MLSys 视角

1. **索引卸载到异构硬件的方法论**：HiDPU 将索引按"热度"和"可计算性"在 DPU 和 Host 之间分层放置的思路，可迁移到 AI 推理系统中的 KV Cache 管理——例如将 KV Cache 的索引/元数据放在近计算端（GPU HBM），而实际数据放在远端（CPU DRAM 或 CXL 内存），通过 learned index 减少跨层访问。

2. **定点数推理技术**：uint_float 方法将浮点 learned model 转为纯整数运算，这与 AI 推理中的量化（INT8/INT4）思路一致。对于在低功耗设备（边缘 NPU）上部署 ML 模型的场景，这种训练时即采用低精度运算确保推理一致性的方法值得参考。

3. **连续性感知的分段策略**：在 AI 训练的 checkpoint 管理、参数服务器的 embedding table 分片中，参数访问也存在连续性差异，可以借鉴 HiDPU 的自适应分段思路优化地址翻译和数据放置。

4. **潜在 Future Work**：将 HiDPU 的混合索引方案应用到 GPU 直接存储（GDS/GPUDirect Storage）场景，在 NVMe-oF 链路上用 SmartNIC/DPU 加速 AI 训练数据加载的地址翻译，减少 CPU 参与。

---

## 八、总结

HiDPU 提出了面向 DPU 的混合索引方案，通过对地址映射按连续性分段（Accurate/PTHash/LPTHash），结合多层 learned index 和 Pilot Cache，在 DPU 极有限的内存（23KB）和算力条件下实现了高效的地址翻译。在华为 Hi1823 DPU 上的实验表明，相比传统页表和 learned index 方案，HiDPU 实现最高 92% 的内存节省和 6.3× 的查询性能提升。主要局限在于方案与特定 DPU 硬件强耦合，写密集场景下的 global reconstruction 阻塞问题有待解决，且缺乏在多种 DPU 平台上的可移植性验证。
