---
type: concept
aliases: [CUDA-Graphs]
last_updated: 2026-07-30
tags: [gpu, runtime, scheduling, kernel-launch]
---

# CUDA Graph

> CUDA Graph 把一组 GPU 操作及依赖捕获为可重复 replay 的 DAG，以一次 dispatch 替代大量 CPU kernel launch；收益来自降低 launch gap，代价是地址、shape、控制流和资源生命周期更静态。

## 核心思想

capture 阶段记录 kernel、memcpy 与依赖，实例化后可反复 replay。它最适合迭代结构固定、kernel 短且 CPU launch 成本可见的训练或推理。实际框架还需维护静态 input placeholder、RNG、allocator 和 mutable parameter；“能 capture”与“启用后更快”是两个不同问题。

## 为什么重要

更快 GPU 和更细算子让 5–10µs launch 成本成为显著空隙。[[GraCE-OSDI26]] 系统性证明 CUDA Graph 的主要障碍已从 API 使用转向编译器与 runtime：CPU tensor 会阻止整图 capture，大 tensor placeholder copy 会吃掉 replay 收益，而且 25% 候选 graph 在启用后反而变慢。

## 关键观察 / 隐含假设

- **一处高层 placement 可阻断数百 kernel 的 capture。** [[GraCE-OSDI26]] 的 XLNET 案例因一个 CPU tensor 丢失 413 个 kernel 的 graph coverage。
- **mutable 参数不一定需要复制数据。** GraCE 以 pointer indirection 将最高约 1 GB replay copy 降到数百 bytes。
- **graph capture 必须做收益判断。** GraCE 发现 29/116 候选 graph 负收益，最差退化 397%，用 compile-time profile 选择性部署才避免 regression。
- **隐含假设**：shape、控制流和成本分布稳定，capture/compile 能被足够多 iteration 摊销；dynamic batching 和多租户干扰会削弱它。

## 设计空间与取舍

- **整图与子图 capture**：整图 launch 最少但静态约束强；子图更灵活，却保留更多 CPU 调度。
- **静态 buffer copy 与 pointer indirection**：前者简单可靠，后者少搬移但需改 kernel signature 或 graph node 参数。
- **全量启用与 profile-guided selection**：选择性部署避免回归，但增加编译时间并依赖 profile 代表性。
- **CUDA Graph 与 persistent mega-kernel**：[[MPK-OSDI26]] 指出 graph 仍保留 kernel 边界，mega-kernel 能进一步暴露 SM-level pipeline，却更侵入且影响多租户。
- **单请求与 continuous batching**：静态 replay 适合固定 iteration；请求加入/退出和 shape 变化需要 graph pool、padding 或重新 capture。

## 引用本概念的论文

- [[GraCE-OSDI26]] — 编译器扩大 capture coverage、parameter indirection 消除 copy、selective deployment 避免 regression
- [[DynaFlow-MLSys26]] — 动态 GPU 执行与 graph/runtime
- [[Torpor-ATC25]] — GPU 调度与执行开销
- [[LAPS-MLSys26]] — launch/调度路径优化
- [[GPreempt-ATC25]] — GPU 抢占与 graph 执行张力
- [[EventTensor-MLSys26]] — event-driven tensor runtime
- [[KTransformers-SOSP25]] — 用单 CUDA Graph 降低 MoE decode 的大量 kernel launch
- [[MPK-OSDI26]] — 以 persistent mega-kernel 作为跨 kernel boundary 的对照路线

## 已知局限 / 开放问题

- dynamic shape、control flow、LoRA adapter 和请求 churn 下的 graph cache 命中与重编译成本不清晰。
- capture 对 alias、host observability、allocator 与 RNG 的正确性面较大，需要 differential test 和形式化约束。
- compile-time profile 在 multi-tenant、温控降频或驱动升级后可能漂移。
- graph replay 的资源占用与抢占、公平性、MIG 隔离之间仍缺少 production 证据。
