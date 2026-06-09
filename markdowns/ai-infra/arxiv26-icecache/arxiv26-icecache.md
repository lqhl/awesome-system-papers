# ICECACHE: MEMORY-EFFICIENT KV-CACHE MANAGE-MENT FOR LONG-SEQUENCE LLMS

Yuzhen Mao   
Simon Fraser University, BC, Canada   
yuzhenm@sfu.ca   
Martin Ester   
Simon Fraser University, BC, Canada   
ester@sfu.ca

Qitong Wang Harvard University, Cambridge, USA qitong@seas.harvard.edu

Ke Li   
Simon Fraser University, BC, Canada   
keli@sfu.ca

## ABSTRACT

Key-Value (KV) cache plays a crucial role in accelerating inference in large language models (LLMs) by storing intermediate attention states and avoiding redundant computation during autoregressive generation. However, its memory footprint scales linearly with sequence length, often leading to severe memory bottlenecks on resource-constrained hardware. Prior work has explored offloading KV-cache to the CPU while retaining only a subset on the GPU, but these approaches often rely on imprecise token selection and suffer performance degradation in longgeneration tasks such as chain-of-thought reasoning. In this paper, we propose a novel KV-cache management strategy, IceCache, which integrates semantic token clustering with PagedAttention. By organizing semantically related tokens into contiguous memory regions managed by a hierarchical, dynamically updatable data structure, our method enables more efficient token selection and better utilization of memory bandwidth during CPU–GPU transfers. Experimental results on Long-Bench show that, with a 256-token budget, IceCache maintains 99% of the original accuracy achieved by the full KV-cache model. Moreover, compared to other offloading-based methods, IceCache attains competitive or even superior latency and accuracy while using only 25% of the KV-cache token budget, demonstrating its effectiveness in long-sequence scenarios. The code is available on our project website at https://yuzhenmao.github.io/IceCache/.

## 1 INTRODUCTION

Key-Value (KV) cache is a critical component in modern large language models (LLMs), which stores the intermediate attention outputs for each token, allowing the model to reuse these computations in subsequent forward passes. This mechanism is particularly important for autoregressive generation, where tokens are produced sequentially. However, a fundamental challenge of KV-cache lies in its memory consumption: as the generated sequence length increases, the cache size grows linearly, often leading to severe memory pressure or out-of-memory errors on devices with limited resources.

Recent studies (Zhang et al., 2024b; Tang et al., 2024; Xiao et al., 2023) have shown that, despite the growing size of the KV-cache, only a small subset of tokens contributes disproportionately to generation accuracy. Building on this insight, subsequent work (Chen et al., 2024a; Lee et al., 2024; Chen et al., 2024b) offloads the KV-cache to the CPU while dynamically retaining only the most important entries on the GPU. However, many existing approaches lack precise mechanisms for identifying truly relevant tokens, resulting in low hit rates for the most relevant cache entries. In addition, they often

![](images/3963086f41f067c9d04e3d12c6ec9454ce4a085ef46b13901c42c696d5cfafc1.jpg)

![](images/06a67f13173c531191363c0c2bd0eb30ae03809c4b181420bca9593f42a2c1f9.jpg)  
Figure 1: IceCache has the best trade-off between CUDA memory footprint and time-per-outputtoken (TPOT) on A100 at a 36k sequence length. Baselines are chosen to represent high-accuracy (Left) and memory-efficient (Right) methods.

lack effective update mechanisms to manage the KV-cache pool as new tokens are generated during decoding. Therefore, in scenarios involving long-generation tasks, such as long-context summarization, multi-step reasoning, and chain-of-thought (CoT) generation, previous methods experience significant performance degradation (Li et al., 2024a).

To improve the identification of relevant KV-cache entries, we propose an innovative approach, IceCache, which integrates semantic token clustering with PagedAttention (Kwon et al., 2023), a widely adopted memory management technique that stores KV-cache entries in non-contiguous pages. As illustrated in Figure 2, by grouping semantically related tokens into the same memory pages, our method increases the likelihood that relevant tokens are co-located, thereby improving page selection hit rates and enhancing memory bandwidth utilization during CPU–GPU transfers. Furthermore, IceCache employs a hierarchical data structure that can be efficiently updated during decoding, mitigating the performance degradation commonly observed in long-generation tasks. As a result, IceCache enables more effective and adaptive KV-cache management – it achieves superior latency and accuracy compared to state-of-the-art baselines under the same KV-cache budget, and still attains comparable accuracy while using substantially smaller budgets.

![](images/20b12aaf62e3fe0483050099f9b4fe91e5cd2b12c8a6ff539c0c65c93de37f2a.jpg)  
Figure 2: Illustration of IceCache. (1) During the prefill stage, tokens are indexed into a hierarchical data structure (the DCI-tree) according to their semantic similarity in the transformed key-embedding space. Each leaf node of the DCI-tree corresponds to a physical memory page. (2) During the decoding stage, given a query q, IceCache performs a tree search to identify the top-k tokens most relevant to q. The zoomed-in section at the bottom illustrates that these relevant tokens (highlighted in yellow) tend to be clustered within the same leaf nodes and are stored together in corresponding memory pages. (3) After the query-aware retrieval, the pages containing the relevant tokens are selected, and all tokens within these pages are used in the subsequent sparse attention with q.

In summary, IceCache makes the following contributions:

• We propose a KV-cache offloading strategy that substantially improves retrieval hit rates by grouping semantically similar tokens into the same memory pages.

• We develop a multi-level DCI algorithm that supports efficient indexing, fast retrieval, and dynamic updates, enabling effective maintenance of the KV-cache data structure.

• We design a pipelining scheme that overlaps CPU and GPU computations, effectively hiding the latency associated with indexing and retrieval.

We evaluated IceCache under constrained GPU memory budgets on the Passkey Retrieval (Mohtashami & Jaggi, 2023), LongBench (Bai et al., 2023), and GSM8K Chain-of-Thought (CoT) reasoning (Wei et al., 2022) using four popular open-source LLMs: Llama3.1-8B-Instruct, Mistral-7B-Instruct-v0.2, LongChat-7B-v1.5 and Qwen3-32B. Across diverse tasks, including open-domain QA, multi-hop reasoning, academic reading comprehension, long-context summarization and longcontext generation, IceCache consistently outperformed six state-of-the-art KV-cache baselines.

Notably, IceCache sustained near-oracle performance on most tasks using only a small fraction (as small as 64 tokens) of the original KV-cache size. Furthermore, by leveraging its hierarchical and dynamically updatable data structure, IceCache effectively mitigates performance degradation in long-generation tasks. As shown in Figure 1, the empirical results demonstrate that IceCache establishes a new state-of-the-art in accuracy–efficiency trade-offs, achieving superior accuracy while significantly reducing CUDA memory usage and decoding latency compared to all existing baselines.

## 2 RELATED WORK

## 2.1 KV-CACHE MANAGEMENT VIA EVICTION AND OFFLOADING

Existing approaches to KV-cache management generally fall into two categories: eviction-based methods and offloading-based methods. Eviction-based methods are typically faster, as they avoid data transfer between the GPU and the CPU. However, they often rely on static selection strategies and fail to adapt to changing contexts. In contrast, offloading-based methods aim to preserve important KV-cache entries more accurately by dynamically transferring data between GPU and CPU, but introduce additional latency.

Eviction-based approaches include H2O (Zhang et al., 2024b), which retains only a subset of tokens selected based on attention scores; StreamingLLM (Xiao et al., 2023), which preserves sink tokens and recent tokens to approximate attention; and SnapKV (Li et al., 2024b), which selects key embeddings from the tail of the prompt to guide subsequent decoding. While efficient, these methods may struggle to maintain accuracy in long-generation scenarios due to their limited flexibility in adapting to evolving contexts. Offloading-based methods dynamically manage KV-cache storage across devices. MagicPiG (Chen et al., 2024b) uses sampling techniques based on Locality Sensitive Hashing (LSH) to approximate attention. OmniKV (Hao et al., 2025) improves efficiency by reusing important tokens across consecutive layers. PQCache (Zhang et al., 2024a) applies product quantization to compress the KV-cache and approximate attention computation. Although these approaches better preserve critical information, they incur additional communication costs from GPU–CPU transfers.

## 2.2 PAGED KV-CACHE MANAGEMENT

PagedAttention (Kwon et al., 2023) is an innovative memory management technique designed to optimize the KV-cache of LLMs. It addresses the challenges by introducing a paging mechanism similar to virtual memory systems in operating systems. This approach divides the KV-cache into fixed-size pages, allowing for more efficient memory allocation and management. By doing so, PagedAttention improves GPU memory utilization by reducing fragmentation and enabling longer context windows without sacrificing performance. However, unlike the methods discussed in the previous subsection, PagedAttention does not address the fundamental issue that the KV-cache continuously grows during decoding.

Quest (Tang et al., 2024) and ArkVale (Chen et al., 2024a) are two query-aware criticality estimation algorithms built on PagedAttention. They effectively identify relevant KV-cache tokens and perform self-attention selectively on the chosen tokens. For each page, Quest and ArkVale calculate an upper bound using the feature values of the Key vector for each page’s criticality estimation. Given all criticality scores of the pages, Top-k pages are chosen to perform approximate self-attention, where k is a preset constant (e.g. 128, 256). Additionally, ArkVale integrates the GPU-CPU offloading into the system to further save GPU memory. However, a key limitation of both Quest and ArkVale is that they construct memory pages according to the original token order. As a result, tokens that are semantically relevant to a given query may be scattered across multiple pages. In contrast, IceCache performs semantic clustering during indexing, grouping similar tokens into the same pages. This organization increases the likelihood that relevant tokens are co-located, improving retrieval hit rates and reducing unnecessary memory transfers.

## 3 BACKGROUND

## 3.1 ATTENTION MECHANISM AND SPARSE ATTENTION

Mathematically, the attention operation takes three matrices as input, K ∈ Rm×d, Q ∈ Rn×d, V ∈ Rm×d′ , which denote keys, queries and values, respectively. Optionally, it may also take in a mask as input, S ∈ Rn×m, whose entries are either 0 or 1. The ith rows of K, Q and V, denoted as ki, qi and vi, represent the ith key, query, and value, respectively. The entry of S in the ith row and jth column, denoted as si,j, represents whether the ith query is allowed to attend to the jth key — if it is 1, it would be allowed; if it is 0, it would not be. A common masking scheme is the causal mask, where si,j is 1 if i ≥ j and 0 otherwise. Keys and queries have the same dimension d, and each key is associated with a value, and so the number of keys and values is the same and denoted as m. The attention operation computes the attention weight matrix A ∈ Rn×m. Its entry in the ith row and jth column, denoted as ai,j, is computed with the following formula:

$$
\tag{1}
$$

The attention matrix A is typically sparse (Nikita et al., 2020; Gupta et al., 2021), i.e., in each row of A, only a few attention weights have significant (large) values, while the majority of the remaining values are close to zero. If we can somehow identify the k unmasked keys that receive the highest attention weights for each query qi without computing the attention weights for all keys, the original attention matrix A can be approximated by only computing the inner product for the identified keys, which can save a significant amount of computational resources.

## 3.2 LLM INFERENCE

The inference process of LLMs primarily comprises two key stages: the prefill (or prompt) stage and the decoding (or generation) stage. In the prefill stage, the model takes an input prompt sequence of length sin and processes it through all layers of the LLM. During this process, the keys and values for each token in the sequence are computed and stored as part of the KV-cache. The decoding stage begins once the prompt has been processed. Here, the model generates output tokens one step at a time, using and updating the KV-cache iteratively. For each decoding step, the current token’s computation depends on the stored keys and values from previous tokens, allowing the model to maintain context over the sequence. The KV-cache thus plays a crucial role in enabling efficient autoregressive generation by reducing redundant computations and maintaining information about past tokens.

## 3.3 MULTI-LEVEL DCI

Prioritized Dynamic Continuous Indexing (P-DCI). Li & Malik (2016) proposed an exact, randomized algorithm designed to perform efficient k-nearest neighbour (k-NN) searches in high-dimensional spaces. Unlike traditional methods, DCI avoids space partitioning, which scales poorly to high dimensions. It does so by constructing multiple indices, each of which allows for points to be efficiently ranked by a lower bound on the distances between them and the query. The lower bound is formed by projecting the distances along a random vector associated with each index. P-DCI (Li & Malik, 2017) aggregates over the lower bounds given by each index to produce a tighter lower bound and uses a priority queue to order points so that points with smaller lower bounds are processed earlier than points with larger lower bounds. This approach significantly reduces the number of distance evaluations and memory usage compared to methods like Locality-Sensitive Hashing (LSH). Mao et al. (2024) first introduced P-DCI into sparse attention mechanisms to accelerate LLM inference.

Multi-level Dynamic Continuous Indexing (M-DCI). In this work, we extend P-DCI by introducing a hierarchical data structure to further enhance search efficiency. The index is organized into multiple levels, each containing a subset of data points. Points are randomly promoted to higher levels, forming a hierarchical data structure. Each point at a lower level is assigned a parent in the next higher level, typically the nearest neighbour among the promoted points. This creates "nodes" or clusters of points sharing the same parent. When querying, the algorithm starts at the top level, using P-DCI to find the k-closest points to the query. It then recursively searches within the nodes associated with these points at the next lower level, continuing this process down the hierarchy. This multi-level approach allows M-DCI to focus computational resources on the most promising regions of the index, effectively narrowing down the search space and improving query times, especially in datasets with high intrinsic dimensionality.

## 4 ICECACHE

We propose an innovative approach, named IceCache, that integrates token clustering with KV-cache storage. Our method consists of three steps: (1) indexing; (2) page selection; and (3) bulk loading. The indexing step occurs either during the prompt processing phase—when IceCache constructs a hierarchical data structure, referred to as the DCI-tree, for the prompt key embeddings; or when new window pages are offloaded to the CPU. In this step, similar tokens are grouped into units called nodes, rather than being stored sequentially in virtual memory pages as in PagedAttention. Here, a node denotes a group of data points that share the same parent in the tree hierarchy. The next two steps take place during the token generation (decoding) phase. In the page selection step, IceCache employs a fast Approximate Nearest Neighbor (ANN) search algorithm, M-DCI, to independently select the top-k most relevant pages for each attention head. Finally, in the bulk loading step, the selected pages are efficiently transferred from the CPU back to the GPU. IceCache also overlaps the indexing (a CPU-intensive operation) with ongoing GPU computations to further reduce the latency.

We provide further details on each of these three steps in the following subsections and illustrate the method in Fig 3.

![](images/285504cbadd9e4f4957eb6c5c45cf812434a799ac63965214ca7a3751f01c59a.jpg)  
Figure 3: Illustration of DCI-tree and IceCache: The hierarchical data structure on the left visualizes the result of indexing key embeddings, DCI-tree, where each tree node stores metadata for the tokens, such as the key ID and node index. The tables on the right depict the mapping between nodes in the DCI-tree and the corresponding pages in physical memory. For each selected node, a mapping table is used to locate the memory region containing the associated key-value embeddings.

## 4.1 INDEXING: CLUSTERING KEY EMBEDDINGS INTO A HIERARCHICAL TREE

During decoding, the dominant bottleneck is often not the computation but memory bandwidth. As the KV-cache grows with sequence length, each decoding step requires repeatedly loading large amounts of KV embeddings from GPU memory. This leads to memory-bandwidth saturation, significantly degrading latency scalability. PagedAttention (Kwon et al., 2023) mitigates this issue by introducing a virtual memory abstraction for the KV-cache. Instead of storing the KV-cache as a single contiguous tensor, it organizes KVs into fixed-size memory pages and maintains a page table to map logical token positions to physical memory locations. Within each page, consecutive tokens are stored contiguously, reducing fragmentation. This paging mechanism enables more flexible memory allocation and more efficient KV-cache management during decoding.

Building on this design, subsequent KV-cache optimization methods such as Quest (Tang et al., 2024) and ArkVale (Chen et al., 2024a) leverage PagedAttention’s paging abstraction while incorporating query-aware page selection. These approaches estimate the importance of each page during decoding and utilize only the top-k pages to approximate attention more efficiently.

However, since pages are constructed based on the original token order, tokens relevant to a given query are often distributed across multiple pages. Therefore, retrieving them requires loading entire pages that may contain many irrelevant tokens, leading to unnecessary memory overhead and reduced selection precision. In contrast, IceCache organizes KV-cache entries based on semantic similarity, concentrating relevant tokens within fewer pages. This design improves retrieval efficiency and achieves superior performance while reducing the number of pages accessed.

Specifically, IceCache organizes key-value embeddings into memory pages through a fundamentally different indexing strategy: instead of relying on the token’s original order, IceCache constructs a separate hierarchical tree data structure for each attention head, called a DCI-tree, which clusters tokens based on the semantic similarity of their key embeddings. Each node in the DCI-tree represents a small group of semantically related tokens that share a common parent, effectively forming a localized cluster. From a memory system perspective, IceCache maps each node directly to a memory page, thereby preserving semantic locality in storage and enabling efficient access during decoding. By clustering semantically similar tokens into the same nodes/pages, IceCache enables more targeted and efficient retrieval during decoding.

Moreover, the DCI-tree data structure used by IceCache is designed for efficient incremental updates. As new windows of tokens (e.g., from a sliding window in long-context scenarios) are offloaded to the CPU, each token is inserted into the appropriate node in the DCI-tree based on its key embedding. When a node exceeds the maximum page size, new pages are dynamically allocated to maintain balance. This adaptive tree maintenance ensures that the index remains both semantically meaningful and efficient, making IceCache particularly effective for long-sequence generation.

In summary, while prior methods treat KV-cache page layout as a static memory allocation problem, IceCache introduces a dynamic, semantically-aware data structure that preserves key similarity across time. This enables more focused page retrieval, reduces memory fragmentation, and supports more efficient decoding. Furthermore, by performing indexing during the prompt or CPU offloading phase, IceCache amortizes the tree construction cost and avoids incurring additional latency during inference.

## 4.2 INDEXING DETAILS

For each attention head, given a set of pre-computed key embeddings, IceCache first indexes them using a hierarchical tree structure which is obtained by a novel approach called Multi-level DCI (M-DCI). It works by constructing a dynamic index called DCI-tree and applies Prioritized DCI (P-DCI) (Li & Malik, 2017) to each level of the tree recursively (more details are in Section 3.3). The data points processed in M-DCI are transformed key embeddings and query embeddings using the following transformation formulas, which we denote as TK : Rd → Rd+1 and TQ : Rd → Rd+1:

$$
\tag{2}
$$

$$
\tag{3}
$$

where c ≥ maxj′ ∥kj′∥2 is at least the maximum norm across all keys. We use the Euclidean distance as the distance function.

At the very beginning of the indexing, all data points are initially placed at the bottom level of the DCI-tree. Subsequently, some points are randomly selected to be promoted to the next higher level based on a promotion ratio r < 1. The ratio r is predefined during DCI-tree initialization and remains fixed throughout the process. After the indexing, we can get the total number of levels in the DCI-tree, denoted as L. The details are presented in Algorithm 2.

Specifically, let nℓ denote the number of data points at level ℓ, with level indices starting from the bottom (i.e., the lowest level is ℓ = 1). Ideally, the number of points satisfies the recurrence relation nℓ = r · nℓ−1. In other words, the distribution over level indices follows a geometric distribution. The probability that a point is assigned to the highest level (ℓ = L) is rL−1, while the probability of being assigned to level ℓ (for 1 ≤ ℓ ≤ L − 1) is rℓ−1 − rℓ.

After level assignment, each data point at level ℓ is linked to a parent at level ℓ + 1, defined as the closest point in terms of key embedding distance. This parent assignment is formulated as a 1-nearest neighbor search and is efficiently solved using M-DCI query.

In the decoding stage, when a new token is generated, its key embedding is inserted into the appropriate position in the DCI-tree. A level ℓ is first assigned to the new key according to the same random promotion process. Then, its parent at level ℓ + 1 is determined, and the key is added to the physical memory page corresponding to the node into which it is inserted.

## 4.3 PAGE SELECTION: HEAD-SPECIFIC ANN SEARCH WITH FINE-GRAINED RETRIEVAL

During the decoding phase, given a query embedding, IceCache performs head-specific page selection to identify the most relevant pages for each attention head. Leveraging the hierarchical DCI-tree constructed during indexing, we apply the fast approximate nearest neighbor (ANN) search algorithm described in Section 3.3, M-DCI, to retrieve the top-k pages that are important to the current query for each head independently. For group-query attention (GQA), where multiple query heads share the same set of key embeddings, we compute the union of the selected pages across queries within the same group and share the resulting pages among them, following Yuan et al. (2025).

## 4.4 PAGE SELECTION DETAILS

As aforementioned, IceCache aims to accelerate self-attention by loading only a limited number of pages into GPU memory for computation. Therefore, the objective of page selection is to maximize the recall (or hit rate) of significant keys for a given query. By clustering semantically similar tokens into the same nodes/pages, IceCache enables more targeted and efficient retrieval during decoding. In contrast, methods like Quest (Tang et al., 2024), Arkvale (Chen et al., 2024a), or PQCache (Zhang et al., 2024a) construct pages based on the original token order, which often causes tokens relevant to a given query to be scattered across multiple pages. Retrieving them requires loading entire pages filled with many irrelevant tokens, resulting in unnecessary memory overhead. IceCache mitigates this inefficiency by grouping similar tokens, so relevant tokens tend to be concentrated within fewer pages. As a result, the hit rate of significant keys during decoding increases. The detailed procedure is shown in Algorithms 3 and 4.

Specifically, when computing the attention matrix, given a query vector qi, we follow the query process described in Section 3.3 to identify the top-k keys that are most likely to yield the highest dot-product values with qi. Once these top-k keys are identified, we load only the pages that contain them. Suppose p pages are loaded, and each page contains d entries, since not all the pages are fully filled, the number of loaded keys N is bounded as: N ≤ pd.

The approximate attention scores between the query q and these N selected keys are then computed using Equation 1. The masks si,j are set to 1 for the selected keys and 0 for all others. Note that, IceCache constructs a separate DCI-tree for each attention head, allowing it to retrieve different sets of significant pages per head. This head-specific, fine-grained selection mechanism distinguishes IceCache from baselines such as Quest and ArkVale, which retrieve the same set of pages for all heads, potentially limiting their retrieval accuracy.

## 4.5 BULK LOADING AND PIPELINING

In this section, we present how we optimize the efficiency of the IceCache workflow, using bulk loading and pipelining. Our key observation is that the selected pages are not contiguous in either main memory or GPU memory. As a result, individual transfer of these pages between main memory and GPU memory is highly inefficient. To overcome this issue, we designed bulk loading algorithms to efficiently offload and backload the selected pages, using two CPU and GPU backload buffers. In addition, we carefully designed an efficient pipeline of prefilling calculations, KV-cache offloading, and DCI indexing, for efficient prefilling. We illustrate our bulk back-loading workflow in Figure 4.

![](images/d508330f91f69e3ca29ee403d73d2ad086fb3eb6b596e894d9b5492a3b411e62.jpg)  
Figure 4: After IceCache selects important KVpages, it aggregates all selected pages into a contiguous CPU preloading buffer. This buffer is then transferred via high-throughput PCIe transaction to a pre-allocated GPU buffer. Finally, the transferred blocks are scattered into their exact locations in the KV-Cache table. This bulk transfer avoids many small copying operations over PCIe and significantly improves utilization.

![](images/8eac19987794aaab966de0ae035a61993a69a276e7bd1c77e658561e3cbbd43a.jpg)  
Figure 5: (a) Baseline serial workflow, where prefilling, offloading (OL), and indexing are executed strictly in sequence. (b) IceCache pipelining, where GPU prefilling overlaps with KVoffloading via PCIe and CPU-side DCI indexing. Once KVs of layer i (Li) arrive in CPU memory, Li-DCI-tree indexing progresses in parallel with GPU prefilling and offloading of the subsequent layer (Li+1). This results in significantly reduced end-to-end prefilling latency.

Offloading follows a similar procedure, except that the steps are executed in reverse. After identifying the most relevant pages (indicated by color), we filter out those already resident in GPU memory from previous token generations. The remaining pages are then aggregated into a pre-allocated CPUmemory buffer, enabling a single high-throughput PCIe transfer into a pre-allocated GPU-memory buffer. Once the pages arrive in the GPU, we perform a scatter operation to load them into the appropriate slots of the KV-Cache table.

Figure 5(b) illustrates the pipelining of IceCache prefilling (other minor stages are omitted for clarity). After the KV embeddings are generated on the GPU, we simultaneously launch the prefilling calculation and the offloading transfer. The DCI index construction starts building the index along with the prefilling calculation, right after the KV states fully arrive in the main memory. This approach allows the offloading and indexing latencies to be largely hidden by the main prefilling computation. Furthermore, IceCache can be easily extended with page reuse techniques (Liu et al., 2023; Hao et al., 2025) to further accelerate prefilling.

## 5 EXPERIMENTS

## 5.1 SETTINGS

To comprehensively evaluate IceCache, we conduct experiments across models of varying scales and attention architectures. We first apply IceCache to Llama-3.1-8B-Instruct and Mistral-7B-Instructv0.2, two widely adopted open-source LLMs employing group-query attention (GQA) (Ainslie et al., 2023). To further assess scalability and architectural generality, we extend our evaluation to Qwen3-32B, a larger-scale model, and LongChat-7B-v1.5, which employs standard multi-head attention (Vaswani et al., 2017) rather than group-query attention. Our evaluation proceeds in four stages. We first measure recall in retrieving important tokens (Mohtashami & Jaggi, 2023). To evaluate the performance of IceCache on long generation tasks, we further conduct experiments on LongBench (Bai et al., 2023), which contains long generation tasks such as summarization and code generation, and GSM8K (Cobbe et al., 2021), which requires chain-of-thought reasoning. Finally, we examine its scalability on RULER (Hsieh et al., 2024) under extremely long-context settings.

Our experimental platform comprises an NVIDIA A100 40GB PCIe GPU (for small models) or an NVIDIA H100 80GB PCIe GPU (for large models). For all experiments, we fix the number of CPU threads to 64. The software stack includes CUDA version 12.2, PyTorch version 2.4.1, and HuggingFace Transformers version 4.57.1. We implement IceCache on top of HuggingFace Transformers, utilizing FlashInfer (Ye et al., 2025) for the attention kernel operation. As prior research indicates (Tang et al., 2024), the initial layers of the model exhibit relatively low sparsity. Therefore, neither IceCache nor baseline methods are applied to the first two layers of the models.

## 5.2 PASSKEY RETRIEVAL ACCURACY

We first evaluate IceCache’s effectiveness in handling long-range dependencies using the passkey retrieval task. We consider context lengths from 10k words to 100k words, and test with the size of cache budget = {256, 128, 64}. For each length, 100 test cases are generated with passkeys inserted at various positions from 0% to 95% of the total context length in increments of 5%. The results are illustrated in Fig. 6. As shown in the figure, IceCache dynamically assesses the importance of evicted pages and recall crucial ones on demand, consistently maintaining 100% retrieval accuracy across all tested budget sizes.

## 5.3 LONGBENCH EVALUATION

To assess the performance of our method in long-context scenarios, we conduct a comprehensive evaluation on the LongBench benchmark (Bai et al., 2023). LongBench is designed to evaluate how well LLMs understand and reason over long-context inputs across diverse real-world tasks. We compare IceCache (ICE) against six state-of-the-art KV cache optimization methods, including MagicPig (MPG) (Chen et al., 2024b), ArkVale (AKV) Chen et al. (2024a), SnapKV (SKV) Li et al. (2024b), StreamingLLM (SLM) Tang et al. (2024), OmniKV (OKV) Hao et al. (2025) and PQCache (PQC) Zhang et al. (2024a) as baselines. We also include the results of full KV-cache (FULL) and ground-truth top-k KV-cache (TOP-k) as baselines. Notably, OmniKV offloads only a subset of layers while keeping all remaining layers fully resident on the GPU, resulting in substantially higher memory usage than other methods. The detailed results are presented in Table 1.

## 5.3.1 ACCURACY ANALYSIS

Accuracy on Llama-3.1-8B-Instruct. On Llama-3.1-8B, the effectiveness of IceCache is particularly pronounced. Most impressively, with a highly constrained KV-Cache budget of just 64, our method achieves an average accuracy of 47.8. This result alone surpasses the strongest baseline,

![](images/38b1d813638b186e1e859e799090fadff3f8d031429e220903019e5f952d654c.jpg)  
(a) Cache Budget = 256

![](images/f57381c6c4b8115c6ed0b26f5cd9efe235d0ffadef97b471546624985bb685f0.jpg)  
(b) Cache Budget = 128

![](images/4e35ddb4de399fb1beb8437057a7a83f1186a85a45e66dd439e59a9f2a486403.jpg)  
(c) Cache Budget = 64  
Figure 6: Passkey retrieval accuracy of IceCache on Llama3.1-8B-Instruct. The horizontal axis indicates the relative insertion position (%) of the passkey, while the vertical axis represents the context length in words. Results are presented for cache budgets of 256, 128, and 64. Notably, IceCache achieves 100% retrieval accuracy across all tested budget sizes.

Table 1: Accuracy comparison of our method (ICE) with SnapKV (SKV), SteamingLLM (SLM), OmniKV (OKV), MagicPig (MPG), PQCache (PQC), ArkVale (AKV), Full KV (FULL) and groundtruth top-k (TOP-k) on LongBench for Llama-3.1-8B-Instruct and Mistral-7B-Instruct. IceCache generally outperforms other methods across various KV-cache budgets and LLMs.  
![](images/888ec25451b94b6d669e34ecd26b065d9159ff31910ca6d6e5fff2d38fbe6f70.jpg)

PQCache, which scores 47.3 while operating with a 4× larger budget of 256. This highlights the exceptional efficiency of our approach in low-resource environments. As we increase the budget for IceCache to 256, its performance climbs to an average score of 49.0. This not only represents a substantial 1.7 point improvement over PQCache but also closes the performance gap to the unconstrained Full KV-Cache (49.5) to a mere 0.5 points. Notably, our performance is remarkably close to the ground-truth Top-k, demonstrating a near-optimal cache management strategy across a diverse set of tasks.

Accuracy on Mistral-7B-Instruct. This strong performance trend is consistent on the Mistral-7B model, confirming the robustness of our method. With a budget of 256, IceCache achieves an average accuracy of 41.7, establishing a significant 2.6 point lead over the best-performing baseline, MagicPig (39.1). Again, the low-budget capability of IceCache stands out; with a budget of 64, IceCache scores 39.0, remaining highly competitive with the top baseline (MagicPig, scores 39.1) that uses four times the cache size (256).

Accuracy on two additional LLMs. To further validate IceCache on larger-scale models and standard multi-head attention architectures, we evaluate it on LongBench using two additional models: Qwen3-32B and LongChat-7B-v1.5. As shown in Tables 2, for Qwen3-32B, IceCache with a small budget of 64 achieves an average accuracy of 42.2 on LongBench, retaining 97.2% of the full KV-cache performance (43.4). This score rises to 99.3% with a budget of 256, nearly matching the vanilla model. Similarly, on LongChat-7B-v1.5, our method preserves 96.3% of the full KV-cache performance with a budget of 64, and achieves up to 99.4% at a budget of 256. These results provide strong evidence that IceCache is effective across different model scales and attention mechanisms.

Table 2: Accuracy comparison of our method (ICE) with Full KV (FULL) on LongBench for Qwen3- 32B and LongChat-7B-v1.5.  
![](images/c691646dab4b28144b354784b46a37bbf27d2764760bcc3d36ebd5704b5a769e.jpg)

## 5.3.2 LATENCY ANALYSIS

Since most baselines, including IceCache, use the entire KV-cache to generate the first token, we follow PQCache (Zhang et al., 2024a) and report the Time to the second token (TT2T) in Fig. 7a, for a 36k sequence length with Llama-3.1-8B-Instruct and all the methods compared in Table 1, except MagicPig, which is restricted to costly AVX-512 CPUs. Additionally, we present results for IceCache incorporating the critical-page-reuse technique (reusing the same selected KV-page indices across layers), a method also used in OmniKV, which serves as an approximate version that trades accuracy for increased speed.

![](images/a25138b6cc9f215bb15eca5c0fb579422b3d9d7531ff1889118af25630339575.jpg)  
(a) Time to the second token.

![](images/a92754c3ab5dc74e6dac3c53cecb146dfb681325427fe6bb720c2334c0003e02.jpg)  
(b) Time per output token.

![](images/3de6952ba5b5758877999dc428bf06b379097cf6d64d542375f74f9c7a0be61c.jpg)  
(c) TPOT Latency breakdown.  
Figure 7: Latency comparison of IceCache and baseline methods on a 36k-token sequence.

As illustrated in the figure, our method, IceCache, achieves competitive latency among retrieval-based algorithms, recording 7.7 seconds. IceCache (reuse) further reduces this to 5.9 seconds, matching OmniKV (5.8 s) and outperforming other retrieval-based baselines such as Arkvale (7.4 s) and PQCache (13.3 s). Although eviction-based methods like SnapKV (0.55 s) and StreamingLLM (0.13 s) are much faster, their speed often comes at the cost of accuracy. Overall, IceCache and IceCache(reuse) offer a strong balance between efficiency and accuracy, with the reuse variant showing how our approach can further optimize latency without significantly sacrificing performance. We include more details of IceCache(reuse) in the appendix B.

Similarly, for decoding latency, Fig. 7b shows the average time per generated token, along with the corresponding accuracy percentage relative to the full KV-cache model, for an input sequence length of 36k. Eviction-based methods, StreamingLLM and SnapKV (both at 0.03 seconds per token), continue to show the fastest speeds due to their minimal overhead. Among the more accurate retrievalbased methods, IceCache(reuse) achieves a highly competitive decoding time of 0.06 seconds per token – substantially faster than PQCache (0.13 s) and nearly matching the speed of OmniKV (0.05 s). Vanilla IceCache maintains a strong balance, combining superior accuracy with efficient decoding.

It achieves the highest accuracy percentage (99.0%) while still outperforming PQCache in speed.   
These results further demonstrate that IceCache effectively balances accuracy and decoding latency.

Figure 7c presents a detailed breakdown of TPOT latency for IceCache at a sequence length of 36k, with a total latency of 0.11 seconds. In this figure, “Loading”, “Query”, and “Decoding” correspond to the overhead from CPU–GPU communication, DCI-query operations, and the overall LLM decoding process, respectively. The largest contributors to latency are the DCI-query module (0.05 s) and decoding (0.04 s), while GPU–CPU offloading and other miscellaneous operations add only 0.015 seconds and 0.005 seconds, respectively.

## 5.4 GSM8K COT REASONING

We also evaluate IceCache on the GSM8K benchmark using Chainof-Thought prompting, applying a 10% budget for all compared methods using Mistral-7B-Instruct-v0.2. As shown in Table 3, Ice-Cache demonstrates superior performance, achieving an accuracy of 47.4%, significantly higher than all other methods under the same budget constraint. In particular, it improves upon the strongest baseline, PQCache (46%), by 1.2% absolute points, reaching 47.4%. Moreover, our approach nearly matches the full KV-cache (48.2%), highlighting the effectiveness of IceCache.

Table 3: GSM8K CoT.  
![](images/0941e0f59130087ff858f764c949e2c4adcdd437e23a7a81f1aa2d68ac63277e.jpg)

## 5.5 SCALABILITY TO EXTREMELY LONG CONTEXT

To further evaluate the performance of IceCache under extremely long-context settings, we conduct experiments on the RULER benchmark and report accuracy on Single-Needle-in-a-Haystack (Single-NIAH), Multi-keys NIAH, and QA tasks with context lengths of 150k, 200k, and 250k tokens, using a token budget of 256. The experiments are conducted using Qwen3-4B-Instruct-2507 on a single H100 GPU with 64 CPU threads enabled. As shown in Table 4, IceCache and IceCache(r) consistently maintain accuracy comparable to Full-KV across all tasks and context lengths. Figure 8 further demonstrates that, as the input context grows, both IceCache and IceCache(r) exhibit a substantially slower increase in per-token decoding latency than Full-KV, whose decoding cost scales sharply with sequence length. These results indicate that IceCache achieves a better accuracy–latency trade-off for extremely long-context inference, enabling scalable decoding without sacrificing accuracy on the RULER benchmark.

![](images/dbca7a6e7f3fe0cef185361dc99c9e355aac564cbc2d350b2d4d48ab5d7c1bbf.jpg)  
Figure 8: Latency scaling across context lengths (150k, 200k, 250k and 300k).

Table 4: Accuracy comparison on Qwen3- 4B-Instruct under different context lengths (150k, 200k, 250k) on RULER benchmark.  
![](images/501e0afb59d3e333c9ed7dc8896915d539119c1ee8d83d0c7f7c22fa2c62ebe1.jpg)

## 6 CONCLUSION

This paper addresses the fundamental challenge of long-context inference in LLMs, where the rapidly growing KV-cache consumes substantial GPU memory and degrades computational efficiency. We first introduce the DCI-tree, a hierarchical indexing structure that integrates naturally with PagedAttention and supports dynamic updates for efficient KV-cache organization. Building on this foundation, we propose IceCache, a page-based KV-cache management framework that combines semantic token clustering with efficient GPU–CPU offloading. Across diverse long-context benchmarks, IceCache consistently achieves superior accuracy–latency trade-offs. These results establish IceCache as a scalable and practical solution for memory-efficient long-context LLM inference.

## 7 ACKNOWLEDGEMENTS

We thank the anonymous reviewers for their insightful feedback and constructive suggestions. This research was enabled in part by support provided by NSERC, the BC DRI Group and the Digital Research Alliance of Canada.

## REFERENCES

Joshua Ainslie, James Lee-Thorp, Michiel De Jong, Yury Zemlyanskiy, Federico Lebrón, and Sumit Sanghai. Gqa: Training generalized multi-query transformer models from multi-head checkpoints. arXiv preprint arXiv:2305.13245, 2023.

Yushi Bai, Xin Lv, Jiajie Zhang, Hongchang Lyu, Jiankai Tang, Zhidian Huang, Zhengxiao Du, Xiao Liu, Aohan Zeng, Lei Hou, et al. Longbench: A bilingual, multitask benchmark for long context understanding. arXiv preprint arXiv:2308.14508, 2023.

Renze Chen, Zhuofeng Wang, Beiquan Cao, Tong Wu, Size Zheng, Xiuhong Li, Xuechao Wei, Shengen Yan, Meng Li, and Yun Liang. Arkvale: Efficient generative llm inference with recallable key-value eviction. In The Thirty-eighth Annual Conference on Neural Information Processing Systems, 2024a.

Zhuoming Chen, Ranajoy Sadhukhan, Zihao Ye, Yang Zhou, Jianyu Zhang, Niklas Nolte, Yuandong Tian, Matthijs Douze, Leon Bottou, Zhihao Jia, et al. Magicpig: Lsh sampling for efficient llm generation. arXiv preprint arXiv:2410.16179, 2024b.

Karl Cobbe, Vineet Kosaraju, Mohammad Bavarian, Mark Chen, Heewoo Jun, Lukasz Kaiser, Matthias Plappert, Jerry Tworek, Jacob Hilton, Reiichiro Nakano, et al. Training verifiers to solve math word problems. arXiv preprint arXiv:2110.14168, 2021.

Ankit Gupta, Guy Dar, Shaya Goodman, David Ciprut, and Jonathan Berant. Memory-efficient transformers via top-k attention. arXiv preprint arXiv:2106.06899, 2021.

Jitai Hao, Yuke Zhu, Tian Wang, Jun Yu, Xin Xin, Bo Zheng, Zhaochun Ren, and Sheng Guo. Omnikv: Dynamic context selection for efficient long-context llms. In The Thirteenth International Conference on Learning Representations, 2025.

Cheng-Ping Hsieh, Simeng Sun, Samuel Kriman, Shantanu Acharya, Dima Rekesh, Fei Jia, Yang Zhang, and Boris Ginsburg. Ruler: What’s the real context size of your long-context language models? arXiv preprint arXiv:2404.06654, 2024.

Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph Gonzalez, Hao Zhang, and Ion Stoica. Efficient memory management for large language model serving with pagedattention. In Proceedings of the 29th Symposium on Operating Systems Principles, pp. 611–626, 2023.

Wonbeom Lee, Jungi Lee, Junghwan Seo, and Jaewoong Sim. {InfiniGen}: Efficient generative inference of large language models with dynamic {KV} cache management. In 18th USENIX Symposium on Operating Systems Design and Implementation (OSDI 24), pp. 155–172, 2024.

Ke Li and Jitendra Malik. Fast k-nearest neighbour search via dynamic continuous indexing. In International conference on machine learning, pp. 671–679. PMLR, 2016.

Ke Li and Jitendra Malik. Fast k-nearest neighbour search via prioritized dci. In International conference on machine learning, pp. 2081–2090. PMLR, 2017.

Yucheng Li, Huiqiang Jiang, Qianhui Wu, Xufang Luo, Surin Ahn, Chengruidong Zhang, Amir H Abdi, Dongsheng Li, Jianfeng Gao, Yuqing Yang, et al. Scbench: A kv cache-centric analysis of long-context methods. arXiv preprint arXiv:2412.10319, 2024a.

Yuhong Li, Yingbing Huang, Bowen Yang, Bharat Venkitesh, Acyr Locatelli, Hanchen Ye, Tianle Cai, Patrick Lewis, and Deming Chen. Snapkv: Llm knows what you are looking for before generation. arXiv preprint arXiv:2404.14469, 2024b.

Zichang Liu, Jue Wang, Tri Dao, Tianyi Zhou, Binhang Yuan, Zhao Song, Anshumali Shrivastava, Ce Zhang, Yuandong Tian, Christopher Re, et al. Deja vu: Contextual sparsity for efficient llms at inference time. In International Conference on Machine Learning, pp. 22137–22176. PMLR, 2023.

Yuzhen Mao, Martin Ester, and Ke Li. Iceformer: Accelerated inference with long-sequence transformers on CPUs. In The Twelfth International Conference on Learning Representations, 2024.

Amirkeivan Mohtashami and Martin Jaggi. Landmark attention: Random-access infinite context length for transformers. arXiv preprint arXiv:2305.16300, 2023.

Kitaev Nikita, Kaiser Lukasz, Levskaya Anselm, et al. Reformer: The efficient transformer. In Proceedings of International Conference on Learning Representations (ICLR), 2020.

Jiaming Tang, Yilong Zhao, Kan Zhu, Guangxuan Xiao, Baris Kasikci, and Song Han. Quest: Query-aware sparsity for efficient long-context llm inference. arXiv preprint arXiv:2406.10774, 2024.

Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N Gomez, Łukasz Kaiser, and Illia Polosukhin. Attention is all you need. Advances in neural information processing systems, 30, 2017.

Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Fei Xia, Ed Chi, Quoc V Le, Denny Zhou, et al. Chain-of-thought prompting elicits reasoning in large language models. Advances in neural information processing systems, 35:24824–24837, 2022.

Yuhao Wu, Ming Shan Hee, Zhiqing Hu, and Roy Ka-Wei Lee. Longgenbench: Benchmarking long-form generation in long context llms. arXiv preprint arXiv:2409.02076, 2024.

Guangxuan Xiao, Yuandong Tian, Beidi Chen, Song Han, and Mike Lewis. Efficient streaming language models with attention sinks. arXiv preprint arXiv:2309.17453, 2023.

Zihao Ye, Lequn Chen, Ruihang Lai, Wuwei Lin, Yineng Zhang, Stephanie Wang, Tianqi Chen, Baris Kasikci, Vinod Grover, Arvind Krishnamurthy, et al. Flashinfer: Efficient and customizable attention engine for llm inference serving. Proceedings of Machine Learning and Systems, 7, 2025.

Jingyang Yuan, Huazuo Gao, Damai Dai, Junyu Luo, Liang Zhao, Zhengyan Zhang, Zhenda Xie, Yuxing Wei, Lean Wang, Zhiping Xiao, et al. Native sparse attention: Hardware-aligned and natively trainable sparse attention. In Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), pp. 23078–23097, 2025.

Hailin Zhang, Xiaodong Ji, Yilin Chen, Fangcheng Fu, Xupeng Miao, Xiaonan Nie, Weipeng Chen, and Bin Cui. Pqcache: Product quantization-based kvcache for long context llm inference. arXiv preprint arXiv:2407.12820, 2024a.

Zhenyu Zhang, Ying Sheng, Tianyi Zhou, Tianlong Chen, Lianmin Zheng, Ruisi Cai, Zhao Song, Yuandong Tian, Christopher Ré, Clark Barrett, et al. H2o: Heavy-hitter oracle for efficient generative inference of large language models. Advances in Neural Information Processing Systems, 36, 2024b.

## A METHOD OVERVIEW

We separate all tokens into three groups: sink tokens, which are the tokens at the very beginning of the input sequence; window tokens, which are the most recent tokens; and all the remaining tokens in between. The pages that store sink tokens are referred to as sink pages, and those that store window tokens are referred to as window pages. We always keep all the sink and window pages in GPU.

We provide the pseudocode below for IceCache. It operates in two main phases: (1) Prefill Phase: During the initial processing of prompt tokens, IceCache allocates paged KV memory per layer and performs self-attention computations. From the third layer onward, it copies KV embeddings to CPU and builds a dynamic index – DCI-tree. This tree enables efficient future lookup of important tokens based on query embeddings. (2) Decode Phase: During autoregressive decoding, each new token’s query embedding is used to retrieve the most relevant KV pages via DCI-based query. Selected pages are back-loaded to GPU on demand, while unimportant pages are offloaded to CPU storage. When a new window page is offloaded, the DCI-tree is incrementally updated to store tokens in this page. The detailed steps are outlined in Algorithm 1. We will explain the mechanisms behind indexing and page selection in the following sections.

## B DETAILS OF ICECACHE (REUSE) ON LONGBENCH

We present the LongBench scores for IceCache (reuse) in Table 5. Starting from the third layer, we build the DCI-tree and perform DCI-queries every three layers; we refer to these as “anchor layers”. For the layers in between, we reuse the KV-cache indices selected at the most recent anchor layer.

Table 5: Accuracy of IceCache (reuse) on LongBench.  
![](images/af61df6ebda715d35f9a46e8b76f15d1c87d7ca62b5a1e9eb1f4b8d64d09b329.jpg)

## C PERFORMANCE ON LONG GENERATION BENCHMARK

To evaluate the effectiveness of IceCache on long-context generation tasks, we conduct experiments on LongGenBench (Wu et al., 2024) using Llama-3.1-8B-Instruct with a 256-token budget. As shown in Table 6, IceCache substantially outperforms PQCache while maintaining accuracies on par with the Full-KV baseline.

Table 6: Accuracy comparison on LongGenBench for Llama-3.1-8B-Instruct.  
![](images/28373d2ab282588120bbda79ed918682e6356d1f2e5355ef9c26f315f020bd1d.jpg)

## D LLM USAGE

This work focuses on optimizing KV-cache management for large language models (LLMs). All the base models used in this paper can be viewed as LLMs, including Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.2, Qwen3-32B, LongChat-7B-v1.5 and Qwen3-4B-Instruct-2507. We also leveraged an LLM to help refine the manuscript’s language and improve its overall readability.

Algorithm 1 IceCache   
1: Input: Sequence of tokens x1:I , Transformer with L attention layers, Page size s   
2: Phase 1: Prefill   
3: for ℓ = 0 to L − 1 do   
4: Allocate pages and arrange KVs to the pages for layer ℓ   
5: if ℓ ≥ 2 then   
6: Copy KVs of tokens between sink tokens and window tokens from GPU to CPU (denoted   
as Sk and Sv)   
7: end if   
8: Compute the output from the current self-attention layer ℓ   
9: if ℓ ≥ 2 then   
10: Tl ← DCI-INDEXING(Sk, Sv)   
11: end if   
12: end for   
13: Phase 2: Decode (repeated over time steps i > I)   
14: while receive new token xi with qi as its query embedding do   
15: for ℓ = 0 to L − 1 do   
16: if Number of tokens in the last page ≥ s − 1 then   
17: Offload the oldest window page Pw from GPU to CPU   
18: Set Flag to True   
19: end if   
20: Append KVs of xi to the end of the newest window page   
21: if ℓ ≥ 2 then   
22: Sl ← PAGE-SELECT(qi, Tl, k)   
23: Recall selected pages Sl from CPU to GPU   
24: end if   
25: Compute the output from the current self-attention layer ℓ   
26: if ℓ ≥ 2 & Flag is True then   
27: // Insert the tokens in offloaded Pw to Tl   
28: for i in Pw do   
29: // Random Promotion   
30: li ← 1 ▷ Start at bottom level   
31: while Random(0, 1) < r do   
32: li ← li + 1 ▷ Promote to the next higher level   
33: end while   
34: {pi} ← QUERY(ki, Tl, li, 1) ▷ Get the parent index using QUERY (Alg.4)   
35: Insert ki to Tl with pi as its parent node index   
36: end for   
37: end if   
38: end for   
39: if xi = EOS then   
40: Break   
41: end if   
42: i = i + 1   
43: end while

Algorithm 2 Indexing   
Require: A list Sk of n keys k1, . . . , kn ∈ Rd, Promotion ratio r   
function DCI-INDEXING(Sk, r)   
for i = 1 to n do   
// Random Promotion   
li ← 1 ▷ Start at bottom level   
while Random(0, 1) < r do   
li ← li + 1 ▷ Promote to the next higher level   
end while   
end for   
Remove the empty levels   
Initialize T with an empty root node   
for i = 1 to n do   
{pi} ← QUERY(ki, T, li, 1) ▷ Get the parent index using QUERY (Alg.4)   
Insert ki to T with pi as its parent node index   
end for   
return T   
end function

Algorithm 3 Page Selection   
Require: Query vector qi ∈ Rd, DCI-tree T , Number of critical keys k   
function PAGE-SELECT(qi, T, k)   
Initialize Sl ← ∅   
Sk ← QUERY(qi, T, −1, k)   
Sl ← FIND-PAGE-INDEX(Sk)   
return Sl   
end function

Algorithm 4 k-Nearest Neighbour Querying   
Require: Query vector qi ∈ Rd, DCI-tree T with L levels, Target level l, Number of critical keys k   
function QUERY(qi, T , l, k)   
if l = −1 then   
l ← 1   
Set Flag to True   
else   
Set Flag to False   
end if   
S ← ∅   
P ← empty priority queue with size k   
for i = L to l do   
S′ ← ∅   
if i = L then   
S ← {root node}   
end if   
for s in S do   
S′′ ← Prioritized-DCI-Query(qi, s, k)   
S′ ← S′ ∪ S′′   
end for   
if Flag is True or i = l then   
for s in S′ do   
P ← Add-to-Priority-Queue (P, s)   
end for   
end if   
S ← S′   
end for   
return k nodes in P that have the keys with maximum inner-product with qi   
end function