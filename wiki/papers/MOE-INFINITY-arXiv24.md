---
type: paper
name: MOE-INFINITY
full_title: "MOE-INFINITY: Efficient MoE Inference on Personal Machines with Sparsity-Aware Expert Cache"
authors: [Leyang Xue, Yao Fu, Zhan Lu, Chuanhao Sun, Luo Mai, Mahesh Marina]
venue: arXiv
year: 2024
tags: [llm-inference, moe, expert-cache, offloading, personal-computing]
source_pdf: "[[arxiv24-xue-moe-infinity.pdf]]"
source_md: "[[arxiv24-xue-moe-infinity]]"
---

# MOE-INFINITY: Efficient MoE Inference on Personal Machines with Sparsity-Aware Expert Cache (arXiv 2024)

> **一句话总结**：MOE-INFINITY 利用单用户本地推理中 [[MoE]] expert 激活在 request 内高度稀疏且可复用的事实，用 request-level Expert Activation Matrix Collection 指导 expert cache 替换和预取，在 DeepSeek/Mixtral 等模型上相对 [[vLLM]]、Ollama、DeepSpeed、BrainStorm 带来 3.1-16.7x per-token latency 改善。

## 问题

大 MoE 模型很适合本地部署，因为每个 token 只激活少数 expert；但模型总参数远超单张消费级 GPU HBM，系统通常需要把 expert 权重放在 host memory，需要时再搬到 GPU。现有 offloading 系统多沿用 dense model 的依赖顺序或 LRU/LFU cache 策略，没有利用 MoE router 的稀疏激活结构，导致 PCIe 上搬运过多 expert，GPU 长时间等待。

论文聚焦 personal machine 场景：batch size 通常为 1，没有云端 continuous batching 的多请求混合。作者的 trace 显示，单个 request 的 decode 阶段只会反复使用很小的 expert 子集；但跨 request 聚合后这种 skew 会消失，所以全局频率统计反而会误导 cache。

## 核心方法

MOE-INFINITY 的核心是 sparsity-aware expert cache。系统为每个 request 维护 Expert Activation Matrix（EAM），记录每层每个 expert 的激活次数，并把历史 request-level EAM 保存在 Expert Activation Matrix Collection（EAMC）里。decode 时，当前 iteration-level EAM 会和历史 EAM 做 cosine-distance 匹配，得到预测的 future expert activation likelihood。

这个预测同时用于两个动作：一是 prefetch 未来层更可能使用的 expert，二是在 cache 满时驱逐 future reuse likelihood 最低的 expert。它比普通 LRU/LFU 更适合 [[MoE]]，因为它捕捉的是「同一个 prompt 内的 expert group 复用」，而不是跨 workload 的平均热度。

实现上，dense 参数和 [[KV-Cache]] 常驻 GPU；expert 权重在 host memory 中，GPU expert cache 只保留 decode 中高概率复用的部分。论文还讨论了 EAMC 容量、workload shift 后恢复以及多 GPU expert hashing 等工程问题。

## 关键结果

- DeepSeek-V2-Lite 在单张 NVIDIA A5000 24GB + PCIe 4.0 上，相对 vLLM、Ollama、DeepSpeed、BrainStorm 等系统实现 3.1-16.7x TPOT 降低。
- 对 Switch、NLLB、DeepSeek，MOE-INFINITY 达到约 155ms、531ms、155ms decode latency，接近全量模型驻留 GPU 的性能，同时只用单 GPU。
- 在 128K long-context DeepSeek-V2-Lite 上，随着 [[KV-Cache]] 挤压 expert cache，性能退化仍比 vLLM/Mixtral-Offloading 更小；on-demand fetching 额外增加约 137ms。
- EAMC 容量从 1 增至 120 后，各 MoE 模型基本达到最低平均 latency；workload 切换后通常几十个 request 内恢复。

## 相关

- **相关概念**：[[MoE]]、[[KV-Cache]]、[[Continuous-Batching]]
- **同类系统**：[[vLLM]]
- **对比**：expert cache / offloading 系统，与 OD-MoE、CoX-MoE、Context-Aware CXL-NDP 路线互补

