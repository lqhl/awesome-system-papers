---
type: paper
name: 2DFS
full_title: "On-Demand Container Partitioning for Distributed ML"
authors: [Giovanni Bartolomeo, Navidreza Asadi, Wolfgang Kellerer, Jorg Ott, Nitinder Mohan]
venue: ATC
year: 2025
tags: [container, oci, distributed-ml, edge, image-format]
source_pdf: "[[atc2025-bartolomeo.pdf]]"
source_md: "[[atc2025-bartolomeo]]"
---

# On-Demand Container Partitioning for Distributed ML (ATC 2025)

> **一句话总结**：扩展 OCI 镜像格式加一层 `2dfs.field` 二维 allotment 矩阵，把模型 split / 权重 / 库解耦成可并行构建、独立缓存、按需 partition 的对象，14 个 ML 模型上构建快 56×（最高 120×）、缓存效率高 25×。

## 问题

分布式 ML（split computing / continuous retraining）需要把模型切成多个 split 部署到异构边缘设备，但容器作为事实标准存在严重摩擦：

- 每个 split 一张 Docker image → n 个 split 有 2^n 种 manifest 组合，预构建空间爆炸；
- ENv2L 模型 82 split 时单张 image 构建超过 4 分钟，更新一层就 cascade 失效全部上层；
- 替代方案：volume mount 边缘没对象存储；MLOps 拉权重无法被 container runtime 缓存。

OCI 的 layered 文件系统适合代码，不适合大文件 / 模型权重 / 驱动。

## 核心方法

**2DFS** 在 OCI 之上加一层 `2dfs.field` media type：

- **Allotment** 是稀疏矩阵中的格子（row, column, digest, diffid），存的是 `.tar.gz` blob；blob 之间满足交换律（commutative）、跨 image 复用、可序列化为标准 OCI layer；
- **Builder** 用 `2dfs.json` 描述符并行计算所有 allotment 的 DiffID 和 blob，三层 cache（key / blob / index），单 allotment 改动只 invalidate 自己；
- **Image Partitioning**：用语义 tag `tag--x1.y1.x2.y2` 让 registry 按矩形 sub-field 即时序列化出 OCI manifest（无需重建），任何 OCI runtime 透明拉取；
- **2DFS Registry** 在 OCI registry 上加 partitioner、语义 tag 解析、`2dfs.field` deserializer。

模型 split 用 Keras API 自动产生 `2dfs.json`，按 information bottleneck 切分。

## 关键结果

- **Build time**：14 个模型平均 16× 快于 Docker；ENv2L 100% split capacity 下 120× 快；41 个 split 一次构建 vs 41 张独立 Docker image。
- **Caching efficiency**：top-down 更新 25× 快，bottom-up 75× 快（Docker bottom-up 重建反而更便宜）。
- **Image download**：partition pull 比预构建 image 平均仅多 20 ms 延迟，bandwidth 持平，registry CPU 仅多 1%。
- **Edge inference**：10 台 Raspberry Pi 4B 部署支持端到端推理。

## 相关

- **相关概念**：[[Container]]、[[OCI-Image]]、[[Split-Computing]]
- **同会议**：[[ATC-2025]]
