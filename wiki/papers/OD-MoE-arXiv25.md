---
type: paper
name: OD-MoE
full_title: "OD-MoE: On-Demand Expert Loading for Cacheless Edge-Distributed MoE Inference"
authors: [Liujianfu Wang, Yuyang Du, Yuchen Pan, Soung Chang Liew, Jiacheng Liu, Kexin Chen]
venue: arXiv
year: 2025
tags: [llm-inference, moe, edge-inference, expert-loading, distributed-inference, quantization]
source_pdf: "[[arxiv25-od-moe.pdf]]"
source_md: "[[arxiv25-od-moe]]"
---

# OD-MoE: On-Demand Expert Loading for Cacheless Edge-Distributed MoE Inference (arXiv 2025)

> **一句话总结**：OD-MoE 的关键判断是 [[MoE]] decode 阶段的 expert loading 延迟可以用「高精度多层 ahead routing 预测 + 多台 edge node 并行 CPU-GPU 传输」隐藏掉；它用 quantized shadow model 的 Scaled Emulative Prediction 达到最高 99.94% expert activation recall，在 10-node testbed 上用约 1/3 GPU memory 保留 fully cached Transformers 部署 75.51% 的 decoding throughput。

## 问题与动机

边缘部署 [[MoE]] LLM 的核心矛盾不是 FLOPs，而是 memory footprint 和 I/O。MoE 每个 token 只激活少数 expert，但所有 expert 权重合起来远大于同等计算量的 dense model；论文称 MoE 相对 comparable-FLOP dense LLM 需要约 4-5 倍 GPU memory。低成本 edge GPU 无法常驻全部 expert，CPU memory 又足够大但 CPU-GPU link 慢，导致 expert offloading 时每层等待权重搬运。

已有 edge / personal-machine MoE offloading 系统通常用 GPU expert cache 缓住 hot expert，或用 quantization / expert skipping 减少加载量。OD-MoE 认为这两条路都不理想：cache 仍然占用最稀缺的 GPU memory，量化或跳 expert 会改变模型质量。它选择一个更硬的目标：**不保留长期 expert cache**，只在下一次激活前 just-in-time 加载目标 expert，用完立刻驱逐。

这个目标成立的前提很窄：系统必须足够早、足够准地知道未来几层会激活哪些 expert，并且要有足够多的独立 CPU-GPU links 把多个 future-layer expert loading 并行起来。OD-MoE 的贡献正是把这两个前提做成系统：Scaled Emulative Prediction（SEP）负责多层 ahead prediction，worker grouping + round-robin scheduling 负责把预测转成并行 I/O。

需要注意论文的 claim 边界：OD-MoE 主要优化 **decode-stage** 的 on-demand expert loading。prefill 阶段由于 batched token 会触发大量 expert，论文明确不做 expert-activation prediction，而是把每层 expert 分散到 worker 上并用 mini-batch pipeline 隐藏 LAN 传输。

## 关键观察 / 隐含假设

- **观察 1**：quantized shadow MoE 在相同输入上与 full-precision MoE 的 routing 行为高度相似，且因为运行更快，可以提前展开未来层 expert activation。
  - **证据**：在 Mixtral-8x7B 上，SEP 使用 FP16 / INT8 / NF4 shadow model 时整体 expert activation recall 分别达到 99.94%、97.34%、95.67%；即使 NF4 也高于 AdapMoE 86%、DAOP 84%、HOBBIT 91% 等已报告 predictor。
  - **依赖假设**：目标模型的 routing 对 quantization perturbation 不敏感；shadow model 的执行速度足够领先 full model；greedy decoding 或低随机性 decoding 让 shadow/full path 更容易对齐。
  - **可能失效场景**：router 对数值误差更敏感的新 MoE 架构、高温采样、多样化 decoding policy、长生成中误差积累更强，或 shadow model 量化到更低精度后 routing drift 变大。

- **观察 2**：autoregressive decoding 中，shadow model 的 token 和 [[KV-Cache]] 会逐 token 漂移；如果不对齐，prediction accuracy 会随 token index 快速恶化。
  - **证据**：Figure 3 显示未对齐 shadow model 的 recall 曲线持续下滑；INT8 / NF4 未对齐时到 100-256 tokens 左右已明显掉到低区间，而 token + KV cache 每轮对齐可以维持接近稳定的高 recall。Figure 8 的 ablation 中，每轮 token+KV 对齐 decoding speed 均值 3.616 tokens/s；去掉 token 对齐或全部对齐都会显著影响速度，完全无 shadow/random preload/按需等路由后再 load 分别跌到约 1.185/1.046/1.032 tokens/s。
  - **依赖假设**：alignment 数据量和网络传输开销可控；论文 testbed 中每次 KV alignment 约 256 KB（32 层 × 每层每 token 8 KB），1 Gbps LAN 还能承受。
  - **可能失效场景**：更深模型、更长 hidden size、更大 batch、更慢网络或更频繁多租户 traffic 会放大 alignment 开销；反过来，GPU 更慢或 expert compute 更长时，最佳 KV alignment period 可能不再是 1。

- **观察 3**：单机 expert offloading 的瓶颈是单条 CPU-GPU link；多台 worker 的独立 link 可以把 future expert loading 分摊到多个设备上，从而把 I/O stall 隐藏在当前层 computation 后面。
  - **证据**：OD-MoE 将 8 个 worker 按 Mixtral top-2 routing 分成 4 组，每组同步负责一层 expert computation 或 future-layer expert loading。timing model 给出不引入 I/O stall 的加载时间上界：$t^{max}_{load}=G t^M+(G-1)t^W$，其中 $G$ 是 worker group 数，$t^M$ 是 main-node non-expert computation 时间，$t^W$ 是 worker expert computation 时间。
  - **依赖假设**：系统有多台带 GPU 的 edge nodes，且每台有足够 CPU memory / storage 存 expert；expert loading 可以跨设备均匀调度；网络 embedding 传输不是新的主瓶颈。
  - **可能失效场景**：真实 IoT/edge 环境节点异构、网络抖动、设备可用性变化大；如果 worker GPU 很弱或 LAN 很慢，round-robin pipeline 可能被 straggler 打断。

- **假设 1**：预测错误的代价足够低，因为错误足够少。
  - **证据强度**：中。99%+ recall 支撑这一点，但论文的性能评估主要在 Mixtral-8x7B、固定数据集和 greedy decoding 下完成；没有展示 prediction miss 对 tail latency 的分布性影响。

- **假设 2**：把 shadow model 放在独立节点上是 edge deployment 可以接受的成本。
  - **证据强度**：弱到中。系统总 GPU memory 是 60 GB，其中 shadow node 使用 45 GB、main node 7 GB、8 个 worker 各 1 GB。worker footprint 很低，但整体系统并不是「每个廉价 IoT device 独立跑 MoE」，而是需要一个较重的 shadow sidecar。

## 核心方法

OD-MoE 的架构有三类节点。main node 保存 full-precision MoE 的 non-expert 参数，包括 attention、gating、normalization 等，并负责标准 autoregressive execution。shadow node 运行一个 quantized Mixtral-8x7B shadow model，目标不是生成最终答案，而是领先 full model 给出未来若干层 expert activation prediction。worker nodes 保存 expert 在 CPU memory / storage 中，根据 shadow node 的 prediction 把目标 expert 加载到 GPU 并执行 expert computation。

**Scaled Emulative Prediction（SEP）** 是论文最重要的机制。传统 predictor 往往用当前层 hidden state 输入下一层 gate，或用历史 expert popularity / cache-hit 统计推断未来 expert。SEP 的思路更直接：让一个更快的 quantized MoE 先跑起来，把它未来层已经实际展开的 routing 结果当作 full model 的 routing 预测。这个设计回应观察 1：quantized model 的 routing path 与 full model 高度相似，因此「emulation」比局部门控 extrapolation 更接近目标。

SEP 需要 **token alignment** 和 **KV cache alignment** 才能长期稳定。shadow model 自己 autoregressive 生成 token 时，哪怕最初输入相同，也会因为 quantization 和 routing 差异逐步走到不同 token path；一旦 token path 或 [[KV-Cache]] 不一致，后续 expert routing 会继续偏离。OD-MoE 在每个 decoding iteration 结束后，把 full model 最新 token 和该 token 对应的 KV cache 传给 shadow node。这样做会带来 late-departure cost：shadow node 要先等 alignment 完成，再追赶未来层；但实验表明在 RTX 3090 + 1Gbps LAN 配置下，降低 prediction error 比减少 late-departure latency 更重要。

decode scheduling 采用 worker grouping + round-robin。Mixtral-8x7B 是 top-2 MoE，因此实现里 group size 取 2，8 个 worker 分成 4 组。当前组执行 layer $l$ 的两个 expert computation 时，其他组加载 layer $l+1,l+2,l+3$ 等未来 expert；当前组完成计算后，转去加载更远未来层。main node 每层仍会运行 gate 得到真实 routing：如果与 prediction 一致，worker 已经准备好；如果不一致，就 fallback 到等待正确 expert 重新加载。

prefill 阶段是另一套路径。因为输入 prompt batch 会让每层大量 expert 被激活，预测单个 future expert 的收益小，OD-MoE 直接把每层 8 个 expert 分到 8 个 worker 并行加载和执行。为降低 edge LAN 上传 embedding 的 idle time，系统把大 batch 切成多个 mini-batch，让 worker 收到第一批 embedding 后先算起来，和后续传输形成 pipeline。

## 设计取舍

- **用 shadow model 换 cache memory**：OD-MoE 减少 worker GPU memory，但引入一个昂贵 shadow node。论文宣传的「worker <1 GB GPU memory」是真的，但系统总配置仍包含 main RTX 3090 与双 RTX 3090 shadow node；这更像一个 edge cluster architecture，而不是单个低端设备方案。
- **用高频 alignment 换 prediction stability**：每轮 token+KV alignment 保持高 recall，也让 decoding speed 最好；代价是 shadow model 每轮 late departure 和额外 LAN traffic。这个取舍依赖当前模型大小、网络和 GPU 速度，论文也显示换成 RTX 3080 worker 后最佳 KV alignment period 变为 4。
- **用分布式 I/O parallelism 换系统复杂度**：多 worker 让 CPU-GPU loading 并行化，但也带来 group scheduling、embedding 网络传输、prediction broadcast、fallback reload、straggler 和故障处理问题。论文给了 timing model 和 testbed，但没有把运维复杂度纳入评价。
- **cacheless 保精度，但牺牲 locality reuse**：完全不保留 expert cache 避免 HBM 占用，也避免量化/skipping 影响质量；但如果 workload 有强 expert reuse，像 [[MOE-INFINITY-arXiv24]] 这类 cache-aware 系统可能在单机/personal-machine 场景更简单。
- **decode 优雅，prefill 边界更硬**：decode 的 sparse top-k activation 很适合 SEP；prefill 则因 batch 激活大量 expert 而退回全 expert 并行加载。长 prompt 或 retrieval-heavy 服务中 TTFT 仍可能主导用户体验。

## 实验与结果

- **testbed**：10 nodes，包括 1 个 main node（单 RTX 3090，32-bit non-expert components）、1 个 shadow node（双 RTX 3090，INT8 unless stated otherwise）、8 个 worker nodes（各单 RTX 3090）。所有节点 AMD R7-7700 CPU，worker 192 GB DRAM，main/shadow 128 GB DRAM，1Gbps Ethernet LAN。
- **model / workload**：Mixtral-8x7B，greedy decoding；speed test 继承 HOBBIT 的 60 个 Alpaca samples，覆盖 `(input tokens, output tokens)` 为 (16,64)、(16,256)、(128,64)、(128,256)。SEP recall 另用 LongWriter 随机 100 prompts，最多 512 output tokens。
- **prediction accuracy**：SEP 在 FP16 / INT8 / NF4 shadow model 下 recall 为 99.94% / 97.34% / 95.67%。对比表中 AdapMoE 86%、DAOP 84%、HOBBIT 91%；Mixtral-Offloading cache-hit 约 80%，fMoE 小于 85%。
- **alignment ablation**：每轮 token+KV alignment 的 decoding speed 均值约 3.616 tokens/s；token-only alignment 约 3.453；KV-only alignment 约 2.445 且 variance 大；无 alignment 约 1.185；random preloading 约 1.046；等 main routing 后再加载约 1.032。说明 token alignment 更关键，KV alignment 仍影响稳定性。
- **alignment period**：RTX 3090 worker 上 token period=1、KV period=1 最快，约 3.606 tokens/s；放宽 token period 会迅速跌到 1.x 或更低。换 RTX 3080 worker 后，token period 固定 1、KV period=4 最好，约 3.005 tokens/s，说明 optimal alignment 是硬件相关参数。
- **decoding throughput**：OD-MoE 平均 3.6925 tokens/s，达到 fully cached Transformers 4.8900 tokens/s 的 75.51%；比 llama.cpp 0.8225 tokens/s 快 4.49×；比 Mixtral-Offloading 2.2375、MoE-Infinity 0.6875、HOBBIT 0.7850、AdapMoE 3.1300 分别快 1.65×、5.37×、4.70×、1.18×。
- **prefill / overall**：OD-MoE TTFT 平均约 2244 ms，慢于 Transformers、AdapMoE 和 Mixtral-Offloading，快于 MoE-Infinity、HOBBIT、llama.cpp；overall output throughput 平均 3.3700 tokens/s，仍高于四个 expert-offloading baselines。
- **memory**：OD-MoE 总 GPU memory 60 GB，其中 main 7 GB、shadow 45 GB、8 个 worker 合计 8 GB；fully cached Transformers baseline 约 180 GB，所以是 1/3。这个结果同时说明 worker 很轻，但 shadow node 很重。
- **answer quality**：OD-MoE 是 full-precision expert computation，不做 expert quantization 或 skipping；论文在 HellaSwag、MMLU、ARC-Challenge、GSM8K、WinoGrande、BigBenchHard、BigCodeBench、HumanEval、MT-bench-101、TruthfulQA 上报告其质量与 full-precision Transformers / llama.cpp 对齐，并优于带压缩或跳 expert 的 offloading baselines。

## Critical Analysis

### 论证链条

论文的主链条基本闭合：MoE edge inference 受 expert weight I/O 限制；cache 会占用 scarce GPU memory；SEP 可以高精度预测 future routing；多 worker round-robin 可以把 future expert loading overlap 到当前 computation；因此无需长期 expert cache 也能接近 fully cached decode speed。最强证据是 alignment ablation：没有 shadow 或没有 alignment 时 throughput 接近 1 token/s，而完整 SEP 到 3.6 token/s 左右。

但它也有一个容易被标题掩盖的转移：**cacheless worker** 不等于 **low-cost whole system**。论文最漂亮的数字是每 worker <1 GB GPU memory，可系统整体需要 60 GB GPU memory，其中 shadow node 独占 45 GB。OD-MoE 的真实贡献更像是把 GPU memory 从许多 worker 的 expert cache 中集中到 shadow predictor，而不是单纯消灭内存需求。

### 假设压力测试

最脆的假设是 routing predictability。Mixtral-8x7B + greedy decoding 下 quantized shadow routing 与 full model 高度一致，但这未必外推到更大、更深、router 更尖锐或含更多 stochasticity 的 MoE。若用户服务使用 temperature sampling、top-p、tool-use 中断、multi-turn prompt mutation，shadow/full token path 的同步成本和失败概率都可能上升。

第二个压力点是 network and straggler。1Gbps LAN 上实验已经把 KV alignment、embedding vector 传输、prediction notification 和 worker output 都放进系统；但真实 edge fleet 可能有 Wi-Fi 抖动、设备休眠、CPU contention、热 throttling。OD-MoE timing model 主要处理平均路径，没有展开 tail latency、worker failure、重新分组和 admission control。

第三个压力点是模型结构变化。OD-MoE 依赖 top-k expert selection 和每层 expert loading 可以按 layer pipeline 组织。如果 future MoE 模型采用 shared experts、fine-grained experts、multi-token routing、expert-choice routing、hybrid attention 或更强 layer-wise irregularity，group size、prediction horizon 和 prefill/decode 切分都需要重做。

### 实验可信度

实验优点是 baseline 覆盖广：fully cached Transformers / llama.cpp 与 Mixtral-Offloading、[[MOE-INFINITY-arXiv24]]、HOBBIT、AdapMoE 都被纳入，且指标同时看 decoding、TTFT、overall throughput、memory 和 answer quality。prediction accuracy 对比也把 recall 和 cache-hit rate 分开说明，避免直接混淆。

局限也明显。workload 只有 60 个 Alpaca samples 做 speed test，输入长度只到 128 tokens，输出最多 256 tokens；prediction recall 用 LongWriter 100 prompts 到 512 tokens。对长上下文、多用户 concurrency、真实 edge traces、batching policy、request arrival distribution、tail SLO 都没有覆盖。OD-MoE claim 的「edge deployment」更像 controlled cluster benchmark，而不是 production edge trace。

baseline 公平性也有结构差异：OD-MoE 使用 10-node distributed cluster，offloading baselines 多是单 GPU / 单服务器系统且不支持 distributed computing。论文这样做是为了忠实复现 baseline，但比较结果同时混合了「方法更好」与「硬件并行度更多」两种因素。它的价值在于证明 distributed edge nodes 可以换取 I/O parallelism，不完全是证明同等硬件下 SEP 一定优于所有 cache/offloading 策略。

### 系统性缺陷

论文未充分讨论 failure handling。cacheless scheduling 对 prediction timing、worker readiness 和 group synchronization 敏感；若某个 worker 加载慢、网络丢包或 prediction message 延迟，当前层 expert computation 会直接卡住。系统也未讨论 multi-tenant isolation：多个 requests 共享 shadow node、main node 和 worker pool 时，alignment traffic 与 expert loading traffic 如何调度。

可观测性与 fallback 成本也不足。论文说 prediction error 很少，所以错误加载影响小；但没有给出 miss-triggered reload 的 tail latency、per-layer stall distribution 或 worst-case burst。对于 edge interactive serving，p99 token latency 可能比 average tokens/s 更重要。

最后，prefill 仍是短板。Table 2 中 OD-MoE TTFT 平均约 2244 ms，明显慢于 Transformers 约 417 ms，也慢于 AdapMoE 约 1387 ms 和 Mixtral-Offloading 约 1845 ms。若实际应用是 short-output / long-prompt / RAG-heavy，decode speed 的优势可能被 TTFT 稀释。

## 局限与 Future Work

- **局限 1**：整体系统 GPU memory 仍高，尤其 shadow node 45 GB，与「低成本 edge」叙事有张力。需要把 worker footprint 和 cluster-wide cost 分开评价。
- **局限 2**：评估 workload 不覆盖真实多租户 edge trace、long context、stochastic decoding、tail latency 和节点异构/故障。
- **局限 3**：SEP 只在 Mixtral-8x7B 上系统验证；routing predictability 是否适用于 DeepSeek/Qwen/Kimi 等新 MoE 架构需要重新测量。
- **局限 4**：prefill 阶段没有从 SEP 获益，TTFT 仍落后 fully cached Transformers 和部分 quantized offloading baselines。
- **Future work 1**：在多个 MoE 架构、不同 decoding temperatures、长上下文长度下测量 shadow/full routing divergence，并报告 per-token / per-layer miss burst 和 p99 reload latency。
- **Future work 2**：设计 adaptive alignment controller，根据当前 worker loading time、network congestion、shadow lag 和 recent recall 动态选择 token/KV alignment period。
- **Future work 3**：把 OD-MoE 与 expert cache 结合成 hybrid policy：只 cache 极少数 high-reuse / high-penalty expert，其余 expert 仍按 SEP on-demand loading，量化 memory-vs-tail-latency tradeoff。
- **Future work 4**：扩展到 heterogeneous edge fleet，加入 worker speed profiling、straggler-aware group assignment、failure recovery 和 admission control，并用真实 edge traces 验证。
- **Future work 5**：单独优化 prefill：比较 mini-batch pipeline、[[Chunked-Prefill]]、layer-group prefill 与 SEP decode pipeline 的端到端组合效果。

## 相关

- **相关概念**：[[MoE]]、[[KV-Cache]]、[[Quantization]]、[[Expert-Parallelism]]、[[Pipeline-Parallelism]]
- **同类系统**：[[MOE-INFINITY-arXiv24]]、[[FluxMoE-arXiv26]]、[[KTransformers-SOSP25]]、[[PipelinedSharding-MLSys26]]
- **同类方向**：Mixtral-Offloading、HOBBIT、AdapMoE、Edge-MoE、DAOP、fMoE
- **核心关键词**：Scaled Emulative Prediction、shadow model、cacheless expert loading、token alignment、KV cache alignment、edge-distributed inference
