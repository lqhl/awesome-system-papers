---
type: paper
name: OpGuard
full_title: "OpGuard: Bitwise Alignment for Precise and General Debugging of Production LLM Training"
authors: [Ziming Zhou, Yinjie Zhao, Hang Zhu, Wenxiao Wang, Zhihao Bai, Yun Zhang, Shuguang Wang, Haibin Lin, Peng Huang]
venue: OSDI
year: 2026
tags: [distributed-training, debugging, determinism, silent-data-corruption, observability]
source_pdf: "[[osdi26-zhou-ziming.pdf]]"
source_md: "[[osdi26-zhou-ziming]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# OpGuard：用逐位对齐精确调试生产大模型训练（OSDI 2026）

> **原题**：OpGuard: Bitwise Alignment for Precise and General Debugging of Production LLM Training

> **一句话总结**：同一 [[LLM|大模型]] 计算的两个执行，即使 framework、fusion 或调度不同，也应在共同的模型算子边界产生相同 tensor；OpGuard 固定可避免的随机性，在这些边界记录轻量 XOR fingerprint，再用容忍局部乱序的 mapper 找到最长逐位相同前缀，把第一个差异交给工程师。它在 ByteDance 的 20 个生产故障中都定位到 faulty operator 或其第一个 consumer，Table 2 所列 11 个案例把历史上 4 小时–14 天的人工诊断降到估算的 5–30 分钟，但前提是能构造可比较的 reference run，默认 trusted mode 还会把运行时间增加到约 1.25–1.45 倍。

## 问题与动机

大规模训练跨越 model code、compiler、distributed framework、通信库、CUDA/Triton kernels、driver 和 hardware。一个 race、错误的 microbatch index、collective topology 差异或 SDC 可能只改一张卡上的几个数；gradient aggregation 和后续 layers 会迅速把它扩散、稀释，直到许多 steps 后才表现为 loss spike、gradient-norm drift、shape error 或模型质量下降（§1–§2.1）。

论文的 motivating incident 来自一次 thousand-GPU vision-language model training：gradient norm 在 3000 多步后告警，工程师连续五天换 flags、换 kernels、反复重跑仍未定位。根因是 embedding backward kernel 中一个 rare-token-pattern 才触发的小 race，只破坏少数 rows；真正错误发生在前一轮 backward，visible symptom 却出现在后续 forward（§1、图 1–2、§6.2）。

生产上常把 suspect run 与 older stable commit、关闭某项 feature 的配置、替代 kernel，甚至另一套 framework 做 differential debugging。Loss/gradient norm 只能说明“最后不一样”，不能说明第一处在哪里；`torch.allclose` 一类 numerical comparison 又需要给每种 tensor 设 tolerance，小阈值会把正常 floating-point reduction-order 差异当 bug，大阈值会吞掉 one-row/one-bit corruption。Dump 每个 intermediate tensor 虽然细，却在大训练中不可承受，还可能改变 timing，使 race 消失（§2.2–§3.1、§6.2、图 6、图 9）。

OpGuard 把问题改写为：先让两次执行在逻辑上可比较，再只观察 implementation 变化后仍存在的 model-level boundaries。若此前所有配对 tensor 都逐位相同，而某个 boundary 第一次不同，这个位置就是一个比 loss curve 更窄的 debugging pivot。它不自动解释 root cause，也不证明整个 run 正确；它把需要人工排查的范围从整个训练栈缩到一个 operator 及附近传播路径（§3、§4.6、§7）。

## 关键观察 / 隐含假设

- **观察 1：错误发生点和高层症状之间通常隔着很长传播链。** 20 个 production cases 包括 kernel race、recompute、collective topology、offload、checkpoint 和 hardware SDC；Table 3 的 first difference 常在 step 1 或某个局部 tensor，表面 loss/shape symptom 则更晚出现（§6.2、表 2–3）。
  - **结果**：检查 loss、grad norm 或整层 summary 的粒度太粗；需要在 forward/backward model operators 之间观察 materialized tensors。
- **观察 2：训练比一般 online system 更容易构造 comparable replay。** Dataset、checkpoint、seed 和 graph 通常已知，同一 operator 在一 step 中还会执行很多次，race 有重复触发机会；reference 可以是 self-replay、stable commit、config tweak、single-GPU/[[Tensor-Parallelism|TP]] simulator 或 cross-stack execution（§3.2、表 3–4）。
  - **依赖假设**：两边必须从等价 checkpoint 出发，读取相同 inputs/microbatch order，使用相同 RNG choices、precision policy、optimizer rule 和 collective reduction order。共同存在于两边的 deterministic bug 不会形成 difference；preprocessing 已经改变 input 时，系统只能报告第一个仍可对齐的 downstream boundary。
- **观察 3：model-level boundary 比 kernel trace 稳定，也比 layer boundary 精细。** Backend 可以重排、fusion 或消除 temporary buffers，但 faithful implementation 仍要在 linear、normalization、[[Attention|attention]]、[[MoE|MoE]] dispatch/combine 等相邻 model components 之间传递逻辑 tensor（§3.2、§4.3、图 4）。
  - **依赖假设**：这些 tensors 确实在两套实现中 materialize，且 shape、dtype、rank identity 可配对。Aggressive compiler 若跨越该 boundary 融合，插入 probe 本身可能迫使它 materialize；不同 sharding shape 还需要 TP simulator，而不是天然可比。
- **观察 4：不用把整个 execution 变成 deterministic。** OpGuard 只固定 RNG/data order、library algorithm、numeric mode、collective tree 和 checkpoint state；固定后仍出现的 user kernel、third-party code 或 hardware schedule sensitivity 被保留成 bug signal（§3.2、§4.2、表 1）。
  - **依赖假设**：这些 controls 足以消除所有 benign bitwise drift，却不会改变待查 race 的触发条件。Figure 6 中 global synchronization 让 4/20 bugs 不再复现，说明任何 instrumentation 都存在 Heisenbug 风险。
- **观察 5：32-bit XOR fingerprint 很便宜，也能看到很小的随机 corruption。** 每个 probe 在 operator stream 上对 raw bytes 做 XOR reduction；实验中 single-bit flip 必然改变 fingerprint，多种 FP32/BF16/FP16 row corruptions 只需 1–2 rows 就能区分，速度约为 `torch.sum` 的 0.8–1.1 倍（附录 A.4、图 10）。
  - **重要边界**：XOR 对 word/row permutation 和偶数次相同 corruption 可能完全不敏感；随机 difference 的 32-bit collision probability 是 `2^-32`，不是形式化零。系统只对发现的 mismatch 再做 full-byte confirmation，所以一次 fingerprint 相同不能严格证明 tensor 相同。
- **观察 6：真实 trace differences 多为短距离插入、fusion 或 reordering。** 九对 traces 的 median length ratio 为 1.005，median unmatched fraction 为 0；最大 unmatched fraction 7.43% 时，anchor + banded DP 仍找到预期 first difference（§6.6、图 7）。
  - **证据边界**：只抽样 9 对，并只评估 expected first difference 之前已知 comparable 的 prefix。完全重写 graph、长距离重排或 anchors 大量重复时尚未验证。

## 核心方法

### 逐位对齐抽象与可比性控制

OpGuard 把每次 execution 表示为 model-level boundary events 的序列。Alignment 是两序列间保持相对顺序的 partial matching；只允许 operator identity、tensor shape/dtype 和 rank 相容的 events 配对。Bitwise-aligned prefix 是从头开始、所有配对 tensors 都相同的最长区间，第一个 mismatch 是 pivot（§3、Definition 1）。

为了让这个 binary predicate 有意义，系统统一 CPU/CUDA RNG、dropout、dataloader workers、sampler 和 distributed initialization；开启 deterministic framework/cuDNN algorithms，关闭 autotuning 与 TF32，固定 cuBLAS workspace；固定 [[NCCL]] algorithm、protocol、topology、bucketization，并从 checkpoint 恢复 RNG、optimizer、dataloader 和 scheduler state（§4.2、附录 A.5）。跨 Tensor Parallel（TP）degree 对比时，TP simulator 让各 rank 执行完整 unsharded arithmetic，把 collectives 退化为 numerical no-op，以免 sharding 改变 accumulation order。这种 simulator 是 diagnostic execution，不是原 production parallel execution。

### 预检阶段发现共同边界（Preflight）

两边先在 eager mode 跑少数 iterations。Python monkeypatch 记录 tensor operators、arguments 和 callstack；CUPTI 同时记录 kernels、memory operations、collectives、streams 和 timestamps，再把 device work 归因到最近的 user-defined operator。CUPTI 不安全或不可用时，可改为 interception `cudaLaunchKernel`、`cuLaunchKernel`、`cublasLtMatmul` 等 API，但新 library launch path 需要继续维护 wrapper registry（§4.3、附录 A.1）。

系统取两边都观察到、直接发起 device work 的最低 Python-level operators 作为 boundary plan。之后用 AST+CST 的 structural tags 把 traced operator 找回 source callsite；它不依赖固定 line number，能容忍 helper extraction、argument reordering、Triton launch 和 indexed in-place write 等小型 refactor（§5、附录 A.2）。

### 受保护执行与轻量指纹（Guarded execution）

真正 replay 时，每个 boundary callsite 被替换成 wrapper：先在原 stream 发 input fingerprint，执行原 operator，再发 output fingerprint；collective output probe 等 completion handle，跨 stream dependency 复用原有 wait edge，不增加 global synchronization。Trace entry 保存 boundary ID、32-bit XOR、shape、dtype、device、stream、rank 和 local timestamp，不搬完整 tensor（§4.4、图 4(a)）。

各 rank 在 memory buffer 中攒数千条 records，再由 background thread 做 JSON conversion 和 disk flush。Intra-rank 用 XOR kernel 附近的 GPU `%globaltimer` 排序；inter-rank 用 Python launch timestamp、rank 和 sequence number 合并。论文假设 node clock skew 小于约 `10^-4`–`10^-1` 秒的 operator latency，没有使用跨机 clock synchronization（§5）。

### 容忍调度差异的映射

两份 logs 不按 event index 直接对齐。Mapper 先找局部唯一、两边都有且顺序一致的 boundaries 作为 anchors，把长 trace 切成 windows；每个 window 内用带宽受限的 monotone dynamic programming，允许带 penalty 的 gaps 来吸收 inserted/fused work；最后再保守 rescue 少量跨 anchor boundary 的 missed matches（§4.5、算法 1、图 4(b)）。

该算法假设 schedule skew 是局部的，并坚持全局 non-crossing order。若真正 counterpart 超出 DP band、metadata 有歧义或出现大范围 reordering，它宁可留下 unmatched gap。Match score 还依赖相近 device time 和 operator index，因此 timestamp skew 会增加 alignment pressure。

### 前缀认证与人工诊断

Alignment 完成后，系统按顺序比较 paired fingerprints。遇到第一个 mismatch，再做一次 byte-level tensor comparison 确认，并返回 operator、input/output、rank、stream、callstack 和邻近传播路径；Perfetto UI 把两个 runs 的 events 放在对应 lanes，用 flow links 连接 matches（§4.6、图 4(c)、图 5）。

Unused padding、scratch workspace、RNG bookkeeping 或 performance counter 会产生不影响模型的 difference。新 workflow 初次接入通常有 2–10 个这种 benign differences，工程师在 UI 中确认后加一行 filter；论文所说“adaptation 后 20 cases 无 false positive”依赖这些人工规则，并不表示系统从第一天就能自动区分所有 harmless mismatch（§4.6、§6.2）。

### 三种部署模式

- **Trusted mode** 是 production reactive debugging 的默认设置：跳过 GEMM、basic elementwise 等 allowlist 中的 high-confidence primitives，其他 boundaries 做 fingerprint。它降低开销，但被跳过的 kernel 出错时可能只能定位到 first consumer。
- **Full mode** 检查每个 discovered operator boundary，用于难复现或深层 bug；覆盖更完整，运行时间接近 baseline 的两倍。
- **Online SDC mode** 不等 incident 后再做完整 two-run replay，而是在长任务中持续检查少量 communication boundaries，发现跨 devices 不一致后隔离 suspect machine。论文给出 deployment results，但没有像 reactive path 一样详细说明 comparison topology、每步 coverage 和 detection latency（§6.1、§6.4、§6.8）。

实现共 25.6K LOC，其中 86.7% Python、11.3% C++、1.1% CUDA（§5）。

## 设计取舍

- **Exact bitwise predicate 换无 tolerance 的清晰 pivot**：不会把 `10^-4` 在不同 tensor 中解释成不同含义；只有在两边 arithmetic contract 已完全统一时才成立，数学等价但 reduction order 不同也会 mismatch。
- **Comparable reference 换 end-to-end oracle**：stable commit、self-replay 或 cross-stack run 可互为基线；两边都有的 common-mode bug、无法重现的 intermittent fault 和 input pipeline 差异无法被排除。
- **Model-level boundary 换跨 stack 稳定性**：比每个 temporary kernel 更稳、比整层更精细；compiler 可能消除 boundary，probe 也可能改变 fusion/materialization。
- **32-bit XOR 换 constant-size trace**：可在许多 boundaries 连续运行；会漏 permutation/canceling differences，并有随比较次数累积的 collision risk。
- **Same-stream asynchronous probes 换保留调度**：避免 global barrier，race 更容易继续出现；额外 kernels 仍改变 stream occupancy 和 memory traffic，不能保证零扰动。
- **Trusted allowlist 换较低日常成本**：production slowdown 约 1.25–1.45 倍；allowlist 维护错误会造成 coverage hole 或把定位推迟到 consumer。
- **Partial monotone alignment 换容忍 fusion/overlap**：真实九对 traces 表现良好；大范围 reorder、repeated generic ops 和跨机 timestamp skew 会让 matching 变脆。
- **Downscaled replay 换较低 incident cost**：可从千卡缩到较少 machines；memory pressure、allocator、schedule 和 faulty hardware 都可能随 scale 消失。

## 实验与结果

- **部署、scale、baseline 与硬件边界**：OpGuard 在 ByteDance 部署 8 个月，覆盖 15 个以上 engineering teams 的 pretraining、post-training、VLM、RL、compiler、platform 和 heterogeneous-backend work；production/debug jobs 最大 512 XPUs，overhead tests 为 8–512 XPUs。论文还描述一个 1024-machine SDC 在 512-machine replay 中因坏设备不在场而消失。它没有公开 model parameter counts、accelerator SKU/数量对应关系、CPU、network、tensor/pipe parallel configuration、trace duration 或 log volume；主要实现细节和 coverage 以 CUDA/CUPTI 为主，NPU backend 的附录表述仍是开发中。比较对象包括历史 manual triage、DeepLocalize/DeepDiagnosis/DeepFD、adapted TTrace、vendor EUD/RVS health checks，以及 global-sync tracer/full tensor dump（§5–§6.1、§6.8、§7）。
- **20 个 production incidents 的定位结果**：OpGuard 对全部 20 个 escalated failures 都把 first difference 放在 faulty kernel 内或其第一个 consumer。Table 2 有可靠工程日志的 11 个 cases 中，manual triage 为 4 小时–14 天，OpGuard 为工程师估算的 5–30 分钟；这些时间是历史 ticket 到 root-cause/fix proposal 与 UI inspection estimate，不是同一 incident 的 randomized controlled comparison。DeepLocalize、DeepDiagnosis、DeepFD 只能检测 2/20；TTrace flags 11/20，平均 blame window 为 6.91 modules、45.64 kernels，而且仅 4 cases 原生存在 single-GPU reference，其余使用作者提供的 multi-device deterministic replay（§6.2、表 2–3）。
- **Open-source 与硬件 SDC**：在 [[Megatron|Megatron-LM]]、[[DeepSpeed|DeepSpeed]]、GPT-Neox、HuggingFace Transformers 的 10 个真实 issues 中，OpGuard 对 8 个产生 precise first-difference operator，reference 来自 self-replay、config/stable version、single-GPU/TP simulator 或 cross-stack path；两例不能 cleanly apply（§6.3、表 4）。独立的 online/offline SDC deployment 找到 21 台已通过 vendor pre-flight diagnostics 的 defective machines，并由 targeted stress 和 on-device EDC 再确认；论文没有给总受检 machine 数、machine-hours、false-negative denominator 或 detection-time distribution，因此只能证明补获了 21 个 baseline miss，不能计算 recall（§6.4）。
- **Ablation、alignment 与 coverage**：把 probes 缩到 40 个，只有 2/20 bugs 仍精确定位；去掉 determinism、用 tolerance `10^-5`/`10^-3` 时分别只有 10/20、7/20；把 XOR 换成 sum 为 14/20；改用 global-sync tracer 为 16/20，另外 4 个 race 因 timing perturbation 不再复现（§6.5、图 6）。九对 divergent traces 全部找到 expected pivot，median/max trace-length ratio 为 1.005/1.048，最大 unmatched fraction 7.43%，但测试只覆盖已知 comparable prefix（§6.6、图 7）。八个 training pipelines 的 aligned CUDA-kernel coverage 为 95.3%–100%；其中 LLM pretraining/RL critic 分别为 99.3%/100%，而同两项的手工标注 probes 只覆盖 32.7%/45.3%（§6.7、图 8）。
- **运行代价**：图 9 在 8–512 XPUs 上报告 runtime factor，而不是单纯的百分比 overhead：online SDC 为约 1.00–1.01 倍，trusted mode 为约 1.25–1.45 倍，full mode 为约 1.8–1.95 倍，RL 因 inference/control path 多而略慢。Figure 9(b) 的代表值为 1.01/1.28/1.82 倍；global-sync tracer 为 3.75 倍，full tensor dumping 约 3000 倍。Full dump 是论文描述的 infeasible comparison，不能把 3000 倍当成完整 production matrix 上的实测基线（§6.8、图 9）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| First bitwise difference 对真实训练故障具有高定位价值 | 20/20 production cases 落在 faulty kernel 或 first consumer；11 个有时间记录的案例从 4 小时–14 天降到估算 5–30 分钟（表 2–3） | 单公司 escalated incidents；需要 comparable reference，时间来自工程日志/估算 | 强（该 deployment） |
| 精细 probes、determinism 和 XOR 都是定位精度所必需 | 三类 ablation 分别把 exact localization 降到 2/20、7–10/20、14/20（图 6） | 同一组 20 production bugs；没有逐组件 runtime-cost breakdown | 强 |
| Schedule-tolerant mapper 可跨常见实现差异对齐 | 九对 self/config/library/cross-stack traces 全部找到 expected first difference（图 7） | 只测 comparable prefix，trace divergence 最大 7.43%，样本小 | 中到强 |
| 系统有较高 device-work coverage 且成本低于 tensor dump | 八个 pipelines 的 aligned kernel coverage 95.3%–100%；trusted/full 为 1.25–1.45/1.8–1.95 倍（图 8–9） | Hardware/model details 未公开；trusted mode 跳过 allowlist | 中到强 |
| Online checks 能补足 vendor pre-flight SDC test | 找到并再次确认 21 台已通过 EUD/RVS 类 checks 的 faulty machines（§6.4） | 无 fleet denominator、recall、time-to-detect；online mechanism 细节有限 | 中 |

## 批判性分析

### 论证链条

论文先用真实 incident 证明 aggregate metric 的 temporal/spatial ambiguity，再把 comparative debugging 提升为逐位 predicate；随后用 determinism controls 清掉 benign differences，用 semantic boundaries 跨越 backend details，用 constant-size fingerprint 控制成本，最后用 partial alignment 找 first difference。20 个 production cases、组件 ablation、开源 issues 和 8–512-XPU overhead 让 observation、design 和 result 基本闭合。尤其是 synchronous tracer 让 4 个 races 消失，反向说明“异步、少扰动”不是可有可无的工程优化。

不过“bitwise alignment 是 correctness oracle”需要收窄。它实际证明的是：给定两个逻辑 contract 一致的 executions，已配对 boundaries 的 32-bit fingerprints 在碰撞/盲区之外相同；第一次不同时通常能定位 differential cause。它不能发现两边共享的 bug，也不能从没有 reference 的一条 run 证明正确。XOR 相同并非 tensor equality 的形式化证书，作者只对 mismatch 做 full-byte confirmation；“certified prefix”比底层 32-bit evidence 更强。

### 假设压力测试

Reference 选择是最大压力点。Stable commit 若同时含旧 bug，self-replay 若 race 没重现，cross-stack 若 precision、masking、optimizer 或 collective arithmetic 略有差异，first difference 分别会漏检、无结果或过早触发。Bug 29 已展示 preprocessing 在第一个 model boundary 前就改了 input；此时 OpGuard 只能说“进入模型时已经不同”，不能定位 data pipeline 内部。

Downscaled replay 可能移除 faulty GPU，改变 allocator pressure、fusion plan、microbatch count 或 communication schedule；论文自己的 1024-to-512-machine SDC case 已失去复现。反过来，为可比性固定 collective topology、关闭 autotuning/TF32、插入 pre/post XOR kernels，也可能改变 production race timing。Async design 降低但不能消除这种 perturbation。

XOR 对 row/word permutation、成对相同 corruption 和构造性 cancellation 无感，32-bit collision 还会随大量 boundary comparisons 累积。若要把 OpGuard 用作 release gate 而不只是 incident pivot，64/128-bit order-sensitive hash 或抽样 full comparison 会更稳。Alignment 则假设大部分 events 保序；compiler 跨 layer fusion、pipeline rescheduling 或 repeated generic ops 可能破坏 anchors。

### 实验可信度

真实 20 个 production cases 是论文最强证据：类别覆盖 code、kernel、communication、checkpoint 与 hardware，且 Table 3 公开 reference type、full/downscaled replay 和 first-difference step。Open-source 10 issues 提供一定外部可检查性；ablation 用同一 20 cases 定量说明为什么不能只放几十个 probes、用 sum 或强行 sync。Coverage 与 mode-specific overhead 也避免只谈功能不谈成本。

但 case set 是已经 escalated 给工具的困难 incidents，不代表所有训练错误；“全部定位”没有 unknown ground-truth false-negative set。Table 2 的 manual/OpGuard time 是历史工程日志和 coarse estimate，工具使用者也知道最终 context，可能有 hindsight bias。DeepLocalize/DeepDiagnosis/DeepFD 主要针对 single-device architecture/hyperparameter bugs，与 distributed race/SDC 并非同一 failure model；TTrace adaptation 也依赖作者的 deterministic replay，公平性有限。

硬件 SKU、model size、训练 step 时间、trace bytes、preflight 时间和额外 replay GPU-hours 都未公开。九对 alignment traces 很少，并在 expected pivot 前截取；coverage 只说明 kernels 被某 boundary 包围，不等于每个 kernel error 都能被 trusted mode 直接区分。21 个 SDC positives 没有受检规模和 negative follow-up，无法比较 detection rate。多数数字没有 repeated-run variance 或 confidence interval。

### 系统性缺陷

OpGuard 不是低成本 always-on debugger。Reactive path 至少需要 reference 与 suspect 两次 instrumented execution、shared checkpoint、input/RNG state，以及 25.6K LOC 的 Python/C++/CUDA stack；trusted replay 最多慢 45%，full replay 接近两倍。Incident 若需 full-scale 复现，额外 cluster cost 仍很大。论文报告 UI inspection 分钟数，没有把准备 reference、排队、replay 到 fault step 和 trace transfer 算进端到端 mean time to diagnosis。

Boundary discovery、AST/CST patching、CUPTI/API wrappers、determinism knobs 和 trusted allowlist 都随 [[PyTorch|PyTorch]]、compiler、CUDA/NCCL 与 custom kernels 演进。新 launch API 漏 wrapper、一个 source line 发多个 CUDA ops 或 compiler 消除中间值，会形成 coverage gap；Figure 8 已把这类 gap 显示为最低 95.3%。NPU/其他 XPU 的公开实现成熟度也不清楚。

每 rank 的 traces 包含 callstack、shape、operator、device 与 timing，可能暴露 model architecture 和 training workflow；日志容量、访问控制、retention 和 multi-tenant isolation 未讨论。Background writer、disk failure、rank crash、partial log、clock skew 和 alignment ambiguity 也缺少 fail-safe：工具应当返回“无法认证”，而不是选择一个看似合理的 pivot。Online SDC mode 如何建立 reference/consensus、保护 fingerprint computation 自身并隔离机器，论文没有充分展开。

## 局限与后续工作

- 用 64/128-bit、order-sensitive fingerprint 与周期性 byte-level samples 对照 XOR，测量 billion-boundary 规模的 observed collision、permutation blind spot 和额外开销。
- 把 end-to-end incident 时间拆成 reference 准备、queue、replay、alignment、UI 和 confirmation，并报告 GPU-hours、trace bytes 与 preflight cost。
- 建立包含 normal runs、common-mode bugs、preprocessing faults 和 non-reproducible races 的 blinded corpus，报告 false-positive、false-negative 与“无法对齐”三种结果。
- 在更强 trace divergence、cross-compiler fusion、不同 sharding/precision 和 multi-pipeline schedule 下扩充 alignment sample，不预先裁到 known comparable prefix。
- 明确 online SDC 的 comparison/consensus、coverage、detection latency、hash protection 和 quarantine protocol，按 machine-hours 给 vendor baseline 的 recall/precision。
- 为 clock skew、rank/log loss、disk backpressure、API wrapper miss 和 ambiguous alignment 设计保守失败模式；评测 crash recovery 与 partial trace。
- 公开匿名化 open-source reproducer、hardware/model 配置和 mode allowlist，单独测 GPU 与 NPU backend，而不只用统一的 XPU 口径。

## 相关

- **相关概念**：[[Deterministic-Execution]]、[[Distributed-Training]]、[[Silent-Data-Corruption]]、[[Fingerprinting]]
- **相关系统**：[[NCCL]]、[[SDCHunter-OSDI26]]
- **同会议**：[[OSDI-2026]]
