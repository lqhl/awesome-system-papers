---
type: entity
kind: tool
aliases: [Enhanced-Read-Only-File-System]
status: active
last_updated: 2026-07-18
tags: [filesystem, read-only, compression, deployment]
---

# EROFS

> EROFS is a read-only filesystem used for compact, deployable images; in this corpus it is a reference point for immutable-data layout, compression, and image-serving trade-offs.

## 是什么

Read-only images avoid update-path metadata and consistency costs, making them attractive for system images, containers, and immutable artifacts. Their performance and space behavior depend on compression format, block layout, cache state, and how mutable state is layered outside the image.

## 关键观察 / 隐含假设

- **观察**：immutable layout can simplify serving but moves update and layering work elsewhere. [[CoFS-FAST26]] studies filesystem/image-path design under this boundary.
- **假设**：compression and layout benefits persist for the deployment workload. [[RubikFS-FAST26]] illustrates why access pattern and image composition need separate evaluation.

## 演进时间线

- 2026 FAST：[[CoFS-FAST26]] — image/filesystem path design involving EROFS.
- 2026 FAST：[[RubikFS-FAST26]] — filesystem layout and deployment trade-offs.

## 相关概念

- [[FUSE]]、[[Page-Cache]]、[[NVMe]]

## 相关论文

- [[CoFS-FAST26]] — immutable-image filesystem design.
- [[RubikFS-FAST26]] — filesystem layout and access-path analysis.
