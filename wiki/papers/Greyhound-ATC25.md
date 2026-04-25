---
type: paper
name: Greyhound
full_title: "Greyhound: Hunting Fail-Slows in Hybrid-Parallel Training at Scale"
authors: [Tianyuan Wu, Wei Wang, Yinghao Yu, Siran Yang, Wenchao Wu, et al.]
venue: ATC
year: 2025
tags: [llm-training, fail-slow, straggler, hybrid-parallelism, characterization]
source_pdf: "[[atc2025-wu-tianyuan.pdf]]"
source_md: "[[atc2025-wu-tianyuan]]"
---

# Greyhound: Hunting Fail-Slows in Hybrid-Parallel Training at Scale (ATC 2025)

> **一句话总结**：在 10000+ GPU 阿里集群上做 fail-slow 表征研究并提出非侵入式检测+多级 ski-rental 缓解，512 GPU 大作业平均被 fail-slow 拖慢 1.34×，Greyhound 在 256 H800 上端到端吞吐提升 1.58×、检测准确率 99.8%。

## 问题

[[LLM-Training]] 大规模混合并行作业里 fail-slow（计算/通信变慢但不崩）比 fail-stop 更隐蔽，现有报告只在 ByteDance、Llama team 的 paper 里零星提及，缺乏系统化的特征研究和针对性 mitigation。简单的 telemetry（GPU SM 利用率、CNP）因同步训练性质会让所有 GPU 一起掉而无法定位；检测性能跑全集群 benchmark 又必须停训练，代价过高。

## 核心方法

**Greyhound-Detect**（非侵入、framework-agnostic）：
- LD_PRELOAD hook NCCL 调用，用 ACF（autocorrelation function）从通信调用序列里推断 iteration 周期；
- 用 Bayesian Online Change-point Detection (BOCD) + verification（前后均值差 >10% 才算）识别 slow iteration；
- 三阶段 workflow：tracking → profiling（cross-group 比较找可疑组）→ validation（短暂挂起训练做 GEMM/P2P benchmark，O(1) 验证 Ring/Tree topology 而非 O(N²)）。

**Greyhound-Mitigate**（多级 ski-rental 风格策略）：
- S1 Ignore → S2 调整 micro-batch 分布（quadratic programming 平衡 DP 组）→ S3 调整 [[Pipeline-Parallelism]] topology（把拥塞链路从 DP 换到 PP、把 stragglers 集中到一个 PP stage）→ S4 checkpoint-restart；
- 累计 slowdown 达到下一档策略的开销时才升级。

深度细节回 [[atc2025-wu-tianyuan]]。

## 关键结果

- 生产集群表征：392 单节点作业 6 个 fail-slow（CPU contention/GPU degradation），107 多节点作业 43 个（主要是网络拥塞），27 个 ≥512 GPU 大作业 16 个 fail-slow，平均拖慢 JCT 34.59%。
- BOCD+V 检测：计算 fail-slow 100% 准确，通信 fail-slow 99.1%，FPR 都为 0。
- S2 micro-batch 调整：单 DP 组 fail-slow 时缓解 1.59×；S3 topology 调整：4 PP 阶段下缓解 1.23×。
- 256 H800 端到端：吞吐 +1.58×；tracking overhead <1%。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Data-Parallelism]]、[[NCCL]]、[[Checkpointing]]
- **同会议**：[[ATC-2025]]
