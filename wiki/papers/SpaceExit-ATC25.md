---
type: paper
name: SpaceExit
full_title: "SpaceExit: Enabling Efficient Adaptive Computing in Space with Early Exits"
authors: [Jiacheng Liu, Xiaozhi Zhu, Tongqiao Xu, Xiaofeng Hou, Chao Li]
venue: ATC
year: 2025
tags: [satellite, edge-computing, early-exit, adaptive-inference, dvfs]
source_pdf: "[[atc2025-liu-jiacheng.pdf]]"
source_md: "[[atc2025-liu-jiacheng]]"
---

# SpaceExit: Enabling Efficient Adaptive Computing in Space with Early Exits (ATC 2025)

> **一句话总结**：在轨边缘计算（OEC）系统集成 multi-exit 检测器 + 复杂度感知调度 + 动态资源控制，比 SOTA 静态 OEC 设计平均提升性能 24.3%（最高 37.6%）。

## 问题

LEO 地球观测卫星每天产 TB 级图像，下行带宽仅 0–220 Mbps；现有 OEC 系统（TargetFuse、Kodan）依赖静态模型与预设规则，模型加载开销远大于推理；切错模型时性能急剧下降。同时卫星面临 -22 °C ~ +77 °C 极端温度、太阳能波动 + 阴影期、单星多异构 chip（Jetson Nano + Xavier NX）的资源约束。

## 核心方法

SpaceExit 三模块：

- **GCAD（Geospatial-Contextual Adaptive Detector）**：multi-scale 主干 + 多 early-exit head；router 用 squeeze-and-excitation 风格（多尺度 pooled feature 拼接 + 两层 MLP + sigmoid）输出 uncertainty score；推理时用一个 130 KB 的 MobileNet 分类 land/ocean，结合 GIS 数据库的地理 embedding（terrain、land cover、POI，全球 < 100 MB）调整退出阈值，复杂城市区域更深推理、海面早退。
- **CATS（Complexity-Driven Adaptive Task Scheduler）**：颜色方差启发式估计 tile 复杂度 $d_t$，按 $w_t = w_{base}/\sqrt{d_t}$ 自适应 tiling；按 $\sigma(i)=\arg\min_j n_j/\nu_j$ 分配到 Nano/Xavier 队列，工作量按 $n_j = \sum d_r |r|$ 加权；队内优先级 $s(r) = \eta/(d(r)-t) + \lambda d_r$ 兼顾 deadline 紧迫与复杂度。
- **SRAC（Satellite Resource Adaptive Controller）**：按 $\partial X_i/\partial P_i$ 在线回归分配能量；DVFS + 学习的热-功率模型 $T_i(t+1)-T_i(t) = \alpha[P_i - \beta(T_i^4 - T_{amb}^4)]$ 主动节流；按 $\tau = \tau_{base}\cdot\gamma P_{current}/P_{nominal}$ 收紧/放宽 GCAD 早退阈值；下行带宽用三优先级队列（计算结果 > 遥测 > 不确定性评分图像）。

testbed：Jetson Nano（10 W）+ Jetson Xavier NX（20 W），DOTA 数据集。深度细节见 [[atc2025-liu-jiacheng]]。

## 关键结果

- 比 BentPipe / SpaceOnly / Kodan / TargetFuse 的 SOTA 平均提升 24.3%，最高 37.6%。
- Geospatial router 仅 130 KB（占完整模型 2.4%）。
- GIS 数据库批量查 50 个 embedding，每分钟一次访问，开销可忽略。

## 相关

- **相关概念**：[[Early-Exit]]、[[Edge-Inference]]、[[DVFS]]、[[Adaptive-Inference]]
- **同类系统**：TargetFuse、Kodan、SpaceOnly
- **同会议**：[[ATC-2025]]
