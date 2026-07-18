---
type: entity
kind: tool
aliases: [torch, PyTorch-Framework]
status: active
last_updated: 2026-07-18
tags: [machine-learning, training, compiler, runtime]
---

# PyTorch

> PyTorch is the execution and programming stack through which many papers in this corpus express model computation, distributed training, extension kernels, and debugging or verification hooks.

## 是什么

Within this wiki, PyTorch is not treated as a single performance baseline. It is the common integration surface for model code, autograd, tensor storage, distributed collectives, custom operators, and compiler/runtime backends. A system contribution may preserve the PyTorch API while replacing a lower layer, or may expose a limitation of the framework's defaults.

The papers use different parts of the stack: training and sharding systems depend on distributed tensor semantics; kernel systems extend operator execution; verification and debugging tools observe or replay model behavior. Consequently, a result about PyTorch generally has an explicit version, backend, device, and workload boundary.

## 关键观察 / 隐含假设

- **观察**：framework compatibility is often the adoption boundary. [[veScale-FSDP-MLSys26]] retains a PyTorch `fully_shard`-style interface while changing placement and buffer management.
- **观察**：custom compiler/runtime paths can improve execution but must still satisfy PyTorch tensor, stream, and autograd semantics. [[Flashlight-MLSys26]] and [[TritorX-MLSys26]] use this boundary in different ways.
- **假设**：a PyTorch-level integration is portable enough to matter. [[TrainCheck-OSDI25]] and [[FPRev-ATC25]] show that the relevant correctness and reproducibility surface also includes versions, operators, and numerical behavior.

## 演进时间线

- 2025 OSDI：[[TrainCheck-OSDI25]] — treats framework behavior as part of reproducible training diagnosis.
- 2026 MLSys：[[veScale-FSDP-MLSys26]] — extends distributed sharding while preserving familiar framework integration.
- 2026 MLSys：[[Flashlight-MLSys26]] — examines specialized execution paths alongside the mainstream framework stack.

## 相关概念

- [[FSDP]]、[[Tensor-Parallelism]]、[[CUDA]]、[[Triton]]

## 相关论文

- [[veScale-FSDP-MLSys26]] — PyTorch-compatible structured FSDP backend.
- [[TritorX-MLSys26]] — compilation/execution work at the tensor-program boundary.
- [[FPRev-ATC25]] — numerical reproducibility analysis involving framework execution.
- [[TrainCheck-OSDI25]] — training error diagnosis across framework behavior.
- [[PyLO-MLSys26]] — PyTorch-oriented learning-system integration.
