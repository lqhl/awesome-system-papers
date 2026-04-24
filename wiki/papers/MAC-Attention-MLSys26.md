---
type: paper
name: MAC-Attention
full_title: "MAC-Attention: A Match-Amend-Complete Scheme for Fast and Accurate Attention Computation"
authors: [Jinghan Yao, Sam Ade Jacobs, Walid Krichene, Masahiro Tanaka, Dhabaleswar K Panda]
venue: MLSys
year: 2026
tags: [long-context, attention, kv-cache, inference, rope]
source_pdf: "[[5ef059938ba799aaa845e1c2e8a762bd.pdf]]"
source_md: "[[5ef059938ba799aaa845e1c2e8a762bd]]"
---

# MAC-Attention: A Match-Amend-Complete Scheme for Fast and Accurate Attention Computation (MLSys 2026)

> **一句话总结**：通过匹配 pre-RoPE 相似查询、复用其 attention summary 并只在边界 band 和 tail 上重新计算，MAC-Attention 在 128K 上下文下将 KV 访问减少最多 99%、token 生成延迟降低 60%+、attention 阶段加速 14.3×，同时保持 full attention 精度。

## 问题

长上下文 LLM 解码是 IO-bound 的：每生成一个 token 都要重新读取不断增长的 [[KV-Cache]]。现有加速方向有两类：

- **压缩**（低秩投影、[[Quantization]]）：降低保真度
- **选择/驱逐**（token/page eviction）：限制可访问范围

这两类方法在需要 delayed recall、跨文档链接、长生成/推理的任务上会显著掉精度。作者观察到同一 decoding stream 内 query 向量有很高的 **temporal redundancy**（多轮对话、代码生成、长推理中 query 模式重复），提出第三条路：**在流内复用 attention 计算**，同时保留对全序列的访问。

## 核心方法

**Match-Amend-Complete** 三阶段：

1. **Match（pre-RoPE L2）**：维护每个请求一个 size-K（≤1024）的 ring buffer，存最近 K 个 **pre-RoPE** 查询 $\tilde Q_t$。新 query 来时，在 ring 内做 L2 匹配。关键选择：
   - **Pre-RoPE 而非 post-RoPE**：RoPE 的相对旋转 $R(m-p)$ 会让 post-RoPE 距离随 $|m-p|$ 增大而爆炸（即使 semantically 相似），pre-RoPE 匹配剥离位置相位
   - **L2 而非 cosine**：L2 同时控制方向和 magnitude，直接上界 logit 近似误差
   - 阈值：$\|\tilde Q_m - \tilde Q_p\| < \sqrt{2d}(1-\tau)$（relative to random baseline）

2. **Amend（rectification band）**：直接复用整个 prefix summary 误差集中在 match 位置附近的 high-mass band（softmax 质量集中在 recent tokens）。方法是缓存 **rectified** summary $AS_{1:p-r}^{(p)}$（剔除最近 $r$ 个 token 的贡献），decode 时重新计算 $[p-r+1, m]$ 这段的 band+tail

3. **Complete（log-domain merge）**：用 numerically stable 的 [[Flash-Attention]]-style associative log-domain merge 合并 cached prefix 和 fresh band+tail：
   $$o_m = \frac{S^{(p)}_{1:p-r} + S^{(m)}_{p-r+1:m}}{Z^{(p)}_{1:p-r} + Z^{(m)}_{p-r+1:m}}$$

**Cache 结构**：每请求两个 ring（query ring + rectified summary ring），容量 K。插入 $O(1)$、匹配 $O(K)$。命中时 compute 和 bandwidth 与序列长度 **无关**（常数）；miss 时 fall back 到 full attention，结果 bit-exact。

**兼容性**：training-free、model-agnostic，与 IO-aware kernel、[[PagedAttention]]、MQA/GQA 组合。MQA/GQA 下匹配在 query head 粒度做（而 KV 在 group 粒度），matching kernel 更 memory-bound 但更轻量。

## 关键结果

- **KV 访问减少 up to 99%**（128K 以上匹配率极高）
- **128K 下 per-token 延迟降低 > 60%**
- **Attention 阶段加速 ≥ 14.3×**，256K 下可达 ~46×
- **端到端加速 up to 2.6×**（LLaMA）
- 在 LongBench v2（120K）、RULER（120K）、LongGenBench（16K 连续生成）上与 **FlashInfer** 对比维持 full-attention quality，不掉点

## 相关

- **相关概念**：[[KV-Cache]]、[[Flash-Attention]]、[[PagedAttention]]、[[Attention]]
- **同类系统**：FlashInfer（baseline）、StreamingLLM、H2O（token eviction 系）
- **同会议**：[[MLSys-2026]]
