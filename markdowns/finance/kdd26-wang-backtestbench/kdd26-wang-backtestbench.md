# BacktestBench: Benchmarking Large Language Models for Automated Quantitative Strategy Backtesting

Zhensheng Wang Beijing Normal University Beijing, China jensenwang@mail.bnu.edu.cn

Lequan Ma   
Beijing Normal University   
Zhuhai, China   
lequanma@mail.bnu.edu.cn   
Wenmian Yang<sup>∗</sup>   
Beijing Normal University   
Zhuhai, China   
wenmianyang@bnu.edu.cn   
Yiquan Zhang   
Elmleaf Ltd.   
Shanghai, China   
zhangyq987@hotmail.com   
Qingtai Wu   
Beijing Normal University   
Zhuhai, China   
qingtaiwu@mail.bnu.edu.cn   
Weijia Jia<sup>∗</sup>   
Beijing Normal University   
Zhuhai, China   
jiawj@bnu.edu.cn

## Abstract

Quantitative backtesting is essential for evaluating trading strategies but remains hampered by high technical barriers and limited scalability. While Large Language Models (LLMs) ofer a transformative path to automate this complex, interdisciplinary workflow through advanced code generation, tool usage, and agentic planning, the practical realization is significantly challenged by the current lack of a large-scale benchmark dedicated to automated quantitative backtesting, which hinders progress in this field. To bridge this critical gap, we introduce BacktestBench, the first largescale benchmark for automated quantitative backtesting. Built from over 6 million real market records, it comprises 18,246 meticulously annotated question-answering pairs across four task categories: metrics calculation, ticker selection, strategy selection, and parameter confirmation. We also propose AutoBacktest, a robust multi-agent baseline that translates natural language strategies into reproducible backtests by coordinating a Summarizer for semantic factor extraction, a Retriever for validated SQL generation, and a Coder for Python backtesting implementation. Our evaluation on 23 mainstream LLMs, complemented by targeted ablations, identifies key factors that influence end-to-end performance and highlights the importance of grounded verification and standardized indicator representations. The dataset and code will be publicly released at https://github.com/jensenw1/BacktestBench.

## CCS Concepts

• Computing methodologies → Language resources; Multiagent systems; • Information systems → Question answering.

## Keywords

Large Language Models, Question Answering, Quantitative Investing, Automated Backtesting, Benchmark, Multi-agent Framework

ACM Reference Format: Zhensheng Wang, Wenmian Yang, Qingtai Wu, Lequan Ma, Yiquan Zhang, and Weijia Jia. 2026. BacktestBench: Benchmarking Large Language Models for Automated Quantitative Strategy Backtesting. In Proceedings of the 32nd ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2 (KDD 2026), August 9–13, 2026, Jeju Island, Republic of Korea. ACM, New York, NY, USA, 25 pages. https://doi.org/10.1145/3770855.3817460

## 1 Introduction

“History does not repeat itself, but it often rhymes.”

— Mark Twain

In quantitative investing, this aphorism captures the fundamental role of backtesting: it involves replaying trading logic on extensive historical data to rigorously assess strategy robustness and its potential adaptability to future market regimes [19]. By reporting quantitative metrics such as the sharpe ratio [22] and maximum drawdown [17], backtesting provides an objective evaluation framework, significantly reducing reliance on subjective judgment and enhancing comparability across diverse investment strategies [5]. However, the traditional backtesting workflow, as illustrated in Figure 1, is inherently complex and interdisciplinary, requiring specialized expertise. Strategy engineers must precisely construct factor combinations, issue accurate historical data queries for specific tickers and time windows, and implement error-free code to execute intricate strategy logic. This process is constrained by high technical barriers, demanding meticulous data retrieval, strict adherence to market timing, and precise trading rule implementation.

The recent advent of Large Language Models (LLMs) and their advanced capabilities in code generation, logical reasoning [3, 16, 20], and, more importantly, agentic planning [32], tool invocation [21], and iterative refinement [23] in interactive environments, presents a transformative opportunity for automating quantitative backtesting. Faced with an exploding search space of factor combinations and rapidly shifting market demands, manual strategy implementation and verification processes can no longer meet the eficiency and scalability requirements of modern quantitative research. This context prompts us to investigate whether LLM-based agents can reliably automate the entire backtesting pipeline, encompassing data retrieval, strategy translation, and execution. Such an endeavor also serves as a practical touchstone for evaluating the capability of Artificial General Intelligence (AGI) [27] on complex vertical-domain problems.

![](images/1844f997a9ea1f85ddec96b090f9d9539300dc113ec6c45196eb6128a012058e.jpg)  
Figure 1: Real-world workflow of a quantitative backtesting engineer.

While the prospect of natural language-driven end-to-end automated backtesting is highly promising, its practical realization presents significant challenges. It demands that models simultaneously possess precise semantic understanding of financial strategies, robust structured data retrieval capabilities, and highly accurate code generation skills [30]. Critically, the academic community currently lacks high-quality evaluation benchmarks specifically designed for such complex financial reasoning tasks. Existing code generation or Text-to-SQL datasets [13, 14, 34], while valuable, do not adequately capture the unique temporal logic and multi-step reasoning requirements inherent in quantitative backtesting.

To bridge this critical gap, we introduce BacktestBench, a novel large-scale benchmark dataset tailored for the field of automated backtesting. Constructed from over 6 million real historical market records from China’s three major exchanges, BacktestBench comprises 18,246 high-quality question-answering (QA) pairs. Each sample is meticulously annotated, covering the entire information chain from a natural language strategy description to core factor extraction, SQL data query generation, Python backtesting code implementation, and the final objective answer. Furthermore, to comprehensively evaluate the holistic capabilities of models, this benchmark systematically designs four distinct task categories: metrics calculation, ticker selection, strategy selection, and parameter confirmation. These categories fully encompass real-world backtest ing scenarios such as strategy comparison, optimization, and asset allocation, thereby providing a rigorous yardstick for measuring the intelligence level of LLMs in this vertical domain.

To systematically address BacktestBench’s challenges and efectively evaluate LLMs’ reasoning and execution capabilities in this domain, this study proposes AutoBacktest, a multi-agent collaborative system serving as a robust baseline. It transforms unstructured natural language strategy descriptions into reproducible backtest results, mimicking human quantitative researchers’ workflows by decoupling complex decision chains into specialized sub-tasks. Specifically, AutoBacktest coordinates three functionally specialized agents: (1) the Summarizer, responsible for semantic-level extraction of financial indicators (including both trading factors and key performance indicators); (2) the Retriever, which handles data-level precise querying and quality verification; and (3) the Coder, focusing on logic-level code implementation and backtest execution. This layered, modular architecture not only significantly reduces the inherent dificulty of end-to-end generation but also enhances the robustness of the entire backtesting pipeline through self-verification mechanisms at each stage, thereby establishing a standardized reference baseline for future research.

The main contributions of this paper are as follows:

• We establish BacktestBench, a large-scale benchmark for automated quantitative backtesting. Built on over 6 million real market records, it covers metrics calculation, ticker selection, strategy selection, and parameter confirmation.

• We propose AutoBacktest, a robust multi-agent baseline system that translates natural language strategies into executable backtests via semantic factor extraction, SQL generation, and Python code execution.

• We evaluate 23 mainstream LLMs on BacktestBench and perform ablation studies to identify critical factors influencing end-to-end backtesting performance.

## 2 Dataset Construction

## 2.1 Data Source

To construct a backtesting dataset tailored to real-world scenarios, we perform rigorous cleaning and integration of raw stock data provided by Elmleaf Information Technology. First, we collect daily trading data for all stocks listed on the Shanghai, Shenzhen, and Beijing Stock Exchanges from January 2, 2020, to September 30, 2025. Post-cleaning, the dataset comprises 6,549,254 records covering 5,401 listed companies over a duration of 1,395 trading days. More detailed schema descriptions and additional statistics are deferred to Appendix C.1.

## 2.2 Core Concepts

In Quantitative Investing, we distinguish four closely related concepts: factor, signal, strategy, and KPI.

A factor is a numerical variable computed from raw market observations (e.g., open, high, low, close, volume) via a deterministic statistical or technical formula, and it quantifies a specific market pattern or state [33]. For example, the 5-day moving average (MA5) maps a price series to a scalar time series that represents the average price over the past five trading days.

A signal is a Boolean decision derived by applying a constraint or threshold rule to one or more factors at time <sup>??</sup>, indicating whether a trading condition is satisfied. For instance, a buy signal can be defined as Open?? <sup>></sup> MA5??<sub>−</sub> , where the factor value uses only infor mation available before time <sup>??</sup> to avoid look-ahead bias. Similarly, a sell signal can be defined by an opposite inequality or a diferent constraint on another factor.

A strategy specifies how to combine buy and sell signals into executable trading actions under a backtesting protocol, including the entry and exit logic, position state transitions, and required constraints (e.g., long-only, alternating buy and sell). For example, a simple long-only strategy enters when the buy signal fires, exits when the sell signal fires, and holds the position otherwise.

A KPI (key performance indicator) is a quantitative metric used to evaluate factors, signals, and strategies under a backtesting protocol, covering predictability, risk, and implementability.

In summary, factors provide the numeric basis, signals convert factors into actionable conditions, strategies compose buy and sell signals into a complete and reproducible trading policy for backtesting, and KPIs provide the evaluation criteria that connect these concepts to measurable and comparable outcomes.

## 2.3 Factor and KPI Selection

2.3.1 Factor Selection. Facing a massive number of candidate factors, this study adheres to two core screening principles:

• Data Availability: The existing database schema must fully support the foundational fields required for factor calculation.

• Computational Determinism: Factors must possess strict mathematical formulations to ensure the uniqueness and reproducibility of calculation results. Based on this princi ple, we exclude factors involving randomness or subjective judgment, such as news sentiment scores generated by LLMs based on non-deterministic seeds, or soft metrics relying on manual annotation.

Based on these criteria, we select 43 factors spanning Risk, Qual ity, Momentum and Technical categories, including 4 sell-only, 2 buy-only and 37 dual-use factors. A detailed list of all factors is provided in Appendix A.

2.3.2 KPI Selection. Guided by domain experts, we select seven KPIs as the primary evaluation criteria: Return Ratio, Maximum Drawdown, Volatility, Annual Sharpe Ratio, Win Rate, Profit Loss Ratio, and Calmar Ratio [8]. The Calmar Ratio is defined as the ratio of annualized return to maximum drawdown and serves as a downside-risk-sensitive indicator. Detailed definitions of all seven KPIs are provided in Appendix Table 6.

## 2.4 Function Implementation

2.4.1 Implementation of Atomic Strategy Functions from Factors. To transform 43 theoretical factors into executable engineering objects, we encapsulate them into 80 atomic strategy functions using Pandas and NumPy. Each function couples factor computation with explicit signal-triggering logic, with 41 dedicated to sell-side and 39 to buy side operations. These collectively form our signal pool.

Each atomic strategy function takes the target ticker’s historical data and specific hyperparameters (e.g., lookback window, decision threshold) as inputs. These functions encapsulate both factor computation and signal evaluation, returning a list of trading dates where the strategy is triggered. The threshold parameter is specifically used to define the boundary conditions for the logic, such as determining whether a value deviation is significant enough to generate a signal. To guarantee realistic backtesting, we strictly avoid look-ahead bias by ensuring that the decision to trade at day <sup>??</sup> relies exclusively on statistics computed from information available up to <sup>??</sup> − 1. An illustrative example is provided in the appendix A.

2.4.2 Implementation of KPI Computation Functions. Because several financial KPIs are sensitive to implementation choices and LLMs can hallucinate when reasoning about these computations, we adopt a standardized backtesting protocol with deterministic trading rules and unambiguous metric definitions to ensure unique and reproducible results.

The protocol fixes the execution microstructure to a long-only setup with strictly alternating buy and sell operations, disallows intraday round trips (T+0), executes buys at the opening price and sells at the closing price, and forcibly liquidates any remaining position at the end of the backtest window.

We simulate a fixed-capital portfolio without leverage, enforce round-lot trading (at least 100 shares), and set transaction costs and taxes to zero in the baseline experiments. We evaluate performance under a daily mark-to-market accounting convention with annualization based on 252 trading days per year and a constant daily risk-free rate of 0.0001 for the Annual Sharpe Ratio, and we assume the input time series is complete and strictly ordered by trading date. We provide the full specification of the execution mechanism, position sizing constraints, return computation, and data integrity assumptions in Appendix B.

The backtesting logic described above is implemented in Python and encapsulated into a dedicated metrics calculation function. This function takes as input a DataFrame containing market data together with the series of buy and sell signals generated by the signal pool, and returns the seven KPI values defined in the evaluation framework.

To ensure both correctness and robustness of the implementation, this study applies a double-blind verification procedure. Two quantitative engineering experts independently implement the same metric computation function strictly following the shared backtesting protocol, and then conduct cross-validation on ten randomly selected market data samples. Only when the outputs of the two implementations match exactly across all test cases is the implementation accepted as correct; the preferred version is then chosen as the final backtesting engine after discussion. This procedure efectively mitigates potential logical errors at the code level and enhances the reliability of the experimental evaluation toolkit.

## 2.5 Strategy Code Construction

To construct a diverse corpus for quantitative investing, we design an automated framework that dynamically synthesizes executable backtesting code. The framework operates by sampling and combining atomic strategy functions. Combinatorial analysis demonstrates that selecting up to four atomic functions without replacement yields a vast search space comprising 92,170 buy strategies and 112,791 sell strategies. Leveraging Python reflection, the system instantiates these atomic operators and maps them into four canonical decision tasks: metrics calculation, ticker selection, parameter confirmation, and strategy selection. Detailed construction procedures and generation statistics are provided in Appendix C.2.

Metrics Calculation. This task family evaluates the model’s ability to compute quantitative performance indicators for a single strategy under a fixed market environment. Each instance presents a natural language description of the strategy and a specified KPI (e.g., Sharpe Ratio or Maximum Drawdown), and the model is required to output the corresponding numerical value.

Ticker Selection. Ticker selection tasks emulate choosing the bestperforming asset from a candidate universe under a shared strategy specification. Given a fixed strategy and multiple ticker histories, the model must identify the asset that optimizes the target KPI.

![](images/f1bb6dd41bd470ca550cbc4f67a1f581ec187aa1d3339a7e7ffed3d3f3de1a5f.jpg)  
Figure 2: Pipeline of natural language strategy generation and evaluation.

Parameter Confirmation. Parameter confirmation tasks focus on selecting hyperparameters within an otherwise fixed strategy architecture. The model is asked to determine which candidate parameter value (such as a threshold or lookback window) yields the best KPI when applied to the same underlying asset and backtest window.

Strategy Selection. Strategy\_selection tasks sit at the top of the decision hierarchy and require choosing among multiple competing strategy logics under identical market conditions. Given several candidate strategies sharing the same underlying, horizon, initial capital, and evaluation metric, the model must decide which logic achieves the highest performance.

Remarks. Across all four task families, each instance is paired with executable Python code, a standardized backtesting environment, and ground-truth labels, enabling end-to-end evaluation from natural language to quantitative outcomes. Further implementation details, including data sampling rules, code synthesis pipelines, and filtering criteria, are provided in Appendix C.2.

## 2.6 Strategy Description Generation

After constructing the corpus of executable strategy code, we adopt a code-to-text reverse-engineering paradigm to obtain humanreadable strategy descriptions aligned with actual backtesting behavior. To ensure both semantic accuracy and financial soundness, we employ a multi-model generation and evaluation pipeline with strict acceptance rules.

2.6.1 Multi-Model Parallel Generation. We select five state-of-theart open-source LLMs as generation agents: Kimi-K2-Thinking-BF16 [1], MiniMax-M2.1-BF16 [2], GLM-4.7 [36], GPT-OSS-120B-BF16 [18], and Qwen3-235B-A22B-Thinking-2507 [31]. These models are deployed on-premise using 72 NVIDIA A800-SXM4-80GB GPUs. For each strategy code sample, each of the five models independently performs reverse parsing and rewriting to produce diverse natural-language descriptions in an instructional style tailored to backtesting scenarios.

Crucially, the input to these models extends beyond raw function bodies. As illustrated in our codebase, each atomic strategy operator and KPI function is annotated with comprehensive docstrings that explicitly define the Strategy Logic, Mathematical Formula, and Input/Output Specifications. This rich semantic context provides ground-truth guidance, significantly reducing ambiguity and minimizing the risk of model hallucination during the generation process. As illustrated on the left side of Figure 2, this procedure follows a code-to-strategy pipeline that transforms executable backtesting programs into aligned natural language strategies. Prompt design details, including how we enforce temporal consistency and separate system-level defaults from strategy-specific logic, are provided in Appendix C.3.

2.6.2 Automated Filtering. To ensure high corpus quality, we implement a rigorous automated filtering mechanism based on peer review. For a natural language strategy description generated by a specific model (e.g., model A), the other four models (e.g., models B, C, D, and E) serve as independent auditors. Each auditor evaluates the code–text pair along two dimensions: code fidelity and strategy validity. Code fidelity ensures the text faithfully reconstructs the program logic, while strategy validity verifies that the trading rules are financially logical and practically executable. We enforce a strict acceptance protocol: a sample is retained if and only if it receives unanimous consensus from all four peer evaluators across both dimensions (totaling eight positive votes). If multiple descriptions for a single strategy code pass this check, one is randomly selected to prevent duplication.

## 2.7 Dataset Statistics and Human Validation

Applying the rigorous filtering pipeline to the initial pool of 33,003 strategy programs yields a finalized corpus of 18,246 high-quality code–text pairs. These instances are stratified by task type into training (10,215), validation (4,195), and testing (3,836) sets. Detailed distributions regarding task families and comparative examples of accepted versus rejected descriptions are provided in Appendix C.3.

To statistically quantify the quality of the generated corpus, we conduct a human audit on a random sample of 200 instances (representing approximately 5% of the test set). Five volunteers assess the completeness of the strategy descriptions, reporting a pass rate of 97.5% (195/200). Simultaneously, six experts in Python implementation verify code correctness, confirming a 98.5% (197/200) consistency between the code and the trading rules.

Furthermore, to benchmark the realism of the synthetic data against human standards, we manually construct a separate set of 70 strategies across seven KPI categories. This expert-crafted subset is developed through a forward generation process that encompasses natural language description, SQL data retrieval, and backtesting implementation, which is subsequently subjected to rigorous expert cross-validation.

## 3 AutoBacktest

To address the challenges of automated backtesting posed by this dataset, we design a multi-agent framework that mimics the workflow of a quantitative researcher. Three specialized agents cooperate in a pipeline: the Summarizer parses natural language strategies into structured indicator representations, the Retriever generates and validates executable SQL to fetch historical market data, and the Coder produces and runs backtesting code to obtain final numerical results. A high-level description is given below, while interaction details, prompts, and implementation code are deferred to Appendix D.

![](images/3282eaeac3135c997ff3c9d123d693c6aa04e17f5754b114d624bf43e0abbcc0.jpg)  
Figure 3: Overall framework of the AutoBacktest.

## 3.1 Summarizer

The Summarizer first employs an LLM, guided by predefined prompts, to extract keywords related to factors and KPIs from the user’s natural language strategy. These summarized keywords then query a BM25 retrieval mechanism, which matches them against a comprehensive library to identify precise standard indicator names. The final output is a structured list of these verified standard indicator names, stored in the shared intermediate state. The concrete prompt design, JSON schema, and reference implementation are provided in Appendix D.

## 3.2 Retriever

The Retriever builds on the Summarizer’s output to construct the data layer for backtesting. It first maps the identified indicator names to their unique Short Codes—compact, token-eficient identifiers (e.g., mapping "13-day Bull Power" to DELAY(HIGH,1)-DELAY( EMA(CLOSE,13),1) that serve as unambiguous keys in the database schema. By injecting this enriched context (Name + Short Code) alongside the original strategy text, it prompts an LLM to generate a single executable SQL query. The agent then performs an execution-based validation loop to ensure that the statement runs successfully on the PostgreSQL database and returns a nonempty result. The finalized SQL string and its corresponding model message are preserved in the shared storage; further engineering details, including the exact SQL prompting pattern and error-handling logic, are described in Appendix D.

## 3.3 Coder

The Coder serves as the execution endpoint that transforms the retrieved data into final backtesting results. Its input consists of three key elements: the user’s natural language strategy, the mapped indicator context (names and Short Codes), and a data preview (head and tail rows) of the DataFrame obtained by the Retriever. Guided by a system prompt that enforces strict backtesting protocols, the Coder invokes a Python execution tool where the full DataFrame has been pre-injected into the runtime environment. The LLM then iteratively writes and debugs the code to calculate the required metrics or execute the strategy logic. Full implementation details and the answer extraction procedure are documented in Appendix D.

## 4 Experiments

## 4.1 Experimental Setup.

4.1.1 Model Configuration. Our experimental benchmark encompasses 23 LLMs, categorized into open-source and closed-source families. The open-source cohort spans several major families, including the Qwen3 series (ranging from 4B to the 235B A22B Mixture-of-Experts), the Ministral reasoning series (14B and 8B), the Kimi family (K2-Thinking and Linear 48B), the GLM family (4.7 and Flash), and the GPT-OSS family (120B and 20B), alongside standalone models such as MiniMax-M2.1, Seed OSS 36B, Mimo V2 Flash [29], and DeepSeek V3.2 [6]. The closed-source cohort comprises four leading proprietary models: Gemini 3 Pro, Qwen3 Max, Qwen3 Coder Plus, and Seed 1.8. See Appendix F.1 for detailed deployment specifications. Notably, while most models leverage CoT reasoning, Kimi Linear 48B and Seed OSS 36B operate without CoT. To ensure fair comparability and balance generation diversity with stability, we uniformly set the temperature parameter to 0.6 across all inference tasks.

4.1.2 Evaluation Metrics. Regarding evaluation metrics, this study quantifies model performance across three dimensions. First, for the factor retrieval task, we employ Accuracy, Precision, Recall, and F1 Score for comprehensive assessment. Second, for the SQL generation task, in addition to computing the Executable Rate (ECR) of generated SQL statements, we also focus on Execution Accuracy (EA) [34], which is defined as the degree of match between the result set returned by the generated SQL query and the groundtruth result set, ignoring element ordering. Finally, for the four categories of strategy backtesting problems, we report the accuracy of the final execution results produced by the model-generated strategy code, reflecting the end-to-end holistic performance. For metrics calculation problems, a prediction is counted as correct only if the absolute error between the predicted value and the groundtruth value is below 10<sup>−3</sup>; otherwise, it is treated as incorrect.

## 4.2 Main Results

4.2.1 Dominance of Closed-Source Models and the Catch-up of Open-Source Models. Table 1 reveals that the closed-source model Gemini 3 Pro [10] holds a dominant position in overall performance, achieving an Overall Accuracy (OA) of 67.41%. Notably, in the Metrics Calculation (MC) task, which demands the highest level of logical reasoning, it secures a top score of 51.67%. In contrast, while the best-performing open-source model GLM 4.7 achieves an

Table 1: This table reports model performance on the synthetic BacktestBench dataset and excludes results from the expertcrafted subset. Overall performance comparison across four task categories. OA denotes the overall performance aggregated across these four categories. Abbreviations: MC: Metrics Calculation, TS: Ticker Selection, PC: Parameter Confirmation, SS: Strategy Selection, ECR: Execution Correctness Rate, EA: Execution Accuracy.  
![](images/4f28e0a5c86ce7c51eef94a44ac1de5544ea8030c98279c519e90f99609cbcb6.jpg)

OA of 56.83% and an MC score of 39.13%, it lags behind Gemini 3 Pro by 10.58 percentage points in OA and 12.54 percentage points in MC. This gap indicates that open-source models continue to face significant bottlenecks in complex financial logic operations.

4.2.2 Sensitivity Diferences to Scaling Laws Across Tasks. Data analysis based on the Qwen3 series (ranging from 4B to 235B parameters) in Table 1 uncovers significant diferences in sensitivity to model parameter size across diferent tasks. Logical reasoning tasks are highly sensitive to parameter scale: when the model size is reduced from 235B to 4B, the Metrics Calculation (MC) score plummets from 34.71% to 1.77%, resulting in an almost complete loss of computational capability. Conversely, indicator retrieval tasks exhibit lower sensitivity to parameter scale: in the same comparison group, the F1 score for Indicator Retrieval only declined from 94.18% to 88.48%, with Qwen3 4B maintaining a relatively high retrieval standard. This suggests that while small-parameter models struggle to complete complex strategy logic calculations, they still possess good potential for basic information retrieval.

4.2.3 Decoupling of Syntax and Logic Capabilities Due to Lack of CoT. The evaluation of non-CoT models in Table 1 highlights a significant decoupling between syntactic proficiency and logical reasoning. Kimi Linear 48B exemplifies this with a high Execution Correctness Rate (ECR) of 99.22% but a low Execution Accuracy (EA) of 48.46% and a minimal Metrics Calculation (MC) score of 0.19%, indicating the generation of executable yet logically flawed code. Similarly, Seed OSS 36B achieves a strong EA of 87.96% but a low Overall Accuracy (OA) of 11.34%, demonstrating that successful data retrieval fails to guarantee downstream reasoning success. These results confirm that CoT is essential for integrating code generation with the rigorous logical deduction necessary for quantitative backtesting.

![](images/93d7a4a3c4c0a5c0739f45036ef3e8ab2d01291b84d8d5d1d62215d2c1e454e0.jpg)  
Figure 4: Detailed model performance on the Metrics Calculation task. All denotes the overall performance on the entire Metrics Calculation task. Abbreviations: Sharpe: Annual Sharpe Ratio, Calmar: Calmar Ratio, MDD: Maximum Drawdown, P/L: Profit Loss Ratio, Return: Return Ratio, Vol: Volatility, WR: Win Rate. The first two rows summarize results on the synthetic BacktestBench dataset, while the grey radar chart in the last row reports performance on the expertcrafted evaluation set.

4.2.4 Accuracy Analysis of Metrics Calculation Tasks. For metrics calculation problems involving seven types of KPIs, we visualized the performance of the top 3 open-source and top 3 closed-source models (see Figure 4).

Complex Mathematical Logic is the Biggest Bottleneck. Figure 4 highlights a steep decline in model performance as KPI complexity increases. While logically simpler metrics like Win Rate and Maximum Drawdown see higher accuracy, complex statistical indicators such as Volatility and Sharpe Ratio remain “disaster zones” across all models, with significantly lower pass rates. This trend confirms that as tasks escalate from basic arithmetic to intricate statistical operations (e.g., variance, annualization), the reliability of LLM-generated code decays precipitously (see Appendix E.2 for detailed error analysis).

Closed-Source Models’ Moat on “High-Order Logic”. In Figure 4, Gemini 3 Pro leads with a comprehensive accuracy (All) of 51.67%, with its core advantage lying in its mastery of high-dificulty indi cators. On the most error-prone Sharpe and Vol indicators, Gemini 3 Pro maintains a significant lead (approximately 4.48 and 1.62 percentage points ahead of the second-place Qwen3 Max, respectively). This implies that top-tier closed-source models possess stronger logical rigor when understanding complex financial mathematical formulas and translating them into precise Python/SQL implementations, capable of handling details such as annualization coeficient adjustments and division-by-zero protection.

![](images/48368297c923be30cdb22b96bccae107070b65025c0de6f77ad8aa1487d11f93.jpg)  
Figure 5: Short Code Ablation.

Open-Source Models: Strong in Extremes, Weak in Statistics. GLM 4.7, representing open-source models (All 39.13%), achieved an accuracy of 54.55% on MDD (Maximum Drawdown) calculation, a score that even surpasses the closed-source model Seed 1.8 (52.86%). The core logic of MDD is “tracking the maximum decline from historical net value peaks,” which is a typical “extreme value tracking” logic. However, on the Vol KPI involving “distribution statistics” logic, GLM 4.7 only scored 22.37%. This contrast illustrates that top open-source models are already perfectly capable of generating procedural calculation code with clear logic but still exhibit high error rates (e.g., formula misuse or library function call errors) when dealing with abstract statistical calculations.

“Logic Collapse” Zone of Base Models. Taking GPT OSS 120B as an example, its scores on Vol and Sharpe KPIs were only 16.71% and 13.06%, respectively. This indicates that some models almost completely lose correctness in code implementation when facing complex financial calculations. Such low scores likely stem from the models’ inability to correctly understand the conversion relationship between “annualized volatility” and “daily volatility,” or ignoring data preprocessing (such as logarithmic return transformation) during coding, resulting in calculation results that deviate significantly from standard values.

Synthetic Data Faithfully Mirrors Expert-crafted Subset Dificulty. Beyond absolute scores, comparing the synthetic and expert-crafted subset radar plots in Figure 4 reveals that their outer contours are highly aligned: models consistently perform worst on Vol and Sharpe, while achieving much higher accuracy on simpler KPIs. This shape-level consistency indicates that the synthetic BacktestBench data faithfully preserves the intrinsic dificulty hierarchy of real world backtest metrics, suggesting that both datasets share a similar underlying task distribution rather than reflecting artifacts of our data generation pipeline.

## 4.3 Ablation Study

4.3.1 Impact of Short Code on SQL Generation. We analyze the impact of the Short Code mechanism by comparing SQL generation performance with and without its inclusion. As shown in Figure 5, the introduction of Short Codes consistently enhances Execution

GPT OSS 120B GPT OSS 20B

![](images/647e24f26777201f08f80066081652741bdabfb71c5e4828e612578b3d493654.jpg)  
Figure 6: Ground Truth Ablation.

Accuracy (EA) across all evaluated models. Specifically, MiniMax M2.1 and GPT OSS 20B exhibit the most pronounced performance jumps, with EA improvements exceeding 20 percentage points, while robust performers like GPT OSS 120B and GLM 4.7 also achieve clear gains. These results confirm that Short Codes act as critical semantic anchors, efectively guiding the models to map natural language intents to precise database schema elements.

4.3.2 Independent Impact of Short Code and SQL Quality. To deeply investigate the independent efects of Short Code and SQL generation quality on strategy backtesting performance, we designed five experimental configurations for comparative analysis. Vanilla serves as the baseline, where the LLM generates SQL and back testing code directly from the user query without any Short Code information. Ours represents the complete implementation of AutoBacktest, including retrieval-augmented Short Code context. Additionally, we introduce three variants: GI+PS (Gold Indicator + Predicted SQL) uses the ground-truth Short Code (Gold Indicator) as context but lets the LLM predict the SQL; NI+GS (No Indicator + Gold SQL) uses no Short Code but provides the ground-truth SQL (Gold SQL); and GI+GS (Gold Indicator + Gold SQL) provides both ground-truth Short Code and Gold SQL, serving as the theoretical performance upper bound.

The experimental results in Figure 6 reveal the decisive role of Short Code in the strategy generation pipeline. Overall, all configurations incorporating Short Code information (Ours, GI+PS, GI+GS) significantly outperform those without it (Vanilla, NI+GS). Remarkably, although the NI+GS method uses perfect Gold SQL, its performance, while better than the Vanilla baseline, still lags substantially behind the three groups containing Short Code. This phenomenon strongly demonstrates that including Short Code in the prompt significantly enhances the LLM’s ability to understand and apply financial indicators, yielding performance gains far exceeding those from optimizing SQL statements alone. Furthermore, comparing Ours with GI+PS reveals minimal performance diferences, with Ours even slightly outperforming in some GPT OSS models (likely due to random experimental error). This further indi cates that given accurate Short Code context, the LLM can generate correct final backtesting code through contextual understanding even if the generated SQL has minor imperfections, highlighting the robustness of the AutoBacktest framework against SQL errors.

## 5 Related Work

## 5.1 LLM-based Strategy Backtesting

Recent works have explored LLMs for quantitative tasks, yet gaps remain in backtesting rigor. Automate Strategy Finding [12] and QuantAgent [28] focus on factor mining and self-improving trading agents, prioritizing profitability over the standardization and reproducibility of the underlying code execution. Similarly, FinMem [35] addresses long-term memory for trading decisions but overlooks the challenges of complex data retrieval and metrics calculation. While AutoPrep [9] automates general tabular data preprocessing, it lacks the specialized temporal logic required to prevent look-ahead bias in financial backtesting.

## 5.2 Datasets for Strategy Backtesting

Existing benchmarks primarily target Reinforcement Learning or specific sub-tasks rather than the full backtesting workflow. Trade-Master [26] and FinRL-Meta [15] provide extensive market environments for training RL agents but do not evaluate the generation of interpretable strategy logic. FNSPID [7] aligns news with market data but serves mainly as an information retrieval resource. While QuantEval [11] assesses strategy coding, it remains limited to a small scale of 60 problems. Similarly, StockBench [4] prioritizes the profitability of agentic trading decisions, and Market-Bench [24] evaluates the implementation accuracy of introductory strategies. In contrast, BacktestBench pioneers a large-scale evaluation of the end-to-end quantitative research workflow. It spans natural language understanding, SQL retrieval, and rigorous backtest execution, comprehensively assessing the translation of complex natural language into executable backtesting logic.

## 6 Conclusion

In this paper, we introduce BacktestBench, a pioneering benchmark dedicated to automated quantitative strategy backtesting, a domain characterized by complex temporal logic and rigorous precision requirements. To support this initiative, we construct a large-scale dataset with 18,246 high-quality QA pairs derived from real-world market records, covering four core decision-making tasks: metrics calculation, ticker selection, strategy selection, and parameter confirmation. Complementing this resource, we propose AutoBacktest, a multi-agent collaboration framework that mimics the professional workflow of quantitative researchers to achieve end-to-end automation from natural language strategy descriptions to executable backtesting code. We systematically evaluate 23 mainstream LLMs on BacktestBench and conduct comprehensive ablation studies to identify key performance drivers in this domain. By establishing a standardized evaluation protocol and a rigorous data resource, this work bridges the gap between general-purpose code generation and quantitative investment research, laying a solid foundation for future advancements in intelligent financial decision-making.

## Acknowledgments

This work is supported in part by the National Natural Science Foundation of China (NSFC) under Grant 62272050 and the grant of Beijing Normal- Hong Kong Baptist University sponsored by

Guangdong Provincial Department of Education; in part by Zhuhai Science-Tech Innovation Bureau under Grant No. 2320004002772 and the Interdisciplinary Intelligence Super Computer Center of Beijing Normal University (Zhuhai).

## References

[1] Yifan Bai, Yiping Bao, Guanduo Chen, Jiahao Chen, Ningxin Chen, Ruijue Chen, Yanru Chen, Yuankun Chen, Yutian Chen, Zhuofu Chen, Jialei Cui, Hao Ding, Mengnan Dong, Angang Du, Chenzhuang Du, Dikang Du, Yulun Du, Yu Fan, Yichen Feng, Kelin Fu, Bofei Gao, Hongcheng Gao, Peizhong Gao, Tong Gao, Xinran Gu, Longyu Guan, Haiqing Guo, Jianhang Guo, Hao Hu, Xiaoru Hao, Tianhong He, Weiran He, Wenyang He, Chao Hong, Yangyang Hu, Zhenxing Hu, Weixiao Huang, Zhiqi Huang, Zihao Huang, Tao Jiang, Zhejun Jiang, Xinyi Jin, Yongsheng Kang, Guokun Lai, Cheng Li, Fang Li, Haoyang Li, Ming Li, Wentao Li, Yanhao Li, Yiwei Li, Zhaowei Li, Zheming Li, Hongzhan Lin, Xiaohan Lin, Zongyu Lin, Chengyin Liu, Chenyu Liu, Hongzhang Liu, Jingyuan Liu, Junqi Liu, Liang Liu, Shaowei Liu, T. Y. Liu, Tianwei Liu, Weizhou Liu, Yangyang Liu, Yibo Liu, Yiping Liu, Yue Liu, Zhengying Liu, Enzhe Lu, Lijun Lu, Shengling Ma, Xinyu Ma, Yingwei Ma, Shaoguang Mao, Jie Mei, Xin Men, Yibo Miao, Siyuan Pan, Yebo Peng, Ruoyu Qin, Bowen Qu, Zeyu Shang, Lidong Shi, Shengyuan Shi, Feifan Song, Jianlin Su, Zhengyuan Su, Xinjie Sun, Flood Sung, Heyi Tang, Jiawen Tao, Qifeng Teng, Chensi Wang, Dinglu Wang, Feng Wang, and Haiming Wang. 2025. Kimi K2: Open Agentic Intelligence. CoRR abs/2507.20534 (2025). arXiv:2507.20534 doi:10.48550/ARXIV.2507.20534

[2] Aili Chen, Aonian Li, Bangwei Gong, Binyang Jiang, Bo Fei, Bo Yang, Boji Shan, Changqing Yu, Chao Wang, Cheng Zhu, Chengjun Xiao, Chengyu Du, Chi Zhang, Chu Qiao, Chunhao Zhang, Chunhui Du, Congchao Guo, Da Chen, Deming Ding, Dianjun Sun, Dong Li, Enwei Jiao, Haigang Zhou, Haimo Zhang, Han Ding, Haohai Sun, Haoyu Feng, Huaiguang Cai, Haichao Zhu, Jian Sun, Jiaqi Zhuang, Jiaren Cai, Jiayuan Song, Jin Zhu, Jingyang Li, Jinhao Tian, Jinli Liu, Junhao Xu Junjie Yan, Junteng Liu, Junxian He, Kaiyi Feng, Ke Yang, Kecheng Xiao, Le Han, Leyang Wang, Lianfei Yu, Liheng Feng, Lin Li, Lin Zheng, Linge Du, Lingyu Yang, Lunbin Zeng, Minghui Yu, Mingliang Tao, Mingyuan Chi, Mozhi Zhang, Mujie Lin, Nan Hu, Nongyu Di, Peng Gao, Pengfei Li, Pengyu Zhao, Qibing Ren, Qidi Xu, Qile Li, Qin Wang, Rong Tian, Ruitao Leng, Shaoxiang Chen, Shaoyu Chen, Shengmin Shi, Shitong Weng, Shuchang Guan, Shuqi Yu, Sichen Li, Songquan Zhu, Tengfei Li, Tianchi Cai, Tianrun Liang, Weiyu Cheng, Weize Kong, Wenkai Li, Xiancai Chen, Xiangjun Song, Xiao Luo, Xiao Su, Xiaobo Li, Xiaodong Han, Xinzhu Hou, Xuan Lu, Xun Zou, Xuyang Shen, Yan Gong, Yan Ma, Yang Wang, Yiqi Shi, Yiran Zhong, and Yonghong Duan. 2025. MiniMax-M1: Scaling Test-Time Compute Eficiently with Lightning Attention. CoRR abs/2506.13585 (2025). arXiv:2506.13585 doi:10.48550/ARXIV.2506.13585

[3] Mark Chen, Jerry Tworek, Heewoo Jun, Qiming Yuan, Henrique Pondé de Oliveira Pinto, Jared Kaplan, Harri Edwards, Yuri Burda, Nicholas Joseph, Greg Brockman, Alex Ray, Raul Puri, Gretchen Krueger, Michael Petrov, Heidy Khlaaf, Girish Sastry, Pamela Mishkin, Brooke Chan, Scott Gray, Nick Ryder, Mikhail Pavlov, Alethea Power, Lukasz Kaiser, Mohammad Bavarian, Clemens Winter, Philippe Tillet, Felipe Petroski Such, Dave Cummings, Matthias Plappert, Fotios Chantzis, Elizabeth Barnes, Ariel Herbert-Voss, William Hebgen Guss, Alex Nichol, Alex Paino, Nikolas Tezak, Jie Tang, Igor Babuschkin, Suchir Balaji, Shan tanu Jain, William Saunders, Christopher Hesse, Andrew N. Carr, Jan Leike, Joshua Achiam, Vedant Misra, Evan Morikawa, Alec Radford, Matthew Knight, Miles Brundage, Mira Murati, Katie Mayer, Peter Welinder, Bob McGrew, Dario Amodei, Sam McCandlish, Ilya Sutskever, and Wojciech Zaremba. 2021. Eval uating Large Language Models Trained on Code. CoRR abs/2107.03374 (2021). arXiv:2107.03374 https://arxiv.org/abs/2107.03374

[4] Yanxu Chen, Zijun Yao, Yantao Liu, Jin Ye, Jianing Yu, Lei Hou, and Juanzi Li. 2025. StockBench: Can LLM Agents Trade Stocks Profitably In Real-world Markets? CoRR abs/2510.02209 (2025). arXiv:2510.02209 doi:10.48550/ARXIV.2510.02209

[5] Marcos Lopez De Prado. 2018. Advances in financial machine learning. John Wiley & Sons.

[6] DeepSeek-AI. 2025. DeepSeek-V3.2: Pushing the Frontier of Open Large Language Models. CoRR abs/2512.02556 (2025). arXiv:2512.02556 doi:10.48550/ARXIV.2512. 02556

[7] Zihan Dong, Xinyu Fan, and Zhiyuan Peng. 2024. FNSPID: A Comprehensive Financial News Dataset in Time Series. In Proceedings of the 30th ACM SIGKDD Conference on Knowledge Discovery and Data Mining (Barcelona, Spain) (KDD ’24). Association for Computing Machinery, New York, NY, USA, 4918–4927. doi:10.1145/3637528.3671629

[8] Martin Eling and Frank Schuhmacher. 2007. Does the choice of performance measure influence the evaluation of hedge funds? Journal of Banking & Finance 31, 9 (2007), 2632–2647.

[9] Meihao Fan, Ju Fan, Nan Tang, Lei Cao, Guoliang Li, and Xiaoyong Du. 2025. AutoPrep: Natural Language Question-Aware Data Preparation with a Multi-Agent Framework. Proc. VLDB Endow. 18, 10 (2025), 3504–3517. doi:10.14778/

3748191.3748211

[10] Gemma Team, Aishwarya Kamath, Johan Ferret, Shreya Pathak, et al. 2025. Gemma 3 Technical Report. arXiv:2503.19786 [cs.CL] https://arxiv.org/abs/2503. 19786

[11] Zhaolu Kang, Junhao Gong, Wenqing Hu, Shuo Yin, Kehan Jiang, Zhicheng Fang, Yingjie He, Chunlei Meng, Rong Fu, Dongyang Chen, Leqi Zheng, Eric Hanchen Jiang, Yunfei Feng, Yitong Leng, Junfan Zhu, Xiaoyou Chen, Xi Yang, and Richeng Xuan. 2026. QuantEval: A Benchmark for Financial Quantitative Tasks in Large Language Models. arXiv:2601.08689 [cs.CL] https://arxiv.org/abs/2601.08689

[12] Zhizhuo Kou, Holam Yu, Jingshu Peng, and Lei Chen. 2024. Automate Strategy Finding with LLM in Quant investment. CoRR abs/2409.06289 (2024). arXiv:2409.06289 doi:10.48550/ARXIV.2409.06289

[13] Fangyu Lei, Jixuan Chen, Yuxiao Ye, Ruisheng Cao, Dongchan Shin, Hongjin Su, Zhaoqing Suo, Hongcheng Gao, Wenjing Hu, Pengcheng Yin, Victor Zhong, Caiming Xiong, Ruoxi Sun, Qian Liu, Sida Wang, and Tao Yu. 2025. Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows. In The Thirteenth International Conference on Learning Representations, ICLR 2025, Singapore, April 24-28, 2025. OpenReview.net. https://openreview.net/forum?id= XmProj9cPs

[14] Jinyang Li, Binyuan Hui, Ge Qu, Jiaxi Yang, Binhua Li, Bowen Li, Bailin Wang, Bowen Qin, Ruiying Geng, Nan Huo, Xuanhe Zhou, Chenhao Ma, Guoliang Li, Kevin C.C. Chang, Fei Huang, Reynold Cheng, and Yongbin Li. 2023. Can LLM already serve as a database interface? a big bench for large-scale database grounded text-to-SQLs. In Proceedings of the 37th International Conference on Neural Information Processing Systems (New Orleans, LA, USA) (NIPS ’23). Curran Associates Inc., Red Hook, NY, USA, Article 1835, 28 pages.

[15] Xiao-Yang Liu, Ziyi Xia, Jingyang Rui, Jiechao Gao, Hongyang Yang, Ming Zhu, Christina Dan Wang, Zhaoran Wang, and Jian Guo. 2022. FinRL-meta: market environments and benchmarks for data-driven financial reinforcement learning. In Proceedings of the 36th International Conference on Neural Information Processing Systems (New Orleans, LA, USA) (NIPS ’22). Curran Associates Inc., Red Hook, NY, USA, Article 134, 15 pages.

[16] Ziyang Luo, Can Xu, Pu Zhao, Qingfeng Sun, Xiubo Geng, Wenxiang Hu, Chongyang Tao, Jing Ma, Qingwei Lin, and Daxin Jiang. 2024. WizardCoder: Empowering Code Large Language Models with Evol-Instruct. In The Twelfth International Conference on Learning Representations, ICLR 2024, Vienna, Austria, May 7-11, 2024. OpenReview.net. https://openreview.net/forum?id=UnUwSIgK5W

[17] Malik Magdon-Ismail and Amir F Atiya. 2004. Maximum drawdown. Risk Magazine 17, 10 (2004), 99–102.

[18] OpenAI. 2025. gpt-oss-120b & gpt-oss-20b Model Card. CoRR abs/2508.10925 (2025). arXiv:2508.10925 doi:10.48550/ARXIV.2508.10925

[19] Robert Pardo. 2011. The evaluation and optimization of trading strategies. John Wiley & Sons.

[20] Baptiste Rozière, Jonas Gehring, Fabian Gloeckle, Sten Sootla, Itai Gat, Xiaoqing Ellen Tan, Yossi Adi, Jingyu Liu, Tal Remez, Jérémy Rapin, Artyom Kozhevnikov, Ivan Evtimov, Joanna Bitton, Manish Bhatt, Cristian Canton-Ferrer, Aaron Grattafiori, Wenhan Xiong, Alexandre Défossez, Jade Copet, Faisal Azhar, Hugo Touvron, Louis Martin, Nicolas Usunier, Thomas Scialom, and Gabriel Syn naeve. 2023. Code Llama: Open Foundation Models for Code. CoRR abs/2308.12950 (2023). arXiv:2308.12950 doi:10.48550/ARXIV.2308.12950

[21] Timo Schick, Jane Dwivedi-Yu, Roberto Dessí, Roberta Raileanu, Maria Lomeli, Eric Hambro, Luke Zettlemoyer, Nicola Cancedda, and Thomas Scialom. 2023. Toolformer: language models can teach themselves to use tools. In Proceedings of the 37th International Conference on Neural Information Processing Systems (New Orleans, LA, USA) (NIPS ’23). Curran Associates Inc., Red Hook, NY, USA, Article 2997, 13 pages.

[22] William F Sharpe. 1998. The sharpe ratio. Streetwise–the Best of the Journal of Portfolio Management 3, 3 (1998), 169–85.

[23] Noah Shinn, Federico Cassano, Ashwin Gopinath, Karthik Narasimhan, and Shunyu Yao. 2023. Reflexion: language agents with verbal reinforcement learning. In Proceedings of the 37th International Conference on Neural Information Processing Systems (New Orleans, LA, USA) (NIPS ’23). Curran Associates Inc., Red Hook, NY, USA, Article 377, 19 pages.

[24] Abhay Srivastava, Sam Jung, and Spencer Mateega. 2025. Market-Bench: Evaluating Large Language Models on Introductory Quantitative Trading and Market Dynamics. CoRR abs/2512.12264 (2025). arXiv:2512.12264 doi:10.48550/ARXIV. 2512.12264

[25] Michael Stonebraker, Lawrence A. Rowe, and Michael Hirohama. 2019. The implementation of POSTGRES. In Making Databases Work: the Pragmatic Wisdom of Michael Stonebraker, Michael L. Brodie (Ed.). ACM Books, Vol. 22. ACM / Morgan & Claypool, 519–559. doi:10.1145/3226595.3226639

[26] Shuo Sun, Molei Qin, Wentao Zhang, Haochong Xia, Chuqiao Zong, Jie Ying, Yonggang Xie, Lingxuan Zhao, Xinrun Wang, and Bo An. 2023. TradeMaster: a holistic quantitative trading platform empowered by reinforcement learning. In Proceedings of the 37th International Conference on Neural Information Processing Systems (New Orleans, LA, USA) (NIPS ’23). Curran Associates Inc., Red Hook, NY, USA, Article 2576, 15 pages.

[27] Alan M. Turing. 1990. Computing Machinery and Intelligence. In The Philosophy of Artificial Intelligence, Margaret A. Boden (Ed.). Oxford University Press, 40–66.

[28] Saizhuo Wang, Hang Yuan, Lionel M. Ni, and Jian Guo. 2024. QuantAgent: Seeking Holy Grail in Trading by Self-Improving Large Language Model. CoRR abs/2402.03755 (2024). arXiv:2402.03755 doi:10.48550/ARXIV.2402.03755

[29] LLM-Core Xiaomi. 2026. MiMo-V2-Flash Technical Report. arXiv:2601.02780 [cs.CL] https://arxiv.org/abs/2601.02780

[30] Qianqian Xie, Weiguang Han, Xiao Zhang, Yanzhao Lai, Min Peng, Alejandro Lopez-Lira, and Jimin Huang. 2023. PIXIU: a large language model, instruction data and evaluation benchmark for finance. In Proceedings of the 37th International Conference on Neural Information Processing Systems (New Orleans, LA, USA) (NIPS ’23). Curran Associates Inc., Red Hook, NY, USA, Article 1454, 16 pages.

[31] An Yang, Anfeng Li, Baosong Yang, Beichen Zhang, Binyuan Hui, Bo Zheng, Bowen Yu, Chang Gao, Chengen Huang, Chenxu Lv, Chujie Zheng, Dayiheng Liu, Fan Zhou, Fei Huang, Feng Hu, Hao Ge, Haoran Wei, Huan Lin, Jialong Tang, Jian Yang, Jianhong Tu, Jianwei Zhang, Jian Yang, Jiaxi Yang, Jingren Zhou, Junyang Lin, Kai Dang, Keqin Bao, Kexin Yang, Le Yu, Lianghao Deng, Mei Li, Mingfeng Xue, Mingze Li, Pei Zhang, Peng Wang, Qin Zhu, Rui Men, Ruize Gao, Shixuan Liu, Shuang Luo, Tianhao Li, Tianyi Tang, Wenbiao Yin, Xingzhang Ren, Xinyu Wang, Xinyu Zhang, Xuancheng Ren, Yang Fan, Yang Su, Yichang Zhang, Yinger Zhang, Yu Wan, Yuqiong Liu, Zekun Wang, Zeyu Cui, Zhenru Zhang, Zhipeng Zhou, and Zihan Qiu. 2025. Qwen3 Technical Report. CoRR abs/2505.09388 (2025). arXiv:2505.09388 doi:10.48550/ARXIV.2505.09388

[32] Shunyu Yao, Jefrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik R. Narasimhan, and Yuan Cao. 2023. ReAct: Synergizing Reasoning and Acting in Language Models. In The Eleventh International Conference on Learning Representations, ICLR 2023, Kigali, Rwanda, May 1-5, 2023. OpenReview.net. https://openreview. net/forum?id=WE\_vluYUL-X

[33] Shuo Yu, Hongyan Xue, Xiang Ao, Feiyang Pan, Jia He, Dandan Tu, and Qing He. 2023. Generating Synergistic Formulaic Alpha Collections via Reinforcement Learning. In Proceedings of the 29th ACM SIGKDD Conference on Knowledge Discovery and Data Mining, KDD 2023, Long Beach, CA, USA, August 6-10, 2023, Ambuj K. Singh, Yizhou Sun, Leman Akoglu, Dimitrios Gunopulos, Xifeng Yan, Ravi Kumar, Fatma Ozcan, and Jieping Ye (Eds.). ACM, New York, NY, USA, 5476–5486. doi:10.1145/3580305.3599831

[34] Tao Yu, Rui Zhang, Kai Yang, Michihiro Yasunaga, Dongxu Wang, Zifan Li, James Ma, Irene Li, Qingning Yao, Shanelle Roman, Zilin Zhang, and Dragomir Radev. 2018. Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task. In Proceedings of the 2018 Conference on Empirical Methods in Natural Language Processing, Ellen Rilof, David Chiang, Julia Hockenmaier, and Jun’ichi Tsujii (Eds.). Association for Computational Linguistics, Brussels, Belgium, 3911–3921. doi:10.18653/v1/D18- 1425

[35] Yangyang Yu, Haohang Li, Zhi Chen, Yuechen Jiang, Yang Li, Jordan W. Suchow, Denghui Zhang, and Khaldoun Khashanah. 2025. FinMem: A Performance Enhanced LLM Trading Agent With Layered Memory and Character Design. IEEE Trans. Big Data 11, 6 (2025), 3443–3459. doi:10.1109/TBDATA.2025.3593370

[36] Aohan Zeng, Xin Lv, Qinkai Zheng, Zhenyu Hou, Bin Chen, Chengxing Xie, Cunxiang Wang, Da Yin, Hao Zeng, Jiajie Zhang, Kedong Wang, Lucen Zhong, Mingdao Liu, Rui Lu, Shulin Cao, Xiaohan Zhang, Xuancheng Huang, Yao Wei, Yean Cheng, Yifan An, Yilin Niu, Yuanhao Wen, Yushi Bai, Zhengxiao Du, Zihan Wang, Zilin Zhu, Bohan Zhang, Bosi Wen, Bowen Wu, Bowen Xu, Can Huang, Casey Zhao, Changpeng Cai, Chao Yu, Chen Li, Chendi Ge, Chenghua Huang, Chenhui Zhang, Chenxi Xu, Chenzheng Zhu, Chuang Li, Congfeng Yin, Daoyan Lin, Dayong Yang, Dazhi Jiang, Ding Ai, Erle Zhu, Fei Wang, Gengzheng Pan, Guo Wang, Hailong Sun, Haitao Li, Haiyang Li, Haiyi Hu, Hanyu Zhang, Hao Peng, Hao Tai, Haoke Zhang, Haoran Wang, Haoyu Yang, He Liu, He Zhao, Hongwei Liu, Hongxi Yan, Huan Liu, Huilong Chen, Ji Li, Jiajing Zhao, Jiamin Ren, Jian Jiao, Jiani Zhao, Jianyang Yan, Jiaqi Wang, Jiayi Gui, Jiayue Zhao, Jie Liu, Jijie Li, Jing Li, Jing Lu, Jingsen Wang, Jingwei Yuan, Jingxuan Li, Jingzhao Du, Jinhua Du, Jinxin Liu, Junkai Zhi, Junli Gao, Ke Wang, Lekang Yang, Liang Xu, Lin Fan, Lindong Wu, Lintao Ding, Lu Wang, Man Zhang, Minghao Li, Minghuan Xu, Mingming Zhao, and Mingshu Zhai. 2025. GLM-4.5: Agentic, Reasoning, and Coding (ARC) Foundation Models. CoRR abs/2508.06471 (2025). arXiv:2508.06471 doi:10.48550/ARXIV.2508.06471

## A Factors

This section provides a comprehensive reference for all factors and KPIs used throughout BacktestBench. Table 5 presents the complete inventory of factors employed in the benchmark, while Tables 6 and 7 detail the correspondence between full names and short codes for factors and KPIs, respectively.

We additionally provide an atomic strategy function example in Figure 7. The example AmountMa6SellStrategy triggers a sell signal when the trading volume on day <sup>??</sup> − 1 significantly exceeds the average volume of the preceding 6 days (from <sup>??</sup> − 2 to <sup>??</sup> − 7). Here, the threshold parameter serves as a multiplier to define what constitutes a significant volume spike; a signal is generated only if the volume at <sup>??</sup> − 1 is greater than the historical average multiplied by this threshold. This design strictly avoids look-ahead bias by comparing the observed volume at<sup>??</sup> −1 against a baseline computed solely from data prior to <sup>??</sup> − 1, ensuring the decision at day <sup>??</sup> relies only on historically available information.

It is important to note that factors appearing similar but difering in time windows (e.g., 5-day vs. 20-day moving averages) are treated as distinct factors in our benchmark. This distinction is crucial because these variations capture fundamentally diferent market dynamics: shorter windows reflect short-term momentum and volatility patterns, while longer windows indicate long-term trends and structural movements. Consequently, each time-window variant represents a unique factor with distinct predictive characteristics and cannot be considered equivalent or interchangeable.

The factor and KPI naming system serves a critical role in the multi-stage AutoBacktest pipeline. During the Summarizer stage, the system retrieves and identifies indicators (include factors and KPIs) using their full names (e.g., “5-day Moving Average" or “Annual Sharpe Ratio"). Subsequently, in the Retriever and Coder stages, both the full names and their corresponding short codes are injected into the prompt context. This dual representation enables the LLM to understand the semantic meaning through full names while generating concise, standardized code using short codes, thereby ensuring consistency and reducing ambiguity in the automated backtesting process.

## B Backtesting Protocol and Standardized Trading Rules

Several financial KPIs are sensitive to implementation details and can be mis-specified in non-standardized settings. Moreover, LLMs are prone to hallucinations when reasoning about these calculations. Therefore, we define a standardized backtesting and trading protocol that enforces deterministic rules and unambiguous computational logic, ensuring that the backtest results are unique and reproducible.

Execution Mechanism. The backtesting framework adopts a longonly trading scheme with strictly alternating buy and sell operations, and it explicitly disallows intraday round trips (T+0). All trades execute at observable and well-defined prices: buy orders fill at the opening price (Buy at Open) and sell orders fill at the closing price (Sell at Close), which removes ambiguity about intraday price paths. If a position remains open on the final day of the backtest window, the framework forcibly liquidates it at the corresponding closing price.

Allocation and Constraints. The simulation uses a fixed-capital setup with initial wealth denoted by Cash<sub>0</sub>, and it does not allow leverage. On each buy date <sup>??</sup>, the trade size <sup>??</sup>?? is computed dynamically as

![](images/f964da35547c246841489d3d4db5ba713ff2420b611390f8c0a0865b37f490ea.jpg)

Table 2: Schema of the stocks database.  
![](images/bcbe36828a095fd19ec4e78c81a25d21aa5b836203d7d939f9e0b33e25468e0b.jpg)

subject to a minimum order lot constraint <sup>??</sup>?? ∈ <sup>Z</sup><sub>≥100</sub>, which corresponds to trading in round lots of 100 shares. On sell dates, the framework enforces full liquidation of the current position. To isolate the impact of trading logic, the baseline experiments set transaction costs and taxes to zero.

Performance Evaluation. The framework adopts a daily mark-tomarket convention when computing returns. The portfolio value PV?? at date <sup>??</sup> is the sum of the market value of all open positions marked at the closing price and the remaining cash balance. The daily return is computed as

![](images/f3d4aa721200807e3aa72d23d5f81fb94d3a49e09fb5dfacadc3e28a0a5f3e6a.jpg)

with <sup>??</sup>?? = 0 on days without an open position. Annualized return and annualized volatility follow the convention of 252 trading days per year, and the daily risk-free rate is fixed to 0.0001 when evaluating the Annual Sharpe Ratio. The Calmar Ratio is computed as the ratio of annualized return to maximum drawdown, which emphasizes downside-risk-adjusted performance.

Data Integrity Assumption. The backtest assumes that the input price time series is complete and strictly ordered by trading date. The current framework does not explicitly handle missing trading days, irregular calendars, or out-of-order records, and we leave these data quality issues for future extensions.

## C Datasets

## C.1 Database Schema

Table 2 presents the schema of the stocks PostgreSQL [25] database, detailing the 15 constituent columns along with their data types and descriptions. This unified schema is applied consistently across the following three exchange tables:

• beijing\_stock\_exchange

• shenzhen\_stock\_exchange

• shanghai\_stock\_exchange

## C.2 Strategy Data Generation Details

This subsection details the construction pipeline for the four task families introduced in Section 3. Unless otherwise specified, all strategy instances are generated from the signal pool and KPI library described in Section A under the standardized backtesting protocol.

Table 3: Overall dataset statistics for BacktestBench across four core Quantitative Investing task families: metrics calculation, ticker selection, parameter confirmation, and strategy\_selection.  
![](images/333f272d39d4825c30314d9ea4138026cf152988201e6cb65a05d9d943ac3661.jpg)

Foundational Framework and Metrics Calculation Tasks. For metrics calculation tasks, the generation pipeline consists of three stages: signal pool sampling, logic composition, and backtest-based validation. First, the system samples a single stock from the three Chinese exchanges according to predefined weights and extracts a contiguous historical window of at least 252 trading days, which is standardized into a DataFrame containing OHLCV fields. Next, using code introspection, the framework independently samples up to four buy-side and four sell-side atomic factors, fuses their signals via set intersection (trades occur only when all selected factors fire on the same date), and randomly chooses one KPI as the optimization objective, assembling them into an executable Python strategy script. Finally, the script is run in an isolated interpreter, the KPI value is recorded as the ground-truth answer, and lowquality samples with sparse trades or anomalous outputs (e.g., NaN or infinite values) are filtered out, yielding a total of 17,082 metrics calculation programs.

Ticker Selection Tasks. Ticker selection tasks extend the above framework to a multi-asset setting. Instead of a single underlying, the system samples a candidate set of stocks, applies the same randomly generated strategy and KPI objective to each asset in parallel, and runs backtests under identical experimental conditions. According to the economic meaning of the KPI, the framework adopts either a maximization principle (for reward-oriented metrics such as return or Sharpe Ratio) or a minimization principle (for downside or risk metrics such as Maximum Drawdown or Volatility) to label the best-performing ticker as the ground truth, resulting in 6,098 ticker selection programs.

Parameter Confirmation Tasks. Parameter confirmation tasks emulate controlled hyperparameter tuning within a fixed strategy and environment. The system first constructs a baseline strategy with a deterministic factor combination and KPI, then selects one atomic factor (e.g., a moving-average breakout rule) as the optimization target and samples a discrete set of candidate parameter values from a predefined space. For each candidate, a strategy variant is formed by substituting the target parameter while keeping all other logic unchanged; all variants are backtested on the same price path and evaluated under the same KPI-based selection rule, and the parameter yielding the best KPI is recorded as the label, producing 4,709 parameter confirmation programs.

Strategy Selection Tasks. Strategy selection tasks capture the decision problem of choosing among heterogeneous strategy logics under a shared market environment. The framework samples a small set of candidate strategies (e.g., a binary contest {<sup>??,</sup> <sup>??</sup>} or ternary contest {<sup>??,</sup> <sup>??, ??</sup>}), independently generates buy and sell factor combinations for each candidate, and constrains all of them to trade the same underlying over the same historical window with identical initial capital and KPI. Dynamic code generation then embeds all candidate strategies into a single script and runs parallel backtests; by comparing KPI values under the appropriate maximization or minimization criterion, the system identifies the best-performing logic (such as “B”) as the ground-truth label, yielding 5,114 strategy\_selection programs.

SQL Query Construction and Annotation. For every strategy instance, the framework automatically constructs and annotates an SQL statement that exactly reproduces the underlying data slice used in backtesting. All queries follow a standard SELECT–FROM –WHERE pattern: during sampling, the chosen exchange, ticker, and date interval are mapped respectively to the FROM clause, ticker constraint, and time filter (e.g., FROM shenzhen\_stock\_exchange WHERE name IN (‘Ping An Bank’) AND trade\_date BETWEEN ‘2019-01-15’ AND ‘2020-03-20’). After strategy code generation, the system parses the code to extract the actually used columns (such as opening\_price, closing\_price, volume\_traded) and constructs a minimal SELECT clause containing only required fields, thereby avoiding redundant data loading. The finalized SQL string is stored together with the strategy code, backtest interval, and ticker list in a JSON file, ensuring a one-to-one correspondence between code, data, and environment that facilitates exact reproduction and error tracing.

## C.3 Natural Language Generation and Evaluation Details

This subsection provides additional implementation details for the natural-language description generation and quality assessment pipeline introduced in Section 3.

Prompt Design and Generation Setup. We employ five specific onpremise models for generation: Kimi-K2-Thinking-BF16, MiniMax-M2.1-BF16, GLM-4.7, GPT-OSS-120B-BF16, and Qwen3-235B-A22B-Thinking-2507. All five models support CoT reasoning and are configured as instruction-following LLMs. The prompts enforce an instructional tone that mimics realistic backtesting requests, explicitly separate strategy-specific logic from system-level defaults (such as capital allocation and execution microstructure), and require precise temporal expressions (e.g., “based on <sup>??</sup> − 1 data”) to avoid look-ahead bias.

Evaluation Criteria and Reporting. During evaluation, each of the four evaluator models produces a structured JSON report for every code–text pair, containing binary decisions for code fidelity and strategy validity, together with brief error diagnoses (e.g., “parameter mismatch”, “future information usage”, or “missing exit rule”).

Only descriptions that receive positive judgments from all evaluators are retained, and the remaining reports are used to categorize and analyze common failure modes.

Scale and Resource Usage. The full pipeline processes 33,003 strategy programs and issues 825,075 LLM calls across the five models deployed on 72 NVIDIA A800-SXM4-80GB GPUs. Under the strict acceptance rule, the final corpus contains 10,244 metrics calculation tasks, 3,455 ticker selection tasks, 2,548 parameter confirmation tasks, and 1,999 strategy selection tasks, totaling 18,246 samples partitioned into 10,215 training, 4,195 validation, and 3,836 test instances. Additional dataset statistics are presented in Table 3.

## D Agent Data Flow and Interaction

In the AutoBacktest framework, each strategy instance is represented as a shared record initialized with a natural-language description stored in the strategy field. The Summarizer, Retriever, and Coder agents operate sequentially on this record, progressively transforming the raw text into a fully specified backtesting sample containing factor definitions, executable data queries, and quantitative results.

The Summarizer is the semantic entry point of the system. Its input consists of the fields strategy, and optionally the global definition of the Financial Indicator vocabulary (which explicitly encompasses both the 43 trading factors and 7 performance KPIs). Based on this information, the Summarizer analyzes the strategy description, extracts the mentioned indicators, normalizes informal wording into canonical Financial Indicator names, and produces a structured list of predicted indicators together with any auxiliary annotations needed for later retrieval. This list is written back into the shared record as fields such as predict\_indicators and a refined version predict\_indicators(BM25), which serve as the semantic bridge from free-form language to the financial indicator library.

The Retriever builds on the enriched record produced by the Summarizer. Its input includes the original strategy text strategy, the predicted indicator list predict\_indicators(BM25), and a separate financial indicator dictionary that maps each financial indicator name to its implementation-level identifiers, for example short codes or database column names. Using these inputs, the Retriever constructs a compact textual context that pairs financial indicators with their short codes and then generates a single SQL statement that specifies which ticker, time interval, and raw fields should be fetched from the historical database for this strategy. Before the statement is accepted, the Retriever executes it against the database to check for syntax correctness and non-empty results; if necessary, it iteratively revises the query based on error messages or empty outputs. Once a valid query is obtained, the final SQL string is stored in the shared record as predict\_SQL.

The Coder is the execution endpoint that turns the verified dataaccess specification into a concrete backtesting result. Its input is the fully enriched record after the Retriever stage, including the strategy text strategy, the strategy type strategy\_type (which determines whether the task is metrics calculation, ticker selection, parameter confirmation, or strategy selection), the indicator context predict\_indicators(BM25) together with the indicator dictionary, and the validated SQL statement predict\_SQL. The

Coder first executes predict\_SQL to obtain a time series of market data corresponding to the requested ticker and period; this data is treated as the backtesting environment, and an empty result triggers an early termination for that record with an error flag. If a non-empty data slice is obtained, the Coder constructs a taskspecific prompt that combines a preview of the retrieved table, the normalized indicator information, and the strategy description, and then uses a tool-augmented language model to write and execute backtesting code within this environment. The final model message is parsed to extract a standardized answer, such as a KPI value, an index of the best-performing ticker, a selected parameter, or a chosen strategy. The final model message is parsed to extract a standardized answer, such as a KPI value, an index of the bestperforming ticker, a selected parameter, or a chosen strategy. The extracted scalar answer is appended to the shared record as the pred\_answer field.

## E Experiments

## E.1 Impact of BM25 in Summarizer

To evaluate the necessity of the retrieval mechanism in our framework, we conduct an ablation study on the Summarizer module. Specifically, we compare the performance of various LLMs with and without the integration of the BM25 algorithm. In the configuration without BM25 (“w/o"), the Summarizer relies solely on the LLM’s internal knowledge to identify relevant intents and slots. Conversely, the configuration with BM25 (“w") augments the prompt with retrieved context related to indicator definitions and project metadata.

Table 4 presents the comparative results. The integration of BM25 yields a significant performance improvement across all tested models. For instance, DeepSeek V3.2 exhibits a substantial increase in Accuracy from 17.65% to 68.98% and an F1 score improvement from 66.92% to 92.90%. Even larger models, such as Qwen3 235B, benefit markedly, with Accuracy rising from 30.42% to 76.41%. These results demonstrate that while LLMs possess strong reasoning capabilities, the precise identification of domain-specific indicators and intents in quantitative investing requires external knowledge retrieval. The BM25 algorithm efectively bridges this gap by providing accurate context, thereby significantly enhancing the Summarizer’s ability to map natural language queries to correct structured representations.

## E.2 Case Study

To diagnose the root causes of performance degradation in metrics calculation tasks—specifically Volatility and Sharpe Ratio—we con struct a targeted analysis framework for the backtesting process. In our experiments with Gemini-3-Pro, we filter for samples with accurate SQL queries and successful indicator retrieval, isolating instances where Python code execution produces unexpected deviations. Our analysis identifies two primary mechanisms driving these failures.

E.2.1 Case 1: Composite Atribution Analysis of Volatility Calculation Failure. This case examines the failure mechanism in volatility calculation tasks, where three systemic logical defects in the generated code cumulatively distort backtesting results.

The primary error occurs during performance attribution, where the code fails to properly initialize the return series. By neglecting to insert the initial capital as a “Day 0” baseline, the first-day return is calculated as invalid and subsequently discarded. This left-side truncation compromises the integrity of the time series, forcing the volatility calculation to rely on an incomplete sample set and introducing significant numerical errors.

Furthermore, regarding indicator construction, the model misinterprets the mathematical definition of “Mean Absolute Deviation (MAD)” within the Commodity Channel Index (CCI). Instead of the standard “average absolute deviation within a rolling window,” the code implements a “simple rolling average of absolute price deviations.” This algorithmic discrepancy causes buy signal triggers to diverge from the intended strategy.

Additionally, the trading logic lacks necessary boundary constraints for the backtesting cycle. Without a filter to prohibit position opening on the final day, the system executes non-compliant intraday bidirectional trading (opening at market start and forced liquidation at close). This artificially inflates transaction costs and skews the final net value, rendering the volatility calculation ineffective.

E.2.2 Case 2: Systematic Bias in Sharpe Ratio Assessment. This case investigates the failure mechanism afecting the Sharpe Ratio, a metric whose accuracy relies heavily on the completeness of the return series and strict adherence to trading logic. We observe that logical defects in two key dimensions cause severe distortion in the assessment.

A critical flaw appears in the construction of the net value sequence, where the code omits the “zero-point anchoring” operation. Failing to explicitly insert the initial capital at the head of the sequence leads to the exclusion of the first-day return during difference calculations. This reduction in sample size afects both the numerator (annualized excess return) and the denominator (return volatility), resulting in a Sharpe Ratio derived from a fragmented time window and destroying statistical validity.

Simultaneously, the code exhibits insuficient boundary control at the end of the backtesting period. By permitting non-compliant “open and close on the same day” operations, the system incurs invalid transaction costs that are directly borne by the net value sequence. This artificially depresses the final return performance, depriving the generated Sharpe Ratio of its reference value as a performance benchmark.

## F Impletation Details

## F.1 LLM Deployments

This section details the LLM configurations employed across the diferent stages of our research. The deployment is divided into two distinct phases: the data construction phase and the experimental evaluation phase.

During the data construction phase, we utilized a high-performance computing cluster equipped with 72 NVIDIA A800-SXM4- 80GB GPUs to deploy five state-of-the-art open-source CoT models. These models were selected for their superior reasoning capabilities and include Kimi-K2-Thinking-BF16, MiniMax-M2.1-BF16, GLM-4.7, GPT-OSS-120B-BF16, and Qwen3-235B-A22B-Thinking-2507. Detailed specifications for these models are provided in Table 8. To optimize inference eficiency, we leveraged SGLang and vLLM as our deployment frameworks. A unified temperature parameter of 0.6 was applied across all models to maintain consistency in generation diversity and stability.

Table 4: Performance Comparison of the Summarizer Module With and Without BM25 Retrieval. This table evaluates the efectiveness of incorporating the BM25 algorithm into the Summarizer stage across various LLMs. “w/o" denotes the baseline performance without BM25, while “w" indicates performance with BM25 integration. The metrics include Accuracy (Acc), Precision (P), Recall (R), and F1 Score.  
![](images/5a734f62be063a59677ce51ceedc01e2136e0ec3324ced44b7bb0a880b95e68c.jpg)

In the experimental phase, we expanded our infrastructure to 100 NVIDIA A800-SXM4-80GB GPUs to locally host 18 models for comprehensive benchmarking. To complement these local deployments, we accessed several proprietary models via external APIs. Specifically, Mimo V2 Flash and Gemini 3 Pro were accessed through Open-Router, incurring a total cost of \$756. For DeepSeek V3.2, Qwen3 Max, and Qwen3 Coder Plus, we utilized their oficial compatiblemode APIs available at https://dashscope.aliyuncs.com/compatiblemode/v1. Additionally, Seed 1.8 was accessed via the Volcengine API at https://ark.cn-beijing.volces.com/api/v3. To ensure a fair comparison between local and API-based models, we strictly maintained the temperature setting at 0.6 for all inferences throughout the experiment.

## F.2 Agent Impletation

We implement the AutoBacktest agent using the LangGraph framework, employing a ReAct (Reasoning and Acting) architecture to orchestrate the backtesting workflow. The agent interacts with a PostgreSQL database to retrieve financial data, which is converted into a Pandas DataFrame. We equip the agent with a Python REPL tool (‘create\_python\_repl\_tool’), enabling it to execute Python code directly on the dataframe to perform complex calculations and logic verification.

To ensure robustness and standardized outputs, the implementation features several key components:

(1) Dynamic Context Construction: The system dynamically generates prompts by injecting the specific trading strategy, indicator definitions retrieved via the BM25 Summarizer, and the dataframe schema. This ensures the LLM possesses all necessary context for code generation.

(2) Structured Output Parsing: We define specific Pydantic models (e.g., ClassA\_FinalAnswerFormat) for diferent task types, such as metric calculation or ticker selection. This enforces strict output formatting, facilitating accurate answer extraction from the agent’s response.

(3) Execution Constraints: To balance reasoning depth with eficiency and prevent infinite loops, the agent is configured with a maximum step limit of 25 iterations per query.

The system also includes a robust answer extraction mechanism that handles various response formats, including CoT traces (e.g., <think> tags) and JSON structures, ensuring reliable evaluation of the model’s predictions.

## G Prompts

This section presents the five critical prompts utilized in our work, categorized into two distinct phases: Dataset Construction and the AutoBacktest Agent Workflow.

## G.1 Dataset Construction Prompts

The construction of the BacktestBench dataset relies on a “Code-to-Text" reverse engineering paradigm. Figure 9 displays the Code-to-Strategy Prompt, which is used to translate synthetically generated atomic strategy code into natural language descriptions. This prompt instructs the LLM to interpret the Python logic and describe the trading rules in a tone mimicking a human quantitative researcher. Subsequently, to ensure the high quality and logical consistency of these generated descriptions, we employ the Strategy Evaluation Prompt shown in Figure 10. This prompt guides a separate set of LLMs to cross-validate the generated text against the original code, checking for discrepancies in logic, parameter values, or potential hallucinations.

## G.2 AutoBacktest Agent Prompts

The inference phase involves three specialized agents, each driven by a carefully designed prompt to handle specific sub-tasks in the quantitative workflow.

• Summarizer Prompt (Figure 11): This prompt guides the Summarizer agent to analyze the user’s raw natural language query. Its primary function is to identify and extract the full names of relevant financial indicators (e.g., “5-day Moving Average") and Key Performance Indicators (KPIs). It serves as the semantic parser that maps unstructured text to the standardized terminology of our indicator library.

• Retriever Prompt (Figure 12): Once the indicators are identified, the Retriever agent uses this prompt to locate the necessary data. Crucially, at this stage, the system injects both the full names and their corresponding Short Codes (e.g., SMA(CLOSE, 5)) into the prompt context. This enables the LLM to precisely understand which database fields are re quired and to construct accurate SQL queries for fetching the underlying market data.

• Coder Prompt (Figure 13): Finally, the Coder agent utilizes this prompt to generate the executable Python backtesting script. Similar to the Retriever, this prompt is enriched with the indicator Short Codes. By explicitly providing these standardized short codes, we constrain the LLM to use our pre-defined, rigorously tested calculation logic rather than hallucinating arbitrary formulas. This ensures that the generated code is not only syntactically correct but also financially valid and aligned with the user’s original intent.

## H Limitations

While this study establishes a rigorous benchmark for evaluating LLMs in the domain of quantitative finance and demonstrates the potential of “code-to-text” reverse engineering to align natural language instructions with executable trading logic, several limitations remain in the current data scope and task design.

First, the dataset primarily focuses on short-term timing strategies driven by daily price fluctuations. It does not yet incorporate long-term value investing strategies that require synthesizing multimodal information, such as macroeconomic indicators, corporate financial reports, or unstructured news text.

Second, the research objective is strictly defined as assessing the capabilities of LLMs within the “strategy understanding–data retrieval–code generation–backtesting verification" pipeline. Consequently, the model outputs are optimized for feasibility verification and code correctness rather than for generating alphagenerating investment advice for live deployment.

Third, constrained by a database that currently supports only daily market data, all backtesting simulations adhere to a simplified daily mark-to-market logic (“buy at open, sell at close"). This approach does not account for real-world execution frictions such as slippage, intraday price path dependence, or high-frequency microstructure details.

Furthermore, to isolate and rigorously test the model’s tool-use and code-implementation abilities, the experimental setup abstracts away certain complex market constraints. The framework does not explicitly model dynamic transaction fees, varying tax rates, or regime-switching minimum trading units, nor does it address ad vanced portfolio management tasks like dynamic position sizing or mean-variance optimization. Methodologically, the benchmark is built around the classical “indicator–signal–backtest" paradigm; it does not currently cover strategies based on machine learning models (e.g., time series forecasting or reinforcement learning) or complex meta-strategies involving indicator weighting and ensemble methods, primarily due to the prohibitive computational costs of grid-searching such high-dimensional spaces.

In summary, the present benchmark serves as a foundational baseline for testing LLMs’ strategy understanding and code generation in a structured financial environment. However, significant room remains for future expansion into more realistic settings that model multi-modal inputs, multi-frequency data, and dynamic market constraints.

Table 5: All factors used in strategy construction. Type indicates whether the factor serves as a buy signal, sell signal, or both.  
![](images/a7061a68c0b86453e5bfdf50c1eabf9b6a95cdf519c9f7f7383ae38b2ff0741e.jpg)

Table 6: Factors with Short Code.  
![](images/1cde33e0621928ade4cba74b40b6ccf0069dec42e0e3e3a1724fc0ff26c55a9b.jpg)

Table 7: KPIs with Calculation Codes. (Note: PV denotes Portfolio Value; PNL denotes Profit and Loss; N represents the calculation window.)  
![](images/1ab7ea2cfc0a40ee06a14c5657b5881c67b4b72e4a01abff6cbd8338e02c96a2.jpg)

Table 8: Comparison of Model Inference Configurations. Abbreviations: Backend = Inference Backend, MFS = mem-fraction static, CoT = Chain of Thought, Algo. = Speculative Algorithm, Steps = speculative-num-steps, TopK = speculative-eagle-topk, Draft = speculative-num-draft-tokens.  
![](images/34f3880aa7dfa3b3962a3589d06165d165cb16f94f0464252a79e71f6d489456.jpg)  
<sup>1</sup>https://www.modelscope.cn/models/Qwen/Qwen3-235B-A22B-Thinking-2507 <sup>2</sup>https://www.modelscope.cn/models/lmsys/Qwen3-235B-A22B-EAGLE3 <sup>3</sup>https://www.modelscope.cn/models/Qwen/Qwen3-Next-80B-A3B-Thinking <sup>4</sup>https://www.modelscope.cn/models/Qwen/Qwen3-32B <sup>5</sup>https://www.modelscope.cn/models/Qwen/Qwen3-30B-A3B-Thinking-2507 <sup>6</sup>https://www.modelscope.cn/models/Qwen/Qwen3-14B <sup>7</sup>https://www.modelscope.cn/models/Qwen/Qwen3-8B <sup>8</sup>https://www.modelscope.cn/models/Qwen/Qwen3-4B <sup>9</sup>https://huggingface.co/ByteDance-Seed/Seed-OSS-36B-Instruct <sup>10</sup>https://huggingface.co/mistralai/Ministral-3-14B-Reasoning-2512 <sup>11</sup>https://huggingface.co/mistralai/Ministral-3-8B-Reasoning-2512 <sup>12</sup>https://www.modelscope.cn/models/unsloth/Kimi-K2-Thinking-BF16 <sup>13</sup>https://www.modelscope.cn/models/moonshotai/Kimi-Linear-48B-A3B-Instruct <sup>14</sup>https://www.modelscope.cn/models/ZhipuAI/GLM-4.7 <sup>15</sup>https://docs.sglang.io/basic\_usage/glm45.html <sup>16</sup>https://www.modelscope.cn/models/ZhipuAI/GLM-4.7-Flash <sup>17</sup>https://www.modelscope.cn/models/QuixiAI/MiniMax-M2.1-bf16 <sup>18</sup>https://www.modelscope.cn/models/unsloth/gpt-oss-120b-BF16 <sup>19</sup>https://www.modelscope.cn/models/nv-community/gpt-oss-120b-Eagle3 <sup>20</sup>https://www.modelscope.cn/models/unsloth/gpt-oss-20b-BF16

![](images/018798e078e25f1fcb5fc515f7ebb44dfd153738a4b372c008ab5a818c091d94.jpg)  
Figure 7: Atomic Strategy Function Example.

![](images/a31ab9fd9b1598bd5ed0d8974d85c25711d8c8dfd81165b9e544a815de9c9de1.jpg)  
Figure 8: QA example.

![](images/7a3dec45a7f9f28b17131f2a983278596eff736efbe3735573278c28bdc3e0d3.jpg)  
Figure 9: Prompt for Converting Python Code to Natural Language.

![](images/4ef618708219517fb3d8fcba0292d1c55ddcba0884b2a005157a532a1f6cf543.jpg)  
Figure 10: Prompt for Evaluating Natural Language Strategies

![](images/6f3590d781cd7b714eafd3a070c7870c1e91c09849877a385324b08787ed1bcf.jpg)  
Figure 11: Factor Retrival Prompt.

![](images/e62b908681d2bb48ef7b570f40642942c2d0d16475ef6726af5f4c76b7ff57e5.jpg)  
Figure 12: Prompt For Retriever.

![](images/f077ff121fa0ab60134588b5aad6fdd15b5fb38cc44f77c4fab71ff97c7832db.jpg)  
Figure 13: Prompt For Coder.