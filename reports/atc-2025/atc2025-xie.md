# Revealing Floating-Point Accumulation Orders in Software/Hardware Implementations

**作者**：Peichen Xie, Yanjie Gao, Yang Wang, Jilong Xue（均来自 Microsoft Research）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/xie
**源文件**：[[atc2025-xie.pdf]]

---

## 一、背景

浮点累加运算（AccumOps），包括求和、点积、矩阵-向量乘法和矩阵乘法，是几乎所有计算领域的基础操作。然而，由于浮点加法不具备结合律，不同的累加顺序会产生不同的数值结果。例如在 float16 下，`(0.5 + 512) + 512.5 = 1025`，而 `0.5 + (512 + 512.5) = 1024`。

目前的软硬件实现普遍不公开其累加顺序。不同 CPU/GPU 架构、不同 BLAS 后端（Intel MKL、OpenBLAS、cuBLAS）、不同编译器优化策略，都可能导致相同代码在不同系统上产生不同结果。这对航空航天、金融等要求严格数值可复现性的领域构成严重威胁。

---

## 二、要解决的问题

1. **累加顺序不透明**：NumPy、PyTorch、JAX 等主流数值库以及 GPU Tensor Core 等硬件加速器，均未文档化其累加顺序，开发者无法确保跨系统的数值一致性。
2. **静态分析不可行**：源码分析繁琐且不适用于黑盒实现和编译器优化；运行时 trace 分析缺乏自动化工具。
3. **暴力搜索不可行**：所有可能的累加顺序数量为 Catalan 数 $C_{n-1} = O(4^n / n^{3/2})$，暴力枚举的时间复杂度为指数级，完全不实际。

---

## 三、洞察与设计

**关键洞察**：通过构造特殊输入（masked all-one array），利用浮点加法的 swamping 现象（极大数 M 加上小数仍等于 M），可以从黑盒实现的数值输出中确定性地推断出累加顺序——具体地，将两个位置设为 $+M$ 和 $-M$，其余为 1.0，则输出值恰好等于"未被 ±M 遮蔽的加数个数"，而这个数与 summation tree 中对应两个节点的最低公共祖先（LCA）子树大小直接对应。

基于此洞察，FPRev 的设计分为三步：

1. **构造测试输入**：对每对 $(i, j)$，构造 masked all-one array $A^{i,j}$，其中位置 $i$ 为 $M$，位置 $j$ 为 $-M$，其余为 1.0。
2. **分析输出**：从 $l_{i,j} = n - \text{SUMIMPL}(A^{i,j})$ 得到 LCA 子树大小信息。
3. **自底向上构建 summation tree**：将 $l_{i,j}$ 按升序排列，使用 union-find 数据结构逐步合并子树。

**算法改进**：

- **BasicFPRev**（基础方案）：需计算所有 $n(n-1)/2$ 个 $l_{i,j}$，时间复杂度 $\Theta(n^2 t(n))$。
- **FPRev**（优化方案）：按需计算 $l_{i,j}$，消除冗余查询，时间复杂度降至 $\Omega(n \cdot t(n))$ ~ $O(n^2 t(n))$，实际接近最优。
- **多路树扩展**：对 Tensor Core 等使用多项融合求和（multi-term fused summation）的硬件，扩展为多路树模型，通过比较子树大小与叶节点数来区分"兄弟节点"和"父节点"两种情况。

---

## 四、实现细节

- **实现语言**：Python 3.11，开源于 https://github.com/peichenxie/FPRev。
- **核心数据结构**：
  - Summation tree：有根满二叉树（标准累加）或多路树（Tensor Core 融合求和）
  - Union-Find（并查集）：用于自底向上合并子树，均摊复杂度 $O(\alpha(n))$
- **测试输入构造**：$M = 2^{127}$（float32）或 $M = 2^{1023}$（float64）；对低动态范围格式（FP8-e4m3 等），使用缩放因子 $e$ 替代 1.0，再将输出除以 $e$ 还原。
- **精度限制处理**：当累加器精度不足以精确表示 $n-2$ 个 1.0 之和时，动态将已构建子树压缩为单一节点（用 0 替代对应位置），递归处理子问题。
- **多路树判断**：在 BUILDSUBTREE 返回值中额外返回 $n^{T_c}_{\text{leaves}}$（完整子树叶节点数），通过与 $|J_l|$ 比较区分兄弟/父节点关系。

---

## 五、实验结果

**实验平台**：
- CPU：Intel Xeon E5-2690 v4、AMD EPYC 7V13、Intel Xeon Silver 4210
- GPU：NVIDIA V100、A100、H100

**Case Study 发现**：

| 库/操作 | 跨平台可复现性 | 累加方式 |
|---|---|---|
| NumPy summation (float32) | 三款 CPU 一致 | n<8 顺序累加；8≤n≤128 八路交错累加 + pairwise sum |
| NumPy BLAS ops (dot/gemv/gemm) | CPU 间不一致 | 依赖后端（MKL vs OpenBLAS），受硬件特性影响 |
| PyTorch summation (float32) | 三款 GPU 一致 | — |
| PyTorch BLAS ops | GPU 间不一致 | cuBLAS 后端 |
| Tensor Core (float16 GEMM) | GPU 间不一致 | V100: 5-way tree; A100: 9-way tree; H100: 17-way tree |

**性能对比**（summation function）：

| n | NaiveSol | BasicFPRev | FPRev |
|---|---|---|---|
| 16 | >24 小时 | <0.01s | <0.01s |
| 8192 | — | >100s | ~1s |

**不同操作的加速比**（n=256，FPRev vs BasicFPRev）：

| 操作 | 加速比 |
|---|---|
| Dot product | 13.0× |
| Matrix-vector multiplication | 32.3× |
| Matrix multiplication | 82.1× |

---

## 六、批判性分析

1. **适用范围受限**：FPRev 明确排除了随机化累加和输入依赖顺序的实现，也排除了 AtomicAdd 等受线程调度影响的操作。然而论文并未量化这些被排除情况在实际生态中的占比——如果主流深度学习训练中大量使用非确定性 reduction，FPRev 的实际覆盖面可能远小于论文暗示的广泛适用性。

2. **实验规模偏小**：Case study 测试的 NumPy 版本为 1.26、PyTorch 版本为 2.3，仅各一个版本。对于"验证跨系统可复现性"这个目标，仅测试 3 款 CPU 和 3 款 GPU 的说服力有限，尤其是未涵盖 AMD GPU、Apple Silicon、ARM 服务器等日益重要的平台。

3. **最坏情况复杂度仍为 $O(n^2 t(n))$**：虽然论文强调"实际中很少出现"，但并未提供理论保证或对实际库的统计分析来支撑这个乐观声明。所谓"cache-unfriendly 的右到左累加顺序没有库使用"只是经验观察。

4. **与数值可复现性的关系被过度渲染**：FPRev 揭示的是累加顺序，但从"知道顺序"到"实现可复现软件"之间还有很大的 gap——开发者需要在新系统上精确复现该顺序，这本身就是一个非平凡的工程问题，论文对此只一笔带过。

5. **Tensor Core 结果验证方式**：论文称在 V100/A100/H100 上分别发现 5-way/9-way/17-way tree，与已有工作 [9, 18] 结论一致。这更多是对已知事实的再确认，而非新发现，但论文并未清楚区分增量贡献。

---

## 七、AI Infra / MLSys 视角

1. **深度学习训练的数值一致性**：混合精度训练（BF16/FP8）在不同 GPU 代际上使用不同的 Tensor Core 融合求和方式（5-way vs 9-way vs 17-way），这意味着同一训练脚本在不同 GPU 上会产生不同的数值结果。FPRev 的方法可以系统性地揭示这些差异，帮助 AI Infra 团队在多代 GPU 混合部署时预判数值漂移问题。

2. **Microscaling 格式（MXFP4/MXFP6）**：论文在 future work 中提到下一代 Tensor Core 将支持 microscaling 数据格式。随着超低精度训练/推理的普及，FPRev 的方法可用于揭示 block-level 的累加行为，这对理解和优化 FP4/FP6 推理精度至关重要。

3. **确定性训练/推理**：在 LLM serving 场景中，确定性输出对于调试、A/B 测试和合规性非常重要。FPRev 可以帮助识别 cuBLAS 等后端中的非确定性源头，指导开发者选择确定性 kernel 或设计容忍策略。

4. **潜在研究方向**：
   - 将 FPRev 集成到 CI/CD 中，在框架升级或硬件迁移时自动检测累加顺序变化
   - 对分布式 AllReduce 操作的累加顺序进行分析，揭示跨节点数值不一致性的根源
   - 结合 FPRev 发现的顺序信息，设计针对特定硬件的数值稳定 kernel

---

## 八、总结

FPRev 是一个通过数值测试非侵入式揭示浮点累加顺序的诊断工具，利用 swamping 现象构造特殊输入，将指数级的暴力搜索降低到多项式时间复杂度。Case study 揭示了 NumPy 和 PyTorch 中未公开的累加顺序，包括 Tensor Core 多路融合求和的具体结构。该工具对需要数值可复现性的场景（科学计算、金融、安全关键系统）有直接价值，但其实际影响力受限于适用范围（排除非确定性实现）和从"揭示顺序"到"实现可复现性"之间的工程 gap。
