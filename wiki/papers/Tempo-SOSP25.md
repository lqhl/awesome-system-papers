---
type: paper
name: Tempo
full_title: "Tempo: Compiled Dynamic Deep Learning with Symbolic Dependence Graphs"
authors: [Pedro F. Silvestre, Peter Pietzuch]
venue: SOSP
year: 2025
tags: [dl-compiler, dynamic-shapes, polyhedral, reinforcement-learning, llm-inference]
source_pdf: "[[3731569.3764840.pdf]]"
source_md: "[[3731569.3764840]]"
---

# Tempo: Compiled Dynamic Deep Learning with Symbolic Dependence Graphs (SOSP 2025)

> **一句话总结**:用 recurrent tensor + 符号依赖图 + 多面体模型调度,把带时间动态依赖的 DL 程序当作单一图做 whole-program 编译,Llama-3.2-3B 解码比 JAX 快 **7×**,RL 算法比 5 个 baseline 快 **54×**,峰值显存低 **16×**。

## 问题

很多 DL 算法天然用递归方程定义——[[Attention]] 在 timestep t 依赖过去所有 K/V;[[Reinforcement-Learning]] 的 loss 依赖未来 reward——现有 DL 系统处理这种动态依赖都有短板:

- **Eager 系统** (PyTorch、TF-Eager):Python 里动态 dispatch,支持动态但无法做 whole-program 编译优化
- **Graph 系统** (TensorFlow、JAX):要求静态 shape,用户被迫 (a) per-shape 编译,(b) unroll 循环,(c) pad + mask——都有严重性能或内存开销

具体后果:LLM 推理中 K/V cache 被迫外化到 vLLM 等系统,不同 attention 类型(causal、window、linear、global)需要不同 cache policy,每种新 attention 都要大量工程;RL 框架不得不把 actor/learner 拆成两张独立的图,带来三个损失:(1) actor 中间激活被丢弃,learner 重新前向——推理开销翻倍;(2) actor/learner 必须串行化;(3) "all-at-once" learning 导致峰值显存高。

## 核心方法

**关键 insight**:动态 DL 算法中的张量有隐式的时间维度,显式化后动态依赖变成正则的张量索引操作,且这种动态性有结构,可用 timestep symbol 的符号表达式简洁表示。

四个技术贡献:

1. **Recurrent Tensor (RT) 声明式编程模型**(§3):RT 有空间维度 + 时间维度(如 t、i),每个时间维有 current step 和 upper bound 两个符号。RT 可用符号表达式(含算术、比较、min/max、slice `start:stop:step`)在时间维上索引,表达动态依赖。有良好定义的 domain broadcast 和反向传播语义(符号化 auto-diff:`∇x[t] = Σ_{t' ∈ φ⁻¹(t)} f'(∇y[t'])`)。
2. **符号依赖图 (Symbolic Dependence Graph, SDG)**(§4):每个 vertex 是 operator,带时间 domain;edge 用从 RT 提取的符号表达式描述跨 timestep 依赖。把经典编译优化(代数简化、冗余消除)扩展到动态计算;把 vectorization 和 tiling 视作维度在时间/空间之间的迁移。通过把动态依赖 tile 成静态 tile,复用现有静态 code-generator 做 fusion。
3. **Polyhedral 调度**(§5.1):SDG 无法拓扑排序(有未来依赖),改用 [[Polyhedral-Model]] 把 SDG 翻译成线性约束,解整数线性规划得到每个 timestep 的物理执行时间,生成 AST 表示的命令式程序。
4. **自动显存管理**(§5.2):用显式 memory-management op(deallocation、donation、GPU/CPU swap)augment SDG,通过依赖边约束,调度时一并解出。

RL 例子(Alg. 1 的 REINFORCE):用户只写一个 loss,loop 里 forward 自然复用,不需要 replay buffer——Tempo 根据动态依赖自动管理存储。不同 attention pattern 只需改 `φ(t)` 表达式,cache policy 自动推导。

## 关键结果

- **Llama-3.2-3B 解码**:比 PyTorch/JAX 快 **7×**,可扩展到 **4×** 更长的序列(因识别动态依赖减少不必要存储)
- **RL 训练**:REINFORCE / A2C / PPO 三种算法比 5 个 baseline(CleanRL 等)快 **54×**,end-to-end 训练时间
- **峰值显存**:低 **16×**(靠 tiling + 及时 deallocation)
- 原型支持 Torch 和 JAX 两个执行后端,单 GPU

## 相关

- **相关概念**:[[Polyhedral-Model]]、[[Dataflow-Graph]]、[[Auto-Diff]]、[[KV-Cache]]、[[Attention]]、[[Operator-Fusion]]、[[Tiling]]、[[Dynamic-Shape]]
- **同类系统**:PyTorch、TensorFlow、JAX、[[vLLM]]、TVM、XLA、CleanRL 等 RL 框架
- **同会议**:[[SOSP-2025]]
