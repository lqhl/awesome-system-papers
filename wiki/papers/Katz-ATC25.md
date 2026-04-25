---
type: paper
name: Katz
full_title: "Katz: Efficient Workflow Serving for Diffusion Models with Many Adapters"
authors: [Suyi Li, Lingyun Yang, Xiaoxiao Jiang, Hanfeng Lu, Dakai An, et al.]
venue: ATC
year: 2025
tags: [diffusion-model, controlnet, lora, serving, t2i]
source_pdf: "[[atc2025-li-suyi-katz.pdf]]"
source_md: "[[atc2025-li-suyi-katz]]"
---

# Katz: Efficient Workflow Serving for Diffusion Models with Many Adapters (ATC 2025)

> **一句话总结**：在生产 T2I workflow（base SDXL + 多 ControlNet/LoRA）上把 ControlNet 解耦成独立服务（缓存+并行）、bounded async LoRA loading、CFG latent parallelism，相对 Diffusers/DistriFusion/Nirvana 端到端最高 7.8× 提速、1.7× 吞吐，无图像质量损失。

## 问题

生产级 T2I 服务（DALL·E、Midjourney、Firefly 等）不是单 base diffusion model，而是 base + 多 ControlNet（控构图）+ 多 LoRA（控风格）。阿里云生产 trace 显示 >98% 请求至少用一个 ControlNet、>95% 至少一个 LoRA，70% 用 2+ 个 ControlNet。

两种 adapter 各有痛点：

- **ControlNet**：3GiB 单个，全 trace 仅 ~150 个，访问极偏斜（top 9–11% 占 95–98% 调用），但 compute-heavy——加 1 个 ControlNet 让 SDXL 单次推理从 2.9s 涨到 4.5s（1.6×）
- **LoRA**：每个几百 MiB，全 trace 14,500 个，长尾分布（99.8% LoRA 单个占比 < 1% 调用），compute-light 但 loading 主导——loading 两个 LoRA 占总延迟 34%

batching 在 SDXL 上几乎无收益（doubling batch ≈ doubling latency），生产固定 batch=1。CFG（classifier-free guidance）的条件/无条件 denoising 用 latent batching 在一个 batch 里跑，反而比拆开慢。

## 核心方法

**ControlNet-as-a-Service**：把 ControlNet 从 base model 解耦，部署成独立可伸缩服务，专属 GPU。三个收益：
- 仅缓存 top 几个高频 ControlNet 在 GPU 内存即可消除 loading（top-5 覆盖 service A 98% 调用）
- ControlNet 与 base UNet 在不同 GPU 上**并行执行**（每步 denoising 仅在 UNet decoder 进入前同步一次），近 ideal 1.45× speedup（NVLink）
- 多 base model 可共享同一 ControlNet 服务（multi-tenant）

**Bounded Asynchronous LoRA Loading (BAL)**：观察到 LoRA 主要影响 denoising 后期步骤——前 K 步即使没 patch LoRA，输出与同步 patch 几乎相同。所以**先用 base model 早启动 denoising 至多 K 步**，同时异步从存储拉 LoRA；K 步后 LoRA 已就位，patch 上去继续后续步骤。K 调好可完全 hide LoRA loading，质量不掉。

**Latent parallelism for CFG**：CFG 每步把 latent 复制成两份（conditioned/unconditioned 各一），它们无依赖。Katz 把两份 denoising 并行跑在两个 GPU 上而非 batch 在同一 GPU。配合 kernel 优化使 base model 推理加速 1.8×。同样应用于 ControlNet 内部 CFG。

整体在 SDXL + 1C/1L 配置下用 4 GPU（base 2 + ControlNet 2）。深度细节回 [[atc2025-li-suyi-katz]]。

## 关键结果

- 生产 trace（阿里两个 T2I 服务、20 天 500k+ 请求）特征：ControlNet 偏斜、LoRA 长尾、batching 无收益
- vs Diffusers/Nirvana/DistriFusion：H800 上 SDXL 平均 latency 降低 **最高 7.8×**、吞吐 **1.7×**
- 75 人 user study 确认图像质量与 Diffusers 等同
- 也适用于 DiT（diffusion transformer）backbone
- 开源：https://github.com/modelscope/Katz

## 相关

- **相关概念**：[[Diffusion-Model]]、[[ControlNet]]、[[LoRA]]、[[Classifier-Free-Guidance]]、[[Adapter-Serving]]
- **同类系统**：Diffusers (HuggingFace)、Nirvana（前 κ 步用相似 prompt 缓存图替噪声）、DistriFusion（latent patch 切片并行）
- **同作者**：[[Toppings-ATC25]]（同一一作 Suyi Li，做 LLM 的 LoRA serving）
- **同会议**：[[ATC-2025]]
