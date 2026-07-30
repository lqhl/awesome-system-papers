---
type: paper
name: Torpor
full_title: "Torpor: GPU-Enabled Serverless Computing for Low-Latency, Resource-Efficient Inference"
authors: [Minchen Yu, Ao Wang, Dong Chen, Haoxuan Yu, Xiaonan Luo, et al.]
venue: ATC
year: 2025
tags: [serverless, gpu-pooling, model-swapping, late-binding, ml-inference, slo-aware-scheduling]
source_pdf: "[[atc2025-yu.pdf]]"
source_md: "[[atc2025-yu]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Torpor：支持 GPU 的无服务器计算，用于低延迟、资源高效的推理（ATC 2025）

> **原题**：Torpor: GPU-Enabled Serverless Computing for Low-Latency, Resource-Efficient Inference

> **一句话总结**：基于 Alibaba Cloud 生产 trace 的观察——85% 推理函数平均 ≤1 次/分钟、早绑定 GPU 导致严重 idle 与负载失衡——Torpor 用 host memory 驻留 + late binding + 按需 model swap（异步 CUDA remoting、NVLink/PCIe 流水化传输、interference-aware 调度）在 4×V100 节点上同时服务 480 个函数并满足 ms 级 SLO，试点部署报告用户 GPU 成本降 70%、平台降 65%。

## 问题与动机

[[Serverless]] 推理的理想形态是用户只发布模型与推理代码，平台负责扩缩容、调度和故障恢复，并按实际用量计费。但 AWS Lambda、Alibaba Function Compute 等现有 GPU [[FaaS]] 仍沿用 serverful 推理的 **early binding**：容器启动时就把模型绑到指定 GPU 上长期驻留，idle 期间用户仍要为占用的 GPU 付费。

作者在 Alibaba Cloud 一周生产 trace 中测到：85% 函数平均调用频率 ≤1 次/分钟，97% ≤1 次/秒；请求到达呈 burst（Figure 1）。在这种 workload 下，early binding 带来三重代价：用户为 idle GPU 买单；多函数打包进单卡仍可能因 burst 造成 hotspot 与 cross-GPU 负载失衡（Figure 2）；若改为频繁回收 GPU 则触发 cold start——ResNet-152 到 Llama2-13B 的容器冷启动需 8–61 s（Table 1），远超 CV/BERT 常见的 80–200 ms SLO。

论文把目标收敛为四个可检验属性：**pay-per-GPU-use**、**GPU efficient**、**SLO compliant**、**model-agnostic**（不窥探模型结构以保护 IP）。Table 2 对比显示 Alibaba Cloud、Molecule、DGSF、INFless 等都无法同时满足。Torpor 的 claim 边界是：在不侵入现有 serverless 控制面的前提下，用 **late binding**——模型 idle 时放 host memory，请求到达再 swap 到 GPU pool——同时逼近 native execution 延迟并显著降低 GPU 供给成本。

## 关键观察 / 隐含假设

- **观察 1：serverless 推理函数绝大多数极低频，GPU 早绑定必然浪费。** 一周 Alibaba trace 显示 85%/97% 函数分别 ≤1 r/m、≤1 r/s；Figure 2 还表明即使把多模型塞满 V100 32 GB 显存，低频下 GPU load 仍低，burst 时又会过载。
  - **依赖假设**：企业客户会把大量长尾、低频推理迁到 serverless，而不是全部走常驻 SageMaker 式服务。
  - **可能失效场景**：若平台主要承载高频 chat/推荐 serving，late binding 的 swap 开销会压过 consolidation 收益；多租户 burst 同步时 host memory 与 PCIe 带宽可能成为新瓶颈。

- **观察 2：推理执行的 CUDA 调用大多异步，同步式 GPU remoting 的通信开销可被大幅削减。** 中间 kernel 在 GPU 上异步执行，host 只需在最终输出同步；Torpor 把 API 分为 blocking（如 `cudaMalloc`）与 non-blocking（如 `cudaLaunchKernel`），并对连续 API 批处理。
  - **依赖假设**：目标 workload 以标准 DL 框架 forward 为主，API 序列稳定；GPU server 与函数容器间网络/IPC 延迟足够低。
  - **可能失效场景**：频繁 host↔device 同步的算子、动态 shape、或 [[CUDA-Graph]] 式整图提交可能削弱异步重定向收益；论文未评估这类 workload。

- **观察 3：model swap 的 PCIe 带宽争用具有模型相关的非线性，且同一模型跨请求的内存访问模式稳定。** Table 3 显示并发 PCIe swap 时 Bert-qa 延迟可从 149 ms 涨到 240 ms（+61%），而 DenseNet-169 几乎不变；因此可按 swap 带宽需求把模型分为 heavy/light，并优先 NVLink GPU-to-GPU 迁移。
  - **依赖假设**：worker 拓扑存在成对 NVLink（Figure 5：4×V100 通过 PCIe switch 与多级 NVLink 互连）；模型参数地址模式在 cold start 后保持不变，可把首次执行当作 profiling。
  - **可能失效场景**：无 NVLink 或拓扑更稀疏的 GPU 代际上，scheduling 优势会缩水；LLM 长上下文下 [[KV-Cache]] 作为 runtime state 纳入 swap 后，heavy/light 分类与地址稳定性需重新验证。

- **观察 4：host memory 容量远大于 GPU memory，足以承载数百个 idle 函数副本。** 节点配置为 384 GB DRAM vs 4×32 GB VRAM；eviction 时只 invalidate GPU 侧、保留 host 副本，避免 GPU→host 卸载开销。
  - **依赖假设**：函数权重 + runtime metadata 总和不超过 host memory；极低频函数仍值得保留在 DRAM 而非更冷存储。
  - **可能失效场景**：论文自己在 production discussion 指出极低频函数仍因 host memory 产生可观费用；超大模型或 model-parallel 跨卡场景当前不支持。

- **隐含假设：单 GPU 上同一时刻只跑一个函数、通过 GPU server 统一拦截 CUDA 即可满足隔离与 SLO 需求。**
  - **证据强度**：中。生产 pilot 默认 runtime isolation（Table 1 显示 runtime 恢复 0.19–1.9 s）；论文声称 container 级 CPU/memory 隔离与 GPU memory region 隔离，但未给出多租户安全审计或侧信道实验。

## 核心方法

Torpor 由 cluster manager 与 worker node 组成。cluster manager 负责路由、节点分配与扩缩；worker 内包含 GPU server（池化本地 GPU）、intra-node router、以容器部署的 inference function。请求路径：cluster → worker router → 查询 GPU server 选定 executor → function 通过 GPU client 把 CUDA 调用重定向到该 executor（Figure 3）。

**Late binding 与 model swap。** idle 模型放在 host memory 的 model repository；请求到达后按需 swap 到可用 GPU。swap 支持 host→GPU（PCIe）、GPU→GPU（NVLink），并对参数分组做 pipeline execution，使传输与 forward 重叠。group size 不依赖模型结构，而是用硬件传输吞吐的 elbow point（测试床约 2 MB）离线标定。LLM 的 runtime state（如 [[KV-Cache]]）被当作模型一部分管理，使设计保持 model-agnostic。

**异步 CUDA API remoting。** 相对 GVirtuS 等同步 remoting，Torpor 让大多数 inference API 异步下发，仅保留必要同步点。ResNet-152 延迟比 GVirtuS 低 88%，比禁用 batching 的变体再低 41%；部分 CV 模型甚至快于 Native，因为 cuDNN descriptor 等 CPU 侧 API 被分流到函数与 GPU server 两侧。

**GPU memory 管理。** 多 GPU 共享逻辑地址空间：按 PyTorch block 级跟踪地址映射，swap 后做 block→physical address 翻译；启动时预留全部 GPU memory，用扩展 Buddy allocator 合并同模型 block、共享同尺寸 block，避免 `cudaMalloc` 碎片与高频分配开销（Figure 13：Torpor-Block 分配延迟可达推理时间 4× 以上）。

**隔离与容错。** 提供 runtime sharing（单 runtime 多模型）与 runtime isolation（每模型独立 runtime）两档；pilot 用后者。executor/GPU 故障时通过 swap 迁移模型并重启；GPU server 把 runtime state 落盘以加速恢复。

**SLO-aware 策略三件套。**
1. **Request queueing**：用 RRC（required request count）$\frac{pn-m}{1-p}$ 衡量函数距离 tail SLO（如 p=98%）还需多少成功请求，RRC 小的优先。
2. **Interference-aware scheduling**（Algorithm 1）：若目标模型已在空闲 GPU 上则直接执行；否则优先 NVLink GPU-to-GPU swap；再退到 host→GPU，并避开邻居正在 swap heavy model 的 GPU。
3. **Model eviction**：全局 GPU memory pool，每模型最多一个 GPU replica；优先 evict light model，剩 heavy 才 LRU。

实现上 GPU server/client 约 5.5k 行 C++，替换 `libcudart.so` 即可 hook PyTorch，无需改框架；已集成进 Alibaba Cloud Function Compute。

## 设计取舍

- **Late binding 换 swap 复杂度**：获得 pay-per-use 与高密度 multiplexing，但引入 remoting、地址翻译、scheduling 与 PCIe/NVLink 争用管理；latency 不再稳定，必须靠策略补偿。
- **Model-agnostic 换优化上限**：不依赖 PipeSwitch/DeepPlan 式模型结构 profiling，elbow-point grouping 与 block-level tracking 通用但可能对特定模型非最优；无法做 operator-level 精细切换。
- **单 GPU 单函数执行换隔离简单性**：避免同卡 spatial sharing 的干扰分析，但牺牲算力利用率；与 StreamBox、MIG 等 spatial sharing 正交、可叠加。
- **Host 常驻副本换 eviction 速度**：避免 GPU→host 卸载，但 DRAM 占用随函数数线性增长；对极长尾函数成本仍显著（论文承认）。
- **Runtime sharing 默认、isolation 用于生产**：sharing 更高效，pilot 为信任边界选择 isolation，额外增加数百 ms–1.5 s runtime 恢复，仍比 cold start 少一个数量级。

## 实验与结果

- **Microbenchmark（8 模型，V100）**：GPU remoting 与 Native 同量级或更快（Table 4）；PCIe swap 对 Bert-qa 等 heavy model 明显变慢（144 ms vs 43 ms remoting-only），NVLink swap 可拉回 45 ms。Pinned memory、pipeline、parameter grouping 分别带来约 35%、15%、22% 额外收益（Figure 7）。
- **单 GPU 低频 multiplexing**：多 ResNet-152 函数、10 r/m 时 Torpor 吞吐超 Native 10×，p99 延迟仍 <50 ms（Figure 8）。
- **4-GPU 负载均衡**：40 个高频 ResNet-152（~200 r/m）下，Native 出现秒级 tail latency，Torpor 各 GPU p99 ~35 ms（Figure 9）。
- **单节点 SLO（生产 trace 采样，5–30 r/m）**：160 函数时 Torpor 160/160 SLO-compliant；Native 仅 72 可执行；INFless-KA 可跑 112 但仅 7 个满足 SLO（Figure 10）。完整 Torpor 在 560 函数时仍 >80% compliant，FIFO/random/LRU/Block 基线显著更差（Figure 11）。
- **集群（6 workers，放宽 SLO 至 150/250 ms）**：1000+ 函数仅 Torpor 持续 SLO-compliant；Native 上限约 500；SimpleSwap/NonSwap 尾延迟可达 deadline 的 4–7×（Figure 14）。GPU load variance 也最低。
- **Pilot production（Table 5）**：>150 用户、>350 GPU、日请求最高 465k；inactive 函数仅收 10% GPU 费用；用户成本平均降 70%，平台 GPU 供给降 65%。案例函数成本降 84%，loading 约占端到端延迟 30%。

## 批判性分析

### 论证链条

观察（极低频 + 早绑定浪费）→ late binding + host memory 在逻辑上直接回应 pay-per-use 与 utilization 诉求；Table 1 的 swap-vs-cold-start 数字支撑「swap 比回收 GPU 更可行」这一关键跳步。异步 remoting 与 pipeline swap 的 microbenchmark（§7.1）较完整地把 C1（通信开销）闭合到 near-native。C3（SLO + 成本）主要靠单节点/集群的 SLO ratio 与 ablation（Torpor-FIFO/Random/LRU/Block）支撑，链条在 **scheduling + eviction + queueing 联合设计** 上较闭合。

薄弱环节在于：**生产节省 70%/65% 与实验 10×/480 函数之间的映射未被严格量化**——pilot 计费规则（idle 只收 10%）本身改变了用户行为与利用率，难以剥离 Torpor 机制本身的因果贡献。LLM 结果（Table 1：Llama/Qwen 启动 3–4.4 s）表明方法可扩展到生成模型，但 §7 主实验仍以 CV/BERT 为主，对长上下文、自回归多 step 的 SLO 论证偏少。

### 假设压力测试

- **高频 / burst serving**：Figure 9 说明 Torpor 能迁移模型平衡负载，但 highly bursty（短时极大 RPS）场景论文只提出「多节点 host 副本 + 未来 RDMA」设想，未实验验证。
- **无 NVLink 硬件**：interference-aware 调度核心依赖 NVLink 规避 PCIe；在 A100/H100 不同拓扑或纯 PCIe 机器上，heavy model 并发 swap 的退化幅度需重测（Table 3 已暗示 Bert-qa 极敏感）。
- **超大模型与 model parallelism**：Discussion 明确不支持跨 GPU/model-parallel；这与当前 LLM serving 主流（TP/PP/[[Disaggregation]]）存在张力。
- **Spatial sharing 共存**：单卡单函数策略在 GPU 昂贵时可能浪费算力；若与 MPS/MIG/StreamBox 混部，swap + remoting + 隔离语义可能冲突——论文称正交但未集成评估。
- **Model-agnostic KV 管理**：把 [[KV-Cache]] 当模型状态 swap 在短请求上可行，长 session、多轮对话下 state 体积与地址稳定性压力论文未展开。

### 实验可信度

**强项**：Alibaba 生产 trace 驱动；Native 与 INFless-KA 基线；组件级 ablation 与 GVirtuS 对比；pilot 部署有真实用户与成本数据。**弱点**：主评估模型以 ResNet/DenseNet/BERT 为主，SLO 设为 80–250 ms，与 LLM 秒级生成混淆时需谨慎外推；INFless 在集群实验中被剔除（因 Figure 10 太差），SOTA 对比覆盖面偏窄；缺乏与 [[PipeSwitch]]、Clockwork、Shepherd 等 **SLO-aware serving** 在同等 late-binding 设定下的对照；correctness、安全隔离、故障注入几乎未量化。

### 系统性缺陷

- **尾延迟与可预测性**：swap 使单次推理延迟依赖邻居行为，虽用 interference-aware 缓解，但论文未给出全局 p99.9 在极端争用下的界限。
- **Host memory 压力与计费**：极低频函数仍占 DRAM，multi-tier storage 仅为 future work；大规模函数注册时的内存碎片与 OOM 策略未讨论。
- **可观测性与运维**：5.5k 行 hook + 替换 `libcudart.so` 的部署复杂度、版本升级、与 CUDA/cuDNN 兼容性风险，论文未展开。
- **跨节点扩展**：cluster manager 只做函数级路由，模型 swap 限定节点内 GPU pool；跨节点冷模型仍需常规定位，论文未讨论全局 model cache。
- **论文未讨论**：多租户 GPU 侧信道、remoting 对调试/ profiling 工具链的影响、与 provisioned concurrency 等云产品特性的交互。

## 局限与后续工作

- **局限 1**：不支持 model-parallel / 跨节点超大模型；late binding 优势在「可单卡容纳权重」的函数上最强。
- **局限 2**：极低频函数 host memory 成本仍高；当前 uniform DRAM 保留策略对长尾不经济。
- **局限 3**：主实验 workload 以中低频 CV/NLP 为主，对 LLM 长输出、高 QPS chat 的 SLO 证据主要来自 pilot 个案与 Table 1 启动延迟，系统性 benchmark 不足。
- **Future work 1**：multi-tier storage（DRAM → 更冷介质）按请求模式自适应，需测量函数访问间隔分布与换入延迟 trade-off。
- **Future work 2**：与 model partitioning / NVLink/PCIe 协同的跨 GPU parallel execution，需重新定义 swap 单元与 scheduling 状态机。
- **Future work 3**：burst 场景下跨节点 RDMA 预复制与副本放置，应基于真实 burst trace 做 cost–latency Pareto 曲线，而非仅 host 多副本。

## 相关

- **相关概念**：[[Serverless]]、[[FaaS]]、[[GPU-Pooling]]、[[Model-Swapping]]、[[CUDA-API-Remoting]]、[[Cold-Start]]、[[NVLink]]、[[KV-Cache]]、[[Late-Binding]]
- **同类系统**：[[INFless]]、[[DGSF]]、[[Molecule]]、[[PipeSwitch]]、[[DeepServe-ATC25|DeepServe]]、[[ServerlessLLM]]、[[GVirtuS]]
- **同会议**：[[ATC-2025]]
- **对比**：early binding（Native/Alibaba GPU function）vs late binding（Torpor）；与 INFless keep-alive 在「避免 cold start」上目标相近但路径不同（swap vs 复用容器）
