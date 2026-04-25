---
type: paper
name: GCR
full_title: "GPU Checkpoint/Restore Made Fast and Lightweight"
authors: [Shaoxun Zeng, Tingxu Ren, Jiwu Shu, Youyou Lu]
venue: FAST
year: 2026
tags: [gpu, checkpoint-restore, llm-inference, incremental-checkpoint, shadow-execution]
source_pdf: "[[fast2026-zeng.pdf]]"
source_md: "[[fast2026-zeng]]"
---

# GPU Checkpoint/Restore Made Fast and Lightweight (FAST 2026)

> **一句话总结**：GCR 通过 control/data 分离的 hybrid C/R（control 走 driver-integrated cuda-ckpt，data buffer 走 interception + async memcpy + 虚拟/物理地址解耦）+ CPU 上的 shadow execution + 符号执行生成的 dirty templates，把 GPU checkpoint 延迟比 cuda-ckpt 降 72.1%、比 PhOS 降 63.6%，restore 降 54.2%/87.1%，正常执行开销 <1%，并支持 incremental checkpoint 减 86.6% 体积。

## 问题

System-level GPU [[Checkpoint-Restore|C/R]] 是 GPU serverless 弹性扩缩、训练/推理任务切换、容错训练的关键 system primitive。两类已有方案各有硬伤：
- **Driver-integrated**（NVIDIA 官方 cuda-ckpt）：normal execution 零开销、control state 处理高效，但 data buffer C/R 仅达 PCIe 带宽的 12%（checkpoint）/28.8%（restore）—— 闭源黑盒，社区无法优化。
- **Interception-based**（PhOS 等）：拦截全部 GPU driver API，data buffer 异步 memcpy 可达 24.3 GB/s（接近 PCIe 上限），但 resource handler 序列化让 control state checkpoint 慢 3.5×、restore 慢 9.2×；常规执行平均拖慢 8.7%（峰值 49.6%）。
- **Incremental checkpoint 全军覆没**：cuda-ckpt 无 dirty 识别；PhOS 有但因 +12% 开销默认关闭，结果每次 checkpoint 都 30 GB（amplification 7.2×）。

## 核心方法

**Hybrid C/R via control/data separation**：
- 只 selectively 拦截 GPU memory (de)allocation（cuMemAlloc、cuMemFree），记录 buffer 地址与长度（每个 16 B），其它 API 不动 → normal execution <1% 开销。
- Checkpoint：先 async memcpy 把 GPU data buffer 拷到 CPU（达 20.5 GB/s），再 deallocate；只剩 control state，用 driver-integrated cuda-ckpt 处理。
- Restore：cuda-ckpt 先恢复 control state，再 memcpy 回 data buffer（达 23.0 GB/s，92% PCIe 上限）。
- **Buffer 地址一致性**：解耦虚/物理。Checkpoint 时调 cuMemUnmap+cuMemRelease 只释放物理内存，保留虚拟地址（一同被 cuda-ckpt 写到 GPU page table）；restore 时虚拟地址因从未释放保持不变，再 cuMemCreate 新物理 + cuMemMap 重映射。比 PhOS 依赖 cuMemAddressReserve 提示更可靠。

**Incremental checkpoint via shadow execution**：
- GPU 硬件无 dirty bit；speculation 粗粒度（PhOS 在 vLLM KV-cache 场景 amplification 18.6×）；Neutrino 风格 instrumentation 重（5.3× 减速 + 7.1 GB GPU 内存）。
- GCR 把 dirty 识别移出 GPU 关键路径：CPU 上做 **shadow execution** 与 GPU kernel 并行，但只算 store 指令的 dirty 地址 + 长度，跳过所有计算。
- **Dirty templates**：离线对每个 kernel 做 PTX-level [[Symbolic-Execution]]，把 store 指令的目标地址/长度转成 kernel argument 与 launch config（gridDim/blockDim）的表达式，消去其他计算，生成的 C++ 函数链接为库。Online 时拦截 cudaLaunchKernel 取参数填模板，CPU 微秒级（如 14 µs）+ <1 MB 内存识别 dirty。
- 闭源 kernel（cuBLAS/NCCL）查文档标 dirty arg；地址依赖 pointer chasing/复杂计算的 kernel fallback 到 const-aware 粗标记。

## 关键结果

- Checkpoint 延迟：相对 cuda-ckpt -72.1%、相对 PhOS -63.6%。
- Restore 延迟：相对 cuda-ckpt -54.2%、相对 PhOS -87.1%。
- 正常执行开销 <1%（PhOS 8.7% / 峰值 49.6%）。
- Incremental checkpoint：体积 -86.6%、延迟 -43.8%（vLLM Llama2-7B 推理 30 GB → 4.1 GB）。
- 覆盖 vLLM、DeepSpeed、Transformers、单/多 GPU；PhOS 因实现限制不少 workload 跑不动。

## 相关

- **相关概念**：[[Checkpoint-Restore]]、[[KV-Cache]]、[[Symbolic-Execution]]、CRIU、CUDA Driver API
- **同类系统**：cuda-ckpt、PhOS、ServerlessLLM、Neutrino
- **同会议**：[[FAST-2026]]
