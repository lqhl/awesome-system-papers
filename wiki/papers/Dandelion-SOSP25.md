---
type: paper
name: Dandelion
full_title: "Unlocking True Elasticity for the Cloud-Native Era with Dandelion"
authors: [Tom Kuchler, Pinghe Li, Yazhuo Zhang, Lazar Cvetković, Boris Goranov, et al.]
venue: SOSP
year: 2025
tags: [serverless, faas, cold-start, cloud-native, sandbox]
source_pdf: "[[3731569.3764803.pdf]]"
source_md: "[[3731569.3764803]]"
---

# Unlocking True Elasticity for the Cloud-Native Era with Dandelion (SOSP 2025)

> **一句话总结**:放弃 POSIX-like sandbox,把应用拆成纯计算函数 + 平台托管的通信函数(DAG),sandbox 100 μs 级冷启动(CHERI 下 90 μs),跑 Azure Functions trace 时承诺内存降 96%、比 Firecracker 性能方差降两三个数量级。

## 问题

Serverless 被标榜弹性,但即使 Firecracker MicroVM + snapshot 冷启动仍要 10+ ms(>8 ms 花在 demand paging guest OS snapshot 和重建 host-guest 网络),Knative 为了避免冷启动预热大量空闲 sandbox,Azure trace 下 committed memory 比实际活跃内存高 16×。根本原因:想给用户函数暴露 POSIX-like 环境就必须启动 guest OS + 配网络。但 cloud-native 时代应用越来越多只通过 REST API 访问 S3、inference、向量库等,POSIX 逐渐不是刚需(AWS Lambda 已不支持 inbound conn)。

## 核心方法

Dandelion 引入一种声明式编程模型:应用是由 **pure compute functions**(纯函数,明确声明 input/output sets)和 **communication functions**(平台实现、用户只能调用,如 HTTP)组成的 DAG。纯函数无法发 syscall、不能开线程/socket,靠 `dlibc`/`dlibc++` 模拟 stdio/mem/filesystem(in-memory virtual FS)。这使得:

- sandbox 不需要 guest OS、不需要独立虚网设备,可用 KVM / Linux process / [[CHERI]] / rWasm 四种轻量隔离后端
- 每个 compute function 独占一 CPU core 跑到完成,无阻塞无 context switch
- 通信走平台统一的 cooperative runtime,按系统里 compute vs. communication 比例动态调 core 分配
- DAG 把数据依赖显式化,边上的 `all / each / key` 关键字决定数据分发策略,支持 nested composition 与动态 spawn

SDK 支持 C/C++(CPython 作为 C 函数编译进来),通过 LLVM 前端可扩到其它语言;rWasm 后端还能直接吃 Wasm。

## 关键结果

- Sandbox 冷启动:KVM/Linux process 后端 100s of μs,CHERI 后端 <90 μs,比 Firecracker snapshot boot 快一个数量级以上
- 跑 Azure Functions trace 内存承诺比 Knative autoscaler 低 96%
- 性能方差比 Firecracker 降 2-3 个数量级(每请求都可 cold start)
- 与 AWS Athena 比:短查询延迟降 40%、成本降 67%
- Text2SQL agentic workflow、分布式 log 处理、SQL query、图像/视频管道等多类 cloud-native 应用可移植

## 相关

- **相关概念**:[[Serverless]]、[[FaaS]]、[[Cold-Start]]、[[MicroVM]]、[[WebAssembly]]、[[CHERI]]
- **同类工作**:Firecracker、gVisor、Wasmtime/Cloudflare Workers、SigmaOS、Faasnap/Catalyzer
- **同会议**:[[SOSP-2025]]
