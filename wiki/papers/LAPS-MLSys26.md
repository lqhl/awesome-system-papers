---
type: paper
name: LAPS
full_title: "LAPS: A Length-Aware-Prefill LLM Serving System"
authors: [Jianshu She, Zonghang Li, Hongchao Du, Shangyu Wu, Wenhao Zheng, "et al."]
venue: MLSys
year: 2026
tags: [llm-serving, scheduling, prefill, disaggregation, multi-turn]
source_pdf: "[[ec5decca5ed3d6b8079e2e7e7bacc9f2.pdf]]"
source_md: "[[ec5decca5ed3d6b8079e2e7e7bacc9f2]]"
---

# LAPS: A Length-Aware-Prefill LLM Serving System (MLSys 2026)

> **一句话总结**：LAPS 在 prefill 阶段内部再做一次按 prompt 长度的 disaggregation，隔离 compute-bound 长 prefill 和 memory-bound 短 (re-)prefill，相比 vanilla [[SGLang]] PD-disaggregation 降低 30% prefill 延迟、28% SLO 违规，高并发下吞吐提升 35%。

## 问题

现代 LLM 服务（[[vLLM]]、[[SGLang]]）已普遍采用 prefill-decode [[Disaggregation]] + [[Continuous-Batching]]，但这一假设所有 prefill 都是 compute-bound 长序列。LMsys-Chat-1M 真实 trace 显示 63% 首轮 prompt < 256 tokens，后续轮次平均 81% < 256 tokens——这些短 (re-)prefill 是 **memory-bound**（被 KV 读写主导）。

长短混批会产生 compute-memory 互扰：短 prefill 排队在长 GEMM 后 TTFT 飙升，长 prefill 被短任务的 KV 流量抢内存带宽。作者用 M/G/1 + Pollaczek-Khinchine 模型刻画 head-of-line blocking，展示 convoy effect。

## 核心方法

**长短 prefill disaggregation**：
- 维护两个独立 prefill pool，完全隔离 LP / SP 队列
- 支持 temporal disaggregation（单实例分时）和 spatial disaggregation（多实例分空间），构成第四种新模式
- 多实例下调度器按负载动态分配 LP/SP 角色

**Short-prefill 优化（核心创新）**：
- **CUDA Graph 复用**：re-prefill 在 multi-turn 中形状稳定（只含新用户输入），预捕获 L∈{8,16,32,64,128,256} × B∈{1,2,...,64} 的 bucket grid，每个请求 pad 到最近 bucket
- **Adaptive Wait-Depth (AWD) scheduler**：自适应等待窗口 W + 目标 batch depth D，按 bucket 聚合请求，收到 deadline 触发时提前派发；派发后按实际 fill time 动态更新 W 和 D
- **Graph-aware memory batching**：在 memory budget 内对齐到捕获的 graph shape

## 关键结果

- 多轮真实负载下 prefill 延迟相比 vanilla SGLang（PD disagg）降低 **>30%**
- 多实例 vanilla 数据并行下 SLO 违规率降低 **28%**，相比 SGLang router (load-balancing) 再降 **12%**
- 高并发混合请求下 Qwen2.5-32B prefill 吞吐提升 **35%**
- 与现有 PD disaggregation 架构完全兼容

## 相关

- **相关概念**：[[Disaggregation]]、[[Chunked-Prefill]]、[[Continuous-Batching]]、[[KV-Cache]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Sarathi-Serve、TensorRT-LLM、Multi-Bin Batching、BucketServe
- **同会议**：[[MLSys-2026]]
