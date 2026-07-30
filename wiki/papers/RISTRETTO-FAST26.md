---
type: paper
name: RISTRETTO
full_title: "Here, There and Everywhere: The Past, the Present and the Future of Local Storage in Cloud"
authors: [Leping Yang, Yanbo Zhou, Gong Zeng, Li Zhang, Saisai Zhang, et al.]
venue: FAST
year: 2026
tags: [cloud-storage, local-storage, dpu, nvme, ebs, alibaba]
source_pdf: "[[fast2026-yang.pdf]]"
source_md: "[[fast2026-yang]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# RISTRETTO：这里、那里、无处不在：云本地存储的过去、现在和未来（FAST 2026）

> **原题**：Here, There and Everywhere: The Past, the Present and the Future of Local Storage in Cloud

> **一句话总结**：阿里云三代 cloud local storage 现场演进揭示：高 IOPS [[NVMe]] 下 host 软件栈的 context switch 是主瓶颈，ASIC DPU 能解放 CPU 但跟不上 SSD 代际与云特性迭代；ASIC+SoC 协同的 RISTRETTO 在单 VD 达 900K IOPS（8 VD 合计 7.2M）、近物理延迟，而本地盘固有的可用性/弹性缺陷推动 PoC [[LATTE]]——以 RISTRETTO 作前端 cache + 标准 EBS 作后端，ML dispatcher 与 [[S3-FIFO]] admission 在 trace 上 82–90% 读命中、价格约为 EBSX 的 1/5–1/10。

## 问题与动机

Cloud local storage（ephemeral storage）把物理 SSD 直挂 compute server，经虚拟化暴露为 virtual disk（VD），以**近物理性能 + 低价**吸引 CDN 缓存、大数据分析中间结果等场景。但 SSD 代际演进（2017–2023 IOPS 从 ~500K 升至 1.5M、PCIe Gen3→Gen4）使 harness 性能越来越难：内核 [[Virtio]] 栈在 [[NVMe]] 上仅达物理盘 9.54% IOPS，却消耗 ~140% CPU，三类 context switch（VM_Exit、syscall、interrupt）在高 IOPS 下成为主导开销。

阿里云先后部署三代方案（ESPRESSO → DOPPIO → RISTRETTO），每代均达数千至上万节点规模，但每代也暴露新瓶颈：用户态 polling 仍占 host 专核、ASIC DPU 算力与灵活性不足、本地盘物理共址带来的可用性/弹性/区域可及性缺陷。与此同时，高性能 EBS（EBSX：30µs、1M IOPS）虽解决 LDL_1–3，但同等性能容量价格约为本地盘的 ~20×。论文核心 claim 是：**通过三代演进归纳设计空间，并以 LATTE 混合架构在性能、可用性与 CapEx 间找新平衡点**。

## 关键观察 / 隐含假设

- **观察 1**：高 IOPS [[NVMe]] workload 下，虚拟化软件栈的 context switch 与 CPU 争用是性能主瓶颈，而非 SSD 本身——内核栈 VD 仅 9.54% 物理 IOPS；[[SPDK]] 用户态 polling（ESPRESSO）把软件开销降 82.35%，但 I/O completion 仍经 eventfd 触发 VM_Exit，深 queue depth 下与物理盘差距拉大（SWL_3）。
  - **依赖假设**：租户 workload 以高 IOPS 随机小 I/O 为主，且 guest 仍使用 interrupt-driven NVMe driver（非 polling guest driver）。
  - **可能失效场景**：大 block sequential I/O、低 QD、或 guest 已改用 polling driver（ESPRESSO-M 实验显示 VM/hypervisor 延迟可再降 60%+）时，软件栈瓶颈权重下降。
- **观察 2**：纯 ASIC DPU 卸载能 bare-metal 就绪并消除 host CPU 占用，但 ASIC 固定逻辑难以跟上 SSD 性能演进（Gen4 单 DPU 上限 ~1.3M IOPS）且不支持 LVM、[[ZNS]] 等需软件管理的云特性（HWL_1–2）；纯 SoC DPU 灵活但 CapEx/功耗约为 ASIC 的 20×/3×。
  - **依赖假设**：云厂商需要同时满足「榨干最新 Gen4/Gen5 SSD」与「快速上线 LVM/FTL/新介质特性」，且部署规模足以摊销定制硬件 NRE。
  - **可能失效场景**：SSD 演进放缓、或云特性可由 host 侧软件实现而不必板上 SoC；FPGA/更强 ASIC 迭代周期缩短时，RISTRETTO 的 co-design 优势收窄。
- **观察 3**：本地盘性能已接近物理盘（RISTRETTO 单 VD 读延迟 77µs vs 物理 75µs），但**可用性、弹性、区域可及性**是结构性缺陷——单盘故障可致小时级停服（需跨盘迁移）、容量绑定单 SSD 粒度、仅高密度用户区域部署；LLM 推理等动态 checkpoint/[[KV-Cache]] 持久化进一步放大弹性需求（LDL_1–3）。
  - **依赖假设**：相当比例租户把 local disk 当 cache/ephemeral 层，可容忍数据丢失但**不能容忍长时间不可用**；EBS 冗余对这类场景是 overkill，推高价格。
  - **可能失效场景**：应用层已做三副本（HDFS/Ceph）且可快速重调度；或租户仅需裸容量、对可用性不敏感时，纯本地盘仍最优。
- **观察 4**：混合 local+cloud 栈中，I/O 路由与 cache admission 决定能否同时利用前端带宽与后端可用性——LATTE 在 production trace 上读命中 82–90%，ML dispatcher 精度 95.6%；75% 命中时读 IOPS 已超 RISTRETTO 单机，50% 命中时读吞吐超 RISTRETTO 与 EBSX 之和。
  - **依赖假设**：工作集存在可预测的 hot set，且后端标准 EBS 带宽/延迟在 burst 时可被 ML 路由绕过；write path 以 append-only + L2P 追踪保证一致性。
  - **可能失效场景**：全随机 one-hit-wonder 读（S3-FIFO 针对此设计但仍可能低命中）、多租户共享前端盘时的 QoS 争用、或后端 EBS 拥塞时 tail latency 恶化（论文承认 LATTE p99.9 仍高）。
- **假设 1**：三代架构对比在**同一 Alibaba 测试床**（8× Gen4 SSD、120 vCPU VM）下公平反映生产趋势。
  - **证据强度**：**中**——微基准与 3 条 TB 级 production trace 有说服力，但各代系统来自不同部署年代，硬件代际混杂（DOPPIO 受 PCIe Gen3 lane 限制）。

## 核心方法

### ESPRESSO（gen-1，2017）：[[SPDK]] 用户态栈

把 local storage stack 从内核迁到用户态：vhost-user polling 收 guest [[Virtio]] 请求，经 [[SPDK]] 直写 SSD，share-nothing 每线程绑专核。2017 年上线，扩至数万节点；单机 12× Gen3 SSD 达 38.4 GB/s、5.76M IOPS。解决 HDD 时代内核栈问题，但引入 SWL_1–3：需 6 核服务 12 盘（无 bare-metal）、专核 p99 利用率 <60%、completion 仍经 eventfd→KVM→VM_Exit（额外 5–12µs）。

### DOPPIO（gen-2，2019）：ASIC DPU 卸载

商用 ASIC DPU（每卡管 2× Gen3 [[NVMe]]）通过 [[SR-IOV]] VF + PCI passthrough 把 VD 直接暴露给 VM；DMA 经 DPU 中间缓冲，硬件 MSI 中断通知 guest。解放 host CPU、支持 bare-metal，2019–2021 部署数千节点（6M IOPS/机）。但 HWL_1：Gen4 下每 DPU 仅 1.3M IOPS；读吞吐受 DPU PCIe（每 SSD 4× Gen3）限制至 ~4.1 GB/s（物理盘 59%）。HWL_2：硬连线 ASIC 难支持 LVM/[[ZNS]]。

### RISTRETTO（gen-3，2023）：ASIC + SoC 协同

PCIe 扩展卡：ASIC（NVMe 控制器仿真、DMA、1000+ VF、MSI 直通 guest via VT-D）+ ARM Cortex-A72 SoC（4 核、64 GB DRAM）经内部 PCIe 互联。数据路径：guest NVMe SQ → ASIC DMA 读命令 → ASIC-to-SoC virtual queue → SoC 上 [[SPDK]] BDEV（LVM/RAID/Caching/FTL，含 [[ZNS]] host-side FTL）→ SoC-to-ASIC VQ → ASIC 封装 NVMe → SSD；SSD DMA 由 ASIC **零拷贝**路由回 guest 内存。

多队列：每 VM NVMe queue pair 对应独立 ASIC↔SoC VQ，匹配物理 SSD 并行度。2023 年上线数千节点；8 VD 实例 48 GB/s、7.2M IOPS（单 VD 900K，较 DOPPIO +80%）。SoC 仅需 4 ARM 核 vs ESPRESSO 8 Xeon 核，per-core 效能提升 >50%。

### LATTE（PoC）：local + EBS 混合

动机：EBSX 性能可比本地盘但 ~20× 价格；纯本地盘有 LDL_1–3。LATTE 在 [[CSAL]]（[[SPDK]] 加速框架）上改造：前端 = RISTRETTO，后端 = 标准 EBS；去掉 CSAL 的 log-compaction/GC（EBS 自带）。

- **写路径**：per-I/O ML dispatcher（linear-SVM，5×6 滑窗输入，推理 ≤200 ns）选择 write-to-cache 或 write-bypass-backend；前端周期性 flush；L2P 表追踪数据位置；双路径均 append-only 保序。
- **读路径**：L2P 定位 → 命中则直返；miss 则经 [[S3-FIFO]] 三队列 admission（基于 Solidigm Append-Cache）决定是否 promote 到前端。
- **模型重训**：每 60s 监测吞吐/延迟方差，超 10% 阈值则 5s 内重训。

## 设计取舍

- **取舍 1**：ESPRESSO 选择成熟 [[SPDK]] 开源栈换快速上线，代价是 host 专核绑定与无法 bare-metal——适合 VM 密集、可牺牲若干 vCPU 的 early NVMe 时代。
- **取舍 2**：DOPPIO 选择低成本低功耗 ASIC DPU（约为 SoC DPU 的 1/20 成本、1/3 功耗），代价是算力天花板与功能僵化——适合 Gen3 时代、功能需求稳定的规模部署。
- **取舍 3**：RISTRETTO 用定制 ASIC+SoC 板卡换性能可扩展性与云特性灵活性，CapEx/复杂度高于 COTS DPU，但 TCO 优于纯 SoC 卸载；板上 64 GB DRAM 与 4 ARM 核是持续运维成本。
- **取舍 4**：LATTE 用标准 EBS（非 EBSX）作后端换成本，接受后端延迟与 tail latency 风险，靠 ML 路由与 cache 掩盖；PoC 未 field deploy，QoS 与多租户共享前端盘仍开放。
- **边界条件**：RISTRETTO 在单租户、Gen4 SSD、需 LVM/FTL/[[ZNS]] 的云本地盘场景最优雅；LATTE 在 trace 显示明显热集的混合读写（DB、社交、AI 推理）上最优雅；纯 sequential、极端随机或强 durability sync 写（O_SYNC）场景下混合层收益未充分验证。

## 实验与结果

- **微基准（FIO 4KB random / 128KB sequential）**：RISTRETTO 单 VD 读 IOPS 949K、8 VD 7,385K；DOPPIO 661K/5,281K；ESPRESSO 572K/4,608K（Table 4）。RISTRETTO 读延迟全 QD 近物理（Figure 11），ESPRESSO 深 QD 最差。
- **写延迟**：LATTE 平均写延迟最低（ML 路由避后端拥塞）；本地盘 QD=128 时 p99.9 写延迟均 >1ms（SSD GC）；EBSX/LATTE 无 host-side GC 惩罚，随机写 IOPS 远高于本地盘稳态 ~230K。
- **LATTE 命中度**：0/25/50/75/100% 人工命中下，75% 时读 IOPS 优于纯 RISTRETTO；50% 时读吞吐 8.9 GB/s 超 RISTRETTO+EBSX 组合带宽；100% 命中反而略低于 75%（未叠加后端带宽）。
- **Production trace replay**（社交 2h/AI 推理 8h/大数据 shuffle 6h，均 >1TB）：LATTE 读命中 90.23%/88.79%/82.80%，写延迟显著优于 EBS/EBSX；ML dispatcher 吸收 burst。
- **MySQL Sysbench**（240GB，10 表×1 亿行）：RISTRETTO 读-only QPS 比 DOPPIO/ESPRESSO 高 1.22×/1.77×；LATTE 写-only QPS 甚至超 RISTRETTO；读-only 仍略逊 EBSX（PMem 读 cache）。
- **CapEx（4TB 归一化，Table 6）**：RISTRETTO=1；EBSX≈19；LATTE Max（后端满配 IOPS）≈13；LATTE Auto（按负载弹性 IOPS）≈2.1–4.0。RISTRETTO 8 盘仅需 2 块 DPU（DOPPIO 需 4 块）且性能更高。

## 批判性分析

### 论证链条

论文链条为 **三代现场痛点归纳 → 逐代架构回应 → 微基准+trace+DB 验证 → 本地盘结构性缺陷 → LATTE 混合 PoC**，作为 Alibaba 经验论文逻辑闭合度好。最强环节是用 SWL/HWL/LDL 编号把 ESPRESSO/DOPPIO/RISTRETTO 的失效模式系统化，并用量产部署规模（数万/数千节点）支撑「不是实验室原型」 claim。

潜在跳步：(1) **RISTRETTO 作为论文命名焦点**，但 LATTE 大量实验与 future vision 占相当篇幅，读者易高估 LATTE 成熟度（文中明确 PoC、未部署）；(2) 三代对比横跨 2017–2023 硬件代际，DOPPIO 的 PCIe 瓶颈部分源于测试配置而非纯粹架构失败，外推「ASIC 不行」时需区分实现约束；(3) LATTE 成本数字（2.1–4.0×）依赖 Auto IOPS scaling 与特定 trace，对 always-burst workload 的 upper bound 未闭合。

### 假设压力测试

- **Workload 漂移**：ML dispatcher 按 60s 窗口重训，对秒级 traffic shift 可能滞后；Figure 10 显示吞吐翻倍后需再等 60s 才降延迟。极端 adversarial（全 miss 随机读）下 LATTE 退化为 EBS 性能 + 前端开销。
- **硬件代际**：结论绑定 PCIe Gen4、Intel VT-D interrupt passthrough；Gen5 SSD（14 GB/s）与更复杂 NVMe 特性可能重新施压 ASIC 并行度与 SoC FTL 复杂度。
- **多租户与 QoS**：LATTE future work 明确指出单块 local disk 可被多个 LATTE 实例共享，burst 叠加时性能下降——论文未给出隔离机制或 p99 SLO 保证。
- **Durability 语义**：默认 write-back；O_DIRECT/O_SYNC 可 write-through 到 EBS，但性能与路径选择 trade-off 未系统量化。crash 时未 flush 前端数据丢失，依赖应用容忍度。

### 实验可信度

- **Benchmark 代表性**：三条 Alibaba production trace + MySQL 覆盖 CDN/AI/大数据/OLTP 类场景，比纯 FIO 更有说服力；但 trace 均来自已选 local storage 集群，对「EBS-only 租户」代表性弱。
- **Baseline 公平性**：与物理盘、标准 EBS、EBSX 对照全面；ESPRESSO/DOPPIO 为历史系统，与 RISTRETTO 同机对比时部分性能差异也反映 SSD/PCIe 升级，非受控 ablation。
- **Ablation**：ESPRESSO-M（guest polling）单独量化 SWL_3；LATTE 命中度 sweep 清晰；缺少「去掉 ML dispatcher 仅启发式路由」「去掉 S3-FIFO 换 LRU」的 LATTE 组件 ablation。
- **Metric 覆盖**：吞吐/IOPS/平均与 p99.9 延迟、CapEx 覆盖较好；**能耗、故障恢复时间、迁移开销、运维复杂度** 仅定性讨论。

### 系统性缺陷

- **供应商锁定与可移植性**：RISTRETTO 为 Alibaba+Solidigm 定制 PCIe 板卡，架构思想可借鉴但硬件难直接复刻；论文在 §8 承认 ad hoc 成分，同时指出 [[SPDK]] 开源栈与 COTS ASIC 降低复制门槛。
- **静态资源绑定**：local storage 实例把 vCPU/内存与盘数绑定，易造成 stranded resources；LATTE「单盘多实例」方向可能缓解，但未生产验证。
- **可观测性**：三代栈分散在 host、DPU、SoC，论文未讨论统一 telemetry 与故障定位；LATTE 的 L2P 一致性调试复杂度高于纯本地盘。
- **Tail latency**：LATTE 平均延迟可比 EBSX，但 p99.9 读延迟仍因 backend miss 偏高；论文未讨论对 LLM 推理等 tail-sensitive  workload 的影响。

## 局限与后续工作

- **局限 1**：LATTE 仍为 PoC，未 field deploy；QoS、多租户共享、故障切换的 production 行为未知。
- **局限 2**：EBS 后端价格假设依赖三副本/EC 冗余，论文提出「弱可靠性 EBS」可进一步降本，但未实现或定价。
- **局限 3**：经验论文深度绑定 Alibaba 栈（Pangu EBS、CSAL、实例规格），其他云厂商的 DPU/Nitro 路径需自行映射。
- **Future work 1**：量化 ML dispatcher vs 更轻量启发式（队列深度阈值）的 tail latency Pareto 曲线，并在多租户共享前端盘压测下测 QoS 隔离需求。
- **Future work 2**：在 Gen5 SSD + 单盘多 LATTE 实例配置下测量「降低 per-node SSD 数量」对 accessibility 与 stranded resource 的实际改善幅度。
- **Future work 3**：作者计划释放 field trace，利于社区复现 LATTE 路由/cache 策略与跨云对比。

## 相关

- **相关概念**：[[NVMe]]、[[SPDK]]、[[Virtio]]、[[SR-IOV]]、[[ZNS]]、[[S3-FIFO]]、[[KV-Cache]]、EBS、DPU、Elastic Block Storage
- **同类系统**：[[CSAL]]、AWS Nitro / EC2 local SSD、Azure Lsv3 local disk、[[BM-Store]]、Spool、EBSX（Alibaba 高性能 EBS）
- **同会议**：[[FAST-2026]]
- **对比**：本地盘近物理性能 vs EBS 高可用/弹性；ESPRESSO（host polling）vs DOPPIO（纯 ASIC）vs RISTRETTO（ASIC+SoC）三代取舍
