---
type: paper
name: PROMPTS
full_title: "PROMPTS: Performance Optimization via Multi-Agent Planning for LLM Training and Serving"
authors: [Yuran Ding, Ruobing Han, Xiaofan Zhang, Xinwei Chen]
venue: MLSys
year: 2026
tags: [llm-training, auto-tuning, sharding, multi-agent, tpu]
source_pdf: "[[03afdbd66e7929b125f8597834fa83a4.pdf]]"
source_md: "[[03afdbd66e7929b125f8597834fa83a4]]"
---

# PROMPTS: Performance Optimization via Multi-Agent Planning for LLM Training and Serving (MLSys 2026)

> **一句话总结**：多 agent 框架用 Analyzer（读 XProf 瓶颈）+ Proposal（RAG 知识库）一次调用给出 top-3 ICI-mesh 分片方案，8 个生产 workload 上 87.5% 的 top-1 与专家配置一致、搜索 effort 平均少 50 次、吞吐最高提升 434%，7/8 案例无需历史库精确匹配。

## 问题

大规模 LLM 训练/serving 的 hybrid parallelism（data/model/sequence/pipeline）组合爆炸，人工 profiling + 试错慢，黑盒搜索（Vizier 等）sample-inefficient 且换模型/硬件就要重搜。现有性能建模工具（dPRO、Lumos）能诊断瓶颈，但不会自动给出可执行的 sharding 方案。需要把专家推理嵌入自动化流程，在保持可解释性的同时大幅剪枝搜索空间。

## 核心方法

**PROMPTS**（PeRformance Optimization via Multi-Agent Planning）用 Google ADK 编排三类 agent：

- **Analyzer Agent**：读 XProf KPI、HLO profile、roofline 与实验配置，输出 compute/memory/communication 瓶颈分类
- **Proposal Agent**：RAG 检索历史优化案例 + 专家文档，结合诊断生成 **3 个** ici_mesh 配置及文字 justification
- **Coordinator + Sharding Memory**：串联工作流并持久化 tool call 审计轨迹

当前聚焦 **ICI-mesh sharding**（决定 memory fit 与通信拓扑上限）；batch size、compiler flag 等维度通过扩展知识库接入。有效性由 TPU compiler 交叉编译自动校验。

与 GSPMD/Partir 等 hybrid partitioning 正交：PROMPTS 自动化「人工 annotation」阶段，黑盒搜索再在剪枝后的子空间细调。

## 关键结果

8 个真实生产 case（2–2048 TPU、v5p/v5e/v6e/tpu7x、2D/3D Torus、dense + [[MoE]]、pretrain/SFT/serving）：

- **100%** 案例：top-3 建议中包含工程师已采纳的生产配置
- **87.5%** 案例：agent **top-1** 即生产配置；7/8 一次试验即命中
- 相对 exhaustive blackbox：搜索空间最多 165 个有效配置，agent 平均只评 **1** 个即找到最优
- 吞吐提升：**40–434%**（Case 5 专有 MoE +434.75%；Case 6 推理 +182.86%）
- 平均 compilability 69%，但足以完成任务；单次调用 <1 min vs 工业黑盒 5 min–数小时
- 7/8 案例无历史库精确匹配，靠 first-principles 推理泛化

## 相关

- **相关概念**：[[MoE]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]
- **同类系统**：Alpa、FlexFlow、GSPMD、Vizier、Metis、Sailor
- **同会议**：[[MLSys-2026]]