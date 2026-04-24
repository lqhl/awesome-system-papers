---
type: paper
name: SysGPT
full_title: "Principles and Methodologies for Serial Performance Optimization"
authors: [Sujin Park, Mingyu Guan, Xiang Cheng, Taesoo Kim]
venue: OSDI
year: 2025
tags: [performance-optimization, methodology, llm-assistant, systems-research]
source_pdf: "[[osdi25-park-sujin.pdf]]"
source_md: "[[osdi25-park-sujin]]"
---

# Principles and Methodologies for Serial Performance Optimization (OSDI 2025)

> **一句话总结**：把系统串行性能优化归结为 3 条原则（removal / replacement / reordering）+ 8 种方法论（batching, caching, precomputing, deferring, relaxation, contextualization, hardware specialization, layering），用过去十年 477 篇 OSDI/SOSP 论文验证框架覆盖性，并 fine-tune 出 SysGPT 做工程侧优化建议。

## 问题

系统性能优化长期依赖直觉和个人经验，社区缺少**结构化的方法论**来回答「还能怎么优化」。虽然 profiling 工具已经很成熟，设计解决方案这一步仍然开放、混沌。Amdahl 律告诉我们串行部分主宰上限；但「串行部分怎么系统地优化」缺少清晰的框架。本文尝试把十年系统论文里的散落手法提炼成一套完整、可操作的 checklist。

## 核心方法

作者首先形式化：把串行段视为任务序列 $S_n = \{t_i\}$，优化 $F(S_n)$ 的手段只可能是——**移除任务** $(P_{rm})$、**替换任务** $(P_{rep})$、**重排任务** $(P_{ord})$。从这三条 meta-原则衍生出 8 种 actionable methodologies：

- **Batching**：合并重复代价（同时覆盖 rm/rep/ord）；
- **Caching**：跨时间消除重复计算（rep）；
- **Precomputing**：把工作移到 epoch 前或关键路径外（rm/ord）；
- **Deferring**：把工作推后（rm/ord），常搭配乐观执行和 batching；
- **Relaxation**：放弃精确/一致性/可用性换取短路径（rep/rm），采样、弱一致等；
- **Contextualization**：把运行时上下文接入决策，用 eBPF、profiling 等缩小 workload/设计语义差；
- **Hardware specialization**：把任务落到更合适的硬件（FPGA、SmartNIC、NVM、NUMA）；
- **Layering**：bypassing / delayering / decoupling 三种子模式调整层级结构。

作者逐一审阅了 2013–2022 的 **477 篇 OSDI/SOSP 论文**：271 篇不涉及性能，其余 206 篇全部可归入这 8 个方法论，平均每篇使用 2.01 种。论文同时展示了两个 case study：SOSP'21 文件/存储系统的全清单注解，以及对 OSDI'22 SynCord 的方法学对照（指出其可以进一步加 caching 和 delayering）。

基于这十年的分析语料，作者 fine-tune GPT-4o 得到 **SysGPT**，给定「问题描述 + 观察」，它会输出标注到方法论的多条优化建议。用 2023–2024 年的 OSDI/SOSP 论文做保留测试集做定性/定量评估。

## 关键结果

- 10 年 477 篇 OSDI/SOSP 论文中 **206 篇性能优化全部能归入 8 个方法论**，框架完备性得到经验验证
- SysGPT 在 precision/recall/F1 上在多种温度和采样配置下持续优于 GPT-4 基线和 few-shot prompting
- 定性对比显示 SysGPT 的建议更具体、更对齐真实研究工作（无直接训练泄漏）
- 已公开数据集和评测基准，方便后续系统 + LLM 交叉方向研究

## 相关

- **相关概念**：Amdahl's law、kernel bypass、eBPF、DPDK、kernel synchronization、fine-tuning
- **相关方向**：AI4Systems、[[AI-Scientist]] 类自动化研究助手
- **同类 taxonomies**：Brewer/Stonebraker 的系统设计原则
- **同会议**：[[OSDI-2025]]
