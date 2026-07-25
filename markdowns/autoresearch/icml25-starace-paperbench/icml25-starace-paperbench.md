# PaperBench: Evaluating AI’s Ability to Replicate AI Research

Giulio Starace 1 \* Oliver Jaffe 1 \* Dane Sherburn 1 \* James Aung 1 \* Chan Jun Shern 1 \* Leon Maksin 1 \* Rachel Dias 1 \* Evan Mays 1 Benjamin Kinsella 1 Wyatt Thompson 1 Johannes Heidecke 1 Amelia Glaese 1 Tejal Patwardhan

## Abstract

We introduce PaperBench, a benchmark evaluating the ability of AI agents to replicate stateof-the-art AI research. Agents must replicate 20 ICML 2024 Spotlight and Oral papers from scratch, including understanding paper contributions, developing a codebase, and successfully executing experiments. For objective evaluation, we develop rubrics that hierarchically decompose each replication task into smaller subtasks with clear grading criteria. In total, Paper-Bench contains 8,316 individually gradable tasks. Rubrics are co-developed with the author(s) of each ICML paper for accuracy and realism. To enable scalable evaluation, we also develop an LLMbased judge to automatically grade replication attempts against rubrics, and assess our judge’s performance by creating a separate benchmark for judges. We evaluate several frontier models on PaperBench, finding that the best-performing tested agent, Claude 3.5 Sonnet (New) with open-source scaffolding, achieves an average replication score of 21.0%. Finally, we recruit top ML PhDs to attempt a subset of PaperBench, finding that models do not yet outperform the human baseline. We open-source our code to facilitate future research in understanding the AI engineering capabilities of AI agents.

## 1. Introduction

We introduce PaperBench, a benchmark evaluating the ability of AI agents to replicate state-of-the-art AI research. AI agents that can autonomously replicate ML research papers could accelerate machine learning progress, a prospect that is exciting but also warrants careful study to ensure AI capabilities are developed safely. PaperBench can be used as a measure of model autonomy in OpenAI’s Preparedness Framework (OpenAI, 2023), autonomous capabilities in Anthropic’s Responsible Scaling Policy (Anthropic, 2024), and ML R&D in Google DeepMind’s Frontier Safety Framework (Google DeepMind, 2024).

Our setup considers AI agents with the ability to write and execute code autonomously. For each ML research paper in our benchmark, we present the agent with the paper content and ask it to replicate the paper’s empirical contributions. Complete replication involves understanding the paper, developing a codebase from scratch to implement all experiments, and running, monitoring, and troubleshooting these experiments as needed. In general, each replication task is highly challenging and takes human experts several days of work at a minimum.

Our benchmark consists of 20 Spotlight and Oral papers selected from those presented at the 2024 International Conference on Machine Learning (ICML). These papers span 12 different ICML topics, including deep reinforcement learning, robustness, and probabilistic methods. Each paper is accompanied by a manually created rubric, which specifies all the necessary outcomes for replicating the paper in detail; resulting in a total of 8,316 individually gradable outcomes across 20 papers. Each of the rubrics in PaperBench has been co-developed with one of the original authors of the paper to ensure that it is high quality and accurate in assessing replication. Rubrics are constructed in a hierarchical manner, such that outcomes can be decomposed into finegrained sub-outcomes, allowing granular measurement of partial progress towards replicating papers.

Given the complexity of ML research papers, we found that even grading a single replication attempt can take tens of hours for a human expert. To streamline the grading process, we explore LLM-based judges and introduce an auxiliary evaluation, JudgeEval, which compares the outputs of automated judges against a dataset of gold labels from human expert judges. Our best LLM-based judge, which uses o3-mini-high with custom scaffolding, achieves an F1 score of 0.83 on the auxiliary evaluation, suggesting that this judge is a reasonable stand-in for a human judge.

![](images/d43c9d5244a15e1b59b93073f64dedb570ba3a419b8ad2065a6ed23cac4b3e4b.jpg)  
Figure 1. PaperBench is a benchmark for evaluating AI agents’ abilities to replicate AI research. Each sample includes a research paper and a grading rubric that specifies the assessment criteria for a complete replication. Agents create a codebase from scratch as their submission (1), which is then executed to verify result reproduction (2) and graded against the rubric by an LLM-based judge (3).

We find that agents exhibit non-trivial capabilities in replicating ML research papers. Anthropic’s Claude 3.5 Sonnet (New) with a simple agentic scaffold achieves a score of 21.0% on PaperBench. On a 3-paper subset, our human baseline of ML PhDs (best of 3 attempts) achieved 41.4% after 48 hours of effort, compared to 26.6% achieved by o1 on the same subset. We further release a variant of Paper-Bench called PaperBench Code-Dev for more lightweight evaluation. On this variant, o1 achieves a score of 43.4%.

## Our contributions include:

• PaperBench: a benchmark of 20 ML research papers and author-approved rubrics, and an automated grading workflow using LLM-based judges.

• PaperBench Code-Dev: a more lightweight variant of the benchmark which relaxes some requirements of PaperBench to make setup and evaluation more accessible to the broader community.

• JudgeEval: a dataset of human-graded submissions, which can be used as an auxiliary evaluation for the development and assessment of automated judges.

• Evaluations of frontier models on PaperBench: an assessment of several frontier AI agents’ abilities to conduct long-horizon tasks and ML R&D.

## 2. PaperBench

In this section, we describe the overall flow of PaperBench.   
See Figure 1 for a visual overview.

## 2.1. Task

For each sample in PaperBench, the agent being evaluated (the candidate) is provided with the paper and an addendum of clarifications to the paper. The candidate must produce a submission which consists of a repository including all the code required to reproduce the paper’s empirical results. This repository must include a reproduce.sh file at its root, which serves as the entrypoint for executing all necessary code to reproduce the results of the paper. A submission successfully replicates the paper if its reproduce.sh reproduces the empirical results reported in the paper.

Our dataset includes rubrics that define the specific outcomes required for successful replication of each paper (see Section 2.3 on how they are used for grading and Section 3.1 on their overall design). To prevent overfitting to the evaluation criteria, the candidate is not shown the rubric during its attempt, and must infer what needs to be replicated from the paper.

Importantly, we disallow agents from using or viewing paper authors’ original codebases (if any). This ensures that we are measuring agents’ abilities to code and execute complex experiments from scratch rather than the ability to use existing research code, which has been covered in prior work (Siegel et al., 2024).

![](images/6a9f1aa01cbab6b361e649b33fac37329f03e41b3bbf236cf14e185a3b4958d6.jpg)  
Figure 2. Rubrics hierarchically decompose the replication task into a tree of increasingly granular requirements. Leaf nodes are graded for binary pass/fail criteria, and a parent’s score is the weighted average of its children. In the example above, the final Replication Score is 55%.

## 2.2. Reproduction

A submission is only considered to have replicated a result when that result is reproduced by running the submission in a fresh setup. To that end, we include a reproduction phase before grading.

When the candidate’s task attempt ends, we copy its submission to a fresh VM running an Ubuntu 24.04 image with access to an A10 GPU. We execute the submission’s reproduction script to generate results from a clean start.1 This execution generates any files (e.g. results and plots) output by the reproduction process, and also produces a reproduce.log file as a side-effect. We refer to the resulting updated submission folder as the executed submission.

By designing the reproduction step to occur separately from a candidate’s run, we increase the credibility of the replication and ensure replication outputs can be distinguished from any results hard-coded by the candidate at task-time.

## 2.3. Grading

Each paper in our benchmark has an accompanying rubric that specifies the assessment criteria for complete paper replication.

A rubric is organized as a tree of requirements, with each leaf node specifying a single clear criterion to pass or fail (see Figure 2), and where each node has been manually weighted for its importance relative to its siblings. We explain the design of rubrics in Section 3.1. Given a leaf criterion, the judge evaluates whether the submission meets its requirements, assigning a binary score of 1 if yes and 0 otherwise.

Once all leaf nodes have been graded, parent nodes are given a score equal to the weighted average of their children’s scores. This propagates all the way up to the root of the tree, and the root-level score is taken as the final Replication Score of the submission.

In other words, each submission is scored in terms of a weight-adjusted proportion of all satisfied rubric requirements, where 100% corresponds to a perfect replication with all leaf node requirements satisfied.

Our main metric is the average Replication Score across all papers.

## 2.4. Requirement Types

Each leaf node has one of three possible requirement types, which determines how it is graded.

1. Result Match leaf nodes assess whether the executed submission contains evidence of replicating a particular result from the paper. Result Match nodes are graded by looking at reproduce.sh and reproduce.log, and any files created or modified in the reproduction step.2

2. Execution leaf nodes assess whether some particular execution result has occurred when running the reproduce.sh script. Given that Result Match nodes are particularly challenging to achieve, having multiple associated Execution nodes allow submissions to receive credit for marking partial progress towards a result even if the corresponding Result Match node isn’t achieved. Execution nodes are assessed by looking at the reproduce.sh, the reproduce.log, and the source code.3

3. Code Development leaf nodes assess whether the candidate’s source code appears to contain a correct implementation of some requirement. Code Development nodes award partial credit towards the achievement of Execution nodes; for example, a submission may have written correct code but failed to execute it correctly in the reproduce.sh.4

It would be possible to have a rubric solely consisting of Result Match nodes, since matching results replicates the paper by definition. However, we include Execution and Code Development nodes to award partial credit towards achieving results, thus ensuring that agent performance on PaperBench improves incrementally.

Conversely, it is conceivable to create a rubric that solely consists of Code Development nodes, since a truly correct implementation of all necessary code entails that when the code is run, the code executes correctly and the expected results are achieved. However, it is in practice infeasible to fully determine the correctness of code without running it. Hence, for practical purposes, it is better to also separately assess whether the code executes and results match to have a more holistic and robust assessment of a submission.

We summarize which files are shown to the judge for each requirement type in Table 1. Submissions without a reproduce.sh score 0 on all Execution and Result Match nodes.

Table 1. Leaf nodes can either be Code Development, Execution or Result Match, which determines which files are shown to the judge when grading on that leaf node.  
![](images/ec51e0fa1db7640bed6103a2baa46723944436d9c9403430259073e43a9a9d49.jpg)

## 2.5. Rules

PaperBench is designed to be agnostic to agent scaffolds, so we do not have specific requirements for the agent’s environment. However, the benchmark does have rules to ensure a fair comparison:

1. The agent can browse the internet, but may not use resources from websites in our provided per-paper blacklists. The blacklist for each paper includes the authors’ own code repository and any other online replications.

2. The resources available to the agent, such as runtime and compute, are not restricted in any way. However, we encourage researchers to report their setups in their results.

3. Developers should provide agents with API keys for necessary online services (e.g. HuggingFace credentials to download datasets). Obtaining access to online accounts is not part of the skillset we intend to assess with PaperBench.

For our experiments, we build a simple post-hoc monitor that checks for occurrences of blacklisted URLs in agent logs, which we escalate to manual review to disqualify any submissions that use blacklisted resources. See Appendix E for more details on our monitor. We find 10 cases of using blacklisted resources across all 646 runs we conducted for our results, and disqualify these submissions by setting their score to 0.

## 2.6. PaperBench Code-Dev

Running a full evaluation on PaperBench is expensive in terms of agent model inference as well as the compute environment provided to agents. For broader accessibility, we release a simplified version of PaperBench, which we call PaperBench Code-Dev. PaperBench Code-Dev reduces the evaluation task to only code development, skipping the focus on executing the code to verify that results are reproduced. During evaluation, we skip the reproduction step and the judge only grades “Code Development” nodes in the rubrics.

This waives the need for expensive GPU hardware typically required to run agent rollouts and the reproduction step in PaperBench. Furthermore, with o3-mini as the judge, we find the cost of grading to be reduced by about 85%.

PaperBench Code-Dev offers a more accessible, but less robust, assessment of agents’ paper replication abilities. We find performance on PaperBench Code-Dev to be weakly correlated with performance on the full PaperBench eval.5 We expect PaperBench Code-Dev to be useful as a preliminary noisy indication of performance on PaperBench.

## 3. Dataset

PaperBench consists of 20 machine learning papers, listed in Table 8. To ensure that our benchmark consists of papers that are representative of contemporary AI research, we consider all Spotlight and Oral papers from ICML 2024, and further curate for suitability based on the criteria described in Appendix B. We release a further 3 papers (one from ICML and two from NeurIPS 2024 Workshops) as a development set and maintain a held-out set for internal use.

## 3.1. Rubrics

Constructing the rubrics for each paper was notably the most time-intensive aspect of developing PaperBench. Each rubric was written in collaboration with one of the original authors of each paper, and took multiple weeks per paper to go from paper reading, initial creation, rubric review, iteration, and final sign-off. We elaborate on the rubric creation process in Appendix C.

Each rubric is structured as a tree which hierarchically decomposes the main outcomes required to replicate a given paper. For example, the root node begins with the highestlevel outcome expected, e.g. “The core contributions of the paper have been reproduced.” The first-level decomposition might introduce a node for each of the core contributions. The children of each of those nodes would go into finer detail about specific outcomes, e.g. “gpt2-xl has been finetuned on the dataset, using the hyperparameters in Section B.1.”. Importantly, satisfying all children of a node indicates that the parent has also been fulfilled, such that it is sufficient to grade all of the leaf nodes of the tree to comprehensively assess overall success.

Leaf nodes have precise and granular requirements. Having many granular requirements enables us to score partial attempts and makes grading individual nodes easier for the judge. We continuously decompose nodes until the requirement they represent is granular enough such that we estimate that an expert human could review whether a submission satisfies it in less than 15 minutes (assuming familiarity with the paper). Across the 20 papers in PaperBench there are 8,316 leaf nodes. Table 8 shows the total number of nodes in each rubric; see Table 9 in the Appendix for a further breakdown of node types.

All rubric nodes are also weighted; the weight of each node indicates the importance of that contribution relative to its siblings, and not necessarily the node’s implementation difficulty. Weighting nodes rewards prioritizing more important parts of the paper when replicating.

## 3.2. Dealing with Underspecification

We manually create an addendum for each paper containing clarifications from the paper’s original authors. The addendums also clarify when parts of the paper are out of scope. Where necessary, we also create a judge-only addendum, containing reference information to help it grade submissions more accurately.

## 4. LLM Judge

In preliminary experiments, we found that manual grading using expert humans took on the order of tens of hours per paper, so having an automated way to perform the evaluation is necessary for the practical application of PaperBench.

To enable scaled evaluation of PaperBench submissions, we develop a simple LLM-based judge (SimpleJudge). Then, we create an auxiliary evaluation, JudgeEval, to evaluate the performance of our judge and future judges.

Importantly, we expect the quality of automated judges to improve over time, allowing the reliability of the scores reported on our benchmark to improve over time as well.

## 4.1. SimpleJudge Implementation

Given a submission, our judge independently grades each leaf node in a rubric. For a specific leaf node, the judge is prompted with the Markdown of the paper, the full rubric JSON, the leaf node’s requirement, and the submission.

As the full submission is often too long to fit entirely within a model’s context, we filter the codebase by having the judge rank the files by relevance and only include the top ten files in its context. We then prompt our judge to assess whether the requirement of the leaf node has been fulfilled.

Unless otherwise stated, we use OpenAI’s o3-mini,6 as the backend model for the judge. We estimate our judge with o3-mini costs around \$66 USD in OpenAI API credits7 to grade a single submission. For PaperBench Code-Dev, the cost drops to around \$10 USD per paper. Our LLM-judge is significantly cheaper and faster than hiring an expert human for grading (See Fig. 5).

We refer to our judge implementation as “SimpleJudge”.   
See Appendix D for further details on our implementation.

## 4.2. Evaluating Judges with JudgeEval

We introduce JudgeEval, a benchmark for evaluating the accuracy of automated judges in the context of PaperBench.

To construct JudgeEval, we use partial replications of four papers from the PaperBench dataset and one from the PaperBench development set. These replications were created either from scratch or by modifying the original author’s codebases.8 We manually grade each replication attempt against the corresponding paper’s rubric and treat these human-graded leaf nodes as ground truth labels when evaluating automated judges.

Since grading each leaf node is a binary classification task, we evaluate JudgeEval using standard binary classification metrics.

Table 2. Macro-averaged metrics of GPT-4o, o1-mini, o1, and o3- mini with our judge scaffolding on JudgeEval. o-series models use the reasoning effort = high. We accompany the performance with the average cost per paper in USD. We report F1 score stratified by requirement type in Appendix G.  
![](images/f42294f07a8708e7fb1f0e1eedac579ad5f9b1ec360acb105391a84e84fadf08.jpg)

We evaluate GPT-4o-mini, GPT-4o, o1-mini, o1, and o3- mini as judge models on JudgeEval, using macro-averaging to aggregate performance across papers. The results, shown in Table 2, indicate that o3-mini with the SimpleJudge scaffolding is the most cost-effective, with an F1 score of 0.83 at \$66 USD per paper. This is the setup we use as our judge for the main results.

## 5. Experiments and Results

## 5.1. Agent and Execution Environment

In our experiments, we run each agent in an Ubuntu 24.04 Docker container that has access to a single A10 GPU. The agent’s local work directory contains the paper in PDF and Markdown format, the paper’s addendum, and a text file containing instructions (see Figure 13 for the instructions).

The container has access to the internet so that the agent can download packages and browse the web as needed. We provide the agent with an API key for HuggingFace and the OpenAI API with \$1000 loaded so it can make use of those services during its run (e.g, if a paper involves running experiments using the OpenAI finetuning API).

We use a simple agent scaffolding based on Inspect AI’s basic agent,9 which we call BasicAgent, and use nanoeval for orchestration. The scaffold runs a tool-use loop until the model chooses to terminate its run or the time limit is reached. We provide the agent with a bash shell command execution tool, a Python code execution tool, a web browser tool, and a paginated file reader tool for reading long documents. See Appendix F for more details on agent scaffolding.

## 5.2. Main Experiment

We evaluate GPT-4o,10 o1,11 o3-mini,12 DeepSeek-R1,13 Claude 3.5 Sonnet (New),14 and Gemini 2.0 Flash15 on all 20 papers for 3 runs per paper. We wished to also evaluate Claude 3.7 Sonnet, but were unable to complete the experiments given rate limits with the Anthropic API. We give agents a maximum run-time of 12 hours.16

See Table 3 for the average Replication Score of each model. We observe promising performance from Claude 3.5 Sonnet which scores 21.0%. OpenAI o1 performs weaker, with a score of 13.2%. Our other tested models performed poorly, with scores under 10%.

We manually inspected several of the agent logs to understand agent performance better. We observed that all models apart from Claude 3.5 Sonnet frequently finished early, claiming that they either had finished the entire replication or had faced a problem they couldn’t solve. All agents failed to strategize about how best to replicate the paper given the limited time available to them. We observed that o3-mini frequently struggled with tool usage.

These failure modes suggest a weakness of current models in being able to conduct long-horizon tasks; despite showing ample abilities in formulating and writing multi-step plans, models fail to actually take series of actions that execute that plan.

We believe that further work on agentic scaffolds would lead to better results on PaperBench. In our work, we focus on introducing the PaperBench benchmark and present our agents’ results on the benchmark merely as an initial baseline. We do not believe that present results represent the upper limit of these models’ capabilities.

Table 3. Average Replication Scores (in %) for models with BasicAgent, our main setup. Error is one standard error of the mean.  
![](images/19342438dd32e7100c23eba9b1d890a2db76bd8b6ca12b61793767e315546364.jpg)

![](images/90187af7a71a7867a775759428b42ac6f5d86fd91b851659fd8ce2e17d7b112f.jpg)  
Figure 3. Comparing human versus agent performance on a 4-paper subset of PaperBench. o1 initially outperforms the human baseline but plateaus after the first hour, leading it to fall behind the humans by the end. Note that the human attempt for test-time-model-adaptation ends at the 24 hour mark and is thus excluded from the ‘3-paper subset’ discussed elsewhere in the paper. Error bars on model performance is SEM over 3 repeats.

Table 4. Average Replication Scores (in %) with IterativeAgent. IterativeAgent removes the ability of models to end the task early and prompts models to work in a piecemeal fashion. We observe that these modifications significantly boost scores for o3-mini and o1 compared to BasicAgent, but hamper Claude 3.5 Sonnet, highlighting models’ sensitivities to prompting.  
![](images/35d0e00e8bc687c0531b43b089ebeb892176ae6b9c9c7e9eaa6c967c597ddfef.jpg)

Table 5. Average Replication Scores (%) on PaperBench Code-Dev for o1 using IterativeAgent. Error is one standard error of the mean.  
![](images/b2d8bd7c75781c261eb5baed613a8eb8e0a21d5d19df7599b5c5bd02f7fa0304.jpg)

## 5.3. IterativeAgent

Given that models tend to fail to use the full time available to them, we test a variant of BasicAgent which forces the agent to run for its full available time by removing its ability to end the task early, and uses prompts tuned to encourage the model to work in a piecemeal fashion. We call this agent IterativeAgent. See Appendix F.2 for details on the prompts used.

We test o1, o3-mini, and Claude 3.5 Sonnet with Itera-

tiveAgent. See Table 4 for results.

We see a significant uplift in scores from o1 and o3-mini with IterativeAgent. We note that Claude 3.5 Sonnet outperforms o1 with BasicAgent but underperforms o1 with IterativeAgent. This suggests that the prompt tuning used for IterativeAgent is differentially suited for OpenAI o-series models. We suspect that a modification to BasicAgent that also prevents it from ending the task early could lead to Claude 3.5 Sonnet outperforming o1 with IterativeAgent.

## 5.4. Human Baseline Performance

We recruit 8 participants who are currently enrolled in or have completed a PhD in machine learning17 to create a human baseline.

Our setup aims to establish a human baseline on a subset of 4 papers: We collect 3 independent replication attempts per paper, assigning participants to papers they were most confident about replicating. The 3 independent attempts per paper allow us to track the best@3 attempt and use that as an “expert” score.

We evaluate participants under similar conditions to our AI agents. We give participants the paper in PDF and Markdown format, along with the paper’s addendum and instructions that are as close as possible to those used with AI agents.18 Participants have access to a single NVIDIA A10 GPU.19 We do not place restrictions on how participants work – for example, they are free to use AI assistants such as ChatGPT and GitHub Copilot – except that they may not consult any websites in the paper’s blacklist (as per the PaperBench rules).

Participants worked part-time and had a four-week window to make as much progress as possible. We evaluate attempts after one week of progress and only extend the best performer of the 3 for the remaining weeks. Active work time is tracked via a timesheet; if a participant’s machine runs experiments unattended (e.g., overnight), that time is included in the total work hours. We use these tracked hours to obtain and grade submission snapshots at various timestamps.

We conduct an extended run of o1 with IterativeAgent for 36 hours, saving hourly snapshots, and grade those taken at 1, 3, 6, 12, and 36 hours.

We compare this extended 36 hour run of o1 with human performance over time in Figure 3. We observe that o1 initially outperforms the human baseline during the early stages of the replication attempt, but humans start outperforming the AI agent after 24 hours. This trend of agents initially outperforming humans but falling behind at longer time horizons is consistent with previous results Wijk et al. (2024). Notably, o1’s scores mostly plateau after the first hour, suggesting that the model is proficient at writing a lot of code quickly at the beginning of the attempt, but fails to effectively work beyond this time horizon to strategize how to improve its submission. Human scores are slow to rise in the initial hours, perhaps as humans spend time digesting the paper.

## 6. Related Work

In this section, we survey related work for evaluating AI agents on ML research and engineering. For a bigger-picture discussion on how rubric-based evaluation compares to other forms of evaluation and oversight, please see Appendix A.

Evaluating ML Engineering and Research CORE-Bench (Siegel et al., 2024) tasks agents to reproduce specific results from a research paper given its repository. In a similar fashion, (Bogin et al., 2024) provides agents with repositories and tasks them to achieve particular results using the codebase. In contrast, PaperBench tasks agents to replicate the results of a research paper from scratch. (Liang et al., 2024) assess whether GPT-4 can generate code for seven empirical software engineering papers by manually reviewing the correctness of the code with human experts against a rubric. In contrast, PaperBench fully specifies the grading criteria for a successful reproduction through its rubrics, enabling automatic grading via llm-as-a-judge.

MLE-bench (Chan et al., 2024), MLAgentBench (Huang et al., 2024), and DSBench (Jing et al., 2024) evaluate agents on Kaggle competitions. Many Kaggle competitions are dated and relatively simple ML challenges, whereas PaperBench only contains tasks relevant to modern machine learning research.

RE-Bench (Wijk et al., 2024) proposes 7 challenging openended ML research engineering tasks for agents to solve. We expect PaperBench to cover a broader range of sub-tasks over a longer horizon of work compared to the more selfcontained tasks proposed in RE-Bench. Additionally, RE-Bench provides agents with a “scoring function” on most tasks to provide a perfect measure of an agents’ performance on the current task; in PaperBench, we are interested in measuring agents’ ability to perform and connect a broad scope of ML research work, where such scoring functions cannot viably capture the full scope of tasks.

Recent work has found that LLMs can generate research ideas of equivalent novelty to human PhDs within specific domains (Si et al., 2024), and solve some toy research problems, involving forming hypotheses, designing and running experiments, and analyzing results (Jansen et al., 2024; Wang et al., 2022).

Automatic judging LLMs have previously been proposed to act as judges to evaluate submissions for tasks (Zheng et al., 2023; Chen et al., 2024; Fu et al., 2023). Agent-based judges have been found to be more accurate than non-agent LLM judges on certain tasks (Zhuge et al., 2024). We benchmark the judging capability of models on significantly harder tasks than what has been used before.

## 7. Limitations

Dataset Size PaperBench currently consists of only 20 papers, and ideally would capture an even larger portion of the ML research community’s output. However, focusing on the number of papers can be misleading: Since each rubric is composed of hundreds of nodes, PaperBench evaluates agents on thousands of different individual requirements.

Contamination For almost all the papers in our benchmark, the original authors’ codebase for the paper exists online. In our experience, these codebases often do not replicate the entire paper and do not conform to the specific format required for PaperBench submissions (e.g., reproduce.sh should exist which executes the code). Nevertheless, models that are pre-trained on large corpuses may have internalized solutions, resulting in inflated performance on this benchmark. While present-day models are most likely not affected by this issue given the recency of the papers in the dataset, this may become an issue for future models.

Challenging dataset creation Producing these detailed rubrics is extremely labor-intensive, each requiring an expert human several full days to create. It requires the creator of the rubric to deeply understand the paper, and each rubric must be carefully written to avoid inaccurate requirements to ensure accurate evaluation. We found it to be challenging to train others to create rubrics at our desired quality level. This poses a challenge for others to replicate the process we undertook to create the dataset. Future work may wish to examine more streamlined approaches to rubric generation, such as with model assistance.

LLM-based judge performance Despite our judge demonstrating good performance in our JudgeEval, it is not as accurate as an expert human judging submissions. Furthermore, our judge is not deterministic due to using non-deterministic model calls. We are excited to see further work in automated judges for complex tasks, as well as future work stress-testing judges via e.g. adversarial submissions. For a broader discussion on complex task evaluation and future advances that will be needed, see Appendix A.

Cost We estimate that on average it costs \$400 in API credits to run an o1 IterativeAgent 12-hour rollout on a single paper in PaperBench. For the 20 papers, this sums to \$8000 USD per eval run. Grading costs an additional \$66 USD per paper on average with o3-mini SimpleJudge. We purposely designed PaperBench Code-Dev (PBCD) not only to eliminate the GPU requirement, but also to address the issue of cost. We expect that PBCD rollouts can be made to run for half the duration of PaperBench roll-outs, due to the lack of execution, which would lead to a cost of \$4000 USD per eval run. The plateauing observed suggests that the rollouts may be shortened even further, further reducing costs. We also find that for PBCD, grading costs are reduced to \$10 per paper on average. Finally, we release work on an experimental version of SimpleJudge, with preliminary results showing a 10x decrease in grading costs (See Appendix H).

## 8. Conclusion

We introduce PaperBench as a challenging benchmark for assessing AI agents’ abilities to replicate cutting-edge machine learning research. Each included paper represents exciting work in a contemporary domain of interest – such as reinforcement learning, robustness, and probabilistic methods – and is evaluated against a rigorous rubric co-developed with the original authors. By requiring AI agents to build entire codebases from scratch, conduct complex experiments, and generate final results, PaperBench offers a demanding real-world test of ML R&D capabilities.

Our experiments with several frontier models suggest that while current AI systems show some capacity to replicate certain facets of machine learning papers, they are still far from competently performing the full range of tasks required for a successful replication. Our strongest evaluated agent in our main setup – Claude 3.5 Sonnet (New) – achieved an average Replication Score of only 21.0%, highlighting both the complexity of ML research tasks and the limitations of current AI agents to conduct complex long-horizon tasks. Nevertheless, these early results underscore nontrivial progress: AI agents succeed in implementing and validating various methods, suggesting promise for future improvements.

By open-sourcing PaperBench, we aim to contribute to evaluating, monitoring, and forecasting the capabilities of AI systems to conduct AI R&D of their own. While our benchmark does not capture every aspect of real-world research, we believe it marks a substantive step towards rigorous evaluation of AI autonomy in ML research.

## Impact Statement

As AI systems progress toward autonomously conducting complex ML research, they offer promise for accelerating scientific discovery in multiple fields. As one pertinent example, AI-driven ML research could significantly accelerate AI safety and alignment research efforts. Being able to replicate cutting-edge ML research from scratch is indicative of an AI system’s autonomy and ML expertise, suggesting that a model capable of high performance on PaperBench would have a non-trivial capacity to tackle real-world, open-ended ML research tasks.

However, the capability to autonomously replicate and extend frontier research can also lead to rapid innovation that outpaces our ability to fully understand its implications. If powerful models can not only replicate state-of-the-art techniques but also iteratively refine and improve them, they might accelerate the development of increasingly capable systems at a pace that poses heightened risks. We may see models introduced with minimal time for thorough risk assessment, governance measures, or safety and alignment interventions, potentially leading to hazardous or destabilizing outcomes.

By open-sourcing PaperBench, we aim to provide a method to measure these emerging autonomous R&D capabilities of frontier AI systems. We acknowledge that PaperBench represents just one piece of a broader evaluation landscape for autonomous AI R&D. We encourage future work in anticipating and preparing for the powerful impacts that AI systems with greater autonomy may eventually unlock.

## Acknowledgements

We express our sincere gratitude to Arvind Ramaswami and Francisco Garcia for their contributions to the creation of the PaperBench dataset.

We would also like to thank the authors of the papers included in PaperBench for working closely with us to validate each rubric: Alexander Spangher, Ananye Agarwal, Andrew Lee, Bartłomiej Cupiał, Bowen Zhao, Chang Xu, Christian Schlarmann, Diana Cai, Dong Gong, Feng Liu, Haotian Sun, Jia Shi, Kevin Frans, Louis Sharrock, Manuel Gloeckler, Michael Samuel Albergo, Pratik Rathore, Shuaicheng Niu, Tim Knappe, Tongliang Liu, Xinyu Xing, and Xisen Jin. Their willingness to clarify methodologies, share additional materials, and support the rubric-writing process was invaluable in creating comprehensive and accurate rubrics for their work.

We also express our thanks to Amy Lu, Anit Kumar Sahu, Armin Wasicek, Brendan Rappazzo, Chun-Wei Chiang, David Khachaturov, Marc Harary, and Stephen Giguere who participated in the human baseline experiments.

Finally, we would like to thank Aparna Dutta, Jerry Tworek, Phoebe Thacker, Phillip Guo, Kevin Liu, Vichyr Pong, Mengyuan Yan and Yining Chen for their advice and collaboration.

## References

Albergo, M. S., Goldstein, M., Boffi, N. M., Ranganath, R., and Vanden-Eijnden, E. Stochastic Interpolants with Data-Dependent Couplings. June 2024. URL https: //openreview.net/forum?id=FFILRGD0jG.

Anthropic. Responsible Scaling Policy. https://www. anthropic.com/news/announcing-our-up dated-responsible-scaling-policy, 2024. Accessed: 2025-01-29.

Bogin, B., Yang, K., Gupta, S., Richardson, K., Bransom, E., Clark, P., Sabharwal, A., and Khot, T. SUPER: Evaluating Agents on Setting Up and Executing Tasks from Research Repositories, September 2024. URL http://arxiv. org/abs/2409.07440. arXiv:2409.07440 [cs].

Cai, C., Ye, Z., Feng, L., Qi, J., and Liu, F. Sample-specific Masks for Visual Reprogramming-based Prompting. June 2024a. URL https://openreview.net/forum ?id=4sikyurTLX.

Cai, D., Modi, C., Pillaud-Vivien, L., Margossian, C., Gower, R. M., Blei, D., and Saul, L. K. Batch and match: black-box variational inference with a score-based divergence. June 2024b. URL https://openreview.n et/forum?id=bplNmU2ROC.

Chan, J. S., Chowdhury, N., Jaffe, O., Aung, J., Sherburn, D., Mays, E., Starace, G., Liu, K., Maksin, L., Patwardhan, T., et al. MLE-bench: Evaluating machine learning agents on machine learning engineering. arXiv preprint arXiv:2410.07095, 2024.

Chen, D., Chen, R., Zhang, S., Liu, Y., Wang, Y., Zhou, H., Zhang, Q., Wan, Y., Zhou, P., and Sun, L. MLLM-as-a-Judge: Assessing Multimodal LLM-as-a-Judge with Vision-Language Benchmark. arXiv preprint arXiv:2402.04788, 2024.

Cheng, Z., Wu, X., Yu, J., Yang, S., Wang, G., and Xing, X. RICE: Breaking Through the Training Bottlenecks of Reinforcement Learning with Explanation.

Chiang, C.-H. and yi Lee, H. Can Large Language Models Be an Alternative to Human Evaluations?, 2023. URL https://arxiv.org/abs/2305.01937.

DeepMind. Specification Gaming: The Flip Side of AI Ingenuity, 2024. URL https://deepmind.google/ discover/blog/specification-gamingthe-flip-side-of-ai-ingenuity/. Accessed: 10 March 2025.

Frans, K., Park, S., Abbeel, P., and Levine, S. Unsupervised Zero-Shot Reinforcement Learning via Functional Reward Encodings. June 2024. URL https: //openreview.net/forum?id=a6wCNfIj8E.

Fu, J., Ng, S.-K., Jiang, Z., and Liu, P. GPTScore: Evaluate as You Desire. arXiv preprint arXiv:2302.04166, 2023.

Gloeckler, M., Deistler, M., Weilbach, C. D., Wood, F., and Macke, J. H. All-in-one simulation-based inference. June 2024. URL https://openreview.net/forum ?id=DL79HYCFFq.

Google DeepMind. Frontier Safety Framework, May 2024.

Harvey Team. Introducing BigLaw Bench, August 2024. URL https://www.harvey.ai/blog/intro ducing-biglaw-bench.

Huang, Q., Vora, J., Liang, P., and Leskovec, J. MLAgentBench: Evaluating Language Agents on Machine Learning Experimentation. In Forty-first International Conference on Machine Learning, 2024.

Jansen, P., Cotˆ e, M.-A., Khot, T., Bransom, E., Mishra, ´ B. D., Majumder, B. P., Tafjord, O., and Clark, P. DIS-COVERYWORLD: A Virtual Environment for Developing and Evaluating Automated Scientific Discovery Agents. arXiv preprint arXiv:2406.06769, 2024.

Jin, X. and Ren, X. What Will My Model Forget? Forecasting Forgotten Examples in Language Model Refinement. June 2024. URL https://openreview.net/for um?id=bzNwexOPWm.

Jing, L., Huang, Z., Wang, X., Yao, W., Yu, W., Ma, K., Zhang, H., Du, X., and Yu, D. DSBench: How Far Are Data Science Agents to Becoming Data Science Experts? arXiv preprint arXiv:2409.07703, 2024.

Lambert, N., Pyatkin, V., Morrison, J., Miranda, L., Lin, B. Y., Chandu, K., Dziri, N., Kumar, S., Zick, T., Choi, Y., Smith, N. A., and Hajishirzi, H. RewardBench: Evaluating Reward Models for Language Modeling, 2024. URL https://arxiv.org/abs/2403.13787.

Lee, A., Bai, X., Pres, I., Wattenberg, M., Kummerfeld, J. K., and Mihalcea, R. A Mechanistic Understanding of Alignment Algorithms: A Case Study on DPO and Toxicity. June 2024. URL https://openreview .net/forum?id=dBqHGZPGZI.

Liang, J. T., Badea, C., Bird, C., DeLine, R., Ford, D., Forsgren, N., and Zimmermann, T. Can GPT-4 Replicate Empirical Software Engineering Research?, June 2024. URL http://arxiv.org/abs/2310.01727. arXiv:2310.01727 [cs].

Niu, S., Miao, C., Chen, G., Wu, P., and Zhao, P. Test-Time Model Adaptation with Only Forward Passes. June 2024. URL https://openreview.net/forum?id= qz1Vx1v9iK.

OpenAI. Preparedness Framework, December 2023.

Pan, A., Bhatia, K., and Steinhardt, J. The Effects of Reward Misspecification: Mapping and Mitigating Misaligned Models, 2022. URL https://arxiv.org/abs/ 2201.03544.

Rathore, P., Lei, W., Frangella, Z., Lu, L., and Udell, M. Challenges in Training PINNs: A Loss Landscape Perspective. June 2024. URL https://openreview.n et/forum?id=mJGiFr8jLa.

Sanchez, G., Spangher, A., Fan, H., Levi, E., and Biderman, S. Stay on Topic with Classifier-Free Guidance. June 2024. URL https://openreview.net/forum ?id=RiM3cl9MdK.

Sawada, T., Paleka, D., Havrilla, A., Tadepalli, P., Vidas, P., Kranias, A., Nay, J. J., Gupta, K., and Komatsuzaki,

A. ARB: Advanced Reasoning Benchmark for Large Language Models, 2023. URL https://arxiv.or g/abs/2307.13692.

Schlarmann, C., Singh, N. D., Croce, F., and Hein, M. Robust CLIP: Unsupervised Adversarial Fine-Tuning of Vision Embeddings for Robust Large Vision-Language Models. June 2024. URL https://openreview.n et/forum?id=WLPhywf1si.

Sharrock, L., Simons, J., Liu, S., and Beaumont, M. Sequential Neural Score Estimation: Likelihood-Free Inference with Conditional Score Based Diffusion Models. June 2024. URL https://openreview.net/forum ?id=8viuf9PdzU.

Shi, J., Gare, G. R., Tian, J., Chai, S., Lin, Z., Vasudevan, A. B., Feng, D., Ferroni, F., and Kong, S. LCA-on-the-Line: Benchmarking Out of Distribution Generalization with Class Taxonomies. June 2024. URL https://op enreview.net/forum?id=HPXRzM9BYZ.

Si, C., Yang, D., and Hashimoto, T. Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers. arXiv preprint arXiv:2409.04109, 2024.

Siegel, Z. S., Kapoor, S., Nagdir, N., Stroebl, B., and Narayanan, A. CORE-Bench: Fostering the Credibility of Published Research Through a Computational Reproducibility Agent Benchmark. arXiv preprint arXiv:2409.11363, 2024.

Singla, J., Agarwal, A., and Pathak, D. SAPG: Split and Aggregate Policy Gradients. June 2024. URL https: //openreview.net/forum?id=4dOJAfXhNV.

Sun, H., Zhuang, Y., Wei, W., Zhang, C., and Dai, B. BBox-Adapter: Lightweight Adapting for Black-Box Large Language Models.

UK AI Safety Institute. Inspect, 2025. URL https: //inspect.ai-safety-institute.org.uk /agents.html#sec-basic-agent.

van der Weij, T., Hofstatter, F., Jaffe, O., Brown, S. F., ¨ and Ward, F. R. AI Sandbagging: Language Models Can Strategically Underperform on Evaluations. arXiv preprint arXiv:2406.07358, 2024.

Wang, R., Jansen, P., Cotˆ e, M.-A., and Ammanabrolu, P. ´ Scienceworld: Is Your Agent Smarter than a 5th Grader? arXiv preprint arXiv:2203.07540, 2022.

Wang, T., Kulikov, I., Golovneva, O., Yu, P., Yuan, W., Dwivedi-Yu, J., Pang, R. Y., Fazel-Zarandi, M., Weston, J., and Li, X. Self-Taught Evaluators, 2024a. URL http s://arxiv.org/abs/2408.02666.

Wang, X., Lin, B., Liu, D., Chen, Y.-C., and Xu, C. Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning. June 2024b. URL https: //openreview.net/forum?id=PpBs2iL0jv.

Wijk, H., Lin, T., Becker, J., Jawhar, S., Parikh, N., Broadley, T., Chan, L., Chen, M., Clymer, J., Dhyani, J., et al. RE-Bench: Evaluating frontier AI R&D capabilities of language model agents against human experts. arXiv preprint arXiv:2411.15114, 2024.

Wolczyk, M., Cupial, B., Ostaszewski, M., Bortkiewicz, M., Zajac, M., Pascanu, R., Kucinski, L., and Milos, P. Fine-tuning Reinforcement Learning Models is Secretly a Forgetting Mitigation Problem. June 2024. URL https: //openreview.net/forum?id=53iSXb1m8w.

Xia, X., Liu, J., Zhang, S., Wu, Q., Wei, H., and Liu, T. Refined Coreset Selection: Towards Minimal Coreset Size under Model Performance Constraints. June 2024. URL https://openreview.net/forum?id= yb5xV8LFDq.

Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., and Cao, Y. ReAct: Synergizing Reasoning and Acting in Language Models, March 2023. URL http:// arxiv.org/abs/2210.03629. arXiv:2210.03629 [cs].

Zhao, B., Hajishirzi, H., and Cao, Q. APT: Adaptive Pruning and Tuning Pretrained Language Models for Efficient Training and Inference. June 2024. URL https: //openreview.net/forum?id=sb81Xl50JG.

Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E., et al. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. Advances in Neural Information Processing Systems, 36: 46595–46623, 2023.

Zhuge, M., Zhao, C., Ashley, D., Wang, W., Khizbullin, D., Xiong, Y., Liu, Z., Chang, E., Krishnamoorthi, R., Tian, Y., et al. Agent-as-a-Judge: Evaluate Agents with Agents. arXiv preprint arXiv:2410.10934, 2024.

## A. Future Directions in AI Evaluation

Our experience working on PaperBench has driven home important lessons about the future of AI development and evaluation. On many tasks (outside of PaperBench), AI systems currently perform near or at the level of expert humans, and there is demand to offload to AI systems tasks that are labor-intensive for humans.

Unlike most present evaluations, PaperBench expects the evaluated agents to produce a complex and unstructured output. Additionally, the output cannot be programmatically graded. Rubrics (Sawada et al., 2023; Harvey Team, 2024) offer one approach for converting the complex and underspecified task into something simpler and more well-specified: To deal with complexity, we break evaluation into smaller sub-criteria. To deal with underspecification, we collaborate with authors from the papers to make specific choices about what is important for replication and how to weigh the importance of various factors (there exist many different realizations of our paper rubrics which are no less valid).

Nevertheless, important limitations of PaperBench remain (see Section 7). Below, we discuss directions that would help solve those limitations and unlock scalable yet trustworthy evaluation of complex and unstructured tasks more generally.

## A.1. Exploring rubric design and creation

In the rubrics designed for PaperBench, the order of child nodes encodes the dependencies; later child nodes are dependent on earlier child nodes. For example, requirements for matching results from the paper come after requirements for implementing the methodology required for running the experiments. However, our current design doesn’t specify exactly which of the previous requirements are necessary; ideally, the design of the rubric would specify which requirements are necessary for any given requirement in the rubric. Future work could explore using dependency graphs in the rubrics as a potential solution.

Given the difficulty of creating rubrics, automated rubric creation is another valuable direction for future work. Our preliminary experiments found that frontier models, such as o1, are excellent partners for understanding and summarizing papers. However, we found frontier models struggle to create reliable rubrics from start to end, even with significant prompt engineering. Due to rubric complexity, it is also a challenge to review and iterate on model-generated rubrics, but we believe human-in-the-loop workflows might prove fruitful here. We also believe that using models to critique rubrics is a promising approach that could lead to faster rubric creation.

## A.2. Improving automated judges

A single rubric in PaperBench typically has hundreds of nodes to evaluate, which is prohibitively expensive to evaluate with humans; in preliminary experiments, we found grading using expert humans to take on the order of tens of hours. As demonstrated by SimpleJudge (Section D), model-based evaluations (Chiang & yi Lee, 2023; Lambert et al., 2024; Wang et al., 2024a) play an important role in the scalability of rubric-based evaluation. We’ve taken an early step with JudgeEval (Section 4.2) to measure the accuracy of model-based judges on tasks with huge complex outputs, but more work is needed to improve accuracy and understand their strengths and weaknesses.

We further note that the more reliable your judge is, the less fine-grained your rubric’s task decomposition needs to be, potentially reducing the effort necessary for task decomposition as judges become more capable. We leave it to future work to study the trade-off between careful specification and delegation to the judge.

## A.3. Specification gaming and adversarial agents

PaperBench rubrics have been carefully designed to avoid false negatives and false positives, but given the large number of nodes and the complexity of paper replication, we cannot yet rule out loopholes in our evaluation. Agents may have incentives to strategically underperform (van der Weij et al., 2024) or overperform (DeepMind, 2024; Pan et al., 2022) on PaperBench; future work could explore both the capability and propensity of agents to convincingly underperform and overperform on PaperBench.

## B. Paper Selection Process

Our final dataset was constructed through a systematic filtering process applied to papers from ICML 2024. Each filter was designed to ensure papers in our dataset would be suitable for replication attempts. We used gpt-4o-2024-08-06 with a series of prompts to implement initial filtering. Below we detail each filtering step and its rationale:

• Commercial and Geographic Filter: Papers were excluded if 75% or more of the authors had affiliations suggesting it would be unlikely for the authors to collaborate, due to constraints involving working with commercial labs or certain countries.

• Empirical Content Filter: At least one of the contributions from the paper must involve a substantial empirical experiment, which requires non-trivial engineering to replicate. This rules out position papers and pure theory papers. We also rule out papers that primarily present a new software framework, library, or tool since they do not present novel experimental results.

• Hardware Requirements Filter: Papers requiring distributed training across multiple compute nodes were excluded. This ensures that all remaining papers can be reproduced on a single machine, making replication more accessible.

• Model Dependency Filter: Papers depending on closed-source pretrained models (e.g., GPT-4, Claude, PaLM) were excluded.

• Data Requirements Filter: Papers requiring human data collection or annotation were excluded. This ensures reproducibility without the need for new human participants or annotators.

• Reproducibility Filter: Sufficient detail must be present in the paper such that it is possible to replicate the results from scratch by reading it and following the methodology. See Section 3.2 for further discussion of how we ensure that papers are replicable even when lacking some information.

• Framework Papers Filter: Papers primarily introducing new software frameworks or libraries were excluded, as these typically require different replication approaches than research papers.

• Accessible Dependencies Filter: All the paper’s dependencies should be easily accessible. If a paper has dependencies that are inaccessible (e.g., modifying closed-source models) or are fast-to-change (e.g., an unreliable API endpoint that frequently changes), these must be substitutable or able to be dropped without making the remaining paper replication uninteresting or impossible.

We then randomly selected the remaining Spotlight and Oral papers and read the paper to ensure that there were no remaining issues that the automated filtering had missed. We reached out to authors of papers that passed this review process until we had reached out to 42 authors and had secured 20 authors who agreed to work with us to produce rubrics for their papers.

## C. Rubric and Addendum Creation Process

Each rubric is collaboratively developed with one of the original authors of the paper to ensure accuracy and relevance. The process begins with two research engineers drafting the initial rubric, which undergoes several rounds of internal review to refine its structure and content.

Once the internal review is complete, the rubric is shared with the original author, who works with us under a formal agreement to verify its correctness and provide expert input. This phase often involves multiple rounds of feedback to address ambiguities or questions about the paper’s methods or results. Any clarifications from the author are incorporated into the paper’s addendum.

On average, the creation of a rubric and its addendum takes many tens of hours of labor. We refer to Figure 4 for an excerpt from one of the rubrics in PaperBench.

## D. SimpleJudge Implementation

Given a submission, our judge independently grades each leaf node in a rubric. For a specific leaf node, the judge is prompted with the Markdown of the paper, the addendums, prior requirements in the rubric (siblings and direct ancestors), the leaf node’s requirement, and relevant files from the submission.

We collect the relevant files of the submission for context-management reasons and do so as follows:

![](images/dafb1791e5f30c0cc2710016db77248cc760e8c3988324d396669feaf84dc54b.jpg)  
Figure 4. An excerpt of the rubric for one of the papers in PaperBench. Shown in the underlying JSON (left) and in a GUI (right).

For Code Development and Execution leaf nodes, the submission directory is first filtered via simple whitelisting of source code, documentation and configuration files (e.g. markdown, python, JSON, TOML, C++, etc.), and blacklisting of anything originating from directories not related to source code, e.g. venv directories. If the entirety of the filtered submission fits within (nctx − 10, 000), where nctx is the size of the context window of the underlying model used in the judge, then all files are concatenated (with filenames added to the top of each file) and added to the context window. Otherwise, we further filter the codebase by having the judge rank the files and only include the top ten in its context. We display all filenames to the judge, ask it to rank the files in order of relevance to the current requirement, then add files in descending order of relevance until the context window limit of (nctx − 10, 000) tokens would be exceeded.

For Result Match nodes, we follow the same exact process, but rather than whitelisting source code and configuration files, we whitelist plaintext files likely to contain tabular data (such as CSV, JSON, JSONL, HTML, etc.) that have a last-modified timestamp that is newer than the start-time of the reproduce.sh execution. Just like in Code Development and Execution, we whitelist documentation files and blacklist non-source directories.

See Figure 7 for the prompt used for file ranking.

Having identified the relevant files, we prompt our judge to assess whether the requirement of the leaf node has been fulfilled and to provide the reasoning for the binary score it chose; see Figures 8 and 9 for the prompt we use. We then use gpt-4o20 to parse the response of the judge model for a score that should be 0 or 1, an explanation that should be a short summary of the judge model’s reasoning, and valid score – a boolean indicating whether the response contained a valid score.

## E. Monitor Implementation

Our basic monitor implementation performs a simple text search on log files to identify occurrences of blacklisted terms. When a blacklisted term is found, the monitor logs the specific term and a few lines of surrounding context to aid human review.

## F. Agent Implementation

When executing agents with a time limit, we did not count time spent retrying when querying the model API towards the time limit; these retries were commonly due to rate limits or server errors.

## F.1. BasicAgent

Our agent scaffold is a basic ReAct (Yao et al., 2023) agent architecture that runs a tool use loop until the agent runs out of steps or time. It is based on Inspect AI’s basic agent (UK AI Safety Institute, 2025) with the following changes:

• We re-frame the submit tool as an “end task” tool that the agent should call when it is completely finished with its attempt, in order to dissuade the agent from calling it too soon.

• We add a simple context length management system that removes old non-instruction messages from the agent’s context when the context limit is approached.

• We provide a paginated file reader tool that allows the agent to read a file in a piecemeal fashion and also search a file for keywords.

We devise our system prompt used by starting with the original Basic Agent system prompt and adjusting it based on the results of preliminary experiments which used a small subset of our final dataset. In these preliminary experiments we found various failure modes such as:

• Models simply describe a plan for how to replicate the paper instead of calling any tools to write code and make a replication itself.

• Reasoning models such as o1 were particularly prone to trying to finish the task in a single response, calling the submit tool with a huge message containing multiple pieces of code.

• Models didn’t attempt to read the full paper, and so naturally weren’t able to complete a full replication.

• Models would frequently call the end task tool very quickly.

The final system message we used for BasicAgent is displayed in Figure 10. The agent is fed the task instructions (see Appendix F.3) via a user message.

## F.2. IterativeAgent

Despite our improvements made to the original scaffold when developing BasicAgent, we found that most models used with BasicAgent still intentionally used the submit tool to end the task early. Interestingly, most of the time models justified this choice by claiming that they were instructed to complete a partial reproduction of the paper, rather than a full reproduction.

We developed IterativeAgent from BasicAgent to encourage models to complete the entire task. Every time we queried the model we instructed it to only take the next step towards replicating the paper; we found this to significantly reduce the likelihood of models finishing early. We also removed the submit tool so IterativeAgent would have to work for the full time available.

IterativeAgent uses a different system message displayed in Figure 11. If the model produces a message with no tool calls we append the user message in Figure 12 to the message history.

## F.3. Task Instructions

We report the task instructions for our benchmark in Figure 13 and Figure 14. We make no rule about how the task instructions should be ingested by a submitting agent scaffold (e.g., scaffolds may choose to ignore this particular formulation of the instructions and prompt the backend model their own way), and provide them as part of our benchmark.

![](images/42e4efa9f043a541ea9f4eed66bee5744e5c15211aad27c97478ccfbd4080ac1.jpg)  
Average SimpleJudge Cost Per Paper [USD]  
Figure 5. Performance on JudgeEval vs average cost per paper in JudgeEval for various model backends in SimpleJudge. Model cost measured in terms of input+output tokens multiplied by their respective cost-per-token on the OpenAI API. Human cost estimated at 12 hours of work at an hourly rate of \$100 USD/hr. Reasoning models are run with with reasoning effort set to “high”.

## G. More on JudgeEval

In Fig. 5, we plot the average performance (F1) vs. cost (\$USD per paper) for various model backends when using SimpleJudge on JudgeEval. We estimate model cost in terms of API usage cost (number of input/output tokens multiplied by the relevant cost-per-token based on public OpenAI o1 API pricing as of 2025/03/21)

We also plot the expert human performance and cost, treating this as ideal performance and estimating cost at 12 hours of work per paper at a hypothetical hourly rate of 100 \$USD/hr. Finally, we plot the performance of a random baseline where the judge randomly marks leaf nodes as satisfied or unsatisfied.

We find that humans are hundreds of dollars more costly than the most expensive model (o1) for end users. Additionally, we find performance comparable to o1 with o3-mini, at one-tenth of the cost.

Table 6. Macro-averaged F1-score for the models evaluated as part of JudgeEval with the SimpleJudge scaffold. We report F1 both overall and stratified across requirement types.  
![](images/915489eb715f4101bf5dfd2c16e1c86d3a1a9f3a32a8648bfa0c443ef1c6bb8f.jpg)

In Table 6 we accompany the overall F1 scores reported in Table 2 with their stratified counterparts, measuring how well SimpleJudge performs based on requirement type.

We see that performance is relatively stable across requirement types, although a clear gradient of “difficulty” is also discernible: models struggle most on Code Development nodes and perform best on Result Match nodes. O3-MINI-HIGH achieves an F1-score of 0.72 in Code Development, which we deem acceptable for tracking signal on this requirement type. We note that O1-HIGH seems to outperform O3-MINI-HIGH on Code Development and Execution, although this difference may be due to noise and remains futile given the much higher costs.

![](images/946ed84e7e763fdd3e2ca224f4938f9ac0f771f25fbdbe7234077fbabcdc1f0b.jpg)  
Figure 6. The replication score assigned by o3-mini SimpleJudge to the ‘rice/0’ submission in JudgeEval, over different depths of pruning. Pruning at depth 100 is equivalent to not pruning for this paper. We plot the ground truth human Judge grade in red. Error bars are standard error of the mean over 3 repeats.

## H. Pruned Rubric Grading

As pointed out in Section 7 and in Appendix G, grading PaperBench rollouts can be quite expensive. Despite o3-mini’s reduced token costs, grading still costs around \$66 per paper on average. While PaperBench Code-Dev offers an alternative, it does come at the cost of foregoing the Execution and Result Match tasks.

As an alternative approach to reduce the cost and time necessary for grading, we experimented with “pruning” the rubrics shown to the judge, collapsing trees past a certain depth into a single leaf node. To do the collapsing, past a certain depth we simply concatenate the contents of the subtrees and subleafs of the current node.

This greatly reduces the amount of output tokens required from the Judge, as the number of decisions is reduced: rather than reasoning and grading all leaf nodes with a binary score, past a certain depth the Judge simply grades entire sub-trees, assigning a float score between 0 and 1. This, however, makes the grading task more difficult for the judge as it must assess in one go whether multiple requirements have been achieved.

In Figure 6, we show the overall replication score assigned by the Judge to one of the submissions in our JudgeEval (see Section 4.2) when pruning at different depths. We observe that, for this paper and submission, pruning anything beyond depth 3 already approaches the score that would be achieved in the default case with no pruning. We note that pruning at depth 3 reduced grading cost by 10×, while the performance of the Judge deteriorates only slightly.

While this is promising, we wish to underline that these are preliminary results on an experimental version of the Judge, and we have also observed cases of unsatisfactory performance. We expect that as models get better, we can increasingly move towards grading subtrees as opposed to grading leaves.

## I. Full Results

In Tables 10, 11, 12, 13, 14, 15, 16, 17, and 18, we display each of the agent performances on each of the 20 papers in our dataset. Notably, for most agents, we see high variance in results on the same paper. Due to the high variance, we recommend others to use several seeds when evaluating PaperBench to get an accurate measure of agent performance.

## I.1. Results stratified by requirement type

See Table 7 for results stratified by requirement type. We observe that models perform poorly on Execution and Result Match requirement types, while scoring better at Code Development nodes. This suggests that models are good at writing lots of code, but aren’t successful at integrating, testing, and successfully running that code to achieve results.

![](images/5de84af50cda90e4e28258280e3620c3cab30995cb2d38630e5bd5cda8c7707f.jpg)  
Table 7. Average Replication Scores for models with our scaffold for each requirement type. Standard error is computed across three seeds, except for o1 (IterativeAgent) and gemini-2.0-flash (BasicAgent) where it is computed across two seeds.

Table 8. List of Papers in PaperBench (with # of rubric nodes from Table 9).  
![](images/9a396858cb8e716d0bf64d85dcb56fc2e6e9052e569b23b8819a029f5d3ebd64.jpg)

Table 9. Counts of Nodes and Leaf Nodes in Rubrics  
![](images/576d796329e624108947f77539e76344d17bf090f53d3d0def83a6d733c47f2e.jpg)

Table 10. GPT-4o BasicAgent results. \* indicates a result that was set to 0% due to disqualification violating PaperBench rules.  
![](images/74e9d15c86665f645bb564aa95aa7630b90374780a2b081eb11a2dfac4dfd579.jpg)

Table 11. o1 BasicAgent results.  
![](images/86dece7ee4c652ec74b64bbc41d4102cc16143aab5474f270438dd16c9f7d201.jpg)

Table 12. o1 IterativeAgent results.  
![](images/b197d88b95fd995f46978067d099c849e7c33fc3de27193a3cf7eaf263568a37.jpg)

Table 13. o3-mini BasicAgent results.  
![](images/8c9297bd8927d1820e44f44f6e332faba2fd3f4e0e433e1dba683acb9c623e23.jpg)

Table 14. o3-mini IterativeAgent results.  
![](images/7c87fcaf24d67f0c38b4bb8c3a1379175a96adb6869c79e063e3beec7ad13ace.jpg)

Table 15. Claude 3.5 Sonnet BasicAgent results.  
![](images/f492dbc70c512d90939b01f79c4a906fa0c9d2ccdb9721ca96f9346290b3087e.jpg)

Table 16. Claude 3.5 Sonnet IterativeAgent results.  
![](images/d18177fae80abeb12f7be4d88cef7de1442496c5780a16a0d83dbc92f791a556.jpg)

Table 17. Gemini 2.0 Flash BasicAgent results. Run 3 of what-will-my-model-forget failed due to infrastructure issues. \* indicates a result that was set to 0% due to disqualification violating PaperBench rules.  
![](images/f1f001a490eefa99500e4d47492e1c5103f68aadf094c622cd4d4f5d8c806998.jpg)

Table 18. R1 BasicAgent results. \* indicates a result that was set to 0% due to disqualification violating PaperBench rules.  
![](images/7a95d76e9db8c2e9c6082a94b4bda9e5499056af2a045822c7cac031a1406b5b.jpg)

![](images/dc4973b01b9e622dd27f3049c65baae9271cd5e1dce7392391da2b47cfeecdff.jpg)  
Figure 7. Judge file ranking prompt. Variables like {tree\_structure} are replaced with their value at runtime.

![](images/6b095309c57df9affdbaafe309bba275e3e78eca06e8209a513da47a1ab85029.jpg)  
Figure 8. Judge Prompt. Part 1 of 2. Variables like {paper\_markdown} are replaced with their value at runtime. Text in red is omitted from the prompt for PaperBench-CodeDev. Text in blue is exclusively shown for PaperBench-CodeDev. Text in green is shown exclusively for Code Development and Execution leaf nodes while text in purple is shown exclusively for textttResult Match nodes.

![](images/f18e99a091aeb00fe1ac8bc52cfd95295e8f9e89d95ce8b40eb3ebebcda30a6f.jpg)  
Figure 9. Judge Prompt. Part 2 of 2. {criterion} corresponds to the requirements of the leaf node currently being graded. {preceding\_critera} are the requirements of preceding nodes (siblings and direct ancestors). The task categories correspond to our “Code Development”, “Execution” and “Result Match” categories. The corresponding {task\_category\_question} are “Does the agent’s source code contain a correct implementation of this?”, “Does running the reproduce.sh script lead to this being successfully executed?”, and “Does the outcome of the reproduction agree with these results?”.

![](images/267997e34fbd5d2670ada922469917fcacdb438d5f262f4e2f8f83fe247d1448.jpg)  
Figure 10. BasicAgent System Prompt

![](images/cc67373a432526dffa6656cd8d89d884e3ee6db2a96580fc768ebc393d0228d1.jpg)  
Figure 11. IterativeAgent System Prompt

![](images/bae92b105b9fa4f9a457a5e38fe4a339c90ffcff36e911dd80d885615a5dd129.jpg)  
Figure 12. IterativeAgent Continue Message

![](images/32e9016ce13942f79e5f720de07ce846ff1a5ea2ac2cf2eac0bb29e24018a241.jpg)  
Figure 13. Task Instructions, continued in Part 2

![](images/d0a8b3dea78301e94a64bcef4e694444a34ad365525116864669a4e465012664.jpg)  
Figure 14. Task Instructions, continued from Part 1