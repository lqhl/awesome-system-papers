---
type: paper
name: MPK
full_title: "MPK: A Compiler and Runtime for Mega-Kernelizing Tensor Programs"
authors: [Xinhao Cheng, Zhihao Zhang, Yu Zhou, Jianan Ji, Jinchen Jiang, Zepeng Zhao, Ziruo Xiao, Zihao Ye, Yingyi Huang, Ruihang Lai, Hongyi Jin, Bohan Hou, Mengdi Wu, Yixin Dong, Anthony Yip, Zihao Ye, Songting Wang, Wenqin Yang, Xupeng Miao, Tianqi Chen, Zhihao Jia]
venue: OSDI
year: 2026
tags: [gpu, compiler, mega-kernel, llm-inference, tensor-program, area/ai-infra]
source_pdf: "[[osdi26-cheng.pdf]]"
source_md: "[[osdi26-cheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 把 Tensor Program 自动编译成 Mega-Kernel（OSDI 2026）

> **原题**：MPK: A Compiler and Runtime for Mega-Kernelizing Tensor Programs

> **一句话总结**：传统 GPU 推理把每个 operator 做成独立 kernel，kernel barrier 和 CPU launch 会阻止跨 operator pipeline 与细粒度通信重叠；MPK 把整张 tensor graph 降为 SM 级 tGraph，再由一个 persistent mega-kernel 内的 scheduler 执行，在固定 64-token prompt、1,024-token decode 的 offline batch 实验中，相对最佳 vLLM/SGLang 获得 1.0–1.7 倍吞吐、8 张 H100 上获得 1.1–1.4 倍吞吐，但没有评测线上 arrival、P99、编译成本或多租户共存。

## 问题与动机

主流 GPU framework 把每个矩阵乘、attention、normalization 和 collective 编译成独立 kernel。相邻 kernel 之间的全局 barrier 很容易保证正确性，却比真实数据依赖更粗：一个 AllReduce tile 可能只依赖一个 MatMul tile，但它仍要等整个 MatMul kernel 完成。kernel boundary 也让下一算子的预取不能和当前算子的计算形成统一 software pipeline。

另一部分成本来自调度。Qwen3-8B 每生成一个 token 需要 293 次 kernel launch。CUDA Graph 可以减少 launch 延迟，却把控制流、shape 和依赖关系静态化；page allocation 和 request scheduling 仍常在 CPU 上完成。模型越小、batch 越低、GPU 越快，真正计算时间越短，这些固定开销就越显眼。

手写 persistent mega-kernel 可以把整次推理放在一个 kernel 内，但开发者要统一 CUDA、attention library、collective、SM 分工和同步，难以迁移到更多模型。MPK（Mirage Persistent Kernel）的目标是：从 PyTorch tensor program 自动生成单 GPU 或多 GPU mega-kernel，同时保留 batch 变化、MoE routing 和连续批处理所需的运行时调度。

## 关键观察 / 隐含假设

- **观察 1：operator-level dependency 太粗。** MatMul 和后续 AllGather/AllReduce 的 tile 之间常是一对一或局部依赖，SM 级 event 可以让通信在部分结果就绪后启动（图 3–4）。
  - **依赖假设**：compiler 能静态推导 task 的读写区域，且分割后的 SM task 足够大，值得支付 event 与 queue 开销。
  - **可能失效**：全局 reduction、数据相关内存访问、非常短的 pointwise task 或无法可靠推导 alias 的自定义 operator。
- **观察 2：固定 launch/barrier 成本随着硬件变快而更突出。** 图 9 的收益通常在小模型、低 batch 和 H100/B200 上较高；Qwen3-30B-A3B 的部分配置只与强 baseline 持平。
  - **依赖假设**：推理主要由许多短 kernel 构成，而不是少数已经吃满 GPU 的大 GEMM。
- **观察 3：纯静态和纯动态调度都不是最优。** [[Attention|attention]] 和 [[MoE|MoE]] routing 的运行时间依赖实际 token，静态分配会不均衡；每个 task 都 JIT dispatch 又会增加 worker↔scheduler 往返（图 8、10）。
  - **依赖假设**：compiler 能把数据相关 operator 标对，并用 global barrier 识别负载重新对齐的位置。
- **假设 1：按模型、GPU、batch 规格化编译的成本可被长期服务摊销。** MPK 为 1、2、4 等代表 batch size 生成多张 tGraph，并按 GPU architecture 生成 task code。
  - **证据强度**：弱到中。论文展示了运行性能，却没有报告 Mirage 搜索时间、首次编译时间、cache 命中或 binary size。
- **假设 2：一个长期驻留的 mega-kernel 可以占用大部分 GPU。** MPK 固定保留 4 个 SM 给 scheduler，其余 SM 做 worker（表 1）。
  - **证据强度**：中。单服务 benchmark 已含这个成本，但没有 concurrent model、MIG、priority stream 或抢占实验。

## 核心方法

**1. 把 operator graph 降为 SM 级 tGraph。** 每个 task 是一个 SM 上执行的计算或通信单元，每个 event 表示细粒度依赖。compiler 按输出 tensor 的 tile 分割 operator，再比较 producer output region 与 consumer input region；区域相交时才插入 event。这样一个下游 task 只等它真正需要的上游 tile，而不是等待整个 kernel（图 4、§3–4）。

**2. 压缩依赖图。** 直接为每个 producer–consumer task pair 建 event 会爆炸。successor-set fusion 合并消费者集合相同的 event，predecessor-set fusion 合并生产者集合相同的 event。normalization 在 fork/join 处插入空 task，使每个 task 最多依赖和触发一个 event；linearization 再把同一 event 释放的 task 排成连续 index range，只保存首尾下标（图 5–6）。这些步骤回应了“细粒度图不能让 metadata 反过来成为瓶颈”的要求。

**3. 为每个 task 自动生成 CUDA device function。** 每个 task 带一个参考 PyTorch 实现，MPK 复用 Mirage superoptimizer 搜索 thread-block graph，再生成包含 intra-SM pipeline、register reuse 和 shared-memory layout 优化的 CUDA code。整个系统通过 `torch.compile(backend=MPK)` 接入 PyTorch；实现约含 44K 行 C++、42K 行 CUDA 和 10K 行 Python（§4.2、§6.1）。

**4. 在一个 persistent kernel 内执行。** 每个 worker 独占一个物理 SM 和 task queue；4 个 scheduler SM 上共运行 16 个 scheduler warp，维护 event queue。task 完成后原子更新触发 event；event 收齐前驱通知后，scheduler 才把后继 task 放进 worker queue。计算和 NVSHMEM 通信使用同一种 task/event 模型，因此快链路可以先释放自己的下游工作，慢链路只阻塞真正依赖它的 task（图 7）。

**5. 混合 JIT 与 AOT launch。** 数据相关 operator 及其后继在遇到 global barrier 前使用 JIT：event 激活后才选择空闲 worker，适合处理 attention 长短不一。其他 task 用 AOT：运行前已经 round-robin 放入固定 worker queue，只等本地 event 激活，少一次 scheduler 往返。worker 优先执行已就绪的 JIT task，再检查 AOT queue（§5.2）。

**6. 管理片上资源与 serving 动态性。** shared memory 被切成 32 KB page，当前 task 释放 page 后，下一个 task 可提前加载数据，实现跨 task pipeline；task description 也会预取到 shared memory。每次 decode 的 start event 内完成 request 回收、接纳与 [[KV-Cache]] metadata 更新。MoE task 读取 top-k routing meta-tensor，在静态 expert task 上动态细分负载；多 GPU collective 则被拆成 NVSHMEM transfer task 和 local reduction task（§5.3、§6.1、§6.4–6.5）。

## 设计取舍

- **细粒度依赖换 graph 大小。** 一个 Qwen3-8B forward 从 293 个 operator 展成 13,867 个 task；event fusion 和 linearization 不是附加优化，而是可执行性的前提。
- **persistent kernel 换共存能力。** 消除 CPU launch、允许统一 pipeline，却更难与其他 model、priority kernel 和 profiler 共存，也扩大一次 kernel failure 的影响范围。
- **JIT/AOT 混合换简单性。** JIT 适应长尾，AOT 减少调度；分类错误会得到负载不均或无谓 scheduler 开销。
- **多张专用 tGraph 换动态性。** powers-of-two batch specialization 比完全动态 graph 快，但 shape、并行度或模型变化会增加编译与 cache 管理。
- **paged shared memory 换 runtime 管理。** page 能跨 task pipeline，但 task 必须遵守“释放后不能再申请”的单调规则。
- **资源例外。** shared memory 按 task 复用，但 mega-kernel 的 per-thread register 数由所有 task 中的最大需求决定，可能压低其他 task occupancy；论文没有单独测这个成本。

## 实验设置

- 五个模型为 Qwen3-0.6B、Llama-3.2-1B-Instruct、Qwen3-1.7B、Qwen3-8B 和 Qwen3-30B-A3B，覆盖 dense 与 MoE，但没有 70B 以上 dense model（图 9）。
- 硬件为 A100、H100、B200；分别有 108、132、148 个 SM，其中固定 4 个给 scheduler，worker 为 104、128、144（表 1）。
- baseline 是 PyTorch+CUDA Graph/`torch.compile`、vLLM 和 SGLang；vLLM/SGLang 使用 FlashInfer、[[Flash-Attention|FlashAttention]]、cuBLAS/CUTLASS 等成熟 kernel。所有系统用 BF16、[[PagedAttention|paged attention]] 和 [[Continuous-Batching|continuous batching]]（§6.3）。
- **所有性能实验实际使用 offline batched inference**，batch size 1–16；每条请求固定 64-token prompt、生成 1,024 token，greedy decode；artifact 说明每个数字为四轮 warmup 后五次运行的中位数。这消除了线上到达不足和 burst，却也没有测真实 serving SLO。

## 实验与结果

- **单 GPU 端到端吞吐**：在五个模型、batch 1–16、A100/H100/B200 上，MPK 相对最佳 vLLM/SGLang 为 1.0–1.7 倍；收益通常在小模型、低 batch 和较新 GPU 上最大（图 9）。Qwen3-8B/A100 的具体 per-token latency 是 14.5 ms 降至 12.5 ms，约 1.16 倍，并接近作者按 16 GB/1.6 TB/s 估计的 10 ms memory-load 下界（§6.3），不是旧页曾写的 8.5 ms。
- **多 GPU**：Qwen3-1.7B tensor parallel 扩到 8 张 H100 时，MPK 相对 PyTorch+CUDA Graph/`torch.compile` 的吞吐最高为 10 倍，相对强 vLLM/SGLang 为 1.1–1.4 倍（图 11、§6.5）。较可信的系统增益应以后一个对照为主。
- **MoE 动态负载**：Qwen3-30B-A3B/B200 上，hybrid MoE 在 batch 1–16 相对 SGLang-MoE 快 1.07–1.18 倍，并始终快于 MPK 的 static partition；SGLang 单独 gather 在 batch 1 时占 MoE 时间最多 11%（图 10、§6.4）。
- **runtime 消融**：Qwen3-8B/B200 的 cross-task pipeline 相对关闭版本快 1.15–1.29 倍，并快于 cuBLAS compiled kernel；Qwen3-1.7B/4×H100 的细粒度 compute–communication overlap 使 iteration latency 降约 1.1 倍（图 12–13）。
- **launch 与 scheduler 开销**：Qwen3-8B 每 token 有 293 次传统 kernel launch；B200 eager 每次 3.8 μs、合计 1.1 ms，CUDA Graph 每次 0.8 μs、合计 0.2 ms。MPK 避免这些 launch，其 in-kernel scheduler 占总 runtime 0.28%（§6.6）。
- **compiler graph 压缩**：三个 Qwen3 tGraph 中，event fusion 把同步点减少 37–118 倍；linearization 把 successor metadata 减少 4.4–15.0 倍，例如 Qwen3-8B 从 110,932 B 降至 18,928 B。所测三个图没有实际 fork/join，因此 normalization 在这些主 workload 中几乎未被用到（表 2、§6.7）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 自动 mega-kernel 能超过成熟 kernel-per-operator serving | 图 9：相对最佳 vLLM/SGLang 为 1.0–1.7 倍 | 五模型、三代 NVIDIA GPU、offline batch 1–16、固定长 decode | 强 |
| SM 级依赖能带来跨 task pipeline 和通信重叠 | 图 12–13：1.15–1.29 倍与约 1.1 倍 | 两个 Qwen3 case，B200 或 4×H100 | 强 |
| multi-GPU mega-kernel 对强系统仍有收益 | 图 11：8×H100 上 1.1–1.4 倍 | 只测 Qwen3-1.7B tensor parallel | 中到强 |
| graph transform 控制了细粒度 metadata | 表 2：event 少 37–118 倍，metadata 少 4.4–15 倍 | 三个 Qwen3 model；normalization 主路径未触发 | 强 |
| MPK 适合动态线上 serving | §6.1 描述 continuous batching 与多 tGraph | 性能评测固定 offline arrival、prompt 和 decode；无 P99 | 弱 |

## 批判性分析

### 论证链条

论文从 kernel barrier 的粗依赖推到 tGraph，从 CPU launch 推到 in-kernel runtime，再用 pipeline、overlap 和 launch 消融逐项闭环，技术主线很扎实。相对 PyTorch 的 10 倍主要说明通用 framework 与专用 serving 的差距；真正有说服力的是相对 vLLM/SGLang 仍有 1.0–1.7 倍和 1.1–1.4 倍。不过“model-agnostic”只由接口设计支持，实验全部是 [[LLM|LLM]] decode，尚未覆盖其他 DNN。

### 假设压力测试

收益依赖每 token 有许多短 kernel。大模型或大 batch 让 GEMM 本身占主导时，图 9 已出现约 1.0 倍，也就是基本持平。在线 serving 的 mixed prefill/decode、[[Prefix-Caching|prefix cache]] hit、[[LoRA|LoRA adapter]]、request cancellation 和 priority 可能不断改变 shape 与控制流；有限的 powers-of-two tGraph 是否足够，需要真实 trace 才知道。异构 interconnect 虽能靠 event readiness 保证局部等待，但不看 topology 的 mapping 未必性能最优。

### 实验可信度

三代 GPU、dense/MoE、single/multi-GPU、强 baseline 和多项消融提供了很好的内部证据，artifact 也明确了重复次数。关键外部边界是固定 64/1,024 token 的 offline batch，故意去掉了 arrival stall；论文没有 TTFT、TPOT 分布、P95/P99、goodput、吞吐—延迟 SLO 曲线或多租户干扰。也没有数值正确性误差、compile/search time、binary size、能耗和冷启动数据。

### 系统性缺陷

一个长期 kernel 内同时承担 request scheduling、KV metadata、compute 和 collective，标准 CUDA kernel trace 会失去 operator 级可见性；deadlock、queue corruption 或一个 task fault 可能挂住整次 model execution。论文没有 timeout、watchdog、单 request cancellation、故障隔离或 CUDA context recovery。固定占用 4 个 scheduler SM、按最大 task 决定 register footprint，也可能影响 GPU sharing 与 occupancy，但没有独立测量。

## 局限与后续工作

- **局限 1**：只验证 NVIDIA CUDA 和 NVSHMEM；“迁移新硬件只改 task generator”仍是设计主张，不是跨平台结果。
- **局限 2**：所有主结果是 offline、固定长度、batch 至多 16，不能直接外推 production P99 或 burst handling。
- **局限 3**：未报告 superoptimization/编译时间、cache、binary 大小、数值误差和生命周期部署成本。
- **局限 4**：persistent kernel 的 preemption、multi-tenancy、fault isolation 与 observability 未评测。
- **后续工作 1**：用 ShareGPT 和至少一条生产 arrival trace，比较 MPK、vLLM、SGLang 的 TTFT、TPOT、P99、goodput，并覆盖 mixed prefill/decode、prefix cache 和 cancellation。
- **后续工作 2**：报告五个模型在冷编译、cache hit、换 batch 上限和换 GPU 时的时间、峰值内存与 binary size，计算需要多少请求才能摊平编译成本。
- **后续工作 3**：并发运行两个 model 或一个 high-priority kernel，测 MPK 的抢占时间、neighbor slowdown、scheduler SM 成本和最大 register footprint 对 occupancy 的影响。
- **后续工作 4**：注入 event 丢失、task 超时、NVSHMEM error 和 worker hang，验证 watchdog、request cancellation 与最小恢复粒度。

## 相关

- **相关概念**：[[Persistent-Kernel]]、[[Kernel-Fusion]]、[[Tensor-Compilation]]、[[Compute-Communication-Overlap]]
- **同类系统**：[[vLLM]]、[[SGLang]]、[[PyTorch]]、[[Triton]]
- **同会议**：[[OSDI-2026]]
