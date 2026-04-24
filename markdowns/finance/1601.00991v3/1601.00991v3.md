# 101 Formulaic Alphas

Zura Kakushadze §†1

Quantigic® Solutions LLC,2 1127 High Ridge Road, #135, Stamford, CT 06905

Free University of Tbilisi, Business School & School of Physics 240, David Agmashenebeli Alley, Tbilisi, 0159, Georgia

December 9, 2015

“There are two kinds of people in this world: Those seeking happiness, and bullfighters.” (Zura Kakushadze, ca. early ’90s)3

## Abstract

We present explicit formulas – that are also computer code – for 101 real-life quantitative trading alphas. Their average holding period approximately ranges 0.6-6.4 days. The average pair-wise correlation of these alphas is low, 15.9%. The returns are strongly correlated with volatility, but have no significant dependence on turnover, directly confirming an earlier result based on a more indirect empirical analysis. We further find empirically that turnover has poor explanatory power for alpha correlations.

## 1. Introduction

There are two complementary – and in some sense even competing – trends in modern quantitative trading. On the one hand, more and more market participants (e.g., quantitative traders, inter alia) employ sophisticated quantitative techniques to mine alphas.4 This results in ever fainter and more ephemeral alphas. On the other hand, technological advances allow to essentially automate (much of) the alpha harvesting process. This yields an ever increasing number of alphas, whose count can be in hundreds of thousands and even millions, and with the exponentially increasing progress in this field will likely be in billions before we know it…

This proliferation of alphas – albeit mostly faint and ephemeral – allows combining them in a sophisticated fashion to arrive at a unified “mega-alpha”. It is then this “mega-alpha” that is actually traded – as opposed to trading individual alphas – with a bonus of automatic internal crossing of trades (and thereby crucial-for-profitability savings on trading costs, etc.), alpha portfolio diversification (which hedges against any subset of alphas going bust in any given time period), and so on. One of the challenges in combining alphas is the usual “too many variables, too few observations” dilemma. Thus, the alpha sample covariance matrix is badly singular.

Also, naturally, quantitative trading is a secretive field and data and other information from practitioners is not readily available. This inadvertently creates an enigma around modern quant trading. E.g., with such a large number of alphas, are they not highly correlated with each other? What do these alphas look like? Are they mostly based on price and volume data, mean-reversion, momentum, etc.? How do alpha returns depend on volatility, turnover, etc.?

In a previous paper [Kakushadze and Tulchinsky, 2015] took a step in demystifying the realm of modern quantitative trading by studying some empirical properties of 4,000 real-life alphas. In this paper we take another step and present explicit formulas – that are also computer code – for 101 real-life quant trading alphas. Our formulaic alphas – albeit most are not necessarily all that “simple” – serve a purpose of giving the reader a glimpse into what some of the simpler real-life alphas look like.5 It also enables the reader to replicate and test these alphas on historical data and do new research and other empirical analyses. Hopefully, it further inspires (young) researchers to come up with new ideas and create their own alphas.

We discuss some general features of our formulaic alphas in Section 2. These alphas are mostly “price-volume” (daily close-to-close returns, open, close, high, low, volume and vwap) based, albeit “fundamental” input is used in some of the alphas, including one alpha utilizing market cap, and a number of alphas employing some kind of a binary industry classification such as GICS, BICS, NAICS, SIC, etc., which are used to industry-neutralize various quantities.6

We discuss empirical properties of our alphas in Section 3 based on data for individual alpha Sharpe ratio, turnover and cents-per-share, and also on a sample covariance matrix. The average holding period approximately ranges from 0.6 to 6.4 days. The average (median) pairwise correlation of these alphas is low, 15.9% (14.3%). The returns  are strongly correlated with the volatility , and as in [Kakushadze and Tulchinsky, 2015] we find an empirical scaling

$$
R \sim V ^ { X }\tag{1}
$$

with $X \approx 0 . 7 6$ for our 101 alphas. Furthermore, we find that the returns have no significant dependence on the turnover . This is a direct confirmation of an earlier result by [Kakushadze and Tulchinsky, 2015], which is based on a more indirect empirical analysis.7

We further find empirically that the turnover per se has poor explanatory power for alpha correlations. This is not to say that the turnover does not add value in, e.g., modeling the covariance matrix via a factor model.8 A more precise statement is that pair-wise correlations $\psi _ { i j }$ of the alphas (,  = 1, … ,  label the  alphas,  ≠ ) are not highly correlated with the product ln $( \tau _ { i } )$ ln $( \tau _ { j } )$ , where $\tau _ { i } = T _ { i } / \mu ,$ , and $\mu$ is an a priori arbitrary normalization constant.9

We briefly conclude in Section 4. Appendix A contains our formulaic alphas with definitions of the functions, operators and input data used therein. Appendix B contains some legalese.

## 2. Formulaic Alphas

In this section we describe some general features of our 101 formulaic alphas. The alphas are proprietary to WorldQuant LLC and are used here with its express permission. We provide as many details as we possibly can within the constraints imposed by the proprietary nature of the alphas. The formulaic expressions – that are also computer code – are given in Appendix A.

Very coarsely, one can think of alpha signals as based on mean-reversion or momentum.10 A mean-reversion alpha has a sign opposite to the return on which it is based. E.g., a simple mean-reversion alpha is given by

$$
- \mathrm { l n } ( \mathrm { t o d a y } ^ { \prime } s \mathrm { o p e n } / \mathrm { y e s t e r d a y } ^ { \prime } s \mathrm { c l o s e } )\tag{2}
$$

Here yesterday’s close is adjusted for any splits and dividends if the ex-date is today. The idea (or hope) here is that the stock will mean-revert and give back part of the gains (if today’s open is higher than yesterday’s close) or recoup part of the losses (if today’s open is lower than yesterday’s close). This is a so-called “delay-0” alpha. Generally, “delay-0” means that the time of some data (e.g., a price) used in the alpha coincides with the time during which the alpha is intended to be traded. E.g., the alpha (2) would ideally be traded at or, more realistically, as close as possible to today’s open. More broadly, this can be some other time, e.g., the close.11

A simple example of a momentum alpha is given by

$$
\ln ( \mathrm { y e s t e r d a y ^ { \prime } s c l o s e / y e s t e r d a y ^ { \prime } s o p e n ) }\tag{3}
$$

Here it makes no difference if the prices are adjusted or not. The idea (or hope) here is that if the stock ran up (slid down) yesterday, the trend will continue today and the gains (losses) will be further increased. This is a so-called “delay-1” alpha if the intent is to trade it today (e.g., starting at the open).12 Generally, “delay-1” means that the alpha is traded on the day subsequent to the date of the most recent data used in computing it. A “delay-2” alpha is defined similarly, with 2 counting the number of days by which the data used is out-of-sample.

In complex alphas elements of mean-reversion and momentum can be mixed, making them less distinct in this regard. However, one can think of smaller building blocks of such alphas as being based on mean-reversion or momentum. For instance, Alpha#101 in Appendix A is a delay-1 momentum alpha: if the stock runs up intraday (i.e., close > open and high > low), the next day one takes a long position in the stock. On the other hand, Alpha#42 in Appendix A essentially is a delay-0 mean-reversion alpha: rank(vwap – close) is lower if a stock runs up in the second half of the day (close > vwap)13 as opposed to sliding down (close < vwap). The denominator weights down richer stocks. The “contrarian” position is taken close to the close.

## 3. Data and Empirical Properties of Alphas

In this section we describe empirical properties of our formulaic alphas based on data proprietary to WorldQuant LLC, which is used here with its express permission. We provide as many details as possible within the constraints of the proprietary nature of this dataset.

For our alphas we take the annualized daily Sharpe ratio 3, daily turnover , and cents-pershare 4. Let us label our alphas by the index $i ( i = 1 , \dots , N )$ , where $N = 1 0 1$ is the number of alphas. For each alpha, $S _ { i } , T _ { i }$ and $C _ { i }$ are defined via

$$
S _ { i } = \sqrt { 2 5 2 } ~ \frac { P _ { i } } { V _ { i } }\tag{4}
$$

$$
T _ { i } = \frac { D _ { i } } { I _ { i } }\tag{5}
$$

$$
C _ { i } = 1 0 0 \frac { P _ { i } } { Q _ { i } }\tag{6}
$$

Here: $P _ { i }$ is the average daily P&L (in dollars); $V _ { i }$ is the daily portfolio volatility; $Q _ { i }$ is the average daily shares traded (buys plus sells) by the -th alpha; $D _ { i }$ is the average daily dollar volume traded; and $I _ { i }$ is the total dollar investment in said alpha (the actual long plus short positions, without leverage). More precisely, the principal of $I _ { i }$ is constant; however, $I _ { i }$ fluctuates due to the daily P&L. So, both $D _ { i }$ and $I _ { i }$ are adjusted accordingly (such that $I _ { i }$ is constant) in Equation (4). The period of time over which this data is collected is Jan 4, 2010-Dec 31, 2013. For the same period we also take the sample covariance matrix $Y _ { i j }$ of the realized daily returns for our alphas. The number of observations in the time series is 1,006, and $Y _ { i j }$ is nonsingular. From $Y _ { i j }$ we read off the daily return volatility $\sigma _ { i } ^ { 2 } = Y _ { i i }$ and the correlation matrix ${ \varPsi _ { i j } } = { \varUpsilon _ { i j } } / { \sigma _ { i } \sigma _ { j } }$ (where $\psi _ { i i } = 1 )$ . Note that $V _ { i } = \sigma _ { i } I _ { i } .$ , and the average14 daily return is given by $R _ { i } = P _ { i } / I _ { i }$

Table 1 and Figure 1 summarize the data for the annualized Sharpe ratio $S _ { i } ,$ daily turnover, $T _ { i } ,$ , average holding period $1 / T _ { i } ,$ cents-per-share $C _ { i } ,$ daily return volatility $\sigma _ { i } ,$ , annualized average daily return $\tilde { R } _ { i } = 2 5 2 R _ { i }$ , and $N ( N - 1 ) / 2$ pair-wise correlations $\psi _ { i j }$ with $i > j$

## 3.1. Return v. Volatility & Turnover

We run two cross-sectional regressions, both with the intercept, of ln $( R _ { i } )$ over i) ln $( \sigma _ { i } )$ as the sole explanatory variable, and ii) over ln(=) and ln $( T _ { i } )$ . The results are summarized in Tables 2 and 3. Consistently with [Kakushadze and Tulchinsky, 2015], we have no statistically

significant dependence on the turnover $T _ { i }$ here, while the average daily return $R _ { i }$ is strongly correlated with the daily return volatility $\sigma _ { i }$ and we have the scaling property (1) with $X \approx 0 . 7 6$

## 3.2. Does Turnover Explain Correlations?

If we draw a parallel between alphas and stocks, then alpha turnover is analogous to stock liquidity, which is typically measured via an average daily dollar volume (ADDV).15 Log of ADDV is routinely used as a style risk factor16 in multifactor risk models17 for approximating stock portfolio covariance matrix structure, whose chief goal is to model the off-diagonal elements of the covariance matrix, that is, the pair-wise correlation structure.18 Following this analogy, we can ask if the turnover – or more precisely its log – has explanatory power for modeling alpha correlations.19 It is evident that using the turnover directly (as opposed to its log) would get us nowhere due to the highly skewed (roughly log-normal) turnover distribution (see Figure 1).

To answer this question, recall that in a factor model the covariance matrix is modeled via

$$
{ \varGamma _ { i j } = \xi _ { i } ^ { 2 } \delta _ { i j } + \sum _ { A , B = 1 } ^ { K } \varOmega _ { i A } \ \varphi _ { A B } \varOmega _ { j B } }\tag{7}
$$

Here: $\xi _ { i } ^ { 2 }$ is the specific risk; $\varOmega _ { i A }$ is an $N \times K$ factor loadings matrix corresponding to $K \ll N$ risk factors; and $\varphi _ { A B }$ is a factor covariance matrix. In our case, we are interested in modeling the correlation matrix $\psi _ { i j }$ and ascertaining whether the turnover has explanatory power for pairwise correlations. Whether the volatility and turnover are correlated is a separate issue.

So, our approach is to take one of the columns of the factor loadings matrix as ln $\left( T _ { i } \right)$ . More precisely, a priori there is no reason why we should pick	ln $\left( T _ { i } \right)$ as opposed to ln $( \tau _ { i } )$ , where $\tau _ { i } = T _ { i } / \mu ,$ , and $\mu$ is some normalization factor. To deal with this, let us normalize $\tau _ { i }$ such that $\ln ( \tau _ { i } )$ has zero cross-sectional mean, and let $\nu _ { i } = 1$ be the unit -vector (the intercept). Then we can construct three symmetric tensor combinations $x _ { i j } = \nu _ { i } \nu _ { j } , y _ { i j } = \nu _ { i } \ln \bigl ( \tau _ { j } \bigr ) + \nu _ { j } \ln ( \tau _ { i } )$ ， and $z _ { i j } = \ln ( \tau _ { i } ) \ln \left( \tau _ { j } \right)$ . Let us now define a composite index $\{ a \} = \{ ( i , j ) | i > j \}$ , which takes $M = \mathit { N } ( N - 1 ) / 2$ values, i.e., we pull the off-diagonal lower-triangular elements of a general symmetric matrix $G _ { i j }$ into a vector $G _ { a }$ . This way we can construct four X-vectors $\psi _ { a } , x _ { a } , y _ { a }$ and $z _ { a }$ . Now we can run a linear regression of $\psi _ { a }$ over $x _ { a } , y _ { a }$ and $z _ { a }$ . Note that $x _ { a } = 1$ is simply the intercept (the unit X-vector), so this is a regression of $\psi _ { a }$ over $y _ { a }$ and $z _ { a }$ with the intercept. The results are summarized in Table 4. It is evident that the linear and bilinear (in ln $( \tau _ { i } ) )$ variables $y _ { a }$ and $z _ { a }$ have poor explanatory power for pair-wise correlations $\psi _ { a } ,$ , while $x _ { a }$ (the intercept) simply models the average correlation Mean $( \psi _ { a } )$ . Recall that by construction $y _ { a }$ and $z _ { a }$ are orthogonal to $x _ { a } ,$ and these three explanatory variables are independent of each other.

Let us emphasize that our conclusion does not necessarily mean the turnover adds no value in the factor model context, it only means that the turnover per se does not appear to help in modeling pair-wise alpha correlations. The above analysis does not address whether the turnover adds explanatory value to modeling variances, e.g., the specific risk.20 Thus, a linear regression of ln(=) over ln() (with the intercept) shows nonzero correlation between these variables (see Table 5), albeit not very strong. To see if the turnover adds value via, e.g., the specific risk requires using certain proprietary methods outside of the scope of this paper.21

## 4. Conclusions

We emphasize that the 101 alphas we present here are not “toy” alphas but real-life trading alphas used in production. In fact, 80 of these alphas are in production as of this writing.22 To our knowledge, this is the first time such a large number of real-life explicit formulaic alphas appear in the literature. This should come as no surprise: naturally, quant trading is highly proprietary and secretive. Our goal here is to provide a glimpse into the complex world of modern and ever-evolving quantitative trading and help demystify it, to any degree possible.

Technological advances nowadays allow automation of alpha mining. Quantitative trading alphas are by far the most numerous of available trading signals that can be turned into trading strategies/portfolios. There are myriad permutations of individual stock holdings in a (dollarneutral) portfolio of, e.g., 2,000 most liquid U.S. stocks that can result in a positive return on high- and mid-frequency time horizons. In addition, many of these alphas are ephemeral and their universe is very fluid. It takes quantitatively sophisticated, technologically well-endowed and ever-adapting trading operations to mine hundreds of thousands, millions and even billions of alphas and combine them into a unified “mega-alpha”, which is then traded with an added bonus of sizeable savings on execution costs due to automatic internal crossing of trades.

In this spirit, we end this paper with an 1832 poem by a Russian poet Mikhail Lermontov (translation from Russian by Zura Kakushadze, ca. 1993):

## The Sail

A lonely sail seeming white, In misty haze mid blue sea, Be foreign gale seeking might? Why home bays did it flee?

The sail’s bending mast is creaking, The wind and waves blast ahead, It isn’t happiness it’s seeking, Nor is it happiness it’s fled!

Beneath are running ázure streams, Above are shining golden beams, But wishing storms the sail seems, As if in storms is peace it deems.

## Appendix A: Formulaic Alphas

In this appendix, in Subsection A.1, we provide our 101 formulaic alphas. The formulas are also code once the functions and operators are defined. The functions and operators used in the alphas are defined in Subsection A.2. The input data is elaborated upon in Subsection A.3.

## A.1. Formulaic Expressions for Alphas

Alpha#1: (rank(Ts\_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)

Alpha#2: (-1 \* correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))

Alpha#3: (-1 \* correlation(rank(open), rank(volume), 10))

Alpha#4: (-1 \* Ts\_Rank(rank(low), 9))

Alpha#5: (rank((open - (sum(vwap, 10) / 10))) \* (-1 \* abs(rank((close - vwap)))))

Alpha#6: (-1 \* correlation(open, volume, 10))

Alpha#7: ((adv20 < volume) ? ((-1 \* ts\_rank(abs(delta(close, 7)), 60)) \* sign(delta(close, 7))) : (-1 \* 1))

Alpha#8: (-1 \* rank(((sum(open, 5) \* sum(returns, 5)) - delay((sum(open, 5) \* sum(returns, 5)),   
10))))   
Alpha#9: ((0 < ts\_min(delta(close, 1), 5)) ? delta(close, 1) : ((ts\_max(delta(close, 1), 5) < 0) ?   
delta(close, 1) : (-1 \* delta(close, 1))))   
Alpha#10: rank(((0 < ts\_min(delta(close, 1), 4)) ? delta(close, 1) : ((ts\_max(delta(close, 1), 4) < 0)   
? delta(close, 1) : (-1 \* delta(close, 1)))))   
Alpha#11: ((rank(ts\_max((vwap - close), 3)) + rank(ts\_min((vwap - close), 3))) \*   
rank(delta(volume, 3)))   
Alpha#12: (sign(delta(volume, 1)) \* (-1 \* delta(close, 1)))   
Alpha#13: (-1 \* rank(covariance(rank(close), rank(volume), 5)))   
Alpha#14: ((-1 \* rank(delta(returns, 3))) \* correlation(open, volume, 10))   
Alpha#15: (-1 \* sum(rank(correlation(rank(high), rank(volume), 3)), 3))   
Alpha#16: (-1 \* rank(covariance(rank(high), rank(volume), 5)))   
Alpha#17: (((-1 \* rank(ts\_rank(close, 10))) \* rank(delta(delta(close, 1), 1))) \*   
rank(ts\_rank((volume / adv20), 5)))   
Alpha#18: (-1 \* rank(((stddev(abs((close - open)), 5) + (close - open)) + correlation(close, open,   
10))))   
Alpha#19: ((-1 \* sign(((close - delay(close, 7)) + delta(close, 7)))) \* (1 + rank((1 + sum(returns,   
250)))))   
Alpha#20: (((-1 \* rank((open - delay(high, 1)))) \* rank((open - delay(close, 1)))) \* rank((open -   
delay(low, 1))))   
Alpha#21: ((((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) / 2)) ? (-1 \* 1) : (((sum(close,   
2) / 2) < ((sum(close, 8) / 8) - stddev(close, 8))) ? 1 : (((1 < (volume / adv20)) || ((volume /   
adv20) == 1)) ? 1 : (-1 \* 1))))   
Alpha#22: (-1 \* (delta(correlation(high, volume, 5), 5) \* rank(stddev(close, 20))))   
Alpha#23: (((sum(high, 20) / 20) < high) ? (-1 \* delta(high, 2)) : 0)   
Alpha#24: ((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05) ||   
((delta((sum(close, 100) / 100), 100) / delay(close, 100)) == 0.05)) ? (-1 \* (close - ts\_min(close,   
100))) : (-1 \* delta(close, 3)))

$$
\mathtt { A l p h a# 2 7 : ( ( 0 . 5 < r a n k ( ( s u m ( c o r r e l a t i o n ( r a n k ( v o l u m e ) , r a n k ( v w a p ) , 6 ) , 2 ) / 2 . 0 ) ) ) ? ( - 1 ^ { * } 1 ) : 1 ) }
$$

$$
\mathsf { A l p h a } \# 2 8 \colon s \mathsf { c a l e } ( ( ( \mathsf { c o r r e l a t i o n } ( \mathsf { a d v } 2 0 , \mathsf { l o w } , 5 ) + ( ( \mathsf { h i g h } + \mathsf { l o w } ) / 2 ) ) - \mathsf { c l o s e } ) )
$$

$$
\begin{array} { r l } & { \frac { \Delta | | { \mathfrak { p h a r s o } } \rangle \langle | \langle ( | 1 . 0 \textrm { - } \mathsf { r a n k } \langle ( ( \mathsf { s i g n } ( ( \mathsf { c l o s e } - \mathsf { d e l a y } ( \mathsf { c l o s e } , 1 ) ) ) ) + \mathsf { s i g n } ( ( \mathsf { d e l a y } ( \mathsf { c l o s e } , 1 ) \cdot \mathsf { d e l a y } ( \mathsf { c l o s e } , 2 ) ) ) ) \rangle + } { \mathsf { s i g n } ( ( \mathsf { d e l a y } ( \mathsf { c l o s e } , 2 ) \cdot \mathsf { d e l a y } ( \mathsf { c l o s e } , 2 ) ) ) ) \rangle + } } \\ & { \mathsf { s i g n } ( ( \mathsf { d e l a y } ( \mathsf { c l o s e } , 2 ) \cdot \mathsf { d e l a y } ( \mathsf { c l o s e } , 3 ) ) ) ) ) \rangle + \mathsf { s u m } ( \mathsf { v o l u m e } , 5 ) ) / \mathsf { s u m } ( \mathsf { v o l u m e } , 2 0 ) ) } \end{array}
$$

$$
\begin{array} { r l } & { \underline { { \mathsf { A l p h a r i a l 3 1 : } } } \left( ( \mathsf { r a n k } ( \mathsf { r a n k } ( \mathsf { r a n k } ( \mathsf { d e c a y \_ l i n e a r } ( ( - 1 \ast \mathsf { r a n k } ( \mathsf { r a n k } ( \mathsf { d e l t a } ( \mathsf { c l o s e , \mathsf { 1 0 } } ) ) ) ) ) , 1 0 ) ) ) + \mathsf { r a n k } ( ( - 1 \ast \mathsf { r a n k } ( \mathsf { r a n k } ( \mathsf { d e l t a } ( \mathsf { c l o s e , 1 0 } ) ) ) ) , 1 0 ) ) \right) } \\ & { \underline { { \mathsf { d e l t a } } } ( \mathsf { c l o s e , 3 } ) ) ) ) + \mathsf { s i g n } ( \mathsf { s c a l e } ( \mathsf { c o r r e l a t i o n } ( \mathsf { a d v } 2 0 , \mathsf { l o w , 1 2 } ) ) ) } \end{array}
$$

$$
\begin{array} { r l } & { \underline { { \mathsf { A l p h a# 3 2 : } } } \left( \mathsf { s c a l e } ( ( ( \mathsf { s u m } ( \mathsf { c l o s e } , 7 ) / 7 ) - \mathsf { c l o s e } ) ) + ( 2 0 ^ { * } \mathsf { s c a l e } ( \mathsf { c o r r e } | \mathsf { a t i o n } ( \mathsf { v w a p } , \mathsf { d e l a y } ( \mathsf { c l o s e } , 5 ) , } \\ & { 2 3 0 ) ) ) \right) } \end{array}
$$

$$
\mathsf { A l p h a } \# 3 3 \colon \mathsf { r a n k } ( ( - 1 \mathrm { ~ ^ * ~ } ( ( 1 \mathrm { ~ - ~ } ( \mathsf { o p e n } / \mathsf { c l o s e } ) ) ^ { \wedge } 1 ) ) )
$$

$$
\Delta | { \mathrm { p h a } } \# 3 4 \div \mathsf { r a n k } ( ( ( 1 - \mathsf { r a n k } ( ( \mathsf { s t a d e v } ( \mathsf { r e t u r n s } , 2 ) / \mathsf { s t a d e v } ( \mathsf { r e t u r n s } , 5 ) ) ) ) + ( 1 - \mathsf { r a n k } ( \mathsf { d e l t a } ( \mathsf { c l o s e } , 1 ) ) ) ) )
$$

$$
\Delta | \mathsf { p h a } \# 3 5 \dot { \Sigma } : ( ( \mathsf { T s } _ { - } \mathrm { R a n k } ( \mathsf { v o l u m e } , 3 2 ) ^ { * } ( 1 - \mathsf { T s } _ { - } \mathsf { R a n k } ( ( ( \mathsf { c l o s e } + \mathsf { h i g h } ) - \mathsf { I o w } ) , 1 6 ) ) ) ^ { * } ( 1 - \mathsf { T s } _ { - } \mathsf { R a n k } ( \mathsf { p o s e } + \mathsf { I n p } ( \mathsf { p o s e } + \mathsf { I n p } ( \mathsf { p o s e } ) , 1 6 ) ) ) ^ { * } ) | \mathsf { p o s } \rangle
$$

$$
\mathtt { A l p h a } \mathtt { 4 } \mathtt { 3 } 7 ; \mathtt { ( r a n k ( c o r r e l a t i o n ( d e l a y ( ( o p e n - c l o s e ) , 1 ) , c l o s e , 2 0 0 ) ) + r a n k ( ( o p e n - c l o s e ) ) ) }
$$

$$
\mathtt { A l p h a } \mathtt { H } 3 8 \mathtt { B } \mathtt { : } ( ( - 1 \ ^ { \ast } \ r \mathtt { a n k } ( \mathsf { T s } \_ { \mathsf { R a n k } } ( \mathsf { c l o s e } , \mathsf { 1 0 } ) ) ) \ ^ { \ast } \ r \mathtt { a n k } ( ( \mathsf { c l o s e } \ / \ \mathsf { o p e n } ) ) )
$$

$$
\begin{array} { r l } & { \frac { \Delta | { \mathsf { p h a f } } \mathsf { 3 } 9 ; \{ ( - 1 ^ { \star } \mathsf { r a n k } ( ( \mathsf { d e l t a } ( \mathsf { c l o s e } , 7 ) ^ { \star } ( 1 - \mathsf { r a n k } ( \mathsf { d e c a y } _ { - } \mathsf { l i n e a r } ( ( \mathsf { v o l u m e } / \mathsf { a d v a m e } / \mathsf { 9 } 0 ) , 9 ) ) ) ) ) \} ) ^ { \star } ( 1 + \mathsf { r a n k } ( \mathsf { d e c a y } _ { - } \mathsf { l i n e a r } ( ( \mathsf { v o l u m e } / \mathsf { a d v a m e } / \mathsf { a d v a m e } 2 0 ) , 9 ) ) ) ) } { \mathsf { 1 } } ) ^ { \star } } \end{array}
$$

$$
\mathtt { A l p h a } \mathtt { \# A } \mathtt { 4 } 0 \because ( ( - 1 \mathrm { ~ \rVert ~ \mathtt { s } ~ r a n k \left( \mathtt { s t d d e v } ( h i g h , \mathtt { 1 } 0 ) ) \right) \mathrm { ~ * ~ \mathtt { c o r r e l a t i o n } ( h i g h , \mathtt { v o l u m e } , \mathtt { 1 } 0 ) ) } }
$$

$$
\mathsf { A l p h a # 4 2 : } \left( \mathsf { r a n k } ( ( \mathsf { v w a p - c l o s e } ) ) / \mathsf { r a n k } ( ( \mathsf { v w a p + c l o s e } ) ) \right)
$$

$$
\mathsf { A l p h a# 4 3 : } \left( \mathsf { t s \_ r a n k } ( ( \mathsf { v o l u m e } \ / \mathsf { a d v } 2 0 ) , 2 0 ) \ast \mathsf { t s \_ r a n k } ( ( - 1 \ast \mathsf { d e l t a } ( \mathsf { c l o s e } , 7 ) ) , 8 ) \right)
$$

```lisp
Alpha#44: (-1 * correlation(high, rank(volume), 5))
Alpha#45: (-1 * ((rank((sum(delay(close, 5), 20) / 20)) * correlation(close, volume, 2)) *
rank(correlation(sum(close, 5), sum(close, 20), 2))))
Alpha#46: ((0.25 < (((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10))) ?
(-1 * 1) : (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < 0) ? 1 :
((-1 * 1) * (close - delay(close, 1)))))
Alpha#47: ((((rank((1 / close)) * volume) / adv20) * ((high * rank((high - close))) / (sum(high, 5) /
5))) - rank((vwap - delay(vwap, 5))))
Alpha#48: (indneutralize(((correlation(delta(close, 1), delta(delay(close, 1), 1), 250) *
delta(close, 1)) / close), IndClass.subindustry) / sum(((delta(close, 1) / delay(close, 1))^2), 250))
Alpha#49: (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 *
0.1)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))
Alpha#50: (-1 * ts_max(rank(correlation(rank(volume), rank(vwap), 5)), 5))
Alpha#51: (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 *
0.05)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))
Alpha#52: ((((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank(((sum(returns, 240) -
sum(returns, 20)) / 220))) * ts_rank(volume, 5))
Alpha#53: (-1 * delta((((close - low) - (high - close)) / (close - low)), 9))
Alpha#54: ((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))
Alpha#55: (-1 * correlation(rank(((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low,
12)))), rank(volume), 6))
Alpha#56: (0 - (1 * (rank((sum(returns, 10) / sum(sum(returns, 2), 3))) * rank((returns * cap)))))
Alpha#57: (0 - (1 * ((close - vwap) / decay_linear(rank(ts_argmax(close, 30)), 2))))
Alpha#58: (-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.sector), volume,
3.92795), 7.89291), 5.50322))
Alpha#59: (-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(((vwap * 0.728317) + (vwap *
(1 - 0.728317))), IndClass.industry), volume, 4.25197), 16.2289), 8.19648))
Alpha#60: (0 - (1 * ((2 * scale(rank(((((close - low) - (high - close)) / (high - low)) * volume)))) -
scale(rank(ts_argmax(close, 10))))))
```

```r
Alpha#61: (rank((vwap - ts_min(vwap, 16.1219))) < rank(correlation(vwap, adv180, 17.9282)))
Alpha#62: ((rank(correlation(vwap, sum(adv20, 22.4101), 9.91009)) < rank(((rank(open) +
rank(open)) < (rank(((high + low) / 2)) + rank(high))))) * -1)
Alpha#63: ((rank(decay_linear(delta(IndNeutralize(close, IndClass.industry), 2.25164), 8.22237))
- rank(decay_linear(correlation(((vwap * 0.318108) + (open * (1 - 0.318108))), sum(adv180,
37.2467), 13.557), 12.2883))) * -1)
Alpha#64: ((rank(correlation(sum(((open * 0.178404) + (low * (1 - 0.178404))), 12.7054),
sum(adv120, 12.7054), 16.6208)) < rank(delta(((((high + low) / 2) * 0.178404) + (vwap * (1 -
0.178404))), 3.69741))) * -1)
Alpha#65: ((rank(correlation(((open * 0.00817205) + (vwap * (1 - 0.00817205))), sum(adv60,
8.6911), 6.40374)) < rank((open - ts_min(open, 13.635)))) * -1)
Alpha#66: ((rank(decay_linear(delta(vwap, 3.51013), 7.23052)) + Ts_Rank(decay_linear(((((low
* 0.96633) + (low * (1 - 0.96633))) - vwap) / (open - ((high + low) / 2))), 11.4157), 6.72611)) * -1)
Alpha#67: ((rank((high - ts_min(high, 2.14593)))^rank(correlation(IndNeutralize(vwap,
IndClass.sector), IndNeutralize(adv20, IndClass.subindustry), 6.02936))) * -1)
Alpha#68: ((Ts_Rank(correlation(rank(high), rank(adv15), 8.91644), 13.9333) <
rank(delta(((close * 0.518371) + (low * (1 - 0.518371))), 1.06157))) * -1)
Alpha#69: ((rank(ts_max(delta(IndNeutralize(vwap, IndClass.industry), 2.72412),
4.79344))^Ts_Rank(correlation(((close * 0.490655) + (vwap * (1 - 0.490655))), adv20, 4.92416),
9.0615)) * -1)
Alpha#70: ((rank(delta(vwap, 1.29456))^Ts_Rank(correlation(IndNeutralize(close,
IndClass.industry), adv50, 17.8256), 17.9171)) * -1)
Alpha#71: max(Ts_Rank(decay_linear(correlation(Ts_Rank(close, 3.43976), Ts_Rank(adv180,
12.0647), 18.0175), 4.20501), 15.6948), Ts_Rank(decay_linear((rank(((low + open) - (vwap +
vwap)))^2), 16.4662), 4.4388))
Alpha#72: (rank(decay_linear(correlation(((high + low) / 2), adv40, 8.93345), 10.1519)) /
rank(decay_linear(correlation(Ts_Rank(vwap, 3.72469), Ts_Rank(volume, 18.5188), 6.86671),
2.95011)))
Alpha#73: (max(rank(decay_linear(delta(vwap, 4.72775), 2.91864)),
Ts_Rank(decay_linear(((delta(((open * 0.147155) + (low * (1 - 0.147155))), 2.03608) / ((open *
0.147155) + (low * (1 - 0.147155)))) * -1), 3.33829), 16.7411)) * -1)
```

Alpha#74: ((rank(correlation(close, sum(adv30, 37.4843), 15.1365)) < rank(correlation(rank(((high \* 0.0261661) + (vwap \* (1 - 0.0261661)))), rank(volume), 11.4791))) \* -1)

Alpha#75: (rank(correlation(vwap, volume, 4.24304)) < rank(correlation(rank(low), rank(adv50), 12.4413)))

Alpha#76: (max(rank(decay\_linear(delta(vwap, 1.24383), 11.8259)), Ts\_Rank(decay\_linear(Ts\_Rank(correlation(IndNeutralize(low, IndClass.sector), adv81, 8.14941), 19.569), 17.1543), 19.383)) \* -1)

Alpha#77: min(rank(decay\_linear(((((high + low) / 2) + high) - (vwap + high)), 20.0451)), rank(decay\_linear(correlation(((high + low) / 2), adv40, 3.1614), 5.64125)))

Alpha#78: (rank(correlation(sum(((low \* 0.352233) + (vwap \* (1 - 0.352233))), 19.7428), sum(adv40, 19.7428), 6.83313))^rank(correlation(rank(vwap), rank(volume), 5.77492)))

Alpha#79: (rank(delta(IndNeutralize(((close \* 0.60733) + (open \* (1 - 0.60733))), IndClass.sector), 1.23438)) < rank(correlation(Ts\_Rank(vwap, 3.60973), Ts\_Rank(adv150, 9.18637), 14.6644)))

Alpha#80: ((rank(Sign(delta(IndNeutralize(((open \* 0.868128) + (high \* (1 - 0.868128))), IndClass.industry), 4.04545)))^Ts\_Rank(correlation(high, adv10, 5.11456), 5.53756)) \* -1)

Alpha#81: ((rank(Log(product(rank((rank(correlation(vwap, sum(adv10, 49.6054), 8.47743))^4)), 14.9655))) < rank(correlation(rank(vwap), rank(volume), 5.07914))) \* -1)

Alpha#82: (min(rank(decay\_linear(delta(open, 1.46063), 14.8717)), Ts\_Rank(decay\_linear(correlation(IndNeutralize(volume, IndClass.sector), ((open \* 0.634196) + (open \* (1 - 0.634196))), 17.4842), 6.92131), 13.4283)) \* -1)

Alpha#83: ((rank(delay(((high - low) / (sum(close, 5) / 5)), 2)) \* rank(rank(volume))) / (((high - low) / (sum(close, 5) / 5)) / (vwap - close)))

Alpha#84: SignedPower(Ts\_Rank((vwap - ts\_max(vwap, 15.3217)), 20.7127), delta(close, 4.96796))

Alpha#85: (rank(correlation(((high \* 0.876703) + (close \* (1 - 0.876703))), adv30, 9.61331))^rank(correlation(Ts\_Rank(((high + low) / 2), 3.70596), Ts\_Rank(volume, 10.1595), 7.11408)))

Alpha#86: ((Ts\_Rank(correlation(close, sum(adv20, 14.7444), 6.00049), 20.4195) < rank(((open + close) - (vwap + open)))) \* -1)

Alpha#87: (max(rank(decay\_linear(delta(((close \* 0.369701) + (vwap \* (1 - 0.369701))), 1.91233), 2.65461)), Ts\_Rank(decay\_linear(abs(correlation(IndNeutralize(adv81, IndClass.industry), close, 13.4132)), 4.89768), 14.4535)) \* -1)

Alpha#88: min(rank(decay\_linear(((rank(open) + rank(low)) - (rank(high) + rank(close))), 8.06882)), Ts\_Rank(decay\_linear(correlation(Ts\_Rank(close, 8.44728), Ts\_Rank(adv60, 20.6966), 8.01266), 6.65053), 2.61957))

Alpha#89: (Ts\_Rank(decay\_linear(correlation(((low \* 0.967285) + (low \* (1 - 0.967285))), adv10, 6.94279), 5.51607), 3.79744) - Ts\_Rank(decay\_linear(delta(IndNeutralize(vwap, IndClass.industry), 3.48158), 10.1466), 15.3012))

Alpha#90: ((rank((close - ts\_max(close, 4.66719)))^Ts\_Rank(correlation(IndNeutralize(adv40, IndClass.subindustry), low, 5.38375), 3.21856)) \* -1)

Alpha#91: ((Ts\_Rank(decay\_linear(decay\_linear(correlation(IndNeutralize(close, IndClass.industry), volume, 9.74928), 16.398), 3.83219), 4.8667) - rank(decay\_linear(correlation(vwap, adv30, 4.01303), 2.6809))) \* -1)

Alpha#92: min(Ts\_Rank(decay\_linear(((((high + low) / 2) + close) < (low + open)), 14.7221), 18.8683), Ts\_Rank(decay\_linear(correlation(rank(low), rank(adv30), 7.58555), 6.94024), 6.80584))

Alpha#93: (Ts\_Rank(decay\_linear(correlation(IndNeutralize(vwap, IndClass.industry), adv81, 17.4193), 19.848), 7.54455) / rank(decay\_linear(delta(((close \* 0.524434) + (vwap \* (1 - 0.524434))), 2.77377), 16.2664)))

Alpha#94: ((rank((vwap - ts\_min(vwap, 11.5783)))^Ts\_Rank(correlation(Ts\_Rank(vwap, 19.6462), Ts\_Rank(adv60, 4.02992), 18.0926), 2.70756)) \* -1)

Alpha#95: (rank((open - ts\_min(open, 12.4105))) < Ts\_Rank((rank(correlation(sum(((high + low) / 2), 19.1351), sum(adv40, 19.1351), 12.8742))^5), 11.7584))

Alpha#96: (max(Ts\_Rank(decay\_linear(correlation(rank(vwap), rank(volume), 3.83878), 4.16783), 8.38151), Ts\_Rank(decay\_linear(Ts\_ArgMax(correlation(Ts\_Rank(close, 7.45404), Ts\_Rank(adv60, 4.13242), 3.65459), 12.6556), 14.0365), 13.4143)) \* -1)

Alpha#97: ((rank(decay\_linear(delta(IndNeutralize(((low \* 0.721001) + (vwap \* (1 - 0.721001))), IndClass.industry), 3.3705), 20.4523)) - Ts\_Rank(decay\_linear(Ts\_Rank(correlation(Ts\_Rank(low, 7.87871), Ts\_Rank(adv60, 17.255), 4.97547), 18.5925), 15.7152), 6.71659)) \* -1)

```r
Alpha#98: (rank(decay_linear(correlation(vwap, sum(adv5, 26.4719), 4.58418), 7.18088)) -
rank(decay_linear(Ts_Rank(Ts_ArgMin(correlation(rank(open), rank(adv15), 20.8187), 8.62571),
6.95668), 8.07206)))
```

Alpha#101: ((close - open) / ((high - low) + .001))

## A.1. Functions and Operators

(Below “{ }” stands for a placeholder. All expressions are case insensitive.)

abs(x), log(x), sign(x) = standard definitions; same for the operators “+”, “-”, “\*”, “/”, “>”, “<”, “==”, “||”, “x ? y : z”

rank(x) = cross-sectional rank

delay(x, d) = value of x d days ago

correlation(x, y, d) = time-serial correlation of x and y for the past d days

covariance(x, y, d) = time-serial covariance of x and y for the past d days

scale(x, a) = rescaled x such that sum(abs(x)) = a (the default is a = 1)

delta(x, d) = today’s value of x minus the value of x d days ago

signedpower(x, a) = x^a

decay\_linear(x, d) = weighted moving average over the past d days with linearly decaying weights d, d – 1, …, 1 (rescaled to sum up to 1)

indneutralize(x, g) = x cross-sectionally neutralized against groups g (subindustries, industries, sectors, etc.), i.e., x is cross-sectionally demeaned within each group g

ts\_{O}(x, d) = operator O applied across the time-series for the past d days; non-integer number of days d is converted to floor(d)

ts\_min(x, d) = time-series min over the past d days

ts\_max(x, d) = time-series max over the past d days

ts\_argmax(x, d) = which day ts\_max(x, d) occurred on

ts\_argmin(x, d) = which day ts\_min(x, d) occurred on

ts\_rank(x, d) = time-series rank in the past d days

min(x, d) = ts\_min(x, d)

max(x, d) = ts\_max(x, d)

sum(x, d) = time-series sum over the past d days

product(x, d) = time-series product over the past d days

stddev(x, d) = moving time-series standard deviation over the past d days

## A.2. Input Data

returns = daily close-to-close returns

open, close, high, low, volume = standard definitions for daily price and volume data

vwap = daily volume-weighted average price

cap = market cap

adv{d} = average daily dollar volume for the past d days

IndClass = a generic placeholder for a binary industry classification such as GICS, BICS, NAICS, SIC, etc., in indneutralize(x, IndClass.level), where level = sector, industry, subindustry, etc. Multiple IndClass in the same alpha need not correspond to the same industry classification.

## Appendix B: Disclaimer

Wherever the context so requires, the masculine gender includes the feminine and/or neuter, and the singular form includes the plural and vice versa. The authors of this paper (“Authors”) and their affiliates including without limitation Quantigic® Solutions LLC (“Authors’ Affiliates” or “their Affiliates”) make no implied or express warranties or any other representations whatsoever, including without limitation implied warranties of merchantability and fitness for a particular purpose, in connection with or with regard to the content of this paper including without limitation any formulae, code or algorithms contained herein (“Content”).

The reader may use the Content solely at his/her/its own risk and the reader shall have no claims whatsoever against the Authors or their Affiliates and the Authors and their Affiliates shall have no liability whatsoever to the reader or any third party whatsoever for any loss, expense, opportunity cost, damages or any other adverse effects whatsoever relating to or arising from the use of the Content by the reader including without any limitation whatsoever: any direct, indirect, incidental, special, consequential or any other damages incurred by the reader, however caused and under any theory of liability; any loss of profit (whether incurred directly or indirectly), any loss of goodwill or reputation, any loss of data suffered, cost of procurement of substitute goods or services, or any other tangible or intangible loss; any reliance placed by the reader on the completeness, accuracy or existence of the Content or any other effect of using the Content; and any and all other adversities or negative effects the reader might encounter in using the Content irrespective of whether the Authors or their Affiliates are or should have been aware of such adversities or negative effects.

The formulae and code included in Appendix A hereof are provided herein with the express permission of WorldQuant LLC. WorldQuant LLC retains all rights, title and interest in and to the formulae and code included in Appendix A hereof and any and all copyrights therefor.

## References

Avellaneda, M. and Lee, J.H. “Statistical arbitrage in the U.S. equity market.” Quantitative Finance 10(7) (2010), pp. 761-782.

Grinold, R.C. and Kahn, R.N. “Active Portfolio Management.” New York, NY: McGraw-Hill, 2000.

Jegadeesh, N. and Titman, S. “Returns to buying winners and selling losers: Implications for stock market efficiency.” Journal of Finance 48(1) (1993), pp. 65-91.

Kakushadze, Z. “Factor Models for Alpha Streams.” The Journal of Investment Strategies 4(1) (2014), pp. 83-109.

Kakushadze, Z. and Tulchinsky, I. “Performance v. Turnover: A Story by 4,000 Alphas.” Journal of Investment Strategies (forthcoming). Available online: http://ssrn.com/abstract=2657603 (September 7, 2015).

Pastor, L. and Stambaugh, R.F. “Liquidity Risk and Expected Stock Returns.” The Journal of Political Economy 111(3) (2003), pp. 642-685.

Tulchinsky, I. et al. “Finding Alphas: A Quantitative Approach to Building Trading Strategies.” New York, NY: Wiley, 2015.

## Tables

<table><tr><td rowspan=1 colspan=1>Quantity</td><td rowspan=1 colspan=1>Minimum</td><td rowspan=1 colspan=1>1st Quartile</td><td rowspan=1 colspan=1>Median</td><td rowspan=1 colspan=1>Mean</td><td rowspan=1 colspan=1>3rd Quartile</td><td rowspan=1 colspan=1>Maximum</td></tr><tr><td rowspan=1 colspan=1>S</td><td rowspan=1 colspan=1>1.238</td><td rowspan=1 colspan=1>1.929</td><td rowspan=1 colspan=1>2.224</td><td rowspan=1 colspan=1>2.265</td><td rowspan=1 colspan=1>2.498</td><td rowspan=1 colspan=1>4.162</td></tr><tr><td rowspan=1 colspan=1>T</td><td rowspan=1 colspan=1>0.1571</td><td rowspan=1 colspan=1>0.3429</td><td rowspan=1 colspan=1>0.4752</td><td rowspan=1 colspan=1>0.5456</td><td rowspan=1 colspan=1>0.6474</td><td rowspan=1 colspan=1>1.604</td></tr><tr><td rowspan=1 colspan=1>1/T</td><td rowspan=1 colspan=1>0.6235</td><td rowspan=1 colspan=1>1.545</td><td rowspan=1 colspan=1>2.104</td><td rowspan=1 colspan=1>2.391</td><td rowspan=1 colspan=1>2.916</td><td rowspan=1 colspan=1>6.365</td></tr><tr><td rowspan=1 colspan=1>C</td><td rowspan=1 colspan=1>0.1324</td><td rowspan=1 colspan=1>0.3125</td><td rowspan=1 colspan=1>0.3969</td><td rowspan=1 colspan=1>0.4814</td><td rowspan=1 colspan=1>0.5073</td><td rowspan=1 colspan=1>2.031</td></tr><tr><td rowspan=1 colspan=1> $1 0 ^ { 3 } ~ \times \sigma$ </td><td rowspan=1 colspan=1>0.9318</td><td rowspan=1 colspan=1>1.194</td><td rowspan=1 colspan=1>1.395</td><td rowspan=1 colspan=1>1.747</td><td rowspan=1 colspan=1>2.019</td><td rowspan=1 colspan=1>10.44</td></tr><tr><td rowspan=1 colspan=1> $1 0 0 \% \times \tilde { R }$ </td><td rowspan=1 colspan=1>3.285</td><td rowspan=1 colspan=1>4.4</td><td rowspan=1 colspan=1>5.441</td><td rowspan=1 colspan=1>6.015</td><td rowspan=1 colspan=1>6.296</td><td rowspan=1 colspan=1>28.72</td></tr><tr><td rowspan=1 colspan=1> $1 0 0 \% \times \psi _ { i j }$ </td><td rowspan=1 colspan=1>-15.09</td><td rowspan=1 colspan=1>7.457</td><td rowspan=1 colspan=1>14.31</td><td rowspan=1 colspan=1>15.86</td><td rowspan=1 colspan=1>22.91</td><td rowspan=1 colspan=1>87.33</td></tr></table>

Table 1. Summary (using the R function summary()) for the annualized Sharpe ratio $S _ { i } ,$ daily turnover, $T _ { i } ,$ , average holding period $1 / T _ { i } ,$ cents-per-share $C _ { i } ,$ daily return volatility $\sigma _ { i } ,$ annualized average daily return ${ \tilde { R } } _ { i } ,$ and pair-wise correlations $\psi _ { i j }$ with $i > j$ (see Section 3). The performance figures are exclusive of any trading or transaction costs, price impact, etc.

<table><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>Estimate</td><td rowspan=1 colspan=1>Standard error</td><td rowspan=1 colspan=1>t-statistic</td><td rowspan=1 colspan=1>Overall</td></tr><tr><td rowspan=1 colspan=1>Intercept</td><td rowspan=1 colspan=1>-3.509</td><td rowspan=1 colspan=1>0.295</td><td rowspan=1 colspan=1>-11.88</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>In(σ)</td><td rowspan=1 colspan=1>0.761</td><td rowspan=1 colspan=1>0.046</td><td rowspan=1 colspan=1>16.65</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>Mult./Adj. R-squared</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>0.737 / 0.734</td></tr><tr><td rowspan=1 colspan=1>F-statistic</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>277.2</td></tr></table>

Table 2. Summary (using the R function summary(lm())) for the cross-sectional regression of ln() over ln(=) with the intercept. See Subsection 3.1 for details. Also see Figure 2.

<table><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>Estimate</td><td rowspan=1 colspan=1> Standard error</td><td rowspan=1 colspan=1>t-statistic</td><td rowspan=1 colspan=1>Overall</td></tr><tr><td rowspan=1 colspan=1>Intercept</td><td rowspan=1 colspan=1>-3.435</td><td rowspan=1 colspan=1>0.324</td><td rowspan=1 colspan=1>-10.60</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>ln(σ)</td><td rowspan=1 colspan=1>0.775</td><td rowspan=1 colspan=1>0.052</td><td rowspan=1 colspan=1>14.84</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>In(T)</td><td rowspan=1 colspan=1>-0.023</td><td rowspan=1 colspan=1>0.040</td><td rowspan=1 colspan=1>-0.57</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>Mult./Adj. R-squared</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>0.738 /0.732</td></tr><tr><td rowspan=1 colspan=1>F-statistic</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>137.8</td></tr></table>

Table 3. Summary for the cross-sectional regression of ln() over ln(=) and ln() with the intercept. See Subsection 3.1 for details.

<table><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>Estimate</td><td rowspan=1 colspan=1>Standard error</td><td rowspan=1 colspan=1>t-statistic</td><td rowspan=1 colspan=1>Overall</td></tr><tr><td rowspan=1 colspan=1>Intercept</td><td rowspan=1 colspan=1>0.1587</td><td rowspan=1 colspan=1>0.0017</td><td rowspan=1 colspan=1>95.18</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1> $y _ { a }$ </td><td rowspan=1 colspan=1>0.0067</td><td rowspan=1 colspan=1>0.0023</td><td rowspan=1 colspan=1>2.907</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1> $\underline { { z } } _ { a }$ </td><td rowspan=1 colspan=1>0.0474</td><td rowspan=1 colspan=1>0.0063</td><td rowspan=1 colspan=1>7.537</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>Mult./Adj. R-squared</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>0.0127 /0.0123</td></tr><tr><td rowspan=1 colspan=1>F-statistic</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>32.55</td></tr></table>

Table 4. Summary for the cross-sectional regression of $\psi _ { a }$ over $y _ { a }$ and $z _ { a }$ with the intercept. See Subsection 3.2 for details. Also see Figure 3.

<table><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>Estimate</td><td rowspan=1 colspan=1>Standard error</td><td rowspan=1 colspan=1>t-statistic</td><td rowspan=1 colspan=1>Overall</td></tr><tr><td rowspan=1 colspan=1>Intercept</td><td rowspan=1 colspan=1>-6.174</td><td rowspan=1 colspan=1>0.062</td><td rowspan=1 colspan=1>-100.1</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>In(T)</td><td rowspan=1 colspan=1>0.368</td><td rowspan=1 colspan=1>0.068</td><td rowspan=1 colspan=1>5.412</td><td rowspan=1 colspan=1></td></tr><tr><td rowspan=1 colspan=1>Mult./Adj. R-squared</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>0.228/0.221</td></tr><tr><td rowspan=1 colspan=1>F-statistic</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>29.29</td></tr></table>

Table 5. Summary for the cross-sectional regression of ln(=) over ln() with the intercept. See Subsection 3.2 for details. Also see Figure 4.

## Figures

![](images/68726e8e9dd548ab19fcd01a02a078ae2a16b0068ddb30286486ccc0631ee5b3.jpg)

![](images/72817b94f31b0d13cfdd64ecf54f16be7010157b1a604fb661d0c03ec7fd4ac6.jpg)

![](images/a3d70cf4ce34603f9a386ef5df9bac3182a92b91b30b7c273ca70999dca1c222.jpg)

![](images/0d0b7f6e1cdcd3c235162daf2a0b5d5bfeab43bac425c95e4f139a9114b2023d.jpg)

![](images/0ddf5422b92109ff5627088927cb4a2d927fe4cfb904a67317c817593b5897b5.jpg)

![](images/26e541530a9f4424537537a2086289e470482a53fc2774f48067fa285d03d9ca.jpg)  
Figure 1. Density (using the R function density()) plots for the annualized Sharpe ratio $S _ { i } ,$ daily turnover, $T _ { i } ,$ cents-per-share $C _ { i } ,$ daily return volatility $\sigma _ { i } ,$ annualized average daily return ${ \tilde { R } } _ { i } ,$ and pair-wise correlations $\psi _ { i j }$ with $i > j$ (see Table 1 and Section 3). The “extreme” outliers in $S _ { i } , \sigma _ { i }$ and ${ \tilde { R } } _ { i }$ are due to the delay-0 alphas (see Section 2).

![](images/cc6cf1bad34da2188fe2fda6a97f3c4ba2174dbc4baf2f9a00c76109be34d5a3.jpg)  
Figure 2. Horizontal axis: ln(=); vertical axis: ln(). The dots represent the data points. The straight line plots the linear regression fit ln $( R ) \approx - 3 . 5 0 9 \ + \ 0 . 7 6 1 \ln ( \sigma )$ . See Table 2.

![](images/c0c98c2e2a80e1a9b6c74ec8b64c3834f000fc8b37e565e509003d5a8677772f.jpg)  
Figure 3. Horizontal axis: $w _ { a } = 0 . 0 0 6 7 y _ { a } + \ 0 . 0 4 7 4 z _ { a } ;$ vertical axis: $\psi _ { a } - \mathsf { M e a n } ( \psi _ { a } )$ . See Table 4 and Subsection 3.2. The numeric coefficients are the regression coefficients in Table 4.

![](images/7d86cfe479140ed3373574137f696cb83e6bf07c16eab932e19472c0c276bbfe.jpg)  
Figure 4. Horizontal axis: ln(); vertical axis: ln(=). The dots represent the data points. The straight line plots the linear regression fit ln $( \sigma ) \approx - 6 . 1 7 4 + 0 . 3 6 8 \ln ( T )$ . See Table 5.