# R&D-Agent-Quant: A Multi-Agent Framework for Data-Centric Factors and Model Joint Optimization

Yuante Li1∗, Xu Yang2, Xiao Yang2,

Minrui Xu3∗, Xisen Wang4∗, Weiqing Liu2†, Jiang Bian2 1 Carnegie Mellon University, 2 Microsoft Research Asia 3 Hong Kong University of Science and Technology, 4 University of Oxford yuantel@cs.cmu.edu, {xuyang1, xiao.yang}@microsoft.com mxubh@connect.ust.hk, xisen.wang@keble.ox.ac.uk {weiqing.liu, jiang.bian}@microsoft.com

## Abstract

Financial markets pose fundamental challenges for asset return prediction due to their high dimensionality, non-stationarity, and persistent volatility. Despite advances in large language models and multi-agent systems, current quantitative research pipelines suffer from limited automation, weak interpretability, and fragmented coordination across key components such as factor mining and model innovation. In this paper, we propose R&D-Agent for Quantitative Finance, in short R&D-Agent(Q), the first data-centric multi-agent framework designed to automate the full-stack research and development of quantitative strategies via coordinated factor-model co-optimization. R&D-Agent(Q) decomposes the quant process into two iterative stages: a Research stage that dynamically sets goal-aligned prompts, formulates hypotheses based on domain priors, and maps them to concrete tasks, and a Development stage that employs a code-generation agent, Co-STEER, to implement task-specific code, which is then executed in real-market backtests. The two stages are connected through a feedback stage that thoroughly evaluates experimental outcomes and informs subsequent iterations, with a multi-armed bandit scheduler for adaptive direction selection. Empirically, R&D-Agent(Q) achieves up to 2× higher annualized returns than classical factor libraries using 70% fewer factors, and outperforms state-of-the-art deep time-series models on real markets. Its joint factor–model optimization delivers a strong balance between predictive accuracy and strategy robustness. Our code is available at: https://github.com/microsoft/RD-Agent.

## 1 Introduction

Financial markets constitute high-dimensional, nonlinear dynamical systems whose return series display heavy tails [1], time-varying volatility [2], and intricate cross-sectional dependence [3]. These features imply that asset prices are driven simultaneously by macro factors, microstructural signals, and behavioral feedback [4–6], making forecasting far more challenging than conventional time series. Driven by the exponential growth of data and breakthroughs in computational power and AI techniques, the asset management industry is transitioning from experience-driven to data-driven paradigms. Within this shift, quantitative investing is becoming mainstream due to: (i) efficient decision-making via the data–factor–model loop, (ii) repeatable execution with integrated risk control, and (iii) precise pursuit of excess returns under increasing strategy convergence [7, 8].

Fig. 1 illustrates the modern quantitative research pipeline. Microsoft’s open-source project Qlib [9] streamlines data processing and backtesting, alleviating much of the repetitive engineering burden. Consequently, this shift redirects the focus of quantitative research toward its core components: factor mining and model innovation. Factor mining progresses from closed-form risk–return models [10, 11] such as Fama–French to evolutionary symbolic regression [12–14] and, more recently, reinforcement learning optimization of factor combinations [15– 17]. Model innovation evolves from classical autoregression [18, 2] to machine learning models [19–21] and sequence-to-sequence deep learning architectures (e.g., GRU [22] and LSTM [23]). More recent developments include specialized time series models that decompose signals into trend–seasonal components [24] or improve attention mechanisms for long-range forecasting [25].

In parallel, stock-specific models integrate temporal event sequences with cross-sectional dependencies via graph neural networks to capture inter-stock interactions [26–28]. Recently, large language models (LLMs) and multi-agent systems further extend the information set by extracting signals from news and social networks [29–31], and simulating hedge funds and collaboration among financial experts [32–34].

Despite these advances, quantitative research still faces three critical limitations: (i) Limited automation: Current workflows require extensive human intervention in hypothesis genera-

![](images/3a7b46f0751722ff25236e66e601062444470a40a40eabc12b90e99e1611f630.jpg)  
Figure 1: Quantitative finance research pipeline. Qlib makes stages ❶ and ❹ easier. R&D-Agent(Q) further automates stages ❷, ❸, and ❺, which are also key aspects of quantitative research.

tion, coding, and tuning, creating slow iterations and biases, Besides, semi-automated systems fail to achieve the responsiveness and scalability required for fast-moving markets. (ii) Poor interpretability: Existing LLM-based agents often produce trading signals directly from language interaction, without grounded factor construction or transparent model logic, and thus are prone to hallucinations. This hinders adoption in live trading, where explainability and risk controls are essential. (iii) Fragmented optimization: Quantitative pipelines span data processing, factor mining, model training, and evaluation, yet current approaches lack systematic task decomposition or agent-level coordination. This siloed structure limits cross-stage feedback and joint performance gains.

To address these challenges, we propose R&D-Agent(Q), the first data-centric multiagent framework for automating full-stack quantitative strategy development via coordinated factor–model co-optimization (Fig. 2). Our framework decomposes quant research into five stages spanning two core phases: Research and Development. In the Research phase, the Specification Unit dynamically generates goalaligned prompts from optimization targets. The

![](images/924f326212d5ce9770d05147a150bbfbeb151b6ed9502d432b210a96ab3cc9e5.jpg)  
Figure 2: Conceptual diagram of R&D-Agent(Q). The modules R&D-Factor and R&D-Model represent the full optimization loops for factor and model development, respectively.

Synthesis Unit then grows a task-specific knowledge forest from prior outcomes and generates new factor or model hypotheses, which are then mapped to executable tasks. In the Development phase, we introduce Co-STEER, a code-generation agent leveraging chain-of-thought [35] reasoning and a graph-based knowledge store. The Implementation Unit translates hypotheses into code, while the Validation Unit runs real-market backtests.The Analysis Unit evaluates with unified metrics and uses a multi-armed bandit scheduler to adaptively select the next optimization direction. This forms a closed hypothesis–implementation–validation–feedback loop that supports continual, goal-directed evolution of strategies, marking a step toward intelligent and autonomous quantitative research.

Our main contributions are as follows:

• End-to-end automation with transparency: R&D-Agent(Q) is the first data-centric multi-agent framework in quantitative finance that automates the entire R&D process with verifiable outputs that enhance interpretability and reduce hallucination risks.

• High-performance R&D tools: In the Research stage, R&D-Agent(Q) mimics analyst workflows via a structured knowledge forest, enabling the generation of coherent, high-quality hypotheses. In the Development stage, we propose Co-STEER, a knowledge-evolving agent tailored for datacentric tasks, improving the accuracy and efficiency of factor and model code generation.

• Strong empirical performance: Extensive experiments in real stock markets show that, at a cost under \$10, R&D-Agent(Q) achieves approximately 2× higher ARR than benchmark factor libraries while using over 70% fewer factors. It also surpasses state-of-the-art deep time-series models under smaller resource budgets. Its alternating factor–model optimization further delivers excellent trade-off between predictive accuracy and strategy robustness.

## 2 R&D-Agent(Q)

Based on the formal quantitative research pipeline structure in Fig.1 and AppendixB, we propose R&D-Agent(Q), a data-centric multi-agent framework for iterative factor-model R&D with automation, interpretability, and efficiency. We decompose the quantitative process into five LLM-powered units, each mainly focused on information gathering and LLM API interactions: Specification (scenario definition), Synthesis (ideas generation), Implementation (code development), Validation (backtesting), and Analysis (result evaluation and task scheduling). Under unified input–output constraints, these units operate in a closed-loop cycle that simulates the trial-and-error process of human quantitative researchers. Unlike manual workflows, R&D-Agent(Q) runs continuously and autonomously, supporting dynamic co-optimization of factor and model components. Moreover, each round’s hypotheses, implementations, and results are persistently stored, enabling cumulative knowledge growth and increasingly informed decision-making over time.

![](images/a7275b85eeea076ef4da91400734063bace1f894168ae9dd4fdd0be30ea60b06.jpg)  
Figure 3: R&D-Agent(Q) consists of five functional modules that collaborate in a continuous iterative loop to generate highly effective quantitative factors and models for real-world financial markets.

## 2.1 Specification Unit

The Specification Unit serves as the top-level component of the R&D-Agent(Q), dynamically configuring task context and constraints for downstream modules, ensuring consistency across design, implementation, and evaluation. It operates along two axes: ❶ Theoretical ➙ encoding prior assumptions, data schemas, and output protocols into a structured specification; ❷ Empirical ➙ establishing a verifiable execution environment and standardized interfaces for backtesting, shielding agents from low-level preprocessing and infrastructure concerns. By combining formal definitions with unified interfaces, the module reduces ambiguity and improves coordination efficiency across components.

We formalize the Specification Unit as a tuple $\boldsymbol { \mathcal { S } } = ( B , \mathcal { D } , \mathcal { F } , \mathcal { M } )$ , where B encodes background assumptions and prior knowledge about factors or models; D defines the market data interface; $\mathcal { F }$ expected output format (e.g., factor tensors or return predictions); and M denotes the external execution environment (e.g., Qlib-based backtesting). Under this formulation, any candidate factor or model $f _ { \theta }$ must satisfy the condition that $\forall , x \in { \bar { \mathcal { D } } } , ; f _ { \theta } ( x ) \in { \mathcal { F } }$ and $f _ { \theta }$ is executable within M. This enforces compatibility with standardized input/output structures and ensures that subsequent modules can interact with $f _ { \theta }$ within a shared operational context, thereby supporting consistency and reproducibility across collaborative workflows. Implementation details are provided in Appendix E.1.

## 2.2 Synthesis Unit

The Synthesis Unit simulates human-like reasoning by generating new hypotheses based on historical experiments. Each optimization action is defined as $a _ { t } \in \{ \mathrm { f a c t o r , m o d e l } \}$ . For the current action ${ { a } _ { t } } ,$ the unit constructs an experiment trajectory by selecting a subset of relevant historical experiments. The t-th experiment is denoted by $e ^ { t } = \{ h ^ { t } , f ^ { \check { t } } \}$ , where ${ \bf \bar { \boldsymbol { h } } } ^ { t }$ is the hypothesis and $f ^ { t }$ is the corresponding feedback from the Analysis Unit. A set of current best-performing solutions is maintained as SOTA. Based on this, the historical hypothesis and feedback sets are defined as $\mathcal { H } _ { t } = \{ h _ { 1 } , \ldots , h _ { t } \}$ and $\mathcal { F } _ { t } = \{ f _ { 1 } , \ldots , f _ { t } \}$ , respectively. Action-conditioned subsets are then extracted as Eq. (1).

$$
\begin{array} { r l } & { \mathcal { F } _ { t } ^ { ( a ) } = \{ f _ { i } ^ { a } \in \mathcal { F } _ { t } \mid a = a _ { t } \lor e _ { i } \in \mathrm { S O T A } ( a ) \} } \\ & { \mathcal { H } _ { t } ^ { ( a ) } = \{ h _ { i } ^ { a } \in \mathcal { H } _ { t } \mid a = a _ { t } \lor h _ { i } \in \mathrm { S O T A } ( a ) \} } \end{array}\tag{1}
$$

These subsets are passed to a generative stochastic mapping G (serving as the core of Research, mimicking the synthesis of theoretical priors and empirical feedback to generate valid and novel hypotheses) to produce the next hypothesis: $h ^ { ( t + 1 ) } = G ( \mathcal { H } _ { t } ^ { ( a ) } , \mathcal { F } _ { t } ^ { ( a ) } )$ . In practice, this module relies on structured templates and standardized formats to ensure that hypotheses are both executable and scientifically grounded. For example, in a factor generation task, $h ^ { ( t + 1 ) }$ incorporates not only the most recent feedback but also current market conditions and domain-specific economic theory, ensuring the factor’s validity and observability. To promote diversity and progressive refinement, the generation mechanism adapts its strategy based on performance feedback. If $\mathcal { F } _ { t } ^ { ( a ) }$ suggests success, the next hypothesis increases in complexity or scope; otherwise, it undergoes structural adjustments or introduces novel variables, thereby constituting an idea forest. This adaptive mechanism enables the agent to explore new directions while maintaining responsiveness to empirical results, supporting iterative and effective strategy development.

Finally, the hypothesis $h ^ { t }$ is instantiated into a concrete task $t ^ { t } ,$ , which the downstream implementation module uses for code-level realization. Factor hypotheses $h _ { t } ^ { \mathrm { f a c t o r } }$ , due to their heterogeneity and potential interactions, can be decomposed into multiple subtasks $t _ { i } ^ { \mathrm { f a c t o r } }$

In contrast, model hypotheses, given their structural coherence, are mapped to a single task tmodel responsible for executing the entire modeling and inference pipeline.

## 2.3 Implementation Unit

The Implementation Unit is responsible for translating the executable tasks generated by the Synthesis Unit into functional code. It forms the core of complex development within the R&D-Agent(Q). To support this process, we design a specialized agent, Co-STEER, tailored for factor and model development in quantitative research. As illustrated in Fig. 4, Co-STEER integrates systematic scheduling and code-generation strategies to ensure correctness, efficiency, and adaptability in implementation.

![](images/88902ad71f9c8edb0c6f8686cd3e2266a0a4694a08be876ca84ce97245307ca7.jpg)  
Figure 4: Diagram of the Co-STEER workflow. In the context of factor development, it consists of two main modules: the scheduling module ingests candidate tasks and performs iterative ranking based on multiple factors; the implementation module learns from previous code execution results to construct a fine-grained, transferable knowledge base applicable across tasks.

In factor development, tasks often exhibit structural dependencies. To address this, we introduce a guided chain-of-thought mechanism that encourages reasoning traceability. Specifically, the agent constructs a directed acyclic graph $\left( \mathrm { D A G } \right) \mathcal { G } = \left( \mathcal { V } , \mathcal { \bar { E } } \right)$ to represent task dependencies, where an edge from task A to task B implies that A should precede B due to knowledge flow or complexity. A topological ordering $\pi _ { S } = \left( t _ { ( 1 ) } , \ldots , t _ { ( n ) } \right)$ is then derived to guide task execution. Scheduling is adaptive. Feedback from previous executions is continually integrated to improve planning: repeated failures on a task signal increased complexity, prompting prioritization of simpler tasks to enhance knowledge accumulation and execution success.

For each task $t _ { j }$ , the implementation agent I generates its corresponding code $c _ { j }$ based on both the task description and the current knowledge base, thus $c _ { j } = I ( t _ { j } , \boldsymbol { \kappa } )$ This process includes task parsing, code synthesis and refinement, execution, and validation. The agent’s objective is to maximize cumulative implementation quality: πI = arg maxπ E $\left\lceil \sum _ { j = 1 } ^ { n } R _ { I } ( c _ { j } ) \right\rceil$ , where $R _ { I } ( c _ { j } )$ evaluates the correctness and performance of code $c _ { j }$ . The knowledge base K plays a central role by recording successful and failed task-code-feedback triples: $\boldsymbol { K } ^ { ( t + 1 ) } = \boldsymbol { K } ^ { ( t ) } \cup \{ ( t _ { j } , c _ { j } , f _ { j } ) \}$ , where $f _ { j }$ denotes the feedback received after executing task $t _ { j }$ . Through a knowledge transfer mechanism, the implementation agent can also retrieve solutions to similar tasks from the knowledge base based on the current feedback $f ^ { ( t ) }$ , thereby improving the efficiency and success rate of code generation for new tasks: cnew = arg maxck∈K similarity $\left( t _ { n e w } , t _ { k } \right) \cdot c _ { k }$ . The complete algorithmic details are provided in Appendix A.1.

This feedback-driven optimization loop allows the Implementation Unit to continually enhance code quality and efficiency, facilitating rapid and robust development of quantitative research components.

## 2.4 Validation Unit

The Validation Unit evaluates the practical effectiveness of factors or model generated by the Implementation Unit. For factors, a de-duplication process is first applied to filter out redundant signals by computing their correlation with the existing SOTA factor library. Given the concatenated factor matrix $\dot { \mathbf { F } } = [ \bar { F } _ { \mathrm { S O T A } } , F _ { \mathrm { n e w } } ] \in \mathbb { R } ^ { T \times ( M + N ) }$ , the IC is computed within each time slice between all $M \times N$ pairs of SOTA and new factors: $\mathrm { I C } _ { m , n } ^ { ( t ) } = \operatorname { c o r r } ( F _ { \mathrm { S O T A } , m } ^ { ( t ) } , F _ { \mathrm { n e w } , n } ^ { ( t ) } )$ , where $( m , n )$ indexes a SOTA-new pair, and t indexes a time slice. These IC values are then averaged across time, and for each new factor n, its maximum IC across all SOTA factors is obtained as $\operatorname { I C } _ { \operatorname* { m a x } } ^ { ( n ) } = \operatorname* { m a x } _ { m } \ \mathbb { E } _ { t } \left[ \operatorname { I C } _ { m , n } ^ { ( t ) } \right]$

New factors with $\mathrm { I C } _ { \operatorname* { m a x } } ^ { ( n ) } \geq 0 . 9 9$ are deemed redundant and excluded. After factor filtering, the remaining candidates are combined with the current SOTA model (or a baseline model, if none is available) and evaluated through the Qlib backtesting platform. This allows performance to be assessed under realistic market conditions. For model, the process is symmetric: each candidate model is paired with the current SOTA factor set and evaluated through the same backtesting pipeline.

Therefore, the Validation Unit provides an integrated and automated pipeline that supports standardized evaluation of novel components within a production-grade market simulation environment.

## 2.5 Analysis Unit

The Analysis Unit serves as both a research evaluator and strategy analyst within the R&D-Agent(Q) framework. After each experimental round, it conducts a multi-dimensional assessment of the current hypothesis $h ^ { t } .$ , the specific task $t ^ { t } .$ , and the experimental result $r ^ { t }$ . If the experiment is judged to outperform the SOTA under action type $a _ { t } .$ , its result is added to the corresponding SOTA set $\mathrm { S O T A } \bar { ( } a _ { t } )$ . The unit then diagnoses failure strategy and generates targeted suggestions for refinement. The feedback $f _ { t }$ is passed to the Synthesis Unit to guide the formulation of future hypotheses.

Notably, the Analysis Unit operates with a local view of the current experiment, while the Synthesis Unit maintains a global perspective across the full experimental history. Their interaction enables a closed-loop system that balances short-term responsiveness with long-term exploration, supporting automated iteration across research design, strategy implementation, validation, and deep analysis.

Following each analysis round, the Analysis Unit further determines whether to prioritize factor refinement or model optimization for the next iteration. To maximize performance gains, this decision is formulated as a contextual two-armed bandit problem and solved via linear Thompson sampling (see Appendix A.2 for the detailed algorithm). Specifically, At each round $t ,$ the system observes an 8-dimensional performance state vector $\mathbf { x } _ { t } \in \mathbb { R } ^ { 8 }$ , which encodes key evaluation metrics of the current strategy. The action space is A = {factor, model}, corresponding to the two possible optimization paths. To evaluate the expected benefit of each action under context $\mathbf { x } _ { t } .$ we adopt a linear reward function $r = \mathbf { w } \mathbf { \theta } ^ { \mid } \mathbf { x } _ { t } ,$ where w reflects the relative importance of each metric. A separate Bayesian linear model is maintained for each action, with Gaussian posteriors encoding uncertainty over reward coefficients. At each step, the system samples a reward vector from each posterior and computes the corresponding expected reward. The action with the highest sampled reward is executed. After observing the actual improvement, the posterior for the chosen arm is updated. Through this contextual Thompson sampling mechanism, R&D-Agent(Q) adaptively balances exploration and exploitation, enabling robust performance improvement across iterations.

## 3 Experimental Setup

➥ Datasets. Following [36–39], we use the CSI 300 dataset, covering 300 large-cap A-share stocks in the Chinese market. The time span is split into training (Jan 1, 2008 – Dec 31, 2014), validation (Jan 1, 2015 – Dec 31, 2016), and testing (Jan 1, 2017 – Aug 1, 2020). We evaluate R&D-Agent(Q) under three configurations: ➊ R&D-Factor fixes the prediction model as LightGBM [40] and optimizes factor sets starting from Alpha 20 3; ➋ R&D-Model fixes the input factor set to Alpha 20 and searches for better models; ➌ R&D-Agent(Q) jointly optimizes both factor and model components.

➥ Baselines. At the factor level, we compare against Alpha 101 [41], Alpha 158 [42], Alpha 360 [43], and AutoAlpha [44]. At the model level, we include machine learning models (Linear, MLP, LightGBM[40], XGBoost [45], CatBoost [46], DoubleEnsemble [47]), and deep learning models (GRU [22], LSTM [23], ALSTM [48], Transformer [49], PatchTST [50], iTransformer [51], Mamba [52], TRA [38], MASTER [39], GATs [53]). More details are provided in Appendix C.3.

➥ Evaluation Details. We evaluate R&D-Agent(Q) using two metric categories: factor predictive metrics, including information coefficient (IC), IC information ratio (ICIR), rank IC, and rank ICIR; and strategy performance metrics, including annualized return (ARR), information ratio (IR), maximum drawdown (MDD), and Calmar ratio (CR). We follow a daily long-short trading strategy based on predicted return rankings, with position updates, holding retention rules, and realistic transaction costs. Full evaluation and implementation details are provided in Appendix C.4 and C.1.

## 4 Experiment Analysis

➥ Analyses of Main Results. Table 1 reports the performance of baseline models and R&D-Agent frameworks on the CSI 300 dataset, showing that the R&D-Agent consistently outperform all baselines in both predictive and strategic metrics.

➊ R&D-Factor (Factor Optimization). When only the factor space is adaptively optimized, both R&D-FactorGPT-4o and R&D-Factoro3-mini surpass static factor libraries (e.g., Alpha 158/360) with higher IC (up to 0.0497) and significantly improved ARR (up to 14.61%) using fewer handcrafted factors. This demonstrates that dynamic hypothesis refinement and factor screening in R&D-Agent(Q) lead to more informative signals than those from fixed, high-dimensional factor sets.

➋ R&D-Model (Model Optimization). For model optimization with fixed factors, R&D-Modelo3-mini surpasses all baseline and achieves best performance on Rank IC(0.0546) and MDD (−6.94%). Machine learning models lag significantly, highlighting their limitations in capturing financial noisy and non-linear patterns. While general deep learning architectures (GRU, LSTM, Transformer) deliver moderate predictive metrics, their strategic performance remains weak, suggesting a gap between feature extraction and actionable returns. Surprisingly, time-series forecasting models (e.g. PatchTST, Mamba) underperform on both fronts, indicating a fundamental mismatch between standard sequence prediction and stock market dynamics. In contrast, specialized stock prediction models (TRA, MASTER) excel in strategic metrics but trail in predictive power, highlighting a trade-off between robustness (low MDD, high IR) and precision (high IC). These results shows that adaptive model configuration—guided by automated hypothesis evaluation—yields more robust and risk-sensitive forecasting structures than both ML and handcrafted DL architectures.

➌ R&D-Agent(Q) (Joint Optimization). By co-optimizing factors and models, R&D-Agent(Q)o3-mini achieves the highest overall performance: an IC of 0.0532, ARR of 14.21%, and IR of 1.74. These improvements exceed those of the strongest baseline methods (e.g., Alpha 158, TRA) by a large margin. This demonstrates that joint refinement of factors and architectures unlocks complementary improvements, enabling scalable and consistent alpha modeling.

➥ Analyses of Research Component. To evaluate the research dynamics of R&D-Agent(Q), we analyze the evolution of factor hypotheses in R&D-Factor, focusing on its balance between exploration (diverse idea generation) and exploitation (local refinement). The methodology involves three steps: (i) Text Embedding: Encode generated hypothesis $h _ { t }$ at iteration t into a fixed-dimensional vector ht using Sentence-BERT [54]; (ii) Similarity matrix: Compute pairwise cosine similarities to form a symmetric matrix $\mathbf { S } \in [ \bar { 0 } , 1 ] ^ { \mathbf { \dot { T } } \times \hat { T } }$ ; (iii) Hierarchical Clustering: Apply agglomerative clustering to group similar hypotheses and reorder S for block structure.

Table 1: Experimental results of all models on the CSI 300 constituent stock dataset, including factor predictive metrics and strategy performance metrics. Visual cues indicate ranking groups: Best , Second Best , Good (3–8) , Average (9–14) , Poor (15–20) , and Worse (21–26) .
<table><tr><td rowspan="3" colspan="2">Models</td><td colspan="8">CSI300</td></tr><tr><td colspan="4">Factor Predictive Power Metrics</td><td colspan="4">Performance Metrics</td></tr><tr><td>IC</td><td>ICIR</td><td>Rank IC</td><td>Rank ICIR</td><td>ARR</td><td>IR (SHR*)</td><td>MDD</td><td>CR</td></tr><tr><td rowspan="6">Machine-Learning Models</td><td>Linear MLP</td><td>0.0134 0.0291</td><td>0.0992 0.2096</td><td>0.0273</td><td>0.1962</td><td>-0.0302 0.0003</td><td>-0.3710</td><td>-0.1987 -0.1390</td><td>-0.1520</td></tr><tr><td></td><td>0.0277</td><td></td><td>0.0412</td><td>0.3238</td><td></td><td>0.0037</td><td></td><td>0.0022</td></tr><tr><td>LightGBM</td><td></td><td>0.2211</td><td>0.0386</td><td>0.3120</td><td>0.0397</td><td>0.5664</td><td>-0.0855</td><td>0.4643</td></tr><tr><td>XGBoost</td><td>0.0291</td><td>0.2410</td><td>0.0384</td><td>0.3257</td><td>0.0316</td><td>0.4620</td><td>-0.1139</td><td>0.2774</td></tr><tr><td>CatBoost</td><td>0.0279</td><td>0.2181</td><td>0.0393</td><td>0.3110</td><td>0.0513</td><td>0.7008</td><td>-0.0924</td><td>0.5552</td></tr><tr><td>DoubleEnsemble</td><td>0.0294</td><td>0.2246</td><td>0.0417</td><td>0.3211</td><td>0.0551</td><td>0.7968</td><td>-0.0971</td><td>0.5675</td></tr><tr><td rowspan="8">Deep-Learning Models</td><td>Transformer</td><td>0.0317</td><td>0.2538</td><td>0.0434</td><td>0.3624</td><td>0.0293</td><td>0.4267</td><td>-0.0987</td><td>0.2969</td></tr><tr><td>GRU</td><td>0.0315</td><td>0.2450</td><td>0.0428</td><td>0.3440</td><td>0.0344</td><td>0.5160</td><td>-0.1017</td><td>0.3382</td></tr><tr><td>LSTM</td><td>0.0318 0.0362</td><td>0.2367</td><td>0.0435</td><td>0.3389</td><td>0.0381</td><td>0.5561</td><td>-0.1207</td><td>0.3157</td></tr><tr><td>ALSTM</td><td>0.0349</td><td>0.2789</td><td>0.0463</td><td>0.3661</td><td>0.0470</td><td>0.6992</td><td>-0.1072</td><td>0.4384</td></tr><tr><td>GATs</td><td></td><td>0.2511</td><td>0.0462</td><td>0.3564</td><td>0.0497</td><td>0.7338</td><td>-0.0777</td><td>0.6396</td></tr><tr><td>PatchTST</td><td>0.0247 0.0270</td><td>0.1945</td><td>0.0315</td><td>0.2463</td><td>0.0571</td><td>0.7191</td><td>-0.1327</td><td>0.4303</td></tr><tr><td>iTransformer Mamba</td><td>0.0281</td><td>0.1946 0.2244</td><td>0.0340 0.0374</td><td>0.2365 0.2952</td><td>0.0979 0.0229</td><td>1.2337</td><td>-0.1151</td><td>0.8506</td></tr><tr><td>TRA</td><td>0.0404</td><td>0.3197</td><td>0.0490</td><td>0.4047</td><td>0.0649</td><td>0.3163 1.0091</td><td>-0.1154 -0.0860</td><td>0.1984 0.7547</td></tr><tr><td rowspan="5">Factor Libraries</td><td>MASTER</td><td>0.0215</td><td>0.1925</td><td>0.0296</td><td>0.2486</td><td>0.0896</td><td>1.3406</td><td>-0.0851</td><td>1.0528</td></tr><tr><td>Alpha 101</td><td>0.0308</td><td>0.2588</td><td>0.0331</td><td>0.2749</td><td>0.0512</td><td>0.5783</td><td>-0.1253</td><td>0.4085</td></tr><tr><td>Alpha 158</td><td>0.0341 0.0420</td><td>0.2952</td><td>0.0450</td><td>0.3987</td><td>0.0570</td><td>0.8459</td><td>-0.0771</td><td>0.7393</td></tr><tr><td>Alpha 360</td><td>0.0334</td><td>0.3290</td><td>0.0514</td><td>0.4225</td><td>0.0438</td><td>0.6731</td><td>-0.0721</td><td>0.6074</td></tr><tr><td>AutoAlpha</td><td></td><td>0.2656</td><td>0.0361</td><td>0.2967</td><td>0.0400</td><td>0.4288</td><td>-0.1225</td><td>0.3266</td></tr><tr><td rowspan="6">R&amp;D-Agent Series Framework*</td><td> ${ \mathrm { R } } \& { \mathrm { D - F a c t o r } _ { \mathrm { G P T - 4 0 } } }$ </td><td>0.0489</td><td>0.4050</td><td>0.0521</td><td>0.4425</td><td>0.1461</td><td>1.6835</td><td>-0.0750</td><td>1.9468</td></tr><tr><td> ${ \mathrm { R } } \& { \mathrm { D - F a c t o r } _ { \mathrm { o 3 - m i n i } } }$ </td><td>0.0497</td><td>0.3931</td><td>0.0500</td><td>0.4246</td><td>0.1184</td><td>1.3566</td><td>-0.0910</td><td>1.3016</td></tr><tr><td> $\mathrm { R } \& \mathrm { D - M o d e l _ { G P T - 4 o } }$ </td><td>0.0326</td><td>0.2305</td><td>0.0401</td><td>0.2767</td><td>0.1229</td><td>1.6676</td><td>-0.0876</td><td>1.4029</td></tr><tr><td> $\mathrm { R } \& \mathrm { D - M o d e l _ { 0 3 - m i n i } }$ </td><td>0.0469</td><td>0.3688</td><td>0.0546</td><td>0.4385</td><td>0.1009</td><td>1.7009</td><td>-0.0694</td><td>1.4538</td></tr><tr><td> $\mathrm { R \& D \mathrm { - A g e n t ( Q ) _ { G P T \cdot 4 o } } }$ </td><td>0.0497</td><td>0.4069</td><td>0.0499</td><td>0.4122</td><td>0.1144</td><td>1.3167</td><td>-0.0811</td><td>1.4108</td></tr><tr><td> ${ \mathrm { R } } \& { \mathrm { D } } { \mathrm { D } } { \mathrm { - A g e n t ( Q ) _ { \mathrm { o 3 - m i n i } } } }$ </td><td>0.0532</td><td>0.4278</td><td>0.0495</td><td>0.4091</td><td>0.1421</td><td>1.7382</td><td>-0.0742</td><td>1.9150</td></tr></table>

Fig. 5 reveals three exploration patterns: ➊ Local refinement followed by directional shift: Diagonal blocks (e.g., trials 1–6, 7–11) show that R&D-Factor performs multi-step refinement within a conceptual thread before shifting direction, balancing depth with novelty. ➋ Strategic revisitation: Trial 26 clusters with earlier trials 12–14, demonstrating the agent’s ability to revisit and incrementally refine promising early hypotheses. ➌ Diverse paths yield synergy: 8 out of 36 trials are selected into the final SOTA set, spanning 5 of 6 clusters. This suggests that exploring multiple directions produces complementary signals that collectively strengthen the final factor library. This refine–shift–reuse pattern underpins efficient deep search and broad conceptual coverage, enabling the construction of compact, diverse, and high-performing factor libraries.

Factor ldea Similarity Landscape  
![](images/1b50945c4fdf0bd74595bfbdcf9bbdbdab3d40ee9f3ad2b9067248c9ad4081f3.jpg)  
Figure 5: Cosine similarity heatmap of factor hypotheses across experiment loops in R&D-Factor. Black boxes mark clusters of similar ideas; RED indices indicate those selected into the SOTA factor library.

## ➥ Analyses of Development Component.

To evaluate the code generation capability of the development component, we analyze Co-STEER’s performance across frameworks of R&D-Agent(Q) using the pass@k accuracy metric (Fig. 6). In both factor and model tasks, success rates quickly converge within a few iterations, showing Co-STEER’s ability to efficiently repair initial errors through feedback. The difference is amplified in full-stack tasks (R&D-Agent(Q)) due to their greater complexity, making iterative refinement essential. Here, o3-mini consistently achieves higher recovery rates, reflecting its stronger chainof-thought reasoning—a clear advantage in structured, high-dependency coding scenarios. Overall, the pass@k trajectory illustrates Co-STEER’s ability to progressively self-correct through iterative refinement in structured financial coding. Additional experiments on Co-STEER are available in Appendix D.4.

![](images/6184aec603eaf58574f461ccea3211e99f4840ae63890e2e429bd252e6d147c5.jpg)

![](images/83f3cf888931164d05de8521003472b5697109f335319ab3ca950fa7800a0781.jpg)

![](images/683887dbaf618aec03e236310e54bdc475ddc4f41bf8df30a2148776f5d76bc2.jpg)  
Figure 6: Pass@k accuracy of GPT-4o and o3-mini in R&D-Factor, R&D-Model, and R&D-Agent(Q). x-axis: attempts (k); y-axis: success rate within k tries.

➥ Analyses of Factor Effects. In Fig. 7, we compare factor libraries produced by R&D-Factor with baselines to assess factor generation. Subfigures (a) and (b) show that even when initialized from Alpha 20, R&D-Factor quickly achieves IC levels comparable to Alpha 158 and Alpha 360 while using only 22% of factors. After 2017, it consistently outperforms Alpha 20, and maintains stable IC during 2019–2020 when baselines degrade. When initialized from Alpha 158, R&D-Factor further improves, particularly with o3-mini, reaching IC >0.07 in 2020 and surpassing all baselines. This demonstrates that iterative factor refinement helps eliminate regime-sensitive or redundant signals, improving overall predictive stability. More relevant results are provided in Appendix D.3.

➥ Analyses of Model Effects. Fig. 8 compares R&D-Model with baseline deep learning models across three dimensions: ARR, MDD, and resource usage. Both R&D-Model variants shift significantly toward the desirable upper-left region. R&D-ModelGPT-4o achieves ARR (12%) with |MDD| (8%), attaining the highest return-risk slope. R&D-Model ${ \tt o } 3 \mathrm { - } \mathtt { m i n i }$ offers lower drawdown with ARR (11%), yielding strong performance under tighter risk constraints.

![](images/423411f367567555b97c40eb1f9e4c1385fdd519c82957c2df4cd431d243b715.jpg)

![](images/2ba4ddb045d3d05b5121396f3c3a6a90932e5d2dc41fb2a65429bb0a22f59a3d.jpg)

![](images/ff0640d8a07241192884416036dd294dfd5e4e6e4f762ca563743e345909d10a.jpg)  
Figure 7: Comparison between classical factor libraries and R&D-Factor-generated factors using a LightGBM predictor on CSI 300. R&D-Factor was initialized from Alpha 20 or Alpha 158 and operated with GPT-4o or o3-mini.  
Figure 8: Comparison of models on CSI 300 in terms of return, drawdown, and resource efficiency. Bubble size encodes memory usage (MB); labels show memory and inference latency (ms). Line slope indicates Calmar Ratio.

Analyses of Empirical Scope and Generalizability. To address concerns about scope, recency, and data leakage, we extended evaluation to another major Chinese market (CSI 500) and the U.S. market (NASDAQ 100). We adopted new dataset splits (Train: 2008-2021, Validation: 2022-2023, Test: 2024-2025), ensuring that both LLM backends have cutoffs completely or nearly prior to the test period. The detailed experimental settings and the complete results are provided in D.1.

Moreover, our framework adopts a data-centric design: the LLM is never exposed to raw market data or explicit temporal splits, but only to schema-level information (as shown in the prompt for the Specification Unit in Appendix E.1). This prevents the model from accessing precise temporal boundaries or dataset partitions, thereby mitigating the risk of information leakage.

As summarized in Table 2, R&D-Agent(Q) consistently achieves top-ranked performance across both Chinese and U.S. markets, with strong out-of-sample robustness in IC, ICIR, IR (SHR\*), and MDD. These findings confirm that our framework generalizes beyond the Chinese market, captures recent dynamics, and remains unaffected by knowledge cutoff concerns, thereby reinforcing its robustness and real-world applicability.

Table 2: Out-of-sample experimental results on the CSI 500 and NASDAQ 100 (both tested from 2024 to June 2025), including factor predictive metrics (IC, ICIR) and strategy performance metrics (IR, MDD). Visual cues indicate ranking groups: Best , Second Best , Good (3–5) , Average (6–10) , Poor (11–15) , and Worse (16–19) .
<table><tr><td rowspan="2" colspan="2">Models</td><td colspan="4">CSI500</td><td colspan="4">NASDAQ100</td></tr><tr><td>IC</td><td>ICIR</td><td>IR (SHR*)</td><td>MDD</td><td>IC</td><td>ICIR</td><td>IR (SHR*)</td><td>MDD</td></tr><tr><td rowspan="3">Machine-Learning Models</td><td>LightGBM XGBoost</td><td>0.0181 0.0240</td><td>0.1271 0.1675</td><td>-0.3178</td><td>-0.2089 -0.1766</td><td>0.0080 0.0076</td><td>0.0652 0.0527</td><td>-0.2603</td><td>-0.1342</td></tr><tr><td></td><td></td><td></td><td>0.0634</td><td></td><td></td><td></td><td>0.1544</td><td>-0.1211</td></tr><tr><td>CatBoost DoubleEnsemble</td><td>0.0241 0.0248</td><td>0.1629 0.1705</td><td>0.1438 0.2500</td><td>-0.1799 -0.2094</td><td>0.0095 0.0047</td><td>0.0614 0.0360</td><td>-0.0735 -0.0046</td><td>-0.1148 -0.1404</td></tr><tr><td rowspan="5">Deep-Learning Models</td><td>Transformer</td><td>0.0194</td><td>0.1355</td><td>0.2898</td><td>-0.1331</td><td>-0.0011</td><td>-0.0077</td><td>-0.0343</td><td>-0.1553</td></tr><tr><td>GRU</td><td>0.0188</td><td>0.1022</td><td>0.3716</td><td>-0.1602</td><td>0.0064</td><td></td><td>0.2930</td><td>-0.1504</td></tr><tr><td></td><td></td><td></td><td>0.6900</td><td></td><td></td><td>0.0457</td><td></td><td></td></tr><tr><td>LSTM GATs</td><td>0.0219</td><td>0.1434 0.1013</td><td></td><td>-0.1075</td><td>0.0062</td><td>0.0409</td><td>0.4526</td><td>-0.1204</td></tr><tr><td>iTransformer</td><td>0.0162 0.0161</td><td>0.1031</td><td>0.5168 0.0985</td><td>-0.1569 -0.1496</td><td>-0.0004 0.0076</td><td>-0.0023 0.0421</td><td>0.5772 0.3612</td><td>-0.1491 -0.1991</td></tr><tr><td rowspan="3">Factor Libraries</td><td>TRA</td><td>0.0260</td><td>0.1813</td><td>0.6040</td><td>-0.1461</td><td>0.0058</td><td>0.0446</td><td>0.4608</td><td>-0.1351</td></tr><tr><td>Alpha 158</td><td></td><td>0.1353</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Alpha 360</td><td>0.0192 0.0195</td><td>0.1331</td><td>0.2515 0.2527</td><td>-0.1771 -0.1270</td><td>0.0040 0.0042</td><td>0.0324 0.0327</td><td>0.0303 0.5890</td><td>-0.1140 -0.1182</td></tr><tr><td rowspan="6">R&amp;D-Agent Series Framework*</td><td>AutoAlpha</td><td>0.0184</td><td>0.1529</td><td>0.5728</td><td>-0.1006</td><td>0.0046</td><td>0.0265</td><td>0.0974</td><td>-0.1165</td></tr><tr><td>R&amp;D-Factor (GPT-4o)</td><td>0.0201</td><td>0.1709</td><td>1.3730</td><td>-0.0787</td><td>0.0070</td><td>0.0446</td><td>1.0985</td><td>-0.0977</td></tr><tr><td>R&amp;D-Factor (o4-mini)</td><td>0.0264</td><td>0.2652</td><td>1.0014</td><td>-0.1215</td><td>0.0166</td><td>0.1017</td><td>1.1169</td><td>-0.0650</td></tr><tr><td>R&amp;D-Model (GPT-4o)</td><td>0.0259</td><td>0.1649</td><td>1.0941</td><td>-0.1367</td><td>0.0128</td><td>0.0831</td><td>1.0742</td><td>-0.0842</td></tr><tr><td>R&amp;D-Model(o4-mini)</td><td>0.0265</td><td>0.1825</td><td>1.4021</td><td>-0.0735</td><td>0.0081</td><td>0.0484</td><td>1.2671</td><td>-0.0741</td></tr><tr><td>R&amp;D-Agent(Q)(GPT-4o) R&amp;D-Agent(Q)(o4-mini)</td><td>0.0241</td><td>0.1532 0.1828</td><td>1.4227 2.1721</td><td>-0.0803 -0.0656</td><td>0.0172 0.0162</td><td>0.0908 0.1035</td><td>1.3312 1.7737</td><td>-0.1044 -0.0634</td></tr></table>

➥ Ablation Study. To evaluate the impact of different action selection strategies, we conduct an ablation study as shown in Table 3. The Bandit scheduler achieves the best overall performance, with the highest IC, ARR, and number of SOTA selections, confirming its ability to prioritize the most promising optimization targets under limited computational budgets. The LLM-based strategy performs moderately but incurs higher per-step overhead due to additional model calls, resulting in fewer iterations. Random scheduling performs the worst, underscoring the importance of informed decision-making in driving effective optimization. Full ablation results are provided in Appendix D.2.

Table 3: Ablation results on action selection strategies for R&D-Agent(Q) (o3-mini). We compare random, LLM-based, and Bandit controllers across predictive quality, strategy performance, and execution statistics (TL: total loops, VL: valid loops, SL: SOTA selections, TRH: runtime in hours).
<table><tr><td rowspan="3" colspan="2">Models</td><td colspan="2">Factor Predictive Power Metrics</td><td colspan="2">Performance Metrics</td><td colspan="4">Execution Metrics SL</td></tr><tr><td>IC</td><td>ICIR</td><td>ARR</td><td>MDD</td><td>TL</td><td>VL</td><td>TRH</td><td></td></tr><tr><td rowspan="3">Algorithm Ablation</td><td>R&amp;D-Agent(Q)w/random</td><td>0.0445</td><td>0.3589</td><td>0.0897</td><td>-0.1004</td><td>33</td><td>19</td><td>7 5</td><td>12</td></tr><tr><td>R&amp;D-Agent (Q)w/LLM</td><td>0.0476</td><td>0.3891</td><td>0.1009</td><td>-0.0794</td><td>33</td><td>20</td><td></td><td>12</td></tr><tr><td>R&amp;D-Agent(Q)w/Bandit</td><td>0.0532</td><td>0.4278</td><td>0.1421</td><td>-0.0742</td><td>44</td><td>24</td><td>8</td><td>12</td></tr></table>

➥ Backend Comparisons. To assess the sensitivity of R&D-Agent(Q) to the LLM backend, we evaluate six API variants across research and strategy metrics (Fig. 9). Despite moderate loop statistics, o1 achieves top performance through several impactful rounds with strong strategic breakthroughs. The recently released GPT-4.1 ranks second across most metrics. Other variants (except GPT-4omini, with limited reasoning capacity, leading to weaker performance) exhibit comparable results, showing the robustness of our framework across LLM backends.

➥ Extended Studies. Appendix D.5 further shows that R&D-Agent(Q)’s cost (in the paper’s setting) is under \$10, confirming its cost-efficient scalability. Appendix D.6 validates its robustness on real-world quant scenarios.

## 5 Related Work

![](images/43df2adcb9d429788d4465a99b80dc93ea89cf3da6658af7bce5d0ded092a282.jpg)  
Figure 9: Comparison of R&D-Agent(Q) using different API backends (30 loops each). Axes are normalized, with outer points indicating better performance.

Traditional Methods in Quantitative Research. Quantitative strategies have traditionally relied on human-crafted factors from asset pricing theory, such as value and momentum [10, 11]. While interpretable, these fixed signals often lack flexibility in adapting to changing regimes. To overcome these limitations, symbolic regression and genetic programming (GP) methods [14, 55] automate factor mining by evolving complex, non-linear expressions. Enhancements like lag operators [13] and operator mutation with pruning [56] yield more diverse and effective signals. Reinforcement learning (RL) methods reframe factor allocation as sequential decision-making, directly optimizing Sharpe or Calmar ratios [15, 57]. Andre et al. [16] model factor weights via Dirichlet policies with KL regularization, enabling sparse and adaptive strategies. However, RL methods often lack robustness under regime shifts (e.g., 2020 circuit breaker [58]) and remain hard to interpret.

Model-wise, early approaches like ARIMA [59] and exponential smoothing [60] struggle with noisy, high-dimensional data. Classical machine learning methods (e.g., SVMs [19], random forests [20]) improve robustness but still require manual feature engineering. Deep learning models like LSTMs [61] and Transformers [62] have since been applied to capture long-term and cross-sectional dependencies [63, 64]. Building upon these, specialized time series neural networks have emerged. PatchTST [65] segments inputs into local patches, while iTransformer [66] remaps variable-token relations to model multivariate structure. Domain-specific models like MASTER [67] further incorporates market-level dynamics for improved financial prediction. However, both factor and model pipelines remain siloed, expert-dependent, and inflexible, restricting scalability in volatile markets.

LLM-Driven Agents in Finance. Large language models (LLMs) offer new opportunities for automating financial research due to their strong reasoning and abstraction capabilities. Recent work explores their use in extracting predictive signals from financial text [68, 31], generating factor explanations [30], and enabling multi-modal market analysis [33]. Parallel advances in LLM-based multi-agent systems (e.g., AutoGen [69], AutoGPT [70]) provide coordination frameworks for complex decision-making. In finance, systems like FinAgent [33] and TradingAgents[34] use rolebased agents for subtasks such as event extraction or portfolio updates. However, most existing efforts focus on narrow subtasks and rely heavily on semantic signals, making them prone to hallucination, hard to interpret, and difficult to reproduce. Moreover, they lack mechanisms for joint factor-model optimization or workflow integration, limiting their effectiveness in real-world quantitative systems.

## 6 Conclusion

We propose R&D-Agent(Q), a LLM-driven framework for collaborative factor-model development in quantitative finance. By decomposing research into modular components and integrating a banditbased scheduler, it supports efficient, adaptive iteration under fixed compute budgets. Empirically, R&D-Agent outperforms baselines in both signal quality and strategy performance, with strong cost-efficiency and generalizability. Its modularity also enables adaptation to real-world settings. However, current framework relies solely on the LLM’s internal financial knowledge. Future work may enhance data diversity, incorporate domain priors, and enable online adaptation to evolving market regimes.

## 7 Disclaimer

Users of the R&D-Agent(Q) framework and the associated code should prepare their own financial data and independently assess and test the risks of the generated factors and model in use’s own scenarios. It is essential to use the agent-generated code, data, and model with caution and thoroughly check them. The R&D-Agent(Q) framework does not provide financial opinions, nor is it designed to replace the role of qualified financial professionals in formulating, assessing, and approving financial products. The outputs of the R&D-Agent(Q) framework do not reflect the opinions of Microsoft.

## References

[1] B. B. Mandelbrot and B. B. Mandelbrot, The variation of certain speculative prices. Springer, 1997.

[2] R. F. Engle, “Autoregressive conditional heteroscedasticity with estimates of the variance of united kingdom inflation,” Econometrica: Journal of the econometric society, pp. 987–1007, 1982.

[3] F. X. Diebold and K. Yılmaz, “On the network topology of variance decompositions: Measuring the connectedness of financial firms,” Journal of econometrics, vol. 182, no. 1, pp. 119–134, 2014.

[4] W. A. Brock and C. H. Hommes, “A rational route to randomness,” Econometrica: Journal of the Econometric Society, pp. 1059–1095, 1997.

[5] ——, “Heterogeneous beliefs and routes to chaos in a simple asset pricing model,” Journal of Economic dynamics and Control, vol. 22, no. 8-9, pp. 1235–1274, 1998.

[6] D. Kahneman and A. Tversky, “Prospect theory: An analysis of decision under risk,” in Handbook of the fundamentals of financial decision making: Part I. World Scientific, 2013, pp. 99–127.

[7] B. Cao, S. Wang, X. Lin, X. Wu, H. Zhang, L. M. Ni, and J. Guo, “From deep learning to llms: A survey of ai in quantitative investment,” 2025. [Online]. Available: https://arxiv.org/abs/2503.21422

[8] N. Gârleanu and L. H. Pedersen, “Dynamic trading with predictable returns and transaction costs,” The Journal of Finance, vol. 68, no. 6, pp. 2309–2340, 2013.

[9] X. Yang, W. Liu, D. Zhou, J. Bian, and T.-Y. Liu, “Qlib: An ai-oriented quantitative investment platform,” arXiv preprint arXiv:2009.11189, 2020.

[10] E. F. Fama and K. R. French, “Common risk factors in the returns on stocks and bonds,” Journal of Financial Economics, vol. 33, no. 1, pp. 3–56, 1993.

[11] M. M. Carhart, “On persistence in mutual fund performance,” The Journal of Finance, vol. 52, no. 1, pp. 57–82, 1997.

[12] J. R. Koza, “Genetic programming: On the programming of computers by means of natural selection (complex adaptive systems),” A Bradford Book, vol. 1, p. 18, 1993.

[13] J. Stelmack, Kaizen Programming with Enhanced Feature Discovery: An Automated Approach to Feature Selection and Feature Discovery for Prediction Models. Rochester Institute of Technology, 2020.

[14] P.-A. Kamienny, G. Lample, S. Lamprier, and M. Virgolin, “Deep generative symbolic regression with monte-carlo-tree-search,” in International Conference on Machine Learning. PMLR, 2023, pp. 15 655–15 668.

[15] J. Zhao, C. Zhang, M. Qin, and P. Yang, “Quantfactor reinforce: Mining steady formulaic alpha factors with variance-bounded reinforce,” arXiv preprint arXiv:2409.05144, 2024.

[16] E. André and G. Coqueret, “Dirichlet policies for reinforced factor portfolios,” arXiv preprint arXiv:2011.05381, 2020.

[17] Y. Deng, F. Bao, Y. Kong, Z. Ren, and Q. Dai, “Deep direct reinforcement learning for financial signal representation and trading,” IEEE transactions on neural networks and learning systems, vol. 28, no. 3, pp. 653–664, 2016.

[18] G. E. Box, G. M. Jenkins, G. C. Reinsel, and G. M. Ljung, Time series analysis: forecasting and control. John Wiley & Sons, 2015.

[19] W. Huang, Y. Nakamori, and S.-Y. Wang, “Forecasting stock market movement direction with support vector machine,” Computers & operations research, pp. 2513–2522, 2005.

[20] F. S. D. Nugroho, T. B. Adji, and S. Fauziati, “Decision support system for stock trading using multiple indicators decision tree,” in International Conference on Information Technology, Computer, and Electrical Engineering, 2014, pp. 291–296.

[21] R. A. Kamble, “Short and long term stock trend prediction using decision tree,” in 2017 International Conference on Intelligent Computing and Control Systems, 2017, pp. 1371–1375.

[22] K. Cho, B. van Merriënboer, C. Gulcehre, D. Bahdanau, F. Bougares, H. Schwenk, and Y. Bengio, “Learning phrase representations using RNN encoder–decoder for statistical machine translation,” in Proceedings of the 2014 Conference on Empirical Methods in Natural Language Processing (EMNLP), 2014, pp. 1724–1734.

[23] S. Hochreiter and J. Schmidhuber, “Long short-term memory,” Neural computation, pp. 1735– 1780, 1997.

[24] H. Wu, J. Xu, J. Wang, and M. Long, “Autoformer: Decomposition transformers with auto-correlation for long-term series forecasting,” Advances in neural information processing systems, vol. 34, pp. 22 419–22 430, 2021.

[25] H. Zhou, S. Zhang, J. Peng, S. Zhang, J. Li, H. Xiong, and W. Zhang, “Informer: Beyond efficient transformer for long sequence time-series forecasting,” in Proceedings of the AAAI conference on artificial intelligence, vol. 35, no. 12, 2021, pp. 11 106–11 115.

[26] Q. Zhang, Y. Zhang, X. Yao, S. Li, C. Zhang, and P. Liu, “A dynamic attributes-driven graph attention network modeling on behavioral finance for stock prediction,” ACM Transactions on Knowledge Discovery from Data, vol. 18, no. 1, pp. 1–29, 2023.

[27] P. Zhu, Y. Li, Y. Hu, Q. Liu, D. Cheng, and Y. Liang, “Lsr-igru: Stock trend prediction based on long short-term relationships and improved gru,” in Proceedings of the 33rd ACM International Conference on Information and Knowledge Management, 2024, pp. 5135–5142.

[28] S. Xiang, D. Cheng, C. Shang, Y. Zhang, and Y. Liang, “Temporal and heterogeneous graph neural network for financial time series prediction,” in ACM International Conference on Information & Knowledge Management, 2022, pp. 3584–3593.

[29] B. Yan, X. Zhang, L. Zhang, L. Zhang, Z. Zhou, D. Miao, and C. Li, “Beyond selftalk: A communication-centric survey of llm-based multi-agent systems,” arXiv preprint arXiv:2502.14321, 2025.

[30] M. Wang, K. Izumi, and H. Sakaji, “Llmfactor: Extracting profitable factors through prompts for explainable stock movement prediction,” in Findings of the Association for Computational Linguistics ACL 2024, 2024, pp. 3120–3131.

[31] A. Lopez-Lira and Y. Tang, “Can chatgpt forecast stock price movements? return predictability and large language models,” arXiv preprint arXiv:2304.07619, 2023.

[32] S. Hong, M. Zhuge, J. Chen, X. Zheng, Y. Cheng, J. Wang, C. Zhang, Z. Wang, S. K. S. Yau, Z. Lin et al., “Metagpt: Meta programming for a multi-agent collaborative framework,” in The Twelfth International Conference on Learning Representations.

[33] W. Zhang, L. Zhao, H. Xia, S. Sun, J. Sun, M. Qin, X. Li, Y. Zhao, Y. Zhao, X. Cai et al., “A multimodal foundation agent for financial trading: Tool-augmented, diversified, and generalist,” in Proceedings of the 30th ACM SIGKDD Conference on Knowledge Discovery and Data Mining, 2024, pp. 4314–4325.

[34] Y. Xiao, E. Sun, D. Luo, and W. Wang, “Tradingagents: Multi-agents llm financial trading framework,” arXiv preprint arXiv:2412.20138, 2024.

[35] J. Wei, X. Wang, D. Schuurmans, M. Bosma, b. ichter, F. Xia, E. Chi, Q. V. Le, and D. Zhou, “Chain-of-thought prompting elicits reasoning in large language models,” in Advances in Neural Information Processing Systems, S. Koyejo, S. Mohamed, A. Agarwal, D. Belgrave, K. Cho, and A. Oh, Eds., vol. 35. Curran Associates, Inc., 2022, pp. 24 824–24 837.

[36] X. Li, Z. Li, C. Shi, Y. Xu, Q. Du, M. Tan, and J. Huang, “Alphafin: Benchmarking financial analysis with retrieval-augmented stock-chain framework,” in Proceedings of the 2024 Joint International Conference on Computational Linguistics, Language Resources and Evaluation (LREC-COLING 2024), 2024, pp. 773–783.

[37] Y. Duan, L. Wang, Q. Zhang, and J. Li, “Factorvae: A probabilistic dynamic factor model based on variational autoencoder for predicting cross-sectional stock returns,” in Proceedings of the AAAI Conference on Artificial Intelligence, 2022, pp. 4468–4476.

[38] H. Lin, D. Zhou, W. Liu, and J. Bian, “Learning multiple stock trading patterns with temporal routing adaptor and optimal transport,” in Proceedings of the 27th ACM SIGKDD conference on knowledge discovery & data mining, 2021, pp. 1017–1026.

[39] T. Li, Z. Liu, Y. Shen, X. Wang, H. Chen, and S. Huang, “Master: Market-guided stock transformer for stock price forecasting,” in Proceedings of the AAAI Conference on Artificial Intelligence, 2024, pp. 162–170.

[40] G. Ke, Q. Meng, T. Finley, T. Wang, W. Chen, W. Ma, Q. Ye, and T.-Y. Liu, “Lightgbm: A highly efficient gradient boosting decision tree,” Advances in neural information processing systems, vol. 30, 2017.

[41] Z. Kakushadze, “101 formulaic alphas,” 2016.

[42] “Alpha 158 from microsoft qlib,” https://github.com/microsoft/qlib/blob/ 85cc74846b5af2e3e6d18666a2f6e399396980b9/qlib/contrib/data/loader.py#61, accessed: 2025-05-12.

[43] “Alpha 360 from microsoft qlib,” https://github.com/microsoft/qlib/blob/ 85cc74846b5af2e3e6d18666a2f6e399396980b9/qlib/contrib/data/loader.py#4, accessed: 2025-05-12.

[44] Z. Kou, H. Yu, J. Luo, J. Peng, and L. Chen, “Automate strategy finding with llm in quant investment,” arXiv preprint arXiv:2409.06289, 2024.

[45] T. Chen and C. Guestrin, “Xgboost: A scalable tree boosting system,” in Proceedings of the 22nd acm sigkdd international conference on knowledge discovery and data mining, 2016, pp. 785–794.

[46] L. Prokhorenkova, G. Gusev, A. Vorobev, A. V. Dorogush, and A. Gulin, “Catboost: unbiased boosting with categorical features,” Advances in neural information processing systems, vol. 31, 2018.

[47] C. Zhang, Y. Li, X. Chen, Y. Jin, P. Tang, and J. Li, “Doubleensemble: A new ensemble method based on sample reweighting and feature selection for financial data analysis,” in 2020 IEEE International Conference on Data Mining (ICDM), 2020, pp. 781–790.

[48] Y. Qin, D. Song, H. Chen, W. Cheng, G. Jiang, and G. W. Cottrell, “A dual-stage attentionbased recurrent neural network for time series prediction,” in Proceedings of the Twenty-Sixth International Joint Conference on Artificial Intelligence, 2017, pp. 2627–2633.

[49] A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, L. u. Kaiser, and I. Polosukhin, “Attention is all you need,” in Advances in Neural Information Processing Systems, 2017.

[50] Y. Nie, N. H. Nguyen, P. Sinthong, and J. Kalagnanam, “A time series is worth 64 words: Longterm forecasting with transformers,” in The Eleventh International Conference on Learning Representations, 2023.

[51] Y. Liu, T. Hu, H. Zhang, H. Wu, S. Wang, L. Ma, and M. Long, “itransformer: Inverted transformers are effective for time series forecasting,” in The Twelfth International Conference on Learning Representations, 2023.

[52] A. Gu and T. Dao, “Mamba: Linear-time sequence modeling with selective state spaces,” in First Conference on Language Modeling, 2024.

[53] P. Velickovi ˇ c, G. Cucurull, A. Casanova, A. Romero, P. Liò, and Y. Bengio, “Graph attention ´ networks,” in 6th International Conference on Learning Representations, 2018.

[54] N. Reimers and I. Gurevych, “Sentence-bert: Sentence embeddings using siamese bertnetworks,” in Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing and the 9th International Joint Conference on Natural Language Processing (EMNLP-IJCNLP), 2019, pp. 3982–3992.

[55] B. K. Petersen, M. L. Larma, T. N. Mundhenk, C. P. Santiago, S. K. Kim, and J. T. Kim, “Deep symbolic regression: Recovering mathematical expressions from data via risk-seeking policy gradients,” in International Conference on Learning Representations.

[56] C. Cui, W. Wang, M. Zhang, G. Chen, Z. Luo, and B. C. Ooi, “Alphaevolve: A learning framework to discover novel alphas in quantitative investment,” in Proceedings of the 2021 International conference on management of data, 2021, pp. 2208–2216.

[57] Y.-J. Hu and S.-J. Lin, “Deep reinforcement learning for optimizing finance portfolio management,” in 2019 amity international conference on artificial intelligence (AICAI). IEEE, 2019, pp. 14–20.

[58] S. Gu, B. Kelly, and D. Xiu, “Empirical asset pricing via machine learning,” The Review of Financial Studies, vol. 33, no. 5, pp. 2223–2273, 2020.

[59] A. A. Ariyo, A. O. Adewumi, and C. K. Ayo, “Stock price prediction using the arima model,” in 2014 UKSim-AMSS 16th International Conference on Computer Modelling and Simulation, 2014, pp. 106–112.

[60] E. S. Gardner Jr, “Exponential smoothing: The state of the art,” Journal of Forecasting, pp. 1–28, 1985.

[61] J. Wang, T. Sun, B. Liu, Y. Cao, and H. Zhu, “Clvsa: a convolutional lstm based variational sequence-to-sequence model with attention for predicting trends of financial markets,” in International Joint Conference on Artificial Intelligence, 2019, pp. 3705–3711.

[62] Q. Ding, S. Wu, H. Sun, J. Guo, and J. Guo, “Hierarchical multi-scale gaussian transformer for stock movement prediction,” in International Joint Conference on Artificial Intelligence, 2020, pp. 4640–4646.

[63] W. Xu, W. Liu, C. Xu, J. Bian, J. Yin, and T.-Y. Liu, “Rest: Relational event-driven stock trend forecasting,” in Proceedings of the Web Conference, 2021, pp. 1–10.

[64] S. Zhao, D. Wang, and R. Douady, “Polymodel for hedge funds’ portfolio construction using machine learning,” 2024. [Online]. Available: https://arxiv.org/abs/2412.11019

[65] Y. Nie, Q. Yuan, and Y. e. a. Wu, “A time series is worth 64 words: Long-term forecasting with transformers,” in Proceedings of the International Conference on Learning Representations (ICLR), 2023.

[66] Y. Liu, Y. Wang, Q. Lin, and et al., “itransformer: Inverted transformers are effective for time-series forecasting,” arXiv preprint arXiv:2310.06625, 2024.

[67] T. Li, Z. Liu, Y. Shen, X. Wang, H. Chen, and S. Huang, “Master: Market-guided stock transformer for stock price forecasting,” in Proceedings of the AAAI Conference on Artificial Intelligence, 2024, pp. 162–170.

[68] Z. Liu, D. Huang, K. Huang, Z. Li, and J. Zhao, “Finbert: A pre-trained financial language representation model for financial text mining,” in Proceedings of the twenty-ninth international conference on international joint conferences on artificial intelligence, 2021, pp. 4513–4519.

[69] Q. Wu, G. Bansal, J. Zhang, Y. Wu, B. Li, E. Zhu, L. Jiang, X. Zhang, S. Zhang, J. Liu et al., “Autogen: Enabling next-gen llm applications via multi-agent conversation,” in ICLR 2024 Workshop on Large Language Model (LLM) Agents.

[70] H. Yang, S. Yue, and Y. He, “Auto-gpt for online decision making: Benchmarks and additional opinions,” arXiv preprint arXiv:2306.02224, 2023.

[71] T. Brown, B. Mann, N. Ryder, M. Subbiah, J. D. Kaplan, P. Dhariwal, A. Neelakantan, P. Shyam, G. Sastry, A. Askell, S. Agarwal, A. Herbert-Voss, G. Krueger, T. Henighan, R. Child, A. Ramesh, D. Ziegler, J. Wu, C. Winter, C. Hesse, M. Chen, E. Sigler, M. Litwin, S. Gray, B. Chess, J. Clark, C. Berner, S. McCandlish, A. Radford, I. Sutskever, and D. Amodei, “Language models are few-shot learners,” in Advances in Neural Information Processing Systems, H. Larochelle, M. Ranzato, R. Hadsell, M. Balcan, and H. Lin, Eds., vol. 33. Curran Associates, Inc., 2020, pp. 1877–1901.

[72] N. Shinn, F. Cassano, A. Gopinath, K. Narasimhan, and S. Yao, “Reflexion: Language agents with verbal reinforcement learning,” in Advances in Neural Information Processing Systems, A. Oh, T. Neumann, A. Globerson, K. Saenko, M. Hardt, and S. Levine, Eds., vol. 36. Curran Associates, Inc., 2023, pp. 8634–8652.

[73] X. Jiang, Y. Dong, L. Wang, Q. Shang, and G. Li, “Self-planning code generation with large language model,” arXiv preprint arXiv:2303.06689, 2023.

[74] X. Chen, M. Lin, N. Schärli, and D. Zhou, “Teaching large language models to self-debug,” in The Twelfth International Conference on Learning Representations, 2024.

[75] H. Shi, W. Song, X. Zhang, J. Shi, C. Luo, X. Ao, H. Arian, and L. A. Seco, “Alphaforge: A framework to mine and dynamically combine formulaic alpha factors,” in Proceedings of the AAAI Conference on Artificial Intelligence, vol. 39, no. 12, 2025, pp. 12 524–12 532.

[76] H. Chen, X. Shen, Z. Ye, X. Yang, X. Yang, W. Liu, and J. Bian, “RD2Bench: Toward data-centric automatic R&D,” in ICLR 2024 Workshop: How Far Are We from AGI, 2024.

[77] A. Meyer, BerniceOptiver, CameronOptiver, IXAGPOPU, J. Liu, M. P. (Optiver), Optiver-Merle, S. Dane, and S. Vallentine, “Optiver realized volatility prediction,” https://kaggle.com/ competitions/optiver-realized-volatility-prediction, 2021, kaggle.

## A Algorithmic Details

## A.1 Co-STEER Implementation Logic

To further clarify the internal mechanism of the Co-STEER agent, we provide both a formal algorithmic procedure (Algorithm 1) and a comparative method analysis (Table 4).

Existing natural-language-to-code methods primarily focus on isolated capabilities. Few-shot [71] learning leverages in-context examples to guide model outputs. Chain-of-Thought (CoT) [35] improves reasoning coherence via step-by-step prompting. Reflexion [72] and Self-Debugging [73] emphasize iterative correction through feedback, while Self-Planning [74] supports automatic task decomposition.

In contrast, Co-STEER offers a unified solution that integrates scheduling, reasoning, feedbackdriven refinement, and long-term knowledge accumulation. It maintains a continually growing knowledge base of prior attempts, which enables retrieval and adaptation of previously successful solutions. Additionally, its scheduling agent supports multi-task code generation, such as factor implementation in quantitative research, by dynamically prioritizing tasks based on complexity and feedback—favoring simpler, more foundational tasks early on to provide informative scaffolding for subsequent code generation.

Table 4: Comparison of code-generation methods in quantitative research. Co-STEER is the only method supporting end-to-end development, from task scheduling to implementation, enhanced by structured reasoning and lifelong knowledge reuse. This makes it especially suited for multi-step, data-centric financial workflows.
<table><tr><td rowspan="2">Methods</td><td>Schedule</td><td colspan="4">Implementation</td></tr><tr><td></td><td>Demonstration</td><td>Planning or Reasoning Before Impl.</td><td>LLM-Based Self-Feedback</td><td>Growing Practical Knowledge</td></tr><tr><td>Few-shot [71]</td><td></td><td>√</td><td></td><td>×</td><td></td></tr><tr><td>CoT[35]</td><td></td><td></td><td>xνxxν/</td><td>xν</td><td>xxx</td></tr><tr><td>Reflexion [72]</td><td>xxx</td><td></td><td></td><td></td><td></td></tr><tr><td>Self-Debugging [73]</td><td>x</td><td></td><td></td><td>√</td><td>x</td></tr><tr><td>Self-Planning [74]</td><td>X</td><td></td><td></td><td>×</td><td>X</td></tr><tr><td>Co-STEER</td><td></td><td></td><td></td><td>【</td><td></td></tr></table>

Below, we present the complete pseudocode of the Co-STEER workflow for the factor implementation task.

## A.2 Bandit Scheduling Logic

As stated in Section 2.5, we apply contextual Thompson Sampling to adaptively select between two optimization directions—factor refinement and model optimization—based on current strategy performance. The problem is formulated as a two-armed contextual bandit with linear reward functions. Each arm maintains its own Bayesian linear regression model, whose posterior is updated after every interaction.

At each round t, the system summarizes strategy quality using the following 8-dimensional performance vector:

$$
\mathbf { x } _ { t } = \left[ \mathbf { I C } , \mathbf { I C I R } , \mathbf { R a n k } ( \mathbf { I C } ) , \mathbf { R a n k } ( \mathbf { I C I R } ) , \mathbf { A R R } , \mathbf { I R } , \mathbf { \Phi } - \mathbf { M D D } , \mathbf { S R } \right] ^ { \top } \in \mathbb { R } ^ { 8 }
$$

Each component is positively correlated with desirable strategy outcomes; maximum drawdown (MDD) is negated to align with this direction.

Given a prior $\mathbf { \nabla } \mu ^ { ( a ) } = \mathbf { 0 } , P ^ { ( a ) } = \tau ^ { - 2 } I$ , the algorithm samples a reward coefficient vector from the posterior for each action, estimates the reward under the current context $\mathbf { x } _ { t }$ , and selects the action with the highest sampled value. The posterior is then updated using standard Bayesian linear regression updates.

Algorithm 1 Co-STEER: Collaborative Scheduling and Task Execution Engine for Quant Research   
Require: Tasks $\mathcal { T } = \{ t _ { 1 } , \ldots , t _ { n } \}$ , Knowledge base $\kappa$   
Ensure: Implemented code solutions $\{ c _ { 1 } , \ldots , c _ { n } \}$   
1: Initialize DAG $\mathcal { G } = ( \nu , \mathcal { E } )$ where $\dot { \mathcal { V } } = \mathcal { T }$   
2: Initialize task complexity scores $\alpha _ { j } = 1$ for all $t _ { j } \in \tau$   
3: function UPDATETASKORDER $. ( \mathcal { G } , \{ \alpha _ { j } \} )$   
4: Compute weighted edges: $w _ { i j } = \alpha _ { i } / \alpha _ { j }$ for $( i , j ) \in \mathcal { E }$   
5: Return topological order $\pi _ { S }$ considering $w _ { i j }$   
6: end function   
7: function IMPLEMENT $\mathrm { T A S K } ( t _ { j } , , \mathcal { K } , f ^ { ( t ) } )$   
8: Find similar tasks: $S _ { j } = \{ t _ { k } \in \mathcal { K } :$ similarity $( t _ { j } , t _ { k } ) > \theta \}$   
9: $c _ { r e f } = \arg \operatorname* { m a x } _ { c _ { k } \in \mathcal { K } }$ similarity $\mathbf { \Phi } ^ { \prime } ( t _ { j } , t _ { k } ) \cdot \mathbf { \Phi } \boldsymbol { c } _ { k }$   
10: Generate code: $c _ { j } = I ( t _ { j } , c _ { r e f } , \bar { \mathcal { K } } )$   
11: Execute and get feedback $f _ { j }$   
12: Update knowledge base: $\check { \kappa } ^ { \prime }  \kappa \cup \{ ( t _ { j } , c _ { j } , f _ { j } ) \}$   
13: return $( c _ { j } , f _ { j } )$   
14: end function   
15: while $\tau$ not empty do   
16: $\pi _ { S } \gets \mathrm { U P D A T E T A S K O R D E R } ( \mathcal { G } , \{ \alpha _ { j } \} )$   
17: for $t _ { j } \in \pi _ { S }$ do   
18: $\begin{array} { r } { \bar { ( c _ { j } , f _ { j } ) } \gets \mathrm { I M P L E M E N T T A S K } ( t _ { j } , \mathcal { K } , f ^ { ( t ) } ) } \end{array}$   
19: if $f _ { j }$ indicates failure then   
20: Update complexity: $\alpha _ { j }  \alpha _ { j } + \delta$   
21: Break and recompute πS   
22: else   
23: $\mathcal { T }  \mathcal { T } \backslash \{ t _ { j } \}$   
24: end if   
25: end for   
26: end while   
27: return $\{ c _ { 1 } , \ldots , c _ { n } \}$

Algorithm 2 Contextual Thompson Sampling scheduler used to adaptively choose between factor   
and model optimization.   
(Assume prior: $\mu ^ { ( a ) } = 0 , P ^ { ( a ) } = \tau ^ { - 2 } I )$   
1: Define reward weight vector $\mathbf { w } \in \mathbb { R } ^ { 8 }$   
2: for $t = 1$ to $T$ do   
3: Get performance state vector $\mathbf { x } _ { t }$   
4: for all $a \in { \mathcal { A } }$ do   
5: Sample $\tilde { \pmb { \theta } } ^ { ( a ) } \sim \mathcal { N } ( \mu ^ { ( a ) } , ( P ^ { ( a ) } ) ^ { - 1 } )$   
6: Compute expected reward: $\hat { r } ^ { ( a ) } = \tilde { \pmb { \theta } } ^ { ( a ) \top } { \mathbf x } _ { t }$   
7: end for   
8: Select $a _ { t } = \arg \operatorname* { m a x } _ { a } \hat { r } ^ { ( a ) } ;$ ; observe reward: $r _ { t }$   
9: Update $\dot { \boldsymbol { P } } ^ { ( a _ { t } ) }$ and $\mu ^ { ( a _ { t } ) }$ based on $\left( \mathbf { x } _ { t } , \boldsymbol { r } _ { t } \right)$   
$P ^ { ( a _ { t } ) } \gets P ^ { ( a _ { t } ) } + \frac { 1 } { \sigma ^ { 2 } } \mathbf { x } _ { t } \mathbf { x } _ { t } ^ { \top }$   
$\mu ^ { ( a _ { t } ) } \gets \Big ( P ^ { ( a _ { t } ) } \Big ) ^ { - 1 } \left( P ^ { ( a _ { t } ) } \mu ^ { ( a _ { t } ) } + \frac { 1 } { \sigma ^ { 2 } } r _ { t } \mathbf { x } _ { t } \right)$   
10: end for

## B Formal Definition of the Quantitative Research Pipeline

Building on several classic works in quantitative finance [9, 39, 75], we define the raw dataset as a three-dimensional tensor with dual temporal indexing, denoted as $\mathbf { X } \in \mathbb { R } ^ { N \times T \times P }$ . This dataset takes stocks as the underlying asset class, each associated with a set of factor dimensions. As formally defined in Equation (2), the tensor contains N assets over an observation period $\mathcal { T } = \{ 1 , \dots , T \}$ The row index corresponds to time $t ,$ the column index to asset $i ,$ and the channel index $p$ refers to one of the $P$ factor dimensions. Each entry $x _ { i , t } ^ { ( p ) }$ represents the value of the p-th factor for asset i at time t.

$$
\mathbf { X } \ = \ \left\{ x _ { i , t } ^ { ( p ) } \ \middle | \ i \in [ N ] , t \in \{ 1 , \ldots , T \} , p \in [ P ] \right\} \in \mathbb { R } ^ { N \times T \times P } ,\tag{2}
$$

New factors are then constructed either analytically or using machine learning, based on the original factor features. Given a sliding window of length ℓ, m new factors $f _ { i , t } ^ { ( j ) }$ are generated via a mapping defined in Equation (3), where $\mathbf { x } _ { i , t - \ell + 1 : t }$ denotes the recent ℓ-day tensor slice for asset i, and $f _ { i , t } ^ { ( j ) }$ is the j-th derived factor. The new factor tensor $\mathbf { Z } \in \mathbb { R } ^ { N \times T \times ( P + m ) }$ is formed by concatenating the original and generated factors, with ${ \bf z } _ { i , t }$ representing the concatenated vector at (i, t), as shown in Equation (4).

$$
\Phi : \mathbb { R } ^ { \ell \times P } \longrightarrow \mathbb { R } ^ { m } , \quad \Phi \big ( \mathbf { x } _ { i , t - \ell + 1 : t } \big ) = \big ( f _ { i , t } ^ { ( 1 ) } , \ldots , f _ { i , t } ^ { ( m ) } \big ) ,\tag{3}
$$

$$
\mathbf { z } _ { i , t } = \left[ \mathbf { x } _ { i , t } \Vert \mathbf { F } _ { i , t } \right] \in \mathbb { R } ^ { P + m } , \quad \mathbf { F } _ { i , t } = \Phi \left( \mathbf { x } _ { i , t - \ell + 1 : t } \right) .\tag{4}
$$

Given the noisy and incomplete nature of financial data, a two-stage preprocessing procedure is adopted to suppress the impact of outliers. First, a cross-sectional robust Z-score normalization is applied to each feature, as in Equation (5), where MAD is the median absolute deviation and $\varepsilon$ is a numerical stability constant. Second, missing values are imputed using a “forward-fill + cross-sectional mean” strategy, formally defined in Equation (6).

$$
\tilde { x } _ { i , t } ^ { ( p ) } = \frac { x _ { i , t } ^ { ( p ) } - \mathrm { M e d i a n } _ { i } \Big ( x _ { \cdot , t } ^ { ( p ) } \Big ) } { \mathrm { M A D } _ { i } \Big ( x _ { \cdot , t } ^ { ( p ) } \Big ) + \varepsilon } ,\tag{5}
$$

$$
\begin{array} { r } { x _ { i , t } ^ { ( p ) } \gets \left\{ \begin{array} { l l } { x _ { i , t - 1 } ^ { ( p ) } , } & { \mathrm { i f } x _ { i , t } ^ { ( p ) } = \mathrm { N A } \mathrm { a n d } x _ { i , t - 1 } ^ { ( p ) } e q \mathrm { N A } , } \\ { \mathrm { M e a n } _ { i } \Big ( x _ { \cdot , t } ^ { ( p ) } \Big ) , } & { \mathrm { o t h e r w i s e } . } \end{array} \right. } \end{array}\tag{6}
$$

Asset returns are defined as the prediction target for training and validation, denoted $y _ { i , t } ^ { ( \tau ) }$ with $\tau = 1$ trading day in this work, as shown in Equation (7). Similar to factor preprocessing, missing labels are removed, and Z-score normalization is applied cross-sectionally on each trading day, yielding the supervised sample pairs $( \mathbf { z } _ { i , t } , \tilde { y } _ { i , t } ^ { ( \tau ) } )$ .

$$
y _ { i , t } ^ { ( \tau ) } = \frac { P _ { i , t + \tau } - P _ { i , t } } { P _ { i , t } } , \quad P _ { i , t } \mathrm { ~ i s ~ t h e ~ c l o s i n g ~ p r i c e ~ o f ~ a s s e t ~ } i \mathrm { ~ a t ~ t i m e ~ } t ,\tag{7}
$$

$$
\tilde { y } _ { i , t } ^ { ( \tau ) } = \frac { y _ { i , t } ^ { ( \tau ) } - \mathrm { M e a n } _ { i } ( y _ { \cdot , t } ^ { ( \tau ) } ) } { \mathrm { S t d } _ { i } ( y _ { \cdot , t } ^ { ( \tau ) } ) + \varepsilon } ,\tag{8}
$$

To better encapsulate the interaction interface between factors and models, predictions $\hat { y } _ { i , t }$ are uniformly generated by a predictor $f _ { \theta }$ as defined in Equation (9), where θ denotes learnable parameters. The predictor supports both tabular models (which take ${ \bf z } _ { i , t }$ as input) and time series models, which instead use the tensor slice $\mathbf { Z } _ { i , t - \ell + 1 : t }$ to capture temporal structures.

$$
\begin{array} { r } { \hat { y } _ { i , t } = f _ { \pmb { \theta } } ( \mathbf { z } _ { i , t } ) , \quad f _ { \pmb { \theta } } : \mathbb { R } ^ { P + m }  \mathbb { R } , } \end{array}\tag{9}
$$

Model training follows a walk-forward validation procedure, minimizing the mean squared error loss L(θ) (Equation (10)) via gradient descent to optimize parameters to $\pmb { \theta } ^ { * }$

$$
\mathcal { L } ( \pmb { \theta } ) = \frac { 1 } { | \mathcal { D } _ { \mathrm { t r a i n } } | } \sum _ { ( i , t ) \in \mathcal { D } _ { \mathrm { t r a i n } } } \big ( y _ { i , t } ^ { ( \tau ) } - \hat { y } _ { i , t } \big ) ^ { 2 } .\tag{10}
$$

This pipeline covers four essential components—data representation, feature engineering, sample construction, and model training—providing a standardized input interface for the dual-loop factormodel optimization mechanism in the R&D-Agent(Q) framework.

## C Experimental Details

## C.1 Implementation Settings

Hardware Setup. All experiments were conducted on a dedicated server equipped with dual Intel Xeon Gold 6348 CPUs, providing a total of 112 threads, and four NVIDIA RTX A6000 GPUs, each with 48 GiB of memory (192 GiB in total).

Evaluation Protocol. All models were trained and validated on consistent dataset splits to ensure fair comparison. For each baseline model, we conducted extensive hyperparameter tuning and evaluated robustness using five independent runs with different random seeds. Rather than reporting standard error bars or confidence intervals, we report the median annualized return (ARR) across these runs. This follows quantitative finance practice, where consistent outperformance is valued more than pointwise variance. The use of median also reduces the influence of outliers.

Framework Configuration. The experiments were conducted using the R&D-Agent framework. R&D-Factor automates factor design and evaluation, and R&D-Model optimizes predictive models. Each module runs for 6 hours per experiment. The joint framework R&D-Agent(Q) alternates between the two for 12 hours total. Persistent caching was enabled throughout to accelerate repeated access to intermediate outputs, including the SOTA factor library, which is referenced in each loop.

Parameter Configuration. We used various LLM API backends during experiments. For GPT-4o and GPT-4o-mini, we enabled streaming, set temperature to 0.8, and capped token usage at 4096. For o3-mini, o3, and GPT-4.1, we disabled streaming, used a temperature of 1.0, and allowed up to 10,000 tokens. All API interactions used a unified system prompt from the user role, adjusted per backend capability. In the Co-STEER module (Implementation Unit), we used text-embedding-ada-002 to compute semantic embeddings for code, hypothesis, and log analysis. To ensure efficiency in fine-grained debugging, inner optimization loops in Co-STEER were capped at 10 iterations per task for both factor and model workflows. For each task, we set the maximum runtime of the Implementation Unit to 600 seconds, and the Validation Unit to 3600 seconds.

## C.2 Dataset

We do not propose a new dataset in this paper. The baseline factor library, Alpha 20, is shown in Table 5. The raw financial data used for factor mining can be divided into two categories: market data and fundamental data. The market data can be generated using the script at https://github.com/microsoft/RD-Agent/blob/main/rdagent/scenarios/ qlib/experiment/factor\_data\_template/generate.py, while the fundamental data—which includes standard financial indicators such as profitability, valuation, and growth metrics—is listed in Table 6.

Table 6: Fundamental data fields used for factor mining in R&D-Agent(Q). These fields can be obtained by searching their names in the Wind terminal (https://www.wind.com.cn/mobile/ WFT/en.html).
<table><tr><td>Factor</td><td>Description</td></tr><tr><td colspan="2">Profitability</td></tr><tr><td>ROE_TTM</td><td>Return on Equity (TTM)</td></tr><tr><td>ROA_TTM</td><td>Return on Assets (TTM)</td></tr><tr><td>ROIC</td><td>Return on Invested Capital</td></tr><tr><td>EBIT_EV</td><td>EBIT /Enterprise Value</td></tr><tr><td>Factor EBITDA_EV</td><td>Description</td></tr><tr><td>NET_PROFIT_YOY NET_PROFIT_YOY_Q NET_PROFIT_MARGIN NET_PROFIT_MARGIN_TTM GROSS_PROFIT_MARGIN_TTM</td><td>EBITDA /Enterprise Value Net Income Year-over-Year Growth Net Income YoY Growth (Quarterly) Net Profit Margin Net Profit Margin (TTM) Gross Profit Margin (TTM)</td></tr><tr><td colspan="2">Growth NET_PROFIT_YOY_TTM Net Profit Growth (TTM)</td></tr><tr><td>OPER_REV_YOY_TTM OPER_REV_YOY OPER_PROFIT_YOY OPER_REV_YOY_Q OPER_REV_QOQ OPER_PROFIT_QOQ NET_PROFIT_QOQ EST_OPER_REV_CHANGE_1M EST_OPER_REV_CHANGE_3M</td><td>Revenue Growth (TTM) Revenue Year-over-Year Growth Operating Profit Year-over-Year Growth Revenue YoY Growth (Quarterly) Revenue Quarter-over-Quarter Growth Operating Profit QoQ Growth Net Profit QoQ Growth Forecast Revenue Change (1M) Forecast Revenue Change (3M)</td></tr><tr><td>EP_TTM BP EP_FY1 BP_FY1 CFO_TO_PRICE_TTM OCF_TO_MKT_CAP</td><td>Valuation Earnings-to-Price Ratio Book-to-Price Ratio Forward Earnings-to-Price Ratio Forward Book-to-Price Ratio Cash Flow-to-Price Ratio Operating Cash Flow /Market Cap</td></tr><tr><td colspan="2">Operating Cash Flow-to-Price Ratio Risk &amp; Volatility 1-Month Volatility</td></tr><tr><td colspan="2">BETA_1Y Market Beta (12-Month) IDIOSYNCRATIC_VOLATILITY Idiosyncratic Volatility</td></tr><tr><td>VOLATILITY_1M</td><td>Risk &amp; Volatility 1-Month Volatility 3-Month Volatility</td></tr><tr><td colspan="2">VOLATILITY_1Y 12-Month Volatility BETA_1Y Market Beta (12-Month)</td></tr><tr><td colspan="2">IDIOSYNCRATIC_VOLATILITY Idiosyncratic Volatility Quality</td></tr><tr><td colspan="2">CFO_TTM Cash Flow from Operations (TTM) CFO_Q Cash Flow from Operations (Quarterly)</td></tr><tr><td colspan="2">CFO_TO_OPER_REV_TTM Operating Cash Flow /Revenue (TTM) NET_PROFIT_MARGIN Net Profit Margin ASSET_TURNOVER_TTM Asset Turnover (TTM)</td></tr><tr><td colspan="2">FIXED_ASSET_TURNOVER_TTM Fixed Asset Turnover (TTM) Sentiment&amp;Flow</td></tr><tr><td colspan="2">MID_ORDER_BUY_AMT Medium Order Active Buy Amount MID_ORDER_SELL_AMT Medium Order Active Sell Amount RATING_UPGRADE Analyst Rating Upgrade</td></tr><tr><td>Factor</td><td>Description</td></tr><tr><td></td><td>Momentum</td></tr><tr><td>RETURN_1M</td><td>30-Day Return</td></tr><tr><td>RETURN_2M</td><td>60-Day Return</td></tr><tr><td>RETURN_3M</td><td>90-Day Return</td></tr><tr><td>RETURN_6M</td><td>182-Day Return</td></tr><tr><td>RETURN_1Y</td><td>365-Day Return</td></tr></table>

## C.3 Baselines

In the benchmark experiments, factor-based experiments are conducted using the LightGBM model, and model-based experiments are conducted using the Alpha 20 factor library.

## Machine Learning Models.

• Linear Model: The most basic linear regression model, used to model linear relationships between features and the target variable. It is highly interpretable and has low complexity, serving as the lower bound benchmark for model predictive performance.

• Multilayer Perceptron (MLP): A feedforward neural network architecture that includes one or more nonlinear hidden layers, suitable for modeling nonlinear relationships between features.

• LightGBM [40]: A tree-based model built on the gradient boosting framework. It uses histogrambased split methods and a leaf-wise growth strategy, offering fast training speed and low memory usage. Source code is available at: https://github.com/microsoft/LightGBM.

• XGBoost [45]: An enhanced tree model that utilizes second-order gradient optimization, pruning, and regularization strategies to improve generalization and robustness. Source code is available at: https://github.com/dmlc/xgboost.

• CatBoost [46]: A boosting tree model optimized for categorical features. It employs an ordered boosting strategy to reduce prediction bias and is applicable to a wide range of structured data modeling tasks. Source code is available at: https://github.com/catboost/catboost.

• DoubleEnsemble [47]: Integrates multiple heterogeneous models and combines sample reweighting with feature selection mechanisms to enhance accuracy and robustness. Source code is available at: https://github.com/microsoft/qlib/tree/main/examples/ benchmarks/DoubleEnsemble.

## Deep Learning Models.

## ➠ General Deep Learning Models.

• Transformer [49]: Utilizes multi-head self-attention mechanisms to capture long-range dependencies in time series data. It processes the entire sequence in parallel and offers better scalability compared to recurrent structures.

• GRU [22]: The Gated Recurrent Unit simplifies traditional recurrent neural networks by introducing update and reset gates, improving training efficiency and mitigating gradient vanishing.

• LSTM [23]: The Long Short-Term Memory network is a variant of recurrent neural networks, incorporating memory cells and gating mechanisms to model long-term dependencies effectively. It is one of the standard methods for time series modeling.

• ALSTM [48]: An enhanced version of the LSTM model that integrates an attention mechanism, enabling the model to focus on key time steps and selectively model sequence features.

• GATs [53]: Graph Attention Networks extend the attention mechanism to graph structures, enabling modeling of relationships among nodes in non-Euclidean space.

## ➠ Time-series Forecasting Models.

• PatchTST [50]: A Transformer-based time series model that uses patching and channel independence techniques. It supports effective pretraining and transfer learning across datasets. Source code is available at: https://github.com/yuqinie98/PatchTST.

Table 5: Alpha 20 Baseline Factor Formulas
<table><tr><td>Factor</td><td>Formula</td></tr><tr><td>RESI5</td><td>Resi($close,5)/$close</td></tr><tr><td>WVMA5</td><td>Std(|$close/Ref($close,1)-1| · $volume,5)/(Mean(|$close/Ref($close,1)-1| ·$volume,5)+le-12)</td></tr><tr><td>RSQR5</td><td>Rsquare($close,5)</td></tr><tr><td>KLEN</td><td>($high-$low)/$open</td></tr><tr><td>RSQR10</td><td>Rsquare($close,10)</td></tr><tr><td>CORR5</td><td>Corr(Sclose,log($volume+1),5)</td></tr><tr><td>CORD5</td><td>Corr($close/Ref($close,1),log($volume/Ref($volume,1)+1),5)</td></tr><tr><td>CORR10</td><td>Corr($close,log($volume+1),10)</td></tr><tr><td>ROC60</td><td>Ref($close,60)/$close</td></tr><tr><td>RESI10</td><td>Resi($close,10)/$close</td></tr><tr><td>VSTD5</td><td>Std(Svolume,5)/($volume +le-12)</td></tr><tr><td>RSQR60</td><td>Rsquare($close,60)</td></tr><tr><td>CORR60</td><td>Corr($close,log($volume+1),60)</td></tr><tr><td>WVMA60</td><td>Std($close/Ref(Sclose,1)-1|· $volume,60)/(Mean(|$close/Ref($close,1)-1|· Svolume,60)+1e-12)</td></tr><tr><td>STD5</td><td>Std($close,5)/$close</td></tr><tr><td>RSQR20</td><td>Rsquare($close,20)</td></tr><tr><td>CORD60</td><td>Corr(Sclose/Ref($close,1),log($volume/Ref($volume,1) +1),60)</td></tr><tr><td>CORD10</td><td>Corr(Sclose/Ref($close,1),log($uolume/Ref($volume,1)+1),10)</td></tr><tr><td>CORR20</td><td>Corr($close,log($volume+1),20)</td></tr><tr><td>KLOW</td><td>(Less($open,$close)-$low)/$open</td></tr></table>

• iTransformer [51]: A Transformer-based time series model that embeds each time series as variable tokens, improving parameter efficiency and modeling precision. It is suitable for long-sequence modeling tasks. Source code is available at: https://github.com/thuml/ iTransformer.

• Mamba [52]: A next-generation long-sequence model based on state-space models, offering parallel computation and linear spatiotemporal complexity.

## ➠ Stock Prediction Models.

• TRA [38]: Introduces a novel dynamic routing mechanism into the Transformer architecture, enabling the model to adaptively learn temporal patterns in stock prices and improve its ability to capture diverse market trends. Source code is available at: https://github.com/ TongjiFinLab/THGNN.

• MASTER [39]: A market-centric Transformer model designed to dynamically model instantaneous and cross-temporal correlations among stocks, thereby improving trend prediction accuracy. Source code is available at: https://github.com/SJTU-DMTai/MASTER.

## Factor Libraries.

• Alpha 101 [41]: A collection of 101 formulaic trading alpha factors proposed by the WorldQuant team in 2015. Constructed using daily price-volume data, it represents an early publicly available benchmark of structured alpha factors in quantitative finance.

• Alpha 158 [42]: Proposed by the Microsoft Qlib team, this library includes 158 traditional technical indicators (e.g., MA, RSI) constructed from combinations over different time windows (e.g., 5, 10, 20 days).

• Alpha 360 [43]: A more comprehensive factor library provided by Microsoft Qlib, containing 360 factors constructed via normalization over historical price sequences (e.g., multi-period relative values of closing prices and volumes).

• AutoAlpha [44]: A dynamic structured factor library driven by large language models, integrating multimodal data such as text, numerical values, and images.

## C.4 Evaluation Details

## C.4.1 Metrics

We adopt two classes of metrics: factor-level predictive performance and strategy-level portfolio returns.

Information Coefficient (IC). IC measures the cross-sectional correlation between the predicted ranking and the realized return ranking. It is widely used in quantitative finance and defined as:

$$
\mathbf { I C } = { \frac { ( { \hat { y } } - \mathbb { E } [ { \hat { y } } ] ) ^ { \top } ( y - \mathbb { E } [ y ] ) } { \sigma ( { \hat { y } } ) \cdot \sigma ( y ) } }\tag{11}
$$

where $\hat { y }$ and $y$ denote the predicted and realized rankings, respectively; E[·] is the expectation, and $\sigma ( \cdot )$ is the standard deviation. In practice, IC is computed daily and reported by its mean across time.

Information Coefficient Information Ratio (ICIR). ICIR evaluates the stability of IC over time and is defined as the ratio of the mean and standard deviation of daily IC values:

$$
\mathrm { I C I R } = { \frac { \mathrm { m e a n } ( \mathrm { I C } ) } { \mathrm { s t d } ( \mathrm { I C } ) } }\tag{12}
$$

A higher ICIR indicates more consistent predictive ranking across trading days.

Rank IC. Rank IC refers to the Spearman rank correlation between the predicted and realized return rankings. It is robust to outliers and particularly suitable for distributions with heavy tails or extreme values.

Rank ICIR. Analogous to ICIR, Rank ICIR measures the temporal stability of Rank IC:

$$
{ \mathrm { R a n k ~ I C I R } } = { \frac { { \mathrm { m e a n } } ( { \mathrm { R a n k ~ I C } } ) } { \mathrm { s t d } ( { \mathrm { R a n k ~ I C } } ) } }\tag{13}
$$

It is a key indicator for assessing the long-term consistency of factor-based ranking models.

Annual Return Ratio (ARR). ARR reflects the compound annual growth rate of the portfolio:

$$
\mathrm { A R R } = \left( \prod _ { t = 1 } ^ { T } ( 1 + r _ { t } ) \right) ^ { \frac { 2 5 2 } { T } } - 1\tag{14}
$$

where $r _ { t }$ denotes the daily return, and $T$ is the total number of trading days.

Information Ratio (IR). IR evaluates the risk-adjusted excess return by comparing the annualized mean and standard deviation of returns relative to a benchmark:

$$
\mathbf { I R } = { \frac { \operatorname* { m e a n } ( r _ { t } - r _ { b } ) } { \operatorname* { s t d } ( r _ { t } - r _ { b } ) } } \times { \sqrt { 2 5 2 } }\tag{15}
$$

where $r _ { b }$ denotes the benchmark return $( \mathrm { e . g . }$ , a market index or risk-free asset). When $r _ { b }$ is set to the risk-free rate $r _ { f }$ , the IR coincides with the Sharpe Ratio.

In our setting, $r _ { b } = r _ { f }$ , so IR and Sharpe Ratio values are numerically identical. To improve clarity, we denote this metric as IR (SHR\*) in Table 1, Table 2, Table 7, and Table 8.

Maximum Drawdown (MDD). MDD measures the maximum loss from peak to trough during the evaluation period and captures downside risk:

$$
\mathbf { M D D } = \operatorname* { m a x } _ { t \in [ 1 , T ] } \left( { \frac { \operatorname* { m a x } _ { i \in [ 1 , t ] } P _ { i } - P _ { t } } { \operatorname* { m a x } _ { i \in [ 1 , t ] } P _ { i } } } \right)\tag{16}
$$

where $P _ { t }$ is the portfolio value on day $t ,$ and T is the evaluation horizon.

Calmar Ratio. The Calmar Ratio quantifies return relative to downside risk and is defined as:

$$
\mathrm { C a l m a r R a t i o } = { \frac { \mathrm { A R R } } { | \mathrm { M D D } | } }\tag{17}
$$

A higher Calmar Ratio indicates better return per unit of maximum loss, making it suitable for evaluating strategies that emphasize drawdown control.

## C.4.2 Trading Strategy

The full trading strategy is simulated as follows:

• On the close of trading day t, the model generates a ranking score for each stock based on its predicted return.

• At the open of trading day t + 1, the trader sells all holdings from day t and selects the top 50 stocks by ranking to construct a new portfolio based on predicted returns. The bottom 5 performing stocks are excluded.

• Stocks that remain consistently highly ranked are retained in the portfolio to support the long-term holding of high-quality assets.

• During trade execution, a price limit threshold of 0.095 is applied. Trades are executed at the closing price, with a buy cost of 0.05%, a sell cost of 0.15%, and a minimum transaction fee of 5 CNY per trade.

## D Supplementary Experiments

## D.1 Empirical Scope and Generalizability Analysis

To further evaluate the effectiveness and generalizability of R&D-Agent(Q), we conducted a series of out-of-sample experiments on two additional markets, namely the CSI 500 and the NASDAQ 100.

For both datasets, we adopt a consistent temporal split, using the period from January 1, 2008, to December 31, 2021, for training, January 1, 2022, to December 31, 2023, for validation, and January 1, 2024, to June 30, 2025, for testing. Regarding the large language model (LLM) backends, we employ GPT-4o, whose training cutoff date is October 1, 2023, entirely preceding our test horizon, and o4-mini, whose training cutoff date is June 1, 2024, which remains almost entirely prior to the designated test period.

For the CSI 500 experiments, we apply the same trading settings as those used for the CSI 300 (see Appendix C.4.2). For the NASDAQ 100, we adopt market-specific settings, including portfolio rebalancing by selecting the top 20 stocks in each period (in contrast to 50 stocks for the CSI 300), a transaction cost of 0.1% per trade (as opposed to 0.5% in CSI 300), and the absence of daily price limits. The resulting out-of-sample performance on both the NASDAQ 100 and CSI 500 markets is summarized below.

As shown in Fig. 7 and Fig. 8, R&D-Agent(Q) consistently achieves strong out-of-sample performance across markets, instruments, and time periods not included in LLM training, providing further evidence for the robustness and real-world applicability of our approach.

## D.2 Ablation Analysis

Table 9 presents an extended ablation study of the R&D-Agent(Q) framework across two LLM backends (GPT-4o and o3-mini). We evaluate component-level contributions and compare three scheduling strategies for action selection: random, LLM-based, and contextual bandit.

Component Ablation. Removing the model branch (R&D-Factor) consistently yields stronger IC, ICIR, and ARR than removing the factor branch (R&D-Model). This reflects two effects: (i) factor optimization enables faster iteration and greater signal discovery under tight runtime; (ii) in early-stage pipelines, improved features have a larger impact than tuning the model. Nonetheless, R&D-Model contributes to portfolio-level risk smoothing (e.g., lower MDD with o3-mini).

Algorithm Ablation. For scheduling, random selection yields the lowest performance across both models. LLM-based decisions improve predictive quality but suffer from planning instability. The

Table 7: Out-of-sample experimental results on the CSI 500 dataset (tested from 2024 to June 2025), including factor predictive metrics and strategy performance metrics. Visual cues indicate ranking groups: Best , Second Best , Good (3–5) , Average (6–10) , Poor (11–15) , and

Worse (16–19) .

<table><tr><td rowspan="2" colspan="2">Models</td><td colspan="8">CSI500</td></tr><tr><td colspan="4">Factor Predictive PowerMetrics</td><td colspan="4">Performance Metrics</td></tr><tr><td rowspan="4">Machine-Learning Models</td><td></td><td>IC</td><td>ICIR</td><td>Rank IC</td><td>Rank ICIR</td><td>ARR</td><td>IR (SHR*)</td><td>MDD</td><td>CR</td></tr><tr><td>LightGBM</td><td>0.0181 0.0240</td><td>0.1271 0.1675</td><td>0.0393</td><td>0.2783</td><td>-0.0294</td><td>-0.3178</td><td>-0.2089</td><td>-0.1407</td></tr><tr><td>XGBoost</td><td>0.0241</td><td>0.1629</td><td>0.0427 0.0390</td><td>0.3054 0.2627</td><td>0.0053 0.0111</td><td>0.0634 0.1438</td><td>-0.1766 -0.1799</td><td>0.0300</td></tr><tr><td>CatBoost DoubleEnsemble</td><td>0.0248</td><td>0.1705</td><td>0.0423</td><td>0.2850</td><td>0.0227</td><td>0.2500</td><td>-0.2094</td><td>0.0617 0.1084</td></tr><tr><td rowspan="6">Deep-Learning Models</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Transformer</td><td>0.0194 0.0188</td><td>0.1355</td><td>0.0416</td><td>0.2884</td><td>0.0234</td><td>0.2898</td><td>-0.1331</td><td>0.1758</td></tr><tr><td>GRU</td><td>0.0219</td><td>0.1022</td><td>0.0512</td><td>0.2711</td><td>0.0398</td><td>0.3716</td><td>-0.1602</td><td>0.2484</td></tr><tr><td>LSTM</td><td>0.0162</td><td>0.1434</td><td>0.0401</td><td>0.2825</td><td>0.0560</td><td>0.6900</td><td>-0.1075</td><td>0.5209</td></tr><tr><td>GATs</td><td>0.0161</td><td>0.1013</td><td>0.0426</td><td>0.2731</td><td>0.0478</td><td>0.5168</td><td>-0.1569</td><td>0.3047</td></tr><tr><td>iTransformer TRA</td><td>0.0260</td><td>0.1031 0.1813</td><td>0.0383 0.0464</td><td>0.2278 0.3285</td><td>0.0102 0.0504</td><td>0.0985 0.6040</td><td>-0.1496 -0.1461</td><td>0.0682 0.3450</td></tr><tr><td rowspan="4">Factor Libraries</td><td>Alpha 158</td><td>0.0192</td><td>0.1353</td><td>0.0374</td><td>0.2639</td><td>0.0199</td><td>0.2515</td><td>-0.1771</td><td>0.1124</td></tr><tr><td>Alpha 360</td><td>0.0195</td><td>0.1331</td><td>0.0308</td><td>0.2089</td><td>0.0191</td><td>0.2527</td><td>-0.1270</td><td>0.1504</td></tr><tr><td>AutoAlpha</td><td>0.0184</td><td>0.1529</td><td>0.0175</td><td>0.1382</td><td>0.0397</td><td>0.5728</td><td>-0.1006</td><td>0.3946</td></tr><tr><td></td><td>0.0201</td><td>0.1709</td><td>0.0176</td><td>0.1404</td><td>0.1010</td><td>1.3730</td><td></td><td></td></tr><tr><td rowspan="5">R&amp;D-Agent Series Framework*</td><td>R&amp;D-FactorGPT-40 R&amp;D-Factoro4-mini</td><td>0.0264</td><td>0.2652</td><td>0.0345</td><td>0.3454</td><td>0.0849</td><td>1.0014</td><td>-0.0787 -0.1215</td><td>1.2833 0.6985</td></tr><tr><td></td><td>0.0259</td><td>0.1649</td><td>0.0532</td><td>0.3469</td><td>0.1039</td><td>1.0941</td><td>-0.1367</td><td>0.7600</td></tr><tr><td>R&amp;D-ModelGPT-40</td><td>0.0265</td><td>0.1825</td><td>0.0521</td><td>0.3616</td><td>0.1160</td><td>1.4021</td><td>-0.0735</td><td>1.5777</td></tr><tr><td>R&amp;D-Modelo4-mini</td><td>0.0241</td><td>0.1532</td><td>0.0555</td><td>0.3574</td><td>0.1358</td><td>1.4227</td><td>-0.0803</td><td>1.6903</td></tr><tr><td>R&amp;D-Agent(Q)GPT-40 R&amp;D-Agent(Q)o4-mini</td><td>0.0288</td><td>0.1828</td><td>0.0564</td><td>0.3523</td><td>0.1982</td><td>2.1721</td><td>-0.0656</td><td>3.0229</td></tr></table>

Table 8: Out-of-sample experimental results on the NASDAQ 100 dataset (tested from 2024 to June 2025), including factor predictive metrics and strategy performance metrics. Visual cues indicate ranking groups: Best , Second Best , Good (3–5) , Average (6–10) , Poor (11–15) , and

Worse (16–19)

<table><tr><td rowspan="2" colspan="2">Models</td><td colspan="8">NASDAQ100</td></tr><tr><td colspan="4">Factor Predictive Power Metrics</td><td colspan="4">Performance Metrics</td></tr><tr><td rowspan="4">Machine-Learning Models</td><td></td><td>IC</td><td>ICIR</td><td>Rank IC</td><td>Rank ICIR</td><td>ARR</td><td>IR (SHR*)</td><td>MDD</td><td>CR</td></tr><tr><td>LightGBM</td><td>0.0080</td><td>0.0652</td><td>0.0087</td><td>0.0842</td><td>-0.0293</td><td>-0.2603</td><td>-0.1342</td><td>-0.2183</td></tr><tr><td>XGBoost</td><td>0.0076 0.0095</td><td>0.0527 0.0614</td><td>0.0112 0.0129</td><td>0.0841 0.1005</td><td>0.0169 -0.0083</td><td>0.1544 -0.0735</td><td>-0.1211</td><td>0.1396</td></tr><tr><td>CatBoost DoubleEnsemble</td><td>0.0047</td><td>0.0360</td><td>0.0086</td><td>0.0683</td><td>-0.0005</td><td>-0.0046</td><td>-0.1148 -0.1404</td><td>-0.0723 -0.0036</td></tr><tr><td rowspan="6">Deep-Learning Models</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>Transformer</td><td>-0.0011</td><td>-0.0077</td><td>0.0092</td><td>0.0686</td><td>-0.0037</td><td>-0.0343</td><td>-0.1553</td><td>-0.0238</td></tr><tr><td>GRU</td><td>0.0064</td><td>0.0457</td><td>0.0147</td><td>0.1075</td><td>0.0347</td><td>0.2930</td><td>-0.1504</td><td>0.2307</td></tr><tr><td>LSTM</td><td>0.0062</td><td>0.0409</td><td>0.0150</td><td>0.1084</td><td>0.0550</td><td>0.4526</td><td>-0.1204</td><td>0.4568</td></tr><tr><td>GATs</td><td>-0.0004</td><td>-0.0023</td><td>0.0169</td><td>0.1015</td><td>0.0677</td><td>0.5772</td><td>-0.1491</td><td>0.4541</td></tr><tr><td>iTransformer TRA</td><td>0.0076 0.0058</td><td>0.0421 0.0446</td><td>0.0041 0.0098</td><td>0.0225 0.0825</td><td>0.0617 0.0505</td><td>0.3612 0.4608</td><td>-0.1991 -0.1351</td><td>0.3099 0.3738</td></tr><tr><td rowspan="4">Factor Libraries</td><td>Alpha 158</td><td>0.0040</td><td>0.0324</td><td>0.0069</td><td>0.0624</td><td>0.0038</td><td>0.0303</td><td>-0.1140</td><td>0.0333</td></tr><tr><td>Alpha 360</td><td>0.0042</td><td>0.0327</td><td>0.0086</td><td>0.0728</td><td>0.0756</td><td>0.5890</td><td>-0.1182</td><td>0.6396</td></tr><tr><td>AutoAlpha</td><td>0.0046</td><td>0.0265</td><td>-0.0052</td><td>-0.0432</td><td>0.0154</td><td>0.0974</td><td>-0.1165</td><td>0.1326</td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td rowspan="6">R&amp;D-Agent Series Framework*</td><td>R&amp;D-FactorGPT-40</td><td>0.0070</td><td>0.0446</td><td>0.0039</td><td>0.0357</td><td>0.1497 0.1693</td><td>1.0985</td><td>-0.0977</td><td>1.5335</td></tr><tr><td>R&amp;D-Factoro4-mini</td><td>0.0166 0.0128</td><td>0.1017</td><td>0.0050</td><td>0.0407</td><td>0.1167</td><td>1.1169 1.0742</td><td>-0.0650 -0.0842</td><td>2.6059</td></tr><tr><td>R&amp;D-ModelGPT-40</td><td>0.0081</td><td>0.0831 0.0484</td><td>0.0215 0.0213</td><td>0.1427 0.1355</td><td>0.1367</td><td>1.2671</td><td>-0.0741</td><td>1.3869 1.8444</td></tr><tr><td>R&amp;D-Modelo4-mini</td><td>0.0172</td><td>0.0908</td><td>0.0067</td><td>0.0490</td><td>0.2328</td><td>1.3312</td><td>-0.1044</td><td>2.2292</td></tr><tr><td>R&amp;D-Agent(Q)GPT-4o</td><td>0.0162</td><td>0.1035</td><td>0.0083</td><td>0.0673</td><td>0.2840</td><td>1.7737</td><td>-0.0634</td><td>4.4814</td></tr><tr><td> $\mathrm { R \& D \mathrm { - A g e n t ( Q ) _ { o 4 - m i n i } } }$ </td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr></table>

Bandit scheduler consistently outperforms alternatives in IC, ARR, and valid loop count, demonstrating superior resource allocation by adapting to evolving performance signals.

Overall, the results highlight the factor branch as the main driver of signal quality, the model branch as a risk stabilizer, and the Bandit scheduler as an efficient mechanism to manage trade-offs under limited time and compute budgets.

## D.3 Factor Library Analysis

Fig. 10 shows the complete results of Factor Effects evaluation experiment. Beyond IC (subfigures (a) and (c)), subfigures (b) and (d) show consistent gains in Rank IC, confirming that R&D-Factor not only improves absolute prediction accuracy but also enhances relative ranking of stock returns.

Table 9: Ablation study of the R&D-Agent(Q) framework. The top rows show component-level ablations by disabling either factor or model generation. The bottom rows compare action selection strategies in R&D-Agent(Q): random, LLM-based, and Bandit. Metrics include factor predictive power (IC, ICIR), strategy performance (ARR, MDD), and execution statistics (TL: total loops; VL: valid loops; SL: SOTA selections; TRH: total runtime in hours).
<table><tr><td rowspan="2" colspan="2">Models</td><td colspan="2">Factor Predictive Power Metrics</td><td colspan="2">Performance Metrics</td><td colspan="4">Execution Metrics</td></tr><tr><td>IC</td><td>ICIR</td><td>ARR</td><td>MDD</td><td>TL</td><td>VL</td><td>SL</td><td>TRH</td></tr><tr><td colspan="10">GPT-40</td></tr><tr><td rowspan="2">Component Ablation</td><td>R&amp;D-Factor</td><td>0.0489</td><td>0.4050</td><td>0.1461</td><td>-0.0750</td><td>36</td><td>33</td><td>9</td><td>6</td></tr><tr><td>R&amp;D-Model</td><td>0.0326</td><td>0.2305</td><td>0.1229</td><td>-0.0876</td><td>23</td><td>12</td><td>5</td><td>6</td></tr><tr><td rowspan="3">Algorithm Ablation</td><td>R&amp;D-Agent(Q)w/random</td><td>0.0318</td><td>0.2431</td><td>0.0914</td><td>-0.0782</td><td>36</td><td>18</td><td>7</td><td>12</td></tr><tr><td>R&amp;D-Agent (Q)w/LLM</td><td>0.0523</td><td>0.4172</td><td>0.0940</td><td>-0.0989</td><td>32</td><td>19</td><td>6</td><td>12</td></tr><tr><td>R&amp;D-Agent(Q)w/Bandit</td><td>0.0497</td><td>0.4069</td><td>0.1144</td><td>-0.0811</td><td>38</td><td>22</td><td>8</td><td>12</td></tr><tr><td colspan="10">o3-mini</td></tr><tr><td rowspan="2">Component Ablation</td><td>R&amp;D-Factor</td><td>0.0497</td><td>0.3931</td><td>0.1184</td><td>-0.0910</td><td>28</td><td>16</td><td>6</td><td>6</td></tr><tr><td>R&amp;D-Model</td><td>0.0469</td><td>0.3688</td><td>0.1009</td><td>-0.0694</td><td>30</td><td>15</td><td>7</td><td>6</td></tr><tr><td rowspan="3">Algorithm Ablation</td><td>R&amp;D-Agent(Q)w/random</td><td>0.0445</td><td>0.3589</td><td>0.0897</td><td>-0.1004</td><td>33</td><td>19</td><td>7</td><td>12</td></tr><tr><td>R&amp;D-Agent(Q)w/LLM</td><td>0.0476</td><td>0.3891</td><td>0.1009</td><td>-0.0794</td><td>33</td><td>20</td><td>5</td><td>12</td></tr><tr><td>R&amp;D-Agent (Q)w/Bandit</td><td>0.0532</td><td>0.4278</td><td>0.1421</td><td>-0.0742</td><td>44</td><td>24</td><td>8</td><td>12</td></tr></table>

Especially under Alpha 158 initialization, Rank IC remains above 0.07 in 2020 with o3-mini, while classical libraries decline sharply. This supports the claim that iterative refinement improves both signal strength and ranking consistency across regimes.

In terms of cumulative return (subfigure (e)), performance divergence becomes evident from early 2018. Factor sets generated by R&D-Factor(158) consistently outperform others, ending with a net asset value (NAV) exceeding 5.1 by 2020 Q3. Even R&D-Factor(20) configurations surpass Alpha360, indicating that larger factor sets do not necessarily yield higher returns. Traditional libraries suffer from increased volatility due to factor redundancy. In contrast, R&D-Factor mitigates this through dynamic filtering, achieving more stable and capital-efficient performance.

These results underscore R&D-Factor’s dual advantage in information efficiency (achieving higher IC/Rank IC with fewer factors) and capital efficiency (delivering superior NAV). Whether starting from a compact or high-dimensional base, its iterative refinement pipeline reliably discovers effective signals and removes redundancies, laying a solid foundation for subsequent model optimization and full-stack co-evolution in RD-Quant.

## D.4 Co-STEER Effectiveness Analysis

As a key component of the Development Phase in R&D-Agent(Q), in addition to the direct implementation of Co-STEER within the R&D-Agent(Q) framework described in Section 4, we conducted further experiments to validate the capabilities of Co-STEER. Specifically, we want to answer the following research questions.

• RQ1: How well does Co-STEER perform in generating executable and semantically correct code for financial tasks, compared to recent code generation baselines?

• RQ2: Can its evolving scheduler improve implementation efficiency and output quality under constrained compute budgets?

Dataset. We evaluate Co-STEER on RD2Bench [76], a comprehensive benchmark for datacentric agent systems in finance. The benchmark encompasses both implementable 27 and nonimplementable 13 factors, spanning fundamental, price-volume, and high-frequency categories. Each factor presents unique challenges, requiring sophisticated reasoning over heterogeneous financial data sources and the generation of executable Python code under strict constraints.

Baselines. We adopted Few-shot [71], CoT [35], Reflexion [72], Self-Debugging [74], and Self-Planning [73] as baselines. For details, see Section A.1.

Metrics. We introduced four evaluation metrics: average execution rate, average formatting correctness, average correlation, and maximum correlation. The average execution rate metric is used to measure the average success rate of code execution; any error encountered during execution is counted as 0. The average formatting correctness metric is used to measure the degree to which the generated code adheres to the correct format, such as whether column names meet expectations. The average correlation metric reflects the average correlation between the code output sequence generated by the model and the ground truth results. For example, given the same input features, it evaluates the correlation between the factors generated by a large language model and those generated by actual implementation. The maximum correlation metric represents the highest correlation between the code output sequence generated by the model and the ground truth results.

(a)Yearly IC: R&D-Factor (based on Alpha 20) vs Baseline  
![](images/05fc945f8d11faae362f773004b36847ff05e37c8e803149aef1ffbb0325195f.jpg)  
(c) Yearly IC:R&D-Factor (based on Alpha 158)vs Baseline

(b) Yearly RanklC: R&D-Factor (based on Alpha 20) vs Baseline  
![](images/c7b91cd108a29a448f44e7424e6b2418d7c4b0dc19788ee8a44dc5140f2f6a3f.jpg)  
(d) Yearly RanklC:R&D-Factor (based on Alpha 158) vs Baseline

![](images/b82698512c1d413b144a9987922b9a86354856940b749516405223ec97f82bdb.jpg)

![](images/273c273be7dde705e94a2caeb45ffc4545ab5d00a747627cd2101a77ce2ee4ea.jpg)

(e) Cumulative Return (NAV)  
![](images/10ce6aaf0ffc3eff923bc0d4e0af9bce4d6dc54bc4d92af89693bc8399d127db.jpg)  
Figure 10: Comparison between classical factor libraries and R&D-Factor-generated factors using a LightGBM predictor on CSI 300. R&D-Factor was initialized from Alpha 20 or Alpha 158 and operated with GPT-4o or o3-mini. The top left figure shows the IC values of each method across different years, while the top right figure shows the RankIC values—the higher the value, the stronger the predictive power. The bottom figure presents the cumulative returns (NAV) of the corresponding strategies.

## Results of Method Implementation (RQ1).

Table 10: Results of method implementation. All the agent workflows are based on GPT-4-turbo.
<table><tr><td>Methods</td><td>avg. exec.</td><td>avg. format</td><td>avg. corr.</td><td>max.corr.</td></tr><tr><td>Few-shot [71]</td><td>0.733</td><td>0.433</td><td>0.454</td><td>0.562</td></tr><tr><td>CoT[35]</td><td>0.833</td><td>0.433</td><td>0.336</td><td>0.538</td></tr><tr><td>Reflexion [72]</td><td>0.822</td><td>0.400</td><td>0.269</td><td>0.550</td></tr><tr><td>Self-Debugging [74]</td><td>0.367</td><td>0.256</td><td>0.232</td><td>0.539</td></tr><tr><td>Self-Planning [73]</td><td>0.578</td><td>0.211</td><td>0.119</td><td>0.341</td></tr><tr><td>Co-STEER (ours)</td><td>0.889</td><td>0.611</td><td>0.646</td><td>0.887</td></tr></table>

Experimental results in Table 10 demonstrate Co-STEER’s superior implementation capabilities across all evaluation metrics on our 27 test cases. This performance advantage stems from two key innovations: dynamic knowledge expansion and contextual retrieval. While both Reflexion and Self-Debugging leverage environmental feedback (Table 4), Co-STEER uniquely accumulates and retrieves practical experience across implementations. Unlike existing approaches that only consider immediate feedback, Co-STEER builds a comprehensive knowledge base through continuous practice, effectively bridging the expertise gap between junior and senior engineers. This systematic knowledge accumulation and retrieval mechanism enables Co-STEER to achieve significant performance gains across diverse implementation scenarios.

Overall Performance Analysis (RQ2). We evaluate Co-STEER’s effectiveness in a resourceconstrained environment, where agents must optimize performance across 40 candidate methods (27 implementable, 13 non-implementable) with limited implementation attempts. This setup mirrors real-world computational constraints and tests the synergy between scheduling and implementation capabilities. Table 11 presents comparative results, revealing several key insights about system performance under practical constraints.

Table 11: Comparison of Co-STEER with random and evolving schedulers under top-k evaluation (for k = 5, 10, 15, 20). Metrics include execution success rate (exec.), format correctness, and correlation with ground truth (average and maximum).
<table><tr><td></td><td colspan="4">Top 5</td><td colspan="4">Top 10</td></tr><tr><td>Methods</td><td></td><td>exec. format</td><td> avg. corr. max.corr. exec. 1</td><td></td><td></td><td>format :</td><td></td><td> avg. corr. max. corr.</td></tr><tr><td>Random Scheduler</td><td>0.522</td><td>0.400</td><td>0.211</td><td>0.444</td><td>0.567</td><td>0.289</td><td>0.417</td><td>0.655</td></tr><tr><td>Evolving Scheduler 0.765</td><td></td><td>0.259</td><td>0.280</td><td>0.515</td><td>0.815</td><td>0.358</td><td>0.519</td><td>0.778</td></tr><tr><td></td><td></td><td></td><td>Top 15</td><td></td><td></td><td></td><td>Top 20</td><td></td></tr><tr><td>Random Scheduler</td><td>0.856</td><td>0.544</td><td>0.594</td><td>0.778</td><td>0.911</td><td>0.589</td><td>0.532</td><td>0.778</td></tr><tr><td>Evolving Scheduler (</td><td>0.856</td><td>0.556</td><td>0.584</td><td>0.872</td><td>0.878</td><td>0.567</td><td>0.792</td><td>0.987</td></tr></table>

❶ Evolving scheduling improves task effectiveness. Table 11 shows that the evolving scheduler consistently outperforms the random baseline across all top-k thresholds. This highlights its ability to learn effective execution orderings by identifying task complexity and dependencies. By accumulating experience over time, the system builds a form of engineering intuition, allowing it to prioritize easier or foundational tasks that unlock downstream implementation success.

❷ More resources lead to stronger generalization. As more budget is allocated, both schedulers benefit, but the evolving strategy shows greater gains. Unlike self-correction approaches that plateau early, the evolutionary process continues improving by retrieving and refining past attempts—regardless of whether initial trials were successful. This co-evolution between scheduler and implementation enables efficient adaptation under practical constraints.

## D.5 Cost Efficiency Analysis

Fig. 11 compares token expenditures of GPT-4o and o3-mini under fixed runtime settings. Factor tasks incur higher cost per loop due to their multi-stage structure—spanning hypothesis generation, implementation, and analysis for multiple candidates—whereas model tasks are simpler and less costly, as each loop generates only one model. GPT-4o and o3-mini show similar per-loop costs in model and quant settings. The larger gap in factor tasks stems from o3-mini generating more complex hypotheses per loop (producing more diverse factor types and handling more difficult implementations), resulting in higher costs. Despite these differences, both backends keep total costs under \$10 across all R&D-Agent(Q) workflows (see Appendix C.1), confirming the framework’s cost-effectiveness for scalable, automated quantitative research.

## D.6 Real-World Quantitative Competition Analysis

To further explore the potentials of R&D-Agent(Q) frameworks, we utilize R&D-Agent(Q) for the Optiver Realized Volatility Prediction [77] competition on Kaggle. This is a forecasting competition focused on predicting short-term volatility for hundreds of stocks using highly granular financial data. The competition challenges participants to predict the realized volatility of a set of stocks using information collected over a 10-minute time window, involving working with classic tabular time-series data and optimizing the Root Mean Squared Percentage Error (RMSPE) metric.

As shown in Fig. 12, the R&D-Agent(Q) achieved its best performance in the 12th experiment. According to the experiment summary, this experiment was based on the hypothesis that by capturing the temporal evolution of bid-ask spreads across different time windows, the model’s ability to predict short-term stock volatility can be enhanced. The specific implementation involved calculating the rolling averages and standard deviations of bid-ask spreads over multiple time windows (5 seconds, 10 seconds, and 30 seconds) to efficiently capture the dynamic characteristics of market microstructure. Overall, from the optimization of the model in the 3rd round to the factor tuning in the 8th and 12th rounds, through continuous experimentation and exploration, R&D-Agent(Q) discovered that capturing the temporal features of bid-ask spread dynamics was most effective for this financial task. This also demonstrates that R&D-Agent(Q) can explore among many possible modeling approaches and, through empirical evaluation rather than relying solely on intuition or predetermined strategies, rationally identify the most promising directions. Furthermore, the R&D-Agent(Q) framework can be adapted to various quantitative financial tasks and performs relatively well.

![](images/192d900c0b916d014e53b3961e36d535b8cd4439b5361cff4dd27f2603b05f85.jpg)

![](images/dd52421388fdea01e3d6004296654345166aebc01b48c9a769ad90a4ddee227c.jpg)  
Figure 11: Token cost across different large language model backends (averaged over 5 trials). Left: total cost over corresponding runtimes (6h for R&D-Factor/R&D-Model, 12h for R&D-Agent(Q)); right: average per-loop cost. All costs are in USD.

Optiver Realized Volatility Prediction  
![](images/0d04d97d7abe1eab8917487edd4614a3756f6e78a3d9a6eba89f2aca86a13adb.jpg)  
Figure 12: The RMSPE curve and fitted curve of R&D-Agent on Optiver Realized Volatility Prediction.

<table><tr><td>Generated Hypotheses of R&amp;D-Agent on Optiver Realized Volatility Prediction Competition</td></tr><tr><td>Experiment Loop Index 1</td></tr><tr><td>Action: Construct Pipeline Hypothesis: /</td></tr><tr><td>Conclusion: /</td></tr><tr><td>Experiment Loop Index 2 Action: Model</td></tr><tr><td></td></tr><tr><td>Hypothesis: Introducing a Gradient Boosting model, like LightGBM, with optimized hyper-</td></tr></table>

parameters will outperform the current linear regression model and ensemble strategy.   
Conclusion: Failed.   
Experiment Loop Index 3   
Action: Model   
Hypothesis: Replacing the linear regression model with a LightGBM model and using early   
stopping will improve the performance by capturing complex patterns better.   
Conclusion: Success   
...   
Experiment Loop Index 8   
Action: Factor   
Hypothesis: Incorporating features that capture the interaction between bid and ask prices,   
such as bid-ask spread and order imbalance, will enhance the model’s ability to predict   
short-term stock volatility.   
Conclusion: Success   
...   
Experiment Loop Index 12   
Action: Factor   
Hypothesis: Incorporating features that capture the temporal evolution of bid-ask spreads   
over different time windows will enhance the model’s ability to predict short-term stock   
volatility.   
Conclusion: Success   
...

## E Prompt Design

## E.1 Specification Unit

As described in Section 2.1, the Specification Unit is responsible for dynamically generating the tuple S based on the current optimization objective. Downstream units selectively access components of S according to their functional roles—for instance, the Synthesis Unit and Analysis Unit typically use B, D, and M, while the Implementation Unit relies on D, F , and M.

Below, we provide the complete specification tuple for both factor and model optimization settings.

Specification Prompt – Factor-Oriented   
You are one of the most authoritative quantitative researchers at a top Wall Street hedge fund.   
I need your expertise to design and implement new factors or models to enhance investment   
returns.   
This time, I need your help with the research and development of the factor.   
Scenario Background   
• Name: Factor name.   
• Description: Explanation of the factor logic.   
• Formulation: Mathematical expression.   
• Variables: All used variables or intermediate functions.   
Clearly list all hyperparameters, such as lookback periods, window sizes, etc. Each factor   
must produce one output using a static data source. Different parameterizations count as   
different factors.   
Source Dataset   
daily\_pv.h5   
• Type: HDF5   
• Index: MultiIndex [datetime, instrument]   
• Columns: \$open, \$high, \$low, \$close, \$volume, \$factor, ...   
Output Format   
• Python file executable via: python {your\_file\_name}.py   
• Includes: import section, function section, and a main function named calcu  
late\_{function\_name}.

• Called under: if \_\_name\_\_ == "\_\_main\_\_"

• Do not use try-except.

• Output: Save computed factor to result.h5 as a pandas DataFrame with index [datetime, instrument] and one column named by the factor.

## Workflow Mechanism

1. Qlib generates a feature table from the factor values.

2. Trains models (e.g., LightGBM, LSTM, GRU) to predict future returns.

3. Builds portfolio based on predicted returns.

4. Evaluates performance (return, Sharpe ratio, max drawdown, etc.).

## Specification Prompt – Model-Oriented

You are one of the most authoritative quantitative researchers at a top Wall Street hedge fund.   
I need your expertise to design and implement new models to enhance investment returns.   
This time, I need your help with the research and development of the model.

Scenario Background The model is a machine learning or deep learning structure used in quantitative investment to predict the returns and risks of a portfolio or a single asset. Models are employed to generate forecasts based on historical data and extracted factors, forming the core of many quantitative investment strategies.

Each model takes factor values as input and predicts future returns. Models are defined with a fixed architecture and hyperparameters to ensure reproducibility and consistency. Each model should include the following components:

• Name: The name of the model.

• Description: Explanation of the model logic and purpose.

• Architecture: The internal structure of the model (e.g., LSTM layers, MLP, decision trees).

• Hyperparameters: All hyperparameters related to model structure.

• Training\_hyperparameters: The hyperparameters used in training (e.g., learning rate, batch size).

• ModelType: One of "Tabular" or "TimeSeries" to indicate the input format.

The model must output one predicted return value. Different sets of hyperparameters define different models.

## Source Dataset

daily\_pv.h5

• Type: HDF5

• Index: MultiIndex [datetime, instrument]

• Columns: \$open, \$high, \$low, \$close, \$volume, \$factor, ...

## Output Format

• Python file named model.py containing a PyTorch model definition.

• Includes the following parts:

– Import section: Import only necessary libraries (e.g., torch, torch.nn).

– Model class: A subclass of torch.nn.Module implementing \_\_init\_\_ and forward.

– Model interface: A variable named model\_cls must be assigned to the defined model class.

• The model must follow these interface constraints:

– For Tabular input: input shape = (batch\_size, num\_features).

– For TimeSeries input: input shape = (batch\_size, num\_timesteps, num\_features).

– Output shape must always be (batch\_size, 1).

– The model must only use current input tensor, no external data loading or saving.

– No other arguments will be passed; model must accept either: (num\_features) or (num\_features, num\_timesteps).

• Do not include any try-except blocks.

• Do not include any training, inference, or saving logic.

• The user will import the model class via: from model import model\_cls   
Workflow Mechanism   
1. Qlib generates a feature table from the factor values.   
2. Trains models (e.g., LightGBM, LSTM, GRU) to predict future returns.   
3. Builds portfolio based on predicted returns.   
4. Evaluates performance (return, Sharpe ratio, max drawdown, etc.).

## E.2 Synthesis Unit

After receiving the dynamically assembled specification tuple from the Specification Unit, the Synthesis Unit leverages its evolving knowledge forest to propose new hypothesis. This is then decomposed into actionable research tasks.

Below is the prompt used when the optimization target is a factor:

## System prompt:

The user has proposed several hypotheses and conducted evaluations. Your task is to analyze these trials, identify why those labeled true were successful, and why those labeled false failed. Then propose how to improve — either by refining existing approaches or exploring a new one.

## Guidelines for Hypothesis Generation:

2. Start with simple, easy-to-implement factors. Avoid complex or combined factors at the beginning. Clearly explain their rationale.

3. Increase complexity gradually. Introduce advanced or combined factors only after simpler ones are validated.

4. If several iterations fail to outperform SOTA, restart with a new direction beginning from simple factors. Optimize a given factor type from simple to complex.

5. Record factors that surpass SOTA to prevent redundant implementation.

```jsonl
{
" action ": " factor ",
" hypothesis ": " The new hypothesis generated based on the
information provided .",
" reason ": " Comprehensive explanation for the new hypothesis ."
}
```

## User prompt:

The former hypotheses and the corresponding feedbacks are as follows:

Trial 1

• Action: factor

• Hypothesis: Develop simple momentum-based and price-volume factors using daily price and volume data.

• Reason: Momentum and price-volume factors are simple yet effective for quant investment. They capture underlying trends and trading activity, which can be indicative of future returns. Testing these straightforward factors will provide a

baseline for performance and help identify potential opportunities for more complex factor development in subsequent iterations.

## • Specific Factors:

– factor\_name: 10\_day\_momentum factor\_description: [Momentum Factor] The momentum factor captures the tendency of stocks with positive recent performance to continue performing well in the near future. Specifically, this factor calculates the return over the past 10 days.

factor\_formulation: $\begin{array} { r } { M O M _ { 1 0 } = \frac { P _ { t } } { P _ { t - 1 0 } } - 1 } \end{array}$

– factor\_name: 10\_day\_volatility factor\_name: 10\_day\_volatility

factor\_description:[Price-Volume Factor] The average volume factor captures the average trading volume over the past 10 days, indicating the level of trading activity. Higher trading volume can signal stronger price movements. factor\_formulation: $V O \bar { L } _ { 1 0 } = \mathrm { s t d } ( R _ { t - i } ) , i = 0 \ldots 9$

• Observation: The newly developed momentum-based and price-volume factors show promising results in the context of the given hypothesis. All implemented factors consistently contributed to a performance that surpassed the previous SOTA results. Specifically, improvements were observed in terms of both the Information Coefficient (IC) and annualized return, which are critical metrics for assessing a predictive model’s effectiveness. However, it is noted that the maximum drawdown has worsened compared to the SOTA benchmark.

• Evaluation: The results support the hypothesis that simple momentum-based and price-volume factors can enhance model performance in quantitative investment. The significant improvement in IC and annualized return suggests that these factors effectively capture underlying patterns and trends in stock performance.

• Decision: True

## Trial 2

## The SOTA hypothesis and the corresponding feedback are as follows:

• Action: factor

• Hypothesis: ...

• Reason: ...

• Specific Factors: ...

• Observation: ...

• Evaluation: ...

• Decision: True

## Last hypothesis and the corresponding feedback are as follows:

• Action: factor

• Hypothesis: ...

• Reason: ...

• Specific Factors: ...

• Observation: ...

• Evaluation: ...

• Decision: ...

• New Hypothesis (from the Analysis Unit, for reference): ...

• Reason: ...

Example Output:   
{   
" action ": " factor ",   
" hypothesis ": " Incorporate advanced variations and   
combinations of existing momentum -based , price -volume , and   
volatility factors . Introduce factors like cumulative   
returns , turnover ratios , or volatility clustering

measures to further refine performance while potentially   
minimizing drawdowns .",   
" reason ": " The previous trials successfully demonstrated that   
basic momentum - based and price - volume factors can improve   
performance metrics like IC and annualized return .   
However , the increased drawdown indicates a potential need   
for more sophisticated risk control . By using advanced   
variations , such as factor combinations and new risk   
measures , we may optimize returns and address volatility   
concerns . This aligns with the feedback suggesting more   
complex factor formulations for enhanced predictability   
and stability in returns ."

## Task Synthesis Prompt – Factor-Oriented

## System prompt:

The user is trying to generate new factors based on the hypothesis generated in the previous step. The factors are used in certain scenario, the scenario is as follows:

## Background information ... (Received from Specification Unit)

The user will use the factors generated to do some experiments. The user will provide this information to you:

1. The target hypothesis you are targeting to generate factors for.

2. The hypothesis generated in the previous steps and their corresponding feedbacks.

3. Former proposed factors on similar hypothesis.

4. Some additional information to help you generate new factors.

## Output Format (JSON Schema):

```jsonl
{
" factor name 1": {
" description ": " description of factor 1 , start with its
type , e.g. [ Momentum Factor ]",
" formulation ": " latex formulation of factor 1",
" variables ": {
" variable or function name 1": " description of variable
or function 1",
" variable or function name 2": " description of variable
or function 2"
}
} ,
" factor name 2": {
" description ": " description of factor 2 , start with its
type , e.g. [ Machine Learning based Factor ]",
" formulation ": " latex formulation of factor 2",
" variables ": {
" variable or function name 1": " description of variable
or function 1",
" variable or function name 2": " description of variable
or function 2"
}
}
}
```

## User prompt:

The user has made several hypothesis on this scenario and did several evaluation on them. The target hypothesis you are targeting to generate factors for is as follows: Chosen Action: factor

Hypothesis: Develop simple momentum-based and price-volume factors using the daily price and volume data available.

Reason: Momentum and price-volume factors are simple yet effective for quant investment. They capture underlying trends and trading activity, which can be indicative of future returns. Testing these straightforward factors will provide a baseline for performance and help identify potential opportunities for more complex factor development in subsequent iterations.

The former hypothesis and the corresponding feedbacks are as follows:

Example Output:   
{   
" cumulative\_return\_30\_days ": {   
" description ": "[ Momentum Factor ] This factor measures the   
cumulative return of a stock over the past 30 days . It   
extends previous momentum factors by capturing a   
longer - term trend of price movements .",   
" formulation ": "CR\_ {30} = \\ prod\_ {i =0}^{29} (1 + R\_{t-i}) -   
1",   
" variables ": {   
"R\_{t-i}": " Daily return at time t-i, defined as (P\_{t-i}   
- P\_{t-i -1}) / P\_{t-i -1}"   
}   
} ,   
" turnover\_ratio\_20\_days ": {   
" description ": "[Price - Volume Factor ] This factor computes   
the average daily turnover ratio over the past 20 days ,   
representing the liquidity and trading activity of the   
stock .",   
" formulation ": "TR\_ {20} = \\ frac {1}{20} \\ sum\_ {i =0}^{19}   
\\ frac {V\_{t-i }}{\\ text { Shares Outstanding }}",   
" variables ": {   
"V\_{t-i}": " Trading volume at time t-i",   
" Shares Outstanding ": " Total number of shares outstanding   
for the stock "   
}   
}   
...   
}

## E.3 Implementation Unit

The Implementation Unit executes tasks proposed by the Synthesis Unit using the Co-STEER framework, which transforms high-level descriptions into executable code through iterative refinement. This process involves three key prompt stages: (i) Code Synthesis: Initial code generation based on task descriptions; (ii) Log Analysis: Parsing error traces or outputs to diagnose issues; (iii) Correctness Verification: Determining if the current code meets specification; if not, prompting for revision.

Each stage contributes to a self-correcting loop that enables robust execution even under imperfect initial synthesis.

Implementation Prompt – Factor-Oriented – Code Implementation   
System prompt:

```rst
The user is trying to implement some factors in the following scenario:
Background information ... (Received from Specification Unit)
Your code is expected to align the scenario in any form which means the user needs to get the
exact factor values with your code as expected.
To help you write the correct code, the user might provide multiple information that helps
you write the correct code:
1. The user might provide you the correct code to similar factors. You should learn from
these code to write the correct code.
2. The user might provide you the failed former code and the corresponding feedback to the
code. The feedback contains the execution, the code and the factor value. You should analyze
the feedback and try to correct the latest code.
3. The user might provide you the suggestion to the latest fail code and some similar fail
to-correct pairs. Each pair contains the fail code with similar error and the corresponding
corrected version code. You should learn from these suggestions to write the correct code.
You must write your code based on your former latest attempt below which consists of your
former code and code feedback. You should read the former attempt carefully and must not
modify the correct parts of your former code.
Output Format (JSON Schema):
{
" code ": " The Python code as a string ."
}
User prompt:
Target factor information:
factor_name: ...
factor_description: ...
factor_formulation: ...
[NOTE]
1. Ensure the computations are efficient. Prefer vectorized operations where possible, and
consider JIT compilation (e.g., via numba) for recursive calculations if necessary.
2. Parallelization techniques (e.g., Joblib, Dask) are allowed if it improves performance.
Here are some success implements of similar component tasks, take them as references:
==Factor 1:==
factor_name: ...
factor_description: ...
factor_formulation: ...
=====Code:==
# File Path : factor . py
< code >
=====Factor 2:=====
...
Here are some wrong implements of similar component tasks, take them as references:
==Factor 1:=
factor_name: ...
factor_description: ...
factor_formulation: ...
=====Code:===
# File Path : factor . py
< code >
```

```textproto
Example Output:
{
" code ": " import pandas as pd\ nimport numpy as np\n\n\ ndef
cumulative_return_30_days () :\n..."
}
```

## System prompt:

The User will provide you the information of the factor.

The user will provide the source Python code and the execution error message if execution failed.

The user might provide you the ground truth code for you to provide the critic. You should not leak the ground truth code to the user in any form, but you can use it to provide the critic. User has also compared the factor values calculated by the user’s code and the ground truth code. The user will provide you some analysis result comparing the two outputs. You may find some error in the code which caused the difference between the two outputs.

If the ground truth code is provided, your critic should only consider checking whether the user’s code is aligned with the ground truth code, since the ground truth is definitely correct. If the ground truth code is not provided, your critic should consider checking whether the user’s code is reasonable and correct.

Notice that your critics are not for user to debug the code. They are sent to the coding agent to correct the code. So do not give any following items for the user to check like “Please check the code line XXX.”

Your suggestion should not include any code, just some clear and short suggestions. Please point out very critical issues in your response, ignore non-important issues to avoid confusion. If no big issue found in the code, you can respond “No critics found.”

You should provide the suggestion to each of your critic to help the user improve the code. Please respond the critic in the following format. Here is an example structure for the output:

critic 1: The critic message to critic 1   
critic 2: The critic message to critic 2   
User prompt:   
=====Factor information:=====   
factor\_name: ...   
factor\_description: ...   
factor\_formulation: ...   
=====Python code:=====   
# File Path : factor . py   
< code >   
==Execution feedback:=====   
Execution succeeded without error.   
Expected output file found.   
====Factor value feedback:==   
The source dataframe has only one column which is correct.   
The source dataframe does not have any infinite values.   
The output format is correct. The dataframe has a MultiIndex with ’datetime’ and ’instrument’,   
a single column for the factor name, and the factor values are of type float32, which is

acceptable. The result aligns with the requirements.   
The generated dataframe is daily.

Example Output1:   
No critics found .   
Example Output2:   
critic 1: The main error arises due to the incorrect index   
handling when applying the rolling function over the grouped   
data . Specifically , ...   
critic 2: The logic for handling empty or zero sums of volumes   
is present , but the application logic in rolling apply needs   
consistent indexing that matches the function ’ s expectations .

## System prompt:

The user has finished evaluation and got some feedback from the evaluator. The user has finished evaluation and got some feedback from the evaluator.

The evaluator ran the code and obtained the factor value dataframe and provided several feedback items regarding the user’s code and output. You should analyze the feedback and, considering the scenario and factor description, give a final decision about the evaluation result. The final decision concludes whether the factor is implemented correctly and, if not, detailed feedback containing the reason and suggestion if the final decision is False.

## The implementation final decision is considered in the following logic:

1. If the value and the ground truth value are exactly the same under a small tolerance, the implementation is considered correct.

2. If the value and the ground truth value have a high correlation on IC or rank IC, the implementation is considered correct.

3. If no ground truth value is provided, the implementation is considered correct if the code executes successfully (assuming the data provided is correct). Any exceptions, including those actively raised, are considered faults of the code. Additionally, the code feedback must align with the scenario and factor description.

## Output Format (JSON Schema):

```json
{
" final_decision ": true ,
" final_feedback ": " The final feedback message "
}
```

## User prompt:

=====Factor information:==   
factor\_name: ...   
factor\_description: ...   
factor\_formulation: ...   
=====Python code:=====   
# File Path : factor . py   
< code >   
=====Execution feedback:=====   
Execution succeeded without error.   
Expected output file found.   
===Factor value feedback:=====   
The source dataframe has only one column which is correct.

The source dataframe does not have any infinite values.   
The output format is correct. The dataframe has a MultiIndex with ’datetime’ and ’instrument’, a single column for the factor name, and the factor values are of type float32, which is acceptable. The result aligns with the requirements.   
The generated dataframe is daily.

Example Output:   
{   
" final\_decision ": " True ",   
" final\_feedback ": "The factor ’10 \_day\_momentum ’ has been   
successfully implemented . The code executed without   
errors , and the resultant dataframe adheres to the   
specified requirements . The factor values are stored in   
the correct format and appear accurate given the nature   
of the momentum factor ."   
}

## E.4 Validation Unit

The Validation Unit does not involve any prompts.

## E.5 Analysis Unit

As described in Section 2.5, the Analysis Unit not only evaluates experimental outcomes but also generates prompt-based feedback for local refinement. After each round, it uses structured prompts to interpret the result triplet $( h ^ { t } , t ^ { t } , r ^ { t } )$ ), identify potential failure causes, and generate short-term hypotheses targeting specific weaknesses (e.g., overfitting, poor generalization, feature instability).

These refined hypotheses are passed to the Synthesis Unit as context for the next generation cycle. While the Analysis Unit operates on local, recent evidence, the Synthesis Unit integrates these suggestions with global search memory—achieving a complementary balance between short-term adaptation and long-term discovery.

## Analysis Prompt – Factor-Oriented

## System prompt:

You will receive a hypothesis, multiple tasks with their factors, their results, and the SOTA result. Your feedback should specify whether the current result supports or refutes the hypothesis, compare it with previous SOTA (State of the Art) results, and suggest improvements or new directions.

Please understand the following operation logic and then make your feedback that is suitable for the scenario:

## 1. Logic Explanation:

a) All factors that have surpassed SOTA in previous attempts will be included in the SOTA factor library.

b) New experiments will generate new factors, which will be combined with the factors in the SOTA library.

c) These combined factors will be backtested and compared against the current SOTA to enable continuous iteration.

## 2. Development Directions:

a) New Direction: Propose a new factor direction for exploration and development.

b) Optimization of Existing Direction:

– Suggest further improvements to that factor (this can include further optimization of the factor or proposing a direction that combines better with the factor).

– Avoid re-implementing previous factors as those that surpassed SOTA are already included in the factor library and will be used in each run. 3. Final Goal: To continuously accumulate factors that surpass each iteration to maintain the best SOTA. Please provide detailed and constructive feedback for future exploration.

Output Format (JSON Schema):   
{   
" Observations ": " Your overall observations here ",   
" Feedback for Hypothesis ": " Observations related to the   
hypothesis ",   
"New Hypothesis ": " Your new hypothesis here ",   
" Reasoning ": " Reasoning for the new hypothesis ",   
" Replace Best Result ": "yes or no"   
}

## User prompt:

Target hypothesis: Incorporate advanced variations and combinations of existing momentum-based, price-volume, and volatility factors. Introduce factors like cumulative returns, turnover ratios, or volatility clustering measures to further refine performance while potentially minimizing drawdowns.

## Tasks and Factors:

• cumulative\_return\_30\_days: [Momentum Factor] This factor measures the cumulative return of a stock over the past 30 days. It extends previous momentum factors by capturing a longer-term trend of price movements. Implemented.

• turnover\_ratio\_20\_days: [Price-Volume Factor] This factor computes the average daily turnover ratio over the past 20 days, representing the liquidity and trading activity of the stock. Not Implemented.

## Combined Results:

• IC: 0.033412 vs SOTA IC: 0.027691

• Annualized Return: 0.097140 vs SOTA: 0.076871

• Max Drawdown: -0.133149 vs SOTA: -0.075444

## Example Output:

" Observations ": "The current results show a slight   
improvement in both the Information Coefficient (IC) and   
annualized return compared to the SOTA results . However ,   
the max drawdown has increased slightly , indicating a   
potential increase in risk .",   
" Feedback for Hypothesis ": " The hypothesis is partly   
supported as the introduction of advanced variations and   
combinations of factors has led to a slight improvement in   
the performance metrics , specifically the IC and   
annualized return . However , the hypothesis also aimed at   
potentially minimizing drawdowns , which was not achieved   
as the max drawdown increased .",   
"New Hypothesis ": " Introduction of risk mitigation techniques   
alongside factor combinations could improve return metrics   
while effectively minimizing drawdowns .",   
" Reasoning ": " While the advanced combinations have improved   
some aspects of the performance , the increased drawdown   
suggests the need to balance risk more effectively .   
Considering risk - adjusted factors or incorporating   
strategies such as variance reduction or diversification

could further refine the improvements while maintaining orreducing drawdowns .",   
" Replace Best Result ": "yes"   
}

## F Discussion

## F.1 Diagnostic Insight

The stability of automated quantitative research pipelines is often challenged by three scenarios: (i) noisy or sparse factors, (ii) exploration loops that fail to diversify, and (iii) sensitivity to the initial factor set. In our framework, each of these issues is explicitly considered.

1. Noisy or sparse factors: To prevent unreliable signals from propagating through iterations, Co-STEER integrates health-check modules that verify factors are leakage-free, non-trivial, and statistically meaningful within the training window. This mechanism filters out sparse or redundant candidates before they enter the optimization loop, as detailed in Section 2.4.

2. Exploration inefficiency: The multi-armed bandit scheduler is regularized by imposing an upper bound on the length of consecutive exploration in one direction. This prevents the system from getting trapped in a local loop and ensures adaptive balancing between factor-side and model-side refinements. Ablation studies in Appendix D.2 confirm that this mechanism improves both predictive quality and SOTA selections under limited resources.

3. Initial factor sensitivity: To reduce the dependence on starting conditions, generated factors are systematically deduplicated against the initial set, and the optimization process is isolated from raw definitions. Empirical results (Fig. 7, Fig. 10) show that when initialized with either small libraries (e.g., Alpha 20) or larger libraries (e.g., Alpha 158), the system converges toward diverse, high-quality factors. In particular, starting from Alpha 20, the framework rapidly achieves performance comparable to Alpha 158, while initialization from Alpha 158 yields further gains by building upon a stronger baseline. Moreover, out-of-sample evaluations across different markets (CSI 300, CSI 500, and NASDAQ 100) and time periods further demonstrate that these improvements are not restricted to specific datasets, but reflect consistent robustness and generalizability.

## F.2 Limitations and Future Works

While R&D-Agent(Q) shows compelling results in both real-world markets and quantitative competitions, we identify several limitations that outline clear paths for future research directions:

• Multimodal Data Integration: Although the system processes diverse market data, its factor generation could be enhanced by incorporating alternative data sources (e.g., news sentiment, macroeconomic indicators, and corporate filings) to capture richer market signals.

• Domain Knowledge Incorporation: While the current system already delivers strong results using general-purpose LLMs (e.g., GPT-4o, o3-mini), it relies solely on the models’ built-in knowledge to propose financial hypotheses. Incorporating structured financial expertise—such as innovative solutions from financial reports or economic theory—through retrieval-augmented generation (RAG) could further enhance the plausibility, domain grounding, and efficiency of hypothesis generation.

• Real-Time Market Adaptation: The batch-based design restricts timely reactions to highfrequency trading. Incorporating event-driven or incremental learning could improve adaptability to regime shifts, anomalies, and emergent signals.

## F.3 Broader Impacts

R&D-Agent(Q) advances intelligent asset management through several transformative contributions:

• Generalizable R&D Automation: Although tailored to quantitative finance, our framework provides a modular, data-centric workflow that can be readily adapted to other scientific and engineering domains requiring hypothesis–implementation–validation cycles, potentially addressing bottlenecks in fields like healthcare, materials science, and operations research.

• Reproducible and Deployable Outputs: Every result produced by R&D-Agent(Q) is implemented as executable code. This design ensures end-to-end reproducibility and enables seamless deployment across different datasets or financial markets with minimal adaptation overhead.

• Toward a New Financial AI Paradigm: The framework unifies data-driven modeling and economic reasoning through a structured multi-agent design, offering a new foundation for interpretable, composable, and adaptive financial intelligence systems.

These advances position R&D-Agent(Q) as a foundational technology for the next decade of evidencebased quantitative investing.

While R&D-Agent(Q) lowers the barrier to building quantitative strategies, this accessibility also raises concerns that non-expert users may deploy generated factors or models directly in live trading without proper financial expertise or risk management. To mitigate this, we include clear disclaimers in the codebase stating that the framework is intended for research purposes only and that outputs require rigorous validation before real-world deployment.

## F.4 Large Language Model Usage

We use large language models (LLMs) as a core component of our framework—specifically, for the automated generation of trading factors and predictive models. All the settings of the LLM we used are provided in Appendix C.1. Apart from this, we only use the LLM for checking grammatical errors and formatting in the paper.