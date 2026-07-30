---
type: entity
kind: tool
aliases: [Enhanced-Read-Only-File-System]
status: active
last_updated: 2026-07-18
tags: [filesystem, read-only, compression, deployment]
---

# EROFS

> EROFS 是一个只读文件系统，用于紧凑的、可部署的映像；在这个语料库中，它是不可变数据布局、压缩和图像服务权衡的参考点。

## 是什么

只读映像避免了更新路径元数据和一致性成本，这使得它们对系统映像、容器和不可变工件具有吸引力。它们的性能和空间行为取决于压缩格式、块布局、缓存状态以及可变状态在图像外部的分层方式。

## 关键观察 / 隐含假设

- **观察**：不可变的布局可以简化服务，但将更新和分层工作转移到其他地方。 [[CoFS-FAST26]] 研究此边界下的文件系统/图像路径设计。
- **假设**：压缩和布局的优势对于部署工作负载来说仍然存在。 [[RubikFS-FAST26]] 说明了为什么访问模式和图像合成需要单独评估。

## 演进时间线

- 2026 FAST：[[CoFS-FAST26]] — image/filesystem path design involving EROFS.
- 2026 FAST：[[RubikFS-FAST26]] — filesystem layout and deployment trade-offs.

## 相关概念

- [[FUSE]]、[[Page-Cache]]、[[NVMe]]

## 相关论文

- [[CoFS-FAST26]] — immutable-image filesystem design.
- [[RubikFS-FAST26]] — filesystem layout and access-path analysis.
