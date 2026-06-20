---
type: paper
name: EarthSight
full_title: "EarthSight: A Distributed Framework for Low-Latency Satellite Intelligence"
authors: [Ansel Erol, Seungjun Lee, Divya Mahajan]
venue: MLSys
year: 2026
tags: [orbital-edge-computing, satellite, multi-task-learning, scheduling, low-latency]
source_pdf: "[[9bf31c7ff062936a96d3c8bd1f8f2ff3.pdf]]"
source_md: "[[9bf31c7ff062936a96d3c8bd1f8f2ff3]]"
---

# EarthSight: A Distributed Framework for Low-Latency Satellite Intelligence (MLSys 2026)

> **一句话总结**：将 onboard 卫星图像分析视为地–轨联合决策：共享 backbone 多任务推理 + 地面 lookahead 调度（DNF 查询、优先级阈值 p*）+ 轨上 utility 驱动 filter 排序与自适应置信阈值；相对 SERVAL baseline，单图平均计算时间 **1.9×** 降低，首触达到交付的 p90 尾延迟 **51→21 分钟**，且不丢弃图像、仅优化下传顺序。

## 问题与动机

LEO 遥感瓶颈已从采集转向分析：全量下传再地面处理延迟达数小时至数天，对灾害响应不可接受。既有 onboard ML 将每颗卫星视为孤立节点、单任务 pipeline，冗余算力与能耗高，且无法在星座层面协调有限 downlink 窗口。

## 关键观察 / 隐含假设

- **观察 1：单任务 onboard inference 在多应用并发时重复 backbone 计算，功耗与算力浪费显著。** 多任务 hard parameter sharing + 可条件执行的 head 可摊销特征提取。
  - **依赖假设**：任务可按域聚类（海事 vs 沙漠），域内特征可共享；head 依赖 backbone latent 的串行依赖可由调度解决。
  - **可能失效场景**：跨域强耦合任务强行单 backbone 会损精度或超边缘内存。

- **观察 2：filter 执行顺序影响期望计算量；最优顺序为 NP-hard SBFE，但地面提供的 pass 概率 pi 使 greedy utility 可早期拒绝低价值图像。** 错误先验只增加 false positive 带宽成本，β 固定保证 negative 判定逻辑正确。
  - **依赖假设**：历史/地面真值校准的 pi、tpri 足够准；utility 中 ni（DNF 项数）反映逻辑影响。
  - **可能失效场景**：新灾害类型分布漂移导致 pi 失效，α 动态升高→过多高优先级下传。

- **观察 3：星座级 downlink 竞争需要地面 lookahead 预测 p*（下一窗口可下传最低优先级）与 rreject，指导轨上算力预算。** 单星孤立优先级无法全局最优。
  - **依赖假设**：轨道与捕获计划可预测；模拟数小时在地面 O(分钟) 可完成。
  - **可能失效场景**：突发云量/姿态异常使预测失准；contact 间隔数小时放大调度误差。

## 核心方法

**多任务架构**：域专用 EfficientNet backbone + MLP head；图可只算 backbone 再稀疏执行所需 head（非 monolithic forward）。

**地面调度器**：布尔查询 + 优先级 p∈{1..5}；R-tree AOI 映射；lookahead 模拟 downlink 窗口与 priority-weighted 字节；生成 per-image DNF 公式与 p*、rreject、filter 成功率先验。

**轨上 runtime**：自适应上界 α（随功耗 rpower、deprioritize 率 rdep、目标 rreject 调整），固定小 β；greedy 选最大 Uϕ 的 filter；CPU–xPU pipeline 预取下一 filter；telemetry 回传校准地面模型。

**开销缓解**：DNF 查表压缩 ~25×；协调网络开销 <0.1% 日下传量。

## 设计取舍

- **不丢图 vs 纯 onboard 丢弃**：保全数据、只重排下传，赢得灾害场景召回，代价是带宽仍可能传低价值图（false positive）。
- **Heuristic filter 序 vs 精确 SBFE**：可实时，但次优期望计算量；依赖先验质量。
- **多 backbone 聚类 vs 单模型**：内存与 specialization 平衡，运维需 uplink 新 head。
- **边界条件**：Coral TPU / Jetson 实测 + trace-driven 模拟；未建模空间辐射/热力学全效应。

## 实验与结果

- 三场景（灾害、情报、城市）多任务模型：multi-task 在相近精度下更小 footprint、更短推理时间（Fig. 5）。
- 端到端：平均计算时间/图 **1.9×**；p90 首触→交付 **51→21 min** vs SERVAL。
- 算力占发电比例等系统指标在 Table 3（论文）；schedule 压缩与 pipelining 降低 idle。

## Critical Analysis

### 论证链条

「孤立 onboard 不够」→ 地轨联合调度 + 多任务 + utility 序，模拟与硬件 profiling 支撑尾延迟 claim。外推到千星规模需假设模拟器忠实反映 contact 争用。

### 假设压力测试

先验 pi 系统性偏差时主要伤效率不伤 negative 正确性（论文结构化论证）；α 升高可能导致带宽拥塞；多租户查询聚合复杂度未在生产验证。

### 实验可信度

沿用 OEC 社区主流 trace+硬件 方法；baseline SERVAL 强。缺真实在轨长期 A/B。

### 系统性缺陷

论文承认模拟难覆盖全部空间环境效应；operator 添加新任务的 4 选项流程增加运维负担。

## 局限与 Future Work

- **局限**：NP-hard 最优序用 greedy；在轨实测有限；多星座异构硬件泛化未充分验证。
- **Future work**：在线 pi 校正与鲁棒 utility；与下传压缩/语义摘要联合优化；多租户公平性与优先级博弈。

## 相关

- **相关概念**：[[Edge-Computing]]、[[Multi-Task-Learning]]
- **同会议**：[[MLSys-2026]]