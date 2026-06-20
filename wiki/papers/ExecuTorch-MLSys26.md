---
type: paper
name: ExecuTorch
full_title: "ExecuTorch - A Unified PyTorch Solution to Run AI Models On-Device"
authors: [Mergen Nachin, Digant Desai, Sicheng Stephen Jia, Chen Lai, Mengwei Liu, et al.]
venue: MLSys
year: 2026
tags: [edge-inference, pytorch, on-device, quantization, deployment]
source_pdf: "[[a5bfc9e07964f8dddeb95fc584cd965d.pdf]]"
source_md: "[[a5bfc9e07964f8dddeb95fc584cd965d]]"
---

# ExecuTorch - A Unified PyTorch Solution to Run AI Models On-Device (MLSys 2026)

> **一句话总结**：边缘部署碎片化（ONNX/TFLite/厂商 SDK）破坏 PyTorch 研究–生产一致性；ExecuTorch 以 **torch.export**→Edge Dialect（<300 Core ATen）→可选 backend delegate→**.pte** 轻量 runtime，实现 **experimentation parity**（PyTorch 内可验证量化/委托再上线），Meta 数十亿次日推理、12 后端，4-bit 权重量化模型体积 **-50%**。

## 问题与动机

>70% 研究用 PyTorch，但边缘推理常需换栈重实现，数值/行为漂移、调试周期长。PyTorch Mobile/TorchScript 内存与硬件集成不足；ONNX/CoreML/SNPE 等割裂语义。

## 关键观察 / 隐含假设

- **观察 1：torch.export 捕获的 Export IR 可在 PyTorch eager 中复现执行，同时降成 device-agnostic AOT 图——「先 PyTorch 验、后设备跑」可行。**
  - **依赖假设**：<300 Core ATen 覆盖目标模型；delegate 子图等价 Edge 语义。
  - **可能失效场景**：动态 shape 极端场景 export 失败；自定义 autograd.Function 需手写 lowering。

- **观察 2：选择性 backend delegation（QNN/CoreML/XNNPACK/Vulkan 等）+ CPU fallback 比纯 CPU 或纯 vendor 栈更平衡性能与可移植。**
  - **依赖假设**：partitioner 正确识别可加速子图；blob 与 runtime 版本匹配。
  - **可能失效场景**：partial delegation 引入 host–accelerator 同步开销；NPU 算子覆盖缺口。

- **观察 3：LLM 边缘瓶颈在 KV 与权重；图级 KV quant、sliding-window、4-bit groupwise 可在 export 图统一评估。**
  - **依赖假设**：TorchAO 量化 workflow 与 on-device kernel 一致。
  - **可能失效场景**：长 context 滑动窗口与状态 mutating op 需受控放宽 Edge 约束。

## 核心方法

**AOT**：torch.export → Edge Dialect（functional、dtype/layout 专化）→ 量化/融合/内存规划 → delegate lowering → PTE 序列化（Linear instruction：KernelCall/DelegateCall）。

**Runtime**：Lean executor；12 backends；extension 支持自定义 kernel、选择性算子构建减 binary。

**Memory planning**：arena + greedy best-fit；mutable state 无限 lifespan。

## 设计取舍

- **PyTorch-native vs 最小 binary**：保留语义与 debug symbol，相对裸 C 引擎体积更大。
- **Core ATen 限制 vs 算子完备**：减 port 负担，偶发 decomposition 性能损。
- **AOT 为主 vs JIT on-device**：可预测、低依赖；灵活性降。
- **边界条件**：0.01W MCU 到 800W 集群宣称；评测侧重手机 CPU/GPU/NPU。

## 实验与结果

- 对比 ONNX Runtime、llama.cpp、LiteRT：CPU(XNNPACK)、移动 GPU(Vulkan)、NPU(QNN) 竞争或 SOTA；CoreML 全图委托匹配原生。
- Meta 生产：数十亿次日推理（Family of Apps、Ray-Ban 等）。
- 4-bit 量化：**50%** 模型体积降；KV quant 等 LLM 技术可 pre-deploy 验证。

## Critical Analysis

### 论证链条

experimentation parity 原则贯穿架构，生产规模佐证 viability。性能对比覆盖面广，但「统一」仍依赖 per-vendor delegate 维护。

### 假设压力测试

新算子进 PyTorch 后 Edge 覆盖滞后；多 backend 行为一致性强测成本高；MCU 极端内存下 PTE 仍可能过大。

### 实验可信度

Meta 生产数据有力；公开 benchmark 可比性因设备异构需谨慎解读。

### 系统性缺陷

Delegate 碎片化运维；OTA 更新与版本兼容；安全审计与模型加密论文未展开。

## 局限与 Future Work

- **局限**：动态图/训练 on-device 非重点；backend 质量不均；export 失败 fallback 路径成本。
- **Future work**：更统一 delegate ABI；与 ExecuTorch LLM 栈深度整合； formal parity 测试套件。

## 相关

- **相关概念**：[[Quantization]]
- **同类系统**：ONNX Runtime、TensorFlow Lite、PyTorch Mobile、[[llama.cpp]]
- **同会议**：[[MLSys-2026]]