---
type: paper
name: NanoFlow
full_title: "NanoFlow: Towards Optimal Large Language Model Serving Throughput"
authors: [Kan Zhu, Yufei Gao, Yilong Zhao, Liangyu Zhao, Gefei Zuo, et al.]
venue: OSDI
year: 2025
tags: [llm-inference, serving, intra-device-parallelism, throughput]
source_pdf: "[[osdi25-zhu-kan.pdf]]"
source_md: "[[osdi25-zhu-kan]]"
---

# NanoFlow: Towards Optimal Large Language Model Serving Throughput (OSDI 2025)

> **一句话总结**：NanoFlow 把一个 batch 拆成 nano-batch 并用 MILP 自动搜出 intra-device pipeline，让 compute/memory/network 在同一张 GPU 上真正并行，LLaMA-2-70B 上吞吐 1.91× 于 TensorRT-LLM、vLLM，达到理论上限的 68.5%。

## 问题

LLM serving 常被认为是 memory-bound，但作者经过 cost model 推导与实测指出：GQA 提升了 batch 密度、模型规模增大、prefill/decode 合并 batch，现代 8×A100 上 LLaMA-2-70B 服务 LMSYS/Splitwise/ShareGPT 真实 workload 时整体是 **compute-bound**——compute 时间是 memory 的 2×以上。

但现有 serving 系统（[[vLLM]]、[[SGLang]]、DeepSpeed-FastGen、TensorRT-LLM）吞吐仍只达到硬件上限的 22–37.8%。根因是 transformer 里 compute-bound（GEMM）、memory-bound（decode [[Attention]]）、network-bound（TP 里的 AllGather/AllReduce）这些异构 op 在设备内被**串行执行**——bottleneck 资源 compute 利用率只有 ~40%。

## 核心方法

**Intra-device parallelism + nano-batching**：把输入 batch 切成多个 nano-batch，每个 op 复制成多个 nano-op 并行处理；因为异构 op 竞争的是不同资源，可以真正 overlap——比如 GEMM 做 KQV 的同时，另一个 nano-batch 正在做 memory-bound 的 decode attention，再叠一路 network-bound 的 AllReduce。虽然要多次加载 weight，但 compute-bound 下这些 memory I/O 可以被 pipeline 藏掉。

**Auto-search（两阶段 MILP）**：nano-batch 数量、大小、顺序、GPU 资源分配的搜索空间巨大。Stage I 假设无 kernel 干扰，MILP 求解管线结构（每个 op 至少切成 2 个 nano-op，有 bubble 就增到更多）；Stage II 用离线 profile 的 pairwise interference table（把 GEMM 性能作为 R 的代理，建立 R→P 的非线性映射，例如分 20% compute 给 GEMM 换来 30% GEMV 的性能）在资源约束 ∑R ≤ 1 下再 refine。约 10 分钟得到一个实用管线。

**Runtime**：异步 scheduling 让 CPU batch formation 与 GPU 执行重叠（接受多解码一个 token 的代价 < 1%）；PagedAttention 管理 KV-cache；对多轮对话做 KV-cache 的 CPU/SSD 分级 offload，用 FFN compute 阶段顺手 offload。Kernel 实现用 CUTLASS profile 找最佳 GEMM，用 CUDA streams + events 保证依赖顺序。

## 关键结果

- LLaMA-2-70B on 8×A100 offline 吞吐：vs vLLM 平均 4.18×，DeepSpeed-FastGen 3.45×，TensorRT-LLM 1.91×（数据集输入输出长度）；constant length 下平均 2.62× / 2.78× / 1.73×。
- 达到理论 compute 上限 1857 tokens/s/GPU 的 68.5%。
- 5 个模型（LLaMA-3 70B、LLaMA-3 8B、Qwen2-72B、Deepseek-67B、Mixtral 8×7B）平均 2.66× vs vLLM，全部达到 50–72% 理论吞吐。
- 200 ms 正则化延迟 SLO 下 LMSYS 上支持 1.64× 请求率 vs TensorRT-LLM；P99 延迟仅 1.07× 平均延迟。
- 实现 ~10K LoC CUDA + 6K LoC Python。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Chunked-Prefill]]、[[Continuous-Batching]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Attention]]、GQA、intra-device parallelism、MILP
- **同类系统**：[[vLLM]]、[[SGLang]]、DeepSpeed-FastGen、TensorRT-LLM
- **同会议**：[[OSDI-2025]]
