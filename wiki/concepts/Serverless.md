---
type: concept
aliases: [Function-as-a-Service, FaaS-Platform]
last_updated: 2026-07-18
tags: [cloud, faas, isolation, scheduling]
---

# Serverless

> Serverless systems execute demand-driven functions while hiding server management behind scheduling, isolation, startup, and billing abstractions; their core systems trade-off is elasticity versus cold-start, resource, and isolation overhead.

## 核心思想

Functions are scheduled onto transient or reused execution environments. The platform must decide when to provision, cache, checkpoint, migrate, or reclaim those environments while preserving isolation and request latency. The abstraction is broader than a particular runtime: containers, microVMs, unikernels, and language runtimes can all implement it.

## 为什么重要

Serverless makes deployment and elasticity accessible, but turns startup, state, data locality, and tail latency into platform-level concerns. The papers in this corpus use it for both short functions and more stateful services, exposing that a single cold-start number is not a complete evaluation.

## 关键观察 / 隐含假设

- **观察**：isolation mechanism affects startup and steady-state cost. [[Dandelion-SOSP25]] and [[Aegaeon-SOSP25]] explore execution-environment trade-offs.
- **观察**：bursty demand makes placement and resource reuse central. [[BurstComputing-ATC25]] and [[Poby-ATC25]] study scheduling-related system behavior.
- **假设**：functions are sufficiently stateless or state can be externalized cheaply. [[Quilt-SOSP25]] and [[RTSFaaS-ATC25]] show why state and runtime boundaries alter that assumption.

## 设计空间与取舍

- **Cold start vs warm pool cost**：prewarming reduces latency but reserves resources.
- **Strong isolation vs reuse**：microVM/container/unikernel choices change startup, security, and operational complexity.
- **Stateless interface vs state locality**：external state simplifies scaling but can add data and coordination overhead.

## 引用本概念的论文

- [[Dandelion-SOSP25]] — serverless execution-environment design.
- [[BurstComputing-ATC25]] — burst scheduling and resource management.
- [[Aegaeon-SOSP25]] — isolation and execution trade-offs.
- [[RTSFaaS-ATC25]] — runtime/FaaS system boundary.
- [[Quilt-SOSP25]] — stateful-system considerations under serverless abstractions.
