---
type: paper
name: MAIO
full_title: "Accelerating Model Loading in LLM Inference by Programmable Page Cache"
authors: [Yubo Liu, Hongbo Li, Xiaojia Huang, Yongfeng Wang, Hanjun Guo, Hui Chen, Yuxin Ren, Ning Jia]
venue: FAST
year: 2026
tags: [llm-inference, model-loading, page-cache, file-system, maas]
source_pdf: "[[fast2026-liu-yubo.pdf]]"
source_md: "[[fast2026-liu-yubo]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Accelerating Model Loading in LLM Inference by Programmable Page Cache (FAST 2026)

> **一句话总结**：观察到 kernel page cache 在 LLM model loading 上 SSD 带宽利用仅 ~17%、忽视 [[NUMA]]/XPU affinity、LRU 驱逐不感知「host→device 拷完即可丢」的时序局部性；用非侵入 stacked FS 框架 PPC + I/O 模板策略 MAIO，在不改 kernel 上游模块、不绑特定硬件、不侵入 [[vLLM]]/[[SGLang]] 的前提下，把 model loading 延迟降最多 **79%**（memory-rich）/ **74%**（memory-constrained），工业部署 DeepSeek-R1-671B 从 **649 s → 452 s**。

## 问题与动机

[[MaaS]] 平台弹性启动 LLM 推理服务时，**startup latency** 直接决定 QoS 与资源利用率。模型已达数百 GB 乃至 TB 级——华为生产平台上 DeepSeek-R1-671B 冷启动约 **1 小时**，其中从 OBS 拉模型占 **>70%**；即便模型已放本地 SSD，Qwen2.5-72B 的 loading 仍达分钟级，占端到端 startup 的 **>50%**。

主流加速路线（[[ServerlessLLM]]、[[BlitzScale]] 等）通过深度改造 inference 框架或依赖 NVLink/[[RDMA]] 互连提速，但牺牲 **兼容性**——而生产环境换 kernel 要数年、推理栈是基础设施黑盒、硬件特性不通用。作者提出三维权衡：

1. **推理生态透明**：不改 [[vLLM]]、[[SGLang]] 等框架与模型格式；
2. **OS 非侵入**：独立 kernel module，不改上游 VFS/eBPF helper；
3. **硬件无关**：不依赖 NVLink/HCCS 等芯片特性。

核心洞察：模型以文件形式存盘，loading 走 POSIX read/mmap，瓶颈在 **kernel page cache 的 prefetch/eviction 策略**——而非缺一个更快的用户态 loader。目标是在本地文件系统上做到 SOTA loading 性能且三面兼容。

## 关键观察 / 隐含假设

- **观察 1**：model loading 期间 SSD 带宽严重闲置，kernel prefetch 无法把 I/O 藏进 startup 其他阶段。
  - **证据**：Qwen2.5-72B / Llama-70B startup 采样，model loading 阶段 SSD 平均带宽仅峰值约 **17%**；framework init 与 tensor 后处理等非 I/O 阶段也未被有效 overlap。
  - **依赖假设**：模型从本地 SSD 经 kernel page cache 加载；prefetch 受 kworker 数量与同文件相邻 **128 KB** 启发式限制。
  - **可能失效场景**：全 DRAM 缓存、NVMe 池化内存、或用户态直读绕过 page cache 时，该观察不成立。

- **观察 2**：model loading 对 **XPU affinity**（数据应落在目标 GPU/NPU 对应 NUMA）敏感，但 kernel prefetch 盲目放到 kworker 所在 NUMA。
  - **证据**：多副本 tmpfs 绑不同 NUMA、改 [[vLLM]] 让每个 XPU 只读本 NUMA 副本，loading 延迟降约 **20%**。
  - **依赖假设**：host→device 传输走 PCIe，NUMA 跨节点拷贝有可观开销；[[Tensor-Parallelism]] 下各 worker 读不同 shard。
  - **可能失效场景**：UMA 架构、device 与 DRAM 等距、或框架已做 pinned memory/DMA 优化削弱 NUMA 影响。

- **观察 3**：model loading 有强 **时序局部性**——页面一旦被 host→XPU 传输完成即可从 host page cache 驱逐，但 kernel LRU 采样无法感知这一生命周期。
  - **证据**：可用 page cache 仅模型大小 **45%** 时，Qwen2.5-72B loading 延迟比充足内存场景高 **38%**。
  - **依赖假设**：推理生命周期内权重常驻 device HBM，host 侧 cache 无复用价值；memory 需留给 [[KV-Cache]] 等。
  - **可能失效场景**：同一节点频繁切换不同模型且 host cache 可复用、或 weight streaming/offload 需反复读 host cache。

- **观察 4**：同一 inference service template（模型 + [[Tensor-Parallelism]] + [[Disaggregation]] 配置一致）的 I/O 序列 **可复现**。
  - **证据**：MaaS 预构建 service template；MAIO 用 service ID（模型名+TP+PD 等参数 hash）关联 I/O template，DeepSeek-R1-671B template 仅 **545 KB**。
  - **依赖假设**：框架按稳定顺序读权重文件；worker PID 与 XPU 拓扑映射在同类部署间一致。
  - **证据强度**：**强**——工业部署与 micro-benchmark 均验证；但 template 需在配置变更时重生。
  - **可能失效场景**：框架升级改变读序、动态 shard、量化格式切换、或 fine-tune 后权重布局变化。

- **假设 1**：stacked read-only file system + userspace UPC 能在 **<7%** 前端 I/O 开销下替换 kernel cache policy。
  - **证据强度**：**中**——empty policy 下 EXT4/XFS memcpy-after-mmap 开销 3.7%/6.4%，远低于 RFUSE 的 14–15%；但 UPC 监听在高压并发下可达 11% CPU。

## 核心方法

### PPC：可编程 Page Cache 框架

PPC 分内核 **RFS（Routing File System）** 与用户态 **CPRT（Cache Policy Runtime）**：

- **RFS**：独立 kernel module，基于 stacked FS（类似 OverlayFS）叠在任意底层 FS 上；只读场景劫持 read / mmap page fault 的 cache miss，把 file handle、offset、length、PID 封装为事件，经 **UPC（Userspace Procedure Call）**——per-core xarray 队列 + epoll，非阻塞入队——通知 userspace。命中则直接走底层 FS，不改 VFS 并发模型。
- **CPRT**：VFS 风格 API（`ppc_init/exit/prefetch/evict`），策略编译为动态库经 `reg_policy` 注册，支持 `rm_policy` 热切换。策略返回 prefetch/evict **建议列表**（path、offset、size、target XPU ID），由 **cache manager** 实际执行：evict 用 `fadvise(DONTNEED)` 且阈值低于 kernel 原生；loader 维护 core-bound 线程池 + ioctl 直调底层 page load，支持 **interruptible** 与 **XPU affinity**（数据落到目标 XPU 的 NUMA 节点）。
- **部署**：`mount -ppc` 把 `ppc_path` 关联 `base_path`；无注册策略时回退 kernel 默认行为。同一 namespace 一时一策略，多策略需分子目录。

### MAIO：I/O 模板驱动的 cache policy

MAIO 是 PPC 上针对 model loading 的策略，核心是把「黑盒 inference 进程的文件读序」变成可预测的 **I/O template**：

1. **Template 生成/解析**：`ppc_init` 检查 service ID 对应 template；不存在则首轮 loading 在 `ppc_prefetch` 中记录每个 XPU worker 的 (path, offset, size) 序列并返回 NULL（只观测不预取）。Template 按 worker ID 分组，可存本地或 NFS 共享。
2. **Interruptible Prefetching**：cache miss 时按 template 从当前位置激进 prefetch 至 I/O group 末尾，充分占满空闲 SSD 带宽；前端真实 I/O 更快时，新 `ppc_prefetch` 触发 loader **中断**旧 prefetch，避免冗余加载与带宽争抢。
3. **XPU Affinity Loading**：template 中 worker ID 与 XPU 一一对应；prefetch 指定 target XPU，loader 把页放进对应 NUMA，加速后续 host→device 传输。
4. **Burn-after-Reading (BAR) Eviction**：model loading 按 template 顺序前进，miss 点之前的数据大概率已拷入 XPU 且不会再读 host cache；`ppc_evict` 在 miss 位置与 eviction cursor 之间驱逐，默认保留 **1 GB** 安全距离防 thrashing。

相对预测型 kernel LRU/LFU、经验型全路径预取、以及框架内嵌的 [[ServerlessLLM]] 类方案，MAIO 的优势在于：(1) template 精确感知时序 + affinity + 生命周期；(2) 可在 **framework init 首次 touch 文件系统** 时就开始 prefetch，overlap 容器启动与结构解析——SLLM-NPU 仅在 loading 阶段介入；(3) memory-constrained 下 BAR + interruptible 避免 EagerLoad/PreCache 的 cache thrashing。

## 设计取舍

- 取舍 1：兼容性 vs 峰值性能。放弃 NVLink 多播、框架内 pipeline load 等「不兼容捷径」，换三面通用；大模型场景仍可比 SLLM-NPU 快 17%，主因是更早 overlap 非 loading 阶段 I/O。
- **取舍 2：非侵入 stacked FS vs 策略延迟**。UPC 异步事件 + 建议式 cache manager 把策略 bug 限制在 userspace 进程；但 cache miss 路径多一跳，empty policy 仍有 3.7–6.4% 开销。
- **取舍 3：I/O template 精确性 vs 运维成本**。配置变更（TP、PD disaggregation、模型版本）需重生 template 并 `reg_policy`；MaaS 控制面可集成到 template 预构建流程，但 ad-hoc 单机部署需一次「观测 run」。
- **取舍 4：激进 prefetch + interruptible vs 编程简单**。假设策略不知系统状态，可能过量发 I/O，依赖 loader 在内存/带宽/线程池压力下中断——换编程模型简单与带宽利用率。
- **边界条件**：当前 RFS **只读**；单节点多 inference service 需 cgroup QoS（裸金属多实例并列 QoS 标为 future work）；BAR 1 GB 距离为经验值；底层 FS 为 EXT4/XFS 类本地 SSD，Ascend NPU + Kunpeng 平台验证为主。

## 实验与结果

**环境**：4×48-core Kunpeng 920、8×Ascend 910B2、1 TB DRAM、3.75 TB SSD；vLLM-Ascend 0.9.2、Linux 5.10；4 NPU 容器部署。对比：**Native**（kernel cache）、**EagerLoad**（首次 miss 一次性 prefetch）、**PreCache**（全量驻内存）、**SLLM-NPU**（[[ServerlessLLM]] NPU 移植版，仅 memory-rich、Transformers only）。

- **Model loading 延迟**：memory-rich 下 MAIO 比 Native 最多快 **79%**，比 EagerLoad 快最多 **32%**，比 PreCache 快最多 **37%**（PreCache 占满内存仍输 NUMA affinity）；比 SLLM-NPU 最多快 **17%**。memory-constrained（cgroup 限 **64 GB**）下比其它方案最多快 **74%**，EagerLoad/PreCache 因 thrashing 几乎不优于 Native。
- **端到端 startup**：含 framework init + loading + [[KV-Cache]] init；memory-rich 比 Native 降最多 **38%**，比 PreCache/EagerLoad 最多 **6.6%**；memory-constrained 比其它方案最多 **51%**。
- **带宽利用**：MAIO/EagerLoad 在 framework init 阶段即打满 SSD 峰值，model loading 阶段几乎全 cache hit；memory-constrained 下 MAIO 不追求满带宽但延迟最短（BAR 精准驱逐）。
- **Ablation**（Qwen2.5-72B、Llama-70B）：interruptible prefetch 单独贡献 **>65%**；加 XPU affinity 再降 **>8.5%**；BAR 在 memory-rich 几乎无增益，在 constrained 下再贡献 **19–23%**。
- **PPC 开销**：empty policy 下 EXT4 memcpy-after-mmap +3.7%（XFS +6.4%）；PPC 进程常驻内存约 **30 MB**；UPC 监听 CPU **1–11%**（随并发）。
- **工业部署**（Intelligence BooM，DeepSeek-R1-671B，2 节点 16 NPU）：loading **649 s → 452 s**，快于全 DRAM 缓存的 **561 s**（I/O 几乎被隐藏，剩余成本主要在 MindSpore tensor 格式化）。
- **弹性 MaaS workload**（ShareGPT，startup→推理→销毁循环）：比 Native 吞吐 +**13%**（memory-rich）/ +**28%**（64 GB 约束）；比 PreCache/EagerLoad 在 constrained 场景平均 +**19%** / +**21%**；interval 越长 loading 占比越小，增益递减。

## Critical Analysis

### 论证链条

测量（SSD 17% 利用 + NUMA 20% 增益 + constrained eviction +38%）→ 根因（kernel cache 不感知 LLM loading 的带宽/affinity/生命周期）→ PPC 非侵入注入策略 → MAIO 用可复现 I/O template 驱动三项机制 → loading/startup/弹性吞吐全面改善。链条在 **本地 SSD + MaaS template 化部署 + Ascend/Kunpeng** 设定下较闭合；ablation 逐步启用 P/A/E 支持设计分解。

薄弱跳步：(1) **36%** 弹性吞吐提升仅在 abstract/introduction 出现，§5.3 详细数字为 13%/28% vs Native——读者需对照 Figure 12 确认「other tested solutions」具体指谁；(2) SLLM-NPU 为作者适配且有 bug、仅 Transformers，与 MAIO 的 vLLM-Ascend 主路径不完全对等；(3) 「快于 PreCache/全 DRAM」部分场景依赖 XPU affinity 与 I/O overlap，而非 page cache 本身_magic_。

### 假设压力测试

- **非 template 化部署**：手工 `python` 起服务、频繁改并行度或权重布局，首轮需 template 生成且 MAIO 退化为观测模式——论文承认依赖 service specification，对 research/开发机不如对 MaaS 控制面友好。
- **框架演进**：[[vLLM]]/MindSpore 升级若改变 mmap/read 顺序或引入 weight streaming，历史 template 失效；论文建议控制面感知变更并重生，但 MAIO 本身无自动失效检测。
- **多租户同节点**：多 MAIO 实例争抢 SSD/CPU，容器 cgroup 可缓解，裸金属并列仅 future work——高混部密度下 interruptible prefetch 可能互相打断。
- **超高速存储**：若模型放 CXL/池化 DRAM/NVMe-oF，17% 带宽闲置观察弱化，MAIO 相对 EagerLoad 的边际收益可能缩小——论文未测此类硬件。
- **写路径与 checkpoint**：RFS 只读，不覆盖 fine-tune checkpoint 写回、LoRA 热更新等需写 cache 一致性的场景。

### 实验可信度

- **Benchmark 代表性**：5 个主流开源模型 + 华为 MaaS 弹性 trace + 工业 DeepSeek-R1-671B 案例，对「SSD 本地热模型 + 弹性扩缩」代表性强；OBS 冷拉取首启路径未作为主实验（生产痛点之一）。
- **Baseline 公平性**：Native/EagerLoad/PreCache 均走 PPC 或同等 mount 路径，兼容类对比较公平；SLLM-NPU 受限且非完整 vLLM 栈，「beat incompatible SOTA」结论应谨慎外推。
- **Ablation**：P/A/E 递增启用清晰；缺少 BAR 距离、prefetch 粒度、template 有误时的鲁棒性扫描。
- **Metrics**：覆盖 loading、端到端 startup、带宽曲线、吞吐、PPC 开销；**未系统测** tail latency 分布、多模型并发切换、template 错误/损坏时的降级行为、安全隔离（userspace 策略恶意 prefetch 的 DoS）。

### 系统性缺陷

- **首轮冷启动 tax**：新 service ID 第一次运行只记录 template 不加速，生产新模型上线仍有慢路径——论文未量化 template 生成 run 的频率与 SLA 影响。
- **BAR 1 GB 经验参数**：论文承认防 thrashing 靠经验；更大模型、更紧 memory 或不同 FS block size 下最优距离未知。
- **可观测性**：未描述如何监控 UPC 队列深度、prefetch 中断率、template 命中率；运维排障需自建指标。
- **故障恢复**：userspace CPRT 崩溃时 RFS 行为（stall vs 回退 kernel policy）论文只说策略 bug 不影响 kernel，未测 daemon 重启期间的 miss 路径延迟。
- **分布式 loading**：多节点 TP 的跨节点 I/O 协调、NFS 上 template 一致性与 stale template 风险仅浅讨论。

## 局限与 Future Work

- **局限 1**：强依赖 inference service 规格稳定；TP/PD/模型版本变化需 MaaS 控制面触发 template 重生——ad-hoc 环境运维负担更高。
- **局限 2**：RFS 仅只读；写密集或 read-after-write 一致性场景未覆盖。
- **局限 3**：裸金属多 service 资源争用靠 cgroup 隔离仍不成熟；论文明确标为 future work。
- **局限 4**：BAR 安全距离、template PID→XPU 映射在框架定制 worker 模型下可能脆弱；SLLM-NPU 对比条件不对等限制「兼容 vs 不兼容」结论外推。
- **Future work 1**：在 bare-metal 多 MAIO 实例下测量 SSD/CPU 争用，设计跨 cgroup 的 prefetch 预算与中断协同。
- **Future work 2**：扩展 RFS 写路径，评估对 checkpoint / adapter 热加载是否仍能保持非侵入与低开销。
- **Future work 3**：对 OBS/网络存储首启路径做端到端测量，明确 MAIO 在「模型不在本地 SSD」时的收益上界；与 [[BlitzScale]]/[[ServerlessLLM]] 在混合存储层次做正交组合而非二选一。

## 相关

- **相关概念**：[[KV-Cache]]、[[Tensor-Parallelism]]、[[Disaggregation]]、[[NUMA]]、[[RDMA]]、[[PagedAttention]]、page cache、stacked file system
- **同类系统**：[[vLLM]]、[[SGLang]]、[[ServerlessLLM]]、[[BlitzScale]]、[[DeepServe]]、PageFlex、FetchBPF、RFUSE、XFUSE
- **同会议**：[[FAST-2026]]
- **对比**：MAIO 走 kernel page cache 策略替换换三面兼容；相对 [[ServerlessLLM]]/[[BlitzScale]] 牺牲硬件/框架深度耦合换通用部署；相对 EagerLoad/PreCache 用 template 精确 prefetch+eviction 解决 constrained memory thrashing
