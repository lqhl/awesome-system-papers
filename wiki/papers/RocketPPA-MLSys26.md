---
type: paper
name: RocketPPA
full_title: "Unified LLM Model for Power, Performance, and Area Prediction from Hardware Code"
authors: [Armin Abdollahi, Mehdi Kamal, Massoud Pedram]
venue: MLSys
year: 2026
tags: [eda, verilog, llm, ppa-estimation, contrastive-learning]
source_pdf: "[[9778d5d219c5080b9a6a17bef029331c.pdf]]"
source_md: "[[9778d5d219c5080b9a6a17bef029331c]]"
---

# Unified LLM Model for Power, Performance, and Area Prediction from Hardware Code (MLSys 2026)

> **一句话总结**：PPA 同时依赖 RTL 与 synthesis regime（node × objective），RocketPPA 用 LLaMA-3.1-8B + LoRA 编码 Verilog 片段、MoE 回归头 + 三策略 contrastive learning，在 15nm/45nm × area/delay-opt 四条件下 pass@10% 比 MetRex 平均高 **9.4pp**（delay），推理 **0.12s/design**（**~20×** CircuitFusion），LORO 跨 regime 退化极小。

## 问题与动机

VLSI 早期 PPA 估计依赖抽象模型/部分综合，难捕捉复杂电路交互，且需大量校准。Verilog RTL 到 PPA 还**强条件于** technology node 与 optimization objective（同模块 area-opt vs delay-opt 结果迥异）。

近年 [[LLM]] 用于 Verilog 生成/理解，但既有 PPA 估计器（MasterRTL SOG、CircuitFusion 多模态、MetRex）多在**固定 node/flow** 下做数值回归，用 MSE/相关而非决策导向的 pass@τ，且跨 regime 需多模型。

作者 claim：单一 **condition-aware** 模型，直接吃 raw Verilog + `[NODE=15nm][OBJ=area-opt]` token，同时预测 power/delay/area，sub-second 推理支撑设计空间探索。

## 关键观察 / 隐含假设

- **观察 1：语义相似设计（同模块不同综合条件、相近 PPA、同结构复杂度类）应在 embedding 空间邻近，可提升跨 regime 泛化。** t-SNE 显示 contrastive 后同设计跨 node/objective 聚类，结构类分离，gate count 平滑变化。
  - **依赖假设**：512-token 片段 + mean-pool 可覆盖长 RTL 全 token；五类结构 archetype（tiny comb、FSM 等）足以刻画电路空间。
  - **可能失效场景**：工业 RTL 含大量宏/黑盒 IP，纯文本片段丢失层次与约束信息。

- **观察 2：PPA 残差 heavy-tailed，Huber + log-zscore 比纯 MSE 稳定。** 少数激进综合优化产生大 outlier。
  - **依赖假设**：训练标签来自 Synopsys Design Compiler 商业流，与目标用户环境一致。
  - **可能失效场景**：不同 EDA 工具/约束脚本导致标签分布漂移；需 5–10% 校准样本（跨 node 实验 **4.2%** 退化 @5% 校准）。

- **假设 1：MoE（N=6, top-k=3）比同等 active FLOPs 的 dense MLP 更能专精不同电路 archetype。**
  - **证据强度**：**强**——Expert 2 主导 combinational、Expert 3 主导 counter/shift（Table 6）；pass@10% 全面优于 dense head。

- **假设 2：Contrastive（λ=0.5）在监督之外贡献 **~2.5pp** pass@10%，推理无额外开销。**
  - **证据强度**：**中**——Table 7 ablation；PPA-based positive pairs 单项贡献最大（Table 8）。

## 核心方法

**架构**：CodeLlama/Llama backbone + LoRA(r=16)；长 Verilog 切 **512-token** 片段独立编码后 mean-pool；条件 token  prepend；last-layer hidden average pool → **MoE 回归头**（6 experts, inference top-3），每 metric 独立头。

**Contrastive**：三策略构造 positive pairs——(1) cross-condition 同设计不同 (node, obj)；(2) PPA 三指标均在 τ=0.15 内；(3) 结构复杂度类对齐。投影头 128-D + NT-Xent，训练用、推理丢弃。

**数据**：>20k 模块（MG-Verilog、GitHub、VeriGen），LLM repair pipeline 保证可综合；每模块最多 4 条 DC 标签；失败综合丢弃。

## 设计取舍

- **端到端 RTL vs SOG/图特征**：避免 CPU 密集预处理（MasterRTL **514s** vs RocketPPA **16s**/138 designs），但牺牲显式结构归纳偏置。

- **片段池化 vs 全长 context**：保 batch 多样性与 contrastive in-batch negatives，依赖片段覆盖完整性。

- **Pass@τ vs MAE**：对齐 EDA 决策（「是否在 10% 误差内」），但弱化细粒度排序能力。

- **Static + dynamic power**：MetRex 仅 static；RocketPPA 预测 total power，更实用但标签噪声更大。

- **边界条件**：45nm planar + 15nm FinFET 训练；7nm ASAP7 扩展实验 pass@10% **~53–70%**；VerilogEval L3 最难子集。

## 实验与结果

- **VerilogEval 138 designs, pass@10% 宏平均**：Area **71.6%**（+13.6pp vs MetRex）、Delay **57.2%**（+9.4pp）、Total power **55.0%**（+9.9pp vs MasterRTL）、Static **56.7%**（+14.7pp vs MetRex）。
- **pass@20%**：Area **84.6%**、Delay **74.9%**、Power **70.8%**。
- **延迟**：A6000 上 **0.12s/design**，**>20×** MetRex/CircuitFusion，**~30×** MasterRTL；全 Yosys+OpenSTA **680s**。
- **LORO 跨 regime**：pass@10% 降幅 modest（Table 4）；跨 node zero-shot 弱，5%/10% 15nm 校准仅 **4.2%/2.7%** 退化。
- **Ablation**：MoE 一致优于 dense；λ=0.5 最优；六 expert 饱和。

## Critical Analysis

### 论证链条

「PPA 条件性 + RTL 语义 + 设计空间结构 → condition-aware LLM + contrastive + MoE」链条清晰；商业综合标签支撑实用性。Level-3 VerilogEval 上优势保持且掉点小于 baselines，支撑复杂设计 claim。

### 假设压力测试

- **已证明**：四 condition per-condition 表（Table 3）；LORO 与 7nm 扩展。
- **可能失效**：未见过 RTL 风格（论文承认 industrial OOD）；极大设计（>607 gates L3）仍挑战 delay；仅两 node 训练时 far node 需校准。
- **未覆盖**：时序 closure 后 signoff 级精度、物理布局后 PPA。

### 实验可信度

Baselines 同数据重训、同 condition 注入方式，公平性较好。10 seed 方差 <1%。测试集固定。Pass@τ 对 outlier 友好，可能高估「近最优」比例。

### 系统性缺陷

仍依赖综合流 ground truth——无法替代 signoff。模块级归因需层次解析多次推理（10–20 子模块 **1–2s** 可接受）。论文未讨论错误预测的代价不对称（delay miss vs area miss）。

## 局限与 Future Work

- **局限 1**：训练 corpus 三公开源，工业编码风格 OOD 需 few-shot 校准。
- **局限 2**：聚合池化设计的模块级归因非原生，需后处理层次遍历。
- **Future work 1**：在真实 chip 项目 trace 上测 pass@τ 与设计师决策一致性（human-in-loop study）。
- **Future work 2**：与生成式 RTL（[[ChipNeMo]] 类）闭环：预测-编辑-再预测的设计空间搜索。

## 相关

- **相关概念**：[[LLM]]、electronic-design-automation
- **同类系统**：MetRex、MasterRTL、CircuitFusion
- **同会议**：[[MLSys-2026]]