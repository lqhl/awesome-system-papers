---
type: paper
name: UCP
full_title: "Universal Checkpointing: A Flexible and Efficient Distributed Checkpointing System for Large-Scale DNN Training with Reconfigurable Parallelism"
authors: [Xinyu Lian, Sam Ade Jacobs, Lev Kurilenko, Masahiro Tanaka, Stas Bekman, Olatunji Ruwase, Minjia Zhang]
venue: ATC
year: 2025
tags: [llm-training, checkpointing, parallelism, deepspeed, reconfiguration, fault-tolerance]
source_pdf: "[[atc2025-lian.pdf]]"
source_md: "[[atc2025-lian]]"
---

# Universal Checkpointing: A Flexible and Efficient Distributed Checkpointing System for Large-Scale DNN Training with Reconfigurable Parallelism (ATC 2025)

> **一句话总结**：观察到大规模 LLM 训练 checkpoint 与并行策略/硬件强耦合，故障或资源弹性时只能手写转换脚本；UCP 用 per-parameter atomic checkpoint + pattern-based 重配置流水线把 DP/TP/PP/SP/ZeRO/3D 并行解耦，1T 模型端到端重配置 < 5 分钟（转换 < 3 分钟、< 0.001% 训练时间），nested-parallel 比串行脚本快 14–257×，且 BLOOM 176B 等生产训练 loss 曲线与无重配 baseline 一致。

## 问题与动机

现代 [[DNN-Training]] / LLM 预训练动辄数周到数月：GPT-4  reportedly 在 ~25,000 A100 上训练 90–100 天；LLaMA 3.1 在 16,000 GPU 上 54 天训练遭遇 419 次故障，平均约每 3 小时一次中断。训练中断后，作业要么长时间等待原配置恢复，要么在 GPU 数量变化、集群迁移、spot instance 回收等场景下被迫换并行策略继续训练。

checkpoint 是支撑「可重配并行」的自然载体：若能把 ZeRO-style [[Data-Parallelism|DP]] 下保存的状态加载到 [[Tensor-Parallelism|TP]] + [[Pipeline-Parallelism|PP]] 的 3D 并行配置，就能在硬件故障或资源弹性时继续训练而不从头开始。但现有系统——PyTorch DCP、Megatron MCP、CheckFreq、Gemini——都把 checkpoint 文件结构与具体并行实现绑定：各 rank 只存自己分片，格式随 ZeRO stage、TP 切分轴、PP stage 分配、interleaved 1F1B 层序而变。

作者的 claim 边界是：**不改变正常训练 checkpoint 保存路径**，只在并行策略或硬件配置变化时 lazy 触发重配置；重点保证 **训练精度不损失**（optimizer state 完整保留），而非优化 checkpoint 保存本身（与 CheckFreq/Gemini 正交）。UCP 已在 [[DeepSpeed]] 开源，并用于 BLOOM 176B、Phi-3.5-MoE 42B 等真实预训练。

## 关键观察 / 隐含假设

- **观察 1**：分布式 checkpoint 与并行实现强耦合，导致重配置只能靠 ad-hoc 脚本，覆盖范围极窄。Figure 1 展示 ZeRO-3 各 rank 独立保存 P/OS 分片，与 DDP「rank 0 存全量」格式完全不同；Table 1 显示 DCP 仅支持改 DP 度，MCP 支持 PP/TP 但不含 ZeRO/SP，CheckFreq/Gemini 几乎不支持重配。
  - **依赖假设**：主流训练栈（Megatron、DeepSpeed、PyTorch）会继续产生格式各异的分片 checkpoint，而不是统一在保存时就写入 strategy-neutral 格式。
  - **可能失效场景**：若 DCP/MCP 未来原生支持全策略互转，UCP 的「通用中间格式」价值会下降；若框架改为 always-save-global-tensor，lazy 重配的必要性也会减弱。

- **观察 2**：参数在分布式 checkpoint 中的分布可归纳为有限 pattern 集合（Unique / Replicate / Partial / Shard-V / Shard-H / Shard-Hy / Shard-NC），足以覆盖 ZeRO-3、3D 并行、[[MoE]] 融合 FFN、[[GQA]] 不规则 QKV 等复杂切分。ZeRO-3 的 1D flatten+padding 对应 Shard-V；3D 并行中 LayerNorm 为 Replicate、matmul 为 Shard-V/H、interleaved PP 层分配为 Unique；MoE 融合权重与 GQA 不等长 QKV 需要 Shard-NC。
  - **依赖假设**：新模型架构与新并行策略仍可由这套 pattern 枚举 + Extract/Union/StripPad 原语表达；pattern 识别只需参数名与张量 fragment 信息，不需重跑训练图。
  - **可能失效场景**：全新 sharding 语义（如动态 expert routing 带来的运行时依赖分片、跨 rank 非确定性状态）可能超出当前 pattern set，需社区手工扩展——论文也承认新 pattern 仍需类似 ZeRO-3/MoE 级别的实现投入。

- **观察 3**：重配置开销可被「训练集群自身的多余算力与 NVLink 带宽」吸收，而不必把 TB 级 checkpoint 搬到离线机器。MapReduce 式 nested parallel reconfiguration + 按 numel 平衡 + node 内多核并行，使转换时间随模型增大但上限约 3 分钟；redundancy-bypassing loading 用 all-gather 替代同 DP group 重复读盘。
  - **依赖假设**：重配置时仍有足够空闲 GPU/CPU 与 ≥3–5 GB/s 本地存储带宽；同 DP group 内 GPU 互联带宽远高于存储（NVLink ~900 GB/s）。
  - **可能失效场景**：故障后集群 GPU 全损、只剩慢速远程 NFS（论文承认带宽受限时性能下降）；极端 spot 场景频繁重配时，即使单次 <5 分钟也可能累积成可观 downtime。

- **假设 1**：所有 atomic checkpoint 以 fp32 存储 weight 与 Adam m/v，可在 resume 时转换到 fp16/bfloat16/fp32 混合精度训练，且不引入数值漂移。
  - **证据强度**：**中**——符合 mixed-precision 训练惯例，GPT-350M/7B/176B 与 MoE 42B 的 loss 曲线与 baseline 重合（Figure 7–9）；但实验主要是短跑（100–200 iter），未覆盖超长训练后 optimizer state 累积误差或动态精度切换边界。

- **假设 2**：训练 job 的并行策略变更频率很低，lazy invocation（仅 $P_{src} \neq P_{tgt}$ 或硬件变化时触发）足以让重配置开销可忽略。
  - **证据强度**：**中**——生产案例（BLOOM 176B 三个月训练一次节点减半）支持；但 spot-instance / 高频抢占环境（Bamboo、Parcae）可能需要更激进的在线重配，论文 Section 7 仅列为 future work。

## 核心方法

UCP 由三层组成：**atomic checkpoint 中间表示**、**pattern-based 重配置流水线**、**高效重配置优化**。整体数据流：$P_{src}$ 分布式 checkpoint → atomic checkpoint → $P_{tgt}$ 分布式 layout（Figure 2）。

### Atomic Checkpoint

每个 tensor operator 对应一组 atomic 文件目录，Adam 优化器下为 `model.pt`（fp32 weight）、`adam_m.pt`、`adam_v.pt`。与 rank id、padding、partition metadata 解耦，只通过参数名索引。这样 atomic 格式天然是「按参数复制的 DP 视图」，又可作为任意并行策略的公共 interchange format，避免为每对 $(P_{src}, P_{tgt})$ 写 converter。

所有数值统一 fp32 存储以保 optimizer 数值稳定；resume 时可再 cast 到 fp16/bfloat16。ZeRO-3 padding（如 [1024] pad 到 [1026] 均分 3 rank）在 Union 后由 StripPad 去除。

### Pattern-Based Reconfiguration Pipeline

**Pattern 识别**（§5.3.1）：从各 rank checkpoint 中判定参数属于 Unique、Replicate、Partial、Shard-V/H/Hy/NC 之一。

**原语**（Table 2）：Extract（并行读 ckpt 拆 fragment）→ Union（按 pattern 做 Replicate 取首份、Partial 求平均、Shard 做 Concat、Unique 直通）→ StripPad → Save 为 atomic；反向路径用 UcpInfo 生成 $P_{tgt}$ 的 rank→参数映射 → layer-by-layer Load。

具体覆盖：
- **ZeRO-3**：flatten 1D 分片为 Shard-V；作 $P_{tgt}$ 时重新 pad 并 broadcast 到 ZeRO 的 fp16 视图。
- **3D 并行**：组合 Replicate/Shard-V/H/Unique；解耦 interleaved 1F1B 的层分配顺序。
- **MoE / GQA**：Shard-NC 处理融合 expert 矩阵与不等长 QKV 的 TP 切分。

算法 1 给出 MapReduce 风格的并行 Extract+Union 伪代码；深度细节见 [[atc2025-lian]]。

### Efficient Reconfiguration

1. **Nested parallel reconfiguration**：mapper 并行读分布式 ckpt，shuffler 按参数名分发，reducer 按 pattern 合并；master 按 numel 把大 embedding 与小 LayerNorm bias 分组平衡，worker 内再多核并行（Figure 6）。
2. **Redundancy-bypassing loading**：同 DP group 各 rank 只读部分 atomic 文件，载入 GPU 后 all-gather 补齐，减少存储→CPU 重复 IO，利用 NVLink 高带宽。
3. **Lazy reconfiguration invocation**：正常训练仍用各框架原生分片保存，不阻塞 critical path；仅在需要换并行或硬件时触发。论文明确反对 save-time 全量 consolidate（会拖慢训练且内存放不下）。

UCP 与 CheckFreq、Gemini、FastPersist 等 **checkpoint 保存优化正交**，可叠加使用。

## 设计取舍

- **取舍 1：fp32 atomic 文件换正确性与通用性**——optimizer state 全 fp32 使 checkpoint 体积约为 param 的 12×（4× weight + 8× optimizer），但避免 mixed-precision 重配时的精度损失；代价是转换与加载 IO 量更大。
- **取舍 2：lazy 两阶段转换换训练路径零侵入**——不修改各框架 save 逻辑，集成成本低；代价是重配时需额外一次全量 read+write atomic，且依赖故障后仍有算力做 MapReduce。
- **取舍 3：pattern DSL 换可扩展覆盖**——比 pairwise converter 工程量少一个数量级，但新并行语义需人工添加 pattern+原语；不是形式化验证的自动 sharding 推断。
- **取舍 4：layer-by-layer load 换内存峰值可控**——峰值 CPU 内存从「全模型 checkpoint」降到「单层」；代价是加载路径比原生直接 mmap 分片略慢（约 +10s，Figure 11）。
- **边界条件**：在 DeepSpeed/Megatron 生态、Adam 优化器、Transformer 族 dense/MoE/GQA 上最优雅；异步训练 Partial pattern、非 Adam optimizer、全新 EP/上下文并行组合需额外扩展；跨集群迁移依赖存储可访问而非 UCP 内置网络传输。

## 实验与结果

- **精度 / 覆盖**：GPT-350M 在 iteration 100 从 TP=2,PP=2,DP=2,ZeRO-1 重配到多种 $P_{tgt}$（改 DP/TP/PP、切 ZeRO-3、换 3D 并行），iteration 101–200 loss 与未重配 baseline 重合（Figure 7a）；多 Source→单 Target 同样一致（Figure 7b）。
- **与 DCP/MCP 对比**（Figure 8）：改 DP 度、切 ZeRO-DP——DCP 可工作；改 MP（PP+TP）——DCP 报错；MCP 支持 MP 但 MoE 与 ZeRO-DP 切换失败；UCP 四类场景全部成功 resume。「失败」指系统级 error，而非 loss 变差。
- **架构泛化**（Figure 9）：GPT-3 7B、176B、Mixtral-style MoE 42B 中途重配后 loss 连续；176B 曲线对应 BLOOM 真实事件（48 node→24 node，2022-07-04）。
- **转换效率**（Figure 10）：7B–1T 模型 nested-parallel (N.P.) vs 串行 (S.Q.) 加速 14–257×；1T 转换约 2.93 min，总端到端 < 5 min（Table 3）。
- **加载开销**（Figure 11）：相对原生分布式 load，atomic load 仅约 +10s，随模型规模稳定；redundancy-bypassing 在 DP 度高时带来 3–20× load 加速。
- **端到端重配**（Table 3）：GPT-3 7B（4×A100）1.38 min；MoE 42B 3.64 min；GPT-3 176B（48 node）2.83 min；GPT-3 1T（128×MI250X）4.12 min。Save 阶段与标准训练相同（0.29–0.50 min）。
- **生产验证**：BLOOM 176B、Phi-3.5-MoE 42B、SmileyLlama 8B、YuLan-Mini 4.2B 端到端训练已使用 UCP。

硬件：精度实验 64×A100-40GB（5 GB/s 存储）；176B 用 384×A100-80GB；1T 效率实验 1024×MI250X（3 GB/s）。

## Critical Analysis

### 论证链条

问题（长训练高故障率 + 资源弹性）→ 观察（checkpoint 与并行耦合导致重配脚本爆炸）→ 设计（atomic IR + pattern pipeline + lazy MapReduce）→ 结果（更广 coverage + loss 不变 + 分钟级开销）链条整体闭合。较强的一环是 **Table 1 / Figure 8 的对比实验**直接证明 prior system 在 MP/ZeRO/MoE 上系统级失败，而 UCP 成功。较弱的一环是 **生产韧性 claim**：BLOOM 案例有力，但 419 failures / 3h 这类行业数字用于动机，未量化「UCP 将 average recovery time 从 X 降到 Y」的 A/B。

另一跳步：论文从「转换可在训练集群内完成」外推到「跨集群迁移可行」（Related Work 对比 Tenplex），但实验未展示跨存储域、跨 GPU 代际（A100→H100）或跨框架（Megatron ckpt→DeepSpeed runtime）的端到端案例。

### 假设压力测试

- **已证明**：DeepSpeed 生态下，GPT/MoE 模型在 DP/TP/PP/SP/ZeRO/3D 间互转保持 short-run loss 一致；DCP/MCP 不能完成的场景 UCP 可完成；1T 规模转换时间有上界。
- **可能失效**（推断）：
  - **高频弹性**：spot 环境若每数十分钟 preempt，分钟级重配 + 全量 atomic 读写仍可能主导 wall-clock；论文引用 Bamboo/Parcae 但无联合实验。
  - **存储瓶颈**：5 GB/s 级带宽已是「consumer SSD / 典型云盘」；更慢远端对象存储下 Table 3 的 4 min 下限可能线性恶化，论文仅定性承认。
  - **Optimizer / 状态扩展**：仅验证 Adam；Lion、AdamW 变体、distillation teacher state、EMA weights、RL rollout buffer 等未讨论。
  - **Expert / EP 并行**：MoE 实验是 Mixtral-style fused FFN + TP，未覆盖独立 [[Expert-Parallelism]] 路由状态与 token 级动态性。
  - **正确性形式**：无 bitwise 或 all-close 数值验证报告，只靠 loss 曲线视觉重合；超长训练后 optimizer momentum 是否漂移未测。

### 实验可信度

- **Benchmark 代表性**：模型从 350M 到 1T、dense+MoE，比仅 DP reshape 的 prior work 更贴近 LLM 生产；训练数据用 Pile 子集，步数偏短（100–200 iter），更像 correctness smoke test 而非 convergence 证明。
- **Baseline 强度**：DCP/MCP 是公平且强的系统对比；但未与手工 conversion script 的 **工程时间/错误率** 或 Tenplex/VirtualFlow 类 runtime reconfig 比端到端 downtime。
- **Ablation**：N.P. vs S.Q. 有力支撑 MapReduce 设计；redundancy-bypassing 有 3–20× 数字；缺少对 pattern 子集（去掉 Shard-NC）、fp32-only storage、layer-by-layer vs bulk load 的独立 ablation。
- **Metrics**：覆盖转换时间、load 时间、loss；**未报告**重配期间 GPU 利用率、峰值 CPU DRAM、训练中断 wall-clock、重配失败回滚、多 job 并发重配干扰。

### 系统性缺陷

- **运维复杂度**：atomic 格式文件数量 = 参数数量 × 3，1T 模型可能产生海量小文件，对对象存储 LIST/元数据压力论文未讨论。
- **尾延迟与调度**：重配触发时训练全停，无在线渐进重shard；对「部分 GPU 失效」是否必须全体 idle 等待转换，论文未讨论。
- **可观测性**：MapReduce 阶段失败、partial Union、StripPad 错误的诊断与回滚机制论文未描述。
- **安全与多租户**：checkpoint 含完整 fp32 训练状态，跨集群迁移时的访问控制、加密论文未讨论。
- **与保存优化集成**：声称与 Gemini/CheckFreq 正交，但无组合实验验证 in-memory checkpoint + UCP 重配的组合开销。

## 局限与 Future Work

- **局限 1**：pattern set 需随新并行策略手工扩展，不是自动从 computation graph 推导；论文承认社区协作_identify 新 pattern。
- **局限 2**：实验以短训练段验证 loss 一致，未覆盖数月训练、动态 mixed-precision 切换、gradient accumulation 与 global batch 变化等生产细节。
- **局限 3**：spot-instance 高频抢占场景仅定性讨论，未量化 UCP 是否足够快以支撑 Parcae/Bamboo 类 proactive migration。
- **Future work 1**：在真实 preemptible trace 上测量「故障→UCP 重配→resume」的 wall-clock 分布，并与 DCP/MCP + 手工脚本、Tenplex 对比 tail downtime。
- **Future work 2**：测量 atomic 格式在 S3/GCS 上的文件数量与 metadata 开销，评估 tar/zarr 打包或 per-layer bundle 是否必要。
- **Future work 3**：扩展 EP、FSDP、上下文并行（Ulysses/Ring Attention）与 RL rollout state 的 pattern 覆盖，并用 bitwise optimizer state 对比补充 loss 曲线验证。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[MoE]]、[[Expert-Parallelism]]、[[Mixed-Precision-Training]]、[[Data-Parallelism]]、[[Checkpointing]]
- **同类系统**：[[DeepSpeed]]、Megatron MCP、PyTorch DCP、CheckFreq、Gemini、Tenplex、FastPersist
- **同会议**：[[ATC-2025]]
- **对比**：UCP 侧重 **checkpoint-time 策略解耦**；[[CrossPipe-ATC25|CrossPipe]] 侧重跨 DC 训练通信；[[Greyhound-ATC25|Greyhound]] 侧重 fail-slow 检测——三者可组合构成弹性大集群训练栈