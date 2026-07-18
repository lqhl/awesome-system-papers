---
type: concept
aliases: [FL, Federated-Learning-System]
last_updated: 2026-07-18
tags: [machine-learning, distributed-systems, privacy, edge]
---

# Federated Learning

> Federated learning coordinates model updates from distributed clients without centralizing raw data; it couples optimization with device heterogeneity, communication, privacy, participation, and failure behavior.

## 核心思想

A server selects clients, distributes a model, aggregates returned updates, and repeats. The abstraction does not itself guarantee privacy or robustness: secure aggregation, differential privacy, participant selection, and systems scheduling provide separate properties under stated threat and availability models.

## 为什么重要

Real cross-device deployments face intermittent connectivity, non-IID data, limited uplink, dropouts, and resource-constrained clients. A protocol speedup or learning result must state whether it is a timing model, simulation, or deployment measurement and which server/client adversaries it covers.

## 关键观察 / 隐含假设

- **观察**：aggregation overhead and privacy requirements can dominate the round. [[DISAGG-MLSys26]] evaluates a committee-based secure-aggregation design under parameterized timing and simulation boundaries.
- **观察**：client heterogeneity and participation affect systems policy. [[PLayer-FL-MLSys26]] and [[FLoRIST-MLSys26]] study federated-system design contexts.
- **假设**：local training and aggregation improve a common objective despite data and availability variation. [[AssyLLM-ATC25]] and [[SONAR-MLSys26]] expose workload/system-specific boundaries.

## 设计空间与取舍

- **Privacy vs communication/compute**：secure aggregation and privacy mechanisms add protocol and endpoint cost.
- **Synchronous vs asynchronous participation**：asynchrony reduces waiting but changes staleness and correctness assumptions.
- **Statistical utility vs systems feasibility**：model convergence, data heterogeneity, and device availability need joint evaluation.

## 引用本概念的论文

- [[DISAGG-MLSys26]] — secure aggregation under a federated threat model.
- [[PLayer-FL-MLSys26]] — federated system design.
- [[FLoRIST-MLSys26]] — federated learning/runtime context.
- [[AssyLLM-ATC25]] — asynchronous/distributed learning boundary.
- [[SONAR-MLSys26]] — federated-system behavior.
