# Here, There and Everywhere: The Past, the Present and the Future of Local Storage in Cloud

**作者**：Leping Yang (上海交通大学), Yanbo Zhou, Gong Zeng, Li Zhang, Saisai Zhang, Ruilin Wu, Chaoyang Sun, Shiyi Luo, Wenrui Li, Keqiang Niu, Xiaolu Zhang, Junping Wu, Jiaji Zhu, Jiesheng Wu (阿里巴巴), Mariusz Barczak, Wayne Gao (Solidigm), Ruiming Lu, Erci Xu, Guangtao Xue (上海交通大学)
**会议**：FAST 2026
**链接**：https://www.usenix.org/conference/fast26/presentation/yang
**源文件**：[[fast2026-yang.pdf]]

---

## 一、背景

云本地存储（Cloud Local Storage）是主流云厂商广泛提供的服务，将物理磁盘直接挂载在计算节点上，通过虚拟化暴露为虚拟磁盘（VD），为 VM 提供近物理设备的性能和较低的价格。典型场景包括 CDN 缓存、大数据 shuffle 中间结果存储等。

NVMe SSD 近年来性能快速演进：IOPS 从 500K 增长到 1.5M，吞吐从 3GB/s（PCIe Gen3）倍增到 6GB/s（PCIe Gen4）。然而，如何在云虚拟化环境中充分发挥这些高性能设备的能力，同时平衡裸金属支持、CPU 效率、弹性和可用性，是云本地存储面临的核心挑战。

---

## 二、要解决的问题

阿里云本地存储在演进过程中依次面临以下痛点：

1. **内核栈无法适配 NVMe SSD**：基于 Virtio 的内核虚拟化栈在 HDD 时代表现尚可，但面对 NVMe SSD 高 IOPS 时产生大量上下文切换，单 VD 仅能达到物理 SSD 的 9.54% IOPS
2. **用户态栈（ESPRESSO）的局限**：(SWL_1) 需要占用宿主机 CPU 核心，无法提供裸金属服务；(SWL_2) 专用核心的实际利用率 P99 低于 60%，但无法安全回收；(SWL_3) I/O 完成路径仍有软件中断带来的上下文切换开销
3. **ASIC DPU 卸载（DOPPIO）的局限**：(HWL_1) ASIC 迭代周期长，跟不上 SSD 性能代际演进（Gen4 SSD 下 DOPPIO 只能达到 1.3M IOPS）；(HWL_2) 硬连线逻辑无法灵活支持新云特性（如 LVM、ZNS）
4. **本地存储的固有缺陷**：可用性弱（磁盘故障导致小时级服务不可用）、弹性受限于物理 SSD 粒度、可访问性受限于物理绑定导致资源利用率低

---

## 三、洞察与设计

**关键洞察**：ASIC 擅长高吞吐的固定逻辑处理（虚拟化后端、NVMe 协议封装、中断注入），而 SoC 擅长灵活的可编程逻辑（块抽象层、LVM、FTL 等云特性）；将两者协同设计在同一 PCIe 扩展板上，可以同时获得 ASIC 的低成本高效率和 SoC 的可编程灵活性，从而在不依赖宿主机 CPU 的前提下实现近物理性能和丰富云特性。

论文呈现了阿里云本地存储的三代演进，并提出第四代混合方案：

### 第一代 ESPRESSO（2017）
基于 SPDK 的用户态栈，用 polling 替代中断，每个线程绑定专用 CPU 核管理一个 VD。12 块 PCIe Gen3 SSD 可提供 38.4GB/s 吞吐和 5.76M IOPS。

### 第二代 DOPPIO（2019）
将虚拟化和 I/O 处理卸载到商用 ASIC DPU。每个 DPU 管理 2 块 SSD，通过 SR-IOV 暴露 VF，使用硬件中断替代软件中断。实现裸金属支持并释放宿主机 CPU。

### 第三代 RISTRETTO（2023）
ASIC/SoC 协同设计的 PCIe 扩展板：
- **ASIC** 负责 NVMe 控制器仿真、DMA 路由、硬件中断注入
- **SoC**（4×ARM Cortex-A72 + 64GB DRAM）运行基于 SPDK 的块抽象层，支持 LVM、RAID、Caching、FTL 等云特性
- ASIC 与 SoC 之间通过虚拟队列（VQ）通信，实现零拷贝数据传输
- 单 VD 达到 900K IOPS，8 VD 合计 7.2M IOPS

### 第四代 LATTE（PoC）
本地磁盘 + 云盘的混合方案：
- RISTRETTO 作为高性能前端缓存吸收突发 I/O 和热数据
- 标准 EBS 作为后端提供容量、可用性和弹性
- **ML Dispatcher**：基于 linear-SVM 的轻量级 I/O 路由模型（推理延迟 ≤200ns），根据滑动窗口内的缓存/后端延迟、I/O 大小、队列深度决定写路径
- **S3-FIFO 缓存**：三队列结构的准入/驱逐控制，解决 one-hit-wonder 问题，读命中率达 82-90%

---

## 四、实现细节

### RISTRETTO 数据流
1. VM 通过 NVMe 驱动提交命令到 SQ，更新 doorbell（映射到 ASIC BAR）
2. ASIC NVMe 控制器通过 DMA 获取命令，解析 PRP/SGL，转换为 block I/O 提交到 VQ
3. SoC 上的 SPDK runtime 从 VQ polling 获取请求，经过块抽象层处理云特性（如 FTL 的 LBA→PBA B+树索引）
4. 处理后的请求通过 SoC-to-ASIC VQ 转发，ASIC 封装为标准 NVMe 包发给 SSD
5. SSD 完成后，ASIC 通过 DMA 路由将数据直接写入 guest OS 内存（零拷贝）
6. ASIC 通过 MSI 硬件中断通知 guest OS 完成

### RISTRETTO 硬件规格
- PCIe 扩展板：32 PCIe Gen4 lanes
- ASIC：DMA 引擎 + 128KB SRAM + PCIe Root Complex，支持超过 1000 个 VF
- SoC：4×ARM Cortex-A72 @2.50GHz + 64GB DRAM

### LATTE ML Dispatcher
- 模型：linear-SVM，5×6 输入特征对应 30 个权重参数，占用 <1KB
- 输入：滑动窗口（默认 5 个 I/O）内的缓存延迟、后端延迟、I/O 大小、队列深度
- 重训练：每 60 秒采集吞吐和延迟统计，方差超 10% 阈值时用短 I/O traces 重训练，耗时约 5 秒
- 精度：95.6%

### LATTE 缓存
- 基于 Solidigm Append-Cache（集成 S3-FIFO 三队列结构到 SPDK）
- 首次 miss 不立即入缓存，仅记录元数据到候选队列；第二次访问才提升
- 写路径支持 write-back（高性能）和 write-through（O_DIRECT/O_SYNC 触发，强持久性）

---

## 五、实验结果

### 实验环境
- CPU: Intel Xeon @2.90GHz (64-Core, 128 HT)，VM 分配 120 vCPU
- 存储: 8×3.84TB PCIe Gen4 SSD
- OS: Linux CentOS Kernel 4.19

### Microbenchmark（4KB 随机读，单 VD）

| 方案 | 最大 IOPS (1VD) | 最大 IOPS (8VDs) | 吞吐 (1VD) | 吞吐 (8VDs) |
|------|----------------|-----------------|-----------|------------|
| ESPRESSO | 572K | 4,608K | 6.5GB/s | 51.5GB/s |
| DOPPIO | 661K | 5,281K | 4.1GB/s | 31.2GB/s |
| RISTRETTO | 949K | 7,385K | 6.7GB/s | 53.4GB/s |

- RISTRETTO 在所有队列深度下均达到近物理性能
- DOPPIO 吞吐受限于 PCIe 通道（每 SSD 仅 4×Gen3 lanes），单盘读吞吐仅 4.1GB/s（物理盘的 59.4%）
- LATTE 在 75% 命中率下读 IOPS 和吞吐均超过 RISTRETTO 和 EBSX（因同时利用前后端带宽）

### Macrobenchmark

- **Trace Replay**（3 个生产 traces：社交网络、AI 模型推理、大数据 Shuffle）：LATTE 读命中率分别达 90.23%、88.79%、82.80%
- **MySQL SysBench**（10 表×1 亿行，240GB）：RISTRETTO 在读和混合负载全面领先（相比 DOPPIO 提升 1.22× QPS）；LATTE 在写负载下 QPS 甚至超过 RISTRETTO

### 成本对比（4TB 容量月价格，RISTRETTO=1）

| 方案 | 读 IOPS | 读吞吐 | 单位价格 |
|------|---------|--------|---------|
| RISTRETTO | 550K | 6.7GB/s | 1 |
| EBSX | 450K | 6.0GB/s | 19 |
| LATTE (Max) | 750K | 8.9GB/s | 13 |
| LATTE (Auto) | 750K | 8.9GB/s | 2.1~4.0 |

---

## 六、批判性分析

1. **LATTE 仅为 PoC，缺乏生产部署验证**：论文坦言 LATTE 尚未上线，但在结论和摘要中将其与已大规模部署的 ESPRESSO/DOPPIO/RISTRETTO 并列呈现，容易给读者造成成熟度等同的错觉。PoC 阶段的性能数据与生产环境可能有显著差异（多租户争用、长期 GC 影响、网络抖动等）

2. **LATTE 成本分析过于乐观**：LATTE Auto 的价格 2.1~4.0 是在"IOPS 自动伸缩"假设下的估算，但论文没有给出实际工作负载下 IOPS 伸缩的分布和频率，也没有讨论 EBS 弹性伸缩本身的延迟和 SLA 影响

3. **ML Dispatcher 的评估不够充分**：95.6% 精度在什么数据集上测得？论文仅展示了一个简单的吞吐变化重训练场景（Figure 10），没有评估模型在复杂真实负载下的鲁棒性（如突发模式切换、混合读写比例变化）。linear-SVM 的表达能力是否足够应对生产多样性值得质疑

4. **实验公平性问题**：ESPRESSO 使用 PCIe Gen3 SSD 部署（2017 年），RISTRETTO 使用 Gen4 SSD（2023 年），但对比测试中统一使用同一型号 SSD。虽然论文声明这是为了公平比较栈差异，但这也意味着 ESPRESSO 在其实际部署硬件上的表现可能不如测试所示

5. **RISTRETTO 的 SoC 可靠性未讨论**：SoC 本身就是一个嵌入式系统（ARM + 64GB DRAM + Linux），其固件升级、故障恢复、watchdog 机制等运维层面的复杂性完全未提及

6. **可用性改善的量化缺失**：LATTE 声称解决了 LDL_1（可用性），但没有给出 RTO/RPO 的量化数据，也没有讨论写缓存未刷数据在磁盘故障时的丢失窗口大小

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理系统的 KV Cache 存储**：论文明确提到 LLM 系统需要弹性存储来持久化 checkpoint 和拉取模型参数/KV cache。LATTE 的本地缓存 + 云盘后端架构非常适合 KV cache offload 场景——热 KV cache 保留在本地 SSD 上获得低延迟访问，冷数据驱逐到 EBS。ML Dispatcher 的 I/O 路由思路可以借鉴到 KV cache 的分层管理中

2. **Checkpoint 存储优化**：分布式训练的 checkpoint 写入是典型的突发大规模顺序写，LATTE 的 write-bypass-cache 路径可以让 checkpoint 直接写入后端 EBS（利用其弹性 IOPS），避免污染本地缓存中的热推理数据

3. **DPU 卸载对 GPU 服务器的启示**：在 GPU 密集的 AI 训练/推理节点上，CPU 资源紧张。RISTRETTO 式的 ASIC/SoC 卸载可以释放宿主机 CPU 给 GPU 数据预处理/后处理，减少 CPU 成为瓶颈的可能

4. **值得跟进的研究方向**：
   - 将 LATTE 的 ML Dispatcher 扩展为 workload-aware 的多级缓存管理器，针对 LLM 推理中 prefill/decode 阶段不同的 I/O 模式做差异化路由
   - 研究在 RISTRETTO SoC 上运行轻量级 KV cache 管理逻辑，实现存储侧的智能 cache 策略，进一步减少 GPU 服务器的 CPU 开销

---

## 八、总结

本文系统回顾了阿里云本地存储从内核栈到用户态（ESPRESSO）、ASIC 卸载（DOPPIO）、ASIC/SoC 协同设计（RISTRETTO）的三代演进历程，并提出了本地磁盘与云盘结合的混合方案 LATTE。核心贡献在于：(1) 提供了真实大规模云存储系统演进的第一手经验和设计权衡分析；(2) RISTRETTO 通过 ASIC/SoC 协同在不消耗宿主机 CPU 的前提下实现了近物理性能（单 VD 900K IOPS）和灵活云特性支持；(3) LATTE 通过 ML 路由和 S3-FIFO 缓存在 1/5~1/10 EBSX 价格下实现可比性能。主要局限在于 LATTE 仍是 PoC 阶段，QoS 保障、成本优化和智能路由的生产化仍需大量工作。
