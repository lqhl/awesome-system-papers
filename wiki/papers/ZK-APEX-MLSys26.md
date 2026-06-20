---
type: paper
name: ZK-APEX
full_title: "ZK-APEX: Zero-Knowledge Approximate Personalized Unlearning with Executable Proofs"
authors: [Mohammad M Maheri, Sunil Cotterill, Alex Davidson, Hamed Haddadi]
venue: MLSys
year: 2026
tags: [machine-unlearning, zero-knowledge, edge, personalization, privacy]
source_pdf: "[[735b90b4568125ed6c3f678819b6e058.pdf]]"
source_md: "[[735b90b4568125ed6c3f678819b6e058]]"
---

# ZK-APEX: Zero-Knowledge Approximate Personalized Unlearning with Executable Proofs (MLSys 2026)

> **一句话总结**：在 provider–client 边缘个性化场景下，作者观察到遗忘信息可稀疏定位、但直接 mask 会损伤本地 utility，且 SGD 式 unlearning 无法高效 ZK 证明；据此用 provider 侧 θ₀ saliency mask + client 侧 block Fisher Group-OBS 零-shot 补偿，Halo2 只验证线性 KKT 证书；ViT 恢复 ~99% 个性化 Top-1、证明 ~2h（比 retrain 验证快 >10⁷×），峰值内存 <0.7 GB。

## 问题与动机

现实部署（Apple Intelligence、Google Photos、手机键盘等）中，provider 分发预训练模型 θ₀，client 在私有数据 D_p 上本地个性化得 θ_p。GDPR/CPRA 的「被遗忘权」要求删除指定 forget-set D_f 的影响，但 provider 必须**验证** client 已正确执行 unlearning，同时 client 不能暴露 θ_p 或 D_p——这是典型的 trustless edge 场景。

现有方案各有硬伤：**exact unlearning**（在 retain set D_r 上 retrain 再 re-personalize）是 gold standard，但 client 拿不到 D_r/D_f，且每轮删除的优化步数 O(E_r|D_r| + E_p|D_p|) 在 edge 不可承受；**ZK proof-of-training/retraining**（Eisenhofer et al. 2025 等）证明成本比 inference 高数个数量级，GA/SCRUB 等多 epoch 梯度电路在 256 GB RAM 上仍 OOM，只能拆成 2²⁰ row 子电路再按样本数线性放大；**把 forget-set 明文发给 client** 违背隐私初衷。更棘手的是 **personalized unlearning**：全局 unlearning update 直接套到 θ_p 往往会破坏 task-specific adaptation。

ZK-APEX 要同时满足：(i) 在 θ_p 上有效遗忘 D_f 关联信息并保留 D_p utility；(ii) 证明生成在资源受限 edge 设备上可扩展；(iii) 确定性算子，避免 SGD 随机性带来的 forging 攻击（Zhang et al., 2024）。

## 关键观察 / 隐含假设

- **观察 1：深度网络中与 forget-set 相关的知识可稀疏定位到少量高 saliency 权重。** 论文用 forget-set 梯度/曲率（diagonal Hessian 或 empirical Fisher）对坐标打分，mask top-k 可显著抬高 L(θ; D_f)（式 7–9）；ViT/LLM 实验将 mask 集中在 Transformer MLP 子层、剪 4% 参数，forget accuracy 大幅下降。
  - **依赖假设**：D_f 敏感性与参数空间存在可分离的稀疏支撑；MLP 比 attention head 更承载待删知识（Meng et al., Pochinkov & Schoots 2024 结论）。
  - **可能失效场景**：forget-set 与 personalization 分布高度重叠、concept-level 纠缠、或需删语义概念而非样本时，固定稀疏 mask 可能不够（论文 §7 自述）。
- **观察 2：直接 mask θ_p 会损伤个性化精度，但 OBS 二阶补偿可在 D_p 曲率锚点下恢复 utility。** mask-only 使 ViT 个性化 Top-1 降约 **3.4%**；Group-OBS（block damped empirical Fisher + Schur complement）后 ZK-APEX 几乎收回全部损失（~**99%** recovery）。
  - **依赖假设**：θ_p 在 D_p 上近似平稳；非 mask 块 C 上 residual gradient、cross-curvature [H_f]_{C,M} 足够小（block-diagonal Hessian、阻尼）；补偿不抵消 mask 带来的 forgetting gain（Appendix A 有界论证）。
  - **可能失效场景**：大规模 forget-set（论文 K 节：|D_f|/|D|=20% 时 forgetting 明显变弱）、强 cross-curvature、或 adapter 更新幅度大导致 provider/client saliency 失配。
- **观察 3：mask 可在 provider 侧于 θ₀ 一次性计算，近似 client 侧 θ_p 上的 client-specific mask。** 隐私约束下 provider 不能读 θ_p，client 不能读 D_f；用 Taylor 展开（式 16–18）论证低秩/短 horizon 个性化（如 [[LoRA]]）下 ∥BA∥ 小，θ₀-based mask 与 θ_p-based mask 的 per-coordinate saliency 偏差可控。
  - **依赖假设**：个性化为 adapter-style、更新集中在少数模块；所有 client 共享同一 public mask Ψ（traceability artifact）。
  - **可能失效场景**：全参数 fine-tuning 幅度大、多 tenant 异质 D_p 导致同一 mask 对部分 client 过删/欠删；论文未做 per-client mask 的 ZK 成本对比。
- **观察 4：零-shot 确定性线性算子比迭代 SGD unlearning 更适合 ZK-SNARK。** 电路只需验证 θ_u = θ_p + δw、mask 置零、以及 C_p δw + E_M λ_M = 0 等线性 KKT 证书（式 20），无需在电路内重跑优化；避免 SGD minibatch 随机性被 adversary 利用伪造 proof。
  - **依赖假设**：Halo2 电路仅含 matvec、内积、加法；Fisher C_p 由 client 在 D_p 子样本（~1K）上离线算一次并 commit。
  - **证据强度**：强。相对 GA/SCRUB（单 epoch 仍需梯度重建子电路、OOM）与 exact retrain（>10⁷× 慢），Table 1 直接量化证明开销鸿沟。
- **假设 1：接受「程序正确性」ZK 保证，语义遗忘质量靠离线实验评估。** 有效 proof 只 certifies θ_u = U(θ_p; Ψ)，不保证 θ_u 等价于 gold-standard θ*（retrain on D_r + re-personalize）；ε_f、ε_p 通过 KL 散度对齐（式 3–4）离线测。
  - **证据强度**：中。MIA AUC、forget/personal accuracy 与 exact baseline 接近，但 cryptographic 层不覆盖 residual memorization。

## 核心方法

**问题形式化（§3）**：gold standard θ* = P(R(θ₀; D_r); D_p)，其中 R 为 retain-set retrain。近似目标：client-side U 将 θ_p 映射到 θ_u，使 D_p 上预测分布接近 θ*、D_f 上接近「从未见过 D_f」的 counterfactual，且只需 client 资源 + public Ψ。

**算子分解（§4）**：U(θ_p; Ψ) = mask + Group-OBS compensation。

1. **Provider-side mask**：在 θ₀ 上用 forget-set 梯度 g_f(θ₀) 与对角曲率代理 c_i(θ₀) 算 saliency s_i ∝ θ_{p,i}² · g_{f,i}² / (2 c_i)，取 top-k 得二进制 mask m*，发布 Ψ = (m*, M)。一次计算服务所有 client，证明负担留在 provider 侧。
2. **Client-side masking**：δw_m 将 (θ_u)_M 置零（式 10）。
3. **Group-OBS compensation**：在 D_p 上建 block-wise damped empirical Fisher C_p，解凸 QP（式 12–14）得 δw*，使非 mask 坐标调整最小化 personalization loss surrogate；实现上用 Fisher-vector product + CG，只显式求 |M|×|M| Schur complement 逆。
4. **组装**：θ_u = θ_p + δw*，满足 (θ_u)_M = 0。

**ZK-SNARK 验证（§5, Halo2）**：public inputs 为 Ψ、Com(θ_p)、Com(θ_u)、Com(C_p)；private witness 含 θ_p、θ_u、δw、λ_M、C_p。电路验证：
- Assembly：θ_u = θ_p + δw
- Mask feasibility：E_M^T δw + w_{p,M} = 0
- KKT stationarity：C_p δw + E_M λ_M = 0

按 block 分解 C_p，全局约束为 Σ_b C_p^{(b)} δw^{(b)} + E_M λ_M = 0，全是线性代数，无 nonlinear activation / lookup table。Algorithm 1 概括端到端流程：client 离线一次 commit Fisher → 收到 Ψ → 本地算 θ_u → 生成 π → provider verify。

**威胁模型**：curious verifier 只见 public inputs + π（zero-knowledge + hiding commitment）；dishonest prover 无法通过 soundness 提交 θ_u ≠ U(θ_p; Ψ)。**不覆盖**：θ_p 安全擦除、black-box 语义遗忘强度。

## 设计取舍

- **近似 unlearning vs exact retrain**：换取 edge 可行性与 10⁷× 级证明加速，语义上只逼近 θ*；当 D_p 与 D_f 分布重叠严重时，论文承认可能仍需 exact retrain（§7）。
- **Provider 统一 mask vs client-specific mask**：隐私与 ZK 成本最优，但牺牲 per-client 最优遗忘/保留权衡；structured forget-set 实验（Appendix J）显示仍可对齐 gold standard，靠 client 侧调 compensation 超参。
- **固定 mask 预算（4% MLP）vs 可变 |D_f|**：证明电路规模随 k=|M| 近线性，但过大 k 抬升 client 补偿与证明时间；|D_f| 达 20% 时固定 k 成为瓶颈（Fig. 6）。
- **程序性 ZK vs 语义遗忘**：密码学保证执行了约定算子，不保证 OBS 近似充分遗忘；MIA/accuracy 单独评估。
- **无安全删除 θ_p**：保证「可验证使用」Com(θ_u) 绑定后续推理，物理擦除旧权重视为正交问题（需 trusted hardware）。

## 实验与结果

- **设置**：ViT-B/16（ImageNet → ImageNet-Sketch 全 fine-tune）；OPT-125M（CodeParrot：Scala/C/C++/Java fine-tune + Rust [[LoRA]] 个性化）。Forget-set：ViT 33,600 样本（2.6%）；LLM Scala 子集（Scala 训练集 4.8%）。Mask：全 block MLP 4% 参数。
- **EQ1 遗忘**：相对 GA/SCRUB（为 ZK 可行性限单 epoch），ZK-APEX forget accuracy 更低、MIA AUC 更接近 50%（membership 信号更弱），遗忘更强。
- **EQ2 保留**：mask-only 个性化 accuracy 降 ~3.4%；ZK-APEX 恢复近 **99%** 所失个性化 Top-1。OPT-125M 约 **70%** 精度恢复（Table 2）。AdaptFormer 个性化（Appendix I）：mask 降 ~4.4 pt，ZK-APEX 恢复 ~3.5 pt（~80%）。
- **EQ3 ZK 效率（32 vCPU / 256 GB）**：ZK-APEX 证明 ~**2 h**，峰值内存 **<0.7 GB**，proof ~**400 MB**，验证 ~10 min；GA/SCRUB/exact 需子电路拆分且总时间远超 retrain 级。相对 retrain-based 验证 **>10⁷×** 更快。
- **EQ4 敏感性（Appendix G）**：Fisher block size、阻尼 λ、稀疏率 k 影响 retention–proof cost 权衡；适度阻尼与较大 block 更稳。
- **Edge（iPhone 14 Pro Max, A17）**：单 block 证明几小时内完成，内存与 proof 尺寸在设备容量内；block 证明可并行，provider 端验证轻量（Table 3）。
- **Structured forget-set（Appendix J）**：单类/少类 D_f 下相对 exact unlearning 偏差更小，偶发 personalization 略优于 oracle（稀疏化正则效应）。
- **|D_f| 缩放（Appendix K）**：≤10% 时 retention 偏差 <1%、forget 贴近 oracle；20% 时 forgetting 明显变弱——固定 4% mask 预算不足。

## Critical Analysis

### 论证链条

链条清晰：**稀疏定位遗忘（观察 1）→ mask 损伤 personalization（观察 2）→ OBS 补偿闭合 utility（式 12–14, Table 1）**；并行线 **SGD/retrain 不可证（观察 4）→ 线性 KKT 电路（式 20, Fig. 2）→ 2h / <0.7GB 证明（Table 1, iPhone 表）**。

较弱环节是 **θ₀ mask ≈ θ_p mask** 主要靠低秩 Taylor 论证 + 实验结果间接支持，缺少对不同 personalization 幅度、全 fine-tune vs [[LoRA]] 的系统性 mask 失配测量。另一跳步是 **Appendix A 界保证 compensation 不 undo forgetting** 依赖 block-diagonal / 小 residual gradient，实验上靠 MIA 与 forget accuracy 佐证，但未在高 overlap 分布下压力测试。

### 假设压力测试

- **统一 public mask**：多 client 异质 D_p 时，同一 Ψ 可能对某些用户过删；论文协议明确 provider 不 per-client 调 mask，只 client 调 compensation——极端异质性下 retention 下限未量化。
- **固定 4% mask**：|D_f| 线性增大时 oracle 可变更多参数，ZK-APEX 在 20% 点失效（Fig. 6）——生产需 mask 预算与删除规模联动策略，**论文未给出自适应 k 的 ZK 成本模型**。
- **Gold standard 不可达**：实验用 exact retrain+re-personalize 作 offline oracle，但协议本身不计算 θ*；当 approximate 不够时，fallback 到 exact 的代价仍回到 10⁷× 差距。
- **LLM 70% recovery**：显著低于 ViT 99%，说明 generative + [[LoRA]] 场景下 OBS 补偿更脆；是否因 Rust/Scala 分布 shift 或 mask 仅覆盖 MLP 未充分讨论。
- **Procedural vs semantic**：诚实 client 执行 U 后仍可能有 black-box 可提取的 D_f 痕迹——MIA 只是诊断，非协议保证。

### 实验可信度

- **Workload**：ImageNet-Sketch、CodeParrot Rust 代表 domain-shift 个性化，合理但规模有限（单 client 设定）；未测联邦多 client 并发证明、窗口批处理下的 provider 验证吞吐（Appendix H 有带宽/吞吐公式但偏示意）。
- **Baseline**：GA/SCRUB 限单 epoch 对 ZK 公平，但也削弱其 unlearning 能力——读者需注意 baseline 是「ZK-tractable GA/SCRUB」而非文献默认多 epoch。Exact retrain 作 oracle 而非 ZK 对比对象，合理。
- **Metric**：分类 Top-1 + MIA AUC；生成 Top-1 + PPL。缺 downstream task 级 utility、fairness、或 regulatory audit 指标。ZK 侧覆盖时间/内存/proof size/verify time，未报 proving 能耗或失败率。
- **Scale**：ViT-B/16、OPT-125M 对 edge 有代表性，但未测更大模型（ViT-L、7B LLM）证明时间缩放；block 并行上限与通信 **论文未系统测量**。

### 系统性缺陷

- **运维与产品化**：每 unlearning window 需 publish Ψ、client 上传 ~400 MB proof（Table 1 约 2–3 min @ 20–25 Mbps uplink）；百万 device 规模下 provider 验证队列、proof 聚合（recursive composition 仅提为方向）**论文未实现**。
- **θ_p 残留与 secure erasure**：明确 out of scope；合规场景可能要求硬件级删除，仅靠 Com(θ_u) 绑定不足以满足所有 regulator 解释。
- **Commitment 前置**：假设 Com(θ_p) 已通过 proof-of-training/personalization 建立——该成本未计入 Table 1 端到端账单。
- **故障与降级**：证明生成失败、Fisher 估计噪声、或 commitment 不一致时的 client 行为 **论文未讨论**。
- **与 on-device training 栈集成**：与 ExecuTorch/Core ML 等 runtime 的实际耦合、量化模型上 Fisher 精度 **论文未覆盖**。

## 局限与 Future Work

- **局限 1**：非 mask 项（residual gradient、cross-curvature、quadratic on C）需足够小，否则 compensation 可能部分抵消遗忘；高 |D_f|、高 overlap 时更明显（§7, Appendix K）。
- **局限 2**：不保证安全擦除 θ_p；archival copy 可违背严格「被遗忘」语义。
- **局限 3**：语义遗忘非密码学性质；接受 proof 只保证算子执行正确。
- **局限 4**：Provider 固定 mask 预算在超大删除请求下成为瓶颈；LLM 恢复率低于 ViT。
- **Future work 1**：将 compensation 投影到与 forget 方向正交的子空间，在保持 ZK 线性的前提下进一步隔离 forgetting gain（§7）。
- **Future work 2**：评测 MPC / 新型 polynomial-commitment SNARK、recursive proof 聚合，降低 400 MB 级 proof 的带宽与验证扇出。
- **Future work 3**：mask 构造引入 differential privacy，防御 verification 过程中的 inversion/reconstruction（Zhang et al., 2024）。
- **Future work 4**：扩展到 concept-level / feature-level unlearning，以及 overlap 极高时 approximate vs exact 的判定准则与混合协议。

## 相关

- **相关概念**：[[LoRA]]、[[Quantization]]（Fisher/梯度估计与部署精度）、零知识证明、machine unlearning、Optimal Brain Surgeon
- **同类系统**：SISA（exact partition retrain）、SCRUB/Gradient Ascent（近似 unlearning）、Eisenhofer et al. 2025（verifiable exact unlearning）、Telesparse（ZK DNN 验证）
- **部署语境**：边缘个性化（Apple Intelligence 类）、GDPR 合规验证
- **同会议**：[[MLSys-2026]]