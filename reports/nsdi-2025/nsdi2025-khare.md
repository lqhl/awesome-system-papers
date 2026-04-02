# SuperServe: Fine-Grained Inference Serving for Unpredictable Workloads

**作者**：Alind Khare¹, Dhruv Garg¹, Sukrit Kalra², Snigdha Grandhi³, Ion Stoica², Alexey Tumanov¹ (¹Georgia Tech, ²UC Berkeley, ³Adobe)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/khare
**源文件**：[[nsdi2025-khare.pdf]]

---

## 一、背景

ML 模型越来越多地部署在生产应用的关键路径上（如数据中心的 Web 应用、边缘的自动驾驶），必须在严格的延迟 SLO 下服务。这些场景面临三个核心需求的张力：**延迟（R1）**——请求必须在 10-100ms 的 SLO 内完成；**精度（R2）**——在满足延迟约束下尽可能使用高精度模型；**资源效率（R3）**——GPU/TPU 等昂贵资源必须被高效利用。

生产环境中的请求到达率极不可预测，呈现突发性（bursty）特征。例如 Microsoft Azure Functions 的峰值流量可达平均值的 50 倍，且 sub-second 级别的突发模式几乎无法预测。这使得推理服务系统必须在延迟、精度和资源效率之间做出艰难权衡。

---

## 二、要解决的问题

1. **静态模型选择的困境**：第一代推理服务系统（Clipper, Clockwork, TF-serving）为每个应用选择一个固定模型，无法同时满足 R1-R3——突发流量下 SLO 被违反，或在正常负载下使用过低精度的模型。

2. **模型切换代价过高**：最新系统（INFaaS, Model-Switching）支持多模型注册并根据请求率切换，但模型加载延迟远超推理延迟（高达 14.1 倍），使得反应式切换不可行。这迫使系统要么将所有模型驻留在 GPU 内存中（浪费资源），要么依赖粗粒度的预测性调度策略。

3. **预测性调度策略的局限**：由于突发请求模式"几乎不可能预测"，粗粒度预测策略无法最优地在 R1-R3 间导航。业界普遍接受"模型切换的非可忽略配置时间排除了反应式技术"的传统观点。

4. **GPU 内存瓶颈**：同时加载多个模型到 GPU 内存在数据中心和边缘场景都面临资源约束。

---

## 三、洞察与设计

**关键洞察**：SuperNet（权重共享的超网络）在架构搜索之后，实际上已经包含（subsume）了其所有 SubNet 的完整架构空间。因此，无需静态提取单个 SubNet 进行独立部署——可以通过在 SuperNet 中插入控制流算子，在运行时以近乎零开销动态路由请求到任意 SubNet，从根本上消除模型切换延迟。

基于这一洞察，SuperServe 包含两个核心组件：

### SubNetAct：近瞬时模型激活机制

SubNetAct 在预训练的 SuperNet 架构中自动插入三种控制流算子：

- **LayerSelect**：在 block 级别操作，通过布尔控制决定是否执行某个 block（控制网络深度 D）。卷积 SuperNet 按 stage 选择前 D_m 个 block；Transformer SuperNet 基于 "every-other" 策略选择 block。
- **WeightSlice**：在层级别操作，动态选择权重的切片（控制网络宽度 W）。对卷积层选择前 ⌈W_k × C_k⌉ 个 channel；对 Transformer 选择前 ⌈W_k × H_k⌉ 个 attention head。
- **SubnetNorm**：仅用于卷积 SuperNet，为每个 SubNet 预计算并存储 BatchNorm 的 μ 和 σ 统计量。这是因为不同 SubNet 共享权重但激活分布不同，朴素共享 BatchNorm 会导致精度下降高达 10%。这些归一化统计量的内存仅为共享层的 1/500。

通过这三个算子，SubNetAct 可以在单个 SuperNet 部署中同时服务多达 500 个 SubNet，内存降低最高 2.6 倍，模型切换延迟 < 1ms（比传统加载方式快数个数量级）。

### SlackFit：基于松弛时间的在线调度策略

SlackFit 利用 SubNetAct 的瞬时激活能力，设计了一个简单而有效的贪心调度策略：

- **离线阶段**：(1) 从 SuperNet 的 |Φ| ≈ 10¹⁹ 架构空间中提取 |Φ_pareto| ≈ 10³ 个 Pareto 最优 SubNet；(2) 基于延迟的三个单调性属性（P1: 延迟随 batch size 单调增；P2: 延迟随精度单调增；P3: 低精度 SubNet 可在更大 batch 下达到与高精度小 batch 相近的延迟），将 (SubNet, batch size) 组合桶化为等间隔的延迟桶。
- **在线阶段**：当查询到达或 GPU 可用时，以最早截止时间队列中首个查询的剩余松弛时间（slack = deadline - current_time）作为流量突发程度的代理信号，选择延迟最接近但不超过该 slack 的桶执行。突发时 slack 减小，自动选择低精度高吞吐桶；空闲时 slack 充裕，自动选择高精度桶。

---

## 四、实现细节

SuperServe 是一个实时异步模型服务系统，架构包含四个组件：

1. **SuperNet Profiler**：在查询到达前完成 NAS 搜索和 SubNetAct 算子插入（≤ 2 分钟）。
2. **Router**：维护全局 EDF（最早截止时间优先）队列，异步接收客户端查询（带 SLO 的 RPC），在 worker 可用且队列非空时调用调度器。
3. **Fine-grained Scheduler**：实现可插拔的调度策略（SlackFit、MaxAcc、MaxBatch 等），决定 (SubNet φ, batch B) 分配。
4. **GPU Workers**：每个 worker 持有一个 SubNetAct 修改后的 SuperNet 实例，通过控制元组 (D, W) 瞬时激活目标 SubNet，执行推理并返回结果。

最优调度问题被形式化为 Zero-One Integer Linear Program (ZILP)，目标是最大化 Σ Acc(φ) · |B| · I(φ,B,n,t)，约束包括：每个查询至多分配一个 batch、每个 GPU 同一时刻只执行一个 SubNet、batch 不能在到达前执行、必须在截止时间前完成等。由于 ZILP 是 NP-Hard 的，SlackFit 作为在线近似启发式策略。

系统支持卷积（OFA ResNet）和 Transformer（DynaBERT）两类 SuperNet，使用 TorchScript 实现控制流算子的自动插入（Algorithm 1）。

---

## 五、实验结果

**实验平台**：8 个 NVIDIA RTX 2080 Ti GPU workers，使用 gRPC 通信。

**评估负载**：
- 真实负载：Microsoft Azure Functions (MAF) 24 小时 trace（32,700 个函数工作负载，压缩到 120 秒）
- 合成负载：可控的 bursty trace（变化 λ_v 和 CV²_a）和 time-varying trace（变化加速率 τ）

**基线**：Clipper+（6 种固定精度版本）、INFaaS

| 指标 | SuperServe vs 最佳基线 | 条件 |
|------|----------------------|------|
| 精度提升 | +4.67% | 相同 SLO 达成率下 (CNN on MAF) |
| SLO 达成率提升 | 2.85× | 相同精度下 (CNN on MAF) |
| Transformer SLO 提升 | 1.2× | 相同精度下 (Transformer on MAF) |
| 精度提升 (Transformer) | +1.72% | 相同 SLO 达成率下 |
| 内存节省 | 最高 2.6× | 相比独立模型部署 |
| 模型激活时间 | < 1ms | 比模型加载快数个数量级 |
| 线性可扩展性 | 最高 ~33,000 QPS | 0.999 SLO 达成率，32 workers |

**合成负载关键发现**：
- 在所有 bursty trace 上 SuperServe 一致达到 >0.999 SLO 达成率
- 随 CV²_a 增加，SuperServe 与 Clipper+ 的精度差距缩小（因更频繁切换低精度模型）
- 即使加速率 τ 高达 5000 q/s²，SLO 达成率仍保持 0.991-1.0
- 具备透明容错能力：逐步减少 worker 时自动切换低精度模型维持 SLO

**策略对比**：SlackFit 在 SLO 达成率和精度的 Pareto 前沿上始终优于 MaxAcc 和 MaxBatch 策略。

---

## 六、批判性分析

1. **评估模型类型局限**：仅在 CNN（OFA ResNet, 图像分类）和小型 Transformer（DynaBERT, NLU 任务）上验证。现代推理服务的主要挑战在于大语言模型（LLM）的 autoregressive serving，涉及 KV cache 管理、prefill/decode 分离等完全不同的计算模式。SuperNet + SubNetAct 的方法能否适配 LLM 场景完全未讨论。

2. **SuperNet 训练成本被轻描淡写**：论文强调使用已公开的预训练 SuperNet 权重，但这些 SuperNet 的训练本身极其昂贵（OFA 需要在 ImageNet 上训练数天）。对于新任务或新架构，用户需要从头训练 SuperNet，这个成本被忽略了。

3. **精度提升的绝对值**：核心指标 "+4.67% accuracy" 的语义需要仔细审视——这是"平均服务精度"而非端到端应用质量。对于实际应用而言，在 73.8%-80.2% 图像分类精度范围内的动态切换是否真正有业务价值存疑。

4. **Trace 压缩的合理性**：将 24 小时 MAF trace 压缩到 120 秒进行评估，虽然保持了形状但极大加速了事件频率。这种压缩可能对有状态组件（如队列积压、GC 等）产生非现实的压力模式。

5. **SlackFit 的假设条件**：SlackFit 的有效性依赖于三个单调性属性 P1-P3，这些属性在 OFA ResNet 和 DynaBERT 上经验性成立，但并非理论保证。对于其他 SuperNet 架构或混合精度场景，这些属性可能不成立。

6. **与真正的 SOTA 对比缺失**：基线选择偏弱——Clipper (2017)、Clockwork (2020)、INFaaS (2021) 都是较老的系统。未与更现代的推理服务系统（如 vLLM、TensorRT-LLM、Triton）对比，尽管这些系统解决的问题略有不同，但对比会更有说服力。

7. **单一应用假设**：系统假设所有请求服务于同一个 SuperNet 的不同 SubNet。真实的多租户推理场景涉及完全不同的模型，SubNetAct 的权重共享优势不再适用。

---

## 七、AI Infra / MLSys 视角

1. **权重共享作为推理弹性机制的启示**：SubNetAct 展示了"同一份权重，不同计算路径"的理念在推理弹性中的价值。这个思路可以迁移到 LLM 推理中——例如根据负载动态调整 attention head 数量或 layer 数量（类似 early exit 和 layer skipping 的动态版本），但需要在 LLM 质量退化和吞吐提升之间找到更好的平衡。

2. **反应式调度 vs 预测式调度的争论**：论文挑战了"反应式调度不可行"的传统观点，通过消除模型切换开销使反应式策略可行。这个 insight 对 LLM serving 同样有价值——如果 KV cache 切换或模型 LoRA adapter 切换能做到近乎零开销，反应式调度策略的设计空间将大大扩展。

3. **可行的延伸方向**：
   - 将 SubNetAct 思想应用于 MoE 模型的 expert 动态激活，根据负载压力调整活跃 expert 数量
   - 结合 speculative decoding，在高负载时使用更小的 draft model（SuperNet 的小 SubNet），低负载时用完整模型
   - 将 SlackFit 的 slack-based 调度思想引入 continuous batching 系统的 prefill/decode 调度

4. **局限性**：SuperNet 的训练范式在 LLM 时代缺乏直接对应物——当前 LLM 的权重共享和子网络提取技术尚不成熟。这限制了 SubNetAct 在最前沿 AI Infra 场景的直接应用价值。

---

## 八、总结

SuperServe 通过 SubNetAct（在 SuperNet 中插入控制流算子实现近瞬时模型激活）和 SlackFit（基于剩余松弛时间的在线调度策略），解决了突发性请求下推理服务的延迟-精度-资源效率三角权衡问题。系统在 MAF 真实 trace 上实现了最高 4.67% 的精度提升和 2.85 倍的 SLO 达成率提升，同时减少 2.6 倍内存。其核心贡献在于挑战了"模型切换延迟排除反应式调度"的传统观点。主要局限在于仅验证了 CNN 和小型 Transformer 场景，在 LLM 推理这一当前最核心的 AI Infra 场景下的适用性尚未探讨。
