---
type: paper
name: Privatar
full_title: "Privatar: Enabling Privacy-Preserving Real-Time Multi-User VR Through Secure Offloading"
authors: [Jianming Tong, Hanshen Xiao, Krishnakumar Nair, Hao Kang, Ziqi Zhang, Ashish Sirasao, G. Edward Suh, Tushar Krishna]
venue: MLSys
year: 2026
tags: [vr, privacy, offloading, avatar, differential-privacy, pac-privacy]
source_pdf: "[[4e732ced3463d06de0ca9a15b6153677.pdf]]"
source_md: "[[4e732ced3463d06de0ca9a15b6153677]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Privatar：通过安全卸载实现保护隐私的实时多用户 VR（MLSys 2026）

> **原题**：Privatar: Enabling Privacy-Preserving Real-Time Multi-User VR Through Secure Offloading

> **一句话总结**：Privatar 基于两条观察——avatar texture 频域能量极度偏斜（base 频带 **94.9%**）、用户表情分布缓慢漂移——用 HP 只 offload 低能量 DCT 分量 + DAMP（PAC privacy 按维最小噪声，较 local DP 降 **17.6×**），在 Meta Quest Pro 上 60 FPS 并发 avatar 数 **2.37×**（约 +3 users），重建 loss **+5.7–6.5%**、能耗 **+9%**，e-PSR 压至随机猜测（**1.54%**）。

## 问题与动机

多用户 VR（演唱会、体育直播、协作设计）需要在每个 receiver headset 上**实时解码所有参与者的 photorealistic avatar**。当前范式把完整 VAE decoder 放在 headset 本地，满足画质与隐私，但算力成为 scalability 瓶颈。

VAE 解决了带宽（latent 约 **0.49 Mbps/user**，相对 raw texture+mesh **~1.25 Gbps** 降 **>99%**），却把计算压力转移到 receiver：Meta Quest Pro **902 GFLOPS** 在 60 FPS 下最多支撑约 **2** 个并发用户。瓶颈在 decoder 的 **8 层 transposed convolution**（texture 重建占 decoder FLOPs **99.4%**；mesh 仅 **0.6%**）。

自然思路是把 decoder 部分 offload 到同局域网内更强但**不可信**的 PC/GPU，但 offloaded latent 会暴露面部纹理与表情 mesh，带来 identity / expression leakage（表情识别、soft-biometric profiling、跨 session tracking）。现有可证明隐私路径各有硬伤：

- **HE / MPC**：延迟或通信量级不适合实时 VR（HE 约 **3 个数量级**更慢；MPC 需 GB 级通信）
- **TEE（CPU SME）**：隐私更强，但 Quest Pro 上吞吐仅 **1.79×**（GPU 无 TEE 时 Privatar **2.37×**）
- **Local DP 各向同性噪声**：低噪声下 ML 攻击 expression 识别 **86.15%**；足够隐私时 fully offload 重建 loss **105×** baseline

论文 claim：利用 **avatar reconstruction 的领域结构**，可在不牺牲 utility 的前提下做可证明隐私的 partial offloading。深度 pipeline 与威胁模型见 [[4e732ced3463d06de0ca9a15b6153677]]。

## 关键观察 / 隐含假设

- **观察 1：unwrapped facial texture 在 block DCT 后能量极度集中于 base frequency component。**
  - **证据**：$B=4$ block DCT 得 16 个频带；base 分量 L2 norm 占全体 **94.9%**，其余 15 个合计约 **5%**（Fig. 4a/6）。各高频分量视觉上接近随机噪声，单独或子集难以还原完整表情。
  - **依赖假设**：该 VAE + BDCT 分解对 Multiface 类 avatar 普遍成立；receiver 侧 merge 时本地高能量分量能「盖住」offloaded 低能量分量的误差。
  - **可能失效场景**：不同 avatar codec、非 DCT 分解、或表情变化主要体现于高频细节时，local/offload 划分收益与隐私边界需重测。

- **观察 2：单用户表情 latent 的统计分布在短时间窗内近似稳定，可在线跟踪。**
  - **证据**：训练集 expression 分布与随机 **2 秒（120 帧）** trace 几乎重合（Fig. 4b）；用户不可能瞬间做出远超历史范围的极端表情（mouth 2× 等）。
  - **依赖假设**：VR session 内 expression 流满足缓慢漂移；headset 可本地维护 per-user covariance 且**永不外传**；PAC privacy 框架下 adversary 知 $D$ 与 $F$ 但仍无法突破噪声界。
  - **可能失效场景**：戏剧表演、夸张滤镜、新用户冷启动（无历史分布）、或 adversary 获得 side-channel 更新分布时，DAMP 噪声校准可能过松或过紧。

- **观察 3：multi-user VR 的 receiver 瓶颈是「单 headset 并行 decode 多人 latent」，而非单用户 encode 或广域传输。**
  - **证据**：Quest Pro roofline 建模 + latency breakdown（Fig. 8/10b）；offload 后 local decoder FLOPs 随 offload 分量数 $m$ 下降，吞吐随 $m$ 上升直至 **communication** 成为主导（Quest 3 上更明显）。
  - **依赖假设**：同户 WiFi-7（≤20 Gbps）PC 可达且延迟可接受；offload host（RTX 5090）算力充裕；多用户 session 中每人独立 latent stream。
  - **可能失效场景**：纯广域网无本地 PC、WiFi 拥塞、或 offload 节点多 tenant 争用 GPU 时，吞吐–loss Pareto 会右移。

- **假设 1：威胁模型对齐 local DP——用户只信自己 headset，局域网 router/PC/其他 headset 均不可信。**
  - **证据强度**：强。与 VR 分站点部署（各家 headset 经 Internet + 本地网关互联）一致；formal 分析按 computationally-unbounded adversary 建模。
  - **可能失效场景**：若实际部署把 offload 固定在运营商边缘且用户「半信任」该边缘，则 noise/HP 设计可能过度保守；compromised headset 本身不在防护范围内。

- **假设 2：HP 的「不完整频域视图」足以提供 empirical 抗 expression identification，形式化保证由 DAMP 补齐。**
  - **证据强度**：中。offload 全部分量时 empirical attacker **86.5%** PSR；base 留本地后 e-PSR 降至 **≈1.54%**（随机猜 65 类）。但 HP alone 无 t-PSR 证书，需与 DAMP 组合才能对 arbitrary attack 说话。

## 核心方法

Privatar 在 VAE avatar pipeline 上做 **horizontal partitioning（HP）** + **Distribution-Aware Minimal Perturbation（DAMP）**，对应 Fig. 5 双路径。

### Horizontal Partitioning (HP)（水平分区（HP））

1. **频域分解**：unwrapped texture（减训练集均值后）做 $B \times B$ block DCT，得 $B^2$ 个分量，各为原图 $1/B^2$ 分辨率，总数据量不变但可 relocation compute。
2. **Local path（绿）**：facial mesh **始终本地**；**base / 高 L2 norm** 频带在 sender/receiver headset 完成 encode–decode；latent 通信加密（AES-GCM，开销可忽略）。
3. **Offloaded path（红）**：**低 L2 norm** 的 $m$ 个频带在 sender 编码 → DAMP 加噪 → 不可信 PC decode → noisy 频带回传 headset merge。
4. **与原版 VAE 差异**：texture 输入下采样至 $1/B$ 空间分辨率，local encoder/decoder 各少 $\log_2 B$ 层；offload $X$ 个分量后 local 仅处理 $B^2-X$ 个，单分量重建成本约 $1/B^2$ 原 VAE。

默认 $B=4$、$m=14$：仅 **2** 个最低方差分量留本地，**14** 个 offload。HP alone 增加 loss **≈5.7–6.4%**（LPIPS **+0.72%**），提供 empirical privacy（partial view），降低 DAMP 所需噪声强度。

### Distribution-Aware Minimal Perturbation (DAMP)（分布感知最小扰动 (DAMP)）

回应观察 2 与 local DP 的「各向同性噪声」失效：

1. **初始化**：用用户历史 expression 估计 offloaded latent 的 covariance $\Sigma_{F(X)}$，SVD 得特征方向。
2. **在线更新**：新表情持续更新分布（仅存 headset，不外传）。
3. **噪声校准**：按 PAC privacy 约束 $\mathrm{MI}(X; F(X)+e) \le v$，逐特征值求最小 Gaussian 噪声协方差；生成 $e \sim \mathcal{N}(0, U\sigma U^T)$ 加到 offload latent。
4. **保证**：对 expression identification attack 给出 **t-PSR** 上界；默认 $v=0.1$ 对应 t-PSR **9%**。

相对 isotropic local DP：协方差 trace 降约 **$10^3$**；单样本扰动 L2 在 t-PSR=40% 时降 **17.6×**，9% 时 **4.1×**，3.5% 时 **1.1×**（Fig. 7/10c）。

### 组合逻辑

HP 减少 offload 信息熵与 sensitivity → DAMP 所需噪声更小；DAMP 将 HP 的 empirical 保护升格为对 **arbitrary adversary** 的可证明界。威胁模型与攻击实例化（empirical matcher + 3-layer NN）见 [[4e732ced3463d06de0ca9a15b6153677]] §D。

## 设计取舍

- **Partial offload vs full offload / 全本地**：只动 texture decoder 中可 offload 的低能量频带，保留 mesh + base 本地，换取 **2.37×** 吞吐且 loss 可控；fully offload + DP 在 privacy 达标时 utility 崩溃（**105×** loss）。
- **频域划分 vs 空间 [[Quantization]] / sparsity**：quantization 不改 MAC 数（activation 仍 FP）；sparsity 破坏 workload 规则性，Quest Pro Snapdragon 无专用支持。HP 是 **compute relocation** 而非仅压缩权重。
- **GPU offload + 噪声 vs CPU TEE**：选更快但无硬件 TEE 的 RTX 5090，用 PAC 噪声换隐私；TEE 路径吞吐 **1.32×**（Privatar）vs TEE 自身 **1.79×**，隐私保证形态不同（TEE 强机密性 vs DAMP 统计不可区分）。
- **PAC privacy vs classical DP**：利用数据分布熵减少噪声，但需维护 per-user 协方差、假设 adversary 知 $D$；分布漂移时需持续 recalibrate。
- **固定 $m=14$ vs 可调 partition**：更大 $m$ 提升吞吐直至 WiFi 下载 reconstructed 频带成为瓶颈；更小 $m$ 降通信但 local compute 仍高。论文选高 device utilization 的配置，非全局最优。

## 实验与结果

**Setup**：Multiface（13 identities，~1.7M frames）；Meta Quest Pro + RTX 5090 offload + AMD 7985WX（SME 作 TEE 对照）；WiFi-7；baseline 为全本地 decoder（$L_0=0.072$ MSE，**2.48** users @60FPS）。

**主结果（$m=14$, $v=0.1$）**：

- 吞吐 **2.37×** users（约 **+3** 并发），users/watt **2.17×**
- 归一化 loss **+8.3%**（HP+DAMP）；HP no-noise **+5.7–6.5%**
- 能耗 **+9%**（32 GOP/s/W compute + 13.94 nJ/bit comm 模型）
- e-PSR **≤1.54%**（随机猜水平），t-PSR **9%** 证书
- vs 8-bit weight [[Quantization]]：**2.27×** 吞吐；vs 10% channel sparsity：**2.05×**；vs CPU SME TEE：**1.32×**（同等 e-PSR）

**Ablation（$m \in \{2,4,\ldots,14\}$）**：

- 吞吐随 $m$ 升，local latency（绿）降，communication（蓝）升；$m=14$ 时 offload compute 仍小于 local+comm
- 只要 base 留本地，各 $m$ 与 noise level 下 e-PSR 维持 **≈1.54%**
- Quest 3（**4.1×** 本地算力）：**1.34×** users，loss **+4.6%**；通信成系统瓶颈

**攻击**：低噪声无 HP 时 empirical **86.15%**、NN attacker 亦高；Privatar 下两者均降至随机猜测。

## 批判性分析

### 论证链条

observation（频域偏斜 + 分布缓慢漂移）→ HP 减敏感度 / empirical 隐私 → DAMP 最小噪声 + PAC 证书 → Quest Pro 吞吐–loss–privacy 三维 Pareto 优于 quantization/sparsity/TEE/FO。链条在 **「VAE avatar + 本地 PC offload」** 这一部署形态上较闭合：ablation 分离了 $m$ 与 MI budget $v$，说明吞吐来自 compute split、隐私来自 HP+DAMP 组合而非单一 trick。

脆弱跳步：(1) **生产 VR 是否真有稳定 LAN PC**——论文实验是 Quest↔PC WiFi-7，与跨 Internet 多站点 Fig. 3a 拓扑之间缺端到端广域测量；(2) **HP empirical 隐私 → 抗 NN attacker** 靠实验验证，未对所有可能 reconstruction 路径形式化；(3) **Multiface 13 人** 到百万级 social VR 的 identity/expression 多样性外推未验证。

### 假设压力测试

- **Workload**：表情剧烈、高频细节主导的情绪捕捉（surprise micro-expression）可能让「base 留本地即可」不成立；非 Lombardi 类 VAE codec 需重做 DCT 能量剖面。
- **硬件**：更强下一代 headset（Quest 3）baseline 已能 **10.6** users，Privatar 相对收益缩至 **1.34×**——问题定义随硬件进步会被部分「消化」，但通信瓶颈仍可能随 $m$ 增大而凸显。
- **网络**：$m=14$ 时需回传多路 noisy reconstructed 频带；弱网或移动热点下 communication bar 可能反超 local compute 节省。
- **Adversary**：模型假设 adversary 知用户分布 $D$；若攻击者通过长期观测 offload 流估计漂移分布，论文未分析 adaptive attack 对在线更新的影响。
- **隐私语义**：保护对象是 expression classification（65 类），不是 raw biometric 复原；identity leakage 主要靠 HP 不完整视图，**无独立 identity PSR 证书**。

### 实验可信度

**强项**：真实 Quest Pro 功耗/算力建模；与 quantization/sparsity/TEE/FO 同 e-PSR 门槛对比；$m$ 与 $v$ 双旋钮 ablation；empirical + NN 双攻击；开源 artifact（Zenodo DOI）。

**弱点**：(1) offload 用 RTX 5090 非 TEE GPU，与威胁模型中「不可信 PC」一致但无 GPU enclave 对照；(2) 仅 Multiface 单 test identity 连续帧；(3) 吞吐由 roofline + 单用户 latency 推导 concurrent users，非真实 N-user 同屏 stress test；(4) 能耗为模型估算非实测电池曲线；(5) 与 confidential computing 的隐私保证不可直接横向比序（统计 vs 机密性）。

### 系统性缺陷

- **运维复杂度**：双路径 VAE、在线协方差、噪声校准、加密密钥分发；论文未给生产级 failure mode（PC 离线、噪声模块超时、分布未收敛）。
- **多用户公平性**：每个 receiver 对各 sender latent 独立 decode；offload PC 多 session 调度、QoS、排队延迟**未讨论**。
- **尾延迟**：60 FPS 硬实时下 comm 抖动对 merge 帧的影响未报 P99。
- **兼容性**：绑定 block DCT + 特定 VAE 切分；换 mesh-only 或 neural rendering pipeline 需重新设计 HP。
- **冷启动**：新用户无历史分布时 DAMP 退化为何种 fallback，论文仅述用历史初始化，未量化首日隐私–utility。

## 局限与后续工作

- **局限 1**：HP 单独只有 empirical 保护，必须叠加 DAMP 才有 formal t-PSR；base 频带永不离开 headset 是 empirical 抗攻击的关键，也是架构硬约束。
- **局限 2**：GPU TEE 不可用，与最强机密 offload 路径（GPU enclave）未对比；CPU TEE 吞吐低于 Privatar。
- **局限 3**：评估限于 Multiface + Quest Pro/3；真实 Meta Horizon 类社交场景的网络拓扑、avatar 标准、攻击面未覆盖。
- **局限 4**：$m$ 增大后 communication 成为瓶颈（Quest 3 已显现），论文指出需 reconfigurable hardware（Feather/MINISA）做更细粒度划分，但未实现。
- **局限 5**：身份隐私与表情隐私未分别证书；对 deanonymization 仅定性讨论。
- **Future work 1**：在真实跨 Internet multi-site trace 上测量 LAN offload 可用率与 tail latency，验证「本地 PC」假设是否成立。
- **Future work 2**：identity-specific PAC 目标与 HP 频带选择联合优化，给出 identity PSR 上界而非仅 expression classification。
- **Future work 3**：multi-receiver 共享 offload pool 的调度与噪声/accounting 组合，避免 PC 侧多租户排队吞噬 FPS 收益。
- **Future work 4**：当 headset 算力持续提升时，测量 Privatar 相对 pure-local 的 break-even 点是否随 avatar 分辨率/FPS 目标上移。

## 相关

- **相关概念**：[[Disaggregation]]、[[Quantization]]、Differential-Privacy、Trusted-Execution-Environment、Homomorphic-Encryption
- **同类系统**：Lombardi et al. VAE avatar pipeline、Multiface dataset、block-DCT face privacy（Ji et al.）、frequency partitioning offloading（Wang et al.）
- **同会议**：[[MLSys-2026]]
- **源材料**：[[4e732ced3463d06de0ca9a15b6153677]]、[[4e732ced3463d06de0ca9a15b6153677.pdf]]、代码 [github.com/georgia-tech-synergy-lab/Privatar](https://github.com/georgia-tech-synergy-lab/Privatar)
