# FLASHATTENTION: Fast and Memory-Efficient Exact Attention with IO-Awareness

Tri Dao†, Daniel Y. Fu †, Stefano Ermon †, Atri Rudra ‡, Christopher Ré †

† Department of Computer Science, Stanford University

‡ Department of Computer Science and Engineering, University at Buffalo, SUNY {trid,danfu}@stanford.edu, ermon@stanford.edu, atri@buffalo.edu, chrismre@cs.stanford.edu

## Abstract

Transformers are slow and memory-hungry on long sequences, since the time and memory complexity of self-attention are quadratic in sequence length. Approximate attention methods have attempted to address this problem by trading off model quality to reduce the compute complexity, but often do not achieve wall-clock speedup. We argue that a missing principle is making attention algorithms IO-aware— accounting for reads and writes between levels of GPU memory. We propose FLASHATTENTION, an IO-aware exact attention algorithm that uses tiling to reduce the number of memory reads/writes between GPU high bandwidth memory (HBM) and GPU on-chip SRAM. We analyze the IO complexity of FLASHATTENTION, showing that it requires fewer HBM accesses than standard attention, and is optimal for a range of SRAM sizes. We also extend FLASHATTENTION to block-sparse attention, yielding an approximate attention algorithm that is faster than any existing approximate attention method. FLASHATTENTION trains Transformers faster than existing baselines: 15% end-to-end wall-clock speedup on BERT-large (seq. length 512) compared to the MLPerf 1.1 training speed record, 3× speedup on GPT-2 (seq. length 1K), and 2.4× speedup on long-range arena (seq. length 1K-4K). FLASHAT-TENTION and block-sparse FLASHATTENTION enable longer context in Transformers, yielding higher quality models (0.7 better perplexity on GPT-2 and 6.4 points of lift on long-document classification) and entirely new capabilities: the first Transformers to achieve better-than-chance performance on the Path-X challenge (seq. length 16K, 61.4% accuracy) and Path-256 (seq. length 64K, 63.1% accuracy).

## 1 Introduction

Transformer models [86] have emerged as the most widely used architecture in applications such as natural language processing and image classification. Transformers have grown larger [5] and deeper [87], but equipping them with longer context remains difficult [83], since the self-attention module at their heart has time and memory complexity quadratic in sequence length. An important question is whether making attention faster and more memory-efficient can help Transformer models address their runtime and memory challenges for long sequences.

Many approximate attention methods have aimed to reduce the compute and memory requirements of attention. These methods range from sparse-approximation [53, 77] to low-rank approximation [13, 52, 88], and their combinations [3, 9, 96]. Although these methods reduce the compute requirements to linear or near-linear in sequence length, many of them do not display wall-clock speedup against standard attention and have not gained wide adoption. One main reason is that they focus on FLOP reduction (which may not correlate with wall-clock speed) and tend to ignore overheads from memory access (IO).

In this paper, we argue that a missing principle is making attention algorithms IO-aware [1]—that is, carefully accounting for reads and writes to different levels of fast and slow memory (e.g., between fast GPU on-chip SRAM and relatively slow GPU high bandwidth memory, or HBM [47], Figure 1 left). On modern GPUs, compute speed has out-paced memory speed [64–66], and most operations in Transformers are bottlenecked by memory accesses [45]. IO-aware algorithms have been critical for similar memory-bound operations, when reading and writing data can account for a large portion of the runtime—such as database joins [74], image processing [73], numerical linear algebra [4], and more [42, 89]. However, common Python interfaces to deep learning such as PyTorch and Tensorflow do not allow fine-grained control of memory access.

![](images/2dc258835e5a7004cb34ca1fd012ec31a4a7b45d046d7a5322deff007c636a7b.jpg)  
Figure 1: Left: FLASHATTENTION uses tiling to prevent materialization of the large ?? ×?? attention matrix (dotted box) on (relatively) slow GPU HBM. In the outer loop (red arrows), FLASHATTENTION loops through blocks of the K and V matrices and loads them to fast on-chip SRAM. In each block, FLASHATTENTION loops over blocks of Q matrix (blue arrows), loading them to SRAM, and writing the output of the attention computation back to HBM. Right: Speedup over the PyTorch implementation of attention on GPT-2. FLASHATTENTION does not read and write the large ?? ×?? attention matrix to HBM, resulting in an 7.6× speedup on the attention computation.

We propose FLASHATTENTION, a new attention algorithm that computes exact attention with far fewer memory accesses. Our main goal is to avoid reading and writing the attention matrix to and from HBM. This requires (i) computing the softmax reduction without access to the whole input (ii) not storing the large intermediate attention matrix for the backward pass. We apply two well-established techniques to address these challenges. (i) We restructure the attention computation to split the input into blocks and make several passes over input blocks, thus incrementally performing the softmax reduction (also known as tiling). (ii) We store the softmax normalization factor from the forward pass to quickly recompute attention on-chip in the backward pass, which is faster than the standard approach of reading the intermediate attention matrix from HBM. We implement FLASHATTENTION in CUDA to achieve fine-grained control over memory access and fuse all the attention operations into one GPU kernel. Even with the increased FLOPs due to recomputation, our algorithm both runs faster (up to 7.6x on GPT-2 [70], Figure 1 right) and uses less memory—linear in sequence length—than standard attention, thanks to the massively reduced amount of HBM access.

We analyze the IO complexity [1] of FLASHATTENTION, proving that it requires $O ( N ^ { 2 } d ^ { 2 } M ^ { - 1 } )$ HBM accesses where ?? is the head dimension and ?? is the size of SRAM, as compared to $\Omega ( N d + N ^ { 2 } )$ of standard attention. For typical values of ?? and ??, FLASHATTENTION requires many times fewer HBM accesses compared to standard attention (up to 9× fewer, as shown in Fig. 2). Moreover, we provide a lower bound, showing that no exact attention algorithm can asymptotically improve on the number of HBM accesses over all SRAM sizes.

We also show that FLASHATTENTION can serve as a useful primitive for realizing the potential of approximate attention algorithms by overcoming their issues with memory access overhead. As a proof of concept, we implement block-sparse FLASHATTENTION, a sparse attention algorithm that is 2-4× faster than even FLASHATTENTION, scaling up to sequence length of 64k. We prove that block-sparse FLASHATTENTION has better IO complexity than FLASHATTENTION by a factor proportional to the sparsity ratio. We discuss further extensions to other operations (attention on multi-GPU, kernel regression, block-sparse matrix multiply) in Section 5. We open-source FLASHATTENTION to make it easier to build on this primitive1.

We empirically validate that FLASHATTENTION speeds up model training and improves model quality by modeling longer context. We also benchmark the runtime and memory footprint of FLASHAT-TENTION and block-sparse FLASHATTENTION compared to prior attention implementations.

• Faster Model Training. FLASHATTENTION trains Transformer models faster in wall-clock time. We train BERT-large (seq. length 512) 15% faster than the training speed record in MLPerf 1.1 [60], GPT2 (seq. length 1K) 3× faster than baseline implementations from HuggingFace [91] and Megatron-LM [80], and long-range arena (seq. length 1K-4K) 2.4× faster than baselines.

• Higher Quality Models. FLASHATTENTION scales Transformers to longer sequences, which improves their quality and enables new capabilities. We observe a 0.7 improvement in perplexity on GPT-2 and 6.4 points of lift from modeling longer sequences on long-document classification [14]. FLASHATTENTION enables the first Transformer that can achieve better-than-chance performance on the Path-X [83] challenge, solely from using a longer sequence length (16K). Block-sparse FLASHATTENTION enables a Transformer to scale to even longer sequences (64K), resulting in the first model that can achieve better-than-chance performance on Path-256.

• Benchmarking Attention. FLASHATTENTION is up to 3× faster than the standard attention implementation across common sequence lengths from 128 to 2K and scales up to 64K. Up to sequence length of 512, FLASHATTENTION is both faster and more memory-efficient than any existing attention method, whereas for sequence length beyond 1K, some approximate attention methods (e.g., Linformer) start to become faster. On the other hand, block-sparse FLASHATTENTION is faster than all existing approximate attention methods that we know of.

## 2 Background

We provide some background on the performance characteristics of common deep learning operations on modern hardware (GPUs). We also describe the standard implementation of attention.

## 2.1 Hardware Performance

We focus here on GPUs. Performance on other hardware accelerators are similar [48, 50].

GPU Memory Hierarchy. The GPU memory hierarchy (Fig. 1 left) comprises multiple forms of memory of different sizes and speeds, with smaller memory being faster. As an example, the A100 GPU has 40-80GB of high bandwidth memory (HBM) with bandwidth 1.5-2.0TB/s and 192KB of on-chip SRAM per each of 108 streaming multiprocessors with bandwidth estimated around 19TB/s [46, 47]. The on-chip SRAM is an order of magnitude faster than HBM but many orders of magnitude smaller in size. As compute has gotten faster relative to memory speed [64–66], operations are increasingly bottlenecked by memory (HBM) accesses. Thus exploiting fast SRAM becomes more important.

Execution Model. GPUs have a massive number of threads to execute an operation (called a kernel).   
Each kernel loads inputs from HBM to registers and SRAM, computes, then writes outputs to HBM.

Performance characteristics. Depending on the balance of computation and memory accesses, operations can be classified as either compute-bound or memory-bound. This is commonly measured by the arithmetic intensity [89], which is the number of arithmetic operations per byte of memory access.

1. Compute-bound: the time taken by the operation is determined by how many arithmetic operations there are, while time accessing HBM is much smaller. Typical examples are matrix multiply with large inner dimension, and convolution with large number of channels.

2. Memory-bound: the time taken by the operation is determined by the number of memory accesses, while time spent in computation is much smaller. Examples include most other operations: elementwise (e.g., activation, dropout), and reduction (e.g., sum, softmax, batch norm, layer norm).

Kernel fusion. The most common approach to accelerate memory-bound operations is kernel fusion: if there are multiple operations applied to the same input, the input can be loaded once from HBM, instead of multiple times for each operation. Compilers can automatically fuse many elementwise operations [55, 68, 78]. However, in the context of model training, the intermediate values still need to be written to HBM to save for the backward pass, reducing the effectiveness of naive kernel fusion.

## 2.2 Standard Attention Implementation

Given input sequences $\mathbf { Q } , \mathbf { K } , \mathbf { V } \in \mathbb { R } ^ { N \times d }$ where ?? is the sequence length and ?? is the head dimension, we want to compute the attention output $\mathbf { O } \in \mathbb { R } ^ { N \times d }$ :

$$
\begin{array} { r } { \mathbf { S } = \mathbf { Q } \mathbf { K } ^ { \top } \in \mathbb { R } ^ { N \times N } , \quad \mathbf { P } = \operatorname { s o f t m a x } ( \mathbf { S } ) \in \mathbb { R } ^ { N \times N } , \quad \mathbf { O } = \mathbf { P } \mathbf { V } \in \mathbb { R } ^ { N \times d } , } \end{array}
$$

where softmax is applied row-wise.

Standard attention implementations materialize the matrices S and P to HBM, which takes $O ( N ^ { 2 } )$ memory. Often $N \gg d \left( { \mathrm { e . g . } } \right.$ , for GPT2, ?? = 1024 and ?? = 64). We describe the standard attention implementation in Algorithm 0. As some or most of the operations are memory-bound (e.g., softmax), the large number of memory accesses translates to slow wall-clock time.

This problem is exacerbated by other elementwise operations applied to the attention matrix, such as masking applied to S or dropout applied to P. As a result, there have been many attempts to fuse several elementwise operations, such as fusing masking with softmax [80].

In Section 3.2, we will show that the standard attention implementation performs HBM accesses quadratic in the sequence length ??. We also compare the number of FLOPs and number of HBM accesses of standard attention and of our method (FLASHATTENTION).

Algorithm 0 Standard Attention Implementation   
Require: Matrices $\mathbf { Q } , \mathbf { K } , \mathbf { V } \in \mathbb { R } ^ { N \times d }$ in HBM.   
1: Load Q,K by blocks from HBM, compute S=QK>, write S to HBM.   
2: Read S from HBM, compute P = softmax(S), write P to HBM.   
3: Load P and V by blocks from HBM, compute O = PV, write O to HBM.   
4: Return O.

## 3 FLASHATTENTION: Algorithm, Analysis, and Extensions

We show how to compute exact attention with fewer HBM reads/writes and without storing large intermediate matrices for the backward pass. This yields an attention algorithm that is both memory efficient and faster in wall-clock time. We analyze its IO complexity, showing that our method requires much fewer HBM accesses compared to standard attention. We further show that FLASHATTENTION can serve as a useful primitive by extending it to handle block-sparse attention.

We focus here on the forward pass for ease of exposition; Appendix B contains details for the backward.

## 3.1 An Efficient Attention Algorithm With Tiling and Recomputation

Given the inputs ${ \bf Q } , { \bf K } , { \bf V } \in \mathbb { R } ^ { N \times d }$ in HBM, we aim to compute the attention output $\mathbf { O } \in \mathbb { R } ^ { N \times d }$ and write it to HBM. Our goal is to reduce the amount of HBM accesses (to sub-quadratic in ??).

We apply two established techniques (tiling, recomputation) to overcome the technical challenge of computing exact attention in sub-quadratic HBM accesses. We describe this in Algorithm 1. The main idea is that we split the inputs Q,K,V into blocks, load them from slow HBM to fast SRAM, then compute the attention output with respect to those blocks. By scaling the output of each block by the right normalization factor before adding them up, we get the correct result at the end.

Tiling. We compute attention by blocks. Softmax couples columns of K, so we decompose the large softmax with scaling [53, 62, 69]. For numerical stability, the softmax of vector $\boldsymbol { x } \in \mathbb { R } ^ { \dot { B } }$ is computed:

$$
m ( x ) : = \operatorname* { m a x } _ { i } \ x _ { i } , \quad f ( x ) : = \left[ e ^ { x _ { 1 } - m ( x ) } \quad \ldots \quad e ^ { x _ { B } - m ( x ) } \right] , \quad \ell ( x ) : = \sum _ { i } f ( x ) _ { i } , \quad \mathrm { s o f t m a x } ( x ) : = \frac { f ( x ) } { \ell ( x ) } .
$$

$$
\boldsymbol { x } ^ { ( 1 ) } , \boldsymbol { x } ^ { ( 2 ) } \in \mathbb { R } ^ { B }
$$

$$
\boldsymbol { x } = \left\lceil \boldsymbol { x } ^ { ( 1 ) } \boldsymbol { x } ^ { ( 2 ) } \right\rceil \in \mathbb { R } ^ { 2 B }
$$

$$
\begin{array} { r } { m ( x ) = m ( [ x ^ { ( 1 ) } ~ x ^ { ( 2 ) } ] ) = \operatorname* { m a x } ( m ( x ^ { ( 1 ) } ) , m ( x ^ { ( 2 ) } ) ) , \quad f ( x ) = [ e ^ { m ( x ^ { ( 1 ) } ) - m ( x ) } f ( x ^ { ( 1 ) } )  \quad e ^ { m ( x ^ { ( 2 ) } ) - m ( x ) } f ( x ^ { ( 2 ) } ) ] } \end{array}
$$

$$
\ell ( x ) = \ell ( \left[ x ^ { ( 1 ) } ~ x ^ { ( 2 ) } \right] ) = e ^ { m ( x ^ { ( 1 ) } ) - m ( x ) } \ell ( x ^ { ( 1 ) } ) + e ^ { m ( x ^ { ( 2 ) } ) - m ( x ) } \ell ( x ^ { ( 2 ) } ) , \quad \mathrm { s o f t m a x } ( x ) = \frac { f ( x ) } { \ell ( x ) } .
$$

Therefore if we keep track of some extra statistics $( m ( x ) , \ell ( x ) )$ , we can compute softmax one block at a time.2 We thus split the inputs Q,K,V into blocks (Algorithm 1 line 1), compute the softmax values along with extra statistics (Algorithm 1 line 1), and combine the results (Algorithm 1 line 1).

Recomputation. One of our goals is to not store $O ( N ^ { 2 } )$ intermediate values for the backward pass. The backward pass typically requires the matrices $\mathbf { S } , \mathbf { \dot { P } } \in \mathrm { \mathbb { R } } ^ { N \times N }$ to compute the gradients with respect to Q,K,V. However, by storing the output O and the softmax normalization statistics $( m , \ell ) .$ , we can recompute the attention matrix S and P easily in the backward pass from blocks of Q,K,V in SRAM. This can be seen as a form of selective gradient checkpointing [10, 36]. While gradient checkpointing has been suggested to reduce the maximum amount of memory required [69], all implementations (that we know off) have to trade speed for memory. In contrast, even with more FLOPs, our recomputation speeds up the backward pass due to reduced HBM accesses (Fig. 2). The full backward pass description is in Appendix B.

Implementation details: Kernel fusion. Tiling enables us to implement our algorithm in one CUDA kernel, loading input from HBM, performing all the computation steps (matrix multiply, softmax, optionally masking and dropout, matrix multiply), then write the result back to HBM (masking and dropout in Appendix B). This avoids repeatedly reading and writing of inputs and outputs from and to HBM.

Algorithm 1 FLASHATTENTION   
Require: Matrices $\mathbf { Q } , \mathbf { K } , \mathbf { V } \in \mathbb { R } ^ { N \times d }$ in HBM, on-chip SRAM of size ??.   
1: Set block sizes $\begin{array} { r } { \bar { B _ { c } } = \lceil \frac { M } { 4 d } \rceil , B _ { r } = \operatorname* { m i n } ( \lceil \frac { M } { 4 d } \rceil , d ) } \end{array}$   
2: Initialize $\mathbf { O } = ( 0 ) _ { N \times d } \in \mathbb { R } ^ { N \times d } , \ell = ( 0 ) _ { N } ^ { \cdots } \in \mathbb { R } ^ { N } , m = ( - \infty ) _ { N } \in \mathbb { R } ^ { N }$ in HBM.   
3: Divide Q into $\begin{array} { r } { T _ { r } = \left\lceil \frac { N } { B _ { r } } \right\rceil } \end{array}$ blocks $\mathbf { Q } _ { 1 } , . . . , \mathbf { Q } _ { T _ { r } }$ of size $B _ { r } \times d$ each, and divide $\mathbf { K } , \mathbf { V }$ in to $\begin{array} { r } { T _ { c } = \left\lceil \frac { N } { B _ { c } } \right\rceil } \end{array}$   
blocks ${ \bf K } _ { 1 } , . . . , { \bf K } _ { T _ { c } }$ and $\dot { \mathbf { V } } _ { 1 } , . . . , \mathbf { V } _ { T _ { c } }$ , of size $B _ { c } { \times } d$ each.   
4: Divide O into $T _ { r }$ blocks $\mathbf { O } _ { i } , . . . , \bar { \mathbf { O } } _ { T _ { r } }$ of size $B _ { r } { \times } d$ each, divide ℓ into $T _ { r }$ blocks $\ell _ { i } , . . . , \ell _ { T _ { r } }$ of size   
$B _ { r }$ each, divide ?? into $T _ { r }$ blocks $m _ { 1 } , . . . , m _ { T _ { r } }$ of size $B _ { r }$ each.   
5: for $1 \leq j \leq T _ { c }$ do   
6: Load $\mathbf { K } _ { j } , \mathbf { V } _ { j }$ from HBM to on-chip SRAM.   
7: for $1 \leq i \leq \dot { T } _ { r }$ do   
8: Load $\mathbf { Q } _ { i } , \mathbf { O } _ { i } , \ell _ { i } , m _ { i }$ from HBM to on-chip SRAM.   
9: On chip, compute $\mathbf { S } _ { i j } = \mathbf { Q } _ { i } \mathbf { K } _ { j } ^ { T } \in \mathbb { R } ^ { B _ { r } \times B _ { c } }$   
10: On chip, compute ??˜ ?? ?? = rowmax $( \mathbf { S } _ { i j } ) \in \mathbb { R } ^ { B _ { r } } , \tilde { \mathbf { P } } _ { i j } = \exp ( \mathbf { S } _ { i j } - \tilde { m } _ { i j } ) \in \mathbb { R } ^ { B _ { r } \times B _ { c } }$ (pointwise),   
$\tilde { \ell } _ { i j } = \mathrm { r o w s u m } ( \tilde { \mathbf { P } } _ { i j } ) \in \mathbb { R } ^ { \tilde { B } _ { r } }$   
11: On chip, compute $m _ { i } ^ { \mathrm { n e w } } = \operatorname* { m a x } ( m _ { i } , \tilde { m } _ { i j } ) \in \mathbb { R } ^ { B _ { r } } , \ell _ { i } ^ { \mathrm { n e w } } = e ^ { m _ { i } - m _ { i } ^ { \mathrm { n e w } } } \ell _ { i } + e ^ { \tilde { m } _ { i j } - m _ { i } ^ { \mathrm { n e w } } } \tilde { \ell } _ { i j } \in \mathbb { R } ^ { B _ { r } }$   
12: Write $\mathbf O _ { i } \gets \mathrm { d i a g } ( \ell _ { i } ^ { \mathrm { n e } } \mathrm { ^ { \dot { w } } } ) ^ { - 1 } ( \mathrm { d i a g } ( \ell _ { i } ) e ^ { m _ { i } - m _ { i } ^ { \mathrm { n e w } } } \mathbf O _ { i } + \dot { e } ^ { \tilde { m } _ { i j } - m _ { i } ^ { \mathrm { n e w } } } \tilde { \mathbf P } _ { i j } \mathbf V _ { j } )$ to HBM.   
13: Write $\ell _ { i } \gets \ell _ { i } ^ { \mathrm { n e w } } , m _ { i } ^ { \cdot } \gets m _ { i } ^ { \mathrm { n e w } }$ to HBM.   
14: end for   
15: end for   
16: Return O.

We show FLASHATTENTION’s correctness, runtime, and memory requirement (proof in Appendix C).

Theorem 1. Algorithm 1 returns ${ \bf O } = \mathrm { s o f t m a x } ( { \bf Q } { \bf K } ^ { \top } ) { \bf V }$ with $O ( N ^ { 2 } d )$ FLOPs and requires ??(??) additional memory beyond inputs and output.

## 3.2 Analysis: IO Complexity of FLASHATTENTION

We analyze the IO complexity of FLASHATTENTION, showing significant reduction in HBM accesses compared to standard attention. We also provide a lower bound, proving that no exact attention algorithm can asymptotically improve on HBM accesses over all SRAM sizes. Proofs are in Appendix C.

Theorem 2. Let ?? be the sequence length, ?? be the head dimension, and ?? be size of SRAM with $d \leq M \leq N d .$ Standard attention (Algorithm 0) requires $\Theta ( N d + N ^ { 2 } )$ HBM accesses, while FLASHATTENTION (Algorithm 1) requires $\stackrel { \smile } { \Theta } ( N ^ { 2 } d ^ { 2 } M ^ { - 1 } )$ HBM accesses.

For typical values of ?? (64-128) and ?? (around 100KB), $d ^ { 2 }$ is many times smaller than ??, and thus FLASHATTENTION requires many times fewer HBM accesses than standard implementation. This leads to both faster execution and lower memory footprint, which we validate in Section 4.3.

The main idea of the proof is that given the SRAM size of ??, we can load blocks of $\mathbf { K } , \mathbf { V }$ of size Θ(??) each (Algorithm 1 line 1). For each block of K and V, we iterate over all blocks of Q (Algorithm 1 line 1) to compute the intermediate values, resulting in $\Theta ( N d M ^ { - 1 } )$ passes over Q. Each pass loads Θ(?? ??) elements, which amounts to $\Theta ( \acute { N } ^ { 2 } d ^ { 2 } M ^ { - 1 } )$ HBM accesses. We similarly prove that the backward pass of standard attention requires $\Theta ( N d + N ^ { 2 } )$ HBM accesses while the backward pass of FLASHATTENTION requires $\Theta ( N ^ { 2 } d ^ { 2 } M ^ { - 1 } )$ HBM accesses (Appendix B).

We prove a lower-bound: one cannot asymptotically improve on the number of HBM accesses for all values of ?? (the SRAM size) when computing exact attention.

<table><tr><td>Attention</td><td>Standard</td><td>FLASHATTENTION</td></tr><tr><td>GFLOPs</td><td>66.6</td><td>75.2</td></tr><tr><td>HBMR/W (GB)</td><td>35.3</td><td>4.4</td></tr><tr><td>Runtime (ms)</td><td>35.1</td><td>11.7</td></tr></table>

![](images/6da7cb789e71659f4b9928f9cc31913357f69306d5189a7df7fff8bb8503bc7e.jpg)

![](images/dd550d344a9a0389a19dce9b4b496fec2548f806000a6188995b00d45415531a.jpg)  
Figure 2: Left: Forward + backward runtime of standard attention and FLASHATTENTION for seq. length 1024, head dim. 64, 16 heads, batch size 64, key-padding mask and no dropout on A100 GPU. HBM access is one of the primary factors affecting runtime. Middle: Forward runtime of FLASHATTENTION (seq. length 1024, head dim. 64, 16 heads, batch size 64) on A100 GPU. Fewer HBM accesses result in faster runtime, up to a point. Right: The runtime (for seq. length 4K) of block-sparse FLASHATTENTION is faster than FLASHATTENTION by a factor proportional to the sparsity.

Proposition 3. Let ?? be the sequence length, ?? be the head dimension, and ?? be size of SRAM with $d \leq \bar { M } \leq N d .$ There does not exist an algorithm to compute exact attention with $o ( N ^ { 2 } d ^ { 2 } M ^ { - 1 } )$ HBM accesses for all ?? in the range $[ d , N d ]$

The proof relies on the fact that for $M = \Theta ( N d )$ any algorithm must perform $\Omega ( N ^ { 2 } d ^ { 2 } M ^ { - 1 } ) = \Omega ( N d )$ HBM accesses. This type of lower bound over a subrange of ?? is common in the streaming algorithms literature [92]. We leave proving parameterized complexity [29] lower bounds in terms of ?? as exciting future work.

We validate that the number of HBM accesses is the main determining factor of attention run-time. In Fig. 2 (left), we see that even though FLASHATTENTION has higher FLOP count compared to standard attention (due to recomputation in the backward pass), it has much fewer HBM accesses, resulting in much faster runtime. In Fig. 2 (middle), we vary the block size $B _ { c }$ of FLASHATTENTION, which results in different amounts of HBM accesses, and measure the runtime of the forward pass. As block size increases, the number of HBM accesses decreases (as we make fewer passes over the input), and runtime decreases. For large enough block size (beyond 256), the runtime is then bottlenecked by other factors (e.g., arithmetic operations). Moreover, larger block size will not fit into the small SRAM size.

## 3.3 Extension: Block-Sparse FLASHATTENTION

We extend FLASHATTENTION to approximate attention: we propose block-sparse FLASHATTEN-TION, whose IO complexity is smaller than FLASHATTENTION by a factor proportional to the sparsity.

Given inputs ${ \mathbf { Q } } , { \mathbf { K } } , { \mathbf { V } } \in \mathbb { R } ^ { N \times d }$ and a mask matrix $\tilde { \mathbf { M } } \in \{ 0 , 1 \} ^ { N \times N }$ , we want to compute:

$$
\begin{array} { r } { \mathbf { S } = \mathbf { Q } \mathbf { K } ^ { \top } \in \mathbb { R } ^ { N \times N } , \quad \mathbf { P } = \operatorname { s o f t m a x } ( \mathbf { S } \odot \mathbb { I } _ { \tilde { \mathbf { M } } } ) \in \mathbb { R } ^ { N \times N } , \quad \mathbf { O } = \mathbf { P } \mathbf { V } \in \mathbb { R } ^ { \tilde { N } \times d } , } \end{array}
$$

where $( \mathbf { S } \odot \mathbb { 1 } _ { \tilde { \mathbf { M } } } ) _ { k l } = \mathbf { S } _ { k l } \mathrm { ~ i f ~ } \tilde { \mathbf { M } } _ { k l } = 1$ and −∞ if ${ \bf M } _ { k l } = 0 .$ . We require M˜ to have block form: for some block sizes $B _ { r } , B _ { c }$ , for all $k , l , \tilde { \mathbf { M } } _ { k , l } = \mathbf { M } _ { i j }$ with $i = \lfloor k / B _ { r } \rfloor , j = \lfloor l / B _ { c } \rfloor$ for some $\mathbf { M } \in \{ 0 , 1 \} ^ { N / B _ { r } \times N / B _ { c } }$

Given a predefined block sparsity mask $\mathbf { M } \in \{ 0 , 1 \} ^ { N / B _ { r } \times N / B _ { c } }$ we can easily adapt Algorithm 1 to only compute the nonzero blocks of the attention matrix. The algorithm is identical to Algorithm 1, except we skip zero blocks. We reproduce the algorithm description in Algorithm 5 in Appendix B.

We also analyze the IO complexity of block-sparse FLASHATTENTION.

Proposition 4. Let ?? be the sequence length, ?? be the head dimension, and ?? be size of SRAM with $d \leq { \overline { { M } } } \leq N d .$ Block-sparse FLASHATTENTION (Algorithm 5) requires $\Theta ( N d + N ^ { 2 } d ^ { 2 } \mathbf { \bar { \mathit { M } } } ^ { - 1 } s )$ HBM accesses where ?? is the fraction of nonzero blocks in the block-sparsity mask.

We see that applying block-sparsity yields a direct improvement by the sparsity to the larger term in the IO complexity. For large sequence lengths √ $N ,$ ?? is often set to $N ^ { - 1 / 2 } \left[ 1 2 \right]$ or ??−1log?? [3, 18, 96], resulting in $\Theta ( N { \sqrt { N } } )$ or Θ(??log??) IO complexity. For downstream experiments, we use the fixed butterfly sparsity pattern [18], which has been shown to be able to approximate arbitrary sparsity [17]. In Fig. 2 (right), we validate that as the sparsity increases, the runtime of block-sparse FLASHATTEN-TION improves proportionally. On the LRA benchmark, block-sparse FLASHATTENTION achieves 2.8× speedup, while performing on par with standard attention (Section 4).

## 4 Experiments

We evaluate the impact of using FLASHATTENTION to train Transformer models. We validate two claims about training time and model accuracy, and report attention runtime and memory benchmarks.

• Training Speed. FLASHATTENTION outperforms the MLPerf 1.1 [60] speed record for BERT by 15%, and speeds up GPT-2 up to 3× over HuggingFace [91] and 1.8× over Megatron [80] over standard Transformers. FLASHATTENTION speeds up the long-range arena (LRA) benchmark 2.4×.

• Quality. FLASHATTENTION scales Transformers to longer sequences, yielding higher quality. FLASHATTENTION trains GPT-2 with context length 4K faster than Megatron trains GPT-2 with context length 1K, while achieving 0.7 better perplexity. Modeling longer sequences yields 6.4 points of lift on two long-document classification tasks. Finally, FLASHATTENTION yields the first Transformer that can achieve better-than-random performance on the challenging Path-X task (sequence length 16K), and block-sparse FLASHATTENTION yields the first sequence model that we know of that can achieve better-than-random performance on Path-256 (sequence length 64K).

• Benchmarking Attention. We measure the runtime and memory performance of FLASHATTEN-TION and block-sparse FLASHATTENTION based on sequence length. We confirm that the memory footprint of FLASHATTENTION scales linearly with seq. length and is up to 3× faster than standard attention for common seq. lengths (up to 2K). We confirm that runtime of block-sparse FLASHAT-TENTION scales linearly in seq. length and is faster than all existing approximate attention baselines.

Additional experiment details are in Appendix E.

## 4.1 Faster Models with FLASHATTENTION

BERT. FLASHATTENTION yields the fastest single-node BERT training speed that we know of. We train a BERT-large [24] model with FLASHATTENTION on Wikipedia. Table 1 compares our training time to the implementation from Nvidia that set the training speed record for MLPerf 1.1 [60, 63]. Our implementation is 15% faster.

Table 1: Training time of BERT-large, starting from the same initialization provided by the MLPerf benchmark, to reach the target accuracy of 72.0% on masked language modeling. Averaged over 10 runs on 8×A100 GPUs.
<table><tr><td>BERTImplementation</td><td>Training time (minutes)</td></tr><tr><td>NvidiaMLPerf1.1[63]</td><td>20.0± 1.5</td></tr><tr><td>FLASHATTENTION (Ours)</td><td>17.4 ± 1.4</td></tr></table>

GPT-2. FLASHATTENTION yields faster training times for GPT-2 [70] on the large OpenWebtext dataset [34] than the widely used HuggingFace [91] and Megatron-LM [80] implementations. Table 2 shows up to 3× end-to-end speedup compared to Huggingface and 1.7× speedup compared to Megatron-LM. FLASHATTENTION achieves the same perplexity as the other two implementations, as we do not change the model definition. Appendix E includes plots of the validation perplexity throughout training, confirming that FLASHATTENTION is as numerically stable as the baselines and produces the same training / validation curves.

Table 2: GPT-2 small and medium using FLASHATTENTION achieve up to 3× speed up compared to Huggingface implementation and up to 1.7× compared to Megatron-LM. Training time reported on 8×A100s GPUs.
<table><tr><td>Model implementations</td><td>OpenWebText (ppl)</td><td>Training time (speedup)</td></tr><tr><td>GPT-2 small - Huggingface [91]</td><td>18.2</td><td>9.5 days (1.0x)</td></tr><tr><td>GPT-2 small - Megatron-LM[80]</td><td>18.2</td><td>4.7 days (2.0x)</td></tr><tr><td>GPT-2 small -FLASHATTENTION</td><td>18.2</td><td>2.7 days (3.5x)</td></tr><tr><td>GPT-2 medium - Huggingface [91]</td><td>14.2</td><td>21.0 days (1.0x)</td></tr><tr><td>GPT-2 medium - Megatron-LM [80]</td><td>14.2</td><td>11.5 days (1.8×)</td></tr><tr><td>GPT-2 medium-FLASHATTENTION</td><td>14.2</td><td>6.9 days (3.0×)</td></tr></table>

Long-range Arena. We compare vanilla Transformer (with either standard implementation or FLASHATTENTION) on the long-range arena (LRA [83]) benchmark. We measure accuracy, throughput, and training time of all models. Each task has a different sequence length varying between 1024 and 4096. We follow the implementation and experimental setting in Tay et al. [83]and Xiong et al. [94].3 Table 3 shows that FLASHATTENTION achieves up 2.4× speed-up compared to standard attention. Block-sparse FLASHATTENTION is faster than all of the approximate attention methods that we have tested.

## 4.2 Better Models with Longer Sequences

Language Modeling with Long Context. The runtime and memory-efficiency of FLASHAT-TENTION allow us to increase the context length of GPT-2 by 4× while still running faster than the optimized implementation from Megatron-LM. Table 4 shows that that GPT-2 with

Table 3: The performance of standard attention, FLASHATTENTION, block-sparse FLASHATTENTION, and approximate attention baselines on the Long-Range-Arena benchmarks.
<table><tr><td>Models</td><td>ListOps</td><td>Text</td><td>Retrieval</td><td>Image</td><td>Pathfinder</td><td>Avg</td><td>Speedup</td></tr><tr><td>Transformer</td><td>36.0</td><td>63.6</td><td>81.6</td><td>42.3</td><td>72.7</td><td>59.3</td><td>=</td></tr><tr><td>FLASHATTENTION</td><td>37.6</td><td>63.9</td><td>81.4</td><td>43.5</td><td>72.7</td><td>59.8</td><td>2.4×</td></tr><tr><td>Block-sparse FLASHATTENTION</td><td>37.0</td><td>63.0</td><td>81.3</td><td>43.6</td><td>73.3</td><td>59.6</td><td>2.8×</td></tr><tr><td>Linformer [88]</td><td>35.6</td><td>55.9</td><td>77.7</td><td>37.8</td><td>67.6</td><td>54.9</td><td>2.5x</td></tr><tr><td>Linear Attention [52]</td><td>38.8</td><td>63.2</td><td>80.7</td><td>42.6</td><td>72.5</td><td>59.6</td><td>2.3×</td></tr><tr><td>Performer [13]</td><td>36.8</td><td>63.6</td><td>82.2</td><td>42.1</td><td>69.9</td><td>58.9</td><td>1.8×</td></tr><tr><td>Local Attention [83]</td><td>36.1</td><td>60.2</td><td>76.7</td><td>40.6</td><td>66.6</td><td>56.0</td><td>1.7×</td></tr><tr><td>Reformer[53]</td><td>36.5</td><td>63.8</td><td>78.5</td><td>39.6</td><td>69.4</td><td>57.6</td><td>1.3×</td></tr><tr><td>Smyrf [20]</td><td>36.1</td><td>64.1</td><td>79.0</td><td>39.6</td><td>70.5</td><td>57.9</td><td>1.7×</td></tr></table>

FLASHATTENTION and context length 4K is still 30% faster than GPT-2 from Megatron with context length 1K, while achieving 0.7 better perplexity.

Table 4: GPT-2 small with FLASHATTENTION, with 4× larger context length compared to Megatron-LM, is still 30% faster while achieving 0.7 better perplexity. Training time on 8×A100 GPUs is reported.
<table><tr><td>Model implementations</td><td>Context length</td><td>Open WebText (ppl)</td><td>Training time (speedup)</td></tr><tr><td>GPT-2 small-Megatron-LM</td><td>1k</td><td>18.2</td><td>4.7 days (1.0x)</td></tr><tr><td>GPT-2 small-FLASHATTENTION</td><td>1k</td><td>18.2</td><td>2.7 days (1.7×)</td></tr><tr><td>GPT-2 small-FLASHATTENTION</td><td>2k</td><td>17.7</td><td>3.0 days (1.6x)</td></tr><tr><td>GPT-2 small - FLASHATTENTION</td><td>4k</td><td>17.2</td><td>3.6 days (1.3x)</td></tr></table>

Long Document Classification. Training Transformers with longer sequences with FLASHAT-TENTION improves performance on the MIMIC-III [49] and ECtHR [6, 7] datasets. MIMIC-III contains intensive care unit patient discharge summaries, each annotated with multiple labels. ECtHR contains legal cases from the European Court of Human Rights, each of which is mapped to articles of the Convention of Human Rights that were allegedly violaged. Both of these datasets contain very long text documents; the average number of tokens in MIMIC is 2,395 tokens, and the longest document contains 14,562 tokens, while the average and longest numbers in ECtHR are 2,197 and 49,392, respectively. We evaluate lift from increasing the sequence length of a pretrained RoBERTa model [58] (we repeat the positional embeddings, as in Beltagy et al. [3]).

Table 5 shows that sequence length 16K outperforms length 512 by 4.3 points on MIMIC, and that length 8K outperforms length 512 by 8.5 points on ECtHR. The discrepancies may be due to subtle distribution shifts: MIMIC-III contains specialized medical text and thus may be more susceptible to a distribution shift in the document length, whereas ECtHR contains general language.

Table 5: Long Document performance (micro $F _ { 1 } )$ at different sequence lengths using FLASHATTEN-TION.  
Table 6: We report the first Transformer model that can achieve non-random performance on Path-X and Path-256.
<table><tr><td></td><td>512</td><td>1024</td><td>2048</td><td>4096</td><td>8192</td><td>16384</td></tr><tr><td>MIMIC-III [49]</td><td>52.8</td><td>50.7</td><td>51.7</td><td>54.6</td><td>56.4</td><td>57.1</td></tr><tr><td>ECtHR[6]</td><td>72.2</td><td>74.3</td><td>77.1</td><td>78.6</td><td>80.7</td><td>79.2</td></tr></table>

<table><tr><td>Model</td><td>Path-X</td><td>Path-256</td></tr><tr><td>Transformer</td><td>X</td><td>X</td></tr><tr><td>Linformer [88]</td><td>X</td><td>X</td></tr><tr><td>Linear Attention [52]</td><td>X</td><td>X</td></tr><tr><td>Performer[13]</td><td>X</td><td>X</td></tr><tr><td>Local Attention [83]</td><td>X</td><td>X</td></tr><tr><td>Reformer[53]</td><td>X</td><td>X</td></tr><tr><td>SMYRF[20]</td><td>X</td><td>X</td></tr><tr><td>FLASHATTENTION</td><td>61.4</td><td>X</td></tr><tr><td>Block-sparseFLASHATTENTION</td><td>56.0</td><td>63.1</td></tr></table>

Path-X and Path-256. The Path-X and Path-256 benchmarks are challenging tasks from the long-range arena benchmark designed to test long context. The task is to classify whether two points in a black and white 128×128 (or 256×256) image have a path connecting them, and the images are fed to the transformer one pixel at a time. In prior work, all transformer models have either run out of memory, or only achieved random performance [83]. There has been a search for alternative architectures that can model such long context [39]. We present here the first result of Transformer models being able to solve Path-X and Path-256 (Table 6). We pretrain a transformer on Path-64, and then transfer to Path-X by spatially interpolating the positional embeddings. FLASHATTENTION achieves 61.4 accuracy on Path-X. Additionally, block-sparse FLASHATTENTION enables the Transformers to scale to sequence length 64K, achieving 63.1 accuracy4 on Path-256.

![](images/585ab4e3f0c38a6e087bdadbbd48cf60010e20150c533eb8e617db1ba65850b4.jpg)  
Figure 3: Left: runtime of forward pass + backward pass. Right: attention memory usage.

## 4.3 Benchmarking Attention

We vary sequence length and measure runtime and memory usage of FLASHATTENTION and block-sparse FLASHATTENTION against various attention baselines on one A100 GPU with 40 GB HBM, with dropout and a padding mask. We compare against reference implementations for exact attention, approximate attention, and sparse attention. We report a subset of baselines in the main body; Appendix E contains more baselines and full details.

Runtime. Figure 3 (left) reports the runtime in milliseconds of the forward + backward pass of FLASHATTENTION and block-sparse FLASHATTENTION compared to the baselines in exact, approximate, and sparse attention (exact numbers in Appendix E). Runtime grows quadratically with sequence length, but FLASHATTENTION runs significantly faster than exact attention baselines, up to 3× faster than the PyTorch implementation. The runtimes of many approximate/sparse attention mechanisms grow linearly with sequence length, but FLASHATTENTION still runs faster than approximate and sparse attention for short sequences due to fewer memory accesses. The approximate attention runtimes begin to cross over with FLASHATTENTION at sequences between 512 and 1024. On the other hand, block-sparse FLASHATTENTION is faster than all implementations of exact, sparse, and approximate attention that we know of, across all sequence lengths.

Memory Footprint. Figure 3 (right) shows the memory footprint of FLASHATTENTION and block-sparse FLASHATTENTION compared to various exact, approximate, and sparse attention baselines. FLASHATTENTION and block-sparse FLASHATTENTION have the same memory footprint, which grows linearly with sequence length. FLASHATTENTION is up to 20× more memory efficient than exact attention baselines, and is more memory-efficient than the approximate attention baselines. All other algorithms except for Linformer run out of memory on an A100 GPU before 64K, and FLASHATTENTION is still 2× more efficient than Linformer.

## 5 Limitations and Future Directions

We discuss limitations of our approach and future directions. Related work is given in Appendix A.

Compiling to CUDA. Our current approach to building IO-aware implementations of attention requires writing a new CUDA kernel for each new attention implementation. This requires writing the attention algorithm in a considerably lower-level language than PyTorch, and requires significant engineering effort. Implementations may also not be transferrable across GPU architectures. These limitations suggest the need for a method that supports writing attention algorithms in a high-level language (e.g., PyTorch), and compiling to IO-aware implementations in CUDA—similar to efforts such as Halide in image processing [73].

IO-Aware Deep Learning. We believe that the IO-aware approach can extend beyond attention. Attention is the most memory-intensive computation in Transformers, but every layer in a deep network touches GPU HBM. We hope our work inspires IO-aware implementations of additional modules. We discuss these potential extensions in Appendix D.

Multi-GPU IO-Aware Methods. Our IO-aware implementation of attention is optimal within constants for computing attention on a single GPU. However, the attention computation may be parallelizable across multiple GPUs [75]. Using multiple GPUs adds an additional layer to IO analysis— accounting for data transfer between GPUs. We hope our work inspires future work in this direction.

Societal Impacts. As Transformer-based foundation models grow in size and data, our work seeks to understand how to train these large models more efficiently. This may allow a general community with limited access to computational resources to train and understand those foundation models. Our method is applicable to all Transformer-based models, which have a variety of applications, both positive and negative. For example, language modeling may make it easier to spread misinformation, while image classification models may make automatic surveillance easier. Alleviating these risks requires addressing application-specific issues such as privacy, bias, and discrimination.

## Acknowledgments

Our implementation uses Apex’s FMHA code (https://github.com/NVIDIA/apex/tree/ master/apex/contrib/csrc/fmha) as a starting point. We thank Young-Jun Ko for the in-depth explanation of his FMHA implementation and for his thoughtful answers to our questions about CUDA. We thank Sabri Eyuboglu, Megan Leszczynski, Laurel Orr, Yuhuai Wu, Beidi Chen, and Xun Huang for their constructive feedback and suggestions on early drafts of the paper. We thank Markus Rabe and Charles Staats for helpful discussion of their attention algorithm.

We gratefully acknowledge the support of NIH under No. U54EB020405 (Mobilize), NSF under Nos. CCF1763315 (Beyond Sparsity), CCF1563078 (Volume to Velocity), and 1937301 (RTML); ARL under No. W911NF-21-2-0251 (Interactive Human-AI Teaming); ONR under No. N000141712266 (Unifying Weak Supervision); ONR N00014-20-1-2480: Understanding and Applying Non-Euclidean Geometry in Machine Learning; N000142012275 (NEPTUNE); NXP, Xilinx, LETI-CEA, Intel, IBM, Microsoft, NEC, Toshiba, TSMC, ARM, Hitachi, BASF, Accenture, Ericsson, Qualcomm, Analog Devices, Google Cloud, Salesforce, Total, the HAI-GCP & HAI-Azure Cloud Credits for Research program, the Stanford Data Science Initiative (SDSI), Department of Defense (DoD) through the National Defense Science and Engineering Graduate Fellowship (NDSEG) Program, and members of the Stanford DAWN project: Facebook, Google, and VMWare. The U.S. Government is authorized to reproduce and distribute reprints for Governmental purposes notwithstanding any copyright notation thereon. Any opinions, findings, and conclusions or recommendations expressed in this material are those of the authors and do not necessarily reflect the views, policies, or endorsements, either expressed or implied, of NIH, ONR, or the U.S. Government. Atri Rudra’s research is supported by NSF grant CCF-1763481.

## References

[1] Alok Aggarwal and S Vitter, Jeffrey. The input/output complexity of sorting and related problems. Communications of the ACM, 31(9):1116–1127, 1988.

[2] Irwan Bello. LambdaNetworks: Modeling long-range interactions without attention. arXiv preprint arXiv:2102.08602, 2021.

[3] Iz Beltagy, Matthew E Peters, and Arman Cohan. Longformer: The long-document transformer. arXiv preprint arXiv:2004.05150, 2020.

[4] L Susan Blackford, Antoine Petitet, Roldan Pozo, Karin Remington, R Clint Whaley, James Demmel, Jack Dongarra, Iain Duff, Sven Hammarling, Greg Henry, et al. An updated set of basic linear algebra subprograms (blas). ACM Transactions on Mathematical Software, 28(2): 135–151, 2002.

[5] Tom Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah, Jared D Kaplan, Prafulla Dhariwal, Arvind Neelakantan, Pranav Shyam, Girish Sastry, Amanda Askell, et al. Language models are few-shot learners. Advances in neural information processing systems, 33:1877–1901, 2020.

[6] Ilias Chalkidis, Ion Androutsopoulos, and Nikolaos Aletras. Neural legal judgment prediction in English. In Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics, pages 4317–4323, Florence, Italy, 2019. Association for Computational Linguistics. doi: 10.18653/v1/P19-1424. URL https://www.aclweb.org/anthology/P19-1424.

[7] Ilias Chalkidis, Manos Fergadiotis, Dimitrios Tsarapatsanis, Nikolaos Aletras, Ion Androutsopoulos, and Prodromos Malakasiotis. Paragraph-level rationale extraction through regularization: A case study on european court of human rights cases. In Proceedings of

the Annual Conference of the North American Chapter of the Association for Computational Linguistics, Mexico City, Mexico, 2021. Association for Computational Linguistics.

[8] Benjamin Charlier, Jean Feydy, Joan Alexis Glaunès, François-David Collin, and Ghislain Durif. Kernel operations on the gpu, with autodiff, without memory overflows. Journal of Machine Learning Research, 22(74):1–6, 2021. URL http://jmlr.org/papers/v22/20-275.html.

[9] Beidi Chen, Tri Dao, Eric Winsor, Zhao Song, Atri Rudra, and Christopher Ré. Scatterbrain: Unifying sparse and low-rank attention. In Advances in Neural Information Processing Systems (NeurIPS), 2021.

[10] Tianqi Chen, Bing Xu, Chiyuan Zhang, and Carlos Guestrin. Training deep nets with sublinear memory cost. arXiv preprint arXiv:1604.06174, 2016.

[11] Tianqi Chen, Thierry Moreau, Ziheng Jiang, Lianmin Zheng, Eddie Yan, Haichen Shen, Meghan Cowan, Leyuan Wang, Yuwei Hu, Luis Ceze, et al. {TVM}: An automated {End-to-End} optimizing compiler for deep learning. In 13th USENIX Symposium on Operating Systems Design and Implementation (OSDI 18), pages 578–594, 2018.

[12] Rewon Child, Scott Gray, Alec Radford, and Ilya Sutskever. Generating long sequences with sparse transformers. arXiv preprint arXiv:1904.10509, 2019.

[13] Krzysztof Marcin Choromanski, Valerii Likhosherstov, David Dohan, Xingyou Song, Andreea Gane, Tamas Sarlos, Peter Hawkins, Jared Quincy Davis, Afroz Mohiuddin, Lukasz Kaiser, et al. Rethinking attention with performers. In International Conference on Learning Representations (ICLR), 2020.

[14] Xiang Dai, Ilias Chalkidis, Sune Darkner, and Desmond Elliott. Revisiting transformer-based models for long document classification. arXiv preprint arXiv:2204.06683, 2022.

[15] Zihang Dai, Zhilin Yang, Yiming Yang, Jaime G Carbonell, Quoc Le, and Ruslan Salakhutdinov. Transformer-XL: Attentive language models beyond a fixed-length context. In Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics, pages 2978–2988, 2019.

[16] Tri Dao, Albert Gu, Matthew Eichhorn, Atri Rudra, and Christopher Ré. Learning fast algorithms for linear transforms using butterfly factorizations. In International Conference on Machine Learning (ICML), 2019.

[17] Tri Dao, Nimit Sohoni, Albert Gu, Matthew Eichhorn, Amit Blonder, Megan Leszczynski, Atri Rudra, and Christopher Ré. Kaleidoscope: An efficient, learnable representation for all structured linear maps. In International Conference on Learning Representations (ICLR), 2020.

[18] Tri Dao, Beidi Chen, Kaizhao Liang, Jiaming Yang, Zhao Song, Atri Rudra, and Christopher Ré. Pixelated butterfly: Simple and efficient sparse training for neural network models. In International Conference on Learning Representations (ICLR), 2022.

[19] Tri Dao, Beidi Chen, Nimit Sohoni, Arjun Desai, Michael Poli, Jessica Grogan, Alexander Liu, Aniruddh Rao, Atri Rudra, and Christopher Ré. Monarch: Expressive structured matrices for efficient and accurate training. In International Conference on Machine Learning (ICML), 2022.

[20] Giannis Daras, Nikita Kitaev, Augustus Odena, and Alexandros G Dimakis. Smyrf-efficient attention using asymmetric clustering. Advances in Neural Information Processing Systems, 33:6476–6489, 2020.

[21] Christopher De Sa, Albert Gu, Rohan Puttagunta, Christopher Ré, and Atri Rudra. A twopronged progress in structured dense matrix vector multiplication. In Proceedings of the Twenty-Ninth Annual ACM-SIAM Symposium on Discrete Algorithms, pages 1060–1079. SIAM, 2018.

[22] Jia Deng, Wei Dong, Richard Socher, Li-Jia Li, Kai Li, and Li Fei-Fei. Imagenet: A large-scale hierarchical image database. In 2009 IEEE conference on computer vision and pattern recognition, pages 248–255. Ieee, 2009.

[23] Peter J Denning. The working set model for program behavior. Communications of the ACM, 11(5):323–333, 1968.

[24] Jacob Devlin, Ming-Wei Chang, Kenton Lee, and Kristina Toutanova. BERT: Pre-training of deep bidirectional transformers for language understanding. 2019.

[25] Xin Dong, Shangyu Chen, and Sinno Jialin Pan. Learning to prune deep neural networks via layer-wise optimal brain surgeon. arXiv preprint arXiv:1705.07565, 2017.

[26] Alexey Dosovitskiy, Lucas Beyer, Alexander Kolesnikov, Dirk Weissenborn, Xiaohua Zhai, Thomas Unterthiner, Mostafa Dehghani, Matthias Minderer, Georg Heigold, Sylvain Gelly, et al. An image is worth 16x16 words: Transformers for image recognition at scale. In International Conference on Learning Representations, 2020.

[27] Y Eidelman and I Gohberg. On a new class of structured matrices. Integral Equations and Operator Theory, 34(3):293–324, 1999.

[28] Jean Feydy, Joan Glaunès, Benjamin Charlier, and Michael Bronstein. Fast geometric learning with symbolic matrices. Advances in Neural Information Processing Systems, 33, 2020.

[29] Jörg Flum and Martin Grohe. Parameterized Complexity Theory. Springer, 2006.

[30] Jonathan Frankle and Michael Carbin. The lottery ticket hypothesis: Finding sparse, trainable neural networks. In International Conference on Learning Representations, 2018.

[31] Jonathan Frankle, Gintare Karolina Dziugaite, Daniel M Roy, and Michael Carbin. Stabilizing the lottery ticket hypothesis. arXiv preprint arXiv:1903.01611, 2019.

[32] Jonathan Frankle, Gintare Karolina Dziugaite, Daniel Roy, and Michael Carbin. Linear mode connectivity and the lottery ticket hypothesis. In International Conference on Machine Learning, pages 3259–3269. PMLR, 2020.

[33] Karan Goel, Albert Gu, Chris Donahue, and Christopher Ré. It’s raw! audio generation with state-space models. In International Conference on Machine Learning (ICML), 2022.

[34] Aaron Gokaslan, Vanya Cohen, Pavlick Ellie, and Stefanie Tellex. Openwebtext corpus, 2019.

[35] Jim Gray, Surajit Chaudhuri, Adam Bosworth, Andrew Layman, Don Reichart, Murali Venkatrao, Frank Pellow, and Hamid Pirahesh. Data cube: A relational aggregation operator generalizing group-by, cross-tab, and sub-totals. Data mining and knowledge discovery, 1(1):29–53, 1997.

[36] Andreas Griewank and Andrea Walther. Evaluating derivatives: principles and techniques of algorithmic differentiation. SIAM, 2008.

[37] Albert Gu, Tri Dao, Stefano Ermon, Atri Rudra, and Christopher Ré. Hippo: Recurrent memory with optimal polynomial projections. In Advances in neural information processing systems (NeurIPS), 2020.

[38] Albert Gu, Isys Johnson, Karan Goel, Khaled Saab, Tri Dao, Atri Rudra, and Christopher Ré. Combining recurrent, convolutional, and continuous-time models with linear state space layers. Advances in Neural Information Processing Systems, 34, 2021.

[39] Albert Gu, Karan Goel, and Christopher Ré. Efficiently modeling long sequences with structured state spaces. In The International Conference on Learning Representations (ICLR), 2022.

[40] Song Han, Jeff Pool, John Tran, and William J Dally. Learning both weights and connections for efficient neural networks. arXiv preprint arXiv:1506.02626, 2015.

[41] Song Han, Huizi Mao, and William J Dally. Deep compression: Compressing deep neural networks with pruning, trained quantization and huffman coding. In International Conference on Learning Representations, 2016.

[42] John Hennessy and David Patterson. Memory hierarchy design. Computer Architecture: A Quantitative Approach, pages 390–525, 2003.

[43] Sara Hooker. The hardware lottery. arXiv preprint arXiv:2009.06489, 2020.

[44] Weizhe Hua, Zihang Dai, Hanxiao Liu, and Quoc V Le. Transformer quality in linear time. arXiv preprint arXiv:2202.10447, 2022.

[45] Andrei Ivanov, Nikoli Dryden, Tal Ben-Nun, Shigang Li, and Torsten Hoefler. Data movement is all you need: A case study on optimizing transformers. Proceedings of Machine Learning and Systems, 3:711–732, 2021.

[46] Zhe Jia and Peter Van Sandt. Dissecting the Ampere GPU architecture via microbenchmarking. GPU Technology Conference, 2021.

[47] Zhe Jia, Marco Maggioni, Benjamin Staiger, and Daniele P Scarpazza. Dissecting the nvidia Volta GPU architecture via microbenchmarking. arXiv preprint arXiv:1804.06826, 2018.

[48] Zhe Jia, Blake Tillman, Marco Maggioni, and Daniele Paolo Scarpazza. Dissecting the graphcore IPU architecture via microbenchmarking. arXiv preprint arXiv:1912.03413, 2019.

[49] Alistair EW Johnson, Tom J Pollard, Lu Shen, Li-wei H Lehman, Mengling Feng, Mohammad Ghassemi, Benjamin Moody, Peter Szolovits, Leo Anthony Celi, and Roger G Mark. Mimic-iii, a freely accessible critical care database. Scientific data, 3(1):1–9, 2016.

[50] Norman P Jouppi, Cliff Young, Nishant Patil, David Patterson, Gaurav Agrawal, Raminder Bajwa, Sarah Bates, Suresh Bhatia, Nan Boden, Al Borchers, et al. In-datacenter performance analysis of a tensor processing unit. In Proceedings of the 44th annual international symposium on computer architecture, pages 1–12, 2017.

[51] Thomas Kailath, Sun-Yuan Kung, and Martin Morf. Displacement ranks of matrices and linear equations. Journal of Mathematical Analysis and Applications, 68(2):395–407, 1979.

[52] Angelos Katharopoulos, Apoorv Vyas, Nikolaos Pappas, and François Fleuret. Transformers are RNNs: Fast autoregressive transformers with linear attention. In International Conference on Machine Learning, pages 5156–5165. PMLR, 2020.

[53] Nikita Kitaev, Łukasz Kaiser, and Anselm Levskaya. Reformer: The efficient transformer. In The International Conference on Machine Learning (ICML), 2020.

[54] Zhenzhong Lan, Mingda Chen, Sebastian Goodman, Kevin Gimpel, Piyush Sharma, and Radu Soricut. Albert: A lite BEDRT for self-supervised learning of language representations. In The International Conference on Learning Representations (ICLR), 2020.

[55] Mingzhen Li, Yi Liu, Xiaoyan Liu, Qingxiao Sun, Xin You, Hailong Yang, Zhongzhi Luan, Lin Gan, Guangwen Yang, and Depei Qian. The deep learning compiler: A comprehensive survey. IEEE Transactions on Parallel and Distributed Systems, 32(3):708–727, 2020.

[56] Valerii Likhosherstov, Krzysztof Choromanski, Jared Davis, Xingyou Song, and Adrian Weller. Sub-linear memory: How to make performers slim. arXiv preprint arXiv:2012.11346, 2020.

[57] Ji Lin, Yongming Rao, Jiwen Lu, and Jie Zhou. Runtime neural pruning. In I. Guyon, U. V. Luxburg, S. Bengio, H. Wallach, R. Fergus, S. Vishwanathan, and R. Garnett, editors, Advances in Neural Information Processing Systems, volume 30. Curran Associates, Inc., 2017.

[58] Yinhan Liu, Myle Ott, Naman Goyal, Jingfei Du, Mandar Joshi, Danqi Chen, Omer Levy, Mike Lewis, Luke Zettlemoyer, and Veselin Stoyanov. Roberta: A robustly optimized bert pretraining approach. arXiv preprint arXiv:1907.11692, 2019.

[59] Xuezhe Ma, Xiang Kong, Sinong Wang, Chunting Zhou, Jonathan May, Hao Ma, and Luke Zettlemoyer. Luna: Linear unified nested attention. Advances in Neural Information Processing Systems, 34, 2021.

[60] Peter Mattson, Christine Cheng, Gregory Diamos, Cody Coleman, Paulius Micikevicius, David Patterson, Hanlin Tang, Gu-Yeon Wei, Peter Bailis, Victor Bittorf, et al. Mlperf training benchmark. Proceedings of Machine Learning and Systems, 2:336–349, 2020.

[61] Frank McSherry, Michael Isard, and Derek G Murray. Scalability! but at what {COST}? In 15th Workshop on Hot Topics in Operating Systems (HotOS XV), 2015.

[62] Maxim Milakov and Natalia Gimelshein. Online normalizer calculation for softmax. arXiv preprint arXiv:1805.02867, 2018.

[63] MLCommons. Mlperf 1.1 training results, 2021. URL https://mlcommons.org/en/ training-normal-11/.

[64] NVIDIA. Nvidia Tesla V100 GPU architecture, 2017.

[65] NVIDIA. Nvidia A100 tensor core GPU architecture, 2020.

[66] NVIDIA. Nvidia H100 tensor core GPU architecture, 2022.

[67] D Stott Parker. Random butterfly transformations with applications in computational linear algebra. 1995.

[68] Adam Paszke, Sam Gross, Francisco Massa, Adam Lerer, James Bradbury, Gregory Chanan, Trevor Killeen, Zeming Lin, Natalia Gimelshein, Luca Antiga, et al. Pytorch: An imperative style, high-performance deep learning library. Advances in neural information processing systems, 32, 2019.

[69] Markus N Rabe and Charles Staats. Self-attention does not need $O ( n ^ { 2 } )$ memory. arXiv preprint arXiv:2112.05682, 2021.

[70] Alec Radford, Jeffrey Wu, Rewon Child, David Luan, Dario Amodei, Ilya Sutskever, et al. Language models are unsupervised multitask learners. OpenAI blog, 1(8):9, 2019.

[71] Jack Rae and Ali Razavi. Do transformers need deep long-range memory? In Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics, Online, July 2020. Association for Computational Linguistics. URL https://www.aclweb.org/anthology/2020.acl-main.672.

[72] Jack W Rae, Anna Potapenko, Siddhant M Jayakumar, and Timothy P Lillicrap. Compressive transformers for long-range sequence modelling. In The International Conference on Learning Representations (ICLR), 2020.

[73] Jonathan Ragan-Kelley, Connelly Barnes, Andrew Adams, Sylvain Paris, Frédo Durand, and Saman Amarasinghe. Halide: a language and compiler for optimizing parallelism, locality, and recomputation in image processing pipelines. Acm Sigplan Notices, 48(6):519–530, 2013.

[74] Raghu Ramakrishnan, Johannes Gehrke, and Johannes Gehrke. Database management systems, volume 3. McGraw-Hill New York, 2003.

[75] Benjamin Recht and Christopher Ré. Parallel stochastic gradient algorithms for large-scale matrix completion. Mathematical Programming Computation, 5(2):201–226, 2013.

[76] Hongyu Ren, Hanjun Dai, Zihang Dai, Mengjiao Yang, Jure Leskovec, Dale Schuurmans, and Bo Dai. Combiner: Full attention transformer with sparse computation cost. Advances in Neural Information Processing Systems, 34, 2021.

[77] Aurko Roy, Mohammad Saffar, Ashish Vaswani, and David Grangier. Efficient content-based sparse attention with routing transformers. Transactions of the Association for Computational Linguistics, 9:53–68, 2021.

[78] Amit Sabne. XLA: Compiling machine learning for peak performance. 2020.

[79] Victor Sanh, Thomas Wolf, and Alexander M Rush. Movement pruning: Adaptive sparsity by fine-tuning. arXiv preprint arXiv:2005.07683, 2020.

[80] Mohammad Shoeybi, Mostofa Patwary, Raul Puri, Patrick LeGresley, Jared Casper, and Bryan Catanzaro. Megatron-LM: Training multi-billion parameter language models using model parallelism. arXiv preprint arXiv:1909.08053, 2019.

[81] Vikas Sindhwani, Tara Sainath, and Sanjiv Kumar. Structured transforms for small-footprint deep learning. In Advances in Neural Information Processing Systems, pages 3088–3096, 2015.

[82] Sainbayar Sukhbaatar, Edouard Grave, Piotr Bojanowski, and Armand Joulin. Adaptive attention span in transformers. In Proceedings of the Annual Meeting of the Association for Computational Linguistics, 2019.

[83] Yi Tay, Mostafa Dehghani, Samira Abnar, Yikang Shen, Dara Bahri, Philip Pham, Jinfeng Rao, Liu Yang, Sebastian Ruder, and Donald Metzler. Long range arena: A benchmark for efficient transformers. In International Conference on Learning Representations, 2020.

[84] Yi Tay, Mostafa Dehghani, Dara Bahri, and Donald Metzler. Efficient transformers: A survey. arXiv preprint arXiv:2009.06732, 2020.

[85] Hugo Touvron, Matthieu Cord, Matthijs Douze, Francisco Massa, Alexandre Sablayrolles, and Hervé Jégou. Training data-efficient image transformers & distillation through attention. In International Conference on Machine Learning, pages 10347–10357. PMLR, 2021.

[86] Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N Gomez, Łukasz Kaiser, and Illia Polosukhin. Attention is all you need. Advances in neural information processing systems, 30, 2017.

[87] Hongyu Wang, Shuming Ma, Li Dong, Shaohan Huang, Dongdong Zhang, and Furu Wei. Deepnet: Scaling transformers to 1,000 layers. arXiv preprint arXiv:2203.00555, 2022.

[88] Sinong Wang, Belinda Z Li, Madian Khabsa, Han Fang, and Hao Ma. Linformer: Self-attention with linear complexity. arXiv preprint arXiv:2006.04768, 2020.

[89] Samuel Williams, Andrew Waterman, and David Patterson. Roofline: an insightful visual performance model for multicore architectures. Communications of the ACM, 52(4):65–76, 2009.

[90] Michael E Wolf and Monica S Lam. A data locality optimizing algorithm. In Proceedings of the ACM SIGPLAN 1991 conference on Programming language design and implementation, pages 30–44, 1991.

[91] Thomas Wolf, Lysandre Debut, Victor Sanh, Julien Chaumond, Clement Delangue, Anthony Moi, Pierric Cistac, Tim Rault, Rémi Louf, Morgan Funtowicz, Joe Davison, Sam Shleifer, Patrick von Platen, Clara Ma, Yacine Jernite, Julien Plu, Canwen Xu, Teven Le Scao, Sylvain Gugger, Mariama Drame, Quentin Lhoest, and Alexander M. Rush. Transformers: State-of-the-art natural language processing. In Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing: System Demonstrations, pages 38–45, Online, October 2020. Association for Computational Linguistics. URL https://www.aclweb.org/anthology/2020.emnlp-demos.6.

[92] David P Woodruff. Optimal space lower bounds for all frequency moments. In SODA, volume 4, pages 167–175. Citeseer, 2004.

[93] Felix Wu, Angela Fan, Alexei Baevski, Yann N Dauphin, and Michael Auli. Pay less attention with lightweight and dynamic convolutions. In The International Conference on Learning Representations (ICLR), 2019.

[94] Yunyang Xiong, Zhanpeng Zeng, Rudrasis Chakraborty, Mingxing Tan, Glenn Fung, Yin Li, and Vikas Singh. Nyströmformer: A nystöm-based algorithm for approximating self-attention. In Proceedings of the AAAI Conference on Artificial Intelligence. AAAI Conference on Artificial Intelligence, volume 35, page 14138, 2021.

[95] Li Yuan, Yunpeng Chen, Tao Wang, Weihao Yu, Yujun Shi, Zi-Hang Jiang, Francis EH Tay, Jiashi Feng, and Shuicheng Yan. Tokens-to-token vit: Training vision transformers from scratch on imagenet. In Proceedings of the IEEE/CVF International Conference on Computer Vision, pages 558–567, 2021.

[96] Manzil Zaheer, Guru Guruganesh, Kumar Avinava Dubey, Joshua Ainslie, Chris Alberti, Santiago Ontanon, Philip Pham, Anirudh Ravula, Qifan Wang, Li Yang, et al. Big bird: Transformers for longer sequences. Advances in Neural Information Processing Systems, 33, 2020.

[97] Shuangfei Zhai, Walter Talbott, Nitish Srivastava, Chen Huang, Hanlin Goh, Ruixiang Zhang, and Josh Susskind. An attention free transformer. arXiv preprint arXiv:2105.14103, 2021.

[98] Chen Zhu, Wei Ping, Chaowei Xiao, Mohammad Shoeybi, Tom Goldstein, Anima Anandkumar, and Bryan Catanzaro. Long-short transformer: Efficient transformers for language and vision. Advances in Neural Information Processing Systems, 34, 2021.

## Checklist

1. For all authors...

(a) Do the main claims made in the abstract and introduction accurately reflect the paper’s contributions and scope? [Yes]

(b) Did you describe the limitations of your work? [Yes] See Section 5

(c) Did you discuss any potential negative societal impacts of your work? [Yes] See Section 5

(d) Have you read the ethics review guidelines and ensured that your paper conforms to them? [Yes]

2. If you are including theoretical results...

(a) Did you state the full set of assumptions of all theoretical results? [Yes] See Section 3.2

(b) Did you include complete proofs of all theoretical results? [Yes] See Appendix C

3. If you ran experiments...

(a) Did you include the code, data, and instructions needed to reproduce the main experimental results (either in the supplemental material or as a URL)? [Yes] See Appendix E

(b) Did you specify all the training details (e.g., data splits, hyperparameters, how they were chosen)? [Yes] See Appendix E

(c) Did you report error bars (e.g., with respect to the random seed after running experiments multiple times)? [Yes] See Section 4

(d) Did you include the total amount of compute and the type of resources used (e.g., type of GPUs, internal cluster, or cloud provider)? [Yes] See Appendix E

4. If you are using existing assets (e.g., code, data, models) or curating/releasing new assets...

(a) If your work uses existing assets, did you cite the creators? [Yes] See Section 4 and Appendix E

(b) Did you mention the license of the assets? [Yes] See Appendix E

(c) Did you include any new assets either in the supplemental material or as a URL? [No]

(d) Did you discuss whether and how consent was obtained from people whose data you’re using/curating? [N/A]

(e) Did you discuss whether the data you are using/curating contains personally identifiable information or offensive content? [N/A]

5. If you used crowdsourcing or conducted research with human subjects...

(a) Did you include the full text of instructions given to participants and screenshots, if applicable? [N/A]

(b) Did you describe any potential participant risks, with links to Institutional Review Board (IRB) approvals, if applicable? [N/A]

(c) Did you include the estimated hourly wage paid to participants and the total amount spent on participant compensation? [N/A]