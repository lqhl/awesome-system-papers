# DSA-2LM: A CPU-Free Tiered Memory Architecture with Intel DSA

**作者**：Ruili Liu (清华大学 / 电子科技大学), Teng Ma (阿里巴巴), Mingxing Zhang, Jialiang Huang, Yingdi Shan (清华大学), Zheng Liu (阿里巴巴), Lingfeng Xiang, Zhen Lin, Hui Lu, Jia Rao (UT Arlington), Kang Chen, Yongwei Wu (清华大学)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/liu-ruili
**源文件**：[[atc2025-liu-ruili.pdf]]

---

## 一、背景

数据密集型应用（图处理、机器学习等）对内存容量的需求持续增长，而 DRAM 成本高昂（Azure 中内存占服务器总成本约 50%）。CXL Memory、NVM 等非 DRAM 设备以较低的单位成本提供大容量内存，但延迟高于本地 DRAM。Tiered Memory 系统通过将热数据放在快速层（DRAM）、冷数据放在慢速层（CXL/NVM）来平衡性能与成本。

现有 tiered memory 系统（TPP、MEMTIS、NOMAD 等）面临核心矛盾：更精确的热度检测和更频繁的页迁移能改善数据放置，但都会消耗大量 CPU 资源（PEBS 采样导致 20% 性能下降，页拷贝占 migrate 过程 73.5% 的 CPU 周期），反而干扰应用性能。

Intel Data Streaming Accelerator (DSA) 是 4/5 代 Xeon 处理器的标配硬件加速器，可在不占用 CPU 的情况下以最高 32 GB/s 的带宽搬移内存数据，为解决上述矛盾提供了硬件基础。

---

## 二、要解决的问题

1. **页拷贝的 CPU 开销过大**：在 MEMTIS 的 profiling 中，migrate 过程占总 CPU 采样的 72.87%，其中页拷贝（migrate_page_copy）单独占 25.31%。CPU 既要运行应用又要做页拷贝，两者争抢资源。

2. **现有内核 DMA 接口不适合细粒度页迁移**：Linux 内核的 DMA 接口需要额外的 buffer 映射/解映射（88 ns 开销），且需要 memory pinning，在 tiered memory 场景下尤其有问题。

3. **4KB 小页无法直接受益于 DSA**：DSA 在传输大小 < 32KB 时性能不如 CPU 拷贝，而 tiered memory 中 4KB 基础页占相当比例，需要设计聚合数据通路。

4. **DSA 参数敏感**：Work Queue 数量和 batch size 对吞吐有显著影响，不同页面组合需要不同配置，需要自适应调优。

---

## 三、洞察与设计

**关键洞察**：DSA 的单次调用延迟高于 CPU 拷贝（小于 32KB 时），但其 pipeline 化的描述符处理机制使得通过 batching 多个小页和多 WQ 并行可以隐藏调用延迟，从而让 4KB 小页也能受益于 DSA 加速；同时 DSA 使用共享虚拟内存（SVM），无需 IOMMU 页表映射和 memory pinning，可以绕过 DMA 接口直接在内核空间使用物理地址提交描述符。

基于此洞察，DSA-2LM 的核心设计包括三个层面：

### 快速迁移工作流（§3.3）
- 继承 MEMTIS 的直方图热度检测算法和 kmigrated 内核线程
- 维护 promotion list（慢→快）和 demotion list（快→慢）
- 因为 DSA 是 CPU-free 的，可以缩短 kmigrated 唤醒间隔，采取更激进的迁移策略而不增加额外开销
- 改进 MEMTIS 的采样算法，始终使用最新样本避免过期数据

### 聚合数据通路（Aggregated Data Path）
- 不区分 4KB/2MB 走不同路径，而是统一处理：
  - 第一遍：将 2MB Huge Page 拆分为多个 256KB 子页，round-robin 分配到各 WQ 并行拷贝
  - 第二遍：将 4KB 基础页聚合为 batch list，均匀分配到各 WQ
- 通过 batch 提交消除小页的 DSA 调用开销

### 自适应并发迁移（§3.4）
- 动态调整 batch size 和 WQ 数量
- 利用 Linux 内核的 completion 机制实现真正的异步等待（MSI-X 中断唤醒），而非用户态的 UMWAIT 或 sched_yield

---

## 四、实现细节

- 基于 Linux 内核 5.13/5.15 实现，修改内存管理子系统约 2K LoC，从内核 6.4 反向移植 IDXD 和 IOMMU 驱动约 8K LoC
- 在 `misc/exp` 目录下实现额外模块，暴露两个新 API：`dsa_multi_copy_pages` 和 `dsa_copy_page_lists`
- DSA 描述符（`idxd_desc`、`dsa_hw_desc`、`dsa_completion_record`）作为 per-cpu 全局变量在初始化阶段创建，避免运行时动态分配开销
- 绕过 DMA 接口，直接使用物理地址提交 DSA 描述符，内核空间操作不触发页错误
- 每个 DSA 设备配置 4 个 Processing Engine 和 1 个 WQ，默认 `limit_chans=8`
- 通过 sysfs API 可动态调整参数，procfs 提供监控统计
- 代码开源：https://github.com/madsys-dev/DSA-2LM

---

## 五、实验结果

**硬件平台**：双路 4th Gen Xeon Platinum（48×2 物理核），每 socket 1TB DDR5，一个 socket 连接 64GB ASIC-based Montage CXL 设备。DRAM NUMA 节点延迟 112 ns，CXL 节点延迟约 300 ns。

**Workloads**：

| 工作负载 | RSS | 描述 |
|---------|-----|------|
| Graph500 | 68.0 GB | 图生成 + BFS |
| PageRank | 12.3 GB | Twitter 数据集迭代 PageRank |
| XSBench | 63.4 GB | 蒙特卡洛中子输运 |
| BTree | 38.3 GB | 内存索引查找 |
| Pandas | 20.2~92.6 GB | 6 种数据处理查询 |

**关键结果**：

| 对比基线 | 改进幅度 |
|---------|---------|
| vs MEMTIS（1:2 ratio） | 2.5%~12.0%（五个应用） |
| vs MEMTIS（1:16 ratio） | 平均 28%，最佳 1.8× |
| vs TPP（32/16 GB fast tier） | Graph500: 14.5%/11.5%, XSBench: 29.8%/53.9% |
| vs NOMAD | 2/3 场景改进 4%~16% |

- 页拷贝微基准：DSA-2LM 在 workload B（1000 个 4KB + 24 个 2MB 页）带宽达 106.3 GB/s，是 CPU 的 14.38×，是 naive DSA 的 2.19×
- perf 采样：migrate 占比从 39.0% 降至 4.24%（仅原来的 2.51%）
- Graph500 总拷贝时间从 14.9s 降至 1.39s（原来的 9.3%）

---

## 六、批判性分析

1. **实验平台单一且特殊**：所有评估在单一的 pre-market CXL 系统上完成，DRAM 与 CXL 延迟比约 1:2.7。不同的延迟比（如更慢的 CXL 2.0 设备）下效果可能不同，但论文未探讨。

2. **热度检测算法完全继承 MEMTIS，未做联合优化**：论文的核心贡献仅在页拷贝加速，但 Section 2 花大量篇幅论证热度检测的 CPU 开销问题（Figure 1），给读者的印象是会同时优化检测和迁移。实际上 PEBS 采样的 CPU 开销并未减少。

3. **与 NOMAD 的对比存在不公平因素**：NOMAD 使用 transactional page migration (TPM)，其设计哲学是避免页拷贝（通过 page remapping），而非加速页拷贝。论文声称 DSA 缩短迁移窗口降低了 TPM 失败率，但这实际上改变了 NOMAD 的核心机制。NOMAD+ 的改进可能更多来自绕过 TPM 而非优化它。

4. **fast tier 比例越小改进越大，但实际部署比例存疑**：论文在 1:16 ratio 下展示了最佳结果（1.8×），但实际生产环境中 CXL 内存的 fast:slow 比通常不会如此极端。在更现实的 1:2 ratio 下改进仅 2.5%~12.0%。

5. **未评估对应用的 CPU 干扰**：虽然声称 DSA 是 "CPU-free"，但 DSA 描述符提交、中断处理、kmigrated 线程的唤醒调度等仍占用 CPU。论文未测量端到端的 CPU 利用率变化，只用 perf 函数采样间接说明。

6. **缺乏多租户/混合负载评估**：论文在 motivation 中提到 co-location 场景下页拷贝问题更严重，但评估全部是单应用独占 32 核的配置。

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理的 KV Cache 管理可借鉴**：LLM 推理中 KV cache 的换入换出（如 vLLM 的 offloading）本质上也是热/冷数据在不同内存层级间的迁移。DSA 加速页拷贝的思路可直接应用于 GPU-CPU-CXL 三级存储的 KV cache offloading，减少 CPU 端的拷贝瓶颈。

2. **大模型训练的 checkpoint 和参数搬移**：分布式训练中参数 checkpoint、optimizer state 的持久化涉及大量内存拷贝。DSA 的 batch + multi-WQ 并行机制可以加速这些操作而不占用计算核心。

3. **CXL 内存池化与 AI 工作负载**：随着 CXL memory pooling（如 Pond）在数据中心部署，tiered memory 管理将成为 AI 集群的基础设施。DSA-2LM 的内核级优化为 CXL-native 的 AI 内存管理提供了参考。

4. **值得跟进的方向**：
   - 将 DSA 加速与 GPU-aware 的页迁移结合（如 CUDA Unified Memory 的页面迁移）
   - 利用 DSA 的 "Memory Fill" 能力加速模型参数的零初始化
   - 在 disaggregated memory 架构下，将 DSA 的 batching 思想扩展到跨节点的 RDMA 数据搬移

---

## 八、总结

DSA-2LM 提出了一种利用 Intel DSA 硬件加速器替代 CPU 进行 tiered memory 页迁移的系统设计，核心贡献是聚合数据通路（将 4KB/2MB 混合页统一通过 batch + multi-WQ 并行迁移）和自适应参数调优。在真实 CXL 平台上相比 MEMTIS/TPP/NOMAD 取得了显著改进，尤其在 fast tier 比例较小时效果突出。主要局限在于实验平台单一、仅优化了页拷贝环节而未触及热度检测开销、且在较现实的内存比例下改进有限。该工作展示了 DSA 在内存管理中的潜力，但距离论文所宣称的 "CPU-free" tiered memory 仍有差距。
