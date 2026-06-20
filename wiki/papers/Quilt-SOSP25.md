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

> **一句话总结**：serverless workflow 每次调用经 gateway/controller/HTTP 毫秒级开销；Quilt 在 [[LLVM]] IR 层按 provider CPU/内存约束做 constraint-aware 合并（可跨 C/Go/Rust/Swift），中位完成时间降 45.6–71%、吞吐 2.05–12.87×，调用降至纳秒级。

## 问题与动机

[[Serverless]] workflow 将 microservice 拆成独立容器函数，flexibility 高但 **invocation tax** 重：warm no-op ~10ms，冷启动更糟。Nightcore/Faastlane 等或需改平台/同机 colocate，或只支持单语言源码 merge，或忽视 provider 资源上限导致 **resource fragmentation**。

## 关键观察 / 隐含假设

- **观察 1**：同 tenant 同 workflow 内，per-function 容器隔离过强；库函数式 in-process call 是合理 trust model。
  - **依赖假设**：敏感函数 opt-out merge；tenant 内互信。
  - **可能失效场景**：含 secrets 的函数被误 merge；merge 后单 crash 拖垮 subgraph。
- **观察 2**：多数语言可编译到 [[LLVM]] IR，REST 交互仅是 JSON 字符串——可在 IR 层替换 libcurl 为 direct call 并跨语言类型桥接。
  - **依赖假设**：函数仅通过 REST 互调，无 shared memory/SQS 等外部中介。
  - **可能失效场景**：新语言 backend 异常；外部 broker 调用不可合并。
- **观察 3**：merge 决策应基于 **runtime profiling**（call graph + peak memory/CPU），且允许子图重叠与高 fan-out 函数不合并。
  - **依赖假设**：OpenTelemetry/nginx tracing 开销可接受；约 1 分钟 offline merge 编译可接受。
  - **可能失效场景**：workload 剧变需频繁 reconsider；LLVM pass 延迟阻碍快速迭代。

## 核心方法

1. **Profiling**：透明 tracing 建 call graph（边权=频率）+ cAdvisor 资源峰值。
2. **Constraint-aware merging**：rooted DAG 聚类，满足 per-subgraph CPU $C$ 与 memory $M$（区分 sync/async 内存语义），最小化跨组边权；允许重叠。
3. **LLVM transformation**：重命名、HTTP→call、跨语言 JSON string 翻译、DCE/library dedup/debloat。
4. **Transparent deploy**：更新 entry point，scheduler 无感；workload 变化时 re-merge。

1.8K C++ + 1.7K Bash/Python；Fission/OpenFaaS/OpenWhisk 零修改。

## 设计取舍

- **In-process merge vs container isolation**：极致性能 vs fault blast radius。
- **LLVM IR vs source-level**：跨语言 vs 编译链脆弱性。
- **Opt-in merge flag**：安全默认 vs 开发者负担。
- **~1min compile**：background merge 可接受，非实时。

## 实验与结果

- Median workflow completion：**45.63%–70.95%** faster。
- Throughput：**2.05×–12.87×**（同资源）。
- DeathStarBench 三应用（C++/Rust）；跨 C/C++/Go/Rust/Swift merge 验证。
- Invocation：毫秒→**纳秒**。

## Critical Analysis

### 论证链条

「invocation 主导短函数 workflow → IR merge + resource-aware clustering → latency/throughput」在 DeathStarBench 类应用闭合。向 general enterprise workflow 外推需注意 external service 与长函数占比。

### 假设压力测试

- Merge 后 fault isolation 消失——论文称 open question，生产需谨慎。
- Resource model 若低估 peak memory 会导致 OOM kill 整个 merged function。
- 1 分钟 compile 对 CI/CD 频繁更新不友好。

### 实验可信度

- 三平台零修改部署加分；DeathStarBench 代表 microservice FaaS。
- 与 Nightcore/Faastlane 等定性对比充分，head-to-head 数字有限。
- 缺少 multi-tenant 安全渗透测试。

### 系统性缺陷

- 论文未讨论 merge 后 observability（per-function trace 归因）。
- LLVM 版本升级可能 break pass——维护成本未量化。
- Graceful degradation on partial crash 未解决。

## 局限与 Future Work

- **局限**：外部服务交互不可 merge；~1min compile；crash blast radius；仅测五语言。
- **Future work**：fault domain 隔离 merge；更快 LLVM pass；与 workflow spec（Step Functions）集成。

## 相关

- **相关概念**：[[Serverless]]、[[FaaS]]、[[LLVM]]、[[Cold-Start]]、Workflow
- **同类系统**：Faastlane、Faasm、Fusionize、Nightcore、SONIC
- **同会议**：[[SOSP-2025]]