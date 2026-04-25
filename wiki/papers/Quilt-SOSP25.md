---
type: paper
name: Quilt
full_title: "Quilt: Resource-aware Merging of Serverless Workflows"
authors: [Yuxuan Zhang, Sebastian Angel]
venue: SOSP
year: 2025
tags: [serverless, faas, workflow, llvm, function-merging]
source_pdf: "[[3731569.3764830.pdf]]"
source_md: "[[3731569.3764830]]"
---

# Quilt: Resource-aware Merging of Serverless Workflows (SOSP 2025)

> **一句话总结**:在 LLVM IR 层把 serverless workflow 的多个函数(可跨语言)自动合并为单进程,在 provider 的 CPU/内存约束下做 constraint-aware 的图聚类,中位完成时间降 45.6–71%、吞吐提升 2.05–12.87×。

## 问题

Serverless workflow 里每次函数调用都要走 API gateway → controller → 新容器/冷启动,一次 warm 调用就 10+ ms,冷启动更是上个数量级。已有 merge 方案(Faastlane、Fusionize、WiseFuse、Faasm)要么只能处理单一解释型语言(JavaScript/Python 源码拼接),要么无视 provider 的容器资源上限——把所有函数合并成一个大函数会引发 bin-packing 碎片,worker 上空闲资源无法利用。

## 核心方法

Quilt 在 **LLVM IR** 层合并函数,覆盖 C/C++/Rust/Go(Gollvm)/Swift/Python(Codon)等语言,可跨语言。流程:

1. **Profiling**:在 API gateway 前放 nginx ingress + OpenTelemetry 做透明分布式 tracing,构建函数 call graph(边权=调用频率),并用 cAdvisor 采集每个容器的 peak memory 和 CPU 时间。可通过 Kubernetes token 动态开关。
2. **Constraint-aware merging**:建模为 rooted DAG 聚类问题。节点带 $(c_i, m_i)$,边带归一化调用频率 $\alpha_{i,j}$。目标是把 graph 切成若干 connected rDAG 子图,每个子图满足 CPU 上限 $C$ 与内存上限 $M$(区分 sync/async 调用的内存回收语义),最小化跨组边权和。允许子图重叠(同一函数可出现在多组)。高 fan-out 函数天然不被合并,保留 [[Serverless]] 的弹性。
3. **Code transformation**:LLVM passes 抽取函数代码、重命名避免 aliasing、把 libcurl HTTP 调用替换成直接函数调用、跨语言时翻译 JSON 字符串类型,配合 dead code elimination / library dedup / debloating。
4. **Transparent runtime**:合并后生成的新函数有统一 entry point,scheduler 以为只是函数更新;workload 变化时 Quilt 会 reconsider merge。

实现 1.8K 行 C++ + 1.7K 行 Bash/Python,在 Fission、OpenFaaS、OpenWhisk 上零修改部署。

## 关键结果

- 中位 workflow 完成时间降低 **45.63%–70.95%**。
- 吞吐提升 **2.05×–12.87×**(资源相同)。
- 函数调用从毫秒级变为纳秒级。
- 在 DeathStarBench 的三个 microservice 应用(port 到 C++ 和 Rust)上验证,且可合并 C/C++/Go/Rust/Swift 跨语言函数。
- 已知局限:LLVM pass 编译约 1 分钟;函数若通过外部服务(如 SQS)交互则无法合并;合并后任一函数 crash 会拖垮整个 workflow。

## 相关

- **相关概念**:[[Serverless]]、[[FaaS]]、[[LLVM]]、[[Cold-Start]]、[[Workflow]]
- **同类系统**:Faastlane、Faasm、Fusionize、WiseFuse、Nightcore、SONIC
- **同会议**:[[SOSP-2025]]
