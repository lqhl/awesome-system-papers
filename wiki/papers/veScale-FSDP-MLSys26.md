---
type: paper
name: veScale-FSDP
full_title: "veScale-FSDP: Flexible and High-Performance FSDP at Scale"
authors: [Zezhou Wang, Youjie Li, Zhiqi Lin, Jiacheng Yang, Cong Xie, "et al."]
venue: MLSys
year: 2026
tags: [fsdp, zero, distributed-training, sharding, pytorch]
source_pdf: "[[642e92efb79421734881b53e1e1b18b6.pdf]]"
source_md: "[[642e92efb79421734881b53e1e1b18b6]]"
---

# veScale-FSDP: Flexible and High-Performance FSDP at Scale (MLSys 2026)

> **一句话总结**：ByteDance 的新 FSDP backend，用 RaggedShard 自定义 block 粒度 + structure-aware planner + Distributed Buffer zero-copy 通信，相比 DeepSpeed ZeRO / FSDP1/2 / Megatron-FSDP 吞吐提升 5-66%，内存降低 16-30%，已在 10K+ GPU 生产部署。

## 问题

FSDP / ZeRO 是大模型训练首选，但现有系统都用 element-wise 或 row-wise 固定 sharding，和 structure-aware 训练方法冲突：
- **非 element-wise optimizer**（Shampoo、Muon）要 2D 矩阵完整做更新。
- **Block-wise quantization**（DeepSeek-V3 FP8 block、8-bit Adam）要 block 完整落在单设备。

shard 边界不对齐时要么强行改 model/optimizer 代码要么额外通信处理边界。性能层面 DeepSpeed/FSDP1 collective 碎片化，FSDP2 每参数 Shard(0) DTensor 格式在 AllGather 后要 interleaved Copy-Out（GPT-OSS-120B/64 H800 测试占 iteration 14%），Megatron-FSDP 改 concatenated sharding 但 row-wise 仍不能支持 block quantization，padding 不当也吃通信。

## 核心方法

**(1) RaggedShard DTensor**：新增 sharding placement，支持任意 block 粒度（atomic 不可切单元）+ 任意分布（每设备多少 block）。最通用的是 Block-wise RaggedShard，block 可为行、列、N-D plane。与 Replicate / Partial / Shard(dim) 组合干净，对 Shard(0) 引入 StridedRaggedShard 携带 stride metadata，对 Shard(dim>0) 取 LCM 避免 block 被切。

**(2) Structure-aware planner**：grouped RaggedShard tensor 打包进 comm buffer 有三种坑——block 被切、tensor 内 padding 不连续、per-device size 不等。planner 两步：先 permute tensor，再在 tensor 之间（而非之内）加 padding。公式化为 NP-hard 优化问题，polynomial heuristic 做 DP + binary search 在 `O(|T|² m log(E) log(|T|m))` 内完成。

**(3) Distributed Buffer (DBuffer)**：为 grouped RaggedShard 提供 zero-copy 访问——持久化地址映射让每个 tensor 在 buffer 内有固定切片；fuse 跨 tensor 的 add/scale/zero 等 kernel；N-D device topology 上直接做 AllGather/ReduceScatter/AllReduce in-place 通信。

保留 PyTorch-native `fully_shard` API，用户代码零修改。

## 关键结果

- 1024 GPU 上 LLaMA-3-70B、GPT-OSS-120B、内部 MoE 模型测试。
- MoE 模型 **11-66% 吞吐领先** 所有 baseline（DeepSpeed ZeRO v0.17.6、FSDP1/2、Megatron-FSDP）。
- LLaMA-3-70B **5% 快于 DeepSpeed/FSDP1/2**，略胜 Megatron-FSDP。
- **内存降 16-30%**。
- 天然支持 Muon、Shampoo、8-bit Adam 等 structure-aware 方法，无需改 model/optimizer。
- 已在 ByteDance Seed 多数生产 workload 部署；RaggedShard 开源 https://github.com/volcengine/veScale。
- Planner 避免 Megatron-FSDP 的 33% MoE padding 膨胀。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Expert-Parallelism]]、[[Quantization]]、[[MoE]]
- **同类系统**：DeepSpeed ZeRO、PyTorch FSDP1/2、Megatron-FSDP
- **同会议**：[[MLSys-2026]]
