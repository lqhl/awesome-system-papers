---
type: paper
name: ExecuTorch
full_title: "ExecuTorch - A Unified PyTorch Solution to Run AI Models On-Device"
authors: [Mergen Nachin, Digant Desai, Sicheng Stephen Jia, Chen Lai, Mengwei Liu, et al.]
venue: MLSys
year: 2026
tags: [edge-inference, pytorch, on-device, quantization, backend-delegation]
source_pdf: "[[a5bfc9e07964f8dddeb95fc584cd965d.pdf]]"
source_md: "[[a5bfc9e07964f8dddeb95fc584cd965d]]"
---

# ExecuTorch - A Unified PyTorch Solution to Run AI Models On-Device (MLSys 2026)

> **一句话总结**：Meta 提出首个 PyTorch-native 端侧部署框架，用 `torch.export` → Edge Dialect → PTE 实现 research-to-production 实验一致性，支撑 12 个硬件 backend、每日数十亿次推理，runtime 反序列化比 PyTorch Mobile 快 5.3×、初始化快 37.4×。

## 问题

>70% AI 研究用 PyTorch，但端侧部署常需转 ONNX/TFLite、重写 llama.cpp 或绑定 vendor runtime（SNPE、CoreML），造成语义鸿沟与调试循环。PyTorch Mobile/TorchScript 内存 footprint 大、硬件集成窄。研究者需要在 PyTorch 内验证量化、delegation、性能，再无缝上手机/MCU，而不牺牲可移植性。

## 核心方法

**Experimentation parity**：`torch.export` 捕获 Export IR（<300 Core ATen ops），再降到 **Edge Dialect**（无 mutation/alias、显式 dtype/layout），可在 PyTorch eager 与设备上保持行为一致。

**AOT 准备栈**：
- **Backend delegation**：子图 partition 到 XNNPACK / Vulkan / QNN / CoreML / Ethos-U 等 delegate，blob 序列化进 PTE
- **Memory planning**：arena 内 greedy best-fit 复用 tensor 生命周期
- **[[Quantization|Quantization]]**：基于 TorchAO，PTQ/QAT 在 export graph 上标注
- **PTE 格式**：线性 instruction list（KernelCall / DelegateCall），segments 支持 mmap、weight sharing（multi-method / PTD 分离）

**Lean runtime**：C++17、无 heap/STL、用户供 MemoryManager；selective build 把 kernel 库从 MiB 缩到 KiB。MCU 演示（Raspberry Pi Pico 2）：int8 CMSIS-NN 推理 **16.46×** 快于 FP32 portable（3.5 ms vs 57.6 ms）。

LLM 优化含 quantized [[KV-Cache]] attention、sliding-window attention、speculative decoding（QNN/CoreML）。

## 关键结果

- 生产：Meta 全家桶 app + Reality Labs 每日 **数十亿** 次推理
- Dense LLM（Galaxy S25 / Pixel 9 Pro）：XNNPACK CPU 持续强于 ONNX/LiteRT；Vulkan GPU decode throughput 常优于 llama.cpp
- Vision（MV3/ResNet50/ViT/Swin-T）：XNNPACK CPU 极强；iPhone 15 Pro CoreML 全图 delegation 匹配原生
- 最小模型 runtime overhead：FlatBuffer 反序列化 **5.3×**、初始化 **37.4×** 快于 PyTorch Mobile Interpreter

## 相关

- **相关概念**：[[Quantization]]、[[KV-Cache]]、torch.export、edge inference
- **同类系统**：ONNX Runtime、TensorFlow Lite、llama.cpp、PyTorch Mobile、CoreML
- **同会议**：[[MLSys-2026]]