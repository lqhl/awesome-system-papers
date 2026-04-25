---
type: paper
name: BurstComputing
full_title: "Burst Computing: Quick, Sudden, Massively Parallel Processing on Serverless Resources"
authors: [Daniel Barcelona-Pons, Aitor Arjona, Pedro García-López, Enrique Molina-Giménez, Stepan Klymonchuk]
venue: ATC
year: 2025
tags: [serverless, faas, mpi, openwhisk, burst-parallel]
source_pdf: "[[atc2025-barcelona-pons.pdf]]"
source_md: "[[atc2025-barcelona-pons]]"
---

# Burst Computing: Quick, Sudden, Massively Parallel Processing on Serverless Resources (ATC 2025)

> **一句话总结**：把 FaaS 的多租户隔离从 function 粒度抬到 job 粒度，提出 group invocation 原语 flare 一次启动整批 worker 并 pack 到同一容器，PageRank 提速 13×、TeraSort 2×，远程通信减少 98.5%。

## 问题

[[FaaS]]（如 AWS Lambda）适合 bursty workload，但跑 burst-parallel job（MapReduce、PageRank、TeraSort、grid search）有三大摩擦点：

- **F1 Worker 隔离过细**：每个 function 调用独立 HTTP 请求，1000 个 worker 启动时间最大差 18.8 s（无法保证并行性）；
- **F2 Job 碎片化**：worker 不能同时存在 → 必须通过外部存储（S3 / Redis）异步通信，迭代算法（PageRank）不可行；
- **F3 海量数据搬运**：grid search 每个 worker 各自从 S3 拖一份数据，bandwidth 浪费严重；shuffle 需要全互联远程连接。

Spark/Dask/Ray 启动要 95-431 s，太慢；Lambda 启动 6 s 但缺 group 语义。

## 核心方法

**Burst computing** 是一种新 serverless 模型，核心两条：group awareness + locality exploitation。

- **Flare 原语**：单次 HTTP 请求启动整组 worker，平台保证同时运行（job-level isolation）；
- **Worker packing**：n 个 worker 按 granularity g 打包到 m = n/g 个 container（heterogeneous / homogeneous / mixed 三策略），同 pack 内共享 runtime、代码、依赖、数据下载；
- **BCM (Burst Communication Middleware)**：暴露 MPI 风格 send/recv/broadcast/all-to-all/reduce，pack 内 zero-copy（共享内存指针，靠 Rust 安全保证），跨 pack 走 DragonflyDB / Redis / RabbitMQ / S3 backend，自动 chunk + 并发 pool。

实现基于 [[OpenWhisk]] v1.0.0（约 2K SLOC 修改），custom Rust runtime + 5K SLOC BCM。

## 关键结果

- **启动时间**：960 worker 启动从 FaaS 的 19.6 s（g=1）降到 1.7 s（g=48），快 11.5×；MAD 从 2.65 s 降到 0.1 s（dispersity 降 26.5×）。
- **数据加载**：1 GiB 对象 grid search 96 worker 拉数据，FaaS 14 s vs g=48 burst 1 s，提速 32.6×。
- **PageRank**：50M 节点 256 partition，g=64 比 g=1 提速 13×，远程流量从 3068 GiB 减到 44 GiB（-98.5%）。
- **TeraSort**：单 flare 替代 MapReduce 两轮，加 locality-aware all-to-all shuffle，提速 2×。
- **DragonflyDB list + 1 MiB chunk** 可达 2.5+ GiB/s 聚合吞吐。

## 相关

- **相关概念**：[[FaaS]]、[[Serverless]]、[[MPI]]
- **实体**：[[OpenWhisk]]
- **同会议**：[[ATC-2025]]
