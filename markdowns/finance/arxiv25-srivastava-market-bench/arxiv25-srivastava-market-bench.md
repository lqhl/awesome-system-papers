# MARKET-BENCH: EVALUATING LARGE LANGUAGE MODELS ON INTRODUCTORY QUANTITATIVE TRADING AND MARKET DYNAMICS

Abhay Srivastava<sup>1</sup> Sam Jung<sup>1∗</sup> Spencer Mateega<sup>1</sup> <sup>1</sup>AfterQuery

## ABSTRACT

We introduce MARKET-BENCH, a benchmark that evaluates large language models (LLMs) on introductory quantitative trading tasks by asking them to construct executable backtesters from natural-language strategy descriptions and market assumptions. Each instance specifies one of three canonical strategies—scheduled trading on Microsoft (NASDAQ: MSFT), pairs trading on Coca-Cola (NASDAQ: KO) and Pepsi (NASDAQ: PEP), or delta hedging on MSFT—and models must produce code whose P&L, drawdown, and position paths match a verifiable reference implementation. We assess thirteen state-of-the-art models using a multi-round evaluation that separates structural reliability (whether the backtest runs) from numerical accuracy (mean absolute error of the backtest metrics), assigning failed outputs a duplicated-metrics baseline MAE. While most models reliably execute the simplest strategy (average Executable Passes of 4.08 out of 5 rounds), errors vary by orders of magnitude across models and tasks: Gemini 3 Pro and Claude 4.5 Sonnet combine strong reliability with low error on simpler strategies, GPT-5.2 achieves strong overall performance with perfect executability, GPT-5.1 Codex-Max achieves the lowest best-run error on the easiest task, and Qwen3 Max attains perfect executability yet sometimes produces inaccurate P&L paths. These results show that current LLMs can scaffold basic trading infrastructure but still struggle to reason robustly about prices, inventory, and risk; we release MARKET-BENCH and a public leaderboard at: https://marketbench.ai.

## 1 INTRODUCTION

The field of quantitative trading is extremely high-stakes. The hallucinations and incomplete inputs of LLMs cannot be used to trade in an environment where there are millions of dollars on the line. In order for these models to be used practically in this field, they must be able to understand and apply fundamental trading concepts and basic market dynamics, such as:

• Trading rules and order execution

• Implementing strategies in backtests

• Understanding market and risk data

The existing evaluations of large language models in finance focus on high-level tasks such as summarizing earnings calls, evaluating company fundamentals, modeling cash flows, or predicting sentiment of headlines. There has been little research that evaluates models on their ability to assist traders on a day-to-day basis.

This paper takes a step toward closing that gap by introducing MARKET-BENCH, a benchmark that evaluates:

Given a description of a trading strategy and market data, can a large language model construct a backtest whose output metrics match those of a verifiable implementation?

We design MARKET-BENCH around three strategies that capture some of the fundamental aspects of market dynamics:

1. Scheduled trading on a single stock (NASDAQ: MSFT), focusing on order-book interaction, position tracking, and P&L accounting.

2. Pairs trading on (NASDAQ: KO) and (NASDAQ: PEP), stressing spread computation, z-scorebased entry/exit rules, and joint capital management across multiple symbols.

3. Options delta hedging on (NASDAQ: MSFT), focusing on hedging deltas from an external options portfolio using the underlying stock.

## 2 RELATED WORK

Financial large language models. There has been increased work to build domain-specific large language models for finance. BloombergGPT, for example, is an early proprietary model trained on a large mixture of general and financial data to support tasks such as sentiment analysis, news classification, and question answering within the Bloomberg ecosystem (Wu et al., 2023). On the other hand, FinGPT proposes an open-source pipeline for financial large language models that emphasizes automatic data pulling and lightweight fine-tuning so that models can be continually adapted to new market information (Yang et al., 2023). Furthermore, the PIXIU framework introduces an evaluation suite that covers multiple financial NLP and prediction tasks, providing one of the first publicly available financial LLM + benchmarks (Xie et al., 2023). More recently, FinBen and Open-FinLLMs continue in this direction by covering a broad range of financial tasks and multimodal benchmarks and models (text, tables, time series, and charts), respectively (Xie et al., 2024a;b). In addition, FinanceQA also demonstrates that models fail 60% of realistic tasks at hedge funds and other financial institutions Mateega et al. (2025). Most of the current work in this area evaluates high-level language tasks such as classification, extraction, and textual analysis.

Financial benchmarks for LLMs. There have been several benchmarks on evaluating large language models in financial domains. FinEval targets Chinese financial domain knowledge through thousands of multiple-choice questions which span academic finance along with industry practice. In addition, CFinBench builds a comprehensive Chinese financial benchmark which tests professional qualification exams and roles like tax consultants and securities analysts (Nie et al., 2024). FinEval-KR further separates knowledge versus reasoning ability and introduces separate metrics and datasets to study both at the same time (Dou et al., 2025). BizFinBench evaluates practical, business driven applications like calculation, reasoning, and information extraction (Lu et al., 2025). While these benchmarks provide broad coverage of financial reasoning and understanding, they do not test how these models could be practically used in a quantitative trader’s day to day life.

Code-generation and program-synthesis benchmarks. On the code side, MARKET-BENCH has similar aspects to general purpose code generation benchmarks. HumanEval evaluates models trained on code by asking them to create function bodies that pass unit tests (Chen et al., 2021). MBPP (Mostly Basic Programming Problems) measures creation on short, natural language problems with unit test evaluation as well (Austin et al., 2021). DS-1000 targets data science code generation in realistic settings by using problems from StackOverflow spanning seven Python libraries. It highlights the inconsistency of model generated code for data science tasks (Lai et al., 2022). Furthermore, SWE Bench tested models on 2,294 different software engineering problems Jimenez et al. (2024). Current state-of-the-art models can solve ∼70% of the latest SWE-bench problems. These benchmarks stress code correctness but are not applied to financial market structure. MARKET-BENCH instead focuses on domain-specific backtesting and market mechanics, evaluating models both on code reliability and on error of P&L, positions, and risk metrics when compared to a verifiable implementation.

## 3 BENCHMARK DESIGN

## 3.1 DATA COLLECTION

All of the datasets were either generated synthetically through a random process or obtained from (Databento Inc., 2025). We preprocessed the datasets by randomizing the volume available at each

price level and only using the top 3 levels available. This was done to ensure that the models tracked the liquidity that trades remove from the book and whether they persisted that liquidity correctly. Furthermore, the options delta dataset for Strategy 3 was generated using a simple random walk.

## 3.2 HIGH-LEVEL STRATEGY DESCRIPTIONS

Strategy 1: Scheduled market-order execution on MSFT. Strategy 1 uses data from Databento’s Market-by-price L10 data for Microsoft (MSFT). At pre-specified timestamps in the data, the strategy sends a market order to either buy or sell various quantities of MSFT. Each market order takes liquidity from the current book, net of previous trades at that price level and potentially from several price levels at once.

The strategy tracks:

• Cash and MSFT position,

• Realized P&L using FIFO accounting,

• Unrealized P&L based on raw-book mid-prices,

• An equity curve and maximum drawdown,

• Synthetic-book statistics such as total size available and bid/ask VWAP post model trades.

Strategy 2: Pairs mean-reversion on Coke and Pepsi stock. Strategy 2 is a pairs trading strategy between KO and PEP which uses L10 order book data from both. At each new book update for either symbol, the strategy calculates mid-prices for both symbols and creates a spread between them as a linear combination of the two. A rolling history of the spread is then used to calculate a mean and the z-score of the current value.

The strategy has a position state (flat, long-spread, or short-spread). When the z-score exceeds an entry threshold, the strategy enters a mean-reversion position by buying one leg and selling the other. Positions are then flattened when the z-score reverts toward zero below an exit threshold. Additional features include:

• A cooldown mechanism that prevents quick re-entry in the same direction,

• A shared capital account for both symbols,

• Synthetic books and VWAP tracking per symbol,

• Immediate-or-cancel limit orders priced from synthetic mid and spread.

Strategy 3: Options delta hedging on MSFT. Strategy 3 utilizes MSFT order book data alongside a predefined option delta time series from a “separate” strategy. At regular time intervals, this strategy evaluates the current net delta and trades a portion of that delta to get flat. A minimum time difference between hedges is also enforced.

Hedge trades use fill-or-kill limit orders, where the limit price is set from synthetic mid-price and book spread. Each order experiences a fixed exchange delay before execution. As in the other strategies, a synthetic book persists consumed liquidity, and we track:

• Stock position and options delta,

• Net delta of the combined portfolio,

• Realized and unrealized P&L from stock trades,

• Equity and maximum drawdown.

All three strategies required the models to track and reserve the liquidity they removed from the book through simulated trades. This is done by reserving these prices and creating a “synthetic book” which nets the raw order book data and the consumed liquidity. Furthermore, Strategies 2 and 3 also include a delay between submitting an order and hearing back from the exchange, mirroring the real world.

## 3.3 PROMPT DESIGN

The prompt for each strategy included relevant information describing the strategy along with information for the input and output datasets. The column names of the input dataset were explicitly detailed. Reasoning and thinking were enabled for the models that support it, and the temperature was set to 0.0. A time limit of 10 minutes was enforced for the model to give a valid response. Furthermore, the allowed packages were: pandas, numpy, pathlib, datetime, collections, typing, statistics, math, sys, os, and dataclasses.

## 3.4 EVALUATION STRUCTURE

For each strategy s ∈ {1, 2, 3}, we define five distinct rounds r ∈ {1, . . . , 5}. The results from each round are averaged to create a final result for that model. Each round corresponds to a specific input dataset, parameter configuration, and reference implementation. Every model m is evaluated on all 3 × 5 = 15 (strategy, round) combinations.

For each (s, m, r), we sample up to K = 3 independent, one-shot attempts. An attempt refers to the model receiving the input data alongside the prompt and outputting code. This code is then checked and run to ensure successful execution. If execution succeeds, we record:

• status = SUCCESS,

• The resulting average MAE between model-generated and reference metrics.

If execution fails (e.g., due to syntax errors, missing fields, or runtime assertions), we record:

• status = FAILED,

• The error trace

4 EVALUATION METRICS AND PROTOCOL

## 4.1 PER-ATTEMPT METRICS

For each attempt, we compute average mae defined as the mean absolute error between the vector of reference metrics y and the vector of model-generated metrics yˆ:

![](images/2c33352abcc9504105493388a07e569827453eca605d0bafe5ac983af8bf1508.jpg)

(1)

where d is the number of scalar metrics (e.g., total P&L, max drawdown, etc.) produced by the backtester for the final state of the simulation.

For attempts that do not produce comparable outputs (failed attempts), we assign a strategy specific baseline MAE by repeating the initial (first row) metrics for all timestamps and computing its MAE against the true metrics time series. This baseline corresponds to not building a backtest at all as it repeats what was initially given.

## 4.2 PER-ROUND AGGREGATION

For each (s, m, r) (strategy, model, round) triple, we aggregate over attempts as follows:

![](images/d60f563efc62b9fc9febc438cda17cceeb1950826080f9185d77f976390a8d8b.jpg)

(2)

and if a round is never solved, we set best mae to the strategy-specific baseline MAE and treat the round as unsolved for executability counting.

## 4.3 PER-STRATEGY METRICS

For each model m and strategy s, we define:

![](images/79089cbdbc17a76e0a889fbff1ffac6b9a4241e110eac0fbf0a8e075be0b6687.jpg)

(3)

![](images/02b56c02cfc29f526e58fc42fa77e80e0369205e5184d9bfa9d464e22a41c8ed.jpg)

(4)

![](images/0103cf9387a3c6bea74880e7e066c6c4196540150725d8eab3a9843fb68a943e.jpg)

(5)

Here, Mean MAE averages numerical error across all rounds, including baseline-filled failures; Best Run MAE captures the best numerical fidelity achieved in any round; and Executable Passes counts how many rounds produced an executable backtest.

## 4.4 OVERALL METRICS AND RANKING

To obtain an overall view across strategies, we aggregate per model over all 15 (strategy, round) combinations:

![](images/a4c9504123d934ce550321e3b9afe7926d726d1e70577f5c3c1121f721b70b23.jpg)

(6)

![](images/65ea8514c82854b8a11b1d92fd8fd006ef75cb9b923913a910037b25b8b2ec84.jpg)

(7)

![](images/4a8d5d6c1ed371ca5b5541ac91ab773c979b601481b9cc3559645bf78e5f3f0e.jpg)

(8)

Within each strategy (and overall), we rank models by: Mean MAE. All scalar figures reported in the tables and text below (MAE and executable passes) are rounded to two decimal places.

## 5 EXPERIMENTAL RESULTS

## 5.1 STRATEGY-LEVEL RESULTS

Tables 1–3 show the per-strategy rankings for all models, sorted from best to worst. Each table lists mean MAE, best run MAE, and executable passes.

## 5.1.1 STRATEGY 1: SINGLE-STOCK SCHEDULED EXECUTION

![](images/82eaea56447031c4618e3dcafd811b8655d41707225dce8a4e55c7077ed698fd.jpg)  
Table 1: Strategy 1: Scheduled execution on MSFT. Eight of thirteen models solve all five rounds (Executable Passes = 5).

Strategy 1 is the easiest task. No model fails all five rounds, and the average Executable Passes across all models is 4.08 out of 5. However, the errors of the outputs vary considerably.

• GPT-5.1 Codex-Max achieves the lowest best-run MAE (0.002) with Executable Passes = 5, though its mean MAE (844.74) is higher due to variance across rounds.

• Gemini 3 Pro and Claude Sonnet combine reliability (Executable Passes = 5) with very small mean MAE (14.83 and 16.36, respectively).

• DeepSeek V3.2 and Mistral-Large-2512 also solve all rounds but with higher MAE (139.19 and 361.87), while Llama-4 Maverick has substantially larger error (4,137.62) despite Executable Passes = 5.

• Qwen3 Max, GPT-5.2, Amazon Nova Premier, Nvidia Nemotron, and Cohere Command-A frequently produce executable backtests but with errors in the hundreds to thousands.

Strategy 1’s results show that even relatively simple single-asset execution logic for market orders requires more reasoning than models can currently execute. Small mistakes in lot tracking or synthetic-book handling accumulate into large discrepancies.

## 5.1.2 STRATEGY 2: PAIRS MEAN-REVERSION ON COKE/PEP

![](images/06cae98b107a185d9a98ef6aaa7dec3cc54090858c9fa0849bc0de8b3bb1f0d4.jpg)  
Table 2: Strategy 2: Pairs mean-reversion on COKE and PEPSI.

Strategy 2 is more structurally challenging. Amazon Nova Premier never produces a successful attempt (Executable Passes = 0), and several other models solve only two of the five rounds. On average, models achieve Executable Passes of 3.46. The errors of the model outputs also show a wide spread:

• Gemini 3 Pro again stands out, with Executable Passes = 5 and the lowest mean MAE of 52.22.

• GPT-5.2 and GPT-5.1 Codex-Max achieve low MAE (107.02 and 136.97, respectively), and both have Executable Passes = 5.

• Claude Sonnet and Mistral-Large-2512 both solve all rounds with moderate MAE (193.32 and 228.90).

• Qwen3 Max attains Executable Passes = 5 but has an MAE on the order of 4.09 × 10<sup>8</sup>, reflecting extreme divergence in logic from the verifiable backtester.

This strategy stresses multi-asset state management along with strict entry and exit rules. Errors in z-score computation, sizing of legs, or shared capital can cause large discrepancies from the intended behavior.

## 5.1.3 STRATEGY 3: DELTA HEDGING WITH MSFT

![](images/df10490f8a6d5d22120ac7ddd1077aeb14cea4fcc3c8e34f611f5f8610fd6988.jpg)  
Table 3: Strategy 3: Delta-hedging MSFT against options delta. MAE spans several orders of magnitude.

Strategy 3 is the most complex and numerically the harshest task. Two models (Amazon Nova Premier and Nvidia Nemotron) never solve a round (Executable Passes = 0), while seven models achieve Executable Passes = 5. Average Executable Passes across models is 3.38, and mean MAE spans several orders of magnitude.

• GPT-5.2 achieves the lowest mean MAE (1,369.59) with Executable Passes = 5.

• Grok 4 also performs well, with Executable Passes = 5 and a mean MAE of 1,482.33.

• GPT-5.1 Codex-Max, Claude Sonnet, and DeepSeek V3.2 solve all rounds but with MAE in the range of 10,496.40–16,157.31.

• Qwen3 Max again shows extreme numerical divergence (329,700.43 MAE) despite consistent output.

The sensitivity of this strategy comes from the interaction between the options delta series, the timing and size of hedge orders, and the fill-or-kill order execution type along with exchange delay. Small conceptual mistakes in how deltas are aggregated or how hedges are throttled can accumulate into very large mismatches in P&L and net delta over the course of the simulation.

## 5.2 STRATEGY DIFFICULTY

We can summarize strategy difficulty by averaging metrics across models (excluding NaN MAE values):

• Strategy 1: Average Executable Passes = 4.08 and average mean MAE = 9.42 × 10<sup>2</sup>. Excluding Qwen3 Max, the average mean MAE drops to 8.53 × 10<sup>2</sup>.

• Strategy 2: Average Executable Passes = 3.46 and average mean MAE = 3.15 × 10<sup>7</sup>, dominated by the extreme outlier from Qwen3 Max. Excluding Qwen3 Max, the average mean MAE falls to 4.50 × 10<sup>2</sup>.

• Strategy 3: Average Executable Passes = 3.38 and average mean MAE = 4.20 × 10<sup>4</sup>. Excluding Qwen3 Max, the average mean MAE drops to 1.81 × 10<sup>4</sup>.

These results are unsurprising; Strategy 1 is the easiest to solve numerically and consistently, with each subsequent strategy becoming harder to solve accurately and reliably.

## 5.3 OVERALL MODEL COMPARISON

Table 4 presents overall metrics averaged across all three strategies, again sorted from best to worst by mean MAE.

![](images/96dc986f8bb1186527f4cbd811af94b8c7cf431378ae9bcb4156bb8b68d4f1aa.jpg)  
Table 4: Overall MARKET-BENCH performance across all three strategies.

These overall results highlight several themes:

• Reliability vs. accuracy. Qwen3 Max achieves perfect overall Executable Passes (15), but its overall mean MAE is enormous (≈ 1.59 × 10<sup>8</sup>) due to extreme divergence on Strategy 2. In contrast, Grok 4 achieves the lowest overall mean MAE (443.24) despite not solving all rounds, and GPT-5.2 combines perfect executability with low mean MAE of 969.39.

• Inconsistency. Cohere Command-A, Amazon Nova Premier, and Nvidia Nemotron frequently fail to produce executable backtests on the harder strategies, leading to low overall Executable Passes even when their MAE on the few solved rounds is not uniformly bad. Furthermore, almost every model showed large variations within the rounds themselves.

## 6 DISCUSSION AND FAILURE MODES

## 6.1 STRUCTURAL VS. SEMANTIC FAILURES

The logs reveal two different types of failures:

Structural failures. These occur when the model-generated output cannot be executed to produce valid, comparable results.

• Incorrect or missing function signatures,

• Invalid references to columns or fields in the market data,

• Inconsistent types in intermediate calculations.

Semantic failures. These occur when the backtest output by the model runs but does not faithfully implement the intended logic. The resulting MAE is large even though the backtester outputs metrics. For example:

• Miscomputing spreads or z-scores in Strategy 2 (for example, wrong hedge ratios between COKE and PEPSI or using wrong rolling windows),

• Processing the options delta stream or hedge timing in Strategy 3 incorrectly, or interpreting delta signs incorrectly,

• Ignoring capital constraints or misapplying FIFO lot accounting in Strategy 1.

Models that are consistent but logically unsound tend to show high Executable Passes with large mean MAE, as seen with Qwen3 Max, Mistral-Large-2512, and, to a smaller extent, DeepSeek V3.2.

## 6.2 IMPLICATIONS FOR REAL-WORLD USE

Even for introductory tasks, MARKET-BENCH shows that:

• High success rates in model output do not guarantee accuracy.

• Multi-asset interactions and hedging risk expose nontrivial weaknesses in the reasoning and understanding of large language models in the trading field.

• There is large variance in the outputs of the same model across different rounds, as the best-run MAE can differ substantially from the mean MAE for each strategy–model pair.

• Current models can only be used as a coding supplement instead of synthesizing trading ideas and strategies.

Currently, large language models struggle with understanding and implementing even basic quantitative trading strategies. Using model output as a drop-in replacement for the work of quants would be extremely risky. In the future, with better training and reasoning from trading data, there may be a path for models to become more useful.

## 7 LIMITATIONS AND FUTURE WORK

Scope of strategies. MARKET-BENCH currently includes only three strategies, each focusing on a different aspect of market dynamics. The benchmark does not yet cover options pricing, multi-asset portfolios beyond pairs, intraday inventory risk limits, or transaction-cost-sensitive execution tactics.

Metric scaling. Our evaluation uses unnormalized MAE on absolute metrics, which can produce very large values for some strategies. While this reflects genuine numerical divergence, it complicates cross-strategy comparisons. Future work could incorporate relative errors, correlations of P&L paths, or risk-adjusted performance metrics to provide additional information and evaluation.

Strategy explanation. In the future, we hope large language models can be applied in the trading industry to identify drawbacks in strategies and pinpoint why a strategy is losing or gaining on certain trades. However, this would require the model to understand and be able to apply the strategy itself.

## 8 CONCLUSION

We present MARKET-BENCH, a benchmark for evaluating large language models on introductory quantitative trading tasks that require both accuracy and consistency. By analyzing 329 total attempts across three unique trading strategies, we find that:

• Current models lack the capabilities to simulate and understand even basic trading strategies.

• Many models can reliably produce executable backtests on simpler strategies, but a subset fail catastrophically on more complex ones.

• Model error varies widely, especially on the most realistic Strategy 3, where small implementation differences can generate huge P&L and risk discrepancies.

We hope MARKET-BENCH can serve as a foundation for future work on large language models that are not just capable of describing strategies but also implementing them in a way that demonstrates deep understanding of market dynamics, risk, and trading mechanics.

## REFERENCES

Jacob Austin et al. Program synthesis with large language models. arXiv preprint arXiv:2108.07732, 2021. URL https://arxiv.org/abs/2108.07732.

Mark Chen et al. Evaluating large language models trained on code. arXiv preprint arXiv:2107.03374, 2021. URL https://arxiv.org/abs/2107.03374.

Databento Inc. Databento US equities. https://databento.com/portal/catalog/ us-equities, 2025.

Shaoyu Dou et al. FinEval-KR: A financial domain evaluation framework for large language models’ knowledge and reasoning. arXiv preprint arXiv:2506.21591, 2025. URL https: //arxiv.org/abs/2506.21591.

Carlos E. Jimenez, John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press, and Karthik Narasimhan. SWE-bench: Can language models resolve real-world GitHub issues?, 2024. URL https://arxiv.org/abs/2310.06770.

Zheng Lai et al. DS-1000: A natural and reliable benchmark for data science code generation. arXiv preprint arXiv:2211.11501, 2022. URL https://arxiv.org/abs/2211.11501.

Guilong Lu et al. BizFinBench: A business-driven real-world financial benchmark for evaluating LLMs. arXiv preprint arXiv:2505.19457, 2025. URL https://arxiv.org/abs/2505. 19457.

Spencer Mateega, Carlos Georgescu, and Danny Tang. FinanceQA: A benchmark for evaluating financial analysis capabilities of large language models, 2025. URL https://arxiv.org/ abs/2501.18062.

Ying Nie et al. CFinBench: A comprehensive chinese financial benchmark for large language models. arXiv preprint arXiv:2407.02301, 2024. URL https://arxiv.org/abs/2407.02301.

Shijie Wu et al. Bloomberggpt: A large language model for finance. arXiv preprint arXiv:2303.17564, 2023. URL https://arxiv.org/abs/2303.17564.

Qianqian Xie et al. PIXIU: A large language model, instruction data and evaluation benchmark for finance. arXiv preprint arXiv:2306.05443, 2023. URL https://arxiv.org/abs/2306. 05443.

Qianqian Xie et al. FinBen: A holistic financial benchmark for large language models. In Advances in Neural Information Processing Systems 37 (Datasets and Benchmarks Track), 2024a. URL https://arxiv.org/abs/2402.12659.

Qianqian Xie et al. Open-FinLLMs: Open multimodal large language models for financial applications. arXiv preprint arXiv:2408.11878, 2024b. URL https://arxiv.org/abs/2408. 11878.

Hongyang Yang, Xiao-Yang Liu, and Christina Dan Wang. FinGPT: Open-source financial large language models. FinLLM Symposium at IJCAI 2023, 2023. URL https://arxiv.org/ abs/2306.06031.