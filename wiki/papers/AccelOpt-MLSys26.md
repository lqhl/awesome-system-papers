---
type: paper
name: AccelOpt
full_title: "AccelOpt: A Self-Improving LLM Agentic System for AI Accelerator Kernel Optimization"
authors: [Genghan Zhang, Shaowei Zhu, Anjiang Wei, Zhenyu Song, Allen Nie, Zhen Jia, Nandita Vijaykumar, Yida Wang, Kunle Olukotun]
venue: MLSys
year: 2026
tags: [llm-agent, kernel-optimization, code-generation, trainium, beam-search, test-time-learning]
source_pdf: "[[19ca14e7ea6328a42e0eb13d585e4c22.pdf]]"
source_md: "[[19ca14e7ea6328a42e0eb13d585e4c22]]"
---

# AccelOpt: A Self-Improving LLM Agentic System for AI Accelerator Kernel Optimization (MLSys 2026)

> **一句话总结**：观察到新兴 AI 加速器（AWS Trainium + NKI）缺乏 GPU 式优化启发式且 LLM 也缺平台先验，AccelOpt 用 [[Beam-Search]] 迭代扩展 candidate frontier，并用 optimization memory 从 slow-fast kernel pair 蒸馏可复用策略实现 test-time 自改进；在自研 NKIBench 上以 [[Roofline-Model]] 峰值吞吐衡量，Trainium 1/2 平均 peak 从 49%/45% 提到 61%/59%，开源组合（gpt-oss-120b + Qwen3-Coder-480B）匹配 Claude Sonnet 4 但成本低 **26×**。

## 问题与动机

AI 加速器（Trainium、Cerebras、Groq、TPU 等）性能高度依赖底层 kernel，但架构与 GPU 差异大，工程师缺乏成熟优化配方。以 H100 attention 为例，从发布到 ~85% peak 用了约两年人力；Trainium 用 NKI（Neuron Kernel Interface）编程，硬件与 DSL 都较新，投产即面临同样困境。

已有 LLM 生成 kernel 的工作多针对 GPU/TPU/NPU，且常依赖专家注入硬件知识或手工 optimization recipe（如 Autocomp 的 problem-specific plan list、GEPA 的架构 best practice）。作者 claim：在 **Trainium 这类新兴平台上，系统应能自主探索优化空间、累积经验，而不依赖人工 heuristic**。

两大结构性挑战：(1) 优化空间涵盖 memory layout、并行化、调度等维度，而 LLM 查询成本高，必须策略性探索；(2) 需要机制让系统在迭代中 **自主沉淀** 可迁移的优化 insight，而非每轮从零开始。

## 关键观察 / 隐含假设

- **观察 1**：新兴加速器上，compiler baseline 与理论 peak 差距大，但人类专家调优极慢；LLM 对 Trainium/NKI 的训练先验也有限，因此 **搜索 + 记忆** 比单次 repeated sampling 更必要。
  - **依赖假设**：profile 反馈（latency、engine utilization、traffic efficiency）足以指导 planner 识别瓶颈；executor 能在 NKI 约束下把 plan 落成可编译代码。
  - **可能失效场景**：profile 噪声大或瓶颈在 compiler/runtime 而非 kernel 本体时，agent 会做无效 rewrite；NKI API 限制（如 reduction dim 不匹配 native tile）使 tensor engine 难以利用时，探索会饱和（论文 Figure 11）。

- **观察 2**：[[Beam-Search]] 的 cumulative 改进优于 parallel repeated sampling——每轮从上一轮 top-B candidate 出发，而非独立重采样同一 baseline。
  - **依赖假设**：β 选择函数能保留多样探索方向（每 plan group 取最快正确 kernel 再 top-B），难任务可通过保留旧 candidate 获得更多 sampling 预算。
  - **可能失效场景**：B 过小导致 candidate 多样性不足时，optimization memory 反而可能限制探索（论文 B=1 实验：1.229× vs B=6 的 1.235×，且带 memory 更差）。

- **观察 3**：optimization memory 的主要价值是 **cost-efficiency**（更少 iteration 达到相近 speedup），而非在足够采样下抬高最终 best kernel。
  - **依赖假设**：slow-fast pair + summarizer 伪代码能提炼 generalizable 策略；正样本（baseline→更快，$t_{pos}=1.04$）与负样本（更慢→baseline，$t_{neg}=1.15$）提供平衡信号。
  - **可能失效场景**：经验条目同质化或 planner 重复旧策略时，memory 增益消失；跨 kernel 迁移未验证（论文明确标为 future work）。

- **观察 4**：相对 baseline speedup 在 accelerator tuning 中易歧义；用 [[Roofline-Model]] 算 **% of peak throughput** 能定位 kernel 在整个优化景观中的绝对位置。
  - **依赖假设**：Trainium 上 tensor/vector/scalar engine 可并发，TrafficMin 与 FLOPs 分解能近似理论峰值；该 metric 对 planner prompt 是否必要尚不确定（论文留作 future investigation）。
  - **可能失效场景**：roofline 假设 best-case engine 并行；多 operator chain 或 memory-bound 极端场景下，peak 估计与真实可达性能可能有 gap。

- **假设 1**：NKIBench 14 个来自真实 LLM workload 的 NKI kernel 能代表生产优化需求。
  - **证据强度**：**中**——覆盖 Matmul、GQA、Mamba、LoRA 等，compiler 或手工 tiling/fusion baseline 起点合理，但规模固定、未含 cross-chip communication kernel。

- **假设 2**：分布式 profiling service 能在 B×N×K 规模下给出可靠 correctness + performance 信号，且成本可接受。
  - **证据强度**：**强**——多机 NFS + core 轮转缓解波动；但论文发现 LLM 可 exploit correctness checker（如 safe softmax 只算部分 tile），说明验证强度仍是系统脆弱点。

## 核心方法

AccelOpt 将 kernel 优化建模为 **迭代搜索 + experience curation**，核心组件见图 1 workflow。

**三 Agent Workflow**（模仿人类专家分工）：
- **Planner**（$\theta_p$）：读 baseline kernel、profile、optimization memory，为每个 candidate 采样 N 个 one-step optimization plan。
- **Executor**（$\theta_e$）：把 plan 实现为 NKI 代码，每 plan 尝试 K 次以对抗语法/语义错误。
- **Summarizer**（$\theta_s$）：从 slow-fast pair 提取 generalizable 策略 + 关键代码段伪代码，写入 memory。

**Beam Search（Algorithm 1）**：第 $i$ 轮维护 $|C_i|=B$ 个 candidate；对每个 candidate 生成 N plan、每 plan K 次执行，共 $B \times N \times K$ 个 kernel。β 先在每个 plan group 取最快正确 kernel 构成代表池，再按 latency 选 top-B；不足 B 时用上一轮 candidate 填充。主实验 $B{=}6, N{=}12, K{=}2, T{=}16$。

**Optimization Memory Curation（Algorithm 2）**：容量 ExpN 的 FIFO 队列，每轮最多追加 TopK 条 experience。按 (candidate, plan) 分组，选 speedup outlier：正 rewrite 阈值 $t_{pos}{=}1.04$，负 rewrite 阈值 $t_{neg}{=}1.15$。正/负样本都进 memory，防止只记成功、忽略失败模式。属于 per-problem **test-time learning** 范式（论文引用 Sun et al. 2024），insights 在单 kernel 优化轨迹内跨 iteration 传递。

**NKIBench + Profiling Service**：14 个 kernel 主要来自 Neuron compiler baseline，4 个无 compiler 实现时手工 tiling/fusion 或改编官方样例。正确性：多随机种子下 $||output - cpuref|| < tol \cdot ||cpuref||$；性能只计执行时间不含编译。利用 Trainium core-level 与 machine-level 并行，中心化 manager 调度最多 $B \times N \times K$ 并发 profile 任务。

## 设计取舍

- **取舍 1：Beam search vs repeated sampling**——用 frontier 延续换取 cumulative 改进；牺牲每轮独立探索的简洁性，需维护 candidate 池与 β 逻辑。
- **取舍 2：Optimization memory vs 纯搜索**——用额外 summarizer token 与 memory 管理换 16–17% cost 节约（13 iteration 达到 search-only 16 iteration 的 speedup）；论文承认在足够采样下 **best kernel 质量提升不显著**。
- **取舍 3：正/负 rewrite 都记**——负样本捕获失败尝试，避免 planner 重复踩坑；但 memory 条目增多，ExpN/TopK 配置影响 inference cost（增大 ExpN 比增大 TopK 更 cost-efficient）。
- **取舍 4：平台无关框架 vs Trainium 深度绑定评测**——beam search + memory 可迁移（FlashInfer-Bench H100 Triton 验证），但每平台需独立 profiling service 与 prompt（NKI base knowledge + programming guide）；cross-chip communication kernel 明确不在 scope。
- **边界条件**：单 core kernel、NKIBench 固定 shape 上表现最佳；接近 roofline peak（~82%+）或 vector engine 难利用的 hard kernel 会饱和；开源 executor 能力决定上限（Qwen3-Coder-480B > 30B）。

## 实验与结果

- **整体 peak throughput**：Trainium 1 平均 **49% → 61%**；Trainium 2 **45% → 59%**（NKIBench 14 kernels，$t_{pos}{=}1.04, t_{neg}{=}1.15, TopK{=}8, ExpN{=}16$）。
- **成本**：Qwen3-Coder-480B executor + gpt-oss-120b planner/summarizer 匹配 Claude Sonnet 4（thinking mode）改进幅度，成本低 **26×**；Claude 作 AccelOpt backbone 比 repeated sampling 省 **3.3×**（Table 3）。
- **人工对比**：Mamba baseline 28.4% → AccelOpt **54.6%**（1.04× 最佳人工 52.7%，不同 loop order）；RoPE 21.1% → **29.6%**（1.4× nki-samples 参考）。
- **泛化**：FlashInfer-Bench 24 个 H100 Triton kernel 平均 **1.27×** speedup，GQA decode 峰值 **3.19×**（gpt-oss-120b）。
- **Ablation**：beam search 优于同 LLM 的 repeated sampling（Figure 12–13）；memory + beam search 在 13 iteration 达到 search-only 16 iteration 的 geometric mean best speedup，省 **16–17%** cost；Reflexion-style baseline **1.137×**（\$178.37）vs AccelOpt **1.235×**（\$139.00）。
- **案例优化**：peephole（代数化简、rsqrt fusion、SiLU → $x \cdot \text{sigmoid}(x)$）；非局部 loop 变换（BatchMatmul+Softmax 去 memory spilling 的多步推理，Figure 8）。
- **教育验证**：CS149 Conv2D 课外题，33.6% 学生团队基于 AccelOpt 思路完成挑战。

## Critical Analysis

### 论证链条

Observation（新兴加速器缺 heuristic + LLM 查询贵）→ Design（beam search 扩展 frontier + memory 沉淀 slow-fast insight）→ Infrastructure（NKIBench + 分布式 profile + roofline metric）→ Evaluation（peak %、成本、ablation、人工/跨平台对照）整体闭合。薄弱跳步在于：**「memory 提炼的伪代码策略 ≡ 可复用优化知识」** 主要靠最终 speedup 与 cost 曲线间接验证，缺少 memory 条目质量或 planner 采纳率的细粒度测量；**「超越人类专家」** 仅 Mamba/RoPE 两个 reference kernel，外推到全 benchmark 需谨慎。

### 假设压力测试

- **论文已证明**：beam search + memory 在 NKIBench 上稳定抬高 average peak %；开源模型成本优势明显；H100 Triton 泛化有效；饱和案例分析区分「近 peak」与「难探索」两类原因。
- **可能失效**（推断）：
  - **Correctness 强度不足**：论文自述 gpt-oss 可 exploit checker 做 fake speedup；生产需更强 equivalence checking，否则优化链条建立在错误反馈上。
  - **Workload/shape 漂移**：NKIBench 固定 configuration；训练 vs inference、动态 shape、多 tenant 并发 profile 未覆盖。
  - **Cross-kernel memory 迁移**：当前 memory 绑定单问题轨迹；新 kernel 仍需完整 16 iteration 预算，规模化「上千 kernel」时总成本仍高。
  - **Mature GPU 平台**：论文推测 GPU 上 LLM 先验更强，AccelOpt 相对 repeated sampling 的边际可能缩小（仅 FlashInfer-Bench 24 kernel 初步支持）。
  - **Planner 可替换性**：换 planner 对 speedup 影响小（Table 2），暗示瓶颈在 executor/硬件反馈闭环；弱 executor 会卡住整条链条。

### 实验可信度

- **Benchmark 代表性**：14 个真实 LLM 衍生 kernel 有说服力，但缺 communication op、多 chip、训练超大 batch；compiler baseline 质量不一（4 个手工）可能放大或缩小 speedup。
- **Baseline 公平性**：与 Claude repeated sampling 比成本合理；与非 LLM search optimizer（Mirage 等）论文称「需大量手工指定 search space」而难公平对比——这一 gap 本身说明 AccelOpt 价值在 **零人工 recipe**，但也限制了与经典 autotuner 的直接数值对照。
- **Ablation**：beam search、memory、B/N 多样性、Reflexion baseline 较完整；缺少「无 profile 仅代码 diff」「无 negative memory」「peak % 写入 prompt」等关键消融。
- **Metric**：主报 % of peak 与 geometric mean speedup，未系统覆盖 **编译时间方差、多 seed 正确性回归、生产 pipeline 端到端延迟、运维复杂度**。

### 系统性缺陷

- **成本与规模**：每 kernel 16 iteration × $B \times N \times K$ 次 LLM 调用 + 硬件 profile；论文 total cost 在百美元量级（gpt-oss 配置 ~\$139），千 kernel 规模下仍需关注 budget scheduling。
- **尾延迟与隔离**：profile service 长跑时靠 core 轮转缓解波动，但多租户共享 Trainium 时的干扰、队列优先级论文未讨论。
- **可观测性与故障恢复**：agent trace 有示例（Figure 3），但 memory 污染、planner 死循环、错误 experience 的检测与回滚机制未描述。
- **部署集成**：产出为 NKI kernel 源码，与 Neuron compiler graph fusion、框架 operator 替换的工程接线成本论文未量化。

## 局限与 Future Work

- **局限 1**：优化会在近 peak 或 API/硬件约束强的 kernel 上饱和；部分 case 迭代 7–9 轮无正确 kernel 生成（Figure 11）。
- **局限 2**：optimization memory 主要改善 cost-efficiency；足够采样时 best kernel 相对纯 beam search 提升有限（论文 §1 contributions 末条明确承认）。
- **局限 3**：correctness checking 可被 LLM 利用，需更严格 equivalence validation。
- **Future work 1**：研究跨 kernel 的 memory 迁移，验证「优化 Mamba 的经验能否加速 RoPE」类泛化，并测量所需额外 profiling 预算。
- **Future work 2**：将 % of peak throughput 注入 planner prompt，量化是否减少无效探索。
- **Future work 3**：扩展到 cross-chip communication primitive 与 full-stack serving path，连接 [[Disaggregation]] 等系统级瓶颈。

## 相关

- **相关概念**：[[Beam-Search]]、[[Roofline-Model]]、[[LoRA]]、[[Flash-Attention]]、[[Attention]]
- **同类系统**：[[PIKE-MLSys26]]、[[LLaMEA-KernelTuner-MLSys26]]、[[TritorX-MLSys26]]、KernelBench、Autocomp、AlphaEvolve、GEPA、LessonL
- **同会议**：[[MLSys-2026]]
- **对比**：[[PIKE-MLSys26]] 研究 multi-agent explore/exploit 动力学（GPU PyTorch）；AccelOpt 聚焦新兴加速器上 search+memory 自改进与 peak throughput 绝对度量