# AlphaEval: A Comprehensive and Eficient Evaluation Framework for Formula Alpha Mining

Hongjun Ding CUNY Baruch College New York, USA hongjun.ding.baruchmfe@gmail.com

Taian Guo<sup>†</sup>   
Peking University   
Beijing, China   
taianguo@stu.pku.edu.cn

Lutong Zou Harvard University Massachusetts, Cambridge, USA xjqrxjqr@gmail.com

Binqi Chen Peking University Beijing, China cbq@stu.pku.edu.cn

Zhengyang Mao<sup>†</sup> Peking University Beijing, China zhengyang.mao@stu.pku.edu.cn

Luchen Liu Zhengren Research, Zhengren Quant Haikou, Hainan, China liulc@zhengrenquant.com

Jinsheng Huang Peking University Beijing, China hjs@stu.pku.edu.cn

Guoyi Shao   
Peking University   
Beijing, China   
2100012950@stu.pku.edu.cn   
Ming Zhang<sup>†‡</sup>   
Peking University   
Beijing, China   
mzhang\_cs@pku.edu.cn

## Abstract

Formula alpha mining, which generates predictive signals from financial data, is critical for quantitative investment. Although various algorithmic approaches—such as genetic programming, reinforcement learning, and large language models—have significantly expanded the capacity for alpha discovery, systematic evaluation remains a key challenge. Existing evaluation metrics predominantly include backtesting and correlation-based measures. Backtesting is computationally intensive, inherently sequential, and sensitive to specific strategy parameters. Correlation-based metrics, though eficient, assess only predictive ability and overlook other crucial properties such as temporal stability, robustness, diversity, and interpretability. Additionally, the closed-source nature of most existing alpha mining models hinders reproducibility and slows progress in this field. To address these issues, we propose <sub>AlphaEval</sub>, a unified, parallelizable, and backtest-free evaluation framework for automated alpha mining models. AlphaEval assesses the overall quality of generated alphas along five complementary dimensions: predictive power, stability, robustness to market perturbations, financial logic, and diversity. Extensive experiments across representative alpha mining algorithms demonstrate that AlphaEval achieves evaluation consistency comparable to comprehensive backtesting, while providing more comprehensive insights and higher eficiency. Furthermore, AlphaEval efectively identifies superior alphas compared to traditional single-metric screening

approaches. All implementations and evaluation tools are opensourced to promote reproducibility and community engagement.

## CCS Concepts

<sup>•</sup> General and reference → Metrics<sup>;</sup> Evaluation<sup>.</sup>

## Keywords

Alpha Mining, Quantitative Finance, Backtest-free Evaluation

ACM Reference Format:   
Hongjun Ding, Binqi Chen, Jinsheng Huang, Taian Guo, Zhengyang Mao, Guoyi Shao, Lutong Zou, Luchen Liu, and Ming Zhang. 2026. AlphaEval: A Comprehensive and Eficient Evaluation Framework for Formula Alpha <sup>Mining.</sup> <sup>In</sup> Proceedings of the 32nd ACM SIGKDD Conference on Knowledge Discovery and Data Mining V.2 (KDD 2026), August 9–13, 2026, Jeju Island, <sub>Republic</sub> <sub>of</sub> <sub>Korea.</sub> ACM, New York, NY, USA, 12 pages. https://doi.org/10. 1145/3770855.3817727

## 1 Introduction

The automated mining of formula alpha is a central challenge in quantitative investment. Formula alpha , defined as computable expressions that transform raw financial data into signals predictive of future returns, have evolved from handcrafted models grounded in financial theory [6] to large-scale automated discovery. Recent developments include genetic programming [3, 5, 26], reinforcement learning [15, 23, 25, 27–29], generative adversarial networks [18], and large language models (LLMs) [1, 10, 11, 14, 19], enabling the generation of vast numbers of candidate alphas.

A summary of representative alpha mining models is shown in Table 1. While many of these methods demonstrate promising results in alpha generation, their evaluation schemes are often limited, inconsistent, and incomplete. In practice, two types of evaluation are commonly used: backtesting and correlation-based metrics such as the Information Coeficient (IC) or RankIC [21]. Backtesting simulates portfolio performance using historical market data, but it is inherently sequential, computationally expensive, and highly sensitive to strategy design choices. IC-based metrics provide a lightweight proxy for assessing the linear correlation between alphas and future returns, yet they focus solely on predictive ability and fail to capture other essential dimensions of alpha quality—such as temporal stability, robustness to market perturbations, diversity, and logical interpretability. These limitations make it dificult to perform fair and comprehensive comparisons across mining models, especially in contexts where backtesting strategy is diferent. Fur thermore, most alpha mining models remain closed-source, which hinders reproducibility and slows progress in this important area of quantitative research.

Table 1: Summary of current alpha mining models. Metrics in bold are based on backtesting.  
![](images/265b55e1cb9396baeba4e393d7cf9707eb665d1958637ff1a454ef1ca95d9df5.jpg)

To address this gap, we propose <sub>AlphaEval</sub>, a structured and eficient evaluation framework for automated alpha mining models. Unlike traditional approaches, AlphaEval evaluates an alpha mining model holistically based on the collection of alphas it produces—without requiring portfolio backtesting. Our framework scores models along five complementary dimensions: <sub>predictive</sub> power<sup>,</sup> temporal stability<sup>,</sup> robustness to market perturbations<sup>,</sup> finan-<sub>cial</sub> <sub>logic</sub>, and <sub>diversity</sub>. These metrics are designed to be parallelizable, interpretable, and applicable across diferent models and markets.

We apply AlphaEval to a suite of representative alpha mining models. The results show that AlphaEval scores are highly consistent with precision backtesting outcomes while ofering broader diagnostic insight and significantly faster evaluation. Furthermore, AlphaEval demonstrates superior alpha selection performance compared to conventional single-metric filtering approaches (e.g., by IC alone).

In summary, our contributions are as follows:

<sub>•</sub> We propose <sub>AlphaEval</sub>, the first unified, backtest-free, and parallelizable framework for evaluating automated alpha mining models.

<sub>•</sub> We design five complementary metrics that comprehensively assess the predictive quality, temporal stability, robustness, interpretability, and diversity of generated alphas.

<sub>•</sub> We conduct large-scale benchmarking across eight popular mining models, showing AlphaEval’s efectiveness and consistency with traditional backtesting.

<sub>•</sub> We open-source all implementations and evaluation tools to foster transparency and reproducibility in the quantitative finance community.

## 2 Related Work

## 2.1 Alpha Mining

Alpha mining typically consists of two sequential stages: first, generating candidate alpha set, and second, selecting and combining these alphas into a predictive signal.

In the alpha generation stage, early research primarily focused on manually crafting alphas based on economic insights or empirical patterns, exemplified by classical models such as Fama-French [6] and curated alpha libraries like Alpha101 [8] and Alpha158 [24]. Although these handcrafted alphas are intuitive and interpretable, their diversity and expressiveness are inherently limited. To address these limitations, researchers introduced automated approaches such as genetic algorithm (GA) [3, 5, 26], reinforcement learning (RL) [25, 29], generative adversarial networks (GANs) [18] and more recently, large language models (LLMs) [11, 19]. Evolutionary algorithms and RL-based methods systematically explore large symbolic search spaces, generating a substantial number of potential alphas; however, these automated methods frequently produce factors lacking clear financial interpretability and often face challenges in generalizing across diferent market conditions. LLM-based approaches leverage financial linguistic understanding to generate more interpretable and semantically meaningful alpha expressions, but often lack comprehensive validation of their practicality due to simplified evaluation criteria.

In the alpha selection and combination stage, generated alpha candidates are assessed and integrated into predictive strategies. A common workflow involves applying metric-based thresholding, such as Information Coeficient (IC) or Sharpe ratio, to initially filter promising alphas, followed by modeling their relationships through techniques including linear regression, LightGBM [9], or XGBoost [4]. An alternative strategy employed by RL-based meth ods (e.g., AlphaGen, AlphaQCM) directly incorporates the selection and combination tasks into the alpha discovery process itself. These methods optimize portfolio-level performance metrics as rewards during alpha search, thereby creating an end-to-end optimization framework. Although this integrated optimization strategy shows promise in enhancing alpha quality, it increases model complexity and computational cost, requiring stronger supervision signals and longer training cycles.

## 2.2 Alpha Evaluation Metrics

The dominant evaluation metrics in alpha mining focus on assessing predictive power. Information Coeficient (IC), RankIC, and various return-based metrics (e.g., annual return, Sharpe ratio) are widely used to quantify the association between alpha signals and future returns. While efective in measuring short-term predictability, these metrics ofer a narrow view of alpha quality. They fail to account for critical properties such as stability over time, robustness to market noise, structural diversity among alphas, and logical consistency. Moreover, backtesting—a common but expensive evaluation method—introduces sensitivity to strategy configurations, sufers from low parallelism, and limits its scalability in large-scale alpha generation tasks.

In addition, current evaluation protocols typically treat each alpha independently, lacking a mechanism to assess the collective performance or quality of the alpha set generated by a mining model. This hinders fair comparison between models and undermines efforts to understand their generalization capabilities. A more holistic evaluation framework is urgently needed to support model-level diagnosis and eficient alpha selection.

## 2.3 Interpretability and Robustness in Quantitative Models

In practical financial applications, interpretability and robustness are increasingly viewed as essential for risk management, regulatory compliance, and human-in-the-loop decision making [16, 20]. Formulaic alphas—unlike deep learning-based signals—have the advantage of being inherently transparent and interpretable. Yet, few existing benchmarks incorporate metrics that explicitly reward logical clarity or penalize unstable behavior.

Recent work in interpretable machine learning has emphasized model transparency [12, 13] and behavioral consistency [2, 17], but their application in alpha mining remains limited. Likewise, robustness to noise and temporal perturbations is rarely examined in evaluating alpha quality, despite being critical for real-world deployment.

Our work fills these gaps by proposing <sub>AlphaEval</sub>, a unified evaluation framework that integrates interpretability, stability, and robustness into the assessment of alpha mining algorithms. In doing so, we shift the focus from narrow, label-dependent metrics to a more comprehensive, model-level evaluation approach.

## 3 Definition & Preliminary

Let ?? <sub>∈</sub> R<sup>??</sup> ×<sup>??</sup> ×<sup>??</sup> denote a panel of financial features, where ?? is the number of time steps, ?? is the number of assets (e.g., stocks), and ?? is the number of features per asset. Correspondingly, let ?? <sub>∈</sub> R<sup>??</sup> ×<sup>??</sup> denote the future returns:

![](images/f3ba15e3b342fe81e538fe5284aa007b0bb7f73a381993b7df26ac009de07486.jpg)

(1)

where close<sub>??,??</sub> denotes the closing price of stock ?? at time ??, <sub>Δ</sub>?? denotes the prediction interval .

The goal of alpha mining is to construct a set of alphas <sub>A =</sub> <sub>{</sub>??<sub>?? }</sub><sup>??</sup><sub>??=1</sub>, where each ??<sub>??</sub> is a symbolic or parametric function that produces a score matrix ?? (<sup>??</sup>) <sub>∈</sub> R<sup>??</sup> ×<sup>??</sup> :

![](images/6fc2f55e0ec33c04fb7337531c315ce21489c96435a5498fb4207cca559ec1a7.jpg)

(2)

where ??<sub>?? ??(??) 1:??,??,: ∈</sub> R<sup>??(??)</sup> ×<sup>??</sup> denotes the sequence of past ??(<sup>??</sup>) feature vectors of asset ?? up to time ??. Each alpha thus operates on a temporal slice of the data and outputs a scalar score per asset and time.

<sub>Stage</sub> <sub>I:</sub> <sub>Alpha</sub> <sub>Generation.</sub> The first stage aims to discover candidate alphas from the data via automated procedures. These include symbolic regression (e.g., genetic programming), reinforcement learning, or language models. The outcome is a candidate pool:

![](images/2e07d714e7fa49f1efa7d349490d39691f3a63c7ee9ef6b46fa54393e70b2c48.jpg)

(3)

Each ??<sub>??</sub> maps asset-level features to scalar scores over the entire panel ?? , resulting in a matrix ?? (<sup>??</sup>) <sub>∈</sub> R<sup>??</sup> ×<sup>??</sup> .

Stage II: Alpha Selection and Combination. <sup>Given</sup> <sup>the</sup> <sup>candidate</sup> pool <sub>Agen</sub>, the second stage selects a subset <sub>Asel ⊆</sub> <sub>Agen</sub> and combines them into a final signal matrix ?? <sub>∈</sub> R × :

![](images/3b76e9e27e3a553bcf8501fbde6f65341b02e23df6c650263d9501d48e195c61.jpg)

(4)

where <sub>F</sub> denotes a combination function, such as a weighted linear combination or a nonlinear model like LightGBM [9] or XG-Boost [4].

## 4 AlphaEval

To enable eficient and comprehensive evaluation of alpha mining models, we introduce <sub>AlphaEval</sub>, a multi-dimensional assessment framework that quantifies the quality of both the generated alpha signals and the underlying mining algorithms.

Unlike traditional evaluation paradigms focused solely on predictive metrics such as IC or backtest returns, AlphaEval ofers a unified benchmark across five complementary dimensions: <sub>predic-</sub> tive power<sup>,</sup> temporal stability<sup>,</sup> robustness to market perturbations<sup>,</sup> <sub>financial</sub> <sub>logic</sub>, and <sub>diversity</sub>. Among them, the first four dimensions are evaluated for the alpha quality and the last one dimension is evaluated for the mining ability of the model. An overview of AlphaEval is shown in Figure 1. In the following, we detail the motivation and implementation of each evaluation dimension.

## 4.1 Predictive Power

The most fundamental property of an alpha is its ability to predict future returns. In AlphaEval, we retain this classical perspective and include predictive power as one core dimension.

We adopt two widely used correlation-based metrics:

• Information Coeficient (IC)<sup>:</sup> <sup>Defined</sup> <sup>as</sup> <sup>the</sup> <sup>average</sup> <sup>Pear-</sup> son correlation between the alpha scores ??<sub>??,:</sub> and the realized returns ??<sub>??,:</sub> across assets over all time steps:

![](images/225a07bd7806f85490ca4ed9efea77bc72032e5e85dea99ac41eae3c7ea8c62a.jpg)

(5)

(6)

• Rank Information Coeficient (RankIC)<sup>:</sup> <sup>Defined</sup> <sup>as</sup> <sup>the</sup> average Spearman rank correlation between ??<sub>??,:</sub> and??<sub>??,:</sub> across time:

![](images/a6f5d7031d64bc4a5dd25473e42272e8fb0172342383540d4d080eed58645c0f.jpg)

(7)

![](images/f727363ffc8c218edaced7b6bd10d648c6a422c9e6493d3c76dcbaa14a0e3980.jpg)

(8)

![](images/6def06612f47aeac4fddf2ce952b12bff8518c5b9e77e136567d7cba6ebec56f.jpg)

(9)

where ?? -<sub>·??,??</sub>  denotes the rank of <sub>·??,??</sub> in <sub>·??,:</sub>.

![](images/444454f46992f38d825987ce9e3b7b9177731638695064c78599e2d0bacb48e4.jpg)  
Figure 1: Overview of AlphaEval. After getting the alpha calculation results from the alpha mining model, the combined alphas are obtained by the alpha combination model and evaluated by AlphaEval, which can get the scores of diferent dimensions for a comprehensive evaluation of the model.

Based on these metrics, we propose the <sub>Predictive</sub> <sub>Power</sub> <sub>Score</sub> <sub>(PPS)</sub>, defined as follows:

![](images/08a87e593fb05f0fdd13404679dc442aa21df9d959d46c320b596c50a81919db.jpg)

(10)

where ?? is a hyperparameter that controls the IC and RankIC occupancy. The metric summarize the predictive strength of an alpha across time. A higher PPS indicates stronger alignment between the alpha scores and subsequent asset returns, which is crucial for investment decision-making.

## 4.2 Temporal Stability

While high predictive accuracy is desirable, unstable alphas are dificult to deploy in real trading environments. Temporal stability measures how consistent an alpha’s ranking of assets remains across consecutive time steps, reflecting its reliability over time.

To quantify this, we propose the <sub>Relative</sub> <sub>Rank</sub> <sub>Entropy</sub> <sub>(RRE)</sub>:

![](images/8eaf195b4a08bfa4694a6b575fda663eae3155fff6601bff345bf7c154195ee0.jpg)

(11)

where KL<sub>(</sub>?? <sub>∥</sub>??<sub>)</sub> is a divergence-based entropy between two rank vectors at time ?? and ?? <sub>−</sub>1. In practice, we compute the KL dispersion

by converting the ranked arrangement into a discrete distribution:

![](images/335a5823a4c82ac06a7a8075189bf6a6ba49d01826111af5b4152c18fc2f4fbb.jpg)

(12)

![](images/b53c3fa3ca1d7c4881604c29664d597d089fa3bdcc1e1fd857a95a8155306d91.jpg)

(13)

A higher RRE indicates greater temporal consistency in asset ranking, which is favorable for stable portfolio construction and lower turnover. This stability is a desirable property in risk-sensitive or strategy-constrained scenarios.

## 4.3 Robustness to Market Perturbations

In financial markets, features are often subject to random fluctuations or structural shocks. A robust alpha should remain stable under such perturbations. To this end, we propose <sub>Perturbation</sub> <sub>Fidelity</sub> <sub>Score</sub> <sub>(PFS)</sub> to evaluate the sensitivity of alpha rankings to input-level noise.

Formally, let ?? <sub>∼</sub> <sub>D</sub> be a perturbation applied to the original feature tensor ?? , and define the perturbed alpha score as ??′ <sub>=</sub> ?? <sub>(</sub>?? <sub>+</sub>??<sub>)</sub>. The robustness of an alpha is quantified as the correlation between the original and perturbed asset rankings:

![](images/4d7eeb653ab81e62111b4e7d3562d8d745422e8fb091d148b164174465d8473a.jpg)

(14)

where Corr<sub>(·</sub>, <sub>·)</sub> denotes the Spearman rank correlation, similar to the RankIC definition above.

We consider two types of perturbation distributions:

<sub>• Gaussian</sub> <sub>noise</sub> (?? <sub>∼</sub> <sub>N</sub> <sub>(</sub>0, ?? <sub>)</sub>): simulates random fluctuations driven by market sentiment or microstructure noise.

<sub>•</sub> ?? <sub>-distribution</sub> (?? <sub>∼</sub> ?? <sub>(</sub>??<sub>)</sub>): mimics structural market shocks such as policy changes or crises, introducing heavy-tailed disturbances.

Based on these two diferent perturbations, the PFS is defined as follows:

![](images/6167a803607aa3948e3647e9bd0b98feaae1cb6c1395cdd4ab5271245a66b56f.jpg)

(15)

An alpha with high PFS is considered more robust and reliable in volatile or nonstationary market environments.

## 4.4 Financial Logic

In addition to statistical properties, the financial interpretability of alpha signals plays a crucial role in practical deployment, especially for risk management and compliance purposes. To assess the financial plausibility of a given alpha, we introduce a <sub>Logic</sub> <sub>Score</sub>, rated by a Large Language Model with financial knowledge.

Given the symbolic expression or natural language description of an alpha ??<sub>??</sub>, we prompt an LLM to evaluate its logical coherence, economic intuition, and interpretability.

The LLM’s response is parsed to extract a numerical score, which we denote as the Logic Score for ??<sub>??</sub> . We average this score across a set of alphas to summarize the logical quality of a mining algorithm.

While inherently subjective, this mechanism reflects a growing trend of combining human-aligned reasoning with automated alpha discovery. It complements traditional metrics by incorporating domain-informed assessments that cannot be easily captured by statistical measures alone.

## 4.5 Diversity

A desirable alpha set should contain diverse signals to avoid redundancy and enhance robustness when combined. We propose <sub>Diversity</sub> <sub>Entropy</sub> <sub>(DE)</sub>, which quantifies the diversity of the selected alpha set by analyzing the covariance structure of the output signals.

Let <sub>{</sub>?? (<sup>??</sup>) <sub>}</sub><sup>??</sup><sub>?? 1</sub> be ?? selected alpha signals, each flattened into a vector over all <sub>(</sub>??, ??<sub>)</sub> pairs. Let ?? <sub>∈</sub> R<sup>??</sup>×<sup>??</sup> be the covariance matrix computed over these ?? alpha vectors. We denote the eigenvalues of ?? as ??<sub>1</sub>, ??<sub>2</sub>, . . . , ??<sub>??</sub>.

To measure the distributional spread of variance across alpha signals, we normalize the eigenvalues into a probability distribution:

![](images/e03c7709cb278aeb40b2cb7b46e3c2574a6e97825e5f2d22b8924eeae7854fef.jpg)

(16)

The DH is then defined as the entropy of this distribution:

![](images/997504aa00cce4de6465726381e026a35fb95ce1a18675940fed02ec60c515c6.jpg)

(17)

Higher entropy indicates a more diverse alpha set that captures complementary information from multiple dimensions.

## 4.6 Overall AlphaEval Score

To aggregate the five dimensions of AlphaEval—Predictive Power (PPS), Temporal Stability (RRE), Robustness to Perturbations (PFS), Financial Logic (Logic), and Diversity (DE)—we compute a normal ized, composite score for each candidate alpha ??. For each metric ?? <sub>∈</sub> <sub>{</sub>PPS, RRE, PFS, Logic, DE<sub>}</sub>, we standardize scores within each dataset and evaluation round: ??˜ <sub>?? =</sub> <sup>??</sup> <sup>− ??</sup> ,where ??<sub>??</sub> and ??<sub>??</sub> ??<sub>??</sub> are the mean and standard deviation of metric ?? across all alphas under comparison. All five metrics are oriented so that larger values indicate better quality. The overall AlphaEval score is the convex combination AlphaEval<sub>(</sub> ??<sub>) =</sub> <sub>?? Í??</sub> ??<sub>??</sub> ??˜ <sub>??</sub>.

## 5 Experiments & Results

In this section, we conduct comprehensive experiments to demonstrate the efectiveness and practicality of the AlphaEval framework. We aim to answer the following questions:

<sub>• Q1:</sub> How do mainstream models perform under the evaluation of AlphaEval?

<sub>•</sub> <sub>Q2:</sub> Do the proposed evaluation dimensions ofer complementary information beyond traditional metrics?

<sub>• Q3:</sub> Is the evaluation framework robust when hyperparameters are adjusted?

<sub>•</sub> <sub>Q4:</sub> Are the evaluation scores aligned with real-world investment behaviors such as turnover and drawdown?

<sub>• Q5:</sub> Does AlphaEval significantly speed up the evaluation process compared to backtesting-based evaluation systems?

## 5.1 Experimental Setting

All evaluations are conducted using our implementation of AlphaEval on the public Qlib platform. We use both A-share and U.S. stock datasets provided by Qlib as our evaluation benchmarks . For the Predictive Power Score (PPS), we set the weighting parameter ?? to 0.5 to balance between predictive accuracy and stability over time. For the Perturbation Fidelity Score (PFS), we apply two types of noise: Gaussian and Student’s t-distributed. The standard deviation of Gaussian noise is set to the average daily volatility of the corresponding market index. For the t-distribution, the degrees of freedom are fixed at 3, and the distribution is rescaled to match the same standard deviation as the Gaussian case. This ensures a controlled comparison of robustness to market sentiment perturbations and policy changes perturbations.

## 5.2 Main Results

To answer <sub>Q1</sub>, We group models by methodology—genetic algorithm (GA-Based), reinforcement learning (RL-Based), generative adversarial networks (GANs-Based), and LLMs (LLMs-Based)—and compare them across all dimensions. Table 2 presents the performance of all baseline models under the proposed AlphaEval framework on A-share (China market) and the results on U.S. stock dataset are provided in Appendix F.

GA-based methods demonstrate strong robustness and stability, with GP achieving the highest robustness (0.983) and AutoAlpha excelling in diversity (0.946), though overall interpretability remains limited. RL-based methods, particularly AlphaGen, show outstanding stability (0.978) and robustness (0.997), alongside competitive predictive power, but sufer from low logic scores, indicating poor transparency. GANs-based methods ofer high predictive performance (0.040 for AlphaForge) and solid stability, but their robustness and logic consistency are less reliable. In contrast, LLMs-based methods—especially AlphaAgent—achieve the best overall tradeof: highest predictive power (0.041), best logic clarity (70.0), and strong diversity, but with slightly lower robustness. These results suggest that while RL and GA methods ofer behavioral reliability and search diversity, LLMs stand out by combining high predictive accuracy with semantic interpretability, making them particularly well-suited for human-in-the-loop financial applications.

Table 2: Performance of alpha mining models on A-Share under the AlphaEval framework. Bold is the highest, underlined is the second, random is only used as a reference value and is not involved in the comparison.  
![](images/10883109ab0d8dbebf0f15cf01365388ab83ae048a2ff82a80d8b44e959a63c8.jpg)

## 5.3 Ablation Study

To answer <sub>Q2</sub>, we conduct an ablation study based on metricspecific alpha selection. From the full set of candidate alphas—generated during the model search process, including those not selected for final output—we construct portfolios using top-ranked alphas ac-<sup>cording</sup> <sup>to</sup> <sup>individual</sup> <sup>metrics:</sup> Predictive Power Score (PPS)<sup>,</sup> Relative Rank Entropy (RRE)<sup>,</sup> Perturbation Fidelity Score (PFS)<sup>,</sup> and <sub>LLM</sub> <sub>Logic</sub> <sub>Score</sub>. These are compared against the integrated selection based on the full <sub>AlphaEval</sub> score.

Figure 2 shows the cumulative returns on the A-share market from 2021 to 2024. We find that each individual metric contributes positively to portfolio performance, reflecting its unique perspective on alpha quality. PPS and LLM Logic yield relatively strong returns, highlighting their efectiveness in capturing predictive and semantic strength, respectively. However, when used alone, they occasionally sufer from instability or diminished robustness. In contrast, RRE and PFS provide more conservative but stable profiles, emphasizing structural stability and noise resistance.

Importantly, the full AlphaEval score, which integrates all metrics, consistently outperforms any single-metric selection. This confirms that the proposed dimensions capture <sub>complementary</sub> as pects of alpha quality—such as predictability, robustness, diversity, and interpretability—and their combination leads to a more reliable and efective evaluation signal than traditional metrics alone.

## 5.4 Sensitivity Analysis

To answer <sub>Q3</sub>, sensitivity analyses were conducted on two key parameters: the weighting coeficient ?? in the Predictive Power Score (PPS), and the threshold for the Perturbation Fidelity Score (PFS).

As shown in Figure 3, varying ?? in the PPS formulation yields non-monotonic efects on cumulative portfolio returns. While moderate values (e.g., ?? <sub>=</sub> 0.5 and ?? <sub>=</sub> 0.8) lead to stronger performance, extreme values (?? <sub>=</sub> 0 or ?? <sub>=</sub> 1) result in diminished returns. This pattern suggests that incorporating multiple factor quality dimensions—rather than relying solely on predictive power—can lead to more robust alpha selection and better generalization.

Figure 4 further examines the impact of the PFS threshold on downside risk. When comparing low-PFS and high-PFS factor groups, factors with higher PFS consistently exhibit lower maximum drawdown. The diference becomes statistically significant (p-value < 0.05) when the threshold lies between 0.8 and 0.9, confirming that PFS efectively captures stability under noise perturbation. Together, these findings demonstrate that the proposed metrics not only guide factor selection but also align with real-world risk control considerations.

## 5.5 Justification of Evaluation Dimensions

To answer <sub>Q4</sub>, we analyzed and verified the rationality of the newly proposed metrics:

• Temporal Stability vs. Turnover<sup>:</sup> <sup>To</sup> <sup>assess</sup> <sup>the</sup> <sup>interpretabil-</sup> ity of Relative Rank Entropy (RRE), we examined its relationship with the annualized turnover rate (AnnTurn) . As shown in Figure 5(a), RRE exhibits a strong and statistically significant negative linear correlation with turnover. The fitted regression line indicates that as RRE increases—i.e., as alpha scores become more stable and structured—the resulting strategy becomes significantly less reactive, reflected in lower turnover rates. This suggests that RRE not only serves as a theoretical measure of rank consistency, but also reflects practical trading behavior.

• Robustness vs. MaxDrawdown<sup>:</sup> <sup>To</sup> <sup>evaluate</sup> <sup>the</sup> <sup>practi-</sup> cal utility of PFS, we partitioned the alpha pool based on a threshold of PFS <sub>≥</sub> 0.9. As illustrated in Figure 5(b), the high-PFS group exhibited substantially lower Max Drawdown (MaxDD), with a tighter and more favorable distribution. The definition of Max Drawdown is provided in Appendix B.

![](images/5f398ccc58f59371fc86974b97af7ee61141ed9a631ee96385f06d8428a1cfa0.jpg)  
Figure 2: Cumulative returns of portfolios constructed by selecting top-ranked alpha alphas based on diferent evaluation metrics: PPS, RRE, PFS, LLM Logic Score, and the integrated AlphaEval score.

![](images/d5ebbfa3645a60247f4c562a660d00db9043d0b177c31504ded52bb9d11352a4.jpg)  
Figure 3: Cumulative return trajectories of portfolios constructed under diferent values of <sup>??</sup> in the PPS formulation. The parameter <sup>??</sup> balances predictive power against factor quality dimensions. Moderate values (<sup>??</sup> = <sup>0.5, 0.8</sup>) yield superior performance compared to extreme values (<sup>??</sup> = <sup>0, 1</sup>), suggesting that an appropriate trade-of between predictive accuracy and robustness leads to more stable and efective alpha selection.

Statistical testing confirmed the diference to be highly sig nificant. These results demonstrate that PFS is not only a predictive score but also an efective selection criterion for identifying robust, low-risk strategies.

![](images/72d38992d30369c1087fdc2bd64544f07a5f9b365388229b7e1a1f88caaa4f30.jpg)  
Figure 4: Sensitivity analysis of the PFS threshold on downside risk. The upper panel shows the mean and median differences in maximum drawdown (MaxDD) between low-PFS and high-PFS factor groups across diferent PFS thresholds. The lower panel reports the corresponding <sup>??</sup>-values from ttests and Mann-Whitney U tests. A clear reduction in MaxDD is observed for higher-PFS groups, with statistical signifi cance achieved when the PFS threshold ranges from 0.8 to 0.9. These results validate the efectiveness of PFS in identifying more stable factors under noise and support its utility in risk-aware factor selection.

• Logic Score vs. Human Expert Judgment<sup>:</sup> <sup>We</sup> <sup>compute</sup> NDCG@?? across multiple cutof values (?? <sub>∈</sub> 5, 10, 20, 50, 100) to assess the model’s alignment with human rankings at diferent granularities [7, 22]. As shown in Figure 5(c), the model achieves consistently high NDCG scores, indicating strong agreement with human judgment in both top-ranked and overall alpha evaluation. These results further support the validity of the logic consistency dimension used in AlphaEval.

• Diversity via Covariance Entropy<sup>:</sup> <sup>The</sup> <sup>proposed</sup> <sup>Diver-</sup> sity Entropy (DH) provides a principled way to quantify the spread of variance across alpha signals by analyzing the spectrum of their covariance matrix. Intuitively, when multiple signals are highly correlated or collinear, their variance is concentrated along a few principal components, resulting in a low-entropy eigenvalue distribution. In contrast, when signals are orthogonal or capture complementary information, variance is more evenly distributed, yielding higher entropy. Therefore, DH serves as an efective proxy for the intrinsic dimensionality of the signal set, and can be used to detect and penalize multicollinearity.

![](images/4a1399fcb447dab5ed912dd29a05b1423a71113a37888ea9b88aaa4aab5a7352.jpg)

![](images/5342980cc95808deb53b74f18444d0b4c0b8f9231b2f8df989fb659114f91277.jpg)

![](images/ece20bee3e8645373d1ccd52f0af91a639431be482609272a3a9145bfd48f2b2.jpg)

![](images/325b3b3b96ab30a2148a317b7c4e87ec536dea6195039e4cf672d3c8712fa618.jpg)  
Figure 5: (a) Relative Rank Entropy (RRE) exhibits a strong negative correlation with annualized turnover (AnnTurn), suggesting that more temporally stable signals result in lower trading activity. (b) Alphas with higher Perturbation Fidelity Score (PFS ≥ <sup>0.9</sup>) show significantly lower maximum drawdown (MaxDD), indicating greater robustness to market perturbations. (c) The LLM-based logic score aligns closely with human expert rankings, as evidenced by consistently high NDCG@k values across diferent cutof thresholds. (d) AlphaEval significantly reduces evaluation time compared to traditional backtesting, highlighting its eficiency and scalability.

These results demonstrate that the AlphaEval metrics are not only computationally eficient but also aligned with real-world financial behaviors and theoretical intuition.

## 5.6 Evaluation Eficiency

To answer <sub>Q5</sub>, we compared the evaluation eficiency of AlphaEval with that of a traditional backtesting-based system. Unlike our metrics, portfolio backtesting exhibits path dependency. Positions, cash balances, and transaction costs evolve through state recursion. Dividing the time dimension into mutually exclusive weekly (or monthly) time slices and backtesting them independently causes cross-slice transfers (of positions, cash, and costs) to fail, leading to state leakage and non-additive gains/losses. Backtesting can be parallelized at the asset or parameter level, but sequential simulation of a single strategy along the timeline is essential to ensure accounting integrity.

For the parts of the computation that can be parallelized, we use 20 processes to parallelize the computation. As shown in Figure 5(d), AlphaEval achieves a significant speedup, reducing relative evaluation time by more than 25%. This improvement stems primarily from its backtesting-free design: all evaluation metrics in AlphaEval are formulated as functions that can be computed independently in parallel, in contrast to the inherently sequential nature of portfolio backtesting. This enables scalable and fast evaluations and accelerates the alpha mining process.

## 6 Conclusion

This paper introduces <sub>AlphaEval</sub>, a unified, backtesting-free, and parallelizable framework for evaluating automated alpha-mining models. To address the limitations of conventional practice—most notably an over-reliance on backtests and the use of incomplete single-metric summaries—we propose five complementary dimensions that together provide a holistic view of alpha quality: predic tive power, temporal stability, robustness to perturbations, financial logic, and diversity.

Extensive experiments spanning genetic programming, reinforcement learning, generative models, and large language models demonstrate the efectiveness of AlphaEval. The framework yields scores that align with backtesting outcomes while providing additional interpretability and diagnostic insight. Ablations confirm that the five dimensions are complementary, and empirical analyses show expected links with real-world behaviors such as turnover and drawdown. Moreover, AlphaEval substantially improves eval uation eficiency, enabling scalable alpha screening within large mining pipelines.

By decoupling evaluation from backtesting and releasing opensource tooling, AlphaEval promotes greater transparency, comparability, and reproducibility in alpha research. Looking forward, an important direction is to use AlphaEval not only as a post-hoc evaluator but also as a training signal during alpha generation—e.g., as reinforcement-learning rewards, diferentiable surrogates, or prompt-conditioning targets. This would enable self-improving agents that optimize not only predictive performance but also stabil ity, interpretability, and robustness. Extending AlphaEval to multi frequency, multi-asset, and cross-market settings is another key avenue for future work.

## 7 Limitations

While AlphaEval is practical and methodologically transparent, it has several limitations. First, the framework evaluates <sub>alphas</sub> rather than complete trading strategies; it does not replace simulation of position sizing, risk control, execution, or path-dependent accounting. Second, the <sub>Logic</sub> dimension currently relies on LLM-based scoring and can be sensitive to model choices and prompt design; although we introduce calibration and cross-judge checks, resid ual evaluator bias may remain. Third, although the framework is, in principle, asset-class agnostic, our empirical study focuses on equities.

To broaden applicability, we are extending AlphaEval to futures and multi-asset settings. For equity index futures, we will use stan dard continuous-contract construction (e.g., volume/open-interest rolls), margin conventions, and cost models, and we will release instrument lists and rolling rules to ensure reproducibility and comparability across asset classes.

## Acknowledgments

This paper is partially supported by grants from the National Key Research and Development Program of China with Grant No. 2023YFC-3341203 and the National Natural Science Foundation of China (NSFC Grant Number 62276002).

## References

[1] Lang Cao, Zekun Xi, Long Liao, Ziwei Yang, and Zheng Cao. 2025. Chain-of-Alpha: Unleashing the Power of Large Language Models for Alpha Mining in <sup>Quantitative</sup> <sup>Trading.</sup> arXiv preprint arXiv:2508.06312 <sup>(2025).</sup>

[2] Dangxing Chen. 2023. Can i trust the explanations? investigating explainable machine learning methods for monotonic models. <sub>arXiv</sub> <sub>preprint</sub> <sub>arXiv:2309.13246</sub> (2023).

[3] Tianxiang Chen, Wei Chen, and Luyao Du. 2021. An empirical study of financial factor mining based on gene expression programming. In <sub>2021</sub> <sub>4th</sub> <sub>International</sub> Conference on Advanced Electronic Materials, Computers and Software Engineering <sub>(AEMCSE)</sub>. IEEE, 1113–1117.

[4] Tianqi Chen and Carlos Guestrin. 2016. XGBoost: A Scalable Tree Boosting <sup>System.</sup> <sup>In</sup> Proceedings of the 22nd ACM SIGKDD International Conference on <sub>Knowledge</sub> <sub>Discovery</sub> <sub>and</sub> <sub>Data</sub> <sub>Mining</sub> (San Francisco California USA, 2016-08- 13). ACM, 785–794. doi:10.1145/2939672.2939785

[5] Can Cui, Wei Wang, Meihui Zhang, Gang Chen, Zhaojing Luo, and Beng Chin Ooi. 2021. AlphaEvolve: A Learning Framework to Discover Novel Alphas <sup>in</sup> <sup>Quantitative</sup> <sup>Investment.</sup> <sup>In</sup> Proceedings of the 2021 International Conference <sub>on</sub> <sub>Management</sub> <sub>of</sub> <sub>Data</sub> (Virtual Event China, 2021-06-09). ACM, 2208–2216. doi:10.1145/3448016.3457324

[6] Eugene F Fama and Kenneth R French. 2015. A five-factor asset pricing model. Journal of financial economics <sup>116,</sup> <sup>1</sup> <sup>(2015),</sup> <sup>1–22.</sup>

[7] Kalervo Järvelin and Jaana Kekäläinen. 2002. Cumulated gain-based evaluation <sup>of</sup> <sup>IR</sup> <sup>techniques.</sup> ACM Transactions on Information Systems (TOIS) <sup>20,</sup> <sup>4</sup> <sup>(2002),</sup> 422–446.

[8] Zura Kakushadze. 2016. 101 formulaic alphas. <sub>Wilmott</sub> 2016, 84 (2016), 72–81.

[9] Guolin Ke, Qi Meng, Thomas Finley, Taifeng Wang, Wei Chen, Weidong Ma, Qiwei Ye, and Tie-Yan Liu. 2017. LightGBM: A Highly Eficient Gradient Boosting <sup>Decision</sup> <sup>Tree.</sup> <sup>In</sup> Advances in Neural Information Processing Systems <sup>(2017),</sup> <sup>Vol.</sup> <sup>30.</sup> Curran Associates, Inc. https://proceedings.neurips.cc/paper\_files/paper/2017/ hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html

[10] Yuante Li, Xu Yang, Xiao Yang, Minrui Xu, Xisen Wang, Weiqing Liu, and Jiang Bian. 2025. R&D-Agent-Quant: A Multi-Agent Framework for Data-Centric Factors and Model Joint Optimization. In <sub>The</sub> <sub>Thirty-ninth</sub> <sub>Annual</sub> <sub>Conference</sub> <sub>on</sub> Neural Information Processing Systems<sup>.</sup>

[11] Zhiwei Li, Ran Song, Caihong Sun, Wei Xu, Zhengtao Yu, and Ji-Rong Wen. 2024. Can Large Language Models Mine Interpretable Financial Factors More Efectively? A Neural-Symbolic Factor Mining Agent Model. In <sub>Findings</sub> <sub>of</sub> <sub>the</sub> Association for Computational Linguistics: ACL 2024<sup>,</sup> <sup>Lun-Wei</sup> <sup>Ku,</sup> <sup>Andre</sup> <sup>Martins,</sup> and Vivek Srikumar (Eds.). Association for Computational Linguistics, Bangkok, Thailand, 3891–3902. doi:10.18653/v1/2024.findings-acl.233

[12] Nitin Rane, Saurabh Choudhary, and Jayesh Rane. 2023. Explainable Artificial Intelligence (XAI) approaches for transparency and accountability in financial decision-making. <sub>Available</sub> <sub>at</sub> <sub>SSRN</sub> <sub>4640316</sub> (2023).

[13] Vishnu Ravi, Vineet Kumar Srivastava, Maninder Pal Singh, Ravi Kumar Burila, Nikhil Kassetty, Padma Naresh Vardhineedi, Venkata Reddy Pasam, Nuzhat Noor Islam Prova, and Indrajit De. 2025. Explainable AI (XAI) for Credit Scoring and Loan Approvals. <sub>arXiv</sub> (2025).

[14] Junji Ren, Junjie Zhao, Shengcai Liu, and Peng Yang. 2025. From Linear to Hierarchical: Evolving Tree-structured Thoughts for Eficient Alpha Mining. doi:10.48550/arXiv.2508.16334 arXiv:2508.16334 [cs].

[15] Tao Ren, Ruihan Zhou, Jinyang Jiang, Jiafeng Liang, Qinghao Wang, and Yijie Peng. 2024. RiskMiner: Discovering Formulaic Alphas via Risk Seeking Monte Carlo Tree Search. http://arxiv.org/abs/2402.07080 arXiv:2402.07080 [q-fin].

[16] Cynthia Rudin. 2019. Stop Explaining Black Box Machine Learning Models for High Stakes Decisions and Use Interpretable Models Instead. arXiv:1811.10154 [stat.ML] https://arxiv.org/abs/1811.10154

[17] Eduardo Sepulveda, Felix Vandervorst, Bart Baesens, and Tim Verdonck. 2025. Enhancing explainability in real-world scenarios: towards a robust stability measure for local interpretability. <sub>Expert</sub> <sub>Systems</sub> <sub>with</sub> <sub>Applications</sub> 274 (March 2025). https://eprints.soton.ac.uk/499079

[18] Hao Shi, Weili Song, Xinting Zhang, Jiahe Shi, Cuicui Luo, Xiang Ao, Hamid Arian, and Luis Angel Seco. 2025. Alphaforge: A framework to mine and dynam ically combine formulaic alpha factors. In <sub>Proceedings</sub> <sub>of</sub> <sub>the</sub> <sub>AAAI</sub> <sub>Conference</sub> <sub>on</sub> Artificial Intelligence<sup>,</sup> <sup>Vol.</sup> <sup>39.</sup> <sup>12524–12532.</sup>

[19] Ziyi Tang, Zechuan Chen, Jiarui Yang, Jiayao Mai, Yongsen Zheng, Keze Wang, Jinrui Chen, and Liang Lin. 2025. Alphaagent: Llm-driven alpha mining with regularized exploration to counteract alpha decay. In <sub>Proceedings</sub> <sub>of</sub> <sub>the</sub> <sub>31st</sub> <sub>ACM</sub> SIGKDD Conference on Knowledge Discovery and Data Mining V. 2<sup>.</sup> <sup>2813–2822.</sup>

[20] Hariom Tatsat and Ariye Shater. 2025. Beyond the Black Box: Interpretability of LLMs in Finance. arXiv:2505.24650 [cs.CE] https://arxiv.org/abs/2505.24650

[21] Saizhuo Wang, Hao Kong, Jiadong Guo, Fengrui Hua, Yiyan Qi, Wanyun Zhou, Jiahao Zheng, Xinyu Wang, Lionel M. Ni, and Jian Guo. 2025. QuantBench: Benchmarking AI Methods for Quantitative Investment. arXiv:2504.18600 [q fin.CP] https://arxiv.org/abs/2504.18600

[22] Yining Wang, Liwei Wang, Yuanzhi Li, Di He, Tie-Yan Liu, and Wei Chen. 2013. A Theoretical Analysis of NDCG Type Ranking Measures. arXiv:1304.6480 [cs.LG]

https://arxiv.org/abs/1304.6480

[23] Feng Xu, Yan Yin, Xinyu Zhang, Tianyuan Liu, Shengyi Jiang, and Zongzhang Zhang. 2024. \$\text{Alpha}^2\$: Discovering Logical Formulaic Alphas using Deep Reinforcement Learning. doi:10.48550/arXiv.2406.16505 arXiv:2406.16505 [cs, q-fin].

[24] Xiao Yang, Weiqing Liu, Dong Zhou, Jiang Bian, and Tie-Yan Liu. 2020. Qlib: An AI-oriented Quantitative Investment Platform. arXiv:2009.11189 [q-fin.GN] https://arxiv.org/abs/2009.11189

[25] Shuo Yu, Hongyan Xue, Xiang Ao, Feiyang Pan, Jia He, Dandan Tu, and Qing He. 2023. Generating Synergistic Formulaic Alpha Collections via Reinforcement <sup>Learning.</sup> <sup>In</sup> Proceedings of the 29th ACM SIGKDD Conference on Knowledge <sub>Discovery</sub> <sub>and</sub> <sub>Data</sub> <sub>Mining</sub>. doi:10.1145/3580305.3599831

[26] Tianping Zhang, Yuanqi Li, Yifei Jin, and Jian Li. 2020. AutoAlpha: an Eficient Hierarchical Evolutionary Algorithm for Mining Alpha Factors in Quantitative Investment. arXiv:2002.08245 [q-fin] http://arxiv.org/abs/2002.08245

[27] Junjie Zhao, Chengxi Zhang, Min Qin, and Peng Yang. 2024. QuantFactor REIN-FORCE: Mining Steady Formulaic Alpha Factors with Variance-bounded REIN-FORCE. doi:10.48550/arXiv.2409.05144 arXiv:2409.05144.

[28] Junjie Zhao, Chengxi Zhang, Chenkai Wang, and Peng Yang. 2025. Learning from Expert Factors: Trajectory-level Reward Shaping for Formulaic Alpha Mining. arXiv:2507.20263 [cs.LG] https://arxiv.org/abs/2507.20263

[29] Zhoufan Zhu and Ke Zhu. 2025. AlphaQCM: Alpha Discovery in Finance with Distributional Reinforcement Learning. In <sub>Forty-second</sub> <sub>International</sub> <sub>Conference</sub> on Machine Learning<sup>.</sup>

## A Code

Our code is available at https://github.com/LeoDingggg/AlphaEval.

## B Basic Metrics

The features and operators used in the alpha mining process and their meanings are in Table 3. For metrics used in previous work, the exact definition is given here.

<sub>ICIR:.</sub> Based on the definition of IC, ICIR can be defined as follows:

![](images/bf9c69d1275abe82e277fb3e14977e733f427775b34b81928fce4218b41cfcdd.jpg)

(18)

RankICIR is defined similarly.

<sub>AR:.</sub> Given the final score matrix ?? <sub>∈</sub> R<sup>??</sup> ×<sup>??</sup> , a daily long-short portfolio is constructed at each time step ??. Let ??<sub>?? ∈</sub> R denote the portfolio weights:

![](images/603b9bbe24adb1f334a2e80290ec6195662d94f050ab733e01f713cdcb63afda.jpg)

(19)

where ?? is the number of assets selected for both long and short sides. The portfolio return at time ?? is defined as:

![](images/bc0c79df4c980fb10a96fcd5ca0bcbed5d2866c321e304b785eee8fc16cb5f22.jpg)

(20)

Therefore, Annualized Return (AR) can be defined as:

![](images/b82fbe50be2ef13197c127b03b3064a39b58b8227532f5be0333db6aaa9e4c18.jpg)

(21)

where ??¯ <sub>=</sub> <sup>1</sup><sub>?? Í</sub><sup>??</sup><sub>??=1</sub> ??<sub>??</sub> is the average daily return, and ?? denotes the number of trading days in a year (typically ?? <sub>=</sub> 252).

<sub>SR:.</sub> Sharpe Ratio (SR) measures the performance of an investment compared to a risk-free asset, after adjusting for its risk. The defination is follows:

![](images/e02163c9127e232f7e782a2a0cbe9bbff51fa326b09e88d70ead320de9b9dcea.jpg)

(22)

<sup>1</sup><sub>?? −1 Í</sub><sup>??</sup><sub>??=1 (</sub>??<sub>??</sub> <sub>−</sub> ??¯<sub>)</sub>2 is the standard deviation of daily 1 where ??<sub>?? =</sub> returns. The risk-free rate is assumed to be zero for simplicity.

Table 3: Features and Operators and their corresponding meanings(partial list).  
![](images/9f059cb7f4243c94635fcb6e6b8765d53a3d70b40d72b582a9ac3bf2a0cbcb95.jpg)

Table 4: OLS Regression Results: RRE as Predictor of Annualized Turnover  
![](images/6e42904c2f766d74fbcbc213b948dd92619cf6d00f2e4c2735e13131f579b96d.jpg)

Table 5: Statistical Comparison of MaxDD between High and Low PFS Groups (Threshold = 0.9)  
![](images/ac79a7eff56b9245e23d3152bbc6a7dac09805b1cb52490a326d8de6aaf2ebb4.jpg)

<sub>Turnover</sub> <sub>Rate:</sub> Turnover Rate measures the trading frequency implied by the signal. A higher turnover indicates more frequent portfolio rebalancing, which may lead to increased transaction costs and lower net returns in real-world deployment. It can be defined as:

![](images/6b6459738b1fcb65889604152ae1cc7fea8ea80bfa50f29a808b074aa31a65b9.jpg)

(23)

where <sub>|</sub> <sub>·</sub> <sub>|1</sub> denotes the ℓ<sub>1</sub> norm, measuring the total absolute change in position weights across consecutive time steps. The range of the turnover rate is <sub>[</sub>0, 2<sub>]</sub>.

<sub>MDD:.</sub> Maximum Drawdown (MaxDD) quantifies the worst-case loss from a historical peak in the cumulative return curve. It reflects the risk of large interim losses and is widely used as a measure of downside risk in portfolio evaluation. Let the cumulative net asset value (NAV) series be defined as:

![](images/2278c6091a808f3caf494c1064f67029ede43402cf52dbb7def2cbefd976bca7.jpg)

(24)

Then the maximum drawdown is computed as:

![](images/79a5356e58eef4a2c45773a7ecd32e5c689a98909f1731dfbbea8094d0f516a2.jpg)

(25)

representing the largest observed loss from a peak to a subsequent trough in the NAV curve.

<sub>NDCG@k.</sub> Let rel<sub>??</sub> denote the relevance grade of the item at rank ?? in a predicted ordering. Define

![](images/b3f1585cba2133cb5a89e84dec3d246b5872154f3de4ace3dd12b266a4d1992f.jpg)

where IDCG@?? is the maximum possible DCG@k achieved by the ideal (ground-truth) ordering. We report NDCG@k to quantify how closely the predicted ordering (e.g., LLM or human-judged Logic scores) matches the reference ordering.

## C Datasets

We get the A-share dataset and S&P 500 dataset from Qlib. The time ranges for Train/Valid/Test on A-Share dataset are 2010-01-01 – 2019-12-31/2020-01-01 – 2020-12-31/2021-01-01 – 2024-12-31. The time ranges for Train/Valid/Test on S&P 500 dataset are 2010-01-01 – 2015-12-31/2016-01-01 – 2016-12-31/2017-01-01 – 2020-12-31.

## D Feature & Operator See Tabel 3.

## E Significance Analysis

In this section, we analyze the significance of the linear fitting experiments of RRE to the annualized turnover rate in the main text, as well as the experiments comparing the threshold of PFS to MaxDD.

Table 4 shows the results of an OLS regression predicting annualized turnover using RRE as the sole independent variable. The coeficient for RRE is significantly negative (?? = -4.361, ?? < 0.001), indicating that higher RRE scores are strongly associated with lower turnover rates. The model explains 81.5% of the variance in turnover (?? = 0.815), suggesting that RRE can serve as a meaningful proxy for trading intensity.

To assess the efectiveness of PFS as a filtering criterion for strategy robustness, we compared Max Drawdown (MaxDD) between groups with PFS <sub>≥</sub> 0.9 and PFS < 0.9. As reported in Table 5, the diference in MaxDD between the two groups was statistically significant. The independent samples t-test yielded ??(70.59) = 4.12, ?? = 0.0001, while the non-parametric Mann-Whitney U test also confirmed this diference (?? = 11,381.5, ?? = 0.0001). These results indicate that higher PFS scores are strongly associated with lower drawdowns, validating the practical utility of PFS as a reliable riskscreening metric.

Table 6: The main results on US Market (S&P 500) under the AlphaEval framework. Bold is the highest, underlined is the second, random is only used as a reference value and is not involved in the comparison.  
![](images/4ab904d65ae359d763acd6262bff3a58974b66a18692fce9a255afa52709006f.jpg)

## F Extra Results

We evaluate all models except AlphaEvlove using AlphaEval on the S&P 500 dataset. The results are in Table 6.

## G Proof of DH as a Multicollinearity Detector

We formally justify that the proposed <sub>Diversity</sub> <sub>Entropy</sub> <sub>(DH)</sub> is inversely related to the degree of multicollinearity among alpha signals.

column vectors of equal length, and let <sup>??</sup> ∈ <sup>R??×??</sup> be their sample covariance matrix. Let <sup>??</sup>1<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>?? be the eigenvalues of <sup>??</sup>, and define the normalized spectral distribution as <sup>??</sup>?? = <sub>Í</sub><sup>????</sup><sub>?? ????</sub> . The Diversity Entropy is defined as:

![](images/8a03887510860fa7572c8039a5783b1703dce6654f45077aca7951742fec3d66.jpg)

Then:

(1) DH <sub>∈</sub> <sub>[</sub>0, 1<sub>].</sub>

<sup>(2)</sup> <sup>DH</sup> = <sup>0</sup> if and only if the rank of <sup>??</sup> is 1 (i.e., all signals are perfectly collinear).

<sup>(3)</sup> Smaller values of <sup>DH</sup> imply stronger linear dependence among the signals (i.e., higher multicollinearity).

Proof. <sub>(1)</sub> The set <sub>{</sub>??<sub>?? }</sub> forms a valid probability distribution since ??<sub>?? ≥</sub> 0 and <sub>Í??</sub> ??<sub>?? =</sub> 1. The normalized Shannon entropy of any such distribution lies in <sub>[</sub>0, 1<sub>]</sub>.

<sub>(2)</sub> If rank<sub>(</sub>??<sub>)</sub> <sub>=</sub> 1, then ?? has only one non-zero eigenvalue, say ??<sub>1</sub> > 0 and ??<sub>2</sub>, . . . , ??<sub>?? =</sub> 0. Then ??<sub>1 =</sub> 1 and ??<sub>?? =</sub> 0 for ?? > 1, so DH <sub>=</sub> 0.

Conversely, if DH <sub>=</sub> 0, then the entropy of <sub>{</sub>??<sub>?? }</sub> is zero, which only occurs when all the probability mass is concentrated at a single

index, i.e., ??<sub>?? =</sub> 1 for some ??, implying all other eigenvalues are zero.   
Thus ?? is rank 1 and signals are linearly dependent.

<sub>(3)</sub> When multicollinearity is strong, the signal vectors lie close to a low-dimensional subspace, and ?? becomes ill-conditioned or low-rank. Its eigenvalue spectrum becomes more skewed (i.e., concentrated), reducing entropy. Thus, lower DH reflects stronger redundancy among signals. □

## H Details of LLMs

In this paper, for the implementation of FAMA and AlphaAgent, we use GPT-4o as the base model. For LLM used in FAMA, we set the max\_tokens <sub>=</sub> 500, temperature=0.5. For Idea Agent in AlphaAgent, we set the temperature=1.0. For Factor Agent in AlphaAgent, we set the temperature=0.3. For Eval Agent in AlphaAgent, we set the temperature=0.4.

For the implementation of Logic Score, we use GPT-4o to judge the logic of alpha. We set the max\_tokens <sub>=</sub> 1000, temperature=0.2, the prompt is following:

Below is a set of quantitative factor expressions designed using qlib syntax.

Please score each factor from 50 to 100 based on the rationality of financial market logic (full score), and provide the corresponding logical explanation.

When scoring, diferences in scores can be larger: logical factors can receive very high scores, and vice versa.

Factor list: {factor\_expressions}

Please return <sub>a</sub> <sub>pure</sub> <sub>JSON</sub> <sub>array</sub> <sub>only</sub>, without any Markdown code blocks. "

The array length should match the factor list, and each element should be an object containing:

<sub>•</sub> factor: the factor expression

<sub>•</sub> score: numeric score (50–100)

<sub>•</sub> explanation: a brief logical explanation