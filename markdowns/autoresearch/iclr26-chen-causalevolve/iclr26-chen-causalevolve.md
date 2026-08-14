# CAUSALEVOLVE: TOWARDS OPEN-ENDED DISCOVERY WITH CAUSAL SCRATCHPAD

Yongqiang Chen<sup>∗1,2</sup> Chenxi Liu <sup>∗3</sup> Zhenhao Chen<sup>1</sup> Tongliang Liu<sup>4,1</sup> Bo Han<sup>3</sup> Kun Zhang<sup>1,2</sup>

<sup>1</sup>MBZUAI <sup>2</sup>Carnegie Mellon University <sup>3</sup>TMLR Group, Hong Kong Baptist University

<sup>4</sup>SAIC Centre, The University of Sydney

yqchen24@gmail.com cscxliu@comp.hkbu.edu.hk

## ABSTRACT

Evolve-based agent such as AlphaEvolve is one of the notable successes in using Large Language Models (LLMs) to build AI Scientists. These agents tackle open-ended scientific problems by iteratively improving and evolving programs, leveraging the prior knowledge and reasoning capabilities of LLMs. Despite the success, existing evolve-based agents lack targeted guidance for evolution and effective mechanisms for organizing and utilizing knowledge acquired from past evolutionary experience. Consequently, they suffer from decreasing evolution efficiency and exhibit oscillatory behavior when approaching known performance boundaries. To mitigate the gap, we develop CausalEvolve, equipped with a causal scratchpad that leverages LLMs to identify and reason about guiding factors for evolution. At the beginning, CausalEvolve first identifies outcome-level factors that offers complementary inspirations in improving the target objective. During the evolution, CausalEvolve also inspects surprise patterns during the evolution and abductive reasoning to hypothesize new factors, which in turn offer novel directions. Through comprehensive experiments, we show that CausalEvolve effectively improve the evolutionary efficiency and discovers better solutions in 4 challenging open-ended scientific tasks.

## 1 INTRODUCTION

As large language model (LLMs) demonstrate increasing capabilities in complex and challenging reasoning tasks (Guo et al., 2025; Li et al., 2025e), the community seeks to build LLM-based agents to facilitate a number of downstream applications (Plaat et al., 2025). One of the most notable and promising applications is the AI Scientist agents (ZHENG et al., 2025), where the LLM-based agent is expected to automate the scientific discovery process ranging from conducting literature surveys (Wan et al., 2026), hypothesis generation (Khemakhem et al., 2020), data-driven analysis (Chan et al., 2024) to experiment design (Li et al., 2025c), etc. In fact, when incorporated into the agentic framework, LLMs have demonstrated great promise. Lu et al. (2024); Gottweis et al. (2025); Mitchener et al. (2025) show that LLMs can come up with new research hypotheses and proposals based on the existing literature and automate the full scientific discovery pipeline (Yamada et al., 2025). Recent advances in using LLMs to assist with scientific discovery shows LLMs can accelerate the idea iteration and deep literature search (Bubeck et al., 2025; Woodruff et al., 2026).

One of the most representative AI Scientist agents is the evolutionary coding agent, like AlphaEvolve (Novikov et al., 2025; Lange et al., 2025b). In the iterative evolutionary framework, LLMs demonstrate great capabilities in proposing, evaluating, and refining iteratively better solutions to a number of scientific problems (Sharma, 2025; Georgiev et al., 2025; Cheng et al., 2025). Despite the success, the evolution process in the existing frameworks is mainly driven by the evolution algorithm or derived from correlational studies. In contrast, human scientists can design purposeful experiments and summarize scientific insights from observational data (Kuhn & Hawkins, 1963; Kaelbling et al., 1998; Glymour). The gap that emerges between the uncontrolled evolutionary process of evolve-based agents and the guided discovery process of humans raises a challenging research question:

## How can we develop evolution-based agents to perform guided scientific discovery like humans?

To tackle the question, we resort to causality, which summarizes the practice of scientific discovery of humans (Spirtes et al., 2000b; Pearl, 2009). Essentially, scientific discovery is about revealing the underlying causal mechanism of the interested problem (Wallace, 1981; Glymour). Hence, we can formulate the evolution based scientific discovery process as a Partially Observable Markov Decision Process (POMDP) (Kaelbling et al., 1998), where the agent needs to uncover the underlying causal mechanism through purposeful actions and interventions (Sec. 3). With the POMDP formulation, we demonstrate that accumulating and guiding the evolution with causal knowledge is crucial to both the efficiency and effectiveness of the discovery process. Without the incorporation of causality, the evolution can easily oscillate or get stuck at local optimal solutions.

To this end, we develop a new evolutionary AI Scientist framework, termed CausalEvolve, where we introduce a causal scratchpad to the evolution-based agent. The guidance provided by CausalEvolve is built upon the interventional factors identified before and during the evolution process. As the evolution-based agent primarily focuses on optimizing a target objective, such as the objective value of a combinatorial optimization problem or the accuracy of a machine learning problem (Lange et al., 2025b), CausalEvolve first identifies a set of outcome-level factors to provide complementary views of the target objective. During the evolution, CausalEvolve leverages a multi-arm bandit (MAB) to adaptively determine the desired intervention with respect to a selected outcome-level factor.

In addition, CausalEvolve also identifies procedure-level factors from the accumulated trials with LLMs (Liu et al., 2024). Intuitively, the procedure-level factors are useful interventions to the solutions that explain the objective value changes. For example, the optimization technique used to solve a combinatorial optimization problem. Nevertheless, some combinations of apparently useful factors may lead to decreased scores, which we term as “surprise patterns”. Understanding and explaining the “surprise patterns” is critical to reveal new scientific insights (Wallace, 1981). Hence, CausalEvolve also performs abductive reasoning to come up with new factors and hypothesis that will be suggested to evaluate in the future experiments to better explain all the observed patterns (Douven, 2025).

Empirically, we show that CausalEvolve significantly improves the evolution efficiency and achieves better results compared to the existing state-of-the-art ShinkaEvolve (Lange et al., 2025b) across 4 open-ended discovery problems. Our contributions can be summarized as follows:

• We propose a theoretical formulation of evolution-based open-ended discovery, and demonstrate the necessity of causality (Sec. 3);

• We propose a new framework CausalEvolve to realize the accumulation and guidance of causal knowledge by identifying outcome-based and procedure-based factors;

• CausalEvolve is shown to improve both the evolution efficiency and effectiveness across 4 open-ended discovery problems.

## 2 RELATED WORK

AI Scientist Agents. With the significant advancement in LLM capacity and the development of Agentic system, there is a rising number of works on developing agents for helping scientific discoveries (Lu et al., 2024; Yamada et al., 2025; Gottweis et al., 2025). One research line is to automating the pipelines in scientific activities, including literature review (Huang et al., 2025b), hypothesis generation (Li et al., 2024a; Yang et al., 2024; Wang et al., 2024; Yang et al., 2025), hypothesis verification (Li et al., 2024b; Huang et al., 2025a), and assistance in scientific reports (Liang et al., 2024). Another research line is to integrating the knowledge and reasoning ability of LLMs to conduct computational intensive evolution or iteration on specific scientific problems (Shojaee et al., 2025; Romera-Paredes et al., 2024; Novikov et al., 2025; Sharma, 2025; Lange et al., 2025a). There are also works on automated tabular data analysis with machine learning workflows (Zha et al., 2023; Li et al., 2023; Zhang et al., 2023; Li et al., 2025b), or embodied agents that can conduct real-world experiments (Roch et al., 2020; Zhu et al., 2022; Tom et al., 2024; Mandal et al., 2025). The impact of these lines of work has been made on scientific fields includes chemistry (Yang et al., 2026; Boiko et al., 2023), earth science (Feng et al., 2025), and biology (Swanson et al., 2025; Truhn et al., 2026).

Causality for Scientific Discovery. There has been a long history for the discussions on how to understand world through observations (Greenland et al., 1999; Spirtes et al., 2000a; Pearl, 2009). One research line is causal discovery for structured data, where algorithms are designed to learn directed acyclic graphs among the random variables as causal structure, including constrained-based methods (Spirtes et al., 1995; 2000a), methods with constrained functional (Shimizu et al., 2006; Zhang & Hyvarinen, 2012; Hoyer et al., 2008), non-stationarity (Malinsky & Spirtes, 2019; Huang et al., 2019; 2020; Liu & Kuang, 2023), the incorporation with multiple domain data (Huang et al., 2020; Yang et al., 2018; Brouillard et al., 2020; Mooij et al., 2020; Perry et al., 2022), and handling latent variables with the pure children assumption (Li et al., 2025d; Li & Liu, 2025). Recently, there are works to integrating causality with large language models. One direction is to empower the causal methods with the knowledge of LLMs, which includes constructing priors based on variable descriptions (Long et al., 2023; Li et al., 2024c), adjusting the causal structure searching process (Ban et al., 2023; Vashishtha et al., 2023; Jiralerspong et al., 2024), constructing structured variables out of unstructured data (Liu et al., 2025; Li et al., 2025a), and finding valid adjustment sets for treatment effect estimation (Dhawan et al., 2024; Liu et al., 2025; Sheth et al.). Another direction is to empower LLM-based agent with causal tools for tabular data analysis (Abdulaal et al., 2023; Khatibi et al., 2024; Shen et al., 2024; Wang et al., 2025a; Verma et al., 2025), revealing insights from data in an autonomous pipeline.

## 3 SCIENTIFIC DISCOVERY VIA OBJECTIVE OPTIMIZATION

## 3.1 FORMULATION OF SCIENTIFIC DISCOVERY

Scientific discovery aims to uncover the underlying scientific knowledge or the causal mechanisms from interactions with the world (Kuhn & Hawkins, 1963), which can be formulated as a Partially Observed Markov Decision Process (POMDP) (Kaelbling et al., 1998).

Scientific knowledge. The primary objective of an AI Scientist is to uncover the underlying scientific knowledge about the task-world, represented by a latent variable Θ ∈ Θ, where Θ may encode causal structure, mechanisms, inductive biases, constraints, etc. Specifically, Θ<sub>sci</sub> = θ<sub>sci</sub> can be parameterized as a Structural Causal Model (SCM) θ<sub>sci</sub> = (G, F , P<sub>U</sub> ) (Spirtes et al., 2000a), where G = (V, E) is a directed graph whose nodes V represent variables of interest and whose edges E encode direct causal dependencies; F = {f<sub>v</sub>}<sub>v∈V</sub> is a collection of structural equations v = f<sub>v</sub>(Pa(v), u<sub>v</sub>), where Pa(v) denotes the parents of v in G and u<sub>v</sub> is an exogenous noise variable; P<sub>U</sub> is a distribution over the exogenous variables U = {u<sub>v</sub>}<sub>v∈V</sub> .

POMDP process. Given θ , as shown in Fig. 1, the AI Scientist agent, implemented via the evolutionary coding framework such as AlphaEvolve (Novikov et al., 2025), will interact with the environment by proposing candidate programs p<sub>t</sub> ∈ P (at turn t) to gain observations, y<sub>t</sub> = F (p<sub>t</sub>, θ<sub>sci</sub>), where F : P ×Θ → <sup>R</sup> is the objective that the agent aims to optimize. Then, the scientific discovery process can be formulated as a POMDP M = (S, A, Ω, T , O, R, γ) with a static hidden parameter as θ<sub>sci</sub> of the underlying scientific knowledge. The hidden state s<sub>t</sub> = θ<sub>sci</sub> is the scientific knowledge θ<sub>sci</sub> that does not change over turns. The action is a<sub>t</sub> = p<sub>t</sub> representing the choice of which program to evaluate. The observation o<sub>t</sub> = y<sub>t</sub> is the evaluation outcome. The transition kernel T can be simply considered as identity, and the observation kernel is O(o<sub>t</sub> | s<sub>t</sub>, a<sub>t</sub>) = P (y<sub>t</sub> | θ<sub>sci</sub>, p<sub>t</sub>). Given a finite experiment budget T , the agent chooses p<sub>0</sub>, . . . , p<sub>T −1</sub> and gain observations y<sub>0</sub>, . . . , y<sub>T −1</sub>, so as to find pˆ = arg max F (p, θ<sub>sci</sub>) and the scientific knowledge θ<sub>sci</sub>.

![](images/33ad757b3a2a457ee932f2f43742f4e4c480118e574176015ce4359e08f43f6a.jpg)  
Figure 1: The iterative scientific discovery loop. Left: Conceptual flow of the agent. The agent maintains a scratchpad memory (m), proposes a program (p), and observes the outcome (y) which is constrained by the unknown world state (θ<sub>sci</sub>). The outcome feeds back into the memory for the next step. Right: The diagram illustrates how the AI Scientist probes the unknown world state θ<sub>sci</sub>. By proposing a candidate program p<sub>t</sub>, the agent triggers an experiment yielding outcome y<sub>t</sub>. This observation provides evidence about θ<sub>sci</sub>, which is integrated into the agent’s scratchpad memory m<sub>t+1</sub>. Over time steps t, t + 1, . . . , this recurrent process allows the agent to navigate the performance landscape and converge towards optimal programs despite the static but unknown nature of θ<sub>sci</sub>.

Evaluation as intervention on SCM. Given the SCM parametrization of θ<sub>sci</sub>, we can consider that a program p ∈ P is encoded as a particular configuration of design variables X = x<sub>p</sub>. Then, F can be implemented as

![](images/fe7c3e1e4854c861c505fd98c3f489008a718fa5dab26eec0f633e11ad2e9007.jpg)

(1)

i.e., the expected outcome under the intervention do(X = x<sub>p</sub>) in the true causal model θ<sub>sci</sub>. Typical implementations of F can be the objective value of a combinatorial optimization problem, the efficiency of a kernel program, or the performance of a machine learning model (Novikov et al., 2025).

Belief as a probability distribution over Θ. We define b<sub>t</sub> as the agent’s Bayesian belief after history h<sub>t</sub> = {(p<sub>0</sub>, y<sub>0</sub>), . . . , (p<sub>t−1</sub>, y<sub>t−1</sub>)}, i.e. a probability distribution on Θ:

![](images/75cf89c9d9e3a4e6d62b29fe13b4e4b0f57df99e1620ce80e27d0fade8df2629.jpg)

(2)

In the ideal Bayesian formalism, the belief b (θ) is a sufficient statistic for decision-making (Kaelbling et al., 1998). In practice, the AI Scientist maintains an internal belief, which is usually implemented as memory m<sub>t</sub> = Φ(h<sub>t</sub>) for some (possibly learnable) summarization function Φ (Lange et al., 2025a), to represent the approximate representation of its knowledge about θ<sub>sci</sub> and the landscape of F (·; θ<sub>sci</sub>). Each evaluation step (p<sub>t</sub>, y<sub>t</sub>) thus updates m<sub>t</sub>, which in turn updates the agent’s effective belief about θ<sub>sci</sub>. In this sense, each step reveals part of the underlying scientific knowledge, which in turn determines the next action p<sub>t+1</sub>.

## 3.2 ESSENTIALITY OF CAUSAL KNOWLEDGE FOR AI SCIENTISTS

If the objective function F is static universally, then with more experiment turns, the optimized solution p<sub>t</sub> and the agent’s revealed scientific knowledge can also be applied universally. However, the observation from the evaluation is usually only given by a proxy knowledge θ<sub>e</sub> about the scientific knowledge Θ<sub>sci</sub> at some specific environment e ∈ E. For example, the performance of a machine learning model is usually assessed on finite samples from the test distribution, and there also exist distribution shifts from the test distribution when deploying the model in the real world (Quinonero-Candela et al., 2008). Different from Θ<sub>sci</sub> that characterizes the complete causal structure about the scientific problem, optimization under environment θ<sub>e</sub> may introduce some spurious correlations that maximize the objective value F<sub>e</sub> (Chen et al., 2023). Therefore, without loss of generality, to retain the optimality of pˆ beyond the source environment e<sub>src</sub> to some target e<sub>tgt</sub>, it is essential to reveal the causal knowledge and answer causal questions for an AI Scientist.

Definition 3.1 (Causal AI Scientist). A Causal AI Scientist is an agent specified by: (i) a policy π<sub>t</sub>(· | θ<sub>t</sub>, e<sub>src</sub>) selecting p<sub>t</sub>, (ii) a counterfactual / explanatory operator CF, that answer interventional queries (e, p) via CF(θ<sub>t</sub>; e, p) as an “explanation” of predicted performance, where θ<sub>t</sub> is the knowledge revealed at turn t.

Without the revealing of the causal knowledge, the discovery process suffers from significant inefficiency and suboptimality issues. We discuss the two issues more concretely below.

Evolutionary efficiency of Causal AI Scientist. We begin by considering a static environment and finite P = {p<sub>1</sub>, . . . , p<sub>K</sub>}. For θ<sub>sci</sub>, we assume each program p has a known feature vector x<sub>p</sub> ∈ <sup>Rd</sup> with ∥x<sub>p</sub>∥<sub>2</sub> ≤ 1, and the unknown scientific parameter is a weight vector w<sup>⋆</sup> ∈ <sup>Rd</sup> and F (p) = ⟨x<sub>p</sub>, w<sup>⋆</sup>⟩. Each evaluation returns a noisy observation y<sub>t</sub> = F (p<sub>t</sub>) + ε<sub>t</sub> where ε<sub>t</sub> ∼ N (0, σ<sup>2</sup>) i.i.d.. A Causal AI Scientist in this environment can be implemented via estimating the w<sup>⋆</sup> and optimizing for pˆ from the history.

In addition, we also consider a black-box baseline that does not consider the interactions between the historical observations. It can be characterized as the following θ<sub>bb</sub> := <sup>n</sup>µ : P → <sup>Ro</sup> where each program has an unrelated unknown mean F (p; µ) = µ(p), and y<sub>t</sub> = µ(p<sub>t</sub>) + ε<sub>t</sub>, where ε<sub>t</sub> is the same Gaussian noise.

Theorem 3.2 (Informal). Under the given environment, there exists a policy π<sub>causal</sub> such that with probability at least 1 − δ, F (ˆp; θ ) obtains less than 2ϵ error than the optimal value, with O(d log(K)) turns; In contrast, the black-box baseline needs O(K).

The formal description of the sample efficiency issue and the proof are given in Appendix B. Theorem 3.2 shows that, when K ≫ d, which is usually the case as the space for all programs is significantly larger than the underlying SCM, encoding (correct) causal structure yields an exponential (or at least multiplicative) gain in sample efficiency under finite budgets.

Generalizability of Causal AI Scientist. To show the necessity of capturing θ<sub>sci</sub>, we have the following: Theorem 3.3. Consider the e<sub>src</sub>, e<sub>tgt</sub> ∈ E and θ<sub>0</sub>, θ<sub>1</sub> ∈ Θ such that F<sub>e</sub> (· | p, θ<sub>0</sub>) = F<sub>e</sub> (· | p, θ<sub>1</sub>) ∀p ∈ P, and ∃ p, p<sup>′</sup> ∈ P s.t. F<sub>etgt</sub> (p; θ<sub>0</sub>) − F<sub>etgt</sub> (p<sup>′</sup>; θ<sub>0</sub>) ≥ ∆ and F<sub>etgt</sub> (p<sup>′</sup>; θ<sub>1</sub>) − F<sub>etgt</sub> (p; θ<sub>1</sub>) ≥ ∆, for some ∆ > 0, then for any policy π that can interact only with e<sub>src</sub>, there exists i ∈ {0, 1} such that for every budget T , max<sub>p∈P</sub> F<sub>etgt</sub> (p; θ<sub>i</sub>) − F<sub>etgt</sub> (ˆp; θ<sub>i</sub>) ≥ ∆/2.

The formal description of the generalizability issue and the proof are given in Appendix C. Intuitively, Theorem 3.3 imply that if the source environment does not distinguish the corresponding θ<sub>sci</sub> among {θ<sub>0</sub>, θ<sub>1</sub>}, then the solution pˆ solved given source environment is always suboptimal. In the real world, it is usually the case that two machine learning models will have similar performances under the public test benchmarks, but exhibit significantly different behaviors when generalizing to distributions from other environments.

## 4 CAUSAL SCRATCHPAD FOR EVOLUTIONARY CODING AGENT

Given the limitations shown in Sec. 3.2, it is essential to explicitly incorporate the causal knowledge into the evolutionary process. Hence, we present CausalEvolve, which incorporates a causal scratchpad to identify critical factors and exploit their causal relations with the objective variables to guide the evolution process. Specifically, we consider incorporating the outcome-level factors and the procedure-level factors to tackle the efficiency and the suboptimality issues, respectively.

## 4.1 OUTCOME-LEVEL FACTOR

Essentially, the underlying configurations of the program can be reflected and recognized from task-dependent, real-valued descriptors extracted from the observable outcomes of program execution. As shown in Theo rem 3.2, intervening on the underlying configuration variables provides significantly higher sample efficiency.

Factor construction. For a given task, a set of outcome-based factors m := (m<sub>1</sub>, m<sub>2</sub>, . . . , m<sub>K</sub> ) is specified by LLMs before the evolution. An LLM would be prompted with the basic task description, which is the same as the system prompt used in evolution, and the expected output of each program, e.g., a list of coordinates, or an n × n matrix. For each of the outcome-based factors, the LLM would define the factor name and also a excitable code that maps the program output to the factor value. We list the outcome-based factors used in our tasks in Appendix D.

Causal Planner with outcome-level factors. With outcome-based factors m, we develop CausalPlanner. Specifically, we define the action space A := ∪<sub>m∈m</sub>(m, +1), (m, −1)	. When applying an action (m, d), the existing programs would be sorted in descending order according to m × d, and then the inspiration programs would be selected from the top of them. In t-th generation, after generating each child program from its parent and the inspiration programs with action a ∈ A, the reward R<sub>a</sub> could be calculated. Let the y<sub>c</sub> be the child’s main target that is to be maximized, and v<sub>t</sub> be the best-so-far value of the main target. We define the reward as R<sub>a</sub> := (y<sub>c</sub> − τ · v<sub>t</sub>)<sub>+</sub>, where τ ∈ (0, 1). We introduce this discounter τ because improving the best-so-far result could be a rare event, and therefore cannot be fairly estimated by only a few iterations. In practice, we alternate between exploration and exploitation: random actions are taken for K iterations, followed by choosing the currently best action for the next K iterations.

## 4.2 PROCEDURE-LEVEL FACTORS

To better capture important designs of the programs and uncover their associated causal knowledge, we also introduce procedure-level factors identified from the programs.

Factor construction. We construct the procedure-level factors based on the COAT framework (Liu et al., 2025) that leverages LLMs to identify useful procedure factors from unstructured data. As LLMs are considered incapable of understanding causality, Liu et al. (2025) constructs feedback to regularize the identified factors by LLMs. Similarly, we prompt LLMs to identify factors that explain the performance differences of the performances of different programs. Then, CausalEvolve estimates an approximated average treatment effect of different factors with respect to the target objective value to provide a holistic view of the usefulness of the identified procedure-level factors. Due to the limited sample size and the existence of hidden confounders, the estimated treatment effects may contain biases, while empirically, we do not need an accurate estimation, but order-preserved quantities to provide insights.

Abductive reasoning. As mainly explaining the performance differences is insufficient for revealing all factors, we also incorporate a surprise detection module and leverage LLMs to perform abductive reasoning on the potentially existing factors and hypotheses that explain the surprise patterns (Douven, 2025). The detection of surprise patterns relies on the estimated treatment effects. Since the estimation can contain biases, we focus on detecting significant shifts in the estimated effects, including the signal inverses, i.e., a positively correlated factor produces negative effects, and significant quantity shifts, i.e., a minor correlated factor produces negative effects. By explaining the surprise patterns, we are able to find the underlying confounder and better reveal the underlying θ<sub>sci</sub>.

## 5 EXPERIMENTS

## 5.1 EXPERIMENTAL SETTING

Baselines. We mainly compare CausalEvolve with the state-of-the-art evolve-based agent ShinkaEvolve (Lange et al., 2025a) that produces the best or competitive results as AlphaEvolve (Novikov et al., 2025) in an sample-efficient manner. As ShinkaEvolve also incorporates a memory module to summarize the insights from h , we also consider two additional variants, CausalPlanner with meta summary module from ShinkaEvolve, and COAT, to ablate the effects of two modules in CausalEvolve. For the LLMs, we fix to using Grok-4.1-fast-reasoning (xAI, 2025) for fair comparisons.

Tasks. We evaluate our framework on four scientific discovery tasks that require optimizing code for different objectives:

Hadamard Matrix (n = 29). The goal is to construct an n×n matrix H with entries in {±1} that maximizes the absolute determinant | det(H)|. For n = 29, the best-known solution achieves | det(H)| = 2<sup>28</sup> · 7<sup>12</sup> · 320, which we use to normalize scores to [0, 1] for comparability with prior work (Wang et al., 2025b). This discrete optimization problem requires balancing matrix properties including row orthogonality, element balance, and determinant magnitude.

Second Autocorrelation Inequality. We seek a step function f : [−1, 1] → <sup>R</sup><sub>≥0</sub> (discretized into n = 256 steps) that minimizes the ratio

![](images/a800e3db3e3998b181e61e6ff1e81cc6615c331bbcc168d88b1cd7f865693b0f.jpg)

where f ∗f denotes linear autoconvolution. The optimal value R(f) ≥ 1.1547 . . . remains an open conjecture. This continuous optimization task requires carefully shaping the function’s smoothness, concentration, and sparsity.

Circle Packing (N = 26). The objective is to place N circles with radii r<sub>i</sub> and centers C<sub>i</sub> = (x<sub>i</sub>, y<sub>i</sub>) in a unit square [0, 1]<sup>2</sup> such that: (i) no circles overlap (∥C<sub>i</sub> − C<sub>j</sub> ∥ ≥ r<sub>i</sub> + r<sub>j</sub> for all i ̸= j), (ii) all circles remain within the square (r<sub>i</sub> ≤ C<sup>x</sup><sub>i</sub> , C<sup>y</sup><sub>i</sub> ≤ 1 − r<sub>i</sub>), and (iii) the sum of radii P r<sub>i</sub> is maximized. This geometric optimization task requires spatial reasoning about density, distribution, and boundary constraints.

AIME Mathematical Problem Solving. We evaluate on the 2024 American Invitational Mathematics Examination (AIME), a challenging competition consisting of 15 problems requiring integer answers in [000, 999]. The task is to build an LLM-based agent that solves these problems efficiently. Performance is measured by accuracy, while auxiliary metrics track format compliance (e.g., \boxed{} format), cost efficiency, and stability across problems.

Evaluation metrics. We run every method using 3 random seeds (1, 2, 3) to accommodate the randomness. To compare the efficiency and the optimality, we inspect the stepwise averaged results as well as the best result from the 3 runs, at 4 intermediate steps. Given the difficulty of different tasks, we inspect steps 50, 100, 150, 200 for Second Autocorrelation Inequality and Circle Packing, steps 20, 40, 80, 100 for Hadamard Matrix, and steps 20, 40, 60, 80 for AIME agent.

Table 1: Main results across four scientific discovery tasks. Performance is reported at training steps 1 through 4. For each step, we report the mean performance (Mean) and the best-so-far value (Best). All tasks are maximization objectives.  
![](images/4f9a9d9480ce3a593938c29faeb1c0ecd3f087efdb625fd4b4948d41c8e76740.jpg)

## 5.2 EXPERIMENTAL RESULTS

The results of the experiments are given in Table 1. From the results, we can find that across all tasks, CausalEvolve produce significantly better averaged results than ShinkaEvolve across different tasks and steps, demonstrating the effectiveness of CausalEvolve. Notably, in AIME, CausalEvolve achieves 38.89% results based on the same scaffolding agent as in ShinkaEvolve. While in the orig inal paper of ShinkaEvolve, even with a more sophisticated ensemble of multiple frontier reasoning models, ShinkaEvolve can only achieve a performance of 34.4%, demonstrating the effectiveness of CausalEvolve in breaking the state-of-the-art results in the open-ended discovery.

When comparing different variants and CausalEvolve, we can find that, across 4 tasks, CausalEvolve maintain the overall best performances, verifying that each module is essential to the success of CausalEvolve. Interestingly, in the majority of tasks, COAT can already produce an impressive best result, demonstrating the effectiveness of procedure-level factors for optimality. When comparing results with and without CausalPlanner, we can also find that with CausalPlanner, we can achieve better results already at early steps, demonstrating the effectiveness of outcome-based factors in sample efficiency.

## 6 CONCLUSIONS

In this work, we studied the evolutionary coding agent for scientific discovery. With the POMDP formulation of the discovery process, we demonstrate the necessity of incorporating causal knowledge. Then, we propose CausalEvolve that uses a causal scratchpad to identify and exploit outcome-based and procedure-based factors and the associated causal knowledge to guide the evolution process. Empirical results with 4 discovery tasks verified the improved efficiency and optimality of CausalEvolve.

## ACKNOWLEDGMENTS

We thank the reviewers for their constructive comments and suggestions.

## REFERENCES

Ahmed Abdulaal, Nina Montana-Brown, Tiantian He, Ayodeji Ijishakin, Ivana Drobnjak, Daniel C Castro, Daniel C Alexander, et al. Causal modelling agents: Causal graph discovery through synergising metadataand data-driven reasoning. In The Twelfth International Conference on Learning Representations, 2023. (Cited on page 3)

Taiyu Ban, Lyuzhou Chen, Derui Lyu, Xiangyu Wang, and Huanhuan Chen. Causal structure learning supervised by large language model. arXiv preprint arXiv:2311.11689, 2023. (Cited on page 3)

Daniil A Boiko, Robert MacKnight, Ben Kline, and Gabe Gomes. Autonomous chemical research with large language models. Nature, 624(7992):570–578, 2023. (Cited on page 3)

Philippe Brouillard, Sebastien Lachapelle, Alexandre Lacoste, Simon Lacoste-Julien, and Alexandre Drouin.´ Differentiable causal discovery from interventional data. Advances in Neural Information Processing Systems, 33:21865–21877, 2020. (Cited on page 3)

Sebastien Bubeck, Christian Coester, Ronen Eldan, Timothy Gowers, Yin Tat Lee, Alexandru Lupsasca,´ Mehtaab Sawhney, Robert Scherrer, Mark Sellke, Brian K. Spears, Derya Unutmaz, Kevin Weil, Steven Yin, and Nikita Zhivotovskiy. Early science acceleration experiments with gpt-5. ArXiv, abs/2511.16072, 2025. (Cited on page 1)

Jun Shern Chan, Neil Chowdhury, Oliver Jaffe, James Aung, Dane Sherburn, Evan Mays, Giulio Starace, Kevin Liu, Leon Maksin, Tejal Patwardhan, Lilian Weng, and Aleksander Madry. Mle-bench: Evaluating machine learning agents on machine learning engineering. 2024. URL https://arxiv.org/abs/ 2410.07095. (Cited on page 1)

Yongqiang Chen, Wei Huang, Kaiwen Zhou, Yatao Bian, Bo Han, and James Cheng. Understanding and improving feature learning for out-of-distribution generalization. In Advances in Neural Information Processing Systems, 2023. (Cited on page 5)

Audrey Cheng, Shu Liu, Melissa Z. Pan, Zhifei Li, Bowen Wang, Alexander Krentsel, Tian Xia, Mert Cemri, Jongseok Park, Shuo Yang, Jeff Chen, Lakshya A Agrawal, Aditya Desai, Jiarong Xing, Koushik Sen, Matei Zaharia, and Ion Stoica. Barbarians at the gate: How ai is upending systems research. ArXiv, abs/2510.06189, 2025. (Cited on page 1)

Nikita Dhawan, Leonardo Cotta, Karen Ullrich, Rahul G Krishnan, and Chris J Maddison. End-to-end causal effect estimation from unstructured natural language data. Advances in Neural Information Processing Systems, 37:77165–77199, 2024. (Cited on page 3)

Igor Douven. Abduction. In Edward N. Zalta and Uri Nodelman (eds.), The Stanford Encyclopedia of Philosophy. Metaphysics Research Lab, Stanford University, Winter 2025 edition, 2025. (Cited on pages 2 and 7)

Peilin Feng, Zhutao Lv, Junyan Ye, Xiaolei Wang, Xinjie Huo, Jinhua Yu, Wanghan Xu, Wenlong Zhang, Lei Bai, Conghui He, et al. Earth-agent: Unlocking the full landscape of earth observation with agents. arXiv preprint arXiv:2509.23141, 2025. (Cited on page 3)

Bogdan Georgiev, Javier G’omez-Serrano, Terence Tao, and Adam Zsolt Wagner. Mathematical exploration and discovery at scale. ArXiv, abs/2511.02864, 2025. (Cited on page 1)

Clark Glymour. An outline of the history of methods of discovering causality. URL https://www.cmu.edu/dietrich/philosophy/docs/glymour/ an-outline-of-the-history-of-methods-of-discovering-causality.pdf. Accessed: 2026-01-29. (Cited on page 2)

Juraj Gottweis, Wei-Hung Weng, Alexander Daryin, Tao Tu, Anil Palepu, Petar Sirkovic, Artiom Myaskovsky, Felix Weissenberger, Keran Rong, Ryutaro Tanno, et al. Towards an ai co-scientist. arXiv preprint arXiv:2502.18864, 2025. (Cited on pages 1 and 2)

Sander Greenland, Judea Pearl, and James M Robins. Causal diagrams for epidemiologic research. Epidemiology, 10(1):37–48, 1999. (Cited on page 3)

Daya Guo, Dejian Yang, Haowei Zhang, Junxiao Song, Ruoyu Zhang, Runxin Xu, Qihao Zhu, Shirong Ma, Peiyi Wang, Xiao Bi, et al. Deepseek-r1: Incentivizing reasoning capability in llms via reinforcement learning. arXiv preprint arXiv:2501.12948, 2025. (Cited on page 1)

Patrik Hoyer, Dominik Janzing, Joris M Mooij, Jonas Peters, and Bernhard Scholkopf. Nonlinear causal¨ discovery with additive noise models. Advances in neural information processing systems, 21, 2008. (Cited on page 3)

Biwei Huang, Kun Zhang, Mingming Gong, and Clark Glymour. Causal discovery and forecasting in nonstationary environments with state-space models. In International conference on machine learning, pp. 2901–2910. Pmlr, 2019. (Cited on page 3)

Biwei Huang, Kun Zhang, Jiji Zhang, Joseph Ramsey, Ruben Sanchez-Romero, Clark Glymour, and Bernhard Scholkopf. Causal discovery from heterogeneous/nonstationary data. ¨ Journal of Machine Learning Research, 21(89):1–53, 2020. (Cited on page 3)

Kexin Huang, Ying Jin, Ryan Li, Michael Y Li, Emmanuel Candes, and Jure Leskovec. Automated hypothesis validation with agentic sequential falsifications. In ICML, 2025a. (Cited on page 3)

Yuxuan Huang, Yihang Chen, Haozheng Zhang, Kang Li, Huichi Zhou, Meng Fang, Linyi Yang, Xiaoguang Li, Lifeng Shang, Songcen Xu, et al. Deep research agents: A systematic examination and roadmap. arXiv preprint arXiv:2506.18096, 2025b. (Cited on page 3)

Krittanut Jiralerspong et al. Efficient causal graph discovery using large language models. arXiv preprint arXiv:2402.01207, 2024. (Cited on page 3)

Leslie Pack Kaelbling, Michael L Littman, and Anthony R Cassandra. Planning and acting in partially observable stochastic domains. Artificial intelligence, 101(1-2):99–134, 1998. (Cited on pages 2, 3 and 4)

Elahe Khatibi, Mahyar Abbasian, Zhongqi Yang, Iman Azimi, and Amir M Rahmani. Alcm: Autonomous llm-augmented causal discovery framework. arXiv preprint arXiv:2405.01744, 2024. (Cited on page 3)

Ilyes Khemakhem, Ricardo Monti, Diederik Kingma, and Aapo Hyvarinen. Ice-beem: Identifiable conditional energy-based deep models based on nonlinear ica. Conference and Workshop on Neural Information Processing Systems, 33:12768–12778, 2020. (Cited on page 1)

Thomas S. Kuhn and David Hawkins. The structure of scientific revolutions. American Journal of Physics, 31:554–555, 1963. (Cited on pages 2 and 3)

Robert Lange et al. Towards open-ended and sample-efficient program evolution. arXiv preprint arXiv:2509.19349, 2025a. (Cited on pages 3, 4 and 7)

Robert Tjarko Lange, Yuki Imajuku, and Edoardo Cetin. Shinkaevolve: Towards open-ended and sampleefficient program evolution. ArXiv, abs/2509.19349, 2025b. (Cited on pages 1 and 2)

Hongxin Li, Jingran Su, Yuntao Chen, Qing Li, and Zhao-Xiang Zhang. Sheetcopilot: Bringing software productivity to the next level through large language models. Advances in Neural Information Processing Systems, 36:4952–4984, 2023. (Cited on page 3)

Jin Li, Shoujin Wang, Qi Zhang, Feng Liu, Tongliang Liu, Longbing Cao, Shui Yu, and Fang Chen. Revealing multimodal causality with large language models. In The Thirty-ninth Annual Conference on Neural Information Processing Systems, 2025a. (Cited on page 3)

Jinyang Li, Nan Huo, Yan Gao, Jiayi Shi, Yingxiu Zhao, Ge Qu, Bowen Qin, Yurong Wu, Xiaodong Li, Chenhao Ma, et al. Are large language models ready for multi-turn tabular data analysis? In Forty-second International Conference on Machine Learning, 2025b. (Cited on page 3)

Junyi Li, Yongqiang Chen, Chenxi Liu, Qianyi Cai, Tongliang Liu, Bo Han, Kun Zhang, and Hui Xiong. Can large language models help experimental design for causal discovery? ArXiv, abs/2503.01139, 2025c. URL https://arxiv.org/abs/2503.01139. (Cited on page 1)

Long Li, Weiwen Xu, Jiayan Guo, Ruochen Zhao, Xingxuan Li, Yuqian Yuan, Boqiang Zhang, Yuming Jiang, Yifei Xin, Ronghao Dang, et al. Chain of ideas: Revolutionizing research via novel idea development with llm agents. arXiv preprint arXiv:2410.13185, 2024a. (Cited on page 3)

Michael Y Li, Vivek Vajipey, Noah D Goodman, and Emily B Fox. Critical: Critic automation with language models. arXiv preprint arXiv:2411.06590, 2024b. (Cited on page 3)

Peiwen Li, Xin Wang, Zeyang Zhang, Yuan Meng, Fang Shen, Yue Li, Jialong Wang, Yang Li, and Wenwu Zhu. Realtcd: Temporal causal discovery from interventional data with large language model. In Proceedings of the 33rd ACM International Conference on Information and Knowledge Management, pp. 4669–4677, 2024c. (Cited on page 3)

Xiu-Chuan Li and Tongliang Liu. Efficient and trustworthy causal discovery with latent variables and complex relations. In The Thirteenth International Conference on Learning Representations, 2025. (Cited on page 3)

Xiu-Chuan Li, Jun Wang, and Tongliang Liu. Recovery of causal graph involving latent variables via homologous surrogates. In The Thirteenth International Conference on Learning Representations, 2025d. (Cited on page 3)

Zhong-Zhi Li, Duzhen Zhang, Ming-Liang Zhang, Jiaxin Zhang, Zengyan Liu, Yuxuan Yao, Haotian Xu, Junhao Zheng, Pei-Jie Wang, Xiuyi Chen, et al. From system 1 to system 2: A survey of reasoning large language models. arXiv preprint arXiv:2502.17419, 2025e. (Cited on page 1)

Weixin Liang, Yuhui Zhang, Hancheng Cao, Binglu Wang, Daisy Yi Ding, Xinyu Yang, Kailas Vodrahalli, Siyu He, Daniel Scott Smith, Yian Yin, et al. Can large language models provide useful feedback on research papers? a large-scale empirical analysis. NEJM AI, 1(8):AIoa2400196, 2024. (Cited on page 3)

Chenxi Liu and Kun Kuang. Causal structure learning for latent intervened non-stationary data. In International Conference on Machine Learning, pp. 21756–21777. PMLR, 2023. (Cited on page 3)

Chenxi Liu, Yongqiang Chen, Tongliang Liu, Mingming Gong, James Cheng, Bo Han, and Kun Zhang. Discovery of the hidden world with large language models. In A. Globerson, L. Mackey, D. Belgrave, A. Fan, U. Paquet, J. Tomczak, and C. Zhang (eds.), Advances in Neural Information Processing Systems, volume 37, pp. 102307–102365. Curran Associates, Inc., 2024. URL https://proceedings.neurips.cc/paper\_files/paper/2024/file/ b99a07486702417d3b1bd64ec2cf74ad-Paper-Conference.pdf. (Cited on page 2)

Chenxi Liu, Yongqiang Chen, Tongliang Liu, Mingming Gong, James Cheng, Bo Han, and Kun Zhang. Discovering and reasoning of causality in the hidden world with large language models, 2025. URL https://arxiv.org/abs/2402.03941. (Cited on pages 3 and 6)

Stephanie Long, Alexandre Piche, Valentina Zantedeschi, Tibor Schuster, and Alexandre Drouin. Causal´ discovery with language models as imperfect experts. arXiv preprint arXiv:2307.02390, 2023. (Cited on page 3)

Chris Lu, Cong Lu, Robert Tjarko Lange, Jakob Foerster, Jeff Clune, and David Ha. The ai scientist: Towards fully automated open-ended scientific discovery. arXiv preprint arXiv:2408.06292, 2024. (Cited on pages 1 and 2)

Daniel Malinsky and Peter Spirtes. Learning the structure of a nonstationary vector autoregression. In The 22nd International Conference on Artificial Intelligence and Statistics, pp. 2986–2994. PMLR, 2019. (Cited on page 3)

Shubham Mandal et al. Artificially intelligent lab assistant for automated experimentation. Nature Communications, 16:1234, 2025. (Cited on page 3)

Ludovico Mitchener, Angela Yiu, Benjamin Chang, Mathieu Bourdenx, Tyler Nadolski, Arvis Sulovari, Eric C. Landsness, Daniel L. Barab´ asi, Siddharth Narayanan, Nicky Evans, Shriya Reddy, Martha S. Foiani,´ Aizad Kamal, Leah P. Shriver, Fang Cao, Asmamaw T. Wassie, Jon M. Laurent, Edwin Melville-Green, Mayk Caldas Ramos, Albert Bou, Kaleigh F. Roberts, Sladjana Zagorac, Timothy C. Orr, Miranda E. Orr, Kevin J. Zwezdaryk, Ali E. Ghareeb, Laurie McCoy, Bruna Gomes, Euan A Ashley, Karen E. Duff, Tonio Buonassisi, Tom Rainforth, Randall J. Bateman, Michael Skarlinski, Samuel G. Rodriques, Michaela M. Hinks, and Andrew D. White. Kosmos: An ai scientist for autonomous discovery. ArXiv, abs/2511.02824, 2025. (Cited on page 1)

Joris M Mooij, Sara Magliacane, and Tom Claassen. Joint causal inference from multiple contexts. Journal of machine learning research, 21(99):1–108, 2020. (Cited on page 3)

Alexander Novikov, Ngan V ˆ u, Marvin Eisenberger, Emilien Dupont, Po-Sen Huang, Adam Zsolt Wagner, ˜ Sergey Shirobokov, Borislav Kozlovskii, Francisco JR Ruiz, Abbas Mehrabian, et al. Alphaevolve: A coding agent for scientific and algorithmic discovery. arXiv preprint arXiv:2506.13131, 2025. (Cited on pages 1, 3, 4 and 7)

Judea Pearl. Causality. Cambridge university press, 2009. (Cited on pages 2 and 3)

Ronan Perry, Julius Von Kugelgen, and Bernhard Sch¨ olkopf. Causal discovery in heterogeneous environments¨ under the sparse mechanism shift hypothesis. Advances in Neural Information Processing Systems, 35: 10904–10917, 2022. (Cited on page 3)

Aske Plaat, Max van Duijn, Niki van Stein, Mike Preuss, Peter van der Putten, and Kees Joost Batenburg. Agentic large language models, a survey. arXiv preprint arXiv:2503.23037, 2025. (Cited on page 1)

Joaquin Quinonero-Candela, Masashi Sugiyama, Anton Schwaighofer, and Neil D Lawrence. Dataset shift in machine learning. Mit Press, 2008. (Cited on page 5)

Lo¨ıc M. Roch et al. Chemos: An orchestration software to democratize autonomous discovery. PLOS ONE, 15(4):e0229862, 2020. (Cited on page 3)

Bernardino Romera-Paredes et al. Mathematical discoveries from program search with large language models. Nature, 625:468–475, 2024. (Cited on page 3)

Asankhaya Sharma. Openevolve: an open-source evolutionary coding agent, 2025. URL https:// github.com/algorithmicsuperintelligence/openevolve. (Cited on pages 1 and 3)

C Shen, Zhengzhang Chen, Dongsheng Luo, Dongkuan Xu, Haifeng Chen, and Jingchao Ni. Exploring multi-modal integration with tool-augmented llm agents for precise causal discovery. arXiv preprint arXiv:2412.13667, 1(3), 2024. (Cited on page 3)

Ivaxi Sheth, Zhijing Jin, Bryan Wilder, Dominik Janzing, and Mario Fritz. Can llms propose instrumental variables for causal reasoning? In NeurIPS 2025 Workshop on CauScien: Uncovering Causality in Science. (Cited on page 3)

Shohei Shimizu, Patrik O Hoyer, Aapo Hyvarinen, Antti Kerminen, and Michael Jordan. A linear non-¨ gaussian acyclic model for causal discovery. Journal of Machine Learning Research, 7(10), 2006. (Cited on page 3)

Parshin Shojaee et al. Scientific equation discovery via programming with large language models. arXiv preprint arXiv:2404.18400, 2025. (Cited on page 3)

Peter Spirtes, Christopher Meek, and Thomas Richardson. Causal inference in the presence of latent variables and selection bias. In Proceedings of the Eleventh conference on Uncertainty in artificial intelligence, pp. 499–506, 1995. (Cited on page 3)

Peter Spirtes, Clark N Glymour, and Richard Scheines. Causation, prediction, and search. MIT press, 2000a. (Cited on page 3)

Peter Spirtes, Clark N Glymour, and Richard Scheines. Causation, prediction, and search. MIT press, 2000b. (Cited on page 2)

Kyle Swanson, Wesley Wu, Nash L Bulaong, John E Pak, and James Zou. The virtual lab of ai agents designs new sars-cov-2 nanobodies. Nature, 646(8085):716–723, 2025. (Cited on page 3)

Gary Tom, Stefan P Schmid, Sterling G Baird, Yang Cao, Kourosh Darvish, Han Hao, Stanley Lo, Sergio Pablo-Garc´ıa, Ella M Rajaonson, Marta Skreta, et al. Self-driving laboratories for chemistry and materials science. Chemical Reviews, 124(16):9633–9732, 2024. (Cited on page 3)

Daniel Truhn, Shekoofeh Azizi, James Zou, Leonor Cerda-Alberich, Faisal Mahmood, and Jakob Nikolas Kather. Artificial intelligence agents in cancer research and oncology. Nature Reviews Cancer, pp. 1–14, 2026. (Cited on page 3)

Siddharth Vashishtha et al. Causal ordering as a robust interface for integrating expert knowledge. Advances in Neural Information Processing Systems, 2023. (Cited on page 3)

Vishal Verma, Sawal Acharya, Devansh Bhardwaj, Samuel Simko, Yongjin Yang, Anahita Haghighat, Dominik Janzing, Mrinmaya Sachan, Bernhard Scholkopf, and Zhijing Jin. Causal AI scientist: Facilitating¨ causal data science with large language models. In NeurIPS 2025 Workshop on CauScien: Uncovering Causality in Science, 2025. URL https://openreview.net/forum?id=EDWTHMVOCj. (Cited on page 3)

W.A. Wallace. Causality and Scientific Explanation. Number v. 2 in Causality and Scientific Explanation. University Press of America, 1981. ISBN 9780819114815. (Cited on page 2)

Haiyuan Wan, Chen Yang, Junchi Yu, Meiqi Tu, Jiaxuan Lu, Di Yu, Jianbao Cao, Ben Gao, Jiaqing Xie, Aoran Wang, et al. Deepresearch arena: The first exam of llms’ research abilities via seminar-grounded tasks. AAAI, 2026. (Cited on page 1)

Qingyun Wang, Doug Downey, Heng Ji, and Tom Hope. Scimon: Scientific inspiration machines optimized for novelty. In Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), pp. 279–299, 2024. (Cited on page 3)

Xinyue Wang, Kun Zhou, Wenyi Wu, Har Simrat Singh, Fang Nan, Songyao Jin, Aryan Philip, Saloni Patnaik, Hou Zhu, Shivam Singh, et al. Causal-copilot: An autonomous causal analysis agent. arXiv preprint arXiv:2504.13263, 2025a. (Cited on page 3)

Yiping Wang, Shao-Rong Su, Zhiyuan Zeng, Eva Xu, Liliang Ren, Xinyu Yang, Zeyi Huang, Xuehai He, Luyao Ma, Baolin Peng, Hao Cheng, Pengcheng He, Weizhu Chen, Shuohang Wang, Simon Shaolei Du, and Yelong Shen. Thetaevolve: Test-time learning on open problems. ArXiv, abs/2511.23473, 2025b. (Cited on page 7)

David P. Woodruff, Vincent Cohen-Addad, Lalit Jain, Jieming Mao, Song Zuo, Mohammad Rez Bateni, Simina Branzei, Michael P. Brenner, Lin Chen, Ying Feng, Lance Fortnow, Gang Fu, Ziyi Guan, Zahraˆ Hadizadeh, Mohammad Taghi Hajiaghayi, Mahdi JafariRaviz, Adel Javanmard, S. KarthikC., Ken ichi Kawarabayashi, Ravi Kumar, Silvio Lattanzi, Euiwoong Lee, Yi Li, Ioannis Panageas, Dimitris Paparas, Benjamin Przybocki, Bernardo Subercaseaux, Ola Svensson, Shayan Taherijam, Xuan Wu, Eylon Yogev, Morteza Zadimoghaddam, Samson Zhou, and Vahab S. Mirrokni. Accelerating scientific research with gemini: Case studies and common techniques. ArXiv, abs/2602.03837, 2026. (Cited on page 1)

xAI. Grok 4.1 fast and agent tools api, 2025. URL https://x.ai/news/grok-4-1-fast. Accessed: 2026-02-10. (Cited on page 7)

Yutaro Yamada, Robert Tjarko Lange, Cong Lu, Shengran Hu, Chris Lu, Jakob Foerster, Jeff Clune, and David Ha. The ai scientist-v2: Workshop-level automated scientific discovery via agentic tree search. arXiv preprint arXiv:2504.08066, 2025. (Cited on pages 1 and 2)

Cheng Yang, Jiaxuan Lu, Haiyuan Wan, Junchi Yu, and Feiwei Qin. From what to why: A multi-agent system for evidence-based chemical reaction condition reasoning. ICLR, 2026. (Cited on page 3)

Karren Yang, Abigail Katcoff, and Caroline Uhler. Characterizing and learning equivalence classes of causal dags under interventions. In International Conference on Machine Learning, pp. 5541–5550. PMLR, 2018. (Cited on page 3)

Zonglin Yang, Xinya Du, Junxian Li, Jie Zheng, Soujanya Poria, and Erik Cambria. Large language models for automated open-domain scientific hypotheses discovery. In Findings of the Association for Computational Linguistics: ACL 2024, pp. 13545–13565, 2024. (Cited on page 3)

Zonglin Yang, Wanhao Liu, Ben Gao, Tong Xie, Yuqiang Li, Wanli Ouyang, Soujanya Poria, Erik Cambria, and Dongzhan Zhou. Moose-chem: Large language models for rediscovering unseen chemistry scientific hypotheses. In ICLR, 2025. (Cited on page 3)

Liangyu Zha, Junlin Zhou, Liyao Li, Rui Wang, Qingyi Huang, Saisai Yang, Jing Yuan, Changbao Su, Xiang Li, Aofeng Su, et al. Tablegpt: Towards unifying tables, nature language and commands into one gpt. arXiv preprint arXiv:2307.08674, 2023. (Cited on page 3)

Kun Zhang and Aapo Hyvarinen. On the identifiability of the post-nonlinear causal model. arXiv preprint arXiv:1205.2599, 2012. (Cited on page 3)

Wenqi Zhang, Yongliang Shen, Weiming Lu, and Yueting Zhuang. Data-copilot: Bridging billions of data and humans with autonomous workflow. arXiv preprint arXiv:2306.07209, 2023. (Cited on page 3)

Tianshi ZHENG, Zheye Deng, Hong Ting Tsang, Weiqi Wang, Jiaxin Bai, Zihao Wang, and Yangqiu Song. From automation to autonomy: A survey on large language models in scientific discovery. ArXiv, abs/2505.13259, 2025. (Cited on page 1)

Qing Zhu, Fei Zhang, Yan Huang, Hengyu Xiao, LuYuan Zhao, XuChun Zhang, Tao Song, XinSheng Tang, Xiang Li, Guo He, et al. An all-round ai-chemist with a scientific mind. National Science Review, 9(10): nwac190, 2022. (Cited on page 3)

## LLM USE STATEMENT

From the research side, this work studies the use of LLMs for automated scientific discovery. From the paper writing side, we use LLMs to assist with improving the writing of this work.

## ETHICS STATEMENT

We study using LLMs to automate scientific discovery that will benefit the whole humanity and society. This work does not involve human subjects or personally identifiable information beyond public benchmarks used under their licenses.

## A ADDITIONAL TECHNICAL DETAILS

## A.1 NOTATION

Table 2: Notation used in the formulation and theorems.  
![](images/2880cfdf181dbf31756c6c8906b45150af733d7ef04224dd2420ee55b40acdb3.jpg)

## A.2 RANDOM VARIABLE, SPACE, AND REALIZATION (TO AVOID NOTATION CONFUSION)

We use the following (standard) convention.

(i) Hypothesis space. Θ is a set that contains all candidate scientific-knowledge hypotheses.

(ii) True but unknown instance. The real world is governed by a fixed but unknown θ<sup>⋆</sup> ∈ Θ.

(iii) Bayesian view (optional but convenient). A Bayesian agent models uncertainty by treating θ<sup>⋆</sup> as a realization of a latent random variable Θ<sub>sci</sub> with prior µ<sub>0</sub>, i.e. Θ<sub>sci</sub> ∼ µ<sub>0</sub> and θ<sup>⋆</sup> is one draw from it. The belief b<sub>t</sub> is simply the posterior distribution of Θ<sub>sci</sub> after seeing history h<sub>t</sub>.

(iv) Does scientific knowledge change across environments? In our formulation, the underlying scientific knowledge θ<sup>⋆</sup> is static across rounds. Different environments e ∈ E represent different evaluation/deployment protocols (distribution shifts, constraint changes, measurement noise, private vs public tests, etc.). Formally,

![](images/09c2cf8aa56d6c8eb5791b2879e31a551f33d25699320e00e58d9894c84fc7c5.jpg)  
Figure 2: The iterative scientific discovery loop. Left: Conceptual flow of the agent. The agent maintains a scratchpad memory (m), proposes a program (p), and observes the outcome (y) which is constrained by the unknown world state (θ<sub>sci</sub>). The outcome feeds back into the memory for the next step. Right: The diagram illustrates how the AI Scientist probes the unknown world state θ<sub>sci</sub>. By proposing a candidate program p<sub>t</sub>, the agent triggers an experiment yielding outcome y<sub>t</sub>. This observation provides evidence about θ<sub>sci</sub>, which is integrated into the agent’s scratchpad memory m<sub>t+1</sub>. Over time steps t, t + 1, . . . , this recurrent process allows the agent to navigate the performance landscape and converge towards optimal programs despite the static but unknown nature of θ<sub>sci</sub>.

environments affect either the true performance map F<sub>e</sub>(·; θ) and/or the observation kernel P<sub>e</sub>(· | p, θ), while θ<sup>⋆</sup> itself remains the same hidden instance.

## A.3 EVALUATOR AS AN OBSERVATION MODEL (COVERS DETERMINISTIC AND STOCHASTIC EVALUATORS)

Fix an environment e ∈ E. When the agent evaluates program p, it receives an observation y ∈ Y drawn from

![](images/57f640624302ca1fd23cf671a38d5fbb3de7a34ebd759cdfd8928b6f93e7db28.jpg)

where P<sub>e</sub>(· | p, θ) is a conditional distribution on Y.

Deterministic evaluator. A deterministic evaluator is the special case where there exists a function g<sub>e</sub> such that

![](images/c869ae23de58cfb3052eb6d148d3df2cd3f7f66937dd319a450c8ea93eed63f3.jpg)

In many program-evolution settings, the evaluator is designed to deterministically check validity and compute an objective score (e.g., via a verifier and a scoring routine).

Stochastic/noisy evaluator. A common instantiation is additive noise:

![](images/e5dba1a15198e545a6bc1e32ae2f3c71292b9e5f9cef0f1d57b0c1f6ef1abd91.jpg)

but our proofs only rely on the specific Gaussian form in Theorem 1.

## A.4 BELIEF AND BAYES UPDATE: KERNEL FORM AND UNDERGRADUATE-FRIENDLY SPECIAL CASES

Let h<sub>t</sub> = {(p<sub>0</sub>, y<sub>0</sub>), . . . , (p<sub>t−1</sub>, y<sub>t−1</sub>)} be the history. The Bayesian belief (posterior) is

![](images/fe763b3498c8cc24aea0da8c603041382616518cd4c81d87d6f82e930a363062.jpg)

General Bayes update (kernel form). After choosing p<sub>t</sub> and observing y<sub>t</sub> in e<sub>src</sub>, the posterior is

![](images/7487b683111f3430fa21f872ab6679b6ecc89101129125cd372682c51c746603.jpg)

(3)

Finite hypothesis space (sum form). If Θ = {θ<sub>1</sub>, . . . , θ<sub>N</sub> } is finite and the likelihood has a pmf P<sub>e</sub> (y<sub>t</sub> | p<sub>t</sub>, θ<sub>i</sub>), then

![](images/9a358329e9278bab21021a849049c6c86a41bd86d9d64458cb63f9d516427ea7.jpg)

Continuous hypothesis space (density form). If P<sub>e</sub> (dy | p, θ) has a density p<sub>e</sub> (y | p, θ), then

![](images/c7919a6ed0c5a7f8c38de271e7576b11aeb8889a7e4825991ae7c1d604fe95aa.jpg)

Deterministic evaluator (indicator/filter form). If y = g<sub>e</sub> (p; θ) deterministically, then the update becomes

![](images/c87bbade0bf4905d72f6b9673550f12ab738d6edf684395004251dde44cb78e1.jpg)

i.e. the posterior is the prior restricted to hypotheses consistent with the observed outcome.

## B PROOF OF THEOREM 3.2 (STATIC SAMPLE-EFFICIENCY GAP)

Throughout this section we fix a single static environment (drop e from notation), and assume P = {p<sub>1</sub>, . . . , p<sub>K</sub> } is finite.

## B.1 PROTOCOL AND PERFORMANCE CRITERION

Experiment–then–commit protocol. A policy π interacts for T rounds. At each round t = 0, . . . , T − 1 it selects a program p ∈ P (possibly randomized) based on the past history h , then observes y ∈ <sup>R</sup>. After T evaluations it outputs a final recommendation pˆ ∈ P.

Simple regret. Let f(p) denote the true mean performance of program p in this environment. Define the (random) simple regret

![](images/55e528f08b015dcb19ded2e2ce35862838ae07417d7d605bd3e6978ba78fa01e.jpg)

(4)

(ϵ, δ)-correctness (uniform). Fix ϵ > 0 and δ ∈ (0, 1). We say a policy π is (ϵ, δ)-correct uniformly on a hypothesis class H if for every instance in H,

![](images/ac86d70da009c6325a40ccdb4e845e37263f4318250e741f2f2303e90ddc212f.jpg)

“Uniformly” means the guarantee must hold for all instances in the class, not only on average.

## B.2 TWO HYPOTHESIS CLASSES

(1) Structured (causal/scientific) linear class. Each program p has a known feature vector x<sub>p</sub> ∈ <sup>Rd</sup> with ∥x<sub>p</sub>∥<sub>2</sub> ≤ 1. The unknown instance is a weight vector w<sup>⋆</sup> ∈ <sup>Rd</sup> and

![](images/c73a1f3a5e703f7949b2df4055ecf11f5fccf87a3ba72d6e38f9d82fc879e345.jpg)

(5)

Observations follow a Gaussian noise model

![](images/13c7e43cd45065efebfeb2890e7dac843a1619b5400eff7e7098874793aacaf9.jpg)

(6)

Assume there exist d basis programs p<sup>(1)</sup>, . . . , p<sup>(d)</sup> whose feature vectors are the standard basis:

![](images/72a1031c52683bb0badafab41bc157395315b92485be6b3fb4e1d0d627273a8d.jpg)

(7)

(2) Unstructured black-box class (baseline). The unknown instance is an arbitrary vector of means

![](images/112e066212e250a9de371184dfd097863092d636dd7a3a7ef48a0e76f101434d.jpg)

and observations are

![](images/c2be1803399cdb596ca51e17f7e5b1b0acab2ab8c243baff8382220e8ad6a15a.jpg)

(8)

where I<sub>t</sub> ∈ {1, . . . , K} is the index of the chosen program p<sub>t</sub> = p<sub>I</sub> . Crucially, there is no assumed relation between µ<sub>i</sub> and µ<sub>j</sub> for i ̸= j.

## B.3 FORMAL STATEMENT AND PROOF

Theorem B.1 (Formal version of Theorem 3.2). Fix ϵ > 0 and δ ∈ (0, 1/4).

1. (Upper bound under the structured linear class). Under equation 5–equation 7 and equation 6, there exists a policy π<sub>lin</sub> such that

![](images/59414c161d8e4fd5a99b9a0dcf3dafb6f588402a221c7d32d5726c404a796f21.jpg)

2. (Lower bound for the unstructured black-box class). For the black-box class equation 8, any policy that is (ϵ, δ)-correct uniformly for all µ ∈ <sup>RK</sup> must satisfy

![](images/ded15bf3d4f2dd01e87af16bb494040d403fa00dd6ebf55a8f637075760f73e5.jpg)

Proof. We prove the two parts separately.

Part (1): constructive upper bound (estimate w<sup>⋆</sup> then commit). Evaluate each basis program p<sup>(i)</sup> exactly (i)

![](images/403b9b30217d0388ffb17b344c24fc1c4a41264c5bdb484e9ab8a68d2edd1cfa.jpg)

By equation 5–equation 7, f(p<sup>(i)</sup>) = w<sup>⋆</sup>. By equation 6, wˆ<sub>i</sub> ∼ N (w<sup>⋆</sup>, σ<sup>2</sup>/n) and these coordinates are independent.

Define for any program p:

![](images/e4b7a26f33a2ddf45cc3e5e814dc8f529840b1ace61ef5e943c41f07f847f37d.jpg)

Then

![](images/a32b68d68d3789e0e53ddaea31686d726861033cb833fe69149f9e8a9fb5d75b.jpg)

so since ∥x<sub>p</sub>∥<sub>2</sub> ≤ 1,

![](images/6ade2bbb8a947e9dd2d559c6186515f069fa6b1f95db0ed68d7527f9c9b0f19e.jpg)

Union bound over K programs gives

![](images/753a333fd27f15b4924a2a73a09a97d8d02da2da725796b316c5313cdeff7ddf.jpg)

Choose

![](images/4ec49db0a9326c067e3e3895c8b93ee117583b78cefe9e32bf9c385f4eba851c.jpg)

so that with probability at least 1 − δ we have max<sub>p</sub> |f (p) − f (p)| ≤ ϵ.

Now output pˆ := arg max<sub>p∈P</sub> f(p). Let p<sup>⋆</sup> := arg max<sub>p</sub> f(p). On the above high-probability event,

![](images/90565e0cf89a70edc3ef59950206ff94c6a1c7f7f7cde1c170134a6ded0cb394.jpg)

Thus Pr(SR<sub>T</sub> ≤ 2ϵ) ≥ 1 − δ for T = nd as stated.

Part (2): lower bound for the black-box class. We construct K hard instances and lower bound any uniformly (ϵ, δ)-correct policy.

Let the programs be p<sub>1</sub>, . . . , p<sub>K</sub>. Define a base instance µ<sup>(0)</sup> ∈ <sup>RK</sup>:

![](images/7c168ad8df2a6a73541f428cab80f13334391dfa670d61e50969a452685d5c50.jpg)

For each i ∈ {2, . . . , K}, define an alternative instance µ<sup>(i)</sup>:

![](images/237d9815ba41a323a94eaa1f5f57726d7b77878935d2923dd90aa54beac1ef73.jpg)

Under µ<sup>(0)</sup>, the unique best program is p<sub>1</sub>, and choosing any p<sub>i</sub> with i ≥ 2 incurs regret 2ϵ > ϵ. Under µ<sup>(i)</sup>, the unique best program is p<sub>i</sub>, and choosing p<sub>1</sub> incurs regret 2ϵ > ϵ.

Let P<sub>0</sub> be the distribution of the full transcript T := (p<sub>0:T −1</sub>, y<sub>0:T −1</sub>, pˆ) under µ<sup>(0)</sup>, and P<sub>i</sub> the analogous distribution under µ<sup>(i)</sup>. Uniform (ϵ, δ)-correctness implies

![](images/a271ff07017997ed64736b0ba064c4e54d814902ce03fd93e1583c59946b0588.jpg)

Step 1: a KL lower bound from an event. For any event A and distributions P, Q, one has

![](images/700fc4c47201adf0371ab3926561a1a7c481ad7c931425215b228fb864da9932.jpg)

Apply it with A = {pˆ = p<sub>1</sub>}, P = P<sub>0</sub>, Q = P<sub>i</sub>. Let p := P<sub>0</sub>(A) ≥ 1 − δ and q := P<sub>i</sub>(A) ≤ δ. For δ ∈ (0, 1/4) this yields

![](images/479a4a300893319273bae992800fb05108128a75a7b42103ab716e9b53520e61.jpg)

(9)

Step 2: compute KL(P<sub>0</sub>∥P<sub>i</sub>) via number of pulls of arm i. Under µ<sup>(0)</sup> and µ<sup>(i)</sup>, the policy is identical; only observations when playing p<sub>i</sub> differ:

![](images/b122dc2e1059a60f18914f089459e9f4d96b75bfdeed84bc714f27e90d825ae4.jpg)

For Gaussians with equal variance, KL(N (m<sub>0</sub>, σ<sup>2</sup>)∥N (m<sub>1</sub>, σ<sup>2</sup>)) = <sup>(m0−m1)2</sup><sub>2</sub> , so each pull of p<sub>i</sub> contributes KL (4ϵ)<sup>2</sup> 2σ<sup>2</sup> = 8ϵ<sup>2</sup> <sub>σ2</sub> .

Let N<sub>i</sub> be the (random) number of times p<sub>i</sub> is evaluated in T rounds. Additivity of log-likelihood ratios over independent Gaussian samples yields

![](images/ee588c34f6fe154f8c1a5e626b48ddac5966da1a8fdaa0983450e3ac8498aad8.jpg)

(10)

Step 3: conclude the lower bound on T . Combine equation 9 and equation 10:

![](images/926145056e490f491218cf12a3335ffea50527361115647645c378c1993e4de6.jpg)

Summing over i = 2, . . . , K gives

![](images/45ad7c6a2ef840664becfc7881c8ceee064513a4e8165aa0f8d96405d40d083d.jpg)

This completes the proof.

Remark (deterministic evaluator). If σ = 0, the structured linear class can recover w<sup>⋆</sup> exactly from d basis evaluations and achieve SR<sub>T</sub> = 0, while in the unstructured black-box class a uniform worst-case guarantee requires evaluating all K programs at least once.

Reference for the black-box lower bound. The above is a standard change-of-measure/KL argument for best-arm identification in K-armed Gaussian bandits (e.g., see classical treatments of best-arm identification lower bounds).

## C PROOF OF THEOREM 3.3 (NON-IDENTIFIABILITY UNDER ENVIRONMENT SHIFTS)

## C.1 SETUP: SOURCE INTERACTION, TARGET EVALUATION, AND TARGET REGRET

The agent can only interact with the source environment e<sub>src</sub>:

![](images/e2d4d6511c6a3ff56de54c915d125502f946fadd0c3f3093702d9a527e5d967e.jpg)

After T rounds it outputs a final program pˆ. Performance is judged in a target environment e<sub>tgt</sub> via F<sub>etgt</sub> (p; θ<sup>⋆</sup>). Define the target (simple) regret:

![](images/eac84c1831c03fe48e6922e3a88c01cc226cf4efb8f5764c5e1abdc7b239518a.jpg)

## C.2 FORMAL STATEMENT AND PROOF

Theorem C.1 (Non-identifiability barrier under shifts). Fix e<sub>src</sub>, e<sub>tgt</sub> ∈ E. Assume there exist two hypotheses θ<sub>0</sub>, θ<sub>1</sub> ∈ Θ such that:

![](images/b7b32e04bdcc08228ffb550393672e329f58e0a3d2fa35165fa93af8e9f843fc.jpg)

(11)

![](images/e44f90020c52332547a50c231f2599eef55eae3a4411482d1d08f1d8bb0eb142.jpg)

(12)

![](images/04a62724096a3a47da335cf915f4917406c843e67a2b95f7f35a251cc077bb41.jpg)

![](images/b85c575b8336d14fbd431f7cca6ed4c5ec608bc5575fad95d518528d73fbd64b.jpg)

(13)

Then for any policy π that can interact only with e<sub>src</sub>, there exists i ∈ {0, 1} such that for every budget T ,

![](images/7471df9cff8a20ab04b7fee333d864f2b31863e49185a78a762a16dec36405cd.jpg)

This impossibility holds whether the evaluator is stochastic or deterministic, since equation 11 is stated at the level of the full observation model P<sub>esrc</sub> .

Proof. Let <sup>P</sup><sub>i</sub> be the distribution over the full transcript

![](images/fd8c2c4e9199a38243bc5cc560ce594fa80e8df2f8f0a5c94bba4afa030b5f77.jpg)

when the true hypothesis is θ<sub>i</sub> and interaction is only with e<sub>src</sub>.

By equation 11, for any history and any chosen action p<sub>t</sub>, the conditional distribution of y<sub>t</sub> is identical under θ and θ . By induction on t, the entire transcript distribution is identical:

![](images/a750f11d35d36fc0799e3ec0ffd1f197d2b21a4eefe58b427709b37d54b6a32a.jpg)

In particular, the marginal distribution of the final output pˆ is the same under θ and θ . Let this common distribution be denoted by Q on P.

Now consider the expected target regret under θ<sub>0</sub>: by equation 13, any output pˆ ̸= p<sub>0</sub> incurs regret at least ∆ under θ<sub>0</sub>:

![](images/86efe11dcaaa6a41ffa7a418fff6cfedae4fa15a236e659bac86aaef30976e29.jpg)

Taking expectation w.r.t. Q yields

![](images/c5e540406e1c80e2a6c7430f1a174237120b6f85a9bb07b7107ec39055d5b943.jpg)

Similarly,

![](images/997f4e24729f8d78f3f0ca15d80732c2ea060daf48db7908e9687984d2e687f3.jpg)

Since Q(ˆp = p<sub>0</sub>) + Q(ˆp = p<sub>1</sub>) ≤ 1, at least one of these probabilities is at most 1/2, so at least one of the two expected regrets is at least ∆/2:

![](images/d475748d48728e749bc7bc9dd73954ed6d6d3f08ff83c92aceab080353ce6de5.jpg)

This proves the claim.

## C.3 CONCRETE EXAMPLES SATISFYING THE CONDITIONS

We give two illustrative examples where source data cannot distinguish two hypotheses, yet the target-optimal decision differs.

Example 1: public test vs private (distribution shift / shortcut feature). Let θ ∈ {θ<sub>0</sub>, θ<sub>1</sub>} encode which feature is truly stable/causal. Programs correspond to two model families: p<sub>0</sub> uses a stable causal feature; p<sub>1</sub> uses a shortcut feature. In the source environment (public benchmark), the shortcut feature is perfectly correlated with labels, so both hypotheses yield the same evaluator distribution for every program, satisfying equation 11. In the target environment (deployment/private), the shortcut correlation breaks: under θ<sub>0</sub>, p<sub>0</sub> is uniquely optimal; under θ<sub>1</sub>, p<sub>1</sub> is uniquely optimal, with margin ∆, satisfying equation 13. No amount of interaction with e can identify which world holds.

Table 3: Mathematical definitions of auxiliary metrics across tasks. All metrics are deterministic outcomelevel functionals of the program outputs. For subset-defined metrics (e.g., large circle margin), if the index set is empty, the metric value is defined as 0.  
![](images/da3a280e7b7f72f569638843d9556c233f5efc00145182fda95ca2497c6e3c66.jpg)

Example 2: relaxed verification (slack) vs exact verification (constraint shift). In combinatorial optimization, it is common to evaluate candidate programs using a relaxed verifier (e.g., allowing numerical slack), then validate with an exact verifier. For instance, in circle packing, one may verify non-overlap with a numerical slack such as 10<sup>−6</sup>, and later validate with an exact checker; converting a relaxed-feasible solution into an exact-feasible one may require tiny but nonzero modifications, and rankings can change when switching verifiers. This is explicitly discussed in the context of circle packing verification with slack vs exact validation. The source environment e<sub>src</sub> can correspond to the relaxed evaluator, while the target environment e<sub>tgt</sub> corresponds to the exact evaluator. Then two hypotheses θ<sub>0</sub>, θ<sub>1</sub> can be constructed so that they are indistinguishable under the relaxed evaluator for all queried programs, yet the exact evaluator reverses which program is truly best (with gap ∆), matching Theorem C.1.

## D MORE DETAILS ON OUTCOME-LEVEL FACTORS