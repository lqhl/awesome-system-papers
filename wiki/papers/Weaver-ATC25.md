---
type: paper
name: Weaver
full_title: "WEAVER: Efficient Multi-LLM Serving with Attention Offloading"
authors: [Shiwei Gao, Qing Wang, Shaoxun Zeng, Youyou Lu, Jiwu Shu]
venue: ATC
year: 2025
tags: [llm-serving, multi-llm, attention-offloading, gpu-multiplexing, multiplexing]
source_pdf: "[[atc2025-gao.pdf]]"
source_md: "[[atc2025-gao]]"
---

# WEAVER: Efficient Multi-LLM Serving with Attention Offloading (ATC 2025)

> **一句话总结**：通过 workload weaving 把热门模型的 [[Attention]] 算子卸载到运行冷模型的 GPU，吞吐相比 dedicated serving 提升最多 77%，相比 multiplexing 方法提升最多 60%。

## 问题

MaaS 平台（HuggingFace、Together.ai 等）通常托管几十到几百个 LLM，但请求分布严重 skew：top 5% 模型吃掉 74.8% token，绝大多数模型 cold。现有方案要么用 dedicated 实例（cold 模型 GPU 显存利用率仅 43%），要么用 model parallelism 多路复用（如 AlpaServe / MuxServe）但通信开销大——TP=2 在 NVLink A100 上仍有 17–26% 的 throughput 损失。

## 核心方法

提出 **workload weaving**：把 hot 模型一部分非参数化的 attention 算子卸载到运行 cold 模型的 GPU 上，借助 cold GPU 的空余显存让 hot 模型用更大 batch size。两个关键挑战：

1. **GPU-driven dynamic control flow**：CPU 预先 issue 大量 kernel 到 GPU 硬件队列（vLLM 一次 iteration 387 个），offload 的 attention 算子会被这些 pre-issued kernel head-of-line 阻塞。WEAVER 把控制流下放到 GPU——sender 通过 cross-GPU shared memory（CUDA IPC）写 QKV tensor 并原子递增 task counter，receiver GPU 上一个 polling kernel 持续轮询并立即执行 offload 的 attention，绕过预排队 kernel。
2. **Operator splitting**：长 kernel（如 Llama-3-8B 的 LM head 在 A100 上 961µs）会阻塞 offload 算子。基于 polling system 的排队论建模，证明长 kernel 对等待时间贡献是平方级的，提出优先级算法把长 kernel 二分切分到等待时间降到 sender 平均 iteration 时间 5% 以下。

实现基于 [[vLLM]] v0.6.0 + [[Flash-Attention]]，使用固定 offload ratio（默认 45%），KV cache 在 cold 实例和 hot 实例间共享分配。深度细节回 [[atc2025-gao]]。

## 关键结果

- A100 + NVLink 上对 hot 模型最多 60% 吞吐提升（vs dedicated），对 cold 模型 TPOT 仅增加 3–5ms。
- L40S + PCIe（低带宽互联）上 hot 模型吞吐相比 multiplexing 提升 77%，差距更大因为 TP 通信开销在 PCIe 上更显著。
- 长输出场景（512 in / 1024 out）相比 MuxServe 最多 42% 更高 max throughput。
- Ablation：仅 GPU-driven control 把 sender TPOT 降 4.83×；再加 operator splitting 进一步降 9.5%。

## 相关

- **相关概念**：[[Attention]]、[[KV-Cache]]、[[Flash-Attention]]、[[Tensor-Parallelism]]
- **同类系统**：MuxServe、AlpaServe、Llumnix、LoongServe
- **同会议**：[[ATC-2025]]
