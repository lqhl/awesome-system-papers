# APE: Faster and Longer Context-Augmented Generation via Adaptive Parallel Encoding

Xinyu Yang<sup>†</sup>, Tianqi Chen<sup>†‡</sup>, Beidi Chen<sup>†</sup>

<sup>†</sup>Carnegie Mellon University, <sup>‡</sup>Nvidia

Context-augmented generation (CAG) techniques, including RAG and ICL, require the eficient combination of multiple contexts to generate responses to user queries. Directly inputting these contexts as a sequence introduces a considerable computational burden by re-encoding the combined selection of contexts for every request. To address this, we explore the promising potential of parallel encoding to independently pre-compute and cache each context’s KV states. This approach enables the direct loading of cached states during inference while accommodating more contexts through position reuse across contexts. However, due to misalignments in attention distribution, directly applying parallel encoding results in a significant performance drop. To enable efective and eficient CAG, we propose Adaptive Parallel Encoding (APE), which brings shared prefix, attention temperature, and scaling factor to align the distribution of parallel encoding with sequential encoding. Results on RAG and ICL tasks demonstrate that APE can preserve 98% and 93% sequential encoding performance using the same inputs while outperforming parallel encoding by 3.6% and 7.9%, respectively. It also scales to many-shot CAG, efectively encoding hundreds of contexts in parallel. Eficiency evaluation shows that APE can achieve an end-to-end 4.5× speedup by reducing 28× prefilling time for a 128K-length context.

![](images/9c1612f94a6331612587b32914de7d0548d6858039aac95f096b531671ed4c36.jpg)

Github: https://github.com/Infini-AI-Lab/APE Website: https://infini-ai-lab.github.io/APE-Page

## 1 Introduction

Recent advances in context-augmented generation (CAG) techniques, particularly retrieval-augmented generation (RAG) (Gupta et al., 2024; Gao et al., 2023) and in-context learning (ICL) (Dong et al., 2022; Wei et al., 2022), have been widely adopted in large language models (LLMs) (Dubey et al., 2024; Achiam et al., 2023), improving their ability to generalize to unseen tasks with contextual information, as demonstrated in Figure 1 (top). These techniques employ a sequential encoding process to ground LLM inputs with knowledge from external sources: concatenating the retrieved texts into one sequence, and encoding the sequence into key-value (KV) states as the context for subsequent queries. While this new, significantly longer input improves performance, the increased latency in context prefilling becomes a bottleneck in tasks that require long inputs but generate short outputs (Bai et al., 2023; Agarwal et al., 2024; Jiang et al., 2024b). For example, prefilling a 128K context takes 17 seconds, whereas generating 256 tokens requires only 6 seconds. This discrepancy leaves significant room to improve the practical eficiency of CAG systems in real-world deployments (Liu, 2022; Chase, 2022).

Since texts for CAG are typically stored independently in external databases (Zayarni et al., 2024; Douze et al., 2024), pre-caching all these texts for direct loading during inference ofers a brute-force approach to accelerate CAG. However, for autoregressive LLMs, the KV states are inherently context-dependent. This dependency makes naive pre-caching impractical, as it would require caching all possible context permutations, leading to factorial growth in memory requirements as the database size increases. For instance, caching all permutations of just ten 256-token text chunks for the <sup>LLaMA-3-8B</sup> model would demand an impractical 22 PB of memory.

To address this issue, parallel encoding (Ratner et al., 2022; Yen et al., 2024; Li et al., 2024; Sun et al., 2024) is introduced to encode each context into KV states separately, ensuring that tokens from diferent contexts cannot attend to each other during encoding. Next, the on-the-fly generation starts by prefilling user queries, which can attend to the cached KV states from all contexts without re-encoding, ofering two benefits:

Pre-caching Contexts for Fast Inference: Texts from external sources can be pre-computed and cached into KV states, which serve as contexts for direct loading during inference. Additionally, this approach allows for cost-free manipulation of contexts, including operations like insertion, deletion, replacement, and swapping.

![](images/dbef80fc1dcbf3a7f335cdd1b23ada74bd2c3d31dad3966b3fc94720eafecfd3.jpg)  
Figure 1 Overview of Our Approach. Context-augmented generation leverages additional contexts to improve LLM response quality to user queries. Sequential encoding prefills selected context chunks as a long sequence during inference, leading to high latency from on-the-fly re-encoding and low accuracy due to context window limitations. Parallel encoding ofers an alternative method to pre-compute more and longer contexts within the same positional range but results in worse performance. To address these challenges, we propose Adaptive Parallel Encoding (APE) to re-align the attention weight distribution of parallel encoding with sequential encoding via three training-free steps: shared prefix, scaling factor, and adaptive temperature, leading to fast and accurate CAG systems in real-world applications.

Re-using Positions for Long Context: Contexts can be inserted into the same range of positions in an LLM’s context window, allowing for more and longer context chunks. It also mitigates the problem of “lost in the middle” in context ordering (Liu et al., 2024a), as each context is equally “close” to the generated tokens.

Despite these advantages, parallel encoding leads to significant performance degradation across multiple RAG and ICL scenarios, as shown in Figure 2, with average declines of 4.9% (despite using 2-10× more contexts) and 49.0%, respectively. While prior works (Sun et al., 2024; Yen et al., 2024) have attempted to correct this with fine-tuning, these methods continue to exhibit reduced accuracy in reasoning tasks (e.g., GSM8K). This decrease arises from the limited generalization capability of models fine-tuned on simple tasks to complex ones.

However, our results in Figure 2 also reveal that parallel encoding holds promise, as LLMs can still generate reasonable responses due to their inherent alignments with sequential encoding. Based on this observation, we aim to strengthen these alignments while addressing the remaining discrepancies to achieve more accurate parallel encoding. Our insight from Figure 3 and Figure 4 is that KV states from independent contexts can be naturally merged into one sequence due to their similarity in direction and magnitude, attributed to the presence of an attention sink (Xiao et al., 2023). This observation reduces our challenge to addressing residual misalignments, which manifest as anomalous distributions at the initial and recent positions within each context.

Motivated by this, we propose Adaptive Parallel Encoding (APE) to align the distribution between sequential and parallel encoding, which enables accurate and fast CAG (see Figure 1 (Bottom)). Our contributions involve:

• We systematically analyze the distribution properties of attention weights in parallel encoding, focusing on the magnitude and direction of KV states across various samples and positions. Our observations identify major alignments and minor misalignments between parallel and sequential encoding for further improvement.

• We propose APE to recover the accuracy of parallel encoding with three alignment steps: (i) Prepend a shared prefix to avoid the duplication of abnormal distribution of initial tokens. (ii) Adjust a lower attention temperature to sharpen the distribution, focusing on contextually important tokens. (iii) Apply a scaling factor to ofset the increase in the magnitude of the LogSumExp value of attention scores from the context.

• We empirically show that (i) APE maintains 98% and 93% of the sequential encoding performance in RAG and ICL tasks, respectively. (ii) APE outperforms parallel encoding in RAG and ICL, yielding improvements of 3.6% and 7.9%, respectively. (iii) APE scales to handle hundreds of contexts in parallel, matching or exceeding sequential encoding in many-shot scenarios. (iv) APE accelerates long-context generation, achieving up to 4.5× speedup through a 28× reduction in prefilling time for a context including 128K tokens.

## 2 Background and Related Work

## 2.1 Context-Augmented Generation

This work explores CAG problems using LLMs, where user queries are enhanced with additional contexts from external databases. CAG typically involves two scenarios: RAG (Asai et al., 2024; Gupta et al., 2024; Gao et al., 2023), which focuses on directly retrieving relevant information, and ICL (Dong et al., 2022; Wei et al., 2022; Agarwal et al., 2024), which emphasizes further acquiring emergent capabilities from in-context examples.

## 2.2 Parallel Encoding

Next, we present the formulation of using parallel encoding in LLMs for CAG settings. Let S represent the input sequence including N contexts C<sub>1</sub>, ..., C<sub>N</sub> and one query Q. Formally, this can be denoted as:

![](images/30ce141b7717ffe071ae4cdd1680f2a366e180a12172b934ea4eef0d2a776875.jpg)

(1)

For simplicity, we can express this as: S = {S<sub>C</sub> , S<sub>C</sub> , . . . , S<sub>C</sub> , S<sub>Q</sub>}. Given two models Θ<sub>Enc</sub> and Θ<sub>Dec</sub> (which may be the same model), a response R is generated to the input S using parallel encoding in two steps:

Pre-caching Contexts. The first step is to encode and cache the KV states for each context independently using Θ<sub>Enc</sub>. For a given context S<sub>C</sub> , we compute its KV states ofline as (K<sub>C</sub> , V<sub>C</sub> ) = Θ<sub>Enc</sub>(S<sub>C</sub> ) and store them for direct loading during inference. Specifically, we denote K<sub>Ci</sub> = {k<sub>Ci,1</sub>, . . . , k<sub>Ci,li</sub> } and V<sub>Ci</sub> = {v<sub>Ci,1</sub>, . . . , v<sub>Ci,li</sub> }.

Generating Response. Next, the user query is augmented by all relevant pre-cached KV states to generate the response: R = Θ<sub>Dec</sub>(S<sub>Q</sub>, K<sub>C</sub> , V<sub>C</sub> ), where K<sub>C</sub> , V<sub>C</sub> are subsets of {K<sub>C</sub> , ..., K<sub>C</sub> } and {V<sub>C</sub> , ..., V<sub>C</sub> }, respectively.

Parallel encoding significantly improves eficiency compared to sequential encoding by reducing the complexity of prefilling from O((l<sub>1</sub> + ... + l<sub>N</sub> + l<sub>Q</sub>)<sup>2</sup>) (i.e., quadratic) to linear concerning the total context length. With pre-caching, the cost becomes O((l<sub>1</sub> + ... + l<sub>N</sub> + l<sub>Q</sub>) · l<sub>Q</sub>). In the absence of pre-caching, the complexity is O(max(l<sup>2</sup>, ..., l<sup>2</sup> ) + ((l<sub>1</sub> + ... + l<sub>N</sub> + l<sub>Q</sub>) · l<sub>Q</sub>), which remains eficient for multiple contexts of similar length.

Prior parallel encoding approaches vary in their design of Θ and Θ . Parallel Context Windows (PCW) (Ratner et al., 2022) directly employs pre-trained LLMs as both, resulting in significant performance drops. Block-Attention (Sun et al., 2024) further fine-tunes the model, successfully recovering performance in RAG tasks. Alternatively, CEPE (Yen et al., 2024) and FocusLLM (Li et al., 2024) train new Transformer-based encoders using encoder-only and decoder-only architectures, respectively. These methods also difer in Θ : CEPE trains additional cross-attention layers for processing contexts, whereas other methods directly input the context into original self-attention layers. While these trainable methods show promising results in RAG tasks, challenges remain regarding their training overheads and generalization abilities to more complex ICL scenarios. Moreover, applying parallel encoding in CAG can be viewed as a kind of memory-augmented neural networks (Burtsev et al., 2020; De Jong et al., 2021; F´evry et al., 2020), where external memory is directly stored into KV states.

## 2.3 Attention Mechanism

In a standard Softmax attention, we attend the query to all past KV states using the following formula:

![](images/7d61aed8eca3bf50f2565e4e8f61afd90e90ed578149882d9029ac433d4d9baa.jpg)

(2)

where Q is the query state, and K and V denote the key and value states, respectively. Previous research has QK<sup>T</sup>   
revealed several significant insights into the distribution of attention weights (i.e., Softmax( )). d

Attention Sink. StreamingLLM (Xiao et al., 2023) identifies the presence of an “attention sink” in LLMs, a token that receives a significantly higher attention score than other tokens but provides limited semantic information. It observes that the attention sink exists in the initial token and influences the following tokens.

Position Embedding. To efectively process sequential input, LLMs require position embeddings, such as absolute position embeddings (Vaswani, 2017; Devlin, 2018) and relative position embeddings (Su et al., 2024; Press et al., 2021). However, the introduction of position embedding not only limits the context window to the training length (Chen et al., 2023) but also results in the “lost in the middle” (Liu et al., 2024a) issue, where LLMs struggle to produce correct answers when relevant information locates in the middle of the context.

## 3 Observations

![](images/4b774266a37ab25e486b64d1ab8eb0a1e14b2358f85d6f03c6f64b9dcb193f57.jpg)  
(a) Retrieval-augmented Generation

![](images/fd42982eeeb7940c2752aa30a0ad3552b036dc31aff0956f0289bfc6aa61d9c7.jpg)  
(b) In-context Learning  
Figure 2 Comparison of sequential encoding, parallel encoding, and CEPED in RAG and ICL scenarios. Parallel encoding and CEPED degrades performance, especially on tasks such as GSM8K that requires reasoning ability.

In Section 3.1, we evaluate sequential encoding, parallel encoding, and CEPE-Distilled (CEPED) (Yen et al., 2024) using the <sup>LLaMA-2-7B-chat</sup> model<sup>1</sup>. Figure 2 presents our findings on various RAG and ICL tasks, highlighting the limitations of trainable approaches in generalizing to complex reasoning tasks. Next, we explore the alignments and misalignments between parallel encoding and sequential encoding in Section 3.2, providing insights into why parallel encoding remains efective and identifying opportunities for further improvement.

## 3.1 Trainable Approaches are only Effective for Easy Tasks.

In Figure 2, we compare the performance of diferent context encoding methods on RAG and ICL tasks, with detailed setups described in Appendix A. Our analysis of the long-context RAG capability on LongBench (Bai et al., 2023) is showcased in Figure 2a. Despite accessing more passages, CEPED only surpasses the sequential baseline in two of the three QA tasks, and it even notably underperforms parallel encoding in the summarization task (MultiNews), which requires synthesizing information from the entire context. We hypothesize that CEPED cannot process complex tasks since the encoder and decoder are only trained on the unlabeled pre-training corpus without instruction-tuning on high-quality QA samples. This conclusion is further supported by the results of ICL tasks (see Figure 2b), where CEPED performs on par with the 1-shot sequential encoding baseline on TriviaQA but falls short of it on GSM8K and MMLU, despite using much more examples. The latter involves reasoning steps that are hard for the ill-trained model to understand. In conclusion, fine-tuning models to improve parallel encoding requires (i) more diverse and labeled data and (ii) resource-intensive instruction-tuning (e.g., SFT or RLHF (Ouyang et al., 2022)). Given this unfavorable trade-of between training costs and model capabilities, we propose developing a training-free method to improve the performance of parallel encoding.

![](images/f161f25067b91dd0d7192236b5324cd4a335b39da59f46f511b2a883a9e0030c.jpg)  
Similarity between tokens from different samples in each positions  
Similarity between the initial token and tokens in different positions  
Figure 3 Top Left: Both <sup>LLaMA-3-8B-Instruct</sup> (a) and <sup>Mistral-7B-Instruct-v0.3</sup> (b) exhibit a cosine similarity larger than 0.9 for the key states from distinct initial tokens. Top Right: Initial token’s key states show similar negative values to those from other positions for <sup>LLaMA-3-8B-Instruct</sup> (c) and <sup>Mistral-7B-Instruct-v0.3</sup> (d) models. Bottom: Value states exhibit patterns similar to those observed in key states. The X-axis shows the positions of key and value states on a logarithmic scale. Visualizations and analyses for more base models are provided in Appendix B.

## 3.2 Comparing Parallel Encoding and Sequential Encoding.

In Figure 2, we observe that parallel encoding still holds promise, as it can generate reasonable responses without further modifications. This finding is non-trivial as contexts are encoded into KV states separately without guarantee that these states can be compared or combined. However, our analysis reveals that the attention mechanism naturally builds alignments between KV states from diferent positions in independent contexts similar to sequential encoding. To clarify this, Figure 3 focuses on the impact of the attention sink (Xiao et al., 2023), where we visualize the direction of KV states for diferent samples and positions. In Figure 4, we further visualize the distribution of various components in the Softmax attention, resulting in several findings.

Key states from diferent contexts are similar. In Figure 3a and 3b, we measure the cosine similarity between the key states of diferent initial tokens for the <sup>LLaMA-3-8B-Instruct</sup> and <sup>Mistral-7B-Instruct-v0.3</sup> models, which consistently yields a value close to 1. This observation indicates that the direction of the initial key state remains invariant mainly across diferent inputs. Figure 3c and 3d further analyze the similarity between the initial key states and their subsequent states, where we observe

![](images/114b6af2c855e264b93c1126e18536ecc04fefc2008160f77e457f1aac8a8a87.jpg)  
Figure 5 Geometry of Key States.

comparable negative values from diferent positions. Therefore, the angles between the initial key states and their subsequent states are similar and significantly larger than the angles between diferent initial key states, as demonstrated in Figure 5. It suggests that the direction of key states remains relatively consistent across contexts, as they are primarily decided by the initial key states, which exhibit similar directions across examples. These findings, combined with the small variance in key state magnitudes across examples in Figure 4b, indicate that key states from diferent contexts share similar directions and magnitudes, making them comparable.

![](images/f5cbff5346541ecc10190defeb7b6c17c8f9d9ed1a2d3bd50a2c53cd1dd5cfbf.jpg)  
(a) Query-Key Similarity

![](images/cf345a8679b52d0f38f6aebcfb81f8b165d58c70a19c875597101e2eb395e6bc.jpg)  
(b) Key Magnitude

![](images/e6267229998f096f37fa250ac35d5178341ff990635b54d5f6b3b455b31dd91c.jpg)  
(c) Value Magnitude

![](images/95040fe6b83f7ebccf6a709ddb8738f34d19235780d013f7a029e38414a273bb.jpg)  
(d) Query-Key Product  
Figure 4 Visualization of Diferent Components in Attention. (a) The cosine similarity between query and key states increases as the distance between their positions decreases. (b) The magnitudes of key states show a slowly upward trend as position increases. (c) The magnitude of value states remain constant across positions. (d) Query-ke dot products keep consistently low values except at initial and recent positions. A red dashed line marks the anomalous region for the first two tokens in all figures. The X-axis shows positions of KV states on a log scale. Results are measured with the <sup>LLaMA-3-8B-Instruct</sup> model. Visualizations and analyses for more base models are provided in Appendix B.

To further understand this, we experiment on HotPotQA using the <sup>LLaMA-3-8B-Instruct</sup> model. Our analysis involves applying rotations of varying degrees around random axes to the initial key states. For parallel encoding, we explore two rotation modes: one using the same rotation axis for all contexts and another employing a random rotation axis for each context. Figure 6 reveals that sequential encoding keeps performance across various rotation degrees. In contrast, both modes in parallel encoding deteriorate when rotations exceed 150 degrees. This efect arises from the duplication of initial key states, intensifying our rotations’ impact. Notably, using separate axes for each context leads to an earlier breakdown

![](images/4377d59302db321e142610995231c060f3632e9392196e12a1e953e4d7682bcd.jpg)  
Figure 6 Rotation Analysis on the First Token

beginning at 90 degrees. This mode disrupts the directional similarity of key states with diferent initial tokens (i.e., k<sub>initial</sub>) in Figure 5 and enlarges the angle between key states from diferent contexts.

Values states from diferent contexts can be combined. In Equation (2), all value states are combined through a weighted summation, where the Softmax operator would normalize the weights of all value states to sum to 1. This normalization indicates that the magnitude of current value states is determined solely by those from previous positions, resulting in a similar L<sup>2</sup> norm across positions, as shown in Figure 4c. Additionally, the small variance shows that the magnitudes are comparable among samples. This finding, coupled with a similar direction across samples and positions in Figure 3 (Bottom), indicates the possibility of combining value states.

Opportunities for improvement. Despite the KV states exhibiting similarity across contexts for most positions, the residual misalignments in Figure 4 still severely reduce accuracy. We summarize them as follows:

• In Figure 4, we observe a notable discrepancy in direction and magnitude for the initial positions, leading to large QK dot products at these positions in Figure 4d. They are identified as an anomaly in the context.

• Figure 4d shows the dot products between the query state and all past key states, revealing a notable increase when the states are positioned close to each other, as reflected in the larger similarity observed in Figure 4a.

## 4 Adaptive Parallel Encoding

With all the lessons learned in Section 3, we will design our APE to address the residual misalignments. APE enables a seamless shift to parallel encoding without requiring training while maintaining most of the model’s capabilities. Our approach adaptively aligns the distribution of attention weights between sequential and parallel encoding via three steps as illustrated in Figure 1, thereby boosting eficiency and performance.

![](images/e919d12db2e08dfea10bdb3ae7781f96586524588dcf88d4d1a0282ac91a1ee8.jpg)  
(a) Sequential

![](images/c0b1ae4fac0734c5bcc8a9dc7b58e6ff3b256ec0456ce293fbad98c296ff9ec1.jpg)  
(b) Parallel (T = 1.0)

![](images/eb7adbe712eb0875721cf5ddbb055bac1ea0d8d03b6809dc73417e9fe617739a.jpg)  
(c) Parallel (T = 0.2)

![](images/ea5fe627cf10ab7bba0ba1d7fa711ce57f9f8d0691a390eef55610cca508f4cf.jpg)  
(d) Parallel vs. Sequential  
Figure 7 Comparison of Attention Weight Distribution within Contexts. (a) Sequential encoding allocates high attention scores to neighboring tokens. (b) Parallel encoding distributes attention scores more uniform across neighboring tokens from all contexts. (c) Adjusting the temperature T sparsifies the distribution. (d) After adjustment, the distribution in parallel encoding becomes similar to sequential encoding. The X-axis represents token positions.

## 4.1 Prepending Shared Prefix.

Figure 4 shows that the distribution of the first few tokens difers significantly from that of subsequent tokens. This discrepancy poses a challenge when encoding contexts in parallel due to duplicating these abnormal KV states. To address this issue, we propose a simple yet efective solution: prepending a shared prefix to all contexts. This approach ensures that these KV states appear only once in each generation step. In practice, the choice of prefix varies with the model and task. We use existing system prompts and instructions as the shared prefix when available. Otherwise, we will insert a few newline characters (i.e., “\n”) before all contexts.

Although the later positions are not identified as abnormal, we still observe instability at the start of LLM inputs. To mitigate this issue, we may also consider extending the existing prefix with more newline characters.

## 4.2 Adjusting Attention Temperature.

In Figure 4d, the value of QK dot products increases as the relative distance decreases, with a notably sharper rise when the distance approaches zero. To show its impact on parallel encoding, we set a 50-token prefix and query, encoding the remaining 900 tokens either sequentially or in five parallel chunks, with attention distributions shown in Figure 7. Comparing Figure 7b with 7a, duplicating neighboring KV states in parallel encoding will disperse the query’s attention to multiple contexts, resulting in a more uniform attention distribution. We adjust the attention temperature T to a value less than 1 to refocus on the most relevant tokens, sharpening the distribution after the Softmax operation. The comparison between diferent T is shown in Figure 7c and 7d.

## 4.3 Adding Scaling Factor.

While adjusting the temperature sharpens the attention distribution among context tokens, it will also alter the overall attention allocated to the whole context, as indicated by the LogSumExp value in Figure 8. Specifically, when the sum of the original QK dot product values in a given layer is significantly greater than 0, reducing temperature amplifies these positive values, resulting in an increased, positive LogSumExp value. Conversely, when the sum is closer to 0, lowering temperature has a stronger efect on the negative QK dot products, leading to a decreased, negative LogSumExp value. These efects generally increase the absolute value of LogSumExp(QK). To compensate for these changes, we introduce a scaling factor S < 1 to reduce this absolute value.

![](images/5548baa936a98ea14a6cc99b2a1535fd3b9985695c197519987f40beed4f1005.jpg)  
Figure 8 Parallel w/ Diferent T .

## 4.4 Formulation.

Given these three steps, we can formulate the modified attention in APE. We begin with the standard Softmax attention, where Q, K, and V are the query, key, and value states, respectively. We use the subscript C<sub>i</sub> for elements from the context C<sub>i</sub>, while those without a subscript correspond to user queries or generated texts.

![](images/8140c88cb30d8b3226d06e9a951126aa279ac466b0026ac5413c87e46e616bec.jpg)

(3)

(4)

![](images/56e4d30b83558096665f208d9615f4f4e789e9a9025cb6b981d40d60f5f52270.jpg)

After incorporating the proposed changes, the formula for our refined attention calculation becomes:

![](images/988e3e2d19f6ffe6ba40b0add9c2fb5d526cba24828d12c161d5f7f3a5f0b740.jpg)

(5)

A<sub>P</sub> represents the attention weights for the shared prefix while A denotes that for query and generated tokens. The attention temperature T and the scaling factor S for the context are less than 1. Appendix C provides a detailed deduction of this formula for better understanding. All these modifications are compatible with fast attention implementations such as flash attention (Dao et al., 2022) by computing the context and non-context KV states separately and merging them into the attention output. This process only incur a negligible overhead.

For the choice of hyperparameters, we conduct a greedy search over a small validation set. If no prefix is provided, we begin by adding two “\n” and increase the prefix length by 10, 20, and 40. S and T are searched in the ranges [0.1, 1.0] using 0.1 step sizes. We use S · T instead of S as the scaling factor to simplify our search.

## 5 Experiments

Empirically, we present the efectiveness and eficiency of APE in CAG scenarios such as RAG and ICL. Since we focus on context encoding problems, we do not include comparisons with long-context LLMs. Specifically,

• In Section 5.1, APE can maintain 98% of the accuracy on ChatRAG-Bench compared to sequential encoding. Furthermore, it improves 3.3% performance for RAG on LongBench by retrieving more and longer contexts.

• In Section 5.2, APE outperforms parallel encoding by 7.9% on average in three ICL tasks. Moreover, APE can maintain 93% of the accuracy achieved by sequential encoding when using the same number of examples.

• In Section 5.3, APE can scale to many-shot CAG tasks, efectively encoding hundreds of texts in parallel.

• In Section 5.4, APE achieves 4.5× faster inference for 128k context through 28× reduction in prefilling time.

## 5.1 Retrieval-Augmented Generation.

In the context of RAG tasks, we validate that APE retains most of the sequential encoding capability while accommodating more and longer contexts, mitigating retrieval errors, and outperforming encoding baselines.

## 5.1.1 Retrieval for Multi-turn Question Answering.

Setup. APE is evaluated on five conversational QA tasks using ChatRAGBench (Liu et al., 2024b). For each query, we prepare about 100 text chunks. Three retrievers of varying quality are employed to retrieve up to the top-5 chunks for evaluation, including Contriever (Izacard et al., 2021), GTE-base Li et al. (2023), and Dragon-multiturn Liu et al. (2024b). We use <sup>Llama3-ChatQA-1.5-8B</sup> as the base model. To fairly measure performance drop after our modifications, the same retrieved texts are used for APE and sequential encoding.

Table 1 Comparison between APE and sequential encoding using three retrievers on ChatRAG-Bench.  
![](images/08931975f4439aaa9b76ce4322d4498b4663d3312a21a36b7902f81f0802bbd1.jpg)

Results. Table 1 shows that switching from sequential encoding to APE results in performance drops of 0.51%, 0.92%, and 1.14% across diferent retrievers, respectively. While this drop increases with retriever quality, APE still keeps 97% of the sequential encoding performance for the best retriever. By increasing the text chunk length for 5 times, APE directly inputs all texts without any retrieval process, achieving superior performance.

## 5.1.2 Retrieval for Long-context Understanding.

Setup. Our evaluation involves eight tasks on LongBench (Bai et al., 2023). Given the long context, we split it into chunks with a size of M words, employ Contriever (Izacard et al., 2021) to compute the embeddings of all chunks and the query and retrieve the top-N chunks according to the cosine similarity of their embeddings to the query embedding. M and N vary across diferent methods. We compare APE with sequential encoding with and without RAG, and PCW, using <sup>Llama-3-8B-Instruct</sup> (Dubey et al., 2024), <sup>Mistral-7B-Instruct</sup> <sup>v0.3</sup> (Jiang et al., 2023), <sup>Gemma-2-9b-it</sup> (Team et al., 2024), and <sup>Llama-3.1-8B-Instruct</sup> as base models.

Results. In Table 2, APE consistently improves performance across all models, achieving a 5.6% average gain over sequential encoding without RAG. It also outperforms sequential RAG baselines by 3.3% by retrieving more and longer contexts. The superior performance over PCW further showcases the efectiveness of our modifications in APE. Notably, APE surpasses the 128K-context variant of the <sup>Llama-3.1-8B-Instruct</sup> model by placing retrieved texts within the 8K context window, mitigating the “lost in the middle” phenomenon.

## 5.2 In-context Learning

Setup. We evaluate APE on three ICL tasks using the LM Evaluation Harness (Gao et al., 2024) codebase: GSM8K (8-shot) (Cobbe et al., 2021a), TriviaQA (5-shot) (Joshi et al., 2017), and MMLU (5-shot) (Hendrycks et al., 2020a). Experiments are conducted using the same base models as in our LongBench evaluations. We compare parallel encoding (PCW) to show the improvement of APE. Sequential encoding with varying numbers of shots (i.e., 1-shot, half-shots, and full-shots) is also employed to measure the gap from the ideal scenarios.

Results. In Figure 9, APE surpasses parallel encoding with average improvements of 15.4% on GSM8K, 4.7% on TriviaQA, and 3.5% on MMLU. When compared with the 1-shot sequential baseline with similar context length, our method consistently yields superior results. Moreover, APE performs better than half-shot sequential encoding in 8/12 settings and preserves 93% accuracy compared to full-shot sequential encoding. Additionally, the <sup>Llama</sup> family exhibits enhanced compatibility with parallel encoding, potentially due to the stronger directional alignment of initial tokens from diferent contexts (see Figure 3a). Across diferent tasks, the performance gap between APE and full-shot sequential encoding is the largest on GSM8K. This finding suggests that while APE keeps most capabilities, its efectiveness may decrease as task complexity increases.

Table 2 Comparison between APE and baselines on LongBench across diferent models using RAG. C denotes Contriever, and M × N indicates retrieval of the top-N chunks, each containing M words.  
![](images/f16f5141aadd96ac540922139adadcf460dedb4490da65241f93650ccbb15699.jpg)

Table 3 Comparison between APE and sequential encoding in various many-shot RAG and ICL tasks.  
![](images/9ac7e6d3185abcade61b904a062deac9ae80da1d8646652b12866dbf6deaedb8.jpg)

## 5.3 Many-shot Context-Augmented Generation

Setup. We evaluate the scalability of APE on four RAG and ICL tasks from the LOFT benchmark (Lee et al., 2024), each involving hundreds of additional texts. We employ <sup>Llama-3.1-8B-Instruct</sup> as our base model to compare APE with sequential encoding, both applied to the same many-shot inputs. The total context lengths for the RAG and ICL tasks are 128K and 32K, respectively. We also include the zero-shot, few-shot (≤ 5), and half-shot sequential encoding baselines. For metrics, F1 score and EM are used in RAG and ICL tasks.

Results. In Table 3, APE achieves performance comparable to sequential encoding when processing the same many-shot long-context inputs, showing its ability to encode hundreds of texts in parallel eficiently. Notably, it outperforms sequential encoding on ArguAna and FEVER for RAG tasks. While APE is expected to reduce performance, it recovers this drop by positioning all texts close to the query, mitigating the “lost in the middle” problem in long-context LLMs. For ICL tasks, APE can learn from examples as efective as sequential encoding.

## 5.4 Efficiency Evaluation

Setup. We measure the latency for sequential encoding, MInference (Jiang et al., 2024a), and APE usingLlama-3.1-8B-Instruct (Dubey et al., 2024) on an H100 GPU with batch sizes of 1 and 4. The query and generation lengths are fixed at 256 tokens, while the context lengths range from 2K to 128K tokens. We employ VLLM (Kwon et al., 2023) as our inference engine and measure both prefilling time and total inference time.

Results. Comparing to sequential encoding and MInference, APE can accelerate inference up to 4.5× and

![](images/304aefdbd4178bf4f3f3f20e26c57ef60641c5dfa40e93b11cb4a439c7112a32.jpg)  
<sub>(a)</sub> Llama-3-8B-Instruct

![](images/ab8dc34b76722f18c672f405cc1362f5d5ae15e3fc1193e69e800a79f61bcdee.jpg)  
<sub>(b)</sub> Llama-3.1-8B-Instruct

![](images/57627241b4c32ab9691edaf39381f400892d7d32d9fc57f9fcfd551289b1b1c2.jpg)  
<sub>(c)</sub> Mistral-7B-Instruct-v0.3

![](images/13a5fe1e05c98ccb0b717fe7716466e30ca427baa5a73935b00f318e4e2ad208.jpg)  
<sub>(d)</sub> Gemma-2-9b-it

Figure 9 Performance comparison of APE, parallel encoding, and sequential encoding on ICL tasks.  
![](images/303479d7bc218d2533933043e34e3bf717f4bff548f5600423a9e2c9189a4b54.jpg)  
(a) Prefill Time (bsz=1)

![](images/018a78332a2b4278771fdf6a2ce3bfd45f2d0f0b2d43e39a0a957e5d7e2508de.jpg)  
(b) Prefill Time (bsz=4)

![](images/fba71e818262468cf7c363084a125f4ecb12fe44ba9650671e74b6de6ecb568b.jpg)  
(c) Total Time (bsz=1)

![](images/dd87ecb5f9f7c29ddf04ee7a52ec7b64bdef6b97c674e1cc1d673dda974c846f.jpg)  
(d) Total Time (bsz=4)  
Figure 10 Latency on H100 GPU: prefill and total inference time (s). The gray text in brackets is batch size.

2.2× respectively for long-context scenarios in Figure 10. For 128K-token contexts, APE reduces prefilling time by 28× compared to MInference. The prefilling cost of APE exhibits linear scaling and consumes less than 10% of inference time, whereas baselines require over 50% as context length increases. APE also shows superior versatility, while MInference slows inference with additional overhead for short contexts and large batches.

## 6 Analysis

This section presents analyses to answer the following research questions: RQ1: Can APE improve performance for real-world RAG applications? RQ2: How does each component in APE contribute to the performance? RQ3: Can APE extend LLM context window size in long-context scenarios without RAG?

## 6.1 Can APE improve performance for real-world RAG applications?

In Table 4, we evaluate APE in real-world RAG scenarios using the CRAG benchmark (Yang et al., 2024). Task 1 augments the model with five webpages, while Task 2 provides an additional knowledge graph as another retrieval source. In our experiments, the sequential encoding baseline is limited to retrieving 4K tokens, whereas APE can process 20 parallel segments of 4K tokens each. By incorporating significantly more external texts,

APE consistently outperforms sequential encoding with limited context sizes while reducing latency. Moreover, the improvement in Task 2 shows the efectiveness of APE in merging text from multiple sources.

Table 4 Performance and latency comparison using the Llama-3-8B-Instruct model on CRAG benchmark.  
![](images/4c5a46c99be60f337c95bcf937217279cd48282723f0ec9c099c7e72e0eda273.jpg)

## 6.2 How does each component in APE contribute to the performance?

In Table 5, we conduct an ablation study to examine each component in APE, including the shared prefix (P ), attention temperature (T ), and scaling factor (S). We present results averaged across the four base models evaluated in Figure 9. Our findings indicate that incorporating each of these components can improve performance for all tasks, with average improvements of 5.19%, 0.59%, and 2.07%, respectively. Among them, adding a shared prefix leads to the largest improvement, while adjusting the attention temperature yields minimal accuracy gains without the complementary efect of the scaling factor.

Table 5 Ablation study of APE components on ICL tasks. P : shared prefix, T : attention temperature, S: scaling factor.

![](images/73de7e155612d0608f5cdd431c6e10a4dbeb49f0bdf42c6ba891e7c19e3fcaa5.jpg)

## 6.3 Can APE extend context lengths in long-context scenarios without RAG?

Table 6 evaluates the efectiveness of APE in handling a single long-context input using the <sup>Llama-3-8B-</sup> <sup>Instruct</sup> model on the LongBench dataset (Bai et al., 2023). To accommodate the long context within our APE, we split it into multiple segments of less than 7,500 tokens. Additionally, we append the last 500 tokens to the query for two code completion tasks. Our results indicate that APE enhances performance across 10/11 tasks, yielding an average improvement of 6.6% compared to the sequential encoding baseline with limited context window size. More baseline results of long-context LLM approaches are provided in Appendix D.

Table 6 Performance comparison across diferent long-context tasks on LongBench (Bai et al., 2023).  
![](images/79b3deae6d8676c54124c1634b1b2e0370c911aeab9d9bccf03aac66d266f5b3.jpg)

## 7 Conclusion

This work explores the potential of parallel encoding in CAG scenarios, which can pre-cache KV states for fast inference and re-use positions for long context but lead to worse performance. To address this, we propose APE, a training-free method to enable accurate, fast, and long CAG systems. APE achieves this by aligning the attention weight distribution of parallel encoding with sequential encoding via three steps: shared prefix, adaptive temperature, and scaling factor. Empirically, we show that APE improves accuracy and eficiency in various RAG and ICL tasks while successfully scaling to process hundreds of chunks in parallel for both settings.

## 8 Limitations

While APE shows the efectiveness and eficiency of parallel encoding with only inference-time modification in the attention distribution, it remains sensitive to hyperparameter selection, particularly the attention temperature T and scaling factor S. In real-world applications, where contexts vary in length, quantity, and content, aligning the distribution between sequential and parallel encoding automatically presents a significant challenge.

## 9 Acknowledgement

This work is supported in part by NSF award CNS-2211882 and a gift from Qualcomm. We thank the authors of ChatQA (Liu et al., 2024b), Longbench (Bai et al., 2023), CRAG (Yang et al., 2024), LM Evaluation Harness (Gao et al., 2024), VLLM (Kwon et al., 2023), and MInference (Jiang et al., 2024a) for their useful codebase, benchmark, and models, and Yixin Dong, Hanshi Sun, Zhuoming Chen for their helpful discussions.

## References

Josh Achiam, Steven Adler, Sandhini Agarwal, Lama Ahmad, Ilge Akkaya, Florencia Leoni Aleman, Diogo Almeida, Janko Altenschmidt, Sam Altman, Shyamal Anadkat, et al. Gpt-4 technical report. arXiv preprint arXiv:2303.08774, 2023.

Rishabh Agarwal, Avi Singh, Lei M Zhang, Bernd Bohnet, Stephanie Chan, Ankesh Anand, Zaheer Abbas, Azade Nova, John D Co-Reyes, Eric Chu, et al. Many-shot in-context learning. arXiv preprint arXiv:2404.11018, 2024.

Akari Asai, Zexuan Zhong, Danqi Chen, Pang Wei Koh, Luke Zettlemoyer, Hannaneh Hajishirzi, and Wen-tau Yih. Reliable, adaptable, and attributable language models with retrieval. arXiv preprint arXiv:2403.03187, 2024.

Yushi Bai, Xin Lv, Jiajie Zhang, Hongchang Lyu, Jiankai Tang, Zhidian Huang, Zhengxiao Du, Xiao Liu, Aohan Zeng, Lei Hou, Yuxiao Dong, Jie Tang, and Juanzi Li. Longbench: A bilingual, multitask benchmark for long context understanding. arXiv preprint arXiv:2308.14508, 2023.

Mikhail S Burtsev, Yuri Kuratov, Anton Peganov, and Grigory V Sapunov. Memory transformer. arXiv preprint arXiv:2006.11527, 2020.

Harrison Chase. Longchain, 2022. https://github.com/langchain-ai/langchain.

Shouyuan Chen, Sherman Wong, Liangjian Chen, and Yuandong Tian. Extending context window of large language models via positional interpolation. arXiv preprint arXiv:2306.15595, 2023.

Karl Cobbe, Vineet Kosaraju, Mohammad Bavarian, Mark Chen, Heewoo Jun, Lukasz Kaiser, Matthias Plappert, Jerry Tworek, Jacob Hilton, Reiichiro Nakano, et al. Training verifiers to solve math word problems. arXiv preprint arXiv:2110.14168, 2021a.

Karl Cobbe, Vineet Kosaraju, Mohammad Bavarian, Mark Chen, Heewoo Jun, Lukasz Kaiser, Matthias Plappert, Jerry Tworek, Jacob Hilton, Reiichiro Nakano, et al. Training verifiers to solve math word problems. arXiv preprint arXiv:2110.14168, 2021b.

Tri Dao, Dan Fu, Stefano Ermon, Atri Rudra, and Christopher R´e. Flashattention: Fast and memory-eficient exact attention with io-awareness. Advances in Neural Information Processing Systems, 35:16344–16359, 2022.

Michiel De Jong, Yury Zemlyanskiy, Nicholas FitzGerald, Fei Sha, and William Cohen. Mention memory: incorporating textual knowledge into transformers through entity mention attention. arXiv preprint arXiv:2110.06176, 2021.

Jacob Devlin. Bert: Pre-training of deep bidirectional transformers for language understanding. arXiv preprint arXiv:1810.04805, 2018.

Qingxiu Dong, Lei Li, Damai Dai, Ce Zheng, Zhiyong Wu, Baobao Chang, Xu Sun, Jingjing Xu, and Zhifang Sui. A survey on in-context learning. arXiv preprint arXiv:2301.00234, 2022.

Matthijs Douze, Alexandr Guzhva, Chengqi Deng, Jef Johnson, Gergely Szilvasy, Pierre-Emmanuel Mazar´e, Maria Lomeli, Lucas Hosseini, and Herv´e J´egou. The faiss library. arXiv preprint arXiv:2401.08281, 2024.

Abhimanyu Dubey, Abhinav Jauhri, Abhinav Pandey, Abhishek Kadian, Ahmad Al-Dahle, Aiesha Letman, Akhil Mathur, Alan Schelten, Amy Yang, Angela Fan, et al. The llama 3 herd of models. arXiv preprint arXiv:2407.21783, 2024.

Alexander R Fabbri, Irene Li, Tianwei She, Suyi Li, and Dragomir R Radev. Multi-news: A large-scale multi-document summarization dataset and abstractive hierarchical model. arXiv preprint arXiv:1906.01749, 2019.

Thibault F´evry, Livio Baldini Soares, Nicholas FitzGerald, Eunsol Choi, and Tom Kwiatkowski. Entities as experts: Sparse memory access with entity supervision. arXiv preprint arXiv:2004.07202, 2020.

Leo Gao, Jonathan Tow, Baber Abbasi, Stella Biderman, Sid Black, Anthony DiPofi, Charles Foster, Laurence Golding, Jefrey Hsu, Alain Le Noac’h, Haonan Li, Kyle McDonell, Niklas Muennighof, Chris Ociepa, Jason Phang, Laria Reynolds, Hailey Schoelkopf, Aviya Skowron, Lintang Sutawika, Eric Tang, Anish Thite, Ben Wang, Kevin Wang, and Andy Zou. A framework for few-shot language model evaluation, 07 2024. https://zenodo.org/records/12608602.

Yunfan Gao, Yun Xiong, Xinyu Gao, Kangxiang Jia, Jinliu Pan, Yuxi Bi, Yi Dai, Jiawei Sun, and Haofen Wang. Retrieval-augmented generation for large language models: A survey. arXiv preprint arXiv:2312.10997, 2023.

AI Gradient. Llama-3-8b-instruct-262k, 2024.

Aman Gupta, Anup Shirgaonkar, Angels de Luis Balaguer, Bruno Silva, Daniel Holstein, Dawei Li, Jennifer Marsman, Leonardo O Nunes, Mahsa Rouzbahman, Morris Sharp, et al. Rag vs fine-tuning: Pipelines, tradeofs, and a case study on agriculture. arXiv preprint arXiv:2401.08406, 2024.

Dan Hendrycks, Collin Burns, Steven Basart, Andy Zou, Mantas Mazeika, Dawn Song, and Jacob Steinhardt. Measuring massive multitask language understanding. arXiv preprint arXiv:2009.03300, 2020a.

Dan Hendrycks, Collin Burns, Steven Basart, Andy Zou, Mantas Mazeika, Dawn Song, and Jacob Steinhardt. Measuring massive multitask language understanding. arXiv preprint arXiv:2009.03300, 2020b.

Xanh Ho, Anh-Khoa Duong Nguyen, Saku Sugawara, and Akiko Aizawa. Constructing a multi-hop qa dataset for comprehensive evaluation of reasoning steps. arXiv preprint arXiv:2011.01060, 2020.

Gautier Izacard, Mathilde Caron, Lucas Hosseini, Sebastian Riedel, Piotr Bojanowski, Armand Joulin, and Edouard Grave. Unsupervised dense information retrieval with contrastive learning. arXiv preprint arXiv:2112.09118, 2021.

Albert Q Jiang, Alexandre Sablayrolles, Arthur Mensch, Chris Bamford, Devendra Singh Chaplot, Diego de las Casas, Florian Bressand, Gianna Lengyel, Guillaume Lample, Lucile Saulnier, et al. Mistral 7b. arXiv preprint arXiv:2310.06825, 2023.

Huiqiang Jiang, Yucheng Li, Chengruidong Zhang, Qianhui Wu, Xufang Luo, Surin Ahn, Zhenhua Han, Amir H Abdi, Dongsheng Li, Chin-Yew Lin, et al. Minference 1.0: Accelerating pre-filling for long-context llms via dynamic sparse attention. arXiv preprint arXiv:2407.02490, 2024a.

Ziyan Jiang, Xueguang Ma, and Wenhu Chen. Longrag: Enhancing retrieval-augmented generation with long-context llms. arXiv preprint arXiv:2406.15319, 2024b.

Hongye Jin, Xiaotian Han, Jingfeng Yang, Zhimeng Jiang, Zirui Liu, Chia-Yuan Chang, Huiyuan Chen, and Xia Hu. Llm maybe longlm: Self-extend llm context window without tuning. arXiv preprint arXiv:2401.01325, 2024.

Mandar Joshi, Eunsol Choi, Daniel S Weld, and Luke Zettlemoyer. Triviaqa: A large scale distantly supervised challenge dataset for reading comprehension. arXiv preprint arXiv:1705.03551, 2017.

Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph Gonzalez, Hao Zhang, and Ion Stoica. Eficient memory management for large language model serving with pagedattention. In Proceedings of the 29th Symposium on Operating Systems Principles, pages 611–626, 2023.

Jinhyuk Lee, Anthony Chen, Zhuyun Dai, Dheeru Dua, Devendra Singh Sachan, Michael Boratko, Yi Luan, S´ebastien MR Arnold, Vincent Perot, Siddharth Dalmia, et al. Can long-context language models subsume retrieval, rag, sql, and more? arXiv preprint arXiv:2406.13121, 2024.

Zehan Li, Xin Zhang, Yanzhao Zhang, Dingkun Long, Pengjun Xie, and Meishan Zhang. Towards general text embeddings with multi-stage contrastive learning. arXiv preprint arXiv:2308.03281, 2023.

Zhenyu Li, Yike Zhang, Tengyu Pan, Yutao Sun, Zhichao Duan, Junjie Fang, Rong Han, Zixuan Wang, and Jianyong Wang. Focusllm: Scaling llm’s context by parallel decoding. arXiv preprint arXiv:2408.11745, 2024.

Jerry Liu. Llamaindex, 11 2022. https://github.com/jerryjliu/llama\_index.

Nelson F Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, and Percy Liang. Lost in the middle: How language models use long contexts. Transactions of the Association for Computational Linguistics, 12:157–173, 2024a.

Zihan Liu, Wei Ping, Rajarshi Roy, Peng Xu, Chankyu Lee, Mohammad Shoeybi, and Bryan Catanzaro. Chatqa: Surpassing gpt-4 on conversational qa and rag. In The Thirty-eighth Annual Conference on Neural Information Processing Systems, 2024b.

Long Ouyang, Jefrey Wu, Xu Jiang, Diogo Almeida, Carroll Wainwright, Pamela Mishkin, Chong Zhang, Sandhini Agarwal, Katarina Slama, Alex Ray, et al. Training language models to follow instructions with human feedback. Advances in neural information processing systems, 35:27730–27744, 2022.

Zhuoshi Pan, Qianhui Wu, Huiqiang Jiang, Menglin Xia, Xufang Luo, Jue Zhang, Qingwei Lin, Victor R¨uhle, Yuqing Yang, Chin-Yew Lin, et al. Llmlingua-2: Data distillation for eficient and faithful task-agnostic prompt compression. arXiv preprint arXiv:2403.12968, 2024.

Ofir Press, Noah A Smith, and Mike Lewis. Train short, test long: Attention with linear biases enables input length extrapolation. arXiv preprint arXiv:2108.12409, 2021.

Nir Ratner, Yoav Levine, Yonatan Belinkov, Ori Ram, Inbal Magar, Omri Abend, Ehud Karpas, Amnon Shashua, Kevin Leyton-Brown, and Yoav Shoham. Parallel context windows for large language models. arXiv preprint arXiv:2212.10947, 2022.

Jianlin Su, Murtadha Ahmed, Yu Lu, Shengfeng Pan, Wen Bo, and Yunfeng Liu. Roformer: Enhanced transformer with rotary position embedding. Neurocomputing, 568:127063, 2024.

East Sun, Yan Wang, and Lan Tian. Block-attention for eficient rag. arXiv preprint arXiv:2409.15355, 2024.

Gemma Team, Morgane Riviere, Shreya Pathak, Pier Giuseppe Sessa, Cassidy Hardin, Surya Bhupatiraju, L´eonard Hussenot, Thomas Mesnard, Bobak Shahriari, Alexandre Ram´e, et al. Gemma 2: Improving open language models at a practical size. arXiv preprint arXiv:2408.00118, 2024.

AI Together. Llama-2-7b-32k-instruct, 2023.

Harsh Trivedi, Niranjan Balasubramanian, Tushar Khot, and Ashish Sabharwal. Musique: Multihop questions via single-hop question composition. Transactions of the Association for Computational Linguistics, 10:539–554, 2022.

A Vaswani. Attention is all you need. Advances in Neural Information Processing Systems, 2017.

Jason Wei, Yi Tay, Rishi Bommasani, Colin Rafel, Barret Zoph, Sebastian Borgeaud, Dani Yogatama, Maarten Bosma, Denny Zhou, Donald Metzler, et al. Emergent abilities of large language models. arXiv preprint arXiv:2206.07682, 2022.

Guangxuan Xiao, Yuandong Tian, Beidi Chen, Song Han, and Mike Lewis. Eficient streaming language models with attention sinks. arXiv preprint arXiv:2309.17453, 2023.

Xiao Yang, Kai Sun, Hao Xin, Yushi Sun, Nikita Bhalla, Xiangsen Chen, Sajal Choudhary, Rongze Daniel Gui, Ziran Will Jiang, Ziyu Jiang, et al. Crag–comprehensive rag benchmark. arXiv preprint arXiv:2406.04744, 2024.

Zhilin Yang, Peng Qi, Saizheng Zhang, Yoshua Bengio, William W Cohen, Ruslan Salakhutdinov, and Christopher D Manning. Hotpotqa: A dataset for diverse, explainable multi-hop question answering. arXiv preprint arXiv:1809.09600, 2018.

Howard Yen, Tianyu Gao, and Danqi Chen. Long-context language modeling with parallel context encoding. arXiv preprint arXiv:2402.16617, 2024.

Andr´e Zayarni, Andrey Vasnetsov, et al. Qdrant, 2024. https://qdrant.tech/.

## Appendix

## A Detailed Experimental Setups for Section 3.1

RAG. We select four tasks that require processing multiple input documents from the LongBench dataset (Bai et al., 2023), including HotpotQA (Yang et al., 2018), 2WikiMultihopQA (Ho et al., 2020), MuSiQue (Trivedi et al., 2022), and MultiNews (Fabbri et al., 2019). The F1 score is used as the evaluation metric for the three QA tasks, while Rouge-L is used for the summarization task. Both parallel encoding and CEPED process each document independently using Θ<sub>Enc</sub>. For documents that exceed the length limitation of Θ<sub>Enc</sub>, we split them into multiple chunks for encoding. In sequential encoding, we will truncate lengthy inputs from the middle.

ICL. We select three few-shot learning tasks from LM Evaluation Harness (Gao et al., 2024) to evaluate the ICL ability of diferent encoding methods, involving GSM8K (Cobbe et al., 2021b), TriviaQA Joshi et al. (2017), and MMLU (Hendrycks et al., 2020b). In parallel encoding and CEPED, we will encode each example separately and input all the resulting KV states to Θ<sub>Dec</sub>. For sequential encoding, we use variants with diferent numbers of shots to further measure the efectiveness of other methods, including 0-shot, 1-shot, half-shot, and full-shot.

## B More Visualization Results for Section 3.2

## B.1 Similarity between Tokens from Different Samples in Each Position for Key States.

In Figure 11, we showcase that key states in diferent layers maintain consistently high cosine similarity values for various initial tokens, with only the first layer exhibiting slightly lower similarities. Our analysis reveals that <sup>LLaMA-3-8B-Instruct</sup> and <sup>LLaMA-3.1-8B-Instruct</sup> exhibit almost the same direction (approximately 1.0) for diferent tokens beyond the first layer, while <sup>Mistral-7B-Instruct-v0.3</sup> and <sup>Gemma-2-9b-it</sup> show substantial but lower similarities ranging from 0.8 to 0.9. These findings indicate inherent alignments across contexts while highlighting the potential for further improvements through the shared prefix in Section 4.1.

![](images/48566fcffd584e9d1702a70103d0a608874d533390a45c0357615cbc5f8e430a.jpg)  
(a) LLaMA-3-8B-Instruct

![](images/3909f25e0d68b3f623b7abaf4e178e2172f833e4c96b65ecacdc52cae0733eb2.jpg)  
(b) LLaMA-3.1-8B-Instruct

![](images/587764e14cde55190440206b281acfb480a9dc51fe0f9effba6828b4d821531f.jpg)  
(c) Mistral-7B-Instruct-v0.3

![](images/31c0577003c58a62ea5b73069c5af88e13c5e6b00e1c40a22239ea7017402e57.jpg)  
(d) Gemma-2-9b-it  
Figure 11 For all base models, key states from distinct inital tokens exhibit a large cosine similarity than the following positions, where the LLaMA family even approaches 1. The X-axis shows positions of key states on a logarithmic scale.

## B.2 Similarity between Tokens from Different Samples in Each Position for Value States.

Similarly, Figure 12 shows that value states maintain high cosine similarity across diferent layers for various initial tokens. There are two notable exceptions: the first layer and the <sup>Gemma-2-9b-it</sup> model. This distinctive pattern in <sup>Gemma-2-9b-it</sup> aligns with the model’s requirement for a system prompt to function correctly.

## B.3 Similarity between the Initial Token and Following Tokens for Key States.

Figure 13 illustrates how the cosine similarity between the initial and subsequent key states stabilizes as position increases. This similarity converges to a near-constant value for all base models after 10 tokens.

![](images/309438992882cf331dcdd8758910e897d823423d2bb3a6b0d652bf3e86a43015.jpg)  
(a) LLaMA-3-8B-Instruct

![](images/dbdfb43cec2e4015a5fcf1feffcb3890eb8d736f08d2524e0c8f3aa118235a9c.jpg)  
(b) LLaMA-3.1-8B-Instruct

![](images/8db062de51d9a2ddf7bb7026de8514ffc61616d034f24167308341f0675147dd.jpg)  
(c) Mistral-7B-Instruct-v0.3

![](images/df2c9768f69919120e275c6e233cbcea6157aaaf234dbc3b5488f13874d6a52e.jpg)  
(d) Gemma-2-9b-it

Figure 12 Among four models, value states from distinct inital tokens exhibit a large cosine similarity than the following positions, except the first layer and <sup>Gemma-2-9b-it</sup>. The X-axis shows positions of value states on a logarithmic scale.  
![](images/ebe697573a0d854c1dd10bdc1b6f8a2d050d73b9f58f6ba0f5e0599d5fc9ae8a.jpg)  
(a) LLaMA-3-8B-Instruct

![](images/d9e4f1ce6fd25ff66f886b8fa40c19161cfa12c9c6fb83b3c725c1521a3c4bc3.jpg)  
(b) LLaMA-3.1-8B-Instruct

![](images/0be67f67410667069c0ae109ef3251e7e0da3b2ce0efb6a012af740e8e782408.jpg)  
(c) Mistral-7B-Instruct-v0.3

![](images/69e5f057bf991edf49e69e313969b7024dabfb165e737538ecb6ebc554c9476c.jpg)  
(d) Gemma-2-9b-it  
Figure 13 For all base models, the similarity between the initial key state and subsequent key states stabilizes as the position increases. The X-axis shows positions of key states on a logarithmic scale.

## B.4 Similarity between the Initial Token and Following Tokens for Value States.

Similar to key states, the value states exhibit a stable similarity between the initial token and subsequent tokens in Figure 14, with all models convergent to a nearly constant value after approximately 10 tokens.

![](images/f0e32022294250bc703e4fff032279acf1770a7bc063cc9f13b45d1b9f42a33c.jpg)  
(a) LLaMA-3-8B-Instruct

![](images/bce2c4986beb1e2c03abbdd898270eda41077f1f6a12865923b5150602c58c61.jpg)  
(b) LLaMA-3.1-8B-Instruct

![](images/d3bb7c9790bb9cc8c438883ed049c91a187a57c6f0bc57300a6a628a050fe64b.jpg)  
(c) Mistral-7B-Instruct-v0.3

![](images/9beb5e436cc665be0ebf8d0fed8898933081348adde61671af695dce34ac056f.jpg)  
(d) Gemma-2-9b-it  
Figure 14 For all base models, the similarity between the initial value state and subsequent value states stabilizes as the position increases. The X-axis shows positions of value states on a logarithmic scale.

## B.5 Similarity between the Query State and Past Key States.

In Figure 15, the query states across all layers, and base models exhibit higher cosine similarity with the initial tokens. Additionally, neighboring positions tend to receive higher cosine similarity.

## B.6 Magnitude of Key States from Different Positions.

Figure 16 illustrates that the magnitude of key states gradually increases with position, except for the first few tokens, which exhibit significantly smaller magnitudes.

![](images/d336713872d1dd2076c7a6921393447d8a7a17801e2947dfa2c2d055d1a06fbb.jpg)  
(a) LLaMA-3-8B-Instruct

![](images/14f9105b2c271fcf50ce64016d4ac42e0b6cada754b8beb0d7172d9d0f856578.jpg)  
(b) LLaMA-3.1-8B-Instruct

![](images/0e9aa23619b83072ed77f14ba61776a5ec99c627e3761b9bd9f75d5e4b662d01.jpg)  
(c) Mistral-7B-Instruct-v0.3

![](images/b7e88742e3492c181ad495ee3845a880e3fb52ebdfab00124704fc5dbf4dec0e.jpg)  
(d) Gemma-2-9b-it

Figure 15 For all base models, the cosine similarity between the query state and past key states stabilizes for most positions, except for the initial and recent key states. The X-axis shows positions of key states on a logarithmic scale.  
![](images/62bc945b5445efad1d499d2f484c4fba22224b9918ce9e8e7b18ff19a7afc3fa.jpg)  
(a) LLaMA-3-8B-Instruct

![](images/9b3388cab2afe2cea9c8eb6fa5b34fda784f6050d5821c9b3661373ecb809a45.jpg)  
(b) LLaMA-3.1-8B-Instruct

![](images/1dbc77cd047681a7901cef4f473a401dbf1e3e47f42a9d235be47549e582fd10.jpg)  
(c) Mistral-7B-Instruct-v0.3

![](images/c4e5409210771bfb84260ac118a6b7ff1d7f2fafc83c10d6f840066c9dfcbaa3.jpg)  
(d) Gemma-2-9b-it  
Figure 16 For all models, key states show a slowly upward trend in magnitude as position increases. A red dashed line marks the anomalous region for the first few tokens. The X-axis shows positions of key states on a logarithmic scale.

## B.7 Magnitude of Value States from Different Positions.

![](images/56c71eddf4dcd3cc226a8fef9e4ba9bee48724b1dc0f8028b90d75da32be3f3c.jpg)  
(a) LLaMA-3-8B-Instruct

![](images/c7dc3eab6d0a00addf4bef83d6144ffb482061541f5b6dc298e31d715a730f6e.jpg)  
(b) LLaMA-3.1-8B-Instruct

![](images/a3a3e17a650a05b531b430738a9ac13c585b940f7c1ac8c0057b769e85b98b83.jpg)  
(c) Mistral-7B-Instruct-v0.3

![](images/0306960cc0c48e61ed46acd6564ba0eb8995fa1877c4ba852db0b23a6103eb23.jpg)  
(d) Gemma-2-9b-it  
Figure 17 For all models, the magnitude of value states remains consistent for most positions, except for the first few positions highlighted by a red dashed line. The X-axis represents the positions of value states on a logarithmic scale.

In Figure 17, the value states across all positions exhibit a similar magnitude, except for the first few positions, which show a noticeable deviation. We indicate this region with a red dashed line.

## B.8 Dot Product between the Query State and Past Key States.

In Figure 18, the query states across all layers, and base models exhibit larger dot product values with the initial tokens. Additionally, neighboring positions also tend to receive larger values.

![](images/d36a91de1729a3c9a551fecb41ce60c2f02ea7305a734c82c51d9e3b40a79bfd.jpg)  
(a) LLaMA-3-8B-Instruct

![](images/79b62bb8b5d78bcddfea791bf6b46a12c3dd48dc24ea3444d0be1c6403b67c4a.jpg)  
(b) LLaMA-3.1-8B-Instruct

![](images/7dcb77b5c219702dbc06b834bdfb09a9d56d57fe4b0a3ed36d6975823c83c21f.jpg)  
(c) Mistral-7B-Instruct-v0.3

![](images/2b3345eead5721c252017a829e163c0ae723b8dd201fc179a52d13cd4b2bbab6.jpg)  
(d) Gemma-2-9b-it  
Figure 18 For all base models, the dot product values between the query state and past key states stabilizes for most positions, except for the initial and recent key states. The X-axis shows positions of key states on a logarithmic scale.

## C Formal Derivation of APE

## C.1 Hierarchical Formula for Softmax Attention.

Here, we begin with the standard Softmax attention, where Q, K, and V are the query, key, and value states from the input, respectively. To distinguish diferent sources, we use the subscript C<sub>i</sub> for elements originating from the context, while those without a subscript correspond to user queries or generated texts.

![](images/7046d36cee8affa88d1d94087b6751776bfe280bdcc78795142bfc56762dc3ae.jpg)

(6)

(7)

![](images/838462684ecbc695e56c4ee18b82002f759849bd2ec32ee1395cd2181eb38234.jpg)

![](images/f2a9bbf00585e5aa062371fa6468d8906612d266e18eb625d60fdd8b3cde6736.jpg)

We can restructure the computation hierarchically, first computing V <sup>h</sup><sub>C</sub> and A<sup>h</sup><sub>C</sub> for each context C<sub>i</sub>:

![](images/ae3045698fe4a1889da965ce05773586d94d437f1e542eda88b9504e82214f3a.jpg)

(8)

Similarly, for the non-context tokens, we compute:

![](images/ae99c18610161e27ba55ec176e41ebd6e9f1ce0ce7ed39a20ba759818ae3ac88.jpg)

(9)

After we get all these values, we can combine them while renormalizing with A<sup>h</sup>:

![](images/4bca3b8fb9b80d913460f371d6ab4dc794adbb16dcca779f36646547bea4c387.jpg)

(10)

## C.2 Hierarchical Formula for APE.

After incorporating all components in APE, we have a new V <sup>h′</sup><sub>C</sub> and A<sup>h′</sup><sub>C</sub> for each context C<sub>i</sub>:

![](images/4f0f6bc22c5110c35f4a0e19719dacb2d3147a4b7f4515602552ceeb624e1d9e.jpg)

(11)

For the non-context tokens, including our shared prefix, the formulas of V <sup>h′</sup> and A<sup>h′</sup> remain unchanged. Here, we introduce separate terms V <sup>h′</sup><sub>P</sub> and A<sup>h′</sup><sub>P</sub> for the shared prefix. Combining them, we have:

![](images/8c5f6823c81392cdad571e3b9404a1c9543a115c53ee0553146540cf6ee8e2b4.jpg)

(12)

## C.3 Relation with Equation 5.

Finally, we show that it can be rewritten as Equation 5, with the only diference being that all contexts are treated as a single context. For an token from the position j in context C<sub>i</sub>, the final attention score a<sup>′′</sup><sub>C ,j</sub> is

![](images/46d24be37b45492ed4d157159412074611da3e830d410f130f388b5e232cd55c.jpg)

(13)

![](images/f08af531c96fd4f630d4888d29acc51d8ac667dd5db70743b475afc10bd140c6.jpg)

(14)

(15)

This formula is equivalent to Equation 5, except it combines the prefix and other non-context tokens for simplicity. Similarly, for the non-context tokens from position j, we can derive a<sup>′′</sup><sub>j</sub> as

![](images/b20cd5d59f1d557a8f6848ca34b6ec63ab320ff0642e4ca03a976d43008322e9.jpg)

(16)

Combining these two components, we obtain the final formula presented in Equation 5.

## C.4 Efficient Implementation.

To combine the computation for context and non-context tokens, we employ flash attention twice—once for each part—and then merge the results. This only introduces a marginal computational overhead, as shown below.

ape attention (query , key , value , temperature , scale ) :   
# s pl i t key and value states into context and non−context parts   
key context , key other = key   
value context , value other = value   
attn output context , lse context = flash attn (query , key, value , temperature = temperature)   
attn output other , lse other = flash attn (query , key , value)   
lse context = lse context ∗( scale )   
attn weights = [ lse context , lse other ]   
attn weights = Softmax(attn weights)   
value states = [ attn output context , attn output other ]   
attn output = attn weights @ value states

## C.5 Future Directions.

The hierarchical formulation of APE can naturally extend to more complex tree structures, as illustrated in Figure 19. This flexibility allows each user query to be enriched with external knowledge organized in such structures, demonstrating APE’s capability to handle structured external data efectively.

![](images/0d0ea88bd93a0d396922ea9570a0fe56a78a1a2d7cf046e705d5c9ce2c2ae22d.jpg)  
Figure 19 Beyond the parallel cache structure discussed in the main paper, APE can be extended to handle more complex cache structures from external sources, where each context forms a tree-like hierarchy. In this setup, computations can be performed hierarchically along each branch, progressively merging intermediate results into the final value state.

## D Comparing APE with Long-context LLMs.

In Table 7, we further compare APE with Long-context LLM, including: (i) Prompt Compression: Truncation, LLMLingua2 (Pan et al., 2024), (ii) KV Cache Eviction: StreamingLLM (Xiao et al., 2023), (iii) Longcontext FT : Llama-3-8B-Instruct-262K (Gradient, 2024), Llama-2-7B-Instruct-32K (Together, 2023), (iv) length extrapolation: Self-Extend (Jin et al., 2024). Experimental results show that APE consistently outperforms all existing long-context LLM methods. We hypothesize that this improvement stems from APE enabling queries to access all past contexts, enhancing retrieval ability. However, since APE has limitations in identifying relationships between contexts, we do not emphasize its performance on current long-context tasks.

## E APE Cache versus Prefix Cache

Finally, we compare the APE cache with the prefix cache to highlight our advantages in serving multiple queries within the CAG setting. Figure 20 illustrates an example with four contexts where both caching strategies are allocated the same budget. Each query retrieves three contexts. Under these conditions, the prefix cache can only match a limited number of combinations, achieving an average hit rate of 41.7%, whereas the APE cache ensures a 100% hit rate. This gap will become even more pronounced as the number of contexts increases.

![](images/0480a4504c9fd7fa43634e5ea2407284d7773293e7605189cd28205ec8b6c0db.jpg)  
Table 7 Performance comparison between APE and long-context LLMs on LongBench (Bai et al., 2023).

![](images/3cfa1e0bfd2784aad916f39836288929512146a61e60ee505487ca81ed92bb6d.jpg)  
(a) Prefix Cache

![](images/ae553cfdf01449ed48e5d8ba33f1224dc955580e7cc52ee45938db6529a10c99.jpg)  
(b) APE Cache  
Figure 20 Prefix Cache vs. APE Cache. Our cache can keep a 100% hit rate while the prefix cache only has 42%.