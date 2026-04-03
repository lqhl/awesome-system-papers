# KATZ: Efficient Workflow Serving for Diffusion Models with Many Adapters

**作者**：Suyi Li, Lingyun Yang, Xiaoxiao Jiang, Hanfeng Lu, Dakai An (Hong Kong University of Science and Technology); Zhipeng Di, Weiyi Lu, Jiawei Chen, Kan Liu, Yinghao Yu, Tao Lan, Guodong Yang, Lin Qu, Liping Zhang (Alibaba Group); Wei Wang (Hong Kong University of Science and Technology)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/li-suyi-katz
**源文件**：[[atc2025-li-suyi-katz.pdf]]

---

## 一、背景

Text-to-Image (T2I) 生成是当前 AI 云服务中最热门的应用之一，DALL·E、Midjourney、Firefly 等商业服务已被广泛使用。生产环境中的 T2I 服务通常以工作流形式部署：以 Stable Diffusion 等基础扩散模型为核心，辅以大量 adapter（适配器）来精细控制输出图像的构图、轮廓、姿态和风格。其中 ControlNet 和 LoRA 是两种最主流的 adapter——ControlNet 通过参考图像控制空间构图，LoRA 则通过低秩参数适配实现风格定制。

在阿里巴巴的生产平台上，超过 98% 的请求需要至少一个 ControlNet，超过 95% 使用至少一个 LoRA。然而现有 T2I serving 系统（如 Diffusers、Nirvana、DistriFusion）主要关注基础模型推理优化，忽略了 adapter 引入的显著延迟开销：在 H800 GPU 上，添加一个 ControlNet 使延迟增加 1.6×，而 adapter 的加载（从存储到 GPU 内存）平均占端到端延迟的 37%。

---

## 二、要解决的问题

1. **ControlNet 计算开销大**：ControlNet 与 UNet encoder 共享类似架构，计算密集。当前系统在每个 denoising step 中顺序执行多个 ControlNet，开销随数量线性累积（1C→4.5s, 3C→13.9s）。
2. **LoRA 加载开销高**：生产环境中有 ~14,500 个 LoRA（每个数百 MiB），呈长尾分布，缓存效果有限。每次请求需从远程存储加载 LoRA 并 patch 到基础模型，两个 LoRA 导致 2.1× 的延迟增长。
3. **LoRA patching 低效**：现有框架（PEFT/Diffusers）采用 create-and-replace 操作来合并 LoRA 权重，一个 341 MiB 的 LoRA 需要 2 秒。
4. **基础模型 CFG 计算未充分并行化**：每个 denoising step 的 CFG（Classifier-Free Guidance）需要对 latent tensor 做两次 denoising（conditioned 和 unconditioned），当前实现采用 latent batching 导致至多 1.7× 的性能下降。
5. **Batching 在扩散模型中几乎无效**：单张图片生成已饱和高端 GPU 的计算能力（SDXL 1024×1024 需要 676 TFLOPS），batch size 翻倍延迟也近似翻倍。

---

## 三、洞察与设计

**关键洞察**：ControlNet 与 LoRA 具有截然不同的性能瓶颈特征——ControlNet 数量少但计算重、流行度偏斜（top 9-11% 覆盖 95-98% 请求），适合缓存和并行化；LoRA 数量巨大但计算轻、瓶颈在加载，且其在 denoising 前期（semantics-planning 阶段）几乎不起作用，可以异步加载而不影响图像质量。

基于此洞察，KATZ 提出三项核心设计：

### 1. ControlNet-as-a-Service

将 ControlNet 从基础模型解耦，部署为独立可扩展的服务：

- **缓存**：仅缓存少量热门 ControlNet（5-8 个即可覆盖 95-98% 请求），消除加载开销
- **并行化**：ControlNet 与 UNet encoder 并行执行于不同 GPU，UNet decoder 同步等待 ControlNet 输出后再继续。由于 ControlNet 与 UNet encoder 计算负载天然均衡，实现接近理论最优加速
- **共享**：单个 ControlNet 实例可被多个基础模型复用
- **异步流水线**：在慢速互联场景下，利用相邻 denoising step 的 ControlNet 输出高度相似（cosine similarity > 0.99），用上一步的 stale 输出代替当前步同步等待，实现通信隐藏

### 2. Bounded Asynchronous LoRA Loading (BAL)

- 观察到 LoRA 在 denoising 初期（semantics-planning 阶段）几乎无效果（cosine similarity > 0.99），效果在后期 artistic-planning 阶段才显现
- 在 LoRA 加载期间，先以无 LoRA 状态启动基础模型推理，最多执行 K 步（通过 profiling 确定，默认 K=10）
- 若 LoRA 在第 K+1 步前加载完成，直接 patch 继续；否则等待加载完成
- 采用 in-place 权重合并取代 PEFT 的 create-and-replace，消除额外内存开销和延迟

### 3. Latent Parallelism

- 将 CFG 的 conditioned 和 unconditioned denoising 分配到两个 GPU 并行执行
- 两者计算负载均衡、无依赖，通信量小（< 1 MiB latent tensor）
- 同样适用于 ControlNet 的 CFG 加速
- 配合 CUDA Graph 和定制 kernel（GEGLU fusion、GroupNorm+SiLU fusion）进一步优化

---

## 四、实现细节

- 基于 HuggingFace Diffusers 实现，包含 5.5k 行 Python 和 2.4k 行 C++/CUDA 代码
- ControlNet-as-a-Service、BAL、latent parallelism 用 Python 实现；定制 CUDA 算子用 C++/CUDA
- LoRA 加载在独立进程中执行，通过共享内存将权重传输到 serving 进程
- CUDA Graph 适配 ControlNet 并行化：按数据依赖关系将基础模型切分为多个独立 CUDA Graph
- 针对 SDXL 的 transformer 计算（token 长度可达 4096），batch size 固定为 1
- 异步 ControlNet 流水线：step t 时基础模型使用 step t-1 的 ControlNet 输出，通信与计算重叠
- BAL 的异步边界 K 通过离线 profiling 确定：计算有/无 LoRA 时各 step latent 的 cosine similarity，取 similarity 开始低于 0.99 的 step 作为 K

---

## 五、实验结果

**实验平台**：NVIDIA H800 GPU、A100 GPU、A10 GPU；AWS g5.2xlarge 实例
**基础模型**：SDXL（UNet-based）、SD3、Hunyuan-DiT（DiT-based）
**基线**：Diffusers、Nirvana-10/20、DistriFusion
**指标**：端到端延迟、CLIP score、FID、SSIM、用户研究（75 人）

### 端到端延迟（SDXL, H800）

| 配置 | Diffusers | DistriFusion | Nirvana-10 | KATZ | 加速比 vs Diffusers |
|------|-----------|-------------|------------|------|-------------------|
| 0C/0L | 2.9s | - | - | 1.7s | 1.7× |
| 1C/1L | 6.2s | - | - | 1.9s | 3.3× |
| 3C/2L | 15.6s | 7.9s | - | 2.0s | 7.8× |

### 图像质量（1 LoRA: Papercut）

| 系统 | CLIP (↑) | FID (↓) | SSIM (↑) |
|------|----------|---------|----------|
| Diffusers | 34.1 | - | - |
| Nirvana-10 | 33.5 | 9.5 | 0.45 |
| DistriFusion | 34.0 | 1.7 | 0.86 |
| KATZ | 34.1 | 2.1 | 0.83 |

### 其他关键结果

- **ControlNet 并行化**：使用 3 个 ControlNet 时达到 2.2× 加速（理论上限 2.35×）
- **BAL**：LoRA 开销降至 230ms，几乎可忽略
- **Latent parallelism**：在 H800/A100/A10 上分别实现 1.36×/1.58×/1.71× 加速
- **吞吐量**：adapter 密集场景下提升至 1.7×
- **用户研究**：KATZ 与 Diffusers 均达 70% 接受率，Nirvana-10 低于 50%
- **DiT 泛化**：三项设计均可直接应用于 SD3 和 Hunyuan-DiT

---

## 六、批判性分析

1. **GPU 资源消耗被淡化**：KATZ 在 3C/2L 配置下使用 8 个 GPU，而 Diffusers 仅用 1 个。论文始终强调延迟加速比（7.8×），但对 per-GPU 效率和成本效益的讨论不够充分。在吞吐量实验中（Fig. 18-Right），0C/0L 场景下 KATZ 的 per-GPU-minute 吞吐量反而低于 Diffusers，说明 latent parallelism 的 GPU 利用率不佳。

2. **BAL 的 K 值泛化性存疑**：论文仅通过 profiling 少量 LoRA 确定 K=10 作为通用阈值，但不同 LoRA 的风格迁移特性差异可能很大（如细腻水彩风 vs 粗犷像素风）。论文未充分探讨 K 值对不同类型 LoRA 的敏感性。

3. **图像质量评估有局限**：FID 和 SSIM 以 Diffusers 输出为"ground truth"，这本身就是一个有偏的评估框架——它衡量的是"与 Diffusers 的相似度"而非"绝对图像质量"。用户研究虽有 75 人参与，但仅有 1.2k 数据点，且参与者主要是大学生，缺乏专业设计师/艺术家的评估。

4. **生产 trace 的代表性**：trace 来自阿里巴巴在线零售应用的 20 天数据，ControlNet 流行度偏斜的特征可能是该特定业务场景的产物。在更多样化的创意设计平台（如 Midjourney 类服务）中，ControlNet 的使用模式可能截然不同。

5. **异步 ControlNet 的质量保证不够严格**：论文基于"相邻 step ControlNet 输出 cosine similarity > 0.99"的观察来证明异步流水线无损，但 cosine similarity 是全局统计量，可能掩盖局部结构差异。对于需要精确边缘对齐的 ControlNet（如 Canny edge），stale 输出的影响需要更细致的分析。

---

## 七、AI Infra / MLSys 视角

1. **Adapter serving 的通用框架**：KATZ 将 adapter 分为"计算密集型"（ControlNet 类）和"加载密集型"（LoRA 类）两类并分别优化的思路具有通用性。在 LLM 领域，Expert Parallelism（MoE 模型中对 expert 的调度）面临类似的"少数热门 expert 高频访问 + 大量冷门 expert 长尾分布"问题，KATZ 的缓存 + 异步加载策略可以借鉴。

2. **Bounded Asynchronous Loading 的启发**：BAL 利用"模型在推理初期对某些参数不敏感"的特性来隐藏加载延迟，这一思路可以迁移到：
   - LLM 推理中 LoRA 的 lazy loading（prefill 阶段可能对 LoRA 不敏感）
   - MoE 模型中 expert 的异步 prefetch（根据 token routing 预测提前加载）

3. **值得跟进的方向**：
   - **Adapter-aware scheduling**：在多租户场景下，根据 adapter 的共享模式和加载成本做请求调度和 GPU 分配
   - **LoRA 流行度预测与预加载**：结合用户行为序列预测下一个 LoRA，提前发起加载
   - **Video diffusion 的 adapter serving**：视频生成模型的 denoising step 更多、latent 更大，adapter 的开销问题会更加突出

4. **最有价值的切入点**：将 ControlNet-as-a-Service 的解耦思想推广为通用的 "Plugin-as-a-Service" 框架，支持各种新兴 adapter（IP-Adapter、BrushNet、IC-Light 等）的高效服务，同时探索跨模型、跨 adapter 的资源共享与复用机制。

---

## 八、总结

KATZ 是首个系统性优化 T2I 工作流中多 adapter serving 的系统。通过将 ControlNet 解耦为独立服务实现缓存和并行化、利用 LoRA 在 denoising 初期无效的特性实现异步加载、以及 latent parallelism 加速 CFG 计算，KATZ 在不损失图像质量的前提下实现最高 7.8× 延迟降低和 1.7× 吞吐量提升。其核心贡献在于深入分析了 adapter 的异质性特征并据此设计差异化优化策略。主要局限在于需要多 GPU 支持（成本较高）、BAL 的通用性需要更多验证、以及评估主要基于 SDXL 等 UNet 模型在特定业务场景下的表现。
