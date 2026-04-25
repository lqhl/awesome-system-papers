---
type: paper
name: MAIO
full_title: "Accelerating Model Loading in LLM Inference by Programmable Page Cache"
authors: [Yubo Liu, Hongbo Li, Xiaojia Huang, Yongfeng Wang, Hanjun Guo, Hui Chen, Yuxin Ren, Ning Jia]
venue: FAST
year: 2026
tags: [llm-inference, model-loading, page-cache, file-system, maas]
source_pdf: "[[fast2026-liu-yubo.pdf]]"
source_md: "[[fast2026-liu-yubo]]"
---

# Accelerating Model Loading in LLM Inference by Programmable Page Cache (FAST 2026)

> **一句话总结**：在不修改 kernel、不依赖特定硬件、不侵入 LLM 推理框架的前提下，用可编程 page cache 框架 PPC（routing FS + userspace runtime）+ I/O 模板驱动的 cache 策略 MAIO（interruptible prefetch + XPU affinity + burn-after-reading eviction），把模型加载延迟降低最多 79%，弹性部署吞吐提升 36%。

## 问题

[[MaaS]] 平台启动 LLM 推理服务（如 DeepSeek-R1-671B 加载耗时 1 小时，模型加载占 70%+）的瓶颈在 model loading。已有方案如 ServerlessLLM、BlitzScale 通过定制 inference 框架/依赖 NVLink/RDMA 提速但牺牲兼容性 —— 而生产环境换 kernel 要数年、推理框架是黑盒不可改、硬件特性不通用。

实测三大 kernel page cache 缺陷：
1. **Prefetch**：SSD 平均带宽利用仅 17%，kworker 数量 + 仅基于"同文件相邻 128 KB"启发式无法配合模型加载的复杂 I/O 模式；
2. **XPU affinity**：把模型副本绑到对应 NUMA 节点的 tmpfs 可降 20% 加载延迟，但 kernel prefetch 盲目放到 kworker 自己的 NUMA；
3. **Eviction**：LRU 不感知"页面已 host→XPU 拷完，可立即驱逐"的时序局部性，可用 cache 仅模型 45% 时延迟增 38%。

已有 cache 控制方案各有短板：FUSE 软件栈重；eBPF 不支持复杂策略且改 kernel；fadvise 无法与前端 I/O 协同。

## 核心方法

**PPC = Routing FS (RFS) + Cache Policy Runtime (CPRT)**：
- **RFS**：基于 stacked file system（类似 OverlayFS）作为只读 kernel module，挂在底层 FS 之上劫持 read / page fault 的 cache miss；mount/lookup/open/read 把 inode/file/dentry 映射到 underlying FS 的对应结构；cache miss 时通过 UPC（Userspace Procedure Call，per-core xarray + epoll，非阻塞）通知 userspace。
- **CPRT**：VFS 风格 API（`ppc_init/exit/prefetch/evict`），策略以动态库注册，可热切换；输出"建议 I/O 列表"，由 cache manager 实际执行。同一 namespace 一时一策略，需要并存就分子目录。

**MAIO 三机制**（基于 PPC 的具体策略）：
- **I/O Template**：观察到同一 inference service（model + 并行配置一致）的 I/O 序列可复现，预先记录每个 XPU 的 I/O 序列作为模板。启动时解析模板获得未来 I/O 计划。
- **Interruptible Prefetching**：用模板驱动激进 prefetch 充分占用空闲 SSD 带宽；前端真实 I/O 命中时若 prefetch 进行中可被中断让路，避免互相阻塞。
- **XPU Affinity Loading**：模板携带 XPU ID，prefetch 直接把数据放进目标 XPU 对应 NUMA 的 page，避免跨 NUMA 拷贝。
- **"Burn-after-Reading" Eviction**：模型页面一旦被 host→XPU 传输完成即可驱逐（推理期间数据驻留 XPU），模板提供精确时序，立刻释放 page cache。

整体保持对 [[vLLM]]、[[SGLang]] 等推理框架透明，无需 kernel 内核改动。

## 关键结果

- 模型加载延迟降低最多 79%（memory-rich）/ 74%（memory-constrained）vs 已有兼容/不兼容方案。
- 弹性 inference 场景吞吐提升最多 36%。
- 在 5 个主流模型（含 Qwen2.5-72B、Llama-70B 等）上验证。
- SSD 带宽利用从 17% 提升（具体数字回 [[fast2026-liu-yubo]]）。
- 兼容性三维度全过：推理框架黑盒、kernel 无侵入（独立 module）、不依赖特定硬件。

## 相关

- **相关概念**：[[Page-Cache]]、[[Prefetching]]、[[NUMA]]、[[FUSE]]、[[eBPF]]、[[KV-Cache]]
- **同类系统**：ServerlessLLM、BlitzScale、PageFlex、FetchBPF、RFUSE、XFUSE
- **同会议**：[[FAST-2026]]
