---
type: paper
name: LLMStation
full_title: Resource Multiplexing in Tuning and Serving Large Language Models
authors: [Yongjun He, Haofeng Yang, Yao Lu, Ana Klimovic, Gustavo Alonso]
venue: ATC
year: 2025
tags: [llm-serving, peft, lora, gpu-multiplexing, fine-tuning, slo]
source_pdf: "[[atc2025-he-yongjun.pdf]]"
source_md: "[[atc2025-he-yongjun]]"
---

# Resource Multiplexing in Tuning and Serving Large Language Models (ATC 2025)

> **一句话总结**：单 GPU 上同时跑 LLM serving 和 [[LoRA]] PEFT，用迭代级调度 + 可挂起 Autograd + 推训融合 fusion engine，相比 vLLM+torchtune / FineInfer / chunked-training 在不违反 SLO 的前提下 PEFT 吞吐 1.38–14.77×。

## 问题

LLM 推理的 decoding 阶段 GPU FLOPs 利用率 < 5%（memory-bound），但 PEFT fine-tuning 又是 compute-bound——直觉是把它们合在一张 GPU 上吃掉空闲算力。但现有方案都不行：(a) 时间复用（FineInfer）保不住 TTFT 因为 PEFT step 不能中途停；(b) 空间复用（MPS）的 thread percentage 启动时固定不能动态调；(c) chunked-training（FlexLLM）把 PEFT 切 chunk 但短 chunk 不能打满 GPU，且数据搬运 2N 次。生产场景需要严格的 p99 TTFT/TPOT SLO。

## 核心方法

LLMStation 三件套：

1. **Iteration-level 多任务调度器**：每个 inference iteration 开始时，planner 用 latency predictor（线性模型 + cache 历史）估 decoding latency $l_d$ 与 PEFT tasklet latency $l_p$，按 SLO 约束 $N_p \leq \frac{(SLO_d - N_{d,all} \cdot l_{d0}) l_d}{(l_d - l_{d0}) l_p}$ 决定本轮可塞多少 PEFT tasklet。Prefill 进来时挂起 PEFT；decoding + PEFT forward 走 fusion engine；decoding + PEFT backward 走 async 并行。
2. **Suspendable Autograd engine**：把 PyTorch Autograd backward path 改成 C++ stackless coroutine，每层用 `co_await`/`co_return`，让 PEFT worker 能在层粒度按 scheduler 指示挂起/恢复——这是迭代级调度真正能落地的前提。
3. **Fusion engine**：decoding tokens (Si, H) 与 PEFT tokens (Sf, H) 拼成 (Sf+Si, H) 喂给 QKV projection / GateUP / Down，但 attention 单独算。装 base model + LoRA 是用 [[Punica]] 风格的 batched adapter computation。Memory manager 共享 base model + adapter，PEFT 独占 fine-tuning state。

## 关键结果

- 2× RTX 3090 跑 Llama-8B：低请求率下 vs FineInfer/vLLM+torchtune/chunked-training 分别 2.38–8.17× / 2.53–14.77× / 1.57–2.18× PEFT 吞吐。
- 4× RTX 3090 + Llama-13B、8× H100 + Llama-70B 也类似，跨 server 部署下相比 FineInfer 1.77×。
- 高请求率下 LLMStation 的 PEFT 吞吐自然降到接近其他方案，但始终守住 SLO；FineInfer 因 TTFT miss 直接掉到 0。

## 相关

- **相关概念**：[[LoRA]]、PEFT、[[Continuous-Batching]]、SLO、GPU-multiplexing
- **同类系统**：FineInfer、FlexLLM、Punica、[[vLLM]]、torchtune
- **同会议**：[[ATC-2025]]
