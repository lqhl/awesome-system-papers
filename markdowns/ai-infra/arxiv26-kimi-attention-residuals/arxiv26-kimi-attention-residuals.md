# ATTENTION RESIDUALS

TECHNICAL REPORT OF ATTENTION RESIDUALS

Kimi Team  https://github.com/MoonshotAI/Attention-Residuals

## ABSTRACT

Residual connections [12] with PreNorm [60] are standard in modern LLMs, yet they accumulate all layer outputs with fixed unit weights. This uniform aggregation causes uncontrolled hidden-state growth with depth, progressively diluting each layer’s contribution [27]. We propose Attention Residuals (AttnRes), which replaces this fixed accumulation with softmax attention over preceding layer outputs, allowing each layer to selectively aggregate earlier representations with learned, inputdependent weights. To address the memory and communication overhead of attending over all preceding layer outputs for large-scale model training, we introduce Block AttnRes, which partitions layers into blocks and attends over block-level representations, reducing the memory footprint while preserving most of the gains of full AttnRes. Combined with cache-based pipeline communication and a two-phase computation strategy, Block AttnRes becomes a practical drop-in replacement for standard residual connections with minimal overhead.

Scaling law experiments confirm that the improvement is consistent across model sizes, and ablations validate the benefit of content-dependent depth-wise selection. We further integrate AttnRes into the Kimi Linear architecture [69] (48B total / 3B activated parameters) and pre-train on 1.4T tokens, where AttnRes mitigates PreNorm dilution, yielding more uniform output magnitudes and gradient distribution across depth, and improves downstream performance across all evaluated tasks.

![](images/40eb28e463aaa8b6347e201092ed0854738e6b530362d1164c51b60405aeaad5.jpg)  
(a) Standard Residuals

![](images/6a3a72e81fd66e57518a8d296fd85cfed22e87dddac939d160c89894b277e6a4.jpg)  
(b) Full Attention Residuals

![](images/7e51272a76fff560ed9d8f3722642ed3d0be76df254eb57355e20721dcde7c71.jpg)  
(c) Block Attention Residuals  
Figure 1: Overview of Attention Residuals. (a) Standard Residuals: standard residual connections with uniform additive accumulation. (b) Full AttnRes: each layer selectively aggregates all previous layer outputs via learned attention weights. (c) Block AttnRes: layers are grouped into blocks, reducing memory from O(Ld) to O(N d).

## 1 Introduction

Standard residual connections [12] are the de facto building block of modern LLMs [35, 51, 9]. The update $h _ { l } =$ $h _ { l - 1 } + f _ { l - 1 } ( h _ { l - 1 } )$ is widely understood as a gradient highway that lets gradients bypass transformations via identity mappings, enabling stable training at depth. Yet residuals also play a second role that has received less attention. Unrolling the recurrence shows that every layer receives the same uniformly-weighted sum of all prior layer outputs; residuals define how information aggregates across depth. Unlike sequence mixing and expert routing, which now employ learnable input-dependent weighting [53, 20, 9], this depth-wise aggregation remains governed by fixed unit weights, with no mechanism to selectively emphasize or suppress individual layer contributions.

In practice, PreNorm [60] has become the dominant paradigm, yet its unweighted accumulation causes hidden-state magnitudes to grow as O(L) with depth, progressively diluting each layer’s relative contribution [27]. Early-layer information is buried and cannot be selectively retrieved; empirically, a significant fraction of layers can be pruned with minimal loss [11]. Recent efforts such as scaled residual paths [54] and multi-stream recurrences [72] remain bound to the additive recurrence, while methods that do introduce cross-layer access [36, 56] are difficult to scale. The situation parallels the challenges that recurrent neural networks (RNNs) faced over the sequence dimension before attention mechanism provided an alternative.

We observe a formal duality between depth-wise accumulation and the sequential recurrence in RNNs. Building on this duality, we propose Attention Residuals (AttnRes), which replaces the fixed accumulation $\begin{array} { r } { \pmb { h } _ { l } = \sum _ { i } \pmb { v } _ { i } } \end{array}$ with $\begin{array} { r } { \pmb { h } _ { l } = \sum _ { i } \alpha _ { i  l } \cdot \pmb { v } _ { i } } \end{array}$ , where $\alpha _ { i \to l }$ are softmax attention weights computed from a single learned pseudo-query $\boldsymbol { w } _ { l } \in \mathbb { R } ^ { d }$ per layer. This lightweight mechanism enables selective, content-aware retrieval across depth with only one d-dimensional vector per layer. Indeed, standard residual connections and prior recurrence-based variants can all be shown to perform depth-wise linear attention; AttnRes generalizes them to depth-wise softmax attention, completing for depth the same linear-to-softmax transition that proved transformative over sequences (§6.2, §6.1).

In standard training, Full AttnRes adds negligible overhead, since the layer outputs it requires are already retained for backpropagation. At scale, however, activation recomputation and pipeline parallelism are routinely employed, and these activations must now be explicitly preserved and communicated across pipeline stages. We introduce Block AttnRes to maintain efficiency in this regime: layers are partitioned into N blocks, each reduced to a single representation via standard residuals, with cross-block attention applied only over the N block-level summaries. This brings both memory and communication down to $O ( N d )$ , and together with infrastructure optimizations (§4), Block AttnRes serves as a drop-in replacement for standard residual connections with marginal training cost and negligible inference latency overhead.

Scaling law experiments confirm that AttnRes consistently outperforms the baseline across compute budgets, with Block AttnRes matching the loss of a baseline trained with 1.25× more compute. We further integrate AttnRes into the Kimi Linear architecture [69] (48B total / 3B activated parameters) and pre-train on 1.4T tokens. Analysis of the resulting training dynamics reveals that AttnRes mitigates PreNorm dilution, with output magnitudes remaining bounded across depth and gradient norms distributing more uniformly across layers. On downstream benchmarks, our final model improves over the baseline across all evaluated tasks.

## Contributions

• Attention Residuals. We propose AttnRes, which replaces fixed residual accumulation with learned softmax attention over depth, and its scalable variant Block AttnRes that reduces memory and communication from $O ( L d )$ to $O ( N d )$ . Through a unified structured-matrix analysis, we show that standard residuals and prior recurrence-based variants correspond to depth-wise linear attention, while AttnRes performs depth-wise softmax attention.

• Infrastructure for scale. We develop system optimizations that make Block AttnRes practical and efficient at scale, including cross-stage caching that eliminates redundant transfers under pipeline parallelism and a two-phase inference strategy that amortizes cross-block attention via online softmax [31]. The resulting training overhead is marginal, and the inference latency overhead is less than 2% on typical inference workloads.

• Comprehensive evaluation and analysis. We validate AttnRes through scaling law experiments, component ablations, and downstream benchmarks on a 48B-parameter model pre-trained on 1.4T tokens, demonstrating consistent improvements over standard residual connections. Training dynamics analysis further reveals that AttnRes mitigates PreNorm dilution, yielding bounded hidden-state magnitudes and more uniform gradient distribution across depth.

## 2 Motivation

Notation. Consider a batch of input sequences with shape $B \times T \times d ,$ where B is the batch size, $T$ is the sequence length, and d is the hidden dimension. For clarity, we write formulas for a single token: $\boldsymbol { h } _ { l } \in \mathbb { R } ^ { d }$ denotes the hidden state entering layer l, where $l \in \{ 1 , \ldots , L \}$ is the layer index and L is the total number of layers. The token embedding is $\pmb { h } _ { 1 }$ The function $f _ { l }$ represents the transformation applied by layer l. In Transformer models, we treat each self-attention or MLP as an individual layer.

## 2.1 Training Deep Networks via Residuals

Residual Learning. Residual learning [12] proves to be a critical technique in training deep networks as it allows gradients to bypass transformations. Specifically, each layer updates the hidden state as:

$$
\pmb { h } _ { l } = \pmb { h } _ { l - 1 } + f _ { l - 1 } ( \pmb { h } _ { l - 1 } )
$$

Expanding this recurrence, the hidden state at layer l is the sum of the embedding and all preceding layer outputs: $\begin{array} { r } { h _ { l } = h _ { 1 } + \sum _ { i = 1 } ^ { l - 1 } f _ { i } ( h _ { i } ) } \end{array}$ . The key insight behind residual connections is identity mapping: each layer preserves a direct path for both information and gradients to flow unchanged. During back-propagation, the gradient with respect to an intermediate hidden state is:

$$
{ \frac { \partial { \mathcal { L } } } { \partial \pmb { h } _ { l } } } = { \frac { \partial { \mathcal { L } } } { \partial \pmb { h } _ { L } } } \cdot \prod _ { j = l } ^ { L - 1 } \left( \mathbf { I } + { \frac { \partial f _ { j } } { \partial \pmb { h } _ { j } } } \right)
$$

Expanding this product yields I plus higher-order terms involving the layer Jacobians $\partial f _ { j } / \partial h _ { j }$ . The identity term is always preserved, providing a direct gradient path from the loss to any layer regardless of depth.

Generalizing Residuals. While effective, the fixed unit coefficients in the residual update treat every layer’s contribution uniformly, offering no mechanism to adapt the mixing across depth. Highway networks [45] relax this by introducing learned element-wise gates:

$$
\pmb { h } _ { l } = ( 1 - \pmb { g } _ { l } ) \odot \pmb { h } _ { l - 1 } + \pmb { g } _ { l } \odot f _ { l - 1 } ( \pmb { h } _ { l - 1 } )
$$

where $\mathbf {  { g } } _ { l } \in [ 0 , 1 ] ^ { d }$ interpolates between the transformation and the identity path. More generally, both are instances of a weighted recurrence $\pmb { h } _ { l } = \alpha _ { l } \cdot \pmb { h } _ { l - 1 } + \beta _ { l } \cdot \pmb { f } _ { l - 1 } ( \pmb { h } _ { l - 1 } )$ , with residual setting $\alpha _ { l } = \beta _ { l } = 1$ and Highway setting $\alpha _ { l } { = } 1 { - } g _ { l } , \beta _ { l } { = } g _ { l }$

Limitations. Whether fixed or gated, both approaches share a fundamental constraint: each layer can only access its immediate input $\boldsymbol { h } _ { l - 1 }$ , a single compressed state that conflates all earlier layer outputs, rather than the individual outputs themselves. This entails several limitations: (1) no selective access: different layer types $( \mathrm { e . g . }$ , attention vs. MLP) receive the same aggregated state, despite potentially benefiting from different weightings; (2) irreversible loss: information lost through aggregation cannot be selectively recovered in deeper layers; and (3) output growth: later layers learn increasingly larger outputs to gain influence over the accumulated residual, which can destabilize training. These limitations motivate a mechanism that lets each layer selectively aggregate information from all preceding layers.

## 3 Attention Residuals: A Unified View of Time and Depth

The limitations discussed above are reminiscent of similar bottlenecks in sequence modeling, suggesting that we seek similar solutions for the depth dimension.

The Duality of Time and Depth. Like RNNs over time, residual connections compress all prior information into a single state $\boldsymbol { h } _ { l }$ over depth. For sequence modeling, the Transformer improved upon RNNs by replacing recurrence with attention [3, 52], allowing each position to selectively access all previous positions with data-dependent weights. We propose the same methodology for depth:

$$
\pmb { h } _ { l } = \alpha _ { 0  l } \cdot \pmb { h } _ { 1 } + \sum _ { i = 1 } ^ { l - 1 } \alpha _ { i  l } \cdot f _ { i } ( \pmb { h } _ { i } )\tag{1}
$$

where $\alpha _ { i \to l }$ are layer-specific attention weights satisfying $\begin{array} { r } { \sum _ { i = 0 } ^ { l - 1 } \alpha _ { i  l } = 1 } \end{array}$ . Unlike sequence length (which can reach millions of tokens), network depth is typically modest $( L < 1 0 0 0 )$ , making $O ( L ^ { 2 } )$ attention over depth computationally feasible. We call this approach Attention Residuals, abbreviated as AttnRes.

## 3.1 Full Attention Residuals

The attention weights can be written as $\alpha _ { i \to l } = \phi ( { \pmb q } _ { l } , { \pmb k } _ { i } )$ for a kernel function $\phi \colon \mathbb { R } ^ { d } \times \mathbb { R } ^ { d } \to \mathbb { R } _ { > 0 }$ , where $\pmb q _ { l }$ and $k _ { i }$ are query and key vectors $[ 2 3 , 7 0 ]$ Different choices of ϕ recover different residual variants $( \ S 6 . 2 )$ ; we adopt ${ \phi } ( \pmb q , \pmb k ) \dot { = } \dot { \exp { ( \pmb q ^ { \top } } }$ RMSNorm(k) [66] with normalization, yielding softmax attention over depth:

$$
\alpha _ { i  l } = \frac { \phi ( \pmb q _ { l } , \pmb k _ { i } ) } { \sum _ { j = 0 } ^ { l - 1 } \phi ( \pmb q _ { l } , \pmb k _ { j } ) }\tag{2}
$$

For each layer $l ,$ we define:

$$
\begin{array} { r } { \pmb { q } _ { l } = \pmb { w } _ { l } , \qquad \pmb { k } _ { i } = \pmb { v } _ { i } = \pmb { \{ { h } _ { 1 } } \atop { f _ { i } ( \pmb { h } _ { i } ) }  } \quad i = 0  \\ { \qquad \pmb { k } _ { i } = \pmb { v } _ { i } = \pmb { \{ { h } _ { 1 } } \atop { f _ { i } ( \pmb { h } _ { i } ) }  } \quad i \leq i \leq l - 1  \end{array}\tag{3}
$$

where the query $q _ { l } = w _ { l }$ is a layer-specific learnable vector in $\mathbb { R } ^ { d } .$ . The RMSNorm inside $\phi$ prevents layers with large-magnitude outputs from dominating the attention weights. The input to layer l is then:

$$
h _ { l } = \sum _ { i = 0 } ^ { l - 1 } \alpha _ { i  l } \cdot v _ { i }\tag{4}
$$

We call this form full attention residuals. For each token, Full AttnRes requires $O ( L ^ { 2 } d )$ arithmetic and $O ( L d )$ memory to store layer outputs. Since depth is far smaller than sequence length, the arithmetic cost is modest.

Overhead. The $O ( L d )$ memory overlaps entirely with the activations already retained for backpropagation, so Full AttnRes introduces no additional memory overhead in vanilla training. At scale, however, activation recomputation and pipeline parallelism are widely adopted: layer outputs that would otherwise be freed and recomputed must now be kept alive for all subsequent layers, and under pipeline parallelism each must further be transmitted across stage boundaries. Both the memory and communication overhead then grow as $O ( L d )$

Blockwise optimization. A deliberate design choice in Full AttnRes is that the pseudo-query ${ \pmb w } _ { l }$ is a learned parameter decoupled from the layer’s forward computation. This independence means that attention weights for any group of layers can be computed in parallel without waiting for their sequential outputs, and in particular permits grouping the L layers into N blocks of S layers each and batching the attention computation within each block, reducing per-layer memory I/O from $O ( L d )$ to $\mathbf { \bar { \xi } } O ( ( S { + } N ) d )$ (we defer the detailed two-phase strategy to §4). Under current distributed training regimes, however, the dominant cost is not local memory bandwidth but cross-stage communication under pipeline parallelism: every layer output must still be transmitted between stages, and this $O ( L d )$ communication overhead cannot be alleviated by local batching. This motivates the Block AttnRes variant introduced below, which reduces the number of cross-stage representations from L to N. We anticipate that future interconnect improvements will make the full $O ( L d )$ communication practical, fully realizing the potential of Full AttnRes.

## 3.2 Block Attention Residuals

We propose Block Attention Residuals, which partitions the L layers into N blocks: within each block, the layer outputs are reduced to a single representation via summation, and across blocks, we apply full attention over only N block-level representations and the token embedding. This reduces both memory and communication overhead from $O ( L d )$ to $\bar { O ( N d ) }$

Intra-Block Accumulation. Specifically, we divide the L layers into N blocks of $S = L / N$ layers each, assuming L is divisible by N ; otherwise, the last block contains the remaining L mod N layers. Let $B _ { n }$ denote the set of layer indices in block $n \left( n = 1 , \ldots , N \right)$ . To form a block, we sum all of its layer outputs:

$$
b _ { n } = \sum _ { j \in B _ { n } } f _ { j } ( h _ { j } )\tag{5}
$$

We further denote $b _ { n } ^ { i }$ as the partial sum over the first i layers in $B _ { n }$ , so that $\boldsymbol { b _ { n } } = \boldsymbol { b } _ { n } ^ { S }$ . When L is not divisible by N , the final partial sum is taken as the last block’s representation. As in Full AttnRes, the RMSNorm inside ϕ prevents magnitude differences between complete blocks and partial sums from biasing the attention weights.

```python
1 def block_attn_res(blocks: list[Tensor], partial_block: Tensor, proj: Linear, norm: RMSNorm) -> Tensor:
2 """
3 Inter-block attention: attend over block reps + partial sum.
4 blocks:
5 N tensors of shape [B, T, D]: completed block representations for each previous block
6 partial_block:
7 [B, T, D]: intra-block partial sum (b_n^i)
8
9 V = torch.stack(blocks + [partial_block]) # [N+1, B, T, D]
10 K = norm(V)
11 logits = torch.einsum('d, n b t d -> n b t', proj.weight.squeeze(), K)
12 h = torch.einsum('n b t, n b t d -> b t d', logits.softmax(0), V)
13 return h
14
15 def forward(self, blocks: list[Tensor], hidden_states: Tensor) -> tuple[list[Tensor], Tensor]:
16 partial_block = hidden_states
17 # apply block attnres before attn
18 # blocks already include token embedding
19 h = block_attn_res(blocks, partial_block, self.attn_res_proj, self.attn_res_norm)
20
21 # if reaches block boundary, start new block
22 # block_size counts ATTN + MLP; each transformer layer has 2
23 if self.layer_number % (self.block_size // 2) == 0:
24 blocks.append(partial_block)
25 partial_block = None
26
27 # self-attention layer
28 attn_out = self.attn(self.attn_norm(h))
29 partial_block = partial_block + attn_out if partial_block is not None else attn_out
30
31 # apply block attnres before MLP
32 h = block_attn_res(blocks, partial_block, self.mlp_res_proj, self.mlp_res_norm)
33
34 # MLP layer
35 mlp_out = self.mlp(self.mlp_norm(h))
36 partial_block = partial_block + mlp_out
37
38 return blocks, partial_block
```  
Figure 2: PyTorch-style pseudo code for Block Attention Residuals. block\_attn\_res computes softmax attention over block representations using a learned pseudo-query wl; forward is a single-layer pass that maintains partial\_block (bin, intra-block residual) and blocks $( [ b _ { 0 } , \ldots , \bar { b } _ { n - 1 } ]$ , inter-block history).

Inter-Block Attention. In Full AttnRes, the input to layer l is computed by attending over all outputs up to $f _ { l - 1 } ( h _ { l - 1 } )$ The block-wise variant replaces these individual outputs with block representations, defining $\pmb { b } _ { 0 } = \pmb { h } _ { 1 }$ so that the token embedding is always included as a source. For the i-th layer in block n, the value matrix is:

$$
\mathbf { V } = \left\{ { \begin{array} { l l } { [ b _ { 0 } , b _ { 1 } , \dots , b _ { n - 1 } ] ^ { \top } } & { { \mathrm { i f ~ } } i = 1 { \mathrm { ~ ( f i r s t ~ l a y e r ~ o f ~ b l o c k ~ } } n { ) } } \\ { [ b _ { 0 } , b _ { 1 } , \dots , b _ { n - 1 } , b _ { n } ^ { i - 1 } ] ^ { \top } } & { { \mathrm { i f ~ } } i \geq 2 { \mathrm { ~ ( s u b s e q u e n t ~ l a y e r s ) } } } \end{array} } \right.\tag{6}
$$

Keys and attention weights follow Eq. 3 and Eq. 2. The input of the very first layer of the network is the token embeddings, i.e. $\pmb { b } _ { 0 } = \pmb { h } _ { 1 }$ . In each block, the first layer receives the previous block representations and the token embeddings, and the subsequent layers additionally attend to the partial sum $b _ { n } ^ { i - 1 }$ . The final output layer aggregates all N block representations. Fig. 2 provides PyTorch-style pseudocode for Block AttnRes.

Efficiency. Since each layer now attends over N block representations rather than L individual outputs, memory reduces from O(L) to O(N) and computation from $O ( L ^ { 2 } )$ to O(N2). The block count N interpolates between two extremes: $N = \dot { L }$ recovers Full AttnRes, while $N = 1$ reduces to standard residual connections with the embedding isolated as $b _ { 0 }$ . Empirically, we find that $N \approx { 8 }$ recovers most of the benefit across model scales, requiring only eight stored hidden states per token (see § 5).

Beyond memory and computation, the block structure also benefits inference latency: block boundaries define the dispatch granularity for the blockwise optimization described in $\ S 3$ , and the fixed block count N bounds the KV cache size. The parallel inter-block results are merged with the sequential intra-block partial sums via online softmax [31], preserving exact equivalence (§4).

## 4 Infrastructure Design

Block AttnRes introduces additional system challenges compared to standard residual connections. For large-scale model training, block representations must be propagated across pipeline stages, causing heavy communication in a naïve implementation. During inference, repeated access to accumulated block representations increases latency, while long-context prefilling amplifies the memory cost of caching block representations. We address these challenges with cross-stage caching in training, and with a two-phase computation strategy together with a memory-efficient prefilling scheme in inference.

![](images/f9d6dab6f57e9fca839b8c1b6c73cae224e097472c5dd36ce449dedf9ef1ac76.jpg)  
Figure 3: Cache-based pipeline communication example with 4 physical ranks and 2 virtual stages per rank, where hatched boxes denote end of AttnRes blocks. Numbers indicate micro-batch indices. Each rank caches previously received blocks; stage transitions only transmit incremental blocks $( + [ b _ { 1 } , b _ { 2 } ] )$ instead of the full history.

## 4.1 Training

For small-scale training, AttnRes adds a tiny computation overhead and no extra memory usage, as the activations need to be saved for backpropagation regardless. Under large-scale distributed training, pipeline parallelism poses the primary infrastructure challenge for AttnRes. Full AttnRes requires all L layer outputs to be transmitted across stages; Block AttnRes reduces this to N block representations, and the optimizations below further minimize the remaining overhead.

Pipeline communication. With standard residual connections, pipeline parallelism [18] transfers a fixed-size hidden state between adjacent stages, independent of pipeline depth. Block AttnRes requires all accumulated block representations at each stage for inter-block attention, and naïvely transmitting the full history at every transition incurs redundant communication.

Consider an interleaved pipeline schedule [33] with P physical stages and V virtual stages per physical stage. For simplicity, assume each physical stage produces on average $N _ { p }$ block representations of dimension d per token.1 With $C = P V$ total chunks (each physical stage in each virtual stage), the j-th chunk accumulates $j N _ { p }$ blocks. Naïvely transmitting all accumulated blocks at every transition incurs per-token communication cost:

$$
{ \mathrm { C o m m } } _ { \mathrm { n a i v e } } = \sum _ { j = 1 } ^ { C - 1 } j N _ { p } \cdot d = { \frac { C ( C - 1 ) } { 2 } } N _ { p } d .\tag{7}
$$

Cross-stage caching. Since each physical stage processes multiple virtual stages in succession, we can eliminate this redundancy by caching blocks locally: blocks received during earlier virtual stages remain in local memory and need not be re-transmitted. The first virtual stage $( v = 1 )$ has no cache and accumulates normally; for $v \geq 2 ,$ , each transition conveys only the ${ \sim } P N _ { p }$ incremental blocks accumulated since the receiver’s corresponding chunk in the previous virtual stage. Total communication reduces to:

$$
\mathrm { C o m m } _ { \mathrm { c a c h e d } } = \underbrace { \frac { P ( P - 1 ) } { 2 } N _ { p } d } _ { \mathrm { f i r s t ~ v i r t u a l ~ s t a g e } } + \underbrace { ( V - 1 ) P ^ { 2 } N _ { p } d } _ { \mathrm { s u b s e q u e n t ~ v i r t u a l ~ s t a g e s } } .\tag{8}
$$

Caching reduces peak per-transition cost from $O ( C )$ to $O ( P )$ , a V × improvement that enables full overlap with computation during steady-state 1F1B. The backward pass benefits from the same scheme. Fig. 3 illustrates this optimization with $\scriptstyle { \bar { P } } = 4$ and $V { = } 2 \colon$ for the second virtual stage, caching eliminates 6 redundant block transmissions.

Algorithm 1: Two-phase computation for block n   
Input: Pseudo queries $\{ w _ { l } \} _ { l \in B _ { n } }$ , block representations $\left\{ b _ { 0 } , \ldots , b _ { n - 1 } \right\}$   
/\* Phase 1: Parallel inter-block attention \*/   
1 $\mathbf { Q } \gets [ \pmb { w } _ { l } ] _ { l \in { \cal B } _ { n } }$ // [S, d]   
2 K, $\dot { \mathbf { V } } \dot {  } \dot { [ } b _ { 0 } ; \dotsc ; { b _ { n - 1 } ] }$ // [n, d]   
3 $\{ o _ { l } ^ { ( 1 ) } , m _ { l } ^ { ( 1 ) } , \ell _ { l } ^ { ( 1 ) } \} _ { l \in \mathcal { B } _ { n } } \gets \mathrm { A T T N W I T H S T A T S } ( \mathbf { Q } , \mathbf { K } , \mathbf { V } )$ // Return LSE   
4   
/\* Phase 2: Sequential intra-block attention + Online softmax merge \* /   
5 $i \gets 0$   
6 for $l \in B _ { n }$ do   
7 $\mathbf { i f } \ i = 0$ then   
8 ${ \pmb h } _ { l }  { \pmb o } _ { l } ^ { ( 1 ) } / \ell _ { l } ^ { ( 1 ) }$ // Inter-block only   
9 else   
10 $o _ { l } ^ { ( 2 ) } , m _ { l } ^ { ( 2 ) } , \ell _ { l } ^ { ( 2 ) } \gets \mathrm { A T T N W I T H S T A T S } ( w _ { l } , b _ { n } ^ { i } , b _ { n } ^ { i } )$ // Intra-block   
11 $\dot { m _ { l } } \gets \operatorname* { i n a x } ( \dot { m } _ { l } ^ { ( 1 ) } , m _ { l } ^ { ( 2 ) } )$   
$\smash { \pmb { b } . \smile \quad } e ^ { m _ { l } ^ { ( 1 ) } - \bar { m _ { l } } } \pmb { o } _ { l } ^ { ( 1 ) } + e ^ { m _ { l } ^ { ( 2 ) } - m _ { l } } \pmb { o } _ { l } ^ { ( 2 ) } $   
12 $^ { \prime \prime } \overline { { e ^ { m _ { l } ^ { ( 1 ) } - m _ { l } } \ell _ { l } ^ { ( 1 ) } + e ^ { m _ { l } ^ { ( 2 ) } - m _ { l } } \ell _ { l } ^ { ( 2 ) } } }$ // Online softmax merge   
13 $i \gets i + 1$   
14 $b _ { n } ^ { i }  b _ { n } ^ { i - 1 } + f _ { l } ( { \pmb h } _ { l } )$ // Update partial sum; $b _ { n } ^ { 0 } : = \mathbf { 0 }$   
15 return $\{ h _ { l } \} _ { l \in B _ { n } }$

Memory overhead. With cross-stage caching, each block is stored exactly once across all V virtual stages, which becomes negligible relative to standard per-layer activation cache. Crucially, the per-layer activation footprint remains identical to standard architectures, as activation checkpointing eliminates all inter-block attention intermediates, and the checkpointed input ${ \mathbf { } } p _ { l }$ matches the memory size of the hidden state $h _ { l }$ it replaces.

In terms of wall-clock time, Block AttnRes adds negligible training overhead when pipeline parallelism is not enabled;   
under pipeline parallelism, the measured end-to-end overhead is less than 4%.

## 4.2 Inference

The two-phase computation strategy described below applies to both Full and Block AttnRes: in either case, layers are grouped into blocks of size S, with Phase 1 batching the inter-block queries and Phase 2 handling sequential intra-block lookback. For Full AttnRes, this reduces per-layer I/O from $O ( L d )$ to $O ( ( S { + } N ) d )$ (detailed derivation shown in Appendix B); Block AttnRes further reduces the stored representations from L to N, since each block is compressed into a single vector. In what follows, we focus on Block AttnRes and detail the two-phase computation strategy together with a sequence-sharded prefilling scheme for long-context inputs.

Two-phase computation strategy. The layer-wise attention computation of Block AttnRes resembles autoregressive decoding, where block representations serve as a shared KV cache reused across layers. A naïve implementation computes the attention residual at every layer, each requiring a full pass over all preceding blocks, resulting in $O ( L \cdot N )$ memory accesses. Since the pseudo-query vectors are decoupled from the forward computation (§3), all $S \stackrel { \cdot } { = } L / N$ queries within a block can be batched into a single matrix multiplication, amortizing memory access from S reads to 1.

Algorithm 1 instantiates a two-phase computation strategy exploiting this property.

Phase 1 computes inter-block attention for all S layers simultaneously via a single batched query against the cached block representations, returning both outputs and softmax statistics (max and log-sum-exp). This amortizes the memory access cost, reducing reads from S times to just once per block.

Phase 2 computes intra-block attention sequentially for each layer using the evolving partial sum, then merges with Phase 1 outputs through online softmax [31]. Because the online-softmax merge is elementwise, this phase naturally admits kernel fusion with surrounding operations, further reducing I/O overhead.

With the two-phase design, Phase 2 preserves an I/O footprint similar to that of standard residual connections, whereas the main additional cost arises from Phase 1 inter-block attention. Because these inter-block reads are amortized across all layers in a block through batching, the total per-layer memory access cost remains only $( \frac { N } { S } + 3 ) d$ reads and 2d writes (Table 1). This is substantially lower than the residual-stream I/O of prior residual generalizations such as (m)HC under typical settings. In practice, Phase 1 can also partially overlap with the computation of the first layer in the block, further reducing its wall-clock impact. As a result, the end-to-end inference latency overhead is less than 2% on typical inference workloads.

Table 1: Memory access cost per token per layer incurred by the residual mechanism under each scheme. The internal I/O of the layer function fl is excluded. For AttnRes, both Full and Block variants use the two-phase inference schedule described in Appendix B; amortized costs are averaged over N layers within a block. Typical values: L=128, N=8, S=L/N=16, m=4.
<table><tr><td colspan="2">Operation</td><td rowspan="2"></td><td rowspan="2">Read</td><td rowspan="2">Write</td><td colspan="2">Total I/O</td></tr><tr><td></td><td></td><td>Symbolic</td><td>Typical</td></tr><tr><td>Standard Residuals</td><td rowspan="2"></td><td>Residual Merge</td><td>2d</td><td>d</td><td rowspan="2">3d</td><td rowspan="2">3d</td></tr><tr><td colspan="2" rowspan="6">mHC (m streams)</td><td>Compute  $\alpha _ { l } , \beta _ { l } , \mathbf { A } _ { l }$  Apply α</td><td>md md+m</td><td> $m ^ { 2 } + 2 m$  d</td></tr><tr><td>Apply βt</td><td>d+m</td><td>md</td><td> $( 8 m + 2 ) d + 2 m ^ { 2 } + 4 m$ </td><td rowspan="2">34d</td></tr><tr><td>Apply Al</td><td>md+m²</td><td>md</td><td></td></tr><tr><td rowspan="2">Residual Merge</td><td>2md</td><td>md</td><td rowspan="2"></td><td rowspan="2"></td></tr><tr><td></td><td></td></tr><tr><td rowspan="3">Full AttnRes Block</td><td>Phase 1 (amortized) Phase 2</td><td>(N-1)d (S-1)d</td><td>d d</td><td rowspan="2">(S+N)d</td><td rowspan="2">24d</td></tr><tr><td rowspan="2">Phase 1 (amortized) Phase 2</td><td rowspan="2"> $\textstyle { \frac { N } { S } } d$ </td><td></td></tr><tr><td>d d</td><td> $\left( \frac { N } { S } + 5 \right) d$  5.5d</td></tr></table>

Memory-efficient prefilling. Storing block representations during prefilling requires N · T · d elements, which incurs 15 GB of memory for a 128K-token sequence with 8 blocks. We mitigate this by sharding these representations along the sequence dimension across P tensor-parallel devices, allowing Phase 1 to execute independently on local sequence shards. The Phase 2 online-softmax merge then integrates into the standard TP all-reduce communication path: the output is reduce-scattered, merged locally, and reconstructed via all-gather, naturally admitting kernel fusion with operations like RMSNorm. This reduces the per-device memory footprint to N · (T /P ) · d—lowering the 128K-context example from 15 GB to roughly 1.9 GB per device. Combined with chunked prefill (e.g., 16K chunk size), the overhead further reduces to under 0.3 GB per device.

## 5 Experiments

Architecture Details. Our architecture is identical to Kimi Linear [69], a Mixture-of-Experts (MoE) Transformer following the Moonlight [28] / DeepSeek-V3 [9] design, which interleaves Kimi Delta Attention (KDA) and Multi-Head Latent Attention (MLA) layers in a 3:1 ratio, each followed by an MoE feed-forward layer. The only modification is the addition of AttnRes to the residual connections; all other components (model depth, hidden dimensions, expert routing, and MLP structure) remain unchanged. AttnRes introduces only one RMSNorm and one pseudo-query vector ${ \pmb w } _ { l } \in \mathbb { R } ^ { d }$ per layer, amounting to a negligible fraction of the total parameter count. Crucially, all pseudo-query vectors must be initialized to zero. This ensures that the initial attention weights $\alpha _ { i \to l }$ are uniform across source layers, which reduces AttnRes to an equal-weight average at the start of training and prevents training volatility, as we validated empirically.

## 5.1 Scaling Laws

We sweep five model sizes (Table 2) and train three variants per size: a PreNorm baseline, Full AttnRes, and Block AttnRes with ≈ 8 blocks. They are trained with an 8192-token context window and a cosine learning rate schedule. Within each scaling law size group, all variants share identical hyperparameters selected under the baseline to ensure fair comparison; this setup intentionally favors the baseline and thus makes the comparison conservative. Following standard practice, we fit power-law curves of the form $\mathcal { L } = A \times C ^ { - \alpha } \left[ 2 2 , 1 5 \right]$ , where L is validation loss and C is compute measured in PFLOP/s-days.

Scaling Behavior. Fig. 4 presents the fitted scaling curves. The Baseline follows $\mathcal { L } = 1 . 8 9 1 \times C ^ { - 0 . 0 5 7 }$ , while Block AttnRes fits $\mathcal { L } = 1 . 8 7 \overset { \smile } { 0 } \times \overset { \cdot } { C } - 0 . 0 5 8$ , and Full AttnRes fits $\mathcal { L } = 1 . 8 6 5 \times C ^ { - 0 . 0 5 7 }$ . All three variants exhibit a similar slope, but AttnRes consistently achieves lower loss across the entire compute range. Based on the fitted curves, at 5.6

Table 2: Baseline vs Block AttnRes (N = 8) vs Full AttnRes vs mHC(-lite) [64]: Model configurations, Hyperparameters, and Validation Loss.
<table><tr><td rowspan="2">#Act. Params†</td><td rowspan="2">Tokens</td><td rowspan="2"> $L _ { b }$ </td><td rowspan="2">H</td><td rowspan="2"> $d _ { \mathrm { m o d e l } }$ </td><td rowspan="2">dff</td><td rowspan="2">lr</td><td rowspan="2">batch size+</td><td colspan="4">Val. Loss</td></tr><tr><td>Baseline</td><td>Block AttnRes</td><td>Full AttnRes</td><td>mHC(-lite)</td></tr><tr><td>194M</td><td>38.7B</td><td>12</td><td>12</td><td>896</td><td>400</td><td> $2 . 9 9 \times 1 0 ^ { - 3 }$ </td><td>192</td><td>1.931</td><td>1.909</td><td>1.899</td><td>1.906</td></tr><tr><td>241M</td><td>45.4B</td><td>13</td><td>13</td><td>960</td><td>432</td><td> $2 . 8 0 \times 1 0 ^ { - 3 }$ </td><td>256</td><td>1.895</td><td>1.875</td><td>1.874</td><td>1.869</td></tr><tr><td>296M</td><td>62.1B</td><td>14</td><td>14</td><td>1024</td><td>464</td><td> $2 . 5 0 \times 1 0 ^ { - 3 }$ </td><td>320</td><td>1.829</td><td>1.809</td><td>1.804</td><td>1.807</td></tr><tr><td>436M</td><td>87.9B</td><td>16</td><td>16</td><td>1168</td><td>528</td><td> $2 . 2 0 \times 1 0 ^ { - 3 }$ </td><td>384</td><td>1.766</td><td>1.746</td><td>1.737</td><td>1.747</td></tr><tr><td>528M</td><td>119.0B</td><td>17</td><td>17</td><td>1264</td><td>560</td><td> $2 . 0 2 \times 1 0 ^ { - 3 }$ </td><td>432</td><td>1.719</td><td>1.693</td><td>1.692</td><td>1.694</td></tr></table>

† Denotes the number of activated parameters in our MoE models, excluding embeddings.  
‡ All models were trained with a context length of 8192.  
⋆ $L _ { b } = L / 2$ denotes the number of Transformer blocks.

![](images/1bd197ffb128b90317307da0c96d1f346ead6fb82271b116af9917588d3b25d0.jpg)  
Figure 4: Scaling law curves for Attention Residuals. Both Full and Block AttnRes consistently outperform the baseline across all scales. Block AttnRes closely tracks Full AttnRes, recovering most of the gain at the largest scale.

PFLOP/s-days, Block AttnRes reaches 1.692 versus the Baseline’s 1.714, equivalent to a 1.25× compute advantage. The gap between Full and Block AttnRes narrows with scale, shrinking to just 0.001 at the largest size. We also list mHC(-lite) [64] in Table 2 for reference. Full AttnRes outperforms mHC, while Block AttnRes matches it at lower memory I/O per layer: 5.5d versus 34d for mHC with m=4 streams (Table 1).

## 5.2 Main Results

Training recipe. The largest models we study are based on the full Kimi Linear 48B configuration: 27 Transformer blocks (54 layers) with 8 out of 256 routed experts plus 1 shared expert, yielding 48B total and 3B activated parameters. This model applies Block AttnRes with 6 layers per block, producing 9 blocks plus the token embedding for a total of 10 depth-wise sources.

We follow the same data and training recipe as the Kimi Linear 1.4T-token runs [69]: all models are pre-trained with a 4096-token context window, the Muon optimizer [28], and a WSD (Warmup–Stable–Decay) learning rate schedule [16], with a global batch size of 8M tokens. Training of the final model proceeds in two stages: (i) a WSD pre-training phase on 1T tokens, followed by (ii) a mid-training phase on ≈ 400B high-quality tokens, following the annealing recipe of Moonlight [28].

After mid-training, we continue training with progressively longer sequence length of 32K tokens. Since our architecture uses hybrid KDA/MLA attention [69], where MLA operates without positional encodings (NoPE) [61], context extension requires no modifications such as YaRN [37] or attention temperature rescaling.

![](images/e11cc5a7fdf39fb96a5e092e291294a9d3cece965af05a7ff8bbe52efd4826c4.jpg)

![](images/4dba442976cb831b44d09ba89e2c83611d0829c186f920264254f07b86d584c3.jpg)  
Transformer Block Index

![](images/d2b5544034d48b99ace9c84d0016032bee679ab2984928dbe770cf797bdc7791.jpg)  
Figure 5: Training dynamics of Baseline and Block AttnRes. (a) Validation loss during training. (b) Each transformer block’s output magnitude at the end of training. (c) Each transformer block’s gradient magnitude.

Training dynamics. We compare the training dynamics of our final Baseline and Block AttnRes models over 1T tokens in Fig. 5.

• Validation loss: AttnRes achieves consistently lower validation loss throughout training, with the gap widening during the decay phase and resulting in a notably lower final loss.

Output magnitude: The Baseline suffers from the PreNorm dilution problem [60, 27]: as hidden-state magnitudes grow monotonically with depth, deeper layers are compelled to learn increasingly large outputs from fixed-scale normalized inputs to remain influential. Block AttnRes confines this growth within each block, as selective aggregation at block boundaries resets the accumulation, yielding a bounded periodic pattern.

Gradient magnitude: With all residual weights fixed to 1, the Baseline provides no means of regulating gradient flow across depth, leading to disproportionately large gradients in the earliest layers. The learnable softmax weights in Block AttnRes (Fig. 8) introduce competition among sources for probability mass, resulting in a substantially more uniform gradient distribution.

Table 3: Performance comparison of AttnRes with the baseline, both after the same pre-training recipe. Best per-row results are bolded.
<table><tr><td colspan="2"></td><td>Baseline</td><td>AttnRes</td></tr><tr><td rowspan="7">General</td><td>MMLU</td><td>73.5</td><td>74.6</td></tr><tr><td>MMLU-Pr0</td><td>52.2</td><td>52.2</td></tr><tr><td>GPQA-Diamond</td><td>36.9</td><td>44.4</td></tr><tr><td>BBH</td><td>76.3</td><td>78.0</td></tr><tr><td>ARC-Challenge</td><td>64.6</td><td>65.7</td></tr><tr><td>HellaSwag</td><td>83.2</td><td>83.4</td></tr><tr><td>TriviaQA</td><td>69.9</td><td>71.8</td></tr><tr><td rowspan="6">Math&amp;Code</td><td>GSM8K</td><td>81.7</td><td>82.4</td></tr><tr><td>MGSM</td><td>64.9</td><td>66.1</td></tr><tr><td>Math</td><td>53.5</td><td>57.1</td></tr><tr><td>CMath</td><td>84.7</td><td>85.1</td></tr><tr><td>HumanEval</td><td>59.1</td><td>62.2</td></tr><tr><td>MBPP</td><td>72.0</td><td>73.9</td></tr><tr><td rowspan="2">Chinese</td><td>CMMLU</td><td>82.0</td><td>82.9</td></tr><tr><td>C-Eval</td><td>79.6</td><td>82.5</td></tr></table>

Downstream performance. Following the evaluation protocol of Kimi Linear [69], we assess both models across three areas (Table 3):

Table 4: Ablation on key components of AttnRes (16-layer model).
<table><tr><td>Variant</td><td>Loss</td></tr><tr><td>Baseline (PreNorm)</td><td>1.766</td></tr><tr><td>DenseFormer [36]</td><td>1.767</td></tr><tr><td>mHC [59]</td><td>1.747</td></tr><tr><td>AttnRes Full</td><td>1.737</td></tr><tr><td>w/ input-dependent query</td><td>1.731</td></tr><tr><td>w/ input-independent mixing</td><td>1.749</td></tr><tr><td>w/ sigmoid</td><td>1.741</td></tr><tr><td>w/o RMSNorm</td><td>1.743</td></tr><tr><td>SWA (W =1+ 8)</td><td>1.764</td></tr><tr><td>Block (S = 4)</td><td>1.746</td></tr><tr><td>w/multihead(H=16)</td><td>1.752</td></tr><tr><td>w/o RMSNorm</td><td>1.750</td></tr></table>

![](images/a589f3f59b8c4be28dc4947819231b34cf117a9f846d7bdf0f563acdb80a2426.jpg)  
Figure 6: Effect of block size on validation loss (16-layer model).

• Language understanding and reasoning: MMLU [13], MMLU-Pro Hard [55], GPQA-Diamond [41], BBH [48], ARC-Challenge [6], HellaSwag [65], and TriviaQA [21].

• Reasoning (Code and Math): GSM8K [7], MGSM [44], Math [25], CMath [14], HumanEval [5], and MBPP [1].

• Chinese language understanding: CMMLU [26] and C-Eval [19].

As shown in Table 3, Block AttnRes matches or outperforms the baseline on all benchmarks. The improvements are particularly pronounced on multi-step reasoning tasks such as GPQA-Diamond (+7.5) and Minerva Math (+3.6), as well as code generation such as HumanEval (+3.1), while knowledge-oriented benchmarks such as MMLU (+1.1) and TriviaQA (+1.9) also show solid gains. This pattern is consistent with the hypothesis that improved depth-wise information flow benefits compositional tasks, where later layers can selectively retrieve and build upon earlier representations.

## 5.3 Ablation Study

We conduct ablation studies on the 16-head model from Table 2 to validate key design choices in AttnRes (Table 4). All models share identical hyperparameters and compute budget.

Comparison with prior methods. We compare AttnRes against the PreNorm baseline (loss 1.766) and two representative methods that generalize residual connections. DenseFormer [36] grants each layer access to all previous outputs but combines them with fixed, input-independent scalar coefficients; it shows no gain over the baseline (1.767), highlighting the importance of input-dependent weighting. mHC [59] introduces input dependence through m parallel streams with learned mixing matrices, improving to 1.747. AttnRes takes this further with explicit content-dependent selection via softmax attention: Full AttnRes achieves 1.737 and Block AttnRes 1.746, outperforming both methods with only a single query vector per layer.

Cross-layer access. We compare three granularities of cross-layer access. Full AttnRes follows directly from the time–depth duality (§ 3), applying attention over all previous layers, and achieves the lowest loss (1.737). A simple way to reduce its memory cost is sliding-window aggregation (SWA), which retains only the most recent W =8 layer outputs plus the token embedding; it improves over baseline (1.764) but falls well short of both Full and Block AttnRes, suggesting that selectively accessing distant layers matters more than attending to many nearby ones.

Block AttnRes offers a better trade-off: with block size S=4 it reaches 1.746 while keeping memory overhead constant per layer. Fig. 6 sweeps S across the full spectrum from S=1 (i.e. Full AttnRes) to increasingly coarse groupings. Loss degrades gracefully as S grows, with S=2, 4, 8 all landing near 1.746 while larger blocks (S=16, 32) move toward baseline. In practice, we fix the number of blocks to ≈ 8 for infrastructure efficiency (§ 4). As future hardware alleviates memory capacity constraints, adopting finer-grained block sizes or Full AttnRes represents a natural pathway to further improve performance.

![](images/b2205610918b7fd61262c3e12edf5b1d1dcc297e7bf55a4c8cc5a8f05bf0bed8.jpg)  
(a) Baseline

![](images/ca37c58504557a2ae8890c11674439e964e588284c137ac7cbd6d7ac5a4db5ae.jpg)  
(b) Attention Residuals  
Figure 7: Architecture sweep under fixed compute (≈ $6 . 5 \times 1 0 ^ { 1 9 }$ FLOPs, $\approx 2 . 3 \times 1 0 ^ { 8 }$ active parameters). Each cell reports validation loss for a $( d _ { \mathrm { m o d e l } } / { \hat { L } } _ { b } , \ H / L _ { b } )$ configuration, where $L _ { b } = L / 2$ is the number of Transformer blocks; the star marks the optimum.

Component design. We further ablate individual components of the attention mechanism:

• Input-dependent query. A natural extension is to make the query input-dependent by projecting it from the current hidden state. This further lowers loss to 1.731, but introduces a d × d projection per layer and requires sequential memory access during decoding, so we default to the learned query.

• Input-independent mixing. We removed the query and key and replaced them with learnable, input-independent scalars to weigh previous layers, which hurts performance (1.749 vs. 1.737).

• softmax vs. sigmoid. Replacing softmax with sigmoid degrades performance (1.741). We attribute this to softmax’s competitive normalization, which forces sharper selection among sources.

• Multihead attention. We test per-head depth aggregation (H=16) on Block AttnRes, allowing different channel groups to attend to different source layers. This hurts performance (1.752 vs. 1.746), indicating that the optimal depth-wise mixture is largely uniform across channels: when a layer’s output is relevant, it is relevant as a whole.

RMSNorm on keys. Removing RMSNorm degrades both Full AttnRes (1.743) and Block AttnRes (1.750). For Full AttnRes, it prevents individual layers with naturally larger outputs from dominating the softmax. This becomes even more critical for Block AttnRes, as block-level representations accumulate over more layers and can develop large magnitude differences; RMSNorm prevents these from biasing the attention weights.

## 5.4 Analysis

## 5.4.1 Optimal Architecture

To understand how AttnRes reshapes optimal architectural scaling, we perform a controlled capacity reallocation study under a fixed compute and parameter budget. Our central question is whether AttnRes alters the preferred depth–width–attention trade-off, and in particular, given its potential strength on the depth dimension, whether it favors deeper models compared to conventional Transformer design heuristics. To isolate structural factors directly coupled to depth, we fix the per-expert MLP expansion ratio based on internal empirical observations $( d _ { \mathrm { f f } } / d _ { \mathrm { m o d e l } } \approx 0 . 4 5 )$ . We further fix total training compute $( \mathrm { F L O P s \approx 6 . 5 \times 1 0 ^ { 1 9 } } )$ and active parameters $( \approx 2 . 3 \times 1 0 ^ { 8 } )$ , ensuring that any performance variation arises purely from architectural reallocation rather than overall capacity differences. Under this constrained budget, we enumerate 25 configurations on a $5 \times 5$ grid over $d _ { \mathrm { m o d e l } } / L _ { b } \in \{ 1 5 , 3 0 , 4 5 , 6 0 , 7 5 \}$ and $H / L _ { b } \in \{ 0 . 3 , 0 . 4 , 0 . 5 , 0 . 6 , 0 . 7 \}$ , where $L _ { b } = L / 2$ is the number of Transformer blocks and H the number of attention heads. The results are shown in Fig. 7.

Both heatmaps exhibit a shared pattern: loss decreases with growing $d _ { \mathrm { m o d e l } } / L _ { b }$ and shrinking $H / L _ { b } ,$ , and both methods reach their optima at $H / L _ { b } \approx 0 . 3$ Despite this shared trend, AttnRes achieves a lower loss than the baseline in each of the 25 configurations, by 0.019–0.063. The most apparent difference lies in the location of the optimum: the baseline achieves its lowest loss at $d _ { \mathrm { m o d e l } } / L _ { b } \approx 6 0 ( 1 . 8 4 7 )$ , whereas AttnRes shifts it to $d _ { \mathrm { m o d e l } } / L _ { b } \approx 4 5 \ : ( \mathrm { \bar { 1 } . 8 0 2 } )$ . Under a fixed parameter budget, a lower $d _ { \mathrm { m o d e l } } / L _ { b }$ corresponds to a deeper, narrower network, suggesting that AttnRes can exploit additional depth more effectively. We note that this preference for depth does not directly translate to a deployment recommendation, as deeper models generally incur higher inference latency due to their sequential computation [39]. Rather, this sweep serves as a diagnostic that reveals where AttnRes benefits most, and this depth preference can be factored into the architecture selection alongside inference cost.

![](images/ea74e03c09dc98f106e4d5c16225a50038235cdff04a433704f3a7333d6f956f.jpg)  
Figure 8: Depth-wise attention weight distributions for a 16-head model with full (top) and block (bottom) Attention Residuals, averaged over tokens. The model has 16 attention and 16 MLP layers. Each row shows how the lth attention (left) or MLP (right) layer distributes weight over previous sources. Diagonal dominance indicates locality remains the primary information pathway, while persistent weights on source 0 (embedding) and occasional off-diagonal concentrations reveal learned skip connections. Block attention $( N = 8 )$ recovers the essential structure with sharper, more decisive weight distributions.

## 5.4.2 Analyzing Learned AttnRes Patterns

We visualize the learned weights $\alpha _ { i \to l }$ in Fig. 8 for the 16-head model (from Table 2) with both full and block $( N { = } 8 )$ AttnRes. Each heatmap shows how the lth attention or MLP layer (rows) allocates its attention over previous sources (columns), with pre-attention and pre-MLP layers shown separately. We highlight three key observations:

• Preserved locality. Each layer attends most strongly to its immediate predecessor, yet selective off-diagonal concentrations emerge (e.g., layer 4 attending to early sources, layers 15–16 reaching back under the block setting), indicating learned skip connections beyond the standard residual path.

• Layer specialization. The embedding $h _ { 1 }$ retains non-trivial weight throughout, especially in pre-attention layers. Pre-MLP inputs show sharper diagonal reliance on recent representations, while pre-attention inputs maintain broader receptive fields, consistent with attention routing information across layers and MLPs operating locally.

• Block AttnRes preserves structure. Diagonal dominance, embedding persistence, and layer specialization all transfer from the full to the block variant, suggesting that block-wise compression acts as implicit regularization while preserving the essential information pathways.

Table 5: Comparison of residual update mechanisms. Weight: whether the mixing coefficients are architecture-fixed, learned-static (fixed after training), or input-dependent (dynamic). Source: which earlier representations layer l can access. Normalization is omitted from most formulas for clarity.
<table><tr><td>Method</td><td>Update rule</td><td>Weight</td><td>Source</td></tr><tr><td colspan="4">Single-state recurrence: layer l receives only hl-1</td></tr><tr><td>Residual [12]</td><td> $\pmb { h } _ { l } = \pmb { h } _ { l - 1 } + f _ { l - 1 } ( \pmb { h } _ { l - 1 } )$ </td><td>Fixed</td><td> $\boldsymbol { h } _ { l - 1 }$ </td></tr><tr><td>ReZero [2]</td><td> $\pmb { h } _ { l } = \pmb { h } _ { l - 1 } + \alpha _ { l } \cdot \pmb { f } _ { l - 1 } ( \pmb { h } _ { l - 1 } )$ </td><td>Static</td><td> $\boldsymbol { h } _ { l - 1 }$ </td></tr><tr><td>LayerScale [50]</td><td> $\pmb { h } _ { l } = \pmb { h } _ { l - 1 } + \mathrm { d i a g } ( \pmb { \lambda } _ { l } ) \cdot \pmb { f } _ { l - 1 } ( \pmb { h } _ { l - 1 } )$ </td><td>Static</td><td> $\boldsymbol { h } _ { l - 1 }$ </td></tr><tr><td>Highway [45]</td><td> $\pmb { h } _ { l } = ( 1 - \pmb { g } _ { l } ) \odot \pmb { h } _ { l - 1 } + \pmb { g } _ { l } \odot f _ { l - 1 } ( \pmb { h } _ { l - 1 } )$ </td><td>Dynamic</td><td> $\mathbf { \delta } _ { h _ { l - 1 } }$ </td></tr><tr><td>DeepNorm [54]</td><td> $\pmb { h } _ { l } = \mathrm { N o r m } ( \alpha \pmb { h } _ { l - 1 } + f _ { l - 1 } ( \pmb { h } _ { l - 1 } ) )$ </td><td>Fixed</td><td> $\mathbf { \delta } _ { h _ { l - 1 } }$ </td></tr><tr><td>KEEL [4]</td><td> $\pmb { h } _ { l } = \mathrm { N o r m } ( \alpha \pmb { h } _ { l - 1 } + f _ { l - 1 } ( \mathrm { N o r m } ( \pmb { h } _ { l - 1 } ) ) )$ </td><td>Fixed</td><td> $\boldsymbol { h } _ { l - 1 }$ </td></tr><tr><td colspan="4">Multi-state recurrence: layer l receives m streams</td></tr><tr><td>SiameseNorm [27]</td><td> $\pmb { h } _ { l } ^ { 1 } = \mathrm { N o r m } ( \pmb { h } _ { l - 1 } ^ { 1 } + \pmb { y } _ { l - 1 } ) ; \pmb { h } _ { l } ^ { 2 } = \pmb { h } _ { l - 1 } ^ { 2 } + \pmb { y } _ { l - 1 } $ </td><td>Fixed</td><td>2 streams</td></tr><tr><td>HC/mHC [72, 59]</td><td> $\mathbf { H } _ { l } = \mathbf { H } _ { l - 1 } \mathbf { A } _ { l } + f _ { l - 1 } \big ( \mathbf { H } _ { l - 1 } \pmb { \alpha } _ { l - 1 } \big ) \beta _ { l - 1 } ^ { \top }$ </td><td>Dynamic</td><td>m streams</td></tr><tr><td>DDL [67]</td><td> $\mathbf { H } _ { l } = ( \mathbf { I } { - } \beta _ { l } \mathbf { k } _ { l } \mathbf { k } _ { l } ^ { \top } ) \mathbf { H } _ { l - 1 } + \beta _ { l } \mathbf { k } _ { l } \mathbf { v } _ { l } ^ { \top }$ </td><td>Dynamic</td><td>du streams</td></tr><tr><td colspan="4">Cross-layer access: layer l can access individual earlier-layer outputs</td></tr><tr><td>DenseNet [17]</td><td> $\begin{array} { r } { \pmb { h } _ { l } = \mathrm { C o n v P o o l } ( [ \pmb { h } _ { 1 } ; ~ f _ { 1 } ( \pmb { h } _ { 1 } ) ; ~ . ~ . ~ . ; ~ f _ { l - 1 } ( \pmb { h } _ { l - 1 } ) ] ) } \end{array}$ </td><td>Static</td><td> $[ h _ { 1 } , \ldots , h _ { l - 1 } ]$ </td></tr><tr><td>DenseFormer [36]</td><td> $\begin{array} { r } { \pmb { h } _ { l } = \alpha _ { 0  l } \pmb { h } _ { 1 } + \sum _ { i = 1 } ^ { l - 1 } \alpha _ { i  l } f _ { i } \big ( \pmb { h } _ { i } \big ) } \end{array}$ </td><td>Static</td><td> $[ h _ { 1 } , \ldots , h _ { l - 1 } ]$ </td></tr><tr><td> $\mathbf { M R L A } \left[ 1 0 \right] ^ { 1 }$ </td><td> $\begin{array} { r } { h _ { l } = \sum _ { i = 1 } ^ { l - 1 } \sigma \big ( \mathrm { C o n v P o o l } ( f _ { l - 1 } ( h _ { l - 1 } ) ) \big ) ^ { \top } \sigma \big ( \mathrm { C o n v P o o l } ( f _ { i } ( h _ { i } ) ) \big ) \mathrm { C o n v } \big ( f _ { i } ( h _ { i } ) \big ) } \end{array}$ </td><td>Dynamic</td><td> $[ h _ { 1 } , \ldots , h _ { l - 1 } ]$ </td></tr><tr><td> AttnRes (ours)</td><td></td><td> $\begin{array} { r } { h _ { l } \propto \sum _ { i = 0 } ^ { l - 1 } \phi ( \pmb { w } _ { l } , \pmb { k } _ { i } ) \pmb { v } _ { i } } \end{array}$ </td><td> Dynamic</td><td> $[ h _ { 1 } , \ldots , h _ { l - 1 } ]$ </td></tr><tr><td></td><td> $\mathrm { F u l l ^ { 2 } }$   $\mathrm { B l o c k ^ { 3 } }$ </td><td> $\begin{array} { r } { \pmb { h } _ { l } \propto \sum _ { i = 0 } ^ { n - 1 } \phi ( \pmb { w } _ { l } , \pmb { k } _ { i } ) \pmb { v } _ { i } + \phi ( \pmb { w } _ { l } , \pmb { k } _ { n } ^ { j } ) \pmb { v } _ { n } ^ { j } } \end{array}$ </td><td> Dynamic</td><td> $[ b _ { 0 } , \ldots , b _ { n - 1 } , b _ { n } ^ { j } ]$ </td></tr></table>

1 ConvPool: pooling operation followed by convolution (channel projection).  
2 ϕ(q, k) = exp  q⊤ RMSNorm(k); ki = vi; v0 = h1, vi≥1 = fi(hi). softmax jointly normalized over all sources.  
3 Same ϕ and normalization as Full; $\pmb { v } _ { i } = \pmb { b } _ { i } , \ \pmb { v } _ { n } ^ { j } = \pmb { b } _ { n } ^ { j }$

## 6 Discussions

## 6.1 Sequence-Depth Duality

Residual connections propagate information over depth via a fixed recurrence $h _ { l } = h _ { l - 1 } + f _ { l - 1 } ( h _ { l - 1 } )$ , much as RNNs propagate information over time. Test-Time Training (TTT) [46] formalizes the sequence side of this analogy (cf. Fast Weight Programmers [43, 32]), casting each recurrent step as gradient descent on a self-supervised loss:

$$
\mathbf { W } _ { t } = \mathbf { W } _ { t - 1 } - \eta \nabla \ell \big ( \mathbf { W } _ { t - 1 } ; \mathbf { \em x } _ { t } \big ) ,\tag{9}
$$

where a slow network parameterizes ℓ and the state W is updated once per token. When f is linear, this reduces to vanilla linear attention $\begin{array} { r } { \dot { \mathbf { S } } _ { t } = \mathbf { S } _ { t - 1 } + k _ { t } \pmb { v } _ { t } ^ { \top } } \end{array}$ The standard residual exhibits the same additive form along depth, with $h _ { l }$ serving as the state and each layer fl acting as one “gradient step.”

As noted by [4], this duality extends to richer variants (Table 5). Data-dependent gates on the sequence side [47, 63] correspond to Highway networks [45] on the depth side; the delta rule [42, 62, 69] corresponds to DDL [67]; and MRLA [10] mirrors GLA’s [63] gated linear attention. These methods all refine the recurrent update while remaining within the recurrence paradigm. AttnRes goes a step further and replaces depth-wise recurrence with direct cross-layer attention, just as Transformers replaced temporal recurrence with self-attention. Since the number of layers in current architectures remains well within the practical regime of softmax attention, we adopt vanilla depth-wise attention. Incorporating more expressive yet memory-efficient (e.g. linear-complexity) alternatives is a natural direction for future work.

## 6.2 Residual Connections as Structured Matrices

The residual variants discussed above can all be viewed as weighted aggregations over previous layer outputs. We formalize this with a depth mixing matrix $\mathbf { M } \in \mathbb { R } ^ { L \times L }$ , where $\mathbf { M } _ { i  l }$ is the weight that layer l assigns to the output of layer i. The variants differ in how these weights arise (fixed, learned, or input-dependent) and whether M is constrained to low rank or allowed to be dense. The semiseparable rank of M [8] offers a unified lens for comparing them.

Concretely, the input to layer l is $\begin{array} { r } { \pmb { h } _ { l } = \sum _ { i = 0 } ^ { l - 1 } \mathbf { M } _ { i  l } \pmb { v } _ { i } } \end{array}$ , where ${ \pmb v } _ { 0 } = { \pmb h } _ { 1 }$ (embedding) and ${ \pmb v } _ { i } = f _ { i } ( { \pmb h } _ { i } )$ for $i \geq 1$ . Fig. 9 visualizes M for representative methods; we derive each below.

![](images/4e1127c808cc7fc61080bbe755d03d4e0b4c12bfe29c1e4da905d4391734a15c.jpg)  
Figure 9: Depth mixing matrices M for four residual variants (L=4; Block AttnRes uses block size S=2). Highway is shown with scalar gates for clarity. AttnRes panels show unnormalized ϕ scores; background colors group entries that share the same source (Full AttnRes) or the same source block (Block AttnRes).

• Standard residual [12], $h _ { l } = h _ { l - 1 } + f _ { l - 1 } ( h _ { l - 1 } )$ . Expanding gives $\begin{array} { r } { \pmb { h } _ { l } = \sum _ { i = 0 } ^ { l - 1 } \pmb { v } _ { i } } \end{array}$ , so $\mathbf { M } _ { i \to l } = 1$ for all $i < l$ and M is an all-ones lower-triangular matrix:

$$
{ \left[ \begin{array} { l } { h _ { 1 } } \\ { h _ { 2 } } \\ { \vdots } \\ { h _ { L } } \end{array} \right] } = { \left[ \begin{array} { l l l l } { 1 } & & & \\ { 1 } & { 1 } & & \\ { \vdots } & { \vdots } & { \ddots } & \\ { 1 } & { 1 } & { \cdots } & { 1 } \end{array} \right] } { \left[ \begin{array} { l } { v _ { 0 } } \\ { v _ { 1 } } \\ { \vdots } \\ { v _ { L - 1 } } \end{array} \right] }
$$

• Highway [45], ${ \pmb h } _ { l } = ( 1 { - } g _ { l } ) { \pmb h } _ { l - 1 } + g _ { l } f _ { l - 1 } ( { \pmb h } _ { l - 1 } )$ (written here with scalar gates for clarity; the element-wise extension is straightforward). Defining the carry product $\begin{array} { r } { \gamma _ { i  l } ^ { \times } : = \prod _ { j = i + 1 } ^ { l } ( 1 - g _ { j } ) } \end{array}$ , the weights are $\mathbf { M } _ { 0  l } = \gamma _ { 1  l } ^ { \times }$ for the embedding and $\mathbf { M } _ { i  l } = g _ { i + 1 } \gamma _ { i + 1  l } ^ { \times }$ for $i \geq 1$ . Since the cumulative products factor through scalar gates, M is 1-semiseparable [8], the same rank as the standard residual but with input-dependent weights. The weights sum to one by construction, making Highway a softmax-free depth-wise instance of stick-breaking attention [49].

• (m)HC [72, 59] maintain m parallel streams $\mathbf { H } _ { l } \in \mathbb { R } ^ { d \times m }$ , updated via

$$
\mathbf { H } _ { l } = \mathbf { H } _ { l - 1 } \mathbf { A } _ { l } + f _ { l - 1 } \big ( \mathbf { H } _ { l - 1 } \pmb { \alpha } _ { l - 1 } \big ) \beta _ { l - 1 } ^ { \top } ,
$$

where $\mathbf { A } _ { l } \in \mathbb { R } ^ { m \times m }$ is a learned transition matrix, $\pmb { \alpha } _ { l - 1 } \in \mathbb { R } ^ { m }$ mixes streams into a single input for $f _ { l - 1 }$ , and $\beta _ { l - 1 } \in \mathbb { R } ^ { m }$ distributes the output back across streams. Unrolling the recurrence gives the effective weight

$$
\mathbf { M } _ { i  l } = \beta _ { i } ^ { \top } \mathbf { A } _ { i + 1  l } ^ { \times } \mathbf { \alpha } \mathbf { \alpha } \mathbf { \alpha } _ { l } ,\tag{10}
$$

where $\begin{array} { r } { \mathbf { A } _ { i  j } ^ { \times } : = \prod _ { k = i + 1 } ^ { j } \mathbf { A } _ { k } } \end{array}$ . The $m \times m$ transitions render M m-semiseparable [8]. mHC [59, 64] further constrains each Al to be doubly stochastic, stabilizing the cumulative products across depth.

• Full AttnRes computes $\mathbf { M } _ { i  l } = \alpha _ { i  l }$ via $\phi ( \mathbf { w } _ { l } , \pmb { k } _ { i } ) = \exp ( \pmb { w } _ { l } ^ { \top }$ RMSNorm(ki) with normalization, where $k _ { i } = v _ { i }$ are input-dependent layer outputs, yielding a dense, rank-L M.

• Block AttnRes partitions layers into N blocks $\boldsymbol { B } _ { 1 } , \dots , \boldsymbol { B } _ { N }$ . For sources i in a completed earlier block $B _ { n } ,$ all share the block-level key/value $\textstyle { b _ { n } } ,$ so $\mathbf { M } _ { i  l } = \alpha _ { n  l }$ for every $i \in \boldsymbol { B } _ { n }$ Within the current block, each layer additionally attends over the evolving partial sum $b _ { n } ^ { i - 1 }$ , introducing one extra distinct source per intra-block position. The effective rank of M therefore lies between N and $N + S$ (where S is the block size), interpolating between standard residual (N =1) and Full AttnRes (N =L).

Practicality. The structured-matrix perspective serves two purposes. First, it enables analytical insights that are not apparent from the recurrence form alone. The input-dependent M of AttnRes, for instance, reveals depth-wise attention sinks (§5.4.2), where certain layers consistently attract high weight regardless of input, mirroring the same phenomenon in sequence-wise attention [57]. Second, it informs new designs by exposing which properties of the kernel ϕ matter. For example, when ϕ decomposes as $\phi ( \pmb q , \pmb k ) = \varphi ( \pmb q ) ^ { \top } \varphi ( \pmb k )$ for some feature map φ [23], depth-wise attention collapses into a recurrence—precisely the structure underlying the MRLA–GLA and DDL–DeltaNet correspondences noted above.

Prior Residuals as Depth-Wise Linear Attention The structured-matrix perspective further relates to the sequencedepth duality by showing that existing residual variants are, in effect, instances of linear attention over the depth axis. For example, the unrolled (m)HC weight $\mathbf { M } _ { i  l } = \beta _ { i } ^ { \top } \mathbf { A } _ { i + 1  l } ^ { \times } \pmb { \alpha } _ { l }$ (Eq. 10) admits a natural attention interpretation in which $\alpha _ { l }$ plays the role of a query issued by layer $l , \beta _ { i }$ serves as a key summarizing the contribution of layer i, and the cumulative transition $\mathbf { A } _ { i + 1  l } ^ { \times }$ acts as a depth-relative positional operator [69] governing the query–key interaction across intervening layers. Notably, the m parallel streams correspond to state expansion [40, 29] along the depth axis, expanding the recurrent state from d to d× m and thereby increasing the semiseparable rank of M. [58] show that replacing $\mathbf { A } _ { i + 1  l } ^ { \times }$ with the identity matrix still yields competitive performance, highlighting the role of state expansion. Through this lens, methods like (m)HC thus act as depth-wise linear attention with matrix-valued states, while AttnRes acts as depth-wise softmax attention.

## 7 Related Work

Normalization, Scaling, and Depth Stability. The standard residual update $\pmb { h } _ { l + 1 } = \pmb { h } _ { l } + f _ { l } ( \pmb { h } _ { l } )$ [12] presents a fundamental tension between normalization placement and gradient propagation. PostNorm [52] maintains bounded magnitudes but distorts gradients, as repeated normalization on the residual path compounds into gradient vanishing at depth [60]. PreNorm [34, 60] restores a clean identity path yet introduces unbounded magnitude growth: since $\| \bar { \boldsymbol { h } } _ { l } \|$ grows as $O ( L )$ , each layer’s relative contribution shrinks, compelling deeper layers to produce ever-larger outputs and limiting effective depth [27]. Subsequent work reconciles both desiderata via scaled residual paths [54], hybrid normalization [73], amplified skip connections [4], or learned element-wise gates [45] (see Table 5). AttnRes sidesteps this tension by replacing the additive recurrence with selective aggregation over individual earlier-layer outputs, avoiding both the cumulative magnitude growth of PreNorm and the repeated scale contraction of PostNorm.

Multi-State Recurrence. All single-state methods above condition layer l only on $\boldsymbol { h } _ { l - 1 }$ , from which individual earlier-layer contributions cannot be selectively retrieved. Several methods address this by widening the recurrence to multiple parallel streams: Hyper-Connections [72] and its stabilized variant mHC [59] maintain m streams with learned mixing matrices; DDL [67] maintains a matrix state updated via a delta-rule erase-and-write mechanism; SiameseNorm [27] maintains two parameter-shared streams—one PreNorm and one PostNorm—to preserve identity gradients and bounded representations. While these methods alleviate information compression, they still condition on the immediate predecessor’s state; AttnRes is orthogonal, providing selective access to individual earlier-layer outputs while remaining compatible with any normalization or gating scheme. We discuss the formal connection to Hyper-Connections in $\ S 6 . 2$

Cross-Layer Connectivity. A separate line of work bypasses the single-state bottleneck by giving each layer direct access to individual earlier-layer outputs. The simplest approach uses static weights: DenseNet [17] concatenates all preceding feature maps; ELMo [38] computes a softmax-weighted sum of layer representations with learned scalar weights; DenseFormer [36] and ANCRe [68] assign learned per-layer scalar coefficients fixed after training. For input-dependent aggregation, MUDDFormer [56] generates position-dependent weights via a small MLP across four decoupled streams; MRLA [10] applies element-wise sigmoid gating over all previous layers, though its separable query–key product is closer to linear attention than softmax-based retrieval. Other methods trade full cross-layer access for more targeted designs: Value Residual Learning [71] accesses only a single earlier layer; LAuReL [30] augments the residual with low-rank projections over the previous k activations; Dreamer [24] combines sequence attention with depth attention and sparse experts. AttnRes combines softmax-normalized, input-dependent weights with selective access to all preceding layers through a single d-dimensional pseudo-query per layer, and introduces a block structure reducing cost from $\check { O } ( L ^ { \tilde { 2 } } )$ to $O ( L \bar { N } )$ . Cache-based pipeline communication and a two-phase computation strategy (§ 4) make Block AttnRes practical at scale with negligible overhead.

## Conclusion

Inspired by the duality between sequence and depth, we introduce AttnRes, which replaces fixed, uniform residual accumulation with learned, input-dependent depth-wise attention. We validate the method through ablation studies and scaling law experiments, showing that its gains persist across scales. Because Full AttnRes must access all preceding layer outputs at every layer, the memory footprint of cross-layer aggregation grows as $O ( L d )$ , which is prohibitive for large-scale models on current hardware. We therefore introduce Block AttnRes, which partitions layers into N blocks and attends over block-level representations. Empirically, using about 8 blocks recovers most of the gains of Full AttnRes, while finer-grained blocking remains a promising direction as future hardware constraints relax. Together with cross-stage caching and a two-phase computation strategy, Block AttnRes is practical at scale, incurring only marginal training overhead and minimal inference overhead.

## References

[1] Jacob Austin et al. Program Synthesis with Large Language Models. 2021. arXiv: 2108.07732 [cs.PL]. URL: https://arxiv.org/abs/2108.07732.

[2] Thomas Bachlechner et al. ReZero is All You Need: Fast Convergence at Large Depth. 2020. arXiv: 2003.04887 [cs.LG]. URL: https://arxiv.org/abs/2003.04887.

[3] Dzmitry Bahdanau, Kyunghyun Cho, and Yoshua Bengio. Neural Machine Translation by Jointly Learning to Align and Translate. 2016. arXiv: 1409.0473 [cs.CL]. URL: https://arxiv.org/abs/1409.0473.

[4] Chen Chen and Lai Wei. Post-LayerNorm Is Back: Stable, ExpressivE, and Deep. 2026. arXiv: 2601.19895 [cs.LG]. URL: https://arxiv.org/abs/2601.19895.

[5] Mark Chen et al. Evaluating Large Language Models Trained on Code. 2021. arXiv: 2107.03374 [cs.LG]. URL: https://arxiv.org/abs/2107.03374.

[6] Peter Clark et al. “Think you have Solved Question Answering? Try ARC, the AI2 Reasoning Challenge”. In: arXiv:1803.05457v1 (2018).

[7] Karl Cobbe et al. Training Verifiers to Solve Math Word Problems. 2021. arXiv: 2110.14168 [cs.LG]. URL: https://arxiv.org/abs/2110.14168.

[8] Tri Dao and Albert Gu. “Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Space Duality”. In: CoRR abs/2405.21060 (2024). DOI: 10.48550/ARXIV.2405.21060. arXiv: 2405.21060. URL: https://doi.org/10.48550/arXiv.2405.21060.

[9] DeepSeek-AI et al. DeepSeek-V3 Technical Report. 2025. arXiv: 2412.19437 [cs.CL]. URL: https://arxiv. org/abs/2412.19437.

[10] Yanwen Fang et al. Cross-Layer Retrospective Retrieving via Layer Attention. 2023. arXiv: 2302 . 03985 [cs.CV]. URL: https://arxiv.org/abs/2302.03985.

[11] Andrey Gromov et al. The Unreasonable Ineffectiveness of the Deeper Layers. 2025. arXiv: 2403 . 17887 [cs.CL]. URL: https://arxiv.org/abs/2403.17887.

[12] Kaiming He et al. Deep Residual Learning for Image Recognition. 2015. arXiv: 1512.03385 [cs.CV]. URL: https://arxiv.org/abs/1512.03385.

[13] Dan Hendrycks et al. Measuring Massive Multitask Language Understanding. 2021. arXiv: 2009 . 03300 [cs.CY]. URL: https://arxiv.org/abs/2009.03300.

[14] Dan Hendrycks et al. Measuring Mathematical Problem Solving With the MATH Dataset. 2021. arXiv: 2103. 03874 [cs.LG]. URL: https://arxiv.org/abs/2103.03874.

[15] Jordan Hoffmann et al. Training Compute-Optimal Large Language Models. 2022. arXiv: 2203.15556 [cs.CL]. URL: https://arxiv.org/abs/2203.15556.

[16] Shengding Hu et al. MiniCPM: Unveiling the Potential of Small Language Models with Scalable Training Strategies. 2024. arXiv: 2404.06395 [cs.CL]. URL: https://arxiv.org/abs/2404.06395.

[17] Gao Huang et al. Densely Connected Convolutional Networks. 2018. arXiv: 1608 . 06993 [cs.CV]. URL: https://arxiv.org/abs/1608.06993.

[18] Yanping Huang et al. “GPipe: Efficient Training of Giant Neural Networks using Pipeline Parallelism”. In: Advances in NeurIPS. 2019.

[19] Yuzhen Huang et al. “C-eval: A multi-level multi-discipline chinese evaluation suite for foundation models”. In: Advances in NeurIPS 36 (2023), pp. 62991–63010.

[20] Robert A. Jacobs et al. “Adaptive Mixtures of Local Experts”. In: Neural Computation 3.1 (1991), pp. 79–87. DOI: 10.1162/neco.1991.3.1.79.

[21] Mandar Joshi et al. “Triviaqa: A large scale distantly supervised challenge dataset for reading comprehension”. In: arXiv preprint arXiv:1705.03551 (2017).

[22] Jared Kaplan et al. Scaling Laws for Neural Language Models. 2020. arXiv: 2001.08361 [cs.LG]. URL: https://arxiv.org/abs/2001.08361.

[23] Angelos Katharopoulos et al. “Transformers are RNNs: Fast Autoregressive Transformers with Linear Attention”. In: Proceedings of ICML. Ed. by Hal Daumé III and Aarti Singh. PMLR, 2020, pp. 5156–5165. URL: https: //proceedings.mlr.press/v119/katharopoulos20a.html.

[24] Jonas Knupp et al. Depth-Recurrent Attention Mixtures: Giving Latent Reasoning the Attention it Deserves. 2026. arXiv: 2601.21582 [cs.AI]. URL: https://arxiv.org/abs/2601.21582.

[25] Aitor Lewkowycz et al. Solving Quantitative Reasoning Problems with Language Models. 2022. arXiv: 2206. 14858 [cs.CL]. URL: https://arxiv.org/abs/2206.14858.

[26] Haonan Li et al. “CMMLU: Measuring massive multitask language understanding in Chinese”. In: Findings of the Association for Computational Linguistics: ACL 2024. Ed. by Lun-Wei Ku, Andre Martins, and Vivek Srikumar. Bangkok, Thailand: Association for Computational Linguistics, Aug. 2024, pp. 11260–11285. DOI: 10 . 18653 / v1 / 2024 . findings - acl . 671. URL: https : / / aclanthology . org / 2024 . findings - acl.671/.

[27] Tianyu Li et al. SiameseNorm: Breaking the Barrier to Reconciling Pre/Post-Norm. 2026. arXiv: 2602.08064 [cs.LG]. URL: https://arxiv.org/abs/2602.08064.

[28] Jingyuan Liu et al. Muon is Scalable for LLM Training. 2025. arXiv: 2502.16982 [cs.LG]. URL: https: //arxiv.org/abs/2502.16982.

[29] Brian Mak and Jeffrey Flanigan. Residual Matrix Transformers: Scaling the Size of the Residual Stream. 2025. arXiv: 2506.22696 [cs.LG]. URL: https://arxiv.org/abs/2506.22696.

[30] Gaurav Menghani, Ravi Kumar, and Sanjiv Kumar. LAuReL: Learned Augmented Residual Layer. 2025. arXiv: 2411.07501 [cs.LG]. URL: https://arxiv.org/abs/2411.07501.

[31] Maxim Milakov and Natalia Gimelshein. Online normalizer calculation for softmax. 2018. arXiv: 1805.02867 [cs.PF]. URL: https://arxiv.org/abs/1805.02867.

[32] Tsendsuren Munkhdalai et al. “Metalearned Neural Memory”. In: ArXiv abs/1907.09720 (2019). URL: https: //api.semanticscholar.org/CorpusID:198179407.

[33] Deepak Narayanan et al. Efficient Large-Scale Language Model Training on GPU Clusters Using Megatron-LM. 2021. arXiv: 2104.04473 [cs.CL]. URL: https://arxiv.org/abs/2104.04473.

[34] Toan Q. Nguyen and Julian Salazar. “Transformers without Tears: Improving the Normalization of Self-Attention”. In: Proceedings of IWSLT. Ed. by Jan Niehues et al. 2019. URL: https : / / aclanthology . org/2019.iwslt-1.17/.

[35] OpenAI et al. GPT-4 Technical Report. 2024. arXiv: 2303.08774 [cs.CL]. URL: https://arxiv.org/abs/ 2303.08774.

[36] Matteo Pagliardini et al. DenseFormer: Enhancing Information Flow in Transformers via Depth Weighted Averaging. 2024. arXiv: 2402.02622 [cs.CL]. URL: https://arxiv.org/abs/2402.02622.

[37] Bowen Peng et al. “Yarn: Efficient context window extension of large language models”. In: arXiv preprint arXiv:2309.00071 (2023).

[38] Matthew E. Peters et al. “Deep Contextualized Word Representations”. In: Proceedings of NAACL. 2018, pp. 2227–2237. URL: https://aclanthology.org/N18-1202/.

[39] Reiner Pope et al. Efficiently Scaling Transformer Inference. 2022. arXiv: 2211.05102 [cs.LG].

[40] Zhen Qin et al. HGRN2: Gated Linear RNNs with State Expansion. 2024. arXiv: 2404.07904 [cs.CL].

[41] David Rein et al. “Gpqa: A graduate-level google-proof q&a benchmark”. In: First Conference on Language Modeling. 2024.

[42] Imanol Schlag, Kazuki Irie, and Jürgen Schmidhuber. “Linear Transformers Are Secretly Fast Weight Programmers”. In: Proceedings of ICML. Ed. by Marina Meila and Tong Zhang. PMLR, 2021, pp. 9355–9366. URL: https://proceedings.mlr.press/v139/schlag21a.html.

[43] Jürgen Schmidhuber. “Learning to control fast-weight memories: An alternative to dynamic recurrent networks”. In: Neural Computation 4.1 (1992), pp. 131–139.

[44] Freda Shi et al. Language Models are Multilingual Chain-of-Thought Reasoners. 2022. arXiv: 2210.03057 [cs.CL]. URL: https://arxiv.org/abs/2210.03057.

[45] Rupesh Kumar Srivastava, Klaus Greff, and Jürgen Schmidhuber. Highway Networks. 2015. arXiv: 1505.00387 [cs.LG]. URL: https://arxiv.org/abs/1505.00387.

[46] Yu Sun et al. “Learning to (Learn at Test Time): RNNs with Expressive Hidden States”. In: ArXiv abs/2407.04620 (2024). URL: https://api.semanticscholar.org/CorpusID:271039606.

[47] Yutao Sun et al. Retentive Network: A Successor to Transformer for Large Language Models. 2023. arXiv: 2307.08621 [cs.CL].

[48] Mirac Suzgun et al. “Challenging big-bench tasks and whether chain-of-thought can solve them”. In: arXiv preprint arXiv:2210.09261 (2022).

[49] Shawn Tan et al. “Scaling Stick-Breaking Attention: An Efficient Implementation and In-depth Study”. In: Proceedings of ICLR. 2025.

[50] Hugo Touvron et al. Going deeper with Image Transformers. 2021. arXiv: 2103.17239 [cs.CV]. URL: https: //arxiv.org/abs/2103.17239.

[51] Hugo Touvron et al. LLaMA: Open and Efficient Foundation Language Models. 2023. arXiv: 2302.13971 [cs.CL].

[52] Ashish Vaswani et al. “Attention is All you Need”. In: Advances in NeurIPS. Ed. by I. Guyon et al. Curran Associates, Inc., 2017. URL: https://proceedings.neurips.cc/paper\_files/paper/2017/file/ 3f5ee243547dee91fbd053c1c4a845aa-Paper.pdf.

[53] Ashish Vaswani et al. “Attention is All you Need”. In: Advances in NeurIPS. Ed. by I. Guyon et al. Vol. 30. Curran Associates, Inc., 2017. URL: https://proceedings.neurips.cc/paper\_files/paper/2017/ file/3f5ee243547dee91fbd053c1c4a845aa-Paper.pdf.

[54] Hongyu Wang et al. DeepNet: Scaling Transformers to 1,000 Layers. 2022. arXiv: 2203.00555 [cs.CL]. URL: https://arxiv.org/abs/2203.00555.

[55] Yubo Wang et al. “Mmlu-pro: A more robust and challenging multi-task language understanding benchmark”. In: Advances in NeurIPS 37 (2024), pp. 95266–95290.

[56] Da Xiao et al. “MUDDFormer: Breaking Residual Bottlenecks in Transformers via Multiway Dynamic Dense Connections”. In: Proceedings of ICML. 2025.

[57] Guangxuan Xiao et al. “Efficient streaming language models with attention sinks”. In: arXiv preprint arXiv:2309.17453 (2023).

[58] Tian Xie. Your DeepSeek mHC Might Not Need the “m”. Zhihu blog post. 2026. URL: https://zhuanlan. zhihu.com/p/2010852389670908320.

[59] Zhenda Xie et al. mHC: Manifold-Constrained Hyper-Connections. 2026. arXiv: 2512.24880 [cs.CL]. URL: https://arxiv.org/abs/2512.24880.

[60] Ruibin Xiong et al. On Layer Normalization in the Transformer Architecture. 2020. arXiv: 2002.04745 [cs.LG]. URL: https://arxiv.org/abs/2002.04745.

[61] Bowen Yang et al. Rope to Nope and Back Again: A New Hybrid Attention Strategy. 2025. arXiv: 2501.18795 [cs.CL]. URL: https://arxiv.org/abs/2501.18795.

[62] Songlin Yang, Jan Kautz, and Ali Hatamizadeh. “Gated Delta Networks: Improving Mamba2 with Delta Rule”. In: Proceedings of ICLR. 2025. URL: https://openreview.net/forum?id=r8H7xhYPwz.

[63] Songlin Yang et al. “Gated Linear Attention Transformers with Hardware-Efficient Training”. In: Proceedings of ICML. PMLR, 2024.

[64] Yongyi Yang and Jianyang Gao. mHC-lite: You Don’t Need 20 Sinkhorn-Knopp Iterations. 2026. arXiv: 2601. 05732 [cs.LG]. URL: https://arxiv.org/abs/2601.05732.

[65] Rowan Zellers et al. “HellaSwag: Can a Machine Really Finish Your Sentence?” In: Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics. 2019.

[66] Biao Zhang and Rico Sennrich. “Root mean square layer normalization”. In: Advances in NeurIPS 32 (2019).

[67] Yifan Zhang et al. Deep Delta Learning. 2026. arXiv: 2601.00417 [cs.LG]. URL: https://arxiv.org/ abs/2601.00417.

[68] Yilang Zhang et al. ANCRe: Adaptive Neural Connection Reassignment for Efficient Depth Scaling. 2026. arXiv: 2602.09009 [cs.LG]. URL: https://arxiv.org/abs/2602.09009.

[69] Yu Zhang et al. Kimi Linear: An Expressive, Efficient Attention Architecture. 2025. arXiv: 2510.26692 [cs.CL].

[70] Shu Zhong et al. Understanding Transformer from the Perspective of Associative Memory. 2025. arXiv: 2505. 19488 [cs.LG]. URL: https://arxiv.org/abs/2505.19488.

[71] Zhanchao Zhou et al. “Value Residual Learning”. In: Proceedings of ACL. Ed. by Wanxiang Che et al. Vienna, Austria, 2025, pp. 28341–28356. URL: https://aclanthology.org/2025.acl-long.1375/.

[72] Defa Zhu et al. Hyper-Connections. 2025. arXiv: 2409.19606 [cs.LG]. URL: https://arxiv.org/abs/ 2409.19606.

[73] Zhijian Zhuo et al. HybridNorm: Towards Stable and Efficient Transformer Training via Hybrid Normalization. 2025. arXiv: 2503.04598 [cs.CL]. URL: https://arxiv.org/abs/2503.04598.

## A Contributions

The authors are listed in order of the significance of their contributions, with those in project leadership roles appearing last.

<table><tr><td rowspan=1 colspan=2>Guangyu Chen*                                               Yanru ChenYu Zhang*                                                     Xin Men</td></tr><tr><td rowspan=1 colspan=1>Jianlin Su*</td><td rowspan=1 colspan=1>Haiqing Guo</td></tr><tr><td rowspan=1 colspan=1>Weixin Xu</td><td rowspan=1 colspan=1>Y. Charles</td></tr><tr><td rowspan=1 colspan=1>Siyuan Pan</td><td rowspan=1 colspan=1>Haoyu Lu</td></tr><tr><td rowspan=1 colspan=1>Yaoyu Wang</td><td rowspan=1 colspan=1>Lin Sui</td></tr><tr><td rowspan=1 colspan=1>Yucheng Wang</td><td rowspan=1 colspan=1>Jinguo Zhu</td></tr><tr><td rowspan=1 colspan=1>Guanduo Chen</td><td rowspan=1 colspan=1>Zaida Zhou</td></tr><tr><td rowspan=1 colspan=1>Bohong Yin</td><td rowspan=1 colspan=1>Weiran He</td></tr><tr><td rowspan=1 colspan=1>Yutian Chen</td><td rowspan=1 colspan=1>Weixiao Huang</td></tr><tr><td rowspan=1 colspan=1>Junjie Yan</td><td rowspan=1 colspan=1>Xinran Xu</td></tr><tr><td rowspan=1 colspan=1>Ming Wei</td><td rowspan=1 colspan=1>Yuzhi Wang</td></tr><tr><td rowspan=1 colspan=1>Y. Zhang</td><td rowspan=1 colspan=1>Guokun Lai</td></tr><tr><td rowspan=1 colspan=1>Fanqing Meng</td><td rowspan=1 colspan=1>Yulun Du</td></tr><tr><td rowspan=1 colspan=1>Chao Hong</td><td rowspan=1 colspan=1>Yuxin Wu</td></tr><tr><td rowspan=1 colspan=1>Xiaotong Xie</td><td rowspan=1 colspan=1>Zhilin Yang</td></tr><tr><td rowspan=1 colspan=2>Shaowei Liu                                                    Xinyu ZhouEnzhe LuYunpeng Tai</td></tr></table>

∗ Equal contribution

## B Optimized Inference I/O for Full Attention Residuals

A naïve implementation of Full AttnRes scans all preceding layer outputs at every layer, so memory traffic scales linearly with depth. As noted in $\ S 4 . 2$ , however, the pseudo-query ${ \pmb w } _ { l }$ is a learned parameter independent of both the input and the hidden state. We can therefore batch inter-block accesses across layers in a two-phase schedule, bringing total I/O well below the naïve bound.

Note that the block partition introduced below is purely an inference scheduling device. Unlike Block AttnRes, it leaves the model architecture unchanged and does not replace per-layer sources with block summaries; it simply makes the amortization argument concrete.

Setup Let the model have L layers and hidden dimension d, partitioned into N contiguous blocks of size $S = L / N$ Inference proceeds one block at a time: Phase 1 jointly computes inter-block attention for all S layers in the block against all preceding blocks, and Phase 2 walks through intra-block dependencies sequentially.

## Phase 1: Batched Inter-block Attention

Consider block n with its S layers. The queries $\{ w _ { l } \} _ { l \in B _ { r } }$ are all known before execution begins, so the $( n { - } 1 ) S$ preceding key–value pairs need only be read once from HBM and reused across all S queries. The read cost for block n is therefore

$$
\mathrm { R e a d } _ { \mathrm { i n t e r } } ^ { ( n ) } = 2 ( n - 1 ) S d ,\tag{11}
$$

where the factor of 2 accounts for both keys and values. Summing over all N blocks and using $S N = L { \mathrm { : } }$

$$
{ \mathrm { R e a d } } _ { \mathrm { i n t e r } } = \sum _ { n = 1 } ^ { N } 2 ( n - 1 ) S d = 2 S d \cdot { \frac { N ( N - 1 ) } { 2 } } = d L ( N - 1 ) .\tag{12}
$$

Phase 1 also writes one d-dimensional output per layer, giving $\mathrm { W r i t e } _ { \mathrm { i n t e r } } ^ { ( n ) } = S d$ per block and

$$
{ \mathrm { W r i t e } } _ { \mathrm { i n t e r } } = L d\tag{13}
$$

in total.

## Phase 2: Sequential Intra-block Attention

Phase 1 covers all sources before the current block. Within the block, however, each layer depends on those before it, so these must be handled in order. Layer t $( 1 \leq t \leq S )$ reads t−1 intra-block key–value pairs at a cost of $2 ( t { - } 1 ) d$ Summing over one block:

$$
{ \mathrm { R e a d } } _ { \mathrm { i n t r a } } ^ { ( n ) } = \sum _ { t = 1 } ^ { S } 2 ( t - 1 ) d = S ( S - 1 ) d .\tag{14}
$$

Phase 2 also writes one output per layer, so $\mathrm { W r i t e } _ { \mathrm { i n t r a } } ^ { ( n ) } = S d .$

## Total Amortized I/O per Layer

Summing both phases over all N blocks:

$$
\mathrm { R e a d } _ { \mathrm { t o t a l } } = d L ( N - 1 ) + N \cdot S ( S - 1 ) d , \qquad \mathrm { W r i t e } _ { \mathrm { t o t a l } } = 2 L d .\tag{15}
$$

Dividing by L and using $S N = L$

$$
\mathrm { R e a d p e r ~ l a y e r } = ( N - 1 ) d + ( S - 1 ) d = ( S + N - 2 ) d , \qquad \mathrm { W r i t e ~ p e r ~ l a y e r } = 2 d ,\tag{16}
$$

$$
\left| { \mathrm { ~ T o t a l ~ I / O ~ p e r ~ l a y e r } } = ( S + N ) d . \right|\tag{17}
$$

Batching inter-block reads thus brings per-layer I/O from $\mathcal { O } ( L )$ down to $\mathcal { O } ( S { + } N )$ . The schedule follows the same two-phase split as Block AttnRes: inter-block attention accounts for the bulk of the traffic, while sequential computation stays local within each block.