---
type: paper
name: EarthSight
full_title: "EARTHSIGHT: A Distributed Framework for Low-Latency Satellite Intelligence"
authors: [Ansel Kaplan Erol, Seungjun Lee, Divya Mahajan]
venue: MLSys
year: 2026
tags: [satellite, edge-computing, multi-task-learning, scheduling, orbital-edge]
source_pdf: "[[9bf31c7ff062936a96d3c8bd1f8f2ff3.pdf]]"
source_md: "[[9bf31c7ff062936a96d3c8bd1f8f2ff3]]"
---

# EARTHSIGHT: A Distributed Framework for Low-Latency Satellite Intelligence (MLSys 2026)

> **一句话总结**：将 LEO 卫星图像分析重构为「地面-轨道」联合调度问题，用多任务共享 backbone + 地面 DNF 查询调度 + 在轨 utility-driven filter 排序，把端到端 P90 延迟从 SERVAL 的 51 min 降到 21 min，单图 compute 降 1.9×。

## 问题

LEO 纳卫星采集的图像受限于下行窗口（每次 10-15 min 传输数十 GB），传统先下传再分析的流程导致灾害响应延迟数小时到数天。已有 orbital edge computing（OEC）方案在星上做 inference 排序，但把每颗卫星当作孤立节点，忽略全星座下行争用；且多为单任务，单幅图跑多个任务（船只检测、尾流、非法捕捞）会造成冗余，超出卫星 1-5 W 的功耗预算。

## 核心方法

EARTHSIGHT 把图像分析建模为横跨地面与轨道的分布式决策问题，三大组件：

**1. 多任务在轨 inference**：EfficientNet 共享 backbone + 多个轻量 MLP task head（hard parameter sharing），按领域（海事、沙漠等）分组共享 backbone，摊销计算；支持仅 uplink 新 head 而无需重传 backbone。

**2. 地面站 query scheduler**：
- 采用查询驱动接口，每个 query 指定 AOI、优先级 1-5 和 DNF 布尔表达式（如 "cloud-free AND ship present AND military"）。
- Look-ahead simulator 预测每个下行窗口的优先级门限 $p^*$ 和 rejection rate $r_{reject}$。
- 按 Algorithm 1 为每个 planned capture 构造 DNF 公式 $\Phi_{loc}$，汇总所有覆盖该位置的 query。
- Schedule 压缩：6 小时内 unique 公式通常 <256，用 1 byte index 编码，平均 25× 压缩。

**3. 在轨 adaptive filter ordering**：
- Stochastic Boolean Function Evaluation（NP-hard）问题用贪心近似。
- Utility：$U_\Phi(f_i, \mathcal{E}) = \frac{(1 - p_i) \cdot tpr_i \cdot n_i}{t_{eff}(f_i, \mathcal{E})}$，每步选单位时间信息增益最高的 filter。
- 置信度 $C_\Phi(\mathcal{E})$ 跨越 $[\beta, \alpha]$ 时停止；$\alpha$ 根据当前功率与 rejection 偏差动态调整。
- CPU-xPU pipelined 执行：xPU 跑 filter $F_k$ 的同时 CPU 预取下一个 $F_{k+1}$ 以及备选项，隐藏决策延迟。

地面和轨道形成反馈回路：在轨运行的 rejection 比、$\alpha$ 调整、compute 利用率在下行时汇总给地面，地面重新校准 filter 成功概率和 look-ahead simulator。

## 关键结果

- P90 端到端延迟（first contact 到 delivery）从 SERVAL 基线的 51 min 降到 21 min。
- 单图平均 compute 时间降低 1.9×。
- 三个多任务场景（基于硬件 enhanced 仿真）均验证有效。
- Schedule 压缩达 ~25×，可在内存受限的纳卫星上承载 >16,000 幅图像的 DNF 公式。

## 相关

- **相关概念**：[[Multi-Task-Learning]]、[[Orbital-Edge-Computing]]、[[Scheduling]]
- **相关方法**：DNF filter formula、Stochastic Boolean Function Evaluation、Utility-driven greedy ordering
- **同会议**：[[MLSys-2026]]
