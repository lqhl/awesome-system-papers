---
type: paper
name: TapML
full_title: "Productively Deploying Emerging Models on Emerging Platforms: A Top-Down Approach for Testing and Debugging"
authors: [Siyuan Feng, Jiawei Liu, Ruihang Lai, Charlie F. Ruan, Yong Yu, Lingming Zhang, Tianqi Chen]
venue: ISSTA
year: 2025
tags: [ml-deployment, testing, debugging, webgpu, model-porting, area/ai-infra]
source_pdf: "[[issta25-feng-tapml.pdf]]"
source_md: "[[issta25-feng-tapml]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-18
---

# TapML：新模型部署的自顶向下测试与调试（ISSTA 2025）

> **原题**：Productively Deploying Emerging Models on Emerging Platforms: A Top-Down Approach for Testing and Debugging

> **一句话总结**：TapML 观察到 WebGPU/Metal 等新平台最慢的不是逐算子实现，而是复合错误的测试定位；它从完整模型自动 carve 真实 operator tests，并按迁移比例逐步将 source backend 替换为 target backend，已作为 MLC-LLM 默认流程支撑两年内 27 架构、105 个模型、5 类平台。

## 问题与动机

bottom-up port 先补 operator 再组 model，手写 test 与真实 shape/layout 脱节；多个错误组合后难判断来自 model、operator 还是 backend。TapML 用完整 source execution 作为 oracle，自顶向下缩小迁移和调试范围（§1–3）。

## 关键观察 / 隐含假设

- **观察 1：真实 model execution 可自动产生高价值 operator test。** test carving 保留实际 shape/dtype/parameter。
  - **依赖假设**：source backend 正确且可运行，数值差异可定义容差。
- **观察 2：渐进 migration 比一次性 port 更容易定位 compound error。**
  - **可能失效场景**：source/target semantics 或 numerics根本不等价。

## 核心方法

TapML 从 source model trace carve tests，逐 operator/region迁移到 target，失败时通过最小新增 target surface定位；MLC-LLM 将其用于 CUDA之外的 Metal、WebGPU、mobile 等 backend（§3–5）。

## 设计取舍

- source oracle提高生产率，但会复制 source bug。
- realistic test覆盖常见 path，不保证 rare/dynamic path。
- gradual migration需混合 backend/interop支持。

## 实验与结果

- 在志愿者调试 benchmark 中，相对传统 bottom-up 方法平均 31 分钟/model、false-positive/false-negative error rate 58.2%/5.5%，TapML 的 localization latency 约 1 分钟、false-positive 10.3% 且无 false negative（表 6）。两年 MLC-LLM deployment workload 另覆盖 105 个模型、27 个 architectures、5 个 emerging platforms（§4–6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Top-down流程可大规模复用 | 105模型/27架构/5平台 | 单项目生态 | 中到强 |
| carving提高测试真实性 | trace-derived inputs/cases | source覆盖路径 | 强 |
| 降低总体开发成本 | 案例与流程比较 | 缺统一人时随机对照 | 中 |

## 批判性分析

### 论证链条

真实 trace 与渐进替换直接回应测试/调试瓶颈，大规模实践很有说服力；但生产率 headline 缺严格 developer-time baseline，部分收益可能来自 MLC 团队经验。

### 假设压力测试

随机控制流、训练、distributed state 与不可同时运行的 source/target 会削弱 carving/migration。

### 实验可信度

真实两年部署优于 toy benchmark；缺独立团队复现、缺陷漏检率和 false localization。

### 系统性缺陷

test artifact/version、敏感输入、oracle drift 与跨平台 tolerance 需要长期治理。

## 局限与后续工作

- **局限 1**：主要是 inference deployment 和 MLC-LLM。
- **后续工作 1**：公开 port trace，比较独立团队的人时、缺陷率与新平台迁移成功率。

## 相关

- **相关概念**：[[MLC-LLM]]、[[Tensor-Compilation]]、[[WebGPU]]
- **相关系统**：[[Relax-ASPLOS25]]
