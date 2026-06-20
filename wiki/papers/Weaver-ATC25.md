---
type: paper
name: Weaver
full_title: "WEAVER: Efficient Multi-LLM Serving with Attention Offloading"
authors: [Shiwei Gao, Qing Wang, Shaoxun Zeng, Youyou Lu, Jiwu Shu]
venue: ATC
year: 2025
tags: [llm-serving, multi-llm, attention-offloading, gpu-multiplexing, kv-cache, operator-splitting]
source_pdf: "[[atc2025-gao.pdf]]"
source_md: "[[atc2025-gao]]"
---

# WEAVER: Efficient Multi-LLM Serving with Attention Offloading (ATC 2025)

> **一句话总结**：WEAVER 抓住 multi-LLM serving 中 hot/cold 模型极度 skew、cold GPU 显存闲置而 [[Tensor-Parallelism]] 通信昂贵的观察，把 hot 模型部分非参数化 [[Attention]] / [[KV-Cache]] 工作卸载到正在服务 cold 模型的 GPU，并用 GPU-side polling + operator splitting 控制 head-of-line blocking，使 hot 模型最大吞吐相对 dedicated serving 提升最高 60%、相对 multiplexing 最高 77%，cold 模型平均 TPOT 只增加约 3-5ms。

## 问题与动机

论文面对的是 MaaS / multi-LLM serving 的资源错配：平台通常同时托管几十到几百个模型，但请求分布不是均匀的。作者分析 OpenRouter 一周、209 个模型、超过 200B tokens 的统计，发现 top 5% 模型消耗 74.8% tokens；也就是说，少数 hot 模型吃掉大部分请求，许多 cold 模型请求少但又不能完全下线。

直接 dedicated serving 的问题是 cold 模型 GPU 显存利用率低。论文用 Llama-3-8B 在 A100-40GB 上做例子：hot 模型 15 QPS 几乎占满显存，而 cold 模型 1 QPS 时 GPU memory utilization 只有 43%。这部分闲置显存正好可以变成 hot 模型 decode 阶段的额外 [[KV-Cache]] 容量，从而允许更大的 batch size。

已有 multiplexing 路线（如 [[AlpaServe]]、[[MuxServe]]）用 model parallelism / [[Tensor-Parallelism]] 让 hot/cold 模型共享 GPU，但它把模型当成较通用的 DNN 负载处理，没有利用 Transformer 中 attention 非参数化这一结构。论文测得在 2 张 A100-40GB + NVLink 上，Llama-3-8B 使用 TP=2 相比两个独立实例仍有 17.5%-26.6% token throughput 损失；在 PCIe 互联上这类通信开销会更明显。

WEAVER 的核心动机是：如果只把 hot 模型的一部分 attention operator 和对应 KV cache 放到 cold GPU，而不是把整层权重切成 TP，那么通信只需要传最新 token 的 QKV tensor 和 attention 输出，cold GPU 也不需要存 hot 模型参数。这比通用 multiplexing 更贴近 LLM decode 的瓶颈结构。

## 关键观察 / 隐含假设

- **观察 1：multi-LLM 请求分布高度 skew，cold 模型低 QPS 但常驻。** 证据来自 OpenRouter trace：top 5% 模型使用 74.8% tokens；专用部署实验中 cold Llama-3-8B 在 1 QPS 下只用到 43% GPU memory。
  - **依赖假设**：平台确实需要让 cold 模型长期在线，而不是通过更激进的 serverless / weight swapping / admission control 把 cold GPU 完全回收。
  - **可能失效场景**：如果模型热度变化很快，或者 cold 模型可以被低成本唤醒，固定绑定的 hot/cold weaving 就可能不如 cluster-level 动态迁移。
- **观察 2：hot 模型 decode 的关键约束是 KV cache memory，而 cold GPU 的闲置显存可以扩大有效 batch size。** 论文在 Azure-Conv + A100 上展示，dedicated serving 15 QPS 时 hot GPU KV cache utilization 达 88.9%、平均 batch size 118；WEAVER 在同一 QPS 下把 hot GPU KV utilization 降到 46.9%，同时使用 cold GPU 36.7% KV cache，并在 22 QPS 时把平均 batch size 提到 231。
  - **依赖假设**：目标负载 decode 阶段足够长，batch size 增大能转化成吞吐收益；projection / FFN 还没有完全成为主导瓶颈。
  - **可能失效场景**：小模型、大 batch、短输出、或 attention 占比低的模型上，offload attention 不能加速 FFN，收益会被 projection 主导项吞掉。
- **观察 3：attention 是非参数化 operator，远端执行的通信比 TP 低。** 对每个 decode step，sender 只需发送最新 token 的 QKV tensor，receiver 持有 offloaded sequence 的 KV cache 并返回 attention result；这避开了 TP 每层 projection / FFN 的跨 GPU 通信。
  - **依赖假设**：GPU 间 one-sided write / CUDA IPC 延迟足够低，并且 receiver 上为 hot 模型保留 KV cache 不会压垮 cold 模型的 SLO。
  - **可能失效场景**：跨节点网络、低带宽 PCIe 拓扑、不同 GPU vendor、MIG 隔离、或安全边界严格的多租户云环境，都会让 cross-GPU shared memory / shared KV allocation 更难部署。
- **假设 1：receiver 的 head-of-line blocking 可以被约束到“至多等待一个小 kernel”。** WEAVER 通过 GPU-driven dynamic control flow 绕过 pre-issued kernel 队列，再用 operator splitting 降低 long-running kernel 阻塞。
  - **证据强度**：中。ablation 显示 GPU control 把 sender TPOT 从 175ms 降低 4.83x，operator splitting 再降 9.5%；但证明依赖 Llama-3-8B、vLLM v0.6.0、特定 kernel profile 和固定 offload ratio。

## 核心方法

WEAVER 提出 **workload weaving**：hot instance 将一部分 sequence 的 attention operator 卸载到 cold instance。hot GPU 继续执行 projection / FFN 和未卸载部分的 attention；cold GPU 保存被卸载 sequence 的 KV cache，执行对应 attention，再把结果写回给 hot GPU。这个设计把 [[Attention]] / [[KV-Cache]] 从“必须跟 hot 模型权重在同一 GPU”里拆出来，利用 cold GPU 的闲置显存增加 hot 模型 decode batch capacity。

第一个系统难点是 pre-issued kernels。像 [[vLLM]] 这类 serving runtime 会由 CPU 一次预先 issue 很多 kernels；论文提到 Llama-3-8B 在 vLLM 中一次 iteration 可有 387 个 kernels。如果 offloaded attention 仍由 receiver CPU 发现后再 launch，它会排在硬件队列后面，无法及时插队。WEAVER 的回应是 **GPU-driven dynamic control flow**：sender 用 CUDA IPC / cross-GPU shared memory 写入 QKV tensor 并原子递增 task counter；receiver GPU 上的 polling kernel 持续检查 task counter，发现新任务后直接执行 attention、写回结果并更新 completion counter。这样 offloaded attention 不需要等 receiver CPU 再发 kernel，也绕开了未执行但已排队的 cold-model kernels。

第二个难点是 long-running kernel。即使 offloaded attention 能成为“下一个执行的任务”，它仍可能被当前正在运行的大 kernel 阻塞；论文举例 Llama-3-8B 的 LM head 在 A100 上可达 961us。WEAVER 把 receiver 看作 polling system，推导出大 operator 对 sender wait time 的贡献近似随 `max(T_i - (K - N), 0)^2` 增长，其中 `K` 是 sender 本地 attention 时间，`N` 是 remote attention service time。因此它不是平均切所有 kernel，而是用 priority queue 反复二分最长 operator，直到估计 wait time 低于 sender 平均 iteration time 的 5% 阈值。

实现上，WEAVER 基于 [[vLLM]] v0.6.0 和 [[Flash-Attention]]。offload ratio 默认固定为 45%；prefill 后，每个 hot request 的 KV cache 被随机分配到 hot 或 cold instance，并在请求结束前保持位置不变。KV 管理使用统一 block allocator，以支持不同 layer 数和 KV head 数的模型。论文明确把 cluster-level scheduler 留作 future work，因此当前系统更像一个高效的两实例 / 多实例机制，而不是完整 MaaS 全局调度器。

这个设计和 [[PagedAttention]] 的关系是互补的：PagedAttention 让单个 serving engine 更有效地管理 KV blocks；WEAVER 则把部分 KV blocks 的物理承载位置扩展到正在运行 cold 模型的 GPU 上。它和 [[MuxServe]] 的区别也在这里：MuxServe 主要用 TP / MPS 做时空复用，WEAVER 则只移动 attention 与 KV cache，不移动 hot 模型参数。

## 设计取舍

- **收益换取调度和 runtime 侵入性**：WEAVER 避免 TP 的参数通信，却需要 GPU-side polling、cross-GPU shared memory、task/completion counters、receiver operator splitting，以及统一 KV allocator。这比“把模型切 TP”更贴合 LLM，但对 serving runtime 和 kernel launch 路径的侵入更深。
- **固定 offload ratio 换取机制简化**：论文默认 45% offload ratio，实验也说明 5%-10% 低 offload 会被通信开销抵消，50% 附近能降低 hot TPOT 但线性增加 cold TPOT。固定比例让系统简单，但不能自动应对 cold load 突增或 hot/cold 角色变化。
- **利用 cold GPU 闲置显存换取 cold 模型 SLO 风险**：平均 cold TPOT 只增加 3-5ms，长输出 synthetic 场景增加最多 8ms；这对论文的 cold QPS=1 设定可接受，但生产环境可能更关心 per-tenant SLO、P99/P999、隔离和故障归因。
- **只 offload attention 换取低通信**：attention 非参数化是关键，因而 WEAVER 不加速 FFN / projection。模型越小、batch 越大、projection 越占主导，收益越容易缩水。
- **边界条件**：WEAVER 在 hot 模型受 KV cache memory 限制、cold 模型低而稳定、GPU 间共享内存可用、decode-heavy workload 较多时优雅；在跨节点、多租户强隔离、cold 模型负载波动大、或需要 root / MPS / MIG 等平台特性受限时会变脆。

## 实验与结果

- **workload 与平台**：使用 BurstGPT（平均 input 575、output 340）和 Azure-Conv（平均 input 749、output 232）两条 trace；过滤超过 2048 tokens 的序列；默认模型 Llama-3-8B，cold model 1 QPS，WEAVER offload ratio 45%。平台包括 4x A100-40GB + NVLink 和 4x L40S + PCIe。
- **baseline 公平性**：对比 dedicated serving（unmodified vLLM）和 [[MuxServe]] / Mux-Temporal；为公平，WEAVER 与 dedicated serving 不启用 CUDA Graph，并把 MuxServe attention kernel 替换为同样的 [[Flash-Attention]]。L40S 云环境无 root 权限，不能启用 NVIDIA MPS，因此只评估 Mux-Temporal。
- **hot 模型主结果**：相对 dedicated serving，WEAVER 最大吞吐提升最高 60%；低负载（<5 QPS）下 TPOT 略高，因为通信开销难以摊薄；高负载下 TPOT 最多降低 39%。相对 multiplexing，A100 上最大吞吐最高提升 22%，L40S + PCIe 上最高提升 77%，说明低带宽互联下避免 TP 通信更重要。
- **cold 模型影响**：高 hot load 下 cold 平均 TPOT 增加约 3-5ms；A100 上 cold P99 TPOT 约 19-22ms，比 mean 高 1-2ms。长输出 synthetic 场景中 offloaded workload 更重，cold TPOT 最多比 dedicated serving 增加 8ms。
- **batch / memory 证据**：Azure-Conv + A100 上，dedicated 15 QPS 时 hot batch size 118、hot GPU KV utilization 88.9%；WEAVER 同 QPS 下 hot KV utilization 46.9%、cold KV utilization 36.7%；在 22 QPS 时 hot average batch size 达 231，几乎翻倍。
- **sensitivity**：hot fixed 10 QPS 时，不同 hot-to-cold request ratio 下 WEAVER 的 hot TPOT 比 MuxServe 低约 15%，比 Mux-Temporal 低 20%-40%；offload ratio 从 5% 到 50% 增大时 cold TPOT 近似线性上升，50% offload 让 hot TPOT 降低 13%，同时给 receiver 增加 3.7ms TPOT。
- **长输出**：512 input / 1024 forced output synthetic workload 上，WEAVER 相比 MuxServe 最大吞吐最高提升 42%，因为长 decode 更受 KV cache 和 attention 占比影响。
- **ablation**：CPU control baseline 下 hot TPOT 高达 175ms；加入 GPU-driven control 后 sender TPOT 降低 4.83x，cold TPOT 只增加 1.8ms；再加入 operator splitting，hot TPOT 进一步降低最多 9.5%，cold TPOT 额外增加 0.7ms，总 cold overhead 约 2.5ms、低于 10%。
- **TTFT**：论文主要优化 decode，因此核心 metric 是 TPOT；TTFT 对比中 WEAVER 比 MuxServe 最多高 5.7%，作者认为来自 vLLM 版本中更复杂的 Python 逻辑，而不是机制本身。

## Critical Analysis

### 论证链条

论文的主链条基本闭合：真实 MaaS trace 证明 hot/cold skew，dedicated 实验证明显存浪费，TP 表格证明 multiplexing 通信开销，attention 非参数化给出低通信 offload 机会，GPU-side control 和 operator splitting 对应解决 receiver 队列阻塞，最后主结果显示 hot throughput 上升且 cold TPOT overhead 可控。

比较有说服力的是 ablation：GPU-driven control 贡献最大，说明 pre-issued kernel 队列确实是 workload weaving 的关键阻塞；operator splitting 收益较小但方向明确，说明 long-running kernel 是二阶但真实的问题。论文没有把 workload weaving 只写成抽象愿景，而是落到 vLLM + FlashAttention 的可运行实现。

主要跳步在“机制有效”到“生产 MaaS 调度可用”。论文证明了固定 hot/cold 配对、固定 offload ratio、固定 cold QPS=1 下的局部机制，但没有证明一个真实平台如何选择 sender/receiver、如何处理 hotness 变化、如何做 admission control、以及如何在多租户安全边界下共享显存与 IPC handle。作者也承认 cluster-level scheduler 是 future work。

### 假设压力测试

WEAVER 最强的假设是 cold 模型稳定低负载。若 cold 模型突然变热，offloaded KV cache 会和本地 cold requests 竞争显存；固定 offload ratio 可能在几秒级热度变化下反应过慢。论文建议可用 request rate 动态调 offload ratio，但没有实现或评估。

硬件假设也偏强。CUDA IPC / cross-GPU shared memory 更适合同节点多 GPU；跨节点 RDMA、异构 GPU、MIG、多租户隔离、云厂商权限限制都会增加工程难度。论文在 L40S 云环境甚至无法启用 MPS，这反过来提醒读者：真实云环境权限和隔离策略会直接影响这类 runtime-level 技术的落地。

模型结构假设是 attention/KV 是主要瓶颈。长输出和 memory-bound decode 下这一点成立；但对于小模型、短输出、大 batch 下 FFN/projection 主导的情况，WEAVER 不移动参数、不加速 FFN，收益会下降。论文在 discussion 中也承认小语言模型收益较弱。

### 实验可信度

实验覆盖 A100 + NVLink 与 L40S + PCIe 两类互联，且使用 BurstGPT / Azure-Conv 两条公开 trace，可信度不错。baseline 处理也比较细：禁用 CUDA Graph、统一 FlashAttention kernel，避免把 kernel 实现差异误算成系统收益。

不过 workload 仍有几个边界：所有主实验默认 Llama-3-8B，过滤 >2048 tokens，cold request rate 固定 1 QPS，arrival 由 Poisson 从 trace 采样。真实 MaaS 中可能有多模型大小混合、长上下文、LoRA / adapter、多租户 burst、prompt cache、高优先级请求等因素。论文展示了 longer-output synthetic，但还不足以说明复杂 production mix 下的稳定性。

metric 以 TPOT 为主是合理的，因为机制作用在 decode instance；但系统论文读者还会关心 goodput under SLO、P99/P999 tail、显存碎片、scheduler failure mode、IPC failure recovery、跨租户隔离、观测和 debug 成本。论文对这些生产运维维度覆盖较少。

### 系统性缺陷

实现复杂度是最大风险。GPU-side polling kernel、operator splitting、shared counters、cross-GPU memory、KV block allocator 都在 serving runtime 的底层路径上，任何 bug 都可能表现为 silent wrong result、hang、tail spike 或显存泄漏。论文没有讨论 failure recovery、timeout、counter wraparound、partial request cancellation、receiver crash 后的 KV ownership 处理。

隔离风险也没有展开。cold GPU 同时承载自己的模型 KV cache 和 hot 模型 offloaded KV cache；如果 hot tenant 和 cold tenant 属于不同客户，shared memory 与调度耦合会带来数据隔离、计费、QoS 和审计问题。论文评估的是性能机制，而不是云平台安全边界。

operator splitting 的可维护性需要继续验证。它假设可以稳定 profile `K` / `N` / `T_i`，并能安全切分 receiver 侧 parameterized operator 与 non-parameterized operator。模型、kernel fusion、CUDA Graph、compiler backend 或 serving runtime 版本变化都可能改变 kernel 粒度，使 splitting plan 过时。

## 局限与 Future Work

- **局限 1：缺少 cluster-level scheduler。** 论文当前固定 offload ratio，未实现根据 hot/cold request rate、SLO、显存余量动态选择 offload pair 和比例的全局调度器。
- **局限 2：模型与 workload 覆盖有限。** 主实验集中在 Llama-3-8B、<=2048 token trace、1 QPS cold model；需要在多模型尺寸、长上下文、adapter serving、burstier arrival、真实 multi-tenant trace 上复测。
- **局限 3：部署假设较强。** CUDA IPC / shared memory / GPU polling 更适合同节点可信 GPU；跨节点、MIG、强隔离云环境、异构 GPU 上需要重新设计通信和安全边界。
- **局限 4：只 offload attention。** 当 FFN/projection 或 weight bandwidth 成为主瓶颈时，WEAVER 的设计空间变窄；论文把 FFN offload 留作 future work。
- **Future work 1：动态 offload controller。** 可客观验证的目标是：在 hot/cold QPS 随时间变化的 trace 下，动态 offload ratio 是否能同时满足 cold P99 TPOT SLO 并提升 hot goodput。
- **Future work 2：生产级 failure / isolation study。** 测量 receiver crash、request cancellation、IPC failure、counter desync、tenant isolation policy 对 correctness、tail latency 和 recovery time 的影响。
- **Future work 3：跨拓扑扩展。** 比较同节点 NVLink、同节点 PCIe、跨节点 RDMA 下 QKV transfer、remote KV allocation 和 operator splitting 的收益边界。

## 相关

- **相关概念**：[[Attention]]、[[KV-Cache]]、[[Flash-Attention]]、[[Tensor-Parallelism]]、[[PagedAttention]]
- **同类系统**：[[MuxServe]]、[[AlpaServe]]、[[Llumnix]]、[[LoongServe]]、[[DistServe]]
- **同会议**：[[ATC-2025]]
