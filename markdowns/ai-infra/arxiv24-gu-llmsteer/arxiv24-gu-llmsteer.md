# LLMSTEER: Improving Long-Context LLM Inference by Steering Attention on Reused Contexts

Zhuohan Gu∗ University of Chicago zhuohan@uchicago.edu

Jiayi Yao∗ University of Chicago jiayi3@uchicago.edu

Kuntai Du University of Chicago kuntai@uchicago.edu

Junchen Jiang University of Chicago junchenj@uchicago.edu

## Abstract

As large language models (LLMs) show impressive performance on complex tasks, they still struggle with longer contextual understanding and high computational costs. To balance efficiency and quality, we introduce LLMSTEER, a fine-tuningfree framework that enhances LLMs through query-independent attention steering. Tested on popular LLMs and datasets, LLMSTEER narrows the performance gap with baselines by 65.9% and reduces the runtime delay by up to 4.8× compared to recent attention steering methods.

## 1 Introduction

Large Language Models (LLMs) have demonstrated remarkable capabilities in complex tasks such as question answering, summarization, and reasoning ( llm [a,b,c]). To enhance their reliability, LLMs are often augmented with domain-specific or user-specific knowledge that extends beyond their inherent training data ( Lewis et al. [2020], Jiang et al. [2023], Chen et al. [2024]). However, incorporating these supplemental contexts, which can exceed thousands of tokens ( Jin et al. [2024], Gao et al. [2023]), presents two challenges: (1) models often struggle to comprehend long context (e.g., lost-in-the-middle problem ( Liu et al. [2023a], Junqing et al. [2023])) and (2) processing long context incurs substantial runtime costs (Liu et al. [2024], Lin et al. [2024], Zhong et al. [2024]).

Since the Key-Value (KV) cache of the same context text chunks is often reused multiple times (Liu et al. [2023b], Yao et al. [2024], Jin et al. [2024]), many recent systems adopt prefix caching (Jin et al. [2024], Liu et al. [2023b], Qin et al. [2024]), which stores the KV caches for the frequently reused contexts such that LLMs no longer need to prefill these contexts repeatedly. However, the model persists in losing track of key information from the context as its KV pairs remain unchanged. So, is there a way to simultaneously achieve high efficiency and high quality without fine-tuning models?

We present LLMSTEER, a pioneering, fine-tuning-free framework that efficiently improves the generation quality of models through post-hoc attention steering. More specifically, LLMSTEER reweights attention scores to steer the model’s attention toward selected tokens, thereby improving its contextual understanding. Our insight comes from the fact that storing and reusing the KV cache offers an opportunity to modify the KV cache offline to improve the model’s understanding regarding the context. Thus, all queries could benefit from this improvement as the process of modifying the KV cache of the preceding context is independent of the queries. LLMSTEER enables LLMs to read the same context in different ways by leveraging the idea that each pass through the same context with different prefix prompts leads the model to generate distinct KV caches, which represent different understandings of the context.

We implemented LLMSTEER on top of LLaMA-3.1-8b-Instruct ( Dubey et al. [2024]), and compared LLMSTEER with LLaMA-3.1-8b-Instruct, LLaMA-3.1-70b-Instruct ( Dubey et al. [2024]) and the state-of-the-art attention steering baseline. LLMSTEER demonstrates that by steering tokens that are consistently important across the model’s understandings, it not only achieves a significant increase in F1 scores (e.g., 72.9 -> 82.0), but also delivers up to 4.8× faster compared to the baselines. LLMSTEER not only reduces runtime costs but also improves generation quality. This paper is the first effort to (1) improve model generation quality without fine-tuning and (2) do so in a way that is compatible with prefix caching.

## 2 Post-hoc attention steering

Attention steering didn’t come out of nowhere. Methods like PASTA ( Zhang et al. [2023]) and AutoPASTA ( Anonymous [2024]) introduce techniques to boost the generation quality of LLMs by guiding their attention to specific parts of the input text. In PASTA, users manually specify tokens in the input and steer the LLM’s attention toward these highlighted tokens through reweighting. However, annotating relevant input spans by humans is not always feasible, especially for lengthy contexts and context-specific tasks.

AutoPASTA enhances PASTA by automating the process of identifying key contextual information through iterative prompting. More specifically, AutoPASTA directly prompts the LLM to generate the key sentence in the context based on the query, and then upweight the attention scores of tokens in the key sentence. Despite its potential in improving model’s generation quality, AutoPASTA has several limitations.

First, the iterative prompting approach necessitates two LLM calls, which increases runtime latency. Second, AutoPASTA is incompatible with prefix caching, a technique in which KV caches of the frequently used text chunks are stored and reused such that the prefill of the reused text chunks can be skipped. For example, Llama-8B ( Dubey et al. [2024]) requires 2.04 seconds to process a 5000-token context using 2 A40 GPUs. However, if the KV cache of the text chunk is precomputed and stored, only the final user query needs to be prefilled, which only takes 0.039 seconds on the same hardware. Although prefix caching can still be applied to the initial call in AutoPASTA, the second call cannot benefit from prefix caching in that the attention of the context is steered in a query-dependent way. Consequently, the KV cache of the context will be altered and can no longer be reused across different queries.

## 3 LLMSTEER design

We now present the design of LLMSTEER, which not only reduces runtime costs but also improves inference quality. We begin with the basic insight, followed by how LLMSTEER selects and steers tokens.

Basic insight: When an LLM processes a context in a single pass, some tokens may not receive sufficient attention. By prompting the LLM to read the context multiple times, each with a different prefix prompt and thus a different KV cache, we hypothesize that tokens with consistently high attention scores across these KV caches are the ones requiring more attention.

![](images/9bf99ba4a4d0ab27f6ea3481bec36fa46c0c6033267a55ed58e6023aab6aed5c.jpg)  
Figure 1: LLMSTEER system in an LLM inference workflow processes the same context twice using different prefix prompts to generate key-value caches. It then reweights the selected tokens.

Key components: LLMSTEER consists of three high-level steps. First, it prompts the LLM to process the context text chunks twice, each time using a different prefix prompt. This approach leverages the insight that varying the prefix prompt influences how the LLM interprets the context. Second, at each layer, it computes the cumulative attention scores for each head, selecting the top k tokens based on these scores across all heads. It then identifies tokens that rank highly in both the first and second passes. Finally, it scales up the attention weight of selected tokens. An illustrative overview of LLMSTEER is shown in Figure 1 and the corresponding algorithm can be found in §A.2.

Contextual re-reading: In this step, LLMSTEER prompts the LLM to process the same context twice, each time using a distinct prefix prompt. The goal is to force the model to read the context in two different ways. The prefix prompts do not include the query itself because we want to ensure that the context is read in a non-query-dependent manner. This allows the model to capture general context-related information without bias toward a specific query. More importantly, given a fixed context C and a sequence of queries, our method makes the prefix cache reusable across all queries and reduces the need to call the LLM twice for each query during online inference.

Token selection: For each pass, we store the cumulative attention scores of the prefix prompt and context tokens at each layer and each head. For simplicity, we will ignore indices for layers and heads. Specifically, for each layer and each head, consider the input prompt tensor $\mathbf { X } \in \mathbb { R } ^ { \dot { L } \times D }$ , where L denotes the input prompt length and D represents the model’s hidden dimension. The attention matrix is computed as:

$$
\mathbf { A } = s o f t m a x \left( \frac { \mathbf { Q } \mathbf { K } ^ { \top } } { \sqrt { D } } \right) \in \mathbb { R } ^ { L \times L } ,
$$

where $\mathbf { Q } = \mathbf { X } \mathbf { W } ^ { Q }$ and $\mathbf { K } = \mathbf { X } \mathbf { W } ^ { K }$ . Here, $\mathbf { W } ^ { Q } , \mathbf { W } ^ { K } \in \mathbb { R } ^ { D \times D }$ are learned weight matrices that project the input prompt X into query and key spaces. Let $L _ { p }$ denote the combined length of the prefix prompt and context. The attention matrix for the prefix prompt and context tokens is:

$$
\mathbf { A } _ { p } = \mathbf { A } [ : L _ { p } , : L _ { p } ] \in \mathbb { R } ^ { L _ { p } \times L _ { p } } .
$$

To compute the cumulative attention scores, we sum the attention weights across each column of the attention matrix. This summation gives us the total attention that each token has received from all preceding tokens:

$$
\mathbf { A } _ { s } = \sum _ { i = 0 } ^ { L _ { p } - 1 } \mathbf { A } _ { p } [ i , : ] \in \mathbb { R } ^ { L _ { p } } ,
$$

where ${ \bf A } _ { s } ( i )$ is the cumulative attention score for token $i ,$ representing the total attention received by token i from all preceding tokens.

We then store the cumulative attention scores from all heads and layers along with their corresponding indices for further processing. To determine which tokens to steer, we first sort the cumulative attention scores for each layer across all heads and identify the top k tokens for that layer. Next, we find the intersection of these top-ranked tokens from both passes, selecting those that consistently rank high in both. These selected tokens are then upweighted.

Steering: In the steering phase, for each layer, LLMSTEER adjusts the attention mechanism by applying a weighting matrix, denoted as M , which scales the attention scores for the selected tokens. Initially, we define $\mathbf { \bar { \boldsymbol { M } } } \in \bar { \mathbb { R } } ^ { L \times L }$ , where L is the input prompt length, as a tensor filled with ones. For the selected tokens at each layer, we update the corresponding entries in M using a predefined scaling factor, α. We then expand M across the batch and head dimensions to align with the shape of the attention weights, creating a tensor of shape $\mathbb { R } ^ { 1 \times H \times L \times L }$ , where H represents the number of attention heads. Finally, we apply this weighting matrix element-wise to the original attention scores at each layer, effectively steering the attention toward the selected tokens:

$$
\mathbf { A } _ { \mathrm { s t e e r e d } } = M \odot \mathbf { A } ,
$$

where $\odot$ denotes element-wise multiplication and A represents the original attention matrix.

## 4 Evaluation

## 4.1 Setup

Datasets: Our evaluation covers three datasets: SQuAD ( Rajpurkar et al. [2016]), TriviaQA ( Joshi et al. [2017]) and GSM8K ( Cobbe et al. [2021]). SQuAD is a reading comprehension dataset with questions based on Wikipedia articles. TriviaQA is a large reading comprehension dataset, requiring reasoning across multiple sentences. GSM8K is a collection of diverse grade school math word problems designed for multi-step reasoning. For each dataset, we randomly sample 100 test cases. We use F1-score as the quality metric and request delay (in seconds) as the efficiency metric across all datasets.

![](images/8d1c122a23a572ab54a9452eae8c4dc1cce88dfbd597a69538f9bd61b198e606.jpg)

![](images/a57b8263a6ad75f5baf8a7accc5316bbd80eec2307ce99ce1fc6e3ba3df0341a.jpg)

![](images/73809f1f974525c3b8b386864270e4ced2055e5bda4b30182aa1f19f433510fa.jpg)  
Figure 2: End-to-end Delay vs. Generation Quality. We assume KV cache is already in GPU memory when the request is being served.

LLMSTEER setting: We apply LLMSTEER to Llama-8B, using an attention scaling factor α. The two prefix prompts we used to generate different KV cache are provided in §A.1. Following the AutoPASTA paper, we adopt coarse-to-fine model profiling on LLMSTEER to search for the optimal set of layers and heads to steer that yields the most quality improvement.

Baselines: We compare LLMSTEER with three baselines: Llama-8B, Llama-70B (8-bit quantized) and Llama-8B with AutoPASTA. We also adopt coarse-to-fine model profiling on AutoPASTA. We assume prefix caching is enabled. That is, the KV cache of the prefix instruction and the context is pre-computed and has already been loaded to GPU memory when the request arrives.

Implementation: We build LLMSTEER and all the baselines on top of Huggingface Transformers ( Wolf et al. [2020]). We implement AutoPASTA based on their paper as the code is not public yet. All experiments are conducted on two NVIDIA A40 GPUs.

## 4.2 Results

Reduced request delay: As shown in Figure 2, LLMSTEER consistently achieves request delays close to the 8B baseline across all datasets. On the SQuAD, TriviaQA, and GSM8K datasets, LLMSTEER’s request delay is nearly negligible compared to the 8B baseline. Compared to the 70B model, LLMSTEER is able to reduce request delay by 7.1–7.5×. Compared to AutoPASTA, LLMSTEER can still reduce the request delay by 1.4–4.8×.

Higher quality: Figure 2 demonstrates the high generation quality of LLMSTEER across all three datasets. On the SQuAD dataset, LLMSTEER increases the F1 score by approximately 10% over the LLaMA-8B model with prefix caching and by about 7% over AutoPASTA. This improvement continues on the TriviaQA dataset, where LLMSTEER achieves a similar F1 score increase, surpassing the 8B model by 12.5% and AutoPASTA by 11.4%. While our method does not outperform the 70B model on the SQuAD and TriviaQA datasets, it closely approaches the performance of the larger model without the substantial delay associated with the larger model. Notably, on the GSM8K dataset, our method even exceeds the performance of the 70B model.

Understanding LLMSTEER’s improvement: Unlike AutoPASTA, LLMSTEER steers attention without relying on query information, operating with less information yet achieving superior performance. We test a query-dependent version of LLMSTEER and observe smaller improvements compared to our query-independent method, suggesting that effective attention steering can be achieved without incorporating query information.

## 5 Limitations and Future work

We plan to extend to longer context lengths (e.g., >10k tokens) to fully explore LLMSTEER’s capabilities and to test it on models beyond Llama-8B to assess generalizability. We will also conducting an ablation study to quantify the contributions of the steering mechanism versus contextual re-reading. We will explore the limitations and capabilities of our method compared to traditional finetuning, especially considering context window length and model reasoning capabilities. Additionally, PagedAttention (Kwon et al. [2023]) and FlashAttention (Dao et al. [2022]) could enhance efficiency. Investigating more fine-grained steering at the granularity of individual token pairs, beyond our current token-level attention upweighting, may further improve generation quality and will be explored in future work.

## 6 Conclusion

We introduce LLMSTEER, a novel attention steering method aimed to improve the generation quality of LLMs by allowing the model to review the context multiple times. Specifically, LLMSTEER narrows the response quality gap between small and large LLMs by 65.9% and deliver the responses faster by 4.8× compared to the state-of-the-art attention steering baseline.

## References

Applications of large language models - indata labs. https://indatalabs.com/blog/ large-language-model-apps, a. (Accessed on 09/21/2023).

12 Practical Large Language Model (LLM) Applications - Techopedia. https://www. techopedia.com/12-practical-large-language-model-llm-applications, b. (Accessed on 09/21/2023).

7 top large language model use cases and applications. https://www.projectpro.io/ article/large-language-model-use-cases-and-applications/887, c. (Accessed on 09/21/2023).

Anonymous. Model tells itself where to attend: Faithfulness meets automatic attention steering. In Submitted to ACL Rolling Review - June 2024, 2024. URL https://openreview.net/forum? id=vFf7ZDoLA2. under review.

Jiawei Chen, Hongyu Lin, Xianpei Han, and Le Sun. Benchmarking large language models in retrieval-augmented generation. In Proceedings of the AAAI Conference on Artificial Intelligence, volume 38, pages 17754–17762, 2024.

Karl Cobbe, Vineet Kosaraju, Mohammad Bavarian, Mark Chen, Heewoo Jun, Lukasz Kaiser, Matthias Plappert, Jerry Tworek, Jacob Hilton, Reiichiro Nakano, Christopher Hesse, and John Schulman. Training verifiers to solve math word problems, 2021. URL https://arxiv.org/ abs/2110.14168.

Tri Dao, Dan Fu, Stefano Ermon, Atri Rudra, and Christopher Ré. Flashattention: Fast and memoryefficient exact attention with io-awareness. Advances in Neural Information Processing Systems, 35:16344–16359, 2022.

Abhimanyu Dubey, Abhinav Jauhri, Abhinav Pandey, Abhishek Kadian, Ahmad Al-Dahle, Aiesha Letman, Akhil Mathur, Alan Schelten, Amy Yang, Angela Fan, et al. The llama 3 herd of models. arXiv preprint arXiv:2407.21783, 2024.

Yunfan Gao, Yun Xiong, Xinyu Gao, Kangxiang Jia, Jinliu Pan, Yuxi Bi, Yi Dai, Jiawei Sun, and Haofen Wang. Retrieval-augmented generation for large language models: A survey. arXiv preprint arXiv:2312.10997, 2023.

Zhengbao Jiang, Frank F Xu, Luyu Gao, Zhiqing Sun, Qian Liu, Jane Dwivedi-Yu, Yiming Yang, Jamie Callan, and Graham Neubig. Active retrieval augmented generation. arXiv preprint arXiv:2305.06983, 2023.

Chao Jin, Zili Zhang, Xuanlin Jiang, Fangyue Liu, Xin Liu, Xuanzhe Liu, and Xin Jin. Ragcache: Efficient knowledge caching for retrieval-augmented generation. arXiv preprint arXiv:2404.12457, 2024.

Mandar Joshi, Eunsol Choi, Daniel S. Weld, and Luke Zettlemoyer. Triviaqa: A large scale distantly supervised challenge dataset for reading comprehension, 2017. URL https://arxiv.org/abs/ 1705.03551.

He Junqing, Pan Kunhao, Dong Xiaoqun, Song Zhuoyang, Liu Yibo, Liang Yuxin, Wang Hao, Sun Qianguo, Zhang Songxin, Xie Zejian, et al. Never lost in the middle: Improving large language models via attention strengthening question answering. arXiv preprint arXiv:2311.09198, 2023.

Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph Gonzalez, Hao Zhang, and Ion Stoica. Efficient memory management for large language model serving with pagedattention. In Proceedings of the 29th Symposium on Operating Systems Principles, pages 611–626, 2023.

Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, et al. Retrieval-augmented generation for knowledge-intensive nlp tasks. Advances in Neural Information Processing Systems, 33: 9459–9474, 2020.

Bin Lin, Tao Peng, Chen Zhang, Minmin Sun, Lanbo Li, Hanyu Zhao, Wencong Xiao, Qi Xu, Xiafei Qiu, Shen Li, et al. Infinite-llm: Efficient llm service for long context with distattention and distributed kvcache. arXiv preprint arXiv:2401.02669, 2024.

Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, and Percy Liang. Lost in the middle: How language models use long contexts, 2023a. URL https://arxiv.org/abs/2307.03172.

Xiaoran Liu, Qipeng Guo, Yuerong Song, Zhigeng Liu, Kai Lv, Hang Yan, Linlin Li, Qun Liu, and Xipeng Qiu. Farewell to length extrapolation, a training-free infinite context with finite attention scope. arXiv preprint arXiv:2407.15176, 2024.

Yuhan Liu, Hanchen Li, Kuntai Du, Jiayi Yao, Yihua Cheng, Yuyang Huang, Shan Lu, Michael Maire, Henry Hoffmann, Ari Holtzman, et al. Cachegen: Fast context loading for language model applications. arXiv preprint arXiv:2310.07240, 2023b.

Ruoyu Qin, Zheming Li, Weiran He, Mingxing Zhang, Yongwei Wu, Weimin Zheng, and Xinran Xu. Mooncake: Kimi’s kvcache-centric architecture for llm serving. arXiv preprint arXiv:2407.00079, 2024.

Pranav Rajpurkar, Jian Zhang, Konstantin Lopyrev, and Percy Liang. Squad: 100,000+ questions for machine comprehension of text, 2016. URL https://arxiv.org/abs/1606.05250.

Thomas Wolf, Lysandre Debut, Victor Sanh, Julien Chaumond, Clement Delangue, Anthony Moi, Pierric Cistac, Tim Rault, Rémi Louf, Morgan Funtowicz, Joe Davison, Sam Shleifer, Patrick von Platen, Clara Ma, Yacine Jernite, Julien Plu, Canwen Xu, Teven Le Scao, Sylvain Gugger, Mariama Drame, Quentin Lhoest, and Alexander M. Rush. Transformers: State-of-the-art natural language processing. In Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing: System Demonstrations, pages 38–45, Online, October 2020. Association for Computational Linguistics. URL https://www.aclweb.org/anthology/2020.emnlp-demos.6.

Jiayi Yao, Hanchen Li, Yuhan Liu, Siddhant Ray, Yihua Cheng, Qizheng Zhang, Kuntai Du, Shan Lu, and Junchen Jiang. Cacheblend: Fast large language model serving with cached knowledge fusion. arXiv preprint arXiv:2405.16444, 2024.

Qingru Zhang, Chandan Singh, Liyuan Liu, Xiaodong Liu, Bin Yu, Jianfeng Gao, and Tuo Zhao. Tell your model where to attend: Post-hoc attention steering for llms, 2023. URL https://arxiv. org/abs/2311.02262.

Yinmin Zhong, Shengyu Liu, Junda Chen, Jianbo Hu, Yibo Zhu, Xuanzhe Liu, Xin Jin, and Hao Zhang. Distserve: Disaggregating prefill and decoding for goodput-optimized large language model serving. arXiv preprint arXiv:2401.09670, 2024.

## A Appendix / supplemental material

## A.1 Prefix prompts

Prefix Prompts:   
Prefix prompt 1: Answer the question based on the given passages. Only   
give me the answer and do not output any other words. The following are   
given passages.   
Prefix prompt 2: Respond to the query using only the provided   
texts. Only return the answer. DO NOT return any extra words.   
Below are the provided texts.  
Figure 3: The two prefix prompts used in LLMSTEER to generate different key-value caches. By processing the same context with these varied prefixes, LLMSTEER encourages the model to interpret the context differently in each pass.

## A.2 LLMSTEER Algorithm

Algorithm 1 LLMSTEER   
Input A context C, a set of queries $\{ q _ { 1 } , q _ { 2 } , \dots , q _ { n } \}$ , an LLM L, prefix prompts $P _ { 1 } , P _ { 2 }$ , and a scaling   
factor α.   
1: Contextual re-reading: Ai = Attention $\mathsf { \Omega } _ { : } ( P _ { i } \oplus C )$ for $i \in \{ 1 , 2 \}$ ;   
2: Token selection: $\begin{array} { r } { T ( l ) = \bigcap _ { i = 1 } ^ { 2 } \mathrm { T o p K } ( \sum _ { h } A _ { i } ^ { l , h } , k ) } \end{array}$ , where l denotes the layer and h denotes the   
attention head;   
3: Steering: $A _ { \mathrm { s t e e r e d } } = \mathbf { M } \odot A$ , where M denotes a weighting matrix;   
Output Modified attention weights for context C: Asteered