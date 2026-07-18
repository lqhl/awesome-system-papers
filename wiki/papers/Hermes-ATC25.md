---
type: paper
name: Hermes
full_title: "Accelerating Model Training on Ascend Chips: An Industrial System for Profiling, Analysis and Optimization"
authors: [Yuhang Zhou, Zibo Wang, Zhibin Wang, Ruyi Zhang, Chen Tian, et al.]
venue: ATC
year: 2025
tags: [training-profiling, bottleneck-analysis, npu, ascend, distributed-training]
source_pdf: "[[atc2025-zhou.pdf]]"
source_md: "[[atc2025-zhou]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Accelerating Model Training on Ascend Chips: An Industrial System for Profiling, Analysis and Optimization (ATC 2025)

> **一句话总结**：基于 3 年 135 个华为 Ascend NPU 生产优化案例，Hermes 把「CPU 调度占 37%、算子 underutilization 占主导、compute/comm 抢 HBM 带宽」等经验编码成 coarse-to-fine profiling + 分层瓶颈分析 + cause-optimization 匹配；在 100B PanGu-α、MobileNetV1-SSD、9000+ NPU MoE 上分别报告 3.05×、1.91×、1.19× 加速，且 lightweight profiling 把 8B Llama-3 单步开销从 1.77× 压到几乎零。

## 问题与动机

大规模 DL 训练的成本不只是算力，更是 profiling-analysis-optimization 这条运维链路的效率。论文区分三类角色：developer 要定位瓶颈并写优化；deployer 要在模型/硬件演进后重新选优化；maintainer 要在数月训练中捕捉瞬态性能波动。三者共同需要轻量但足够细的 [[Profiling]]、跨 host/device/network 的整体瓶颈分析，以及能把根因映射到可行优化的 advisor。

现有方案在这三点上都偏窄。PyTorch Profiler 等 detailed profiling 对 8B Llama-3 8-NPU 单步从 85.19s 拉到 150.58s（1.77×），连续监测不可接受。PRESTO 只看 I/O，R-Pingmesh/Meta 工作只看 RDMA，Syndicate 主要看 compute-comm overlap，都缺少 host 侧 CPU 调度与跨瓶颈依赖。DayDream、dPRO 又把优化建议限制在 [[Data-Parallelism]] 场景。更麻烦的是 Ascend NPU 有 AICore/AICPU/HCCS 等 GPU 没有的架构差异，需要专用 profiling 接口和 holistic analysis，而不能照搬 Nsight 的孤立瓶颈视角。

作者的 claim 边界是工业经验系统：Hermes 面向 Ascend 生产集群，价值在于把 223 次异常处理、135 个典型案例沉淀成可复用 workflow，而不是在开放 benchmark 上证明某个单点算法支配所有训练栈。论文也承认 mstt advisor 对 Ascend 特有瓶颈（AICPU、private format、HCCS byte alignment）的规则不能直接外推到 NVIDIA GPU。

## 关键观察 / 隐含假设

- **观察 1：生产训练瓶颈高度偏 host/CPU，但工具链长期忽视。** 135 个案例中 host bottleneck 占 45.9%，其中 CPU 占 37.0%；典型根因包括 dynamic shape 触发 JIT 重编译、过多小算子 dispatch、Python GC、Prometheus 等外部进程争抢 CPU（GPT-3 案例里误部署 Prometheus 占 4000% CPU）。
  - **依赖假设**：训练仍走 PyTorch/MindSpore + CANN 的经典 host-device 异步模型，CPU 编译/dispatch/数据预处理与 NPU 执行之间存在可被 timeline 分离的同步点。
  - **可能失效场景**：全图编译、CUDA Graph/NPU 等价物、或 host 侧极薄 wrapper 的栈里，CPU 占比会下降，Hermes 的 CPU 规则权重需要重标定。

- **观察 2：computation bottleneck 的绝对多数不是 compute-bound，而是 underutilization。** 100B PanGu-α 中 61.48% 算子 underutilized，ResNet50 高达 97.8%；小模型 underutilization 比例更高。Ascend 上常见原因是 AICPU fallback、Cube 对齐不佳、private format 频繁 TransData/Cast。
  - **依赖假设**：[[Roofline-Model]] 阈值和 AICore/AICPU 亲和规则在目标模型上稳定；operator fusion、format 切换、替换高性能算子能带来可观 MFU 提升。
  - **可能失效场景**：算子已高度融合、或瓶颈转移到 memory-bound/compute-bound 时，underutilization 规则收益会快速饱和；GPU 上 AICPU/private format 问题不存在，需换检测逻辑。

- **观察 3：compute 与 communication 的 overlap 并不总有益，HBM 带宽争抢可让性能掉 20–40%。** 论文在 tensor parallelism 细粒度 chunk overlap 中观察到 MatMul 等 memory-bound 算子与 HCCS DMA 并发时争抢 HBM；因此需要重调度或 HBM 访问优先级，而不是盲目追求 overlap。
  - **依赖假设**：intra-node 通信与计算共享 HBM/PCIe/HCCS 带宽，且争用可被 timeline 上的并发度检测到。
  - **可能失效场景**：NVLink 带宽充裕、或通信走独立 NIC/RDMA 不占 device HBM 的拓扑里，这条经验的外推需谨慎；过度重调度也可能伤害原本有效的 overlap。

- **观察 4：性能波动只需少量 coarse metrics 就能定位异常 step/device，再触发 fine-grained profiling。** lightweight monitor 只采 step time、throughput、MFU、带宽；同学域设备 step time 不一致即标出问题卡。8B Llama-3 上 monitor 单步 85.20s，几乎等于无 profiling 的 85.19s。
  - **依赖假设**：波动表现为 step time/MFU 的可检测异常，且慢卡能在 communication domain 内被横向比较；dynamic profiling 通过共享内存改配置可不中断训练。
  - **可能失效场景**：全体同步等待导致的「齐慢」、或 expert parallelism/context parallelism 下 domain 划分复杂时，单卡 outlier 检测可能失效；万卡集群上 parsing 虽做了异步与 75% 内存压缩，TB 级 trace 仍可能拖慢诊断闭环。

- **隐含假设：135 个案例总结的 cause-optimization 映射足以覆盖未来大部分生产瓶颈。**
  - **证据强度**：中。Table 4 覆盖了 parallel/I/O/CPU/computation/communication 全类，并有 ResNet50、VGG16、PanGu、MoE 等案例支撑；但映射是 rule-based、手工维护，论文自己也说 RLHF、multimodal、复杂 MoE AlltoAll 失衡仍难诊断。

## 核心方法

Hermes workflow 分三步，用户可按角色裁剪：developer 可只做 profiling + analysis；maintainer 依赖 continuous monitor；优化是迭代式的，消掉当前瓶颈后再跑下一轮。

**Coarse-to-fine Profiling** 回应观察 4。lightweight monitor 在线采集少量指标，用历史 step 对比找异常，再在 communication domain 内找最慢 device。确认问题后，fine-grained profiler 对问题 step/device 采 operator 级 host/computation/communication 指标和跨组件 timeline。dynamic profiling 把配置放在共享内存，专用线程监听变更，step 边界读取并执行，避免像 `torch.profiler.schedule` 那样中断训练重载 checkpoint。解析侧标准化 DB 格式、多机 idle CPU 并行解析、训练期异步解析，MindStudio Insight 声称 10GB+ 数据集 <30s 可视化。相对 always-on detailed profiling，7B Bloom 端到端训练从 1300s 降到 1000s（−23%），230B PanGu 128 卡从 120min 到 102min（−15%），内存仅 +5–9%、CPU +4%。

**Hierarchical Bottleneck Analysis** 回应观察 1–3 和训练流水线的层级结构（Figure 2：host 数据准备、device AICore/AICPU 计算、network HCCS/RDMA 通信）。先做 inter-operator：multi-component parallel analysis 量化 host/compute/comm overlap 与非重叠段，overlap 过低则判 parallel bottleneck；[[Critical-Path]] 分析从 timeline 反推跨组件最长依赖链，把待分析算子数减半以上。再做 intra-operator：queue-based I/O 用 device/host/data 三级队列区分 reading/processing/fetching；CPU 分编译、dispatch、GC、外部争抢、环境配置五类；computation 用 roofline 分 compute-bound/memory-bound/underutilization；communication 把 AllReduce 拆成 synchronization waste（$R_{wait}=1-T_{avg}/T_{max}$）和 transmission 问题（bandwidth contention、RDMA 重传、小包、HCCS 512B 对齐、交换机/HCCL 配置）。

**Bottleneck Cause-Optimization Match（mstt advisor）** 把 135 案例编码成 Table 4 规则，输入 profiling 数据自动出 HTML 报告。例如检测到 AICPU 算子超时，建议改 dtype 到 AICore 支持格式或替换等价算子；检测到小包 AllReduce，建议 adaptive gradient fusion——论文还实现了基于 profiling 的 forward search，在带宽收益与 tail latency 间 greedy 分段，避免 PyTorch 固定 BucketSize 过小无效、过大长尾的问题。作者明确：advisor 主要覆盖 hardware-agnostic 的 parallel/CPU/大部分 communication 瓶颈；AICPU、private format、HCCS alignment 等 Ascend 特有项不可直接迁移。

## 设计取舍

- **轻量 monitor + 按需 fine-grained，换可接受的诊断盲区**：continuous profiling 几乎零开销，但只在检测到异常 step/device 时才采 operator 级数据；短暂、全体一致的退化可能被漏掉。
- **规则表 advisor 换可解释性与落地速度**：相对 DayDream/dPRO 的依赖图预测或未来的 LLM agent，Hermes 选择 3 年案例沉淀的 explicit rules，易给运维出 checklist，但新训练技术出现时需要人工更新 Table 4。
- **分层分析换实现复杂度**：inter- + intra-operator 两层覆盖 host/device/network，比 PRESTO/SketchDLC 等单类工具全面，也比纯人工看 timeline 省时间；代价是大量 Ascend 特有检测逻辑与 mstt 工具链绑定。
- **dynamic profiling 无侵入换框架耦合度**：共享内存改配置避免停训，但仍依赖 CANN/Ascend metrics 接口和训练框架 hook；换到纯 GPU 栈需要重做采集层。
- **边界条件**：在瓶颈已明确且单一（如纯 I/O num_workers=1）时 Hermes 很高效；当 MoE AlltoAll 严重不均衡、或外部环境的罕见 CPU 干扰时，论文承认仍需人工介入。

## 实验与结果

- **Profiling 开销**：8B Llama-3 8-NPU 单步 85.19s（无）/ 150.58s（detailed）/ 85.20s（lightweight monitor）；7B Bloom 8 卡端到端 1300s→1000s，230B PanGu 128 卡 120min→102min。
- **经典瓶颈案例**：ResNet50 单卡 I/O，`num_workers` 1→12 后 data prep 72.8ms→0.25ms，step 90ms→18.07ms（5.34×）；VGG16 8 卡 adaptive gradient fusion 后 non-overlap AllReduce 21.76ms→3.59ms，step 76.5ms→56.6ms（1.35×）；GPT-3 停掉误部署 Prometheus 后 step 444.4ms→374.9ms，>10% 波动 step 从 128/4989 降到 4/4989。
- **100B PanGu-α 128 卡迭代优化**：baseline 2856h、4839 tokens/s；三轮分别打 computation（operator opt 2.05× 总时长）、parallel（auto hybrid PP + multi-shard 1.41×）、communication（adaptive gradient fusion 1.05×），最终 936h、约 3.05×。单步从 98.01s→26.43s。
- **MobileNetV1-SSD 部署**：A800→Ascend 直接迁移仅 43% 性能；经 disable JIT、消除 `tensor.item()` sync、替换 affinity API、解除 taskset CPU 绑定后，8 卡训练 11.10ms→5.81ms（1.91×），FPS 达 GPU 约 90%。
- **9000+ NPU MoE 波动**：GC 阈值调优 + 周期性 `gc.collect()` 后 400 step 平均吞吐 53.33→56.23 TFLOPs/s（1.05×）；18000 卡集群修链路、隔离 30 节点、日志写本地后平均吞吐 85→101 TFLOPs/s（1.19×），方差 291→31。
- **Table 6 部署汇总**：vision/NLP/recommend 多模型总加速 1.08–5.34×；通信优化对非瓶颈模型（如 ResNet50 step）改进有限，符合「先判定瓶颈类型再优化」的逻辑。

## Critical Analysis

### 论证链条

主链条清晰：生产训练需要轻量连续监测 → coarse-to-fine profiling；瓶颈跨 host/device/network 且互相关联 → hierarchical analysis；运维不能靠个人经验选优化 → 135 案例驱动的 advisor。PanGu-α 三轮迭代把链条闭环到 3.05×，MoE/GPT-3 案例也说明同一框架能处理波动与部署问题。

薄弱处在于组件贡献未充分隔离。PanGu 的 3.05× 是 operator opt、auto hybrid parallelism、multi-shard、gradient fusion 的串联结果，没有 ablation 证明 Hermes 的「分析」本身相对资深工程师手工看 timeline 节省多少 wall-clock。VGG16 gradient fusion 算法是论文新增贡献，但与 Hermes advisor 的耦合程度也未单独量化。mstt advisor 更像经验引擎，论文对 false positive/false negative 没有统计。

### 假设压力测试

最脆的是 **案例分布向 Ascend 生产倾斜**。135 个案例来自华为客户群，CPU 37%、underutilization 主导、port flapping 常见——换到 GPU 云或不同存储/监控栈，Table 4 比例可能完全不同。论文声称 hardware-agnostic 优化可扩展，但最强规则（AICPU、private format、HCCS alignment）恰恰不可扩展。

第二个压力来自 **workload 演进**。RLHF 的 reward/policy 迭代、multimodal 的 cross-modal alignment、MoE expert parallelism 的 AlltoAll 失衡，论文在 §6 坦承现有 synchronization analysis 不够，慢卡 vs 慢网难区分。随着 EP/CP 普及，communication domain 内的「同域同耗时」假设会更脆。

第三个压力是 **规则表时效性**。新模型结构、新 CANN 版本、新并行策略会持续引入新瓶颈；rule-based advisor 需要持续喂案例，否则会把运维引向过时建议。论文计划用训练日志和 LLM agent 辅助，但当前系统仍是静态映射。

### 实验可信度

可信之处在于数据来自真实生产，覆盖 profiling 开销、单点经典瓶颈、端到端大模型迭代、万卡波动治理，且数字具体（step 时间、吞吐、方差、案例数）。Profiling 对比直接量化了 lightweight vs detailed 的差异，对 maintainer 场景很有说服力。

不足是可复现性与 baseline 公平性。实验依赖 Ascend 集群拓扑（Appendix A：HCCS 30GB/s、PCIe 4.0 32GB/s、RoCE 100G）、MindSpore/PyTorch 生产配置和 mstt 私有工具，外部读者无法独立验证。与 Nsight Systems、PyTorch Profiler + 人工专家、或 DayDream/dPRO 的端到端时间对比缺失；PanGu 加速也未与同类 Ascend 优化服务对比。

### 系统性缺陷

**尾延迟与隔离**：论文关注 step time 均值和波动次数，但未系统报告优化后 P99 step time、跨租户干扰、或错误建议导致性能回退的风险。

**可观测性与运维成本**：dynamic profiling、异步 parsing、MindStudio Insight 组成较重工具链；论文未量化 advisor 误报时的排查成本，也未讨论万卡集群上 monitor 自身的 fan-out 与存储成本。

**正确性**：优化建议聚焦性能，对数值精度（mixed precision、算子替换）、收敛性（改 parallel 配置、disable GC）影响几乎未讨论。

**故障恢复**：网络 link failure、port flapping 被当作瓶颈根因，但修复动作（换光模块、隔离节点）是人工运维，Hermes 自动化边界在检测与建议，不在闭环修复。

## 局限与 Future Work

- **局限 1：RLHF、multimodal 等新训练范式覆盖不足。** 论文承认 reward modeling、policy optimization、image-text fusion 等瓶颈尚无有效规则。Future work：为 multi-model、multi-phase training 增加 phase-aware profiling 与独立 critical path。
- **局限 2：复杂 MoE / EP / CP 场景诊断不够。** AlltoAll 失衡时慢卡与慢通信难区分。Future work：结合 expert load trace 与 per-link telemetry，做 imbalance-aware synchronization model。
- **局限 3：规则表需持续维护，静态映射会过时。** Future work：用训练日志 + LLM agent 辅助根因推理，并报告 rule drift 检测与人工 override 率。
- **局限 4：GPU 外推性未验证。** hardware-agnostic 优化虽在 Table 4 中标出，但缺少同 workload 在 NVIDIA 集群上的对照实验。Future work：对 CPU/I/O/gradient fusion 等规则做 cross-hardware replay。
- **局限 5：优化对收敛与精度的影响未评估。** disable GC、改 parallel、替换算子可能改变训练动态。Future work：把 loss/收敛曲线纳入 advisor 约束，而不只看 step time/MFU。

## 相关

- **相关概念**：[[Profiling]]、[[Critical-Path]]、[[Roofline-Model]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Data-Parallelism]]、[[MoE]]、[[Expert-Parallelism]]、[[RDMA]]、[[Mixed-Precision-Training]]
- **同类系统**：[[DeepServe-ATC25]]（同 Ascend 生态的生产系统）、DayDream、dPRO、PRESTO、R-Pingmesh、Syndicate、Nsight Systems
- **同会议**：[[ATC-2025]]
- **对比**：Hermes 解决 training profiling/analysis；[[DeepServe-ATC25]] 解决 serving runtime——二者都强调 Ascend 生产经验，但生命周期与瓶颈类型不同
