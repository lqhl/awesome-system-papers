# OSDI 2025 综合会议综述

> 本综述基于 OSDI 2025 全部 53 篇论文的阅读报告综合分析。

---

## 1. 会议概述

### 论文总数

OSDI 2025 共录用了 **53 篇论文**，与近年来 OSDI 的论文规模（通常在 45-55 篇之间）基本持平。

### 论文主题分布（按官方 Session 分类）

| Session | 论文数 | 占比 |
|---------|--------|------|
| Distributed Systems and Data Centers I & II | 11 | 20.8% |
| AI + Systems I, II & III | 13 | 24.5% |
| Kernel and Operating Systems I & II | 10 | 18.9% |
| File and Storage Systems | 5 | 9.4% |
| Database Systems | 5 | 9.4% |
| Privacy and Security | 4 | 7.5% |
| Scheduling and Resource Management | 5 | 9.4% |
| **合计** | **53** | **100%** |

### 总体研究风格评价

OSDI 2025 呈现出几个鲜明的特点：

1. **工业界参与度极高**：53 篇论文中，约有一半以上有工业界作者（Meta、Microsoft、Google、华为、阿里、字节跳动、Cerebras 等），多篇论文基于真实生产环境数据（Meta 的 TAO、Azure 的 VM 分配、阿里/华为的存储和渲染系统等）。这使得本届 OSDI 的研究问题普遍具有强烈的现实驱动性，而非纯粹的学术探索。

2. **系统实现导向**：绝大多数论文都包含完整的系统原型实现（通常数千至上万行代码），并在真实硬件或生产环境中进行评估。"build it and show it works" 仍是 OSDI 的主流方法论。

3. **新硬件场景成为研究前沿**：晶圆级加速器（WaferLLM）、CXL 内存（Tigon、FineMem）、量子计算（QOS、HyperQ）、持久内存（WOLVES、F2FSJ）、新代 GPU 异构性（PipeThreader）等新硬件场景共同构成了今年最活跃的研究前沿之一。

4. **AI/ML 与系统研究深度融合**：超过三分之一的论文（AI 系统 11 篇 + LLM 推理 7 篇 + 分布式 AI 训练相关）直接涉及 AI/ML 工作负载的系统优化。这反映了 AI 推理和训练在当前系统研究中的核心地位。

---

## 2. 论文详细分类（按官方 Session）

> 以下按 [OSDI 2025 官方 Technical Sessions](https://www.usenix.org/conference/osdi25/technical-sessions) 分类。

---

### Distributed Systems and Data Centers I（6 篇，Monday 10:45–12:45）

**1. [Basilisk](osdi25-zhang-tony.md) — 从来源不变量自动化推导分布式协议不变量**
- 作者：Tony Nuda Zhang, Manos Kapritsos (密歇根大学), Bryan Parno (CMU) 等
- 核心贡献：Provenance Invariants（Network-Provenance + Host-Provenance）通过追踪状态的历史来源建立主机间关系。Atomic Sharding 算法自动推导 Provenance Invariants，无需 EPR 限制。在 16 个协议上自动找到归纳不变量，Multi-Paxos 仅需 4 个手工不变量（vs Kondo 的 20+）。
- 亮点：Multi-Paxos 不变量自动推导是形式化验证领域的重大突破。

**2. [T2C](osdi25-lou.md) — 从测试代码合成语义检查器检测静默失败**
- 作者：Chang Lou, Peng Huang (密歇根大学) 等
- 核心贡献：从测试代码自动合成语义检查器，多级验证（编译→JVM→自验证→交叉验证）确保质量。在 672 个检查器上检测 15/20 真实静默失败（75%），比所有基线组合（8/20）高出近一倍。
- 亮点：复用开发者精心编写的测试代码中蕴含的语义信息。

**3. [Picsou](osdi25-frank.md) — 复制状态机间高效通信**
- 作者：Reginald Frank, Micah Murray (UC Berkeley) 等
- 核心贡献：Cross-Cluster Consistent Broadcast（C3B）原语，为 RSM 间通信提供形式化框架。QUACKs 机制实现单消息发送、常量元数据的效率，支持 Raft/PBFT/Algorand 等异构 RSM。
- 亮点：C3B 填补了跨 RSM 通信缺乏形式化保证的空白。

**4. [FineMem](osdi25-wang-xiaoyang.md) — 细粒度 RDMA 内存解聚分配**
- 作者：Xiaoyang Wang, Yongkun Li (中国科学技术大学), Kan Wu (Google) 等
- 核心贡献：MW（内存窗口）替代 MR 注册消除分配开销（1µs vs 480µs per 4MB）+ 两层位图树结构（Section/Span）减少 RDMA 往返次数和 CAS 重试 + 紧凑临时 redo-log 保证崩溃一致性。分配延迟降低 95%，内存利用率提升 2.25-2.8 倍。
- 亮点：MW rkey 快速生成技术将细粒度分配变为实用。

**5. [VIO](osdi25-wang-yun.md) — 无需 PRI 的动态 I/O 设备直通**
- 作者：Yun Wang (上海交通大学), Liang Chen (阿里巴巴) 等
- 核心贡献：IOPA Snooping 机制利用 VirtIO 数据平面在 hypervisor 侧提前探测 DMA 页错误，消除 PCIe ATS/PRI 硬件依赖。IOPS 感知弹性直通（低 IOPS 用 VIO 模式回收内存，高 IOPS 切换直通模式）。Alibaba 300K VMs 规模部署，每天回收约 120GB 内存。
- 亮点：利用 VirtIO 标准特性的巧妙设计，无需硬件修改即可解决 legacy VM 兼容性问题。

**6. [FuseLink](osdi25-ren.md) — 多 NIC GPU 通信高效聚合**
- 作者：Zhenghang Ren, Yuxuan Li (香港科技大学) 等
- 核心贡献：利用 NVLink relay 聚合多 NIC 带宽，将 GPU 间 inter-server 带宽从 49.27 GBps 提升到 212.35 GBps（4.31 倍）。NCCL 集成使 ML 应用零代码修改受益。
- 亮点：动态流量 ML 任务（LLM Serving、MoE、DLRM）中流量不均衡问题的系统性解决。

---

### Database Systems（5 篇，Monday 14:00–15:40）

**1. [Tigon](osdi25-huang-yibo.md) — CXL Pod 分布式数据库**
- 作者：Yibo Huang, Emmett Witchel (UT Austin), Vijay Chidambaram 等
- 核心贡献：Cross-host Active Tuples（CAT）概念——活跃事务访问的元组集合很小可放入 CXL 硬件一致内存。SWcc（软件缓存一致性）+ HWcc（硬件缓存一致性）分离设计 + 无 2PC 的 epoch-based logging。TPC-C 比 Sundial+ 快 2.5 倍，8 主机吞吐量线性扩展 5.7 倍。
- 亮点：CAT 概念精准捕捉了跨主机事务处理的关键——正是活跃数据决定了一致性需求。

**2. [Mako](osdi25-shen-weihai.md) — 地理复制的投机分布式事务**
- 作者：Weihai Shen (Stony Brook), Yang Cui (Google), Siddhartha Sen (Microsoft Research) 等
- 核心贡献：将事务协调与复制解耦——事务在 DPDK 加速的同一数据中心内投机执行（speculatively），而复制在后台异步进行。2PC speculation 避免 unbounded cascading aborts，Per-core Paxos streams 避免跨核协调瓶颈。Azure 部署达 3.66M TPC-C/s，比最优竞品快 8.6 倍。
- 亮点：将协调与复制"解耦"反直觉地优于过去 15 年"合并"的趋势。

**3. [Quake](osdi25-mohoney.md) — 动态工作负载自适应向量索引**
- 作者：Jason Mohoney, Devesh Sarda (威斯康星大学) 等
- 核心贡献：自适应分层分区索引（Split/Merge/AddLevel/RemoveLevel）+ 自适应分区扫描（APS，基于几何的闭合形式召回估计，无需离线训练）+ NUMA 感知并行。Wikipedia-12M 动态工作负载下延迟比 HNSW 低 1.5-13 倍，更新延迟低 18-126 倍。
- 亮点：首个公开的真实向量搜索工作负载（Wikipedia-12M）填补了社区空白。

**4. [PipeANN](osdi25-guo.md) — SSD 上低延迟图基向量搜索**
- 作者：hao Guo, Youyou Lu (清华大学)
- 核心贡献：PipeSearch 算法引入伪依赖概念，使 I/O 与计算 overlap，I/O 管道利用率最大化。动态管道宽度调整在收敛阶段使用更大宽度。10 亿级数据集延迟仅为 DiskANN 的 35.0%，吞吐量高 1.71 倍。
- 亮点：首次揭示 best-first 搜索算法与 SSD I/O 特性的不匹配，伪依赖洞察极为精准。

**5. [Skybridge](osdi25-lyerly.md) — 分布式缓存的有界陈旧度**
- 作者：Robert Lyerly, Kevin Doherty, Greg Rogers (Meta) 等
- 核心贡献：Replication with Gap Detection（RGD）语义，实现 2 秒有界陈旧度保证（达 99.99998%）。系统仅占缓存部署规模的 0.54%，无需回源的请求达 99.9996%。
- 亮点：RGD 语义的设计取舍（只复制元数据而非数据）极具工程智慧。

---

### AI + Systems I（4 篇，Monday 16:10–17:30）

**1. [KPerfIR](osdi25-guan.md) — 编译器中心的 GPU 性能工具基础设施**
- 作者：Yue Guan (UCSD), Yuanwei Fang (Meta) 等
- 核心贡献：将 profiling 功能作为编译器 pass 实现（KPerfIR IR → KPerfGPUIR → LLVM），提供程序语义感知的细粒度分析。开销 < 10%，发现 FA3 内核 idle bubble 区域，改进后提升 24.1%。
- 亮点：编译器中心的架构弥合了 profiling 工具与编译器之间的语义鸿沟。

**2. [Mirage](osdi25-wu-mengdi.md) — 多层级张量程序超优化器**
- 作者：Mengdi Wu (CMU), Xinhao Cheng 等
- 核心贡献：μGraph 表示 + 多层级（algorithm/schedule/block/thread）超优化搜索，自动发现 FlashAttention 和 GEMM 等手工优化。TVM 上最高 4.5 倍加速，超越现有所有张量编译器。
- 亮点：首个端到端覆盖 kernel 生成到硬件映射的自动化超优化框架。

**3. [QiMeng-Xpiler](osdi25-dong.md) — 神经-符号张量程序跨平台翻译**
- 作者：Shouyang Dong, Jun Bi (中科院计算所) 等
- 核心贡献：LLM 生成高层代码框架 + SMT solver 修复低层细节，11 个转换 pass 覆盖三类转换（顺序化/并行化、内存转换、张量化/反张量化）。4 个 DLS 平台平均翻译准确率 95%，编程效率提升 34.3-96 倍。
- 亮点：神经-符号结合的方法论——两者各司其职，避免各自单独使用的局限性。

**4. [WaferLLM](osdi25-he.md) — 晶圆级大规模 LLM 推理**
- 作者：Congjie He, Pei Mu (爱丁堡大学), Luo Mai (爱丁堡大学) 等
- 核心贡献：PLMR 模型（P/并行/L/非均匀延迟/M/受限本地内存/R/受限路由）捕捉晶圆级加速器关键特性。MeshGEMM 利用 cyclic shifting + interleaving 在 720×720 核心规模维持 >70% 计算效率（比 SUMMA/Cannon 高 2-3 倍）。比 SGLang (A100) 提速 30-40 倍。
- 亮点：首个针对 Cerebras WSE-2 的 LLM 推理系统，PLMR 模型为后续研究提供分析框架。

---

### AI + Systems II（5 篇，Tuesday 09:00–10:40）

**1. [BLITZSCALE](osdi25-zhang-dingyan.md) — 亚秒级活体 LLM 自动扩缩容**
- 作者：Dingyan Zhang, Haotian Wang (华为云 & 上海交大) 等
- 核心贡献：O(1) 主机缓存（全局参数池多播，无逐实例缓存）+ GPU 计算网络空闲带宽传输模型参数（无需预缓存）+ Zigzag 流水线实现层级别细粒度活体扩缩。TTFT 比 ServerlessLLM 缩短 47-75%，GPU 资源节省 49%。
- 亮点：完全脱离缓存命中率依赖，使 LLM MAAS 的自动扩缩容真正实用化。

**2. [Bayesian Code Diffusion](osdi25-jeong.md) — 高效自动深度学习程序优化**
- 作者：Isu Jeong, Seulki Lee (UNIST)
- 核心贡献：Prior 传播（从已优化子图向相似子图）+ Code Diffusion（贝叶斯框架重新表述为代码优化上下文）+ Pre-training + Fine-tuning Cost Model。在 Ansor 上实现 CPU/GPU 最高 3.31 倍编译加速。
- 亮点：将 prior propagation 思想系统化应用于深度学习编译器 auto-tuning。

**3. [TrainCheck](osdi25-jiang.md) — 深度学习训练静默错误的自动化检测**
- 作者：Yuxuan Jiang, Runhui Xu, Peng Huang (密歇根大学) 等
- 核心贡献：对 88 个真实静默训练错误的实证分析。训练不变量自动推断 + 前置条件自动推导，检测率 18/20（90%），发现 6 个此前未知 bug。
- 亮点：不变量可迁移性（8%+ 适用于 16+ 流水线）是实用化的关键。

**4. [NEUTRINO](osdi25-huang-songlin.md) — 通过可编程探测实现细粒度 GPU 内核分析**
- 作者：Songlin Huang, Chenshu Wu (香港大学)
- 核心贡献：汇编层（PTX/GCNAsm）probing 系统，提供细粒度（指令级）、可编程（用户定义探针逻辑）、硬件无关的 GPU profiling。发现 Flash Attention 中的 Tailing Effect 新行为。
- 亮点：首次揭示 warp specialization 中的 Tailing Effect，为 FA3 优化提供洞察。

**5. [Principles and Methodologies for Serial Performance Optimization](osdi25-park-sujin.md)**
- 作者：Sujin Park, Taesoo Kim (佐治亚理工)
- 核心贡献：对 2013-2022 年 OSDI/SOSP 477 篇论文的分析，提炼出三个基本原则（Removal/Replacement/Reordering）和八种方法论（Batching/Caching/Precomputing/Deferring/Relaxation/Contextualization/Hardware Specialization/Layering）。SysGPT 微调 GPT-4o 提供情境感知优化建议。
- 亮点：将经验性的性能优化知识系统化，为 AI 辅助优化奠定方法论基础。

---

### Scheduling and Resource Management（5 篇，Tuesday 11:10–12:50）

**1. [Söze](osdi25-wang-weitao.md) — 单边网络遥测实现按流加权带宽分配**
- 作者：Weitao Wang, T. S. Eugene Ng (Rice University)
- 核心贡献：理论发现仅需一条流的路径上的一个网络遥测点（队列延迟），无需了解网络拓扑和路由信息，即可实现精确的加权 max-min 公平分配。收敛精度在 5% 以内，约 3-5 个 RTT 即可收敛。
- 亮点：将 INT 从监控工具提升为协调工具，理论基石（Lemma 3.3 瓶颈链路属性）严谨。

**2. [DeDe](osdi25-xu.md) — 规模化资源分配的解耦分解框架**
- 作者：Zhiying Xu, Minlan Yu (Harvard) 等
- 核心贡献：发现真实资源分配问题的可分离结构（目标函数可分离 + 约束按资源/需求独立），通过 ADMM 框架将问题并行分解为 n 个"每资源"子问题和 m 个"每需求"子问题。DEDE 在 3 秒内达到 0.94 最优分配质量，比 POP-4 快 1.6 倍。
- 亮点：可分离结构的洞察简单但深刻，将全局优化问题转化为可独立并行求解的子问题。

**3. [HyperQ](osdi25-tao.md) — 量子虚拟机**
- 作者：Runzhou Tao, Jason Nieh, Ronghui Gu (哥伦比亚大学) 等
- 核心贡献：qVM 抽象将量子计算机重复物理结构映射为虚拟资源，支持空间-时间双维度调度。利用 IBM Eagle 的 I 形区域结构，无需硬件修改即可实现量子虚拟化。吞吐量提升最高 9.7 倍，延迟改善最高 43 倍（19-40 小时缩短到 2-3 小时）。
- 亮点：将经典 VM 思想系统性引入量子计算，crosstalk 感知调度甚至可改善保真度。

**4. [Scalio](osdi25-sun.md) — DPU-based JBOF 键值存储 NVMe-oF 卸载**
- 作者：Xun Sun, Mingxing Zhang (清华大学) 等
- 核心贡献：利用 NVMe-oF Target Offload 让客户端直接读取 SSD，绕过 DPU CPU。7 块 SSD 配置下比 LEED 加速 2.5-17 倍。采用双层内存数据结构（DRAM 热点缓存 + SSD 直读）结合 RDMA 驱动的缓存一致性协议。
- 亮点：精准定位 DPU-JBOF 系统的 CPU 瓶颈与网络资源浪费之间的错配。

**5. [QOS](osdi25-giortamis.md) — 量子操作系统**
- 作者：Emmanouil Giortamis, Pramod Bhatotia (TU Munich)
- 核心贡献：Qernel 抽象作为量子作业统一执行单元 + 可组合错误缓解管道（Circuit Cutting + Qubit Freezing + Qubit Reuse）比单一技术提升 51% 电路深度减少 + 保真度感知调度器（等待时间降低 5 倍，保真度损失仅 2%）。首个多目标量子调度器。
- 亮点：量子作业调度的首个系统化框架，Qernel 抽象优雅统一了多样化量子作业。

---

### Distributed Systems and Data Centers II（5 篇，Tuesday 14:00–15:40）

**1. [Belfast](osdi25-bhat.md) — 投机共享日志降低端到端延迟**
- 作者：Shreesha G. Bhat, Tony Hong, Xuhao Luo (UIUC) 等
- 核心贡献：SpecLog 抽象通过 Fix-Ante Ordering 机制预测全局顺序，使 durability-first 共享日志可在协调完成前投机交付记录。Belfast 实现端到端延迟比 Scalog 低 1.6 倍。
- 亮点：将投机执行思想引入共享日志，优雅解决批量延迟问题。

**2. [TrainCheck](osdi25-lin-jinkun.md) — 大模型训练 straggler 根因分析**
- 作者：Jinkun Lin, Zhuoming Zhang, Gennady Pekhimenko (U of T) 等
- 核心贡献：5 个月跟踪、3079 个作业的系统性 straggler 分析。识别 6 类 straggler 根因（内存/网络/GPU/存储/调度/算法），What-if 分析框架量化每类根因的影响。发现超过 60% straggler 由 GPU 资源竞争而非硬件故障引起。
- 亮点：从"事后修复"到"事前预防"的范式转变。

**3. [AFaaS](osdi25-chai-xiaohu.md) — 生产无服务器系统的冷启动优化**
- 作者：Xiaohu Chai, Tianyu Zhou (清华大学 & 蚂蚁集团) 等
- 核心贡献：深度揭示三个被忽视的冷启动延迟来源（控制路径 RPC 18ms、资源竞争 namespace 创建 ×24 并发从 1.45ms 到 418ms、用户代码初始化 275ms）。FRI 接口替代 OCI 三层调用链 + cgroup/veth 池化 + Seccomp 预编译 + 树形 seed CoW。端到端冷启动 5.45-14.55ms，18 个月生产部署验证。
- 亮点：生产级数据驱动的深度分析，远超学术仿真的洞察深度。

**4. [Kamino](osdi25-domingo.md) — 延迟驱动的缓存感知 VM 分配**
- 作者：David Domingo (Rutgers), Hugo Barbalho, Marco Molinaro, Ishai Menache (微软研究院) 等
- 核心贡献：LatCache 算法首个延迟驱动的缓存感知在线请求调度算法 + Kamino 框架生产级实现。部分指标推理通过 AA 队列中请求类型和缓存命中预测来估计延迟。Azure AA 减少 17% 内存，p99 延迟降低 11.9%。
- 亮点：延迟估计模型的创新——无需完整缓存状态即可预测缓存命中。

**5. [ZEN](osdi25-wang-zhuang.md) — 稀疏驱动的分布式训练数据同步**
- 作者：Zhuang Wang, T. S. Eugene Ng (Rice University) 等
- 核心贡献：系统性分析稀疏张量三个关键特性（重叠率变化、聚合后密度提升、非零梯度偏斜分布），在四维设计空间中证明 Balanced Parallelism 或 Hierarchical Centralization 为通信最优方案。Theorem 1 的最优性证明为稀疏通信方案选择提供严格理论依据。
- 亮点：2.48 倍训练吞吐量提升，稀疏通信研究的里程碑式工作。

---

### Kernel and Operating Systems I（5 篇，Tuesday 16:10–17:50）

**1. [bpftime](osdi25-zheng-yusheng.md) — 安全高效的应用扩展**
- 作者：Yusheng Zheng, Dan Williams (弗吉尼亚理工) 等
- 核心贡献：EIM（扩展接口模型）将扩展所需功能抽象为资源 + 能力，bpftime 基于 eBPF 风格验证 + ERIM 风格 MPK 隔离 + 动态二进制重写。Nginx 扩展仅 2% 开销（vs Wasm 12%、ERIM 11%），GitHub 1000+ stars 说明真实用户基础。
- 亮点：EIM 的资源/能力模型是扩展场景的 capability 系统，概念贡献突出。

**2. [Tintin](osdi25-li.md) — 统一硬件性能剖析基础设施**
- 作者：Ao Li, Sanjoy Baruah (华盛顿大学圣路易斯分校)
- 核心贡献：EventProfilingContext（ePX）原语实现灵活精确的分析归属 + 不确定性驱动的弹性 HPC 调度（方差作为误差代理）。Tintin 弹性调度平均误差 2.91%（vs perf_event 的 9.01%）。云编排（Pond）延迟预测准确率提升 64%，入侵检测 AUC 提升 22.8%。
- 亮点：首个向用户报告测量置信度的 profiling 工具，改变了 HPC 测量的范式。

**3. [Omniglot](osdi25-schuermann.md) — 跨语言安全交互的内存隔离**
- 作者：Leon Schuermann, Amit Levy (Princeton) 等
- 核心贡献：识别 Rust soundness 四类不变量（Memory Safety + Aliasing/Mutability + Type Safety + Concurrency），Reference & Validation Types 将 foreign 返回值逐步验证为安全类型，Scopes 编译时强制执行零成本 temporal invariants。RISC-V PMP 和 x86 MPK 两个平台实现。
- 亮点：FFI soundness 问题首次被系统性解决，零成本安全的理念优雅。

**4. [KRR](osdi25-zhang-tianren.md) — 高效可扩展的内核记录-重放**
- 作者：Tianren Zhang (SmartX), Sishuai Gong, Pedro Fonseca (普渡大学)
- 核心贡献：Slice Record-Replay 边界从整个 VM 缩小到仅内核，Split-Recorder 架构（Guest 内核记录软件输入 + Hypervisor 记录硬件输入）。RC Spinlock 保证重放时指令计数严格一致。8 核 VM 记录开销仅 1.52-2.79 倍（vs VM-RR 的 8.97-29.94 倍）。
- 亮点：仅记录内核层而非整个 VM，在大数据和 kernel bypass 趋势下越发重要。

**5. [DeCl](osdi25-yedidia.md) — 在不受信任机器码上强制执行确定性**
- 作者：Zachary Yedidia, David Mazieres (Stanford)
- 核心贡献：将 SFI 技术从内存隔离扩展到确定性，通过 FADEC decoder + 未定义标志位数据流分析验证 x86-64/Arm64 确定性指令子集。Groundhog 智能合约引擎集成，启动 <15µs，比 JIT 快 2 倍，比解释执行快 30 倍。
- 亮点：无需信任编译器的确定性执行，智能合约场景的最佳落地。

---

### Kernel and Operating Systems II（5 篇，Wednesday 09:00–10:40）

**1. [rxBisect](osdi25-pismenny.md) — 解耦 NIC 接收环的双重角色**
- 作者：Boris Pismenny (EPFL & NVIDIA), Adam Morrison (Tel Aviv University), Dan Tsafrir (Technion)
- 核心贡献：将 Rx ring 的内存分配角色（A ring）与数据包交付角色（B ring）解耦，NIC 可从任意 Ax ring 获取 buffer，实现跨核 buffer 共享。吞吐量比 per-core baseline 提升 37%，延迟降低 11 倍。
- 亮点：首次系统揭示 Rx ring 双重角色耦合是 I/O 工作集问题的根本原因。

**2. [XSched](osdi25-shen-weihang.md) — 多样化 XPU 的抢占式调度**
- 作者：Weihang Shen, Rong Chen (上海交通大学) 等
- 核心贡献：XQueue 抽象（preemptible command queue）+ Multi-level 硬件模型（Lv1/Lv2/Lv3 对应 pending/in-flight/running 命令抢占）+ 跨 10 种 XPU 实现。视频会议在 NPU 上尾延迟降低 9.26 倍，Triton inference server 推理延迟降低 30.0%。
- 亮点：Multi-level 硬件模型使不同能力的 XPU 都能找到合适的抢占实现层次。

**3. [Spars](osdi25-wu-yuanpei.md) — 乱序执行/有序提交的并行 OS 渲染服务**
- 作者：Yuanpei Wu, Dong Du (上海交通大学), Haibo Chen (上海交大) 等
- 核心贡献：将乱序执行/有序提交（OOO/ISO）计算机体系结构思想引入 OS 渲染服务，In-order preparation → Out-of-order execution → In-order commit 三阶段管线。Spade2D 无状态引擎兼容现有有状态 API。帧率提升 1.76-1.91 倍，功耗降低 3.0%。
- 亮点：跨领域思想迁移的典范，乱序执行类比极为优雅。

**4. [EMT](osdi25-chai-siyuan.md) — 新型内存翻译架构的 OS 框架**
- 作者：Siyuan Chai, Tianyin Xu (UIUC) 等
- 核心贡献：类比 VFS 设计（Translation Object/Database/Service 三层抽象），为新内存翻译架构（ECPT、FPT 等）提供可扩展 Linux 支持，无需修改架构无关代码。平均开销 <0.5%，QEMU 工具链支持无真实硬件评估。
- 亮点：Iterator 优化将页故障处理降低 52.5%，展示看似微小的 OS 路径优化可产生巨大影响。

**5. [SoarAlto](osdi25-liu.md) — 超越热度的分层内存管理**
- 作者：Jinshu Liu, Huaicheng Li (弗吉尼亚理工) 等
- 核心贡献：AOL（Amortized Offcore Latency）指标 = Latency / MLP，整合延迟和内存级并行（MLP）来准确量化分层内存性能影响。证明热度作为性能代理不可靠——"热"页面放 DRAM、"冷"页面放 CXL 仅达 All-on-DRAM 的 52.4%。Soar 在 90% 内存在慢层时维持 <20% 减速（vs Nomad 最高 217% 减速）。
- 亮点：AOL 指标直击热度策略的根本缺陷。

---

### AI + Systems III（4 篇，Wednesday 11:10–12:30）

**1. [NanoFlow](osdi25-zhu-kan.md) — 接近最优的 LLM 推理吞吐量**
- 作者：Kan Zhu, Yufei Gao, Arvind Krishnamurthy (华盛顿大学) 等
- 核心贡献：揭示批处理后 LLM 推理实际是 compute-bound（而非传统认为的 memory-bound）。NanoFlow 将操作分成 nano-batches 实现设备内并行，两阶段 MILP Auto-search 自动计算最优流水线。相比 vLLM 提速 1.91 倍（达理论最优的 68.5%）。
- 亮点：反直觉的核心发现——compute-bound 而非 memory-bound，改变了 LLM serving 系统设计的基本假设。

**2. [PipeThreader](osdi25-cheng.md) — 软件定义的 DNN 执行流水线**
- 作者：Yu Cheng, Lei Wang (北京大学), Mao Yang (微软研究院) 等
- 核心贡献：sTask 和 sEU 抽象将 DNN 计算映射到 GPU 异构执行单元（TensorCore/TMU/CUDA Core），Propagate 接口自动推导 tile shape。在 H100 和 AMD MI300X 上自动发现与 FlashAttention-3 手工实现相当的流水线方案；Mamba2 ChunkScan 显著优于官方实现。
- 亮点：超越手工优化——编译器自动探索的流水线配置达到甚至超过人工优化水平。

**3. [WLB-LLM](osdi25-wang-zheng.md) — 大语言模型训练的工作负载均衡 4D 并行**
- 作者：Zheng Wang (UCSD, Meta), Anna Cai (Meta) 等
- 核心贡献：首次系统性分析 4D 并行中的 PP 和 CP 层工作负载不均衡。ILP 公式化可变长度文档打包 + 自适应异常值延迟策略，CP 层按文档分片。瓶颈 GPU 延迟从 1.44 倍降至接近 1.0 倍，平均训练加速 1.23 倍。
- 亮点：Meta 真实 405B 模型、128K 上下文的生产数据验证。

**4. [DecDEC](osdi25-park-yeonhong.md) — 低比特 LLM 量化的动态误差补偿**
- 作者：Yeonhong Park, Jake Hyun (首尔大学) 等
- 核心贡献：动态识别显著通道（基于激活异常值的逐解码步骤变化），选择性从 CPU 内存获取残差进行误差补偿。困惑度从 10.15 降至 9.12（3-bit Llama-3），GPU 内存增量仅 0.0003%，RTX 4050 Mobile 延迟增加仅 1.7%。
- 亮点：CPU-GPU 异构平台利用的精准切入点——激活异常值的动态特性。

---

### File and Storage Systems（5 篇，Wednesday 14:00–15:40）

**1. [Nostor](osdi25-gao.md) — 无 Stripe 的纠删码内存存储**
- 作者：Jian Gao, Jiwu Shu (清华大学) 等
- 核心贡献：基于对称平衡不完全区组设计（SBIBD）的无 stripe 数据放置方案，无需 MDS 协调即可保证多节点故障恢复。吞吐量比 Cocytus/PQ 高 1.61-2.60 倍。
- 亮点：将组合数学理论（SBIBD）应用于分布式存储设计。

**2. [PoWER](osdi25-leblanc.md) — 工具无关的崩溃一致性和损坏检测验证**
- 作者：Hayley LeBlanc (UT Austin), Chris Hawblitzel (Microsoft Research), Nickolai Zeldovich (MIT) 等
- 核心贡献：Preconditions on Writes Enforcing Recoverability（PoWER）方法——仅依赖标准 Hoare 逻辑和量词，无需额外验证器特性。灵活 CRC 数据损坏模型 + CDB 原语。CAPYBARAKV（Verus）和 CAPYBARANS（Dafny）两个验证系统，证明/代码比 2.6。Azure Storage 原型集成。
- 亮点：工具无关性使形式化验证不再被陡峭学习曲线阻挡。

**3. [WOLVES](osdi25-pan.md) — 快速同步崩溃一致性的元数据 Write-Once 文件系统**
- 作者：Yanqi Pan, Wen Xia (哈尔滨工业大学) 等
- 核心贡献：WOFS 模型将每个文件操作的元数据聚合为单一 Write-Once package（仅需一次排序点），Package 翻译层（PTL）兼容传统文件系统抽象。顺序写达 97.3-99.1% PM 带宽利用率，随机写比 NOVA/PMFS/SplitFS 快 1.65-9.44 倍。
- 亮点：Package 概念——将多个排序点减少为单一排序点，是核心创新。

**4. [F2FSJ](osdi25-cui.md) — 去中心化基于 Epoch 的 F2FS 日志**
- 作者：Yaotian Cui, Zhiqi Wang (香港中文大学) 等
- 核心贡献：per-inode 日志（去中心化，避免 JBD2 集中式锁竞争）+ Epoch-based 数据/控制平面解耦（日志周期切换零等待）+ Fast-forward-to-latest 合并多个小更新。检查点时间缩短 4.9 倍，可恢复 99.9% 文件/元数据（vs F2FS 默认的 90.9%）。
- 亮点：仅 3,000 行代码改动即可在生产级文件系统中实现。

**5. [Okapi](osdi25-athlur.md) — 数据条带化与冗余分组解耦**
- 作者：Sanjith Athlur, Timothy Kim (CMU), Saurabh Kadekodi (Google) 等
- 核心贡献：将数据条带化（stripe width）与纠删码分组（group width）解耦，使两者可独立配置。提出贪婪部分奇偶校验计算，实现 EC 转换 IO 节省约 50%。生产验证：Google 每天 100K+ 次 EC 转换。
- 亮点：Google 生产数据支撑，HDFS 最小改动集成。

---

### Privacy and Security（4 篇，Wednesday 16:10–17:30）

**1. [Compass](osdi25-zhu-jinhao.md) — 高精度加密语义搜索**
- 作者：Jinhao Zhu (UC Berkeley), Matei Zaharia, Raluca Ada Popa 等
- 核心贡献：Encrypted Semantic Search（ESS）框架，利用信息论下界（SIM 攻击）量化安全性，通过 encrypted embedding 保持语义精度。在 SOTA PIR 方案上实现 26.7-55.8% 精度提升，同时满足查询级安全。
- 亮点：首次在加密数据上实现有语义保障的高精度搜索。

**2. [Weave](osdi25-soleimani.md) — 高效表达力强的遗忘分析**
- 作者：Mahdi Soleimani, Anurag Khandelwal (耶鲁大学)
- 核心贡献：IND-CDJA 安全定义 + Three-phase shuffle（Random-shuffle → Histogram → Balanced-shuffle）防止 split-based 和 distribution-based leakage + 遗忘内存访问（EPC + ORAM）。Apache Spark 实现，网络开销仅 ~3 倍（非 oblivious sort 的 10 倍以上）。
- 亮点：常数因子 overhead（非 log-linear）使 oblivious analytics 首次接近实用。

**3. [Paralegal](osdi25-adam.md) — 隐私漏洞实用静态分析**
- 作者：Justus Adam, Shriram Krishnamurthi, Malte Schwarzkopf (Brown University)
- 核心贡献：Marker 抽象分离隐私工程师与应用开发者的职责，PDG（程序依赖图）+ Rust 所有权类型系统利用。不变量无需人工编写。发现 Lemmy 平台 2 个此前未知漏洞，CodeQL 和 IFC 均无法检测。
- 亮点：隐私工程师与应用开发者技能不对称问题的优雅解决方案。

**4. [MettEagle](osdi25-miemietz.md) — 微内核上的容器实现**
- 作者：Till Miemietz, Hermann Härtig (Barkhausen Institut & TU Dresden) 等
- 核心贡献：在 L4Re 微内核上实现容器级隔离（visibility restrictions + resource budgets + 接口限制）。TCB 代码量是 Linux + runc 的 1/30（89K vs 2.7M SLOC），33 个容器隔离相关 CVE 中微内核方法从根本上减少了暴露面。SeBS 无服务器基准测试与 runC 性能相当。
- 亮点：微内核最小权限原则与容器隔离的自然契合，提供了量化安全对比。

---

--

## 3. 研究趋势分析

### 3.1 最热门的子领域

**AI + Systems 三分天下**：OSDI 2025 官方 Session 中 AI + Systems I/II/III 共 13 篇论文（占总论文数 24.5%），涵盖 LLM serving（NanoFlow、BLITZSCALE、WaferLLM、DecDEC）、AI 编译器（PipeThreader、Mirage、QiMeng-Xpiler、Bayesian Code Diffusion）、分布式训练（WLB-LLM、ZEN、TrainCheck）和 GPU profiling（KPerfIR、NEUTRINO、Principles）。AI 相关论文合计超过 20 篇，是 OSDI 有史以来最集中的 AI 系统研究热潮。

**量子计算异军突起**：QOS 和 HyperQ 共同表明量子计算系统研究已成熟到可以在 OSDI 这样的顶级系统会议上占据一席之地。两者都从"虚拟化"和"调度"这些经典系统问题出发，为量子资源管理奠定基础。

### 3.2 新硬件/新技术成为研究热点

**晶圆级加速器（Cerebras WSE-2）**：[WaferLLM](osdi25-he.md) 是 OSDI 历史上首次系统性研究在晶圆级芯片上运行 LLM 推理，PLMR 模型（P/L/M/R）填补了此类硬件的系统设计理论空白。

**CXL 内存**：[Tigon](osdi25-huang-yibo.md) 和 [FineMem](osdi25-wang-xiaoyang.md) 分别从数据库（事务处理）和内存解聚（RDMA 分配）两个角度切入 CXL 内存这一新兴硬件。两者都表明 CXL 的硬件一致性（HWcc）和独特延迟/带宽特性需要新的系统设计。

**GPU 异构性**：H100/AMD MI300X 中 TensorCore/TMU/CUDA Core 的异构共存（[PipeThreader](osdi25-cheng.md)），多 NIC GPU 服务器的通信瓶颈（[FuseLink](osdi25-ren.md)），NVLink 作为 relay 基础设施的可能性——这些都表明 GPU 集群的系统设计正在从"同构 GPU + NCCL"向更复杂的异构生态演进。

**持久内存**：[WOLVES](osdi25-pan.md) 和 [F2FSJ](osdi25-cui.md) 对 3D-XPoint/CXL-SSD 的文件系统优化，表明 PM 领域从早期的性能探索进入系统实用化阶段。

### 3.3 系统研究方法论的演变

**生产数据驱动的深度分析**：AFaaS（18 个月生产运行、50K 函数）、[Lin-jinkun](osdi25-lin-jinkun.md)（5 个月跟踪、3079 个作业）、Skybridge（Meta TAO 生产环境）、WLB-LLM（405B 模型 128K 上下文实际训练）等论文表明，工业界超大规模部署为系统研究提供了前所未有的实证基础。这对学术论文的研究问题选择和评估设计产生了深刻影响。

**理论-工程精准结合**：Söze（Lemma 3.3 瓶颈链路属性数学证明）、ZEN（Theorem 1 最优稀疏通信证明）、Basilisk（Provenance Invariants 形式化推导）、[DeDe](osdi25-xu.md)（ADMM 收敛性保证）等论文表明，系统论文中的理论分析不再只是"装饰"，而是真正指导系统设计的核心。

**编译器中心化设计**：KPerfIR、NEUTRINO 将 profiling 作为编译器 pass 实现，QiMeng-Xpiler 将 LLM + SMT 联合引入程序翻译——这些都表明编译器基础设施正在成为系统性能优化的核心杠杆。

### 3.4 AI/ML 与系统研究的融合趋势

**AI 推理的系统优化**：[NanoFlow](osdi25-zhu-kan.md) 的 compute-bound 发现改变了 LLM serving 系统设计的基本假设，[BLITZSCALE](osdi25-zhang-dingyan.md) 实现了真正实用的 autoscaling，[DecDEC](osdi25-park-yeonhong.md) 精准利用 CPU-GPU 异构性——这些表明 LLM serving 的系统优化已从"好不好用"进入"怎么最优"的精细化阶段。

**AI 编译器的崛起**：[PipeThreader](osdi25-cheng.md)（编译器探索超越手工优化）、[KPerfIR](osdi25-guan.md)/[NEUTRINO](osdi25-huang-songlin.md)（编译器感知 profiling）、[QiMeng-Xpiler](osdi25-dong.md)（跨平台程序翻译）、[Bayesian Code Diffusion](osdi25-jeong.md)（学习型编译优化）、[Mirage](osdi25-wu-mengdi.md)（超优化器）——AI 编译器作为连接算法和硬件的桥梁，其重要性在 OSDI 2025 中得到充分体现。

**LLM 训练的系统优化**：WLB-LLM（4D 并行负载均衡）、ZEN（稀疏梯度通信）、TrainCheck（静默训练错误检测）——大模型训练的系统优化（而非仅推理优化）开始受到更多关注。

---

## 4. 未来研究方向建议

### 4.1 最具潜力的探索方向

**1. 跨 LLM Serving 栈的端到端协同优化**

[NanoFlow](osdi25-zhu-kan.md) 优化单 GPU 设备内并行，[BLITZSCALE](osdi25-zhang-dingyan.md) 优化多实例扩缩容，[DecDEC](osdi25-park-yeonhong.md) 优化低比特量化——但目前这三者之间几乎没有协同。探索 NanoFlow + BLITZSCALE + DecDEC 的联合优化有望进一步提升 LLM serving 效率。建议理由：各层优化正交，联合设计有望实现"1+1+1 > 3"的效果。

**2. 形式化验证工具的自动化与普及化**

[Basilisk](osdi25-zhang-tony.md)（分布式协议不变量自动推导）和 [PoWER](osdi25-leblanc.md)（工具无关验证）表明形式化验证正在从"专家专用"向"工程师可用"转变。未来方向：基于 LLM 的不变量推荐（结合 [SysGPT](osdi25-park-sujin.md) 思路）+ 更自动化的验证建议生成。潜在影响力：降低形式化验证门槛可能改变系统安全工程的实践。

**3. CXL 内存生态的完整系统栈**

[Tigon](osdi25-huang-yibo.md)（数据库）和 [FineMem](osdi25-wang-xiaoyang.md)（内存解聚）分别解决了 CXL 内存的一个子问题，但 CXL 内存生态（HWcc + SWcc + CXL switch + 内存池化）需要从操作系统（[EMT](osdi25-chai-siyuan.md)）、运行时（内存分配器）、应用（数据库/键值存储）到调度器（[Kamino](osdi25-domingo.md)/[XSched](osdi25-shen-weihang.md)）的完整协同。潜在影响力：CXL 预计在 2025-2027 年成为数据中心主流，完整的系统栈研究空间巨大。

**4. 量子-经典混合系统的资源管理**

[QOS](osdi25-giortamis.md)（量子作业调度）和 [HyperQ](osdi25-tao.md)（量子虚拟机）开创了量子计算系统研究，但两者都专注于单量子计算机。未来方向：量子-经典异构集群的联合调度、量子错误缓解与经典预处理的协同、量子云计算的 SLA 管理。潜在影响力：量子计算正处于从 NISQ 向 FTQC（容错量子计算）的过渡期，提前布局至关重要。

**5. 遗忘计算的大规模实用化**

[Weave](osdi25-soleimani.md) 实现了 ~3 倍 overhead（vs 10 倍+ 的 oblivious sort），但其安全定义（IND-CDJA）和 TEE 依赖在生产环境中仍有局限。未来方向：更强的 obliviousness 保证（对抗更强的 adversary）+ 纯软件实现（不依赖 TEE）+ 更复杂的分析操作（join、aggregate 等）。潜在影响力：在数据隐私法规（GDPR、CCPA）日益严格的背景下，遗忘分析是合规计算的基础设施。

### 4.2 中期值得关注的方向

**6. GPU/AI 训练集群的网络化**：[FuseLink](osdi25-ren.md)（GPU 间通信聚合）、[ZEN](osdi25-wang-zhuang.md)（稀疏梯度同步）、[WLB-LLM](osdi25-wang-zheng.md)（4D 并行负载均衡）都揭示了当前 ML 集群网络的低效，但三者相对独立。未来方向：联合通信-计算调度 + 自适应稀疏-稠密切换。

**7. 多模态 AI 系统的端到端性能**：当前 LLM serving 研究主要关注纯文本场景，多模态（图像、视频、语音）推理有完全不同的计算特性和延迟需求。

**8. 形式化验证与 AI 的结合**：[Basilisk](osdi25-zhang-tony.md) 和 [SysGPT](osdi25-park-sujin.md) 代表了两个方向（自动化推导 + AI 辅助建议），但两者尚未结合。下一代形式化验证工具可能由 AI 模型驱动，同时保留 SMT solver 的正确性保证。

---

## 5. 重点论文推荐

以下按重要性排序，附推荐理由：

### 第一梯队（极具影响力）

**1. [NanoFlow](osdi25-zhu-kan.md) (Zhu et al.)**
- 推荐理由：反直觉的 compute-bound 发现改变了 LLM serving 系统设计的基本假设。68.5% 接近理论最优吞吐量 + 1.91 倍相对 vLLM 提速，标志着 LLM inference optimization 进入系统化新阶段。方法论（成本模型 + MILP Auto-search）对后续工作具有指导意义。

**2. [WaferLLM](osdi25-he.md) (He et al.)**
- 推荐理由：OSDI 历史上首次系统性研究晶圆级 LLM 推理，PLMR 模型为后续研究提供了无可替代的分析框架。30-40 倍相对 SGLang 提速和 160 倍 prefill 加速展示了新硬件的颠覆性潜力。开源也是加分项。

**3. [Basilisk](osdi25-zhang-tony.md) (Zhang et al.)**
- 推荐理由：Multi-Paxox 不变量自动推导是形式化验证领域的重大突破，将开发者从数月的"猜测-证明-修正"循环中解放。Theorem 1 的最优性证明严谨，16 个协议的广泛验证覆盖了分布式系统核心场景。

**4. [Mako](osdi25-shen-weihai.md) (Shen et al.)**
- 推荐理由：协调-复制解耦的反直觉方向 + Epoch-based bounded failure recovery 的精巧设计，使地理复制分布式事务吞吐量接近单机器水平。Azure 3.66M TPC-C/s 的数字在实际系统中有说服力。

**5. [PipeThreader](osdi25-cheng.md) (Cheng et al.)**
- 推荐理由：编译器自动探索超过 FlashAttention-3 手工优化，证明了"软件定义流水线"的可行性和价值。sTask/sEU 抽象优雅捕捉了 GPU 异构性，对 AI 编译器生态有持久影响。

### 第二梯队（重要贡献）

**6. [BLITZSCALE](osdi25-zhang-dingyan.md) (Zhang et al.)**
- 推荐理由：完全脱离缓存命中率依赖的 autoscaling 是 LLM MAAS 实用化的关键一步。Zigzag 流水线允许部分加载实例先工作的想法朴素但极为有效。

**7. [SoarAlto](osdi25-liu.md) (Liu et al.)**
- 推荐理由：AOL 指标直击热度策略的根本缺陷，"NoTier 优于许多分层基线"这一观察极为有力。Soar（profile-guided 静态分配）+ Alto（自适应动态调控）的双轨策略成熟务实。

**8. [Skybridge](osdi25-lyerly.md) (Lyerly et al.)**
- 推荐理由：RGD 语义的设计取舍（只复制元数据）极具工程智慧，解决了 Meta TAO 的真实痛点。0.54% 存储规模的数字令人信服。

**9. [QOS](osdi25-giortamis.md) (Giortamis et al.)**
- 推荐理由：首个量子操作系统框架，Qernel 抽象为量子作业管理奠定基础。三种错误缓解技术的可组合性（Circuit Cutting + Qubit Freezing + Qubit Reuse）是量子计算领域的创新应用。

**10. [DeCl](osdi25-yedidia.md) (Yedidia et al.)**
- 推荐理由：无需信任编译器的确定性执行，解决了智能合约的核心安全问题。未定义标志位的数据流分析严谨，Groundhog 集成验证了实用价值。

**11. [WOLVES](osdi25-pan.md) (Pan et al.)**
- 推荐理由：Package 概念简单但极为有效，将 PM 文件系统的多个排序点减少为单一排序点。97.3-99.1% PM 带宽利用率是极高的性能水准。

**12. [Omniglot](osdi25-schuermann.md) (Schuermann et al.)**
- 推荐理由：Rust FFI soundness 问题的系统性解决，四类不变量分类（Memory/Aliasing/Type/Concurrency）是该领域的概念性突破。零成本安全的 Scopes 机制优雅。

**13. [Spars](osdi25-wu-yuanpei.md) (Wu et al.)**
- 推荐理由：乱序执行/有序提交的跨领域思想迁移极具启发性。在华为多款旗舰手机上（Mate70、MateX5、MateXT）的工业级验证具有高度可信度。

**14. [AFaaS](osdi25-chai-xiaohu.md) (Chai et al.)**
- 推荐理由：三个被忽视的冷启动延迟来源（控制路径 RPC、资源竞争、用户代码初始化）的揭示具有广泛适用性。18 个月生产部署证明了方案的工程成熟度。

**15. [ZEN](osdi25-wang-zhuang.md) (Wang et al.)**
- 推荐理由：稀疏张量三个关键特性的系统性分析 + Theorem 1 的最优性证明，为稀疏通信研究提供了严格的理论框架和工程指南。2.48 倍训练吞吐量提升在实际训练场景中价值巨大。

---

## 6. 个人评注

### 6.1 本届 OSDI 的亮点

**工业界与学术界的深度融合**：本届 OSDI 最令人印象深刻的特点是工业界研究机构的主导性。Meta（[Skybridge](osdi25-lyerly.md)、[Mako](osdi25-shen-weihai.md) 的部分作者）、Microsoft（[PoWER](osdi25-leblanc.md)、[KRR](osdi25-zhang-tianren.md)）、Google（[Okapi](osdi25-athlur.md)、[Mako](osdi25-shen-weihai.md)）、华为/阿里（[FineMem](osdi25-wang-xiaoyang.md)、[Spars](osdi25-wu-yuanpei.md)、[AFaaS](osdi25-chai-xiaohu.md)）、Cerebras（[WaferLLM](osdi25-he.md) 的硬件支持）等超大规模机构的参与，为 OSDI 带来了真实、量大、有代表性的生产数据和部署验证。这使得 OSDI 2025 的研究问题普遍具有强烈的现实意义，而非纯粹的学术探索。

**新硬件研究的系统性突破**：晶圆级加速器（Cerebras WSE-2）、CXL 内存、量子计算、持久内存——这些硬件的共同特点是"在真实硬件上可用，但在系统层面缺乏设计经验"。OSDI 2025 的多篇论文（[WaferLLM](osdi25-he.md)、[Tigon](osdi25-huang-yibo.md)、[FineMem](osdi25-wang-xiaoyang.md)、[QOS](osdi25-giortamis.md)、[HyperQ](osdi25-tao.md)）共同为这些新硬件构建了第一批系统化知识和设计原则。

**形式化验证走向实用**：[Basilisk](osdi25-zhang-tony.md) 和 [PoWER](osdi25-leblanc.md) 标志着形式化验证正在从"理论可行"向"工程师可用"转变。工具无关性和自动化不变量推导降低了下游开发者使用形式化方法的门槛，这是改变系统安全工程实践的长期趋势。

**跨领域思想迁移**：[Spars](osdi25-wu-yuanpei.md)（计算机体系结构 → OS 渲染）、[Söze](osdi25-wang-weitao.md)（网络测量 → 网络协调）、[PipeThreader](osdi25-cheng.md)（硬件并行模型 → AI 编译器调度）、[Omniglot](osdi25-schuermann.md)（OS capability 系统 → FFI 安全）——这些论文展示了系统研究的核心价值：从一个问题领域的深刻理解中提炼可迁移的设计原则。

### 6.2 潜在不足与观察

**某些论文的"首创"声明值得审视**：多篇论文声称"首个"——首个量子操作系统（[QOS](osdi25-giortamis.md)）、首个 CXL Pod 数据库（[Tigon](osdi25-huang-yibo.md)）、首个编译器中心 GPU 性能工具（[KPerfIR](osdi25-guan.md)）。其中部分声明取决于如何定义边界（QOS 更像是作业调度框架而非传统意义上的操作系统），读者应注意区分概念贡献和系统贡献的相对强度。

**"X 倍提升"数字需要谨慎解读**：OSDI 2025 论文中大量出现"最高 X 倍提升"的数字，但这些数字往往在特定配置、特定硬件、特定工作负载下达成的。例如：[DecDEC](osdi25-park-yeonhong.md) 的 94% TBT 降低仅在 BurstGPT+Qwen2.5-72B 配置下，[BLITZSCALE](osdi25-zhang-dingyan.md) 的结果在 NVLink 环境下最佳，[WaferLLM](osdi25-he.md) 相对于 SGLang (A100) 的提速在多 GPU 配置下可能缩小。读者在评估具体工作时，应注意这些数字的条件性和上下文。

**方法论验证的局限性**：部分论文（[rxBisect](osdi25-pismenny.md)、[HyperQ](osdi25-tao.md)）主要依赖软件仿真而非真实硬件。虽然论文作者通常会说明这一点，但在评估其结论的可信度时应纳入考量。

**开源生态的挑战**：本届 OSDI 论文中，明确开源（GitHub）的比例约为 40-50%。这低于社区期望，也限制了其他研究者对工作进行独立验证和扩展。值得欣慰的是 [WaferLLM](osdi25-he.md)、[KPerfIR](osdi25-guan.md)、[QiMeng-Xpiler](osdi25-dong.md)、[ZEN](osdi25-wang-zhuang.md)、[bpftime](osdi25-zheng-yusheng.md) 等重要工作已开源。

### 6.3 对系统领域学术生态的观察

**"Big Tech Systems" 的成熟**：以 Meta、Microsoft、Google、华为/阿里/字节为代表的新一代工业界系统研究团队，已经形成了完整的研究-工程-发表闭环。这些团队产出的论文（Skybridge、Mako、WLB-LLM 等）在问题选择、数据规模、工程完整性上都达到了顶级学术标准，对学术系统研究形成了有力的竞争和补充。

**AI for Systems 和 Systems for AI 的双向融合**：本届 OSDI 清晰地展示了 AI 和系统研究的两条融合路径——AI for Systems（[SysGPT](osdi25-park-sujin.md) 辅助性能优化、[Bayesian Code Diffusion](osdi25-jeong.md)、[QiMeng-Xpiler](osdi25-dong.md)、[Mirage](osdi25-wu-mengdi.md)）和 Systems for AI（[NanoFlow](osdi25-zhu-kan.md)、[BLITZSCALE](osdi25-zhang-dingyan.md)、[WaferLLM](osdi25-he.md)、[DecDEC](osdi25-park-yeonhong.md)）。前者使用 AI 方法解决系统问题，后者为 AI 工作负载构建更好的系统基础设施。两条路径都极具前景。

**形式化验证的第三波浪潮**：从 IronFleet（手工归纳不变量）到 Kondo（EPR 限制的自动推导）再到 Basilisk（Provenance Invariants，移除 EPR 限制）——形式化验证领域正在经历快速演进。随着自动化程度的提升，形式化验证有望在未来 5 年内进入更多系统工程师的工具箱。

---

*本综述基于 OSDI 2025 全部 53 篇论文的个人阅读报告综合撰写，力求客观呈现每篇论文的核心贡献和研究价值，同时提出个人见解。疏漏和偏颇之处在所难免，仅供参考，欢迎指正。*
