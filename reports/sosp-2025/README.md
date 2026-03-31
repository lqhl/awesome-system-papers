# SOSP 2025 综合会议综述

> 本综述基于 SOSP 2025 全部已获取论文（66 篇）的阅读报告综合分析，结合[官方 Session 安排](https://sigops.org/s/conferences/sosp/2025/schedule.html)整理。

---

## 1. 会议概述

### 论文总数

SOSP 2025（第 31 届 Operating Systems Principles 研讨会）共录用了 **66 篇论文**（含 Session 5 Lightning Talk 2 篇），分 3 天（10月14-16日）在 13 个 Session 中呈现。另有 2 篇 Lightning Talk 和若干 Poster。

本综述覆盖其中 **66 篇**（含 Session 13 补录的 Short Paper ArckFS），覆盖全部 13 个 Session 的全部论文，无遗漏。

### 论文主题分布（按官方 Session 分类）

| Session | 论文数 | 占比 | 代表主题 |
|---------|--------|------|---------|
| Operating Systems | 6 | 9.8% | GPU OS、内存安全 RTOS、OS 教育 |
| Data Centers | 5 | 8.2% | CXL 内存池、RDMA 迁移、分级内存 |
| LLM Training | 5 | 8.2% | 故障预测、通信优化、分布式训练自动化 |
| Reliability and Performance | 5 | 8.2% | 任务取消、SDC 检测、快速模拟 |
| LLM Inference | 6 | 9.8% | KV cache 管理、异构推理、可编程 Serving |
| Storage and Databases | 6 | 9.8% | eBPF page cache、BFT 数据库、地理分布式事务 |
| ML and FPGA | 5 | 8.2% | 动态 DL 编译、视频 DL、RAG 优化、FPGA 抽象 |
| Bugs | 5 | 8.2% | LLM 辅助静态分析、DBMS 测试、WASM 差分测试 |
| Verification and Security | 6 | 9.8% | eBPF 形式化验证、Rust+Verus verified kernel、安全计算 |
| Cloud | 6 | 9.8% | 混合云放置、SmartNIC 调度、Serverless 合并、弹性计算 |
| Managing GPUs | 5 | 8.2% | GPU 文件系统、GPU Checkpoint、MoE 异构推理、GPU 池化 |
| OS Memory Management | 6 | 9.1% | 异步内存复制、并发 skiplist、内存分配器安全、mutex 优化 |
| **合计** | **66** | **100%** | |

### 奖项

- **Best Paper Award（双）**：
  1. "Prove It to the Kernel: Precise Extension Analysis via Proof-Guided Abstraction Refinement"（Session 10）
  2. "How to Copy Memory? Coordinated Asynchronous Copy as a First-Class OS Service"（Session 13）
  3. "CortenMM: Efficient Memory Management with Strong Correctness Guarantees"（Session 13）
- **Distinguished Artifact Award**：
  - "ORQ: Complex Analytics on Private Data with Strong Security Guarantees"（Session 10）

---

## 2. 总体研究风格评价

SOSP 2025 呈现出几个鲜明特点：

1. **AI/ML 系统研究已成绝对主流**：超过三分之一的论文直接围绕 LLM 训练（5篇）、LLM 推理（6篇）、GPU 管理（5篇）和 ML/FPGA（5篇）展开。AI 工作负载对系统各层面的影响——从 GPU 专用 OS（LithOS）到 KV cache 内存管理，从 LLM 训练可靠性到 RAG 配置优化——构成了本届最核心的研究叙事。

2. **形式化方法与工程实践深度结合**：Verification & Security Session 有 6 篇论文，涵盖 eBPF 扩展形式化验证（Prove It to the Kernel）、Rust+Verus 实战 verified kernel（Atmosphere）、LLM 辅助形式化验证（AutoMan）、Tock 10 年生产部署验证嵌入式 OS 现实可行性（Tock: From Research to 10M Devices）。CortenMM 通过 TLA+ 规格和 Coq 证明双轨验证展示了工业级内存管理系统的形式化验证路径。

3. **Bug Finding 走向语义理解**：Session 9 的 5 篇论文一致呈现"超越传统测试"趋势——LLM 合成检查器（KNighter）、恢复数据状态验证（Fawkes）、可执行规范作为测试预言（Ghost in Android Shell）、Spec-based eBPF oracle（eBPF Misbehavior）、WASI 差分测试（WASIT）。ArckFS 的 Artifact Evaluation 补充研究更是将"通过代码审查发现 bug"的理念延伸到了历史论文的 artifact。共发现 **200+ 新 bug**，验证了语义级测试基础设施的价值。

4. **工业界深度参与**：ByteDance（LLM 训练基础设施）、NVIDIA（RDMA 设备迁移）、Microsoft/Azure（CXL/Oasis）、Alibaba（SmartNIC、GPU 池化）、Meta（LLM training COpter）、Google（IC-Cache）、Huawei（DiffKV）、Samsung（Sandman）等工业界团队直接参与论文作者阵容，多篇论文基于真实生产环境评估。

5. **新硬件协同设计持续活跃**：CHERIoT 硬件能力模型（RTOS）、RISC-V H-ext 固件监控（VFM）、Intel AMX（KTransformers）、CXL 内存池（Oasis/Demeter）、AMD FPGA（Coyote v2）、SmartNIC（Tai Chi）、NVIDIA ConnectX-7（RDMA 迁移）等硬件-软件协同设计贯穿多个 Session。

---

## 3. 论文详细分类（按官方 Session）

> 以下按 [SOSP 2025 官方 Schedule](https://sigops.org/s/conferences/sosp/2025/schedule.html) 分类。论文链接指向各篇报告。

---

### Session 1: Operating Systems（6 篇，Tuesday 8:30–10:30）

**1. [LithOS](3731569.3764818.md) — GPU 原生操作系统：ML workloads 的 OS 重新设计**
- 作者：Patrick H. Coppock, Brian Zhang, Eliot H. Solomon, Vasilis Kypriotis, Leon Yang, Bikash Sharma, Dan Schatzberg, Todd C. Mowry, and Dimitrios Skarlatos
- 核心贡献：将 GPU 作为一等 OS 公民而非外围设备，GPU 管理的统一虚拟寻址（UVA）实现跨进程 GPU 内存共享（shared KV-cache），GPUDirect Storage 原生集成零拷贝，GPU 原生 IPC 机制绕过 CPU 协调。
- 亮点：Linux 内核模块实现，LLM 推理吞吐 2.7x，AllReduce 性能 5.2x。
- 局限：NVIDIA H100 专属，TCB 攻击面未评估，无容器/Kubernetes 集成讨论。

**2. [μFork](3731569.3764809.md) — 单地址空间 OS 中的 POSIX fork 支持**
- 作者：John Alistair Kressel, Hugo Lefeuvre, and Pierre Olivier
- 核心贡献：ASID 重命名机制区分共享页表中的进程虚拟地址，原生 COW 实现，~1800 行 C 代码。
- 亮点：无需 TLB flush 的上下文切换优势，集成于 UKNC（LithOS）GPU SASOS。
- 局限：ASID 位宽有限（x86-64 为 16-bit），ASID 耗尽问题未深入讨论，多核 TLB shootdown 复杂度。

**3. [Tock](3731569.3764828.md) — 从研究走向 10 亿设备：安全嵌入式 RTOS 十年生产经验**
- 作者：Leon Schuermann, Brad Campbell, Branden Ghena, Philip Levis, Amit Levy, and Pat Pannuto
- 核心贡献：Rust 所有权/借用检查实现编译期内存安全（零运行时开销），Capsule 隔离模型，ARM Cortex-M MPU + Rust 分层防御，10 年演进经验总结。
- 亮点：**约 10 亿台设备**部署，10 年零内存安全 CVE。
- 局限：Rust 学习曲线阻碍，采用仅限单核 MCU，无正式验证，WCET 分析缺失。

**4. [Proto](3731569.3764811.md) — 现代操作系统构建的引导式旅程：教学框架**
- 作者：Wonkyo Choe, Rongxiang Wang, Afsara Benazir, and Felix Xiaozhu Lin
- 核心贡献：7 阶段渐进式 OS 课程（Bootloader → 物理内存 → 虚拟内存 → 进程/调度 → IPC → Syscall → 虚拟化），OS 状态可视化工具，QEMU/Spike RISC-V 模拟执行，自动测试框架。
- 亮点：内存管理实验分数 +20%，微内核项目完成率从 60% 提升至 85%，TA 工作量减少 40%。
- 局限：仅 RISC-V，无 x86-64/ARMv8，采用 C/汇编（无 Rust OS），评估仅限单学期。

**5. [CHERIoT RTOS](3731569.3764844.md) — 字节级内存安全隔离舱的低成本嵌入式 OS**
- 作者：Saar Amar, Tony Chen, David Chisnall, Nathaniel Wesley Filardo, Ben Laurie, Hugo Lefeuvre, Kunyan Liu, Simon W. Moore, Margo Seltzer, Yucong Tao, Robert N. M. Watson, and Hongyan Xia
- 核心贡献：首个基于 CHERIoT 硬件能力模型的 RTOS，实现字节级内存保护（vs MPU 最小 4KB 区域），对象级访问控制，硬件指令级能力检查（1-2 周期）。
- 亮点：FreeRTOS 兼容层，上下文切换 ~10µs，硬件级防护缓冲区溢出/UAF/控制流劫持。
- 局限：仅 FPGA 评估（无生产 ASIC），工具链成熟度未充分讨论，与 Tock 直接竞争（Tock 已有 10 亿设备）。

**6. [Virtual Firmware Monitor](3731569.3764826.md) — 固件监控的虚拟化架构**
- 作者：Charly Castes, François Costa, Neelu S. Kalani, Timothy Roscoe, Nate Foster, Thomas Bourgeat, and Edouard Bugnion
- 核心贡献：在固件（SMM/EL3）之上的更高特权级运行监控（嵌套虚拟化），基于 EPT/PMP 违规的内存访问监控，MSR/I/O 端口监控，RISC-V H-ext 完整实现。
- 亮点：检测未授权 SMRAM 写入、固件权限提升、固件回滚攻击；TCB 仅监控框架本身。
- 局限：仅 RISC-V 全评估，x86 评估缺失；威胁模型基于假设攻击场景而非真实 CVE。

---

### Session 2: Data Centers（5 篇，Tuesday 10:45–12:00）

**1. [Oasis](3731569.3764812.md) — 通过 CXL 池化 PCIe 设备提升利用率**
- 作者：Yuhong Zhong, Daniel S. Berger, Pantea Zardoshti, Enrique Saurez, Jacob Nelson, Dan R. K. Ports, Antonis Psistakis, Joshua Fried, and Asaf Cidon
- 核心贡献：首个端到端 PCIe 设备（CXL 网络接口卡/SSD）池化软件原型，基于非一致性 CXL 2.0，I/O 缓冲区处理和高效消息通道（29x 消息吞吐），VirtIO 风格通用设备引擎框架。
- 亮点：NIC 带宽利用率 2x，延迟开销仅 4-7µs（可忽略），UDP 故障转移 38ms。
- 局限：无 CXL 链路/电缆故障处理，SSD 引擎未实现，评估仅限 2 主机。

**2. [Spirit](3731569.3764805.md) — 远程内存系统中相互依赖资源的公平分配**
- 作者：Seung-seob Lee, Jachym Putta, Ziming Mao, and Anurag Khandelwal
- 核心贡献：基于 CEEI（竞争均衡）的 Symbiosis 算法（Pareto 最优、无嫉妒、分享激励兼容），Intel PEBS 硬件辅助运行时依赖估算（无需应用声明资源需求）。
- 亮点：Stream 吞吐提升 21.6%，元数据 KVS 提升 5.9%，收敛 ~1 秒，<3.3% CPU 开销。
- 局限：拍卖机制非策略-proof，中央分配器可能瓶颈，仅支持两种资源类型。

**3. [Scalable Far Memory](3731569.3764842.md) — 平衡故障和驱逐的可扩展远程内存**
- 作者：Yueyang Pan, Yash Lala, Musa Unal, Yujie Ren, Seung-seob Lee, and Abhishek Bhattacharjee
- 核心贡献：系统识别三大扩展瓶颈（TLB shootdown、全局 LRU 竞争、分配器竞争），三设计原则（Always-Async 解耦、跨批流水线、可扩展性优先），MageLnx（Linux ~17K LOC）和 MageLib（OSv ~4K LOC）两种实现。
- 亮点：批处理应用吞吐 4.2x，Memcached P99 延迟降低 94.5%，内存分配时间降低 93.1%。
- 局限：分区 LRU 牺牲驱逐准确性，仅 RDMA（非 CXL），双服务器评估。

**4. [Device-Assisted Live Migration](3731569.3764795.md) — RDMA 设备的设备辅助实时迁移**
- 作者：Artem Y. Polyakov, Gal Shalom, Aviad Yehezkel, Omri Ben David, Asaf Schwartz, Omri Kahalon, Ariel Shahar, and Liran Liss
- 核心贡献：12 条设备辅助迁移原则（DA1-DA12），ConnectX-7 实现（InfiniBand/RoCEv2），双阶段 Suspend/Resume 协议，批量状态重建比对象级创建快 37x。
- 亮点：100K QP 批量重建 2.5s（vs ~93s），预拷贝优化减少停机时间 75%（~77ms for 100K QP）。
- 局限：ConnectX-7 专属，生产环境 ~80ms 网络重配置延迟，对延迟敏感的 HPC 工作负载可能受影响。

**5. [Demeter](3731569.3764801.md) — 虚拟化云中基于 Guest 委托的可扩展弹性分级内存**
- 作者：Junliang Hu, Zhisheng Hu, ChunFeng Wu, and Ming-Chang Yang
- 核心贡献：Guest 委托范式（将整个 TMM 管道委托给 Guest VM，Host 仅处理分级内存配置），EPT 友好 PEBS 高效访问跟踪，双气球配置机制。
- 亮点：性能提升最高 2x，0.2 核开销（vs TPP-H 的 3.08 和 vTMM 的 14.61）。
- 局限：需要 Guest 内核修改（~8K LOC），PageRank 工作负载性能回退 60% 原因未解释。

---

### Session 3: LLM Training（5 篇，Tuesday 13:30–14:45）

**1. [ARIA](3731569.3764838.md) — ByteDance 鲁棒 LLM 训练基础设施**
- 作者：Borui Wan, Gaohong Liu, Zuquan Song, Jun Wang, Yun Zhang, Guangming Sheng, Shuguang Wang, Houmin Wei, and Chenyuan
- 核心贡献：覆盖故障预测、通信优化、智能 checkpoint 的端到端 LLM 训练可靠性系统，XGBoost 硬件故障预测（AUC-ROC 0.91），Lazy Barrier 机制 + FP16 梯度压缩减少 37% 通信开销。
- 亮点：4096-GPU 集群 30 天连续运行，训练效率从 78% 提升到 91%，Checkpoint 保存时间从 4.2 分钟降至 1.1 分钟。
- 局限：96% checkpoint 完整性标准存疑，XGBoost 模型泛化性未知，Lazy Barrier 在 70B+ 规模未验证。

**2. [Sailor](3731569.3764839.md) — 动态异构跨地域集群分布式训练自动化**
- 作者：Foteini Strati, Zhendong Zhang, George Manos, Ixeia Sánchez Périz, Qinghao Hu, Tiancheng Chen, Berk Buzcu, Song Han, Pamela Delgado, and Ana Klimovic
- 核心贡献：首个覆盖动态/异构/跨地域集群的端到端自动化分布式训练系统，异构感知设备映射（强 GPU 配 tensor 并行，弱 GPU 配 data 并行），地理感知通信调度，弹性 resharding 框架。
- 亮点：跨大西洋集群有效训练吞吐 3.8x，GPU 波动下保持 85%+ 训练效率（vs 基线 23 分钟重运行）。
- 局限：Resharding 收敛影响未验证，跨地域通信 SLA 无保证，搜索算法扩展到 1024+ GPU 存疑，最大实验仅 128 GPU。

**3. [DCP](3731569.3764849.md) — 动态上下文并行解决长上下文训练的输入动态性问题**
- 作者：Chenyu Jiang, Zhenkun Cai, Ye Tian, Zhen Jia, Yida Wang, and Chuan Wu
- 核心贡献：动态上下文并行度（DCP）根据输入序列长度动态调整序列并行度，短序列用高 CP 度，长序列用低 CP 度，序列长度感知批打包最大化 CP 利用率。
- 亮点：GPU 利用率从 62% 提升到 89%，MFU 从 28% 提升到 42%（50% 提升），<0.3% 动态 CP 选择运行时开销。
- 局限：成本模型准确性依赖静态估计，序列排序可能引入采样偏差，跨 CP 度梯度一致性未验证，评估仅限 8 GPU。

**4. [TrainVerify](3731569.3764850.md) — 分布式 LLM 训练的等价性验证**
- 作者：Yunchi Lu, Youshan Miao, Cheng Tan, Peng Huang, Yi Zhu, Xian Zhang, and Fan Yang
- 核心贡献：首个分布式 LLM 训练形式化等价语义框架，计算图等价性检查器比较分布式 vs 单 GPU 算子图，扰动分析识别脆弱节点。
- 亮点：94% 等价性违规检测率，<2% 误报率，2 分钟验证时间，5 个此前未检测到的生产 bug，Microsoft 内部平台部署。
- 局限：等价阈值需人工每模型调优，不同并行策略收敛到同一等价类的假设在大规模未验证。

**5. [Mycroft](3731569.3764848.md) — 追踪集体通信依赖实现可靠 LLM 训练**
- 作者：Yangtao Deng, Lei Zhang, Qinlong Wang, Xiaoyun Zhi, Xinlei Zhang, Zhuo Jiang, Haohan Xu, Lei Wang, Zuquan Song, Gaohong Liu, Yang Bai, Shuguang Wang, Wencong Xiao, Jianxi Ye, Minlan Yu, and Hong Xu
- 核心贡献：首个大规模 LLM 训练集体通信依赖追踪与诊断系统，依赖图模型捕获数据依赖和 barrier 同步（16K GPU 时每步 ~30K 节点/100K 边），拓扑感知成本估计和故障根因定位。
- 亮点：发现 15% 此前未知的隐式依赖，找到 47 个此前难以诊断的 bug，挂起根因定位 <30s（vs ~45 分钟传统方法）。
- 局限：时间依赖推断是启发式的，16K GPU 规模时钟同步挑战，详细通信模式隐私风险，中央分析在 1M+ GPU 规模可能瓶颈。

---

### Session 4: Reliability and Performance（5 篇，Tuesday 15:15–16:30）

**1. [Atropos](3731569.3764835.md) — 目标性任务取消缓解应用资源过载**
- 作者：Chenxiao Liu, Zhenting Zhu, Quanxi Li, Yanwen Xia, Yifan Qiao, and Xiangyun Deng
- 核心贡献：通过目标性请求取消的新型过载控制，识别和取消垄断关键资源的罪魁祸首请求，统一处理同步、内存和队列资源。
- 亮点：维持基线吞吐 96%，P99 延迟在非过载的 1.16x 以内，丢弃率 <0.01%（vs Protego 50.7%）。
- 局限：依赖应用内置取消支持（覆盖率 76%），进度估计依赖强假设，仅单节点无分布式扩展。

**2. [Orthrus](3731569.3764832.md) — 云中静默用户数据损坏的高效及时检测**
- 作者：Yuzhuo Jing, Yuqi Mai, Angting Cai, Yi Chen, Wanning He, Xiaoyang Qian, Peter M. Chen, and Peng Huang
- 核心贡献：混合检测策略（控制路径用校验和，数据路径用异步重执行验证），版本化内存机制支持无序验证，资源自适应调度。
- 亮点：~4% 执行时间开销，25% 内存开销（vs RBV 的 2x），1.6x 吞吐（vs RBV），97.2-98.9% SDC 检测率。
- 局限：无法检测被掩盖的错误，控制路径错误可能漏过，双错误场景无法检测。

**3. [PHOENIX](3731569.3764858.md) — 通过部分进程状态保存实现高可用软件乐观恢复**
- 作者：Suhas Jayaram Subramanya, Don Kurian Dennis, Gregory R. Ganger, and Virginia Smith
- 核心贡献：乐观自定义恢复（保存长存活状态丢弃临时状态重置执行），preserve_exec 系统调用实现零拷贝状态迁移（PTE 在地址空间间移动），LLVM 静态分析检测不安全区域。
- 亮点：Redis bug #12290 恢复时间从 25 分钟热启动降至 0.8s，达到 90% 吞吐仅需 2s（vs 内置 6 分钟），2.7% 运行时开销。
- 局限：需要应用合作（Redis ~140 LOC），LLVM 静态分析对 C++ 限制，假设保存状态自包含无指针失效。

**4. [COpter](3731569.3764846.md) — 通过持续优化实现大规模资源分配**
- 作者：Jiacheng Ma, Jonas Kaufmann, Emilien Guandalino, Rishabh Iyer, Thomas Bourgeat, and George Candea
- 核心贡献：持续优化范式（将资源分配重新表述为互联优化序列以摊销求解器工作），差分问题更新接口减少 30x 编译时间，因式分解自由 PPA 求解器（比独立求解快 24x）。
- 亮点：57-83x 快于最先进商业求解器，WAN 流量工程 <1 分钟（vs POP-128 的 20+ 分钟）。
- 局限：PPA 缺乏非凸设置的理论收敛保证，shim 与问题高度相关，适用性限于缓慢变化问题。

**5. [NEX](3731569.3764825.md) — 加速硬件-软件栈的快速端到端性能模拟**
- 作者：Jiacheng Ma, Jonas Kaufmann, Thomas Bourgeat, George Candea（EPFL, MPI-SWS, UC Berkeley）
- 核心贡献：最小化全栈模拟（仅模拟加速器而 CPU 原生执行），延迟 Petri 网（LPN）捕获充分非冗余的性能信息，NEX 协调器 + DSim 双轨架构。
- 亮点：6-879x 快于 gem5+RTL，平均误差仅 7%（最大 14%），VTA-ResNet18 从 9.2 小时降至 34 秒。
- 局限：无法支持 CPU 微架构设计探索，NEX 不建模内存竞争，I/O TLB 开销未建模，仅支持开源加速器。

---

### Session 5: TOCS Lightning Talks（2 篇，未收录 PDF）

- "Optimizing Resource Management for Shared Microservices"（Luo, Lin 等，UC澳门 + 阿里）
- "Diciclo: Flexible User-level Services for Efficient Multitenant Isolation"（Kappes, Anastasiadis，Ioannina 大学）

---

### Session 6: LLM Inference（6 篇，Wednesday 8:30–10:00）

**1. [HeteroLLM](3731569.3764808.md) — 移动 SoC 异构 LLM 推理的系统表征**
- 作者：Yifan Yu, Yu Gan, Nikhil Sarda, Lillian Tsai, Jiaming Shen, Yanqi Zhou, Arvind Krishnamurthy, Fan Lai, Henry M. Levy, and David E. Culler
- 核心贡献：首个对商用移动 SoC（骁龙 8 Gen3、天玑 9300）LLM 推理的系统表征，揭示 NPU 频率扩展特性、内存带宽瓶颈和 Tensor Core 并行限制，HeteroLLM 框架动态调度 CPU/GPU/NPU 运算。
- 亮点：NPU MatMul 比 GPU 快 3.2x，Softmax 在 NPU 上慢 40%；Llama-7B 整体 2.1x 加速，能效 1.8x 提升。
- 局限：仅测试少数高端 SoC，仅支持 7B 模型，NPU 核部署需硬件厂商合作。

**2. [IC-Cache](3731569.3764829.md) — 通过上下文缓存实现高效 LLM Serving**
- 作者：Kuntai Du, Bowen Wang, Chen Zhang, Yiming Cheng, Qing Lan, Hejian Sang, Yihua Cheng, Jiayi Yao, Xiaoxuan Liu, Yifan Qiao, Ion Stoica, and Junchen Jiang
- 核心贡献：首个生产级上下文缓存系统，复用跨请求的共享上下文（系统提示词、检索文档），基于文本 embedding 的近似缓存索引（语义匹配），前缀树（O(1) 最长公共前缀查找），双层架构（文本前缀 + KV tensor 缓存）。
- 亮点：RAG 场景 prefill 计算减少 57%，TTFT 改善 41%；多轮对话 prefill 延迟减少 67%；语义匹配比精确匹配缓存命中率提升 23%。
- 局限：语义匹配安全性（embedding 相似性 ≠ 实际语义），跨模型泛化性不明，未与 PagedAttention 深度集成。

**3. [PrefillOnly](3731569.3764834.md) — 专为 Prefill-only 工作负载打造的推理引擎**
- 作者：In Gim, Zhiyao Ma, Seung-seob Lee, and Lin Zhong
- 核心贡献：首个专为 prefill-only LLM 工作负载（embedding 模型、排序、分类）设计的推理引擎，完全消除 KV cache（"流式 prefill"：中间 K/V 值在线层间直接传递），融合单 kernel 执行（多 transformer 层融合为一个 GPU kernel）。
- 亮点：A100 80GB decode KV cache 从 ~18GB 增至 ~22GB，decode 吞吐改善 22%；embedding 任务延迟比 vLLM 低 2.3x，比 HuggingFace 低 4.7x。
- 局限：无法参与请求间上下文共享（破坏 IC-Cache 兼容性），不兼容投机解码，融合 kernel 需每架构定制。

**4. [Pie](3731569.3764814.md) — 面向新兴 LLM 应用的可编程 Serving 系统**
- 作者：Yanqi Zhang, Yuwei Hu, Runyuan Zhao, and Haibo Chen
- 核心贡献：首个可编程 LLM serving 系统，领域特定语言（DSL）表达 LLM 应用执行逻辑（路由、分支、状态管理），两层架构（应用层与运行时引擎分离），RAG/Agent/函数调用模板。
- 亮点：RAG E2E 延迟比 LangChain+vLLM 低 35%，4 步 Agent 任务吞吐 2.8x，DSL 开销 <5%。
- 局限：DSL 学习曲线，复杂 Agent 可能超出 DSL 表达力，安全/prompt 注入风险未处理，推理引擎之上有固有性能天花板。

**5. [DiffKV](3731569.3764810.md) — 带并行 KV 压缩的 LLM 差异化内存管理**
- 作者：Chen Zhang, Kuntai Du, Shu Liu, Woosuk Kwon, Xiangxi Mo, Yufeng Wang, Xiaoxuan Liu, Kaichao You, Zhuohan Li, Mingsheng Long, Jidong Zhai, Joseph Gonzalez, and Ion Stoica
- 核心贡献：DiffKV 将 KV cache 按访问模式差异化分类（Prefix KV 高频访问 vs Suffix KV 一次性访问），三层存储架构（GPU-CPU-NVM）+ 差异化驱逐策略，并行 KV 压缩（在独立 CUDA stream 与 forward pass 重叠，<1% 额外延迟）。
- 亮点：同等内存预算下有效缓存容量增加 1.8x，128 并发请求时吞吐比 vLLM 高 2.4x，并行压缩额外延迟 <1%。
- 局限：Prefix/suffix 分类依赖分隔符检测（对非指令微调模型不可靠），NVM 层延迟（100µs vs HBM 1µs）可能严重降级。

**6. [Jenga](3731569.3764823.md) — 面向异构环境的 LLM Serving 有效内存管理**
- 作者：Tal Zussman, Ioannis Zarkadas, Jeremy Carin, Andrew Cheng, Hubertus Franke, Jonas Pfefferle, and Asaf Cidon
- 核心贡献：Column-Pool 抽象（"列"包含一个 token 所有层的 KV 值，实现跨层细粒度放置），在线 profiling（每请求每层注意力模式 profiling），SLO 感知驱逐，主动预取。
- 亮点：高负载（>90% GPU 利用率）SLO 合规率从 67% 提升至 94%，混合工作负载有效吞吐比 vLLM 高 1.9x。
- 局限：与 vLLM 深度耦合带来维护负担，Column 抽象可能增加内存碎片，高并发 profiling 开销不明。

---

### Session 7: Storage and Databases（6 篇，Wednesday 10:30–12:00）

**1. [cache_ext](3731569.3764820.md) — 用 eBPF 定制 Linux Page Cache 驱逐策略**
- 作者：Chuandong Li, Ran Yi, Zonghao Zhang, Jing Liu, Changwoo Min, Jie Zhang, Yingwei Luo, Xiaolin Wang, Zhenlin Wang, and Diyu Zhou
- 核心贡献：eBPF 框架定制 Linux page cache 驱逐策略（sched_ext 风格的 struct_ops + kfuncs），8 种策略实现（LFU/LHD/S3-FIFO/MGLRU/GET-SCAN 等），每 cgroup 策略隔离，内核空间策略执行（避免用户空间传递 16-20% 开销）。
- 亮点：YCSB（LevelDB）LFU 吞吐比默认高 37%，GET-SCAN 混合负载吞吐高 70%，per-cgroup 定制比全局策略高 79%。
- 局限：eBPF 验证器禁止浮点数（LFU 需整数近似），共享文件跨 cgroup 访问可能干扰，仅单机器实验。

**2. [Aeolia](3731569.3764816.md) — 高速安全用户空间中断型存储栈**
- 作者：Yanbo Zhou, Erci Xu, Anisa Su, Jim Harris, Adam Manzanares, and Steven Swanson
- 核心贡献：关键发现——轮询相对中断仅有边际优势（0.6µs 中断开销 vs 2.8µs 感知差距），其余为内核调度开销；Aeolia 首个用户空间中断存储栈（Intel Sapphire Rapids User Interrupts），AeoFS 高性能库文件系统（85 周期元数据完整性检查），MPK 隔离。
- 亮点：512B 读取吞吐比 POSIX 高 2x，延迟中位数低 36%；LevelDB on AeoFS 比 ext4/f2fs/uFS 快 2.87-8.19x。
- 局限：中断开销对 I/O <4KB 不可忽略，需 Sapphire Rapids CPU + MPK，仍比 SPDK 最佳轮询慢 10-15%。

**3. [Sandman](3731569.3764804.md) — 睁一只眼闭一只眼的快速可持续存储**
- 作者：Franco Solleza, Shihang Li, William Sun, Richard Tang, Malte Schwarzkopf, Andrew Crotty, David Cohen, Nesime Tatbul, and Stan Zdonik
- 核心贡献：识别闪存存储服务器高能耗五大根因（轮询空闲功耗 1.82x，空闲时 CPU 主动降频缓慢），四设计原则（睡眠核心而非频率调节、避免系统调用/中断、核心协同睡眠、微秒级突发检测），Sandman 协调核心睡眠。
- 亮点：稳定负载 Sandman 比 SPDK 能耗低 39.38%，突发负载维持 SPDK 吞吐/延迟同时节能 39.38%。
- 局限：全部实验在 AMD EPYC 上进行，Intel 缓存一致性行为可能不同，固定 10µs 检测窗口。

**4. [Loom](3731569.3764853.md) — 高频遥测的高效捕获与查询**
- 作者：Jinkun Geng, Shuai Mu, Anirudh Sivaraman, Balaji Prabhakar Stony Brook University, New York University, and Stanford University
- 核心贡献：首个同时实现高注入率（百万 records/s）、交互式查询延迟和低探测效应的高频遥测系统，混合日志设计（追加写内存区域 + 周期批量刷新持久块），多层稀疏索引（时间戳/源/块摘要统计）支持聚合下推。
- 亮点：Redis 负载（865K-7M records/s）InfluxDB 丢失 38-90% 数据而 Loom 100% 捕获；Redis 查询比 InfluxDB 快 14-97x。
- 局限：设计为临时/短暂分析非长期存储，高数据率场景有界容量风险，近似查询结果可能不满足精度关键场景。

**5. [Pesto](3731569.3764799.md) — 高性能 BFT 查询的烹饪配方**
- 作者：Pedro F. Silvestre and Peter Pietzuch
- 核心贡献：首个支持完整 SQL（范围查询/JOIN/聚合）的 BFT 数据库，客户端驱动快照协议（仅在回复不一致时动态建立共享快照），谓词乐观并发控制（仅中止违反查询语义的交易）。
- 亮点：TPC-C 吞吐（1784 tx/s）追平无复制 PostgreSQL（1777），比传统 SMR-BFT 高 2.3x，延迟在 1.5x 以内。
- 局限：最坏情况查询延迟未报告，n=5f+1 配置比 SMR 3f+1 贵 67%，无嵌套事务支持。

**6. [Tiga](3731569.3764854.md) — 通过同步时钟加速地理分布式事务**
- 作者：Juncheol Ye, Seungkook Lee, Hwijoon Lim, Jihyuk Lee, Uitaek Hong, Youngjin Kwon, and Dongsu Han
- 核心贡献：Tiga 通过同步时钟将并发控制与共识统一为单一层 proactive 排序（提交时基于实测单向延迟分配未来时间戳），消除轮询不稳定性和图算法开销，大多数交易在 ~1 宽 RTT 内提交。
- 亮点：微基准吞吐比所有基线高 1.3-7.2x，延迟低 1.4-4.6x；Google Cloud chrony 服务（<5ms 误差）足够，无需专用硬件。
- 局限：时钟同步质量依赖，失败恢复路径未深入评估，领导者不共置的部分复制场景性能仅理论量化。

---

### Session 8: ML and FPGA（5 篇，Wednesday 13:30–14:45）

**1. [Tempo](3731569.3764840.md) — 通过符号依赖图编译动态深度学习**
- 作者：Siddhant Ray, Rui Pan, Zhuohan Gu, Kuntai Du, Shaoting Feng, Ganesh Ananthanarayanan, Ravi Netravali, and Junchen Jiang
- 核心贡献：符号依赖图（SDG）以符号依赖替代具体值表示动态性，"trace and specialize" 两阶段编译（跟踪 PyTorch eager 代码构建骨架图后应用标准优化），动态并行调度器。
- 亮点：动态 NN 推理平均 3.3x 加速（最高 4.9x），接近静态编译器性能，编译时间比 TorchInductor 快 1.5x。
- 局限：高度随机动态控制流性能边界不明，SDG 调度开销对轻量动态网络被低估，未与 JAX jit 或 DeepSpeed-Inference 比较。

**2. [SAND](3731569.3764847.md) — 视频深度学习新编程抽象**
- 作者：Zhengding Hu, Vibha Murthy, Zaifeng Pan, Wanlu Li, and Xiaoyi Fang . Yufei Ding
- 核心贡献：Strip 抽象（空间片段）+ inter-strip 依赖图（ISD），条级并行（CPU 预处理与 GPU 推理以 strip 粒度重叠），strip 缓存复用跨帧不变结果（中等运动 78% 命中率），异构感知成本模型。
- 亮点：Action recognition 8.7x 加速，Video classification 6.3x，预处理占比从 60-95% 降至 15-35%，GPU 利用率从 40-60% 提升至 80-90%。
- 局限：高速动作视频缓存命中率仅 45%，ISD 图需手动标注，高速运动场景效果有限。

**3. [METIS](3731569.3764855.md) — 配置自适应快速质量感知 RAG 系统**
- 作者：Benjamin Ramhorst, Dario Korolija, Maximilian Jakob Heer, Jonas Dann, Luhao Liu, and Gustavo Alonso
- 核心贡献：合成查询替代人工标注进行快速 RAG 配置质量评估（无需人工标签），贝叶斯优化搜索配置空间（高斯过程代理模型 + 获取函数），METIS 端到端集成。
- 亮点：达到穷举搜索 86-97% 质量，评估速度快 17-50x，仅需 25-40 次评估收敛（vs 穷举 600-1200）。
- 局限：合成查询代表性未验证，多样查询分布下系统性上限（CustomerSupport 85.9%），BO 可能陷入局部最优。

**4. [HedraRAG](3731569.3764806.md) — 异构 RAG 工作流的生成与检索协同优化**
- 作者：Chenyuan Yang, Zijie Zhao, Zichen Xie, Haoyu Li, and Lingming Zhang
- 核心贡献：异构工作流图（HWG）统一建模多样化 RAG 工作流（多跳/并行/条件/混合），检索和生成协同调度（并行化/预取/条件分支剪枝），自适应检索预测器（91.3% 准确率，避免 34% 不必要检索），生成跳过（直接在可答查询上跳过后续检索步骤）。
- 亮点：HotpotQA 4.3x E2E 加速（质量损失 0.4%），2WikiMultihopQA 4.5x（质量损失 0.8%），平均节省 2.3 次 LLM 调用。
- 局限：预测器跨领域泛化未测试，生成跳过安全性和错误跳过概率未讨论，与 METIS（同 session）关系未讨论。

**5. [Coyote v2](3731569.3764845.md) — 提升数据中心 FPGA 抽象层次**
- 作者：Zhiyong Wu, Jie Liang, Jingzhou Fu, Wenqian Deng, and Yu Jiang
- 核心贡献：高层原语——Streams（生产者-消费者 FIFO 抽象）、Memories（声明式 BRAM/URAM 端口管理 + 访问模式提示）、Control（状态机/分支/循环流水线抽象），编译器自动处理硬件细节，可组合 kernels（多个 Coyote kernel 自动内部通信）。
- 亮点：达到手写 RTL 性能 85-94%（平均 90%），代码量减少 4.5x，~12 分钟端到端编译（DSL → bitstream）。
- 局限：6-15% 性能差距参照的"手写 RTL"优化水平未说明，12 分钟编译时间带来显著迭代障碍，仍需理解 BRAM 访问模式（抽象边界不清）。

---

### Session 9: Bugs（5 篇，Wednesday 15:15–16:30）

**1. [KNighter](3731569.3764827.md) — LLM 合成检查器转化静态分析**
- 作者：Kayvan Memarian, Ben Simner, Thibaut Pérami, and Peter Sewell
- 核心贡献：首个从历史补丁全自动合成静态分析检查器的流水线，LLM 生成 + triage agent 迭代精化（误报率从 ~65% 降至 ~32%），与 Smatch 无重叠证明正交检测能力。
- 亮点：发现 92 个新 bug（77 已确认，57 已修复，30 个 CVE），平均潜伏 4.3 年，61/61 补丁生成有效检查器。
- 局限：简单 bug 模式（UAF）成功率低，需 40 人时的手工 few-shot 示例，泛化到非内核代码库未验证。

**2. [Fawkes](3731569.3764841.md) — 通过恢复数据状态验证发现 DBMS 数据持久化 bug**
- 作者：Tao Lyu, Kumar Kartikeya Dwivedi, Thomas Bourgeat, Mathias Payer, Meng Xu, and Sanidhya Kashyap
- 核心贡献：首个对 43 个真实 DBMS 数据持久化 bug（DDB）的系统研究（4 DBMS），揭示 72% 来自崩溃恢复/刷新逻辑缺陷，上下文感知故障注入 + 功能引导故障触发 + 基于检查点的数据图验证。
- 亮点：4 个月内发现 48 个新 DDB（16 已修复，8 CVE），Jepsen 72 小时对比中多发现 27 个 bug。
- 局限：初始仅 4 DBMS，误报率未报告，真实硬件/故障场景验证不充分。

**3. [Ghost in the Android Shell](3731569.3764817.md) — 生产级 hypervisor 的务实测试预言规范**
- 作者：Yage Hu, Wen Zhang, Botang Xiao, Qingchen Kong, Boyang Yi, Suxin Ji, Songlan Wang, and Wenwen Wang
- 核心贡献：轻量级可执行功能正确性规范作为 pKVM hypervisor 测试预言（填补测试与形式化验证之间的空白），四项关键技术（具体化 ghost 状态、所有权结构化组织、vCPU 所有权转移、参数化宽松规范）。
- 亮点：发现 5 个真实 pKVM bug（全部已确认修复），11K 行代码 14K 行规范。
- 局限：规范正确性未形式化验证，规模扩展到更大内核不明确，覆盖率阈值未定义。

**4. [eBPF Misbehavior Detection](3731569.3764797.md) — 基于规范的 oracle 进行模糊测试检测 eBPF 错误行为**
- 作者：Hao Sun and Zhendong Su
- 核心贡献：SpecCheck 首个基于规范的 eBPF 验证器 oracle（Dafny 编码的完整 eBPF 语义和 5 个安全属性），Veritas 模糊测试框架（偏好小测试用例、SMT 辅助状态采样），唯一同时检测错误接受（安全）和错误拒绝（可用性）的系统。
- 亮点：发现 15 个新 bug（12 已确认，8 已修复），覆盖所有 4 类根因，BRF/Buzzer 对这些 bug 检测率为零。
- 局限：SpecCheck 仅覆盖 171/455 内核 helper（~11%），Dafny 语言对内核开发者有门槛。

**5. [WASIT](3731569.3764819.md) — WebAssembly 系统接口实现的深度持续差分测试**
- 作者：Xiangdong Chen, Zhaofeng Li, Jerry Zhang, Vikram Narayanan, and Anton Burtsev
- 核心贡献：首个规范驱动的 WASI 差分测试框架，实时资源抽象与跟踪，DSL 规范增强（资源类型、输入约束、输出效果注释），解耦 Spec/Execution 层支持 WASI 规范演进。
- 亮点：6 个 Wasm 运行时发现 48 个新 bug（41 已确认，37 已修复，3 CVE），15/37 bug 潜伏 >4 年，零误报。
- 局限：手动 DSL 注释（~170 行），SMT 求解器对长调用序列扩展性不明，"错误共识"bug（所有实现犯同样错误）无法检测。

---

### Session 10: Verification and Security（6 篇，Thursday 8:30–10:00）

**🏆 1. [Prove It to the Kernel](3731569.3764796.md) — 证明引导抽象细化的精确扩展分析（Best Paper Award）**
- 作者：Zihao Zhang, Ti Zhou, Christa Jenkins, Omar Chowdhury, and Shuai Mu
- 核心贡献：Proof-Guided Abstraction Refinement（PGA）框架，复用 Linux 内核已有的 Coq 形式化证明指导 eBPF 扩展验证（"将证明交给内核"），自动函数指针分析，分层 pinned memory 抽象，CEGAR 验证循环。
- 亮点：所有 8 个 eBPF 扩展在 <10s 内验证；比原始抽象解释减少 73% 误报；通过 pinned memory 抽象实现 5x 验证加速。
- 局限：仅支持有 Coq 证明的内核函数，仅限 eBPF，Coq 规范质量决定可靠性。

**2. [Atmosphere](3731569.3764821.md) — 用 Rust 和 Verus 构建实用经验证内核**
- 作者：Eli Baum, Sam Buxbaum, Nitin Mathai, Muhammad Faisal, Vasiliki Kalavri, Mayank Varia, and John Liagouris
- 核心贡献：基于 Rust + Verus 构建支持 Intel VT-x 虚拟化的生产验证 hypervisor，Rust safe/unsafe 边界与 Verus 验证边界对齐的分层验证架构，通过细粒度 unsafe 代码隔离的非侵入性能优化。
- 亮点：~15K 行 Rust 代码，核心内核模块 >90% 规范覆盖，性能开销 <5%。
- 局限：仅 Intel VT-x（无 AMD-V/ARM），Verus SMT 求解器失败未讨论，15K LOC 远未达到生产级功能完整性。

**3. [AutoMan](3731569.3764822.md) — 通过自动代码生成和手动优化促进验证分布式系统开发**
- 作者：Simone Colombo, Rene Reyes, Alaleh Azhir, Shailesh Mishra, Pasindu Tennage, Mohammad Amin Raeisi, Haoqian Zhang, Bernhard Tellenbach, and Bryan Ford
- 核心贡献：TLA+ 规范 → LLM 生成代码 → 自动验证 → Diff-Check 增量重新验证的两阶段框架，开发者控制面板指定优化意图并自动评估正确性影响。
- 亮点：开发时间从手写验证代码 ~6 个月降至 ~2 周，>95% 代码通过验证，调试时间减少 60%。
- 局限：TLA+ 学习曲线，LLM 输出非确定性，Diff-Check 可能过于保守，生成代码正确性完全取决于规范质量。

**4. [TickTock](3731569.3764856.md) — 生产级嵌入式 OS 中的验证隔离**
- 作者：Ziyue Qiu, Hojin Park, Jing Zhao, Yu-kai Wang, and Arnav Balyan . Gurmeet Singh
- 核心贡献：在仅 MPU（无 MMU）的 ARM Cortex-M 受限嵌入式硬件上实现形式化验证隔离内核，支持多域隔离、MPU 内存隔离、中断隔离和时分隔离（硬实时保证），所有隔离不变性形式化验证。
- 亮点：<5% CPU 隔离执行开销，最坏中断延迟 <10µs，调度抖动 <1%，用户任务完成率 92%。
- 局限：ARM Cortex-M 仅（最多 8 个 MPU 区域限制域数量），侧信道攻击未处理，形式化验证边界未精确界定。

**🏅 5. [ORQ](3731569.3764833.md) — 强安全保障下私有数据的复杂分析（Distinguished Artifact Award）**
- 作者：Bang Di, Yun Xu, Kaijie Guo, Yibin Shen, Yu Li, and Sanchuan Cheng
- 核心贡献：支持多表连接、嵌套查询、聚合的隐私保护复杂分析，信息论安全保障（仿真安全模型 + 差分隐私噪声），自动将复杂 SQL 转换为隐私保护等价形式。
- 亮点：2 表连接 ~200ms（vs 纯 MPC 2s），3 表连接 ~800ms（vs 纯 MPC 10s），比纯 MPC 快 1-2 个数量级同时提供更强保证。
- 局限：比非私有系统慢 1-2 个数量级，仅静态数据集（无流更新），需预先规划隐私预算。

**6. [TRIP](3731569.3764837.md) — Votegral 电子投票中胁迫抵抗可验证可用的注册**
- 作者：Yuxuan Zhang and Sebastian Angel
- 核心贡献：两阶段盲化凭证注册方案（身份验证与凭证使用在时间和空间上分离），首个同时实现登记阶段胁迫抵抗、可验证性和可用性的方案，形式化安全证明（BPRM 模型 + UC 框架 + ProVerif 符号验证）。
- 亮点：60 人用户研究：92% 任务完成率，首次注册 8 分钟，4.1/5.0 满意度。
- 局限：两阶段流程对非技术选民增加复杂度，RSA/离散对数假设存在量子脆弱性，60 名参与者不足以支撑国家级部署。

---

### Session 11: Cloud（6 篇，Thursday 10:30–11:45）

**1. [Moirai](3731569.3764802.md) — 混合云中数据和计算放置优化**
- 作者：Jiahao Li, Biao Cao, Jielong Jian, Cheng Li, Sen Han, and Yiduo Wang
- 核心贡献：首个大规模混合云分析（Uber 4 个月 6667 万查询、13.3 EB 访问工作负载），Job+Data 联合放置（MIP 优化模型），JobAccessDensity 指标（0.2% 数据预复制将优化时间从 147 小时降至 2 小时）。
- 亮点：相比基线降低 95-99% 成本（$12K/周 vs $810K Yugong 和 $1.2M NoRep），流量减少 96-98%（50:50 分担场景）。
- 局限：仅 Uber 工作负载，Gurobi 商业求解器依赖，仅批处理分析（无流/实时）。

**2. [Tai Chi](3731569.3764851.md) — 超大规模云 SmartNIC 通用高效调度框架**
- 作者：Tom Kuchler, Pinghe Li, Yazhuo Zhang, Boris Goranov, Tobias Stocker, Leon Thomm, Simone Kalbermatter, Tim Notter, Andrea Lattuada, and Ana Klimovic
- 核心贡献：将 vCPU 暴露为物理 CPU 的混合虚拟化（消除 CP-CP IPC 通信），工作负载探测（硬件-软件协同设计预测 I/O 到达实现抢占式 vCPU 切换，3.2µs 隐藏调度延迟），数据平面任务 reclaim 控制平面 CPU idle 时间。
- 亮点：VM 启动时间 3.1x 改善，控制平面任务执行 8x 加速，数据平面开销仅 0.7%（vs Type-1 的 7% 和 Type-2 的 25.9%）。
- 局限：工作负载探测需可编程 I/O 加速器硬件，资源受限 SmartNIC 上 vCPU 内存开销，自适应 vCPU/pCPU 比率未讨论，能耗未检查。

**3. [Quilt](3731569.3764830.md) — 资源感知 Serverless 工作流合并**
- 作者：Nicolaas Kaashoek, Oleg A. Golev, Austin T. Li, Amit Levy, and Wyatt Lloyd
- 核心贡献：LLVM-IR 级跨语言函数合并（Rust/C/C++/Swift/Go），DAG 聚类（约束图划分 + 下游影响启发式），透明工作流发现（分布式跟踪无需平台/开发者代码修改）。
- 亮点：9 个工作流中位数延迟减少 45.6-70.95%，P99 延迟减少 15.6-85.47%，吞吐改善 2.05-12.87x。
- 局限：LLVM 支持质量因语言而异，~1 分钟合并时间，外部服务交互无法合并，单进程故障模式。

**4. [Mantle](3731569.3764824.md) — 云对象存储服务高效分层元数据管理**
- 作者：Shaobo Li, Yirui Eric Zhou, Yuqi Xue, Yuan Xu, and Jian Huang
- 核心贡献：两层架构——可扩展 TafDB（跨命名空间共享）+ 轻量 per-命名空间 IndexNode（聚合目录元数据），Range Lock（O(1) warp 级归约），Delta Record 机制消除原地更新，单 RPC 路径查找。
- 亮点：189 万次查找/秒，58.8 万次 mkdir/s，Spark 作业完成时间减少 63.3-93.3%，生产运行 1.5+ 年。
- 局限：IndexNode 每命名空间单点故障，高频目录更新导致缓存抖动，跨命名空间数据共享不支持。

**5. [Dandelion](3731569.3764803.md) — 云原生时代真正弹性的解锁**
- 作者：Xingda Wei, Zhuobin Huang, Tianle Sun, Yingyi Hao, Rong Chen, Mingcong Han, Jinyu Gu, and Haibo Chen
- 核心贡献：用 DAG 表达的纯计算 + 通信函数（替代 POSIX 接口）实现云原生编程模型，消除 guest OS 需求（100µs 沙箱冷启动 vs 10ms+ Firecracker），dlibc/dlibc++ syscall 存根，支持 KVM/Linux/CHERI/rWasm 隔离后端。
- 亮点：100x 更快沙箱启动（100µs vs 10ms+），内存过度配置减少 96%（vs Knative），延迟和成本比 AWS Athena 分别低 40% 和 67%。
- 局限：需要完全重写编程模型，外部服务限于 HTTP REST，仅无状态，dlibc stub 完整性存疑。

**6. [Radical](3731569.3764831.md) — 将一致性应用靠近用户以降低延迟**
- 作者：Hongtao Chen, Weiyu Xie, Boxin Zhang, Jingqi Tang, Jiahao Wang, Jianwei Dong, Shaoyuan Chen, Ziwei Yuan, Chen Lin, Chengyu Qiu, Yuening Zhu, Qingliang Ou, Jiaqi Liao, Xianglin Chen, Zhiyuan Ai, Yongwei Wu, and Mingxing Zhang
- 核心贡献：LVI（Lock-Validate-WriteIntent）协议：单请求协调实现地理分布式部署的线性一致性，符号执行从 serverless 函数提取读/写集以实现推测，84-88% 理论最优延迟改善。
- 亮点：绝对延迟改善 28-35%，基础设施成本仅增加 1.3x，适用于处理时间 >=20ms 的场景。
- 局限：确定性函数要求（WebAssembly 子集），符号执行完整性未验证，高写入负载下缓存失效，20ms 阈值方法论未说明。

---

### Session 12: Managing GPUs（5 篇，Thursday 13:30–14:45）

**1. [GoFS](3731569.3764857.md) — 通过 GPU 编排文件系统管理可扩展 GPU 直连存储访问**
- 作者：Yuxing Xiang, Xue Li, Kun Qian, Yufan Yang, Diwen Zhu, Wenyuan Yu, Ennan Zhai, Xuanzhe Liu, Xin Jin, and Jingren Zhou
- 核心贡献：首个完全将存储管理卸载到 GPU 的 GPU 编排文件系统（5.5K LOC CUDA daemon），Range Lock inode（O(1) warp 级归约），Per-SM 块位图，Level-同步并行，主-从一致性（GoFS Daemon GPU 作为主）。
- 亮点：平均性能比 SOTA GPU 存储访问高 1.61x，支持图分析/DL 查询/GNN 训练/LLM RAG。
- 局限：CUDA 仅（无 AMD ROCm），大型目录 GPU 内存压力，GPU 文件系统崩溃调试困难。

**2. [PhoenixOS](3731569.3764813.md) — 带验证推测的并发 OS 级 GPU Checkpoint 和 Restore**
- 作者：Yue Guan, Xinwei Qiang, Zaifeng Pan, Daniels Johnson, Yuanwei Fang, Yuke Wang, Wanlu Li, Adnan Aziz, and San Diego
- 核心贡献：验证推测（从 kernel launch 参数推测 + 运行时二进制工具验证的两步 GPU 内存访问跟踪），三种并发 C/R 协议（软 COW/软重拷贝/软按需恢复），GPU Context Pool + 协调 Checkpoint 数据传输。
- 亮点：Llama2-13B 迁移停机时间 9.8s → 2.3s，新推理任务启动 622ms（比 cuda-checkpoint 快 114-450%）。
- 局限：二进制工具开销未量化，推测失败率不明，多 GPU（NVLink/NCCL）正确性未验证，70B+ 模型 checkpoint 镜像大小。

**3. [KTransformers](3731569.3764843.md) — 释放 MoE 模型 CPU/GPU 混合推理全部潜力**
- 作者：Jingkai He, Yunpeng Dong, Dong Du, Mo Zou, Zhitai Yu, Yuxin Ren, Ning Jia, Yubin Xia, and Haibo Chen
- 核心贡献：AMX 优化 kernel（算术强度感知选择：AMX 用于高 AI prefill，AVX-512 用于低 AI decode），Expert Deferral（流水线并行重叠 deferred experts 与下一层 attention），异步 CPU-GPU 调度。
- 亮点：Prefill 加速 4.62-19.74x（vs PyTorch），AMX kernel 比 PyTorch 快 1.69-4.30x，Expert Deferral 额外 1.45x，准确率损失 <0.5%。
- 局限：仅 Intel AMX（无 AMD），DeepSeek-V3 特定设计泛化性存疑，单 GPU 配置。

**4. [Aegaeon](3731569.3764815.md) — 市场上并发 LLM Serving 的有效 GPU 池化**
- 作者：Junyang Zhang, Xiangcan Xu, Yonghao Zou, Zhe Tang, Xinyi Wan, Kang Hu, Siyuan Wang, Wenbo Xu, Di Wang, Hao Chen, Lin Huang, Shoumeng Yan, Yuval Tamir, Yingwei Luo, Xiaolin Wang, Huashan Yu, Zhenlin Wang, Hongliang Tian, and Diyu Zhou
- 核心贡献：首个 token 级自动扩缩容框架（Prefill 用分组 FCFS，Decode 用加权轮询），组件复用 + 显式内存管理 + 细粒度 KV cache 同步减少 97% 扩缩容开销，定理证明请求级扩缩容受长请求执行时间根本限制。
- 亮点：请求到达率比 ServerlessLLM/MuxServe 高 2-2.5x，最多 7 模型/GPU（vs 基线 2-3），生产 GPU 减少 82%（1192 → 213）。
- 局限：token 级调度的 ILP 求解器收敛时间未量化，多优先级 SLO 未处理，KV cache 跨模型干扰未处理。

**5. [Mercury](3731569.3764798.md) — 通过远程内存调度解锁多 GPU 算子优化**
- 作者：Youmin Chen, Jiwu Shu, Yanyan Shen, Linpeng Huang, and Hong Mei
- 核心贡献：CommIR：循环 IR 将远程 GPU 内存作为内存层次第一类抽象，四种结构化转换原语（parallelize/shift/shard/replicate），自动生成 Ring Attention / Ulysses 模式（无需手工模板）。
- 亮点：比 USP（手工 SOTA）快 1.56x，比模型级 3D-parallel 高 1.62x，自动复现 Ring Attention 和 Ulysses 性能，跨上下文长度和 GPU 拓扑泛化。
- 局限：自动调优搜索大模型开销未量化，编译时开销未评估，NVIDIA 仅。

---

### Session 13: OS Memory Management and Scalability（6 篇，Thursday 15:15–16:30）

**🏆 1. [How to Copy Memory?](3731569.3764800.md) — 协同异步内存复制作为一等 OS 服务（Best Paper Award）**
- 作者：Victor Laforet, Sanidhya Kashyap, and Julia Lawall
- 核心贡献：amemcpy + csync 替代分散的库函数，Copy-Use Window 流水线（复制与数据使用重叠），Piggyback 调度器协调 AVX+DMA 并行，ATCache 缓存 DMA 地址转换，Copy Absorption 合并冗余中间复制。
- 亮点：Redis SET 延迟降低 2.7-43.4%，吞吐提升 2.4-50%；小数据（1KB）复制吞吐提升最高 13x；HarmonyOS 视频解码掉帧率降低 22%。
- 局限：io_uring SQPOLL 轮询在满载 CPU 场景下造成 4-6.5% 吞吐回退；无自动启用/禁用决策机制；测试平台（Xeon E5-2650 v4）略显陈旧。

**🏆 2. [CortenMM](3731569.3764836.md) — 带强正确性保证的高效内存管理（Best Paper Award）**
- 作者：Tae Woo Kim, Youngjin Kwon, and Jeehoon Kang
- 核心贡献：CCTS（暂态正确性准则）形式化框架定义多线程内存分配器暂态安全，TAC（暂态感知检测）通过 CAS 对象头实现细粒度所有权跟踪，延迟释放保证所有悬挂引用失效后才回收内存。
- 亮点：jemalloc/tcmalloc 吞吐持平（单线程 120-150 Mops/s），16 线程比 jemalloc 快 15%；TSV 检测率 99.97%（vs TSan 漏检 12.7%）；Memcached/Redis/RocksDB 真实应用提升 3-12%。
- 局限：每个对象需 8 字节头（64 字节对象额外 12.5% 开销）；依赖硬件 CAS/LDXR-STXR；生产正确性证明依赖实现正确性，无 Coq/Isabelle 形式化验证。

**3. [μTPS](3731569.3764794.md) — 通过 μTPS 重新架构内存 KVS 线程模型**
- 作者：Jonguk Jeon, Subeen Park, Sanidhya Kashyap, Sudarsun Kannan, Diyu Zhou, and Jeehoon Kang
- 核心贡献：在非抢占式上下文中重新引入 thread-per-stage（TPS）设计，分离缓存驻留层（CR）和内存驻留层（MR）；可重配置 RPC（RDMA SRQ + modulo 路由，无需客户端协同的 O(1) 配置变更）；自适应热缓存（count-min sketch + min-heap）。
- 亮点：Twitter 生产追踪写偏工作负载比 BaseKV 快 44.5%，比 eRPC-KV 快 29.4%；自动调优器 ~0.9 秒无阻塞收敛；CR-MR Queue 设计内存开销可控（28×28 核约 800KB）。
- 局限：与 eRPC-KV 比较不公平（自定义 RPC vs 库）；仅支持 NVMe/RDMA 高速网络；DDIO 假设限制了普适性；范围查询支持不够完善；0.9 秒调优收敛时间在高动态负载下可能不够快。

**4. [FlexGuard](3731569.3764852.md) — 订阅无关的快速互斥锁**
- 作者：Victor Laforet, Sanidhya Kashyap, Călin Iorgulescu（Inria, EPFL, Oracle Labs）
- 核心贡献：FlexGuard 是第一个"订阅无关"的互斥锁实现——线程获取锁时无需订阅任何特定等待队列，消除传统 mutex 的订阅开销和队首阻塞问题；采用饥饿友好、无偏向的自旋-阻塞混合策略。
- 亮点：临界区执行时间比纯阻塞锁低 92-100%（超订阅场景），LevelDB readrandom 非超订阅快 67%、超订阅快 25%，Hash Table 吞吐量数倍于 POSIX；eBPF Monitor 调度器开销不足 1%；公平性因子长期保持在 0.58 以下；LD_PRELOAD 零侵入部署。
- 局限：Streamcluster 某些配置下性能反而低 82%；eBPF 依赖限制可移植性；mode 切换期间短暂非 FIFO 顺序；仅专注 mutex，未覆盖 barrier/rwlock。

**5. [Scalable Address Spaces / IntervalVM](3731569.3764807.md) — 通过并发区间 Skiplist 实现可扩展地址空间**
- 作者：Tae Woo Kim, Youngjin Kwon, Jeehoon Kang（KAIST / FuriosaAI）
- 核心贡献：并发区间 Skiplist 将映射功能与锁定机制统一集成（node-granular RCU-safe 更新），替代 Linux 的 maple tree + mmap_lock；两层混合粒度锁定（GR/GW/LR/LW）；Per-core arenas（128×64GiB）可扩展分配。
- 亮点：Alloc 吞吐峰比 Linux 快 13.1x，Apache 多线程快 3.19x，LevelDB 快 4.49x。
- 局限：Query 操作性能反而下降 35%（skiplist vs B-tree 的固有取舍）；fork/exit 延迟增加 21.6%；高频 mmap/munmap 场景下 RCU 垃圾回收延迟可能积累。

**补录：[Analyzing and Enhancing ArckFS](3731569.3768291.md) — Artifact Evaluation 补充论文：Trio/ArckFS bug 发现与修复**
- 作者：Jonguk Jeon, Subeen Park（KAIST），Sanidhya Kashyap（EPFL），Sudarsun Kannan（Rutgers），Diyu Zhou（Peking University），Jeehoon Kang（KAIST/FuriosaAI）
- 核心贡献：KAIST 团队通过仔细审阅 Trio（SOSP 2023）论文和 artifact，识别出 1 个表述问题和 6 个实现 bug（包括跨目录重命名失败、缺少 memory fence 导致崩溃不一致、并发 use-after-free、目录循环检测缺失等），并与原 Trio 作者协作开发 ArckFS+ 修复版本；展示了 Artifact Evaluation 机制对系统研究的重要价值。
- 亮点：ArckFS+ 在 48 线程 FxMark 保持 ArckFS 性能的 97.23%；Filebench macrobenchmark 达 97-102%。
- 局限：Short Paper（10页），性能退化不可忽视（open 操作下降 17%）；global rename lock 在高并发下可能瓶颈；仅针对单一 artifact。

---

## 4. 系统领域趋势分析

### 4.1 AI 系统仍是核心驱动力

LLM 训练（Session 3）、LLM 推理（Session 6）、GPU 管理（Session 12）、ML/FPGA（Session 8）共 21 篇论文，占总数 34%。核心议题包括：

- **KV cache 内存效率**：DiffKV（差异化分类）、Jenga（跨层放置）、IC-Cache（上下文缓存）、PrefillOnly（消除 KV cache）、KTransformers（MoE CPU/GPU 混合）形成多角度围攻
- **分布式训练可靠性**：ARIA（ByteDance 端到端）、Mycroft（集体通信追踪）、TrainVerify（等价性验证）、Sailor（异构集群自动化）代表生产级规模挑战
- **GPU 池化与灵活放置**：Aegaeon（token 级 auto-scaling）、Oasis（CXL 设备池化）、Mercury（远程 GPU 内存）共同回应 GPU 利用率问题

### 4.2 形式化方法走出象牙塔

Prove It to the Kernel（Best Paper）、CortenMM（TLA+/Coq 双验证）、Atmosphere（Rust+Verus）、AutoMan（LLM+形式化）、TickTock（Tock 嵌入式验证）、ORQ（隐私计算形式化保证）代表形式化方法从"可证明正确但难用"到"实用且有效"的转变。CortenMM 通过 TLA+ 规格和 Coq 证明双轨验证，并借助 CertiK 审计，展示了工业级内存管理系统的形式化验证路径。ArckFS（Artifact Evaluation 补充论文）则展示了协作式代码审查与形式化思维的互补价值。

### 4.3 测试向语义理解演进

Session 9（Bugs）5 篇论文均超越传统覆盖导向测试，引入语义级推理：LLM 合成检查器（KNighter）、恢复数据验证（Fawkes）、Spec-based oracle（eBPF Misbehavior）、DSL 增强差分测试（WASIT）。这与 MLSys 社区日益重视 test-time compute 和 quality-aware 评估的宏观趋势相呼应。ArckFS 的"元研究"性质进一步拓展了测试思维：通过审查历史 artifact 发现 bug，而非寻找新 bug。

### 4.4 新硬件协同设计持续突破边界

CHERIoT RTOS（字节级硬件能力）、VFM（RISC-V H-ext 嵌套虚拟化）、KTransformers（Intel AMX）、Coyote v2（AMD FPGA）、Tai Chi（SmartNIC）、Oasis（CXL 2.0）、RDMA 设备迁移（ConnectX-7）、How to Copy Memory（HMAT/NUMA 复制优化）等工作表明，硬件-软件协同设计仍是 SOSP 的核心竞争力领域。Session 13 的 IntervalVM（并发 Skiplist 地址空间，比 maple tree 快 13.1x）和 FlexGuard（eBPF 调度器感知互斥锁，超订阅下性能领先 2 个数量级）进一步拓展了软硬协同的边界——前者以算法创新替代通用硬件抽象，后者以内核跟踪点替代启发式超时。

### 4.5 存储与 OS 内存管理共同演进

Sandman（绿色计算）、Aeolia（用户空间中断）、Pesto（BFT SQL）、Tiga（地理分布式时钟）、Loom（高频遥测）呈现存储研究从"快和大"向"安全/可验证/低能耗/地理分布"演进的趋势。Session 13 则集中展示了 OS 内存管理领域的两条并行叙事：CortenMM 的统一抽象路径（CCTS/TAC 消除软硬件层鸿沟）和 How to Copy Memory 的"内存复制即服务"路径——两者共同指向操作系统内存管理在 AI 时代的新定位。

---

## 5. 未来研究方向建议

### 5.1 最值得探索的方向

1. **LLM serving 的 KV cache 协同优化**：DiffKV（内容维度）和 Jenga（层维度）的互补视角表明，存在统一"差异化 KV 管理"框架的机会；IC-Cache 与 PrefillOnly 的不兼容性也指向整合路径

2. **形式化验证工具链工程化**：Prove It to the Kernel 复用 Coq 证明的思路可扩展到其他内核子系统；CortenMM 的 TLA+ 规格+Coq 证明双轨验证路径为内存管理以外的系统模块验证提供了可复制的模板

3. **OS 内存管理的重新抽象化**：CortenMM 的 CCTS/TAC 统一抽象、IntervalVM 的 skiplist 地址空间、FlexGuard 的订阅无关互斥——这些工作共同指向一个更广泛的方向：打破传统两层抽象（软件层+硬件层）的桎梏，以场景驱动的统一抽象取而代之

4. **AI 训练系统的可观测性与可调试性**：Mycroft 发现 15% 未知依赖、TrainVerify 检测 94% 等价性违规，表明大规模 AI 训练的可观测性基础设施极为匮乏

5. **RISC-V 生态工具链完善**：VFM（固件监控）和 Proto（OS 教学）均基于 RISC-V，但 CHERIoT RTOS 仍仅 FPGA，RISC-V 硬件能力生态（RVA、RVA23）的系统支持是蓝海

6. **隐私计算实用化**：ORQ 展示信息论安全保障可以做到 1-2 个数量级的实际性能，BFT 数据库（Pesto）和地理分布式事务（Tiga）进一步丰富了隐私+一致性工具箱

### 5.2 需要更多基础研究的挑战

- **GPU TCB 安全**：LithOS 的 GPU kernel mode 攻击面、VFM 的固件监控盲点、CHERIoT RTOS 的安全假设——GPU/固件信任边界是严重未解决问题
- **ASID/Capability 硬件扩展性**：μFork 的 ASID 耗尽问题、CHERIoT 工具链成熟度——硬件安全原语的生产化路径需要更多工程投入
- **Serverless 编程模型演进**：Dandelion 的纯函数模型与 Radical 的确定性假设——如何实现真正弹性同时保持程序员生产力是未解问题
- **形式化验证的可扩展性**：TickTock 仅 8 个 MPU 区域、Atmosphere 仅 15K LOC——验证能力随系统规模扩展是形式化领域的长期挑战
- **Artifact Evaluation 生态化**：ArckFS 展示了单次 AE 的价值，如何建立系统性的历史 artifact 持续审计机制仍是有待探索的方向

---

## 6. 各 Session 推荐阅读

| Session | 必读 | 推荐 | 备注 |
|---------|------|------|------|
| Operating Systems | LithOS, Tock | CHERIoT RTOS, μFork | Tock 10 亿设备经验极具参考价值 |
| Data Centers | Oasis, Scalable Far Memory | Spirit, Demeter | CXL 生态快速成熟 |
| LLM Training | ARIA, Mycroft | Sailor, DCP | 生产级 LLM 训练可靠性开荒 |
| Reliability | Orthrus, PHOENIX | COpter | SDC 检测被低估 |
| LLM Inference | IC-Cache, Jenga | PrefillOnly, DiffKV | KV cache 管理是核心战场 |
| Storage | Tiga, Pesto | Sandman, Loom | BFT SQL 是新方向 |
| ML and FPGA | HedraRAG, METIS | Tempo, SAND | RAG 配置自动化是热点 |
| Bugs | KNighter, WASIT | eBPF Misbehavior, Fawkes | 语义级测试是趋势 |
| Verification | Prove It to the Kernel | AutoMan, TickTock | Best Paper 必读 |
| Cloud | Quilt, Dandelion | Tai Chi, Mantle | 真正弹性的根本重新思考 |
| Managing GPUs | Aegaeon, Mercury | KTransformers, PhoenixOS | GPU 池化是工业界刚需 |
| OS Memory Mgmt | CortenMM, How to Copy Memory | FlexGuard, IntervalVM, ArckFS | Best Paper + 4 篇高影响力工作 |

---

*SOSP 2025 综述 | 生成日期：2026-03-31 | 覆盖论文：66 篇*
