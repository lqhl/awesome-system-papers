# 151 Trading Strategies

Zura Kakushadze§†1 and Juan Andr´es Serur]2

§ Quantigicr Solutions LLC 1127 High Ridge Road #135, Stamford, CT 06905 3   
† Free University of Tbilisi, Business School & School of Physics 240, David Agmashenebeli Alley, Tbilisi, 0159, Georgia ] Universidad del CEMA   
Av. C´ordoba 374, C1054AAP, Ciudad de Buenos Aires, Argentina (August 17, 2018)

ZK: To my mother Mila and my children Mirabelle and Maximilien

JAS: To my parents, Claudio and Andrea, and my brother Emiliano

## Abstract

We provide detailed descriptions, including over 550 mathematical formulas, for over 150 trading strategies across a host of asset classes (and trading styles). This includes stocks, options, fixed income, futures, ETFs, indexes, commodities, foreign exchange, convertibles, structured assets, volatility (as an asset class), real estate, distressed assets, cash, cryptocurrencies, miscellany (such as weather, energy, inflation), global macro, infrastructure, and tax arbitrage. Some strategies are based on machine learning algorithms (such as artificial neural networks, Bayes, k-nearest neighbors). We also give: source code for illustrating out-of-sample backtesting with explanatory notes; around 2,000 bibliographic references; and over 900 glossary, acronym and math definitions. The presentation is intended to be descriptive and pedagogical.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## Contents

Praises of 151 Trading Strategies 7   
Author Biographies 9   
Preface (by Zura Kakushadze) 10   
1 Introduction and Summary 15   
2 Options 17   
2.1 Generalities 17   
2.2 Strategy: Covered call 18   
2.3 Strategy: Covered put 18   
2.4 Strategy: Protective put 19   
2.5 Strategy: Protective call 19   
2.6 Strategy: Bull call spread 19   
2.7 Strategy: Bull put spread 20   
2.8 Strategy: Bear call spread 20   
2.9 Strategy: Bear put spread 20   
2.10 Strategy: Long synthetic forward 21   
2.11 Strategy: Short synthetic forward 21   
2.12 Strategy: Long combo 21   
2.13 Strategy: Short combo 22   
2.14 Strategy: Bull call ladder . 22   
2.15 Strategy: Bull put ladder . 23   
2.16 Strategy: Bear call ladder 23   
2.17 Strategy: Bear put ladder 23   
2.18 Strategy: Calendar call spread 24   
2.19 Strategy: Calendar put spread 24   
2.20 Strategy: Diagonal call spread 25   
2.21 Strategy: Diagonal put spread 25   
2.22 Strategy: Long straddle 26   
2.23 Strategy: Long strangle . 26   
2.24 Strategy: Long guts . . 26   
2.25 Strategy: Short straddle 27   
2.26 Strategy: Short strangle 27   
2.27 Strategy: Short guts 27   
2.28 Strategy: Long call synthetic straddle 28   
2.29 Strategy: Long put synthetic straddle . 28   
2.30 Strategy: Short call synthetic straddle 28   
2.31 Strategy: Short put synthetic straddle 29   
2.32 Strategy: Covered short straddle 29   
2.33 Strategy: Covered short strangle . . 29   
2.34 Strategy: Strap 30   
2.35 Strategy: Strip 30   
2.36 Strategy: Call ratio backspread 30   
2.37 Strategy: Put ratio backspread 31   
2.38 Strategy: Ratio call spread 31   
2.39 Strategy: Ratio put spread . 31   
2.40 Strategy: Long call butterfly 32   
2.40.1 Strategy: Modified call butterfly 32   
2.41 Strategy: Long put butterfly . 32   
2.41.1 Strategy: Modified put butterfly 33   
2.42 Strategy: Short call butterfly 33   
2.43 Strategy: Short put butterfly 33   
2.44 Strategy: “Long” iron butterfly 34   
2.45 Strategy: “Short” iron butterfly 34   
2.46 Strategy: Long call condor 34   
2.47 Strategy: Long put condor 35   
2.48 Strategy: Short call condor 35   
2.49 Strategy: Short put condor 35   
2.50 Strategy: Long iron condor . 36   
2.51 Strategy: Short iron condor 36   
2.52 Strategy: Long box . . 37   
2.53 Strategy: Collar . 37   
2.54 Strategy: Bullish short seagull spread 37   
2.55 Strategy: Bearish long seagull spread 38   
2.56 Strategy: Bearish short seagull spread 38   
2.57 Strategy: Bullish long seagull spread 39   
Stocks 40   
3.1 Strategy: Price-momentum . 40   
3.2 Strategy: Earnings-momentum . 41   
3.3 Strategy: Value . 42   
3.4 Strategy: Low-volatility anomaly 42   
3.5 Strategy: Implied volatility . 43   
3.6 Strategy: Multifactor portfolio 43   
3.7 Strategy: Residual momentum 44   
3.8 Strategy: Pairs trading . . 45   
3.9 Strategy: Mean-reversion – single cluster 46   
3.9.1 Strategy: Mean-reversion – multiple clusters 47   
3.10 Mean-reversion – weighted regression 49   
3.11 Strategy: Single moving average 49   
3.12 Strategy: Two moving averages 50   
3.13 Strategy: Three moving averages 51   
3.14 Strategy: Support and resistance 51   
3.15 Strategy: Channel 52   
3.16 Strategy: Event-driven – M&A 52   
3.17 Strategy: Machine learning – single-stock KNN 53   
3.18 Strategy: Statistical arbitrage – optimization . 55   
3.18.1 Dollar-neutrality 56   
3.19 Strategy: Market-making 58   
3.20 Strategy: Alpha combos 59   
3.21 A few comments 60   
4 Exchange-traded funds (ETFs) 61   
4.1 Strategy: Sector momentum rotation 61   
4.1.1 Strategy: Sector momentum rotation with MA filter . 62   
4.1.2 Strategy: Dual-momentum sector rotation 62   
4.2 Strategy: Alpha rotation 63   
4.3 Strategy: R-squared 63   
4.4 Strategy: Mean-reversion . 64   
4.5 Strategy: Leveraged ETFs (LETFs) 64   
4.6 Strategy: Multi-asset trend following 65   
5 Fixed Income 66   
5.1 Generalities 66   
5.1.1 Zero-coupon bonds 66   
5.1.2 Bonds with coupons 66   
5.1.3 Floating rate bonds 67   
5.1.4 Swaps 67   
5.1.5 Duration and convexity . 68   
5.2 Strategy: Bullets 69   
5.3 Strategy: Barbells . 69   
5.4 Strategy: Ladders 70   
5.5 Strategy: Bond immunization 70   
5.6 Strategy: Dollar-duration-neutral butterfly 71   
5.7 Strategy: Fifty-fifty butterfly 72   
5.8 Strategy: Regression-weighted butterfly 72   
5.8.1 Strategy: Maturity-weighted butterfly . 73   
5.9 Strategy: Low-risk factor . 73   
5.10 Strategy: Value factor 73   
5.11 Strategy: Carry factor 74   
5.12 Strategy: Rolling down the yield curve 74   
5.13 Strategy: Yield curve spread (flatteners & steepeners) 75   
5.14 Strategy: CDS basis arbitrage 75   
5.15 Strategy: Swap-spread arbitrage . . 76

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

6 Indexes 76   
6.1 Generalities . 76   
6.2 Strategy: Cash-and-carry arbitrage 77   
6.3 Strategy: Dispersion trading in equity indexes 77   
6.3.1 Strategy: Dispersion trading – subset portfolio 78   
6.4 Strategy: Intraday arbitrage between index ETFs 79   
6.5 Strategy: Index volatility targeting with risk-free asset 80   
7 Volatility 80   
7.1 Generalities 80   
7.2 Strategy: VIX futures basis trading 81   
7.3 Strategy: Volatility carry with two ETNs 82   
7.3.1 Strategy: Hedging short VXX with VIX futures 82   
7.4 Strategy: Volatility risk premium 83   
7.4.1 Strategy: Volatility risk premium with Gamma hedging 83   
7.5 Strategy: Volatility skew – long risk reversal 84   
7.6 Strategy: Volatility trading with variance swaps 84   
8 Foreign Exchange (FX) 85   
8.1 Strategy: Moving averages with HP filter 85   
8.2 Strategy: Carry trade . . 86   
8.2.1 Strategy: High-minus-low carry 87   
8.3 Strategy: Dollar carry trade 88   
8.4 Strategy: Momentum & carry combo 88   
8.5 Strategy: FX triangular arbitrage 89   
9 Commodities 89   
9.1 Strategy: Roll yields 89   
9.2 Strategy: Trading based on hedging pressure 90   
9.3 Strategy: Portfolio diversification with commodities 90   
9.4 Strategy: Value 90   
9.5 Strategy: Skewness premium . 91   
9.6 Strategy: Trading with pricing models 91   
10 Futures 92   
10.1 Strategy: Hedging risk with futures 92   
10.1.1 Strategy: Cross-hedging 93   
10.1.2 Strategy: Interest rate risk hedging 93   
10.2 Strategy: Calendar spread 94   
10.3 Strategy: Contrarian trading (mean-reversion) 95   
10.3.1 Strategy: Contrarian trading – market activity . 95   
10.4 Strategy: Trend following (momentum) 96

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

11 Structured Assets 97   
11.1 Generalities: Collateralized Debt Obligations (CDOs) 97   
11.2 Strategy: Carry, equity tranche – index hedging 99   
11.3 Strategy: Carry, senior/mezzanine – index hedging 99   
11.4 Strategy: Carry – tranche hedging . 99   
11.5 Strategy: Carry – CDS hedging 100   
11.6 Strategy: CDOs – curve trades 100   
11.7 Strategy: Mortgage-backed security (MBS) trading 100   
12 Convertibles 101   
12.1 Strategy: Convertible arbitrage 101   
12.2 Strategy: Convertible option-adjusted spread . 102   
13 Tax Arbitrage 102   
13.1 Strategy: Municipal bond tax arbitrage 102   
13.2 Strategy: Cross-border tax arbitrage 103   
13.2.1 Strategy: Cross-border tax arbitrage with options 104   
14 Miscellaneous Assets 104   
14.1 Strategy: Inflation hedging – inflation swaps 104   
14.2 Strategy: TIPS-Treasury arbitrage 105   
14.3 Strategy: Weather risk – demand hedging 106   
14.4 Strategy: Energy – spark spread . 108   
15 Distressed Assets 108   
15.1 Strategy: Buying and holding distressed debt 108   
15.2 Strategy: Active distressed investing 109   
15.2.1 Strategy: Planning a reorganization 109   
15.2.2 Strategy: Buying outstanding debt 109   
15.2.3 Strategy: Loan-to-own 110   
15.3 Strategy: Distress risk puzzle . 110   
15.3.1 Strategy: Distress risk puzzle – risk management 110   
16 Real Estate 111   
16.1 Generalities 111   
16.2 Strategy: Mixed-asset diversification with real estate 111   
16.3 Strategy: Intra-asset diversification within real estate 112   
16.3.1 Strategy: Property type diversification 112   
16.3.2 Strategy: Economic diversification . 112   
16.3.3 Strategy: Property type and geographic diversification 113   
16.4 Strategy: Real estate momentum – regional approach 113   
16.5 Strategy: Inflation hedging with real estate . . 113   
16.6 Strategy: Fix-and-flip . . . 114

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

17 Cash 114   
17.1 Generalities 114   
17.2 Strategy: Money laundering – the dark side of cash 114   
17.3 Strategy: Liquidity management . 115   
17.4 Strategy: Repurchase agreement (REPO) 115   
17.5 Strategy: Pawnbroking 115   
17.6 Strategy: Loan sharking 116   
18 Cryptocurrencies 116   
18.1 Generalities 116   
18.2 Strategy: Artificial neural network (ANN) 116   
18.3 Strategy: Sentiment analysis – na¨ıve Bayes Bernoulli 120   
19 Global Macro 121   
19.1 Generalities 121   
19.2 Strategy: Fundamental macro momentum 122   
19.3 Strategy: Global macro inflation hedge 122   
19.4 Strategy: Global fixed-income strategy 123   
19.5 Strategy: Trading on economic announcements . 123   
20 Infrastructure 123   
Acknowledgments 124   
A R Source Code for Backtesting 125   
B DISCLAIMERS 132   
References 134   
Glossary 279   
Acronyms 336   
Some Math Notations 340   
Explanatory Comments for Index 341   
Index 342

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## Praises of 151 Trading Strategies

“If you want to work as a trader or quant on Wall Street, you have to walk the walk and talk the talk. This unique book is a comprehensive introduction to a wide variety of tried and tested trading strategies. I highly recommend a 152nd trading strategy called buy this book!”

–Peter Carr, Professor and Chair of Finance and Risk Engineering Department, NYU’s Tandon School of Engineering; and 2010 Financial Engineer of the Year, International Association for Quantitative Finance & Sungard

“This book is an encyclopedic guided tour of “quant” investment strategies, from the simplest ones (like trend following) to much more exotic ones using sophisticated derivative contracts. No claim is made about the profitability of these strategies: one knows all too well how much implementation details and transaction costs matter. But no quant trader can afford ignoring what’s out there, as a source of inspiration or as a benchmark for new ideas.”

–Jean-Philippe Bouchaud, Chairman and Chief Scientist, Capital Fund Management; Professor, Ecole Normale Sup´erieure; Member, French Academy of Sci- ´ ences; and Co-Director, CFM-Imperial Institute of Quantitative Finance

“Zura Kakushadze and Juan Andr´es Serur have created a masterful encyclopedia of quantitative trading strategies. The authors offer us a rigorous but accessible treatment of the mathematical foundations of these strategies. The coverage is comprehensive, starting with simple and well-known strategies such as covered call and then moving naturally to strategies involving cryptocurrencies. The supporting material such as a detailed glossary and an extensive list of references will make this book an essential reference for financial economists and investment professionals.”

–Hossein Kazemi, Michael & Cheryl Philipp Endowed Professor of Finance, University of Massachusetts at Amherst; and Editor-in-Chief, The Journal of Alternative Investments

“The successful trading of financial instruments is both a science and an art, just as the efforts of a chef reflect both gastronomic artistry and the underlying chemical and thermal processes of cooking. In 151 Trading Strategies financial traders are provided with a compendium of sound recipes, spanning the broad range of methods that can be applied to modern investment practice. The exposition of both the mathematics and intuition of each described trade is clear and concise. Readers will appreciate the inclusion of extensive computer code so as to reduce effort needed to implement any required calculations.”

–Dan diBartolomeo, President, Northfield Information Services; and Editor, Journal of Asset Management

“A real tour de force–151 Trading Strategies provides the most comprehensive un-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

covering of popular hedge fund strategies. By revealing all the hedge funds’ secret sauce, Kakushadze and Serur have now rendered everything as beta-strategies. Time to lower ’em fees!”

–Jim Kyung-Soo Liew, Assistant Professor of Finance, Carey Business School, Johns Hopkins University; Advisory Board Member, The Journal of Portfolio Management; and Co-Founder, SoKat

“This book is an impressive concentration of strategies and formulas to expand knowledge in quantitative finance; it’s a must-read for anyone who wants to drastically improve his or her expertise in financial markets dynamics.”

–Daniele Bernardi, CEO, DIAMAN Capital; and Chairman of the Board, INVESTORS’ Magazine Italia

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## Author Biographies

Zura Kakushadze received his Ph.D. in theoretical physics from Cornell University, USA at 23, was a Postdoctoral Fellow at Harvard University, USA and an Assistant Professor at C.N. Yang Institute for Theoretical Physics at Stony Brook University, USA. He received an Alfred P. Sloan Foundation Fellowship in 2001. After expanding into quantitative finance, he was a Director at RBC Capital Markets, Managing Director at WorldQuant, Executive Vice President and substantial shareholder at Revere Data (now part of FactSet), and Adjunct Professor at the University of Connecticut, USA. Currently he is the President and CEO of Quantigicr Solutions and a Full Professor at Free University of Tbilisi, Georgia. He has over 17 years of hands-on experience in quantitative trading and finance, 130+ publications in physics, finance, cancer research and other fields, 3,400+ citations and h-index 30+, 170,000+ downloads on SSRN, and over a quarter million followers on LinkedIn.

Juan Andr´es Serur holds a Master’s Degree in Finance from the University of CEMA, Argentina. With more than 6 years of experience in trading in the stock market, he currently works as a quantitative analyst and strategist in an Argentine quantitative asset management firm and as a financial consultant for large corporations. In addition, he serves as the Academic Secretary of the Master of Finance Program at the University of CEMA, where he teaches undergraduate and postgraduate computational finance courses as an Assistant Professor. In 2016 he won the First Prize in an Argentine Capital Markets Simulation Challenge for Universities and Professional Institutions.

## Preface (by Zura Kakushadze)

The purpose of this “post-factum” Preface is to give some history, which sheds light on why we (the authors) have decided to make this book, which has been published in hardcover (and as an e-book),4 into a freely downloadable PDF e-book on SSRN.

In December of 2015 I posted the paper “101 Formulaic Alphas” on SSRN [Kakushadze, 2016], which provides explicit formulas (that are also computer source code) for 101 real-life formulaic quantitative trading alphas. That paper was a hit – in hindsight, perhaps unsurprisingly, considering how secretive quant trading is.

So, at some point down the road, a light bulb went on in my head and I got this seemingly “crazy” idea to write a paper entitled “101 Trading Strategies”, except that this time these 101 strategies would be spread across all asset classes (as opposed to equities (StatArb) quant trading alphas as in “101 Formulaic Alphas”). I did not envision this as a book, just as a paper, maybe 100+ pages long, 1 page per strategy on average, plus overhead (introduction, references, etc.), something publishable in a journal (at least online). I also thought it would be both fun and efficient to get around 10-12 coauthors together, each would contribute about 10 strategies in one or two asset classes according to their fields of expertise, so the project would go faster. So, I pinged my contacts by email and posted several posts in the LinkedIn feed and groups saying that I was looking for collaborators for this project. I got a rather decent number of responses, some evidently were not serious, but some were.

However, once I outlined in more detail what I had in mind for this project – I had a written plan – apparently people realized that this would not be a cakewalk, and most disappeared. As it turned out, the only person who was truly serious about this project was Juan Andr´es Serur, a young professor from Buenos Aires, Argentina, whom I had never even met in person. There were a lot of challenges along the way (including that Juan had never worked on a project of this magnitude and was learning on the job, so to speak). But at the end we got through it. Except that we did not have just 100+ pages with 101 strategies but over 350 pages with around 160-170 strategies (depending on how one counts). This was not publishable in any journal, by any stretch. This project basically had taken on a life of its own and turned into... a book. So, we discussed it and decided to publish it as such.

Publishing a quant trading/finance book such as “151 Trading Strategies” is not a very rewarding business (at least financially), for several reasons. First, the target audience is rather limited because of the highly technical nature of the material. In my original exploratory call with them, the publisher mentioned that books like this sell around 1,000 copies total. This was consistent with what I was told by someone who is well-known in the field and had published 5 quant trading/finance books over the years, which had sold around 5,000 copies altogether. Second, if the book is published by a major publisher, the authors get dismal royalties, usually in the 8-12% range, which can go to around 20% if the book sells better than

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

expected. At \$60-\$70 for a hardcover, your book has to sell 100,000+ copies for you to make any decent money so it is a least somewhat commensurate with the time you spend on writing the book – this book took about 9 months to write, not including the time I spent on it before drafting started (conceiving it, looking for coauthors, etc.) or the time spent dealing with the publisher, advertising it, etc. Third, this particular publisher does not publish paperbacks as a matter of some policy I do not comprehend, and when the price is set around \$60-\$70 for a hardcover, the pool of potential buyers is dramatically reduced compared with a \$20-\$30 price point a paperback would have. Fourth, there are plenty of people working in quant trading/finance who can easily afford \$60-\$70, but many of these people – not to offend anyone – would rather download a pirated PDF copy from the internet... Fifth, the publisher’s business model appears to be immune to the fact that they cannot make much money from hardcover sales. Instead, their business model appears to hinge on e-book downloads through their existing (institutional) subscriptions: a subscriber, who pays a subscription fee, can freely download any book from the publisher’s portfolio. So, the success of a book is measured by e-book downloads by subscribers, not by hardcover sales, and the authors do not get paid per download, they only get paid a very symbolic (mildly put) flat fee irrespective of the number of such downloads. The bottom line is that there is no money to be made in this business for the authors. We were well-aware of this from the get-go. We did not publish this book for money – originally, it was going to be a paper.

What is worse though is that, unlike in the olden days when editors would read every word of your manuscript and mark it up so it could be improved, etc., nowadays there appears to be little to no editorial support. We wrote the manuscript in LaTeX (as there are over 550 elevated equations in the book, not counting inline math), we created the index ourselves (which is a major pain and very time-consuming, if done right; in fact, it is probably the single worst part of writing a book), and proofread the manuscript several times to the point where upon the final proofreading right before printing we found only 5 minor typos attributable to our original manuscript. The bottom line is that we spent a lot of time perfecting our manuscript and it was very much print-ready. However, things got really messy on the publisher’s end.

The nightmare started with the book cover. The publisher ask me if I had any concrete ideas for how I wanted the cover designed, and if I had a specific cover image in mind and to feel free to send along some images from Getty and Alamy (the image providers the publisher uses). I was taken aback. They keep almost all the profits and they ask me for the cover design? If we have to design our own cover, then we might as self-well publish and keep most royalties. I told them to design the cover professionally, as this was their responsibility. Their so-called “designs” they forwarded were highly unimpressive (just really super-minimalist – mildly put). So, I ended up designing the cover myself, including picking the cover image from the library of thousands of available images, placing the title and author names on the cover, etc. Their “design team” used my cover design and the only “substantial” change they made was changing the color of the title fonts to (in my

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

humble opinion) suboptimal white – the publisher said they could not accommodate the color I suggested. So, imagine how appalled and taken aback I was when in the ready-to-publish final book version, on the copyright page, they put some name for the cover design credit, and did not even mention mine. They said the cover design “is theirs”, apparently referring to their “design team”. This was just factually false. But we did not wish to appear “difficult” or “unaccommodating”, so we let this go.

However, the nightmare continued with author biographies on an inside flap of the dust jacket. They asked us to provide our headshots. We did. At least three times they produced the author biographies with one of the headshots sizably larger than the other, even though we provided identically sized headshots. Worse yet, they claimed that the headshots on the dust jacket were the same size when they clearly were not. So, again, not to appear “difficult” or “unaccommodating”, having wasted an inordinate amount of time on this, we let them leave our headshots out of the inside flap as their “design team” either could not or would not get them right.

Little did we know that this was only the tip of the iceberg. When we finally (and belatedly) received the proofs from the publisher, we found over 100 typos introduced by the publisher’s typesetters in most incomprehensible ways. Worse yet, the one inadvertent grammar typo we did have in our original manuscript (along with four other, more subtle, non-grammar typos) was not fixed. It was painfully evident that they did not proofread the manuscript very carefully – them creating 100+ unfathomable typos speaks volumes. So, we spent countless additional hours fixing their typos, and it took more than one round of revisions for them to get it right. In hindsight, this should come as no surprise: as many other publishers, they apparently outsource typesetting, copyediting, cover design, etc., to a developing country, and I highly doubt that, e.g., the English proficiency on the other end of this outsourcing process is top-notch. It is the all-familiar and prevalent sad story: English-language books are produced by people whose first language is not English.

Finally, the book was online. However, the nightmare continued. There is an appendix in the book with computer source code and a lengthy discussion. This appendix was just another chapter in the book and was not supposed to be a part of the free preview of the book, which we expressly discussed and agreed on with the publisher in writing to be limited to the first two chapters. Yet, they included the appendix in the back matter of the book, which is freely downloadable from the publisher’s website along with the front matter. When I pointed this out to the publisher, their reply was that, for them to redo the files, it would delay the release of the book accordingly (and, based on prior history, that meant weeks, if not longer). This was already after multiple delays on the publisher’s end. So, once again, not to appear “difficult” or “unaccommodating”, we let this go and the appendix stayed in the freely-downloadable back matter. Speaking of which, while in our original manuscript all references were in one place, at the end, in the published version the references were cited at the end of each chapter. However, the publisher – for the reasons we do not comprehend – also kept the full list of references in the freelydownloadable back matter. While in the modular (where all chapters, front matter

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

and back matter have separate PDF files) electronic e-book version this is not a big deal, they actually also included these duplicate references in the back matter in the printed version, which substantially (and artificially) increased its number of pages.

But there is more. One would imagine that their production team would do some basic quality control post-production. Months later we found out that the Kindle version on Amazon was all messed up, with equations not displaying properly, etc. The publisher claimed that they provided correct files to Amazon and that the problem was on Amazon’s end. It took them several weeks to fix this issue, and the fix was a “hack”: they replaced the Kindle version with the so-called “replica” version, which is just a replica of the PDF. Anyone can easily create a “replica” version from a PDF using Kindle Create – this does not take a leading publisher. Furthermore, the Kindle preview version displays material substantially outside of the preview material we agreed on. But then again, who cares about the authors?

Nor did the publisher seem to care much about the apparent pirated versions of the book PDF appearing on various websites. Basically, it was unclear what, if anything, the publisher was doing for the book. Their entire marketing effort was apparently limited to whopping two tweets they sent when the book was published. Essentially all the marketing efforts came from me promoting the book on LinkedIn (where I have over quarter million followers) by posting links to the preview version then-available on SSRN and the full version/hardcover on the publisher’s websites.

Perhaps most unfathomably, not only did the publisher apparently did not do much to protect the book from pirated copies being available on the internet, or to promote the book, they outright refused to refute a factually false and defamatory “review” an anonymous purchaser placed on Amazon. E.g., that review falsely claims that “there is only a tiny paragraph (no more than 10 lines), very general, on each strategy and then close to 10 pages of book references after each strategy.” This is factually false: there are not “10 pages of book references after each strategy”. There are references after each chapter (not strategy or section) pursuant to the publisher’s own formatting (see above). The review also falsely claims that “A 10 line description of a very general strategy, no math, no backrest, no optimization.” Again, this is factually false: as the reader can readily see, the book has over 550 elevated equations (not counting lots of math embedded in the text), the source code for backtesting in Appendix A, strategies involving optimization, 900+ glossary terms, acronyms and math definitions, etc. Furthermore, simpler strategies have concise (but precise) descriptions, while others span pages, not “10 lines”, contrary to what the review falsely claims. The review also complains about the number of references in the book. The book description on Amazon (as well as the publisher’s websites) expressly states that there are around 2,000 bibliographic references in the book, one of whose aims is to serve as a reference guide into (and essentially an encyclopedia of) trading strategies (which is also stated in the Editorial Reviews of the book). Therefore, the anonymous reviewer was well aware of this before purchasing the book. The review further falsely claims: “And then, as if it were not enough, at the end of the book the author recaps all the references

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

one more time.” The review is expressly attacking “the author” of the book, even though, as mentioned above, the specific formatting of the references (whereby the references pertinent to each chapter are included after each chapter, and all references are also included in the back matter, which is freely downloadable from the publisher’s website) was performed by the publisher, not by the authors. Our original manuscript has references only at the end. Again, as mentioned above, why the publisher duplicated the references both after the chapters and in the back matter is not something we understand, and it is not something we did or had control over, contrary to the anonymous reviewer’s factually false and defamatory statements.

When we discovered the aforesaid factually false and defamatory review on Amazon, we contacted the publisher and asked them, at the minimum to put a comment on the review refuting its factually false statements, and also to contact Amazon to remove the review (as under Amazon’s policies, defamatory reviews are not allowed). To our bewilderment, the publisher suggested that we use our contacts to generate positive reviews on Amazon to counteract that negative review. Incredible, isn’t it?

To be clear, having over a quarter million followers on LinkedIn and putting lots of content out there on social media, I have had my share of haters. And one thing I have learned is that there is some truth to the common expression “haters make us famous”. When you write a paper or a book or anything else you stick your neck out with, it comes with the territory: some will love it, some will hate it, and some will not care. I write things for the “some-will-love-it” demographic and I do not care about the rest. However, there is a big difference between someone expressing a negative opinion about what you have written – this is perfectly acceptable, we live in a free country with freedom of speech – and someone making factually false and defamatory statements, which is not acceptable. And when you write a book and grant the publisher all kinds of rights for the book, it falls onto the publisher to protect its integrity and reputation, as the publisher owns the rights to the book.

There is a lesson to be learned from all this. That a large publisher will do little to nothing to protect the integrity and reputation of the book or its authors (especially if it involves a potential headache with Amazon) or to promote the book. So, as an author, you do all the hard work, and your publisher just takes over your sweat-and-blood creation, makes money from it, while you do all the work promoting the book, with little to no support from the publisher, including protecting the book from, e.g., being pirated on the internet, defamed, etc. Is this fair? Absolutely not!

So, we have terminated the publishing agreement and are making our work free for everyone to download and benefit from the knowledge we have compiled in this now-free e-book. We hope you enjoy it and thanks for reading our book and our story, which hopefully will also be useful to other authors contemplating publishing a book. Consider this. Without real editorial support, when you have to design the book cover, deal with a large number of typos introduced by the typesetters, etc., is publishing with a big-name publisher all that different from “vanity publishing”?

Finally, I will let you read the book. Innovate. Disrupt. Spread the knowledge.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 1 Introduction and Summary

A trading strategy can be defined as a set of instructions to achieve certain asset holdings by some predefined times $t _ { 1 } , t _ { 2 } , \ldots$ , which holdings can (but need not) be null at one or more of these times. In many cases, the main objective of a trading strategy is to make a profit, i.e., to generate a positive return on its investment. However, some viable trading strategies are not always outright profitable as standalone strategies. E.g., a hedging strategy can be a part of a bigger plan, which itself can but need not be a trading strategy. Thus, an airline hedging against rising fuel costs with commodity futures is a trading strategy, which is a risk-management step in executing the airline’s business strategy of generating profits through its services.

In the case of trading strategies that are intended to be outright profitable as stand-alone strategies, one may argue that the phrase “buy low, sell high” captures their essence. However this viewpoint is somewhat superfluous and, while it applies to trading strategies that buy and sell a single asset (e.g., a single stock), it would exclude a whole host of viable strategies that do not work quite like that. E.g., a trading strategy that uses a hedging sub-strategy for risk management may not always “buy low, sell high” when it comes to a particular asset in its portfolio. This is because hedging risk – or, essentially, transferring some risk to other market participants – is not free, and often a trader will pay a premium for hedging some risks in a trading strategy to achieve its objectives. Another example would be the so-called statistical arbitrage, wherein the trading portfolio can consist of, e.g., thousands of stocks and profitability is typically not achieved by buying low and selling high each stock or even any discernable groups of stocks, but statistically, across all stocks, with some trades making money and some losing it. It gets complicated quickly.

The purpose of these notes is to collect a variety of trading strategies in the context of finance (as opposed to trading baseball cards, classic cars, etc.) across essentially all (or at least most frequently encountered) asset classes. Here we deliberately use the term “asset class” somewhat loosely and include what can be referred to as “asset sub-classes”. Thus, a narrower definition would include stocks, bonds, cash, currencies, real estate, commodities and infrastructure. However, this definition would be too narrow for our purposes here. We also consider: derivatives such as options and futures; exchange-traded funds (ETFs); indexes (which are usually traded through vehicles such as ETFs and futures); volatility, which can be treated as an asset class (and traded via, among other things, exchange-traded notes); structured assets (such as collateralized debt obligations and mortgage-backed securities); convertible bonds (which represent a hybrid between bonds and stocks); distressed assets (which are not a separate asset class per se, but the corresponding trading strategies are rather distinct); cryptocurrencies; miscellaneous assets such as weather and energy (derivatives); and also trading strategies such as tax arbitrage and global macro (which use some assets mentioned above as tradables). Some strategies are relatively simple and can be described in words, while many (in fact, most) require a much more detailed mathematical description, which we provide formulaically.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

It is important to bear in mind that, unlike the laws of nature (physics), which (apparently) are set in stone and do not change in time, financial markets are manmade and change essentially continuously, and at times quite dramatically. One of the consequences of this transiency is that trading strategies that may have worked well for some time, may die, sometimes quite abruptly. E.g., when the New York Stock Exchange (NYSE) started switching away from its human-operated “specialist” system to electronic trading beginning late 2006,5 many statistical arbitrage strategies that were profitable for years prior to that, pretty much died overnight as volatility increased and what used to do the trick before no longer did. Eventually the market was flooded with high frequency trading (HFT)6 strategies further diminishing profit margins of many “good old” trading strategies and killing them.

However, technological advances gave rise to new types of trading, including ubiquitous trading strategies based on data mining and machine learning, which seek to identify – typically quite ephemeral – signals or trends by analyzing large volumes of diverse types of data. Many of these trading signals are so faint that they cannot be traded on their own, so one combines thousands, in fact, tens or even hundreds of thousands if not millions of such signals with nontrivial weights to amplify and enhance the overall signal such that it becomes tradable on its own and profitable after trading costs and slippage, including that inflicted by HFT.7

Considering the intrinsically ephemeral nature of the financial markets and trading strategies designed to make a profit therefrom, the purpose of these notes is not to convey to the reader how to make money using any trading strategy but simply to provide information on and give some flavor of what kind of trading strategies people have considered across a broad cross-section of asset classes and trading styles. In light of the foregoing, we make the following DISCLAIMER: Any information or opinions provided herein are for informational purposes only and are not intended, and shall not be construed, as an investment, legal, tax or any other such advice, or an offer, solicitation, recommendation or endorsement of any trading strategy, security, product or service. For further legal disclaimers, see Appendix B hereof.

We hope these notes will be useful to academics, practitioners, students and aspiring researchers/traders for years to come. These notes intentionally – not to duplicate prior literature and to avoid this manuscript spanning thousands of pages – do not contain any numeric simulations, backtests, empirical studies, etc. However, we do provide an eclectic cornucopia of references, including those with detailed empirical analyses. Our purpose here is to describe, in many cases in sizable detail, various trading strategies. Also, Appendix A provides source code for illustrating out-of-sample backtesting (see Appendix B for legalese).8 So, we hope you enjoy!

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 2 Options

## 2.1 Generalities

An option is a form of a financial derivative. It is a contract sold by the option writer to the option holder. Typically, an option gives the option holder the right, but not the obligation, to buy or sell an underlying security or financial asset (e.g., a share of common stock) at an agreed-upon price (referred to as the strike price) during a certain period of time or on a specific date (referred to as the exercise date). A buyer pays a premium to the seller for the option. For option pricing, see, e.g., [Harrison and Pliska, 1981], [Baxter and Rennie, 1996], [Hull, 2012], [Kakushadze, 2015a].

A European call option is a right (but not an obligation) to buy a stock at the maturity time T for the strike price k agreed on at time t = 0. The claim for the call option $f ^ { c a l l } ( S _ { T } , k ) = ( S _ { T } - k ) ^ { + }$ . Here $( x ) ^ { + } = x { \mathrm { ~ i f ~ } } x > 0$ , and $( x ) ^ { + } = 0 { \mathrm { ~ i f ~ } } x \leq 0$ . By the “claim” we mean how much the option is worth at maturity T . If the stock price at maturity $S _ { T } > k$ , then the option holder gains $S _ { T } - k$ (excluding the cost paid for the option at $t = 0 )$ . If the price at maturity $S _ { T } \leq k$ , then there is no profit to be made from the option as it makes no sense to exercise it if $S _ { T } < k$ (as it is cheaper to buy the stock in the market) and it makes no difference if $S _ { T } = k \mathrm { ~ - ~ } \mathrm { a l l }$ this is assuming no transaction costs. Similarly, a European put option is a right (but not an obligation) to sell a stock at the maturity time T for the strike price k agreed on at time t = 0. The claim for the put option is given by $f ^ { p u t } ( S _ { T } , k ) = ( k - S _ { T } ) ^ { + }$

Options can be issued on a variety of underlying assets, e.g., equities (singlestock options), bonds, futures, indexes, commodities, currencies, etc. For the sake of terminological convenience and definiteness, in the following we will frequently refer to the underlying asset as “stock”, even though in many cases the discussion can be readily generalized to other assets. Furthermore, there is a variety of option styles (beyond European options – for European options, see, e.g., [Black and Scholes, 1973]), e.g., American options (that can be exercised on any trading day on or before expiration – see, e.g., [Kim, 1990]), Bermudan options (that can be exercised only on specified dates on or before expiration – see, e.g., [Andersen, 1999]), Canary options (that can be exercised, say, quarterly, but not before a determined time period, say, 1 year, has elapsed – see, e.g., [Henrard, 2006]), Asian options (whose payoff is determined by the average underlying price over some preset time period – see, e.g., [Rogers and Shi, 1995]), barrier options (which can be exercised only if the underlying security’s price passes a certain level or “barrier” – see, e.g., [Haug, 2001]), other exotic options (a broad category of options that typically are complexly structured – see, e.g., [Fabozzi, 2002]), etc. Let us also mention binary (a.k.a. allor-nothing or digital) options (that pay a preset amount, say, \$1, if the underlying security meets a predefined condition on expiration, otherwise they simply expire without paying anything to the holder – see, e.g., [Breeden and Litzenberger, 1978]).

Some trading strategies can be built using, e.g., combinations of options. Such trading strategies can be divided into two groups: directional and non-directional.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Directional strategies imply an expectation on the direction of the future stock price movements. Non-directional (a.k.a. neutral) strategies are not based on the future direction: the trader is oblivious to whether the stock price goes up or down.

Directional strategies can be divided into two subgroups: (i) bullish strategies, where the trader profits if the stock price goes up; and (ii) bearish strategies, where the trader profits if the stock price goes down. Non-directional strategies can be divided into two subgroups: (a) volatility strategies that profit if the stock has large price movements (high volatility environment); and (b) sideways strategies that profit if the stock price remains stable (low volatility environment). Also, one can distinguish income, capital gain, hedging strategies, etc. (see, e.g., [Cohen, 2005]).

In the remainder of this section, unless stated otherwise, all options are for the same stock and have the same time-to-maturity (TTM). The moneyness abbreviations are: ATM = at-the-money, ITM = in-the-money, OTM = out-of-the-money. Also: $f _ { T }$ is the payoff at maturity $T \colon S _ { 0 }$ is the stock price at the time $t = 0$ of entering the trade (i.e., establishing the initial position); $S _ { T }$ is the stock price at maturity; C is the net credit received at $t = 0$ , and D is the net debit required at $t = 0$ , as applicable; $H = D$ (for a net debit trade) or $H = - C$ (for a net credit trade);9 $S _ { \ast u p }$ and $S _ { \ast d o w n }$ are the higher and lower break-even (i.e., for which $f _ { T } = 0 )$ stock prices at maturity; if there is only one break-even price, it is denoted by $S _ { * } ;$ $P _ { m a x }$ is the maximum profit at maturity; $L _ { m a x }$ is the maximum loss at maturity.

## 2.2 Strategy: Covered call

This strategy (a.k.a. “buy-write” strategy) amounts to buying stock and writing a call option with a strike price K against the stock position. The trader’s outlook on the stock price is neutral to bullish. The covered call strategy has the same payoff as writing a put option (short/naked put).10 While maintaining the long stock position, the trader can generate income by periodically selling OTM call options. We have:11

$$
f _ { T } = S _ { T } - S _ { 0 } - ( S _ { T } - K ) ^ { + } + C = K - S _ { 0 } - ( K - S _ { T } ) ^ { + } + C\tag{1}
$$

$$
S _ { * } = S _ { 0 } - C\tag{2}
$$

$$
P _ { m a x } = K - S _ { 0 } + C\tag{3}
$$

$$
L _ { m a x } = S _ { 0 } - C\tag{4}
$$

## 2.3 Strategy: Covered put

This strategy (a.k.a. “sell-write” strategy) amounts to shorting stock and writing a put option with a strike price K against the stock position. The trader’s outlook is

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

neutral to bearish. The covered put strategy has the same payoff as writing a call option (short/naked call). While maintaining the short stock position, the trader can generate income by periodically selling OTM put options. We have:12

$$
f _ { T } = S _ { 0 } - S _ { T } - ( K - S _ { T } ) ^ { + } + C = S _ { 0 } - K - ( S _ { T } - K ) ^ { + } + C\tag{5}
$$

$$
S _ { * } = S _ { 0 } + C\tag{6}
$$

$$
P _ { m a x } = S _ { 0 } - K + C\tag{7}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{8}
$$

## 2.4 Strategy: Protective put

This strategy (a.k.a. “married put” or “synthetic call”) amounts to buying stock and an ATM or OTM put option with a strike price $K \leq S _ { 0 }$ . The trader’s outlook is bullish. This is a hedging strategy: the put option hedges the risk of the stock price falling. We have:13

$$
f _ { T } = S _ { T } - S _ { 0 } + ( K - S _ { T } ) ^ { + } - D = K - S _ { 0 } + ( S _ { T } - K ) ^ { + } - D\tag{9}
$$

$$
S _ { * } = S _ { 0 } + D\tag{10}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{11}
$$

$$
L _ { m a x } = S _ { 0 } - K + D\tag{12}
$$

## 2.5 Strategy: Protective call

This strategy (a.k.a. “married call” or “synthetic put”) amounts to shorting stock and buying an ATM or OTM call option with a strike price $K \geq S _ { 0 }$ . The trader’s outlook is bearish. This is a hedging strategy: the call option hedges the risk of the stock price rising. We have:14

$$
f _ { T } = S _ { 0 } - S _ { T } + ( S _ { T } - K ) ^ { + } - D = S _ { 0 } - K + ( K - S _ { T } ) ^ { + } - D\tag{13}
$$

$$
S _ { * } = S _ { 0 } - D\tag{14}
$$

$$
P _ { m a x } = S _ { 0 } - D\tag{15}
$$

$$
L _ { m a x } = K - S _ { 0 } + D\tag{16}
$$

## 2.6 Strategy: Bull call spread

This is a vertical spread consisting of a long position in a close to ATM call option with a strike price $K _ { 1 }$ , and a short position in an OTM call option with a higher

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

strike price $K _ { 2 }$ . This is a net debit trade. The trader’s outlook is bullish: the strategy profits if the stock price rises. This is a capital gain strategy. We have:15

$$
f _ { T } = ( S _ { T } - K _ { 1 } ) ^ { + } - ( S _ { T } - K _ { 2 } ) ^ { + } - D\tag{17}
$$

$$
S _ { * } = K _ { 1 } + D\tag{18}
$$

$$
P _ { m a x } = K _ { 2 } - K _ { 1 } - D\tag{19}
$$

$$
L _ { m a x } = D\tag{20}
$$

## 2.7 Strategy: Bull put spread

This is a vertical spread consisting of a long position in an OTM put option with a strike price $K _ { 1 }$ , and a short position in another OTM put option with a higher strike price $K _ { 2 }$ . This is a net credit trade. The trader’s outlook is bullish. This is an income strategy. We have:

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } + C\tag{21}
$$

$$
S _ { * } = K _ { 2 } - C\tag{22}
$$

$$
P _ { m a x } = C\tag{23}
$$

$$
L _ { m a x } = K _ { 2 } - K _ { 1 } - C\tag{24}
$$

## 2.8 Strategy: Bear call spread

This is a vertical spread consisting of a long position in an OTM call option with a strike price $K _ { 1 }$ , and a short position in another OTM call option with a lower strike price $K _ { 2 }$ . This is a net credit trade. The trader’s outlook is bearish. This is an income strategy. We have:

$$
f _ { T } = ( S _ { T } - K _ { 1 } ) ^ { + } - ( S _ { T } - K _ { 2 } ) ^ { + } + C\tag{25}
$$

$$
S _ { * } = K _ { 2 } + C\tag{26}
$$

$$
P _ { m a x } = C\tag{27}
$$

$$
L _ { m a x } = K _ { 1 } - K _ { 2 } - C\tag{28}
$$

## 2.9 Strategy: Bear put spread

This is a vertical spread consisting of a long position in a close to ATM put option with a strike price $K _ { 1 }$ , and a short position in an OTM put option with a lower

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

strike price $K _ { 2 }$ . This is a net debit trade. The trader’s outlook is bearish: this strategy profits if the stock price falls. This is a capital gain strategy. We have:

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } - D\tag{29}
$$

$$
S _ { * } = K _ { 1 } - D\tag{30}
$$

$$
P _ { m a x } = K _ { 1 } - K _ { 2 } - D\tag{31}
$$

$$
L _ { m a x } = D\tag{32}
$$

## 2.10 Strategy: Long synthetic forward

This strategy amounts to buying an ATM call option and selling an ATM put option with a strike price $K = S _ { 0 }$ . This can be a net debit or net credit trade. Typically, $| H | \ll S _ { 0 }$ . The trader’s outlook is bullish: this strategy mimics a long stock or futures position; it replicates a long forward contract with the delivery price K and the same maturity as the options. This is a capital gain strategy. We have:16

$$
f _ { T } = ( S _ { T } - K ) ^ { + } - ( K - S _ { T } ) ^ { + } - H = S _ { T } - K - H\tag{33}
$$

$$
S _ { * } = K + H\tag{34}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{35}
$$

$$
L _ { m a x } = K + H\tag{36}
$$

## 2.11 Strategy: Short synthetic forward

This strategy amounts to buying an ATM put option and selling an ATM call option with a strike price $K = S _ { 0 }$ . This can be a net debit or net credit trade. Typically, $| H | \ll S _ { 0 }$ . The trader’s outlook is bearish: this strategy mimics a short stock or futures position; it replicates a short forward contract with the delivery price K and the same maturity as the options. This is a capital gain strategy. We have:

$$
f _ { T } = ( K - S _ { T } ) ^ { + } - ( S _ { T } - K ) ^ { + } - H = K - S _ { T } - H\tag{37}
$$

$$
S _ { * } = K - H\tag{38}
$$

$$
P _ { m a x } = K - H\tag{39}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{40}
$$

## 2.12 Strategy: Long combo

This strategy (a.k.a. “long risk reversal”) amounts to buying an OTM call option with a strike price $K _ { 1 }$ and selling an OTM put option with a strike price $K _ { 2 }$ . The

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

trader’s outlook is bullish. This is a capital gain strategy.17 We have $( K _ { 1 } > K _ { 2 } )$

$$
f _ { T } = ( S _ { T } - K _ { 1 } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } - H\tag{41}
$$

$$
S _ { * } = K _ { 1 } + H , \quad H > 0\tag{42}
$$

$$
S _ { * } = K _ { 2 } + H , \quad H < 0\tag{43}
$$

$$
K _ { 2 } \leq S _ { * } \leq K _ { 1 } , \quad H = 0\tag{44}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{45}
$$

$$
L _ { m a x } = K _ { 2 } + H\tag{46}
$$

## 2.13 Strategy: Short combo

This strategy (a.k.a. “short risk reversal”) amounts to buying an OTM put option with a strike price $K _ { 1 }$ and selling an OTM call option with a strike price $K _ { 2 }$ . The trader’s outlook is bearish. This is a capital gain strategy. We have $( K _ { 2 } > K _ { 1 } )$ :

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } - ( S _ { T } - K _ { 2 } ) ^ { + } - H\tag{47}
$$

$$
S _ { * } = K _ { 1 } - H , \quad H > 0\tag{48}
$$

$$
S _ { * } = K _ { 2 } - H , \quad H < 0\tag{49}
$$

$$
K _ { 1 } \leq S _ { * } \leq K _ { 2 } , \quad H = 0\tag{50}
$$

$$
P _ { m a x } = K _ { 1 } - H\tag{51}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{52}
$$

## 2.14 Strategy: Bull call ladder

This is a vertical spread consisting of a long position in (usually) a close to ATM call option with a strike price $K _ { 1 }$ , a short position in an OTM call option with a strike price $K _ { 2 }$ , and a short position in another OTM call option with a higher strike price $K _ { 3 }$ . A bull call ladder is a bull call spread financed by selling another OTM call option (with the strike price $K _ { 3 } )$ .18 This adjusts the trader’s outlook from bullish (bull call spread) to conservatively bullish or even non-directional (with an expectation of low volatility). We have:

$$
f _ { T } = ( S _ { T } - K _ { 1 } ) ^ { + } - ( S _ { T } - K _ { 2 } ) ^ { + } - ( S _ { T } - K _ { 3 } ) ^ { + } - H\tag{53}
$$

$$
S _ { * d o w n } = K _ { 1 } + H , \quad H > 0\tag{54}
$$

$$
S _ { * u p } = K _ { 3 } + K _ { 2 } - K _ { 1 } - H\tag{55}
$$

$$
P _ { m a x } = K _ { 2 } - K _ { 1 } - H\tag{56}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{57}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 2.15 Strategy: Bull put ladder

This is a vertical spread consisting of a short position in (usually) a close to ATM put option with a strike price $K _ { 1 }$ , a long position in an OTM put option with a strike price $K _ { 2 }$ , and a long position in another OTM put option with a lower strike price $K _ { 3 }$ . A bull put ladder typically arises when a bull put spread (a bullish strategy) goes wrong (the stock trades lower), so the trader buys another OTM put option (with the strike price $K _ { 3 } )$ to adjust the position to bearish. We have:19

$$
f _ { T } = ( K _ { 3 } - S _ { T } ) ^ { + } + ( K _ { 2 } - S _ { T } ) ^ { + } - ( K _ { 1 } - S _ { T } ) ^ { + } - H\tag{58}
$$

$$
S _ { \ast u p } = K _ { 1 } + H , \quad H < 0\tag{59}
$$

$$
S _ { * d o w n } = K _ { 3 } + K _ { 2 } - K _ { 1 } - H\tag{60}
$$

$$
P _ { m a x } = K _ { 3 } + K _ { 2 } - K _ { 1 } - H\tag{61}
$$

$$
L _ { m a x } = K _ { 1 } - K _ { 2 } + H\tag{62}
$$

## 2.16 Strategy: Bear call ladder

This is a vertical spread consisting of a short position in (usually) a close to ATM call option with a strike price $K _ { 1 }$ , a long position in an OTM call option with a strike price $K _ { 2 }$ , and a long position in another OTM call option with a higher strike price $K _ { 3 }$ . A bear call ladder typically arises when a bear call spread (a bearish strategy) goes wrong (the stock trades higher), so the trader buys another OTM call option (with the strike price $K _ { 3 } )$ to adjust the position to bullish. We have:

$$
f _ { T } = ( S _ { T } - K _ { 3 } ) ^ { + } + ( S _ { T } - K _ { 2 } ) ^ { + } - ( S _ { T } - K _ { 1 } ) ^ { + } - H\tag{63}
$$

$$
S _ { * d o w n } = K _ { 1 } - H , \quad H < 0\tag{64}
$$

$$
S _ { * u p } = K _ { 3 } + K _ { 2 } - K _ { 1 } + H\tag{65}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }
$$

$$
L _ { m a x } = K _ { 2 } - K _ { 1 } + H\tag{66}
$$

(67)

## 2.17 Strategy: Bear put ladder

This is a vertical spread consisting of a long position in (usually) a close to ATM put option with a strike price $K _ { 1 }$ , a short position in an OTM put option with a strike price $K _ { 2 }$ , and a short position in another OTM put option with a lower strike price $K _ { 3 }$ . A bear put ladder is a bear put spread financed by selling another OTM put option (with the strike price $K _ { 3 } )$ .20 This adjusts the trader’s outlook from bearish (bear put spread) to conservatively bearish or even non-directional (with an

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

expectation of low volatility). We have (assuming $K _ { 3 } + K _ { 2 } - K _ { 1 } + H > \operatorname* { m a x } ( H , 0 ) )$

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } - ( K _ { 3 } - S _ { T } ) ^ { + } - H\tag{68}
$$

$$
S _ { \ast u p } = K _ { 1 } - H , \quad H > 0\tag{69}
$$

$$
S _ { * d o w n } = K _ { 3 } + K _ { 2 } - K _ { 1 } + H\tag{70}
$$

$$
P _ { m a x } = K _ { 1 } - K _ { 2 } - H\tag{71}
$$

$$
L _ { m a x } = K _ { 3 } + K _ { 2 } - K _ { 1 } + H\tag{72}
$$

## 2.18 Strategy: Calendar call spread

This is a horizontal spread consisting of a long position in a close to ATM call option with TTM $T ^ { \prime }$ and a short position in another call option with the same strike price K but shorter TTM $T < T ^ { \prime }$ . This is a net debit trade. The trader’s outlook is neutral to bullish. At the expiration of the short call option $( t = T )$ , the best case scenario is if the stock price is right at the strike price $( S _ { T } = K )$ . At $t = T$ let V be the value of the long call option (expiring at $t = T ^ { \prime } )$ assuming $S _ { T } = K$ . We have:21

$$
P _ { m a x } = V - D\tag{73}
$$

$$
L _ { m a x } = D\tag{74}
$$

If at the expiration of the short call option the stock price $S _ { s t o p - l o s s } \leq S _ { T } \leq K _ { \cdot }$ where $S _ { s t o p } .$ −loss is the stop-loss price below which the trader would unwind the entire position, then the trader can write another call option with the strike price K and TTM $T _ { 1 } < T ^ { \prime }$ . While maintaining the long position in the call option with TTM $T ^ { \prime }$ , the trader can generate income by periodically selling call options with shorter maturities. In this regard, this strategy resembles the covered call strategy.

## 2.19 Strategy: Calendar put spread

This is a horizontal spread consisting of a long position in a close to ATM put option with TTM $T ^ { \prime }$ and a short position in another put option with the same strike price K but shorter TTM $T < T ^ { \prime }$ . This is a net debit trade. The trader’s outlook is neutral to bearish. At the expiration of the short put option $( t = T )$ , the best case scenario is if the stock price is right at the strike price $( S _ { T } = K )$ $\mathrm { A t } ~ t = T$ let V be the value of the long put option (expiring at $t = T ^ { \prime } )$ assuming $S _ { T } = K$ . We have:

$$
P _ { m a x } = V - D\tag{75}
$$

$$
L _ { m a x } = D\tag{76}
$$

If at the expiration of the short put option the stock price $K \leq S _ { T } \leq S _ { s t o p - l o s s } ,$ where $S _ { s t o p } .$ −loss is the stop-loss price above which the trader would unwind the

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

entire position, then the trader can write another put option with the strike price $K$ and TTM $T _ { 1 } < T ^ { \prime }$ . While maintaining the long position in the put option with TTM $T ^ { \prime }$ , the trader can generate income by periodically selling put options with shorter maturities. In this regard, this strategy resembles the covered put strategy.

## 2.20 Strategy: Diagonal call spread

This is a diagonal spread consisting of a long position in a deep ITM call option with a strike price $K _ { 1 }$ and TTM $T ^ { \prime }$ , and a short position in an OTM call option with a strike price $K _ { 2 }$ and shorter TTM $T < T ^ { \prime }$ . This is a net debit trade. The trader’s outlook is bullish. $\mathrm { A t } ~ t = T$ let V be the value of the long call option (expiring at $t = T ^ { \prime } )$ assuming $S _ { T } = K$ . We have:

$$
P _ { m a x } = V - D\tag{77}
$$

$$
L _ { m a x } = D\tag{78}
$$

If at the expiration of the short call option the stock price $S _ { s t o p - l o s s } \leq S _ { T } \leq K _ { 2 }$ where $S _ { s t o p - l o s s }$ is the stop-loss price below which the trader would unwind the entire position, then the trader can write another OTM call option with TTM $T _ { 1 } < T ^ { \prime }$ While maintaining the long position in the call option with TTM $T ^ { \prime }$ , the trader can generate income by periodically selling OTM call options with shorter maturities. In this regard, this strategy is similar to the calendar call spread. The main difference is that, in the diagonal call spread the deep ITM call option (unlike the close to ATM call option in the calendar call spread) more closely mimics the underlying stock, so the position is more protected against a sharp rise in the stock price.

## 2.21 Strategy: Diagonal put spread

This is a diagonal spread consisting of a long position in a deep ITM put option with a strike price $K _ { 1 }$ and TTM $T ^ { \prime }$ , and a short position in an OTM put option with a strike price $K _ { 2 }$ and shorter TTM $T < T ^ { \prime }$ . This is a net debit trade. The trader’s outlook is bearish. $\mathrm { A t } ~ t = T$ let V be the value of the long put option (expiring at $t = T ^ { \prime } )$ assuming $S _ { T } = K$ . We have:

$$
P _ { m a x } = V - D\tag{79}
$$

$$
L _ { m a x } = D\tag{80}
$$

If at the expiration of the short put option the stock price $K _ { 2 } \leq S _ { T } \leq S _ { s t o p - l o s s } ,$ where $S _ { s t o p - l o s s }$ is the stop-loss price above which the trader would unwind the entire position, then the trader can write another OTM put option with TTM $T _ { 1 } < T ^ { \prime }$ While maintaining the long position in the put option with TTM $T ^ { \prime }$ , the trader can generate income by periodically selling OTM put options with shorter maturities. In this regard, this strategy is similar to the calendar put spread. The main difference is that, in the diagonal put spread the deep ITM put option (unlike the close to

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

ATM put option in the calendar put spread) more closely mimics the underlying stock, so the position is more protected against a sharp drop in the stock price.

## 2.22 Strategy: Long straddle

This is a volatility strategy consisting of a long position in an ATM call option, and a long position in an ATM put option with a strike price K. This is a net debit trade. The trader’s outlook is neutral. This is a capital gain strategy. We have22:

$$
f _ { T } = ( S _ { T } - K ) ^ { + } + ( K - S _ { T } ) ^ { + } - D\tag{81}
$$

$$
S _ { \ast u p } = K + D\tag{82}
$$

$$
S _ { * d o w n } = K - D\tag{83}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{84}
$$

$$
L _ { m a x } = D\tag{85}
$$

## 2.23 Strategy: Long strangle

This is a volatility strategy consisting of a long position in an OTM call option with a strike price $K _ { 1 }$ , and a long position in an OTM put option with a strike price $K _ { 2 }$ This is a net debit trade. However, because both call and put options are OTM, this strategy is less costly to establish than a long straddle position. The flipside is that the movement in the stock price required to reach one of the break-even points is also more significant. The trader’s outlook is neutral. This is a capital gain strategy. We have:

$$
f _ { T } = ( S _ { T } - K _ { 1 } ) ^ { + } + ( K _ { 2 } - S _ { T } ) ^ { + } - D\tag{86}
$$

$$
S _ { * u p } = K _ { 1 } + D\tag{87}
$$

$$
S _ { * d o w n } = K _ { 2 } - D\tag{88}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }
$$

$$
L _ { m a x } = D\tag{89}
$$

(90)

## 2.24 Strategy: Long guts

This is a volatility strategy consisting of a long position in an ITM call option with a strike price $K _ { 1 } .$ , and a long position in an ITM put option with a strike price $K _ { 2 }$ This is a net debit trade. Since both call and put options are ITM, this strategy

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

is more costly to establish than a long straddle position. The trader’s outlook is neutral. This is a capital gain strategy. We have (assuming $D > K _ { 2 } - K _ { 1 } )$ ):23

$$
f _ { T } = ( S _ { T } - K _ { 1 } ) ^ { + } + ( K _ { 2 } - S _ { T } ) ^ { + } - D\tag{91}
$$

$$
S _ { * u p } = K _ { 1 } + D\tag{92}
$$

$$
S _ { * d o w n } = K _ { 2 } - D\tag{93}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{94}
$$

$$
L _ { m a x } = D - \left( K _ { 2 } - K _ { 1 } \right)\tag{95}
$$

## 2.25 Strategy: Short straddle

This a is sideways strategy consisting of a short position in an ATM call option, and a short position in an ATM put option with a strike price K. This is a net credit trade. The trader’s outlook is neutral. This is an income strategy. We have:

$$
f _ { T } = - ( S _ { T } - K ) ^ { + } - ( K - S _ { T } ) ^ { + } + C\tag{96}
$$

$$
S _ { \ast u p } = K + C\tag{97}
$$

$$
S _ { * d o w n } = K - C\tag{98}
$$

$$
P _ { m a x } = C\tag{99}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{100}
$$

## 2.26 Strategy: Short strangle

This is a sideways strategy consisting of a short position in an OTM call option with a strike price $K _ { 1 }$ , and a short position in an OTM put option with a strike price $K _ { 2 }$ This is a net credit trade. Since both call and put options are OTM, this strategy is less risky than a short straddle position. The flipside is that the initial credit is also lower. The trader’s outlook is neutral. This is an income strategy. We have:

$$
f _ { T } = - ( S _ { T } - K _ { 1 } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } + C\tag{101}
$$

$$
S _ { * u p } = K _ { 1 } + C\tag{102}
$$

$$
S _ { * d o w n } = K _ { 2 } - C\tag{103}
$$

$$
P _ { m a x } = C\tag{104}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{105}
$$

## 2.27 Strategy: Short guts

This is a sideways strategy consisting of a short position in an ITM call option with a strike price $K _ { 1 }$ , and a short position in an ITM put option with a strike price $K _ { 2 }$ . This is a net credit trade. Since both call and put options are ITM, the initial

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

credit is higher than in a short straddle position. The flipside is that the risk is also higher. The trader’s outlook is neutral. This is an income strategy. We have:24

$$
f _ { T } = - ( S _ { T } - K _ { 1 } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } + C\tag{106}
$$

$$
S _ { * u p } = K _ { 1 } + C\tag{107}
$$

$$
S _ { * d o w n } = K _ { 2 } - C\tag{108}
$$

$$
P _ { m a x } = C - \left( K _ { 2 } - K _ { 1 } \right)\tag{109}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{110}
$$

## 2.28 Strategy: Long call synthetic straddle

This volatility strategy (which is the same as a long straddle with the put replaced by a synthetic put) amounts to shorting stock and buying two ATM (or the nearest ITM) call options with a strike price $K .$ . The trader’s outlook is neutral. This is a capital gain strategy.25 We have (assuming $S _ { 0 } \geq K$ and $D > S _ { 0 } - K )$ :

$$
f _ { T } = S _ { 0 } - S _ { T } + 2 \times ( S _ { T } - K ) ^ { + } - D\tag{111}
$$

$$
S _ { * u p } = 2 \times K - S _ { 0 } + D\tag{112}
$$

$$
S _ { * d o w n } = S _ { 0 } - D\tag{113}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{114}
$$

$$
L _ { m a x } = D - ( S _ { 0 } - K )\tag{115}
$$

## 2.29 Strategy: Long put synthetic straddle

This volatility strategy (which is the same as a long straddle with the call replaced by a synthetic call) amounts to buying stock and buying two ATM (or the nearest ITM) put options with a strike price $K$ . The trader’s outlook is neutral. This is a capital gain strategy. We have (assuming $S _ { 0 } \leq K$ and $D > K - S _ { 0 } )$ :

$$
f _ { T } = S _ { T } - S _ { 0 } + 2 \times ( K - S _ { T } ) ^ { + } - D\tag{116}
$$

$$
S _ { \ast u p } = S _ { 0 } + D\tag{117}
$$

$$
S _ { * d o w n } = 2 \times K - S _ { 0 } - D\tag{118}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{119}
$$

$$
L _ { m a x } = D - \left( K - S _ { 0 } \right)\tag{120}
$$

## 2.30 Strategy: Short call synthetic straddle

This sideways strategy (which is the same as a short straddle with the put replaced by a synthetic put) amounts to buying stock and selling two ATM (or the nearest

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

OTM) call options with a strike price K. The trader’s outlook is neutral. This is a capital gain strategy. We have (assuming $S _ { 0 } \leq K )$ :

$$
f _ { T } = S _ { T } - S _ { 0 } - 2 \times ( S _ { T } - K ) ^ { + } + C\tag{121}
$$

$$
S _ { * u p } = 2 \times K - S _ { 0 } + C\tag{122}
$$

$$
S _ { * d o w n } = S _ { 0 } - C\tag{123}
$$

$$
P _ { m a x } = K - S _ { 0 } + C\tag{124}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{125}
$$

## 2.31 Strategy: Short put synthetic straddle

This sideways strategy (which is the same as a short straddle with the call replaced by a synthetic call) amounts to shorting stock and selling two ATM (or the nearest OTM) put options with a strike price K. The trader’s outlook is neutral. This is a capital gain strategy. We have (assuming $S _ { 0 } \geq K )$ :

$$
f _ { T } = S _ { 0 } - S _ { T } - 2 \times ( K - S _ { T } ) ^ { + } + C\tag{126}
$$

$$
S _ { \ast u p } = S _ { 0 } + C\tag{127}
$$

$$
S _ { * d o w n } = 2 \times K - S _ { 0 } - C\tag{128}
$$

$$
P _ { m a x } = S _ { 0 } - K + C\tag{129}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{130}
$$

## 2.32 Strategy: Covered short straddle

This strategy amounts to augmenting a covered call by writing a put option with the same strike price K and TTM as the sold call option and thereby increasing the income. The trader’s outlook is bullish. We have:

$$
f _ { T } = S _ { T } - S _ { 0 } - ( S _ { T } - K ) ^ { + } - ( K - S _ { T } ) ^ { + } + C\tag{131}
$$

$$
S _ { * } = \frac { 1 } { 2 } \left( S _ { 0 } + K - C \right)\tag{132}
$$

$$
P _ { m a x } = K - S _ { 0 } + C\tag{133}
$$

$$
L _ { m a x } = S _ { 0 } + K - C\tag{134}
$$

## 2.33 Strategy: Covered short strangle

This strategy amounts to augmenting a covered call by writing an OTM put option with a strike price $K ^ { \prime }$ and the same TTM as the sold call option (whose strike price is K) and thereby increasing the income. The trader’s outlook is bullish. We have:

$$
f _ { T } = S _ { T } - S _ { 0 } - ( S _ { T } - K ) ^ { + } - ( K ^ { \prime } - S _ { T } ) ^ { + } + C\tag{135}
$$

$$
P _ { m a x } = K - S _ { 0 } + C\tag{136}
$$

$$
L _ { m a x } = S _ { 0 } + K ^ { \prime } - C\tag{137}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 2.34 Strategy: Strap

This is a volatility strategy consisting of a long position in two ATM call options, and a long position in an ATM put option with a strike price K. This is a net debit trade. The trader’s outlook is bullish. This is a capital gain strategy. We have:26

$$
f _ { T } = 2 \times ( S _ { T } - K ) ^ { + } + ( K - S _ { T } ) ^ { + } - D\tag{138}
$$

$$
S _ { \ast u p } = K + \frac { D } { 2 }\tag{139}
$$

$$
S _ { * d o w n } = K - D\tag{140}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{141}
$$

$$
L _ { m a x } = D\tag{142}
$$

## 2.35 Strategy: Strip

This is a volatility strategy consisting of a long position in an ATM call option, and a long position in two ATM put options with a strike price K. This is a net debit trade. The trader’s outlook is bearish. This is a capital gain strategy. We have:

$$
f _ { T } = ( S _ { T } - K ) ^ { + } + 2 \times ( K - S _ { T } ) ^ { + } - D\tag{143}
$$

$$
S _ { \ast u p } = K + D\tag{144}
$$

$$
S _ { \ast d o w n } = K - \frac { D } { 2 }\tag{145}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{146}
$$

$$
L _ { m a x } = D\tag{147}
$$

## 2.36 Strategy: Call ratio backspread

This strategy consists of a short position in $N _ { S }$ close to ATM call options with a strike price $K _ { 1 }$ , and a long position in $N _ { L }$ OTM call options with a strike price $K _ { 2 }$ where $N _ { L } > N _ { S }$ . Typically, $N _ { L } = 2$ and $N _ { S } = 1$ , or $N _ { L } = 3$ and $N _ { S } = 2 $ The trader’s outlook is strongly bullish. This is a capital gain strategy. We have:27

$$
f _ { T } = N _ { L } \times ( S _ { T } - K _ { 2 } ) ^ { + } - N _ { S } \times ( S _ { T } - K _ { 1 } ) ^ { + } - H\tag{148}
$$

$$
S _ { * d o w n } = K _ { 1 } - H / N _ { S } , \quad H < 0\tag{149}
$$

$$
S _ { * u p } = ( N _ { L } \times K _ { 2 } - N _ { S } \times K _ { 1 } + H ) / ( N _ { L } - N _ { S } )\tag{150}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }\tag{151}
$$

$$
L _ { m a x } = N _ { S } \times ( K _ { 2 } - K _ { 1 } ) + H\tag{152}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 2.37 Strategy: Put ratio backspread

This strategy consists of a short position in $N _ { S }$ close to ATM put options with a strike price $K _ { 1 }$ , and a long position in $N _ { L }$ OTM put options with a strike price $K _ { 2 }$ where $N _ { L } > N _ { S }$ . Typically, $N _ { L } = 2$ and $N _ { S } = 1$ , or $N _ { L } = 3$ and $N _ { S } = 2$ The trader’s outlook is strongly bearish. This is a capital gain strategy. We have:

$$
f _ { T } = N _ { L } \times ( K _ { 2 } - S _ { T } ) ^ { + } - N _ { S } \times ( K _ { 1 } - S _ { T } ) ^ { + } - H\tag{153}
$$

$$
S _ { * u p } = K _ { 1 } + H / N _ { S } , \quad H < 0\tag{154}
$$

$$
S _ { * d o w n } = ( N _ { L } \times K _ { 2 } - N _ { S } \times K _ { 1 } - H ) / ( N _ { L } - N _ { S } )\tag{155}
$$

$$
P _ { m a x } = N _ { L } \times K _ { 2 } - N _ { S } \times K _ { 1 } - H\tag{156}
$$

$$
L _ { m a x } = N _ { S } \times ( K _ { 1 } - K _ { 2 } ) + H\tag{157}
$$

## 2.38 Strategy: Ratio call spread

This strategy consists of a short position in $N _ { S }$ close to ATM call options with a strike price $K _ { 1 }$ , and a long position in $N _ { L }$ ITM call options with a strike price $K _ { 2 }$ 2， where $N _ { L } < N _ { S }$ . Typically, $N _ { L } = 1$ and $N _ { S } = 2$ , or $N _ { L } = 2$ and $N _ { S } = 3$ . This is an income strategy if it is structured as a net credit trade. The trader’s outlook is neutral to bearish. We have:28

$$
f _ { T } = N _ { L } \times ( S _ { T } - K _ { 2 } ) ^ { + } - N _ { S } \times ( S _ { T } - K _ { 1 } ) ^ { + } - H\tag{158}
$$

$$
S _ { * d o w n } = K _ { 2 } + H / N _ { L } , \quad H > 0\tag{159}
$$

$$
S _ { * u p } = ( N _ { S } \times K _ { 1 } - N _ { L } \times K _ { 2 } - H ) / ( N _ { S } - N _ { L } )\tag{160}
$$

$$
P _ { m a x } = N _ { L } \times ( K _ { 1 } - K _ { 2 } ) - H
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{161}
$$

(162)

## 2.39 Strategy: Ratio put spread

This strategy consists of a short position in $N _ { S }$ close to ATM put options with a strike price $K _ { 1 }$ , and a long position in $N _ { L }$ ITM put options with a strike price $K _ { 2 }$ ， where $N _ { L } < N _ { S }$ . Typically, $N _ { L } = 1$ and $N _ { S } = 2$ , or $N _ { L } = 2$ and $N _ { S } = 3$ . This is an income strategy if it is structured as a net credit trade. The trader’s outlook is neutral to bullish. We have:

$$
f _ { T } = N _ { L } \times ( K _ { 2 } - S _ { T } ) ^ { + } - N _ { S } \times ( K _ { 1 } - S _ { T } ) ^ { + } - H\tag{163}
$$

$$
S _ { * u p } = K _ { 2 } - H / N _ { L } , \quad H > 0\tag{164}
$$

$$
S _ { * d o w n } = ( N _ { S } \times K _ { 1 } - N _ { L } \times K _ { 2 } + H ) / ( N _ { S } - N _ { L } )\tag{165}
$$

$$
P _ { m a x } = N _ { L } \times \left( K _ { 2 } - K _ { 1 } \right) - H\tag{166}
$$

$$
L _ { m a x } = N _ { S } \times K _ { 1 } - N _ { L } \times K _ { 2 } + H\tag{167}
$$

28 ${ \mathrm { S o } } ,$ the difference between call/put ratio backspreads and ratio call/put spreads is that in the former $N _ { L } > N _ { S }$ , while in the latter $N _ { L } < N _ { S }$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 2.40 Strategy: Long call butterfly

This is a sideways strategy consisting of a long position in an OTM call option with a strike price $K _ { 1 }$ , a short position in two ATM call options with a strike price $K _ { 2 }$ and a long position in an ITM call option with a strike price $K _ { 3 }$ . The strikes are equidistant: $K _ { 2 } - K _ { 3 } = K _ { 1 } - K _ { 2 } = \kappa$ . This is a relatively low cost net debit trade. The trader’s outlook is neutral. This is a capital gain strategy. We have:29

$$
f _ { T } = ( S _ { T } - K _ { 1 } ) ^ { + } + ( S _ { T } - K _ { 3 } ) ^ { + } - 2 \times ( S _ { T } - K _ { 2 } ) ^ { + } - D\tag{168}
$$

$$
S _ { * d o w n } = K _ { 3 } + D\tag{169}
$$

$$
S _ { * u p } = K _ { 1 } - D\tag{170}
$$

$$
P _ { m a x } = \kappa - D\tag{171}
$$

$$
L _ { m a x } = D\tag{172}
$$

## 2.40.1 Strategy: Modified call butterfly

This is a variation of the long call butterfly strategy where the strikes are no longer equidistant; instead we have $K _ { 1 } - K _ { 2 } < K _ { 2 } - K _ { 3 }$ . This results in a sideways strategy with a bullish bias. We have:

$$
f _ { T } = ( S _ { T } - K _ { 1 } ) ^ { + } + ( S _ { T } - K _ { 3 } ) ^ { + } - 2 \times ( S _ { T } - K _ { 2 } ) ^ { + } - D\tag{173}
$$

$$
S _ { * } = K _ { 3 } + D\tag{174}
$$

$$
P _ { m a x } = K _ { 2 } - K _ { 3 } - D\tag{175}
$$

$$
L _ { m a x } = D\tag{176}
$$

## 2.41 Strategy: Long put butterfly

This is a sideways strategy consisting of a long position in an OTM put option with a strike price $K _ { 1 }$ , a short position in two ATM put options with a strike price $K _ { 2 }$ and a long position in an ITM put option with a strike price $K _ { 3 }$ . The strikes are equidistant: $K _ { 3 } - K _ { 2 } = K _ { 2 } - K _ { 1 } = \kappa$ . This is a relatively low cost net debit trade. The trader’s outlook is neutral. This is a capital gain strategy. We have:

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } + ( K _ { 3 } - S _ { T } ) ^ { + } - 2 \times ( K _ { 2 } - S _ { T } ) ^ { + } - D\tag{177}
$$

$$
S _ { \ast u p } = K _ { 3 } - D\tag{178}
$$

$$
S _ { * d o w n } = K _ { 1 } + D\tag{179}
$$

$$
P _ { m a x } = \kappa - D
$$

$$
L _ { m a x } = D\tag{180}
$$

(181)

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 2.41.1 Strategy: Modified put butterfly

This is a variation of the long put butterfly strategy where the strikes are no longer equidistant; instead we have $K _ { 3 } - K _ { 2 } < K _ { 2 } - K _ { 1 }$ . This results in a sideways strategy with a bullish bias. We have (for $H > 0$ there is also $S _ { * u p } = K _ { 3 } - H )$ :30

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } + ( K _ { 3 } - S _ { T } ) ^ { + } - 2 \times ( K _ { 2 } - S _ { T } ) ^ { + } - H\tag{182}
$$

$$
S _ { * d o w n } = 2 \times K _ { 2 } - K _ { 3 } + H\tag{183}
$$

$$
P _ { m a x } = K _ { 3 } - K _ { 2 } - H\tag{184}
$$

$$
L _ { m a x } = 2 \times K _ { 2 } - K _ { 1 } - K _ { 3 } + H\tag{185}
$$

## 2.42 Strategy: Short call butterfly

This is a volatility strategy consisting of a short position in an ITM call option with a strike price $K _ { 1 }$ , a long position in two ATM call options with a strike price $K _ { 2 }$ and a short position in an OTM call option with a strike price $K _ { 3 }$ . The strikes are equidistant: $K _ { 3 } - K _ { 2 } = K _ { 2 } - K _ { 1 } = \kappa$ . This is a net credit trade. In this sense, this is an income strategy. However, the potential reward is sizably smaller than with a short straddle or a short strangle (albeit with a lower risk). The trader’s outlook is neutral. We have:

$$
f _ { T } = 2 \times ( S _ { T } - K _ { 2 } ) ^ { + } - ( S _ { T } - K _ { 1 } ) ^ { + } - ( S _ { T } - K _ { 3 } ) ^ { + } + C\tag{186}
$$

$$
S _ { \ast u p } = K _ { 3 } - C\tag{187}
$$

$$
S _ { * d o w n } = K _ { 1 } + C\tag{188}
$$

$$
P _ { m a x } = C\tag{189}
$$

$$
L _ { m a x } = \kappa - C\tag{190}
$$

## 2.43 Strategy: Short put butterfly

This is a volatility strategy consisting of a short position in an ITM put option with a strike price $K _ { 1 }$ , a long position in two ATM put options with a strike price $K _ { 2 }$ and a short position in an OTM put option with a strike price $K _ { 3 }$ . The strikes are equidistant: $K _ { 2 } - K _ { 3 } = K _ { 1 } - K _ { 2 } = \kappa$ . This is a net credit trade. In this sense, this is an income strategy. However, the potential reward is sizably smaller than with a short straddle or a short strangle (albeit with a lower risk). The trader’s outlook is neutral. We have:

$$
f _ { T } = 2 \times ( K _ { 2 } - S _ { T } ) ^ { + } - ( K _ { 1 } - S _ { T } ) ^ { + } - ( K _ { 3 } - S _ { T } ) ^ { + } + C\tag{191}
$$

$$
S _ { * d o w n } = K _ { 3 } + C\tag{192}
$$

$$
S _ { \ast u p } = K _ { 1 } - C\tag{193}
$$

$$
P _ { m a x } = C\tag{194}
$$

$$
L _ { m a x } = \kappa - C\tag{195}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 2.44 Strategy: “Long” iron butterfly

This sideways strategy is a combination of a bull put spread and a bear call spread and consists of a long position in an OTM put option with a strike price $K _ { 1 }$ , a short position in an ATM put option and an ATM call option with a strike price $K _ { 2 } ,$ and a long position in an OTM call option with a strike price $K _ { 3 }$ . The strikes are equidistant: $K _ { 2 } - K _ { 1 } = K _ { 3 } - K _ { 2 } = \kappa$ . This is a net credit trade. The trader’s outlook is neutral. This is an income strategy. We have:

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } - ( S _ { T } - K _ { 2 } ) ^ { + } + ( S _ { T } - K _ { 3 } ) ^ { + } + C\tag{196}
$$

$$
S _ { \ast u p } = K _ { 2 } + C\tag{197}
$$

$$
S _ { * d o w n } = K _ { 2 } - C\tag{198}
$$

$$
P _ { m a x } = C\tag{199}
$$

$$
L _ { m a x } = \kappa - C\tag{200}
$$

## 2.45 Strategy: “Short” iron butterfly

This volatility strategy is a combination of a bear put spread and a bull call spread and consists of a short position in an OTM put option with a strike price $K _ { 1 }$ , a long position in an ATM put option and an ATM call option with a strike price $K _ { 2 }$ , and a short position in an OTM call option with a strike price $K _ { 3 }$ . The strikes are equidistant: $K _ { 2 } - K _ { 1 } = K _ { 3 } - K _ { 2 } = \kappa$ . This is a net debit trade. The trader’s outlook is neutral. This is a capital gain strategy. We have:

$$
f _ { T } = ( K _ { 2 } - S _ { T } ) ^ { + } + ( S _ { T } - K _ { 2 } ) ^ { + } - ( K _ { 1 } - S _ { T } ) ^ { + } - ( S _ { T } - K _ { 3 } ) ^ { + } - D\tag{201}
$$

$$
S _ { * u p } = K _ { 2 } + D\tag{202}
$$

$$
S _ { * d o w n } = K _ { 2 } - D\tag{203}
$$

$$
P _ { m a x } = \kappa - D\tag{204}
$$

$$
L _ { m a x } = D\tag{205}
$$

## 2.46 Strategy: Long call condor

This is a sideways strategy consisting of a long position in an ITM call option with a strike price $K _ { 1 }$ , a short position in an ITM call option with a higher strike price $K _ { 2 }$ a short position in an OTM call option with a strike price $K _ { 3 }$ , and a long position in an OTM call option with a higher strike price $K _ { 4 }$ . All strikes are equidistant: $K _ { 4 } - K _ { 3 } = K _ { 3 } - K _ { 2 } = K _ { 2 } - K _ { 1 } = \kappa$ . This is a relatively low cost net debit trade. The trader’s outlook is neutral. This is a capital gain strategy. We have:

$$
f _ { T } = ( S _ { T } - K _ { 1 } ) ^ { + } - ( S _ { T } - K _ { 2 } ) ^ { + } - ( S _ { T } - K _ { 3 } ) ^ { + } + ( S _ { T } - K _ { 4 } ) ^ { + } - D\tag{206}
$$

$$
S _ { \ast u p } = K _ { 4 } - D\tag{207}
$$

$$
S _ { * d o w n } = K _ { 1 } + D\tag{208}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

$$
P _ { m a x } = \kappa - D\tag{209}
$$

$$
L _ { m a x } = D\tag{210}
$$

## 2.47 Strategy: Long put condor

This is a sideways strategy consisting of a long position in an OTM put option with a strike price $K _ { 1 }$ , a short position in an OTM put option with a higher strike price $K _ { 2 }$ a short position in an ITM put option with a strike price $K _ { 3 }$ , and a long position in an ITM put option with a higher strike price $K _ { 4 }$ . All strikes are equidistant: $K _ { 4 } - K _ { 3 } = K _ { 3 } - K _ { 2 } = K _ { 2 } - K _ { 1 } = \kappa$ . This is a relatively low cost net debit trade. The trader’s outlook is neutral. This is a capital gain strategy. We have:

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } - ( K _ { 3 } - S _ { T } ) ^ { + } + ( K _ { 4 } - S _ { T } ) ^ { + } - D\tag{211}
$$

$$
S _ { \ast u p } = K _ { 4 } - D\tag{212}
$$

$$
S _ { * d o w n } = K _ { 1 } + D\tag{213}
$$

$$
P _ { m a x } = \kappa - D\tag{214}
$$

$$
L _ { m a x } = D\tag{215}
$$

## 2.48 Strategy: Short call condor

This is a volatility strategy consisting of a short position in an ITM call option with a strike price $K _ { 1 }$ , a long position in an ITM call option with a higher strike price $K _ { 2 }$ a long position in an OTM call option with a strike price $K _ { 3 }$ , and a short position in an OTM call option with a higher strike price $K _ { 4 }$ . All strikes are equidistant: $K _ { 4 } - K _ { 3 } = K _ { 3 } - K _ { 2 } = K _ { 2 } - K _ { 1 } = \kappa$ This is a relatively low net credit trade. As with a short call butterfly, the potential reward is sizably smaller than with a short straddle or a short strangle (albeit with a lower risk). So, this is a capital gain (rather than an income) strategy. The trader’s outlook is neutral. We have:

$$
f _ { T } = ( S _ { T } - K _ { 2 } ) ^ { + } + ( S _ { T } - K _ { 3 } ) ^ { + } - ( S _ { T } - K _ { 1 } ) ^ { + } - ( S _ { T } - K _ { 4 } ) ^ { + } + C\tag{216}
$$

$$
S _ { \ast u p } = K _ { 4 } - C\tag{217}
$$

$$
S _ { * d o w n } = K _ { 1 } + C\tag{218}
$$

$$
P _ { m a x } = C\tag{219}
$$

$$
L _ { m a x } = \kappa - C\tag{220}
$$

## 2.49 Strategy: Short put condor

This is a volatility strategy consisting of a short position in an OTM put option with a strike price $K _ { 1 }$ , a long position in an OTM put option with a higher strike price $K _ { 2 }$ a long position in an ITM put option with a strike price $K _ { 3 }$ , and a short position in an ITM put option with a higher strike price $K _ { 4 }$ . All strikes are equidistant: $K _ { 4 } - K _ { 3 } = K _ { 3 } - K _ { 2 } = K _ { 2 } - K _ { 1 } = \kappa$ . This is a relatively low net credit trade.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

As with a short put butterfly, the potential reward is sizably smaller than with a short straddle or a short strangle (albeit with a lower risk). So, this is a capital gain (rather than an income) strategy. The trader’s outlook is neutral. We have:

$$
f _ { T } = ( K _ { 2 } - S _ { T } ) ^ { + } + ( K _ { 3 } - S _ { T } ) ^ { + } - ( K _ { 1 } - S _ { T } ) ^ { + } - ( K _ { 4 } - S _ { T } ) ^ { + } + C\tag{221}
$$

$$
S _ { \ast u p } = K _ { 4 } - C\tag{222}
$$

$$
S _ { * d o w n } = K _ { 1 } + C\tag{223}
$$

$$
P _ { m a x } = C\tag{224}
$$

$$
L _ { m a x } = \kappa - C\tag{225}
$$

## 2.50 Strategy: Long iron condor

This sideways strategy is a combination of a bull put spread and a bear call spread and consists of a long position in an OTM put option with a strike price $K _ { 1 }$ , a short position in an OTM put option with a higher strike price $K _ { 2 }$ , a short position in an OTM call option with a strike price $K _ { 3 } .$ , and a long position in an OTM call option with a higher strike price $K _ { 4 }$ . The strikes are equidistant: $K _ { 4 } - K _ { 3 } = K _ { 3 } - K _ { 2 } =$ $K _ { 2 } - K _ { 1 } = \kappa$ This is a net credit trade. The trader’s outlook is neutral. This is an income strategy. We have:

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } + ( S _ { T } - K _ { 4 } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } - ( S _ { T } - K _ { 3 } ) ^ { + } + C\tag{226}
$$

$$
S _ { \ast u p } = K _ { 3 } + C\tag{227}
$$

$$
S _ { * d o w n } = K _ { 2 } - C\tag{228}
$$

$$
P _ { m a x } = C\tag{229}
$$

$$
L _ { m a x } = \kappa - C\tag{230}
$$

## 2.51 Strategy: Short iron condor

This volatility strategy is a combination of a bear put spread and a bull call spread and consists of a short position in an OTM put option with a strike price $K _ { 1 }$ , a long position in an OTM put option with a higher strike price $K _ { 2 }$ , a long position in an OTM call option with a strike price $K _ { 3 }$ , and a short position in an OTM call option with a higher strike price $K _ { 4 }$ . The strikes are equidistant: $K _ { 4 } - K _ { 3 } = K _ { 3 } - K _ { 2 } =$ $K _ { 2 } - K _ { 1 } = \kappa$ . This is a net debit trade. The trader’s outlook is neutral. This is a capital gain strategy. We have:

$$
f _ { T } = ( K _ { 2 } - S _ { T } ) ^ { + } + ( S _ { T } - K _ { 3 } ) ^ { + } - ( K _ { 1 } - S _ { T } ) ^ { + } - ( S _ { T } - K _ { 4 } ) ^ { + } - D\tag{231}
$$

$$
S _ { \ast u p } = K _ { 3 } + D\tag{232}
$$

$$
S _ { * d o w n } = K _ { 2 } - D\tag{233}
$$

$$
P _ { m a x } = \kappa - D\tag{234}
$$

$$
L _ { m a x } = D\tag{235}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 2.52 Strategy: Long box

This volatility strategy can be viewed as a combination of a long synthetic forward and a short synthetic forward, or as a combination of a bull call spread and a bear put spread, and consists of a long position in an ITM put option with a strike price $K _ { 1 } ,$ a short position in an OTM put option with a lower strike price $K _ { 2 } ,$ a long position in an ITM call option with the strike price $K _ { 2 }$ , and a short position in an OTM call option with the strike price $K _ { 1 }$ . The trader’s outlook is neutral. This is a capital gain strategy.31 We have (assuming $K _ { 1 } \ge K _ { 2 } + D )$

$$
f _ { T } ~ = ~ ( K _ { 1 } - S _ { T } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } + ( S _ { T } - K _ { 2 } ) ^ { + } - ( S _ { T } - K _ { 1 } ) ^ { + } - D
$$

$$
= \ K _ { 1 } - K _ { 2 } - D\tag{236}
$$

$$
P _ { m a x } = ( K _ { 1 } - K _ { 2 } ) - D\tag{237}
$$

## 2.53 Strategy: Collar

This strategy (a.k.a. “fence”) is a covered call augmented by a long put option as insurance against the stock price falling.32 It amounts to buying stock, buying an OTM put option with a strike price $K _ { 1 }$ , and selling an OTM call option with a higher strike price $K _ { 2 }$ . The trader’s outlook is moderately bullish. This is a capital gain strategy. We have:33

$$
f _ { T } = S _ { T } - S _ { 0 } + ( K _ { 1 } - S _ { T } ) ^ { + } - ( S _ { T } - K _ { 2 } ) ^ { + } - H\tag{238}
$$

$$
S _ { * } = S _ { 0 } + H\tag{239}
$$

$$
P _ { m a x } = K _ { 2 } - S _ { 0 } - H\tag{240}
$$

$$
L _ { m a x } = S _ { 0 } - K _ { 1 } + H\tag{241}
$$

## 2.54 Strategy: Bullish short seagull spread

This option trading strategy is a bull call spread financed with a sale of an OTM put option. It amounts to a short position in an OTM put option with a strike price $K _ { 1 } .$ a long position in an ATM call option with a strike price $K _ { 2 }$ , and a short position in an OTM call option with a strike price $K _ { 3 }$ . Ideally, the trade should be structured to have zero cost. The trader’s outlook is bullish. This is a capital gain

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

strategy. We have:34

$$
f _ { T } = - ( K _ { 1 } - S _ { T } ) ^ { + } + ( S _ { T } - K _ { 2 } ) ^ { + } - ( S _ { T } - K _ { 3 } ) ^ { + } - H\tag{242}
$$

$$
S _ { * } = K _ { 2 } + H , \quad H > 0\tag{243}
$$

$$
S _ { * } = K _ { 1 } + H , \quad H < 0\tag{244}
$$

$$
K _ { 1 } \leq S _ { * } \leq K _ { 2 } , \quad H = 0\tag{245}
$$

$$
P _ { m a x } = K _ { 3 } - K _ { 2 } - H\tag{246}
$$

$$
L _ { m a x } = K _ { 1 } + H\tag{247}
$$

## 2.55 Strategy: Bearish long seagull spread

This option trading strategy is a short combo (short risk reversal) hedged against the stock price rising by buying an OTM call option. It amounts to a long position in an OTM put option with a strike price $K _ { 1 }$ , a short position in an ATM call option with a strike price $K _ { 2 } ,$ , and a long position in an OTM call option with a strike price $K _ { 3 }$ . Ideally, the trade should be structured to have zero cost. The trader’s outlook is bearish. This is a capital gain strategy. We have:

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } - ( S _ { T } - K _ { 2 } ) ^ { + } + ( S _ { T } - K _ { 3 } ) ^ { + } - H\tag{248}
$$

$$
S _ { * } = K _ { 1 } - H , \quad H > 0\tag{249}
$$

$$
S _ { * } = K _ { 2 } - H , \quad H < 0\tag{250}
$$

$$
K _ { 1 } \leq S _ { * } \leq K _ { 2 } , \quad H = 0\tag{251}
$$

$$
P _ { m a x } = K _ { 1 } - H\tag{252}
$$

$$
{ \cal L } _ { m a x } = K _ { 3 } - K _ { 2 } + H\tag{253}
$$

## 2.56 Strategy: Bearish short seagull spread

This option trading strategy is a bear put spread financed with a sale of an OTM call option. It amounts to a short position in an OTM put option with a strike price $K _ { 1 }$ , a long position in an ATM put option with a strike price $K _ { 2 }$ , and a short position in an OTM call option with a strike price $K _ { 3 }$ . Ideally, the trade should be structured to have zero cost. The trader’s outlook is bearish. This is a capital gain strategy. We have:

$$
f _ { T } = - ( K _ { 1 } - S _ { T } ) ^ { + } + ( K _ { 2 } - S _ { T } ) ^ { + } - ( S _ { T } - K _ { 3 } ) ^ { + } - H\tag{254}
$$

$$
S _ { * } = K _ { 2 } - H , \quad H > 0\tag{255}
$$

$$
S _ { * } = K _ { 3 } - H , \quad H < 0\tag{256}
$$

$$
K _ { 2 } \leq S _ { * } \leq K _ { 3 } , \quad H = 0\tag{257}
$$

$$
P _ { m a x } = K _ { 2 } - K _ { 1 } - H\tag{258}
$$

$$
L _ { m a x } = \mathrm { u n l i m i t e d }\tag{259}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 2.57 Strategy: Bullish long seagull spread

This option trading strategy is a long combo (long risk reversal) hedged against the stock price falling by buying an OTM put option. It amounts to a long position in an OTM put option with a strike price $K _ { 1 }$ , a short position in an ATM put option with a strike price $K _ { 2 } ,$ , and a long position in an OTM call option with a strike price $K _ { 3 }$ . Ideally, the trade should be structured to have zero cost. The trader’s outlook is bullish. This is a capital gain strategy. We have:

$$
f _ { T } = ( K _ { 1 } - S _ { T } ) ^ { + } - ( K _ { 2 } - S _ { T } ) ^ { + } + ( S _ { T } - K _ { 3 } ) ^ { + } - H\tag{260}
$$

$$
S _ { * } = K _ { 3 } + H , \quad H > 0\tag{261}
$$

$$
S _ { * } = K _ { 2 } + H , \quad H < 0\tag{262}
$$

$$
K _ { 2 } \leq S _ { * } \leq K _ { 3 } , \quad H = 0\tag{263}
$$

$$
P _ { m a x } = \mathrm { u n l i m i t e d }
$$

$$
L _ { m a x } = K _ { 2 } - K _ { 1 } + H\tag{264}
$$

(265)

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 3 Stocks

## 3.1 Strategy: Price-momentum

Empirically, there appears to be certain “inertia” in stock returns known as the momentum effect, whereby future returns are positively correlated with past returns (see, e.g., [Asness, 1994], [Asness et al, 2014], [Asness, Moskowitz and Pedersen, 2013], [Grinblatt and Moskowitz, 2004], [Jegadeesh and Titman, 1993]). Let t denote time measured in the units of 1 month, with $t = 0$ corresponding to the most recent time. Let $P _ { i } ( t )$ be the time series of prices (fully adjusted for splits and dividends) for the stock labeled by $i \ ( i = 1 , \ldots , N$ , where N is the number of stocks in the trading universe). Let

$$
R _ { i } ( t ) = \frac { P _ { i } ( t ) } { P _ { i } ( t + 1 ) } - 1\tag{266}
$$

$$
R _ { i } ^ { c u m } = \frac { P _ { i } ( S ) } { P _ { i } ( S + T ) } - 1\tag{267}
$$

$$
R _ { i } ^ { m e a n } = \frac { 1 } { T } \sum _ { t = S } ^ { S + T - 1 } R _ { i } ( t )\tag{268}
$$

$$
R _ { i } ^ { r i s k . a d j } = \frac { R _ { i } ^ { m e a n } } { \sigma _ { i } }\tag{269}
$$

$$
\sigma _ { i } ^ { 2 } = \frac { 1 } { T - 1 } \sum _ { t = S } ^ { S + T - 1 } { ( R _ { i } ( t ) - R _ { i } ^ { m e a n } ) ^ { 2 } }\tag{270}
$$

Here: $R _ { i } ( t )$ is the monthly return; $R _ { i } ^ { c u m }$ is the cumulative return computed over the T -month “formation period” (usually $T = 1 2 )$ skipping the most recent S-month “skip period” (usually $S = 1 )$ ;35 Rmeani is the mean monthly return computed over the formation period; $R _ { i } ^ { r i s k . a \dot { d } j }$ is the risk-adjusted mean return over the formation period; and $\sigma _ { i }$ is the monthly volatility calculated over the formation period.

The price-momentum strategy amounts to buying the best performing stocks and selling the worst performing stocks, where the “performance” is measured by a selection criterion based on $R _ { i } ^ { c u m }$ , Rmeani , $R _ { i } ^ { r i s k . a d j }$ or some other criterion. E.g., after the stocks are sorted by $R _ { i } ^ { c u m }$ (in the decreasing order), the trader can, e.g., buy stocks in the top decile (winners) and short stocks in the bottom decile (losers).36 This can be a zero-cost strategy, i.e., the corresponding portfolio is dollar-neutral. Alternatively, a long-only portfolio can be constructed by buying stocks in, $\mathrm { e . g . }$ the top decile. Once a portfolio is established at $t = 0$ , it is kept unaltered during

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

a predefined “holding period”,37 which can be 1 month or longer (longer holding period portfolios typically have diminishing returns before trading costs as the momentum effect fades with time). Multi-month-holding portfolios can be constructed by overlapping 1-month-holding portfolios (see, e.g., [Jegadeesh and Titman, 1993]).

The above prescription does not fix the relative weights $w _ { i }$ of the stocks in the portfolio. For a long-only portfolio we have $w _ { i } \geq 0$ and

$$
\sum _ { i = 1 } ^ { N } w _ { i } = 1\tag{271}
$$

So, if the total investment level is I, then the stock labeled by i has $I \times w _ { i }$ dollars invested in it. This, up to rounding, translates into $Q _ { i } = I \times w _ { i } / P _ { i } ( 0 )$ shares.38 One can simply take uniform weights, $w _ { i } = 1 / N$ for all stocks, albeit other weighting schemes are possible. $\mathrm { E . g . }$ , we can have nonuniform $w _ { i } \propto 1 / \sigma _ { i } .$ , or $w _ { i } \propto 1 / \sigma _ { i } ^ { 2 }$ , etc.

For a dollar-neutral portfolio we can have negative $w _ { i }$ and

$$
\sum _ { i = 1 } ^ { N } \left| w _ { i } \right| = 1\tag{272}
$$

$$
\sum _ { i = 1 } ^ { N } w _ { i } = 0\tag{273}
$$

So, if the total investment level is $I = I _ { L } + I _ { S }$ , where $I _ { L }$ is the total long investment, and $I _ { S }$ is the absolute value of the total short investment,39 then the stock labeled by i has $I \times w _ { i }$ dollars invested in it, where $w _ { i } > 0$ for long stocks, and $w _ { i } < 0$ for short stocks. One can simply take modulus-uniform weights, where $w _ { i } = 1 / 2 N _ { L }$ for all $N _ { L }$ long stocks, and $w _ { i } = - 1 / 2 N _ { S }$ for all $N _ { S }$ short stocks. However, other weighting schemes are possible, e.g., as above, weights suppressed by $\sigma _ { i } , \sigma _ { i } ^ { 2 }$ 2, etc.40

## 3.2 Strategy: Earnings-momentum

This strategy amounts to buying winners and selling losers as in the price-momentum strategy, but the selection criterion is based on earnings. One way to define such a

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

selection criterion is via standardized unexpected earnings (SUE) [Chan, Jegadeesh and Lakonishok, 1996]:41

$$
\mathrm { S U E } _ { i } = \frac { E _ { i } - E _ { i } ^ { \prime } } { \sigma _ { i } }\tag{274}
$$

Here: $E _ { i }$ is the most recently announced quarterly earnings per share of the stock labeled by i; $E _ { i } ^ { \prime }$ is the earnings per share announced 4 quarters ago; $\sigma _ { i }$ is the standard deviation of the unexpected earnings $E _ { i } - E _ { i } ^ { \prime }$ over the last 8 quarters. Similarly to the price-momentum strategy, the trader can, e.g., construct a dollar-neutral portfolio by buying stocks in the top decile by SUE, and shorting stocks in the bottom decile.42

## 3.3 Strategy: Value

This strategy amounts to buying winners and selling losers as in the price-momentum and earnings-momentum strategies, but the selection criterion is based on value. Value can be defined as the Book-to-Price $\mathrm { ( B / P ) }$ ratio (see, e.g., [Rosenberg, Reid and Lanstein, 1985]). Here “Book” is the company’s book value per share outstanding (so the $\mathrm { B / P }$ ratio is the same as the Book-to-Market ratio, where now “Book” stands for its total book value, not per share outstanding, and “Market” is its market capitalization). The trader can, e.g., construct a zero-cost portfolio by buying stocks in the top decile by the $\mathrm { B / P }$ ratio, and shorting stocks in the bottom decile. There can be variations in the definition of the B/P ratio. Thus, e.g., [Asness, Moskowitz and Pedersen, 2013] uses current (i.e., most up-to-date) prices, while [Fama and French, 1992] and some others use prices contemporaneous with the book value.43

## 3.4 Strategy: Low-volatility anomaly

This strategy is based on the empirical observation that future returns of previously low-return-volatility portfolios outperform those of previously high-return-volatility portfolios,44 which goes counter to the “na¨ıve” expectation that higher risk assets

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

should yield proportionately higher returns. Thus, if $\sigma _ { i }$ is defined as the historical volatility (computed over a time series of historical returns, as in $\operatorname { E q . }$ (270)), the trader can, e.g., construct a dollar-neutral portfolio by buying stocks in the bottom decile by $\sigma _ { i }$ (low-volatility stocks), and shorting stocks in the top decile (high-volatility stocks). The length of the sample used for computing the historical volatility can, e.g., be 6 months (126 trading days) to a year (252 trading days), with a similar duration for the holding period (with no “skip period” required).

## 3.5 Strategy: Implied volatility

This strategy is based on the empirical observation that stocks with larger increases in call implied volatilities over the previous month on average have higher future returns, while stocks with larger increases in put implied volatilities over the previous month on average have lower future returns (see, e.g., [An et al, 2014], [Chen, Chung and Tsai, 2016]).45 Therefore, the trader can, e.g., construct a dollar-neutral portfolio by buying stocks in the top decile by the increase in call implied volatilities, and shorting stocks in the top decile by the increase in put implied volatilities. One can also consider variations, e.g., buying stocks in the top decile by the difference twixt the change in call implied volatilities and the change in put implied volatilities.

## 3.6 Strategy: Multifactor portfolio

This strategy amounts to buying and shorting stocks based on multiple factors such as value, momentum, etc. For instance, usually value and momentum are negatively correlated and combining them can add value (see, e.g., [Asness, Moskowitz and Pedersen, 2013]). There is a variety of ways in which $F > 1$ factors can be combined.46 The simplest way is to diversify the exposure to the F factors with some weights $w _ { A }$ , where $A = 1 , \dotsc , F$ labels the factors. That is, if I is the total investment level, then the F portfolios (each built as above based on the corresponding factor) are allocated the investment levels $I _ { A } = w _ { A } \times I$ , where (assuming all $w _ { A } > 0 )$

$$
\sum _ { A = 1 } ^ { F } w _ { A } = 1\tag{275}
$$

Thus, one can simply take uniform weights $w _ { A } = 1 / F$ , albeit this may not be the most optimal weighting scheme. E.g., similarly to Subsection 3.1, there are weighting

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

schemes with $w _ { A } \propto 1 / \sigma _ { A } , w _ { A } \propto 1 / \sigma _ { A } ^ { 2 }$ , etc., where $\sigma _ { A }$ is the historical volatility for the corresponding factor portfolio (uniformly normalized, e.g., per dollar invested).47

Alternatively, consider F rankings of stocks based on the F factors. One can now combine these rankings in various ways to blend the factors. E.g., in the case of two factors, momentum and value, one can take the top (winners) and bottom (losers) quintiles by momentum and further split them into top half and bottom half, respectively, by value. Or one can take the top and bottom quintiles by value and split them by momentum.48 Yet another way is to define demeaned ranks

$$
s _ { A i } = \mathrm { r a n k } ( f _ { A i } ) - \frac { 1 } { N } \sum _ { j = 1 } ^ { N } \mathrm { r a n k } ( f _ { A j } )\tag{276}
$$

where $f _ { A i }$ is the numeric value of the factor labeled by A (e.g., momentum) for the stock labeled by $i ( i = 1 , \dots , N )$ . One can then simply average the ranks:

$$
s _ { i } = \frac { 1 } { F } \sum _ { A = 1 } ^ { F } s _ { A i }\tag{277}
$$

The combined “score” $s _ { i }$ can have ties, which, if need be (e.g., if there is an ambiguity at the border of the top decile) can be resolved, e.g., simply by giving preference to one of the factor rankings. Averaging over $s _ { A i }$ simply minimizes the sum of squares of the Euclidean distances between the N-vector $s _ { i }$ and the K N-vectors $s _ { A i }$ . One can introduce nonuniform weights into this sum (which would amount to a weighted average in Eq. (277)), or even use a different definition of the distance (e.g., the Manhattan distance), which would complicate the problem computationally. Etc.49

## 3.7 Strategy: Residual momentum

This is the same as the price-momentum strategy with the stock returns $R _ { i } ( t )$ replaced by the residuals $\epsilon _ { i } ( t )$ of a serial regression of the stock returns $R _ { i } ( t )$ over, e.g., the 3 Fama-French factors MKT(t), SMB(t), HML(t),50 with the intercept (see,

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

e.g., [Blitz, Huij and Martens, 2011]):51

$$
R _ { i } ( t ) = \alpha _ { i } + \beta _ { 1 , i } ~ \mathrm { M K T } ( t ) + \beta _ { 2 , i } ~ \mathrm { S M B } ( t ) + \beta _ { 3 , i } ~ \mathrm { H M L } ( t ) + \epsilon _ { i } ( t )\tag{278}
$$

The regression is run over a 36-month period [Blitz, Huij and Martens, 2011] (with the 1-month skip period) to estimate the regression coefficients $\alpha _ { i } , \ \beta _ { 1 , i } , \ \beta _ { 2 , i } , \ \beta _ { 3 , i }$ Once the coefficients are estimated, the residuals can be computed for the 12-month formation period (again, with the 1-month skip period):

$$
\epsilon _ { i } ( t ) = R _ { i } ( t ) - \beta _ { 1 , i } \ \mathrm { M K T } ( t ) - \beta _ { 2 , i } \ \mathrm { S M B } ( t ) - \beta _ { 3 , i } \ \mathrm { H M L } ( t )\tag{279}
$$

Note that $\alpha _ { i }$ is not included in this computation of the residuals for the 12-month formation period as $\alpha _ { i }$ was computed for the 36-month period. These residuals $\epsilon _ { i } ( t )$ are then used to compute, e.g., the risk-adjusted residual returns $\widetilde { R } _ { i } ^ { r i s k . a d j }$ (here $S = 1$ and $T = 1 2$ ; the holding period typically is 1 month, but can be longer):

$$
\epsilon _ { i } ^ { m e a n } = \frac { 1 } { T } \sum _ { t = S } ^ { S + T - 1 } \epsilon _ { i } ( t )\tag{280}
$$

$$
\widetilde { R } _ { i } ^ { r i s k . a d j } = \frac { \epsilon _ { i } ^ { m e a n } } { \widetilde { \sigma } _ { i } }\tag{281}
$$

$$
\widetilde \sigma _ { i } ^ { 2 } = \frac { 1 } { T - 1 } \sum _ { t = S } ^ { S + T - 1 } ( \epsilon _ { i } ( t ) - \epsilon _ { i } ^ { m e a n } ) ^ { 2 }\tag{282}
$$

E.g., a dollar-neutral portfolio can be constructed by buying stocks in the top decile by $\widetilde { R } _ { i } ^ { r i s k . a d j }$ , and shorting stocks in the bottom decile (with (non)uniform weights).

## 3.8 Strategy: Pairs trading

This dollar-neutral strategy amounts to identifying a pair of historically highly correlated stocks (call them stock A and stock B) and, when a mispricing (i.e., a deviation from the high historical correlation) occurs, shorting the “rich” stock and buying the “cheap” stock. This is an example of a mean-reversion strategy. Let $P _ { A } ( t _ { 1 } )$ and $P _ { B } ( t _ { 1 } )$ be the prices of stock A and stock B at time $t _ { 1 }$ , and let $P _ { A } ( t _ { 2 } )$ and $P _ { B } ( t _ { 2 } )$ be the prices of stock A and stock B at a later time $t _ { 2 }$ . All prices are fully adjusted for any splits and dividends. The corresponding returns (from $t _ { 1 }$ to $t _ { 2 } )$ are

$$
R _ { A } = \frac { P _ { A } ( t _ { 2 } ) } { P _ { A } ( t _ { 1 } ) } - 1\tag{283}
$$

$$
R _ { B } = \frac { P _ { B } ( t _ { 2 } ) } { P _ { B } ( t _ { 1 } ) } - 1\tag{284}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Since typically these returns are small, we can use an alternative definition:

$$
R _ { A } = \ln \left( \frac { P _ { A } ( t _ { 2 } ) } { P _ { A } ( t _ { 1 } ) } \right)\tag{285}
$$

$$
R _ { B } = \ln \left( \frac { P _ { B } ( t _ { 2 } ) } { P _ { B } ( t _ { 1 } ) } \right)\tag{286}
$$

Next, let $\widetilde { R } _ { A }$ and ${ \widetilde { R } } _ { B }$ be the demeaned returns:

$$
\overline { { { R } } } = \frac { 1 } { 2 } \left( R _ { A } + R _ { B } \right)\tag{287}
$$

$$
\widetilde { R } _ { A } = R _ { A } - \overline { { R } }\tag{288}
$$

$$
\widetilde { R } _ { B } = R _ { B } - \overline { { R } }\tag{289}
$$

where $\overline { { R } }$ is the mean return. A stock is “rich” if its demeaned return is positive, and it is “cheap” if its demeaned return is negative. The numbers of shares $Q _ { A } , Q _ { B }$ to short/buy are fixed by the total desired dollar investment I (Eq. (290)) and the requirement of dollar-neutrality (Eq. (291)):

$$
P _ { A } \ \left| Q _ { A } \right| + P _ { B } \ \left| Q _ { B } \right| = I\tag{290}
$$

$$
P _ { A } ~ Q _ { A } + P _ { B } ~ Q _ { B } = 0\tag{291}
$$

where $P _ { A } , P _ { B }$ are the stock prices at the time t∗ the position is established $\left( t _ { * } \geq t _ { 2 } \right)$ 52

## 3.9 Strategy: Mean-reversion – single cluster

This is a generalization of the pairs trading strategy to $N \ > \ 2$ stocks that are historically highly correlated (e.g., stocks belonging to the same industry or sector). Let $R _ { i } , i = 1 , \ldots , N$ , be the returns for these N stocks:

$$
R _ { i } = \ln \left( \frac { P _ { i } ( t _ { 2 } ) } { P _ { i } ( t _ { 1 } ) } \right)\tag{292}
$$

$$
\overline { { R } } = \frac { 1 } { N } \sum _ { i = 1 } ^ { N } R _ { i }\tag{293}
$$

$$
\widetilde { R } _ { i } = R _ { i } - \overline { { R } }\tag{294}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Following the pairs trading intuition, we can short stocks with positive ${ \widetilde { R } } _ { i }$ and buy stocks with negative ${ \widetilde { R } } _ { i }$ . We have the following conditions:

$$
\sum _ { i = 1 } ^ { N } P _ { i } \ \left| Q _ { i } \right| = I\tag{295}
$$

$$
\sum _ { i = 1 } ^ { N } P _ { i } \ Q _ { i } = 0\tag{296}
$$

Here: I is the total desired dollar investment; Eq. (296) is the dollar-neutrality constraint; $Q _ { i } < 0$ for short-sales; $Q _ { i } > 0$ for buys; P $P _ { i }$ are the prices at the time the position is established. We have 2 equations and $N > 2$ unknowns. A simple prescription (which is one out of myriad possibilities) for specifying $Q _ { i }$ is to have the dollar positions $D _ { i } = P _ { i } \ Q _ { i }$ proportional to the demeaned returns:

$$
D _ { i } = - \gamma \ \widetilde { R } _ { i }\tag{297}
$$

where $\gamma > 0$ (recall that we short $\widetilde { R } _ { i } > 0$ stocks and buy $\widetilde { R } _ { i } < 0$ stocks). Then Eq. (296) is automatically satisfied, while Eq. (295) fixes γ:

$$
\gamma = \frac { I } { \sum _ { i = 1 } ^ { N } \Big | \widetilde { R } _ { i } \Big | }\tag{298}
$$

## 3.9.1 Strategy: Mean-reversion – multiple clusters

The mean-reversion strategy of Subsection 3.9 can be readily generalized to the case where we have $K > 1$ clusters such that stocks within each cluster are historically highly correlated.53 We can simply treat clusters independently from each other and construct a mean-reversion strategy following the above procedure in each cluster. Then, e.g., we can allocate investments to these K independent strategies uniformly.

There is a neat way of treating all clusters in a “unified” fashion using a linear regression. Let the K clusters be labeled by $A = 1 , \dotsc , K$ . Let $\Lambda _ { i A }$ be an $N \times K$ matrix such that if the stock labeled by $i \ ( i = 1 , \ldots , N )$ belongs to the cluster labeled by A, then $\Lambda _ { i A } = 1 $ ; otherwise, $\Lambda _ { i A } = 0$ We will assume that each and every stock belongs to one and only one cluster (so there are no empty clusters):

$$
N _ { A } = \sum _ { i = 1 } ^ { N } \Lambda _ { i A } > 0\tag{299}
$$

$$
N = \sum _ { A = 1 } ^ { K } N _ { A }\tag{300}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

We have

$$
\Lambda _ { i A } = \delta _ { G ( i ) , A }\tag{301}
$$

$$
G : \left\{ 1 , \dots , N \right\} \mapsto \left\{ 1 , \dots , K \right\}\tag{302}
$$

Here: G is the map between stocks and clusters; and $\Lambda _ { i A }$ is the loadings matrix.

Now consider a linear regression of the stock returns $R _ { i }$ over $\Lambda _ { i A }$ (without the intercept and with unit weights):

$$
R _ { i } = \sum _ { A = 1 } ^ { K } \Lambda _ { i A } ~ f _ { A } + \varepsilon _ { i }\tag{303}
$$

where $f _ { A }$ are the regression coefficients given by (in matrix notation, where R is the N-vector $R _ { i } , f$ is the K-vector $f _ { A }$ , and Λ is the $N \times K$ matrix $\Lambda _ { i A } )$

$$
f = Q ^ { - 1 } \Lambda ^ { T } \ R\tag{304}
$$

$$
Q = \Lambda ^ { T } \mathrm { ~ } \Lambda\tag{305}
$$

and $\varepsilon _ { i }$ are the regression residuals. For binary $\Lambda _ { i A }$ given by Eq. (301), these residuals are nothing but the returns $R _ { i }$ demeaned w.r.t. to the corresponding cluster:

$$
\varepsilon = R - \Lambda Q ^ { - 1 } \Lambda ^ { T } R
$$

$$
Q _ { A B } = N _ { A } \ \delta _ { A B }\tag{306}
$$

$$
\overline { { R } } _ { A } = \frac { 1 } { N _ { A } } \sum _ { j \in J _ { A } } R _ { j }\tag{307}
$$

(308)

$$
\varepsilon _ { i } = R _ { i } - \overline { { R } } _ { G ( i ) } = \widetilde { R } _ { i }\tag{309}
$$

where $\overline { { R } } _ { A }$ is the mean return for the cluster labeled by A, and ${ \widetilde { R } } _ { i }$ is the demeaned return obtained by subtracting from $R _ { i }$ the mean return for the cluster labeled by $A = G ( i )$ to which the stock labeled by i belongs: $J _ { A } = \{ i | G ( i ) = A \} \subset \{ 1 , \ldots , N \}$

The demeaned returns are cluster-neutral, i.e.,

$$
\sum _ { i = 1 } ^ { N } \widetilde { R } _ { i } \ \Lambda _ { i A } = 0 , \quad A = 1 , \dots , K\tag{310}
$$

Also, note that we automatically have (so $D _ { i }$ given by Eq. (297) satisfy Eq. (296))

$$
\sum _ { i = 1 } ^ { N } \widetilde { R } _ { i } \ \nu _ { i } = 0\tag{311}
$$

where $\nu _ { i } \equiv 1 , i = 1 , \dots , N$ , i.e., the N -vector ν is the unit vector. In the regression language, ν is the intercept. We did not have to add the intercept to the loadings matrix Λ as it is already subsumed in it:

$$
\sum _ { A = 1 } ^ { K } \Lambda _ { i A } = \nu _ { i }\tag{312}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 3.10 Mean-reversion – weighted regression

The conditions (310) satisfied by the demeaned returns when the loadings matrix is binary simply mean that these returns are cluster-neutral, i.e., orthogonal to the K N -vectors $v ^ { ( A ) }$ comprising the columns of $\Lambda _ { i A }$ . Such orthogonality can be defined for any loadings matrix, not just a binary one. So, we can consider a generalization where the loadings matrix, call it $\Omega _ { i A }$ , may have some binary columns, but generally it need not. The binary columns, if any, can, e.g., be industry (or sector) based risk factors; the non-binary columns are interpreted as some non-industry based risk factors; and the orthogonality condition

$$
\sum _ { i = 1 } ^ { N } \widetilde { R } _ { i } \ \Omega _ { i A } , A = 1 , \dots , K\tag{313}
$$

can be satisfied if the twiddled returns ${ \widetilde { R } } _ { i }$ are related to the residuals $\varepsilon _ { i }$ of the regression of $R _ { i }$ over $\Omega _ { i A }$ with some (generally nonuniform) regression weights $z _ { i }$ via

$$
\widetilde { R } = Z \varepsilon\tag{314}
$$

$$
\varepsilon = R - \Omega \ Q ^ { - 1 } \ \Omega ^ { T } \ Z \ R\tag{315}
$$

$$
Z = \mathrm { d i a g } ( z _ { i } )\tag{316}
$$

$$
Q = \Omega ^ { T } ~ Z ~ \Omega\tag{317}
$$

If the intercept is included in $\Omega _ { i A } \ { \mathrm { ( i . e . } }$ , a linear combination of the columns of $\Omega _ { i A }$ equals the unit N-vector ν), then we automatically have

$$
\sum _ { i = 1 } ^ { N } \widetilde { R } _ { i } = 0\tag{318}
$$

The weights $z _ { i } \ { \mathrm { c a n } } , \ { \mathrm { e . g . } }$ , be taken as $z _ { i } = 1 / \sigma _ { i } ^ { 2 }$ , where $\sigma _ { i }$ are historical volatilities.54

## 3.11 Strategy: Single moving average

This strategy is based on the stock price crossing a moving average. One can use different types of moving averages (MAs), such as a simple moving average (SMA),

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

or an exponential moving average (EMA):55

$$
\begin{array} { l } { \operatorname { S M A } ( T ) = \displaystyle \frac { 1 } { T } \sum _ { t = 1 } ^ { T } P ( t ) } \\ { \operatorname { E M A } ( T , \lambda ) = \displaystyle \frac { \sum _ { t = 1 } ^ { T } \lambda ^ { t - 1 } ~ P ( t ) } { \sum _ { t = 1 } ^ { T } \lambda ^ { t - 1 } } = \frac { 1 - \lambda } { 1 - \lambda ^ { T } } ~ \sum _ { t = 1 } ^ { T } \lambda ^ { t - 1 } ~ P ( t ) } \end{array}\tag{319}
$$

(320)

Here: t = 1 corresponds to the most recent time in the time series of historical stock prices P (t); T is the length of the MA (t and $T$ are usually measured in trading days); and $\lambda < 1$ is the factor which suppresses past contributions. Below MA will refer to SMA or EMA. A simple strategy is defined as follows $( P$ is the price at $t = 0$ , on the trading day immediately following the most recent trading day $t = 1$ in the time series $P ( t ) )$ :

$$
{ \mathrm { S i g n a l } } = { \left\{ \begin{array} { l l } { { \mathrm { E s t a b l i s h ~ l o n g / l i q u i d a t e ~ s h o r t ~ p o s i t i o n ~ i f ~ } } P > { \mathrm { M A } } ( T ) } \right.} \\ { { \mathrm { E s t a b l i s h ~ s h o r t / l i q u i d a t e ~ l o n g ~ p o s i t i o n ~ i f ~ } } P < { \mathrm { M A } } ( T ) } \end{array}  \tag{321}
$$

This strategy can be run as, e.g., long-only, short-only, or both long and short. It can be straightforwardly applied to multiple stocks (on a single-stock basis, with no cross-sectional interaction between the signals for individual stocks). With a large number of stocks, it may be possible to construct (near-)dollar-neutral portfolios.

## 3.12 Strategy: Two moving averages

The simplest variant of this strategy replaces the stock price P in Eq. (321) by another moving average. That is, we have 2 moving averages with lengths $T ^ { \prime }$ and $T$ , where $T ^ { \prime } < T \mathrm { \ : ( e . g . , \ : } T ^ { \prime } = 1 0$ and $T = 3 0 )$ , and the signal is given by:

$$
\mathrm { S i g n a l } = \left\{ \begin{array} { l l } { \mathrm { E s t a b l i s h ~ l o n g / l i q u i d a t e ~ s h o r t ~ p o s i t i o n ~ i f ~ M A } ( { \cal T } ^ { \prime } ) > \mathrm { M A } ( { \cal T } ) } \\ { \mathrm { E s t a b l i s h ~ s h o r t / l i q u i d a t e ~ l o n g ~ p o s i t i o n ~ i f ~ M A } ( { \cal T } ^ { \prime } ) < \mathrm { M A } ( { \cal T } ) } \end{array} \right.\tag{322}
$$

This signal can be augmented with additional “stop-loss” rules to protect realized profits. E.g., if a long position has been established, the trader can define a threshold

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

to liquidate the long position if the stock begins to fall (even if the shorter moving average has not crossed the longer moving average yet):

$$
{ \mathrm { S i g n a l } } = { \left\{ \begin{array} { l l } { { \mathrm { E s t a b l i s h ~ l o n g ~ p o s i t i o n ~ i f ~ M A ( } } T ^ { \prime } { \mathrm { ) } } > { \mathrm { M A } } ( T ) } \\ { { \mathrm { L i q u i d a t e ~ l o n g ~ p o s i t i o n ~ i f ~ } } P < ( 1 - \Delta ) \times P _ { 1 } } \\ { { \mathrm { E s t a b l i s h ~ s h o r t ~ p o s i t i o n ~ i f ~ M A ( } } T ^ { \prime } { \mathrm { ) } } < { \mathrm { M A } } ( T ) } \\ { { \mathrm { L i q u i d a t e ~ s h o r t ~ p o s i t i o n ~ i f ~ } } P > ( 1 + \Delta ) \times P _ { 1 } } \end{array} \right. }\tag{323}
$$

Here $\Delta$ is some predefined percentage, $\mathrm { e . g . , } \Delta = 2 \%$ . So, a long position is liquidated if the current price P falls over 2% below the previous day’s price $P _ { 1 } { \mathrm { : } }$ ; and a short position is liquidated if P rises over $2 \%$ above $P _ { 1 }$ . Other variations can be used.

## 3.13 Strategy: Three moving averages

In some cases, using 3 moving averages with lengths $T _ { 1 } < T _ { 2 } < T _ { 3 } ( \mathrm { e . g . , } T _ { 1 } = 3$ $T _ { 2 } = 1 0 , T _ { 3 } = 2 1 )$ can help filter false signals:

$$
\mathrm { S i g n a l } = \left\{ \begin{array} { l l } { \mathrm { E s t a b l i s h ~ l o n g ~ p o s i t i o n ~ i f ~ M A } ( T _ { 1 } ) > \mathrm { M A } ( T _ { 2 } ) > \mathrm { M A } ( T _ { 3 } ) } \\ { \mathrm { L i q u i d a t e ~ l o n g ~ p o s i t i o n ~ i f ~ M A } ( T _ { 1 } ) \leq \mathrm { M A } ( T _ { 2 } ) } \\ { \mathrm { E s t a b l i s h ~ s h o r t ~ p o s i t i o n ~ i f ~ M A } ( T _ { 1 } ) < \mathrm { M A } ( T _ { 2 } ) < \mathrm { M A } ( T _ { 3 } ) } \\ { \mathrm { L i q u i d a t e ~ s h o r t ~ p o s i t i o n ~ i f ~ M A } ( T _ { 1 } ) \geq \mathrm { M A } ( T _ { 2 } ) } \end{array} \right.\tag{324}
$$

## 3.14 Strategy: Support and resistance

This strategy uses “support” S and “resistance” R levels, which can be computed using the “pivot point” (a.k.a. the “center”) C as follows:56

$$
C = \frac { P _ { H } + P _ { L } + P _ { C } } { 3 }\tag{325}
$$

$$
R = 2 \times C - P _ { L }\tag{326}
$$

$$
S = 2 \times C - P _ { H }\tag{327}
$$

Here $P _ { H } , P _ { L }$ and $P _ { C }$ are the previous day’s high, low and closing prices. One way to define a trading signal is as follows (as above, P is the current price):

$$
{ \mathrm { S i g n a l } } = { \left\{ \begin{array} { l l } { { \mathrm { E s t a b l i s h ~ l o n g ~ p o s i t i o n ~ i f ~ } } P > C } \\ { { \mathrm { L i q u i d a t e ~ l o n g ~ p o s i t i o n ~ i f ~ } } P \geq R } \\ { { \mathrm { E s t a b l i s h ~ s h o r t ~ p o s i t i o n ~ i f ~ } } P < C } \\ { { \mathrm { L i q u i d a t e ~ s h o r t ~ p o s i t i o n ~ i f ~ } } P \leq S } \end{array} \right. }\tag{328}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 3.15 Strategy: Channel

This strategy amounts to buying and selling a stock when it reaches the floor and the ceiling of a channel, respectively. A channel is a range/band, bounded by a ceiling and a floor, within which the stock price fluctuates. The trader’s expectation may be that if the floor or the ceiling is reached, the stock price will bounce in the opposite direction. On the other hand, if the stock price breaks through the ceiling or the floor, the trader may conclude that a new trend has emerged and follow this new trend instead. A simple and common definition of a channel is the Donchian Channel [Donchian, 1960], where the ceiling $B _ { u p }$ and the floor $B _ { d o w n }$ are defined as follows (with the same notations as above):57

$$
\boldsymbol { B _ { u p } } = \operatorname* { m a x } ( P ( 1 ) , P ( 2 ) , \dots , P ( T ) )\tag{329}
$$

$$
B _ { d o w n } = \operatorname* { m i n } ( P ( 1 ) , P ( 2 ) , \dots , P ( T ) )\tag{330}
$$

A simple trading strategy then is as follows:

$$
\mathrm { S i g n a l } = \left\{ \begin{array} { l l } { { \mathrm { E s t a b l i s h ~ l o n g / l i q u i d a t e ~ s h o r t ~ p o s i t i o n ~ i f } ~ } P = B _ { d o w n } } \\ { { \mathrm { E s t a b l i s h ~ s h o r t / l i q u i d a t e ~ l o n g ~ p o s i t i o n ~ i f } ~ } P = B _ { u p } } \end{array} \right.\tag{331}
$$

The wider the channel, the higher the volatility. Usually, the channel indicator is used together with other indicators. E.g., the signal can be more robust when a price reversal (or a channel break) occurs with an increase in the traded volume.

## 3.16 Strategy: Event-driven – M&A

This strategy, referred to as “merger arbitrage” or “risk arbitrage”, attempts to capture excess returns generated via corporate actions such as mergers and acquisitions (M&A). A merger arbitrage opportunity arises when one publicly traded company intends to acquire another publicly traded company at a price that differs from the latter’s market price. In this regard, there are two main types of transactions: cash mergers and stock mergers. In the case of a cash merger, the trader establishes a long position in the target company stock. In the case of a stock merger, the trader establishes a long position in the target company stock (call it A) and a short position in the acquirer company stock (call it B). For instance, if the current price of A is \$67, the current price of B is \$35, and under the proposed stock merger deal each share of A is swapped for 2 shares of B, then the trader buys one share of A and shorts 2 shares of B generating an initial net credit of $\$ 3$ , which is the profit per each share of A bought if the deal goes through. The trader’s risk is in that, if the deal falls through, the trader will likely lose money on this trade.58

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 3.17 Strategy: Machine learning – single-stock KNN

Some strategies rely on machine learning techniques, such as the k-nearest neighbor (KNN) algorithm (see, e.g., [Altman, 1992], [Samworth, 2012]), to predict future stock returns (the target variable) based on a set of predictor (feature) variables, which can be based on technical, fundamental and/or some other data. The strategy we describe here is a single-stock strategy, i.e., for each stock the target variable is predicted using the price and volume data only for this stock (but no cross-sectional data, i.e., no data for other stocks). The target variable $Y ( t )$ is defined as the cumulative return over the next T trading days (as above, the ascending integer values of $t ,$ which is measured in trading days, correspond to going back in time):

$$
Y ( t ) = \frac { P ( t - T ) } { P ( t ) } - 1\tag{332}
$$

The predictor variables $X _ { a } ( t ) , a = 1 , . . . , m$ , are defined using prices $P ( t ^ { \prime } )$ and volumes $V ( t ^ { \prime } )$ at times t0 before $t \ ( \mathrm { i . e . , } t ^ { \prime } > t )$ , so they are out-of-sample. Examples of such variables are moving averages of the price and volume of varying lengths:

$$
X _ { 1 } ( t ) = \frac { 1 } { T _ { 1 } } \sum _ { s = 1 } ^ { T _ { 1 } } V ( t + s )\tag{333}
$$

$$
X _ { 2 } ( t ) = \frac { 1 } { T _ { 2 } } \sum _ { s = 1 } ^ { T _ { 2 } } P ( t + s )\tag{334}
$$

$$
X _ { 3 } ( t ) = \frac { 1 } { T _ { 3 } } \sum _ { s = 1 } ^ { T _ { 3 } } P ( t + s )\tag{335}
$$

(336)

The predictor variables are further normalized to lie between 0 and 1:

$$
\widetilde X _ { a } ( t ) = \frac { X _ { a } ( t ) - X _ { a } ^ { - } } { X _ { a } ^ { + } - X _ { a } ^ { - } }\tag{337}
$$

where $X _ { a } ^ { + }$ and $X _ { a } ^ { - }$ are the maximum and minimum values of $X _ { a } ( t )$ over the training period. The final ingredient is the number k of the nearest neighbors (see below). For a given value of t we can take k nearest neighbors of the m-vector $\widetilde { X } _ { a } ( t )$ among the m-vectors $\widetilde X _ { a } ( t ^ { \prime } ) , t ^ { \prime } = t + 1 , t + 2 , \dots , t + T _ { * }$ , using the KNN algorithm (here

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

$T _ { * }$ is the sample size). For KNN we can use the Euclidean distance $D ( t , t ^ { \prime } )$ between $\widetilde { X } _ { a } ( t )$ and $\widetilde { X } _ { a } ^ { \textrm { - } } ( t ^ { \prime } )$ defined as

$$
[ D ( t , t ^ { \prime } ) ] ^ { 2 } = \sum _ { a = 1 } ^ { m } ( \widetilde { X } _ { a } ( t ) - \widetilde { X } _ { a } ( t ^ { \prime } ) ) ^ { 2 }\tag{338}
$$

However, we can use some other distance (e.g., the Manhattan distance). Let the k nearest neighbors of $\widetilde { X } _ { a } ( t )$ be $\widetilde { X } _ { a } ( t _ { \alpha } ^ { \prime } ( t ) ) , \alpha = 1 , \ldots , k$ . (Note that the k values $t _ { \alpha } ^ { \prime } ( t )$ depend on t.) Then we can define the predicted value $\mathcal { V } ( t )$ simply as an average of the corresponding realized values $Y ( t _ { \alpha } ^ { \prime } ( t ) )$ :

$$
\mathcal { V } ( t ) = \frac { 1 } { k } \sum _ { \alpha = 1 } ^ { k } Y ( t _ { \alpha } ^ { \prime } ( t ) )\tag{339}
$$

Alternatively, we can, e.g., consider a linear model

$$
\mathcal { V } ( t ) = \sum _ { \alpha = 1 } ^ { k } Y ( t _ { \alpha } ^ { \prime } ( t ) ) \ w _ { \alpha } + v\tag{340}
$$

and fix the coefficients $w _ { \alpha }$ and v by running a regression59 of the realized values $Y ( t )$ over $Y ( t _ { \alpha } ^ { \prime } ( t ) )$ for some number – call it M – of values of t. I.e., we pull $Y ( t )$ for these values of t into an M -vector and regress it over the $M \times k$ matrix of the corresponding values $Y ( t _ { \alpha } ^ { \prime } ( t ) )$ . The coefficients of this regression are $w _ { \alpha }$ and v.

The advantage of using Eq. (339) is simplicity – there are no parameters to train in this case. We still have to backtest the strategy (see below) out-of-sample. The disadvantage is that equally weighting contributions of all k nearest neighbors could be suboptimal. In this regard, there are various (e.g., distance-based) weighting schemes one may consider. Nontrivial weighting is precisely what Eq. (340) intends to capture. However, this requires training and cross-validation (using metrics such as root mean square error), and the fitted parameters $w _ { \alpha }$ and v can be (and often are) out-of-sample unstable. The data can be split, e.g., 60% for training and 40% for cross-validation. Ultimately, the strategy must backtest well out-of-sample.

The signal at $t = 0$ can be defined using the predicted value $\mathcal { V } = \mathcal { V } ( 0 )$ , which is the expected return for the next T days. For single-stock trading60 one can simply define thresholds for establishing long and short trades, and liquidating existing

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

positions, e.g., as follows:61

$$
{ \mathrm { S i g n a l } } = { \left\{ \begin{array} { l l } { { \mathrm { E s t a b l i s h ~ l o n g ~ p o s i t i o n ~ i f ~ } } \mathcal { V } > z _ { 1 } } \\ { { \mathrm { L i q u i d a t e ~ l o n g ~ p o s i t i o n ~ i f ~ } } \mathcal { V } \leq z _ { 2 } } \\ { { \mathrm { E s t a b l i s h ~ s h o r t ~ p o s i t i o n ~ i f ~ } } \mathcal { V } < - z _ { 1 } } \\ { { \mathrm { L i q u i d a t e ~ s h o r t ~ p o s i t i o n ~ i f ~ } } \mathcal { V } \geq - z _ { 2 } } \end{array} \right. }\tag{341}
$$

Here, $z _ { 1 }$ and $z _ { 2 }$ are trader-defined thresholds. This signal must be backtested outof-sample. The number k of nearest neighbors can be optimized using a backtest (by trying a set of values of k). Alternatively, one can use a common heuristic, e.g.,√ √ $k = \mathrm { f l o o r } ( \sqrt { T _ { * } } )$ or $k = \mathrm { c e i l i n g } ( \sqrt { T _ { * } } )$ . Also see, e.g., [Hall, Park and Samworth, 2008].

## 3.18 Strategy: Statistical arbitrage – optimization

Let $C _ { i j }$ be the sample or model covariance matrix for the N stock returns in a portfolio.62 Let $D _ { i }$ be the dollar holdings in our portfolio. The expected portfolio P&L P , volatility V and Sharpe ratio S are given by

$$
P = \sum _ { i = 1 } ^ { N } E _ { i } \ D _ { i }\tag{342}
$$

$$
V ^ { 2 } = \sum _ { i , j = 1 } ^ { N } C _ { i j } \ D _ { i } \ D _ { j }\tag{343}
$$

$$
S = P / V\tag{344}
$$

Here $E _ { i }$ are the expected stock returns. Instead of the dollar holdings $D _ { i } .$ , it is more convenient to work with dimensionless holding weights (which are positive/negative for long/short positions)

$$
w _ { i } = D _ { i } / I\tag{345}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

where I is the total investment level. The holding weights satisfy the condition

$$
\sum _ { i = 1 } ^ { N } \left| w _ { i } \right| = 1\tag{346}
$$

We have $\boldsymbol { P } = \boldsymbol { I } \times \boldsymbol { \widetilde { P } } , \boldsymbol { V } = \boldsymbol { I } \times \boldsymbol { \widetilde { V } }$ and $S = \widetilde { P } / \widetilde { V }$ , where

$$
\widetilde { P } = \sum _ { i = 1 } ^ { N } E _ { i } \ w _ { i }\tag{347}
$$

$$
\widetilde { V } ^ { 2 } = \sum _ { i , j = 1 } ^ { N } C _ { i j } \ w _ { i } \ w _ { j }\tag{348}
$$

To determine the portfolio weights $w _ { i }$ , often one requires that the Sharpe ratio [Sharpe, 1966], [Sharpe, 1994] be maximized:

$$
S  \mathrm { m a x }\tag{349}
$$

Assuming no additional conditions on $w _ { i }$ (e.g., upper or lower bounds), the solution to Eq. (349) in the absence of trading costs is given by

$$
w _ { i } = \gamma \sum _ { j = 1 } ^ { N } C _ { i j } ^ { - 1 } E _ { j }\tag{350}
$$

where $C ^ { - 1 }$ is the inverse of $C ,$ and the normalization coefficient $\gamma$ is determined from Eq. (346) (and $\gamma > 0$ so $\widetilde P > 0 )$ . The weights given by Eq. (350) generically do not correspond to a dollar-neutral portfolio. To have a dollar-neutral portfolio, we need to maximize the Sharpe ratio subject to the dollar-neutrality constraint.

## 3.18.1 Dollar-neutrality

We can achieve dollar-neutrality as follows. In the absence of bounds, trading costs, etc., the Sharpe ratio is invariant under simultaneous rescalings of all holding weights $w _ { i }  \zeta \ w _ { i }$ , where $\zeta > 0$ . Due to this scale invariance, the Sharpe ratio maximization problem can be recast in terms of minimizing a quadratic objective function:

$$
g ( w , \lambda ) = \frac { \lambda } { 2 } \sum _ { i , j = 1 } ^ { N } C _ { i j } \ w _ { i } \ w _ { j } - \sum _ { i = 1 } ^ { N } E _ { i } \ w _ { i }\tag{351}
$$

$$
g ( w , \lambda ) \to \operatorname* { m i n }\tag{352}
$$

where $\lambda > 0$ is a parameter, and minimization is w.r.t. $w _ { i }$ . The solution is given by

$$
w _ { i } = \frac { 1 } { \lambda } \sum _ { j = 1 } ^ { N } C _ { i j } ^ { - 1 } E _ { j }\tag{353}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

and λ is fixed via Eq. (346). The objective function approach – which is the meanvariance optimization [Markowitz, 1952] – is convenient if we wish to impose linear homogeneous constraints (which do not spoil the aforesaid scale invariance) on $w _ { i }$ e.g., the dollar-neutrality constraint. We introduce a Lagrange multiplier $\mu    \mathrm { : } ^ { 6 3 }$

$$
g ( w , \mu , \lambda ) = { \frac { \lambda } { 2 } } \sum _ { i , j = 1 } ^ { N } C _ { i j } \ w _ { i } \ w _ { j } - \sum _ { i = 1 } ^ { N } E _ { i } \ w _ { i } - \mu \ \sum _ { i = 1 } ^ { N } w _ { i }\tag{354}
$$

$$
g ( w , \mu , \lambda ) \to \operatorname* { m i n }\tag{355}
$$

Minimization w.r.t. $w _ { i }$ and $\mu$ now gives the following equations:

$$
\lambda \sum _ { j = 1 } ^ { N } C _ { i j } \ w _ { j } = E _ { i } + \mu\tag{356}
$$

$$
\sum _ { i = 1 } ^ { N } w _ { i } = 0\tag{357}
$$

So we have dollar-neutrality. The solution to Eqs. (356) and (357) is given by:

$$
w _ { i } = \frac { 1 } { \lambda } \left[ \sum _ { j = 1 } ^ { N } C _ { i j } ^ { - 1 } E _ { j } - \sum _ { j = 1 } ^ { N } C _ { i j } ^ { - 1 } \ \frac { \sum _ { k , l = 1 } ^ { N } C _ { k l } ^ { - 1 } E _ { l } } { \sum _ { k , l = 1 } ^ { N } C _ { k l } ^ { - 1 } } \right]\tag{358}
$$

By construction, $w _ { i }$ satisfy the dollar-neutrality constraint (357), and λ is fixed via Eq. (346). The expected returns $E _ { i }$ can be based on mean-reversion, momentum, machine learning or other signals. Eq. (358) constructs a dollar-neutral portfolio with “risk management” built in. E.g., the weights $w _ { i }$ (roughly) are suppressed by stock volatilities $\sigma _ { i }$ (where $\sigma _ { i } ^ { 2 } = C _ { i i } )$ assuming that on average $| E _ { i } |$ are of order $\sigma _ { i } . ^ { 6 4 }$

The above implementation of the dollar-neutrality constraint via minimizing the quadratic objective function (354) is equivalent to imposing this constraint in Sharpe ratio maximization as no trading costs, position/trading bounds, nonlinear/inhomogeneous constraints, etc., are present. More generally Sharpe ratio maximization is not equivalent to minimizing a quadratic objective function (see, e.g., [Kakushadze, 2015b]), albeit in practice usually the latter approach is used.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 3.19 Strategy: Market-making

Over-simplistically, this strategy amounts to capturing the bid-ask spread for a given stock and can be (again, over-simplistically) summarized as follows:

$$
{ \mathrm { R u l e } } = { \left\{ \begin{array} { l l } { { \mathrm { B u y ~ a t ~ t h e ~ b i d } } } \\ { { \mathrm { S e l l ~ a t ~ t h e ~ a s k } } } \end{array} \right. }\tag{359}
$$

In a market where most order flow is “dumb” (or uninformed), this strategy on average would work very well. However, in a market where most order flow is “smart” (or informed, i.e., “toxic”), this strategy, as stated, would lose money. This is because of adverse selection, where, precisely because most order flow is smart, most fills at the bid (ask) would be when the market is trading through it downward (upward), so these trades would lose money. Furthermore, most limit orders to buy (sell) at the bid (ask) would never be filled as the price would run away from them, i.e., increase (decrease). So, ideally, this strategy should be structured such that it captures dumb order flow and avoids smart order flow, which is not that simple.

One approach is, at any given time, within a short time horizon, to stay on the “right” side of the market, i.e., to have a short-horizon signal indicating the direction of the market and place limit orders accordingly (to buy at the bid if the signal indicates a price increase, and to sell at the ask if the signal indicates a price decrease). If the signal were (magically) 100% correct, this would capture the dumb order flow assuming that the orders get filled. This is a big assumption as for this to be guaranteed, the trader would have to be $\# 1$ in the queue among many other market participants placing limit orders at the same price point. This is where high frequency trading comes in – it is essentially all about speed with which orders are placed, canceled, and cancel-replaced. Infrastructure and technology are key in this.

Another possibility is to modulate the short-horizon signal with a longer-horizon signal (which can still be an intraday signal). The longer-horizon signal typically will have a higher cents-per-share65 than the shorter-horizon signal. Now certain trades can be profitable even with adverse selection, because they are established based on the longer-horizon signal. I.e., they “lose money” in the short term due to adverse selection (as the market trades through the corresponding limit orders), but they make money in a longer term. The market-making aspect of this is valuable as placing a passive limit order as opposed to an aggressive market or limit order saves money. On the other hand, in some cases, if the longer-horizon signal is strong enough and the shorter-horizon signal is in the same direction, a passive limit order would likely not get filled and it may make more sense to place an aggressive order. Such aggressive order flow is not dumb but smart, as it is based on nontrivial shortand long-horizon signals with a positive expected return.66 And speed still matters.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 3.20 Strategy: Alpha combos

With technological advances – hardware becoming cheaper and more powerful – it is now possible to data mine hundreds of thousands and even millions of alphas using machine learning methods. Here the term “alpha” – following common trader lingo – generally means any reasonable “expected return” that one may wish to trade on and is not necessarily the same as the “academic” alpha.67 In practice, often the detailed information about how alphas are constructed may not even be available, e.g., the only data available could be the position data, so “alpha” then is a set of instructions to achieve certain stock (or some other instrument) holdings by some times t1, t2, . . . Also, “machine learning” here refers to sophisticated methods that go beyond single-stock methods such as those discussed in Subsection 3.17 and involve cross-sectional analyses based on price-volume as well as other types of data (e.g., market cap, some other fundamental data such as earnings, industry classification data, sentiment data, etc.) for a large number of stocks (typically, a few thousand and up). 101 explicit examples of such quantitative trading alphas are given in [Kakushadze, 2016].68 The flipside is that these ubiquitous alphas are faint, ephemeral and cannot be traded on their own as any profit on paper would be eaten away by trading costs. To mitigate this, one combines a large number of such alphas and trades the so-combined “mega-alpha”. Hence “alpha combo” strategies.

This is not critical, but for definiteness let us assume that all alphas trade the same underlying instruments, even more concretely, the same universe of (say, 2,500) most liquid U.S. stocks. Each alpha produces desired holdings for this trading universe. What we need is the weights with which to combine individual alphas, whose number N can be large (in hundreds of thousands or even millions).69 Here is a procedure for fixing the alpha weights $w _ { i } , i = 1 , \ldots , N$ [Kakushadze and Yu, 2017b] (also see [Kakushadze and Yu, 2018a]):

• 1) Start with a time series of realized alpha returns $^ { 7 0 } R _ { i s } , i = 1 , . . . , N , s =$ $1 , \ldots , M + 1$

• 2) Calculate the serially demeaned returns $\begin{array} { r } { X _ { i s } = R _ { i s } - \frac { 1 } { M + 1 } \sum _ { s = 1 } ^ { M + 1 } R _ { i s } } \end{array}$

• 3) Calculate sample variances of alpha returns $\begin{array} { r } { { ^ { 7 1 } \sigma _ { i } ^ { 2 } = \frac { 1 } { M } \sum _ { s = 1 } ^ { M + 1 } X _ { i s } ^ { 2 } } } \end{array}$

• 4) Calculate the normalized demeaned returns $Y _ { i s } = X _ { i s } / \sigma _ { i } .$

• 5) Keep only the first M columns in $Y _ { i s } \colon s = 1 , \ldots , M$

• 6) Cross-sectionally demean $\begin{array} { r } { Y _ { i s } \colon \Lambda _ { i s } = Y _ { i s } - \frac { 1 } { N } \sum _ { i = 1 } ^ { N } Y _ { j s } } \end{array}$

• 7) Keep only the first M − 1 columns in $\Lambda _ { i s } \colon s = \mathsf { \bar { l } } , \ldots , M - 1$

• 8) Take the expected alpha returns $E _ { i }$ and normalize them: $\widetilde { E } _ { i } = E _ { i } / \sigma _ { i }$ . One (but by far not the only) way of computing expected alpha returns is via d-day moving averages (note that d need not be the same as T ):

$$
E _ { i } = \frac { 1 } { d } \sum _ { s = 1 } ^ { d } R _ { i s }\tag{360}
$$

• 9) Calculate the residuals $\widetilde { \varepsilon _ { i } }$ of the regression (without the intercept and with unit weights) of ${ \widetilde { E } } _ { i }$ over $\Lambda _ { i s }$

• 10) Set the alpha portfolio weights to $w _ { i } = \eta \widetilde { \varepsilon _ { i } } / \sigma _ { i }$

e• 11) Set the normalization coefficient η such that $\textstyle \sum _ { i = 1 } ^ { N } | w _ { i } | = 1$

## 3.21 A few comments

We end this section with a few comments on some of the stock trading strategies discussed above. First, single-stock technical analysis strategies (i.e., those based solely on single-stock as opposed to cross-sectional data) such as those based on moving averages, support and resistance, channel and even single-stock KNN, are deemed “unscientific” by many professionals and academics. On the face of it, “fundamentally” speaking (not to be confused with fundamental analysis), there is no reason why, say, a short moving average crossing a long moving average should have any forecasting power.72 This is not to say that moving averages are “unscientific” or that they should not be used. After all, e.g., trend following/momentum strategies are based on moving averages, i.e., the expected returns are computed via moving averages. However, looking at a large cross-section of stocks brings in a statistical element into the game. Mean-reversion is expected to work because stocks are expected to be correlated if they belong to the same industries, etc. This relates back

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

to fundamental analysis and – even more importantly – to the investors’ perception of how stock prices/returns “should” behave based on the companies’ fundamentals. However, here too it is important to keep in mind that the stock market – an imperfect man-made construct – is not governed by laws of nature the same way as, say, the motion of planets in the solar system is governed by fundamental laws of gravity (see, e.g., [Kakushadze, 2015d]). The markets behave the way they do because their participants behave in certain ways, which are sometimes irrational and certainly not always efficient. In this regard, the key difference between technical analysis strategies and statistical arbitrage strategies is that the latter are based on certain perceptions trickled down from longer holding horizons (fundamental analysis based strategies) to shorter horizons (statistical arbitrage) further enhanced by statistics, i.e., the fact that these strategies are based on a large number of stocks whose properties are further “stratified” according to some statistical and other features.

This brings us to the second point relating to precisely these “stratifications” in the context of statistical arbitrage. Thus, in Subsection 3.10 we can use a binary industry classification matrix as the loadings matrix $\Omega _ { i A }$ . Such industry classifications are based on pertinent fundamental/economic data, such as companies’ products and services, revenue sources, suppliers, competitors, partners, etc. They are essentially independent of the pricing data and, if well-built, tend to be rather stable out-of-sample as companies seldom jump industries. However, binary classifications can also be built based purely on pricing data, via clustering algorithms (see, e.g., [Kakushadze and Yu, 2016b]). Alternatively, the matrix $\Omega _ { i A }$ can be nonbinary and built using, say, principal components (see, e.g., [Kakushadze and Yu, 2017a]). Some of the columns of $\Omega _ { i A }$ can be based on longer-horizon style risk factors such as value, growth, size, momentum, liquidity and volatility (see, e.g., [Ang et al, 2006], [Anson, 2013], [Asness, 1995], [Asness et al, 2001], [Asness, Porter and Stevens, 2000], [Banz, 1981], [Basu, 1977], [Fama and French, 1992], [Fama and French, 1993], [Haugen, 1995], [Jegadeesh and Titman, 1993], [Lakonishok, Shleifer and Vishny, 1994], [Liew and Vassalou, 2000], [P´astor and Stambaugh, 2003], [Scholes and Williams, 1977]),73 or shorter-horizon style factors [Kakushadze, 2015c].

## 4 Exchange-traded funds (ETFs)

## 4.1 Strategy: Sector momentum rotation

Empirical evidence suggests that the momentum effect exists not only for individual stocks but also for sectors and industries.74 A sector momentum rotation strategy is

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

based on overweighing holdings in outperforming sectors and underweighing holdings in underperforming sectors, where the “outperformance” and “underperformance” are based on momentum during the past T -month formation period (which typically ranges from 6 to 12 months). ETFs concentrated in specific sectors/industries offer a simple way to implement sector/industry rotation without having to buy or sell a large number of underlying stocks. Similarly to Subsection 3.1, as a measure of sector/industry momentum, we can use the corresponding ETF’s cumulative return:

$$
R _ { i } ^ { c u m } ( t ) = \frac { P _ { i } ( t ) } { P _ { i } ( t + T ) } - 1\tag{361}
$$

Here $P _ { i } ( t )$ is the price of the ETF labeled by i. (As above, $t + T$ is T months in the past w.r.t. t.) Right after time t, the trader can, e.g., buy the ETFs in the top decile by $R _ { i } ^ { c u m } ( t )$ and hold the portfolio for a holding period (typically 1 to 3 months). Dollar-neutral strategies can also be constructed by, e.g., buying ETFs in the top decile and shorting ETFs in the bottom decile (as stocks, ETFs can be shorted).75

## 4.1.1 Strategy: Sector momentum rotation with MA filter

This is a variation/refinement of the sector momentum rotation strategy. An ETF in the top (bottom) decile is bought (sold) only if it passes an additional filter based on a moving average $\mathrm { M A } ( T ^ { \prime } )$ of this ETF’s price:

$$
{ \mathrm { R u l e } } = { \left\{ \begin{array} { l l } { { \mathrm { B u y ~ t o p  – d e c i l e ~ E T F s ~ o n l y ~ i f ~ } } P > { \mathrm { M A } } ( T ^ { \prime } ) } \\ { { \mathrm { S h o r t ~ b o t t o m  – d e c i l e ~ E T F s ~ o n l y ~ i f ~ } } P < { \mathrm { M A } } ( T ^ { \prime } ) } \end{array} \right. }\tag{362}
$$

Here P is the ETF’s price at the time of the transaction, and MA(T 0) is computed using daily prices $( T ^ { \prime }$ can but need not be equal $T \mathrm { ; ~ e . g . , ~ } T ^ { \prime }$ can be 100 to 200 days).

## 4.1.2 Strategy: Dual-momentum sector rotation

In long-only strategies, to mitigate the risk of buying ETFs when the broad market is trending down, relative (i.e., cross-sectional) momentum of sector ETFs can be augmented by the absolute (i.e., time-series) momentum of, e.g., a broad market index ETF (see, e.g., [Antonacci, 2014], [Antonacci, 2017]).76 So, a long position based on the sector rotation signal (discussed above) is established only if the broad

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

market index has an upward trend; otherwise, the total available funds are invested into an ETF (e.g., gold or Treasury ETF) uncorrelated with the broad market index:

$$
{ \mathrm { R u l e } } = { \left\{ \begin{array} { l l } { { \mathrm { B u y ~ t o p  – d e c i l e ~ E T F s ~ i f ~ } } P > { \mathrm { M A } } ( T ^ { \prime } ) } \\ { { \mathrm { B u y ~ a n ~ u n c o r r e l a t e d ~ E T F ~ i f ~ } } P \leq { \mathrm { M A } } ( T ^ { \prime } ) } \end{array} \right. }\tag{363}
$$

Here P is the broad market index ETF’s price at the time of the transaction, and MA(T 0) is the moving average of this ETF’s price. Typically, $T ^ { \prime }$ is 100 to 200 days.

## 4.2 Strategy: Alpha rotation

This is the same as the sector momentum rotation strategy with the cumulative ETF returns $R _ { i } ^ { c u m }$ replaced by ETF alphas $\alpha _ { i }$ , which are the regression coefficients corresponding to the intercept in a serial regression of the ETF returns77 Ri(t) over, e.g., the 3 Fama-French factors MKT(t), SMB(t), HML(t) (see fn. 50):78

$$
R _ { i } ( t ) = \alpha _ { i } + \beta _ { 1 , i } ~ \mathrm { M K T } ( t ) + \beta _ { 2 , i } ~ \mathrm { S M B } ( t ) + \beta _ { 3 , i } ~ \mathrm { H M L } ( t ) + \epsilon _ { i } ( t )\tag{364}
$$

## 4.3 Strategy: R-squared

Empirical studies for mutual funds (see, e.g., [Amihud and Goyenko, 2013], [Ferson and Mo, 2016]) and ETFs (see, e.g., [Garyn-Tal, 2014a], [Garyn-Tal, 2014b]) suggest that augmenting alpha by an indicator based on $R ^ { 2 }$ of a serial regression of the returns $R _ { i } ( t )$ over multiple factors, e.g., the 3 Fama-French factors MKT(t), SMB(t), HML(t) plus Carhart’s momentum factor MOM(t) (see fn. 50), adds value in forecasting future returns. Thus, from the serial regression

$$
R _ { i } ( t ) = \alpha _ { i } + \beta _ { 1 , i } \ \mathrm { M K T } ( t ) + \beta _ { 2 , i } \ \mathrm { S M B } ( t ) + \beta _ { 3 , i } \ \mathrm { H M L } ( t ) + \beta _ { 4 , i } \ \mathrm { M O M } ( t ) + \epsilon _ { i } ( t )\tag{365}
$$

we can estimate $\alpha _ { i }$ (the regression coefficients corresponding to the intercept) and the regression $R ^ { 2 }$ , which is defined as $\mathrm { ( ^ { 6 6 } S S ^ { 5 } ) }$ stands for “sum of squares”):

$$
R ^ { 2 } = 1 - \frac { \mathrm { S S } _ { r e s } } { \mathrm { S S } _ { t o t } }\tag{366}
$$

$$
\mathrm { S S } _ { r e s } = \sum _ { i = 1 } ^ { N } \epsilon _ { i } ^ { 2 } ( t )\tag{367}
$$

$$
\mathrm { S S } _ { t o t } = \sum _ { i = 1 } ^ { N } ( R _ { i } ( t ) - \overline { { R } } ( t ) ) ^ { 2 }\tag{368}
$$

$$
\overline { { R } } ( t ) = \frac { 1 } { N } \sum _ { i = 1 } ^ { N } R _ { i } ( t )\tag{369}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

An R-squared strategy then amounts to overweighing ETFs with higher “selectivity” (defined as $1 - R ^ { 2 }$ [Amihud and Goyenko, 2013]) and underweighing ETFs with lower “selectivity”. E.g., one can first sort ETFs into quintiles by $R ^ { 2 }$ , and then sort ETFs in each such quintile into further sub-quintiles by alpha (resulting in 25 groups of ETFs). One can then, e.g., buy ETFs in the group corresponding to the lowest $R ^ { 2 }$ quintile and its highest alpha sub-quintile and sell ETFs in the group corresponding to the highest $R ^ { 2 }$ quintile and its lowest alpha sub-quintile. Other variations are possible. Finally, the estimation period and the returns for $R ^ { 2 }$ can be the same as in the alpha rotation strategy (see Subsection 4.2 and fn. 77). However, longer estimation periods can be considered, especially if $R _ { i } ( t )$ are monthly returns.79

## 4.4 Strategy: Mean-reversion

One way (among myriad others) to construct a mean-reversion strategy for ETFs is to use the Internal Bar Strength (IBS) based on the previous day’s close $P _ { C } .$ , high $P _ { H }$ and low $P _ { L }$ prices:80

$$
{ \mathrm { I B S } } = { \frac { P _ { C } - P _ { L } } { P _ { H } - P _ { L } } }\tag{370}
$$

Note that IBS ranges from 0 to 1.81 An ETF can be thought of as being “rich” if its IBS is close to 1, and as “cheap” if its IBS is close to 0. Upon sorting a universe of ETFs cross-sectionally by IBS, a dollar-neutral strategy can, e.g., be constructed by selling ETFs in the top decile and buying ETFs in the bottom decile. As with stock strategies discussed above, weights can be uniform for all long and all short ETFs, respectively, or nonuniform, e.g., based on historical ETF volatilities. Furthermore, mean-reversion strategies we discussed above for stocks can also be adapted to ETFs.

## 4.5 Strategy: Leveraged ETFs (LETFs)

A leveraged (inverse) ETF seeks to double or triple (the inverse of) the daily return of its underlying index.82 To maintain a daily leverage of 2× or $3 \times$ , LETFs rebalance

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

every day, which requires buying on the days when the market is up and selling when the market is down. This can result in a negative drift in the long term, which can be exploited by shorting both a leveraged ETF and a leveraged inverse ETF (both with the same leverage and for the same underlying index) and investing the proceeds into, e.g., a Treasury ETF. This strategy can have a significant downside risk in the short term if one of the short ETF legs has a sizable positive return.

## 4.6 Strategy: Multi-asset trend following

One allure of ETFs is their diversification power: ETFs allow to gain exposure to different sectors, countries, asset classes, factors, etc., by taking positions in a relatively small number of ETFs (as opposed to taking positions in a large number of underlying instruments, e.g., thousands of stocks). Here we focus on long-only trend-following portfolios. One needs to determine the weight $w _ { i }$ of each ETF. One (but by far not the only) way to fix these weights is as follows. First, as in the sector momentum rotation strategy, we compute cumulative returns $R _ { i } ^ { c u m }$ (over some period T , e.g., 6-12 months). We only take ETFs with positive $R _ { i } ^ { c u m }$ If desired, optionally, we can further filter out ETFs as in the sector momentum rotation strategy with an MA filter, by keeping only the ETFs whose last closing prices $P _ { i }$ are higher than their corresponding long-term moving averages $\mathrm { M A } _ { i } ( T ^ { \prime } )$ (typically, the MA length $T ^ { \prime }$ is 100 to 200 days). Now, instead of taking ETFs in the top decile by $R _ { i } ^ { c u m }$ (as in the sector momentum rotation strategy), we can assign nonzero weights $w _ { i }$ to all remaining ETFs, whose number in this context is relatively small to begin with by design. The weights can, e.g., be assigned as follows:

$$
w _ { i } = \gamma _ { 1 } \ R _ { i } ^ { c u m }
$$

$$
w _ { i } = \gamma _ { 2 } \ R _ { i } ^ { c u m } / \sigma _ { i }\tag{371}
$$

$$
w _ { i } = \gamma _ { 3 } ~ R _ { i } ^ { c u m } / \sigma _ { i } ^ { 2 }\tag{372}
$$

(373)

Here: $\sigma _ { i }$ is the historical volatility; and the overall normalization coefficients $\gamma _ { 1 } , \gamma _ { 2 } ,$ γ 3 in each case are computed based on the requirement that $\textstyle \sum _ { i = 1 } ^ { N } w _ { i } = 1$ (where N is the number of ETFs in our portfolio after all filters are applied, i.e., those with nonzero weights). Thus, the weights in Eq. (371) are simply proportional to the past cumulative returns $R _ { i } ^ { c u m }$ , which are taken as the measure of momentum, so the expected returns are also given by (or, more precisely, proportional to) $R _ { i } ^ { c u m }$ The issue with this weighting scheme is that it overweighs volatile ETFs as on average $R _ { i } ^ { c u m } \propto \sigma _ { i }$ . The weights in Eq. (372) mitigate this, while the weights in Eq. (373) actually optimize the Sharpe ratio of the ETF portfolio assuming a diagonal covariance matrix $C _ { i j } = \mathrm { d i a g } ( \sigma _ { i } ^ { 2 } )$ for the ETF returns, i.e., by ignoring their correlations.83 Imposing bounds $w _ { i } \leq w _ { i } ^ { m a x }$ can further mitigate overweighing.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 5 Fixed Income

## 5.1 Generalities

## 5.1.1 Zero-coupon bonds

A promise of being paid \$1 at the maturity time T can be regarded as an asset, which has some worth at time t before T . This asset is called a (zero-coupon) discount bond. Let its price at time $0 \leq t \leq T$ be $\textstyle P ( t , T )$ . Then $P ( T , T ) = 1$ . The yield of a discount bond is defined $\mathrm { a s ^ { 8 4 } }$

$$
R ( t , T ) = - { \frac { \ln ( P ( t , T ) ) } { T - t } }\tag{374}
$$

and has the meaning of an average interest rate over the period of time $T - t .$ . The higher the bond price at time t, the lower the yield $R ( t , T )$ and vice versa. Below we refer to a zero-coupon bond with a \$1 principal and maturity T as a T -bond.

## 5.1.2 Bonds with coupons

In practice, a bond usually pays not only its principal at maturity T , but also makes smaller coupon payments before maturity. Consider a bond that makes n regular coupon payments at a fixed uncompounded rate k at times $T _ { i } = T _ { 0 } + i \delta$ $i = 1 , 2 , \dots , n$ , and also pays \$1 principal at maturity T . The amount of each coupon payment is kδ, where δ is the payment period. This income stream is equivalent to owning one T -bond plus kδ units of each Ti-bond, $i = 1 , \ldots , n$ . The price of the coupon bond at time t then is

$$
P _ { c } ( t , T ) = P ( t , T ) + k \delta \sum _ { i = I ( t ) } ^ { n } P ( t , T _ { i } )\tag{375}
$$

where $I ( t ) = \operatorname* { m i n } ( i : t < T _ { i } )$ . At time $t = T _ { 0 }$ we have

$$
P _ { c } ( T _ { 0 } , T ) = P ( T _ { 0 } , T ) + k \delta \sum _ { i = 1 } ^ { n } P ( T _ { 0 } , T _ { i } )\tag{376}
$$

If we desire the coupon bond to start with its face value $( P _ { c } ( T _ { 0 } , T ) = 1 )$ , then the corresponding coupon rate is given by

$$
k = { \frac { 1 - P ( T _ { 0 } , T ) } { \delta \sum _ { i = 1 } ^ { n } P ( T _ { 0 } , T _ { i } ) } }\tag{377}
$$

2015], [Sassetti and Tani, 2006], [Sharpe, 2009], [Sharpe and Perold, 2009], [Sørensen, 1999], [Tripathi and Garg, 2016], [Wu, 2003], [Zakamulin, 2014b].

84 More precisely, this definition assumes continuous compounding. For periodic compounding at n discrete times $T _ { i } = T _ { 0 } + i \delta , i = 1 , . . . , n$ , the yield between $t = T _ { 0 }$ and $t = T _ { n }$ is given by $R ( T _ { 0 } , T _ { n } ) = \delta ^ { - 1 } \left( [ P ( T _ { 0 } , T _ { n } ) ] ^ { - 1 / n } - 1 \right)$ assuming $P ( T _ { n } , T _ { n } ) = 1 , { \mathrm { i . e . , } } T _ { n }$ is the maturity. Eq. (374) is recovered in the limit where n → ∞, δ → 0, nδ = fixed (and equal to $T - t$ in Eq. (374)).

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 5.1.3 Floating rate bonds

A bond might also have floating coupon payments. Thus, consider a bond that pays \$1 at maturity T , and also makes coupon payments at times $T _ { i } = T _ { 0 } + i \delta$ $i = 1 , 2 , \dots , n$ with amounts based on the variable rate (usually LIBOR – see Subsection 5.15)

$$
L ( T _ { i - 1 } ) = \frac { 1 } { \delta } \left[ \frac { 1 } { P ( T _ { i - 1 } , T _ { i } ) } - 1 \right]\tag{378}
$$

The actual coupon payment at time $T _ { i }$ is

$$
X _ { i } = L ( T _ { i - 1 } ) \delta = \frac { 1 } { P ( T _ { i - 1 } , T _ { i } ) } - 1\tag{379}
$$

which is the amount of interest we would get by buying \$1’s worth of a Ti-bond at time $T _ { i - 1 }$ . Indeed, a Ti-bond is worth $P ( T _ { i - 1 } , T _ { i } )$ at $t = T _ { i - 1 }$ , so \$1’s worth a $T _ { i }$ -bond at $t = T _ { i - 1 }$ is worth $1 / P ( T _ { i - 1 } , T _ { i } )$ at $t = T _ { i } .$ , so the interest earned is given by Eq. (379). The total value of the variable coupon bond at $t = T _ { 0 }$ is given by:

$$
V _ { 0 } = 1 - [ P ( T _ { 0 } , T _ { n } ) - P ( T _ { 0 } , T ) ]\tag{380}
$$

If $T = T _ { n }$ , then we have $V _ { 0 } = 1$ . This is because this bond is equivalent to the following sequence of trades. At time $t = T _ { 0 }$ take \$1 and buy T1-bonds with it. At time $t = T _ { 1 }$ take the interest from the $T _ { 1 }$ -bonds as the T1-coupon, and buy T2-bonds with the leftover \$1 principal. Repeat until we are left with \$1 at time $T _ { n }$ . This has exactly the same cash flow as the variable coupon bond, so the initial prices must match. If $T > T _ { n }$ , then $V _ { 0 } < 1$ and can be determined as follows. First, note that

$$
V _ { 0 } = P ( T _ { 0 } , T ) + V _ { 0 } ^ { c o u p o n s }\tag{381}
$$

where $V _ { 0 } ^ { c o u p o n s }$ is the total value of all n coupon payments at $t = T _ { 0 }$ . This value is independent of T and is determined from

$$
P ( T _ { 0 } , T _ { n } ) + V _ { 0 } ^ { c o u p o n s } = 1\tag{382}
$$

which is the value of the variable coupon bond with maturity $T _ { n }$ . Hence Eq. (380).

## 5.1.4 Swaps

Swaps are contracts that exchange a stream of floating rate payments for a stream of fixed rate payments or vice versa. A swap where we receive a stream of fixed rate payments in exchange for floating rate payments is simply a portfolio which is long a fixed coupon bond and short a variable coupon bond. The price of the former at $t = T _ { 0 }$ is given by Eq. (376), while that of the latter is given by Eq. (380). The fixed rate that gives the swap initial null value is independent of maturity T and given by

$$
k = \frac { 1 - P ( T _ { 0 } , T _ { n } ) } { \delta \sum _ { i = 1 } ^ { n } P ( T _ { 0 } , T _ { i } ) }\tag{383}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 5.1.5 Duration and convexity

Macaulay duration of a bond is a weighted average maturity of its cash flows, where the weights are the present values of said cash flows. E.g., for a fixed rate coupon bond we have (see Eq. (376))

$$
\operatorname { M a c D } ( t , T ) = { \frac { 1 } { P _ { c } ( t , T ) } } \ \left[ \left( T - t \right) P ( t , T ) + k \delta \sum _ { i = I ( t ) } ^ { n } \left( T _ { i } - t \right) P ( t , T _ { i } ) \right]\tag{384}
$$

Modified duration is defined as (assuming parallel shifts in the yield curve)85

$$
\mathrm { M o d D } ( t , T ) = - \frac { \partial \ln \left( P _ { c } ( t , T ) \right) } { \partial R ( t , T ) }\tag{385}
$$

For continuous compounding, Macaulay duration and modified duration are the same (see Eq. (374)). For periodic compounding, they differ. For a constant yield $R ( t , \tau ) = Y = \mathrm { c o n s t } .$ . (for all $t < \tau < T )$ , they are related via (see fn. 84):

$$
\mathrm { M o d D } ( t , T ) = \mathrm { M a c D } ( t , T ) / ( 1 + Y \delta )\tag{386}
$$

Modified duration is a measure of the relative bond price sensitivity to changes in the interest rates: $\Delta P _ { c } ( t , T ) / P _ { c } ( t , T ) \approx - \mathrm { M o d D } ( t , T ) \ \Delta R ( t , T )$ (for parallel shifts $\Delta R ( t , \tau ) = \Delta R = \mathrm { c o n s t } .$ ., for all $t < \tau < T )$ . Similarly, dollar duration defined as

$$
\mathrm { D D } ( t , T ) = - { \frac { \partial P _ { c } ( t , T ) } { \partial R ( t , T ) } } = \mathrm { M o d D } ( t , T ) \ P _ { c } ( t , T )\tag{387}
$$

is a measure of the absolute bond price sensitivity to changes in the interest rates. Convexity of a bond is defined as (again, assuming parallel shifts)86

$$
C ( t , T ) = - \frac { 1 } { P _ { c } ( t , T ) } \frac { \partial ^ { 2 } P _ { c } ( t , T ) } { \partial R ( t , T ) ^ { 2 } }\tag{388}
$$

and corresponds to nonlinear effects in the response of the bond price to interest rate changes:

$$
\Delta P _ { c } ( t , T ) / P _ { c } ( t , T ) \approx - \mathrm { M o d } \mathrm { D } ( t , T ) \Delta R ( t , T ) + { \frac { 1 } { 2 } } C ( t , T ) [ \Delta R ( t , T ) ] ^ { 2 }\tag{389}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 5.2 Strategy: Bullets

In a bullet portfolio, all bonds have the same maturity date T thereby targeting a specific segment of the yield curve. The maturity can be picked based on the trader’s outlook on the future interest rates: if the interest rates are expected to fall (i.e., the bond prices to rise), then picking a longer maturity would make more sense; if the interest rates are expected to rise (i.e., the bond prices to fall), then a shorter maturity would be more warranted; however, if the trader is uncertain about the future interest rates, a more diversified portfolio (e.g., a barbell/ladder portfolio – see below) is in order (as opposed to a bullet portfolio). Typically, the bonds in a bullet portfolio are purchased over time, which mitigates the interest rate risk to some extent: if the interest rates rise, the later bond purchases will be at higher rates; if the interest rates fall, the earlier bond purchases will have higher yields.87

## 5.3 Strategy: Barbells

In this strategy all purchased bonds are concentrated in two maturities $T _ { 1 }$ (short maturity) and $T _ { 2 }$ (long maturity), so this portfolio is a combination of two bullet strategies. This strategy takes advantage of the higher yields from the long-maturity bonds while hedging the interest rate risk with the short-maturity bonds: if the interest rates rise, the long-maturity bonds will lose value, but the proceeds from the short-maturity bonds can be reinvested at higher rates.88 The modified duration (call it D) of the barbell strategy is the same as the modified duration (call it $D _ { * } )$ of a bullet strategy with a mid-range maturity (call it $T _ { * } , \ T _ { 1 } \ < \ T _ { * } \ < \ T _ { 2 } \Big )$ However, the convexity (call it C) of the barbell strategy is higher than the convexity (call it $C _ { * } )$ of this bullet strategy. Intuitively this can be understood by noting that modified duration scales approximately linearly with maturity, while convexity scales approximately quadratically with maturity. For illustrative purposes and simplicity, let us consider a barbell strategy consisting of $w _ { 1 }$ dollars’ worth of zerocoupon bonds with short maturity $T _ { 1 }$ and $w _ { 2 }$ dollars’ worth of zero-coupon bonds with long maturity $T _ { 2 }$ (each bond has \$1 face value). Furthermore, let us assume continuous compounding and a constant yield Y . We then have

$$
D = \frac { \widetilde { w } _ { 1 } T _ { 1 } + \widetilde { w } _ { 2 } T _ { 2 } } { \widetilde { w } _ { 1 } + \widetilde { w } _ { 2 } }
$$

$$
T _ { * } = D _ { * } = D\tag{390}
$$

(391)

$$
C = \frac { \widetilde { w } _ { 1 } T _ { 1 } ^ { 2 } + \widetilde { w } _ { 2 } T _ { 2 } ^ { 2 } } { \widetilde { w } _ { 1 } + \widetilde { w } _ { 2 } }\tag{392}
$$

$$
C _ { * } = T _ { * } ^ { 2 }\tag{393}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

where $\widetilde { w } _ { 1 } = w _ { 1 } \ \exp ( - T _ { 1 } \ Y )$ and $\widetilde { w } _ { 2 } = w _ { 2 } \ \mathrm { e x p } ( - T _ { 2 } \ Y )$ . Straightforward algebra gives

$$
C - C _ { * } = \frac { \widetilde { w } _ { 1 } \widetilde { w } _ { 2 } } { ( \widetilde { w } _ { 1 } + \widetilde { w } _ { 2 } ) ^ { 2 } } ~ ( T _ { 2 } - T _ { 1 } ) ^ { 2 } > 0\tag{394}
$$

Higher convexity of the barbell portfolio provides a better protection against parallel shifts in the yield curve. However, this comes at the expense of a lower overall yield.

## 5.4 Strategy: Ladders

A ladder is a bond portfolio with (roughly) equal capital allocations into bonds of n different maturities $T _ { i } , i = 1 , \ldots , n$ (where the number of rungs n is sizable, $\mathrm { e . g . } , n = 1 0 )$ The maturities are equidistant: $T _ { i + 1 } = T _ { i } + \delta$ . This is a durationtargeting strategy,89 which maintains an approximately constant duration by selling shorter-maturity bonds as they approach maturity and replacing them with new longer-maturity bonds. A ladder portfolio aims to diversify the interest rate and reinvestment risks90 by avoiding exposure to only a few maturities (as in bullets and barbells). It also generates a regular revenue stream from the coupons of each bond. The maturity of a ladder portfolio can be defined as the average maturity:

$$
T = \frac { 1 } { n } \sum _ { i = 1 } ^ { n } T _ { i }\tag{395}
$$

The income is higher for higher values of $T ;$ however, so is the interest rate risk.

## 5.5 Strategy: Bond immunization

Bond immunization is used in cases such as a predetermined future cash obligation. A simple solution would be to purchase a zero-coupon bond with the required maturity (and desirable/acceptable yield). However, such a bond may not always be available in the market, so a portfolio of bonds with varying maturities must be used instead. Such a portfolio is subject to the interest rate and reinvestment risks. One way to mitigate these risks is to build a portfolio whose duration matches the maturity of the future cash obligation (thereby “immunizing” the bond portfolio against parallel shifts in the yield curve). Consider a portfolio of bonds with 2 different maturities $T _ { 1 } , T _ { 2 }$ and the corresponding durations $D _ { 1 } , D _ { 2 }$ (where “duration” means modified duration). Let: the dollar amounts invested in these bonds be $P _ { 1 } , P _ { 2 } ;$ the total amount to be invested be $P ;$ the desired duration of the portfolio be D (which

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

is related to the maturity $T _ { * }$ of the future cash obligation – see below); and the constant yield (which is assumed to be the same for all bonds – see below) be Y . Then P is fixed using Y and the amount of the future obligation $F ;$

$$
P = F / ( 1 + Y \delta ) ^ { T _ { * } / \delta }\tag{396}
$$

where we are assuming periodic compounding and δ is the length of each compounding period (e.g., 1 year).91 Then we have:

$$
P _ { 1 } + P _ { 2 } = P\tag{397}
$$

$$
P _ { 1 } \ D _ { 1 } + P _ { 2 } \ D _ { 2 } = P \ D\tag{398}
$$

where

$$
D = T _ { * } / ( 1 + Y \delta )\tag{399}
$$

With 3 bonds, we can also match the convexity:

$$
P _ { 1 } + P _ { 2 } + P _ { 3 } = P\tag{400}
$$

$$
P _ { 1 } \ D _ { 1 } + P _ { 2 } \ D _ { 2 } + P _ { 3 } \ D _ { 3 } = P \ D\tag{401}
$$

$$
P _ { 1 } \ C _ { 1 } + P _ { 2 } \ C _ { 2 } + P _ { 3 } \ C _ { 3 } = P \ C\tag{402}
$$

where $C _ { 1 } , C _ { 2 } , C _ { 3 }$ are the convexities of the 3 bonds and

$$
C = T _ { * } ( T _ { * } + \delta ) / ( 1 + Y \delta ) ^ { 2 }\tag{403}
$$

In practice, the yield curve changes over time, which (among other things) requires that the portfolio be periodically rebalanced. This introduces nontrivial transaction costs, which must also be accounted for. Furthermore, the yields are not the same for all bonds in the portfolio, which introduces additional complexity into the problem.92

## 5.6 Strategy: Dollar-duration-neutral butterfly

This is a zero-cost combination of a long barbell portfolio (with short $T _ { 1 }$ and long $T _ { 3 }$ maturities) and a short bullet portfolio (with a medium maturity $T _ { 2 }$ , where $T _ { 1 } < T _ { 2 } < T _ { 3 } )$ . Let: the dollar amounts invested in the 3 bonds be $P _ { 1 } , P _ { 2 } , P _ { 3 } ;$ and

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

the corresponding modified durations be $D _ { 1 } , D _ { 2 } , D _ { 3 }$ Then zero cost (i.e., dollarneutrality) and the dollar-duration-neutrality (the latter protects the portfolio from parallel shifts in the yield curve) imply that

$$
P _ { 1 } + P _ { 3 } = P _ { 2 }\tag{404}
$$

$$
P _ { 1 } \ D _ { 1 } + P _ { 3 } \ D _ { 3 } = P _ { 2 } \ D _ { 2 }\tag{405}
$$

This fixes $P _ { 1 } , P _ { 3 }$ via $P _ { 2 }$ . While the portfolio is immune to parallel shifts in the yield curve, it is not immune to changes in the slope or the curvature of the yield curve.93

## 5.7 Strategy: Fifty-fifty butterfly

This is a variation of the standard butterfly. In the above notations for the dollarduration-neutral butterfly, we have

$$
P _ { 1 } ~ D _ { 1 } = P _ { 3 } ~ D _ { 3 } = { \frac { 1 } { 2 } } ~ P _ { 2 } ~ D _ { 2 }\tag{406}
$$

So, the fifty-fifty butterfly is still dollar-duration-neutral, but it is no longer dollarneutral (i.e., it is not a zero-cost strategy). Instead, dollar durations of the wings are the same (hence the term “fifty-fifty”). As a result, the strategy is (approximately) neutral to small steepening and flattening of the yield curve, to wit, if the interest rate spread change between the body and the short-maturity wing is equal to the spread change between the long-maturity wing and the body. That is why this strategy is a.k.a. “neutral curve butterfly” (whose cost is non-dollar-neutrality).

## 5.8 Strategy: Regression-weighted butterfly

Empirically, short-term interest rates are sizably more volatile than long-term interest rates.94 Therefore, the interest rate spread change between the body and the short-maturity wing (of the butterfly – see above) can be expected to be greater by some factor – call it β – than the spread change between the long-maturity wing and the body (so, typically $\beta > 1 )$ . This factor can be obtained from historical data via, e.g., running a regression of the spread change between the body and the short-maturity wing over the spread change between the long-maturity wing and the body. Then, instead of Eq. (406), we have the following dollar-duration-neutrality and “curve-neutrality” conditions:

$$
P _ { 1 } \ D _ { 1 } + P _ { 3 } \ D _ { 3 } = P _ { 2 } \ D _ { 2 }
$$

$$
P _ { 1 } ~ D _ { 1 } = \beta ~ P _ { 3 } ~ D _ { 3 }\tag{407}
$$

(408)

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 5.8.1 Strategy: Maturity-weighted butterfly

This is a variation of the regression-weighted butterfly, where instead of fixing $\beta$ in Eq. (408) via a regression based on historical data, this coefficient is based on the 3 bond maturities:

$$
\beta = \frac { T _ { 2 } - T _ { 1 } } { T _ { 3 } - T _ { 2 } }\tag{409}
$$

## 5.9 Strategy: Low-risk factor

As in stocks, empirical evidence suggests that lower-risk bonds tend to outperform higher-risk bonds on the risk-adjusted basis (“low-risk anomaly”).95 One can define “riskiness” of a bond using different metrics, e.g., bond credit rating and maturity. For instance, a long portfolio can be built (see, e.g., [Houweling and van Vundert, 2017]) by taking Investment Grade bonds with credit ratings AAA through A-, and then taking the bottom decile by maturity. Similarly, one can take High Yield bonds with credit ratings BB+ through B-, and then take the bottom decile by maturity.

## 5.10 Strategy: Value factor

“Value” for bonds (see, e.g., [Correia, Richardson and Tuna, 2012], [Houweling and van Vundert, 2017], [L’Hoir and Boulhabel, 2010]) is trickier to define than for stocks. One way is to compare the observed credit spread96 to a theoretical prediction therefor. One way to estimate the latter is, e.g., via a linear cross-sectional (across N bonds labeled by $i = 1 , \ldots , N )$ regression [Houweling and van Vundert, 2017]:

$$
S _ { i } = \sum _ { r = 1 } ^ { K } \beta _ { r } ~ I _ { i r } + \gamma ~ T _ { i } + \epsilon _ { i }\tag{410}
$$

$$
S _ { i } ^ { * } = S _ { i } - \epsilon _ { i }\tag{411}
$$

Here: $S _ { i }$ is the credit spread; $I _ { i r }$ is a dummy variable $( I _ { i r } = 1$ if the bond labeled by i has credit rating $r ;$ otherwise, $I _ { i r } = 0 )$ for bond credit rating r (which labels K credit ratings present among the N bonds, which can be one of the 21 credit ratings);97 $T _ { i }$ are bond maturities; $\beta _ { r } , \gamma$ are the regression coefficients; $\epsilon _ { i }$ are the regression residuals; and $S _ { i } ^ { * }$ is the fitted (theoretical) value of the credit spread. The $N \times K$ matrix $I _ { i r }$ has no columns with all zeros (so K can be less than 21). Note that by definition, since each bond has one and only one credit rating, we have

$$
\sum _ { r = 1 } ^ { K } I _ { i r } = 1\tag{412}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

so the intercept is subsumed in $I _ { i r }$ (which is why there is no separate regression coefficient for the intercept). Next, value is defined as $V _ { i } = \ln ( S _ { i } / S _ { i } ^ { * } )$ or $V _ { i } = \epsilon _ { i } / S _ { i } ^ { * } =$ $S _ { i } / S _ { i } ^ { * } - 1$ , and the bonds in the top decile by $V _ { i }$ are selected for the portfolio.

## 5.11 Strategy: Carry factor

Carry is defined as the return from the appreciation of the bond value as the bond rolls down the yield curve (see, e.g., [Beekhuizen et al, 2016], [Koijen, Moskowitz, Pedersen and Vrugt, 2018]):98

$$
C ( t , t + \Delta t , T ) = \frac { P ( t + \Delta t , T ) - P ( t , T ) } { P ( t , T ) }\tag{413}
$$

Here $\Delta t$ is the period over which carry is computed. A simplification arises if we assume that the entire term structure of the interest rates stays constant, i.e., the yield $R ( t , T ) = f ( T - t )$ is a function of only $T - t \ ( { \mathrm { i . e . } }$ , time to maturity). Then, at time $t + \Delta t$ the yield is $R ( t + \Delta t , T ) = R ( t , T - \Delta t )$ . So, we have99

$$
\begin{array} { r c l } { C ( t , t + \Delta t , T ) } & { = } & { \frac { P ( t + \Delta t , T ) | _ { R ( t + \Delta t , T ) } - P ( t , T ) | _ { R ( t , T ) } } { P ( t , T ) | _ { R ( t , T ) } } = } \\ & { = } & { R ( t , T ) \Delta t + C _ { r o l l } ( t , t + \Delta t , T ) } \end{array}\tag{414}
$$

where (taking into account the definition of the modified duration, Eq. (385))

$$
\begin{array} { r c l } { C _ { r o l l } ( t , t + \Delta t , T ) } & { = } & { \frac { P ( t + \Delta t , T ) | _ { R ( t , T - \Delta t ) } - P ( t + \Delta t , T ) | _ { R ( t , T ) } } { P ( t , T ) | _ { R ( t , T ) } } \approx } \\ & { \approx } & { - \mathrm { M o d D } ( t , T ) \left[ R ( t , T - \Delta t ) - R ( t , T ) \right] } \end{array}\tag{415}
$$

${ \mathrm { S o } } ,$ if the term structure of the interest rates is constant, then carry $C ( t , t + \Delta t , T )$ receives two contributions: i) R(t, T ) ∆t from the bond yield; and ii) $C _ { r o l l } ( t , t + \Delta t , T )$ from the bond rolling down the yield curve. A zero-cost strategy can be built, e.g., by buying bonds in the top decile by carry and selling bonds in the bottom decile.

## 5.12 Strategy: Rolling down the yield curve

The objective of this strategy is to capture the “roll-down” component $C _ { r o l l } ( t , t +$ $\Delta t , T )$ of bond yields. These returns are maximized in the steepest segments of the yield curve. Therefore, the trader can, e.g., buy long- or medium-term bonds from

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

such segments and hold them while they are “rolling down the curve”.100 The bonds must be sold as they approach maturity and the proceeds can be used to buy new long/medium-term bonds from the steepest segment of the yield curve at that time.

## 5.13 Strategy: Yield curve spread (flatteners & steepeners)

This strategy consists of buying or selling the yield curve spread.101 The yield curve spread is defined as the difference between the yields of two bonds of the same issuer with different maturities. If the interest rates are expected to fall, the yield curve is expected to steepen. If the interest rates are expected to rise, the yield curve is expected to flatten. The yield curve spread strategy can be summarized via the following rule:

$$
{ \mathrm { R u l e } } = { \left\{ \begin{array} { l l } { { \mathrm { F l a t t e n e r : ~ S h o r t ~ s p r e a d ~ i f ~ i n t e r e s t ~ r a t e s ~ a r e ~ e x p e c t e d ~ t o ~ r i s e } } } \\ { { \mathrm { S t e e p e n e r : ~ B u y ~ s p r e a d ~ i f ~ i n t e r e s t ~ r a t e s ~ a r e ~ e x p e c t e d ~ t o ~ f a l l } } } \end{array} \right. }\tag{416}
$$

Shorting the spread amounts to selling shorter-maturity bonds (a.k.a. the front leg) and buying longer-maturity bonds (a.k.a. the back leg). Buying the spread is the opposite trade: buying the front leg and selling the back leg. If the yield curve has parallel shifts, this strategy can generate losses. Matching dollar durations of the front and back legs immunizes the portfolio to small parallel shifts in the yield curve.

## 5.14 Strategy: CDS basis arbitrage

A credit default swap (CDS) is insurance against default on a bond.102 The CDS price, known as the CDS spread, is a periodic (e.g., annual) premium per dollar of the insured debt. The CDS essentially makes the bond a risk-free instrument. Therefore, the CDS spread should equal the bond yield spread, i.e., the spread between the bond yield and the risk-free rate. The difference between the CDS spread and the bond spread is known as the CDS basis:

$$
\mathrm { C D S ~ b a s i s } = \mathrm { C D S ~ s p r e a d } - \mathrm { b o n d ~ s p r e a d }\tag{417}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Negative basis indicates that the bond spread is too high relative to the CDS spread, i.e., the bond is relatively cheap. The CDS arbitrage trade then amounts to buying the bond and insuring it with the CDS103 thereby generating a risk-free profit.104

## 5.15 Strategy: Swap-spread arbitrage

This dollar-neutral strategy consists of a long (short) position in an interest rate swap (see Subsection 5.1.4) and a short (long) position in a Treasury bond (with the constant yield $Y _ { T r e a s u r y } )$ with the same maturity as the swap. A long (short) swap involves receiving (making) fixed rate $r _ { s w a p }$ coupon payments in exchange for making (receiving) variable rate coupon payments at LIBOR (the London Interbank Offer Rate) L(t). The short (long) position in the Treasury bond generates (is financed at) the “repo rate” (the discount rate at which the central bank repurchases government securities from commercial banks) $r ( t )$ in a margin account. The per-dollar-invested rate C(t) at which this strategy generates P&L is given by

$$
C ( t ) = \pm [ C _ { 1 } - C _ { 2 } ( t ) ]\tag{418}
$$

$$
C _ { 1 } = r _ { s w a p } - Y _ { T r e a s u r y }\tag{419}
$$

$$
C _ { 2 } ( t ) = L ( t ) - r ( t )\tag{420}
$$

where the plus (minus) sign corresponds to the long (short) swap strategy. The long (short) swap strategy is profitable if LIBOR falls (rises). So, this is a LIBOR bet.105

## 6 Indexes

## 6.1 Generalities

An index is a diversified portfolio of assets combined with some weights. The underlying assets are often stocks, e.g., in indexes such as DJIA, S&P 500, Russell 3000, etc. DJIA weights are based on price, while S&P 500 and Russell 3000 weights are based on market capitalization. Investment vehicles such as index futures, indexbased ETFs, etc., allow gaining exposure to a broad index with a single trade.106

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 6.2 Strategy: Cash-and-carry arbitrage

This strategy (a.k.a. “index arbitrage”) aims to exploit price inefficiencies between the index spot107 price and index futures price.108 Theoretically, the price of the index futures must equal the spot price accounting for the cost of carry during the life of the futures contract:

$$
F ^ { * } ( t , T ) = \left[ S ( t ) - D ( t , T ) \right] \exp \left( r \left( T - t \right) \right)\tag{421}
$$

Here: $F ^ { * } ( t , T )$ is the theoretical $( ^ { \circ } \mathrm { f a i r } ^ { \prime \prime } )$ price, at time t, of the futures contract with the delivery time $T ; \ S ( t )$ is the spot value at time $\because D ( t , T )$ is the sum of (discounted values of) the dividends paid by the underlying stocks between the time t and delivery; and r is the risk-free rate, which for the sake of simplicity is assumed to be constant from t to delivery.109 The basis is defined as

$$
B ( t , T ) = \frac { F ( t , T ) - F ^ { * } ( t , T ) } { S ( t ) }\tag{422}
$$

where $F ( t , T )$ is the current price of the futures contract with the delivery time $T .$ If $B ( t , T ) \neq 0$ , more precisely, if $| B ( t , T ) |$ exceeds the pertinent transaction costs of executing the arbitrage trade, then there is an arbitrage opportunity. If the basis is positive (negative), the futures price is rich (cheap) compared with the spot price, so the arbitrage trade amounts to selling (buying) the futures and buying (selling) the cash (i.e., the index basket).110 The position is closed when the basis goes to zero, i.e., the futures price converges to its fair value. Such arbitrage opportunities are short-lived and with the advent of high frequency trading require extremely fast execution. In many cases, the slippage can be prohibitive to execute the trade.111

## 6.3 Strategy: Dispersion trading in equity indexes

This strategy takes long positions on volatilities of the index constituents and a short position on index volatility. It is rooted in an empirical observation that, for

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

the most part,112 the implied volatility $\widetilde { \sigma } _ { I }$ from index options is sizably higher than the theoretical index volatility $\sigma _ { I }$ egiven by

$$
\sigma _ { I } ^ { 2 } = \sum _ { i , j = 1 } ^ { N } w _ { i } w _ { j } \sigma _ { i } \sigma _ { j } \rho _ { i j }\tag{423}
$$

where $w _ { i }$ are the weights of the stocks in the index, $\sigma _ { i }$ are their implied volatilities from single-stock options, and $\rho _ { i j }$ is the sample correlation matrix $( \rho _ { i i } ~ = ~ 1 ) ^ { 1 1 3 }$ computed based on a time series of historical returns.114 Put differently, the index options are priced higher than the price corresponding to the aforesaid theoretical volatility. So, a basic strategy can be structured as follows. For each stock in the index we have a long position in $n _ { i }$ (near-ATM) single-stock option straddles (whose payoffs are based on the stock prices $P _ { i } )$ , and we have a short position in a (near-ATM) option straddle for the index (whose payoff is based on the index level $P _ { I } -$ see below), where

$$
n _ { i } = \frac { S _ { i } P _ { I } } { \sum _ { i = 1 } ^ { N } { S _ { i } P _ { i } } }\tag{424}
$$

Here: $S _ { i }$ is shares outstanding for stock $i$ (we are assuming the index is market cap weighted); and $P _ { I }$ is the index level. With this definition of $n _ { i } .$ , we have $P _ { I } =$ $\textstyle \sum _ { i = 1 } ^ { \bar { N } } n _ { i } P _ { i }$ , so the index option straddle payoff matches the individual single-stock option straddle payoffs as closely as possible.115 All options have approximately 1 month until the expiration, and all positions remain open until the expiration.116

## 6.3.1 Strategy: Dispersion trading – subset portfolio

For some indexes, some component stocks may not have single-stock options. Often these would be less liquid, lower market cap stocks. They would have to be excluded

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

from the bought portfolio. Reducing the number of bought underlying single-stock options is also desirable to reduce transaction costs. Furthermore, the sample correlation matrix $\rho _ { i j }$ is singular for a typical lookback period (e.g., daily close-to-close returns, going back 1 year, which is about 252 trading days) as the number of assets is large (500 for S&P 500 and even larger for other indexes). As mentioned above, the pair-wise correlations are unstable out-of-sample, which increases errors in the theoretical value $\sigma _ { I }$ computed via Eq. (423). This can be mitigated as follows.117

The singular and unstable correlation matrix can be made nonsingular and more stable by replacing it with a statistical risk model [Kakushadze and Yu, 2017a]. Let $V _ { i } ^ { ( A ) }$ be the principal components of $\rho _ { i j }$ with the eigenvalues $\lambda ^ { ( A ) }$ in the decreasing order, $\lambda ^ { ( 1 ) } > \lambda ^ { ( 2 ) } > \lambda ^ { ( r ) }$ , where r is the rank of $\rho _ { i j }$ (if $r < N$ , the other eigenvalues are null: $\lambda ^ { ( A ) } = 0 , A > r )$ . The statistical risk model correlation matrix is given by

$$
\psi _ { i j } = \xi _ { i } ^ { 2 } ~ \delta _ { i j } + \sum _ { A = 1 } ^ { K } \lambda ^ { ( A ) } ~ V _ { i } ^ { ( A ) } ~ V _ { j } ^ { ( A ) }\tag{425}
$$

$$
\xi _ { i } ^ { 2 } = 1 - \sum _ { A = 1 } ^ { K } \lambda ^ { ( A ) } \left[ V _ { i } ^ { ( A ) } \right] ^ { 2 }\tag{426}
$$

where $K < r$ is the number of risk factors based on the first K principal components that are chosen to explain systematic risk, and $\xi _ { i }$ is the specific (a.k.a. idiosyncratic) risk. The simplest way to fix K is via eRank (effective rank) [Roy and Vetterli, 2007] – see [Kakushadze and Yu, 2017a] for details and complete source code for constructing $\psi _ { i j }$ and fixing K. So, now we can use $\psi _ { i j }$ (instead of $\rho _ { i j } )$ to compute the theoretical volatility $\sigma _ { I } .$

$$
\sigma _ { I } ^ { 2 } = \sum _ { i , j = 1 } ^ { N } w _ { i } w _ { j } \sigma _ { i } \sigma _ { j } \psi _ { i j } = \sum _ { i = 1 } ^ { N } w _ { i } ^ { 2 } \sigma _ { i } ^ { 2 } \xi _ { i } ^ { 2 } + \sum _ { A = 1 } ^ { K } \left[ \sum _ { i = 1 } ^ { N } \lambda ^ { ( A ) } V _ { i } ^ { ( A ) } w _ { i } \sigma _ { i } \right] ^ { 2 }\tag{427}
$$

The first term on the r.h.s. of Eq. (427) is due to the specific risk. The long portfolio then contains only the straddles corresponding to the first $N _ { * }$ single-stock options with the lowest $N _ { * }$ values of $w _ { i } ^ { 2 } \sigma _ { i } ^ { 2 } \xi _ { i } ^ { 2 }$ . E.g., for S&P 500 we can take $N _ { * } = 1 0 0$

## 6.4 Strategy: Intraday arbitrage between index ETFs

This strategy amounts to exploiting short-term mispricings between two ETFs (call them ETF1 and ETF2) on the same underlying index.118 It can be summarized as

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

follows:

$$
{ \mathrm { R u l e } } = { \left\{ \begin{array} { l l } { { \mathrm { B u y ~ E T F 2 , ~ s h o r t ~ E T F 1 } } } & { { \mathrm { i f ~ } } P _ { 1 } ^ { B i d } \geq P _ { 2 } ^ { A s k } \times \kappa } \\ { { \mathrm { L i q u i d a t e ~ p o s i t i o n ~ } } } & { { \mathrm { i f ~ } } P _ { 2 } ^ { B i d } \geq P _ { 1 } ^ { A s k } } \\ { { \mathrm { B u y ~ E T F 1 , ~ s h o r t ~ E T F 2 } } } & { { \mathrm { i f ~ } } P _ { 2 } ^ { B i d } \geq P _ { 1 } ^ { A s k } \times \kappa } \\ { { \mathrm { L i q u i d a t e ~ p o s i t i o n ~ } } } & { { \mathrm { i f ~ } } P _ { 1 } ^ { B i d } \geq P _ { 2 } ^ { A s k } } \end{array} \right. }\tag{428}
$$

Here: κ is a predefined threshold, which is close to 1, e.g., κ = 1.002 (see, e.g., [Marshall, Nguyen and Visaltanachoti]); $P _ { 1 } ^ { B i d }$ and $P _ { 2 } ^ { B i d }$ are the bid prices for ETF1 and ETF2, and $P _ { 1 } ^ { A s k }$ and $P _ { 2 } ^ { A s k }$ are the ask prices. Marketable “fill or $\mathrm { k i l l } ^ { \dag }$ limit orders can be used to execute the trades. Such arbitrage opportunities are ephemeral and require a fast order execution system or else slippage will eat away the profits.

## 6.5 Strategy: Index volatility targeting with risk-free asset

A volatility targeting strategy aims to maintain a constant volatility level, which can be achieved by a periodic (weekly, monthly, etc.) rebalancing between a risky asset – in this case an index – and a riskless asset (e.g., U.S. Treasury bills).119 If σ is the volatility of the risky asset120 and the volatility target is $\sigma _ { * } ,$ then the allocation weight for the risky asset is given $\mathrm { b y } ^ { 1 2 1 } ~ w = \sigma _ { * } / \sigma$ , and the allocation weight for the risk-free asset is $1 - w$ . To avoid overtrading and reduce transaction costs, rebalancing (instead of periodically) can be done based, e.g., on a preset threshold κ, say, only if the percentage change $| \Delta w | / w$ since the last rebalancing exceeds κ.

## 7 Volatility

## 7.1 Generalities

Some option trading strategies discussed in Section 2 are volatility strategies, in the sense that they make bets on high or low future volatility.122 There are various ways to make volatility bets, and volatility can be viewed as an asset class of its own. Historical volatility is based on a time series of past returns. In contrast, implied volatility extracted from options is considered a forward-looking measure of volatility.123 VIX (CBOE Volatility Index, a.k.a. the “uncertainty index” or the

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

“fear gauge index”)124 and other volatility indexes125 and derivatives (options and futures) on volatility indexes such as VIX provide avenues for volatility trading.

## 7.2 Strategy: VIX futures basis trading

This is essentially a mean-reversion strategy. It is rooted in empirical observations (see, e.g., [Mixon, 2007], [Nossman and Wilhelmsson, 2009], [Simon and Campasano, 2014])126 that the VIX futures basis (defined below) has essentially no forecasting power for subsequent VIX changes but has substantial forecasting power for subsequent VIX futures price changes. The VIX futures basis $B _ { V I X }$ (for our purposes here) is defined as

$$
B _ { V I X } = P _ { U X 1 } - P _ { V I X }\tag{429}
$$

$$
D = { \frac { B _ { V I X } } { T } }\tag{430}
$$

Here: $P _ { U X 1 }$ is the price of the first-month contract VIX futures;127 $P _ { V I X }$ is the VIX price; D is the daily roll value; and T is the number of business days until the settlement (which is assumed to be at least 10). Empirically, the futures prices tend to fall for positive basis and rise for negative basis (mean-reversion). So, the strategy amounts to shorting VIX futures when the VIX futures curve is upwardsloping (a.k.a. “contango”, so the basis is positive), and buying VIX futures when the VIX futures curve is downward-sloping (a.k.a. “backwardation”, so the basis is negative). Here is a simple trading rule (see, e.g., [Simon and Campasano, 2014]):

$$
{ \mathrm { R u l e } } = { \left\{ \begin{array} { l l } { { \mathrm { O p e n ~ l o n g ~ U X 1 ~ p o s i t i o n } } } & { { \mathrm { ~ i f ~ } } D < - 0 . 1 0 } \\ { { \mathrm { C l o s e ~ l o n g ~ U X 1 ~ p o s i t i o n } } } & { { \mathrm { ~ i f ~ } } D > - 0 . 0 5 } \\ { { \mathrm { O p e n ~ s h o r t ~ U X 1 ~ p o s i t i o n } } } & { { \mathrm { ~ i f ~ } } D > 0 . 1 0 } \\ { { \mathrm { C l o s e ~ s h o r t ~ U X 1 ~ p o s i t i o n } } } & { { \mathrm { ~ i f ~ } } D < 0 . 0 5 } \end{array} \right. }\tag{431}
$$

A short (long) UX1 position is exposed to a risk of a sudden increase (decrease) in the volatility, which typically occurs during equity market sell-offs (rallies), so this risk can be hedged by, e.g., shorting (buying) mini-S&P 500 futures.128 The hedge

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

ratio can be estimated, e.g., based on a historical serial regression of the VIX futures price changes over the front-month mini-S&P 500 futures contract returns.129

## 7.3 Strategy: Volatility carry with two ETNs

VXX is an exchange-traded note (ETN) that tracks VIX via a portfolio of shortmaturity (months 1 and 2) VIX futures contracts. To maintain a constant maturity, at the close of each day, a portion of the shorter-maturity futures is sold and replaced with the longer-maturity futures bought with the proceeds. Since the VIX futures curve is in contango most of the time, the longer-maturity futures are priced higher than the shorter-maturity futures, so this rebalancing amounts to a decay in the value of VXX over time, which is known as the roll (or contango) loss. Further, as time passes, the futures converge to the spot (VIX), so VXX loses value so long as the VIX futures curve is in contango. VXZ is yet another ETN that tracks VIX via a portfolio of medium-maturity (months 4 through 7) VIX futures. VXZ also suffers roll loss, but to a lesser degree than VXX as the slope of the VIX futures curve in contango decreases with maturity.130 The basic strategy then is to short VXX and buy VXZ with the hedge ratio that can be determined via a serial regression.131 This strategy is not without risks, however. There can be short-term spikes in VXX (the corresponding spikes in VXZ usually are sizably smaller), which can lead to substantial short-term P&L drawdowns, even if the strategy is overall profitable.

## 7.3.1 Strategy: Hedging short VXX with VIX futures

Instead of using a long position in VXZ to hedge the short position in VXX, one can directly use a basket of, e.g., medium-maturity VIX futures.132 The N VIX futures have some weights $w _ { i }$ . These weights can be fixed in a variety of ways, e.g., by minimizing the tracking error, i.e., by running a serial regression (with the intercept) of VXX returns over the N futures returns. Then we have:

$$
w _ { i } = \sigma _ { X } \sum _ { j = 1 } ^ { N } C _ { i j } ^ { - 1 } \sigma _ { j } \rho _ { j }\tag{432}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Here: $\rho _ { i }$ is the pair-wise historical correlation between the futures labeled by i and VXX; $C _ { i j }$ is the N × N sample covariance matrix for the N futures $( \sigma _ { i } ^ { 2 } = C _ { i i }$ is the historical variance for the futures labeled by i); and $\sigma _ { X }$ is the historical volatility of VXX. Some $w _ { i }$ may turn out to be negative. This is not necessarily an issue, but one may wish to impose the bounds $w _ { i } \geq 0$ . Further, one may wish the strategy to be dollar-neutral, which would amount to imposing the constraint

$$
\sum _ { i = 1 } ^ { N } w _ { i } = 1\tag{433}
$$

which the optimal hedge ratios (432) generally do not satisfy. Also, instead of minimizing the tracking error, one may wish to minimize the variance of the entire portfolio. And so on. The portfolio can be rebalanced monthly or more frequently.

## 7.4 Strategy: Volatility risk premium

Empirical evidence indicates that implied volatility tends to be higher than realized volatility most of the time, which is known as the “volatility risk premium”.133 Simply put, most of the time options are priced higher than the prices one would expect based on realized volatility, so the idea is to sell volatility. E.g., the trader can sell straddles based on S&P 500 options. As a possible proxy for volatility risk premium, the trader can, e.g., use the difference between VIX at the beginning of the current month and the realized volatility (in %, as VIX is quoted in %) of S&P 500 daily returns since the beginning of the current month. If the spread is positive, the trader sells the straddle. If the volatility spikes (which usually happens if the market sells of), the strategy will lose money. It is profitable in sideways markets.134

## 7.4.1 Strategy: Volatility risk premium with Gamma hedging

The ATM straddles in the above strategy are Delta-neutral.135 So, this is a “Vega play”, i.e., the trader is shorting Vega. If the underlying (S&P 500) moves, the short straddle is no longer Delta-neutral: if the underlying goes up (down), Delta becomes negative (positive). So a variation of this strategy is to use Gamma hedging to keep the strategy close to Delta-neutral, which is achieved by buying (selling) the underlying if it moves up (down). Then this becomes a “Theta play”, i.e., the

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

strategy now aims to capitalize on the Theta-decay of the value of the sold options. So, the price of this is the cost of the Gamma hedging, which reduces the P&L. As the underlying moves more and more away from the strike of the sold put and call options, the Gamma hedge becomes more and more expensive and eventually will exceed the collected option premia, at which point the strategy starts losing money.

## 7.5 Strategy: Volatility skew – long risk reversal

OTM put options with the underlying at $S _ { 0 } = K + \kappa$ tend to be priced higher than OTM call options with the underlying at $S _ { 0 } = K - \kappa$ (here K is the strike price, and $\kappa > 0$ is the distance from the strike). I.e., with all else being equal, the implied volatility for puts is higher than for calls.136 The long risk reversal strategy (see Subsection 2.12), where the trader buys an OTM call option and sells an OTM put option, captures this skew. However, this is a directional strategy – it loses money if the price of the underlying drops below $K _ { p u t } - C$ , where $K _ { p u t }$ is the strike price of the put, and $C > 0$ is the premium of the put minus the premium of the call.

## 7.6 Strategy: Volatility trading with variance swaps

One issue with trading volatility using options is the need to (almost continuously) Delta-hedge the position to avoid directional exposure,137 which practically can be both cumbersome and costly. To avoid the need for Delta-hedging, one can make volatility bets using variance swaps. A variance swap is a derivative contract whose payoff $P ( T )$ at maturity T is proportional to the difference between the realized variance v(T ) of the underlying and the preset variance strike $K ^ { \prime }$ :

$$
P ( T ) = N \times ( v ( T ) - K )\tag{434}
$$

$$
v ( T ) = \frac { F } { T } \sum _ { t = 1 } ^ { T } R ^ { 2 } ( t )\tag{435}
$$

$$
R ( t ) = \ln \left[ \frac { S ( t ) } { S ( t - 1 ) } \right]\tag{436}
$$

Here: $t = 0 , 1 , \dots , T$ labels sample points (e.g., trading days); $S ( t )$ is the price of the underlying at time $t ; R ( t )$ is the log-return from t − 1 to t; F is the annualization factor (thus, if t labels trading days, then $F = 2 5 2 )$ ; and N is the “variance notional”, which is preset. Note that in Eq. (435) the mean of R(t) over the period $t = 1$ to $t = T$ is not subtracted, hence T in the denominator.138 Long (short) variance swap

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

is a bet that the future realized volatility will be higher (lower) than the current implied volatility. Long (short) variance swaps can therefore be used instead of, e.g., long (short) straddles to go long (short) volatility. For instance, the dispersion strategy of Subsection 6.3 can be executed by selling a variance swap on an index and buying variance swaps on the index constituents (cf. selling and buying straddles).139

## 8 Foreign Exchange (FX)

## 8.1 Strategy: Moving averages with HP filter

In Subsection 3.12 we discussed a trading strategy for stocks wherein the trading signal is based on 2 intersecting (shorter and longer) moving averages. A similar approach can be applied to FX as well. However, FX spot rate time series tend to be rather noisy, which can lead to false signals based on moving averages. To mitigate this, before computing the moving averages, the higher-frequency noise can first be filtered out, e.g., using the so-called Hodrick-Prescott (HP) filter.140 Then, the remaining lower-frequency trend component (as opposed to the raw spot rate) can be used to compute the moving averages and generate the trading signal (see, e.g., [Harris and Yilmaz, 2009]). The HP filter is given by:

$$
S ( t ) = S ^ { * } ( t ) + \nu ( t )\tag{437}
$$

$$
\begin{array} { l } { { g = \displaystyle \sum _ { t = 1 } ^ { T } \left[ S ( t ) - S ^ { * } ( t ) \right] ^ { 2 } + \lambda \sum _ { t = 2 } ^ { T - 1 } [ S ^ { * } ( t + 1 ) - 2 S ^ { * } ( t ) + S ^ { * } ( t - 1 ) ] ^ { 2 } } } \\ { { g \to \operatorname* { m i n } } } \end{array}\tag{438}
$$

(439)

Here: the objective function g is minimized w.r.t. the set of T values of $S ^ { * } ( t ) , t =$ $1 , \ldots , T ; S ( t )$ is the FX spot rate at time $t ; S ^ { * } ( t )$ is the lower-frequency $( ^ { \circ } \mathrm { r e g u l a r } ^ { \prime \prime } )$ component; $\nu ( t )$ is the higher-frequency $( \mathrm { { ' } i r r e g u l a r " } )$ component, which is treated as noise; the first term in Eq. (438) minimizes the noise, while the second term (based on the discretized second derivative of $S ^ { * } ( t ) )$ penalizes the variation in $S ^ { * } ( t )$ ; and λ is the smoothing parameter. There is no “fundamental” method to fix λ. Sometimes (but not always) it is set to $\lambda = 1 0 0 \times n ^ { 2 }$ , where n is the data frequency measured on

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

an annual basis (see, e.g., [Baxter and King, 1999] for more detail). So, for monthly data, which is what is usually used in this context, $n = 1 2$ . The estimation period usually spans several years (of monthly data). Once $S ^ { * } ( t )$ is determined, two moving averages $\mathrm { M A } ( T _ { 1 } )$ and $\mathrm { M A } ( T _ { 2 } ) , T _ { 1 } < T _ { 2 }$ , are calculated based on $S ^ { * } ( t )$ . Then, as before, $\mathrm { M A } ( T _ { 1 } ) > \mathrm { M A } ( T _ { 2 } )$ is a buy signal, and $\mathrm { M A } ( T _ { 1 } ) < \mathrm { M A } ( T _ { 2 } )$ is a sell signal.

## 8.2 Strategy: Carry trade

Pursuant to “Uncovered Interest Rate Parity” (UIRP), excess interest earned in one country compared with another country due to a differential between risk-free interest rates in these countries would be precisely offset by depreciation in the FX rate between their currencies:

$$
( 1 + r _ { d } ) = \frac { E _ { t } ( S ( t + T ) ) } { S ( t ) } \ : \left( 1 + r _ { f } \right)\tag{440}
$$

Here: $r _ { d }$ is the domestic interest rate; $r _ { f }$ is the foreign interest rate; both $r _ { d }$ and $r _ { f }$ are assumed to be constant over the compounding period $T ; S ( t )$ is the spot FX rate at time t, which is the worth of 1 unit of the foreign currency in units of the domestic currency; and $E _ { t } ( S ( t + T ) )$ is the future (at time $t + T )$ spot FX rate expected at time $t . ^ { 1 4 1 }$ UIRP does not always hold, giving rise to trading opportunities – which are not risk-free arbitrage opportunities (see below). Thus, UIRP implies that high interest rate currencies should depreciate w.r.t. low interest rate currencies, whereas empirically on average the opposite tends to transpire, i.e., such currencies tend to appreciate (somewhat).142 So, the basic carry strategy amounts to writing (i.e., selling) forwards on currencies that are at a forward premium, i.e., the forward FX rate $F ( t , T )$ exceeds the spot FX rate $S ( t )$ , and buying forwards on currencies that are at a forward discount, i.e., the forward FX rate $F ( t , T )$ is lower than the spot FX rate $S ( t ) . ^ { 1 4 3 }$ The forward FX rate is given by144

$$
F ( t , T ) = S ( t ) \ { \frac { 1 + r _ { d } } { 1 + r _ { f } } }\tag{441}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

As mentioned above, the carry strategy145 is not without risks: this trade can generate losses if the borrowed (lent) currency suddenly appreciates (depreciates) w.r.t. its counterpart, i.e., it is exposed to the FX rate risk. On the other hand, if we borrow the low interest rate currency with the maturity date T , invest the funds in the high interest rate currency, and hedge this position with a forward contract to exchange the high interest rate currency for the low interest rate currency at maturity T (so we can cover the loan), ignoring the transaction costs (and other subtleties such as taxes, etc.), this is a risk-free position and any gains therefrom would amount to risk-free arbitrage. Hence Eq. (441), which is a no-risk-free-arbitrage condition.146

## 8.2.1 Strategy: High-minus-low carry

The carry strategy discussed above can be applied to individual foreign currencies. It can also be applied cross-sectionally, to multiple foreign currencies. Let $s ( t ) =$ ln(S(t)) (log spot FX rate) and $f ( t , T ) = \ln ( F ( t , T ) )$ (log forward FX rate). The forward discount $D ( t , T )$ is defined as

$$
D ( t , T ) = s ( t ) - f ( t , T )\tag{442}
$$

Pursuant to CIRP, Eq. (441), we have

$$
D ( t , T ) = \ln \left( \frac { 1 + r _ { f } } { 1 + r _ { d } } \right) \approx r _ { f } - r _ { d }\tag{443}
$$

For a positive forward discount, we buy a forward (i.e., borrow the domestic currency and invest in the foreign currency), and the higher the forward discount, the more profitable the strategy. For a negative forward discount, we sell a forward (i.e., borrow the foreign currency and invest in the domestic currency), and the lower the forward discount, the more profitable the strategy. So, we can construct a cross-sectional trade (including a zero-cost, i.e., dollar-neutral trade – see, e.g., [Lustig, Roussanov and Verdelhan, 2011]) by buying forwards on currencies in some top quantile147 by forward discount and selling forwards on currencies in the corresponding bottom quantile. The forwards can, e.g., be one-month forwards.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 8.3 Strategy: Dollar carry trade

This strategy is based on the average cross-sectional forward discount $\overline { { \cal D } } ( t , T )$ (see, e.g., [Lustig, Roussanov and Verdelhan, 2014]) for a basket of N foreign currencies:

$$
\overline { { D } } ( t , T ) = \frac { 1 } { N } \sum _ { i = 1 } ^ { N } D _ { i } ( t , T )\tag{444}
$$

where $D _ { i } ( t , T )$ is the forward discount for the currency labeled by $i = 1 , \ldots , N$ . This strategy then goes long (short), with equal weights, all N foreign currency forwards when $\overline { { \cal D } } ( t , T )$ is positive (negative), where T can be 1, 2, 3, 6, 12 months. Empirical evidence suggests that this strategy relates to the state of the U.S. economy, to wit, when the U.S. economy is weak, the average forward discount tends to be positive.148

## 8.4 Strategy: Momentum & carry combo

This is a combination of the momentum strategy (Subsection $8 . 1 ) ^ { 1 4 9 }$ and the carry strategy (Subsection 8.2), or their variations. There is a variety of ways these strategies can be combined (including an equally weighted combo, or some ideas discussed in, e.g., Subsection 3.6 and Subsection 4.6). A simple combination is based on minimizing the variance of the combo strategy using the sample covariance matrix of historical returns $R _ { 1 } ( t _ { s } )$ and $R _ { 2 } ( t _ { s } )$ of the two strategies (see, $\mathrm { e . g . , }$ [Olszweski and Zhou, 2013]). Let (here Var and Cor are serial variance and correlation, respectively)

$$
\sigma _ { 1 } ^ { 2 } = \mathrm { V a r } ( R _ { 1 } ( t _ { s } ) )\tag{445}
$$

$$
\sigma _ { 2 } ^ { 2 } = \mathrm { V a r } ( R _ { 2 } ( t _ { s } ) )\tag{446}
$$

$$
\rho = \mathrm { C o r } ( R _ { 1 } ( t _ { s } ) , R _ { 2 } ( t _ { s } ) )\tag{447}
$$

Then minimizing the historical variance of the combined return $R ( t _ { s } )$ fixes the strategy weights $w _ { 1 }$ and $w _ { 2 }$ :

$$
R ( t _ { s } ) = w _ { 1 } \ R _ { 1 } ( t _ { s } ) + w _ { 2 } \ R _ { 2 } ( t _ { s } )\tag{448}
$$

$$
w _ { 1 } + w _ { 2 } = 1\tag{449}
$$

$$
\operatorname { V a r } ( R ( t _ { s } ) ) \to \operatorname* { m i n }\tag{450}
$$

$$
w _ { 1 } = \frac { \sigma _ { 2 } ^ { 2 } - \sigma _ { 1 } \sigma _ { 2 } \rho } { \sigma _ { 1 } ^ { 2 } + \sigma _ { 2 } ^ { 2 } - 2 \sigma _ { 1 } \sigma _ { 2 } \rho }\tag{451}
$$

$$
w _ { 2 } = \frac { \sigma _ { 1 } ^ { 2 } - \sigma _ { 1 } \sigma _ { 2 } \rho } { \sigma _ { 1 } ^ { 2 } + \sigma _ { 2 } ^ { 2 } - 2 \sigma _ { 1 } \sigma _ { 2 } \rho }\tag{452}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 8.5 Strategy: FX triangular arbitrage

This strategy is based on 3 currency pairs.150 Let these currencies be A, B and C. Then we have 2 chains: i) exchange A for B, exchange B for C, and exchange C for A; and ii) exchange A for C, exchange C for B, and exchange B for A. We will focus on the first chain as the second one is obtained by swapping B for C. Each currency pair has the bid and the ask; e.g., $B i d ( A  B )$ and $A s k ( B \to A )$ for the A-B pair. So, the rate at which A is exchanged into B is $B i d ( A  B )$ , while the rate at which B is exchanged into A is $1 / A s k ( B \to A )$ . Therefore, $B i d ( B \to A ) = 1 / A s k ( B \to A )$ and $A s k ( A \to B ) = 1 / B i d ( A \to B )$ . In the chain i) above, the trader starts with A and loops back to A with the overall exchange rate

$$
R ( A \to B \to C \to A ) = B i d ( A \to B ) \times B i d ( B \to C ) \times { \frac { 1 } { A s k ( C \to A ) } }\tag{453}
$$

If this quantity is greater than 1, then the trader makes a profit. Such opportunities are ephemeral, so fast market data and trade execution systems are critical here.151

## 9 Commodities

## 9.1 Strategy: Roll yields

When commodity futures are in backwardation (contango), i.e., when the term structure of futures prices is downward (upward) sloping, long (short) futures positions on average generate positive returns due to the roll yield. Roll yields come from rebalancing futures positions: when the current long (short) futures contract is about to expire, it is sold (covered) and another futures contract with longer expiration is bought (sold). Let

$$
\phi = P _ { 1 } / P _ { 2 }\tag{454}
$$

where $P _ { 1 }$ is the front-month futures price, and $P _ { 2 }$ is the second-month futures price. The ratio $\phi$ is a measure of backwardation $( \phi > 1 )$ and contango $( \phi < 1 )$ . A zerocost long-short portfolio can then be built based on $\phi , \mathrm { e . g . }$ , by buying commodity futures with higher values of $\phi$ and selling futures with lower values thereof.152

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 9.2 Strategy: Trading based on hedging pressure

This strategy is based on hedgers’ and speculators’ position data provided (weekly) by the U.S. Commodity Futures Trading Commission (CFTC) in the Commitments of Traders (COT) reports. For each commodity, the “hedging pressure” (HP), separately for hedgers and speculators, is calculated as the number of long contracts divided by the total number of contracts (long plus short). So, HP is between 0 and 1. High (low) hedgers’ HP is indicative of contango (backwardation), while high (low) speculators’ HP is indicative of backwardation (contango). A zero-cost portfolio can be constructed, e.g., as follows. First, the cross-section of commodities is divided into the upper half and the lower half by the speculators’ HP. Then, the upper half commodity futures are bought if they are in the bottom quintile by the hedgers’ HP, and the lower half commodity futures are sold if they are in the top quintile by the hedger’s HP. Typical formation and holding periods are 6 months.153

## 9.3 Strategy: Portfolio diversification with commodities

Commodity markets typically have a low correlation with equity markets, which can be used to improve performance characteristics of equity portfolios by combining equity and commodity investments. There are different ways to do this. A “passive approach” would amount to buying commodities with a preset portion of the available funds, holding them, and rebalancing the portfolio with some periodicity (e.g., monthly or annually). An “active approach” would amount to a tactical asset allocation approach via increasing/decreasing the exposure to commodities based on an increase/decrease in the Fed discount rate (empirically, commodity returns tend to be sizably correlated with the Fed monetary policy) or some other methodology.154

## 9.4 Strategy: Value

This strategy is similar to the value strategy for stocks (see Subsection 3.3). Value for commodities can be defined as, e.g., the ratio (see, e.g., [Asness, Moskowitz and

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Pedersen, 2013])

$$
v = P _ { 5 } / P _ { 0 }\tag{455}
$$

where $P _ { 5 }$ is the spot price 5 years ago,155 and $P _ { 0 }$ is the current spot price. Then one can build a zero-cost portfolio by, e.g., buying the commodities in the top tercile by value, and selling those in the bottom tercile. The portfolio is rebalanced monthly.

## 9.5 Strategy: Skewness premium

This strategy is based on the empirically observed negative correlation between the skewness of historical returns and future expected returns of the commodity futures. The skewness $S _ { i }$ is defined as $( i = 1 , \ldots , N$ labels different commodities):

$$
S _ { i } = \frac { 1 } { \sigma _ { i } ^ { 3 } T } \sum _ { s = 1 } ^ { T } \left[ R _ { i s } - \overline { { R } } _ { i } \right] ^ { 3 }\tag{456}
$$

$$
\overline { { R } } _ { i } = \frac { 1 } { T } \sum _ { s = 1 } ^ { T } R _ { i s }\tag{457}
$$

$$
\sigma _ { i } ^ { 2 } = \frac { 1 } { T - 1 } \sum _ { s = 1 } ^ { T } \left[ R _ { i s } - \overline { { R } } _ { i } \right] ^ { 2 }\tag{458}
$$

where $R _ { i s }$ are the time series of historical returns (with T observations in each time series). A zero-cost strategy can be built by, e.g., buying the commodity futures in the bottom quintile by skewness, and selling the futures in the top quintile.156

## 9.6 Strategy: Trading with pricing models

Commodity futures term structure is nontrivial. One way to model it is via stochastic processes. Let $S ( t )$ be the spot price, and let $X ( t ) \ = \ \ln ( S ( t ) )$ Then X(t) can be modeled using, e.g., a mean-reverting Brownian motion (i.e., the Ornstein-Uhlenbeck process [Uhlenbeck and Ornstein, 1930]):157

$$
d X ( t ) = \kappa \left[ a - X ( t ) \right] d t + \sigma ~ d W ( t )\tag{459}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Here the parameters κ (mean-reversion parameter), a (the long-run mean) and σ (log-volatility) are assumed to be constant; and W (t) is a Q-Brownian motion, where Q is a risk-free probability measure.158 The standard claim pricing argument (see, e.g., [Baxter and Rennie, 1996], [Hull, 2012], [Kakushadze, 2015a]) gives for the futures price F (t, T ) (which is the price at time t of the futures contract with the delivery date T )

$$
F ( t , T ) = E _ { t } ( S ( T ) )\tag{460}
$$

$$
\ln ( F ( t , T ) ) = E _ { t } ( X ( T ) ) + { \frac { 1 } { 2 } } V _ { t } ( X ( T ) )\tag{461}
$$

Here $E _ { t } ( \cdot )$ and $V _ { t } ( \cdot )$ are the conditional expectation and variance, respectively, at time t. This gives:

$$
\begin{array} { r c l } { \ln ( F ( t , T ) ) } & { = } & { \exp \left( - \kappa ( T - t ) \right) X ( t ) + a \left[ 1 - \exp \left( - \kappa ( T - t ) \right) \right] + } \\ & { + } & { \displaystyle \frac { \sigma ^ { 2 } } { 4 \kappa } \left[ 1 - \exp \left( - 2 \kappa ( T - t ) \right) \right] } \end{array}\tag{462}
$$

The parameters $\kappa , a , \sigma$ can be fitted using historical data (e.g., using nonlinear least squares). Then the current market price can be compared to the model price to identify the futures that are rich (sell signal) and cheap (buy signal) compared with the model prediction. Here two cautionary remarks are in order. First, the model fit could work in-sample but have no predictive power out-of-sample, so the forecasting power needs to be ascertained (see, e.g., [Paschke and Prokopczuk, 2012]). Second, a priori we could write down any reasonable term structure model with desirable qualitative properties (e.g., mean-reversion) and fit the parameters using historical data without any reference to an underlying stochastic dynamics whatsoever, including using, e.g., “black-box” machine learning techniques. So long as the model works out-of-sample, there is no magic bullet here and “fancy” does not equal “better”.

## 10 Futures

## 10.1 Strategy: Hedging risk with futures

Exposures to certain risks can be mitigated by hedging with futures. E.g., a grain trader who at time t anticipates that he or she will need to buy (sell) X tons of soy at a later time T can hedge the risk of soy prices increasing (decreasing) between t and T by buying (selling) at time t a futures contract with the delivery date T for the desired amount of soy. This simple strategy can have tweaks and variations.159

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 10.1.1 Strategy: Cross-hedging

Sometimes a futures contract for the asset to be hedged may not be available. In such cases, the trader may be able to hedge using a futures contract for another asset with similar characteristics.160 At maturity $T _ { \ast }$ the payoff of the cross-hedged position established at time t (assuming the short futures position with the unit hedge ratio) is given by:

$$
\begin{array} { l } { { S ( T ) - F ( T , T ) + F ( t , T ) = } } \\ { { \ } [ S _ { * } ( T ) - F ( T , T ) ] + [ S ( T ) - S _ { * } ( T ) ] + F ( t , T ) } \end{array}\tag{463}
$$

Here: the subscript ∗ indicates that the underlying asset of the futures contract is different from the hedged asset; $S ( t )$ is the spot price; $F ( t , T )$ is the futures price; the first term on the r.h.s. represents the basis risk stemming from the difference at delivery between the futures and the spot prices; and the second term represents the difference twixt the two underlying prices. In practice, the optimal hedge ratio may not be 1 and can be estimated via, e.g., a serial regression or some other method.161

## 10.1.2 Strategy: Interest rate risk hedging

Fixed-income assets are sensitive to interest rate variations (see Section 5) and futures contracts can be used to hedge the interest rate risk. A long (short) hedge position amounts to buying (selling) interest rate futures in order to hedge against an increase (decrease) in the price of the underlying asset, i.e., a decrease (increase) in the interest rates.162 The corresponding P&L $( P _ { L } ( t , T )$ for the long hedge and $P _ { S } ( t , T )$ for the short hedge, assuming the position is established at t = 0 with the unit hedge ratio and the maturity is $T )$ is given by:

$$
P _ { L } ( t , T ) = B ( 0 , T ) - B ( t , T )\tag{464}
$$

$$
P _ { S } ( t , T ) = B ( t , T ) - B ( 0 , T )\tag{465}
$$

$$
B ( t , T ) = S ( t ) - F ( t , T )\tag{466}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

where $B ( t , T )$ is the futures basis. In practice, the hedge ratio may not be 1. If a hedge is against a bond in the futures delivery basket,163 then the conversion factor model164 is commonly used to compute the hedge ratio $h _ { C }$

$$
h _ { C } = C \ { \frac { M _ { B } } { M _ { F } } } \tag{467}
$$

where $M _ { B }$ is the nominal value of the bond, $M _ { F }$ is the nominal value of the futures, and C is the conversion factor. Unlike the conversion factor model, the modified duration hedge ratio $h _ { D }$ can be used for both deliverable and non-deliverable bonds:

$$
h _ { D } = \beta \ \frac { D _ { B } } { D _ { F } }\tag{468}
$$

where $D _ { B }$ is the dollar duration165 of the bond, $D _ { F }$ is the dollar duration of the futures, and $\beta$ (which is often set to 1) is the change in the bond yield relative to the change in the futures yield, both taken for a given change in the risk-free rate.166

## 10.2 Strategy: Calendar spread

A bull (bear) futures spread amounts to buying (selling) a near-month futures and selling (buying) a deferred-month futures. This reduces exposure to the overall market volatility and allows to focus more on the fundamentals. Thus, for commodity futures, for the most part, near-month contracts react to supply and demand more than deferred-month contracts. Therefore, if the trader expects low (high) supply and high (low) demand, then the trader can make a bet with a bull (bear) spread.167

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 10.3 Strategy: Contrarian trading (mean-reversion)

This strategy is similar to the mean-reversion strategy discussed in Subsection 3.9. Within a given universe of futures labeled by $i = 1 , \ldots , N$ , the “market index” return is calculated as an equally weighted average:

$$
R _ { m } = \frac { 1 } { N } \sum _ { i = 1 } ^ { N } R _ { i }\tag{469}
$$

where $R _ { i }$ are the individual futures returns (typically over the last one week). The capital allocation weights $w _ { i }$ then are given by

$$
w _ { i } = - \gamma \left[ R _ { i } - R _ { m } \right]\tag{470}
$$

where $\gamma > 0$ is fixed via the normalization condition

$$
\sum _ { i = 1 } ^ { N } \left| w _ { i } \right| = 1\tag{471}
$$

Note that the strategy is automatically dollar-neutral. It amounts to buying losers and selling winners w.r.t. the market index (see, e.g., [Wang and Yu, 2004]).168 As in the case of equities, the simple weighting scheme given by Eq. (470) is prone to overinvesting in volatile futures, which can be mitigated by suppressing $w _ { i }$ by $1 / \sigma _ { i }$ or $1 / \sigma _ { i } ^ { 2 }$ , where $\sigma _ { i }$ are the historical volatilities. The portfolio is rebalanced weekly.

## 10.3.1 Strategy: Contrarian trading – market activity

Bells and whistles can be added to the above “basic” mean-reversion strategy by incorporating volume and open interest filters. Let $V _ { i }$ be the total volume for the futures labeled by i over the last week (i.e., the sum of daily volumes over the last week), and $V _ { i } ^ { \prime }$ be the total volume over the prior week. Let $U _ { i }$ and $U _ { i } ^ { \prime }$ be the analogous quantities for the open interest. Let

$$
v _ { i } = \ln ( V _ { i } / V _ { i } ^ { \prime } )
$$

$$
u _ { i } = \ln ( U _ { i } / U _ { i } ^ { \prime } )\tag{472}
$$

(473)

Then the strategy can be built, e.g., by taking the upper half of the futures by the volume factor $v _ { i } ,$ taking the lower half of these futures by the open interest factor $u _ { i } .$ , and applying the strategy defined by Eq. (470) to this subset of the futures.169

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 10.4 Strategy: Trend following (momentum)

Various momentum strategies for futures can be constructed similarly to those for stocks. Here is a simple example (see, e.g., [Balta and Kosowski, 2013], [Moskowitz, Ooi and Pedersen, 2012]).170 Let $R _ { i }$ be the returns for the futures labeled by $i =$ $1 , \ldots , N$ over the past period $T$ (which can be measured in, e.g., days, weeks, or months). Then the weights $w _ { i }$ of the trading portfolio are given by

$$
w _ { i } = \gamma \ { \frac { \eta _ { i } } { \sigma _ { i } } }\tag{474}
$$

$$
\eta _ { i } = \mathrm { s i g n } ( R _ { i } )\tag{475}
$$

where $\sigma _ { i }$ are the historical volatilities (computed over the period $T$ or some other period), and $\gamma > 0$ is fixed via the normalization condition

$$
\sum _ { i = 1 } ^ { N } \left| w _ { i } \right| = 1\tag{476}
$$

Note that this strategy is equivalent to the optimization strategy (see Subsection 3.18, Eq. (350)) with a diagonal covariance matrix $C _ { i j } = \sigma _ { i } ^ { 2 } \ \delta _ { i j }$ (i.e., the correlations between different futures are ignored) and the expected returns $E _ { i } = \eta _ { i } \sigma _ { i }$ . This is to be contrasted with the expected returns based on the cumulative returns (Eq. (267)), which in this case equal $R _ { i }$ . One issue with using $E _ { i } = \eta _ { i } \sigma _ { i }$ as opposed to $E _ { i } = R _ { i }$ is that, for small $\left| R _ { i } \right|$ (e.g., compared with $\sigma _ { i } )$ , $\eta _ { i }$ can flip even though the change in $R _ { i }$ is small. This results in an undesirable instability in the strategy. There are ways to mitigate this, e.g., by smoothing via $\eta _ { i } = \operatorname { t a n h } ( R _ { i } / \kappa )$ , where κ is some parameter, e.g., the cross-sectional standard deviation of $R _ { i }$ (see, e.g., [Kakushadze, 2015b]). Alternatively, one may simply take $E _ { i } = R _ { i }$ (and further use a non-diagonal $C _ { i j } )$ . Also, note that the weights defined by Eq. (474) are not dollar-neutral. This can be rectified by demeaning them:

$$
w _ { i } = \gamma \left[ \frac { \eta _ { i } } { \sigma _ { i } } - \frac { 1 } { N } \sum _ { j = 1 } ^ { N } \frac { \eta _ { j } } { \sigma _ { j } } \right]\tag{477}
$$

One shortcoming of this is that now some futures with $\eta _ { i } > 0$ may be sold, and some futures with $\eta _ { i } < 0$ may be bought. To avoid this, if the number $N _ { + } = | H _ { + } |$ of the

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

futures with $\eta _ { i } > 0$ is not dramatically different from the number $N _ { - } = | H _ { - } |$ of the futures with $\eta _ { i } < 0$ (here $H _ { \pm } = \{ i | \pm \eta _ { i } > 0 \} )$ ), we can take the weights to be

$$
w _ { i } = \gamma _ { + } \ \frac { \eta _ { i } } { \sigma _ { i } } , \quad i \in H _ { + }\tag{478}
$$

$$
w _ { i } = \gamma _ { - } \ \frac { \eta _ { i } } { \sigma _ { i } } , \quad i \in H _ { - }\tag{479}
$$

${ \mathrm { S o } } ,$ now we have two parameters $\gamma _ { \pm }$ , which can be fixed to satisfy Eq. (476) and the dollar-neutrality condition

$$
\sum _ { i = 1 } ^ { N } w _ { i } = 0\tag{480}
$$

However, if most $\eta _ { i }$ are positive (negative), i.e., we have skewed returns, then long (short) positions will be well-diversified, while the short (long) positions will not be. This can happen, e.g., if the broad market is rallying (selling off). Eq. (477) mitigates this to some extent. However, $\eta _ { i }$ can still be skewed in this case. A simple way to avoid this altogether is to use the demeaned returns ${ \widetilde { R } } _ { i }$ instead of $R _ { i } .$ where $\widetilde { R } _ { i } = R _ { i } - R _ { m } .$ and the “market index” return $R _ { m }$ is defined by Eq. (469).171 Then $\eta _ { i } = \mathrm { s i g n } ( \widetilde { R } _ { i } )$ are no longer skewed and dollar-neutrality can be achieved as above.172

## 11 Structured Assets

## 11.1 Generalities: Collateralized Debt Obligations (CDOs)

A CDO is an asset-backed security (ABS) consisting of a basket of assets such as bonds, credit default swaps, etc. It is divided into multiple tranches, which consist of assets with different credit ratings and interest rates. Each tranche has an attachment point a and a detachment point d. E.g., a 3-8% tranche (for which $a \ = \ 3 \%$ and $d \ : = \ : 8 \% )$ means that it begins to lose value when the underlying portfolio loss exceeds 3%; and when the underlying portfolio loss exceeds 8%, the tranche value is completely wiped out.173 A buyer (long position) of a CDO tranche is a protection seller: in return for receiving periodic premium payments, in the

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

event of a default, the buyer has the obligation to cover the default up to the size of the tranche. A seller (short position) of a CDO tranche is a protection buyer: in return for making periodic premium payments, the seller receives a payment in the event of a default. Synthetic CDOs are “synthesized” through credit derivatives such as CDS (credit default swaps – see Subsection 5.14) on a pool of reference entities (e.g., bonds, loans, names of companies or countries). Reference pools for exchange-traded single-tranche CDOs are CDS indexes such as CDX and iTraxx.174

Let $t _ { i } , i = 1 , \ldots , n$ , denote the times at which the periodic premium payments are made.175 Let $H ( t )$ denote the set of possible defaults $\ell _ { \alpha } , \alpha = 1 , \ldots , K$ , that can occur by time $t ,$ and let $p _ { \alpha } ( t )$ denote the corresponding probabilities (which are model-dependent). Here $\ell _ { \alpha }$ are the dollar amounts of the defaults.176 The expected loss $L ( t )$ can be computed as

$$
L ( t ) = \sum _ { \alpha = 1 } ^ { K } p _ { \alpha } ( t ) \operatorname* { m a x } ( \operatorname* { m i n } ( \ell _ { \alpha } , L _ { d } ) - L _ { a } , 0 )\tag{481}
$$

where $L _ { a } = a ~ M _ { C D O } , L _ { d } = d ~ M _ { C D O }$ , and $M _ { C D O }$ is the CDO notional in dollars.177 From the long tranche investor’s perspective, the mark-to-market (MTM) value of the tranche, call it $\mathcal { M } .$ , is given by

$$
M = P - C\tag{482}
$$

$$
P = S \sum _ { i = 1 } ^ { n } D _ { i } \Delta _ { i } [ M _ { t r } - L ( t _ { i } ) ]\tag{483}
$$

$$
C = \sum _ { i = 1 } ^ { n } D _ { i } \left[ L ( t _ { i } ) - L ( t _ { i - 1 } ) \right]\tag{484}
$$

Here: P is the premium leg; C is the contingent (default) leg; S is the spread; $\Delta _ { i } \ : = \ : t _ { i } - t _ { i - 1 } ; \ : D _ { i }$ is the risk-free discount factor for the payment date $t _ { i } ;$ and

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

$M _ { t r } = L _ { d } - L _ { a }$ is the tranche notional. (Also, t is measured in years, $t _ { 0 }$ is the initial time, and $L ( t _ { 0 } ) = 0 )$ . Setting the MTM $\mathcal { M } = 0$ fixes the value of the spread $S = S _ { * }$

We can further define the “risky duration” D of the tranche as the first derivative of the MTM w.r.t. the spread:

$$
\mathcal M ( S ) = ( S - S _ { * } ) \sum _ { i = 1 } ^ { n } D _ { i } \ \Delta _ { i } \left[ M _ { t r } - L ( t _ { i } ) \right]\tag{485}
$$

$$
\mathcal { D } = \partial \mathcal { M } / \partial S = \sum _ { i = 1 } ^ { n } D _ { i } \ : \Delta _ { i } \left[ M _ { t r } - L ( t _ { i } ) \right]\tag{486}
$$

The risky duration $\mathcal { D } _ { i x }$ can also be defined in a similar fashion for a CDS index.

## 11.2 Strategy: Carry, equity tranche – index hedging

This strategy amounts to buying the equity (lowest quality) tranche and Deltahedging it by selling the index. The Delta (i.e., the hedge ratio) is given by178

$$
\Delta _ { i x } = \frac { \mathcal { D } } { \mathcal { D } _ { i x } }\tag{487}
$$

The premiums received from the equity tranche are higher than the premiums paid on the short index position. The risk is the exposure to equity tranche credit events.

## 11.3 Strategy: Carry, senior/mezzanine – index hedging

This strategy amounts to selling a high quality tranche (e.g., senior/mezzanine) and Delta-hedging the position by buying the index.179 The Delta is given by Eq. (487).

## 11.4 Strategy: Carry – tranche hedging

This strategy amounts to buying a low quality tranche and Delta-hedging the position by selling a high quality tranche. The hedge ratio is given by:

$$
\Delta _ { h i g h } = \frac { \mathcal { D } _ { l o w } } { \mathcal { D } _ { h i g h } }\tag{488}
$$

Here $\mathcal { D } _ { l o w }$ and $\mathcal { D } _ { h i g h }$ are the risky durations of the low and high quality tranches.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 11.5 Strategy: Carry – CDS hedging

This strategy amounts to buying a low quality tranche and Delta-hedging the position by selling a single-name CDS with lower premium payments than the long tranche (instead of the index or a higher quality tranche). The hedge ratio is given by Eq. (487) with $\mathcal { D } _ { i x }$ replaced by the risky duration $\mathcal { D } _ { C D S }$ of the CDS:

$$
\Delta _ { C D S } = \frac { \mathcal { D } } { \mathcal { D } _ { C D S } }\tag{489}
$$

## 11.6 Strategy: CDOs – curve trades

As in the case of bonds (see Subsection 5.13), a flattener (steepener) curve trade involves a simultaneous sale (purchase) of a short-term tranche and a purchase (sale) of a long-term tranche. Put differently, with a flattener (steepener), the trader is buying (selling) short-term protection and selling (buying) long-term protection, i.e., the trader expects the spread curve to flatten (steepen), whereby the spread between the long-term and short-term tranches decreases (increases). The carry of the curve trade over the period from time t to time $t + \Delta t$ can be defined as follows

$$
C ( t , t + \Delta t ) = ( M _ { l o n g } \ S _ { l o n g } - M _ { s h o r t } \ S _ { s h o r t } ) \Delta t\tag{490}
$$

where $M _ { l o n g }$ and $M _ { s h o r t }$ are the long and short tranche notionals, and $\boldsymbol { S _ { l o n g } }$ and $S _ { s h o r t }$ are the corresponding spreads. The trade can be structured to be dollar-neutral $( \mathrm { i . e . , }$ notional-neutral, $M _ { l o n g } = M _ { s h o r t } )$ ,180 risky-duration-neutral $( \mathcal { D } _ { l o n g } = \mathcal { D } _ { s h o r t } ,$ see Eq. (486)), carry-neutral $( M _ { l o n g } S _ { l o n g } = M _ { s h o r t } S _ { s h o r t } )$ , etc.181 The P&L of the strategy is given by $( \mathcal { M } _ { l o n g }$ and $\mathcal { M } _ { s h o r t }$ are the long and short tranche MTMs, see Eq. (485)):

$$
\mathrm { P \& L } = \mathcal { M } _ { l o n g } - \mathcal { M } _ { s h o r t }\tag{491}
$$

## 11.7 Strategy: Mortgage-backed security (MBS) trading

This strategy amounts to buying MBS passthroughs182 and duration-hedging their interest rate exposure with interest rate swaps. Thus, the main risk of a passthrough MBS is the prepayment risk, whereby homeowners have an option to prepay their mortgages. Homeowners refinance their mortgages as the interest rates drop, which results in negative convexity in the MBS price as a function of the interest rates

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

(e.g., the 5-year swap rate). The hedge ratios are model-dependent and a variety of prepayment models can be constructed. Alternatively one can follow a nonparametric approach whereby using historical data one estimates the first derivative of the passthrough MBS price P w.r.t. the 5-year swap rate R with the constraint that P is a non-increasing function of R (see, e.g., [Duarte, Longstaff and Yu, 2006]),183 employing, e.g., a constrained regression (see, e.g., [A¨ıt-Sahalia and Duarte, 2003]).

## 12 Convertibles

## 12.1 Strategy: Convertible arbitrage

A convertible bond is a hybrid security with an embedded option to convert the bond (a fixed-income instrument) to a preset number (knows as the conversion ratio) of the issuer’s stock (an equity instrument) when, e.g., the stock price reaches a preset level (known as the conversion price). Empirically, convertibles at the issuance tend to be undervalued relative to their “fair” value.184 This gives rise to arbitrage opportunities. A convertible arbitrage strategy amounts to buying a convertible bond and simultaneously shorting h units of the underlying stock, where the hedge ratio is given by

$$
h = \Delta \times C\tag{492}
$$

$$
\Delta = \partial V / \partial S\tag{493}
$$

Here: C is the conversion ratio; V is the value of the conversion option (which is model-dependent); S is the underlying stock price; and $\Delta$ is the (model-dependent)

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Delta of the conversion option.185 Typically, the position is held for 6-12 months starting at the issuance date of the convertible and the hedge ratio is updated daily.

## 12.2 Strategy: Convertible option-adjusted spread

This strategy amounts to simultaneously buying and selling two different convertible bonds of the same issuer. The long position is in a bond with a higher optionadjusted spread (OAS), and the short position is in a bond with a lower OAS (see, e.g., [Calamos, 2003]). Then the trade is profitable if these two spreads converge.

The OAS can be calculated as follows (see, e.g., [Hull, 2012]).186 A straightforward (but not the only)187 way to compute the price $P _ { C }$ of the convertible bond is to assume that

$$
P _ { C } = P _ { B } + V\tag{494}
$$

where $P _ { B }$ is the price of the straight bond (without the embedded option), and V is the value of the conversion option, which is a call option. $P _ { B }$ is computed via the standard discounting of the future cash flows of the bond. On the other hand, V depends on the risk-free interest rate curve. At the initial iteration, V is computed (using a pricing model for the call option) assuming the zero-coupon government Treasury curve as the risk-free interest rate curve. This initial iteration $V ^ { ( 0 ) }$ may not coincide with $P _ { C } ^ { m k t } - P _ { B }$ , where $P _ { C } ^ { m k t }$ is the market price of the convertible bond. Then one iteratively (e.g., using the bisection method) parallel-shifts the input Treasury curve until V computed using the so-shifted curve is such that $V =$ $P _ { C } ^ { m k t } - P _ { B }$ . The curve parallel shift obtained via this iterative procedure is the OAS.

## 13 Tax Arbitrage

## 13.1 Strategy: Municipal bond tax arbitrage

This strategy is one of the most common and simple forms of tax arbitrage. It amounts to borrowing money and buying tax-exempt municipal bonds.188 The strat-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

egy return is given by

$$
R = r _ { l o n g } - r _ { s h o r t } ( 1 - \tau )\tag{495}
$$

Here: $r _ { l o n g }$ is the interest rate of the bought municipal bonds, $r _ { s h o r t }$ is the interest rate of the loan, and τ is the corporate tax rate. This strategy is attractive to companies in jurisdictions where tax rules allow them to buy tax-exempt municipal bonds and deduct interest expenses from their taxable income (a.k.a. “tax shield”).

## 13.2 Strategy: Cross-border tax arbitrage

The U.S. double-taxes corporate income. The corporate income is first taxed at the corporate level. Then, it is taxed again when dividends are received by the shareholders. In some other countries the taxation systems are designed to relieve the tax burden, e.g., by not taxing dividends (as, e.g., in Singapore), or by giving shareholders tax credits attached to dividend payments (as, e.g., in Australia). In the case where this “dividend imputation” corporate tax system gives the full tax credit to shareholders, it can be schematically described as follows (see, e.g., [McDonald, 2001]):189

$$
{ \left\{ \begin{array} { l l } { { \mathrm { C o r p o r a t e ~ t a x ~ r a t e = } } \tau _ { c } } \\ { { \mathrm { C a s h ~ d i v i d e n d ~ p a i d } } = D } \\ { { \mathrm { D i v i d e n d ~ t a x ~ c r e d i t } } = C = D \ { \frac { \tau _ { c } } { 1 - \tau _ { c } } } } \\ { { \mathrm { T a x a b l e ~ i n c o m e } } = I _ { t } = D + C = { \frac { D } { 1 - \tau _ { c } } } } \\ { { \mathrm { P e r s o n a l ~ t a x ~ r a t e } } = \tau _ { p } } \\ { { \mathrm { P e r s o n a l ~ i n c o m e } } \ t { \mathrm { a x } } = T = I _ { t } \ \tau _ { p } } \\ { { \mathrm { D i v i d e n d ~ i n c o m e } } \ { \mathrm { a f t e r ~ c r e d i t ~ a n d ~ t a x } } = I = D + C - T = D \ { \frac { 1 - \tau _ { p } } { 1 - \tau _ { c } } } } \end{array} \right. }\tag{496}
$$

So, if the corporate income is P and the corporation pays all its income after taxes as dividends, then $D = P \left( 1 - \tau _ { c } \right)$ and $I = P \left( 1 - \tau _ { p } \right)$ ), so there is no double-taxation.190

While in countries with imputation systems domestic investors enjoy tax credits, generally foreign investors do not. If there were no tax credits, the price drop between cum-dividend and ex-dividend191 is expected to reflect the dividend. In the presence of tax credits, the drop is expected to be higher: if it fully reflects the tax credit, then it is $D \left( 1 + \kappa \right)$ , where κ is the tax credit rate. (In the above nomenclature, $1 + \kappa = 1 / ( 1 + \tau _ { c } ) . )$ So, a foreign investor is effectively penalized for

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

holding the stock. To avoid this, the foreign investor can sell the stock cum-dividend and buy it back ex-dividend.192 Alternatively, the foreign investor can loan the stock to a domestic investor cum-dividend and receive the stock back ex-dividend along with (some preset portion of) the tax credit – assuming no restrictions on such crossborder tax arbitrage. A swap agreement would also achieve the same result.193

## 13.2.1 Strategy: Cross-border tax arbitrage with options

Absent a tax credit, there is a theoretical upper bound on the value of an American put option (see, e.g., [Hull, 2012]):

$$
V _ { p u t } ( K , T ) \le V _ { c a l l } ( K , T ) - S _ { 0 } + K + D\tag{497}
$$

Here: $V _ { p u t } ~ \left( V _ { c a l l } \right)$ is the price of the put (call) option at time $t \ = \ 0 ;$ K is the strike price; $S _ { 0 }$ is the stock price at $t = 0 ;$ ; T is the time to maturity; and D is the present value of the dividends during the life of the option. Put options are optimally exercised ex-dividend. Therefore, in the presence of a tax credit, it is expected that put prices should reflect the tax credit, i.e., they should be higher than in the absence of the tax credit (see, e.g., [McDonald, 2001]). So the foreign investor can sell the stock cum-dividend (at price S0) and write a deep ITM put option, whose value close to expiration approximately is (here κ is the tax credit rate defined above)

$$
V _ { p u t } ( K , T ) = K - \left[ S _ { 0 } - D \left( 1 + \kappa \right) \right]\tag{498}
$$

The P&L, once the put is exercised ex-dividend at the strike price K, is the same as with the stock loan/swap strategy discussed above:

$$
\mathrm { P } \& \mathrm { L } = S _ { 0 } + V _ { p u t } ( K , T ) - K = D \left( 1 + \kappa \right)\tag{499}
$$

## 14 Miscellaneous Assets

## 14.1 Strategy: Inflation hedging – inflation swaps

This strategy amounts to buying (selling) inflation swaps in order to exchange a fixed (floating) rate of inflation for a floating (fixed) rate. Inflation swaps conceptually are similar to interest rate swaps (see Subsection 5.1.4). A buyer (seller) of an inflation swap is long (short) the inflation and receives the floating (fixed) rate. The buyer has a positive return if the inflation exceeds the expected inflation (i.e., the swap

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

fixed rate, a.k.a. the “breakeven rate”). The fixed rate typically is calculated as the interest rate spread between the Treasury notes/bonds (as applicable) and Treasury Inflation-Protected Securities (TIPS) with the same maturity as that of the swap. The floating rate usually is based on an inflation index such as the Consumer Price Index (CPI). The most common type of inflation swap is the zero-coupon inflation swap (ZC), which has only one cash flow at maturity $T$ (measured in years). This cash flow is the difference between the fixed rate cash flow $C _ { f i x e d }$ and the floating rate cash flow $C _ { f l o a t i n g } .$ . These cash flows, per \$1 notational, are given by:

$$
C _ { f i x e d } = ( 1 + K ) ^ { T } - 1\tag{500}
$$

$$
C _ { f l o a t i n g } = I ( T ) / I ( 0 ) - 1\tag{501}
$$

Here: K is the fixed rate; and I(t) is the CPI value at time $t ~ ( t = 0$ is the time at which the swap contract is entered into). Another type of inflation swaps is the year-on-year inflation swap (YoY), which references annual inflation (as opposed to the cumulative inflation referenced by the zero-coupon swap). Thus, assuming for simplicity annual payments, we have (here $t = 1 , \dots , T$ is measured in years):194

$$
C _ { f i x e d } ( t ) = K\tag{502}
$$

$$
C _ { f l o a t i n g } ( t ) = I ( t ) / I ( t - 1 ) - 1\tag{503}
$$

## 14.2 Strategy: TIPS-Treasury arbitrage

This strategy is based on the empirical observation that Treasury bonds tend to be overvalued relative to TIPS195 almost all the time (see, e.g., [Campbell, Shiller and Viceira, 2009], [Driessen, Nijman and Simon, 2017], [Fleckenstein, 2012], [Haubrich,

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Pennacchi and Ritchken, 2012]). The strategy amounts to selling a Treasury bond (whose price is $P _ { T r e a s u r y }$ , fixed coupon rate is $r _ { T r e a s u r y } .$ , and maturity is T ) and offsetting this short position with a synthetic portfolio, which precisely replicates the Treasury bond coupon and principal payments, but costs less than the Treasury bond. This synthetic portfolio is constructed by buying TIPS (whose price is $P _ { T I P S }$ and maturity T is the same as that of the Treasury bond) with a fixed coupon rate r and n coupon payments at times $t _ { i } , i = 1 , \ldots , n$ (with $t _ { n } = T )$ , and simultaneously selling n zero-coupon inflation swaps with maturities $t _ { i } ,$ the fixed rate $K ,$ and the notionals $N _ { i } = r + \delta _ { t _ { i } , T }$ per \$1 of the TIPS principal. The cash flows (per \$1 notional) at $t = t _ { i }$ are given by (as above, I(t) is the CPI value at time $t ;$ also, time is measured in the units of the (typically, semiannual) compounding periods):

$$
C _ { T I P S } ( t _ { i } ) = N _ { i } \ I ( t _ { i } ) / I ( 0 )\tag{504}
$$

$$
C _ { s w a p } ( t _ { i } ) = N _ { i } \left[ ( 1 + K ) ^ { t _ { i } } - I ( t _ { i } ) / I ( 0 ) \right]\tag{505}
$$

$$
C _ { t o t a l } ( t _ { i } ) = C _ { s w a p } ( t _ { i } ) + C _ { T I P S } ( t _ { i } ) = N _ { i } ( 1 + K ) ^ { t _ { i } }\tag{506}
$$

$\mathrm { S o } ,$ the synthetic portfolio converts the indexed payments from TIPS into fixed payments with the effective coupon rates $r _ { e f f } ( t _ { i } ) = r ( 1 + K ) ^ { t _ { i } }$ These synthetic coupon payments almost replicate the Treasury bond coupons rT reasury. The exact matching involves small long or short positions in STRIPS196, which are given by (see, e.g., [Fleckenstein, Longstaff and Lustig, 2013] for details)

$$
S ( t _ { i } ) = D ( t _ { i } ) \left\{ \left[ r _ { T r e a s u r y } - r _ { e f f } ( t _ { i } ) \right] + \delta _ { t _ { i } , T } \left[ 1 - ( 1 + K ) ^ { t _ { i } } \right] \right\}\tag{507}
$$

where $D ( \tau )$ is the value of the STRIPS with maturity τ at time $t = 0 \mathrm { ~ } ( \mathrm { i . e . , ~ } D ( \tau )$ is a discount factor). In Eq. (507) the second term in the curly brackets (which is proportional to $\delta _ { t _ { i } , T }$ and is nonzero only for $i = n ,$ , i.e., at maturity T ) is included as we must also match the principals at maturity. Note that the STRIPS positions are established at $t = 0$ . The net cash flow $C ( 0 )$ at $t = 0$ is given by (note that the net cash flows at $t > 0$ are all null by replication)

$$
C ( 0 ) = P _ { T r e a s u r y } - P _ { T I P S } - \sum _ { i = 1 } ^ { n } S ( t _ { i } )\tag{508}
$$

Empirically C(0) tends to be positive (even after transaction costs). Hence arbitrage.

## 14.3 Strategy: Weather risk – demand hedging

Various businesses and sectors of the economy can be affected by weather conditions, both directly and indirectly. Weather risk is hedged using weather derivatives. There are no “tradable” weather indexes, so various synthetic indexes have been created.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

The most common ones are based on temperature. The cooling-degree-days (CDD) and heating-degree-days (HDD) measure extreme high temperatures and extreme low temperatures, respectively:197

$$
I _ { C D D } = \sum _ { i = 1 } ^ { n } \operatorname* { m a x } ( 0 , T _ { i } - T _ { b a s e } )\tag{509}
$$

$$
I _ { H D D } = \sum _ { i = 1 } ^ { n } \operatorname* { m a x } ( 0 , T _ { b a s e } - T _ { i } )\tag{510}
$$

$$
T _ { i } = \frac { T _ { i } ^ { m i n } + T _ { i } ^ { m a x } } { 2 }\tag{511}
$$

Here: $i = 1 , \ldots , n$ labels days; n is the life of the contract (a week, a month or a season) measured in days; $T _ { i } ^ { m i n }$ and $T _ { i } ^ { m a x }$ are the minimum and maximum temperatures recorded on the day labeled by $i ;$ and $T _ { b a s e } = 6 5 ^ { \circ } \mathrm { F }$ . Then, the demand risk for heating days can, e.g., be hedged by a short futures position or a long put option position with the hedge ratios given by (here (Cov) Var is serial (co)variance):

$$
h _ { f u t u r e s } ^ { H D D } = \mathrm { C o v } ( q _ { w } , I _ { H D D } ) / \mathrm { V a r } ( I _ { H D D } )\tag{512}
$$

$$
h _ { p u t } ^ { H D D } = - \mathrm { C o v } \left( q _ { w } , \operatorname* { m a x } ( K - I _ { H D D } , 0 ) \right) / \mathrm { V a r } \left( \operatorname* { m a x } ( K - I _ { H D D } , 0 ) \right)\tag{513}
$$

Here: $q _ { w }$ is the portion of the demand affected by weather conditions (as there might be other, exogenous, non-weather-related components to the demand); and K is the strike price. Similarly, the demand risk for cooling days can, e.g., be hedged by a long futures position or a long call option position with the hedge ratios given by:

$$
h _ { f u t u r e s } ^ { C D D } = \mathrm { C o v } ( q _ { w } , I _ { C D D } ) / \mathrm { V a r } ( I _ { C D D } )\tag{514}
$$

$$
h _ { c a l l } ^ { C D D } = \mathrm { C o v } ( q _ { w } , \operatorname* { m a x } ( I _ { C D D } - K , 0 ) ) / \mathrm { V a r } ( \operatorname* { m a x } ( I _ { C D D } - K , 0 ) )\tag{515}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 14.4 Strategy: Energy – spark spread

The spark spread is the difference between the wholesale price of electricity and the price of natural gas required to produce it.198 A spark spread can be built by, e.g., taking a short position in electricity futures and a long position in the corresponding number of fuel futures. Such positions are used by electricity producers to hedge against changes in the electricity price or in the cost of fuel, as well as by traders or speculators who want to make a bet on a power plant. The number of fuel futures is determined by the so-called heat rate H, which measures the efficiency with which the plant converts fuel into electricity:

$$
H = Q _ { F } / Q _ { E }\tag{516}
$$

Here: $Q _ { F }$ is the amount of fuel used to produce the amount of electricity $Q _ { E } ; ~ Q _ { F }$ is measured in MMBtu; Btu = British thermal unit, which is approximately 1,055 Joules; MBtu = 1,000 Btu; MMBtu = 1,000,000 Btu; $Q _ { E }$ is measured in Mwh = Megawatt hour; the heat rate H is measured in MMBtu/Mwh. The spark spread is measured in \$/Mwh. So, if the price of electricity is $P _ { E }$ (measured in \$/Mwh) and the price of fuel is $P _ { F }$ (measured in \$/MMBtu), then the spark spread is given by

$$
S = P _ { E } - H \ P _ { F }\tag{517}
$$

The hedge ratio for the futures is affected by the available futures contract sizes. Thus, an electricity futures contract is $F _ { E } = 7 3 6$ Mwh, and a gas futures contract is $F _ { F } = 1 0 , 0 0 0 ~ \mathrm { M M B t u } .$ So, the hedge ratio is given by

$$
h = H \ F _ { E } / F _ { F }\tag{518}
$$

which generally is not a whole number. Therefore, it is (approximately, within the desired precision) represented as a ratio $h \approx N _ { F } / N _ { E }$ with the lowest possible denominator $N _ { E } ,$ , where $N _ { F }$ and $N _ { E }$ are whole numbers. Then the hedge consists of buying $N _ { F }$ gas futures contracts for every $N _ { E }$ sold electricity futures contracts.

## 15 Distressed Assets

## 15.1 Strategy: Buying and holding distressed debt

Distressed securities are those whose issuers are undergoing financial/operational distress, default or bankruptcy. One definition of distressed debt is if the spread

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

between the yields of Treasury bonds and those of the issuer is greater than some preset number, e.g., 1,000 basis points (see, e.g., [Harner, 2008]). A common and simple distressed debt passive trading strategy amounts to buying debt of a distressed company at a steep discount,199 expecting (hoping) that the company will repay its debt. Typically, a distressed debt portfolio is diversified across industries, entities and debt seniority level. It is anticipated that only a small fraction of the held assets will have positive returns, but those that do, will provide high rates of return (see, e.g., [Greenhaus, 1991]). There are two broad categories of passive distressed debt strategies (see, e.g., [Altman and Hotchkiss, 2006]). First, using various models (see Subsection 15.3) one can attempt to predict whether a company will declare bankruptcy. Second, some strategies focus on assets of companies in default or bankruptcy, a successful reorganization being the driver of returns. Typically, positions are established at key dates, such as at the end of the default month or at the end of the bankruptcy-filing month, with the view of exploiting overreaction in the distressed debt market (see, e.g., [Eberhart and Sweeney, 1992], [Gilson, 1995]).

## 15.2 Strategy: Active distressed investing

This strategy amounts to buying distressed assets with the view (unlike the passive strategy discussed above) to acquire some degree of control of the management and direction of the company. When facing a distress situation, a company has various options in its reorganization process. It can file for bankruptcy protection under Chapter 11 of the U.S. Bankruptcy Code to reorganize. Or it can work directly with its creditors out of Court.200 Below are some scenarios for active investing.

## 15.2.1 Strategy: Planning a reorganization

An investor can submit a reorganization plan to Court with an objective to obtain participation in the management of the company, attempt to increase its value and generate profits. Plans by significant debt holders tend to be more competitive.

## 15.2.2 Strategy: Buying outstanding debt

This strategy amounts to buying outstanding debt of a distressed firm at a discount with the view that, after reorganization, part of this debt will be converted into the firm’s equity thereby giving the investor a certain level of control of the company.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 15.2.3 Strategy: Loan-to-own

This strategy amounts to financing (via secured loans) a distressed firm that is not bankrupt with the view that it i) overcomes the distress situation, avoids bankruptcy and increases its equity value, or ii) files for Chapter 11 protection and, upon reorganization, the secured loan is converted into the firm’s equity with control rights.

## 15.3 Strategy: Distress risk puzzle

Some studies suggest that companies more prone to bankruptcy offer higher returns, which is a form of a risk premium (see, e.g., [Chan and Chen, 1991], [Fama and French, 1992], [Fama and French, 1996], [Vassalou and Xing, 2004]). However, more recent studies suggest the opposite, i.e., that such companies do not outperform healthier ones, and that the latter actually offer higher returns. This is the so-called “distress risk puzzle” (see, e.g., [George and Hwang, 2010], [Godfrey and Brooks, 2015], [Griffin and Lemmon, 2002], [Ozdagli, 2010]). So, this strategy amounts to buying the safest companies and selling the riskiest ones. As a proxy, one can use the probability of bankruptcy $P _ { i } , i = 1 , \dots , N$ (N is the number of stocks), which can, e.g., be modeled via a logistic regression (see, e.g., [Campbell, Hilscher and Sziglayi, 2008]).201 A zero-cost portfolio can be constructed by, e.g., selling the stocks in the top decile by $P _ { i } ,$ and buying the stocks in the bottom decile. Typically, the portfolio is rebalanced monthly, but annual rebalancing is also possible (with similar returns).

## 15.3.1 Strategy: Distress risk puzzle – risk management

This strategy is a variation of the distress risk puzzle strategy in Subsection 15.3. Empirical studies suggest that zero-cost healthy-minus-distressed (HMD) strategies tend to have a high time-varying market beta, which turns significantly negative following market downturns (usually associated with increased volatility), which can cause large losses if the market bounces abruptly (see, e.g., [Garlappi and Yan, 2011], [O’Doherty, 2012], [Opp, 2017]). This is similar to what happens in other

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

factor-based strategies.202 To mitigate this, the strategy can be modified as follows (see, e.g., [Eisdorfer and Misirli, 2015]):

$$
\mathrm { H M D } _ { * } = \frac { \sigma _ { t a r g e t } } { \widehat { \sigma } } \ \mathrm { H M D }\tag{519}
$$

Here: HMD is for the standard HMD strategy in Subsection 15.3; $\sigma _ { t a r g e t }$ is the level of target volatility (typically, between 10% and 15%, depending on the trader preferences); and $\widehat { \sigma }$ is the estimated realized volatility over the prior year using daily data. So, 100% of the investment is allocated only if $\widehat { \sigma } = \sigma _ { t a r g e t }$ , and a lower amount is allocated when $\widehat { \sigma } > \sigma _ { t a r g e t }$ . When $\widehat { \sigma } < \sigma _ { t a r g e t : }$ b, the strategy could be leveraged.203

## 16 Real Estate

## 16.1 Generalities

Real estate, unlike most other financial assets, is tangible. It can be divided into two main groups: commercial (offices, shopping centers, etc.) and residential (houses, apartments, etc.) real estate. There are various ways to get exposure to real estate, e.g., via real estate investment trusts (REITs), which often trade on major exchanges and allow investors to take a liquid stake in real estate.204 There are several ways to measure a return from a real estate investment. A common and simple way is as follows:

$$
R ( t _ { 1 } , t _ { 2 } ) = \frac { P ( t _ { 2 } ) + C ( t _ { 1 } , t _ { 2 } ) } { P ( t _ { 1 } ) } - 1\tag{520}
$$

Here: $R ( t _ { 1 } , t _ { 2 } )$ is the return of the investment from the beginning of the holding period $t _ { 1 }$ to the end of the holding period $t _ { 2 } ; P ( t _ { 1 } )$ and $P ( t _ { 2 } )$ are the market values of the property at those times; $C ( t _ { 1 } , t _ { 2 } )$ is the cash flows received, net of costs.205

## 16.2 Strategy: Mixed-asset diversification with real estate

Real estate assets are attractive as a tool for diversification. Empirical studies suggest that their correlation with traditional assets, such as bonds and stocks, is low and remains such even through extreme market events (e.g., financial crises),

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

when the correlations between traditional assets tend to increase. In addition, the correlation tends to be lower at longer time horizons, so long-term investors may improve their portfolio performance in terms of risk-adjusted returns by including real estate assets (see, e.g., [Feldman, 2003], [Geltner et al, 2006], [Seiler, Webb and Myer, 1999], [Webb, Curcio and Rubens, 1988]). So, a simple strategy amounts to buying and holding real estate assets within a traditional portfolio containing, e.g., bonds, equities, etc. The optimal allocation varies depending on investor preferences (in terms of risk and return) and the horizon (see, e.g., [Geltner, Rodriguez and O’Connor, 1995], [Lee and Stevenson, 2005], [Mueller and Mueller, 2003], [Rehring, 2012]), and techniques such as mean-variance optimization or vector autoregressive model (VAR)206 can be used to calculate the optimal allocation conditional on the time horizon and desired performance characteristics (see, e.g., [Fugazza, Guidolin and Nicodano, 2007], [Hoevenaars et al, 2008], [MacKinnon and Al Zaman, 2009]).

## 16.3 Strategy: Intra-asset diversification within real estate

This strategy amounts to diversifying real estate holdings (which can be part of a larger portfolio as in Subsection 16.2). Real estate assets can be diversified by geographic area, type of property, size, proximity to a metropolitan area, economic region, etc. (see, e.g., [Eichholtz et al, 1995], [Hartzell, Hekman and Miles, 1986], [Hartzell, Shulman and Wurtzebach, 1987], [Hudson-Wilson, 1990], [Seiler, Webb and Myer, 1999], [Viezer, 2000]). Various standard portfolio construction techniques (such as those mentioned in Subsection 16.2) can be applied to determine allocations.

## 16.3.1 Strategy: Property type diversification

This strategy amounts to investing in real estate assets of different types, e.g., apartments, offices, industrial properties (which include manufacturing buildings and property), shopping centers, etc. Empirical studies suggest that property type diversification can be beneficial for non-systematic risk reduction after taking into account transaction costs (see, e.g., [Firstenberg, Ross and Zisler, 1988], [Grissom, Kuhle and Walther, 1987], [Miles and McCue, 1984], [Mueller and Laposa, 1995]).

## 16.3.2 Strategy: Economic diversification

This strategy amounts to diversifying real estate investments by different regions divided according to economic characteristics such as the main economic activity, employment statistics, average income, etc. Empirical studies suggest that such diversification can reduce non-systematic risk and transaction costs (see, e.g., [Hartzell, Shulman and Wurtzebach, 1987], [Malizia and Simons, 1991], [Mueller, 1993]).

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 16.3.3 Strategy: Property type and geographic diversification

This strategy combines diversification based on more than one attribute, e.g., property type and region. Thus, if we consider four property types, to wit, office, retail, industrial and residential, and four U.S. regions, to wit, East, Midwest, South, and West, we can diversify across the resultant 16 groups (see, e.g., [Viezer, 2000]).207

## 16.4 Strategy: Real estate momentum – regional approach

This strategy amounts to buying real estate properties based on their past returns. Empirical evidence suggests that there is a momentum effect across the U.S. metropolitan statistical areas (MSAs), i.e., areas with higher (lower) past returns tend to continue to deliver higher (lower) returns in the future (see, e.g., [Beracha and Downs, 2015], [Beracha and Skiba, 2011]). In some cases, a zero-cost strategy can be constructed, e.g., by using alternative real estate vehicles such as REITs, and futures and options on U.S. housing indices based on different geographical areas.208

## 16.5 Strategy: Inflation hedging with real estate

Empirical studies suggest a strong relationship between the real estate returns and inflation rate. Therefore, real estate can be used as a hedge against inflation. Further, empirically, some property types (e.g., commercial real estate, which tends to adjust faster to inflationary price increases) appear to provide a better hedge than others, albeit this can depend on various aspects such as the sample, market, etc.209

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 16.6 Strategy: Fix-and-flip

This is a short-term real estate investment strategy. It amounts to purchasing a property, which typically is in a distressed condition and requires renovations, at a (substantial) discount below market prices. The investor renovates the property and resells it at a price high enough to cover the renovation costs and make a profit.210

## 17 Cash

## 17.1 Generalities

Cash is an asset, albeit at times its function as an asset might be overlooked or taken for granted. As an asset, cash can be used in a variety of ways, e.g., i) as a risk management tool, as it can help mitigate drawdowns and volatility; ii) as an opportunity management tool, as it allows to take advantage of specific or unusual situations; and iii) as a liquidity management tool in unexpected situations that require liquid funds. There are several ways to include liquid funds in a portfolio, e.g., via U.S. Treasury bills, bank deposit certificates (CDs), commercial paper, banker’s acceptances, eurodollars, and repurchase agreements (a.k.a. repos), etc.211

## 17.2 Strategy: Money laundering – the dark side of cash

Money laundering, broadly, is an activity wherein cash is used as a vehicle to transform illegal profits into legitimate-appearing assets. There are three main steps in a money laundering process. The first and the riskiest step is the placement, whereby illegal funds are introduced into the legal economy via fraudulent means, e.g., by dividing funds into small amounts and depositing them into multiple bank accounts thereby avoiding detection. The second step, layering, involves moving the money around between different accounts and even countries thereby creating complexity and separating the money from its source by several degrees. The third step is integration, whereby money launderers get back the money via legitimate-looking sources, e.g., cash-intensive businesses such as bars and restaurants, car washes, hotels (at least in some countries), gambling establishments, parking garages, etc.212

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 17.3 Strategy: Liquidity management

From a portfolio management perspective, this strategy amounts to optimally defining the amount of cash to be held in the portfolio to meet liquidity demands generated by unforeseen events.213 Cash provides immediate liquidity, whereas other assets would have to be liquidated first, which can be associated with substantial transaction costs, especially if liquidation is abrupt.214 From a corporate perspective, holding cash can be a precautionary measure aimed at avoiding cash flow shortfalls that can yield, inter alia, loss of investment opportunities, financial distress, etc.215

## 17.4 Strategy: Repurchase agreement (REPO)

A repurchase agreement (REPO) is a cash-equivalent asset that provides immediate liquidity at a preset interest rate for a specific period of time in exchange for another asset used as a collateral. A reverse repurchase agreement is the opposite. So, a REPO strategy amounts to borrowing (lending) cash with interest in exchange for securities with the commitment of repurchasing them from (reselling them to) the counterparty. This type of a transaction typically spans from 1 day to 6 months.216

## 17.5 Strategy: Pawnbroking

REPOs are in some sense similar to much more ancient pawnbroking strategies. A pawnbroker extends a secured cash loan with pre-agreed interest and period (which can sometimes be extended). The loan is secured with a collateral, which is some valuable item(s), such as jewelry, electronics, vehicles, rare books or musical instruments, etc. If the loan is not repaid with interest as agreed, then the collateral is forfeited by the borrower and the pawnbroker can keep it or sell it. The amount of loan typically is at a significant discount to the appraised value of the collateral.217

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 17.6 Strategy: Loan sharking

Unlike pawnbroking, loan sharking in many jurisdictions is illegal. Loan sharking consists of offering a loan at excessively high interest rates. Such a loan is not necessarily secured by a collateral. Instead, a loan shark can sometimes resort to blackmail and/or violence to enforce the terms of a loan (see, e.g., [Aldohni, 2013]).

## 18 Cryptocurrencies

## 18.1 Generalities

Cryptocurrencies, such as Bitcoin (BTC), Ethereum (ETH), etc., unlike traditional fiat currencies (USD, EUR, etc.), are decentralized digital currencies based on opensource peer-to-peer (P2P) internet protocols. Cryptocurrencies such as BTC and ETH use the blockchain technology [Nakamoto, 2008].218 Total market capitalization of cryptocurrencies is measured in hundreds of billions of dollars.219 Many investors are attracted to cryptocurrencies as speculative buy-and-hold assets. Thus, some view them as diversifiers due to their low correlation with traditional assets. Others perceive them as the future of money. Some investors simply want to make a quick buck on a speculative bubble. Etc.220 Be it as it may, unlike, e.g., stocks, there are no evident “fundamentals” for cryptoassets based on which one could build “fundamental” trading strategies (e.g., value-based strategies). So, cryptocurrency trading strategies tend to rely on trend data mining via machine learning techniques.

## 18.2 Strategy: Artificial neural network (ANN)

This strategy uses ANN to forecast short-term movements of BTC based on input technical indicators. In ANN we have an input layer, an output layer, and some

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

number of hidden layers. So, in this strategy the input layer is built using technical indicators.221 E.g., we can use (exponential) moving averages ((E)MAs), (exponential) moving standard deviations ((E)MSDs), relative strength index (RSI),222 etc. More concretely, we can construct the input layer as follows (see, e.g., [Nakano, Takahashi and Takahashi, 2018]). Let $P ( t )$ be the BTC price at time t, where $t = 1 , 2 , . . .$ . is measured in some units (e.g., 15-minute intervals; also, $t = 1$ is the most recent time). Let:

$$
R ( t ) = \frac { P ( t ) } { P ( t + 1 ) } - 1\tag{521}
$$

$$
\widetilde { R } ( t , T _ { 1 } ) = R ( t ) - \overline { { R } } ( t , T _ { 1 } )\tag{522}
$$

$$
\overline { { R } } ( t , T _ { 1 } ) = \frac { 1 } { T _ { 1 } } \sum _ { t ^ { \prime } = t + 1 } ^ { t + T _ { 1 } } R ( t ^ { \prime } )\tag{523}
$$

$$
\widehat { R } ( t , T _ { 1 } ) = \frac { \widetilde { R } ( t , T _ { 1 } ) } { \sigma ( t , T _ { 1 } ) }\tag{524}
$$

$$
[ \sigma ( t , T _ { 1 } ) ] ^ { 2 } = \frac { 1 } { T _ { 1 } - 1 } \sum _ { t ^ { \prime } = t + 1 } ^ { t + T _ { 1 } } [ \widetilde { R } ( t , T _ { 1 } ) ] ^ { 2 }\tag{525}
$$

So: $R ( t )$ is the return from $t + 1$ to t; $\overline { { R } } ( t , T _ { 1 } )$ is the serial mean return from $t + T _ { 1 }$ to $t + 1$ , i.e., over $T _ { 1 }$ periods, where $T _ { 1 }$ can be chosen to be long enough to provide a reasonable estimate for the volatility (see below); $\widetilde { R } ( t , T _ { 1 } )$ is the serially demeaned return; $\sigma ( t , T _ { 1 } )$ is the volatility computed from $t + T _ { 1 }$ to $t + 1 { \mathrm { : } }$ ; and $\widehat { R } ( t , T _ { 1 } )$ is the normalized (serially demeaned) return. Below, for notational simplicity we will omit the reference to the $T _ { 1 }$ parameter and will use $\widehat { R } ( t )$ to denote the normalized returns.

Next, we can define EMAs, EMSDs and RSI as follows:223

$$
\operatorname { E M A } ( t , \lambda , \tau ) = \frac { 1 - \lambda } { 1 - \lambda ^ { \tau } } \sum _ { t ^ { \prime } = t + 1 } ^ { t + \tau } \lambda ^ { t ^ { \prime } - t - 1 } \widehat { R } ( t ^ { \prime } )\tag{526}
$$

$$
[ \mathrm { E M S D } ( t , \lambda , \tau ) ] ^ { 2 } = \frac { 1 - \lambda } { \lambda - \lambda ^ { \tau } } \sum _ { t ^ { \prime } = t + 1 } ^ { t + \tau } \lambda ^ { t ^ { \prime } - t - 1 } [ \widehat { R } ( t ^ { \prime } ) - \mathrm { E M A } ( t , \lambda , \tau ) ] ^ { 2 }\tag{527}
$$

$$
\operatorname { R S I } ( t , \tau ) = \frac { \nu _ { + } ( t , \tau ) } { \nu _ { + } ( t , \tau ) + \nu _ { - } ( t , \tau ) }\tag{528}
$$

$$
\nu _ { \pm } ( t , \tau ) = \sum _ { t ^ { \prime } = t + 1 } ^ { t + \tau } \operatorname* { m a x } ( \pm \widehat { R } ( t ^ { \prime } ) , 0 )\tag{529}
$$

Here: $\tau$ is the moving average length; λ is the exponential smoothing parameter.224

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

The input layer can then be defined as consisting of, $\mathrm { e . g . , } \ \widehat { R } ( t )$ , EMA $( t , \lambda _ { a } , \tau _ { a } )$ ， $\mathrm { E M S D } ( t , \lambda _ { a } , \tau _ { a } )$ , and $\mathrm { R S I } ( t , \tau _ { a ^ { \prime } } ^ { \prime } )$ , where $a = 1 , \ldots , m , a ^ { \prime } = 1 , \ldots , m ^ { \prime }$ . The values $\tau _ { a }$ can, e.g., be chosen to correspond to 30 min, 1 hr, 3 hrs and 6 hrs $( \operatorname { s o } m = 4 ;$ see fn. 224 for the values of $\lambda _ { a } )$ . The values $\tau _ { a ^ { \prime } } ^ { \prime }$ can, e.g., be chosen to correspond to 3 hrs, 6 hrs and 12 hrs $( \mathrm { s o \ m ^ { \prime } = 3 } )$ . There is no magic bullet here. These values can be chosen based on out-of-sample backtests keeping in mind, however, the ever-present danger of over-fitting various free parameters (see below), including $\tau _ { a } , \lambda _ { a }$ and $\tau _ { a ^ { \prime } } ^ { \prime }$

The output layer can be constructed as follows. Let the objective be to forecast which quantile the future normalized return will belong to. Let the number of quantiles be K. Thus, for the values of t corresponding to the training dataset $D _ { t r a i n } , { } ^ { 2 2 5 }$ we have the normalized returns $\widehat { R } ( t ) , t \in D _ { t r a i n }$ . Let the $( K - 1 )$ quantile values of $\widehat { R } ( t ) , t \in D _ { t r a i n }$ , be $q _ { \alpha } , \alpha = 1 , \ldots , ( K - 1 )$ . For each value of t, we can define the supervisory K-vectors ${ \cal S } _ { \alpha } ( t ) , \alpha = 1 , \ldots , K$ , as follows:

$$
\left\{ \begin{array} { l l } { S _ { 1 } ( t ) = 1 , } & { \widehat { R } ( t ) \leq q _ { 1 } } \\ { S _ { \alpha } ( t ) = 1 , } & { q _ { \alpha - 1 } \leq \widehat { R } ( t ) < q _ { \alpha } , \quad 1 < \alpha < K } \\ { S _ { K } ( t ) = 1 , } & { q _ { K - 1 } \leq \widehat { R } ( t ) } \\ { S _ { \alpha } ( t ) = 0 , } & { \mathrm { o t h e r w i s e } } \end{array} \right.\tag{530}
$$

The output layer can then be a nonnegative K-vector $p _ { \alpha } ( t )$ , whose elements are interpreted as the probabilities of the future normalized return to be in the α-th quantile. So, we have

$$
\sum _ { \alpha = 1 } ^ { K } p _ { \alpha } ( t ) = 1\tag{531}
$$

The output layer is constructed from the input layer as some nonlinear function thereof with some number of parameters to be determined via training. In ANN we have L layers labeled by $\ell = 1 , \ldots , L$ , where $\ell = 1$ corresponds to the input layer, and $\ell = L$ corresponds to the output layer. At each layer we have $N ^ { ( \ell ) }$ nodes and the corresponding $N ^ { ( \ell ) }$ -vectors $\vec { X } ^ { ( \ell ) }$ with components $\dot { X } _ { i ^ { ( \ell ) } } ^ { ( \ell ) } , i ^ { ( \ell ) } = 1 , \dots , N ^ { ( \ell ) } ; { ^ { 2 2 6 } }$

$$
X _ { i ^ { ( \ell ) } } ^ { ( \ell ) } = h _ { i ^ { ( \ell ) } } ^ { ( \ell ) } ( \vec { Y } ^ { ( \ell ) } ) , \quad \ell = 2 , \dots , L\tag{532}
$$

$$
Y _ { i ^ { ( \ell ) } } ^ { ( \ell ) } = \sum _ { j ^ { ( \ell - 1 ) } = 1 } A _ { i ^ { ( \ell ) } j ^ { ( \ell - 1 ) } } ^ { ( \ell ) } X _ { j ^ { ( \ell - 1 ) } } ^ { ( \ell - 1 ) } + B _ { i ^ { ( \ell ) } } ^ { ( \ell ) }\tag{533}
$$

Here: $\vec { Y } ^ { ( \ell ) }$ is an $N ^ { ( \ell ) }$ -vector with components $Y _ { i ^ { ( \ell ) } } ^ { ( \ell ) } , \ i ^ { ( \ell ) } \ = \ 1 , \dots , N ^ { ( \ell ) } ; \ X _ { i ^ { ( 1 ) } } ^ { ( 1 ) }$ are the input data (for each value of $t , \mathrm { i . e . , } \ \widehat { R } ( t )$ , EMA(t, λa, τa), $\mathrm { E M S D } ( t , \lambda _ { a } , \tau _ { a } )$ , and $\mathrm { R S I } ( t , \tau _ { a ^ { \prime } } ^ { \prime } )$ – see above); $X _ { i ^ { ( L ) } } ^ { ( L ) }$ are the output data $p _ { \alpha } ( t ) \ ( \mathrm { i . e . , } N ^ { ( L ) } = K$ and the index

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

$i ^ { ( L ) }$ is the same as α); the unknown parameters $A _ { i ^ { ( \ell ) } j ^ { ( \ell - 1 ) } } ^ { ( \ell ) }$ (the so-called weights) and $B _ { i ^ { ( \ell ) } } ^ { ( \ell ) }$ (the so-called bias) are determined via training (see below); and there is much arbitrariness in terms of picking the values of $N ^ { ( \ell ) }$ and the so-called activation functions $h _ { i ^ { ( \ell ) } } ^ { ( \ell ) }$ . A possible choice (out of myriad others) is as follows (see, e.g., [Nakano, Takahashi and Takahashi, 2018]):227

$$
h _ { i ^ { ( \ell ) } } ^ { ( \ell ) } ( \vec { Y } ^ { ( \ell ) } ) = \operatorname* { m a x } \left( Y _ { i ^ { ( \ell ) } } ^ { ( \ell ) } , 0 \right) , \quad \ell = 2 , \ldots , L - 1 \quad \mathrm { ( R e L U ) }\tag{534}
$$

$$
h _ { i ^ { ( L ) } } ^ { ( L ) } ( \vec { Y } ^ { ( L ) } ) = Y _ { i ^ { ( L ) } } ^ { ( L ) } \left[ \sum _ { j ^ { ( L ) } = 1 } ^ { N ^ { ( L ) } } Y _ { j ^ { ( L ) } } ^ { ( L ) } \right] ^ { - 1 } \quad \mathrm { ( s o f t m a x ) }\tag{535}
$$

I.e., ReLU is used at the hidden layers (and the algorithm moves onto the next layer only if some neurons are activated (fired) at layer \`, i.e., at least some $Y _ { i ^ { ( \ell ) } } ^ { ( \ell ) } > 0 )$ and softmax is used at the output layer (so that we have the condition (531) by construction). Further, to train the model, i.e., to determine the unknown parameters, some kind of error function E (we suppress its variables) must be minimized, e.g., the so-called cross-entropy (see, e.g., [de Boer et al, 2005]):

$$
E = - \sum _ { \substack { t \in D _ { t r a i n } \alpha = 1 } } S _ { \alpha } ( t ) \ \ln ( p _ { \alpha } ( t ) )\tag{536}
$$

To minimize $E ,$ one can, e.g., use the stochastic gradient descent (SGD) method, which minimizes the error function iteratively until the procedure converges.228

Finally, we must specify the trading rules. There are a number of possibilities here depending on the number of quantiles, i.e., the choice of K. A reasonable trading signal is given by:

$$
{ \mathrm { S i g n a l } } = { \left\{ \begin{array} { l l } { { \mathrm { B u y , } } } & { { \mathrm { i f } } \quad { \mathrm { m a x } } ( p _ { \alpha } ( t ) ) = p _ { K } ( t ) } \\ { { \mathrm { S e l l , } } } & { { \mathrm { i f } } \quad { \mathrm { m a x } } ( p _ { \alpha } ( t ) ) = p _ { 1 } ( t ) } \end{array} \right. }\tag{537}
$$

Therefore, the trader buys BTC if the predicted class is $p _ { K } ( t )$ (the top quantile), and sells if it is $p _ { 1 } ( t )$ (the bottom quantile). This trading rule can be modified. E.g., the buy signal can be based on the top 2 quantiles, and the sell signal can be based on the bottom 2 quantiles (see, e.g., [Nakano, Takahashi and Takahashi, 2018]).229

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## 18.3 Strategy: Sentiment analysis – na¨ıve Bayes Bernoulli

Social media sentiment analysis based strategies have been used in stock trading230 and also applied to cryptocurrency trading. The premise is to use a machine learning classification scheme to forecast, e.g., the direction of the BTC price movement based on tweet data. This entails collecting all tweets containing at least one keyword from a pertinent (to BTC price forecasting) learning vocabulary V over some timeframe, and cleaning this data.231 The resultant data is then further processed by assigning a so-called feature (M -vector) $X _ { i }$ to each tweet labeled by $i = 1 , \ldots , N$ , where N is the number of tweets in the dataset. Here $M = | V |$ is the number of keywords in the learning vocabulary V . So, the components of each vector $X _ { i }$ are $X _ { i a }$ , where $a = 1 , \dots , M$ labels the words in V . Thus, if the word $w _ { a } \in V$ labeled by a is not present in the tweet $T _ { i }$ labeled by i, then $X _ { i a } = 0$ . If $w _ { a }$ is present in $T _ { i } .$ then we can set $X _ { i a } = 1$ or $X _ { i a } = n _ { i a }$ , where $n _ { i a }$ counts the number of times $w _ { a }$ appears in $T _ { i }$ In the former case (which is what we focus on in the following) we have a Bernoulli probability distribution, while in the latter case we have a multinomial distribution.

Next, we need to build a model that, given the N feature vectors $X _ { i }$ , predicts one out of a preset number K of outcomes (so-called classes) $C _ { \alpha } , \alpha = 1 , \ldots , K$ E.g., we can have $K = 2$ outcomes, whereby BTC is forecasted to go up or down, which can be used as the buy/sell signal. Alternatively, as in the ANN strategy in Subsection 18.2, we can have K quantiles for the normalized returns $\widehat { R } ( t )$ . Etc. This then defines our trading rules. Once the classes $C _ { \alpha }$ are chosen, a simple way to forecast them is to build a model for conditional probabilities $P ( C _ { \alpha } | X _ { 1 } , \dots , X _ { N } )$ Here, generally, $P ( A | B )$ denotes the conditional probability of A occurring assuming B is true. Pursuant to Bayes’ theorem, we have

$$
P ( A | B ) = { \frac { P ( B | A ) \ P ( A ) } { P ( B ) } }\tag{538}
$$

where $P ( A )$ and $P ( B )$ are the probabilities of A and B occurring independently of each other. So, we have

$$
P ( C _ { \alpha } | X _ { 1 } , \ldots , X _ { N } ) = { \frac { P ( X _ { 1 } , \ldots , X _ { N } | C _ { \alpha } ) \ P ( C _ { \alpha } ) } { P ( X _ { 1 } , \ldots , X _ { N } ) } }\tag{539}
$$

Note that $P ( X _ { 1 } , \ldots , X _ { N } )$ is independent of $C _ { \alpha }$ and will not be important below. Now, $P ( C _ { \alpha } )$ can be estimated from the training data. The primary difficulty is in

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

estimating $P ( X _ { 1 } , \dots , X _ { N } | C _ { \alpha } )$ . Here a simplification occurs if we make the “na¨ıve” conditional independence assumption (hence the term “na¨ıve Bayes”), i.e., that, given the class $C _ { \alpha }$ , for all i the feature $X _ { i }$ is conditionally independent of every other feature $X _ { j } , j = 1 , \dotsc , N \ ( j \neq i )$ :

$$
P ( X _ { i } | C _ { \alpha } , X _ { 1 } , \ldots , X _ { i - 1 } , X _ { i + 1 } , \ldots , X _ { N } ) = P ( X _ { i } | C _ { \alpha } )\tag{540}
$$

Then Eq. (539) simplifies as follows:

$$
P ( C _ { \alpha } | X _ { 1 } , \dots , X _ { N } ) = \gamma \ P ( C _ { \alpha } ) \ \prod _ { i = 1 } ^ { N } P ( X _ { i } | C _ { \alpha } )\tag{541}
$$

$$
\gamma = 1 / P ( X _ { 1 } , \ldots , X _ { N } )\tag{542}
$$

The conditional probabilities $P ( X _ { i } | C _ { \alpha } )$ can be estimated using the conditional probabilities $P ( w _ { a } | C _ { \alpha } )$ for the M words $w _ { a }$ in the learning vocabulary V :

$$
P ( X _ { i } | C _ { \alpha } ) = \prod _ { a = 1 } ^ { M } Q _ { i a \alpha }\tag{543}
$$

$$
Q _ { i a \alpha } = P ( w _ { a } | C _ { \alpha } ) , \quad X _ { i a } = 1\tag{544}
$$

$$
Q _ { i a \alpha } = 1 - P ( w _ { a } | C _ { \alpha } ) , \quad X _ { i a } = 0\tag{545}
$$

The conditional probabilities $P ( w _ { a } | C _ { \alpha } )$ can simply be estimated based on the occurrence frequencies of the words $w _ { a }$ in the training data. Similarly, the probabilities $P ( C _ { \alpha } )$ can be estimated from the training data.232 So, if we set the forecasted value $C _ { p r e d }$ of the outcome to that with the maximum $P ( C _ { \alpha } | X _ { 1 } , \dots , X _ { N } )$ , then

$$
C _ { p r e d } = \mathrm { a r g m a x } _ { C _ { \alpha \in \{ 1 , \ldots , K \} } } P ( C _ { \alpha } ) \prod _ { i = 1 } ^ { N } \prod _ { a = 1 } ^ { M } [ P ( w _ { a } | C _ { \alpha } ) ] ^ { X _ { i a } } [ 1 - P ( w _ { a } | C _ { \alpha } ) ] ^ { 1 - X _ { i a } }\tag{546}
$$

## 19 Global Macro

## 19.1 Generalities

Actually, macro trading strategies constitute an investment style, not an asset class. These types of strategies are not limited to any particular asset class or a geographical region and can invest in stocks, bonds, currencies, commodities, derivatives, etc.,

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

seeking to capitalize on regional, economic and political changes around the world. While many macro strategies are based on analysts’ subjective opinions (these are discretionary strategies), a systematic approach (non-discretionary strategies) also plays a prominent role. Global macro strategies can vary by their style, e.g., there are directional strategies, long-short strategies, relative value strategies, etc.233

## 19.2 Strategy: Fundamental macro momentum

This strategy aims to capture returns from the market underreaction to changes in macroeconomic trends by buying (selling) assets favored (adversely affected) by incoming macroeconomic trends. Different asset classes can be used in building an investment portfolio, e.g., global equity indexes, currencies, government bonds, etc.234 The “state variables” to consider are the business cycle, international trade, monetary policy, and risk sentiment trends (see, e.g., [Brooks, 2017]).235 E.g., equity indexes from some number of countries are ranked using the values of the aforesaid 4 state variables for each country.236 A zero-cost portfolio can then be constructed by, e.g., going long the indexes in the top decile and shorting those in the bottom decile. The so-constructed portfolios for various asset classes can, e.g., be combined with equal weights. Typically, the holding period ranges from three to six months.

## 19.3 Strategy: Global macro inflation hedge

Exogenous shocks (such as a political or geopolitical issue) can have an impact on commodity prices such as oil leading to an increase in prices in oil-dependent economies. There are two steps in this process: (i) a pass-through from commodity prices to the headline inflation (HI), and (ii) then, a pass-through from HI to the core inflation (CI).237 I.e., HI quickly reflects various shocks around the world. So,

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

the global macro inflation hedge strategy is based on the spread between HI and CI as an indicator to hedge inflation using commodities:238

$$
\mathrm { C A } = \operatorname* { m a x } \Bigg ( 0 , \operatorname* { m i n } \left( \frac { \mathrm { H I } _ { Y o Y } - \mathrm { C I } _ { Y o Y } } { \mathrm { H I } _ { Y o Y } } , 1 \right) \Bigg )\tag{547}
$$

Here: CA is the commodity allocation percentage within the portfolio, and “YoY” stands for “year-on-year”. The hedge can be executed by, e.g., buying a basket of various commodities through ETFs, futures, etc. (see, e.g., [Fulli-Lemaire, 2013]).

## 19.4 Strategy: Global fixed-income strategy

This systematic macro trading strategy is based on a cross-sectional analysis of government bonds from various countries using variables such as (see, e.g., [Br¨uck and Fan, 2017]) GDP, inflation, sovereign risk, real interest rate, output gap, value, momentum, term spread, and the so-called Cochrane-Piazzesi predictor [Cochrane and Piazzesi, 2005]. Thus, said bonds can be ranked based on these factors and a zero-cost portfolio can be constructed by buying bonds in the top quantile and selling bonds in the bottom quantile. Similarly to Subsection 3.6, multifactor portfolios can also be constructed. Typically, country-bond ETFs are used in such portfolios.239

## 19.5 Strategy: Trading on economic announcements

Empirical evidence suggests that stocks tend to yield higher returns on important announcement dates such Federal Open Market Committee (FOMC) announcements.240 So, a simple macro trading strategy consists of buying stocks on important announcement days (ADs), such as the FOMC announcements, and switching to risk-free assets during non-announcement days (NDAs). This is done via ETFs, futures, etc., as opposed to individual stocks, as the strategy involves moving from 100% allocated in equities to 100% allocated in Treasuries (see, e.g., [Stotz, 2016]).241

## 20 Infrastructure

Broadly, investing in infrastructure includes investing in long-term projects such as transportation (roads, bridges, tunnels, railways, ports, airports, etc.), telecommuni-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

cations (transmission cables, satellites, towers, etc.), utilities (electricity generation, gas or electricity transmission or distribution, water supply, sewage, waste, etc.), energy (including but not limited to renewable energy), healthcare (hospitals, clinics, senior homes, etc.), educational facilities (schools, universities, research institutes, etc.), etc. An investor can gain exposure to infrastructure assets through different direct or indirect investments such private equity-type investments (e.g., via unlisted infrastructure funds), listed infrastructure funds, stocks of publicly traded infrastructure companies, municipal bonds earmarked to infrastructure projects, etc.242

Infrastructure investments, by their nature, are long-term, buy-and-hold investments. One investment strategy is to use infrastructure assets to improve riskadjusted returns of well-diversified portfolios, e.g., via tracking ETFs, global infrastructure funds, unlisted infrastructure funds, etc.243 Another investment strategy is to use infrastructure assets for inflation hedging.244 Yet another investment strategy is to generate stable cash flows from infrastructure investments. For this purpose, “brownfield” projects (associated with established assets in need of improvement) are more appropriate than “greenfield” projects (associated with assets to be constructed). Diversification across different sectors can be beneficial in this regard.245

## Acknowledgments

JAS would like to thank Juli´an R. Siri for valuable discussions.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## A R Source Code for Backtesting

In this appendix we give the R (R Package for Statistical Computing, http://www. r-project.org) source code for backtesting intraday strategies, where the position is established at the open and liquidated at the close of the same day. The sole purpose of this code is to illustrate some simple tricks for doing out-of-sample backtesting. In particular, this code does not deal with the survivorship bias in any way,246 albeit for this kind of strategies – precisely because these are intraday strategies – the survivorship bias is not detrimental (see, e.g., [Kakushadze, 2015b]).247

The main function (which internally calls some subfunctions) is qrm.backtest() with the following inputs: (i) days is the lookback; (ii) d.r is used for computing risk, both as the length of the moving standard deviation tr (computed internally over d.r-day moving windows) as well as the lookback for computing the risk model (and, if applicable, a statistical industry classification) – see below; (iii) d.addv is used as the lookback for the average daily dollar volume addv, which is computed internally; (iv) n.addv is the number of top tickers by addv used as the trading universe, which is recomputed every d.r days; (v) inv.lvl is the total investment level (long plus short, and the strategy is dollar-neutral); (vi) bnds controls the position bounds (which are the same in this strategy as the trading bounds), i.e., the dollar holdings $H _ { i }$ for each stock are bounded via $( B _ { i }$ are the bnds elements, which can be uniform)

$$
\left| H _ { i } \right| \le B _ { i } \ A _ { i }\tag{548}
$$

where $i = 1 , \dots ,$ , N labels the stocks in the trading universe, and $A _ { i }$ are the corresponding elements of addv; (vii) incl.cost is a Boolean for including linear trading costs, which are modeled as follows.248 For the stock labeled by i, let $E _ { i }$ be its expected return, and $w _ { i }$ be its weight in the portfolio. The source code below determines $w _ { i }$ via (mean-variance) optimization (with bounds). For the stock labeled by $i ,$ let the linear trading cost per dollar traded be $\tau _ { i }$ . Including such costs in portfolio optimization amounts to replacing the expected return of the portfolio

$$
E _ { p o r t } = \sum _ { i = 1 } ^ { N } E _ { i } \mathrm { ~ } w _ { i }\tag{549}
$$

by

$$
E _ { p o r t } = \sum _ { i = 1 } ^ { N } \left[ E _ { i } \ w _ { i } - \tau _ { i } \ | w _ { i } | \right]\tag{550}
$$

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

A complete algorithm for including linear trading costs in mean-variance optimization is given in, e.g., [Kakushadze, 2015b]. However, for our purposes here the following simple “hack” suffices. We can define the effective return

$$
E _ { i } ^ { e f f } = \mathrm { s i g n } ( E _ { i } ) \operatorname* { m a x } ( | E _ { i } | - \tau _ { i } , 0 )\tag{551}
$$

and simply set

$$
E _ { p o r t } = \sum _ { i = 1 } ^ { N } E _ { i } ^ { e f f } \ w _ { i }\tag{552}
$$

I.e., if the magnitude for the expected return for a given stock is less than the expected cost to be incurred, we set the expected return to zero, otherwise we reduce said magnitude by said cost. This way we can avoid a nontrivial iterative procedure (see, e.g., [Kakushadze, 2015b]), albeit this is only an approximation.

So, what should we use as $\tau _ { i }$ in (551)? The model of [Almgren et al, 2005] is reasonable for our purposes here. Let $H _ { i }$ be the dollar amount traded for the stock labeled by i. Then for the linear trading costs we have

$$
T _ { i } = \zeta \ \sigma _ { i } \ \frac { | H _ { i } | } { A _ { i } }\tag{553}
$$

where $\sigma _ { i }$ is the historical volatility, $A _ { i }$ is the average daily dollar volume (ADDV), and ζ is an overall normalization constant we need to fix. However, above we work with weights $w _ { i } ,$ not traded dollar amounts $H _ { i }$ . In our case of a purely intraday trading strategy discussed above, they are related simply via $H _ { i } = I \ w _ { i }$ , where I is the total investment level (i.e., the total absolute dollar holdings of the portfolio after establishing it). Therefore, we have (note that $T _ { i } = \tau _ { i } \ | { \cal H } _ { i } | = \tau _ { i } ~ I \ | w _ { i } | )$

$$
\tau _ { i } = \zeta \ \frac { \sigma _ { i } } { A _ { i } }\tag{554}
$$

We will fix the overall normalization ζ via the following heuristic. We will (conservatively) assume that the average linear trading cost per dollar traded is 10 bps (1 bps = 1 basis point = 1/100 of 1%),249 i.e., mean $. ( \tau _ { i } ) = 1 0 ^ { - 3 }$ and $\zeta = 1 0 ^ { - 3 } / \mathrm { m e a n } ( \sigma _ { i } / A _ { i } )$

Next, internally the code sources price and volume data by reading it from tabdelimited files250 nrm.ret.txt (overnight return internally referred to as ret – see below), nrm.open.txt (daily raw, unadjusted open price, internally referred to as open), nrm.close.txt (daily raw, unadjusted close price, internally referred to as close), nrm.vol.txt (daily raw, unadjusted volume, internally referred to as vol), nrm.prc.txt (daily close price fully adjusted for all splits and dividends, internally referred to as prc). The rows of ret, open, close, vol and prc correspond to the N tickers (index i). Let trading days be labeled by $t = 0 , 1 , 2 , \ldots , T$ , where t = 0 is the

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

most recent day. Then the columns of open, close, vol and prc correspond to the trading days $t = 1 , 2 , \dots , T$ , i.e., the value of t is the same as the value of the column index. On the other hand, the columns of ret correspond to the overnight close-toopen returns from the trading day t to the trading day $t - 1$ . I.e., the first column of ret corresponds to the overnight close-to-open return from the trading day $t = 1$ to the trading day $t = 0$ . Furthermore, ret, call it $R _ { i } ( t )$ , where $t = 1 , 2 , \dots , T$ labels the columns of ret, is computed as follows:

$$
R _ { i } ( t ) = \ln \left( \frac { P _ { i } ^ { A O } ( t - 1 ) } { P _ { i } ^ { A C } ( t ) } \right)\tag{555}
$$

$$
P _ { i } ^ { A O } ( t ) = \gamma _ { i } ^ { a d j } ( t ) \ P _ { i } ^ { O } ( t )\tag{556}
$$

$$
\gamma _ { i } ^ { a d j } ( t ) = \frac { P _ { i } ^ { A C } ( t ) } { P _ { i } ^ { C } ( t ) }\tag{557}
$$

Here: $P _ { i } ^ { O } ( t )$ is the raw open price (which is the corresponding element of open for $t = 1 , 2 , . . . , T ) ; P _ { i } ^ { C } ( t )$ is the raw close price (which is the corresponding element of close for $t = 1 , 2 , \ldots , T ) ; P _ { i } ^ { A C } ( t )$ is the fully adjusted close price (which is the corresponding element of prc for $\dot { t } = 1 , 2 , \dots , \dot { T } ) ; \hat { \gamma _ { i } ^ { a d j } } ( t )$ is the adjustment factor, which is used for computing the fully adjusted open price $P _ { i } ^ { A O } ( t )$ ; so $R _ { i } ( t )$ is the overnight, close-to-open return based on fully adjusted prices. Note that the $t = 0$ prices required for computing $R _ { i } ( 1 )$ are not part of the matrices open, close and prc. Also, the code internally assumes that the matrices ret, open, close, vol and prc are all aligned, i.e., all tickers and dates are the same and in the same order in each of the 5 files nrm.ret.txt (note the labeling of the returns described above), nrm.open.txt, nrm.close.txt, nrm.vol.txt and nrm.prc.txt. The ordering of the tickers in these files is immaterial, so long as it is the same in all 5 files as the code is oblivious to this ordering. However, the dates must be ordered in the descending order, i.e., the first column corresponds to the most recent date, the second column corresponds to the date before it, etc. (here $\mathrm { ^ { 6 } d a t e ^ { 9 } }$ corresponds to a trading day). Finally, note that the internal function read. ${ \bf \nabla } \cdot { \bf x } \left( { \bf \nabla } \right)$ reads these files with the parameter value as.is = T. This means that these files are in the “R-ready” tab-delimited format, with $N + 1$ tab-delimited lines. The lines 2 through $N + 1$ have $T + 1$ elements each, the first element being a ticker symbol (so the N ticker symbols comprise dimnames(·)[[1]] of the corresponding matrix, e.g., open for the open prices), and the other $T$ elements being the $T$ values $( \mathrm { e . g . , } P _ { i } ^ { O } ( t ) , t = 1 , . . . , T$ for the open prices). However, the first line has only $T$ elements, which are the labels of the trading days (so these comprise dimnames(·)[[2]] of the corresponding matrix, $\mathrm { e . g . } , \mathrm { g . . }$ , open for the open prices). Internal functions that use this input data, such as calc.mv.avg() (which computes simple moving averages) and calc.mv.sd() (which computes simple moving standard deviations) are simple and self-explanatory.

As mentioned above, the input parameter d.r is used for recomputing the trading universe every d.r trading days and also recomputing the risk models (see below) every d.r trading days. These computations are done 100% out-of-sample, i.e., the

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

data used in these computations is 100% in the past w.r.t. to the trading day on which the resultant quantities are used for (simulated) trading. This is accomplished in part by using the internal function calc.ix(). Note that the input data described above is structured and further used in such a way that the backtests are 100% outof-sample. Here two conceptually different aspects must be distinguished. Thus, we have the expected returns and “the rest”, the latter – which can be loosely referred to as “risk management” – being the universe selection, the risk model computation, etc., i.e., the machinery that gets us from the expected returns to the desired holdings (that is, the strategy positions). The risk management part must be 100% out-of-sample. In real life the expected returns are also 100% outof-sample. However, in backtesting, while the expected returns cannot under any circumstances look into the future, they can sometimes be “borderline in-sample”. Thus, consider a strategy that today trades on the overnight yesterday’s-close-totoday’s-open return. If we assume that the positions are established based on this return sometime after the open, then the backtest is out-of-sample by the “delay” time between the open and when the position is established. However, if we assume that the position is established at the open, then this is the so-called “delay-0” strategy, and the backtest is “borderline in-sample” in the sense that in real life the orders would have to be sent with some, albeit possibly small, delay, but could never be executed exactly at the open. In this sense it still makes sense to backtest such a strategy to measure the strength of the signal. What would make no sense and should never be done is to run an outright in-sample backtest that looks into the future. E.g., using today’s closing prices for computing expected returns for trading at today’s open would be grossly in-sample. On the other hand, using yesterday’s prices to trade at today’s open is the so-called “delay-1” strategy, which is basically 1 day out-of-sample (and, not surprisingly, is expected to backtest much worse than a delay-0 strategy). The code gives examples of both delay-0 (mean-reversion) and delay-1 (momentum) strategies (see the comments DELAY-0 and DELAY-1 in the code).

The code internally computes the desired holdings via optimization. The optimizer function (which incorporates bounds and linear constraints such as dollarneutrality) bopt.calc.opt() is given in [Kakushadze, 2015e]. One of its inputs is the inverse model covariance matrix for the stocks. This matrix is computed internally via functions such as qrm.cov.pc() and qrm.erank.pc(), which are given in and utilize the statistical risk model construction of [Kakushadze and Yu, 2017a], or qrm.gen.het(), which is given in and utilizes the heterotic risk model construction of [Kakushadze and Yu, 2016a]. The latter requires a multilevel binary industry classification. The code below builds such a classification via the function qrm.stat.ind.class.all(), which is given in and utilizes the statistical industry classification construction of [Kakushadze and Yu, 2016b]. However, the code can be straightforwardly modified to utilize a fundamental industry classification, such as GICS (Global Industry Classification Standard), BICS (Bloomberg Industry Classification System), SIC (Standard Industrial Classification), etc. One issue with this is that practically it is difficult to do this 100% out-of-sample. However, “in-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

sampleness” of a fundamental industry classification – which is relatively stable – typically does not pose a serious issue in such backtests as stocks rarely jump industries. Furthermore, note that the aforesaid “external” functions have various other parameters (which are set to their implicit default values in the code below), which can be modified (see the references above that provide the aforesaid functions).

Finally, the code internally computes the desired holdings and various performance characteristics such as the total P&L over the backtesting period, annualized return, annualized Sharpe ratio, and cents-per-share. These and other quantities computed internally can be returned (e.g., via environments or lists), dumped into files, printed on-screen, etc. The code is straightforward and can be tweaked depending on the user’s specific needs/strategies. Its purpose is illustrative/pedagogical.

```r
qrm.backtest <- function (days = 252 * 5, d.r = 21, d.addv = 21,
n.addv = 2000, inv.lvl = 2e+07, bnds = .01, incl.cost = F)
{
calc.ix <- function(i, d, d.r)
{
k1 <- d - i
k1 <- trunc(k1 / d.r)
ix <- d - k1 * d.r
return(ix)
}
calc.mv.avg <- function(x, days, d.r)
{
y <- matrix(0, nrow(x), days)
for(i in 1:days)
y[, i] <- rowMeans(x[, i:(i + d.r - 1)])
return(y)
}
calc.mv.sd <- function(x, days, d.r)
{
y <- matrix(0, nrow(x), days)
for(i in 1:days)
y[, i] <- apply(x[, i:(i + d.r - 1)], 1, sd)
return(y)
}
read.x <- function(file)
{
```

```r
Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights
Reserved.
x <- read.delim(file, as.is = T)
x <- as.matrix(x)
mode(x) <- "numeric"
return(x)
}
calc.sharpe <- function (pnl, inv.lvl)
{
print(sum(pnl, na.rm = T))
print(mean(pnl, na.rm = T) * 252 / inv.lvl * 100)
print(mean(pnl, na.rm = T) / sd(pnl, na.rm = T) * sqrt(252))
}
ret <- read.x("nrm.ret.txt")
open <- read.x("nrm.open.txt")
close <- read.x("nrm.close.txt")
vol <- read.x("nrm.vol.txt")
prc <- read.x("nrm.prc.txt")
addv <- calc.mv.avg(vol * close, days, d.addv)
ret.close <- log(prc[, -ncol(prc)]/prc[, -1])
tr <- calc.mv.sd(ret.close, days, d.r)
ret <- ret[, 1:days]
prc <- prc[, 1:days]
close <- close[, 1:days]
open <- open[, 1:days]
close1 <- cbind(close[, 1], close[, -ncol(close)])
open1 <- cbind(close[, 1], open[, -ncol(open)])
pnl <- matrix(0, nrow(ret), ncol(ret))
des.hold <- matrix(0, nrow(ret), ncol(ret))
for(i in 1:ncol(ret))
{
ix <- calc.ix(i, ncol(ret), d.r)
if(i == 1)
prev.ix <- 0
if(ix != prev.ix)
{
liq <- addv[, ix]
x <- sort(liq)
```

right c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights   
rved.   
x <- x[length(x):1]   
take <- liq >= x[n.addv]   
r1 <- ret.close[take, (ix:(ix + d.r - 1))]   
### ind.list <- qrm.stat.ind.class.all(r1,   
### c(100, 30, 10), iter.max = 100)   
### rr <- qrm.gen.het(r1, ind.list)   
rr <- qrm.cov.pc(r1)   
### rr <- qrm.erank.pc(r1)   
cov.mat <- rr\$inv.cov   
prev.ix <- ix   
}   
w.int <- rep(1, sum(take))   
ret.opt <- ret ### DELAY-0 MEAN-REVERSION   
### ret.opt <- -log(close/open) ### DELAY-1 MOMENTUM   
if(incl.cost)   
{   
lin.cost <- tr[take, i] / addv[take, i]   
lin.cost <- 1e-3 \* lin.cost / mean(lin.cost)   
}   
else   
lin.cost <- 0   
ret.lin.cost <- ret.opt[take, i]   
ret.lin.cost <- sign(ret.lin.cost) \*   
pmax(abs(ret.lin.cost) - lin.cost, 0)   
des.hold[take, i] <- as.vector(bopt.calc.opt(ret.lin.cost, w.int,   
cov.mat, bnds \* liq[take]/inv.lvl, -bnds \* liq[take]/inv.lvl))   
des.hold[take, i] <- -des.hold[take, i] \*   
inv.lvl / sum(abs(des.hold[take, i]))   
pnl[take, i] <- des.hold[take, i] \*   
(close1[take, i]/open1[take, i] - 1)   
pnl[take, i] <- pnl[take, i] - abs(des.hold[take, i]) \* lin.cost   
131

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

```r
}
des.hold <- des.hold[, -1]
pnl <- pnl[, -1]
pnl <- colSums(pnl)
calc.sharpe(pnl, inv.lvl)
trd.vol <- 2 * sum(abs(des.hold/open1[, -1]))
cps <- 100 * sum(pnl) / trd.vol
print(cps)
}
```

## B DISCLAIMERS

Wherever the context so requires, the masculine gender includes the feminine and/or neuter, and the singular form includes the plural and vice versa. The author of this paper (“Author”) and his affiliates including without limitation Quantigicr Solutions LLC (“Author’s Affiliates” or “his Affiliates”) make no implied or express warranties or any other representations whatsoever, including without limitation implied warranties of merchantability and fitness for a particular purpose, in connection with or with regard to the content of this paper including without limitation any code or algorithms contained herein (“Content”).

The reader may use the Content solely at his/her/its own risk and the reader shall have no claims whatsoever against the Author or his Affiliates and the Author and his Affiliates shall have no liability whatsoever to the reader or any third party whatsoever for any loss, expense, opportunity cost, damages or any other adverse effects whatsoever relating to or arising from the use of the Content by the reader including without any limitation whatsoever: any direct, indirect, incidental, special, consequential or any other damages incurred by the reader, however caused and under any theory of liability; any loss of profit (whether incurred directly or indirectly), any loss of goodwill or reputation, any loss of data suffered, cost of procurement of substitute goods or services, or any other tangible or intangible loss; any reliance placed by the reader on the completeness, accuracy or existence of the Content or any other effect of using the Content; and any and all other adversities or negative effects the reader might encounter in using the Content irrespective of whether the Author or his Affiliates is or are or should have been aware of such adversities or negative effects.

Any information or opinions provided herein are for informational purposes only and are not intended, and shall not be construed, as an investment, legal, tax or any other such advice, or an offer, solicitation, recommendation or endorsement of any trading strategy, security, product or service, or any article, book or any other publication referenced herein or any of the content contained therein.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

The R code included in Appendix A hereof is part of the copyrighted R code of Quantigicr Solutions LLC and is provided herein with the express permission of Quantigicr Solutions LLC. The copyright owner retains all rights, title and interest in and to its copyrighted source code included in Appendix A hereof and any and all copyrights therefor.

## References

Abken, P.A. (1989) An analysis of intra-market spreads in heating oil futures. Journal of Futures Markets 9(1): 77-86.

Abken, P.A. and Nandi, S. (1996) Options and Volatility. Federal Reserve Bank of Atlanta, Economic Review 81(3): 21-35.

Abraham, J.M. and Hendershott, P.H. (1993) Patterns and Determinants of Metropolitan House Prices, 1977 to 1991. In: Browne, L.E. and Rosengren, E.S. (eds.) Real Estate and the Credit Crunch. Boston, MA: Federal Reserve Bank of Boston, pp. 18-42.

Abraham, J.M. and Hendershott, P.H. (1996) Bubbles in Metropolitan Housing Markets. Journal of Housing Research 7(2): 191-207.

Abreu, D. and Brunnermeier, M.K. (2002) Synchronization risk and delayed arbitrage. Journal of Financial Economics 66(2-3): 341-360.

Accominotti, O. and Chambers, D. (2014) Out-of-Sample Evidence on the Returns to Currency Trading. Working Paper. Available online: https:// ssrn.com/abstract=2293684.

Acharya, V.V., Almeida, H. and Campello, M. (2007) Is cash negative debt? A hedging perspective on corporate financial policies. Journal of Financial Intermediation 16(4): 515-554.

Ackert, L.F. and Tian, Y.S. (2000) Arbitrage and valuation in the market for Standard and Poor’s Depositary Receipts. Financial Management 29(3): 71-87.

Adam, F. and Lin, L.H. (2001) An Analysis of the Applications of Neural Networks in Finance. Interfaces 31(4): 112-122.

Adams, Z. and Gl¨uck, T. (2015) Financialization in commodity markets: A passing trend or the new normal? Journal of Banking & Finance 60: 93-111.

Adrangi, B., Chatrath, A., Song, F. and Szidarovszky, F. (2006) Petroleum spreads and the term structure of futures prices. Applied Economics 38(16): 1917-1929.

Adrian, T., Begalle, B., Copeland, A. and Martin, A. (2013) Repo and Securities Lending. Federal Reserve Bank of New York Staff Reports, No. 529. Available online:

https://www.newyorkfed.org/medialibrary/media/research/staff\_ reports/sr529.pdf.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Adrian, T. and Wu, H. (2010) The Term Structure of Inflation Expectations. Federal Reserve Bank of New York Staff Reports, No. 362. Available online: https://www.newyorkfed.org/medialibrary/media/research/staff\_ reports/sr362.pdf.

Agapova, A. (2011a) Conventional mutual funds versus exchange-traded funds. Journal of Financial Markets 14(2): 323-343.

Agapova, A. (2011b) The Role of Money Market Mutual Funds in Mutual Fund Families. Journal of Applied Finance 21(1): 87-102.

Agarwal, V., Fung, W.H., Loon, Y.C. and Naik, N.Y. (2011) Risk and return in convertible arbitrage: Evidence from the convertible bond market. Journal of Empirical Finance 18(2): 175-194.

Ahmadi, H.Z., Sharp, P.A. and Walther, C.H. (1986) The effectiveness of futures and options in hedging currency risk. In: Fabozzi, F. (ed.) Advances in Futures and Options Research, Vol. 1, Part B. Greenwich, CT: JAI Press, Inc., pp. 171-191.

Ahmerkamp, J.D. and Grant, J. (2013) The Returns to Carry and Momentum Strategies. Working Paper. Available online: https://ssrn.com/abstract= 2227387.

Ahn, D.-H., Boudoukh, J., Richardson, M. and Whitelaw, R.F. (2002) Partial adjustment or stale prices? Implications from stock index and futures return autocorrelations. Review of Financial Studies 15(2): 655-689.

Ahn, D.-H., Conrad, J. and Dittmar, R. (2003) Risk Adjustment and Trading Strategies. Review of Financial Studies 16(2): 459-485.

Ai, H. and Bansal, R. (2016) Risk Preferences and the Macro Announcement Premium. Working Paper. Available online: https://ssrn.com/abstract= 2827445.

Aiba, Y. and Hatano, N. (2006) A microscopic model of triangular arbitrage. Physica A: Statistical Mechanics and its Applications 371(2): 572-584.

Aiba, Y., Hatano, N., Takayasu, H., Marumo, K. and Shimizu, T. (2002) Triangular arbitrage as an interaction among foreign exchange rates. Physica A: Statistical Mechanics and its Applications 310(3-4): 467-479.

Aiba, Y., Hatano, N., Takayasu, H., Marumo, K. and Shimizu, T. (2003) Triangular arbitrage and negative auto-correlation of foreign exchange rates. Physica A: Statistical Mechanics and its Applications 324(1-2): 253-257.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Aij¨o, J. (2008) Implied volatility term structure linkages between VDAX, ¨ VSMI and VSTOXX volatility indices. Global Finance Journal 18(3): 290- 302.

A¨ıt-Sahalia, Y. and Duarte, J. (2003) Nonparametric option pricing under shape restrictions. Journal of Econometrics 116(1-2): 9-47.

A¨ıt-Sahalia, Y., Karaman, M. and Mancini, L. (2015) The Term Structure of Variance Swaps and Risk Premia. Working Paper. Available online: https: //ssrn.com/abstract=2136820.

Akram, Q.F., Rime, D. and Sarno, L. (2008) Arbitrage in the foreign exchange market: Turning on the microscope. Journal of International Economics 76(2): 237-253.

Alaminos, D., del Castillo, A. and Fern´andez, M.A. (2016) A Global Model ´ for Bankruptcy Prediction. PLoS ONE 11(11): e0166693.

Alaton, P., Djehiche, B. and Stillberger, D. (2010) On modelling and pricing weather derivatives. Applied Mathematical Finance 9(1): 1-20.

Albeverio, S., Steblovskaya, V. and Wallbaum, K. (2013) Investment instruments with volatility target mechanism. Quantitative Finance 13(10): 1519- 1528.

Albrecht, P. (1985) A note on immunization under a general stochastic equilibrium model of the term structure. Insurance: Mathematics and Economics 4(4): 239-244.

Aldohni, A.K. (2013) Loan Sharks v. Short-term Lenders: How Do the Law and Regulators Draw the Line? Journal of Law and Society 40(3): 420-449.

Aldridge, I. (2013) High-Frequency Trading: A Practical Guide to Algorithmic Strategies and Trading Systems. (2nd ed.) Hoboken, NJ: John Wiley & Sons, Inc.

Aldridge, I. (2016) ETFs, High-Frequency Trading, and Flash Crashes. Journal of Portfolio Management 43(1): 17-28.

Alessandretti, L., ElBahrawy, A., Aiello, L.M. and Baronchelli, A. (2018) Machine Learning the Cryptocurrency Market. Working Paper. Available online: https://arxiv.org/pdf/1805.08550.pdf.

Alexander, C. and Korovilas, D. (2012) Understanding ETNs on VIX Futures. Working Paper. Available online: https://ssrn.com/abstract=2043061.

Alexander, G.J. and Resnick, B.G. (1985) Using linear and goal programming to immunize bond portfolios. Journal of Banking & Finance 9(1): 35-54.

Allen, F. and Michaely, R. (1995) Dividend Policy. In: Jarrow, R.A., Maksimovic, V. and Ziemba, W.T. (eds.) Handbooks in Operations Research and Management Science, Vol 9. Amsterdam, The Netherlands: Elsevier, Chapter 25, pp. 793-837.

Almeida, H., Campello, M. and Weisbach, M.S. (2005) The Cash Flow Sensitivity of Cash. Journal of Finance 59(4): 1777-1804.

Almgren, R., Thum, C., Hauptmann, E. and Li, H. (2005) Equity market impact. Risk Magazine 18(7): 57-62.

Altman, E.I. (1968) Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy. Journal of Finance 23(4): 589-609.

Altman, E. (1993) Corporate financial distress and bankruptcy. (2nd ed.) Hoboken, NJ: John Wiley & Sons, Inc.

Altman, E.I. (1998) Market Dynamics and Investment Performance of Distressed and Defaulted Debt Securities. Working Paper. Available online: https://ssrn.com/abstract=164502.

Altman, N.S. (1992) An introduction to kernel and nearest-neighbor nonparametric regression. American Statistician 46(3): 175-185.

Altman, E.I., Brady, B., Resti, A. and Sironi, A. (2005) The link between default and recovery rates: theory, empirical evidence and implications. Journal of Business 78(6): 2203-2228.

Altman, E.I. and Hotchkiss, E. (2006) Corporate Financial Distress and Bankruptcy: Predict and Avoid Bankruptcy, Analyze and Invest in Distressed Debt. Hoboken, NJ: John Wiley & Sons, Inc.

Amaitiek, O.F.S., B´alint, T. and Reˇsovsk´y, M. (2010) The Short Call Ladder strategy and its application in trading and hedging. Acta Montanistica Slovaca 15(3): 171-182.

Amato, J.D. and Gyntelberg, J. (2005) CDS Index Tranches and the Pricing of Credit Risk Correlations. BIS Quarterly Review, December 2005, pp. 73-87. Available online: https://www.bis.org/publ/qtrpdf/r\_qt0503g.pdf.

Amato, J.D. and Remolona, E.M. (2003) The credit spread puzzle. BIS Quarterly Review, December 2003, pp. 51-63. Available online: https://www.bis. org/publ/qtrpdf/r\_qt0312e.pdf.

Ambrose, B., LaCour-Little, M. and Sanders, A. (2004) The Effect of Conforming Loan Status on Mortgage Yield Spreads: A Loan Level Analysis. Real Estate Economics 32(4): 541-569.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Amenc, N., Ducoulombier, F., Goltz, F. and Ulahel, J. (2016) Ten Misconceptions about Smart Beta. Working Paper. Available online: https://www. edhec.edu/sites/www.edhec-portail.pprod.net/files/publications/ pdf/edhec-position-paper-ten-misconceptions-about-smart-beta% 5F1468395239135-pdfjpg.

Amenc, N., Goltz, F., Sivasubramanian, S. and Lodh, A. (2015) Robustness of Smart Beta Strategies. Journal of Index Investing 6(1): 17-38.

Amenc, N., Martellini, L. and Ziemann, V. (2009) Inflation-Hedging Properties of Real Assets and Implications for Asset-Liability Management Decisions. Journal of Portfolio Management 35(4): 94-110.

Amihud, Y. (2002) Illiquidity and stock returns: cross-section and time-series effects. Journal of Financial Markets 5(1): 31-56.

Amihud, Y. and Goyenko, R. (2013) Mutual Fund’s R2 as Predictor of Performance. Review of Financial Studies 26(3): 667-694.

Amihud, Y. and Murgia, M. (1997) Dividends, Taxes, and Signaling: Evidence from Germany. Journal of Finance 52(1): 397-408.

Amin, G.S. and Kat, H.M. (2003) Welcome to the Dark Side: Hedge Fund Attrition and Survivorship Bias over the Period 1994-2001. Journal of Alternative Investments 6(1): 57-73.

Amiri, M., Zandieh, M., Vahdani, B., Soltani, R. and Roshanaei, V. (2010) An integrated eigenvector-DEA-TOPSIS methodology for portfolio risk evaluation in the FOREX spot market. Expert Systems with Applications 37(1): 509-516.

Amjad, M.J. and Shah, D. (2017) Trading Bitcoin and Online Time Series Prediction. Working Paper. Available online: http://proceedings.mlr.press/ v55/amjad16.pdf.

Ammann, M., Kind, A. and Seiz, R. (2010) What drives the performance of convertible-bond funds? Journal of Banking & Finance 34(11): 2600-2613.

Ammann, M., Kind, A. and Wilde, C. (2003) Are convertible bonds underpriced? An analysis of the French market. Journal of Banking & Finance 27(4): 635-653.

An, B.-J., Ang, A., Bali, T.G. and Cakici, N. (2014) The Joint Cross Section of Stocks and Options. Journal of Finance 69(5): 2279-2337.

Anacker, K.B. (2009) Big flipping schemes in small cities? The case of Mansfield, Ohio. Housing and Society 36(1): 5-28.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Anacker, K.B. and Schintler, L.A. (2015) Flip that house: visualising and analysing potential real estate property flipping transactions in a cold local housing market in the United States. International Journal of Housing Policy 15(3): 285-303.

Anand, A. and Venkataraman, K. (2016) Market Conditions, Fragility, and the Economics of Market Making. Journal of Financial Economics 121(2): 327-349.

Andersen, L. (1999) A Simple Approach to the Pricing of Bermudan Swaptions in the Multi-factor Libor Market Model. Journal of Computational Finance 3(2): 5-32.

Andersen, L.B.G. (2010) Markov models for commodity futures: theory and practice. Quantitative Finance 10(8): 831-854.

Andersen, L. and Sidenius, J. (2005) Extensions to the Gaussian Copula: Random Recovery and Random Factor Loadings. Journal of Credit Risk 1(1): 29-70.

Andersen, L., Sidenius, J. and Basu, S. (2003) All your hedges in one basket. Risk, November 2003, pp. 67-72.

Anderson, R.M., Bianchi, S.W. and Goldberg, L.R. (2014) Determinants of Levered Portfolio Performance. Financial Analysts Journal 70(5): 53-72.

Anderson, R.W. and Danthine, J.P. (1981) Cross Hedging. Journal of Political Economy 89(6): 1182-1196.

Andrade, G., Mitchell, M. and Stafford, E. (2001) New evidence and perspectives on mergers. Journal of Economic Perspectives 15(2): 103-120.

Andrie¸s, A.M. and Vˆırlan, C.A. (2017) Risk arbitrage in emerging Europe: are cross-border mergers and acquisition deals more risky? Economic Research – Ekonomska Istraˇzivanja 30(1): 1367-1389.

An´e, T. and Labidi, C. (2001) Implied volatility surfaces and market activity over time. Journal of Economics and Finance 25(3): 259-275.

Ang, S., Alles, L. and Allen, D. (1998) Riding the Yield Curve: An Analysis of International Evidence. Journal of Fixed Income 8(3): 57-74.

Ang, A., Bekaert, G. and Wei, M. (2008) The Term Structure of Real Rates and Expected Inflation. Journal of Finance 63(2): 797-849.

Ang, A., Green, R.C., Longstaff, F.A. and Xing, Y. (2017) Advance Refundings of Municipal Bonds. Journal of Finance 72(4): 1645-1682.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Ang, A., Hodrick, R., Xing, Y. and Zhang, X. (2006) The Cross-Section of Volatility and Expected Returns. Journal of Finance 61(1): 259-299.

Ang, A., Hodrick, R., Xing, Y. and Zhang, X. (2009) High Idiosyncratic Volatility and Low Returns: International and Further U.S. Evidence. Journal of Financial Economics 91(1): 1-23.

Ang, K.K. and Quek, C. (2006) Stock trading using RSPOP: A novel rough set-based neuro-fuzzy approach. IEEE Transactions on Neural Networks 17(5): 1301-1315.

Anglin, P.M., Rutherford, R. and Springer, T. (2003) The Trade-off Between the Selling Price of Residential Properties and Time-on-the-Market: The Impact of Price Setting. Journal of Real Estate Finance and Economics 26(1): 95-111.

Anker, P. (1999) Uncovered interest parity, monetary policy and time-varying risk premia. Journal of International Money and Finance 18(6): 835-851.

Ankirchner, S., Dimitroff, G., Heyne, G. and Pigorsch, C. (2012) Futures Cross-Hedging with a Stationary Basis. Journal of Financial and Quantitative Analysis 47(6): 1361-1395.

Ankirchner, S. and Heyne, G. (2012) Cross Hedging with Stochastic Correlation. Finance and Stochastics 16(1): 17-43.

Ansar, A., Flyvbjerg, B., Budzier, A. and Lunn, D. (2016) Does infrastructure investment lead to economic growth or economic fragility? Evidence from China. Oxford Review of Economic Policy 32(3): 360-390.

Anson, M.J.P (1998) Spot Returns, Roll Yield, and Diversification with Commodity Futures. Journal of Alternative Investments 1(3): 16-32.

Anson, M. (2013) Performance Measurement in Private Equity: The Impact of FAS 157 on the Lagged Beta Effect. Journal of Private Equity 17(1): 29-44.

Antonacci, G. (2014) Dual Momentum Investing: An Innovative Strategy for Higher Returns with Lower Risk. New York, NY: McGraw-Hill, Inc.

Antonacci, G. (2017) Risk Premia Harvesting Through Dual Momentum. Journal of Management & Entrepreneurship 11(1): 27-55.

Antoniou, A. and Holmes, P. (1995) Futures Trading, Information and Spot Price Volatility: Evidence from the FTSE 100 Stock Index Futures Contract using GARCH. Journal of Banking & Finance 19(1): 117-129.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Aragon, G.O., Ergun, A.T., Getmansky, M. and Girardi, G. (2017) Hedge Fund Liquidity Management. Working Paper. Available online: https:// ssrn.com/abstract=3033930.

Ardizzi, G., Petraglia, C., Piacenza, M., Schneider, F. and Turati, G. (2014) Money Laundering as a Crime in the Financial Sector: A New Approach to Quantitative Assessment, with an Application to Italy. Journal of Money, Credit and Banking 46(8): 1555-1590.

Aretz, K. and Pope, P.F. (2013) Common factors in default risk across countries and industries. European Financial Management 19(1): 108-152.

Arezki, R. and Sy, A. (2016) Financing Africa’s Infrastructure Deficit: From Development Banking to Long-term Investing. Journal of African Economies 25(S2): 59-73.

Armann, V. and Weisdorf, M. (2008) Hedging Inflation with Infrastructure Assets. In: Benaben, B. and Goldenberg, S. (eds.) Inflation Risk and Products: The Complete Guide. London, UK: Risk Books, pp. 111-126.

Arnott, R., Chaves, D., Gunzberg, J., Hsu, J. and Tsui, P. (2014) Getting Smarter about Commodities: An index to counter the possible pitfalls. Journal of Indexes, November/December 2014, pp. 52-60.

Arnott, R.D., Hsu, J., Kalesnik, V. and Tindall, P. (2013) The Surprising Alpha from Malkiel’s Monkey and Upside-Down Strategies. Journal of Portfolio Management 39(4): 91-105.

Arnsdorf, M. and Halperin, I. (2007) BSLP: Markovian bivariate spreadloss model for portfolio credit derivatives. Working Paper. Available online: https://arxiv.org/pdf/0901.3398.

Asem, E. and Tian, G. (2010) Market Dynamics and Momentum Profits. Journal of Financial and Quantitative Analysis 45(6): 1549-1562.

Asgharian, M., Diz, F., Gregoriou, G.N. and Rouah, F. (2004) The Global Macro Hedge Fund Cemetery. Journal of Derivatives Accounting 1(2): 187- 194.

Asgharian, H. and Karlsson, S. (2008) An Empirical Analysis of Factors Driving the Swap Spread. Journal of Fixed Income 18(2): 41-56.

Asness, C.S. (1994) Variables that Explain Stock Returns (Ph.D. Thesis). Chicago, IL: University of Chicago.

Asness, C.S. (1995) The Power of Past Stock Returns to Explain Future Stock Returns. Working Paper (unpublished). New York, NY: Goldman Sachs Asset Management.

Asness, C. (1997) The Interaction of Value and Momentum Strategies. Financial Analysts Journal 53(2): 29-36.

Asness, C., Frazzini, A., Israel, R. and Moskowitz, T. (2014) Fact, Fiction, and Momentum Investing. Journal of Portfolio Management 40(5): 75-92.

Asness, C., Krail, R.J. and Liew, J.M. (2001) Do Hedge Funds Hedge? Journal of Portfolio Management 28(1): 6-19.

Asness, C., Moskowitz, T. and Pedersen, L.H. (2013) Value and Momentum Everywhere. Journal of Finance 68(3): 929-985.

Asness, C.S., Porter, R.B. and Stevens, R.L. (2000) Predicting Stock Returns Using Industry-Relative Firm Characteristics. Working Paper. Available online: https://ssrn.com/abstract=213872.

Augustin, P., Brenner, B. and Subrahmanyam, M.G. (2015) Informed Options Trading prior to M&A Announcements: Insider Trading? Working Paper. Available online: https://ssrn.com/abstract=2441606.

Aussenegg, W., G¨otz, L. and Jelic, R. (2014) European asset swap spreads and the credit crisis. European Journal of Finance 22(7): 572-600.

Avdjiev, S., Du, W., Koch, C. and Shin, H.S. (2016) The Dollar, Bank Leverage and the Deviation from Covered Interest Parity. Working Paper. Available online: https://ssrn.com/abstract=2870057.

Avellaneda, M. and Lee, J.H. (2010) Statistical arbitrage in the U.S. equity market. Quantitative Finance 10(7): 761-782.

Avellaneda, M. and Papanicolaou, A. (2018) Statistics of VIX Futures and Applications to Trading Volatility Exchange-Traded Products. Journal of Investment Strategies 7(2): 1-33.

Avellaneda, M. and Stoikov, S. (2008) High frequency trading in a limit order book. Quantitative Finance 8(3): 217-224.

Avellaneda, M. and Zhang, S. (2010) Path-Dependence of Leveraged ETF Returns. Journal on Financial Mathematics 1(1): 586-603.

Ayache, E., Forsyth, P.A. and Vetzal, K.R. (2003) Valuation of Convertible Bonds With Credit Risk. Journal of Derivatives 11(1): 9-29.

Ayuso, J. and Restoy, F. (1996) Interest Rate Parity and Foreign Exchange Risk Premia in the ERM. Journal of International Money and Finance 15(3): 369-382.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Azmat, Q. and Iqbal, A.M. (2017) The role of financial constraints on precautionary cash holdings: evidence from Pakistan. Economic Research – Ekonomska Istraˇzivanja 30(1): 596-610.

Baba, N. and Packer, F. (2009) Interpreting deviations from covered interest parity during the financial market turmoil of 2007-08. Journal of Banking & Finance 33(11): 1953-1962.

Babbs, S.H. and Nowman, B.K. (1999) Kalman filtering of generalized Vasicek term structure models. Journal of Financial and Quantitative Analysis 34(1): 115-130.

Bacchetta, P. and van Wincoop, E. (2006) Incomplete Information Processing: A Solution to the Forward Discount Puzzle. American Economic Review 96(3): 552-576.

Bacchetta, P. and van Wincoop, E. (2010) Infrequent Portfolio Decisions: A Solution to the Forward Discount Puzzle. American Economic Review 100(3): 870-904.

Baek, C. and Elbeck, M. (2014) Bitcoins as an Investment or Speculative Vehicle? A First Look. Applied Economics Letters 22(1): 30-34.

Bai, Q., Bond, S.A. and Hatch, B.C. (2015) The Impact of Leveraged and Inverse ETFs on Underlying Real Estate Returns. Real Estate Economics 43(1): 37-66.

Bai, J. and Collin-Dufresne, P. (2013) The CDS-Bond Basis. Working Paper. Available online: https://ssrn.com/abstract=2024531.

Baillie, R.T. and Myers, R.J. (1991) Bivariate GARCH estimation of the optimal commodity futures hedge. Journal of Applied Econometrics 6(2): 109-124.

Baillie, R.T. and Osterberg, W.P. (2000) Deviations from daily uncovered interest rate parity and the role of intervention. Journal of International Financial Markets, Institutions and Money 10(4): 363-379.

Baker, M., Bradley, B. and Wurgler, J. (2011) Benchmarks as Limits to Arbitrage: Understanding the Low-Volatility Anomaly. Financial Analysts Journal 67(1): 40-54.

Baker, M., Pan, A. and Wurgler, J. (2012) The effect of reference point prices on mergers and acquisitions. Journal of Financial Economics 106(1): 49-71.

Baker, M. and Sava¸soglu, S. (2002) Limited arbitrage in mergers and acquisitions. Journal of Financial Economics 64(1): 91-115.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Bakshi, G. and Kapadia, N. (2003a) Delta-Hedged Gains and the Negative Market Volatility Risk Premium. Review of Financial Studies 16(2): 527-566.

Bakshi, G. and Kapadia, N. (2003b) Volatility Risk Premiums Embedded in Individual Equity Options. Journal of Derivatives 11(1): 45-54.

Bakshi, G., Kapadia, N. and Madan, D. (2003) Stock Return Characteristics, Skew Laws, and the Differential Pricing of Individual Equity Options. Review of Financial Studies 16(1): 101-143.

Bakshi, G. and Panayotov, G. (2013) Predictability of currency carry trades and asset pricing implications. Journal of Financial Economics 110(1): 139- 163.

Balb´as, A., Longarela, I.R. and Lucia, J.J. (1999) How Financial Theory Applies to Catastrophe-Linked Derivatives – An Empirical Test of Several Pricing Models. Journal of Risk and Insurance 66(4): 551-582.

Bali, T.G. and Demirtas, K.O. (2008) Testing mean reversion in financial market volatility: Evidence from S&P 500 index futures. Journal of Futures Markets 28(1): 1-33.

Bali, T.G. and Hovakimian, A. (2009) Volatility Spreads and Expected Stock Returns. Management Science 55(11): 1797-1812.

Ballings, M., Van den Poel, D., Hespeels, N. and Gryp, R. (2015) Evaluating multiple classifiers for stock price direction prediction. Expert Systems with Applications 42(20): 7046-7056.

Balta, A.-N. and Kosowki, R. (2013) Momentum Strategies in Futures Markets and Trend-Following Funds. Working Paper. Available online: https://www. edhec.edu/sites/www.edhec-portail.pprod.net/files/publications/ pdf/edhec-working-paper-momentum-strategies-in-futures\_ 1410350911195-pdfjpg.

Bandarchuk, P. and Hilscher, J. (2013) Sources of Momentum Profits: Evidence on the Irrelevance of Characteristics. Review of Finance 17(2): 809-845.

Banz, R. (1981) The relationship between return and market value of common stocks. Journal of Financial Economics 9(1): 3-18.

Barber, J., Bennett, S. and Gvozdeva, E. (2015) How to Choose a Strategic Multifactor Equity Portfolio? Journal of Index Investing 6(2): 34-45.

Barberis, N. (2000) Investing for the Long Run when Returns Are Predictable. Journal of Finance 55(1): 225-264.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Barberis, N. and Huang, M. (2008) Stocks as Lotteries: The Implications of Probability Weighting for Security Prices. American Economic Review 98(5): 2066-2100.

Bardong, F. and Lehnert, T. (2004) TIPS, Break-Even Inflation, and Inflation Forecasts. Journal of Fixed Income 14(3): 15-35.

Bariviera, A.F., Basgall, M.J., Hasperu´e, W. and Naiouf, M. (2017) Some stylized facts of the Bitcoin market. Physica A: Statistical Mechanics and its Applications 484: 82-90.

Barnes, M.L., Bodie, Z., Triest, R.K. and Wang, J.C. (2010) A TIPS Scorecard: Are They Accomplishing Their Objectives? Financial Analysts Journal 66(5): 68-84.

Baron, M., Brogaard, J., Hagstr¨omer, B. and Kirilenko, A. (2014) Risk and Return in High-Frequency Trading. Journal of Financial and Quantitative Analysis (forthcoming). Available online: https://ssrn.com/abstract=2433118.

Barr, D.G. and Campbell, J.Y. (1997) Inflation, real interest rates, and the bond market: A study of UK nominal and index-linked government bond prices. Journal of Monetary Economics 39(3): 361-383.

Barrett, W.B. and Kolb, R.W. (1995) Analysis of spreads in agricultural futures. Journal of Futures Markets 15(1): 69-86.

Barrieu, P. and El Karoui, N. (2002) Optimal design of weather derivatives. ALGO Research 5(1): 79-92.

Barrieu, P. and Scaillet, O. (2010) A Primer on Weather Derivatives. In: Filar, J.A. and Haurie, A. (eds.) Uncertainty and Environmental Decision Making: A Handbook of Research and Best Practice. International Series in Operations Research & Management Science, Vol. 138. New York, NY: Springer U.S.

Barroso, P. and Santa-Clara, P. (2014) Momentum Has Its Moments. Journal of Financial Economics 116(1): 111-120.

Bartonov´a, M. (2012) Hedging of Sales by Zero-cost Collar and its Financial Impact. Journal of Competitiveness 4(2): 111-127.

Bartov, E., Radhakrishnan, S. and Krinsky, I. (2005) Investor Sophistication and Patterns in Stock Returns after Earnings Announcements. Accounting Review 75(1): 289-319.

Basu, S. (1977) The investment performance of common stocks in relation to their price to earnings ratios: A test of the efficient market hypothesis. Journal of Finance 32(3): 663-682.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Basu, D. and Miffre, J. (2013) Capturing the risk premium of commodity futures: The role of hedging pressure. Journal of Banking & Finance 37(7): 2652-2664.

Batta, G., Chacko, G. and Dharan, B. (2010) A Liquidity-Based Explanation of Convertible Arbitrage Alphas. Journal of Fixed Income 20(1): 28-43.

Battalio, R. and Mendenhall, R. (2007) Post-Earnings Announcement Drift: Intra-Day Timing and Liquidity Costs. Working Paper. Available online: https://ssrn.com/abstract=937257.

Batten, J. and Ellis, C. (1996) Technical trading system performance in the Australian share market: Some empirical evidence. Asia Pacific Journal of Management 13(1): 87-99.

Batten, J.A., Khaw, K. and Young, M.R. (2014) Convertible Bond Pricing Models. Journal of Economic Surveys 28(5): 775-803.

Baxter, M. and King, R. (1999) Measuring business cycles: Approximate bandpass filters for economic time-series. Review of Economics and Statistics 81(4): 575-593.

Baxter, M. and Rennie, A. (1996) Financial Calculus: An Introduction to Derivative Pricing. Cambridge, UK: Cambridge University Press.

Bayer, P.J., Geissler, C., Mangum, K. and Roberts, J.W. (2015) Speculators and Middlemen: The Strategy and Performance of Investors in the Housing Market. Working Paper. Available online: https://ssrn.com/abstract= 1754003.

Beaver, W.H. (1966) Financial ratios as predictors of failure. Journal of Accounting Research 4: 71-111.

Beaver, W.H., McNichols, M.F. and Rhie, J.-W. (2005) Have financial statements become less informative? Evidence from the ability of financial ratios to predict bankruptcy. Review of Accounting Studies 10(1): 93-122.

Bedendo, M., Cathcart, L. and El-Jahel, L. (2007) The Slope of the Term Structure of Credit Spreads: An Empirical Investigation. Journal of Financial Research 30(2): 237-257.

Beekhuizen, P., Duyvesteyn, J., Martens, M. and Zomerdijk, C. (2016) Carry Investing on the Yield Curve. Working Paper. Available online: http://ssrn. com/abstract=2808327.

Bekaert, G. and Wang, X. (2010) Inflation Risk and the Inflation Risk Premium. Economic Policy 25(64): 755-806.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Bekaert, G., Wei, M. and Xing, Y. (2007) Uncovered interest rate parity and the term structure. Journal of International Money and Finance 26(6): 1038- 1069.

Bekkers, N., Doeswijk, R.Q. and Lam, T.W. (2009) Strategic Asset Allocation: Determining the Optimal Portfolio with Ten Asset Classes. Journal of Wealth Management 12(3): 61-77.

Belgrade, N. and Benhamou, E. (2004) Reconciling Year on Year and Zero Coupon Inflation Swap: A Market Model Approach. Working Paper. Available online: https://ssrn.com/abstract=583641.

Belgrade, N., Benhamou, E. and Koehler, E. (2004) A Market Model for Inflation. Working Paper. Available online: https://ssrn.com/abstract= 576081.

Belkin, B., Suchover, S. and Forest, L. (1998) A one-parameter representation of credit risk and transition matrices. Credit Metrics Monitor 1(3): 46-56.

Bellamy, D.E. (1994) Evidence of imputation clienteles in the Australian equity market. Asia Pacific Journal of Management 11(2): 275-287.

Bellovary, J.L., Giacomino, D.E. and Akers, M.D. (2007) A review of bankruptcy prediction studies: 1930 to present. Journal of Financial Education 33(4): 3-41.

Benavides, G. (2009) Predictive Accuracy of Futures Options Implied Volatility: The Case of the Exchange Rate Futures Mexican Peso-US Dollar. Panorama Econ´omico 5(9): 55-95.

Ben-David, I., Franzoni, F.A. and Moussawi, R. (2012) ETFs, Arbitrage, and Contagion. Working Paper. Available online: http://www.nccr-finrisk. uzh.ch/media/pdf/wp/WP793\_B1.pdf.

Ben-David, I., Franzoni, F.A. and Moussawi, R. (2017) Do ETFs Increase Volatility? Journal of Finance (forthcoming). Available online: https:// ssrn.com/abstract=1967599.

Beneish, M.D. and Whaley, R.E. (1996) An Anatomy of the “S&P Game”: The Effects of Changing the Rules. Journal of Finance 51(5): 1909-1930.

Benet, B.A. (1990) Commodity futures cross hedging of foreign exchange exposure. Journal of Futures Markets 10(3): 287-306.

Bengio, Y. (2009) Learning Deep Architectures for AI. Foundations and Trends in Machine Learning 2(1): 1-127.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Benhamou, E. (2016) Trend Without Hiccups – A Kalman Filter Approach. Working Paper. Available online: https://ssrn.com/abstract=2747102.

Benos, E., Brugler, J., Hjalmarsson, E. and Zikes, F. (2017) Interactions among High-Frequency Traders. Journal of Financial and Quantitative Analysis 52(4): 1375-1402.

Benos, E. and Sagade, S. (2016) Price Discovery and the Cross-Section of High-Frequency Trading. Journal of Financial Markets 30: 54-77.

Benth, F. (2003) On arbitrage-free pricing of weather derivatives based on fractional Brownian motion. Applied Mathematical Finance 10(4): 303-324.

Benth, F.E. and Kettler, P.C. (2010) Dynamic copula models for the spark spread. Quantitative Finance 11(3): 407-421.

Benth, F.E., Kholodnyi, V.A. and Laurence, P. (eds.) (2014) Quantitative Energy Finance: Modeling, Pricing, and Hedging in Energy and Commodity Markets. New York, NY: Springer-Verlag.

Benth, F.E. and Saltyte-Benth, J. (2005) Stochastic modelling of temperature variations with a view towards weather derivatives. Applied Mathematical Finance 12(1): 53-85.

Benth, F.E. and Saltyte-Benth, J. (2007) The volatility of temperature and pricing of weather derivatives. Quantitative Finance 7(5): 553-561.

Benth, F., Saltyte-Benth, J. and Koekebakker, S. (2007) Putting a price on temperature. Scandinavian Journal of Statistics 34(4): 746-767.

BenZion, U., Anan, S.D. and Yagil, J. (2005) Box Spread Strategies and Arbitrage Opportunities. Journal of Derivatives 12(3): 47-62.

BenZion, U., Klein, P., Shachmurove, Y. and Yagil, J. (2003) Efficiency differences between the S&P 500 and the Tel-Aviv 25 indices: a moving average comparison. International Journal of Business 8(3): 267-284.

Beracha, E. and Downs, D.H. (2015) Value and Momentum in Commercial Real Estate: A Market-Level Analysis. Journal of Portfolio Management 41(6): 48-61.

Beracha, E. and Skiba, H. (2011) Momentum in Residential Real Estate. Journal of Real Estate Finance and Economics 43(3): 229-320.

Berk, J., Green, R. and Naik, V. (1999) Optimal Investment, Growth Options and Security Returns. Journal of Finance 54(5): 1153-1608.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Bernadell, C., Coche, J. and Nyholm, K. (2005) Yield curve prediction for the strategic investor. Working Paper Series, No. 472. Frankfurt am Main, Germany: European Central Bank. Available online: https://www.ecb.europa. eu/pub/pdf/scpwps/ecbwp472.pdf?1dc8846d9df4642959c54aa73cee81ad.

Bernanke, B.S. and Kuttner, K.N. (2005) What Explains the Stock Market’s Reaction to Federal Reserve Policy? Journal of Finance 60(3): 1221-1257.

Bernard, C., Cui, Z. and Mcleish, D. (2014) Convergence of the discrete variance swap in time-homogeneous diffusion models. Quantitative Finance Letters 2(1): 1-6.

Bernard, V.L. and Thomas, J.K. (1989) Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium? Journal of Accounting Research 27: 1-36.

Bernard, V.L. and Thomas, J.K. (1990) Evidence That Stock Prices Do Not Fully Reflect the Implications of Current Earnings for Future Earnings. Journal of Accounting and Economics 13(4): 305-340.

Bernardi, S., Leippold, M. and Lohre, H. (2018) Maximum Diversification Strategies along Commodity Risk Factors. European Financial Management 24(1): 53-78.

Bernstein, J. (1990) Jake Bernstein’s seasonal futures spreads: high-probability seasonal spreads for futures traders. Hoboken, NJ: John Wiley & Sons, Inc.

Bessembinder, H. (1992) Systematic risk, hedging pressure, and risk premiums in futures markets. Review of Financial Studies 5(4): 637-667.

Bessembinder, H. (1993) An empirical analysis of risk premia in futures markets. Journal of Futures Markets 13(6): 611-630.

Bessembinder, H. and Chan, K. (1992) Time-varying risk premia and forecastable returns in futures markets. Journal of Financial Economics 32(2): 169-193.

Bessembinder, H., Coughenour, J.F., Seguin, P.J. and Smoller, M.M. (1995) Mean reversion in equilibrium asset prices: evidence from the futures term structure. Journal of Finance 50(1): 361-375.

Bessembinder, H. and Maxwell, W. (2008) Markets: Transparency and the Corporate Bond Market. Journal of Economic Perspectives 22(2): 217-234.

Bessembinder, H. and Seguin, P.J. (1993) Price volatility, trading volume, and market depth: Evidence from futures markets. Journal of Financial and Quantitative Analysis 28(1): 21-39.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Bester, A., Martinez, V.H. and Rosu, I. (2017) Cash Mergers and the Volatility Smile. Working Paper. Available online: https://ssrn.com/abstract= 1364491.

Beyaert, A., Garc´ıa-Solanes, J. and P´erez-Castej´on, J.J. (2007) Uncovered interest parity with switching regimes. Economic Modelling 24(2): 189-202.

Bharadwaj, A. and Wiggins, J.B. (2001) Box Spread and Put-Call Parity Tests for the S&P 500 Index LEAPS Market. Journal of Derivatives 8(4): 62-71.

Bhattacharya, U., Loos, B., Meyer, S. and Hackethal, A. (2017) Abusing ETFs. Review of Finance 21(3): 1217-1250.

Bhojraj, S. and Swaminathan, B. (2006) Macromomentum: Returns Predictability in International Equity Indices. Journal of Business 79(1): 429-451.

Bhushan, R. (1994) An Informational Efficiency Perspective on the Post-Earnings Announcement Drift. Journal of Accounting and Economics 18(1): 45-65.

Biais, B. and Foucault, T. (2014) HFT and market quality. Bankers, Markets & Investors 128: 5-19.

Biais, B., Foucault, T. and Moinas, S. (2014) Equilibrium Fast Trading. Working Paper. Available online: https://ssrn.com/abstract=2024360.

Bianchi, R.J., Drew, M. and Fan, J. (2015) Combining momentum with reversal in commodity futures. Journal of Banking & Finance 59: 423-444.

Biby, J.D., Modukuri, S. and Hargrave, B. (2001) Collateralized Borrowing via Dollar Rolls. In: Fabozzi, F.J. (ed.) The Handbook of Mortgage-Backed Securities. (5th ed.) New York, NY: McGraw-Hill, Inc.

Bielecki, T.R., Brigo, D. and Patras, F. (2011) Credit Risk Frontiers: Subprime Crisis, Pricing and Hedging, CVA, MBS, Ratings, and Liquidity. Hoboken, NJ: John Wiley & Sons, Inc.

Bielecki, T., Jeanblanc, M. and Rutkowski, M. (2007) Hedging of basket credit derivatives in the Credit Default Swap market. Journal of Credit Risk 3(1): 91-132.

Bielecki, T., Vidozzi, A. and Vidozzi, L. (2008) A Markov copulae approach to pricing and hedging of credit index derivatives and ratings triggered step-up bonds. Journal of Credit Risk 4(1): 47-76.

Bieri, D.S. and Chincarini, L.B. (2004) Riding the Yield Curve: Diversification of Strategies. Working Paper. Available online: https://ssrn.com/ abstract=547682.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Bieri, D.S. and Chincarini, L.B. (2005) Riding the Yield Curve: A Variety of Strategies. Journal of Fixed Income 15(2): 6-35.

Bierwag, G.O. (1979) Dynamic portfolio immunization policies. Journal of Banking & Finance 3(1): 23-41.

Bierwag, G.O. and Kaufman, G. (1978) Bond Portfolio Strategy Simulations: A Critique. Journal of Financial and Quantitative Analysis 13(3): 519-525.

Billingsley, R.S. and Chance, D.M. (1985) Options Market Efficiency and the Box Spread Strategy. Financial Review 20(4): 287-301.

Billingsley, R.S. and Chance, D.M. (1988) The pricing and performance of stock index futures spreads. Journal of Futures Markets 8(3): 303-318.

Bilson, J.F.O. (1981) The “Speculative Efficiency” Hypothesis. Journal of Business 54(3): 435-451.

Birari, A. and Rode, M. (2014) Edge Ratio of Nifty for Last 15 Years on Donchian Channel. SIJ Transactions on Industrial, Financial & Business Management (IFBM) 2(5): 247-254.

Bird, R., Liem, H. and Thorp, S. (2014) Infrastructure: Real Assets and Real Returns. European Financial Management 20(4): 802-824.

Bitsch, F., Buchner, A. and Kaserer, C. (2010) Risk, Return and Cash Flow Characteristics of Infrastructure Fund Investments. EIB Papers 15(1): 106- 136.

Bjornson, B. and Carter, C.A. (1997) New Evidence on Agricultural Commodity Return Performance under Time-Varying Risk. American Journal of Agricultural Economics 79(3): 918-930.

Black, F. (1972) Capital Market Equilibrium with Restricted Borrowing. Journal of Business 45(3): 444-455.

Black, F. and Litterman, R. (1991) Asset allocation: Combining investors’ views with market equilibrium. Journal of Fixed Income 1(2): 7-18.

Black, F. and Litterman, R. (1992) Global portfolio optimization. Financial Analysts Journal 48(5): 28-43.

Black, F. and Scholes, M. (1973) The pricing of options and corporate liabilities. Journal of Political Economy 81(3): 637-659.

Blake, M.L. and Catlett, L. (1984) Cross Hedging Hay Using Corn Futures: An Empirical Test. Western Journal of Agricultural Economics 9(1): 127-134.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Blanc-Brude, F., Hasan, M. and Whittaker, T. (2016) Benchmarking infrastructure project finance: Objectives, roadmap, and recent progress. Journal of Alternative Investments 19(2): 7-18.

Blanc-Brude, F., Whittaker, T. and Wilde, S. (2017) Searching for a listed infrastructure asset class using mean-variance spanning. Financial Markets and Portfolio Management 31(2): 137-179.

Blanchard, O.J. and Gali, J. (2007) The Macroeconomic Effects of Oil Shocks: Why are the 2000s So Different from the 1970s? Working Paper. Available online: http://www.nber.org/papers/w13368.pdf.

Blanchard, O.J. and Riggi, M. (2013) Why are the 2000s so different from the 1970s? A structural interpretation of changes in the macroeconomic effects of oil prices. Journal of the European Economic Association 11(5): 1032-1052.

Blank, S.C. (1984) Cross Hedging Australian Cattle. Australian Journal of Agricultural Economics 28(2-3): 153-162.

Blitz, D., Huij, J., Lansdorp, S. and Verbeek, M. (2013) Short-term residual reversal. Journal of Financial Markets 16(3): 477-504.

Blitz, D., Huij, J. and Martens, M. (2011) Residual Momentum. Journal of Empirical Finance 18(3): 506-521.

Blitz, D.C. and van Vliet, P. (2007) The Volatility Effect: Lower Risk without Lower Return. Journal of Portfolio Management 34(1): 102-113.

Blitz, D. and Van Vliet, P. (2008) Global Tactical Cross Asset Allocation: Applying Value and Momentum Across Asset Classes. Journal of Portfolio Management 35(1): 23-28.

Block, R.L. (2011) Investing in REITs: Real Estate Investment Trusts. New York, NY: Bloomberg Press.

Bloesch, J. and Gourio, F. (2015) The effect of winter weather on U.S. economic activity. Federal Reserve Bank of Chicago, Economic Perspectives 39(1): 1-20.

Bloom, L., Easley, D. and O’Hara, M. (1994) Market Statistics and Technical Analysis: The Role of Volume. Journal of Finance 49(1): 153-181.

Blundell, L. (2006) Infrastructure investment: On the up. Property Australia 20(9): 20-22.

Bobey, B. (2010) The Effects of Default Correlation on Corporate Bond Credit Spreads. Working Paper. Available online: https://ssrn.com/abstract= 1510170.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Bodie, Z. (1983) Commodity Futures as a Hedge against Inflation. Journal of Portfolio Management 9(3): 12-17.

Bodie, Z., Kane, A. and Marcus, A.J. (1996) Investments. New York, NY: McGraw-Hill, Inc.

Bodie, Z. and Rosansky, V.I. (1980) Risk and Return in Commodity Futures. Financial Analysts Journal 36(3): 27-39.

Bogomolov, T. (2013) Pairs trading based on statistical variability of the spread process. Quantitative Finance 13(9): 1411-1430.

Bohlin, S. and Strickland, G. (2004) Climbing the Ladder: How to Manage Risk in Your Bond Portfolio. American Association of Individual Investors Journal, July 2004, pp. 5-8.

Bol, G., Rachev, S.T. and W¨urth, R. (eds.) (2009) Risk Assessment: Decisions in Banking and Finance. Heidelberg, Germany: Physica-Verlag.

Bollen, N.P.B. and Busse, J.A. (2005) Short-Term Persistence in Mutual Fund Performance. Review of Financial Studies 18(2): 569-597.

Bollen, J. and Mao, H. (2011) Twitter mood as a stock market predictor. Computer 44(10): 91-94.

Bollen, J., Mao, H. and Zeng, X. (2011) Twitter mood predicts the stock market. Journal of Computational Science 2(1): 1-8.

Bollen, N.P.B. and Whaley, R. (2004) Does Net Buying Pressure Affect the Shape of Implied Volatility Functions? Journal of Finance 59(2): 711-754.

Bollerslev, T., Gibson, M. and Zhou, H. (2011) Dynamic estimation of volatility risk premia and investor risk aversion from option-implied and realized volatilities. Journal of Econometrics 160(1): 235-245.

Bologna, P. and Cavallo, L. (2002) Does the Introduction of Index Futures Effectively Reduce Stock Market Volatility? Is the Futures Effect Immediate? Evidence from the Italian Stock Exchange Using GARCH. Applied Financial Economics 12(3): 183-192.

Bond, M.T. and Seiler, M.J. (1998) Real Estate Returns and Inflation: An Added Variable Approach. Journal of Real Estate Research 15(3): 327-338.

Bondarenko, O. (2014) Why Are Put Options So Expensive? Quarterly Journal of Finance 4(3): 1450015.

Booth, L.D. (1987) The dividend tax credit and Canadian ownership objectives. Canadian Journal of Economics 20(2): 321-339.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Booth, L.D. and Johnston, D.J. (1984) The ex-dividend day behavior of Canadian stock prices: Tax changes and clientele effects. Journal of Finance 39(2): 457-476.

Booth, J.R., Smith, R.L. and Stolz, R.W. (1984) The Use of Interest Rate Futures by Financial Institutions. Journal of Bank Research 15(1): 15-20.

Borovkova, S. and Geman, H. (2006) Seasonal and stochastic effects in commodity forward curves. Review of Derivatives Research 9(2): 167-186.

Bos, R. (2000) Index Calculation Primer. New York, NY: Standard and Poor’s Quantitative Services.

Bos, M., Carter, S. and Skiba, P.M. (2012) The Pawn Industry and Its Customers: The United States and Europe. Working Paper. Available online: https://ssrn.com/abstract=2149575.

Boscher, H. and Ward, I. (2002) Long or short in CDOs. Risk, June 2002, pp. 125-129.

Bossu, S. (2006) Introduction to Variance Swaps. Wilmott Magazine, March 2006, pp. 50-55.

Boudoukh, J., Richardson, M. and Whitelaw, R.F. (1994) Industry Returns and the Fisher Effect. Journal of Finance 49(5): 1595-1615.

Boudoukh, J., Whitelaw, R., Richardson, M. and Stanton, R. (1997) Pricing Mortgage-Backed Securities in a Multifactor Interest Rate Environment: A Multivariate Density Estimation Approach. Review of Financial Studies 10(2): 405-446.

Boulos, N. and Swanson, P.E. (1994) Interest Rate Parity in Times of Turbulence: The Issue Revisited. Journal of Financial and Strategic Decisions 7(2): 43-52.

Bouman, F.J.A. and Houtman, R. (1988) Pawnbroking as an Instrument of Rural Banking in the Third World. Economic Development and Cultural Change 37(1): 69-89.

Bouoiyour, J., Selmi, R. and Tiwari, A.K. (2015) Is Bitcoin business income or speculative foolery? New ideas through an improved frequency domain analysis. Annals of Financial Economics 10(1): 1-23.

Bouoiyour, J., Selmi, R., Tiwari, A.K. and Olayeni, O.R. (2016) What drives Bitcoin price? Economics Bulletin 36(2): 843-850.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Bouri, E., Gupta, R., Tiwari, A.K. and Roubaud, D. (2017a) Does Bitcoin hedge global uncertainty? Evidence from wavelet-based quantile-in-quantile regressions. Finance Research Letters 23: 87-95.

Bouri, E., Moln´ar, P., Azzi, G., Roubaud, D. and Hagfors, L.I. (2017b) On the hedge and safe haven properties of Bitcoin: Is it really more than a diversifier? Finance Research Letters 20: 192-198.

Bouzoubaa, M. and Osseiran, A. (2010) Exotic options and hybrids: a Guide to Structuring, Pricing and Trading. Chichester, UK: John Wiley & Sons, Ltd.

Bowen, D.A. and Hutchinson, M.C. (2016) Pairs trading in the UK equity market: Risk and return. European Journal of Finance 22(14): 1363-1387.

Bowen, D., Hutchinson, M.C. and O’Sullivan, N. (2010) High frequency equity pairs trading: Transaction costs, speed of execution and patterns in returns. Journal of Trading 5(3): 31-38.

Bowsher, N. (1979) Repurchase Agreements. Federal Reserve Bank of St. Louis Review 61(9): 17-22.

Boyarchenko, N., Fuster, A. and Lucca, D.O. (2014) Understanding Mortgage Spreads. Federal Reserve Bank of New York Staff Reports, No. 674. Available online:

https://www.newyorkfed.org/medialibrary/media/research/staff\_ reports/sr674.pdf.

Boyd, J.H., Hu, J. and Jagannathan, R. (2005) The Stock Market’s Reaction to Unemployment News: Why Bad News Is Usually Good for Stocks. Journal of Finance 60(2): 649-672.

Boyd, N.E. and Mercer, J.M. (2010) Gains from Active Bond Portfolio Management Strategies. Journal of Fixed Income 19(4): 73-83.

Boyle, P.P. (1978) Immunization under stochastic models of the term structure. Journal of the Institute of Actuaries 105(2): 177-187.

Bozdog, D., Florescu, I., Khashanah, K. and Wang, J. (2011) Rare Events Analysis of High-Frequency Equity Data. Wilmott Magazine 2011(54): 74-81.

Bozic, M. and Fortenbery, T.R. (2012) Creating Synthetic Cheese Futures: A Method for Matching Cash and Futures Prices in Dairy. Journal of Agribusiness 30(2): 87-102.

Brandvold, M., Moln´ar, P., Vagstad, K. and Valstad, O.C.A. (2015) Price discovery on Bitcoin exchanges. Journal of International Financial Markets, Institutions and Money 36: 18-35.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Branger, N. and Schlag, C. (2004) Why is the Index Smile So Steep? Review of Finance 8(1): 109-127.

Brazil, A.J. (1988) Citicorp’s mortgage valuation model: Option-adjusted spreads and option-based durations. Journal of Real Estate Finance and Economics 1(2): 151-162.

Breeden, D.T. and Litzenberger, R.H. (1978) Prices of state-contingent claims implicit in option prices. Journal of Business 51(4): 621-651.

Brennan, M.J. and Schwartz, E.S. (1977) Convertible Bonds: Valuation and Optimal Strategies for Call and Conversion. Journal of Finance 32(5): 1699- 1715.

Brennan, M.J. and Schwartz, E.S. (1985) Determinants of GNMA Mortgage Prices. Real Estate Economics 13(3): 209-228.

Brennan, M.J. and Schwartz, E.S. (1988) The case for convertibles. Journal of Applied Corporate Finance 1(2): 55-64.

Brenner, M., Subrahmanyam, M.G. and Uno, J. (1989) Stock index futures arbitrage in the Japanese markets. Japan and the World Economy 1(3): 303- 330.

Brezigar-Masten, A. and Masten, P. (2012) CART-based selection of bankruptcy predictors for the logit model. Expert Systems with Applications 39(11): 10153-10159.

Bri\`ere, M., Oosterlinck, K. and Szafarz, A. (2015) Virtual currency, tangible return: Portfolio diversification with bitcoin. Journal of Asset Management 16(6): 365-373.

Briys, E. and Solnik, B. (1992) Optimal currency hedge ratios and interest rate risk. Journal of International Money and Finance 11(5): 431-445.

Broadie, M. and Jain, A. (2008) The effect of jumps and discrete sampling on volatility and variance swaps. International Journal of Theoretical and Applied Finance 11(8): 761-797.

Brock, W., Lakonishock, J. and LeBaron, B. (1992) Simple technical trading rules and the stochastic properties of stock returns. Journal of Finance 47(5): 1731-1764.

Brockett, P., Golden, L.L., Wen, M. and Yang, C. (2010) Pricing weather derivatives using the indifference pricing approach. North American Actuarial Journal 13(3): 303-315.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Brockett, P.L., Wang, M. and Yang, C. (2005) Weather Derivatives And Weather Risk Management. Risk Management and Insurance Review 8(1): 127-140.

Brody, D., Syroka, J. and Zervos, M. (2002) Dynamical pricing of weather derivatives. Quantitative Finance 2(3): 189-198.

Brogaard, J. and Garriott, C. (2018) High-Frequency Trading Competition. Working Paper. Available online: https://ssrn.com/abstract=2435999.

Brogaard, J., Hagstr¨omer, B., Nord´en, L. and Riordan, R. (2015) Trading Fast and Slow: Colocation and Liquidity. Review of Financial Studies 28(12): 3407-3443.

Brogaard, J., Hendershott, T. and Riordan, R. (2014) High-Frequency Trading and Price Discovery. Review of Financial Studies 27(8): 2267-2306.

Brooks, J. (2017) A Half Century of Macro Momentum. Working Paper. Available online: https://www.aqr.com/-/media/AQR/Documents/Insights/White-Papers/ A-Half-Century-of-Macro-Momentum.pdf.

Brooks, C. and Chong, J. (2001) The Cross-Currency Hedging Performance of Implied Versus Statistical Forecasting Models. Journal of Futures Markets 21(11): 1043-1069.

Brooks, C., Davies, R.J. and Kim, S.S. (2007) Cross Hedging with Single Stock Futures. Assurances et Gestion des Risques 74(4): 473-504.

Brooks, C., Henry, O.T. and Persand, G. (2002) The Effect of Asymmetries on Optimal Hedge Ratios. Journal of Business 75(2): 333-352.

Brooks, J. and Moskowitz, T.J. (2017) Yield Curve Premia. Working Paper. Available online: https://ssrn.com/abstract=2956411.

Brown, D. (1999) The Determinants of Expected Returns on Mortgage-backed Securities: An Empirical Analysis of Option-adjusted Spreads. Journal of Fixed Income 9(2): 8-18.

Brown, P. and Clarke, A. (1993) The Ex-Dividend Day Behaviour of Australian Share Prices Before and After Dividend Imputation. Australian Journal of Management 18(1): 1-40.

Brown, D.C., Davies, S. and Ringgenberg, M. (2018) ETF Arbitrage and Return Predictability. Working Paper. Available online: https://ssrn.com/ abstract=2872414.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Brown, S.J., Goetzmann, W., Ibbotson, R.G. and Ross, S.A. (1992) Survivorship Bias in Performance Studies. Review of Financial Studies 5(4): 553-580.

Brown, S.J., Grundy, B.D., Lewis, C.M. and Verwijmeren, P. (2012) Convertibles and hedge funds as distributors of equity exposure. Review of Financial Studies 25(10): 3077-3112.

Brown, K.C. and Raymond, M.V. (1986) Risk arbitrage and the prediction of successful corporate takeovers. Financial Management 15(3): 54-63.

Browne, S. (2000) Risk-constrained dynamic active portfolio management. Management Science 46(9): 1188-1199.

Br¨uck, E. and Fan, Y. (2017) Smart Beta In Global Government Bonds And Its Risk Exposure. Working Paper. Available online: https://www.cfasociety.org/France/Documents/QuantAwards2017\_ Etienne%20BRUECK%20and%20Yuanting%20FAN\_EDHEC.pdf.

Bruder, B., Dao, T.-L., Richard, R.-J. and Roncalli, T. (2013) Trend Filtering Methods for Momentum Strategies. Working Paper. Available online: https: //ssrn.com/abstract=2289097.

Brunnermeier, M.K., Nagel, S. and Pedersen, L.H. (2008) Carry Trades and Currency Crashes. NBER Macroeconomics Annual 23(1): 313-347.

Bu, Q. and Lacey, N. (2007) Exposing Survivorship Bias in Mutual Fund Data. Journal of Business and Economics Studies 13(1): 22-37.

Budish, E., Cramton, P. and Shim, J. (2015) The High-Frequency Trading Arms Race: Frequent Batch Auctions as a Market Design Response. Quarterly Journal of Economics 130(4): 1547-1621.

Buetow, G.W. and Henderson, B.J. (2012) An empirical analysis of exchangetraded funds. Journal of Portfolio Management 38(4): 112-127.

Buetow, G.W. and Henderson, B.J. (2016) The VIX Futures Basis: Determinants and Implications. Journal of Portfolio Management 42(2): 119-130.

B¨uhler, W. and Kempf, A. (1995) DAX index futures: Mispricing and arbitrage in German markets. Journal of Futures Markets 15(7): 833-859.

Bundgaard, J. (2013) Coordination Rules as a Weapon in the War against Cross-Border Tax Arbitrage – The Case of Hybrid Entities and Hybrid Financial Instruments. Bulletin for International Taxation, April/May 2013, pp. 200-204.

Buraschi, A. and Jiltsov, A. (2005) Inflation Risk Premia and the Expectations Hypothesis. Journal of Financial Economics 75(2): 429-490.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Burnside, C., Eichenbaum, M., Kleshchelski, I. and Rebelo, S. (2011) Do peso problems explain the returns to the carry trade? Review of Financial Studies 24(3): 853-891.

Burnside, C., Eichenbaum, M. and Rebelo, S. (2007) The Returns to Currency Speculation in Emerging Markets. American Economic Review 97(2): 333-338.

Burnside, C., Eichenbaum, M. and Rebelo, S. (2008) Carry Trade: The Gains of Diversification. Journal of the European Economic Association 6(2/3): 581- 588.

Burnside, C., Eichenbaum, M. and Rebelo, S. (2011) Carry trade and momentum in currency markets. Annual Review of Financial Economics 3: 511-535.

Burtshell, X., Gregory, J. and Laurent, J.-P. (2009) A comparative analysis of CDO pricing models under the factor copula framework. Journal of Derivatives 16(4): 9-37.

Busch, T., Christensen, B.J. and Nielsen, M.Ø. (2011) The Role of Implied Volatility in Forecasting Future Realized Volatility and Jumps in Foreign Exchange, Stock, and Bond Markets. Journal of Econometrics 160(1): 48-57.

Buser, S.A. and Hess, P.J. (1986) Empirical determinants of the relative yields on taxable and tax-exempt securities. Journal of Financial Economics 17(2): 335-355.

Butterworth, D. and Holmes, P. (2010) Mispricing in stock index futures contracts: evidence for the FTSE 100 and FTSE mid 250 contracts. Applied Economics Letters 7(12): 795-801.

Buttimer, R.J., Hyland, D.C. and Sanders, A.B. (2005) REITs, IPO Waves, and Long-Run Performance. Real Estate Economics 33(1): 51-87.

Caginalp, G., DeSantis, M. and Sayrak, A. (2014) The nonlinear price dynamics of US equity ETFs. Journal of Econometrics 183(2): 193-201.

Calamos, N.P. (2003) Convertible Arbitrage: Insights and Techniques for Successful Hedging. Hoboken, NJ: John Wiley & Sons, Inc.

Caldeira, J. and Moura, G.V. (2013) Selection of a portfolio of pairs based on cointegration: A statistical arbitrage strategy. Working Paper. Available online: https://ssrn.com/abstract=2196391.

Callaghan, S.R. and Barry, C.B. (2003) Tax-induced trading of equity securities: Evidence from the ADR market. Journal of Finance 58(4): 1583-1611.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Callej´on, A.M., Casado, A.M., Fern´andez, M.A. and Pel´aez, J.I. (2013) A System of Insolvency Prediction for industrial companies using a financial alternative model with neural networks. International Journal of Computational Intelligence Systems 6(1): 29-37.

Campbell, J.Y. (1991) A Variance Decomposition for Stock Returns. Economic Journal 101(405): 157-179.

Campbell, J.Y., Chan, Y.L. and Viceira, L.M. (2003) A multivariate model of strategic asset allocation. Journal of Financial Economics 67(1): 41-80.

Campbell, S.D. and Diebold, F.X. (2005) Weather forecasting for weather derivatives. Journal of the American Statistical Association 100(469): 6-16.

Campbell, J.Y., Hilscher, J. and Sziglayi, J. (2008) In Search of Distress Risk. Journal of Finance 63(6): 2899-2939.

Campbell, J.Y., Shiller, R.J. and Viceira, L.M. (2009) Understanding Inflation-Indexed Bond Markets. In: Romer, D. and Wolfers, J. (eds.) Brookings Papers on Economic Activity. Washington, DC: Brookings Institution Press, pp. 79-120.

Campbell, J.Y., Sunderam, A. and Viceira, L.M. (2017) Inflation Bets or Deflation Hedges? The Changing Risks of Nominal Bonds. Critical Finance Review 6(2): 263-301.

Campbell, J.Y. and Viceira, L.M. (2004) Long-Horizon Mean-Variance Analysis: A User Guide. Working Paper. Available online: http://www.people. hbs.edu/lviceira/faj\_cv\_userguide.pdf.

Campbell, J.Y. and Viceira, L.M. (2005) The Term Structure of the Risk: Return Trade-Off. Financial Analysts Journal 61(1): 34-44.

Canina, L. and Figlewski, S. (1993) The Informational Content of Implied Volatility. Review of Financial Studies 6(3): 659-681.

Cao, C., Chen, Y., Liang, B. and Lo, A.W. (2013) Can hedge funds time market liquidity? Journal of Financial Economics 109(2): 493-516.

Cao, C., Goldie, B., Liang, B. and Petrasek, L. (2016) What Is the Nature of Hedge Fund Manager Skills? Evidence from the Risk-Arbitrage Strategy. Journal of Financial and Quantitative Analysis 51(3): 929-957.

Cao, M. and Wei, J. (2000) Pricing the weather. Risk, May 2000, pp. 67-70.

Cao, M. and Wei, J. (2004) Weather derivatives valuation and market price of weather risk. Journal of Futures Markets 24(11): 1065-1089.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Caplin, A. and Leahy, J. (2011) Trading Frictions and House Price Dynamics. Journal of Money, Credit and Banking 43(7): 283-303.

Capozza, D.R., Hendershott, P.H. and Mack, C. (2004) An Anatomy of Price Dynamics in Illiquid Markets: Analysis and Evidence from Local Housing Markets. Real Estate Economics 32(1): 1-32.

Carhart, M.M. (1997) Persistence in mutual fund performance. Journal of Finance 52(1): 57-82.

Carhart, M.M., Carpenter, J.N., Lynch, A.W. and Musto, D.K. (2002) Mutual Fund Survivorship. Review of Financial Studies 15(5): 1439-1463.

Carmona, R. and Cr´epey, S. (2010) Particle methods for the estimation of credit portfolio loss distributions. International Journal of Theoretical and Applied Finance 13(4): 577-602.

Carmona, R. and Durrleman, V. (2003) Pricing and Hedging Spread Options. SIAM Review 45(4): 627-685.

Carr, P. and Javaheri, A. (2005) The forward PDE for European options on stocks with fixed fractional jumps. International Journal of Theoretical and Applied Finance 8(2): 239-253.

Carr, P. and Lee, R. (2007) Realized volatility and variance: Options via swaps. Risk 20(5): 76-83.

Carr, P. and Lee, R. (2009) Volatility Derivatives. Annual Review of Financial Economics 1: 319-339.

Carr, P., Lee, R. and Wu, L. (2012) Variance swaps on time-changed L´evy processes. Finance and Stochastics 16(2): 335-355.

Carr, P. and Wu, L. (2009) Variance risk premiums. Review of Financial Studies 22(3): 1311-1341.

Carr, P. and Wu, L. (2016) Analyzing volatility risk and risk premium in option contracts: A new theory. Journal of Financial Economics 120(1): 1-20.

Carrasco, C.G. (2007) Studying the properties of the correlation trades. Working Paper. Available online: https://mpra.ub.uni-muenchen.de/22318/1/ MPRA\_paper\_22318.pdf.

Carrion, A. (2013) Very fast money: High-frequency trading on the NASDAQ. Journal of Financial Markets 16(4): 680-711.

Carrion, A. and Kolay, M. (2017) Trade Signing in Fast Markets. Working Paper. Available online: https://ssrn.com/abstract=2489868.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Carron, A.S. and Hogan, M. (1988) The option valuation approach to mortgage pricing. Journal of Real Estate Finance and Economics 1(2): 131-149.

Cartea, A. and Figueroa, M. (2005) Pricing in electricity markets: a mean reverting jump diffusion model with seasonality. Applied Mathematical Finance 12(4): 313-335.

Cartea, A. and Pedraz, C.G. (2012) How Much Should We Pay for Interconnecting Electricity Markets? A Real Options Approach. Energy Economics 34(1): 14-30.

Carter, C., Rausser, G. and Schmitz, A. (1983) Efficient asset portfolios and the theory of normal backwardation. Journal of Political Economy 91(2): 319- 331.

Casassus, J. and Collin-Dufresne, P. (2005) Stochastic convenience yield implied from commodity futures and interest rates. Journal of Finance 60(5): 2283-2331.

Case, K.E. and Shiller, R.J. (1987) Prices of Single Family Homes since 1970: New Indexes for Four Cities. Federal Reserve Bank of Boston, New England Economic Review, September-October 1987, pp. 45-56.

Case, K.E. and Shiller, R.J. (1989) The Efficiency of the Market for Single-Family Homes. American Economic Review 79(1): 125-137.

Case, K.E. and Shiller, R.J. (1990) Forecasting Prices and Excess Returns in the Housing Market. Real Estate Economics 18(3): 253-273.

Caskey, J.P. (1991) Pawnbroking in America: the Economics of a Forgotten Credit Market. Journal of Money, Credit and Banking 23(1): 85-99.

Cassano, M. and Sick, G. (2013) Valuation of a spark spread: an LM6000 power plant. European Journal of Finance 18(7-8): 689-714.

Castelino, M.G and Vora, A. (1984) Spread volatility in commodity futures: The length effect. Journal of Futures Markets 4(1): 39-46.

Cavaglia, S. and Vadim, M. (2002) Cross-Industry, Cross Country Allocation. Financial Analysts Journal 58(6): 78-97.

Cecchetti, S.G., Cumby, R.E. and Figlewski, S. (1988) Estimation of the Optimal Futures Hedge. Review of Economics and Statistics 70(4): 623-630.

Cerovi´c, S. and Pepi´c, M. (2011) Interest rate derivatives in developing coun- ˇ tries in Europe. Perspectives of Innovation in Economics and Business 9(3): 38-42.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Cerovi´c, S., Pepi´c, M., ˇ Cerovi´c, S. and ˇ Cerovi´c, N. (2014) Duration and con- ˇ vexity of bonds. Singidunum Journal of Applied Sciences 11(1): 53-66.

Cerrato, M. and Djennad, A. (2008) Dynamic Option Adjusted Spread and the Value of Mortgage Backed Securities. Working Paper. Available online: https://www.gla.ac.uk/media/media\_71226\_en.pdf.

Chaboud, A.P. and Wright, J.H. (2005) Uncovered interest parity: it works, but not for long. Journal of International Economics 66(2): 349-362.

Chaiyapo, N. and Phewchean, N. (2017) An application of Ornstein-Uhlenbeck process to commodity pricing in Thailand. Advances in Difference Equations 2017: 179.

Chakravarty, S., Gulen, H. and Mayhew, S. (2004) Informed Trading in Stock and Option Markets. Journal of Finance 59(3): 1235-1257.

Chalmers, J.M.R. (1998) Default Risk Cannot Explain the Muni Puzzle: Evidence from Municipal Bonds that are Secured by U.S. Treasury Obligations. Review of Financial Studies 11(2): 281-308.

Chambers, D.R., Foy, M., Liebner, J. and Lu, Q. (2014) Index Option Returns: Still Puzzling. Review of Financial Studies 27(6): 1915-1928.

Chan, E.P. (2013) Algorithmic Trading: Winning Strategies and Their Rationale. Hoboken, NJ: John Wiley & Sons, Inc.

Chan, A.W.H. and Chen, N.-F. (2007) Convertible bond underpricing: Renegotiable covenants, seasoning, and convergence. Management Science 53(11): 1793-1814.

Chan, K.C. and Chen, N.-F. (1991) Structural and Return Characteristics of Small and Large Firms. Journal of Finance 46(4): 1467-1484.

Chan, K. and Chung, Y.P. (1993) Intraday relationships among index arbitrage, spot and futures price volatility, and spot market volume: A transactions data test. Journal of Banking & Finance 17(4): 663-687.

Chan, K.C., Hendershott, P.H. and Sanders, A.B. (1990) Risk and Return on Real Estate: Evidence from Equity REITs. AREUEA Journal 18(4): 431-452.

Chan, K.C., Jegadeesh, N. and Lakonishok, J. (1996) Momentum Strategies. Journal of Finance 51(5): 1681-1713.

Chan, S.H., Leung, W.K. and Wang, K. (1998) Institutional Investment in REITs: Evidence and Implications. Journal of Real Estate Research 16(3): 357-374.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Chan, K.F., Treepongkaruna, S., Brooks, R. and Gray, S. (2011) Asset market linkages: Evidence from financial, commodity and real estate assets. Journal of Banking & Finance 35(6): 1415-1426.

Chance, D. (1994) Managed Futures and Their Role in Investment Portfolios. Charlottesville, VA: The Research Foundation of the Institute of Chartered Financial Analysts.

Chance, D.M. and Jordan, J.V. (1996) Duration, Convexity, and Time as Components of Bond Returns. Journal of Fixed Income 6(2): 88-96.

Chandra, P. (2003) Sigmoidal Function Classes for Feedforward Artificial Neural Networks. Neural Processing Letters 18(3): 205-215.

Chang, E.C., Cheng, J.W. and Pinegar, J.M. (1999) Does Futures Trading Increase Stock Market Volatility? The Case of the Nikkei Stock Index Futures Exchange. Journal of Banking & Finance 23(5): 727-753.

Chang, J.S. and Fang, H. (1990) An intertemporal measure of hedging effectiveness. Journal of Futures Markets 10(3): 307-321.

Chang, R.P., Ko, K.-C., Nakano, S. and Rhee, S.G. (2016) Residual Momentum and Investor Underreaction in Japan. Working Paper. Available online: http://sfm.finance.nsysu.edu.tw/php/Papers/CompletePaper/ 134-1136665035.pdf.

Chaput, J.S. and Ederington, L.H. (2003) Option Spread and Combination Trading. Journal of Derivatives 10(4): 70-88.

Chaput, J.S. and Ederington, L.H. (2005) Vertical Spread Design. Journal of Derivatives 12(3): 28-46.

Chaput, J.S. and Ederington, L.H. (2008) Ratio Spreads. Journal of Derivatives 15(3): 41-57.

Charupat, N. and Miu, P. (2011) The Pricing and Performance of Leveraged Exchange-Traded Funds. Journal of Banking & Finance 35(4): 966-977.

Chatterjee, S., Dhillon, U.S. and Ram´ırez, G.G. (1996) Resolution of Financial Distress: Debt Restructurings via Chapter 11, Prepackaged Bankruptcies, and Workouts. Financial Management 25(1): 5-18.

Chaudhuri, A. and De, K. (2011) Fuzzy support vector machine for bankruptcy prediction. Applied Soft Computing 11(2): 2472-2486.

Chaumont, S., Imkeller, P. and M¨uller, M. (2006) Equilibrium Trading of Climate and Weather Risk and Numerical Simulation in a Markovian Framework. Stochastic Environment Research and Risk Assessment 20(3): 184-205.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Chava, S. and Jarrow, R.A. (2004) Bankruptcy Prediction with Industry Effects. Review of Finance 8(4): 537-569.

Chaves, D.B. (2012) Eureka! A Momentum Strategy that Also Works in Japan. Working Paper. Available online: https://ssrn.com/abstract=1982100.

Chaves, D.B. and Viswanathan, V. (2016) Momentum and mean-reversion in commodity spot and futures markets. Journal of Commodity Markets 3(1): 39-53.

Che, Y.S. (2016) A study on the risk and return of option writing strategies (Ph.D. Thesis). HKBU Institutional Repository. Open Access Theses and Dissertations. 187. Hong Kong, China: Hong Kong Baptist University. Available online: https://repository.hkbu.edu.hk/etd\_oa/187/.

Che, S.Y.S. and Fung, J.K.W. (2011) The performance of alternative futures buy-write strategies. Journal of Futures Markets 31(12): 1202-1227.

Cheah, E.T. and Fry, J. (2015) Speculative Bubbles in Bitcoin markets? An Empirical Investigation into the Fundamental Value of Bitcoin. Economics Letters 130: 32-36.

Chen, M.Y. (2014) A high-order fuzzy time series forecasting model for internet stock trading. Future Generation Computer Systems 37: 461-467.

Chen, H.J., Chen, S.J., Chen, Z. and Li, F. (2017) Empirical Investigation of an Equity Pairs Trading Strategy. Management Science (forthcoming). DOI: https://doi.org/10.1287/mnsc.2017.2825.

Chen, A.H.Y., Chen, K.C. and Howell, S. (1999) An analysis of dividend enhanced convertible stocks. International Review of Economics and Finance 8(3): 327-338.

Chen, T.F., Chung, S.L. and Tsai, W.C. (2016) Option-Implied Equity Risk and the Cross-Section of Stock Returns. Financial Analysts Journal 72(6): 42-55.

Chen, S.-J., Hsieh, C., Vines, T.W. and Chiou, S. (1998) Macroeconomic Variables, Firm-Specific Variables and Returns to REITs. Journal of Real Estate Research 16(3): 269-278.

Chen, A.H., Kang, J. and Yang, B. (2005) A Model for Convexity-Based Cross-Hedges with Treasury Futures. Journal of Fixed Income 15(3): 68-79.

Chen, L., Lesmond, D.A. and Wei, J. (2007) Corporate Yield Spreads and Bond Liquidity. Journal of Finance 62(1): 119-149.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Chen, A.S., Leung, M.T. and Daouk, H. (2003) Application of neural networks to an emerging financial market: Forecasting and trading the Taiwan Stock Index. Computers & Operations Research 30(6): 901-923.

Chen, R.-R., Liu, B. and Cheng, X. (2010) Pricing the Term Structure of Inflation Risk Premia: Theory and Evidence from TIPS. Journal of Empirical Finance 17(4): 702-721.

Chen, Z., Mao, C.X. and Wang, Y. (2010) Why firms issue callable bonds: Hedging investment uncertainty. Journal of Corporate Finance 16(4): 588- 607.

Chen, G., Roberts, M.C. and Thraen, C.S. (2006) Managing dairy profit risk using weather derivatives. Journal of Agricultural and Resource Economics 31(3): 653-666.

Chen, A.H. and Selender, A.K. (1994) Determination of Swap Spreads: An Empirical Analysis. Cox School of Business Historical Working Papers, No. 170. Dallas, TX: Southern Methodist University. Available online: http:// scholar.smu.edu/business\_workingpapers/170.

Chen, F. and Sutcliffe, C. (2007) Better Cross Hedges With Composite Hedging? Hedging Equity Portfolios Using Financial and Commodity Futures. European Journal of Finance 18(6): 575-595.

Chen, H.-L., Yang, B., Wang, G., Liu, J., Xu, X., Wang, S.-J. and Liu D.- Y. (2011) A novel bankruptcy prediction model based on an adaptive fuzzy k-nearest neighbor method. Knowledge-Based Systems 24(8): 1348-1359.

Cheng, M. and Madhavan, A. (2010) The Dynamics of Leveraged and Inverse Exchange-Traded Funds. Journal of Investment Management 7(4): 43-62.

Cheng, I.-H. and Xiong, W. (2013) Why Do Hedgers Trade so Much? Working Paper. Available online: https://ssrn.com/abstract=2358762.

Chernenko, S. and Sunderam, A. (2016) Liquidity Transformation in Asset Management: Evidence from the Cash Holdings of Mutual Funds. Working Paper. Available online: http://www.nber.org/papers/w22391.

Chernov, M. and Mueller, P. (2012) The Term Structure of Inflation Expectations. Journal of Financial Economics 106(2): 367-394.

Cherry, J. (2004) The Limits of Arbitrage: Evidence from Exchange Traded Funds. Working Paper. Available online: https://ssrn.com/abstract= 628061.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Cheung, W. (2010) The Black-Litterman model explained. Journal of Asset Management 11(4): 229-243.

Cheung, C.S., Kwan, C.C.Y. and Sarkar, S. (2010) Bond Portfolio Laddering: A Mean-Variance Perspective. Journal of Applied Finance 20(1): 103-109.

Cheung, C.W., Kwan, C.C. and Yip, P.C. (1990) The hedging effectiveness of options and futures: a mean-gini approach. Journal of Futures Markets 10(1): 61-73.

Cheung, A., Roca, E. and Su, J.-J. (2015) Crypto-currency Bubbles: an Application of the Phillips-Shi-Yu (2013) Methodology on Mt. Gox Bitcoin Prices. Applied Economics 47(23): 2348-2358.

Chiang, T.C. and Jiang, C.X. (1995) Foreign exchange returns over short and long horizons. International Review of Economics & Finance 4(3): 267-282.

Chiang, M.H. and Wang, C.Y. (2002) The Impact of Futures Trading on Spot Index Volatility: Evidence from Taiwan Index Futures. Applied Economics Letters 9(6): 381-385.

Chidambaran, N.K., Fernando, C.S. and Spindt, P.A. (2001) Credit enhancement through financial engineering: Freeport McMoRan’s gold-denominated depositary shares. Journal of Financial Economics 60(2-3): 487-528.

Chin, J.Y.F., Prevost, A.K. and Gottesman, A.A. (2002) Contrarian investing in a small capitalization market: Evidence from New Zealand. Financial Review 37(3): 421-446.

Chinco, A. and Mayer, C. (2012) Distant speculators and asset bubbles in the housing market. Working Paper. Available online: http://www.econ.yale. edu/\~shiller/behfin/2012-04-11/Chinco\_Mayer.pdf.

Chinloy, P. (1989) The Probability of Prepayment. Journal of Real Estate Finance and Economics 2(4): 267-283.

Cho, M. (1996) House Price Dynamics: A Survey of Theoretical and Empirical Issues. Journal of Housing Research 7(2): 145-172.

Choi, M.S. (2011) Momentary exchange rate locked in a triangular mechanism of international currency. Applied Economics 43(16): 2079-2087.

Choi, D., Getmansky, M., Henderson, B. and Tookes, H. (2010) Convertible bond arbitrageurs as suppliers of capital. Review of Financial Studies 23(6): 2492-2522.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Choi, D., Getmansky, M. and Tookes, H. (2009) Convertible bond arbitrage, liquidity externalities, and stock prices. Journal of Financial Economics 91(2): 227-251.

Choi, H.I., Kwon, S.-H., Kim, J.Y. and Jung, D.-S. (2014) Commodity Futures Term Structure Model. Bulletin of the Korean Mathematical Society 51(6): 1791-1804.

Chong, E., Han, C. and Park, F.C. (2017) Deep learning networks for stock market analysis and prediction: Methodology, data representations, and case studies. Expert Systems with Applications 83: 187-205.

Chong, J. and Miffre, J. (2010) Conditional Correlation and Volatility in Commodity Futures and Traditional Asset Markets. Journal of Alternative Investments 12(3): 61-75.

Chordia, T., Goyal, A., Sadka, G., Sadka, R. and Shivakumar, L. (2009) Liquidity and the Post-Earnings-Announcement Drift. Financial Analysts Journal 65(4): 18-32.

Chordia, T. and Shivakumar, L. (2002) Momentum, Business Cycle, and Time-Varying Expected Returns. Journal of Finance 57(2): 985-1019.

Chordia, T. and Shivakumar, L. (2006) Earnings and price momentum. Journal of Financial Economics 80(3): 627-656.

Choro´s-Tomczyk, B., H¨ardle, W.K. and Okhrin, O. (2016) A semiparametric factor model for CDO surfaces dynamics. Journal of Multivariate Analysis 146: 151-163.

Choudhry, M. (2004) The credit default swap basis: analysing the relationship between cash and synthetic credit markets. Journal of Derivatives Use, Trading and Regulation 10(1): 8-26.

Choudhry, M. (2006) Revisiting the Credit Default Swap Basis: Further Analysis of the Cash and Synthetic Credit Market Differential. Journal of Structured Finance 11(4): 21-32.

Choudhry, M. (2007) Trading the CDS Basis: Illustrating Positive and Negative Basis Arbitrage Trades. Journal of Trading 2(1): 79-94.

Christensen, M. (1999) Duration and Convexity for Bond Portfolios. Finanzmarkt und Portfolio Management 13(1): 66-72.

Christensen, P.E. and Fabozzi, F.J. (1985) Bond Immunization: An Asset Liability Optimization Strategy. In: Fabozzi, F.J. and Pollack, I.M. (eds.) The Handbook of Fixed Income Securities. (2nd ed.) Homewood, IL: Dow Jones-Irwin, pp. 676-703.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Christensen, J.H.E. and Gillan, J.M. (2012) Could the U.S. Treasury Benefit from Issuing More TIPS? Federal Reserve Bank of San Francisco, Working Papers Series, No. 2011-16. Available online: https://www.frbsf.org/ economic-research/files/wp11-16bk.pdf.

Christensen, J.H.E., Lopez, J.A. and Rudebusch, G.D. (2010) Inflation Expectations and Risk Premiums in an Arbitrage-Free Model of Nominal and Real Bond Yields. Journal of Money, Credit, and Banking 42(6): 143-178.

Christensen, B.J. and Prabhala, N.R. (1998) The relation between implied and realized volatility. Journal of Financial Economics 50(2): 125-150.

Christiansen, C. and Lund, J. (2005) Revisiting the Shape of the Yield Curve: The Effect of Interest Rate Volatility. Working Paper. Available online: https://ssrn.com/abstract=264139.

Christie-David, R. and Chaudry, M. (2001) Coskewness and cokurtosis in futures markets. Journal of Empirical Finance 8(1): 55-81.

Christoffersen, S.E.K., G´eczy, C.C., Musto, D.K. and Reed, A.V. (2005) Crossborder Dividend Taxation and the Preferences of Taxable and Nontaxable Investors: Evidence From Canada. Journal of Financial Economics 78(1): 121-144.

Christoffersen, S.E.K., Reed, A.V., G´eczy, C.C. and Musto, D.K. (2003) The Limits to Dividend Arbitrage: Implications for Cross Border Investment. Working Paper. Available online: https://ssrn.com/abstract=413867.

Chua, C.T., Koh, W.T.H. and Ramaswamy, K. (2006) Profiting from Mean-Reverting Yield Curve Trading Strategies. Journal of Fixed Income 15(4): 20-33.

Chuang, H. (2015) Time Series Residual Momentum. Working Paper. Available online: http://www.econ.tohoku.ac.jp/econ/datascience/DDSR-DP/ no38.pdf.

Chuang, H. and Ho, H.-C. (2014) Implied Price Risk and Momentum Strategy. Review of Finance 18(2): 591-622.

Chui, A.C.W., Titman, S. and Wei, K.C.J. (2003a) The Cross-Section of Expected REIT Returns. Real Estate Economics 31(3): 451-479.

Chui, A.C.W., Titman, S. and Wei, K.C.J. (2003b) Intra-industry momentum: the case of REITs. Journal of Financial Markets 6(3): 363-387.

Chung, S.Y. (2000) Review of Macro Trading and Investment Strategies: Macroeconomic Arbitrage in Global Markets. Journal of Alternative Investments 3(1): 84-85.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Ciaian, P., Rajcaniova, M. and Kancs, D. (2015) The economics of BitCoin price formation. Applied Economics 48(19): 1799-1815.

Cirelli, S., Vitali, S., Ortobelli Lozza, S. and Moriggia, V. (2017) A conservative discontinuous target volatility strategy. Investment Management and Financial Innovations 14(2-1): 176-190.

Clare, A.D., Ioannides, M. and Skinner, F.S. (2000) Hedging Corporate Bonds with Stock Index Futures: A Word of Caution. Journal of Fixed Income 10(2): 25-34.

Clarida, R.H., Davis, J.M. and Pedersen, N. (2009) Currency carry trade regimes: Beyond the Fama regression. Journal of International Money and Finance 28(8): 1375-1389.

Clarida, R. and Waldman, D. (2007) Is Bad News About Inflation Good News for the Exchange Rate? Working Paper. Available online: http://www.nber. org/papers/w13010.pdf.

Clark, G.L. (2017) Financial intermediation, infrastructure investment and regional growth. Area Development and Policy 2(3): 217-236.

Clark, G.L., Monk, A.H.B., Orr, R. and Scott, W. (2012) The new Era of infrastructure investing. Pensions: An International Journal 17(2): 103-111.

Clark, T.E. and Terry, S.J. (2010) Time Variation in the Inflation Passthrough of Energy Prices. Journal of Finance 42(7): 1419-1433.

Clark, T.A. and Weinstein, M.I. (1983) The behavior of the common stock of bankrupt firms. Journal of Finance 38(2): 489-504.

Clarke, R.G., de Silva, H. and Thorley, S. (2006) Minimum-Variance Portfolios in the U.S. Equity Market. Journal of Portfolio Management 33(1): 10-24.

Clarke, R.G., de Silva, H. and Thorley, S. (2010) Know Your VMS Exposure. Journal of Portfolio Management 36(2): 52-59.

Clarke, R.G., de Silva, H. and Thorley, S. (2013) Fundamentals of Futures and Options. New York, NY: The Research Foundation of CFA Institute.

Clifford, C.P., Fulkerson, J.A. and Jordan, B.D. (2014) What Drives ETF Flows? Financial Review 49(3): 619-642.

Clinton, K. (1988) Transactions costs and covered interest arbitrage: Theory and evidence. Journal of Political Economy 96(2): 358-370.

Cochrane, J.H. (1999) Portfolio Advice for a Multifactor World. Federal Reserve Bank of Chicago, Economic Perspectives 23(3): 59-78.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Cochrane, J.H. and Piazzesi, M. (2005) Bond Risk Premia. American Economic Review 95(1): 138-160.

Coffey, N., Hrung, W.B. and Sarkar, A. (2009) Capital constraints, counterparty risk, and deviations from covered interest rate parity. Federal Reserve Bank of New York Staff Reports, No. 393. Available online: https://www.newyorkfed.org/medialibrary/media/research/staff\_ reports/sr393.pdf.

Cohen, G. (2005) The bible of options strategies: the definitive guide for practical trading strategies. Upper Saddle River, NJ: Financial Times Prentice Hall.

Cole, C.A., Kastens, T.L., Hampel, F.A. and Gow, L.R. (1999) A calendar spread trading simulation of seasonal processing spreads. In: Proceedings of the NCCC-134 Conference on Applied Commodity Price Analysis, Forecasting, and Market Risk Management. Available online: http://www.farmdoc. illinois.edu/nccc134/conf\_1999/pdf/confp14-99.pdf.

Cole, C.S. and Young, P.J. (1995) Modified duration and convexity with semiannual compounding. Journal of Economics and Finance 19(1): 1-15.

Colianni, S., Rosales, S. and Signorotti, M. (2015) Algorithmic Trading of Cryptocurrency Based on Twitter Sentiment Analysis. Working Paper. Available online: http://cs229.stanford.edu/proj2015/029\_report.pdf.

Collin-Dufresne, P. and Solnik, B. (2001) On the Term Structure of Default Premia in the Swap and LIBOR Markets. Journal of Finance 56(3): 1095- 1115.

Cong, J., Tan, K.S. and Weng, C. (2013) VAR-Based Optimal Partial Hedging. ASTIN Bulletin: The Journal of the IAA 43(3): 271-299.

Cong, J., Tan, K.S. and Weng, C. (2014) CVaR-Based Optimal Partial Hedging. Journal of Risk 16(3): 49-83.

Connor, G. and Leland, H. (1995) Cash Management for Index Tracking. Financial Analysts Journal 51(6): 75-80.

Connor, G. and Woo, M. (2004) An Introduction to hedge funds. Working Paper. Available online: http://eprints.lse.ac.uk/24675/1/dp477.pdf.

Conover, C.M., Jensen, G., Johnson, R. and Mercer, M. (2008) Sector Rotation and Monetary Conditions. Journal of Investing 28(1): 34-46.

Conover, C.M., Jensen, G.R., Johnson, R.R. and Mercer, J.M. (2010) Is Now the Time to Add Commodities to Your Portfolio? Journal of Investing 19(3): 10-19.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Conrad, J., Dittmar, R.F. and Ghysels, E. (2013) Ex Ante Skewness and Expected Stock Returns. Journal of Finance 68(1): 85-124.

Conrad, J.S., Hameed, A. and Niden, C. (1994) Volume and autocovariances in short-horizon individual security returns. Journal of Finance 49(4): 1305- 1329.

Conrad, J. and Kaul, G. (1998) An Anatomy of Trading Strategies. Review of Financial Studies 11(3): 489-519.

Cont, R. and Minca, A. (2013) Recovering Portfolio Default Intensities Implied by CDO Quotes. Mathematical Finance 23(1): 94-121.

Cook, T.Q. and LaRoche, R.B. (eds.) (1993) Instruments of the money market. (7th ed.) Richmond, Virginia: Federal Reserve Bank of Richmond.

Cook, T.Q. and Rowe, T.D. (eds.) (1986) Instruments of the money market. (6th ed.) Richmond, Virginia: Federal Reserve Bank of Richmond.

Cooper, T. (2010) Alpha Generation and Risk Smoothing Using Managed Volatility. Working Paper. Available online: https://ssrn.com/abstract= 1664823.

Cooper, M., Downs, D.H. and Patterson, G.A. (1999) Real Estate Securities and a Filter-based, Short-term Trading Strategy. Journal of Real Estate Research 18(2): 313-334.

Cooper, M.J., Gutierrez, R.C., Jr. and Hameed, A. (2004) Market States and Momentum. Journal of Finance 59(3): 1345-1365.

Cooper, I. and Priestley, R. (2008) Time-Varying Risk Premiums and the Output Gap. Review of Financial Studies 22(7): 2801-2833.

Copeland, T.E. and Galai, D. (1983) Information Effects on the bid-ask spread. Journal of Finance 38(5): 1457-1469.

Corbally, M. and Dang, P. (2002) Underlying Markets and Indexes. In: Banks, E. (ed.) Weather Risk Management: Market, Products and Applications. London, UK: Palgrave Macmillan.

Corbett, M. (2006) Find it, fix it, flip it! Make millions in real estate – one house at a time. New York, NY: Plume.

Cornell, B. and French, K.R. (1983) The pricing of stock index futures. Journal of Futures Markets 3(1): 1-14.

Cornelli, F. and Li, D.D. (2002) Risk Arbitrage in Takeovers. Review of Financial Studies 15(3): 837-868.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Corrado, C.J. and Miller, T.W., Jr. (2005) The forecast quality of CBOE implied volatility indexes. Journal of Futures Markets 25(4): 339-373.

Corrado, C.J. and Su, T. (1997) Implied volatility skews and stock return skewness and kurtosis implied by stock option prices. European Journal of Finance 3(1): 73-85.

Correia, M.M., Richardson, S.A. and Tuna, A.I. (2012) Value Investing in Credit Markets. Review of Accounting Studies 17(3): 572-609.

Cosandier, P.-A. and Lang, B.R. (1981) Interest rate parity tests: Switzerland and some major western countries. Journal of Banking & Finance 5(2): 187- 200.

Cousin, A. and Laurent, J. (2012) Dynamic Hedging of Synthetic CDO Tranches: Bridging the Gap between Theory and Practice. In: Bielecki, T.R., Brigo, D. and Patras, F. (eds.) Credit Risk Frontiers. Hoboken, NJ: John Wiley & Sons, Inc., Chapter 6.

Coval, J.D. and Shumway, T. (2001) Expected options returns. Journal of Finance 56(3): 983-1009.

Cover, T.M. (1984) An algorithm for maximizing expected log investment return. IEEE Transactions on Information Theory 30(2): 369-373.

Cox, D. (2015) Handbook of Anti Money Laundering. Chichester, UK: John Wiley & Sons, Ltd.

Crabbe, L.E. and Fabozzi, F.J. (2002) Corporate Bond Portfolio Management. Hoboken, NJ: John Wiley & Sons, Inc.

Creamer, G.G. and Freund, Y. (2007) A Boosting Approach for Automated Trading. Journal of Trading 2(3): 84-96.

Creamer, G.G. and Freund, Y. (2010) Automated Trading with Boosting and Expert Weighting. Quantitative Finance 10(4): 401-420.

Cremers, M. and Weinbaum, D. (2010) Deviations from Put-Call Parity and Stock Return Predictability. Journal of Financial and Quantitative Analysis 45(2): 335-367.

Creti, A., Jo¨ets, M. and Mignon, V. (2013) On the links between stock and commodity markets’ volatility. Energy Economics 37: 16-28.

Cross, R. and Kozyakin, V. (2015) Fact and fictions in FX arbitrage processes. Journal of Physics: Conference Series 585: 012015.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Cultrera, L. and Br´edart, X. (2015) Bankruptcy prediction: the case of Belgian SMEs. Review of Accounting and Finance 15(1): 101-119.

Czaja, M.-G., Kaufmann, P. and Scholz, H. (2013) Enhancing the profitability of earnings momentum strategies: The role of price momentum, information diffusion and earnings uncertainty. Journal of Investment Strategies 2(4): 3-57.

Dahlgran, R.A. (2000) Cross-hedging the cottonseed crush: A case study. Agribusiness 16(2): 141-158.

Daigler, R.T. (2007) Spread volume for currency futures. Journal of Economics and Finance 31(1): 12-19.

Daigler, R.T. and Copper, M. (1998) A Futures Duration-Convexity Hedging Method. Financial Review 33(4): 61-80.

Dale, A. and Currie, E. (2015) An alternative funding model for agribusiness research in Canada. Agricultural Sciences 6(9): 961-969.

Damghani, B.M. and Kos, A. (2013) De-arbitraging With a Weak Smile: Application to Skew Risk. Wilmott Magazine 2013(64): 40-49.

Damiani, D. (2012) The Case for Cash. CFA Institute Magazine 23(4): 8-9.

D’Amico, S., Kim, D. and Wei, M. (2018) Tips from TIPS: The Informational Content of Treasury Inflation-Protected Security Prices. Journal of Financial and Quantitative Analysis 53(1): 395-436.

Daniel, K. (2001) The Power and Size of Mean Reversion Tests. Journal of Empirical Finance 8(5): 493-535.

Daniel, K. and Moskowitz, T.J. (2016) Momentum crashes. Journal of Financial Economics 122(2): 221-247.

D’Antonio, L. (2008) Equity Collars as Alternative to Asset Allocation. Journal of Financial Service Professionals 62(1): 67-76.

Dao, T.-L. (2014) Momentum strategies with the L1 filter. Journal of Investment Strategies 3(4): 57-82.

Das, S. (2005) Credit Derivatives: Trading & Management of Credit & Default Risk. (3rd ed.) Hoboken, NJ: John Wiley & Sons, Inc.

da S. Gomes, G.S., Ludermir, T.B. and Lima, L.M.M.R. (2011) Comparison of new activation functions in neural network for forecasting financial time series. Neural Computing and Applications 20(3): 417-439.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Dash, R. and Dash, P.K. (2016) A hybrid stock trading framework integrating technical analysis with machine learning techniques. Journal of Finance and Data Science 2(1): 42-57.

Da Silva, A.S., Lee, W. and Pornrojnangkool, B. (2009) The Black-Litterman model for active portfolio management. Journal of Portfolio Management 35(2): 61-70.

Daumas, L.D. (2017) Hedging stocks through commodity indexes: a DCC-GARCH approach. Working Paper. Available online: https://impa.br/ wp-content/uploads/2017/11/RiO2017-PP\_FAiube.pdf.

Davidson, A.S., Herskovitz, M.D. and Van Drunen, L.D. (1988) The refinancing threshold pricing model: An economic approach to valuing MBS. Journal of Real Estate Finance and Economics 1(2): 117-130.

Davis, J.L. (1996) The cross-section of stock returns and survivorship bias: Evidence from delisted stocks. Quarterly Review of Economics and Finance 36(3): 365-375.

Davis, M. (2001) Pricing Weather Derivatives by Marginal Value. Quantitative Finance 1(3): 305-308.

Davis, M.H.A. (2006) Optimal Hedging with Basis Risk. In: Kabanov, Y., Liptser, R. and Stoyanov, J. (eds.) From Stochastic Calculus to Mathematical Finance. Berlin, Germany: Springer.

Davis, M. and Lleo, S. (2012) Fractional Kelly strategies in continuous time: Recent developments. In: MacLean, L.C. and Ziemba, W. (eds.) Handbook of the Fundamentals of Financial Decision Making. Singapore: World Scientific Publishing.

Davis, M. and Lo, V. (2001) Infectious defaults. Quantitative Finance 1(4): 382-387.

Deacon, M., Derry, A. and Mirfendereski, D. (2004) Inflation-indexed Securities: Bonds, Swaps and other Derivatives. Chichester, UK: John Wiley & Sons, Ltd.

Deardorff, A.V. (1979) One-Way Arbitrage and Its Implications for the Foreign Exchange Markets. Journal of Political Economy 87(2): 351-364.

de Boer, P.-T., Kroese, D.P., Mannor, S. and Rubinstein, R.Y. (2005) A Tutorial on the Cross-Entropy Method. Annals of Operations Research 134(1): 19-67.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

DeBondt, W.F.M. and Thaler, R.H. (1985) Does stock market overreact? Journal of Finance 40(3): 793-807.

De Carvalho, R.L., Dugnolle, P., Lu, X. and Moulin, P. (2014) Low-Risk Anomalies in Global Fixed Income: Evidence from Major Broad Markets. Journal of Fixed Income 23(4): 51-70.

Dechant, T. and Finkenzeller, K. (2013) How much into infrastructure? Evidence from dynamic asset allocation. Journal of Property Research 30(2): 103-127.

Dechario, T., Mosser, P., Tracy, J., Vickery, J. and Wright, J. (2010) A Private Lender Cooperative Model for Residential Mortgage Finance. Federal Reserve Bank of New York Staff Reports, No. 466. Available online: https://www.newyorkfed.org/medialibrary/media/research/staff\_ reports/sr466.pdf.

De Jong, A., Dutordoir, M. and Verwijmeren, P. (2011) Why do convertible issuers simultaneously repurchase stock? An arbitrage-based explanation. Journal of Financial Economics 100(1): 113-129.

De La Pe˜na, J.I., Garayeta, A. and Iturricastillo, I. (2017) Dynamic immunisation does not imply cash flow matching: a hard application to Spain. Economic Research – Ekonomska Istraˇzivanja 30(1): 238-255.

DeLisle, J., Doran, J. and Krieger, K. (2014) Volatility as an Asset Class: Holding VIX in a Portfolio. Working Paper. Available online: https://ssrn. com/abstract=2534081.

DeMaskey, A.L. (1995) A Comparison of the Effectiveness of Currency Futures and Currency Options in the Context of Foreign Exchange Risk Management. Managerial Finance 21(4): 40-51.

DeMaskey, A.L. (1997) Single and Multiple Portfolio Cross-Hedging with Currency Futures. Multinational Finance Journal 1(1): 23-46.

DeMaskey, A.L. and Pearce, J.A. (1998) Commodity and Currency Futures Cross-Hedging of ASEAN Currency Exposures. Journal of Transnational Management Development 4(1): 5-24.

Demeterfi, K., Derman, E., Kamal, M. and Zou, J. (1999) A guide to volatility and variance swaps. Journal of Derivatives 6(4): 9-32.

DeMiguel, V., Plyakha, Y., Uppal, R. and Vilkov, G. (2013) Improving Portfolio Selection Using Option-Implied Volatility and Skewness. Journal of Financial and Quantitative Analysis 48(6): 1813-1845.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

DeMoura, C.E., Pizzinga, A. and Zubelli, J. (2016) A pairs trading strategy based on linear state space models and the Kalman filter. Quantitative Finance 16(10): 1559-1573.

Dempster, M.A.H. and Jones, C.M. (2002) Can channel pattern trading be profitably automated? European Journal of Finance 8(3): 275-301.

Deng, Q. (2008) Volatility Dispersion Trading. Working Paper. Available online: https://ssrn.com/abstract=1156620.

Deng, S.-J., Johnson, B. and Sogomonian, A. (2001) Exotic electricity options and the valuation of electricity generation and transmission assets. Decision Support Systems 30(3): 383-392.

Deng, G., McCann, C. and Wang, O. (2012) Are VIX Futures ETPs Effective Hedges? Journal of Index Investing 3(3): 35-48.

Dennis, P. and Mayhew, S. (2002) Risk-Neutral Skewness: Evidence from Stock Options. Journal of Financial and Quantitative Analysis 37(3): 471- 493.

Dennis, P., Mayhew, S. and Stivers, C. (2006) Stock Returns, Implied Volatility Innovations, and the Asymmetric Volatility Phenomenon. Journal of Financial and Quantitative Analysis 41(2): 381-406.

Denton, J.W. and Hung, M.S. (1996) A comparison of nonlinear optimization methods for supervised learning in multilayer feedforward neural networks. European Journal of Operational Research 93(2): 358-368.

de Oliveira, F.A., Nobre, C.N. and Z´arate, L.E. (2013) Applying Artificial Neural Networks to prediction of stock price and improvement of the directional prediction index – Case study of PETR4, Petrobras, Brazil. Expert Systems with Applications 40(18): 7596-7606.

Depken, C.A., Hollans, H. and Swidler, S. (2009) An empirical analysis of residential property flipping. Journal of Real Estate Finance and Economics 39(3): 248-263.

Depken, C.A., Hollans, H. and Swidler, S. (2011) Flips, flops and foreclosures: Anatomy of a real estate bubble. Journal of Financial Economic Policy 3(1): 49-65.

Derman, E. and Kani, I. (1994) Riding on a Smile. Risk 7(2): 139-145.

de Roon, F.A., Nijman, T.E. and Veld, C. (1998) Pricing Term Structure Risk in Futures Markets. Journal of Financial and Quantitative Analysis 33(1): 139-157.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

de Roon, F.A., Nijman, T.E. and Veld, C. (2000) Hedging pressure effects in futures markets. Journal of Finance 55(3): 1437-1456.

Derwall, J., Huij, J., Brounen, D. and Marquering, W. (2009) REIT Momentum and the Performance of Real Estate Mutual Funds. Financial Analysts Journal 65(5): 24-34.

Derwall, J., Huij, J. and De Zwart, G.B. (2009) The Short-Term Corporate Bond Anomaly. Working Paper. Available online: https://ssrn.com/ abstract=1101070.

D’Este, R. (2014) The Effect of Stolen Goods Markets on Crime: Evidence from a Quasi-Natural Experiment. Working Paper. Available online: https://warwick.ac.uk/fac/soc/economics/research/workingpapers/ 2014/twerp\_1040b\_deste.pdf.

Detemple, J. and Rindisbacher, M. (2010) Dynamic Asset Allocation: Portfolio Decomposition Formula and Applications. Review of Financial Studies 23(1): 25-100.

Detlefsen, K. and H¨ardle, W.K. (2013) Variance swap dynamics. Quantitative Finance 13(5): 675-685.

Dewally, M., Ederington, L.H. and Fernando, C.S. (2013) Determinants of Trader Profits in Commodity Futures Markets. Review of Financial Studies 26(10): 2648-2683.

De Wit, I. (2010) International Diversification Strategies for Direct Real Estate. Journal of Real Estate Finance and Economics 41(4): 433-457.

De Wit, J. (2006) Exploring the CDS-Bond Basis. Working Paper. Available online: https://ssrn.com/abstract=1687659.

de Wit, E.R. and van der Klaauw, B. (2013) Asymmetric Information and List-Price Reductions in the Housing Market. Regional Science and Urban Economics 43(3): 507-520.

De Zwart, G., Markwat, T., Swinkels, L. and van Dijk, D. (2009) The economic value of fundamental and technical information in emerging currency markets. Journal of International Money and Finance 28(4): 581-604.

Dichev, I. (1998) Is the risk of bankruptcy a systematic risk? Journal of Finance 53(3): 1131-1147.

Diebold, F.X. and Li, C. (2002) Forecasting the term structure of government bond yields. Journal of Econometrics 130(2): 337-364.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Diebold, F.X., Rudebusch, G.D. and Aruoba, S.B. (2006) The macroeconomy and the yield curve: a dynamic latent factor approach. Journal of Econometrics 131(1-2): 309-338.

Ding, J.J. and Sherris, M. (2011) Comparison of market models for measuring and hedging synthetic CDO tranche spread risks. European Actuarial Journal 1(S2): 261-281.

Disatnik, D., Duchin, R. and Schmidt, B. (2014) Cash Flow Hedging and Liquidity Choices. Review of Finance 18(2): 715-748.

Dischel, B. (1998a) At last: A model for weather risk. Energy and Power Risk Management 11(3): 20-21.

Dischel, B. (1998b) Black-Scholes won’t do. Energy and Power Risk Management 11(10): 8-9.

Dischel, B. (1999) Shaping history for weather risk management. Energy and Power Risk Management 12(8): 13-15.

Do, B. and Faff, R. (2010) Does simple pairs trading still work? Financial Analysts Journal 66(4): 83-95.

Do, B. and Faff, R. (2012) Are pairs trading profits robust to trading costs? Journal of Financial Research 35(2): 261-287.

Doan, M.P., Alexeev, V. and Brooks, R. (2014) Concurrent momentum and contrarian strategies in the Australian stock market. Australian Journal of Management 41(1): 77-106.

Dobson, M.W.R. (1984) Global Investment Portfolios: The United Kingdom and Scandinavia. ICFA Continuing Education Series 1984(4): 56-60.

Doeswijk, R., Lam, T. and Swinkels, L. (2014) The Global Multi-Asset Market Portfolio, 1959-2012. Financial Analysts Journal 70(2): 26-41.

Doeswijk, R. and van Vliet, P. (2011) Global tactical sector allocation: a quantitative approach. Journal of Portfolio Management 28(1): 29-47.

Dolan, C.P. (1999) Forecasting the Yield Curve Shape. Journal of Fixed Income 9(1): 92-99.

Dolvin, S.D. (2009) ETFs: Arbitrage opportunities and market forecasting. Journal of Index Investing 1(1): 107-116.

Dolvin, S. and Kirby, J. (2011) Momentum Trading in Sector ETFs. Journal of Index Investing 2(3): 50-57.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Donchian, R.D. (1960) High finance in copper. Financial Analysts Journal 16(6): 133-142.

Dong, J.-C., Liu, J.-X., Wang, C.-H., Yuan, H. and Wang, W.-J. (2009) Pricing Mortgage-Backed Security: An Empirical Analysis. Systems Engineering Theory & Practice 29(12): 46-52.

Dong, Z. and Zhou, D.-X. (2008) Learning gradients by a gradient descent algorithm. Journal of Mathematical Analysis and Applications 341(2): 1018- 1027.

Donier, J. and Bouchaud, J.-P. (2015) Why Do Markets Crash? Bitcoin Data Offers Unprecedented Insights. PLoS ONE 10(10): e0139356.

Donninger, C. (2014) VIX Futures Basis Trading: The Calvados-Strategy 2.0. Working Paper. Available online: https://ssrn.com/abstract=2379985.

Donninger, C. (2015) Trading the Patience of Mrs. Yellen. A Short Vix-Futures Strategy for FOMC Announcement Days. Working Paper. Available online: https://ssrn.com/abstract=2544445.

Doran, J.S. and Krieger, K. (2010) Implications for Asset Returns in the Implied Volatility Skew. Financial Analysts Journal 66(1): 65-76.

Doran, J.S., Peterson, D.R. and Tarrant, B.C. (2007) Is there information in the volatility skew? Journal of Futures Markets 27(10): 921-959.

Dorfleitner, G. and Wimmer, M. (2010) The pricing of temperature futures at the Chicago Mercantile Exchange. Journal of Banking & Finance 34(6): 1360-1370.

Dornier, F. and Queruel, M. (2000) Caution to the wind. Energy and Power Risk Management 13(8): 30-32.

Doskov, N. and Swinkels, L. (2015) Empirical evidence on the currency carry trade, 1900-2012. Journal of International Money and Finance 51: 370-389.

Douglas, R. (ed.) (2007) Credit Derivative Strategies: New Thinking on Managing Risk and Return. New York, NY: Bloomberg Press.

Dowd, K. and Hutchinson, M. (2015) Bitcoin Will Bite the Dust. Cato Journal 35(2): 357-382.

Downing, C., Jaffee, D. and Wallace, N. (2009) Is the Market for Mortgage-Backed Securities a Market for Lemons? Review of Financial Studies 22(7): 2457-2494.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Doyle, J.T., Lundholm, R.J. and Soliman, M.T. (2006) The extreme future stock returns following I/B/E/S earnings surprises. Journal of Accounting Research 44(5): 849-887.

Draper, P., Faff, R.W. and Hillier, D. (2006) Do Precious Metals Shine? An Investment Perspective. Financial Analysts Journal 62(2): 98-106.

Dreyfus, S.E. (1990) Artificial neural networks, back propagation, and the Kelley-Bryson gradient procedure. Journal of Guidance, Control, and Dynamics 13(5): 926-928.

Driessen, J., Maenhout, P.J. and Vilkov, G. (2009) The Price of Correlation Risk: Evidence from Equity Options. Journal of Finance 64(3): 1377-1406.

Driessen, J., Nijman, T. and Simon, Z. (2017) The Missing Piece of the Puzzle: Liquidity Premiums in Inflation-Indexed Markets. Working Paper. Available online: https://ssrn.com/abstract=3042506.

Drobetz, W. (2001) How to Avoid the Pitfalls in Portfolio Optimization? Putting the Black-Litterman Approach at Work. Financial Markets and Portfolio Management 15(1): 59-75.

Drobny, S. (2006) Inside the House of Money: Top Hedge Fund Traders on Profiting in the Global Markets. Hoboken, NJ: John Wiley & Sons, Inc.

Droms, W.G. and Walker, D.A. (2001) Performance persistence of international mutual funds. Global Finance Journal 12(2): 237-248.

Du, W., Tepper, A. and Verdelhan, A. (2018) Deviations from Covered Interest Rate Parity. Journal of Finance (forthcoming). DOI: https://doi.org/10. 1111/jofi.12620. Available online: https://ssrn.com/abstract=2768207.

Duarte, J., Longstaff, F.A. and Yu, F. (2006) Risk and Return in Fixed-Income Arbitrage: Nickels in Front of a Steamroller? Review of Financial Studies 20(3): 769-811.

Dubil, R. (2011) Hedge Funds: Alpha, Beta and Replication Strategies. Journal of Financial Planning 24(10): 68-77.

Duca, E., Dutordoir, M., Veld, C. and Verwijmeren, P. (2012) Why are convertible bond announcements associated with increasingly negative issuer stock returns? An arbitrage based explanation. Journal of Banking & Finance 36(11): 2884-2899.

Duchin, R. (2010) Cash Holdings and Corporate Diversification. Journal of Finance 65(3): 955-992.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Dudley, W., Roush, J.E. and Steinberg, M. (2009) The Case for Tips: An Examination of the Costs and Benefits. Federal Reserve Bank of New York, Economic Policy Review 15(1): 1-17.

Duffie, D. (1996) Special repo rates. Journal of Finance 51(2): 493-526.

Duffie, D. (2004) Time to adapt copula methods for modelling credit risk correlation. Risk, April 2004, p. 77.

Duffie, D. (2017) The covered interest parity conundrum. Risk, May 2017. Available online: https://www.risk.net/4353726.

Duffie, D. and Gˆarleanu, N. (2001) Risk and Valuation of Collateralized Debt Obligations. Financial Analysts Journal 57(1): 41-59.

Duffie, D. and Huang, M. (1996) Swap Rates and Credit Quality. Journal of Finance 51(2): 921-949.

Duffie, D., Saita, L. and Wang, K. (2007) Multi-period corporate default prediction with stochastic covariates. Journal of Financial Economics 83(3): 635- 665.

Duffie, D. and Singleton, K.J. (1997a) Modeling term structures of defaultable bonds. Review of Financial Studies 12(4): 687-720.

Duffie, D. and Singleton, K.J. (1997b) An Econometric Model of the Term Structure of Interest Rate Swap Yields. Journal of Finance 52(4): 1287-1321.

DuJardin, P. (2015) Bankruptcy prediction using terminal failure processes. European Journal of Operational Research 242(1): 286-303.

Dukes, W.P., Frolich, C.J. and Ma, C.K. (1992) Risk arbitrage in tender offers. Journal of Portfolio Management 18(4): 47-55.

Dumas, B., Fleming, J. and Whaley, R. (1998) Implied Volatility Functions: Empirical Tests. Journal of Finance 53(6): 2059-2106.

Dunis, C., Laws, J. and Evans, B. (2006) Trading futures spreads. Applied Financial Economics 16(12): 903-914.

Dunis, C., Laws, J. and Evans, B. (2010) Trading and filtering futures spread portfolios. Journal of Derivatives & Hedge Funds 15(4): 274-287.

Dunis, C., Laws, J. and Rudy, J. (2013) Mean Reversion Based on Autocorrelation: A Comparison Using the S&P 100 Constituent Stocks and the 100 Most Liquid ETFs. ETF Risk, October 2013, pp. 36-41.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Dunn, K.B. and McConnell, J.J. (1981a) A Comparison of Alternative Models for Pricing GNMA Mortgage-Backed Securities. Journal of Finance 36(2): 471-484.

Dunn, K.B. and McConnell, J.J. (1981b) Valuation of GNMA Mortgage-Backed Securities. Journal of Finance 36(3): 599-616.

Dupire, B. (1994) Pricing with a smile. Risk 7(1): 18-20.

Dusak, K. (1973) Futures Trading and Investor Returns: An Investigation of Commodity Market Risk Premiums. Journal of Political Economy 81(6): 1387-1406.

Dutordoir, M., Lewis, C.M., Seward, J. and Veld, C. (2014) What we do and do not know about convertible bond financing. Journal of Corporate Finance 24: 3-20.

Dutt, H.R., Fenton, J., Smith, J.D. and Wang, G.H.K. (1997) Crop year influences and variability of the agricultural futures spreads. Journal of Futures Markets 17(3): 341-367.

Dwyer, G.P., Jr., Locke, P. and Yu, W. (1996) Index Arbitrage and Nonlinear dynamics Between the S&P 500 Futures and Cash. Review of Financial Studies 9(1): 301-332.

Dyhrberg, A.H. (2015) Bitcoin, gold and the dollar – a GARCH volatility analysis. Finance Research Letters 16: 85-92.

Dyhrberg, A.H. (2016) Hedging capabilities of bitcoin. Is it the virtual gold? Finance Research Letters 16: 139-144.

Dyl, E.A. and Joehnk, M.D. (1981) Riding the Yield Curve: Does it Work? Journal of Portfolio Management 7(3): 13-17.

Dyl, E.A. and Martin, S.A. (1986) Another Look at Barbells Versus Ladders. Journal of Portfolio Management 12(3): 54-59.

Dynkin, L., Hyman, J., Konstantinovsky, V. and Roth, N. (2001) Building an MBS Index: Conventions and Calculations. In: Fabozzi, F.J. (ed.) The Handbook of Mortgage-Backed Securities. (5th ed.) New York, NY: McGraw-Hill, Inc.

Dzikeviˇcius, A. and Sanranda, S. (2010) EMA versus SMA: Usage to forecast ˇ Stock Markets: The Case of S&P 500 and OMX Baltic Benchmark. Verslas: teorija ir praktika – Business: theory and practice 11(3): 248-255.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Easley, D., L´opez de Prado, M.M. and O’Hara, M. (2011) The microstructure of the ‘flash crash’: flow toxicity, liquidity crashes and the probability of informed trading. Journal of Portfolio Management 37(2): 118-128.

Easley, D., L´opez de Prado, M.M. and O’Hara, M. (2012) The volume clock: Insights into the high frequency paradigm. Journal of Portfolio Management 39(1): 19-29.

Eastman, A.M. and Lucey, B.M. (2008) Skewness and asymmetry in futures returns and volumes. Applied Financial Economics 18(10): 777-800.

Eberhart, A., Altman, E. and Aggarwal, R. (1999) The Equity Performance of Firms Emerging from Bankruptcy. Journal of Finance 54(5): 1855-1868.

Eberhart, A.C. and Sweeney, R.J. (1992) Does the Bond Market Predict Bankruptcy Settlements? Journal of Finance 47(3): 943-980.

Ebrahim, S. and Rahman, S. (2005) On the pareto-optimality of futures contracts over Islamic forward contracts: Implications for the emerging Muslim economies. Journal of Economic Behavior & Organization 56(2): 273-295.

Ederington, L.H. (1979) The hedging performance of the new futures markets. Journal of Finance 34(1): 157-170.

Edwards, D.W. (2009) Energy Trading & Investing: Trading, Risk Management and Structuring Deals in the Energy Market. New York, NY: McGraw-Hill, Inc.

Edwards, F.R. (1988) Futures Trading and Cash Market Volatility: Stock Index and Interest Rate Futures. Journal of Futures Markets 8(4): 421-439.

Edwards, R. and Magee, J. (1992) Technical Analysis of Stock Trends. New York, NY: New York Institute of Finance.

Edwards, F.R. and Park, J.M. (1996) Do Managed Futures Make Good Investments? Journal of Futures Markets 16(5): 475-517.

Edwards, S. and Susmel, R. (2003) Interest-Rate Volatility in Emerging Markets. Review of Economics and Statistics 85(2): 328-348.

Egginton, J.F., Van Ness, B.F. and Van Ness, R.A. (2016) Quote Stuffing. Financial Management 45(3): 583-608.

Ehlgen, J. (1998) Distortionary effects of the optimal Hodrick-Prescott filter. Economics Letters 61(3): 345-349.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Eichenbaum, M. and Evans, C.L. (1995) Some Empirical Evidence on the Effects of Shocks to Monetary Policy on Exchange Rates. Quarterly Journal of Economics 110(4): 975-1009.

Eichholtz, P.M.A., Hoesli, M., MacGregor, B.D. and Nanthakumaran, N. (1995) Real estate portfolio diversification by property type and region. Journal of Property Finance 6(3): 39-59.

Eisdorfer, A. and Misirli, E. (2015) Distressed Stocks in Distressed Times. Working Paper. Available online: https://ssrn.com/abstract=2697771.

Eisl, A., Gasser, S. and Weinmayer, K. (2015) Caveat Emptor: Does Bitcoin Improve Portfolio Diversification? Working Paper. Available online: https: //ssrn.com/abstract=2408997.

Elder, A. (2014) The New Trading for a Living. Hoboken, NJ: John Wiley & Sons, Inc.

Eldred, G.W. (2004) The Beginner’s Guide to Real Estate Investing. Hoboken, NJ: John Wiley & Sons, Inc.

Elias, R.S., Wahab, M.I.M. and Fang, L. (2016) The spark spread and clean spark spread option based valuation of a power plant with multiple turbines. Energy Economics 59: 314-327.

El Kalak, I. and Hudson, R. (2016) The effect of size on the failure probabilities of SMEs: An empirical study on the US market using discrete hazard model. International Review of Financial Analysis 43: 135-145.

Elliott, R., Siu, T. and Chan, L. (2007) Pricing volatility swaps under Heston’s stochastic volatility model with regime switching. Applied Mathematical Finance 14(1): 41-62.

Elliott, R.J., van der Hoek, J. and Malcolm, W.P. (2005) Pairs trading. Quantitative Finance 5(3): 271-276.

Elton, E.J., Gruber, M.J. and Blake, C.R. (1996a) The Persistence of Risk-Adjusted Mutual Fund Performance. Journal of Business 69(2): 133-157.

Elton, E.J., Gruber, M.J. and Blake, C.R. (1996b) Survivor Bias and Mutual Fund Performance. Review of Financial Studies 9(4): 1097-1120.

Elton, E.J., Gruber, M.J. and Rentzler, J.C. (1987) Professionally Managed, Publicly Traded Commodity Funds. Journal of Business 60(2): 175-199.

Emery, G.W. and Liu, Q. (2002) An analysis of the relationship between electricity and natural gas futures prices. Journal of Futures Markets 22(2): 95-122.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Engel, C. (1996) The Forward Discount Anomaly and the Risk Premium: A Survey of Recent Evidence. Journal of Empirical Finance 3(2): 123-192.

Engle, R.F. and Granger, C.W.J. (1987) Co-integration and error correction: Representation, estimation and testing. Econometrica 55(2): 251-276.

Engle, R. and Rosenberg, J. (2000) Testing the volatility term structure using option hedging criteria. Journal of Derivatives 8(1): 10-28.

Engle, R.F. and Watson, M.W. (1987) The Kalman Filter: applications to forecasting and rational-expectation models. In: Bewley, T.F. (ed.) Fifth World Conference: Advances in Econometrics, Vol. 1. Cambridge, UK: Cambridge University Press.

Eraker, B. (2009) The Volatility Premium. Working Paper. Available online: http://www.nccr-finrisk.uzh.ch/media/pdf/Eraker\_23-10.pdf.

Eraker, B. and Wu, Y. (2014) Explaining the Negative Returns to VIX Futures and ETNs: An Equilibrium Approach. Working Paper. Available online: https://ssrn.com/abstract=2340070.

Erb, C. and Harvey, C. (2006) The Strategic and Tactical Value of Commodity Futures. Financial Analysts Journal 62(2): 69-97.

Erickson, M., Goolsbee, A. and Maydew, E. (2003) How Prevalent is Tax Arbitrage? Evidence from the Market for Municipal Bonds. National Tax Journal 56(1): 259-270.

Ertugrul, M. and Giambona, E. (2011) Property Segment and REIT Capital Structure. Journal of Real Estate Finance and Economics 43(4): 505-526.

Espinoza, R.D. and Luccioni, L. (2002) Proper Risk Management: The Key To Successful Brownfield Development. WIT Transactions on Ecology and the Environment 55: 297-306.

Eun, C.S. and Sabherwal, S. (2003) Cross-border listings and price discovery: Evidence from U.S. listed Canadian stocks. Journal of Finance 58(2): 549-575.

Evans, M.D.D. (1998) Real Rates, Expected Inflation, and Inflation Risk Premia. Journal of Finance 53(1): 187-218.

Evans, C.L. and Marshall, D.A. (2007) Economic determinants of the nominal treasury yield curve. Journal of Monetary Economics 54(7): 1986-2003.

Faber, M. (2007) A Quantitative Approach to Tactical Asset Allocation. Journal of Wealth Management 9(4): 69-79.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Faber, M. (2015) Learning to Play Offense and Defense: Combining Value and Momentum from the Bottom Up, and the Top Down. Working Paper. Available online: https://ssrn.com/abstract=2669202.

Faber, M. (2016) The Trinity Portfolio: A Long-Term Investing Framework Engineered for Simplicity, Safety, and Outperformance. Working Paper. Available online: https://ssrn.com/abstract=2801856.

Fabozzi, F.J. (ed.) (2002) The Handbook of Financial Instruments. Hoboken, NJ: John Wiley & Sons, Inc.

Fabozzi, F.J. (2006a) Fixed Income Mathematics: Analytical & Statistical Techniques. New York, NY: McGraw-Hill, Inc.

Fabozzi, F.J. (ed.) (2006b) The Handbook of Mortgage-Backed Securities. New York, NY: McGraw-Hill, Inc.

Fabozzi, F.J. (2012a) Bond markets, analysis, and strategies. Upper Saddle River, NJ: Prentice Hall.

Fabozzi, F.J. (2012b) Institutional Investment Management: Equity and Bond Portfolio Strategies and Applications. Hoboken, NJ: John Wiley & Sons, Inc.

Fabozzi, F.J., Focardi, S.M. and Jonas, C. (2010) Investment Management after the Global Financial Crisis. Charlottesville, VA: The Research Foundation of CFA Institute.

Fabozzi, F.J. and Mann, S.V. (2010) Introduction to Fixed Income Analytics: Relative Value Analysis, Risk Measures, and Valuation. Hoboken, NJ: John Wiley & Sons, Inc.

Fabozzi, F.J., Martellini, L. and Priaulet, P. (2006) Advanced Bond Portfolio Management. Best Practices in Modeling and Strategies. Hoboken, NJ: John Wiley & Sons, Inc.

Falkenstein, E. and Hanweck, J. (1996) Minimizing Basis Risk from Non-Parallel Shifts in the Yield Curve. Journal of Fixed Income 6(1): 60-68.

Fama, E.F. (1984) Forward and spot exchange rates. Journal of Monetary Economics 14(3): 319-338.

Fama, E.F. (1996) Multifactor Portfolio Efficiency and Multifactor Asset Pricing. Journal of Financial and Quantitative Analysis 31(4): 441-465.

Fama, E.F. and French, K.R. (1987) Commodity futures prices: some evidence on forecast power, premiums, and the theory of storage. Journal of Business 60(1): 55-73.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Fama, E.F. and French, K.R. (1988) Business Cycles and the Behavior of Metals Prices. Journal of Finance 43(5): 1075-1093.

Fama, E.F. and French, K.R. (1992) The Cross-Section of Expected Stock Returns. Journal of Finance 47(2): 427-465.

Fama, E.F. and French, K.R. (1993) Common Risk Factors in the Returns on Stocks and Bonds. Journal of Financial Economics 33(1): 3-56.

Fama, E.F. and French, K.R. (1996) Multifactor Explanations of Asset Pricing Anomalies. Journal of Finance 51(1): 55-84.

Fama, E.F. and French, K.R. (1998) Value versus Growth: The International Evidence. Journal of Finance 53(6): 1975-1999.

Fama, E.F. and French, K.R. (2008) Dissecting Anomalies. Journal of Finance 63(4): 1653-1678.

Fama, E.F. and French, K.R. (2012) Size, Value and Momentum in International Stock Returns. Journal of Financial Economics 105(3): 457-472.

Fama, E.F. and Schwert, G.W. (1977) Asset returns and inflation. Journal of Financial Economics 5(2): 115-146.

Fass, S.M. and Francis, J. (2004) Where have all the hot goods gone? The role of pawnshops. Journal of Research in Crime and Delinquency 41(2): 156-179.

Fassas, A.P. (2011) Mispricing in stock index futures markets – the case of Greece. Investment Management and Financial Innovations 8(2): 101-107.

Fedorova, E., Gilenko, E. and Dovzhenko, S. (2013) Bankruptcy prediction for Russian companies: Application of combined classifiers. Expert Systems with Applications 40(18): 7285-7293.

Feldh¨utter, P. and Lando, D. (2008) Decomposing swap spreads. Journal of Financial Economics 88(2): 375-405.

Feldman, B.E. (2003) Investment Policy for Securitized and Direct Real Estate. Journal of Portfolio Management 29(5): 112-121.

Feldman, B. and Roy, D. (2004) Passive Options-based Investment Strategies: The Case of the CBOE S&P 500 BuyWrite Index. ETF and Indexing 38(1): 72-89.

Feldman, B. and Till, H. (2006) Backwardation and Commodity Futures Performance: Evidence from Evolving Agricultural Markets. Journal of Alternative Investments 9(3): 24-39.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

F´elix, J.A. and Rodr´ıguez, F.F. (2008) Improving moving average trading rules with boosting and statistical learning methods. Journal of Forecasting 27(5): 433-449.

Fengler, M.R., Herwartz, H. and Werner, C. (2012) A Dynamic Copula Approach to Recovering the Index Implied Volatility Skew. Journal of Financial Econometrics 10(3): 457-493.

Fenn, D.J., Howison, S.D., Mcdonald, M., Williams, S. and Johnson, N.F. (2009) The mirage of triangular arbitrage in the spot foreign exchange market. International Journal of Theoretical and Applied Finance 12(8): 1105-1123.

Fernandez-Perez, A., Frijns, B., Fuertes, A.M. and Miffre, J. (2018) The skewness of commodity futures returns. Journal of Banking & Finance 86: 143-158.

Fernandez-Perez, A., Fuertes, A.M. and Miffre, J. (2016) Is idiosyncratic volatility priced in commodity futures markets? International Review of Financial Analysis 46: 219-226.

Ferreira, S., Grammatikos, T. and Michala, D. (2016) Forecasting distress in Europe SME portfolios. Journal of Banking & Finance 64: 112-135.

Ferson, W. and Mo, H. (2016) Performance measurement with selectivity, market and volatility timing. Journal of Financial Economics 121(1): 93-110.

Fifield, S.G.M., Power, D.M. and Knipe, D.G.S. (2008) The performance of moving average rules in emerging stock markets. Applied Financial Economics 18(19): 1515-1532.

Figlewski, S., Chidambaran, N.K. and Kaplan, S. (1993) Evaluating the Performance of the Protective Put Strategy. Financial Analysts Journal 49(4): 46-56, 69.

Filipovi´c, D., Gourier, E. and Mancini, L. (2016) Quadratic variance swap models. Journal of Financial Economics 119(1): 44-68.

Finger, C.C. (1999) Conditional approaches for credit metrics portfolio distributions. Credit Metrics Monitor 2(1): 14-33.

Finkenzeller, K., Dechant, T. and Sch¨afers, W. (2010) Infrastructure: a new dimension of real estate? An asset allocation analysis. Journal of Property Investment & Finance 28(4): 263-274.

Finnerty, J.D. and Tu, M. (2017) Valuing Convertible Bonds: A New Approach. Business Valuation Review 36(3): 85-102.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Fiorenzani, S. (2006) Quantitative Methods for Electricity Trading and Risk Management: Advanced Mathematical and Statistical Methods for Energy Finance. London, UK: Palgrave Macmillan.

Firstenberg, P.M., Ross, S.A. and Zisler, R.C. (1988) Real estate: The whole story. Journal of Portfolio Management 14(3): 22-34.

Fishe, R.P.H., Janzen, J.P. and Smith, A. (2014) Hedging and Speculative Trading in Agricultural Futures Markets. American Journal of Agricultural Economics 96(2): 542-556.

Fisher, M. (2002) Special Repo Rates: An Introduction. Federal Reserve Bank of Atlanta, Economic Review 87(2): 27-43.

Fisher, G., Shah, R. and Titman, S. (2016) Combining Value and Momentum. Journal of Investment Management 14(2): 33-48.

Fisher, L. and Weil, R.L. (1971) Coping with the Risk of Interest-Rate Fluctuations: Returns to Bondholders from Na¨ıve and Optimal Strategies. Journal of Business 44(4): 408-431.

Fleckenstein, M. (2012) The Inflation-Indexed Bond Puzzle. Working Paper. Available online: https://ssrn.com/abstract=2180251.

Fleckenstein, M., Longstaff, F.A. and Lustig, H.N. (2013) Why Does the Treasury Issue TIPS? The TIPS-Treasury Bond Puzzle. Journal of Finance 69(5): 2151-2197.

Fleckenstein, M., Longstaff, F.A. and Lustig, H.N. (2017) Deflation Risk. Review of Financial Studies 30(8): 2719-2760.

Fleming, M.J. and Krishnan, N. (2012) The Microstructure of the TIPS Market. Federal Reserve Bank of New York, Economic Policy Review 18(1): 27-45.

Fleming, J., Ostdiek, B. and Whaley, R.E. (1995) Predicting stock market volatility: A new measure. Journal of Futures Markets 15(3): 265-302.

Fleming, M.J. and Sporn, J.R. (2013) Trading Activity and Price Transparency in the Inflation Swap Market. Federal Reserve Bank of New York, Economic Policy Review 19(1): 45-58.

Flint, E. and Mar´e, E. (2017) Fractional Black-Scholes option pricing, volatility calibration and implied Hurst exponents in South African context. South African Journal of Economic and Management Sciences 20(1): a1532.

Fong, H.G. and Vasicek, O.A. (1983). The tradeoff between return and risk in immunized portfolios. Financial Analysts Journal 39(5): 73-78.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Fong, H.G. and Vasicek, O.A. (1984) A Risk Minimizing Strategy for Portfolio Immunization. Journal of Finance 39(5): 1541-1546.

Fong, W.M. and Yong, L.H.M. (2005) Chasing trends: recursive moving average trading rules and internet stocks. Journal of Empirical Finance 12(1): 43-76.

Fontaine, J.-F. and Nolin, G. (2017) Measuring Limits of Arbitrage in Fixed-Income Markets. Staff Working Paper, No. 2017-44. Ottawa, Canada: Bank of Canada.

Fontana, A. (2010) The Persistent Negative CDS-Bond Basis during the 2007/08 Financial Crisis. Working Paper. Available online: http://www.unive.it/media/allegato/DIP/Economia/Working\_papers/ Working\_papers\_2010/WP\_DSE\_fontana\_13\_10.pdf.

Fontana, A. and Scheicher, M. (2016) An analysis of euro area sovereign CDS and their relation with government bonds. Journal of Banking & Finance 62: 126-140.

Fortin, M. and Khoury, N. (1984) Hedging Interest Rate Risks with Financial Futures. Canadian Journal of Administrative Sciences 1(2): 367-382.

Foster, G., Olsen, C. and Shevlin, T. (1984) Earnings releases, anomalies, and the behavior of security returns. Accounting Review 59(4): 574-603.

Foster, F.D. and Whiteman, C.H. (2002) Bayesian Cross Hedging: An Example from the Soybean Market. Australian Journal of Management 27(2): 95-122.

Frachot, A. (1996) A reexamination of the uncovered interest rate parity hypothesis. Journal of International Money and Finance 15(3): 419-437.

Frankel, J.A. (2006) The Effect of Monetary Policy on Real Commodity Prices. In: Campbell, J. (ed.) Asset Prices and Monetary Policy. Chicago, IL: University of Chicago Press, pp. 291-333.

Franken, J.R.V. and Parcell, J.L. (2003) Cash Ethanol Cross-Hedging Opportunities. Journal of Agricultural and Applied Economics 35(3): 509-516.

Frazzini, A. and Pedersen, L.H. (2014) Betting against Beta. Journal of Financial Economics 111(1): 1-25.

Frenkel, J.A. and Levich, R.M. (1975) Covered interest arbitrage: Unexploited profits? Journal of Political Economy 83(2): 325-338.

Frenkel, J.A. and Levich, R.M. (1981) Covered interest arbitrage in the 1970’s. Economics Letters 8(3): 267-274.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Frey, R. and Backhaus, J. (2008) Pricing and Hedging of Portfolio Credit Derivatives with Interacting Default Intensities. International Journal of Theoretical and Applied Finance 11(6): 611-634.

Frey, R. and Backhaus, J. (2010) Dynamic hedging of synthetic CDO tranches with spread risk and default contagion. Journal of Economic Dynamics and Control 34(4): 710-724.

Frey, R., McNeil, A. and Nyfeler, N. (2001) Copulas and Credit Models. Risk, October 2001, pp. 111-114.

Fridson, M.S. and Xu, X. (2014) Duration Targeting: No Magic for High-Yield Investors. Financial Analysts Journal 70(3): 28-33.

Friewald, N., Jankowitsch, R. and Subrahmanyam, M. (2012) Illiquidity, or Credit Deterioration: A Study of Liquidity in the U.S. Bond Market during Financial Crises. Journal of Financial Economics 105(1): 18-36.

Frino, A., Gallagher, D.R., Neubert, A.S. and Oetomo, T.N. (2004) Index Design and Implications for Index Tracking. Journal of Portfolio Management 30(2): 89-95.

Frino, A. and McKenzie, M. (2002) The pricing of stock index futures spreads at contract expiration. Journal of Futures Markets 22(5): 451-469.

Froot, K.A., Scharfstein, D.S. and Stein, J.C. (1993) Risk Management: Coordinating Corporate Investment and Financing Policies. Journal of Finance 48(5): 1629-1658.

Froot, K.A. and Thaler, R.H. (1990) Anomalies: Foreign Exchange. Journal of Economic Perspectives 4(3): 179-192.

Fry, J. and Cheah, E.T. (2016) Negative bubbles and shocks in cryptocurrency markets. International Review of Financial Analysis 47: 343-352.

Fu, F. (2009) Idiosyncratic Risk and the Cross-Section of Expected Stock Returns. Journal of Financial Economics 91(1): 24-37.

Fu, Y. and Qian, W. (2014) Speculators and Price Overreaction in the Housing Market. Real Estate Economics 42(4): 977-1007.

Fu, X., Sandri, M. and Shackleton, M.B. (2016) Asymmetric Effects of Volatility Risk on Stock Returns: Evidence from VIX and VIX Futures. Journal of Futures Markets 36(11): 1029-1056.

Fuertes, A., Miffre, J. and Fernandez-Perez, A. (2015) Commodity Strategies Based on Momentum, Term Structure, and Idiosyncratic Volatility. Journal of Futures Markets 35(3): 274-297.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Fuertes, A., Miffre, J. and Rallis, G. (2010) Tactical allocation in commodity futures markets: Combining momentum and term structure signals. Journal of Banking & Finance 34(10): 2530-2548.

Fugazza, C., Guidolin, M. and Nicodano, G. (2007) Investing for the Longrun in European Real Estate. Journal of Real Estate Finance and Economics 34(1): 35-80.

Fulli-Lemaire, N. (2013) An Inflation Hedging Strategy with Commodities: A Core Driven Global Macro. Journal of Investment Strategies 2(3): 23-50.

Fung, W. and Hsieh, D.A. (1999) A Primer on Hedge Funds. Journal of Empirical Finance 6(3): 309-331.

Fung, J.K.W., Mok, H.M.K. and Wong, K.C.K. (2004) Pricing Efficiency in a Thin Market with Competitive Market Makers: Box Spread Strategies in the Hang Seng Index Options Market. Financial Review 39(3): 435-454.

Fusaro, P.C. and James, T. (2005) Energy Hedging in Asia: Market Structure and Trading Opportunities. London, UK: Palgrave Macmillan.

F¨uss, R. and Nikitina, O. (2011) Explaining Yield Curve Dynamics. Journal of Fixed Income 21(2): 68-87.

Gabaix, X., Krishnamurthy, A. and Vigneron, O. (2007) Limits of arbitrage: theory and evidence from the mortgage-backed securities market. Journal of Finance 62(2): 557-595.

Gajardo, G., Kristjanpoller, W.D. and Minutolo, M. (2018) Does Bitcoin exhibit the same asymmetric multifractal cross-correlations with crude oil, gold and DJIA as the Euro, Great British Pound and Yen? Chaos, Solitons & Fractals 109: 195-205.

Gande, A., Altman, E. and Saunders, A. (2010) Bank Debt vs. Bond Debt: Evidence from Secondary Market Prices. Journal of Money, Credit and Banking 42(4): 755-767.

Gao, B. and Ren, R.-E. (2015) A New Sector Rotation Strategy and its Performance Evaluation: Based on a Principal Component Regression Model. Working Paper. Available online: https://ssrn.com/abstract=2628058.

Gao, C., Xing, Y. and Zhang, X. (2017) Anticipating Uncertainty: Straddles Around Earnings Announcements. Working Paper. Available online: https: //ssrn.com/abstract=2204549.

Garbade, K.D. (2004) Origins of the Federal Reserve Book-Entry System. Federal Reserve Bank of New York, Economic Policy Review 10(3): 33-50.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Garcia, C.B. and Gould, F.J. (1993) Survivorship Bias. Journal of Portfolio Management 19(3): 52-56.

Garcia, D. and Schweitzer, F. (2015) Social signals and algorithmic trading of Bitcoin. Royal Society Open Science 2(9): 150288.

Garcia, D., Tessone, C.J., Mavrodiev, P. and Perony, N. (2014) The digital traces of bubbles: feedback cycles between socioeconomic signals in the Bitcoin economy. Journal of The Royal Society Interface 11(99): 0623.

Garcia-Feij´oo, L., Kochard, L., Sullivan, R.N. and Wang, P. (2015) Low-Volatility Cycles: The Influence of Valuation and Momentum on Low-Volatility Portfolios. Financial Analysts Journal 71(3): 47-60.

Garlappi, L. and Yan, H. (2011) Financial Distress and the Cross-section of Equity Returns. Journal of Finance 66(3): 789-822.

Gˆarleanu, N., Pedersen, L.H. and Poteshman, A.M. (2009) Demand-Based Option Pricing. Review of Financial Studies 22(10): 4259-4299.

Garvey, R. and Wu, F. (2009) Intraday time and order execution quality dimensions. Journal of Financial Markets 12(2): 203-228.

Garyn-Tal, S. (2014a) An Investment Strategy in Active ETFs. Journal of Index Investing 4(1): 12-22.

Garyn-Tal, S. (2014b) Explaining and Predicting ETFs Alphas: The R2 Methodology. Journal of Index Investing 4(4): 19-32.

Garzarelli, F., Cristelli, M., Pompa, G., Zaccaria, A. and Pietronero, L. (2014) Memory effects in stock price dynamics: evidences of technical trading. Scientific Reports 4: 4487.

Gatev, E., Goetzmann, W.N. and Rouwenhorst, K.G. (2006) Pairs Trading: Performance of a Relative-Value Arbitrage Rule. Review of Financial Studies 19(3): 797-827.

Gatheral, J. and Jacquier, A. (2014) Arbitrage-free SVI volatility surfaces. Quantitative Finance 14(1): 59-71.

Gatzlaff, D.H. and Tirtiroglu, D. (1995) Real Estate Market Efficiency: Issues and Evidence. Journal of Real Estate Literature 3(2): 157-189.

Gay, G.D. and Kolb, R.W. (1983) The Management of Interest Rate Risk. Journal of Portfolio Management 9(2): 65-70.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Gay, G.D., Kolb, R.W. and Chiang, R. (1983) Interest Rate Hedging: An Empirical Test Of Alternative Strategies. Journal of Financial Research 6(3): 187-197.

Ge, W. (2016) A Survey of Three Derivative-Based Methods to Harvest the Volatility Premium in Equity Markets. Journal of Investing 25(3): 48-58.

G´eczy, C., Minton, B.A. and Schrand, C. (1997) Why Firms Use Currency Derivatives. Journal of Finance 52(4): 1323-1354.

G´eczy, C.C. and Samonov, M. (2016) Two Centuries of Price-Return Momentum. Financial Analysts Journal 72(5): 32-56.

Gehricke, S.A. and Zhang, J.E. (2018) Modeling VXX. Journal of Futures Markets 38(8): 958-976.

Geltner, D.M., Miller, N.G., Clayton, J. and Eichholtz, P. (2006) Commercial Real Estate Analysis and Investments. (2nd ed.) Atlanta, GA: OnCourse Learning Publishing.

Geltner, D.M., Rodriguez, J.V. and O’Connor, D. (1995) The Similar Genetics of Public and Private Real Estate and the Optimal Long-Horizon Portfolio Mix. Real Estate Finance 12(3): 13-25.

Geman, H. (1998) Insurance and Weather Derivatives: From Exotic Options to Exotic Underlyings. London, UK: Risk Books.

Geman, H. and Leonardi, M.-P. (2005) Alternative approaches to weather derivatives pricing. Managerial Finance 31(6): 46-72.

Geman, H. and Roncoroni, A. (2006) Understanding the fine structure of electricity prices. Journal of Business 79(3): 1225-1261.

Gen¸cay, R. (1996) Nonlinear prediction of security returns with moving average rules. Journal of Forecasting 15(3): 165-174.

Gen¸cay, R. (1998) The Predictability of securities returns with simple technical rules. Journal of Empirical Finance 5(4): 347-359.

Gen¸cay, R. and Stengos, T. (1998) Moving average rules, volume and the predictability of security returns with feedforward networks. Journal of Forecasting 17(5-6): 401-414.

Genesove, D. and Han, L. (2012) Search and Matching in the Housing Market. Journal of Urban Economics 72(1): 31-35.

Genesove, D. and Mayer, C. (1997) Equity and Time to Sale in the Real Estate Market. American Economic Review 87(3): 255-269.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Genesove, D. and Mayer, C. (2001) Loss Aversion and Seller Behavior: Evidence From the Housing Market. Quarterly Journal of Economics 116(4): 1233-1260.

George, T.J. and Hwang, C.-Y. (2010) A resolution of the distress risk and leverage puzzles in the cross section of stock returns. Journal of Financial Economics 96(1): 56-79.

Georgoula, I., Pournarakis, D., Bilanakos, C., Sotiropoulos, D. and Giaglis, G.M. (2015) Using Time-Series and Sentiment Analysis to Detect the Determinants of Bitcoin Prices. Working Paper. Available online: https: //ssrn.com/abstract=2607167.

Gerakos, J. and Linnainmaa, J. (2012) Decomposing Value. Working Paper. Available online: https://ssrn.com/abstract=2083166.

Gervais, S. and Odean, T. (2001) Learning to Be Overconfident. Review of Financial Studies 14(1): 1-27.

Geske, R.L. and Pieptea, D.R. (1987) Controlling Interest Rate Risk and Return with Futures. Review of Futures Markets 6(1): 64-86.

Gestel, T., Suykens, J.A.K., Baestaend, D.E., Lambrechts, A., Lanckriet, G., Vandaele, B., Moor, B. and Vandewalle, J. (2001) Financial time series prediction using least squares support vector machines within the evidence framework. IEEE Transactions on Neural Networks 12(4): 809-821.

Ghiulnara, A. and Viegas, C. (2010) Introduction of weather-derivative concepts: perspectives for Portugal. Journal of Risk Finance 11(1): 9-19.

Ghosh, A. (1993) Hedging with stock index futures: Estimation and forecasting with error correction model. Journal of Futures Markets 13(7): 743-752.

Ghosh, A. (2012) Comparative study of Financial Time Series Prediction by Artificial Neural Network with Gradient Descent Learning. International Journal of Scientific & Engineering Research 3(1): 41-49.

Gibson, M.S. (2004) Understanding the Risk of Synthetic CDOs. Finance and Economics Discussion Series (FEDS), Paper No. 2004-36. Washington, DC: Board of Governors of the Federal Reserve System. Available online: https: //www.federalreserve.gov/pubs/feds/2004/200436/200436pap.pdf.

Gibson, M.S. and Pritsker, M. (2000) Improving Grid-based Methods for Estimating Value at Risk of Fixed-Income Portfolios. Journal of Risk 3(2): 65-89.

Gibson, R. and Schwartz, E.S. (1990) Stochastic convenience yield and the pricing of oil contingent claims. Journal of Finance 15(3): 959-967.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Giese, P. (2012) Optimal design of volatility-driven algo-alpha trading strategies. Risk 25(5): 68-73.

Giesecke, K. and Weber, S. (2006) Credit contagion and aggregate losses. Journal of Economic Dynamics and Control 30(5): 741-767.

Gilbert, S., Jones, S.K. and Morris, G.H. (2006) The impact of skewness in the hedging decision. Journal of Futures Markets 26(5): 503-520.

Gilmour, N. and Ridley, N. (2015) Everyday vulnerabilities – money laundering through cash intensive businesses. Journal of Money Laundering Control 18(3): 293-303.

Gilson, S.C. (1995) Investing in Distressed Situations: A Market Survey. Financial Analysts Journal 51(6): 8-27.

Gilson, S.C. (2010) Creating Value Through Corporate Restructuring: Case Studies in Bankruptcies, Buyouts, and Breakups. Hoboken, NJ: John Wiley & Sons, Inc.

Gilson, S. (2012) Preserving Value by Restructuring Debt. Journal of Applied Corporate Finance 24(4): 22-35.

Gilson, S.C., John, K. and Lang, L.H.P. (1990) Troubled debt restructurings: An empirical study of private reorganization of firms in default. Journal of Financial Economics 27(2): 315-353.

Girma, P.B. and Paulson, A.S. (1998) Seasonality in petroleum futures spreads. Journal of Futures Markets 18(5): 581-598.

Glabadanidis, P. (2015) Market Timing With Moving Averages. International Review of Finance 15(3): 387-425.

Glaeser, E.L. and Kallal, H.D. (1997) Thin Markets, Asymmetric Information, and Mortgage-Backed Securities. Journal of Financial Intermediation 6(1): 64-86.

Glasserman, P. and Wu, Q. (2010) Forward and future implied volatility. International Journal of Theoretical and Applied Finance 14(3): 407-432.

Gliner, G. (2014) Global Macro Trading: Profiting in a New World Economy. Hoboken, NJ: John Wiley & Sons, Inc.

Glorot, X., Bordes, A. and Bengio, Y. (2011) Deep Sparse Rectifier Neural Networks. Proceedings of Machine Learning Research 15: 315-323.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Godfrey, C. and Brooks, C. (2015) The Negative Credit Risk Premium Puzzle: A Limits to Arbitrage Story. Working Paper. Available online: https://ssrn. com/abstract=2661232.

Goebel, P.R., Harrison, D.M., Mercer, J.M. and Whitby, R.J. (2013) REIT Momentum and Characteristic-Related REIT Returns. Journal of Real Estate Finance and Economics 47(3): 564-581.

Goetzmann, W.N. and Ibbotson, R.G. (1990) The Performance of Real Estate as an Asset Class. Journal of Applied Corporate Finance 3(1): 65-76.

Goetzmann, W.N. and Ibbotson, R.G. (1994) Do Winners Repeat? Journal of Portfolio Management 20(2): 9-18.

Golden, L.L., Wang, M. and Yang, C. (2007) Handling Weather Related Risks through the Financial Markets: Considerations of Credit Risk, Basis Risk, and Hedging. Journal of Risk and Insurance 74(2): 319-346.

Goldstein, H.N. (1964) The Implications of Triangular Arbitrage for Forward Exchange Policy. Journal of Finance 19(3): 544-551.

Goltz, F. and Lai, W.N. (2009) Empirical properties of straddle returns. Journal of Derivatives 17(1): 38-48.

G¨onc¨u, A. (2012) Pricing temperature-based weather derivatives in China. Journal of Risk Finance 13(1): 32-44.

Goodfellow, I., Warde-Farley, D., Mirza, M., Courville, A. and Bengio, Y. (2013) Maxout Networks. Proceedings of Machine Learning Research 28(3): 1319-1327.

Goodfriend, M. (2011) Money Markets. Annual Review of Financial Economics 3: 119-1137.

Goodman, L.S. (2002) Synthetic CDOs: An Introduction. Journal of Derivatives 9(3): 60-72.

Goodman, L.S. and Lucas, D.J. (2002) And When CDOs PIK? Journal of Fixed Income 12(1): 96-102.

Gordini, N. (2014) A genetic algorithm approach for SMEs bankruptcy prediction: Empirical evidence from Italy. Expert Systems with Applications 41(14): 6433-6455.

Gorton, G.B., Hayashi, F. and Rouwenhorst, K.G. (2013) The Fundamentals of Commodity Futures Returns. Review of Finance 17(1): 35-105.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Gorton, G. and Metrick, A. (2012) Securitized banking and the run on repo. Journal of Financial Economics 104(3): 425-451.

Gorton, G.B. and Rouwenhorst, K.G. (2006) Facts and Fantasies about Commodity Futures. Financial Analysts Journal 62(2): 47-68.

Gradojevic, N., Gen¸cay, R. and Erdemlioglu, D. (2017) Robust Prediction of Triangular Currency Arbitrage with Liquidity and Realized Risk Measures: A New Wavelet-Based Ultra-High-Frequency Analysis. Working Paper. Available online: https://ssrn.com/abstract=3018815.

Graff, R., Harrington, A. and Young, M. (1999) Serial Persistence in Disaggregated Australian Real Estate Returns. Journal of Real Estate Portfolio Management 5(2): 113-128.

Graff, R.A. and Young, M.S. (1997) Serial Persistence in Equity REIT Returns. Journal of Real Estate Research 14(3): 183-214.

Graham, M., Nikkinen, J. and Sahlstr¨om, P. (2003) Relative importance of scheduled macroeconomic news for stock market investors. Journal of Economics and Finance 27(2): 153-165.

Graham, S. and Pirie, W. (1994) Index Fund Rebalancing and Market Efficiency. Journal of Economics and Finance 18(2): 219-229.

Grant, J. (2016) Trading Strategies in Futures Markets (Ph.D. Thesis). London, UK: Imperial College. Available online: https://spiral.imperial.ac. uk/bitstream/10044/1/32011/1/Grant-J-2016-PhD-Thesis.PDFA.pdf.

Grantier, B.J. (1988) Convexity and Bond Performance: The Benter the Better. Financial Analysts Journal 44(6): 79-81.

Grasselli, M. and Wagalath, L. (2018) VIX vs VXX: A Joint Analytical Framework. Working Paper. Available online: https://ssrn.com/abstract= 3144526.

Green, R.C. and Rydqvist, K. (1999) Ex-day behavior with dividend preference and limitations to short-term arbitrage: the case of Swedish lottery bonds. Journal of Financial Economics 53(2): 145-187.

Greenhaus, S.F. (1991) Approaches to Investing in Distressed Securities: Passive Approaches. In: Bowman, T.A. (ed.) Analyzing Investment Opportunities in Distressed and Bankrupt Companies. (AIMR Conference Proceedings, Vol. 1991, Iss. 1.) Chicago, IL: AIMR, pp. 47-52.

Greer, R.J. (1978) Conservative Commodities: A Key Inflation Hedge. Journal of Portfolio Management 4(4): 26-29.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Greer, R.J. (2000) The Nature of Commodity Index Returns. Journal of Alternative Investments 3(1): 45-52.

Greer, R.J. (2007) The Role of Commodities in Investment Portfolios. CFA Institute Conference Proceedings Quarterly 24(4): 35-44.

Grieves, R. (1999) Butterfly Trades. Journal of Portfolio Management 26(1): 87-95.

Grieves, R. and Mann, S.V. (2004) An Overlooked Coupon Effect in Treasury Futures Contracts. Journal of Derivatives 12(2): 56-61.

Grieves, R., Mann, S.V., Marcus, A.J. and Ramanlal, P. (1999) Riding the Bill Curve. Journal of Portfolio Management 25(3): 74-82.

Grieves, R. and Marcus, A.J. (1992) Riding the Yield Curve: Reprise. Journal of Portfolio Management 18(4): 67-76.

Grieves, R. and Marcus, A.J. (2005) Delivery Options and Treasury-Bond Futures Hedge Ratios. Journal of Derivatives 13(2): 70-76.

Griffin, J.M., Ji, X. and Martin, J.S. (2003) Momentum Investing and Business Cycle Risks: Evidence from Pole to Pole. Journal of Finance 58(6): 2515-2547.

Griffin, J.M. and Lemmon, M.L. (2002) Book-to-Market Equity, Distress Risk, and Stock Returns. Journal of Finance 57(5): 2317-2336.

Grigg, N.S. (2010) Infrastructure Finance: The Business of Infrastructure for a Sustainable Future. Hoboken, NJ: John Wiley & Sons, Inc.

Grimsey, D. and Lewis, M.K. (2002) Evaluating the risks of public private partnerships for infrastructure projects. International Journal of Project Management 20(2): 107-118.

Grinblatt, M. and Moskowitz, T.J. (2004) Predicting Stock Price Movements from Past Returns: The Role of Consistency and Tax-Loss Selling. Journal of Financial Economics 71(3): 541-579.

Grinblatt, M. and Titman, S. (1992) The Persistence of Mutual Fund Performance. Journal of Finance 47(5): 1977-1984.

Grinold, R.C. and Kahn, R.N. (2000) Active Portfolio Management. New York, NY: McGraw-Hill, Inc.

Grishchenko, O.V. and Huang, J.-Z. (2013) Inflation Risk Premium: Evidence from the TIPS Market. Journal of Fixed Income 22(4): 5-30.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Grishchenko, O.V., Vanden, J.M. and Zhang, J. (2016) The Informational Content of the Embedded Deflation Option in TIPS. Journal of Banking & Finance 65: 1-26.

Grissom, T.V., Kuhle, J.L. and Walther, C.H. (1987) Diversification works in real estate, too. Journal of Portfolio Management 13(2): 66-71.

Grobys, K., Heinonen, J.-P. and Kolari, J.W. (2016) Is Currency Momentum a Hedge for Global Economic Risk? Working Paper. Available online: https: //ssrn.com/abstract=2619146.

Grudnitski, G. and Osborn, L. (1993) Forecasting S&P and Gold Futures Prices: An Application of Neural Networks. Journal of Futures Markets 13(6): 631-643.

Grundy, B.D. and Martin, J.S. (2001) Understanding the Nature of the Risks and the Source of the Rewards to Momentum Investing. Review of Financial Studies 14(1): 29-78.

Grundy, B.D. and Verwijmeren, P. (2016) Disappearing call delay and dividend-protected convertible bonds. Journal of Finance 71(1): 195-224.

Gunasekarage, A. and Power, D.M. (2001) The profitability of moving average trading rules in South Asian stock markets. Emerging Markets Review 2(1): 17-33.

Gunasekarage, A., Power, D.M. and Ting Zhou, T.T. (2008) The long-term inflation hedging effectiveness of real estate and financial assets: A New Zealand investigation. Studies in Economics and Finance 25(4): 267-278.

Guo, D. (2000) Dynamic Volatility Trading Strategies in the Currency Option Market. Review of Derivatives Research 4(2): 133-154.

Gupta, R. and Miller, S.M. (2012) “Ripple effects” and forecasting home prices in Los Angeles, Las Vegas, and Phoenix. Annals of Regional Science 48(3): 763-782.

Guren, A.M. (2014) The Causes and Consequences of House Price Momentum. Working Paper. Available online: http://scholar.harvard.edu/ files/guren/files/gurenjmp.pdf.

G¨urkaynak, R.S., Sack, B. and Wright, J.H. (2010) The TIPS Yield Curve and Inflation Compensation. American Economic Journal: Macroeconomics 2(1): 70-92.

Gutierrez, R.C. and Prinsky, C.A. (2007) Momentum, Reversal, and the Trading Behaviors of Institutions. Journal of Financial Markets 10(1): 48-75.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Hafner, R. and Wallmeier, M. (2007) Volatility as an Asset Class: European Evidence. European Journal of Finance 13(7): 621-644.

Hagenstein, F., Mertz, A. and Seifert, J. (2004) Investing in Corporate Bonds and Credit Risk. London, UK: Palgrave Macmillan.

Hagopian, G.C. (1999) Property-flipping and fraudulent appraisals: The phenomenon and the crackdown. Assessment Journal 6(6): 33-39.

Hagstr¨omer, B. and Nord´en, L. (2013) The Diversity of High-Frequency Traders. Journal of Financial Markets 16(4): 741-770.

Hagstr¨omer, B., Nord´en, L. and Zhang, D. (2014) The Aggressiveness of High-Frequency Traders. Financial Review 49(2): 395-419.

Hall, P., Park, B.U. and Samworth, R.J. (2008) Choice of neighbor order in nearest-neighbor classification. Annals of Statistics 36(5): 2135-2152.

Hall, J., Pinnuck, M. and Thorne, M. (2013) Market risk exposure of merger arbitrage in Australia. Accounting & Finance 53(1): 185-215.

Hamelink, F. and Hoesli, M. (1996) Swiss real estate as a hedge against inflation: New evidence using hedonic and autoregressive models. Journal of Property Finance 7(1): 33-49.

Hamerle, A., Igl, A. and Plank, K. (2012) Correlation smile, volatility skew, and systematic risk sensitivity of tranches. Journal of Derivatives 19(3): 8-27.

Hamilton, J. (2003) What is an oil shock? Journal of Econometrics 113(2): 363-398.

Hamisultane, H. (2009) Utility-based pricing of weather derivatives. European Journal of Finance 16(6): 503-525.

Han, S. and Qiu, J. (2007) Corporate precautionary cash holdings. Journal of Corporate Finance 13(1): 43-57.

Hancock, G.D. (2013) VIX Futures ETNs: Three Dimensional Losers. Accounting and Finance Research 2(3): 53-64.

Hanley, M. (1999) Hedging the Force of Nature. Risk Professional 5(4): 21-25.

Hanly, J., Morales, L. and Cassells, D. (2018) The efficacy of financial futures as a hedging tool in electricity markets. International Journal of Financial Economics 23(1): 29-40.

Hansch, O., Naik, N.Y. and Viswanathan, S. (1998) Do inventories matter in dealership markets? Evidence from the London stock exchange. Journal of Finance 53(5): 1623-1656.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Hansen, L.P. and Hodrick, R.J. (1980) Forward Exchange Rates as Optimal Predictors of Future Spot Rates: An Econometric Analysis. Journal of Political Economy 88(5): 829-853.

Happ, S. (1986) The Behavior of Rates on Federal Funds and Repurchase Agreements. American Economist 30(2): 22-32.

Haran, M., Newell, G., Adair, A., McGreal, S. and Berry, J. (2011) The performance of UK regeneration property within a mixed asset portfolio. Journal of Property Research 28(1): 75-95.

Harˇcarikov´a, M. and Solt´es, M. (2016) Risk Management in Energy Sector ˇ Using Short Call Ladder Strategy. Montenegrin Journal of Economics 12(3): 39-54.

H¨ardle, W.K. and L´opez Cabrera, B. (2011) The Implied Market Price of Weather Risk. Applied Mathematical Finance 19(1): 59-95.

H¨ardle, W. and Silyakova, E. (2010) Volatility Investing with Variance Swaps. Working Paper. Available online: https://ssrn.com/abstract=2894245.

Hardy, C.C. (1978) The Investor’s Guide to Technical Analysis. New York, NY: McGraw-Hill, Inc.

Harford, J. (2005) What drives merger waves? Journal of Financial Economics 77(3): 529-560.

Harner, M.M. (2008) The Corporate Governance and Public Policy Implications of Activist Distressed Debt Investing. Fordham Law Review 77(2): 703-773.

Harner, M.M. (2011) Activist Distressed Debtholders: The New Barbarians at the Gate? Washington University Law Review 89(1): 155-206.

Harris, T.S., Hubbard, R.G. and Kemsley, D. (2001) The Share Price Effects Of Dividend Taxes And Tax Imputation Credits. Journal of Public Economics 79(3): 569-596.

Harris, L.E. and Namvar, E. (2016) The Economics of Flash Orders and Trading. Journal of Investment Management 14(4): 74-86.

Harris, R.D.F. and Yilmaz, F. (2009) A momentum trading strategy based on the low frequency component of the exchange rate. Journal of Banking & Finance 33(9): 1575-1585.

Harrison, J.M. and Pliska, S.R. (1981) Martingales and stochastic integrals in the theory of continuous trading. Stochastic Processes and Their Applications 11(3): 215-260.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Hartigan, L.R., Prasad, R. and De Francesco, A.J. (2011) Constructing an investment return series for the UK unlisted infrastructure market: estimation and application. Journal of Property Research 28(1): 35-58.

Hartzell, D.J., Eichholtz, P. and Selender, A. (2007) Economic diversification in European real estate portfolios. Journal of Property Research 10(1): 5-25.

Hartzell, D., Hekman, J. and Miles, M. (1986) Diversification Categories in Investment Real Estate. Real Estate Economics 14(2): 230-254.

Hartzell, D., Hekman, J.S. and Miles, M.E. (1987) Real Estate Returns and Inflation. Real Estate Economics 15(1): 617-637.

Hartzell, D.J., Shulman, D.G. and Wurtzebach, C.H. (1987) Refining the Analysis of Regional Diversification for Income-Producing Real Estate. Journal of Real Estate Research 2(2): 85-95.

Hartzog, J. (1982) Controlling Profit Volatility: Hedging with GNMA Options. Federal Home Loan Bank Board Journal 15(2): 10-14.

Harvey, A.C. (1984) A unified view of statistical forecasting procedures. Journal of Forecasting 3(3): 245-275.

Harvey, A.C. (1990) Forecasting, Structural Time Series Models and the Kalman Filter. Cambridge, UK: Cambridge University Press.

Harvey, C.R. (2014) Bitcoin Myths and Facts. Working Paper. Available online: https://ssrn.com/abstract=2479670.

Harvey, C.R. (2016) Cryptofinance. Working Paper. Available online: https: //ssrn.com/abstract=2438299.

Harvey, J.T. (2015) Deviations from uncovered interest rate parity: a Post Keynesian explanation. Journal of Post Keynesian Economics 27(1): 19-35.

Harvey, A. and Trimbur, T. (2008) Trend Estimation and the Hodrick-Prescott Filter. Journal of the Japan Statistical Society 38(1): 41-49.

Hasbrouck, J. and Saar, G. (2013) Low-latency Trading. Journal of Financial Markets 16(4): 646-679.

Hastings, A. and Nordby, H. (2007) Benefits of Global Diversification on a Real Estate Portfolio. Journal of Portfolio Management 33(5): 53-62.

Hatemi-J, A. and Roca, E. (2006) Calculating the optimal hedge ratio: constant, time varying and the Kalman Filter approach. Applied Economics Letters 13(5): 293-299.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Hau, H. (2014) The exchange rate effect of multi-currency risk arbitrage. Journal of International Money and Finance 47: 304-331.

Haubrich, J., Pennacchi, G. and Ritchken, P. (2012) Inflation Expectations, Real Rates, and Risk Premia: Evidence from Inflation Swaps. Review of Financial Studies 25(5): 1588-1629.

Haug, E.G. (2001) Closed form Valuation of American Barrier Options. International Journal of Theoretical and Applied Finance 4(2): 355-359.

Haugen, R.A. (1995) The New Finance: The Case Against Efficient Markets. Upper Saddle River, NJ: Prentice Hall.

Haurin, D.R. and Gill, H.L. (2002) The Impact of Transaction Costs and the Expected Length of Stay on Homeownership. Journal of Urban Economics 51(3): 563-584.

Haurin, D.R., Haurin, J.L., Nadauld, T. and Sanders, A. (2010) List Prices, Sale Prices and Marketing Time: An Application to U.S. Housing Markets. Real Estate Economics 38(4): 659-685.

Hautcoeur, P.C. (2006) Why and how to measure stock market fluctuations? The early history of stock market indices, with special reference to the French case. Working Paper. Available online: https://halshs. archives-ouvertes.fr/halshs-00590522/PDF/wp200610.pdf.

Hayes, B. (2011) Multiple time scale attribution for commodity trading advisor (CTA) funds. Journal of Investment Management 9(2): 35-72.

Hayre, L.S. (1990) Understanding option-adjusted spreads and their use. Journal of Portfolio Management 16(4): 68-69.

He, D.X., Hsu, J.C. and Rue, N. (2015) Option-Writing Strategies in a Low-Volatility Framework. Journal of Investing 24(3): 116-128.

He, J., Tang, Q. and Zhang, H. (2016) Risk reducers in convex order. Insurance: Mathematics and Economics 70: 80-88.

Head, A., Lloyd-Ellis, H. and Sun, H. (2014) Search, Liquidity, and the Dynamics of House Prices and Construction. American Economic Review 104(4): 1172-1210.

Heaton, H. (1988) On the possible tax-driven arbitrage opportunities in the new municipal bond futures contract. Journal of Futures Markets 8(3): 291- 302.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Hegde, S.P. (1982) The Impact of Interest Rate Level and Volatility on the Performance of Interest Rate Hedges. Journal of Futures Markets 2(4): 341- 356.

Heidari, M. and Wu, L. (2003) Are Interest Rate Derivatives Spanned by the Term Structure of Interest Rates? Journal of Fixed Income 13(1): 75-86.

Helm, D. (2009) Infrastructure Investment, the Cost of Capital, and Regulation: an Assessment. Oxford Review of Economic Policy 25(3): 307-326.

Helm, D. and Tindall, T. (2009) The Evolution of Infrastructure and Utility Ownership and its Implications. Oxford Review of Economic Policy 25(3): 411-434.

Hemler, M.L. and Miller, T.W., Jr. (1997) Box spread arbitrage profits following the 1987 market crash. Journal of Financial and Quantitative Analysis 32(1): 71-90.

Hemler, M.L. and Miller, T.W., Jr. (2015) The Performance of Options-Based Investment Strategies: Evidence for Individual Stocks During 2003-2013. Working Paper. Available online: http://www.optionseducation.org/content/dam/oic/documents/ literature/files/perf-options-strategies.pdf.

Hendershott, T., Jones, C. and Menkveld, A. (2011) Does Algorithmic Trading Improve Liquidity? Journal of Finance 66(1): 1-33.

Hendershott, T., Jones, C. and Menkveld, A. (2013) Implementation Shortfall with Transitory Price Effects. In: Easley, D., L´opez de Prado, M. and O’Hara, M. (eds.) High Frequency Trading: New Realities for Traders, Markets and Regulators. London, UK: Risk Books, Chapter 9.

Hendershott, T. and Moulton, P.C. (2011) Automation, speed, and stock market quality: The NYSE’s Hybrid. Journal of Financial Markets 14(4): 568-604.

Hendershott, T. and Riordan, R. (2013) Algorithmic Trading and the Market for Liquidity. Journal of Financial and Quantitative Analysis 48(4): 1001- 1024.

Henderson, B. (2005) Convertible Bonds: New Issue Performance and Arbitrage Opportunities (Ph.D. Thesis). Urbana-Champaign IL: University of Illinois.

Henderson, R. (1924) A new method of graduation. Transactions of the Actuarial Society of America 25: 29-40.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Henderson, R. (1925) Further remarks on graduation. Transactions of the Actuarial Society of America 26: 52-57.

Henderson, R. (1938) Mathematical Theory of Graduation. New York, NY: Actuarial Society of America.

Henderson, T.M. (2003) Fixed Income Strategy: The Practitioner’s Guide to Riding the Curve. Chichester, UK: John Wiley & Sons, Ltd.

Henderson, B.J. and Tookes, H. (2012) Do investment banks’ relationships with investors impact pricing? The case of convertible bond issues. Management Science 58(2): 2272-2291.

Henrard, M.P.A. (2006) A Semi-Explicit Approach to Canary Swaptions in HJM One-Factor Model. Applied Mathematical Finance 13(1): 1-18.

Hensher, D. and Jones, S. (2007) Forecasting corporate bankruptcy: Optimizing the performance of the mixed logit model. Abacus 43(3): 241-364.

Herbertsson, A. (2008) Pricing synthetic CDO tranches in a model with default contagion using the matrix-analytic approach. Journal of Credit Risk 4(4): 3- 35.

Herranz-Lonc´an, A. (2007) Infrastructure investment and Spanish economic growth, 1850-1935. Explorations in Economic History 44(3): 452-468.

Hess, D., Huang, H. and Niessen, A. (2008) How Do Commodity Futures Respond to Macroeconomic News? Financial Markets and Portfolio Management 22(2): 127-146.

Hew, D., Skerratt, L., Strong, N. and Walker, M. (1996) Post-earningsannouncement drift: Some preliminary evidence for the UK. Accounting & Business Research 26(4): 283-293.

Hill, J.M., Balasubramanian, V., Gregory, K. and Tierens, I. (2006) Finding Alpha via Covered Call Writing. Financial Analysts Journal 62(5): 29-46.

Hill, J.M., Nadig, D. and Hougan, M. (2015) A Comprehensive Guide to Exchange-Traded Funds (ETFs). Research Foundation Publications 2015(3): 1-181.

Hillegeist, S.A., Keating, E., Cram, D.P. and Lunstedt, K.G. (2004) Assessing the probability of bankruptcy. Review of Accounting Studies 9(1): 5-34.

Hilliard, J.E. (1984) Hedging Interest Rate Risk with Futures Portfolios under Term Structure Effects. Journal of Finance 39(5): 1547-1569.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Hilliard, J. and Jordan, S. (1989) Hedging Interest Rate Risk with Futures Portfolios under Full-Rank Assumptions. Journal of Financial and Quantitative Analysis 24(2): 217-240.

Hilliard, J. and Reis, J. (1998) Valuation of commodity futures and options under stochastic convenience yields, interest rates, and jump diffusions on the spot. Journal of Financial and Quantitative Analysis 33(1): 61-86.

Hinnerich, M. (2008) Inflation-indexed swaps and swaptions. Journal of Banking & Finance 32(11): 2293-2306.

Hirschey, N. (2018) Do High-Frequency Traders Anticipate Buying and Selling Pressure? Working Paper. Available online: https://ssrn.com/abstract= 2238516.

Hirshleifer, D. (1990) Hedging Pressure and Futures Price Movements in a General Equilibrium Model. Econometrica 58(2): 411-428.

Hirshleifer, D., Lim, S.S. and Teoh, S.H. (2009) Driven to distraction: Extraneous events and underreaction to earnings news. Journal of Finance 64(5): 2289-2325.

Ho, T. and Saunders, A. (1983) Fixed Rate Loan Commitments, Take-Down Risk, and the Dynamics of Hedging with Futures. Journal of Financial and Quantitative Analysis 18(4): 499-516.

Hodges, S. and Carverhill, A. (1993) Quasi mean reversion in an efficient stock market: the characterization of economic equilibria which support Black-Scholes option pricing. Economic Journal 103(417): 395-405.

Hodrick, R.J. (1987) The Empirical Evidence on the Efficiency of Forward and Futures Foreign Exchange Markets. New York, NY: Harwood Academic.

Hodrick, R.J. and Prescott, E.C. (1997) Postwar U.S. Business Cycles: An Empirical Investigation. Journal of Money, Credit and Banking 29(1): 1-16.

Hoesli, M. and Lekander, J. (2008) Real estate portfolio strategy and product innovation in Europe. Journal of Property Investment & Finance 26(2): 162- 176.

Hoevenaars, R.P.M.M., Molenaar, R.D.J., Schotman, P.C. and Steenkamp, T.B.M. (2008) Strategic asset allocation with liabilities: Beyond stocks and bonds. Journal of Economic Dynamics and Control 32(9): 2939-2970.

Holden, C.W. and Jacobsen, S. (2014) Liquidity Measurement Problems in Fast Competitive Markets: Expensive and Cheap Solutions. Journal of Finance 69(4): 1747-1885.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Holmes, P. (1996) Stock index futures hedging: hedge ratio estimation, duration effects, expiration effects and hedge ratio stability. Journal of Business Finance & Accounting 23(1): 63-77.

Hong, H., Torous, W. and Valkanov, R. (2007) Do Industries Lead Stock Markets? Journal of Financial Economics 83(2): 367-396.

Hopton, D. (1999) Prevention of Money Laundering: The Practical Day-to-Day Problems and Some Solutions. Journal of Money Laundering Control 2(3): 249-252.

H¨ordahl, P. and Tristani, O. (2012) Inflation Risk Premia in the Term Structure of Interest Rates. Journal of the European Economic Association 10(3): 634-657.

H¨ordahl, P. and Tristani, O. (2014) Inflation Risk Premia in the Euro Area and the United States. International Journal of Central Banking 10(3): 1-47.

Horvath, P.A. (1998) A Measurement of the Errors in Intra-Period Compounding and Bond Valuation: A Short Extension. Financial Review 23(3): 359-363.

Hotchkiss, E.S. and Mooradian, R.M. (1997) Vulture Investors and the Market for Control of Distressed Firms. Journal of Financial Economics 43(3): 401- 432.

Hotchkiss, E.S. and Ronen, R. (2002) The Informational Efficiency of the Corporate Bond Market: An Intraday Analysis. Review of Financial Studies 15(5): 1325-1354.

Hou, A.J. and Nord´en, L.L. (2018) VIX futures calendar spreads. Journal of Futures Markets 38(7): 822-838.

Houdain, J.P. and Guegan, D. (2006) Hedging tranches index products: illustration of model dependency. ICFAI Journal of Derivatives Markets 4: 39-61.

Houweling, P. and van Vundert, J. (2017) Factor Investing in the Corporate Bond Market. Financial Analysts Journal 73(2): 100-115.

Howison, S.D., Reisinger, C. and Witte, J.H. (2013) The Effect of Nonsmooth Payoffs on the Penalty Approximation of American Options. SIAM Journal on Financial Mathematics 4(1): 539-574.

Hsieh, C.H. and Barmish, B.R. (2015) On Kelly betting: Some limitations. In: Proceeding of the 53rd Annual Allerton Conference on Communication, Control, and Computing. Washington, DC: IEEE, pp. 165-172.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Hsieh, C.H., Barmish, B.R. and Gubner, J.A. (2016) Kelly betting can be too conservative. In: Proceedings of the 2016 Conference on Decision and Control (CDC). Washington, DC: IEEE, pp. 3695-3701.

Hsieh, J. and Walkling, R.A. (2005) Determinants and Implications of Arbitrage Holdings in Acquisitions. Journal of Financial Economics 77(3): 605- 648.

Hsu, M. (1998) Spark Spread Options Are Hot! Electricity Journal 11(2): 28-39.

Hsu, Y.-C., Lin, H.-W. and Vincent, K. (2018) Analyzing the Performance of Multi-Factor Investment Strategies under Multiple Testing Framework. Working Paper. Available online: http://www.econ.sinica.edu.tw/UpFiles/2013092817175327692/ Seminar\_PDF2013093010102890633/17-A0001(all).pdf.

Hu, J. (2001) Basics of Mortgage-Backed Securities. (2nd ed.) Hoboken, NJ: John Wiley & Sons, Inc.

Huang, J-.Z. and Kong, W. (2003) Explaining Credit Spread Changes: New Evidence From Option-Adjusted Bond Indexes. Journal of Derivatives 11(1): 30-44.

Huang, W., Nakamori, Y. and Wang, S.-Y. (2005) Forecasting stock market movement direction with support vector machine. Computers & Operation Research 32(10): 2513-2522.

Huang, H., Shiu, Y. and Lin, P. (2008) HDD and CDD option pricing with market price of weather risk for Taiwan. Journal of Futures Markets 28(8): 790-814.

Huang, C.L. and Tsai, C.Y. (2009) A hybrid SOFM-SVR with a filter-based feature selection for stock market forecasting. Expert Systems with Applications 36(2): 1529-1539.

Huault, I. and Rainelli-Weis, H. (2011) A Market for Weather Risk? Conflicting Metrics, Attempts at compromise, and Limits to Commensuration. Organization Studies 32(10): 1395-1419.

Huck, N. (2009) Pairs selection and outranking: An application to the S&P 100 index. European Journal of Operational Research 196(2): 819-825.

Huck, N. (2015) Pairs trading: Does volatility timing matter? Applied Economics 47(57): 6239-6256.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Huck, N. and Afawubo, K. (2014) Pairs trading and selection methods: is cointegration superior? Applied Economics 47(6): 599-613.

Hudson-Wilson, S. (1990) New Trends in Portfolio Theory. Journal of Property Management 55(3): 57-58.

Hudson-Wilson, S., Gordon, J.N., Fabozzi, F.J., Anson, M.J.P. and Giliberto, M. (2005) Why Real Estate? Journal of Portfolio Management 31(5): 12-21.

Huerta, R., Elkan, C. and Corbacho, F. (2013) Nonlinear Support Vector Machines Can Systematically Identify Stocks with High and Low Future Returns. Algorithmic Finance 2(1): 45-58.

H¨uhn, H. and Scholz, H. (2017) Alpha Momentum and Price Momentum. Working Paper. Available online: https://ssrn.com/abstract=2287848.

Huij, J. and Lansdorp, S. (2017) Residual Momentum and Reversal Strategies Revisited. Working Paper. Available online: https://ssrn.com/abstract= 2929306.

Hull, D.A. (1996) Stemming algorithms: A case study for detailed evaluation. Journal of the American Society for Information Science and Technology 47(1): 70-84.

Hull, J.C. (2012) Options, Futures and Other Derivatives. Upper Saddle River, NJ: Prentice Hall.

Hull, J.C. and White, A.D. (2004) Valuation of a CDO and an nth to Default CDS without Monte Carlo Simulation. Journal of Derivatives 12(2): 8-23.

Hull, J.C. and White, A.D. (2006) Valuing Credit Derivatives Using an Implied Copula Approach. Journal of Derivatives 14(2): 8-28.

Hull, J.C. and White, A.D. (2010) An Improved Implied Copula Model and its Application to the Valuation of Bespoke CDO Tranches. Journal of Investment Management 8(3): 11-31.

Hull, J., Predescu, M. and White, A. (2005) Bond Prices, Default Probabilities and Risk Premiums. Journal of Credit Risk 1(2): 53-60.

Hung, N.H. (2016) Various moving average convergence divergence trading strategies: a comparison. Investment Management and Financial Innovations 13(2): 363-369.

Hunter, R. (1999) Managing Mother Nature. Derivatives Strategy 4(2): 15-19.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Hunter, D.M. and Simon, D.P. (2005) Are TIPS the “real” deal?: A conditional assessment of their role in a nominal portfolio. Journal of Banking & Finance 29(2): 347-368.

H¨urlimann, W. (2002) On immunization, stop-loss order and the maximum Shiu measure. Insurance: Mathematics and Economics 31(3): 315-325.

H¨urlimann, W. (2012) On directional immunization and exact matching. Communications in Mathematical Finance 1(1): 1-12

Hurst, B., Ooi, Y.H. and Pedersen, L.H. (2017) A Century of Evidence on Trend-Following Investing. Journal of Portfolio Management 44(1): 15-29.

Husson, T. and McCann, C.J. (2011) The VXX ETN and Volatility Exposure. PIABA Bar Journal 18(2): 235-252.

Hutson, E. (2000) Takeover targets and the probability of bid success: Evidence from the Australian market. International Review of Financial Analysis 9(1): 45-65.

Hwang, C.-Y. and George, T.J. (2004) The 52-Week High and Momentum Investing. Journal of Finance 59(5): 2145-2176.

Idzorek, T. (2007) A Step-by-Step Guide to the Black-Litterman Model. In: Satchell, S. (ed.) Forecasting Expected Returns in the Financial Markets. Waltham, MA: Academic Press.

Illueca, M. and Lafuente, J.A. (2003) The Effect of Spot and Futures Trading on Stock Index Volatility: A Non-parametric Approach. Journal of Futures Markets 23(9): 841-858.

Ilmanen, A. (2011) Expected Returns: An Investor’s Guide to Harvesting Market Rewards. Hoboken, NJ: John Wiley & Sons, Inc.

Ilmanen, A., Byrne, R., Gunasekera, H. and Minikin, R. (2004) Which Risks Have Been Best Rewarded? Journal of Portfolio Management 30(2): 53-57.

Ilut, C. (2012) Ambiguity Aversion: Implications for the Uncovered Interest Rate Parity Puzzle. American Economic Journal: Macroeconomics 4(3): 33- 65.

Inderst, G. (2010a) Infrastructure as an Asset Class. EIB Papers 15(1): 70- 105.

Inderst, G. (2010b) Pension fund investment in infrastructure: What have we learnt? Pensions: An International Journal 15(2): 89-99.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Ingersoll, J. (1977) A contingent-claims valuation of convertible securities. Journal of Financial Economics 4(3): 289-322.

Irwin, S.H., Zulauf, C.R. and Jackson, T.E. (1996) Monte Carlo analysis of mean reversion in commodity futures prices. American Journal of Agricultural Economics 78(2): 387-399.

Israelov, R. (2017) Pathetic Protection: The Elusive Benefits of Protective Puts. Working Paper. Available online: https://ssrn.com/abstract= 2934538.

Israelov, R. and Klein, M. (2016) Risk and Return of Equity Index Collar Strategies. Journal of Alternative Investments 19(1): 41-54.

Israelov, R. and Nielsen, L.N. (2014) Covered Call Strategies: One Fact and Eight Myths. Financial Analysts Journal 70(6): 23-31.

Israelov, R. and Nielsen, L.N. (2015a) Covered Calls Uncovered. Financial Analysts Journal 71(6): 44-57.

Israelov, R. and Nielsen, L.N. (2015b) Still Not Cheap: Portfolio Protection in Calm Markets. Journal of Portfolio Management 41(4): 108-120.

Israelov, R., Nielsen L.N. and Villalon, D. (2017) Embracing Downside Risk. Journal of Alternative Investments 19(3): 59-67.

Ito, T., Yamada, K., Takayasu, M. and Takayasu, H. (2012) Free Lunch! Arbitrage Opportunities in the Foreign Exchange Markets. Working Paper. Available online: http://www.nber.org/papers/w18541.

Iturricastillo, I. and De La Pe˜na, J.I. (2010) Absolute Immunization Risk as general measure of immunization risk. An´alisis Financiero 114(3): 42-59.

Ivanov, I.T. and Lenkey, S.L. (2014) Are Concerns About Leveraged ETFs Overblown? Finance and Economics Discussion Series (FEDS), Paper No. 2014-106. Washington, DC: Board of Governors of the Federal Reserve System. Available online: https://www.federalreserve.gov/econresdata/feds/ 2014/files/2014106pap.pdf.

Jabbour, G. and Budwick, P. (2010) The option trader handbook: strategies and trade adjustments. (2nd ed.) Hoboken, NJ: John Wiley & Sons, Inc.

Jackwerth, J.C. (2000) Recovering Risk Aversion from Option Prices and Realized Returns. Review of Financial Studies 13(2): 433-451.

Jacobs, H. and Weber, M. (2015) On the determinants of pairs trading profitability. Journal of Financial Markets 23: 75-97.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Jacoby, G. and Shiller, I. (2008) Duration and Pricing of TIPS. Journal of Fixed Income 18(2): 71-84.

Jain, G. and Baile, C. (2000) Managing weather risks. Strategic Risk, September 2000, pp. 28-31.

James, F.E., Jr. (1968) Monthly moving averages – An effective investment tool? Journal of Financial and Quantitative Analysis 3(3): 315-326.

James, T. (2003) Energy Price Risk: Trading and Price Risk Management. London, UK: Palgrave Macmillan.

Jan, T.C. and Hung, M.W. (2004) Short-Run and Long-Run Persistence in Mutual Funds. Journal of Investing 13(1): 67-71.

Jankowitsch, R. and Nettekoven, M. (2008) Trading strategies based on term structure model residuals. European Journal of Finance 14(4): 281-298.

Jansen, I.P. and Nikiforov, A.L. (2016) Fear and Greed: A Returns-Based Trading Strategy around Earnings Announcements. Journal of Portfolio Management 42(4): 88-95.

Jarrow, R.A. (2010) Understanding the risk of leveraged ETFs. Finance Research Letters 7(3): 135-139.

Jarrow, R., Kchia, Y., Larsson, M. and Protter, P. (2013) Discretely sampled variance and volatility swaps versus their continuous approximations. Finance and Stochastics 17(2): 305-324.

Jarrow, R., Lando, D. and Turnbull, S. (1997) A Markov model for the term structure of credit spreads. Review of Financial Studies 10(2): 481-523.

Jarrow, R.A. and Protter, P. (2012) A Dysfunctional Role of High Frequency Trading in Electronic Markets. International Journal of Theoretical and Applied Finance 15(3): 1250022.

Jarrow, R.A. and Turnbull, S.M. (1995) Pricing Derivatives on Financial Securities Subject to Credit Risk. Journal of Finance 50(1): 53-85.

Jarrow, R. and Yildirim, Y. (2003) Pricing treasury inflation protected securities and related derivatives using an HJM model. Journal of Financial and Quantitative Analysis 38(2): 409-430.

Jasemi, M. and Kimiagari, A.M. (2012) An investigation of model selection criteria for technical analysis of moving average. Journal of Industrial Engineering International 8: 5.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Jegadeesh, N. (1990) Evidence of Predictable Behavior of Security Returns. Journal of Finance 45(3): 881-898.

Jegadeesh, N. and Titman, S. (1993) Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency. Journal of Finance 48(1): 65-91.

Jegadeesh, N. and Titman, S. (1995) Overreaction, delayed reaction, and contrarian profits. Review of Financial Studies 8(4): 973-993.

Jegadeesh, N. and Titman, S. (2001) Profitability of Momentum Strategies: An Evaluation of Alternative Explanations. Journal of Finance 56(2): 699- 720.

Jensen, M.C. (1968) The Performance of Mutual Funds in the Period 1945- 1964. Journal of Finance 23(2): 389-416.

Jensen, G.R., Johnson, R.R. and Mercer, J.M. (2000) Efficient use of commodity futures in diversified portfolios. Journal of Futures Markets 20(5): 489-506.

Jensen, G.R., Johnson, R.R. and Mercer, J.M. (2002) Tactical Asset Allocation and Commodity Futures. Journal of Portfolio Management 28(4): 100-111.

Jermann, U.J. (2016) Negative Swap Spreads and Limited Arbitrage. Working Paper. Available online: https://ssrn.com/abstract=2737408.

Jetley, G. and Ji, X. (2010) The shrinking merger arbitrage spread: Reasons and implications. Financial Analysts Journal 66(2): 54-68.

Jewson, S. (2004a) Weather Derivative Pricing and the Distributions of Standard Weather Indices on US Temperatures. Working Paper. Available online: https://ssrn.com/abstract=535982.

Jewson, S. (2004b) Introduction to Weather Derivative Pricing. Working Paper. Available online: https://ssrn.com/abstract=557831.

Jewson, S., Brix, A. and Ziehmann, C. (2005) Weather Derivative Valuation: The Meteorological, Statistical, Financial and Mathematical Foundations. Cambridge, UK: Cambridge University Press.

Jewson, S. and Caballero, R. (2003) Seasonality in the statistics of surface air temperature and the pricing of weather derivatives. Meteorological Applications 10(4): 367-376.

Jha, R. and Kalimipal, M. (2010) The economic significance of conditional skewness in index option markets. Journal of Futures Markets 30(4): 378-406.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Jiang, H., Li, D. and Wang, A. (2017) Dynamic Liquidity Management by Corporate Bond Mutual Funds. Working Paper. Available online: https: //ssrn.com/abstract=2776829.

Jiang, W., Li, K. and Wang, W. (2012) Hedge Funds and Chapter 11. Journal of Finance 67(2): 513-560.

Jiang, Z. and Liang, J. (2017) Cryptocurrency Portfolio Management with Deep Reinforcement Learning. Working Paper. Available online: https:// arxiv.org/pdf/1612.01277.pdf.

Jiang, X. and Peterburgsky, S. (2017) Investment performance of shorted leveraged ETF pairs. Applied Economics 49(44): 4410-4427.

Jo, H., Han, I. and Lee, H. (1997) Bankruptcy prediction using case-based reasoning, neural networks, and discriminant analysis. Expert Systems with Applications 13(2): 97-108.

Jobst, A. (2005) Tranche Pricing in Subordinated Loan Securitization. Journal of Structured Finance 11(2): 64-96.

Jobst, A. (2006a) European Securitization: A GARCH Model of Secondary Market Spreads. Journal of Structured Finance 12(1): 55-80.

Jobst, A. (2006b) Sovereign Securitization in Emerging Markets. Journal of Structured Finance 12(3): 2-13.

Jobst, A. (2006c) Correlation, Price Discovery and Co-movement of ABS and Equity. Derivatives Use, Trading & Regulation 12(1-2): 60-101.

Jobst, A. (2007) A Primer on Structured Finance. Journal of Derivatives & Hedge Funds 13(3): 199-213.

John, W. and Brigitte, U. (2009) Measuring Global Money Laundering: “The Walker Gravity Model”. Review of Law & Economics 5(2): 821-853.

Johnson, H.F. (1979) Is It Better to Go Naked on the Street? A Primer on the Options Market. Notre Dame Lawyer (Notre Dame Law Review) 55(1): 7-32.

Johnson, T.C. (2002) Rational Momentum Effects. Journal of Finance 57(2): 585-608.

Johnson, T.C. (2008) Volume, liquidity, and liquidity risk. Journal of Financial Economics 87(2): 388-417.

Jones, F.J. (1991) Yield Curve Strategies. Journal of Fixed Income 1(2): 43- 48.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Jones, C.M., Lamont, O. and Lumsdaine, R.L. (1998) Macroeconomic news and bond market volatility. Journal of Financial Economics 47(3): 315-337.

Jongadsayakul, W. (2016) A Box Spread Test of the SET50 Index Options Market Efficiency: Evidence from the Thailand Futures Exchange. International Journal of Economics and Financial Issues 6(4): 1744-1749.

Jongadsayakul, W. (2017) Arbitrage Opportunity In Thailand Futures Exchange: An Empirical Study of SET50 Index Options. In: 2017 IACB, ICE & ISEC Proceedings, Paper No. 381. Littleton, CO: Clute Institute.

Jonsson, J. and Fridson, M. (1996) Forecasting Default Rates on High Yield Bonds. Journal of Fixed Income 6(1): 69-77.

Jordan, B.D. and Jordan, S. (1997) Special repo rates: An empirical analysis. Journal of Finance 52(5): 2051-2072.

Joseph, A. (1952) The Whittaker-Henderson Method of Graduation. Journal of the Institute of Actuaries 78(1): 99-114.

Joshi, N.N. and Lambert, J.H. (2011) Diversification of infrastructure projects for emergent and unknown non-systematic risks. Journal of Risk Research 14(6): 717-733.

Joslin, S. and Konchitchki, Y. (2018) Interest rate volatility, the yield curve, and the macroeconomy. Journal of Financial Economics 128(2): 344-362.

Joslin, S., Priebsch, M. and Singleton, K.J. (2014) Risk Premiums in Dynamic Term Structure Models with Unspanned Macro Risks. Journal of Finance 69(3): 1197-1233.

Jostarndt, P. and Sautner, Z. (2010) Out-of-Court Restructuring versus Formal Bankruptcy in a Non-Interventionist Bankruptcy Setting. Review of Finance 14(4): 623-668.

Jostova, G., Nikolova, S., Philipov, A. and Stahel, C.W. (2013) Momentum in Corporate Bond Returns. Review of Financial Studies 26(7): 1649-1693.

Joyce, M., Lildholdt, P. and Sorensen, S. (2010) Extracting Inflation Expectations and Inflation Risk Premia from the Term Structure: A Joint Model of the UK Nominal and Real Yield Curves. Journal of Banking & Finance 34(2): 281-294.

Judd, K.L., Kubler, F. and Schmedders, K. (2011) Bond Ladders and Optimal Portfolios. Review of Financial Studies 24(12): 4123-4166.

Julio, I.F., Hassan, M.K. and Ngene, G.M. (2013) Trading Strategies in Futures Markets. Global Journal of Finance and Economics 10(1): 1-12.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Junkus, J.C. (1991) Systematic skewness in futures contracts. Journal of Futures Markets 11(1): 9-24.

Jurek, J.W. (2014) Crash-neutral currency carry trades. Journal of Financial Economics 113(3): 325-347.

Kablan, A. (2009) Adaptive Neuro-Fuzzy Inference System for Financial Trading using Intraday Seasonality Observation Model. International Journal of Economics and Management Engineering 3(10): 1909-1918.

Kahn, R.N. and Lemmon, M. (2015) Smart Beta: The Owner’s Manual. Journal of Portfolio Management 41(2): 76-83.

Kahn, R.N. and Lemmon, M. (2016) The Asset Manager’s Dilemma: How Smart Beta Is Disrupting the Investment Management Industry. Financial Analysts Journal 72(1): 15-20.

Kahneman, D. and Tversky, A. (1979) Prospect theory: an analysis of decision under risk. Econometrica 47(2): 263-292.

Kakodkar, A., Galiani, S., J´onsson, J.G. and Gallo, A. (2006) Credit Derivatives Handbook 2006 – Vol. 2: A Guide to the Exotics Credit Derivatives Market. New York, NY: Credit Derivatives Strategy, Merrill Lynch.

Kakushadze, Z. (2015a) Phynance. Universal Journal of Physics and Application 9(2): 64-133. Available online: https://ssrn.com/abstract=2433826.

Kakushadze, Z. (2015b) Mean-Reversion and Optimization. Journal of Asset Management 16(1): 14-40. Available online: https://ssrn.com/abstract= 2478345.

Kakushadze, Z. (2015c) 4-Factor Model for Overnight Returns. Wilmott Magazine 2015(79): 56-62. Available online: https://ssrn.com/abstract= 2511874.

Kakushadze, Z. (2015d) On Origins of Alpha. Hedge Fund Journal 108: 47-50. Available online: https://ssrn.com/abstract=2575007.

Kakushadze, Z. (2015e) Heterotic Risk Models. Wilmott Magazine 2015(80): 40-55. Available online: https://ssrn.com/abstract=2600798.

Kakushadze, Z. (2016) 101 Formulaic Alphas. Wilmott Magazine 2016(84): 72-80. Available online: https://ssrn.com/abstract=2701346.

Kakushadze, Z. and Tulchinsky, I. (2016) Performance v. Turnover: A Story by 4,000 Alphas. Journal of Investment Strategies 5(2): 75-89. Available online: http://ssrn.com/abstract=2657603.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Kakushadze, Z. and Yu, W. (2016a) Multifactor Risk Models and Heterotic CAPM. Journal of Investment Strategies 5(4): 1-49. Available online: https: //ssrn.com/abstract=2722093.

Kakushadze, Z. and Yu, W. (2016b) Statistical Industry Classification. Journal of Risk & Control 3(1): 17-65. Available online: https://ssrn.com/ abstract=2802753.

Kakushadze, Z. and Yu, W. (2017a) Statistical Risk Models. Journal of Investment Strategies 6(2): 1-40. Available online: https://ssrn.com/abstract= 2732453.

Kakushadze, Z. and Yu, W. (2017b) How to Combine a Billion Alphas. Journal of Asset Management 18(1): 64-80. Available online: https://ssrn.com/ abstract=2739219.

Kakushadze, Z. and Yu, W. (2017c) \*K-Means and Cluster Models for Cancer Signatures. Biomolecular Detection and Quantification 13: 7-31. Available online: https://ssrn.com/abstract=2908286.

Kakushadze, Z. and Yu, W. (2018a) Decoding Stock Market with Quant Alphas. Journal of Asset Management 19(1): 38-48. Available online: https: //ssrn.com/abstract=2965224.

Kakushadze, Z. and Yu, W. (2018b) Notes on Fano Ratio and Portfolio Optimization. Journal of Risk & Control 5(1): 1-33. Available online: https: //ssrn.com/abstract=3050140.

Kalev, P.S. and Inder, B.A. (2006) The information content of the term structure of interest rates. Applied Economics 38(1): 33-45.

Kallberg, J.G., Liu, C.L. and Trzcinka, C. (2000) The Value Added from Investment Managers: An Examination of Funds of REITs. Journal of Financial and Quantitative Analysis 35(3): 387-408.

Kalman, P.E. (1960) A New Approach to Linear Filtering and Prediction Problems. Journal of Basic Engineering 82(1): 35-45.

Kambhu, J. (2006) Trading Risk, Market Liquidity, and Convergence Trading in the Interest Rate Swap Spread. Federal Reserve Bank of New York, Economic Policy Review 12(1): 1-13.

Kaminski, V. (2004) Managing Energy Price Risk: The New Challenges and Solutions. London, UK: Risk Books.

Kandel, S., Ofer, A.R. and Sarig, O. (1996) Real Interest Rates and Inflation: An Ex-Ante Empirical Analysis. Journal of Finance 51(1): 205-225.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Kandel, S. and Stambaugh, R.F. (1987) Long-horizon Returns and Shorthorizon Models. CRSP Working Paper No. 222. Chicago, IL: University of Chicago.

Kang, H.B. and Gardner, J. (1989) Selling Price and Marketing Time in the Residential Real Estate Market. Journal of Real Estate Research 4(1): 21-35.

Kang, J.K. and Lee, Y.W. (1996) The pricing of convertible debt offerings. Journal of Financial Economics 41(2): 231-248.

Kang, J., Liu, M.H. and Ni, S.X. (2002) Contrarian and momentum strategies in the China stock market: 1993-2000. Pacific-Basin Finance Journal 10(3): 243-265.

Kapadia, N. and Szado, E. (2007) The Risk Return Characteristics of the Buy-Write Strategy on the Russell 2000 Index. Journal of Alternative Investments 9(4): 39-56.

Kaplan, P. and Lummer, S.L. (1998) Update: GSCI Collateralized Futures as a Hedging Diversification Tool for Institutional Portfolios. Journal of Investing 7(4): 11-18.

Kara, Y., Boyacioglu, M.A. and Baykan, O.K. (2011) Predicting direction of stock price index movement using artificial neural networks and support vector machines: The sample of the Istanbul Stock Exchange. Expert Systems with Applications 38(5): 5311-5319.

Karlik, B. and Vehbi, A. (2011) Performance Analysis of Various Activation Functions in Generalized MLP Architectures of Neural Networks. International Journal of Artificial Intelligence and Expert Systems 1(4): 111-122.

Karolyi, G.A. and Kho, B.C. (2004) Momentum strategies: Some bootstrap tests. Journal of Empirical Finance 11(4): 509-536.

Karolyi, G.A. and Sanders, A.B. (1998) The Variation of Economic Risk Premiums in Real Estate Returns. Journal of Real Estate Finance and Economics 17(3): 245-262.

Karolyi, G.A. and Shannon, J. (1999) Where’s the Risk in Risk Arbitrage? Canadian Investment Review 12(2): 12-18.

Kau, J.B., Keenan, D.C., Muller, W.J., III and Epperson, J.F. (1995) The valuation at origination of fixed-rate mortgages with default and prepayment. Journal of Real Estate Finance and Economics 11(1): 5-36.

Kawaller, I.G., Koch, P.D. and Ludan, L. (2002) Calendar spreads, outright futures positions and risk. Journal of Alternative Investments 5(3): 59-74.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Kazemi, H. and Li, Y. (2009) Market timing of CTAs: An examination of systematic CTAs vs. discretionary CTAs. Journal of Futures Markets 29(11): 1067-1099.

Keane, F. (1996) Repo rate patterns for new Treasury notes. Federal Reserve Bank of New York, Current Issues in Economics and Finance 2(10): 1-6.

Kelly, J.L. (1956) A New Interpretation of Information Rate. Bell System Technical Journal 35(4): 917-926.

Kemp, K. (2007) Flipping confidential: The secrets of renovating property for profit in any market. Hoboken, NJ: John Wiley & Sons, Inc.

Kenett, D.Y., Ben-Jacob, E., Stanley, H.E. and gur-Gershgoren, G. (2013) How High Frequency Trading Affects a Market Index. Scientific Reports 3: 2110.

Kenyon, C. (2008) Inflation is normal. Risk, July 2008, pp. 76-82.

Khan, S.A. (2002) Merger Arbitrage: A Long-Term Investment Strategy. Journal of Wealth Management 4(4): 76-81.

Khandani, A. and Lo, A.W. (2011) What Happened to the Quants in August 2007? Evidence from Factors and Transactions Data. Journal of Financial Markets 14(1): 1-46.

Khang, C.H. (1983) A dynamic global portfolio immunization strategy in the world of multiple interest rate changes: A dynamic immunization and minimax theorem. Journal of Financial and Quantitative Analysis 18(3): 355-363.

Khuzwayo, B. and Mar´e, E. (2014) Aspects of volatility targeting for South African equity investors. South African Journal of Economic and Management Sciences 17(5): 691-699.

Kidd, D. (2014) Global Tactical Asset Allocation: One Strategy Fits All? In: Investment Risk and Performance. Charlottesville, VA: CFA Institute.

Kilgallen, T. (2012) Testing the Simple Moving Average across Commodities, Global Stock Indices, and Currencies. Journal of Wealth Management 15(1): 82-100.

Kim, I.J. (1990) The analytic valuation of American options. Review of Financial Studies 3(4): 547-572.

Kim, K. (2011) Performance Analysis of Pairs Trading Strategy Utilizing High Frequency Data with an Application to KOSPI 100 Equities. Working Paper. Available online: https://ssrn.com/abstract=1913707.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Kim, K.J. (2003) Financial time series forecasting using support vector machines. Neurocomputing 55(1-2): 307-319.

Kim, K.J. (2006) Artificial neural networks with evolutionary instance selection for financial forecasting. Expert Systems with Applications 30(3): 519-526.

Kim, Y. and Enke, D. (2016) Using neural networks to forecast volatility for an asset allocation strategy based on the target volatility. Procedia Computer Science 95: 281-286.

Kim, K. and Han, I. (2000) Genetic algorithms approach to feature discretization in artificial neural networks for the prediction of stock price index. Expert Systems with Applications 19(2): 125-132.

Kim, M.-K. and Leuthold, R.M. (1997) The Distributional Behavior of Futures Price Spread Changes: Parametric and Nonparametric Tests for Gold, T-Bonds, Corn, and Live Cattle. Working Paper. Available online: https:// ageconsearch.umn.edu/bitstream/14767/1/aceo9703.pdf.

Kim, G.H., Li, H. and Zhang, W. (2016) CDS-Bond Basis and Bond Return Predictability. Journal of Empirical Finance 38: 307-337.

Kim, G.H., Li, H. and Zhang, W. (2017) The CDS-Bond Basis Arbitrage and the Cross Section of Corporate Bond Returns. Journal of Futures Markets 37(8): 836-861.

Kim, Y.B., Kim, J.G., Kim, W., Im, J.H., Kim, T.H., Kang, S.J. and Kim, C.H. (2016) Predicting Fluctuations in Cryptocurrency Transactions Based on User Comments and Replies. PLoS ONE 11(8): e0161197.

King, R. (1986) Convertible Bond Valuation: An Empirical Test. Journal of Financial Research 9(1): 53-69.

King, T.H.D. and Mauer, D.C. (2014) Determinants of corporate call policy for convertible bonds. Journal of Corporate Finance 24: 112-134.

Kingma, D.P. and Ba, J. (2014) Adam: A Method for Stochastic Optimization. Working Paper. Available online: https://arxiv.org/pdf/1412.6980.

Kirby, C. and Ostdiek, B. (2012) It’s All in the Timing: Simple Active Portfolio Strategies that Outperform Na¨ıve Diversification. Journal of Financial and Quantitative Analysis 47(2): 437-467.

Kirilenko, A., Kyle, A., Samadi, M. and Tuzun, T. (2017) The Flash Crash: High-Frequency Trading in an Electronic Market. Journal of Finance 72(3): 967-998.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Kishore, V. (2012) Optimizing Pairs Trading of US Equities in a High Frequency Setting. Working Paper. Available online: https://repository.upenn.edu/cgi/viewcontent.cgi?article=1095& context=wharton\_research\_scholars.

Kitsul, Y. and Wright, J.H. (2013) The Economics of Options-Implied Inflation Probability Density Functions. Journal of Financial Economics 110(3): 696- 711.

Klingler, S. and Sundaresan, S.M. (2016) An Explanation of Negative Swap Spreads: Demand for Duration from Underfunded Pension Plans. Working Paper. Available online: https://ssrn.com/abstract=2814975.

Knight, J.R. (2002) Listing Price, Time on Market, and Ultimate Selling Price: Causes and Effects of Listing Price Changes. Real Estate Economics 30(2): 213-237.

Kobor, A., Shi, L. and Zelenko, I. (2005) What Determines U.S. Swap Spreads? World Bank Working Paper No. 62. Washington, DC: World Bank.

Kocherlakota, R., Rosenbloom, E. and Shiu, E. (1988) Algorithms for cashflow matching. Transactions of Society of Actuaries 40: 477-484.

Kocherlakota, R., Rosenbloom, E. and Shiu, E. (1990) Cash-flow matching and linear programming duality. Transactions of Society of Actuaries 42: 281-293.

Kochin, L. and Parks, R. (1988) Was the tax-exempt bond market inefficient or were future expected tax rates negative? Journal of Finance 43(4): 913-931.

Koijen, R.S.J., Moskowitz, T.J., Pedersen, L.H. and Vrugt, E.B. (2018) Carry. Journal of Financial Economics 127(2): 197-225.

Kolb, R.W. and Chiang, R. (1981) Improving Hedging Performance Using Interest Rate Futures. Financial Management 10(3): 72-79.

Kolb, R.W. and Chiang, R. (1982) Duration, Immunization, and Hedging with Interest Rate Futures. Journal of Financial Research 5(2): 161-170.

Konstantinidi, E. and Skiadopoulos, G. (2016) How does the market variance risk premium vary over time? Evidence from S&P 500 variance swap investment returns. Journal of Banking & Finance 62: 62-75.

Koopman, S.J., Lucas, A. and Schwaab, B. (2012) Dynamic factor models with macro, frailty, and industry effects for U.S. default counts: The credit crisis of 2008. Econometric Reviews 30(4): 521-532.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Korajczyk, R.A. and Murphy, D. (2017) High Frequency Market Making to Large Institutional Trades. Working Paper. Available online: https://ssrn. com/abstract=2567016.

Korajczyk, R.A. and Sadka, R. (2004) Are momentum profits robust to trading costs? Journal of Finance 59(3): 1039-1082.

Kordonis, J., Symeonidis, A. and Arampatzis, A. (2016) Stock Price Forecasting via Sentiment Analysis on Twitter. In: Proceedings of the 20th Pan-Hellenic Conference on Informatics (PCI’16). New York, NY: ACM, Article No. 36.

Kordos, M. and Cwiok, A. (2011) A new approach to neural network based stock trading strategy. In: Yin, H., Wang, W. and Rayward-Smith, V. (eds.) Intelligent Data Engineering and Automated Learning-IDEAL. Berlin, Germany: Springer, pp. 429-436.

Korkeamaki, T. and Michael, T.B. (2013) Where are they now? An analysis of the life cycle of convertible bonds. Financial Review 48(3): 489-509.

Korol, T. (2013) Early warning models against bankruptcy risk for Central European and Latin American enterprises. Economic Modelling 31: 22-30.

Kozhan, R., Neuberger, A. and Schneider, P. (2013) The Skew Risk Premium in the Equity Index Market. Review of Financial Studies 26(9): 2174-2203.

Kozhan, R. and Tham, W.W. (2012) Execution Risk in High-Frequency Arbitrage. Management Science 58(11): 2131-2149.

Kozhemiakin, A.V. (2007) The Risk Premium of Corporate Bonds. Journal of Portfolio Management 33(2): 101-109.

Kozicki, S. and Tinsley, P.A. (2012) Effective Use of Survey Information in Estimating the Evolution of Expected Inflation. Journal of Money, Credit and Banking 44(1): 145-169.

Kozlov, M. and Petajisto, A. (2013) Global Return Premiums on Earnings Quality, Value, and Size. Working Paper. Available online: https://ssrn. com/abstract=2179247.

Kraenzlin, S. (2007) The characteristics and development of the Swiss franc repurchase agreement market. Financial Markets and Portfolio Management 21(2): 241-261.

Krainer, J. (2001) A Theory of Liquidity in Residential Real Estate Markets. Journal of Urban Economics 49(1): 32-53.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Krause, T., Ehsani, S. and Lien, D. (2014) Exchange-traded funds, liquidity and volatility. Applied Financial Economics 24(24): 1617-1630.

Krauss, C. (2017) Statistical arbitrage pairs trading strategies: Review and outlook. Journal of Economic Surveys 31(2): 513-545.

Krauss, C. and St¨ubinger, J. (2017) Non-linear dependence modelling with bivariate copulas: Statistical arbitrage pairs trading on the S&P 100. Applied Economics 23(1): 1-18.

Krishnamurthy, A. (2002) The Bond/Old-Bond Spread. Journal of Financial Economics 66(2): 463-506.

Kristoufek, L. (2015) What Are the Main Drivers of the Bitcoin Price? Evidence from Wavelet Coherence Analysis. PLoS ONE 10(4): e0123923.

Kroner, K.F. and Sultan, J. (1993) Time-Varying Distributions and Dynamic Hedging with Foreign Currency Futures. Journal of Financial and Quantitative Analysis 28(4): 535-551.

Kruttli, M., Monin, P. and Watugala, S.W. (2018) Investor Concentration, Flows, and Cash Holdings: Evidence from Hedge Funds. Working Paper. Available online: https://ssrn.com/abstract=3031663.

Kryzanowski, L., Galler, M. and Wright, D. (1993) Using Artificial Neural Networks to Pick Stocks. Financial Analysts Journal 49(4): 21-27.

Kuberek, R.C. and Pefley, N.G. (1983) Hedging Corporate Debt with U.S. Treasury Bond Futures. Journal of Futures Markets 3(4): 345-353.

Kudryavtsev, A. (2012) Overnight stock price reversals. Journal of Advanced Studies in Finance 3(2): 162-170.

Kuhle, J. and Alvayay, J. (2000) The Efficiency of Equity REIT Prices. Journal of Real Estate Portfolio Management 6(4): 349-354.

Kumar, A. (2009) Who Gambles in the Stock Market? Journal of Finance 64(4): 1889-1933.

Kumar, V.A. (2012) Money Laundering: Concept, Significance and its Impact. European Journal of Business and Management 4(2): 113-119.

Kumar, M. and Thenmozhi, M. (2001) Forecasting Stock Index Movement: A Comparison of Support Vector Machines and Random Forest. Working Paper. Available online: https://ssrn.com/abstract=876544.

Kwok, Y.K. (2014) Game option models of convertible bonds: Determinants of call policies. Journal of Financial Engineering 1(4): 1450029.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Lafuente, J.A. (2013) Optimal cross-hedging under futures mispricing: A note. Journal of Derivatives & Hedge Funds 19(3): 181-188.

Lahmiri, S. (2014) Wavelet low- and high-frequency components as features for predicting stock prices with backpropagation neural networks. Journal of King Saud University – Computer and Information Sciences 26(2): 218-227.

Lai, H.-C., Tseng, T.-C. and Huang, S.-C. (2016) Combining value averaging and Bollinger Band for an ETF trading strategy. Applied Economics 48(37): 3550-3557.

Laitinen, E.K. and Laitinen, T. (2000) Bankruptcy prediction application of the Taylor’s expansion in logistic regression. International Review of Financial Analysis 9(4): 327-349.

Lakonishok, J., Lee, I., Pearson, N.D. and Poteshman, A.M. (2007) Option market activity. Review of Financial Studies 20(3): 813-857.

Lakonishok, J., Shleifer, A. and Vishny, R.W. (1994) Contrarian investment, extrapolation, and risk. Journal of Finance 49(5): 1541-1578.

Lakonishok, J. and Vermaelen, T. (1986) Tax-Induced Trading Around the Ex-Day. Journal of Financial Economics 16(3): 287-319.

Lambert, M., Papageorgiou, N. and Platania, F. (2006) Market Efficiency and Hedge Fund Trading Strategies. Working Paper. Available online: https://www.edhec.edu/sites/www.edhec-portail.pprod.net/files/ edhec\_working\_paper\_market\_efficiency\_and\_hedge\_fund\_trading\_ strategies\_f.compressed.pdf.

Lamoureux, C.G. and Lastrapes, W. (1993) Forecasting stock return variance: towards understanding stochastic implied volatility. Review of Financial Studies 6(2): 293-326.

Lamoureux, C. and Wansley, J. (1987) Market Effects of Changes in the S&P 500 Index. Financial Review 22(1): 53-69.

Landes, W.J., Stoffels, J.D. and Seifert, J.A. (1985) An Empirical Test of a Duration-Based Hedge: The Case of Corporate Bonds. Journal of Futures Markets 5(2): 173-182.

Lang, L.H.P., Litzenberger, R.H. and Liu, A.L. (1998) Determinants of Interest Rate Swap Spreads. Journal of Banking & Finance 22(12): 1507-1532.

Langetieg, T.C., Leibowitz, L. and Kogelman, S. (1990) Duration Targeting and the Management of Multiperiod Returns. Financial Analysts Journal 46(5): 35-45.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Larker, D. and Lys, T. (1987) An empirical analysis of the incentives to engage in costly information acquisition: The case of risk arbitrage. Journal of Financial Economics 18(1): 111-126.

Larkin, D.E., Babin, M.L. and Rose, C.A. (2004) Structuring European real estate private equity funds. Briefings in Real Estate Finance 3(3): 229-235.

Larsen, G. and Resnick, B. (1998) Empirical Insights on Indexing. Journal of Portfolio Management 25(1): 51-60.

Larsson, P. and Flohr, L. (2011) Optimal proxy-hedging of options on illiquid baskets. Working Paper. Available online: https://www.math.kth.se/ matstat/seminarier/reports/M-exjobb11/110131a.pdf.

Lasfer, M.A. (1995) Ex-Day Behavior: Tax or Short-Term Trading Effects. Journal of Finance 50(3): 875-897.

Laurent, J.-P. and Gregory, J. (2005) Basket Default Swaps, CDOs and Factor Copulas. Journal of Risk 7(4): 8-23.

Laurent, J.-P., Cousin, A. and Fermanian, J.D. (2011) Hedging default risks of CDOs in Markovian contagion models. Quantitative Finance 11(12): 1773- 1791.

Laureti, P., Medo, M. and Zhang, Y.-C. (2010) Analysis of Kelly-optimal portfolios. Quantitative Finance 10(7): 689-697.

Lautier, D. and Galli, A. (2004) Simple and extended Kalman filters: an application to term structures of commodity prices. Applied Financial Economics 14(13): 963-973.

Lazo, J.K., Lawson, M., Larsen, P.H. and Waldman, D.M. (2011) U.S. Economic Sensitivity to Weather Variability. Bulletin of the American Meteorological Society 92(6): 709-720.

Lebeck, W.W. (1978) Futures trading and hedging. Food Policy 3(1): 29-35.

Lee, S. (2010) The Changing Benefit of REITs to the Multi-Asset Portfolio. Journal of Real Estate Portfolio Management 16(3): 201-215.

Lee, D.K.C., Guo, L. and Wang, Y. (2018) Cryptocurrency: A New Investment Opportunity? Journal of Alternative Investments 20(3): 16-40.

Lee, H., Liao, T. and Tung, P. (2017) Investors’ Heterogeneity in Beliefs, the VIX Futures Basis, and S&P 500 Index Futures Returns. Journal of Futures Markets 37(9): 939-960.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Lee, S.B. and Oh, S.H. (1993) Managing non-parallel shift risk of yield curve with interest rate futures. Journal of Futures Markets 13(5): 515-526.

Lee, Y. and Oren, S. (2009) An equilibrium pricing model for weather derivatives in a multi-commodity setting. Energy Economics 31(5): 702-713.

Lee, S. and Stevenson, S. (2005) The Case for REITs in the Mixed-Asset Portfolio in the Short and Long Run. Journal of Real Estate Portfolio Management 11(1): 55-80.

Leggio, K. and Lien, D. (2002) Hedging gas bills with weather derivatives. Journal of Economics and Finance 26(1): 88-100.

Lehecka, G.V. (2013) Hedging and Speculative Pressures: An Investigation of the Relationships among Trading Positions and Prices in Commodity Futures Markets. In: Proceedings of the NCCC-134 Conference on Applied Commodity Price Analysis, Forecasting, and Market Risk Management. Available online: http://www.farmdoc.illinois.edu/nccc134/conf\_2013/pdf/ Lehecka\_NCCC-134\_2013.pdf.

Lehmann, B.N. (1990) Fads, Martingales, and Market Efficiency. Quarterly Journal of Economics 105(1): 1-28.

Leibowitz, M.L. and Bova, A. (2013) Duration Targeting and Index Convergence. Morgan Stanley Investment Management Journal 3(1): 73-80.

Leibowitz, M.L., Bova, A. and Kogelman, S. (2014) Long-Term Bond Returns under Duration Targeting. Financial Analysts Journal 70(1): 31-51.

Leibowitz, M.L., Bova, A. and Kogelman, S. (2015) Bond Ladders and Rolling Yield Convergence. Financial Analysts Journal 71(2): 32-46.

Leigland, J. (2018) Changing Perceptions of PPP Risk and Return: The Case of Brownfield Concessions. Journal of Structured Finance 23(4): 47-56.

Leland, H. and Connor, G. (1995) Optimal Cash Management for Investment Funds. Research Program in Finance Working Papers, No. RPF-244. Berkeley, CA: University of California at Berkeley.

Leland, E.C. and Panos, N. (1997) The Puttable Bond Market: Structure, Historical Experience, and Strategies. Journal of Fixed Income 7(3): 47-60.

Le Moigne, C. and Viveiros, E. (2008) Private Real Estate as an Inflation ´ Hedge: An Updated Look with a Global Perspective. Journal of Real Estate Portfolio Management 14(4): 263-286.

Leontsinis, S. and Alexander, C. (2016) Arithmetic variance swaps. Quantitative Finance 17(4): 551-569.

Lessambo, F.I. (2016) International Aspects of the US Taxation System. New York, NY: Palgrave Macmillan.

Leung, T., Li, J., Li, X. and Wang, Z. (2016) Speculative Futures Trading under Mean Reversion. Asia-Pacific Financial Markets 23(4): 281-304.

Leung, C.K.Y. and Tse, C.-Y. (2013) Flippers in housing market search. Working Paper. Available online: https://hub.hku.hk/bitstream/10722/ 190689/1/Content.pdf.

Levi, M. and Reuter, P. (2006) Money Laundering. Crime and Justice 34(1): 289-375.

Levin, A. and Davidson, A. (2005) Prepayment Risk-and Option-Adjusted Valuation of MBS. Journal of Portfolio Management 31(4): 73-85.

Levine, A. and Pedersen, L.H. (2016) Which Trend Is Your Friend? Financial Analysts Journal 72(3): 51-66.

Levis, M. and Liodakis, M. (1999) The Profitability of Style Rotation Strategies in the United Kingdom. Journal of Portfolio Management 26(1): 73-86.

Levitt, S.D. and Syverson, C. (2008) Market Distortions When Agents Are Better Informed: The Value of Information in Real Estate Transactions. Review of Economics and Statistics 90(4): 599-611.

Levy, P.S. (1991) Approaches to Investing in Distressed Securities: Active Approaches. In: Bowman, T.A. (ed.) Analyzing Investment Opportunities in Distressed and Bankrupt Companies. (AIMR Conference Proceedings, Vol. 1991, Iss. 1.) Chicago, IL: AIMR, pp. 44-46.

Levy, A. and Lieberman, O. (2013) Overreaction of country ETFs to US market returns: Intraday vs. daily horizons and the role of synchronized trading. Journal of Banking & Finance 37(5): 1412-1421.

Lewis, K. (1995) Puzzles in International Financial Markets. In: Grossman G.M. and Rogoff, K. (eds.) Handbook of International Economics, Vol. 3. Amsterdam, The Netherlands: North-Holland, Chapter 37.

Lewis, M. (2014) Flash Boys: A Wall Street Revolt. New York, NY: W.W. Norton & Company, Inc.

Lewis, C.M., Rogalski, R.J. and Seward, J.K. (1999) Is convertible debt a substitute for straight debt or for common equity? Financial Management 28(3): 5-27.

Lewis, C.M. and Verwijmeren, P. (2011) Convertible security design and contract innovation. Journal of Corporate Finance 17(4): 809-831.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Lhabitant, F.-S. (2002) Hedge Funds: Myths and Limits. Chichester, UK: John Wiley & Sons, Ltd.

L’Hoir, M. and Boulhabel, M. (2010) A Bond-Picking Model for Corporate Bond Allocation. Journal of Portfolio Management 36(3): 131-139.

Li, D.X. (2000) On default correlation: a copula function approach. Journal of Fixed Income 9(4): 43-54.

Li, T.R., Chamrajnagar, A.S., Fong, X.R., Rizik, N.R. and Fu, F. (2018) Sentiment-Based Prediction of Alternative Cryptocurrency Price Fluctuations Using Gradient Boosting Tree Model. Working Paper. Available online: https://arxiv.org/pdf/1805.00558.pdf.

Li, X., Deng, X., Zhu, S., Wang, F. and Xie, H. (2014) An intelligent market making strategy in algorithmic trading. Frontiers of Computer Science 8(4): 596-608.

Li, B., Hoi, S.C.H., Sahoo, D. and Liu, Z.-Y. (2015) Moving average reversion strategy for on-line portfolio selection. Artificial Intelligence 222: 104-123.

Li, L. and Kleindorfer, P.R. (2009) On hedging spark spread options in electricity markets. Risk and Decision Analysis 1(4): 211-220.

Li, X., Sullivan, R.N. and Garcia-Feij´oo, L. (2014) The Limits to Arbitrage and the Low-Volatility Anomaly. Financial Analysts Journal 70(1): 52-63.

Li, X., Sullivan, R.N. and Garcia-Feij´oo, L. (2016) The Low-Volatility Anomaly: Market Evidence on Systematic Risk vs. Mispricing. Financial Analysts Journal 72(1): 36-47.

Li, Y. and Wang, K. (1995) The Predictability of REIT Returns and Market Segmentation. Journal of Real Estate Research 10(5): 471-482.

Li, P. and Yang, J. (2017) Pricing Collar Options with Stochastic Volatility. Discrete Dynamics in Nature and Society 2017: 9673630.

Li, B., Zhao, P., Hoi, S.C.H. and Gopalkrishnan, V. (2012) PAMR: Passive aggressive mean reversion strategy for portfolio selection. Machine Learning 87(2): 221-258.

Liao, G.Y. (2016) Credit migration and covered interest rate parity. Working Paper. Available online: http://scholar.harvard.edu/files/gliao/ files/creditcip.pdf.

Lien, D. (1992) Optimal Hedging and Spreading in Cointegrated Markets. Economics Letters 40(1): 91-95.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Lien, D. (2004) Cointegration and the Optimal Hedge Ratio: The General Case. Quarterly Review of Economics and Finance 44(5): 654-658.

Lien, D. (2010) The effects of skewness on optimal production and hedging decisions: An application of the skew-normal distribution. Journal of Futures Markets 30(3): 278-289.

Lien, D. and Luo, X. (1993) Estimating Multiperiod Hedge Ratios in Cointegrated Markets. Journal of Futures Markets 13(8): 909-920.

Lien, D. and Tse, Y.K. (2000) Hedging downside risk with futures contracts. Applied Financial Economics 10(2): 163-170.

Lien, D. and Wang, Y. (2015) Effects of skewness and kurtosis on production and hedging decisions: A skewed t distribution approach. European Journal of Finance 21(13-14): 1132-1143.

Liew, J.K.-S. and Budav´ari, T. (2016) Do Tweet Sentiments Still Predict the Stock Market? Working Paper. Available online: https://ssrn.com/ abstract=2820269.

Liew, J.K.-S., Li, R.Z. and Budav´ari, T. (2018) Crypto-Currency Investing Examined. Working Paper. Available online: https://ssrn.com/abstract= 3157926.

Liew, J.K.-S. and Mayster, B. (2018) Forecasting ETFs with Machine Learning Algorithms. Journal of Alternative Investments 20(3): 58-78.

Liew, J. and Roberts, R. (2013) U.S. Equity Mean-Reversion Examined. Risks 1(3): 162-175.

Liew, J. and Vassalou, M. (2000) Can Book-to-Market, Size and Momentum be Risk Factors that Predict Economic Growth? Journal of Financial Economics 57(2): 221-245.

Liew, R. and Wu, Y. (2013) Pairs trading: A copula approach. Journal of Derivatives & Hedge Funds 19(1): 12-30.

Lin, L., Lan, L.-H. and Chuang, S.-s. (2013) An Option-Based Approach to Risk Arbitrage in Emerging Markets: Evidence from Taiwan Takeover Attempts. Journal of Forecasting 32(6): 512-521.

Lin, Y.-X., McCrae, M. and Gulati, C. (2006) Loss protection in pairs trading through minimum profit bounds: A cointegration approach. Journal of Applied Mathematics and Decision Sciences 2006(4): 1-14.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Lin, S.-Y. and Shyy, G. (2008) Credit Spreads, Default Correlations and CDO Tranching: New Evidence from CDS Quotes. Working Paper. Available online: https://ssrn.com/abstract=496225.

Lin, C.Y. and Yung, K. (2004) Real Estate Mutual Funds: Performance and Persistence. Journal of Real Estate Research 26(1): 69-93.

Lindahl, M. (1992) Minimum variance hedge ratios for stock index futures: duration and expiration effects. Journal of Futures Markets 12(1): 33-53.

Lioui, A. and Poncet, P. (2005) General equilibrium pricing of CPI derivatives. Journal of Banking & Finance 29(5): 1265-1294.

Litterman, R.B. and Scheinkman, J. (1991) Common Factors Affecting Bond Returns. Journal of Fixed Income 1(1): 54-61.

Litzenberger, R.H. and Rabinowitz, N. (1995) Backwardation in oil futures markets: Theory and empirical evidence. Journal of Finance 50(3): 1517- 1545.

Liu, B., Chang, L.B. and Geman, H. (2017) Intraday pairs trading strategies on high frequency data: The case of oil companies. Quantitative Finance 17(1): 87-100.

Liu, B. and Dash, S. (2012) Volatility ETFs and ETNs. Journal of Trading 7(1): 43-48.

Liu, J., Longstaff, F.A. and Mandell, R.E. (2006) The Market Price of Risk in Interest Rate Swaps: The Roles of Default and Liquidity Risks. Journal of Business 79(5): 2337-2360.

Liu, C.H. and Mei, J. (1992) The Predictability of Returns on Equity REITs and their Co-Movement with Other Assets. Journal of Real Estate Finance and Economics 5(4): 401-418.

Liu, F., Pantelous, A.A. and von Mettenheim, H.-J. (2018) Forecasting and trading high frequency volatility on large indices. Quantitative Finance 18(5): 737-748.

Liu, P. and Tang, K. (2010) No-arbitrage conditions for storable commodities and the models of futures term structures. Journal of Banking & Finance 34(7): 1675-1687.

Liu, P. and Tang, K. (2011) The stochastic behavior of commodity prices with heteroscedasticity in the convenience yield. Journal of Empirical Finance 18(2): 211-224.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Liu, Z.F. and van der Heijden, T. (2016) Model-Free Risk-Neutral Moments and Proxies. Working Paper. Available online: https://ssrn.com/ abstract=2641559.

Liu, J.-G. and Xu, E. (1998) Pricing of mortgage-backed securities with optionadjusted spread. Managerial Finance 24(9-10): 94-109.

Liu, L.X. and Zhang, L. (2008) Momentum Profits, Factor Pricing, and Macroeconomic Risk. Review of Financial Studies 21(6): 2417-2448.

Liverance, E. (2010) Variance Swap. In: Cont, R. (ed.) Encyclopedia of Quantitative Finance. Hoboken, NJ: John Wiley & Sons, Inc.

Livnat, J. and Mendenhall, R.R. (2006) Comparing the post-earnings announcement drift for surprises calculated from analyst and time series forecasts. Journal of Accounting Research 44(1): 177-205.

Lo, A. (2008) Where Do Alphas Come From?: A New Measure of the Value of Active Investment Management. Journal of Investment Management 6(2): 1-29.

Lo, A. (2016) What Is an Index? Journal of Portfolio Management 42(2): 21-36.

Lo, A.W. and MacKinlay, A.C. (1990) When Are Contrarian Profits Due to Stock Market Overreaction? Review of Financial Studies 3(3): 175-205.

Lo, A., Mamaysky, H. and Wang, J. (2000) Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation. Journal of Finance 55(4): 1705-1765.

Lo, A.W., Orr, A. and Zhang, R. (2017) The Growth of Relative Wealth and the Kelly Criterion. Working Paper. Available online: https://ssrn.com/ abstract=2900509.

Loh, R.K. and Warachka, M. (2012) Streaks in earnings surprises and the cross-section of stock returns. Management Science 58(7): 1305-1321.

Loncarski, I., ter Horst, J.R. and Veld, C.H. (2006) The Convertible Arbitrage Strategy Analyzed. Working Paper. Available online: https://pure.uvt.nl/ ws/files/779871/98.pdf.

Loncarski, I., ter Horst, J. and Veld, C. (2009) The Rise and Demise of the Convertible Arbitrage Strategy. Financial Analysts Journal 65(5): 35-50.

Longstaff, F. (2005) Borrower Credit and the Valuation of Mortgage-Backed Securities. Real Estate Economics 33(4): 619-661.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Longstaff, F.A. (2011) Municipal Debt and Marginal Tax Rates: Is There a Tax Premium in Asset Prices? Journal of Finance 66(3): 721-751.

Low, A., Muthuswamy, J., Sakar, S. and Terry, E. (2002) Multiperiod hedging with futures contracts. Journal of Futures Markets 22(12): 1179-1203.

Lozovaia, T. and Hizhniakova, H. (2005) How to Extend Modern Portfolio Theory to Make Money from Trading Equity Options. Working Paper. Available online: http://www.ivolatility.com/doc/Dispersion\_Article.pdf.

Lu, C.J., Lee, T.S. and Chiu, C. (2009) Financial time series forecasting using independent component analysis and support vector regression. Decision Support Systems 47(2): 115-125.

Lu, L., Wang, J. and Zhang, G. (2012) Long term performance of leveraged ETFs. Financial Services Review 21(1): 63-80.

Lucas, D.J., Goodman, L.S. and Fabozzi, F.J. (eds.) (2006) Collateralized Debt Obligations: Structures and Analysis. Hoboken, NJ: John Wiley & Sons, Inc.

Lucca, D.O. and Moench, E. (2012) The Pre-FOMC Announcement Drift. Journal of Finance 70(1): 329-371.

Lummer, S.L. and Siegel, L.B. (1993) GSCI Collateralized Futures: A Hedging and Diversification Tool for Institutional Portfolio. Journal of Investing 2(2): 75-82.

Lumpkin, S.A. (1987) Repurchase and Reverse Repurchase Agreements. Federal Reserve Bank of Richmond, Economic Review 73(1): 15-23.

Lustig, H., Roussanov, N. and Verdelhan, A. (2011) Common Risk Factors in Currency Markets. Review of Financial Studies 24(11): 3731-3777.

Lustig, H., Roussanov, N. and Verdelhan, A. (2014) Countercyclical currency risk premia. Journal of Financial Economics 111(3): 527-553.

Lustig, H. and Verdelhan, A. (2007) The Cross-Section of Foreign Currency Risk Premia and US Consumption Growth Risk. American Economic Review 97(1): 89-117.

Ma, K., Mercer, M. and Walker, M. (1992) Rolling over futures contracts: A note. Journal of Futures Markets 12(2): 203-217.

Maaravi, Y. and Levy, A. (2017) When your anchor sinks your boat: Information asymmetry in distributive negotiations and the disadvantage of making the first offer. Judgment and Decision Making 12(5): 420-429.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Macaulay, F.R. (1938) Some theoretical problems suggested by the movements of interest rates, bond yields and stock prices in the United States since 1856. New York, NY: NBER, Inc.

MacKinnon, G.H. and Al Zaman, A. (2009) Real estate for the long term: the effect of return predictability on long-horizon allocations. Real Estate Economics 37(1): 117-153.

Mackintosh, P. (2017) It’s all about active ETFs. Journal of Index Investing 7(4): 6-15.

Madhavan, A. (2012) Exchange-Traded Funds, Market Structure, and the Flash Crash. Financial Analysts Journal 68(4): 20-35.

Madhavan, A.N. (2016) Exchange-Traded Funds and the New Dynamics of Investing. Oxford, UK: Oxford University Press.

Madura, J. and Ngo, T. (2008) Impact of ETF inception on the valuation and trading of component stocks. Applied Financial Economics 18(12): 995-1007.

Maghrebi, N., Kim, M. and Nishina, K. (2007) The KOSPI200 Implied Volatility Index: Evidence of Regime Shifts in Expected Volatility. Asia-Pacific Journal of Financial Studies 36(2): 163-187.

Maheswaran, K. and Yeoh, S.C. (2005) The Profitability of Merger Arbitrage: Some Australian Evidence. Australian Journal of Management 30(1): 111-126.

Malizia, E.E. and Simons, R.A. (1991) Comparing Regional Classifications for Real Estate Portfolio Diversification. Journal of Real Estate Research 6(1): 53-77.

Malkiel, B.G. (2014) Is Smart Beta Really Smart? Journal of Portfolio Management 40(5): 127-134.

Malpezzi, S. (1999) A Simple Error Correction Model of House Prices. Journal of Housing Economics 8(1): 27-62.

Maluf, Y.S. and Albuquerque, P.H.M. (2013) Empirical evidence: arbitrage with Exchange-traded Funds (ETFs) on the Brazilian market. Revista Contabilidade & Finan¸cas 24(61): 64-74.

Mancini-Griffoli, T. and Ranaldo, A. (2011) Limits to Arbitrage During the Crisis: Funding Liquidity Constraints and Covered Interest Parity. Working Paper. Available online: https://ssrn.com/abstract=1549668.

Mankiw, N.G. and Summers, L.H. (1984) Do Long-Term Interest Rates Overreact to Short-Term Interest Rates? Brookings Papers on Economic Activity, No. 1, pp. 223-242.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Mann, S.V. and Ramanlal, P. (1997) The relative performance of yield curve strategies. Journal of Portfolio Management 23(4): 64-70.

Manoliu, M. (2004) Storage options valuation using multilevel trees and calendar spreads. International Journal of Theoretical and Applied Finance 7(4): 425-464.

Maribu, K.M., Galli, A. and Armstrong, M. (2007) Valuation of spark-spread options with mean reversion and stochastic volatility. International Journal of Electronic Business Management 5(3): 173-181.

Mark, N.C. and Wu, Y. (2001) Rethinking Deviations From Uncovered Interest Parity: the Role of Covariance Risk and Noise. Economic Journal 108(451): 1686-1706.

Markowitz, H. (1952) Portfolio Selection. Journal of Finance 7(1): 77-91.

Markwardt, D., Lopez, C. and DeVol, R. (2016) The Economic Impact of Chapter 11 Bankruptcy versus Out-of-Court Restructuring. Journal of Applied Corporate Finance 28(4): 124-128.

Marques, C.R., Neves, P.D. and Sarmento, L.M. (2003) Evaluating core inflation indicators. Economic Modelling 20(4): 765-775.

Marshall, C.M. (2008) Volatility trading: Hedge funds and the search for alpha (new challenges to the efficient markets hypothesis) (Ph.D. Thesis). New York, NY: Fordham University. Available online: https://fordham.bepress.com/ dissertations/AAI3353774/.

Marshall, C.M. (2009) Dispersion trading: Empirical evidence from U.S. options markets. Global Finance Journal 20(3): 289-301.

Marshall, B.R., Cahan, R.H. and Cahan, J.M. (2008) Can commodity futures be profitably traded with quantitative market timing strategies? Journal of Banking & Finance 32(9): 1810-1819.

Marshall, B.R., Nguyen, N.H. and Visaltanachoti, N. (2013) ETF arbitrage: Intraday evidence. Journal of Banking & Finance 37(9): 3486-3498.

Martellini, L., Milhau, V. and Tarelli, A. (2015) Hedging Inflation-Linked Liabilities without Inflation-Linked Instruments through Long/Short Investments in Nominal Bonds. Journal of Fixed Income 24(3): 5-29.

Martellini, L., Priaulet, P. and Priaulet, S. (2002) Understanding the butterfly strategy. Journal of Bond Trading and Management 1(1): 9-19.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Martellini, L., Priaulet, P. and Priaulet, S. (2003) Fixed Income Securities: Valuation, Risk Management and Portfolio Strategies. Hoboken, NJ: John Wiley & Sons, Inc.

Martin, G. (2010) The Long-Horizon Benefits of Traditional and New Real Assets in the Institutional Portfolio. Journal of Alternative Investments 13(1): 6-29.

Martin, I. (2011) Simple Variance Swaps. Working Paper. Available online: http://www.nber.org/papers/w16884.

Martinelli, R. and Rhoads, N. (2010) Predicting Market Data Using The Kalman Filter, Part 1 and Part 2. Technical Analysis of Stocks & Commodities 28(1): 44-47; ibid. 28(2): 46-51.

Mart´ınez, B. and Torr´o, H. (2018) Hedging spark spread risk with futures. Energy Policy 113: 731-746.

Maslov, S. and Zhang, Y.-C. (1998) Optimal investment strategy for risky assets. International Journal of Theoretical and Applied Finance 1(3): 377- 387.

Matsypura, D. and Timkovsky, V.G. (2010) Combinatorics of Option Spreads: The Margining Aspect. Working Paper. Available online: https://ses.library.usyd.edu.au/bitstream/2123/8172/1/OMWP\_2010\_ 04.pdf.

Mauer, R. and Sebastian, S. (2002) Inflation Risk Analysis of European Real Estate Securities. Journal of Real Estate Research 24(1): 47-78.

Mayers, D. (1998) Why firms issue convertible bonds: The matching of financial and real investment options. Journal of Financial Economics 47(1): 83-102.

Mayhew, S. (1995) Implied Volatility. Financial Analysts Journal 51(4): 8-20.

Maze, S. (2012) Dispersion Trading in South Africa: An Analysis of Profitability and a Strategy Comparison. Working Paper. Available online: https: //ssrn.com/abstract=2398223.

Mazurczak, A. (2011) Development of Real Estate Investment Trust (REIT) regimes in Europe. Journal of International Studies 4(1): 115-123.

McCants, A. (2007) Goods at Pawn: The Overlapping Worlds of Material Possessions and Family Finance in Early Modern Amsterdam. Social Science History 31(2): 213-238.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

McComas, A. (2003) Getting technical with spreads. Futures Magazine, July 2013, pp. 52-55.

McConnell, J.J. and Buser, S.A. (2011) The Origins and Evolution of the Market for Mortgage-Backed Securities. Annual Review of Financial Economics 3: 173-192.

McConnell, J.J. and Schwartz, E.S. (1986) LYON Taming. Journal of Finance 41(3): 561-577.

McDevitt, D. and Kirwan, J. (2008) Corporate and Infrastructure-backed Inflation-linked Bonds. In: Benaben, B. and Goldenberg, S. (eds.) Inflation Risk and Products: The Complete Guide. London, UK: Risk Books, pp. 621- 641.

McDonald, R.L. (2001) Cross-Border Investing with Tax Arbitrage: The Case of German Dividend Tax Credits. Review of Financial Studies 14(3): 617-657.

Mcelroy, T. (2008) Exact formulas for the Hodrick-Prescott Filter. Econometrics Journal 11(1): 208-217.

McEnally, R.W. and Rice, M.L. (1979) Hedging Possibilities in the Flotation of Debt Securities. Financial Management 8(4): 12-18.

McKee, T.E. and Lensberg, T. (2002) Genetic programming and rough sets: A hybrid approach to bankruptcy classification. European Journal of Operational Research 138(2): 436-451.

McKenzie, J.A. (2002) A Reconsideration of the Jumbo/Non-Jumbo Mortgage Rate Differential. Journal of Real Estate Finance and Economics 25(2-3): 197- 213.

McMillan, L.G. (2002) Options as a Strategic Investment. (4th ed.) New York, NY: New York Institute of Finance.

Meen, G. (2002) The Time-Series Behavior of House Prices: A Transatlantic Divide? Journal of Housing Economics 11(1): 1-23.

Mehra, Y.P. (2002) Survey Measures of Expected Inflation: Revisiting the Issues of Predictive Content and Rationality. Federal Reserve Bank of Richmond, Economic Quarterly 88(3): 17-36.

Mei, J. and Gao, B. (1995) Price Reversals, Transaction costs and Arbitrage Profits in the Real Estate Securities Market. Journal of Real Estate Finance and Economics 11(2): 153-165.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Mei, J. and Liao, H.H. (1998) Risk Characteristics of Real Estate Related Securities: An Extension of Liu and Mei (1992). Journal of Real Estate Research 16(3): 279-290.

Meissner, G. (ed.) (2008) The Definitive Guide to CDOs. London, UK: Incisive Media.

Meissner, G. (2016) Correlation Trading Strategies: Opportunities and Limitations. Journal of Trading 11(4): 14-32.

Mendenhall, R. (2004) Arbitrage Risk and the Post-Earnings-Announcement Drift. Journal of Business 77(6): 875-894.

Menkhoff, L., Sarno, L., Schmeling, M. and Schrimpf, A. (2012) Currency momentum strategies. Journal of Financial Economics 106(3): 660-684.

Menkveld, A.J. (2013) High Frequency Trading and the New Market Makers. Journal of Financial Markets 16(4): 712-740.

Menkveld, A.J. (2016) The Economics of High-Frequency Trading: Taking Stock. Annual Review of Financial Economics 8: 1-24.

Mercurio, F. (2005) Pricing inflation-indexed derivatives. Quantitative Finance 5(3): 289-302.

Mercurio, F. and Moreni, N. (2006) Inflation with a smile. Risk 19(3): 70-75.

Mercurio, F. and Moreni, N. (2009) Inflation modelling with SABR dynamics. Risk, June 2009, pp. 106-111.

Mercurio, F. and Yildirim, Y. (2008) Modelling Inflation. In: Benaben, B. and Goldenberg, S. (eds.) Inflation Risks and Products: The Complete Guide. London, UK: Risk Books.

Merton, R.C. (1987) A Simple Model of Capital Market Equilibrium with Incomplete Information. Journal of Finance 42(3): 483-510.

Metghalchi, M., Marcucci, J. and Chang, Y.-H. (2012) Are moving average trading rules profitable? Evidence from the European stock markets. Applied Economics 44(12): 1539-1559.

Meziani, A.S. (2015) Active exchange-traded funds: Are we there yet? Journal of Index Investing 6(2): 86-98.

Mhaskar, H.N. and Micchelli, C.A. (1993) How to choose an activation function. In: Proceedings of the 6th International Conference on Neural Information Processing Systems (NIPS’93). San Francisco, CA: Morgan Kaufmann Publishers, Inc., pp. 319-326.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Miao, G.J. (2014) High frequency and dynamic pairs trading based on statistical arbitrage using a two-stage correlation and cointegration approach. International Journal of Economics and Finance 6(3): 96-110.

Miao, G.J., Wei, B. and Zhou, H. (2012) Ambiguity Aversion and Variance Premium. Working Paper. Available online: https://ssrn.com/abstract= 2023765.

Miffre, J. (2012) Hedging pressure-based long/short commodity strategy used for third generation commodity index. Risk, January 2012. Available online: https://www.risk.net/2247251.

Miffre, J. and Rallis, G. (2007) Momentum strategies in commodity futures markets. Journal of Banking & Finance 31(6): 1863-1886.

Milanov, K., Kounchev, O., Fabozzi, F.J., Kim, Y.S. and Rachev, S.T. (2013) A Binomial-Tree Model for Convertible Bond Pricing. Journal of Fixed Income 22(3): 79-94.

Miles, M. and Mahoney, J. (1997) Is commercial real estate an inflation hedge? Real Estate Finance 13(4): 31-45.

Miles, M. and McCue, T. (1984) Commercial Real Estate Returns. Real Estate Economics 12(3): 355-377.

Miller, M.H. (1977) Debt and taxes. Journal of Finance 32(2): 261-275.

Milonas, N.T. (1991) Measuring seasonalities in commodity markets and the half-month effect. Journal of Futures Markets 11(3): 331-346.

Milosevic, N. (2016) Equity Forecast: Predicting Long Term Stock Price Movement using Machine Learning. Journal of Economics Library 3(2): 288-294.

Miltersen, K.R. and Schwartz, E.S. (1998) Pricing of options on commodity futures with stochastic term structures of convenience yield and interest rates. Journal of Financial and Quantitative Analysis 33(1): 33-59.

Min, S., Lee, J. and Han, I. (2006) Hybrid genetic algorithms and support vector machines for bankruptcy prediction. Expert Systems with Applications 31(3): 652-660.

Minton, B.A. (1997) An empirical examination of basic valuation models for plain vanilla U.S. interest rate swaps. Journal of Financial Economics 44(2): 251-277.

Mitchell, M. and Pulvino, T. (2001) Characteristics of Risk and Return in Risk Arbitrage. Journal of Finance 56(6): 2135-2175.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Mittal, A. and Goel, A. (2012) Stock Prediction Using Twitter Sentiment Analysis. Working Paper. Palo Alto, CA: Stanford University.

Mitton, T. and Vorkink, K. (2007) Equilibrium Underdiversification and the Preference for Skewness. Review of Financial Studies 20(4): 1255-1288.

Mixon, S. (2007) The implied volatility term structure of stock index options. Journal of Empirical Finance 14(3): 333-354.

Mixon, S. (2011) What Does Implied Volatility Skew Measure? Journal of Derivatives 18(4): 9-25.

Mladina, P. (2014) Dynamic Asset Allocation with Horizon Risk: Revisiting Glide Path Construction. Journal of Wealth Management 16(4): 18-26.

Monkhouse, P.H.L. (1993) The Cost of Equity Under the Australian Dividend Imputation Tax System. Accounting and Finance 33(2): 1-18.

Monoyios, M. (2004) Performance of Utility-Based Strategies for Hedging Basis Risk. Quantitative Finance 4(3): 245-255.

Monoyios, M. and Sarno, L. (2002) Mean reversion in stock index futures markets: a nonlinear analysis. Journal of Futures Markets 22(4): 285-314.

Montelongo, A. and Chang, H.K. (2008) Flip and grow rich: The heart and mind of real estate investing. San Antonio, TX: Armondo Montelongo Worldwide, Inc.

Montrucchio, L. and Peccati, L. (1991) A note on Shiu-Fisher-Weil immunization theorem. Insurance: Mathematics and Economics 10(2): 125-131.

Moore, S., Toepke, J. and Colley, N. (2006) The encyclopedia of commodity and financial spreads. Hoboken, NJ: John Wiley & Sons, Inc.

Moosa, I. (2001) Triangular Arbitrage in the Spot and Forward Foreign Exchange Markets. Quantitative Finance 1(4): 387-390.

Moosa, I.A. (2003a) Two-Currency, Three-Currency and Multi-Currency Arbitrage. In: International Financial Operations: Arbitrage, Hedging, Speculation, Financing and Investment. Finance and Capital Markets Series. London, UK: Palgrave Macmillan, Chapter 1, pp. 1-18.

Moosa, I.A. (2003b) The sensitivity of the optimal hedge ratio to model specification. Finance Letters 1(1): 15-20.

Moran, M.T. and Dash, S. (2007) VIX Futures and Options: Pricing and Using Volatility Products to Manage Downside Risk and Improve Efficiency in Equity Portfolios. Journal of Trading 2(3): 96-105.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Morisawa, Y. (2009) Toward a Geometric Formulation of Triangular Arbitrage: An Introduction to Gauge Theory of Arbitrage. Progress of Theoretical Physics Supplement 179: 209-215.

Morse, D. and Shaw, W. (1988) Investing in Bankrupt Firms. Journal of Finance 43(5): 1193-1206.

Moskowitz, T.J. and Grinblatt, M. (1999) Do Industries Explain Momentum? Journal of Finance 54(4): 1249-1290.

Moskowitz, T.J., Ooi, Y.H. and Pedersen, L.H. (2012) Time Series Momentum. Journal of Financial Economics 104(2): 228-250.

Moss, A., Clare, A., Thomas, S. and Seaton, J. (2015) Trend Following and Momentum Strategies for Global REITs. Journal of Real Estate Portfolio Management 21(1): 21-31.

Mossman, C.E., Bell, G.G., Swartz, L.M. and Turtle, H. (1998) An empirical comparison of bankruptcy models. Financial Review 33(2): 35-54.

Mou, Y. (2010) Limits to Arbitrage and Commodity Index Investment: Front-Running the Goldman Roll. Working Paper. Available online: https://ssrn. com/abstract=1716841.

Mouakhar, T. and Roberge, M. (2010) The Optimal Approach to Futures Contract Roll in Commodity Portfolios. Journal of Alternative Investments 12(3): 51-60.

Moyer, S.G., Martin, D. and Martin, J. (2012) A Primer on Distressed Investing: Buying Companies by Acquiring Their Debt. Journal of Applied Corporate Finance 24(4): 59-76.

Mraoua, M. (2007) Temperature stochastic modelling and weather derivatives pricing: empirical study with Moroccan data. Afrika Statistika 2(1): 22-43.

Mueller, G.R. (1993) Refining Economic Diversification Strategies for Real Estate Portfolios. Journal of Real Estate Research 8(1): 55-68.

Mueller, G.R. and Laposa, S.P. (1995) Property-Type Diversification in Real Estate Portfolios: A Size and Return Perspective. Journal of Real Estate Portfolio Management 1(1): 39-50.

Mueller, A. and Mueller, G. (2003) Public and Private Real Estate in a Mixed-Asset Portfolio. Journal of Real Estate Portfolio Management 9(3): 193-203.

Mugwagwa, T., Ramiah, V., Naughton, T. and Moosa, I. (2012) The efficiency of the buy-write strategy: Evidence from Australia. Journal of International Financial Markets, Institutions and Money 22(2): 305-328.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

M¨uller, A. and Grandi, M. (2000) Weather Derivatives: A Risk Management Tool for Weather-sensitive Industries. Geneva Papers on Risk and Insurance 25(2): 273-287.

Mun, K.-C. (2016) Hedging bank market risk with futures and forwards. Quarterly Review of Economics and Finance 61: 112-125.

Mun, K.-C. and Morgan, G.E. (1997) Cross-hedging foreign exchange rate risks: The case of deposit money banks in emerging Asian countries. Pacific-Basin Finance Journal 5(2): 215-230.

Mun, J.C., Vasconcellos, G.M. and Kish, R. (2000) The contrarian overreaction hypothesis: An analysis of the US and Canadian stock markets. Global Finance Journal 11(1-2): 53-72.

Murphy, J.J. (1986) Technical analysis of the futures markets: A comprehensive guide to trading methods and applications. New York, NY: New York Institute of Finance.

Muthuswamy, J., Palmer, J., Richie, N. and Webb, R. (2011) High-Frequency Trading: Implications for Markets, Regulators, and Efficiency. Journal of Trading 6(1): 87-97.

Mwangi, C.I. and Duncan, M.O. (2012) An investigation into the existence of exchange rate arbitrage in the Mombasa spot market. International Journal of Humanities and Social Science 2(21): 182-196.

Myers, R.J. (1991) Estimating time-varying optimal hedge ratios on futures markets. Journal of Futures Markets 11(1): 39-53.

Nakamoto, S. (2008) Bitcoin: A Peer-to-Peer Electronic Cash System. Working Paper. Available online: https://bitcoin.org/bitcoin.pdf.

Nakano, M., Takahashi, A. and Takahashi, S. (2018) Bitcoin Technical Trading With Artificial Neural Network. Working Paper. Available online: https: //ssrn.com/abstract=3128726.

Nandy (Pal), S. and Chattopadhyay, A.Kr. (2016) Impact of Individual Stock Derivatives Introduction in India on Its Underlying Spot Market Volatility. Asia-Pacific Journal of Management Research and Innovation 12(2): 109-133.

Nartea, G. and Eves, C. (2010) Role of farm real estate in a globally diversified asset portfolio. Journal of Property Investment & Finance 28(3): 198-220.

Nashikkar, A., Subrahmanyam, M.G. and Mahanti, S. (2011) Liquidity and Arbitrage in the Market for Credit Risk. Journal of Financial and Quantitative Analysis 46(3): 627-656.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Nawalkha, S.K. and Chambers, D.R. (1996) An improved immunization strategy: M-absolute. Financial Analysts Journal 52(5): 69-76.

Nekrasov, V. (2014) Kelly Criterion for Multivariate Portfolios: A Model-Free Approach. Working Paper. Available online: https://ssrn.com/abstract= 2259133.

Nelken, I. (2006) Variance swap volatility dispersion. Derivatives Use, Trading & Regulation 11(4): 334-344.

Nelling, E. and Gyourko, J. (1998) The Predictability of Equity REIT Returns. Journal of Real Estate Research 16(3): 251-268.

Newell, G. (1996) The inflation-hedging characteristics of Australian commercial property: 1984-1995. Journal of Property Finance 7(1): 6-20.

Newell, G., Chau, K.W. and Wong, S.K. (2009) The significance and performance of infrastructure in China. Journal of Property Investment & Finance 27(2): 180-202.

Newell, G. and Peng, H.W. (2008) The role of US infrastructure in investment portfolios. Journal of Real Estate Portfolio Management 14(1): 21-34.

Newell, G., Peng, H.W. and De Francesco, A. (2011) The performance of unlisted infrastructure in investment portfolios. Journal of Property Research 28(1): 59-74.

Ng, K.Y. and Phelps, B.D. (2015) The Hunt for a Low-Risk Anomaly in the USD Corporate Bond Market. Journal of Portfolio Management 42(1): 63-84.

Ng, V.K. and Pirrong, S.C. (1994) Fundamentals and volatility: storage, spreads, and the dynamics of metals prices. Journal of Business 67(2): 203- 230.

Ng, J., Rusticus, T. and Verdi, R. (2008) Implications of Transaction Costs for the Post-Earnings Announcement Drift. Journal of Accounting Research 46(3): 661-696.

Nguyen, V.T.T. and Sercu, P. (2010) Tactical Asset Allocation with Commodity Futures: Implications of Business Cycle and Monetary Policy. Working Paper. Available online: https://ssrn.com/abstract=1695889.

Niblock, S.J. (2017) Flight of the Condors: Evidence on the Performance of Condor Option Spreads in Australia. Applied Finance Letters 6(1): 38-53.

Nielsen, M.J. and Schwartz, E.S. (2004) Theory of storage and the pricing of commodity claims. Review of Derivatives Research 7(1): 5-24.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Nisar, T.M. and Yeung, M. (2018) Twitter as a tool for forecasting stock market movements: A short-window event study. Journal of Finance and Data Science 4(2): 101-119.

Noh, J., Engle, R.F. and Kane, A. (1994) Forecasting volatility and option prices of the S&P500 Index. Journal of Derivatives 2(1): 17-30.

Nossman, M. and Wilhelmsson, A. (2009) Is the VIX Futures Market Able to Predict the VIX Index? A Test of the Expectation Hypothesis. Journal of Alternative Investments 12(2): 54-67.

Nothaft, F.E., Lekkas, V. and Wang, G.H.K. (1995) The Failure of the Mortgage-Backed Futures Contract. Journal of Futures Markets 15(5): 585- 603.

Novak, M.G. and Veluˇs¸cek, D. (2016) Prediction of stock price movement based on daily high prices. Quantitative Finance 16(5): 793-826.

Novy-Marx, R. (2009) Hot and Cold Markets. Real Estate Economics 37(1): 1-22.

Novy-Marx, R. (2013) The other side of value: The gross profitability premium. Journal of Financial Economics 108(1): 1-28.

Nyaradi, J. (2010) Super Sectors: How to Outsmart the Market Using Sector Rotation and ETFs. Hoboken, NJ: John Wiley & Sons, Inc.

Odean, T. (2002) Volume, Volatility, Price, and Profit When All Traders Are Above Average. Journal of Finance 53(6): 1887-1934.

O’Doherty, M.S. (2012) On the Conditional Risk and Performance of Financially Distressed Stocks. Management Science 58(8): 1502-1520.

Odom, M.D. and Sharda, R. (1990) A neural network model for bankruptcy prediction. In: Proceedings of the International Joint Conference on Neural Networks, Vol. 2. Washington, DC: IEEE, pp. 163-168.

Oetomo, T. and Stevenson, M. (2005) Hot or cold? A comparison of different approaches to the pricing of weather derivatives. Journal of Emerging Market Finance 4(2): 101-133.

Officer, M.S. (2004) Collars and renegotiation in mergers and acquisitions. Journal of Finance 59(6): 2719-2743.

Officer, M.S. (2006) The market pricing of implicit options in merger collars. Journal of Business 79(1): 115-136.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

O’Hara, M. (2015) High frequency market microstructure. Journal of Financial Economics 116(2): 257-270.

Ohlson, J.A. (1980) Financial Ratios and the Probabilistic Prediction of Bankruptcy. Journal of Accounting Research 18(1): 109-131.

Okunev, J. and White, D. (2003) Do Momentum-Based Strategies Still Work in Foreign Currency Markets? Journal of Financial and Quantitative Analysis 38(2): 425-447.

Olmo, J. and Pilbeam, K. (2009) The profitability of carry trades. Annals of Finance 5(2): 231-241.

Olszweski, F. and Zhou, G. (2013) Strategy diversification: Combining momentum and carry strategies within a foreign exchange portfolio. Journal of Derivatives & Hedge Funds 19(4): 311-320.

O’Neal, E.S. (2000) Industry Momentum and Sector Mutual Funds. Financial Analysts Journal 56(4): 37-49.

Opler, T., Pinkowitz, L., Stulz, R. and Williamson, R. (1999) The determinants and implications of corporate cash holdings. Journal of Financial Economics 52(1): 3-46.

Opp, C.C. (2017) Learning, Optimal Default, and the Pricing of Distress Risk. Working Paper. Available online: https://ssrn.com/abstract=2181441.

Ortalo-Magn´e, F. and Rady, S. (2006) Housing Market Dynamics: On the Contribution of Income Shocks and Credit Constraints. Review of Economic Studies 73(2): 459-485.

Ortisi, M. (2016) Bitcoin Market Volatility Analysis Using Grand Canonical Minority Game. Ledger 1: 111-118.

Osborne, M.J. (2005) On the computation of a formula for the duration of a bond that yields precise results. Quarterly Review of Economics and Finance 45(1): 161-183.

Osler, C.L. (2000) Support for Resistance: Technical Analysis and Intraday Exchange Rates. Federal Reserve Bank of New York, Economic Policy Review 6(2): 53-68.

Osler, C.L. (2003) Currency Orders and Exchange Rate Dynamics: An explanation for the predictive success of Technical Analysis. Journal of Finance 58(5): 1791-1819.

Osteryoung, J.S., McCarty, D.E. and Roberts, G.S. (1981) Riding the Yield Curve with Treasury Bills. Financial Review 16(3): 57-66.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Osu, B.O. (2010) Currency Cross Rate and Triangular Arbitrage in Nigerian Exchange Market. International Journal of Trade, Economics and Finance 1(4): 345-348.

O’Tool, R. (2013) The Black-Litterman model: A risk budgeting perspective. Journal of Asset Management 14(1): 2-13.

Ou, P. and Wang, H. (2009) Prediction of stock market index movement by ten data mining techniques. Modern Applied Science 3(12): 28-42.

Oyedele, J.B., Adair, A. and McGreal, S. (2014) Performance of global listed infrastructure investment in a mixed asset portfolio. Journal of Property Research 31(1): 1-25.

Ozdagli, A.K. (2010) The Distress Premium Puzzle. Working Paper. Available online: https://ssrn.com/abstract=1713449.

Oztekin, A.S., Mishra, S., Jain, P.K., Daigler, R.T., Strobl, S. and Holowczak, R.D. (2017) Price Discovery and Liquidity Characteristics for U.S. Electronic Futures and ETF Markets. Journal of Trading 12(2): 59-72.

Packer, F. and Zhu, H. (2005) Contractual terms and CDS pricing. BIS Quarterly Review, March 2005, pp. 89-100. Available online: https://www.bis. org/publ/qtrpdf/r\_qt0503h.pdf.

Pagnotta, E. and Philippon, T. (2012) Competing on Speed. Working Paper. Available online: https://ssrn.com/abstract=1972807.

Pagolu, V.S., Reddy, K.N., Panda, G. and Majhi, B. (2016) Sentiment analysis of Twitter data for predicting stock market movements. In: Proceedings of the 2016 International Conference on Signal Processing, Communication, Power and Embedded System (SCOPES). Washington, DC: IEEE, pp. 1345-1350.

Pagonidis, A.S. (2014) The IBS Effect: Mean Reversion in Equity ETFs. Working Paper. Available online: http://www.naaim.org/wp-content/uploads/2014/04/00V\_Alexander\_ Pagonidis\_The-IBS-Effect-Mean-Reversion-in-Equity-ETFs-1.pdf.

Pan, J. and Poteshman, A.M. (2006) The Information in Option Volume for Future Stock Prices. Review of Financial Studies 19(3): 871-908.

Panayiotou, A. and Medda, F.R. (2014) Attracting Private Sector Participation in Transport Investment. Procedia – Social and Behavioral Sciences 111: 424-431.

Panayiotou, A. and Medda, F. (2016) Portfolio of Infrastructure Investments: Analysis of European Infrastructure. Journal of Infrastructure Systems 22(3): 04016011.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Pantalone, C. and Platt, H. (1984) Riding the Yield Curve. Journal of Financial Education, No. 13, pp. 5-9.

Papageorgiou, N.A., Reeves, J.J. and Sherris, M. (2017) Equity investing with targeted constant volatility exposure. Working Paper. Available online: https://ssrn.com/abstract=2614828.

Park, K., Jung, M. and Lee, S. (2018) Credit ratings and convertible bond prices: a simulation-based valuation. European Journal of Finance 24(12): 1001-1025.

Parnaudeau, M. and Bertrand, J.-L. (2018) The contribution of weather variability to economic sectors. Applied Economics 50(43): 4632-4649.

Pascalau, R. and Poirier, R. (2015) Bootstrapping the Relative Performance of Yield Curve Strategies. Journal of Investment Strategies 4(2): 55-81.

Paschke, R. and Prokopczuk, M. (2012) Investing in commodity futures markets: can pricing models help? European Journal of Finance 18(1): 59-87.

Passmore, W., Sherlund, S.M. and Burgess, G. (2005) The Effect of Housing Government-Sponsored Enterprises on Mortgage Rates. Real Estate Economics 33(3): 427-463.

P´astor, L’. and Stambaugh, R.F. (2003) Liquidity Risk and Expected Stock Returns. Journal of Political Economy 111(3): 642-685.

P¨at¨ari, E. and Vilska, M. (2014) Performance of moving average trading strategies over varying stock market conditions: the Finnish evidence. Applied Economics 46(24): 2851-2872.

Pelaez, R.F. (1997) Riding the yield curve: Term premiums and excess returns. Review of Financial Economics 6(1): 113-119.

Peng, H.W. and Newell, G. (2007) The Significance of Infrastructure in Australian Investment Portfolios. Pacific Rim Property Research Journal 13(4): 423-450.

Pennacchi, G.G. (1991) Identifying the Dynamics of Real Interest Rates and Inflation: Evidence Using Survey Data. Review of Financial Studies 4(1): 53- 86.

Pepi´c, M. (2014) Managing interest rate risk with interest rate futures. Ekonomika preduze´ca 62(3-4): 201-209.

Perchanok, K. (2012) Futures spreads: theory and praxis (Ph.D. Thesis). Northampton, UK: The University of Northampton. Available online: http: //nectar.northampton.ac.uk/4963/1/Perchanok20124963.pdf.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Perchanok, K. and Kakabadse, N. (2013) Causes of Market Anomalies of Crude Oil Calendar Spreads: Does Theory of Storage Address the Issue? Problems and Perspectives in Management 11(2): 35-47.

Perchet, R., de Carvalho, R.L. and Moulin, P. (2014) Intertemporal risk parity: a constant volatility framework for factor investing. Journal of Investment Strategies 4(1): 19-41.

Perez-Gonzalez, F. and Yun, H. (2010) Risk Management and Firm Value: Evidence from Weather Derivatives. Working Paper. Available online: https: //ssrn.com/abstract=1357385.

Peri´c, M.R. (2015) Ekonomski aspekti korporativnih bankrotstava i steˇcajnih procesa. Belgrade, Serbia: Modern Business School.

Perlin, M.S. (2009) Evaluation of pairs-trading strategy at the Brazilian financial market. Journal of Derivatives & Hedge Funds 15(2): 122-136.

Person, J.L. (2007) Candlestick and Pivot Point Trading Triggers. Hoboken, NJ: John Wiley & Sons, Inc.

Peterson, J.D. and Hsieh, C.-H. (1997) Do Common Risk Factors in the Returns on Stocks and Bonds Explain Returns on REITs? Real Estate Economics 25(2): 321-345.

Petre, G. (2015) A Case for Dynamic Asset Allocation for Long Term Investors. Procedia Economics and Finance 29: 41-55.

Pflueger, C.E. and Viceira, L.M. (2011) Inflation-Indexed Bonds and the Expectations Hypothesis. Annual Review of Financial Economics 3: 139-158.

Philosophov, L.V. and Philosophov, V.L. (2005) Optimization of a firm’s capital structure: A quantitative approach based on a probabilistic prognosis of risk and time of bankruptcy. International Review of Financial Analysis 14(2): 191-209.

Piazzesi, M. and Schneider, M. (2009) Momentum Traders in the Housing Market: Survey Evidence and a Search Model. American Economic Review 99(2): 406-411.

Picou, G. (1981) Managing Interest Rate Risk with Interest Rate Futures. Bankers Magazine, Vol. 164, May-June 1981, pp. 76-81.

Pindado, J., Rodrigues, L. and de la Torre, C. (2008) Estimating financial distress likelihood. Journal of Business Research 61(9): 995-1003.

Pindyck, R.S. (2001) The dynamics of commodity spot and futures markets: a primer. Energy Journal 22(3): 1-30.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Piotroski, J.D. (2000) Value investing: The use of historical financial statement information to separate winners from losers. Journal of Accounting Research 38: 1-41.

Piotroski, J.D. and So, E.C. (2012) Identifying Expectation Errors in Value/ Glamour Strategies: A Fundamental Analysis Approach. Review of Financial Studies 25(9): 2841-2875.

Pirrong, C. (2005) Momentum in Futures Markets. Working Paper. Available online: https://ssrn.com/abstract=671841.

Pirrong, C. (2017) The economics of commodity market manipulation: A survey. Journal of Commodity Markets 5: 1-17.

Pisani, B. (2010) Man Vs. Machine: How Stock Trading Got So Complex. CNBC (September 13, 2010). Available online: https://www.cnbc.com/id/ 38978686.

Pitts, M. (1985) The Management of Interest Rate Risk: Comment. Journal of Portfolio Management 11(4): 67-69.

Pivar, W. (2003) Real Estate Investing From A to Z: The Most Comprehensive, Practical, and Readable Guide to Investing Profitably in Real Estate. New York, NY: McGraw-Hill, Inc.

Pizzutilo, F. (2013) A note on the effectiveness of pairs trading for individual investors. International Journal of Economics and Financial Issues 3(3): 763- 771.

Podobnik, B., Horvatic, D., Petersen, A.M., Uroˇsevi´c, B. and Stanley, H.E. (2010) Bankruptcy risk model and empirical tests. Proceedings of the National Academy of Sciences 107(43): 18325-18330.

Poitras, G. (1990) The distribution of gold futures spreads. Journal of Futures Markets 10(6): 643-659.

Pole, A. (2007) Statistical arbitrage: algorithmic trading insights and techniques. Hoboken, NJ: John Wiley & Sons, Inc.

Popper, H. (1993) Long-term covered interest parity: evidence from currency swaps. Journal of International Money and Finance 12(4): 439-448.

Porter, M.F. (1980) An Algorithm for Suffix Stripping. Program 14(3): 130- 137.

Poterba, J. (1986) Explaining the yield spread between taxable and tax exempt bonds. In: Rosen, H. (ed.) Studies in State and Local Public Finance. Chicago, IL: University of Chicago Press, pp. 5-48.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Poterba, J. (1989) Tax reform and the market for tax-exempt debt. Regional Science and Urban Economics 19(3): 537-562.

Poterba, J. and Sinai, T. (2008) Tax Expenditures for Owner-Occupied Housing: Deductions for Property Taxes and Mortgage Interest and the Exclusion of Imputed Rental Income. American Economic Review 98(2): 84-89.

Poterba, J.M. and Summers, L.H. (1988) Mean reversion in stock prices: evidence and implications. Journal of Financial Economics 22(1): 27-59.

Potjer, D. and Gould, C. (2007) Global Tactical Asset Allocation: Exploiting the opportunity of relative movements across asset classes and financial markets. London, UK: Risk Books.

Pounds, H. (1978) Covered Call Option Writing Strategies and Results. Journal of Portfolio Management 4(2): 31-42.

Prince, J.T. (2005) Investing in Collateralized Debt Obligations. CFA Institute Conference Proceedings 2005(1): 52-61.

Pring, M.J. (1985) Technical analysis explained: The successful investor’s guide to spotting investment trends and turning points. (3rd ed.) New York, NY: McGraw-Hill, Inc.

Prokopczuk, M. and Simen, C.W. (2014) The importance of the volatility risk premium for volatility forecasting. Journal of Banking & Finance 40: 303-320.

Putnam, G., III (1991) Investment Opportunities in Distressed Equities. In: Levine, S. (ed.) Handbook of Turnaround and Bankruptcy Investing. New York, NY: HarperCollins, pp. 196-207.

Puttonen, V. (1993) The ex ante profitability of index arbitrage in the new Finnish markets. Scandinavian Journal of Management 9(S1): 117-127.

Quintero, R.G. (1989) Acquiring the Turnaround Candidate. In: Levine, S. (ed.) The Acquisitions Manual. New York, NY: New York Institute of Finance, pp. 379-441.

Rad, H., Low, R.K.Y. and Faff, R. (2016) The profitability of pairs trading strategies: distance, cointegration and copula methods. Quantitative Finance 16(10): 1541-1558.

Rajan, A., McDermott, G. and Roy, R. (eds.) (2007) The Structured Credit Handbook. Hoboken, NJ: John Wiley & Sons, Inc.

Ramamurti, R. and Doh, J. (2004) Rethinking Foreign Infrastructure Investment in Developing Countries. Journal of World Business 39(2): 151-167.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Rao, V.K. (2011) Multiperiod Hedging using Futures: Mean Reversion and the Optimal Hedging Path. Journal of Risk and Financial Management 4(1): 133-161.

Rao, T. and Srivastava, S. (2012) Analyzing stock market movements using twitter sentiment analysis. In: Proceedings of the 2012 International Conference on Advances in Social Networks Analysis and Mining (ASONAM 2012). Washington, DC: IEEE, pp. 119-123.

Raulji, J.K. and Saini, J.R. (2016) Stop-Word Removal Algorithm and its Implementation for Sanskrit Language. International Journal of Computer Applications 150(2): 15-17.

Ready, R., Roussanov, N. and Ward, C. (2017) Commodity Trade and the Carry Trade: A Tale of Two Countries. Journal of Finance 72(6): 2629-2684.

Reddington, F.M. (1952) Review of the Principles of Life Insurance Valuations. Journal of the Institute of Actuaries 78(3): 286-340.

Refenes, A.N., Zapranis, A.S. and Francis, G. (1994) Stock Performance Modeling Using Neural Networks: Comparative Study with Regressive Models. Neural Networks 7(2): 375-388.

Rehring, C. (2012) Real Estate in a Mixed-Asset Portfolio: The Role of the Investment Horizon. Real Estate Economics 40(1): 65-95.

Reiss, M.F. and Phelps, T.G. (1991) Identifying a Troubled Company. In: Dinapoli, D., Sigoloff, S.C. and Cushman, R.F. (eds.) Workouts and Turnarounds: The Handbook of Restructuring and Investing in Distressed Companies. Homewood, IL: Business One-Irwin, pp. 7-43.

Reitano, R. (1996) Non-parallel yield curve shifts and stochastic immunization. Journal of Portfolio Management 22(2): 71-78.

Remolona, E.M., Wickens, M.R. and Gong, F.F. (1998) What Was the Market’s View of UK Monetary Policy? Estimating Inflation Risk and Expected Inflation with Indexed Bonds. Federal Reserve Bank of New York Staff Reports, No. 57. Available online: https://ssrn.com/abstract=937350.

Rendleman, R.J. (1999) Duration-Based Hedging with Treasury Bond Futures. Journal of Fixed Income 9(1): 84-91.

Rendleman, R.J., Jones, C.P. and Latan´e, H.A. (1982) Empirical anomalies based on unexpected earnings and the importance of risk adjustments. Journal of Financial Economics 10(3): 269-287.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Reynauld, J. and Tessier, J. (1984) Risk Premiums in Futures Markets: An Empirical Investigation. Journal of Futures Markets 4(2): 189-211.

Rhee, S.G. and Chang, R.P. (1992) Intra-Day Arbitrage Opportunities in Foreign Exchange and Eurocurrency Markets. Journal of Finance 47(1): 363-379.

Ribeiro, B., Silva, C., Chen, N., Vieira, A. and das Neves, J.C. (2012) Enhanced default risk models with SVM+. Expert Systems with Applications 39(11): 10140-10152.

Richard, S.F. and Roll, R. (1989) Prepayments on fixed-rate mortgage-backed securities. Journal of Portfolio Management 15(3): 73-82.

Richards, T., Manfredo, M. and Sanders, D. (2004) Pricing weather derivatives. American Journal of Agricultural Economics 86(4): 1005-1017.

Richie, N., Daigler, R.T. and Gleason, K.C. (2008) The limits to stock index arbitrage: Examining S&P 500 futures and SPDRS. Journal of Futures Markets 28(12): 1182-1205.

Rickards, D. (2008) Global Infrastructure – A Growth Story. In: Davis, H. (ed.) Infrastructure Finance: Trends and Techniques. London, UK: Euromoney Books, pp. 1-47.

Rime, D., Schrimpf, A. and Syrstad, O. (2017) Segmented Money Markets and Covered Interest Parity Arbitrage. Working Paper. Available online: https: //ssrn.com/abstract=2879904.

Riordan, R. and Storkenmaier, A. (2012) Latency, liquidity and price discovery. Journal of Financial Markets 15(4): 416-437.

Rising, J.K. and Wyner, A.J. (2012) Partial Kelly portfolios and shrinkage estimators. In: Proceedings of the 2012 International Symposium on Information Theory (ISIT). Washington, DC: IEEE, pp. 1618-1622.

R¨odel, M. and Rothballer, C. (2012) Infrastructure as Hedge against Inflation – Fact or Fantasy? Journal of Alternative Investments 15(1): 110-123.

Rodr´ıguez-Gonz´alez, A., Garc´ıa-Crespo, A., Colomo-Palacios, R., Iglesias, ´ F.G. and G´omez-Berb´ıs, J.M. (2011) CAST: Using neural networks to improve trading systems based on technical analysis by means of the RSI financial indicator. Expert Systems with Applications 38(9): 11489-11500.

Rogers, L.C.G. and Shi, Z. (1995) The Value of an Asian Option. Journal of Applied Probability 32(4): 1077-1088.

Roll, R. (1996) U.S. Treasury Inflation-Indexed Bonds: The Design of a New Security. Journal of Fixed Income 6(3): 9-28.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Roll, R. (2004) Empirical TIPS. Financial Analysts Journal 60(1): 31-53.

Roll, R. and Yan, S. (2008) An explanation of the forward premium ‘puzzle’. European Financial Management 6(2): 121-148.

Rompotis, G.G. (2011a) The performance of actively managed exchange traded funds. Journal of Index Investing 1(4): 53-65.

Rompotis, G.G. (2011b) Active vs. passive management: New evidence from exchange traded funds. International Review of Applied Financial Issues and Economics 3(1): 169-186.

Ronn, A.G. and Ronn, E.I. (1989) The Box Spread Arbitrage Conditions: Theory, Tests, and Investment Strategies. Review of Financial Studies 2(1): 91-108.

Rosales, E.B. and McMillan, D. (2017) Time-series and cross-sectional momentum and contrarian strategies within the commodity futures markets. Cogent Economics & Finance 5(1): 1339772.

Rosenberg, H. (1992) Vulture Investors. New York, NY: HarperCollins.

Rosenberg, B., Reid, K. and Lanstein, R. (1985) Persuasive evidence of market inefficiency. Journal of Portfolio Management 11(3): 9-16.

Ross, J. (2006) Exploiting spread trades. Futures Magazine, December 2006, pp. 34-36.

Ross, S. and Zisler, R. (1991) Risk and return in real estate. Journal of Real Estate Finance and Economics 4(2): 175-190.

Rothballer, C. and Kaserer, C. (2012) The Risk Profile of Infrastructure Investments: Challenging Conventional Wisdom. Journal of Structured Finance 18(2): 95-109.

Routledge, B., Seppi, D.J. and Spatt, C. (2000) Equilibrium forward curves for commodities. Journal of Finance 55(3): 1297-1338.

Rouwenhorst, K.G. (1998) International Momentum Strategies. Journal of Finance 53(1): 267-284.

Roy, O. and Vetterli, M. (2007) The effective rank: A measure of effective dimensionality. In: Proceedings – EUSIPCO 2007, 15th European Signal Processing Conference. Pozna´n, Poland (September 3-7), pp. 606-610.

Ruan, Y., Durresi, A. and Alfantoukh, L. (2018) Using Twitter trust network for stock market analysis. Knowledge-Based Systems 145: 207-218.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Ruchin, A. (2011) Can Securities Lending Transactions Substitute for Repurchase Agreement Transactions? Banking Law Journal 128(5): 450-480.

Ruder, S. (2017) An overview of gradient descent optimization algorithms. Working Paper. Available online: https://arxiv.org/pdf/1609.04747.pdf.

Rudy, J., Dunis, C. and Laws, J. (2010) Profitable Pair Trading: A Comparison Using the S&P 100 Constituent Stocks and the 100 Most Liquid ETFs. Working Paper. Available online: https://ssrn.com/abstract=2272791.

Rujivan, S. and Zhu, S.P. (2012) A simplified analytical approach for pricing discretely sampled variance swaps with stochastic volatility. Applied Mathematics Letters 25(11): 1644-1650.

Rumelhart, D.E., Hinton, G.E. and Williams, R.J. (1986) Learning representations by back-propagating errors. Nature 323(6088): 533-536.

Rusn´akov´a, M. and Solt´es, V. (2012) Long strangle strategy using barrier ˇ options and its application in hedging. Actual Problems of Economics 134(8): 452-465.

Rusn´akov´a, M., Solt´es, V. and Szabo, Z.K. (2015) Short Combo Strategy ˇ Using Barrier Options and its Application in Hedging. Procedia Economics and Finance 32: 166-179.

Ryabkov, N. (2015) Hedge Fund Price Pressure in Convertible Bond Markets. Working Paper. Available online: https://ssrn.com/abstract=2539929.

Saad, E.W., Prokhorov, D.V. and Wunsch, D.C. (1998) Comparative study of stock trend prediction using time delay, recurrent and probabilistic neural networks. IEEE Transactions on Neural Networks 9(6): 1456-1470.

Sack, B. and Elsasser, R. (2004) Treasury Inflation-Indexed Debt: A Review of the U.S. Experience. Federal Reserve Bank of New York, Economic Policy Review 10(1): 47-63.

Sadka, R. (2002) The Seasonality of Momentum: Analysis of Tradability. Working Paper. Available online: https://ssrn.com/abstract=306371.

Sagi, J. and Seasholes, M. (2007) Firm-specific Attributes and the Crosssection of Momentum. Journal of Financial Economics 84(2): 389-434.

Salcedo, Y. (2004) Spreads for the fall. Futures Magazine, September 2004, pp. 54-57.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Saltyte-Benth, J. and Benth, F.E. (2012) A critical view on temperature modelling for application in weather derivatives markets. Energy Economics 34(2): 592-602.

Samuelson, P.A. (1945) The effect of interest rate increases on the banking system. American Economic Review 35(1): 16-27.

Samuelson, P. (1971) The “fallacy” of maximizing the geometric mean in long sequences of investing or gambling. Proceedings of the National Academy of Sciences 68(10): 2493-2496.

Samuelson, W. and Rosenthal, L. (1986) Price Movements as Indicators of Tender Offer Success. Journal of Finance 41(2): 481-499.

Samworth, R.J. (2012) Optimal weighted nearest neighbour classifiers. Annals of Statistics 40(5): 2733-2763.

Sanchez-Robles, B. (1998) Infrastructure Investment and Growth: Some Empirical Evidence. Contemporary Economic Policy 16(1): 98-108.

Saretto, A. and Goyal, A. (2009) Cross-section of option returns and volatility. Journal of Financial Economics 94(2): 310-326.

Sassetti, P. and Tani, M. (2006) Dynamic Asset Allocation Using Systematic Sector Rotation. Journal of Wealth Management 8(4): 59-70.

Satchell, S. and Scowcroft, A. (2000) A demystification of the Black-Litterman model: Managing quantitative and traditional portfolio construction. Journal of Asset Management 1(2): 138-150.

Savor, P. and Wilson, M. (2013) How Much Do Investors Care About Macroeconomic Risk? Evidence from Scheduled Economic Announcements. Journal of Financial and Quantitative Analysis 48(2): 343-375.

Sawant, R.J. (2010a) Infrastructure Investing: Managing Risks & Rewards for Pensions, Insurance Companies & Endowments. Hoboken, NJ: John Wiley & Sons, Inc.

Sawant, R.J. (2010b) Emerging Market Infrastructure Project Bonds: Their Risks and Returns. Journal of Structured Finance 15(4): 75-83.

Schaede, U. (1990) The introduction of commercial paper – a case study in the liberalisation of the Japanese financial markets. Japan Forum 2(2): 215-234.

Schap, K. (2005) The complete guide to spread trading. New York, NY: McGraw-Hill, Inc.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Schatz, H.R. (2012) The Characterization of Repurchase Agreements in the Context of the Federal Securities Laws. St. John’s Law Review 61(2): 290-310.

Schiereck, D., Bondt, W.D. and Weber, M. (1999) Contrarian and momentum strategies in Germany. Financial Analysts Journal 55(6): 104-116.

Schiller, F., Seidler, G. and Wimmer, M. (2010) Temperature models for pricing weather derivatives. Quantitative Finance 12(3): 489-500.

Schizas, P. (2014) Active ETFs and their performance vis-\`a-vis passive ETFs, mutual funds, and hedge funds. Journal of Wealth Management 17(3): 84-98.

Schizas, P., Thomakos, D.D. and Wang, T. (2011) Pairs Trading on International ETFs. Working Paper. Available online: https://ssrn.com/ abstract=1958546.

Schmidhuber, J. (2015) Deep learning in neural networks: An overview. Neural Networks 61: 85-117.

Schmidt, W. and Ward, I. (2002) Pricing default baskets. Risk, January 2002, pp. 111-114.

Schneeweis, T. and Gupta, R. (2006) Diversification benefits of managed futures. Journal of Investment Consulting 8(1): 53-62.

Schneider, F. and Windischbauer, U. (2008) Money laundering: some facts. European Journal of Law and Economics 26(3): 387-404.

Scholes, M. and Williams, J. (1977) Estimating Betas from Nonsynchronous Data. Journal of Financial Economics 5(3): 309-327.

Sch¨onbucher, P.J. (2003) Credit Derivatives Pricing Models. Hoboken, NJ: John Wiley & Sons, Inc.

Schoutens, W. (2005) Moment swaps. Quantitative Finance 5(6): 525-530.

Schultz, G.M. (2016) Investing in Mortgage-Backed and Asset-Backed Securities: Financial Modeling with R and Open Source Analytics + Website. Hoboken, NJ: John Wiley & Sons, Inc.

Schumaker, R.P. and Chen, H. (2010) A Discrete Stock Price Prediction Engine Based on Financial News. Computer 43(1): 51-56.

Schwartz, E.S. (1997) The Stochastic Behavior of Commodity Prices: Implications for Valuation and Hedging. Journal of Finance 52(3): 923-973.

Schwartz, E.S. (1998) Valuing long-term commodity assets. Journal of Energy Finance & Development 3(2): 85-99.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Schwartz, T.V. and Laatsch, F. (1991) Price Discovery and Risk Transfer in Stock Index Cash and Futures Markets. Journal of Futures Markets 11(6): 669-683.

Schwartz, E.S. and Smith, J.E. (2000) Short-term variations and long-term dynamics in commodity prices. Management Science 46(7): 893-911.

Schwartz, E.S. and Torous, W.N. (1989) Prepayment and the Valuation of Mortgage-Backed Securities. Journal of Finance 44(2): 375-392.

Schwartz, E.S. and Torous, W.N. (1992) Prepayment, Default, and the Valuation of Mortgage Pass-through Securities. Journal of Business 65(2): 221-239.

Schwert, G.W. (2003) Anomalies and market efficiency. In: Constantinides, G.M., Harris, M. and Stulz, R.M. (eds.) Handbook of the Economics of Finance, Vol 1B. (1st ed.) Amsterdam, The Netherlands: Elsevier, Chapter 15, pp. 939-974.

Sefton, J.A. and Scowcroft, A. (2005) Understanding Momentum. Financial Analysts Journal 61(2): 64-82.

Seiler, M.J., Webb, J.R. and Myer, F.C.N. (1999) Diversification Issues in Real Estate Investment. Journal of Real Estate Literature 7(2): 163-179.

Sepp¨al¨a, J. (2004) The term structure of real interest rates: theory and evidence from UK index-linked bonds. Journal of Monetary Economics 51(7): 1509-1549.

Serban, A.F. (2010) Combining mean reversion and momentum trading strategies in foreign exchange markets. Journal of Banking & Finance 34(11): 2720- 2727.

Seymour, B. (2008) Global Money Laundering. Journal of Applied Security Research 3(3-4): 373-387.

Sezer, O.B., Ozbayoglu, M. and Dogdu, E. (2017) A Deep Neural-Network Based Stock Trading System Based on Evolutionary Optimized Technical Analysis Parameters. Procedia Computer Science 114: 473-480.

Shackman, J.D. and Tenney, G. (2006) The Effects of Government Regulations on the Supply of Pawn Loans: Evidence from 51 Jurisdictions in the US. Journal of Financial Services Research 30(1): 69-91.

Shah, A. (2017) Hedging of a Portfolio of Rainfall Insurances using Rainfall Bonds and European Call Options (Bull Spread). Working Paper. Available online: https://ssrn.com/abstract=2778647.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Shah, D. and Zhang, K. (2014) Bayesian regression and Bitcoin. Working Paper. Available online: https://arxiv.org/pdf/1410.1231.pdf.

Shaikh, I. and Padhi, P. (2015) The implied volatility index: Is ‘investor fear gauge’ or ‘forward-looking’? Borsa Istanbul Review 15(1): 44-52.

Shan, L., Garvin, M.J. and Kumar, R. (2010) Collar options to manage revenue risks in real toll public-private partnership transportation projects. Construction Management and Economics 28(10): 1057-1069.

Sharpe, W.F. (1966) Mutual Fund Performance. Journal of Business 39(1): 119-138.

Sharpe, W.F. (1994) The Sharpe Ratio. Journal of Portfolio Management 21(1): 49-58.

Sharpe, W.F. (2009) Adaptive Asset Allocation Policies. Financial Analysts Journal 66(3): 45-59.

Sharpe, W.F. and Perold, A.F. (1988) Dynamic Strategies for Asset Allocation. Financial Analysts Journal 44(1): 16-27.

Shaviro, D. (2002) Dynamic Strategies for Asset Allocation. Chicago Journal of International Law 3(2): 317-331.

Shen, P. (2006) Liquidity Risk Premia and Breakeven Inflation Rates. Federal Reserve Bank of Kansas City, Economic Review 91(2): 29-54.

Shen, P. and Corning, J. (2001) Can TIPS Help Identify Long-Term Inflation Expectations? Federal Reserve Bank of Kansas City, Economic Review 86(4): 61-87.

Sher, G. (2014) Cashing in for Growth: Corporate Cash Holdings as an Opportunity for Investment in Japan. Working Paper. Available online: https: //ssrn.com/abstract=2561246.

Sherrill, D.E. and Upton, K. (2018) Actively managed ETFs vs actively managed mutual funds. Managerial Finance 44(3): 303-325.

Shi, H.-L., Jiang, Z.-Q. and Zhou, W.-X. (2015) Profitability of Contrarian Strategies in the Chinese Stock Market. PLoS ONE 10(9): e0137892.

Shiller, R.J. (1979) The Volatility of Long-Term Interest Rates and Expectations Models of the Term Structure. Journal of Political Economy 87(6): 1190-1219.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Shiller, R.J. and Modigliani, F. (1979) Coupon and tax effects on new and seasoned bond yields and the measurement of the cost of debt capital. Journal of Financial Economics 7(3): 297-318.

Shimko, D.C. (1994) Options on futures spreads: Hedging, speculation, and valuation. Journal of Futures Markets 14(2): 183-213.

Shin, K. and Lee, Y. (2002) A genetic algorithm application in bankruptcy prediction modeling. Expert Systems with Applications 23(3): 321-328.

Shiu, E.S.W. (1987) On the Fisher-Weil immunization theorem. Insurance: Mathematics and Economics 6(4): 259-266.

Shiu, E.S.W. (1988) Immunization of multiple liabilities. Insurance: Mathematics and Economics 7(4): 219-224.

Shiu, Y.-M. and Lu, T.-H. (2011) Pinpoint and Synergistic Trading Strategies of Candlesticks. International Journal of Economics and Finance 3(1): 234- 244.

Shum, P., Hejazi, W., Haryanto, E. and Rodier, A. (2016) Intraday Share Price Volatility and Leveraged ETF Rebalancing. Review of Finance 20(6): 2379-2409.

Shumway, T. (2001) Forecasting Bankruptcy More Accurately: A Simple Hazard Model. Journal of Business 74(1): 101-104.

Siganos, A. and Chelley-Steeley, P. (2006) Momentum Profits Following Bull and Bear Markets. Journal of Asset Management 6(5): 381-388.

Sill, K. (1996) The Cyclical Volatility of Interest Rates. Business Review of the Federal Reserve Bank of Philadelphia, January/February 1996, pp. 15-29.

Simmons, E. (1954) Sales of Government Securities to Federal Reserve Banks Under Repurchase Agreements. Journal of Finance 9(1): 23-40.

Simon, D.P. and Campasano, J. (2014) The VIX Futures Basis: Evidence and Trading Strategies. Journal of Derivatives 21(3): 54-69.

Simpson, M.W. and Grossman, A. (2016) The Role of Industry Effects in Simultaneous Reversal and Momentum Patterns in One-Month Stock Returns. Journal of Behavioral Finance 17(4): 309-320.

Simutin, M. (2014) Cash Holdings and Mutual Fund Performance. Review of Finance 18(4): 1425-1464.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Sing, T.-F. and Low, S.-H.Y. (2000) The inflation-hedging characteristics of real estate and financial assets in Singapore. Journal of Real Estate Portfolio Management 6(4): 373-386.

Singh, Y. and Chandra, P. (2003) A class +1 sigmoidal activation functions for FFANNs. Journal of Economic Dynamics and Control 28(1): 183-187.

Singhal, S., Newell, G. and Nguyen, T.K. (2011) The significance and performance of infrastructure in India. Journal of Property Research 28(1): 15-34.

Siriopoulos, C. and Fassas, A. (2009) Implied Volatility Indices – A Review. Working Paper. Available online: https://ssrn.com/abstract=1421202.

Skelton, J.L. (1983) Banks, firms and the relative pricing of tax-exempt and taxable bonds. Journal of Financial Economics 12(3): 343-355.

Skiadopoulos, G. (2004) The Greek implied volatility index: construction and properties. Applied Financial Economics 14(16): 1187-1196.

Skiadopoulos, G., Hodges, S. and Clewlow, L. (1999) The Dynamics of the S&P 500 Implied Volatility Surface. Review of Derivatives Research 3(3): 263- 282.

Slowinski, R. and Zopounidis, C. (1995) Application of the rough set approach to evaluation of bankruptcy risk. Intelligent Systems in Accounting, Finance and Management 4(1): 27-41.

Smit, H.T.J. and Trigeorgis, L. (2009) Valuing infrastructure investment: An option games approach. California Management Review 51(2): 82-104.

Smith, D.M. and Pantilei, V.S. (2015) Do “Dogs of the World” Bark or Bite? Evidence from Single-Country ETFs. Journal of Investing 24(1): 7-15.

Smith, K.V. and Shulman, D. (1976) Institutions Beware: The Performance of Equity Real Estate Investment Trusts. Financial Analysts Journal 32(5): 61-66.

Sollinger, A. (1994) The Triparty Is Just Beginning. Institutional Investor 28(1): 133-135.

Solt´es, M. (2010) Relationship of speed certificates and inverse vertical ratio ˇ call back spread option strategy. E+M Ekonomie a Management 13(2): 119- 124.

Solt´es, V. (2011) The application of the long and short combo option strategies ˇ in the building of structured products. In: Kocourek, A. (ed.) Proceedings of the 10th International Conference: Liberec Economic Forum 2011. Liberec, Czech Republic: Technical University of Liberec, pp. 481-487.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Solt´es, V. and Amaitiek, O.F.S. (2010a) The Short Put Ladder Strategy and its ˇ Application in Trading and Hedging. Club of Economics in Miskolc: Theory, Methodology, Practice 6(2): 77-85.

Solt´es, V. and Amaitiek, O.F.S. (2010b) Inverse Vertical Ratio Put Spread ˇ Strategy and its Application in Hedging against a Price Drop. Journal of Advanced Studies in Finance 1(1): 100-107.

Solt´es, V. and Rusn´akov´a, M. (2012) Long Combo strategy using barrier op- ˇ tions and its application in hedging against a price drop. Acta Montanistica Slovaca 17(1): 17-32.

Solt´es, V. and Rusn´akov´a, M. (2013) Hedging Against a Price Drop Using ˇ the Inverse Vertical Ratio Put Spread Strategy Formed by Barrier Options. Engineering Economics 24(1): 18-27.

Sørensen, C. (1999) Dynamic Asset Allocation and Fixed Income Management. Journal of Financial and Quantitative Analysis 34(4): 513-531.

Sorensen, E.H. and Burke, T. (1986) Portfolio Returns from Active Industry Group Rotation. Financial Analysts Journal 42(5): 43-50.

Sørensen, C. and Trolle, A.B. (2005) A General Model of Dynamic Asset Allocation with Incomplete Information and Learning. Working paper. Available online: https://ssrn.com/abstract=675625.

S¨orensson, T. (1993) Two methods for valuing convertible bonds – A comparison. Scandinavian Journal of Management 9(S1): 129-139.

Soudijn, M.R.J. (2016) Rethinking money laundering and drug trafficking: Some implications for investigators, policy makers and researchers. Journal of Money Laundering Control 19(3): 298-310.

Sprenger, T.O., Tumasjan, A., Sandner, P.G. and Welpe, I.M. (2014) Tweets and trades: The information content of stock microblogs. European Financial Management 20(5): 926-957.

Spyrou, S.I. (2005) Index Futures Trading and Spot Price Volatility: Evidence from an Emerging Market. Journal of Emerging Market Finance 4(2): 151-167.

Staal, A., Corsi, M., Shores, S. and Woida, C. (2015) A Factor Approach to Smart Beta Development in Fixed Income. Journal of Index Investing 6(1): 98-110.

Stambaugh, R.F. (1988) The information in forward rates: Implications for models of the term structure. Journal of Financial Economics 21(1): 41-70.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Stanton, R. (1995) Rational Prepayment and the Valuation of Mortgage-Backed Securities. Review of Financial Studies 8(3): 677-708.

Statman, M., Thorley, S. and Vorkink, K. (2006) Investor Overconfidence and Trading Volume. Review of Financial Studies 19(4): 1531-1565.

Stattman, D. (1980) Book Values and Stock Returns. Chicago MBA: A Journal of Selected Papers 1980(4): 25-45.

Stefanini, F. (2006) Investment Strategies of Hedge Funds. Chichester, UK: John Wiley & Sons, Ltd.

Stein, J.C. (1992) Convertible bonds as backdoor equity financing. Journal of Financial Economics 32(1): 3-21.

Stein, J.C. (1995) Prices and Trading Volume in the Housing Market: A Model with Down-Payment Effects. Quarterly Journal of Economics 110(2): 379-406.

Steinert, M. and Crowe, S. (2001) Global Real Estate Investment: Characteristics, Optimal Portfolio Allocation and Future Trends. Pacific Rim Property Research Journal 7(4): 223-239.

Stevenson, S. (2001) Bayes-Stein Estimators and International Real Estate Asset Allocation. Journal of Real Estate Research 21(1/2): 89-104.

Stevenson, S. (2002) Momentum Effects and Mean Reversion in Real Estate Securities. Journal of Real Estate Research 23(1/2): 47-64.

Stickel, S.E. (1991) Common stock returns surrounding earnings forecast revisions: More puzzling evidence. Accounting Review 66(2): 402-416.

Stivers, C. and Sun, L. (2010) Cross-Sectional Return Dispersion and Time Variation in Value and Momentum Premiums. Journal of Financial and Quantitative Analysis 45(4): 987-1014.

Stoll, H.R. (1969) The Relationship Between Put and Call Option Prices. Journal of Finance 24(5): 801-824.

Stotz, O. (2016) Investment strategies and macroeconomic news announcement days. Journal of Asset Management 17(1): 45-56.

Stovall, S. (1996) Sector Investing. New York, NY: McGraw Hill, Inc.

Stroebel, J. and Taylor, J.B. (2012) Estimated Impact of the Federal Reserve’s Mortgage-Backed Securities Purchase Program. International Journal of Central Banking 8(2): 1-42.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

St¨ubinger, J. and Bredthauer, J. (2017) Statistical Arbitrage Pairs Trading with High-frequency Data. International Journal of Economics and Financial Issues 7(4): 650-662.

St¨ubinger, J. and Endres, S. (2017) Pairs trading with a mean-reverting jumpdiffusion model on high-frequency data. Quantitative Finance (forthcoming). DOI: https://doi.org/10.1080/14697688.2017.1417624.

Stulz, R.M. (1996) Rethinking risk management. Journal of Applied Corporate Finance 9(3): 8-25.

Stulz, R.M. (2010) Credit Default Swaps and the Credit Crisis. Journal of Economic Perspectives 24(1): 73-92.

Su, X. (2006) Hedging basket options by using a subset of underlying assets. Working paper. Available online: https://www.econstor.eu/bitstream/ 10419/22959/1/bgse14\_2006.pdf.

Su, E. and Knowles, T.W. (2010) Measuring Bond Portfolio Value at Risk and Expected Shortfall in US Treasury Market. Asia Pacific Management Review 15(4): 477-501.

Subha, M. and Nambi, S. (2012) Classification of stock index movement using k-Nearest Neighbours (k-NN) algorithm. WSEAS Transactions on Information Science and Applications 9(9): 261-270.

Subramanian, A. (2004) Option pricing on stocks in mergers and acquisitions. Journal of Finance 59(2): 795-829.

Suhonen, A., Lennkh, M. and Perez, F. (2017) Quantifying Backtest Overfitting in Alternative Beta Strategies. Journal of Portfolio Management 43(2): 90-104.

Sul, H.K., Dennis, A.R. and Yuan, L.(I). (2017) Trading on Twitter: Using Social Media Sentiment to Predict Stock Returns. Decision Sciences 48(3): 454-488.

Sullivan, R., Timmermann, A. and White, H. (1999) Data-snooping, technical trading rule performance, and the bootstrap. Journal of Finance 54(5): 1647- 1691.

Summers, B.J. (1980) Negotiable Certificates of Deposit. Federal Reserve Bank of Richmond, Economic Review 66(4): 8-19.

Suresh, A.S. (2015) Analysis of Option Combination Strategies. Management Insight 11(1): 31-40.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Svec, J. and Stevenson, M. (2007) Modelling and forecasting temperature based weather derivatives. Global Finance Journal 18(2): 185-204.

Swank, T.A. and Root, T.H. (1995) Bonds in Default: Is Patience a Virtue? Journal of Fixed Income 5(1): 26-31.

Swinkels, L. (2002) International Industry Momentum. Journal of Asset Management 3(2): 124-141.

Swishchuk, A. and Cui, K. (2013) Weather derivatives with applications to Canadian data. Journal of Mathematical Finance 3(1): 81-95.

Switzer, L.N. and Jiang, H. (2010) Market Efficiency and the Risks and Returns of Dynamic Trading Strategies with Commodity Futures. In: Stanley, H.E. (ed.) Proceedings Of The First Interdisciplinary Chess Interactions Conference. Singapore: World Scientific Publishing, pp. 127-156.

Symeonidis, L., Prokopczuk, M., Brooks, C. and Lazar, E. (2012) Futures basis, inventory and commodity price volatility: An empirical analysis. Economic Modelling 29(6): 2651-2663.

Szado, E. and Schneeweis, T. (2010) Loosening Your Collar: Alternative Implementations of QQQ Collars. Journal of Trading 5(2): 35-56.

Szado, E. and Schneeweis, T. (2011) An Update of ‘Loosening Your Collar: Alternative Implementations of QQQ Collars’: Credit Crisis and Out-of-Sample Performance. Working Paper. Available online: http://ssrn.com/abstract= 1507991.

Szakmary, A.C., Shen, Q. and Sharma, S.C. (2010) Trend-following trading strategies in commodity futures: A re-examination. Journal of Banking & Finance 34(2): 409-426.

Szakmary, A.C. and Zhou, X. (2015) Industry momentum in an earlier time: Evidence from the Cowles data. Journal of Financial Research 38(3): 319-347.

Tang, C.H. and Jang, S.H. (2011) Weather risk management in ski resorts: Financial hedging and Geographical diversification. International Journal of Hospitality Management 30(2): 301-311

Tang, H. and Xu, X.E. (2013) Solving the Return Deviation Conundrum of Leveraged Exchange-Traded Funds. Journal of Financial and Quantitative Analysis 48(1): 309-342.

Tavakoli, J.M. (1998) Credit Derivatives & Synthetic Structures: A Guide to Instruments and Applications. (2nd ed.) Hoboken, NJ: John Wiley & Sons, Inc.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Tay, F.E.H. and Cao, L. (2001) Application of support vector machines in financial time series forecasting. Omega 29(4): 309-317.

Taylor, C.R. (1999) Time-on-the-Market as a Sign of Quality. Review of Economic Studies 66(3): 555-578.

Taylor, N. (2004) Modeling discontinuous periodic conditional volatility: Evidence from the commodity futures market. Journal of Futures Markets 24(9): 805-834.

Taylor, N. (2016) Roll strategy efficiency in commodity futures markets. Journal of Commodity Markets 1(1): 14-34.

Taylor, M.P. and Allen, H. (1992) The use of technical analysis in the foreign exchange market. Journal of International Money and Finance 11(3): 304-314.

Teixeira, L.A. and de Oliveira, A.L.I. (2010) A method for automatic stock trading combining technical analysis and nearest neighbor classification. Expert Systems with Applications 37(10): 6885-6890.

Telser, L.G. (1958) Futures Trading and the Storage of Cotton and Wheat. Journal of Political Economy 66(3): 233-255.

The Options Institute (1995) Options: Essential Concepts and Trading Strategies. (2nd ed.) Chicago, IL: Richard D. Irwin, Inc.

Thibodeau, T.G. and Giliberto, S.M. (1989) Modeling Conventional Residential Mortgage Refinancing. Journal of Real Estate Finance and Economics 2(4): 285-299.

Thomsett, M.C. (2003) Support and Resistance Simplified. Columbia, MD: Marketplace Books.

Thornes, J.E. (2006) An introduction to weather and climate derivatives. Weather 58(5): 193-196.

Thorp, E.O. (2006) The Kelly criterion in blackjack, sports betting, and the stock market. In: Zenios, S.A. and Ziemba, W.T. (eds.) Handbook of Asset and Liability Management: Theory and Methodology (Vol. 1). Amsterdam, The Netherlands: Elsevier, pp. 385-428.

Thorp, E.O. and Kassouf, S.T. (1967) Beat the Market: A Scientific Stock Market System. New York, NY: Random House.

Till, H. (2008) Case Studies and Risk Management Lessons in Commodity Derivatives Trading. In: Geman, H. (ed.) Risk Management in Commodity Markets: From Shipping to Agriculturals and Energy. Chichester, UK: John Wiley & Sons, Ltd., pp. 255-291.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Till, H. and Eagleeye, J. (2017) Commodity Futures Trading Strategies: Trend-Following and Calendar Spreads. Working Paper. Available online: https://ssrn.com/abstract=2942340.

Tille, C., Stoffels, N. and Gorbachev, O. (2001) To What Extent Does Productivity Drive the Dollar? Current Issues in Economics and Finance 7(8): 1-6.

Timmermans, S.H.J.T., Schumacher, J.M. and Ponds, E.H.M. (2017) A multiobjective decision framework for lifecycle investment. Working Paper. Available online: http://ssrn.com/abstract=3038803.

Tinoco, M.H. and Wilson, N. (2013) Financial distress and bankruptcy prediction among listed companies using accounting, market and macroeconomic variables. International Review of Financial Analysis 30: 394-419.

Titman, S. and Warga, A. (1986) Risk and the Performance of Real Estate Investment Trusts: A Multiple Index Approach. AREUEA Journal 14(3): 414- 431.

Todorov, V. (2010) Variance Risk-Premium Dynamics: The Role of Jumps. Review of Financial Studies 23(1): 345-383.

Toevs, A. and Jacob, D. (1986) Futures and Alternative Hedge Ratio Methodologies. Journal of Portfolio Management 12(3): 60-70.

Tokic, D. (2013) Crude oil futures markets: Another look into traders’ positions. Journal of Derivatives & Hedge Funds 19(4): 321-342.

Topaloglou, N., Vladimirou, H. and Zenios, S.A. (2011) Optimizing International Portfolios with Options and Forwards. Journal of Banking & Finance 35(12): 3188-3201.

Torrance, M.I. (2007) The Power of Governance in Financial Relationships: Governing Tensions in Exotic Infrastructure Territory. Growth and Change 38(4): 671-695.

Torricelli, L. (2018) Volatility Targeting Using Delayed Diffusions. Working Paper. Available online: https://ssrn.com/abstract=2902063.

Trainer, F.H., Jr. (1983) The Uses of Treasury Bond Futures in Fixed Income Portfolio Management. Financial Analysts Journal 39(1): 27-34.

Trainor, W.J., Jr. (2010) Do Leveraged ETFs Increase Volatility? Technology and Investment 1(3): 215-220.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Trehan, B. (2005) Oil price shocks and inflation. Federal Reserve Bank of San Francisco, Economic Letter, No. 2005-28. Available online: https://www. frbsf.org/economic-research/files/el2005-28.pdf.

Trifonov, Y., Yashin, S., Koshelev, E. and Podshibyakin, D. (2011) Application of Synthetic Straddles for Equity Risk Management. In: Cern´ak, Z. (ed.) ˇ Materi´aly VII mezin´arodn´ı vˇedecko – praktick´a konference “Zpr´avy vˇedeck´e ideje – 2011”. Prague, Czech Republic: Education and Science.

Trifonov, Y., Yashin, S., Koshelev, E. and Podshibyakin, D. (2014) Testing the Technology of Synthetic Straddles. Working Paper. Available online: https: //ssrn.com/abstract=2429657.

Tripathi, V. and Garg, S. (2016) A Cross-Country Analysis of Pricing Efficiency of Exchange Traded Funds. Journal of Applied Finance 22(3): 41-63.

Trzcinka, C. (1982) The Pricing of Tax-Exempt Bonds and the Miller Hypothesis. Journal of Finance 37(4): 907-923.

Tsai, C.F. and Hsiao, Y.C. (2010) Combining multiple feature selection methods for stock prediction: Union, intersection, and multi-intersection approaches. Decision Support Systems 50(1): 258-269.

Tsai, C., Hsu, Y. and Yen, D.C. (2014) A comparative study of classifier ensembles for bankruptcy prediction. Applied Soft Computing 24: 977-984.

Tse, Y. (2017) Return predictability and contrarian profits of international index futures. Journal of Futures Markets 38(7): 788-803.

Tsiveriotis, K. and Fernandes, C. (1998) Valuing convertible bonds with credit risk. Journal of Fixed Income 8(2): 95-102.

Tuckman, B. and Serrat, A. (2012) Fixed Income Securities: Tools for Today’s Markets. (3rd ed.) Hoboken, NJ: John Wiley & Sons, Inc.

Tulchinsky, I. et al. (2015) Finding Alphas: A Quantitative Approach to Building Trading Strategies. New York, NY: John Wiley & Sons, Inc.

Turnovsky, S.J. (1989) The Term Structure of Interest Rates and the Effects of Macroeconomic Policy. Journal of Money, Credit and Banking 21(3): 321-347.

Tuzun, T. (2013) Are Leveraged and Inverse ETFs the New Portfolio Insurers? Finance and Economics Discussion Series (FEDS), Paper No. 2013-48. Washington, DC: Board of Governors of the Federal Reserve System. Available online: https://www.federalreserve.gov/pubs/feds/2013/201348/ 201348pap.pdf.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Tversky, A. and Kahneman, D. (1992) Advances in prospect theory: Cumulative representation of uncertainty. Journal of Risk and Uncertainty 5(4): 297-323.

Uhlenbeck, G.E. and Ornstein, L.S. (1930) On the Theory of the Brownian Motion. Physical Review 36(5): 823-841.

Vaitonis, M. and Masteika, S. (2016) Research in high frequency trading and pairs selection algorithm with Baltic region stocks. In: Dregvaite, G. and Damasevicius, R. (eds.) Proceedings of the 22nd International Conference on Information and Software Technologies (ICIST 2016). Cham, Switzerland: Springer, pp. 208-217.

Van Alstyne, M. (2014) Why Bitcoin has value. Communications of the ACM 57(5): 30-32.

van den Goorbergh, R.W.J. (2004) Essays on optimal hedging and investment strategies and on derivative pricing (Ph.D. Thesis). Tilburg, The Netherlands: Tilburg University.

van den Noord, P. and Andr´e, C. (2007) Why has Core Inflation Remained so Muted in the Face of the Oil Shock? Working Paper. Available online: http://dx.doi.org/10.1787/206408110285.

Van Kervel, V. and Menkveld, A.J. (2017) High-Frequency Trading around Large Institutional Orders. Journal of Finance (forthcoming). Available online: https://ssrn.com/abstract=2619686.

van Marle, M. and Verwijmeren, P. (2017) The long and the short of convertible arbitrage: An empirical examination of arbitrageurs’ holding periods. Journal of Empirical Finance 44: 237-249.

Van Oord, J.A. (2016) Essays on Momentum Strategies in Finance (Ph.D. Thesis). Rotterdam, The Netherlands: Erasmus University. Available online: https://repub.eur.nl/pub/80036/EPS2016380F-A9789058924445.pdf.

Vanstone, B. and Finnie, G. (2009) An empirical methodology for developing stockmarket trading systems using artificial neural networks. Expert Systems with Applications 36(3): 6668-6680.

Van Tassel, P. (2016) Merger Options and Risk Arbitrage. Federal Reserve Bank of New York Staff Reports, No. 761. Available online: https://www.newyorkfed.org/medialibrary/media/research/staff\_ reports/sr761.pdf?la=en.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Vasicek, O.A. (2015) Probability of Loss on Loan Portfolio. In: Vasicek, O.A. (ed.) Finance, Economics and Mathematics. Hoboken, NJ: John Wiley & Sons, Inc., Chapter 17.

Vassalou, M. and Xing, Y. (2004) Default Risk in Equity Returns. Journal of Finance 59(2): 831-868.

Vedenov, D.V. and Barnett, B.J. (2004) Efficiency of Weather Derivatives as Primary Crop Insurance Instruments. Journal of Agricultural Economics 29(3): 387-403.

Vickery, J. and Wright, J. (2010) TBA Trading and Liquidity in the Agency MBS Market. Federal Reserve Bank of New York Staff Reports, No. 468. Available online: https://www.newyorkfed.org/medialibrary/media/ research/staff\_reports/sr468.pdf.

Vidyamurthy, G. (2004) Pairs Trading: Quantitative Methods and Analysis. Hoboken, NJ: John Wiley & Sons, Inc.

Viezer, T.W. (2000) Evaluating “Within Real Estate” Diversification Strategies. Journal of Real Estate Portfolio Management 6(1): 75-95.

Villani, R. and Davis, C. (2006) FLIP: How to find, fix, and sell houses for profit. New York, NY: McGraw-Hill, Inc.

Vipul (2009) Box-spread arbitrage efficiency of Nifty index options: The Indian evidence. Journal of Futures Markets 29(6): 544-562.

Viswanath, P.V. (1993) Efficient Use of Information, Convergence Adjustments, and Regression Estimates of Hedge Ratios. Journal of Futures Markets 13(1): 43-53.

Vives, A. (1999) Pension Funds in Infrastructure Project Finance: Regulations and Instrument Design. Journal of Structured Finance 5(2): 37-52.

Volpert, B.S. (1991) Opportunities for Investing in Troubled Companies. In: Dinapoli, D., Sigoloff, S.C. and Cushman, R.F. (eds.) Workouts and Turnarounds: The Handbook of Restructuring and Investing in Distressed Companies. Homewood, IL: Business One-Irwin, pp. 514-542.

Vrugt, E.B., Bauer, R., Molenaar, R. and Steenkamp, T. (2007) Dynamic commodity trading strategies. In: Till, H. and Eagleeye, J. (eds.) Intelligent Commodity Investing: New Strategies and Practical Insights for Informed Decision Making. London, UK: Risk Books, Chapter 16.

Walker, J. (1999) How Big is Global Money Laundering? Journal of Money Laundering Control 3(1): 25-37.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Walker, M.B. (2008) The static hedging of CDO tranche correlation risk. International Journal of Computer Mathematics 86(6): 940-954.

Walkling, R.A. (1985) Predicting tender offer success: A logistic analysis. Journal of Financial and Quantitative Analysis 20(4): 461-478.

Wang, K.Q. (2005) Multifactor Evaluation of Style Rotation. Journal of Financial and Quantitative Analysis 40(2): 349-372.

Wang, L. (2014) Margin-Based Asset Pricing and the Determinants of the CDS Basis. Journal of Fixed Income 24(2): 61-78.

Wang, J., Brooks, R., Lu, X. and Holzhauer, H.M. (2017) Sector Momentum. Journal of Investing 26(2): 48-60.

Wang, C.-H. and Min, K.J. (2013) Electric Power Plant Valuation Based on Day-Ahead Spark Spreads. Engineering Economist 58(3): 157-178.

Wang, S. and Vergne, J.-P. (2017) Buzz factor or innovation potential: What explains cryptocurrencies returns? PLoS ONE 12(1): e0169556.

Wang, C. and Yu, M. (2004) Trading activity and price reversals in futures markets. Journal of Banking & Finance 28(6): 1337-1361.

Ward, D. and Griepentrog, G. (1993) Risk and Return in Defaulted Bonds. Financial Analysts Journal 49(3): 61-65.

Watts, R.L. (1978) Systematic ‘abnormal’ returns after quarterly earnings announcements. Journal of Financial Economics 6(2-3): 127-150.

Webb, J.R., Curcio, R.J. and Rubens, J.H. (1988) Diversification gains from including real estate in mixed-asset portfolios. Decision Sciences 19(2): 434- 452.

Weber, B.R., Adair, A. and McGreal, S. (2008) Solutions to the five key brownfield valuation problems. Journal of Property Investment & Finance 26(1): 8-37.

Weber, B., Staub-Bisang, M. and Alfen, H.W. (2016) Infrastructure as an Asset Class: Investment Strategy, Sustainability, Project Finance and PPP. Chichester, UK: John Wiley & Sons, Ltd.

Weinert, H.L. (2007) Efficient computation for Whittaker-Henderson smoothing. Computational Statistics & Data Analysis 52(2): 959-974.

Weiser, S. (2003) The strategic case for commodities in portfolio diversification. Commodities Now, September 2003, pp. 7-11.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Weller, P.A., Friesen, G.C. and Dunham, L.M. (2009) Price trends and patterns in technical analysis: a theoretical and empirical examination. Journal of Banking & Finance 6(33): 1089-1100.

Wells, B. (2016) The Foreign Tax Credit War. Brigham Young University Law Review 2016(6): 1895-1965.

Whaley, R.E. (2000) The Investor Fear Gauge. Journal of Portfolio Management 26(3): 12-16.

Whaley, R.E. (2002) Return and Risk of CBOE Buy Write Monthly Index. Journal of Derivatives 10(2): 35-42.

Whaley, R.E. (2009) Understanding the VIX. Journal of Portfolio Management 35(3): 98-105.

Wheaton, W.C. (1990) Vacancy, Search, and Prices in a Housing Market Matching Model. Journal of Political Economy 98(6): 1270-1292.

White, L.H. (2015) The Market for Cryptocurrencies. Cato Journal 35(2): 383-402.

Whittaker, E.T. (1923) On a New Method of Graduations. Proceedings of the Edinburgh Mathematical Society 41: 63-75.

Whittaker, E.T. (1924) On the theory of graduation. Proceedings of the Royal Society of Edinburgh 44: 77-83.

Wilder, J.W., Jr. (1978) New Concepts in Technical Trading Systems. Greensboro, NC: Trend Research.

Willett, P. (2006) The Porter stemming algorithm: then and now. Program: Electronic Library and Information Systems 40(3): 219-223.

Wilner, R. (1996) A new tool for portfolio managers: Level, slope, and curvature durations. Journal of Fixed Income 6(1): 48-59.

Wilson, D.J. (2016) The Impact of Weather on Local Employment: Using Big Data on Small Places. Federal Reserve Bank of San Francisco Working Papers Series, No. 2016-21. Available online: https://www.frbsf.org/ economic-research/files/wp2016-21.pdf.

Wilson, A.C., Roelofs, R., Stern, M., Stern, N. and Recht, B. (2018) The Marginal Value of Adaptive Gradient Methods in Machine Learning. Working Paper. Available online: https://arxiv.org/pdf/1705.08292.pdf.

Wilson, R.L. and Sharda, R. (1994) Bankruptcy prediction using neural networks. Decision Support Systems 11(5): 545-557.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Windas, T. (2007) An Introduction to Option-Adjusted Spread Analysis. (Miller, T. (ed.) Revised and Expanded Third Edition.) Princeton, NJ: Bloomberg Press.

Wolf, A. (1987) Optimal hedging with futures options. Journal of Economics and Business 39(2): 141-158.

Wolf, V. (2014) Comparison of Markovian Price Processes and Optimality of Payoffs (Ph.D. Thesis). Freiburg im Breisgau, Germany: Albert-Ludwigs-Universit¨at Freiburg. Available online: https://freidok.uni-freiburg.de/ fedora/objects/freidok:9664/datastreams/FILE1/content.

Wong, W.-K., Thompson, H.E. and Teh, K. (2011) Was There Abnormal Trading in the S&P 500 Index Options Prior to the September 11 Attacks? Multinational Finance Journal 15(3/4): 1-46.

Wood, J. (1997) A Simple Model for Pricing Imputation Tax Credits Under Australia’s Dividend Imputation Tax System. Pacific-Basin Finance Journal 5(4): 465-480.

Woodard, J. and Garcia, P. (2008) Weather Derivatives, Spatial Aggregation, and Systemic Risk: Implications for Reinsurance Hedging. Journal of Agricultural and Resource Economics 33(1): 34-51.

Woodlock, P. and Dangol, R. (2014) Managing bankruptcy and default risk. Journal of Corporate Accounting & Finance 26(1): 33-38.

Woodward, G.T. (1990) The Real Thing: A Dynamic Profile of the Term Structure of Real Interest Rates and Inflation. Journal of Business 63(3): 373- 398.

Working, H. (1953) Futures Trading and Hedging. American Economic Review 43(3): 314-434.

Worzala, E. and Newell, G. (1997) International real estate: A review of strategic investment issues. Journal of Real Estate Portfolio Management 3(2): 87- 96.

Wright, R., Tekin, E., Topalli, V., McClellan, C., Dickinson, T. and Rosenfeld, R. (2017) Less Cash, Less Crime: Evidence from the Electronic Benefit Transfer Program. Journal of Law and Economics 60(2): 361-383.

Wu, H. (2009) Global stability analysis of a general class of discontinuous neural networks with linear growth activation functions. Information Sciences 179(19): 3432-3441.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Wu, L. (2003) Jumps and Dynamic Asset Allocation. Review of Quantitative Finance and Accounting 20(3): 207-243.

Wurstbauer, D., Lang, S., Rothballer, C. and Sch¨afers, W. (2016) Can common risk factors explain infrastructure equity returns? Evidence from European capital markets. Journal of Property Research 33(2): 97-120.

Wurstbauer, D. and Sch¨afers, W. (2015) Inflation hedging and protection characteristics of infrastructure and real estate assets. Journal of Property Investment & Finance 33(1): 19-44.

Wurtzebach, C.H., Mueller, G.R. and Machi, D. (1991) The Impact of Inflation and Vacancy on Real Estate Returns. Journal of Real Estate Research 6(2): 153-168.

Wystup, U. (2017) FX Options and Structured Products. (2nd ed.) eBook: John Wiley & Sons, Inc.

Wystup, U. and Zhou, Q. (2014) Volatility as investment – crash protection with calendar spreads of variance swaps. Journal of Applied Operational Research 6(4): 243-254.

Xiao, T. (2013) A simple and precise method for pricing convertible bond with credit risk. Journal of Derivatives & Hedge Funds 19(4): 259-277.

Xie, W., Liew, Q.R., Wu, Y. and Zou, X. (2014) Pairs Trading with Copulas. Working Paper. Available online: https://ssrn.com/abstract=2383185.

Xing, Y., Zhang, X. and Zhao, R. (2010) What Does Individual Option Volatility Smirk Tell Us About Future Equity Returns? Journal of Financial and Quantitative Analysis 45(3): 641-662.

Yadav, P.K. and Pope, P.F. (1990) Stock index futures arbitrage: International evidence. Journal of Futures Markets 10(6): 573-603.

Yadav, P.K. and Pope, P.F. (1994) Stock index futures mispricing: profit opportunities or risk premia? Journal of Banking & Finance 18(5): 921-953.

Yamada, S. (1999) Risk Premiums in the JGB Market and Application to Investment Strategies. Journal of Fixed Income 9(2): 20-41.

Yan, X. (2006) The Determinants and Implications of Mutual Fund Cash Holdings: Theory and Evidence. Financial Management 35(2): 67-91.

Yang, C.C., Brockett, P.L. and Wen, M.-M. (2009) Basis risk and hedging efficiency of weather derivatives. Journal of Risk Finance 10(5): 517-536.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Yang, Z., You, W. and Ji, G. (2011) Using partial least squares and support vector machines for bankruptcy prediction. Expert Systems with Applications 38(7): 8336-8342.

Yao, Y. (2012) Momentum, contrarian, and the January seasonality. Journal of Banking & Finance 36(10): 2757-2769.

Yao, J. and Tan, C.L. (2000) A case study on using neural networks to perform technical forecasting of forex. Neurocomputing 34(1-4): 79-98.

Yao, J., Tan, C.L. and Poh, H.L. (1999) Neural networks for technical analysis: a study on KLCI. International Journal of Theoretical and Applied Finance 2(2): 221-241.

Yared, F. and Veronesi, P. (1999) Short and Long Horizon Term and Inflation Risk Premia in the US Term Structure: Evidence from an Integrated Model for Nominal and Real Bond Prices Under Regime Shifts. Working Paper. Available online: https://ssrn.com/abstract=199448.

Yavas, A. and Yang, S. (1995) The Strategic Role of Listing Price in Marketing Real Estate: Theory and Evidence. Real Estate Economics 23(3): 347-368.

Yawitz, J.B., Maloney, K.J. and Ederington, L.H. (1985) Taxes, Default Risk, and Yield Spreads. Journal of Finance 40(4): 1127-1140.

Yawitz, J.B. and Marshall, W.B. (1985) The Use of Futures in Immunized Portfolios. Journal of Portfolio Management 11(2): 51-55.

Yeutter, C. and Dew, J.K. (1982) The Use of Futures in Bank Loans. In: Prochnow, H.V. (ed.) Bank Credit. New York, NY: Harper and Row.

Yim, H.L., Lee, S.H., Yoo, S.K. and Kim, J.J. (2011) A zero-cost collar option applied to materials procurement contracts to reduce price fluctuation risks in construction. International Journal of Social, Behavioral, Educational, Economic, Business and Industrial Engineering 5(12): 1769-1774.

Yo, S.W. (2001) Index Futures Trading and Spot Price Volatility. Applied Economics Letters 8(3): 183-186.

Yoshikawa, D. (2017) An Entropic Approach for Pair Trading. Entropy 19(7): 320.

Youbi, F., Pindza, E. and Mar´e, E. (2017) A Comparative Study of Spectral Methods for Valuing Financial Options. Applied Mathematics & Information Sciences 11(3): 939-950.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Young, M. and Graff, R.A. (1996) Systematic Behavior in Real Estate Investment Risk: Performance Persistence in NCREIF Returns. Journal of Real Estate Research 12(3): 369-381.

Ysmailov, B. (2017) Interest Rates, Cash and Short-Term Investments. Working Paper. Available online: http://www.fmaconferences.org/Boston/ Interest\_Rates\_Cash\_and\_ShortTermInv.pdf.

Yu, L., Wang, S. and Lai, K.K. (2005) Mining Stock Market Tendency Using GA-Based Support Vector Machines. In: Deng, X. and Ye, Y. (eds.) Internet and Network Economics. WINE 2005. Lecture Notes in Computer Science, Vol. 3828. Berlin, Germany: Springer, pp. 336-345.

Yu, S. and Webb, G. (2014) The Profitability of Pairs Trading Strategies Based on ETFs. Working Paper. Available online: http://swfa2015.uno. edu/B\_Asset\_Pricing\_III/paper\_196.pdf.

Zabolotnyuk, Y., Jones, R. and Veld, C. (2010) An empirical comparison of convertible bond valuation models. Financial Management 39(2): 675-706.

Zakamulin, V. (2014a) The Real-Life Performance of Market Timing with Moving Average and Time-Series Momentum Rules. Journal of Asset Management 15(4): 261-278.

Zakamulin, V. (2014b) Dynamic Asset Allocation Strategies Based on Unexpected Volatility. Journal of Alternative Investments 16(4): 37-50.

Zakamulin, V. (2015) A Comprehensive Look at the Empirical Performance of Moving Average Trading Strategies. Working Paper. Available online: https: //ssrn.com/abstract=2677212.

Zapranis, A. and Alexandridis, A. (2008) Modelling the temperature timedependent speed of mean reversion in the context of weather derivatives pricing. Applied Mathematical Finance 15(3-4): 355-386.

Zapranis, A. and Alexandridis, A. (2009) Weather derivatives pricing: modeling the seasonal residual variance of an Ornstein-Uhlenbeck temperature process with neural networks. Neurocomputing 73(1-3): 37-48.

Zapranis, A. and Tsinaslanidis, P.E. (2012) Identifying and evaluating horizontal support and resistance levels: an empirical study on US stock markets. Applied Financial Economics 22(19): 1571-1585.

Zaremba, A. (2014) A Performance Evaluation Model for Global Macro Funds. International Journal of Finance & Banking Studies 3(1): 161-171.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Zeng, L. (2000) Pricing weather derivatives. Journal of Risk Finance 1(3): 72-78.

Zeng, Z. and Lee, C.G. (2014) Pairs trading: Optimal thresholds and profitability. Quantitative Finance 14(11): 1881-1893.

Zhang, C. (2015) Using Excel’s Data Table and Chart Tools Effectively in Finance Courses. Journal of Accounting and Finance 15(7): 79-93.

Zhang, L. (2005) The Value Premium. Journal of Finance 60(1): 67-103.

Zhang, L. (2014) A closed-form pricing formula for variance swaps with meanreverting Gaussian volatility. ANZIAM Journal 55(4): 362-382.

Zhang, X.F. (2006) Information Uncertainty and Stock Returns. Journal of Finance 61(1): 105-136.

Zhang, J.Z., Fargher, N.L. and Hou, W. (2018) Do Banks Audited by Specialists Engage in Less Real Activities Management? Evidence from Repurchase Agreements. AUDITING: A Journal of Practice & Theory (forthcoming). DOI: https://doi.org/10.2308/ajpt-52017.

Zhang, X., Fuehres, H. and Gloor, P.A. (2011) Predicting Stock Market Indicators Through Twitter “I hope it is not as bad as I fear”. Procedia – Social and Behavioral Sciences 26: 55-62.

Zhang, J.E., Shu, J. and Brenner, M. (2010) The new market for volatility trading. Journal of Futures Markets 30(9): 809-833.

Zhang, J.E. and Xiang, Y. (2008) The implied volatility smirk. Quantitative Finance 8(3): 263-284.

Zhang, J.E. and Zhu, Y. (2006) VIX futures. Journal of Futures Markets 26(6): 521-531.

Zheng, W. and Kwok, Y.K. (2014) Closed form pricing formulas for discretely sampled generalized variance swaps. Mathematical Finance 24(4): 855-881.

Zheng, H., Thomas, L.C. and Allen, D.E. (2003) The Duration Derby: A Comparison of Duration Strategies in Asset Liability Management. Journal of Bond Trading and Management 1(4): 371-380.

Zhou, L. (2013) Performance of corporate bankruptcy prediction models on imbalanced dataset: The effect of sampling methods. Knowledge-Based Systems 41: 16-25.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Zhou, L., Yao, S., Wang, J. and Ou, J. (2016) Global financial crisis and China’s pawnbroking industry. Journal of Chinese Economic and Business Studies 14(2): 151-164.

Zhu, H. (2006) An Empirical Comparison of Credit Spreads between the Bond Market and the Credit Default Swap Market. Journal of Financial Services Research 29(3): 211-235.

Zmijewski, M.E. (1984) Methodological Issues Related to the Estimation of Financial Distress Prediction Models. Journal of Accounting Research 22: 59- 82.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## Glossary

absolute momentum: time-series momentum.

acquirer company: the company purchasing another company (target company) in a corporate acquisition.

activation function: a function that defines the output of a node (artificial neuron) in an artificial neural network given an input (or a set of inputs).

active investing (a.k.a. active management): an investment strategy that involves active (frequent) buying and selling of securities in a portfolio (cf. passive investing) with the view of exploiting (perceived) profit-generating opportunities.

actively managed ETF: an exchange-traded fund whose underlying portfolio allocation is actively managed.

adjusted price: a stock’s price adjusted for splits and dividends.

adverse selection: an effect caused by smart order flow, whereby most limit orders to buy at the bid (sell at the ask) get filled when the market is trading through them downward (upward).

aggressive order: a market order, or a marketable limit order (to buy at the ask or higher, or to sell at the bid or lower).

aggressive order flow: order flow comprised of aggressive orders.

alpha: following common trader lingo, any reasonable “expected return” that one may wish to trade on.

alpha portfolio (a.k.a. alpha combo): a portfolio of (typically, a large number of) alphas combined with some weights.

alpha rotation: a type of ETF trading strategy.

American option: an option (e.g., call or put) that can be exercised on any trading day on or before expiration.

announcement days: days with important economic announcements such as FOMC announcements (cf. non-announcement days).

annualization factor: a multiplicative factor for annualizing a quantity.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

annualized return: an average daily return times 252 (the number of trading days in a year).

annualized Sharpe ratio: a daily Sharpe ratio times the square root of 252 (the number of trading days in a year).

appraised value: an evaluation of a property’s or some other valuable object’s (e.g., jewelry) value at a given time.

arbitrage: taking advantage of a (perceived) mispricing (a.k.a. arbitrage opportunity) in one or more securities to make a profit.

arbitrage trade: a set of transactions executed with the view of exploiting an arbitrage opportunity.

artificial neural network (ANN): a computing system (inspired by the neural structure of a brain) of nodes (artificial neurons) linked by connections (akin to the synapses in a brain) that can transmit signals from one node to another.

Asian option: an option whose payoff is determined by the average underlying price over some preset time period.

ask (a.k.a. ask price, or offer, or offer price): the price at which a seller is willing (offering) to sell.

asset allocation: assigning weights (allocation percentages) to the assets in a portfolio, typically based on risk-reward considerations.

asset-backed security (ABS): a financial security collateralized by a pool of assets such as loans, mortgages, royalties, etc.

asset class: a group of securities with similar characteristics.

at-the-money (ATM) option: an option whose exercise price is the same as the current price of the underlying asset.

attachment (a.k.a. attachment point): the percentage of the underlying portfolio loss at which a tranche of a CDO (collateralized debt obligation) starts to lose value.

back leg: longer-maturity bonds in a yield curve spread strategy (flattener or steepener).

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

backspread: a type of options strategies.

backtest: a simulation of strategy performance using historical data.

backtesting period: the historical period over which a backtest is performed.

backwardation: when the futures curve (term structure) is downward-sloping.

bank deposit certificate (a.k.a. certificate of deposit, or CD): a savings certificate (a promissory note issued by a bank) with a fixed maturity date and interest rate.

banker’s acceptance (BA): a short-term debt instrument issued by a company and guaranteed by a commercial bank.

bankruptcy: a legal status (imposed by a Court order) of a company that cannot repay debts to its creditors.

barbell: a bond portfolio consisting of bonds with only two (typically, short and long) maturities.

barrier option: an option that can be exercised only if the underlying security’s price passes a certain level or “barrier”.

base form (a.k.a. stem): in linguistics, the part of a word that is common to all its inflected variants.

basis point (bps): 1/100 of 1%.

basket: a portfolio of assets combined with some weights.

Bayes’ theorem: $P ( A | B ) = P ( B | A ) \times P ( A ) / P ( B )$ , where P (A|B) is the conditional probability of A occurring assuming B is true, and P (A) and P (B) are the probabilities of A and B occurring independently of each other.

bearish outlook: when a trader expects the market or a security to trade lower.

bearish strategy: a directional strategy where the trader profits if the underlying instrument’s price goes down.

Bermudan option: an option that can be exercised only on specified dates on or before expiration.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Bernoulli probability distribution: a discrete probability distribution of a random variable which takes the value 1 with probability p and the value 0 with probability q = 1 − p.

bias: in an artificial neural network, the inhomogeneous component of the argument of an activation function.

bid (a.k.a. bid price): the price at which a buyer is willing to buy.

bid-ask spread: ask price minus bid price.

binary industry classification: an industry classification where each company belongs to one and only one sub-industry, industry, sector, etc.

binary option (a.k.a. digital option, or all-or-nothing option): an option that pays a preset amount, say, \$1, if the underlying security meets a predefined condition on expiration, otherwise it simply expires without paying anything to the holder.

bisection method: a root-finding method that repeatedly bisects an interval and selects a subinterval in which a root must lie for further examination.

Bitcoin (BTC): the world’s first decentralized digital currency (cryptocurrency).

black-box algorithm: an algorithm that can be viewed in terms of its inputs and outputs, without any knowledge of its internal workings.

Black-Scholes model (a.k.a. Black-Scholes-Merton model): a mathematical model of stock (or other underlying asset) dynamics used in pricing options and other derivatives, where the log of the underlying price is described by a Brownian motion with a constant drift.

blockchain: a distributed ledger for keeping a record of all transactions that consists of a sequential chain of blocks, linked using cryptography and time-stamping, and containing transaction records.

body: the middle (by maturity in bond portfolios, and by strike price in option portfolios) leg of a butterfly portfolio.

bond: a fixed-income instrument, a promise of being paid some amount (principal) at some future time T (maturity), and possibly some smaller amounts (coupon

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

payments) at some times prior to T .

bond immunization: matching the duration of a bond portfolio to the maturity of a future cash obligation.

bond maturity: the time at which the principal of a bond is paid.

bond principal: the amount the borrower (bond issuer) owes to the bondholder in full at bond maturity.

bond value: the worth of a bond at a given time before maturity.

bond yield (here, yield to maturity): the overall interest rate earned assuming the bond is held until maturity and all coupon and principal payments are made as promised.

bond yield spread (a.k.a. bond spread): the spread between the bond yield and the risk-free rate.

bondholder: bond owner.

book-to-market ratio: the company’s total book value divided by its market capitalization (same as B/P ratio).

book-to-price ratio (a.k.a. B/P ratio): the company’s book value per share outstanding divided by its stock share price.

book value: the company’s total assets minus its total liabilities.

Boolean: a binary variable with only two possible values, TRUE and FALSE.

box: an option trading strategy.

break-even price (a.k.a. break-even point): a price of the underlying security (e.g., stock) in an option trading strategy at which it breaks even (i.e., when the P&L is zero).

breakeven rate: the fixed rate of an inflation swap.

broad market index: an index based on a broad cross-section of securities (e.g., S&P 500, Russell 3000, etc.).

brownfield project: a project associated with established infrastructure as-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

sets in need of improvement.

Brownian motion (a.k.a. Wiener process): a continuous-time (t) stochastic process Wt, where $W _ { 0 } = 0$ , Wt is a normal random variable with mean 0 and variance t, and the increment $W _ { s + t } - W _ { s }$ is a normal random variable with mean 0 and variance t and is independent of the history of what the process did up to time s.

Btu: British thermal unit, approximately 1,055 Joules.

bubble (a.k.a. economic, asset, speculative, market, price or financial bubble): an asset trading at prices strongly inflated compared with its intrinsic value.

bullet: a bond portfolio where all bonds have the same maturity.

bullish outlook: when a trader expects the market or a security to trade higher.

bullish strategy: a directional strategy where the trader profits if the underlying instrument’s price goes up.

butterfly: a portfolio (of bonds or options) with 3 legs, two peripheral (by maturity in bond portfolios, and by strike price in option portfolios) wings and a body in the middle.

butterfly spread: a butterfly option strategy.

buy-and-hold asset/investment: an asset/investment for a passive long-term strategy where the investor holds a long position irrespective of short-term fluctuations in the market.

buy-write strategy: buying stock and writing (selling) a call option against the stock position.

calendar spread (for futures): buying (selling) a near-month futures and selling (buying) a deferred-month futures.

calendar spread (for options): buying a longer-expiration option (call or put) and selling a shorter-expiration option (of the same type, for the same underlying, and with the same strike price).

call option (a.k.a. call): see European call option, option.

Canary option: an option that can be exercised, say, quarterly, but not before

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

a determined time period, say, 1 year, has elapsed.

cancel-replaced order: a placed order that has been subsequently canceled and replaced with another order.

canceled order: a placed order that has been subsequently canceled.

capital allocation: see asset allocation.

capital gain strategy: a strategy that profits from buying and selling an asset (or, more generally, establishing and liquidating a position).

Carhart’s momentum factor (a.k.a. MOM): winners minus losers by (12- month) momentum.

carry (a.k.a. cost of carry): a return (positive or negative) from holding an asset.

carry trade (a.k.a. carry strategy): a strategy based on earning a spread between borrowing a low carry asset and lending a high carry asset.

cash (for indexes): in common trader lingo, “cash” refers to the underlying index portfolio (e.g., the S&P 500 stocks for the S&P 500 index).

cash-equivalent asset: a highly liquid short-term investment security with high credit quality (e.g., REPO).

cash flow: the net amount of cash and cash-equivalent assets being transferred into and out of a company (in the business context) or a portfolio (in the trading context).

cash flow shortfall: the amount by which a financial obligation or liability exceeds the amount of cash (or, more generally, liquid funds) that is available.

cash merger: a merger where the acquirer company pays the target company’s shareholders cash for its stock.

CDO tranche: a part of a CDO consisting of assets with different credit ratings and interest rates.

CDO tranche spread: for achieving a null MTM of a CDO tranche, the value of the default leg of the tranche divided by its risky duration.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

CDS basis: CDS spread minus bond yield spread.

CDS basis arbitrage (a.k.a. CDS arbitrage): buying a bond and insuring it with a CDS.

CDS index: a credit default swap index such as CDX and iTraxx.

CDS spread: a periodic (e.g., annual) premium per dollar of the insured debt.

cents-per-share (CPS): the realized P&L in cents (as opposed to dollars) divided by the total shares traded (which includes both establishing and liquidating trades).

channel: a range/band, bounded by a ceiling and a floor, within which the stock price fluctuates.

Chapter 11: a chapter of Title 11, the United States Bankruptcy Code.

cheap stock: a stock that is perceived to be undervalued by some criterion.

claim: the payoff of an option (or some other derivative).

class: in machine learning, one of the possible predicted outcomes of a machine learning algorithm.

close (a.k.a. close price, or closing price): the closing price of a stock at the NYSE close (4:00 PM Eastern Time).

close-to-close return: the return from the close of the previous trading day to the close of the current trading day.

close-to-open return: the return from the close of the previous trading day to the open of the current trading day.

clustering algorithm: grouping objects (into clusters) based on some similarity criterion (or criteria).

Cochrane-Piazzesi predictor: a bond return predictor.

collar (a.k.a. fence): an option trading strategy.

collateral: something of value pledged as security for repayment of a loan, forfeited if the borrower defaults.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

collateralized debt obligation (CDO): an asset-backed security (ABS) consisting of a basket of assets such as bonds, credit default swaps, etc.

combo (for options): a type of option trading strategies.

commercial paper: short-term unsecured promissory notes issued by companies.

commercial real estate: real estate property used for business purposes (rather than living space), e.g., shopping centers, retail shops, office space, etc.

Commitments of Traders (COT): weekly reports provided by CFTC.

commodity: a raw material (e.g., gold, silver, oil, copper) or an agricultural product (e.g., wheat, soy, rice) that can be bought and sold.

commodity allocation percentage (CA): the allocation weight for commodities included as an inflation hedge in a portfolio of other assets.

commodity futures: futures contracts on commodities.

common stock: a security representing ownership in a corporation entitling its holder to exercise control over the company affairs (e.g., via voting on electing a board of directors and corporate policy), with the lowest priority (after bondholders, preferred stockholders, etc.) for rights to the company’s assets in the event of its liquidation.

compounding: reinvestment of interest earned to generate additional interest in the future.

compounding period: the period between two consecutive points in time when interest is paid or added to the principal.

conditional expectation (a.k.a. conditional expected value, or conditional mean): an average value of a quantity assuming some condition occurs.

conditional independence: A and B are conditionally independent assuming C is true iff the occurrence of A assuming C is independent from the occurrence of B assuming C and vice versa, i.e., $P ( A \cap B | C ) = P ( A | C ) \times P ( B | C )$ , where P (A|B) is a conditional probability.

conditional probability: P (A|B), the probability of A occurring assuming

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

B is true.

condor: a type of options strategies.

constrained regression: a linear regression subject to a set of linear or nonlinear constraints, e.g., non-negative least squares (NNLS), where the regression coefficients are required to be nonnegative.

Consumer Price Index (CPI): a measure of the price level of a market basket of consumer goods and services.

contango: when the futures curve (term structure) is upward-sloping.

contingent leg: in a CDO, the default leg, the other leg being the premium leg.

continuous compounding: an idealized mathematical limit of compounding where the number of compounding periods n goes to infinity, the length δ of each compounding period goes to zero, and the product n × δ is kept fixed and finite.

contrarian effect: see mean-reversion effect.

control rights: the legal entitlements granted to an investor (e.g., a shareholder holding common stock), such as the right to transfer shares, receive regular and accurate financial disclosure, vote on specific issues at the company, etc.

conversion factor: the quoted price a bond would have per dollar of principal on the first day of the delivery month of an interest rate futures contract assuming that the interest rate for all maturities equals 6% per annum with semiannual compounding.

conversion factor model: a model (based on the conversion factor) commonly used to calculate hedge ratios when hedging interest rate risk with interest rate futures.

conversion price: the price of the underlying stock at which a convertible bond can be converted into stock.

conversion ratio: the number of the issuer’s stock shares into which a convertible bond can be converted.

convertible arbitrage: a trading strategy involving a convertible bond and stock of the same issuer.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

convertible bond: a hybrid security with an embedded option to convert a bond to a preset number (conversion ratio) of the issuer’s stock when, e.g., the stock price reaches a preset level (conversion price).

convexity (for bonds): a measure of non-linear dependence of bond prices on changes in interest rates, which involves the second derivative of the bond price w.r.t. the interest rates.

core inflation (CI): long run inflation, with items subject to volatile prices (such as food and energy) excluded (cf. headline inflation)

corporate actions: events initiated by a publicly traded company such as stock splits, dividends, mergers and acquisitions (M&A), rights issues, spin-offs, etc.

correlation: a measure of how closely two securities move in relation to each other, defined as the covariance of their returns divided by a product of the standard deviations of said returns.

correlation matrix: an N × N matrix with unit diagonal elements, whose off-diagonal elements are the pair-wise correlations of N different securities.

correlation trading: arbitraging the average pair-wise correlation of the index constituents vs. its future realized value.

counterparty: the other party that participates in a financial transaction.

coupon bond: a bond that makes periodic coupon payments before maturity.

coupon rate: an uncompounded, fixed or variable rate at which a coupon bond makes coupon payments.

covariance: a mean value of the product of the deviations of the returns of two securities from their respective mean values.

covariance matrix: an N × N matrix, whose off-diagonal elements are the pair-wise covariances of N different securities, and whose diagonal elements are the corresponding variances.

covered call: see buy-write strategy.

covered interest arbitrage: a trading strategy that exploits deviations from CIRP.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

covered put: see sell-write strategy.

credit default swap (CDS): a swap that provides insurance against default on a bond.

credit derivatives: financial contracts (e.g., CDS) that allow parties to transfer or receive exposure to credit risk.

credit rating (for bonds): a measure of the creditworthiness of corporate or government bonds (e.g., S&P’s credit ratings AAA, AA+, AA, AA-, A+, A, A-, BBB+, BBB, BBB-, BB+, BB, BB-, B+, B, B-, CCC+, CCC, CCC-, CC, C, D).

credit spread: the difference between the bond yield and the risk-free rate (same as the bond yield spread).

cross-border tax arbitrage: exploiting differences in the tax regimes of two or more countries.

cross-hedging: managing risk exposure to one security by taking an opposite position (with some hedge ratio) in another security (or its derivative, e.g., futures), where the two securities are positively correlated and have similar price movements.

cross-sectional quantity: a quantity (e.g., mean, standard deviation, etc.) computed across a set of securities (e.g., stocks in a portfolio) as opposed to serially (i.e., across a time series for each security).

cross-sectional regression: a regression where the independent variables are vectors whose elements are labeled by a cross-sectional index, e.g., that which labels stocks in a portfolio (cf. serial regression).

cross-validation (a.k.a. out-of-sample testing): a technique to evaluate predictive models by partitioning the original data sample into a training set to train the model, and a test set to evaluate it.

cryptoassets: cryptocurrencies and similar digital assets.

cryptocurrency: a digital medium of exchange that uses cryptography (e.g., BTC).

cryptography: constructing and analyzing protocols that prevent third parties from reading private messages.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

cum-dividend: when the stock buyer is entitled to receive a dividend that has been declared but not paid (cf. ex-dividend).

cumulative inflation: inflation rate measured from time $t _ { 1 }$ to time $t _ { 2 }$ (cf.   
year-on-year inflation).

cumulative return: an asset’s return from time $t _ { 1 }$ to time $t _ { 2 }$

curvature: in a yield curve, the change in the slope thereof as a function of maturity.

curve-neutrality: approximate neutrality of a bond portfolio to small steepening and flattening of the yield curve.

curve trade: a flattener or steepener (in bonds or CDOs).

daily roll value: futures basis divided by the number of business days until the settlement.

dark spread: the difference between the wholesale price of electricity and the price of coal required to produce it by a coal-fired power plant.

data mining: a process of finding patterns/trends in large data sets.

debt seniority: the order of repayment of debt in the event of a sale or bankruptcy of the debt issuer.

decentralized digital currency: a decentralized cryptocurrency such as BTC, ETH, etc.

decile: each of the 10 (approximately) equal parts of a sample (e.g., data sample).

default: a failure to repay a loan/debt.

default risk: the (estimated/perceived) risk of a default of a borrower.

deferred-month futures: a futures contract with the settlement date in the later months (cf. front-month futures).

delay-d backtest: a backtest in which all quantities used for establishing or liquidating simulated positions at any given time t are computed using historical quantities from times at least d trading days prior to t.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

deliverable bond: a bond in the delivery basket of an interest rate futures contract.

delivery: transferring the underlying instrument (or commodity) in a contract (e.g., futures or forward) to the buyer at maturity (delivery date) at a pre-agreed price (delivery price).

delivery basket: in interest rate futures, the array of bonds that can be delivered at the delivery date.

delivery month: the month in which the delivery in a futures contract occurs.

Delta: the first derivative of the value of a derivative asset (e.g., option) w.r.t.   
the price of the underlying asset.

Delta-hedge: hedging a long (short) position in a derivative asset with a short (long) position in the underlying asset with the hedge ratio equal the Delta of the derivative asset.

Delta-neutral strategy: a trading strategy which achieves null Delta via, e.g., Delta-hedging.

demeaning: subtracting from the elements of a sample their mean value across said sample.

derivative (a.k.a. derivative contract, or contingent claim): a security (e.g., option) whose future payoff depends on the value of its underlying asset (e.g., stock) and is contingent on some uncertain future event.

desired holdings: portfolio holdings to be attained by a trading strategy.

detachment (a.k.a. detachment point): the percentage of the underlying portfolio loss at which a tranche of a CDO (collateralized debt obligation) loses all its value.

diagonal spread: an option trading strategy.

dimnames: a command in R for the names of column and row labels of a matrix.

directional strategy: a strategy that profits based on the underlying secu-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

rity’s (or securities’) future direction (cf. non-directional strategy).

discount bond (a.k.a. zero-coupon bond): a bond that pays only its principal at maturity but makes no coupon payments.

discount factor: the worth of a discount bond with \$1 principal at time t prior to its maturity T .

discount rate (a.k.a. Fed discount rate, or Federal discount rate): the interest rate charged to commercial banks and other depository institutions for loans received from the U.S. Federal Reserve.

discretionary strategy: a strategy that relies on the fund manager’s skills (cf. systematic strategy).

discretionary macro: discretionary global macro strategies based on analysts’ subjective opinions.

dispersion trading: arbitraging the index implied volatility vs. implied volatilities of its constituents.

distress risk puzzle: an empirical occurrence that companies with lower bankruptcy risk tend to yield higher returns than riskier ones.

distressed asset: an asset (e.g., debt) of a distressed company.

distressed debt: see distressed asset.

distressed debt strategy: strategies based on acquiring debt of a distressed company.

distressed company: a company undergoing financial or operational distress.

distributed ledger: a database shared and synchronized across a (typically large, peer-to-peer) network encompassing multiple sites.

diversification: allocating capital to reduce exposure to any one particular asset or risk by investing in a variety of assets.

dividend: a distribution of some of the earnings of a company, as decided by its board of directors, to a class of its shareholders, usually (but not always) quarterly.

dividend imputation: a corporate tax system in which some or all of the

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

tax paid by a company may be attributed, or imputed, to the shareholders via a tax credit to reduce the income tax payable on a distribution via, e.g., dividends.

dollar carry trade: an FX trading strategy.

dollar duration: a measure of the absolute bond price sensitivity to changes in the interest rates, defined as the modified duration times the bond price.

dollar-duration-neutrality: when the sum of dollar durations of a bond portfolio is null (with dollar durations of short bond positions defined to be negative).

dollar holding (a.k.a. dollar position): the dollar value of an asset’s position in a portfolio.

dollar-neutrality: when the sum of dollar holdings in a portfolio is null (with dollar holdings of short positions defined to be negative).

domestic currency: the currency of the investor’s home country.

Donchian Channel: a commonly used definition of a channel in channel trading strategies.

double-taxation: a corporate taxation system (e.g., in the U.S.) where the corporate income is first taxed at the corporate level, and then again when dividends are received by the shareholders.

downside risk: the risk associated with losses.

drawdown: a peak-to-trough decline in the P&L during a given period, where the peak (trough) is defined as the P&L maximum (minimum) in said period.

drift: a mean change in a time-dependent quantity over a period of time, i.e., a serial mean.

dual-momentum sector rotation: an ETF momentum strategy.

dumb order flow (a.k.a. uninformed order flow): aggressive order flow not based on a predictive expected return.

dummy variable (a.k.a. binary variable): a predictor variable taking binary values 0 or 1 to indicate the absence or presence of some effect or belonging or not belonging to some category that may affect the outcome (e.g., if a company belongs to a given economic sector).

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

duration: see dollar duration, Macaulay duration, modified duration, risky duration.

duration-hedging: hedging duration risk (i.e., interest rate risk) with interest rate swaps or interest rate futures.

duration-targeting strategy: a strategy (e.g., a bond ladder) that maintains an approximately constant duration by selling shorter-maturity bonds as they approach maturity and replacing them with new longer-maturity bonds.

dynamic asset allocation: frequently adjusting the asset allocations in a portfolio according to changing market conditions.

earnings: the after-tax net income of a company.

earnings-momentum: a momentum strategy based on earnings.

economic activity: production, distribution, exchange and consumption of goods and services.

economic data: data (typically, time series) pertaining to an actual economy.

eigenvalue: a root of the characteristic equation of a matrix (see eigenvector).

eigenvector: for a square symmetric N × N matrix A, an N -vector V that solves the characteristic equation A V = λ V , where λ is the corresponding eigenvalue (which is a number).

electronic trading: trading securities electronically, as opposed to by human traders on the trading floors of the exchanges.

EMA: an exponential moving average, a serial moving average with past contributions suppressed with exponentially decreasing weights.

embedded option: in a convertible bond, the option to convert the bond to a preset number of the issuer’s stock.

EMSD: an exponential moving standard deviation, a serial moving standard deviation with past contributions suppressed with exponentially decreasing weights.

equally-weighted portfolio: a portfolio where all assets have equal dollar

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

holdings.

equity: a company’s stock or other security representing its ownership interest.

equity market: a stock market.

equity tranche: the lowest quality tranche of a CDO.

eRank (a.k.a. effective rank): a measure of effective dimensionality of a matrix.

error function: in machine learning, a function to be minimized that is constructed from the errors (or similar), e.g., the sum of squares of the errors, or some other suitable function (not to be confused with the Gauss error function erf(x)).

establishing: buying or shorting an asset or portfolio from a null position.

estimation period: the length of a time-series data sample used in estimating some parameters, e.g., regression coefficients.

ETH: ether/Ethereum, a cryptocurrency.

Euclidean distance: the distance between two vectors defined as the square root of the sum of squares of the differences between their components.

EUR: euro, a unit of the eurozone currency.

eurodollar: a USD deposit held in a bank outside the U.S.

European call option: a right (but not an obligation) to buy a stock at the maturity time T for the strike price k agreed on at time t = 0.

European put option: a right (but not an obligation) to sell a stock at the maturity time T for the strike price k agreed on at time t = 0.

ex-dividend when the stock seller is entitled to receive a dividend that has been declared but not paid (cf. cum-dividend).

excess return: a return of an asset in excess of some benchmark return (e.g., risk-free rate).

exchange rate (a.k.a. FX rate): the rate of exchange between two dif-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

ferent currencies.

execution price: the price at which an order (e.g., to buy stock) is filled (executed).

exercise date: a date on which an option can be exercised.

exotic options: a broad category of options that typically are complexly structured.

expected return: a future return of an asset expected based on some reasonable consideration, e.g., an average realized return over some past period.

expiration: the last date on which a derivatives contract (e.g., option or futures) is valid.

explanatory variable: a variable that has (or is expected to have) some explanatory power for an observed variable (e.g., hours studied by a student for a final exam can be expected to be an explanatory variable for the student’s final exam grade/score).

exponential smoothing parameter: the exponential suppression factor in an exponential moving average.

exposure: the amount that can be lost (or gained) in an investment.

face value (a.k.a. principal): the amount paid to the bondholder at maturity.

factor (a.k.a. risk factor): a common explanatory variable for a cross-section of asset returns (e.g., stocks).

factor loadings matrix: the N × K matrix $\Omega _ { i A } \ ( i = 1 , \ldots , N , A = 1 , \ldots , K .$ typically $K \ll N )$ in a K-factor model $\begin{array} { r } { Y _ { i } = \sum _ { A = 1 } ^ { K } \Omega _ { i A } \ F _ { A } + \epsilon _ { i } } \end{array}$ , where $Y _ { i }$ are the observed variables, $F _ { A }$ are the unobserved variables (common factors), and $\epsilon _ { i }$ are the unobserved error terms.

factor portfolio: a portfolio that aims to attain exposure to a given factor.

fair value: a market value of a security or, in the absence of a market value, a theoretical value based on some reasonable modeling.

Fama-French factors: MKT, the excess return (defined as the return in excess of the risk-free rate, in turn defined as the one-month Treasury bill rate) of

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

the market portfolio; SMB, the excess return of the Small minus Big (by market capitalization) portfolio; HML, the excess return of the High minus Low (by bookto-market) portfolio.

Fama puzzle: see forward discount anomaly.

feature (in machine learning): a predictor, an input variable.

fiat currency: a legal tender declared by a government (e.g., U.S. dollar) but not backed by a physical commodity (such as gold).

fill: when an order to buy or sell a security or commodity is completed, with a partial completion (e.g., only 100 shares of a 200 share buy order are filled) known as a partial fill.

fill or kill limit order (a.k.a. FOK): a limit order to buy or sell stock that must be executed immediately and completely or not at all (no partial fills are allowed).

financial crisis: when some financial assets suddenly lose a large part of their nominal value.

first-month contract: see front-month futures.

fix-and-flip: a real estate strategy.

fixed coupon bond (a.k.a. fixed rate coupon bond): a bond with a fixed (as opposed to variable) coupon rate.

fixed-income asset: a debt instrument that generates fixed returns in the form of interest payments.

fixed interest rate (a.k.a. fixed rate): an interest rate on a liability that remains unchanged either for the entire term of the loan or for its part.

fixed rate payment: a coupon payment of a fixed coupon bond.

flattener: a yield curve spread bond strategy.

floating coupon bond (a.k.a. floating rate coupon bond, or variable coupon bond, or variable rate coupon bond): a bond with a variable (as opposed to fixed) coupon rate.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

floating interest rate (a.k.a. floating rate, or variable interest rate, or variable rate): interest rate on a liability that varies during the term of the loan.

floating rate payment: a coupon payment of a floating coupon bond.

FOMC announcements: Federal Open Market Committee announcements such as interest rate hikes.

forecasting future returns: predicting future returns.

foreign currency: a currency (that is different from the domestic currency) of a country other than the investor’s home country.

formation period: in momentum strategies, the period over which the momentum indicator is computed.

forward (a.k.a. forward contract): a contract struck at time t = 0, where one of the two parties agrees to sell the other an asset at some future time T (known as the expiry, delivery date or maturity of the contract) for the pre-agreed strike price k.

forward discount: when the forward FX rate is lower than the spot FX rate.

forward discount anomaly (a.k.a. forward premium anomaly, or forward discount puzzle, or forward premium puzzle, or Fama puzzle): an empirical occurrence whereby on average high interest rate currencies tend to appreciate (somewhat) w.r.t. low interest rate currencies.

forward FX rate: the FX rate of a forward FX contract.

forward premium: when the forward FX rate is higher than the spot FX rate.

front leg: shorter-maturity bonds in a yield curve spread strategy (flattener or steepener).

front-month futures: a futures contract with the settlement date closest to the current date (cf. deferred-month futures).

fundamental analysis: evaluating securities based on fundamental data.

fundamental data: data pertaining to the fundamentals of stocks or other

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

securities, including time series and/or cross-sectional data.

fundamental industry classification: an industry classification of companies (into sectors, industries, sub-industries, etc.) based on fundamental/economic data, such as companies’ products and services, revenue sources, suppliers, competitors, partners, etc. (cf. statistical industry classification).

fundamental trading strategy: a trading strategy based on fundamental analysis.

fundamentals: quantitative and qualitative information on the financial/economic health and valuation of a company, security, currency, etc.

futures (a.k.a. futures contract): a standardized forward contract traded on a futures exchange.

futures basis: the futures price minus the underlying spot price.

futures curve (a.k.a. futures term structure): the dependence of the futures prices on time to delivery.

futures delivery basket: see delivery basket.

futures spread: see calendar spread (for futures).

FX pair: currencies of 2 different countries.

FX rate: see exchange rate.

FX rate risk: exposure to FX rate changes.

FX spot rate: see spot FX rate.

FX triangular arbitrage: arbitraging 3 FX pairs.

Gamma: the second derivative of the value of a derivative asset (e.g., option) w.r.t. the price of the underlying asset.

Gamma hedging: an options hedging strategy to eliminate or reduce the exposure caused by changes in an option portfolio’s Delta as a result of the underlying security’s price movements.

Gamma scalping: Gamma hedging by buying and selling the underlying secu-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

rity in response to its price movements that cause changes in an option portfolio’s Delta.

global macro: trading strategies seeking to capitalize on regional, economic and political changes around the world.

Greeks: see Delta, Gamma, Theta, Vega.

greenfield project: a project associated with infrastructure assets to be constructed.

guaranteed loan: a loan guaranteed by a third party in case the borrower defaults.

guts: an option trading strategy.

hard-to-borrow security: a security on a “Hard-to-Borrow List”, an inventory record used by brokerages for securities that are difficult to borrow for short sale transactions due to short supply or high volatility.

headline inflation (HI): a measure of the total inflation within an economy, including commodity prices such as food and energy (cf. core inflation).

heat rate: the efficiency with which an electricity production plant converts fuel into electricity.

hedge: an investment (typically, via an offsetting position in a related security) to reduce the risk of losing money on an existing position.

hedge ratio: in a hedge, the number of units (or the dollar notional) of the offsetting security for each unit (or dollar) of the security to be hedged.

hedger: a market participant attempting to reduce risk associated with a security’s price movement (cf. speculator).

hedging pressure (HP): in (commodities) futures markets, the number of long contracts divided by the total number of contracts (long plus short).

hedging strategy: see hedge.

heterotic risk model: a multifactor risk model combining a multilevel fundamental industry classification with principal component analysis.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

hidden layers: in an artificial neural network, the intermediate layers of nodes (artificial neurons) between the input layer and the output layer.

high (a.k.a. high price): the maximum price attained by a stock (or other security) within a given trading day (or some other time interval).

high-minus-low carry: an FX trading strategy based on the forward discount anomaly.

High Yield bonds (a.k.a. junk bonds): bonds with S&P credit ratings below BBB-.

historical quantity: a quantity (e.g., correlation, variance, volatility, return, etc.) computed based on historical data.

HMD (a.k.a. healthy-minus-distressed): buying the safest companies and selling the riskiest ones by probability of bankruptcy.

HML (a.k.a. High minus Low): see Fama-French factors.

Hodrick-Prescott filter (a.k.a. HP filter, or Whittaker-Henderson method in actuarial sciences): a time-series filter for separating a lower-frequency (“regular”) component from a higher-frequency (“irregular”) component (noise).

holding period: the period for which a position in a security or a portfolio is held after being established and before being liquidated (or, more loosely, rebalanced).

holding weights: the weights with which assets are held in a portfolio.

holdings: the contents of a portfolio; also, a shorthand for, e.g., dollar holdings.

horizon (a.k.a. investment horizon): see holding period.

horizontal spread (a.k.a. time spread): see calendar spread.

Hybrid Market: a blend of an automated electronic trading platform and a traditional (human-operated) floor broker system.

hybrid security: a security with mixed characteristics of two asset classes, e.g., a convertible bond.

IBS: internal bar strength, defined as the difference between the close price

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

and the low price divided by the difference between the high price and the low price.

implied volatility: in option pricing, the volatility of the underlying instrument, which, when used as an input in an option pricing model (such as the Black-Scholes model), yields the model value of the option price equal to its market value.

imputation system: see dividend imputation.

in-sample: when a computation or backtest is not out-of-sample.

in-the-money (ITM) option: a call (put) option whose exercise price is below (above) the current price of the underlying asset.

income strategy: a trading strategy that generates income, usually via some risk exposure.

incomplete basket: a subset of the portfolio that would ideally be traded, e.g., in index arbitrage.

index: a diversified portfolio of assets combined with some weights.

index arbitrage (a.k.a. cash-and-carry arbitrage): an arbitrage strategy exploiting mispricings between the index spot price and index futures price (i.e., the index futures basis).

index basket: an index portfolio.

index constituents: the assets in an index portfolio.

index ETF: an ETF that tracks an index.

index futures: a futures on an index.

index hedging: hedging a position (e.g., a CDO tranche) with a pertinent index.

index level: for market cap weighted indexes, the current value of the index level $I ( t ) = I ( 0 ) \times C ( t ) / C ( 0 )$ , where I(0) is the initial value of the index level (which is defined, not calculated), C(t) is the current total market cap of the index constituents, and C(0) is its initial value.

index spot price: the current market price of an index basket, where the number of units of each constituent is determined by the index weighting scheme

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

(market cap weighted index, price weighted index, etc.) with the overall normalization constant fixed depending on a specific purpose, e.g., to match the index portfolio to be delivered at the index futures delivery in the case of index arbitrage.

indexed payments: payments adjusted according to the value of some index, e.g., CPI in inflation swaps or TIPS.

industrial properties: commercial real estate properties including manufacturing buildings and property, warehouses, etc.

industry (in economy): a group of companies that are related based on their primary business activities.

industry (in industry classification): a grouping of companies based (among other things) on which economic industry they belong to.

industry classification: a taxonomy of companies (stocks) based on some similarity criterion (or criteria), e.g., a company’s main source of revenues, how closely stock returns follow each other historically, etc.

inflation: a sustained increase in the price level of goods and services in an economy over a period of time, which is measured as an annual percentage change known as the inflation rate.

inflation hedge: a hedge against inflation.

inflation index: e.g., CPI.

inflation-indexed product: a security (e.g., TIPS) with indexed payments based on an inflation index.

inflation swap: a swap whose buyer is long the inflation and receives a floating rate (based on an inflation index) and pays a fixed rate (breakeven rate).

informed order flow: see smart order flow.

infrastructure funds: unlisted infrastructure funds (private equity-type investments), listed infrastructure funds (exchange-traded).

infrastructure investment: investing in long-term projects such as transportation (roads, bridges, tunnels, railways, ports, airports, etc.), telecommunications (transmission cables, satellites, towers, etc.), utilities (electricity generation, gas or electricity transmission or distribution, water supply, sewage, waste, etc.), en-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

ergy (including but not limited to renewable energy), healthcare (hospitals, clinics, senior homes, etc.), educational facilities (schools, universities, research institutes, etc.), etc.

input layer: in an artificial neural network, the layer of nodes (artificial neurons) that processes the input data.

institutional trader: a trader who buys and sells securities for an account of a group or institution such as a pension fund, mutual fund, insurance company, ETF, etc.

integration: the final step of the money laundering process whereby money launderers get back the money via legitimate-looking sources.

intercept: in a linear regression, the regression coefficient of the independent variable (which is also colloquially referred to as the intercept) whose elements are all equal 1.

interest: the amount paid by the borrower to the lender above the principal (the actual amount borrowed).

interest rate: the interest per \$1 of the principal.

interest rate futures: a futures contract typically with an array (delivery basket) of underlying instruments (e.g., bonds) that pay interest.

interest rate risk (a.k.a. interest rate exposure): the exposure to interest rate fluctuations, which affect bond and other fixed-income asset prices.

interest rate spread: the difference between the interest rates paid by two instruments.

interest rate swap: a contract that exchanges a stream of floating rate payments for a stream of fixed rate payments or vice versa.

intra-asset diversification: in real estate investments, diversification by property type (residential, commercial, etc.), economic diversification (by different regions divided according to economic characteristics), geographic diversification, etc.

intraday arbitrage: taking advantage of intraday mispricings, e.g., in ETFs and stocks.

intraday signal: a trading signal used by an intraday strategy.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

intraday strategy: a trading strategy that starts with a null position, buys and sells/shorts securities intraday, and ends with a null position by the close (in trader lingo, “goes home flat”).

inverse ETF: an ETF designed to track the return inverse to its underlying index.

inverse matrix: for an N × N square matrix A, the inverse matrix A−1 is the N × N square matrix such that $A \ A ^ { - 1 } = A ^ { - 1 } \ A = I$ , where I is the N × N identity matrix (whose diagonal elements equal 1, and off-diagonal elements equal 0).

investment: allocating money with an expectation of a positive return.

Investment Grade bonds (a.k.a. IG bonds): bonds with S&P credit ratings AAA through AA- (high credit quality) and A+ through BBB- (medium credit quality).

investment vehicle: an investment product (e.g., ETF) used by investors for generating positive returns.

iron butterfly: a type of option trading strategies.

iron condor: a type of option trading strategies.

iShares (ticker IVV): an S&P 500 tracking EFT.

Jensen’s alpha: an abnormal return of a security or portfolio, usually calculated as the intercept coefficient in a linear model, where excess returns of said security or portfolio are serially regressed over excess returns of one or more factor portfolios (e.g., MKT).

Joule: a unit of work, heat and energy in the International System of Units (SI).

JPY: Japanese Yen, a unit of Japanese currency.

junior mezzanine tranche: the next (by increasing quality) tranche of a CDO after the equity tranche.

k-nearest neighbor algorithm (a.k.a. KNN or k-NN): a statistical classification algorithm based on a similarity criterion such as distance, angle, etc., between multi-dimensional vectors.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Kalman filter: a time-series filter for separating signal from noise.

Kelly strategy: an allocation (betting) strategy based on maximizing the expectation of the logarithm of wealth.

keyword: in sentiment analysis (e.g., Twitter sentiment) using machine learning techniques, a word in the learning vocabulary pertinent to the goal (e.g., predicting stock or cryptocurrency price movements).

ladder (for bonds): a bond portfolio with (roughly) equal capital allocations into bonds of a sizable number of different (and usually approximately equidistant) maturities.

ladder (for options): a vertical spread consisting of 3 options, all 3 are call options or put options, 2 are long and 1 is short, or 1 is long and 2 are short.

Lagrange multiplier: when minimizing a (multivariate) function g(x) w.r.t. x subject to a constraint h(x) = 0, an additional variable λ in the function g(x, λ) = g(x) + λ h(x), whose (unconstrained) minimization w.r.t. x and λ is equivalent to the original constrained minimization problem.

layer: see input layer, output layer, hidden layer.

layering: the middle step in the money laundering process, which amounts to moving the money around between different accounts and even countries thereby creating complexity and separating the money from its source by several degrees.

learning vocabulary: in sentiment analysis (e.g., Twitter sentiment) using machine learning techniques, a set of keywords pertinent to the goal (e.g., predicting stock or cryptocurrency price movements).

least squares: in regression analysis, minimizing the sum of squares of the residuals (possibly, with nonuniform weights).

ledger: a book or other collection of financial accounts and transaction records.

leg: a component in a trading portfolio, usually when a portfolio can be thought of as consisting of a relatively small number of groupings (e.g., short leg and long leg, referring to short and long positions, respectively).

LETF: leveraged (inverse) ETF, an ETF designed to track the return (inverse to) n times the return of its underlying index, where n is the leverage (usually, 2 or 3).

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

leverage: using borrowed funds to purchase an asset.

limit order: an order to buy or sell a stock (or other security) at a specified price or better.

linear homogeneous constraint: for an N-vector $x _ { i } \ ( i = 1 , \ldots , N )$ , a constraint of the form $\textstyle \sum _ { i = 1 } ^ { N } a _ { i } \ x _ { i } = 0$ , where at least some $a _ { i }$ are nonzero.

linear regression (a.k.a. linear model): fitting data for the observable variable using a linear combination of some number of (linear or nonlinear) functions of independent variables, with or without the intercept.

liquid asset: an asset that can be converted into cash quickly with minimal transaction costs.

liquid U.S. stocks: a subset of U.S. listed stocks usually defined using ADDV and market cap filters (e.g., top 2,000 most liquid stocks by ADDV).

liquidation (for assets or portfolios): closing of the open positions.

liquidation (for companies): winding up (bringing to an end) a company’s business and distributing its assets to claimants, usually when the company is insolvent.

liquidity: availability of liquid assets/funds.

loadings matrix: see factor loadings matrix.

loan: lending of money or another asset by one party (lender) to another (borrower).

loan shark: a lender offering a loan at excessively high interest rates.

loan-to-own strategy: financing a distressed company via secured loans with the view of obtaining equity with control rights if the company files for bankruptcy.

log: a logarithm (usually, unless specified otherwise, the natural logarithm).

log-return: the natural log of the ratio of an asset’s price at time $t _ { 2 }$ to its price at time $t _ { 1 } \ \left( t _ { 2 } > t _ { 1 } \right)$

log-volatility: a standard deviation of the natural logarithms of prices.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

logistic regression (a.k.a. logit model): a statistical model typically applied to a binary dependent variable.

long-only: a portfolio or strategy with only long holdings.

long-run mean: in a mean-reverting Ornstein-Uhlenbeck process, the mean value of the state variable in the infinite time limit.

long-short: a portfolio or strategy with both long and short holdings.

lookback (a.k.a. lookback period): the length of a time-series data sample used in a backtest or historical computation.

losers: stocks or other assets in a portfolio or trading universe that underperform based on some criterion (benchmark).

low (a.k.a. low price): the minimum price attained by a stock (or other security) within a given trading day (or some other time interval).

low-volatility anomaly: an empirical occurrence that future returns of previously low-return-volatility portfolios outperform those of previously high-returnvolatility portfolios.

Macaulay duration: a weighted average maturity of a bond’s cash flows, where the weights are the present values of said cash flows.

machine learning (ML): a method of data analysis that automates predictive analytical model building based on the premise that computational systems can “learn” from data, identify patterns and make decisions with minimal human intervention.

macro: macro trading strategies.

Manhattan distance: the distance between two vectors defined as the sum of the absolute values of the differences between their components.

margin account: a brokerage account in which the broker lends the customer cash to purchase securities.

mark-to-market (MTM): valuing assets or portfolios based on the most recent pertinent market prices.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

market: a medium that allows buyers and sellers to interact to facilitate an exchange of securities, commodities, goods, services, etc.

market beta: a measure of the volatility (systematic risk) of an asset or portfolio in comparison to the broad market.

market capitalization (a.k.a. market cap, or cap): the market value of a company’s shares outstanding.

market crash: a sudden dramatic decline of asset prices across their significant cross-section.

market data: price and trade-related data for a financial security reported by a trading exchange (or similar).

market-making: providing liquidity by simultaneously quoting both buy and sell prices in a financial instrument or commodity held in inventory with the view of making a profit on the bid-ask spread.

married call: see protective call.

married put: see protective put.

maturity (a.k.a. maturity date, or maturity time): the time at which a financial instrument will cease to exist and any principal and/or interest are repaid in full.

mean: an average value.

mean-reversion effect (a.k.a. mean-reversion, or contrarian effect): a tendency of asset prices and/or their returns to revert to their mean values, which mean values can be serial and/or cross-sectional, depending on the context.

mean-reversion parameter: in a mean-reverting Ornstein-Uhlenbeck process, the parameter that controls the rate of mean-reversion.

mean-reversion strategy: a trading strategy based on a mean-reversion effect.

mean-variance optimization: an optimization technique for constructing a portfolio of assets such that its expected return is maximized for a given level of its risk.

Megawatt: 1,000,000 watts.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Megawatt hour (Mwh): 1,000,000 watts times 1 hour, which equals 3.6 × 109 Joules.

merger: a consolidation of two companies into one.

merger arbitrage (a.k.a. risk arbitrage): a trading strategy that attempts to capture excess returns generated via corporate actions such as mergers and acquisitions (M&A).

metropolitan statistical area (MSA): a core area containing a substantial population nucleus, together with adjacent communities having a high degree of economic and social integration with that core.

mini-S&P futures (a.k.a. e-mini): a futures contract on S&P 500 with the notional value of 50 times the value of the S&P 500 stock index.

mishedge: an imperfect hedge, or when a hedge becomes undone (e.g., by underlying price movements).

mispricing: an inefficiency in the pricing of a security, when its price does not match its intrinsic value or (perceived) fair value.

MKT: see Fama-French factors.

modified duration: a measure of the relative bond price sensitivity to changes in the interest rates, defined as the negative first derivative of the bond price w.r.t. the bond yield.

MOM: see Carhart’s momentum factor.

momentum (a.k.a. momentum effect): an empirical occurrence whereby assets’ future returns are positively correlated with their past returns.

momentum strategy: a trading strategy based on momentum.

monetary policy: usually by a central bank, a process by which the monetary authority of a country controls the size and rate of growth of the money supply, via modifying the interest rates, buying or selling government bonds, and changing the required bank reserves (the amount of money banks are required to keep in their vaults).

money laundering: an activity wherein cash is used as a vehicle to trans-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

form illegal profits into legitimate-appearing assets.

moneyness: where a derivative contract’s strike price is in relation to its underlying asset’s current price, which determines the derivative’s intrinsic value.

mortgage: a debt instrument, secured by a real estate property as a collateral, that the borrower is obligated to pay back with a predetermined set of payments.

mortgage-backed security (MBS): an asset backed by a pool of mortgages.

moving average (a.k.a. rolling average): in a time series, an average (possibly computed with nontrivial weights) over a time interval of fixed length (moving average length), where the most recent time in said interval can take various values in the time series.

moving standard deviation: in a time series, a standard deviation (possibly computed with nontrivial weights) over a time interval of fixed length, where the most recent time in said interval can take various values in the time series.

multi-currency arbitrage: arbitraging 4 or more FX pairs.

multifactor risk model: a risk model based on a number (which can be sizable) of risk factors.

multifactor strategy: a trading strategy based on combining exposures to multiple factors, e.g., momentum, value, etc. (multifactor portfolio).

multinomial probability distribution: a discrete probability distribution of a random variable which takes k different values with probabilities p1, . . . , pk.

municipal bond (a.k.a. muni bond): a bond issued by a local government/territory or its agency.

municipal bond tax arbitrage: a trading strategy based on borrowing money and buying tax-exempt municipal bonds.

mutual fund: an investment vehicle funded by a pool of money collected from many investors for the purpose of buying various securities (stocks, bonds, money market instruments, etc.).

naked call: a stand-alone short call option.

naked put: a stand-alone put call option.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

near-month contract: see near-month futures.

near-month futures: see front-month futures.

neutral curve butterfly: a bond butterfly strategy with curve-neutrality.

neutral outlook: when a trader expects the market or a security to trade around its current level.

no-risk-free-arbitrage condition: a condition that ensures that no risk-free profits can be made by a trading strategy (at least, in excess to the risk-free rate).

node: in an artificial neural network, an artificial neuron, which (using an activation function) processes a set of inputs and generates an output.

noise: in a financial time series, random fluctuations without any apparent trend.

non-announcement days: days without any important economic announcements such as FOMC announcements (cf. announcement days).

non-deliverable bond: a bond not in the delivery basket of an interest rate futures contract.

non-directional strategy (a.k.a. neutral strategy): a strategy not based on the underlying security’s (or securities’) future direction, so the trader is oblivious to whether its price goes up or down (cf. directional strategy).

non-discretionary strategy: a trading strategy based on a systematic approach (as opposed to discretionary).

non-systematic risk: specific (a.k.a. idiosyncratic) risk, which is specific to each company, asset, etc., and exposure to which can be reduced via diversification, albeit never completely eliminated (cf. systematic risk).

nonlinear least squares: least squares used to fit a set of observations with a model that is nonlinear in the unknown parameters (regression coefficients).

notional (a.k.a. notional value): the total (dollar) value of a position.

objective function: a function to be maximized or minimized in optimization.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

open (a.k.a. open price, or opening price): the opening price of a stock at the NYSE open (9:30 AM Eastern Time).

open interest (a.k.a. open contracts, or open commitments): the total number of open futures (or options) contracts at any given time (i.e., those contracts that have not been settled).

optimal hedge ratio: a hedge ratio calculated by minimizing the variance of a hedged portfolio.

optimization: see portfolio optimization.

option: a financial derivative contract that gives the buyer (option holder) the right (but not the obligation) to buy (call option) or sell (put option) the underlying asset at an agreed-upon price during a predefined period of time or on a specific date.

option-adjusted spread (OAS): a parallel shift in the Treasury curve (or some other benchmark yield curve) that matches a security’s price calculated based on a pricing model to its market value, with the view to account for the security’s embedded options.

option premium: the cost charged by the option seller to the option buyer.

option writer: an option seller.

order: an investor’s instructions to a broker or brokerage firm to purchase or sell a security.

order execution system: a software component that executes trades based on input buy and/or sell order sequences.

Ornstein-Uhlenbeck process: Brownian motion with mean-reversion.

orthogonality: vectors xi and $y _ { i } ( i = 1 , \ldots , N )$ are orthogonal if $\begin{array} { r } { \sum _ { i = 1 } ^ { N } x _ { i } y _ { i } = 0 } \end{array}$

out-of-sample backtest: a backtest in which all quantities used for establishing or liquidating simulated positions corresponding to any given time t are computed using historical quantities from times prior to t.

out-of-sample computation: a computation where all quantities to be used for forecasting purposes at any given simulated time t are computed using historical quantities from times prior to t.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

out-of-the-money (OTM) option: a call (put) option whose exercise price is above (below) the current price of the underlying asset.

outcome (a.k.a. class): in machine learning, one of the possible results (outputs, predictions) of a machine learning algorithm.

output gap: the difference between the actual output of an economy and its maximum potential output as a percentage of GDP.

output layer: in an artificial neural network, the layer of nodes (artificial neurons) that generates the output data (the result).

over-fitting: in a statistical model, fitting more free parameters than justified by the data, thereby (often unwittingly) essentially fitting noise and rendering the model unpredictive out-of-sample.

overnight return: broadly, a return from some time during the previous trading day to some time during the current day (e.g., close-to-open return, close-to-close return); usually, close-to-open return.

overreaction: in financial markets, an irrational response by market participants (based on greed or fear) to new information.

pairs trading: a mean-reversion strategy involving two historically correlated assets.

parallel shift: in a yield curve, all interest rates for all maturities changing by the same amount.

passive investing: a longer-horizon, essentially buy-and-hold, investment strategy with the view of minimizing transaction costs and replicating the performance of a (typically, well-diversified) benchmark portfolio.

passive limit order: a liquidity-providing limit order to buy at the bid (or lower) or sell at the ask (or higher).

passive trading strategy: a trading strategy based on the passive investing approach.

passthrough MBS: an MBS where cash flows are passed from debtors to investors through an intermediary.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

pawnbroker: a lender that extends a secured cash loan with pre-agreed interest and period (which can sometimes be extended), where the loan is secured with a collateral (forfeited if the borrower defaults), which is some valuable item(s), such as jewelry, electronics, vehicles, rare books or musical instruments, etc.

payment period: the period between two consecutive bond coupon payments.

payoff: the amount the option seller pays to the option buyer if and when the option is exercised.

peer-to-peer (P2P) network: a distributed computing application architecture with workload partitioned between equally privileged peers.

pension fund: a pool of funds that provides retirement income.

performance characteristics: for a portfolio or strategy, characteristics such as return-on-capital, Sharpe ratio, cents-per-share, maximum drawdown, etc.

periodic compounding: compounding with equal compounding periods, e.g., quarterly, semiannual or annual compounding.

physical commodity: the actual commodity (e.g., copper) that is delivered to a commodity futures contract buyer at the expiration.

pivot point (a.k.a. center): in support and resistance strategies, a definitiondependent quantity, e.g., defined as the equally weighted average of the previous trading day’s high, low and close prices.

placed order: an order that has been submitted to an exchange and placed in a queue for execution.

placement: the initial stage in the money laundering process, whereby illegal funds are introduced into the legal economy via fraudulent means.

Porter stemming algorithm: an algorithm for reducing words to their base form (stemming).

portfolio: a collection of assets held by an institution or individual investor.

portfolio diversification: see diversification.

portfolio optimization: selecting the best portfolio based on some criterion (e.g., maximizing the Sharpe ratio).

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

portfolio weights: the relative percentages of the dollar holdings in a portfolio to its total notional value (defined as the total notional value of the long positions plus the total absolute notional value of the short positions).

position: the amount of stock or other security held, expressed in dollars, shares, or some other units, with short positions possibly having negative values depending on a convention used.

position bounds: upper or lower bounds on the dollar holdings of various assets in a portfolio.

predicted class: in machine learning, the outcome predicted by an algorithm.

predictor (a.k.a. predictor variable): in machine learning, an input variable.

premium (for insurance-type products): a periodic payment for insurance coverage, e.g., in a CDS, CDO, etc.

premium (for options): the cost of buying an option.

premium leg: the leg of a CDO corresponding to the CDO premiums, the other leg being the default leg.

prepayment: settling a debt or installment payment before its due date (e.g., mortgage prepayment).

prepayment risk: the main risk to investors in a passthrough MBS whereby homeowners have an option to prepay their mortgages (e.g., by refinancing their mortgages as the interest rates drop).

price-momentum strategy: a momentum strategy where the momentum indicator is based on past returns.

pricing data: historical and real-time data containing prices, trading volumes and related quantities (see market data).

pricing model: a model for valuing (pricing) a security or a set of securities.

principal: the amount the debt issuer (borrower) owes the lender at debt maturity.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

principal component: for a symmetric square matrix, an eigenvector thereof normalized such that the sum of squares of its components equals 1, with different principal components ordered in the descending order by the corresponding eigenvalues.

principal component analysis (PCA): a mathematical procedure that transforms some number of (typically, correlated) variables into a (typically, smaller) number of uncorrelated variables (principal components), with the first principal component accounting for as much of the variability in the data as possible, and each succeeding principal component accounting for as much of the remaining variability as possible.

probability distribution: a function that provides the probabilities of occurrence of different possible outcomes.

probability measure: a real function valued in the interval between 0 and 1 (0 corresponding to the empty set and 1 corresponding to the entire space) defined on a set of events in a probability space that satisfies the countable additivity property, i.e., simply put, that the probability of a union of disjoint events A and B equals the sum of their probabilities.

protection buyer: a buyer of insurance.

protection seller: a seller of insurance.

protective call (a.k.a. married call, or synthetic put): hedging a short stock position with a long call option position.

protective put (a.k.a. married put, or synthetic call): hedging a long stock position with a long put option position.

publicly traded company (a.k.a. public company): a company whose shares are freely traded on a stock exchange or in over-the-counter markets.

put-call parity: the relationship whereby the payoff of a European call option (with a strike price K and expiration T ) minus the payoff of a European put option (on the same underlying and with the same strike and expiration) equals the payoff of a forward contract (on said underlying) with the strike K and expiry T .

put option (a.k.a. put): see European put option, option.

quantile: each of the n (approximately) equal parts of a sample (e.g., data sample), where n > 1.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

quantitative trading: systematic trading strategies based on quantitative analysis and mathematical computations with little to no human intervention outside of developing a strategy (which includes coding it up in a suitable computer language).

quark spread: the analog of the spark spread and the dark spread for nuclear power plants.

quintile: each of the 5 (approximately) equal parts of a sample (e.g., data sample).

R: R Package for Statistical Computing.

R-squared: in a regression, 1 minus a ratio, whose numerator is the sum of squares of the residuals, and whose denominator is the sum of squares of the deviations of the values of the observable variable from their mean value across the data sample.

rally: in financial markets, a period of sustained gains.

rank (for matrices): the maximum number of linearly independent columns of a matrix.

rank (a.k.a. ranking): the position of an element of a set after sorting it according to some criterion (with a prescription for resolving possible ties).

rate: see interest rate, inflation.

rating: see credit rating.

ratio spread: a type of options strategies.

real estate: tangible immovable assets including land, structures built on it, etc.

real estate investment trust (REIT): a company (often traded on major exchanges and thus allowing investors to take a liquid stake in real estate) that owns, operates or finances income-producing real estate.

real interest rate: interest rate adjusted for inflation.

realized P&L: the P&L on a completed trade, i.e., the P&L resulting from establishing a position and then completely liquidating it.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

realized profit: see realized P&L.

realized return: historical return.

realized volatility: historical volatility.

rebalancing: changing the holding weights in a portfolio.

recovery rate: the percentage of the principal and accrued interest on defaulted debt that can be recovered.

rectified linear unit (ReLU): the function of x given by max(x, 0).

reference entities: in a CDS, bonds, loans, names of companies or countries, etc., on which default protection is provided.

regression: see linear regression.

regression coefficient: the slope of an independent variable in a linear regression.

regression residuals: the differences between the observed values and the fitted (model predicted) values of the dependent variable in a linear regression.

regression-weighted butterfly: a type of bond butterfly portfolio.

regression weights: the positive weights wi (which need not equal 1) in the sum of squares $\textstyle \sum _ { i = 1 } ^ { N } w _ { i } \epsilon _ { i } ^ { 2 }$ , whose minimization determines the regression coefficients and regression residuals i.

reinvestment risk: the risk that the proceeds (from the coupon payments and/or principal of a bond or similar instrument) would be reinvested at a lower rate than the original investment.

relative momentum: cross-sectional momentum.

relative strength index (RSI): during a specified timeframe, the average gain of the up periods divided by the sum of the average gain of the up periods and the absolute value of the average loss of the down periods.

relative value strategy: a strategy that aims to exploit differences in the prices, returns or rates (e.g., interest rates) of related (by some criterion) securities (e.g., historically correlated stock pairs in pairs trading).

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

reorganization: a Court-supervised process of restructuring a company’s finances in bankruptcy.

reorganization plan: a plan for reorganization of a company in bankruptcy that can be submitted (e.g., by a creditor with the view of obtaining participation in the management of the company) to Court for approval.

replication: a strategy whereby a dynamic portfolio of assets precisely replicates cash flows of another asset or portfolio.

repurchase agreement (a.k.a. REPO or repo): a cash-equivalent asset that provides immediate liquidity at a preset interest rate for a specific period of time in exchange for another asset used as a collateral.

resistance: in technical analysis, the (perceived) price level at which a rising stock price is expected to bounce back down.

retail trader: a non-professional individual trader.

reverse repurchase agreement: a REPO from the standpoint of the lender.

rich stock: a stock that is perceived to be overvalued by some criterion.

risk: the possibility that the realized return will differ from the expected return.

risk-adjusted return: return divided by volatility.

risk arbitrage: see merger arbitrage.

risk factor: see factor.

risk-free arbitrage: making profit without any risk.

risk-free asset (a.k.a. riskless asset): an asset with a certain future return, e.g., Treasury bills.

risk-free discount factor: a discount factor that uses a risk-free rate for discounting future cash flows.

risk-free probability measure (a.k.a. risk-neutral measure): a theoretical probability measure under which an asset’s current price equals its future

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

expected value discounted by a risk-free rate.

risk-free rate: the rate of return of a risk-free asset, often taken to be the one-month Treasury bill rate.

risk management: identifying, analyzing and mitigating potential risks.

risk model: a mathematical model for estimating risk (e.g., modeling a covariance matrix).

risk premia (same as risk premiums): plural of risk premium.

risk premium: the (expected) return in excess of the risk-free rate from an investment.

risk reversal (a.k.a. combo): a type of options strategies.

risk sentiment: investor risk tolerance in response to global economic patterns, whereby when risk is perceived as low (high), investors tend to engage in higher-risk (lower-risk) investments (a.k.a. “risk-on risk-off”).

risky duration: a weighted sum (over the payment dates) of the (discounted) differences between the notional (of a CDO tranche or similar) and expected loss for each such date, where each weight is the time from the previous payment date.

roll: in futures contracts, rebalancing futures positions, whereby when the current long (short) futures contract is about to expire, it is sold (covered) and another futures contract with longer expiration is bought (sold).

roll loss (a.k.a. contango loss): in ETNs such as VXX and VXZ consisting of VIX futures portfolios, a decay in their values (when the VIX futures curve is in contango) due to their daily rebalancing required to maintain a constant maturity.

roll value: see daily roll value.

roll yield: in commodity futures, positive returns from the roll generated by long (short) positions when the term structure is in backwardation (contango).

rolling down the yield curve (a.k.a. rolling down the curve): a trading strategy that amounts to buying long- or medium-term bonds from the steepest segment of the yield curve (assuming it is upward-sloping) and selling them as they approach maturity.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

root mean square error (RMSE): the square root of the mean value of the squares of the differences between the predicted and observed values of a variable.

rotation: see alpha rotation, sector momentum rotation.

rung: in a bond ladder portfolio, the bonds of the same maturity.

Russell 3000: a market cap weighted index of the 3,000 largest U.S.-traded stocks by market cap.

S&P 500: a market cap weighted index of the 500 largest U.S. publicly traded companies by market cap.

sample correlation matrix: a correlation matrix for a set of securities computed based on the time series of their historical returns.

sample covariance matrix: a covariance matrix for a set of securities computed based on the time series of their historical returns.

sample variance: a variance computed based on the time series of a security’s historical returns.

scale invariance: a function f (xi) of N variables $x _ { i } \ ( i = 1 , \ldots , N )$ is scale invariant if $f ( \zeta x _ { i } ) = f ( x _ { i } )$ for an arbitrary scale factor ζ taking values in a continuous interval (e.g., positive real values).

seagull spread: a type of options strategies.

second-month futures: a futures contract with the nearest expiration after the front-month futures.

sector (in economy): an area of the economy in which businesses share similar products or services.

sector (in industry classification): usually, the least granular level in a multilevel industry classification (e.g., sectors are split into industries, industries are split into sub-industries).

sector momentum rotation: a type of momentum strategy for ETFs.

secured loan: a loan secured with a collateral.

security: in finance, usually a fungible, negotiable financial instrument with

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

monetary value.

selectivity: a quantitative measure of active management of mutual funds (as well as actively-managed ETFs).

sell-write strategy: shorting stock and writing (selling) a put option against the stock position.

senior mezzanine tranche: the next (by increasing quality) tranche of a CDO after the junior mezzanine tranche.

senior tranche: the next (by increasing quality) tranche of a CDO after the senior mezzanine tranche.

sentiment analysis (a.k.a. opinion mining): the use of natural language processing and other computational techniques to extract information from (electronic) documents (e.g., tweets) pertinent to a security, e.g., for forecasting the direction of its price movements.

sentiment data: the textual data used in sentiment analysis (e.g., the contents of tweets).

Separate Trading of Registered Interest and Principal of Securities (a.k.a.   
STRIPS): zero-coupon Treasury securities.

serial correlation: a pair-wise correlation between two securities computed based on their time series of historical returns.

serial quantity: a quantity (e.g., mean, standard deviation, etc.) computed serially (i.e., across the time series for each security) as opposed to cross-sectionally (i.e., across a set of securities).

serial regression: a regression where the independent variables are time series (cf. cross-sectional regression).

settlement: the fulfillment of the obligations under a futures or forward contract at expiration.

share: a unit of ownership interest in a corporation or financial asset.

shareholder (a.k.a. stockholder): an owner of shares in a company.

shares outstanding: the total number of a company’s shares held by all its

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

shareholders.

Sharpe ratio: (excess) return divided by volatility.

short position (a.k.a. short): selling an asset without owning it by borrowing it from someone else, typically, a brokerage firm.

short-sale (a.k.a. short-selling, or shorting): establishing a short position.

sideways market: when prices remain in a tight range, without clear up or down trends.

sideways strategy: a trading strategy that aims to capitalize on an expected low volatility environment, e.g., by selling volatility.

sigmoid: the function of x given by 1/(1 + exp(−x)).

signal: a trading signal, e.g., to buy (buy signal) or sell (sell signal) a security.

simple moving average (SMA): a moving average without suppressing past contributions (cf. exponential moving average).

simple moving standard deviation: a moving standard deviation without suppressing past contributions (cf. exponential moving standard deviation).

single-name CDS: a CDS on a single reference entity.

single-stock option: an option on a single underlying stock (as opposed to, e.g., an option on a portfolio of stocks such as an index).

single-stock strategy: a trading strategy that derives a trading signal for any given stock using data for only that stock and no other stocks.

skewness: a measure of asymmetry in a probability distribution, defined as the mean value of the cubic power of the deviation from the mean divided by the cubic power of the standard deviation.

skewness premium: in commodity futures, an empirical occurrence whereby future expected returns tend to be negatively correlated with the skewness of historical returns.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

skip period: in price-momentum and similar strategies, the period (usually, the last 1 month) skipped before the formation period (usually the last 12 months prior to the skip period).

slippage: the difference between the price at which an (initial) order is placed (or expected/hoped to be executed) and at which it is filled (including after cancelreplacing the initial order when chasing the bid or ask with buy or sell limit orders, respectively), sometimes averaged over multiple orders (e.g., when a large order is broken up into smaller ones).

smart order flow (a.k.a. toxic order flow): order flow based on some predictive expected return.

SMB (a.k.a. Small minus Big): see Fama-French factors.

social media sentiment: the sentiment on stocks or other securities extracted from social media posts or messages (e.g., on Twitter).

softmax: the function $\textstyle \exp ( x _ { i } ) / \sum _ { j = 1 } ^ { N } \exp ( x _ { j } )$ of an N -vector $x _ { i } \ ( i = 1 , \ldots , N )$

sorting: organizing a set in an ascending or descending order based on some quantity (with a prescription for resolving possible ties).

source code (a.k.a. code): computer code written in some computer programming language.

sovereign risk: the risk that a government could default on its debt (sovereign debt, e.g., government-issued bonds) or other obligations, or that changes in a central bank’s policy may adversely affect FX contracts.

spark spread: the difference between the wholesale price of electricity and the price of natural gas required to produce it.

SPDR Trust (ticker SPY): an S&P 500 tracking EFT.

specialist system: a (largely) human-controlled and operated market-making system at NYSE prior to switching to (mostly) electronic trading.

specific risk (a.k.a. idiosyncratic risk): see non-systematic risk.

speculative asset: an asset with little to no intrinsic value.

speculative bubble: see bubble.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

speculator: a market participant attempting to profit from a security’s price movement (cf. hedger).

spike: a relatively large upward or downward movement of a security’s price in a short period of time.

split (a.k.a. stock split): a corporate action in which a company divides its existing shares into multiple shares (forward stock split) or combines multiple shares into one (reverse stock split).

spot (a.k.a. spot price, or spot value): the current price of an asset.

spot FX rate (a.k.a. FX spot rate, or spot rate): the current FX rate.

spread: the difference between two quantities, or a portfolio consisting of two (or more) legs comprised of the same type of assets different only by one or more specific quantities (e.g., strike price, or strike price and expiration).

standard deviation: the square root of the variance.

standardized unexpected earnings (SUE): a ratio, whose numerator (unexpected earnings) is the difference between the most recently announced quarterly earnings per share and those announced 4 quarters ago, and whose denominator is the standard deviation of the unexpected earnings over the last 8 quarters.

state variable: one of a set of variables (which may or may not be observable) used to describe a dynamical system.

statistical arbitrage (a.k.a. Stat Arb, or StatArb): typically, shorterhorizon trading strategies with sizable trading universes (e.g., a few thousand stocks) based on complex cross-sectional (and serial) statistical mean-reversion signals.

statistical industry classification: a multilevel clustering of companies based on purely statistical techniques, e.g., distance-based clustering of the companies’ returns (cf. fundamental industry classification).

statistical risk model: a risk model built using only the pricing data (e.g., using principal components of the sample correlation matrix of stock returns), without any reference to fundamental data (including any fundamental industry classification).

steepener: a yield curve spread bond strategy.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

stemming: reducing a word to its base form, the part of a word that is common to all its inflected variants.

stemming algorithm: see Porter stemming algorithm.

stochastic dynamics: see stochastic process.

stochastic gradient descent (SGD): an iterative method for optimizing a differentiable objective function.

stochastic process: a collection of random variables that change with time.

stock: a security representing fractional ownership in a corporation.

stock merger: a merger where each share of the target company is swapped for some number (which can be fractional) of the acquirer company’s shares.

stop-loss price: the price of an asset at which a position in said asset is (automatically) liquidated.

stop-word: the most commonly used words in a language (e.g., “the”, “is”, “in”, “which”, etc.) that add no value in a particular context and are ignored by a natural language processing tool.

straddle: an option trading strategy.

strangle: an option trading strategy.

strap: an option trading strategy.

strategy: see trading strategy.

strike price (a.k.a. strike): the price at which a derivative contract can be exercised.

strip: an option trading strategy.

structured asset: a complexly structured (debt) instrument such as a CDO or ABS.

style risk factor (a.k.a. style factor): risk factors such as value, growth, size, momentum, liquidity and volatility.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

sub-industry (in industry classification): usually, a subgroup of companies within the same industry grouped together based on a more granular criterion.

super senior tranche: the highest quality tranche of a CDO.

support: in technical analysis, the (perceived) price level at which a falling stock price is expected to bounce back up.

support and resistance strategy: a technical analysis strategy based on support and resistance.

support vector machine (SVM): in machine learning, a type of supervised learning models.

swap (a.k.a. swap agreement, or swap contract): a derivative contract through which two parties exchange financial instruments.

swap spread: the difference between the fixed rate of an interest rate swap and the yield on a Treasury security with a similar maturity.

swap-spread arbitrage: a dollar-neutral strategy consisting of a long (short) position in an interest rate swap and a short (long) position in a Treasury bond with the same maturity as the swap.

synthetic security (a.k.a. synthetic): a financial instrument created (via a portfolio of assets) to replicate (or approximately reproduce) the same cash flows as another security (e.g., synthetic put, call, straddle, forward, futures, etc.).

systematic approach: methodical, rules-based trading strategies with welldefined trade goals and risk controls (as opposed to, e.g., analysts’ subjective opinions).

systematic macro: non-discretionary, systematic macro trading strategies.

systematic risk: non-diversifiable risk inherent to the entire market or its segment, such as exposure to broad market movements, which cannot be diversified away in long-only portfolios, but can nonetheless be substantially reduced or even essentially eliminated in long-short (e.g., dollar-neutral) portfolios.

tactical asset allocation: a dynamic investment strategy that actively adjusts a portfolio’s asset allocation weights.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

tanh: hyperbolic tangent.

target company: the company chosen by the acquirer company for a potential corporate merger or acquisition.

target variable: in machine learning, the variable whose values are to be modeled and predicted.

tax arbitrage: profiting from differences in how income, capital gains, transactions, etc., are taxed.

tax credit: see dividend imputation.

tax-exempt municipal bonds: e.g., municipal bonds that are not subject to Federal income taxes (on the interest earned) in the U.S.

tax shield: the reduction in income taxes that results from taking an allowable deduction from taxable income.

technical analysis: a methodology for forecasting the direction of prices using historical market data, primarily price and volume (cf. fundamental analysis).

technical indicator: a mathematical quantity used in technical analysis.

tercile: each of the 3 (approximately) equal parts of a sample (e.g., data sample).

term spread: an interest rate spread corresponding to two different maturities.

term structure (in futures): the dependence of futures prices on time to maturity.

term structure (in interest rates): see yield curve.

Theta: the first derivative of the value of a derivative asset (e.g., option) w.r.t.   
time.

Theta-decay: the time decay of an option’s (or other asset’s) value as time nears the expiration.

ticker (a.k.a. ticker symbol): a short character string representing a particular publicly traded security.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

time series: a series of data points indexed in time order, i.e., labeled by time values.

time-to-maturity (TTM): time left before an option expires.

TIPS-Treasury arbitrage: a trading strategy consisting of selling a T-bond and offsetting the short position by a lower-cost replicating portfolio consisting of TIPS, inflation swaps and STRIPS.

Treasury Inflation-Protected Securities (TIPS): Treasury securities that pay semiannual fixed coupons at a fixed rate, but the coupon payments (and principal) are adjusted based on inflation.

tracking error: the square root of the variance of the differences between the returns of a portfolio and those of the benchmark or index said portfolio is meant to mimic or beat.

tracking ETF: an ETF that tracks an index.

trader: a person who buys and sells goods, currency, stocks, commodities, etc.

trading bounds: upper or lower bounds on the dollar amounts of allowed trades for various assets in a portfolio, when establishing, rebalancing or liquidating.

trading on economic announcements: a trading strategy that buys stocks on important announcement days, such as FOMC announcements, while holding risk-free assets on other days.

trading costs (a.k.a. transaction costs): costs associated with trading securities, including (as applicable) exchange fees, brokerage fees, SEC fees, slippage, etc.

trading days: usually, the days on which NYSE is open.

trading rule: a set of buy and sell instructions, with the quantities of the assets to be bought or sold.

trading signal: see signal.

trading strategy: a set of instructions to achieve certain asset holdings by some predefined times t1, t2, . . . , which holdings can (but need not) be null at one or more of these times.

trading universe (a.k.a. universe): the tickers of stocks (or other securi-

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

ties) in a trading portfolio.

traditional assets: stocks, bonds, cash, real estate and, in some cases, also currencies and commodities.

training: in machine learning, fixing free parameters in an algorithm using training data.

training data (a.k.a. training dataset): in machine learning, a set of inputoutput pairs known in advance, which are used to train a machine learning algorithm.

training period: in machine learning, the period spanned by the training data when it is a time series.

tranche: see CDO tranche.

Treasuries: Treasury securities.

Treasury: the U.S. Department of Treasury.

Treasury bill (a.k.a. T-bill): a short-term debt obligation issued by the U.S. Treasury with maturity under 1 year.

Treasury bond (a.k.a. T-bond): a bond issued by the U.S. Treasury with maturity of more than 10 years.

Treasury curve: the yield curve of Treasury securities.

Treasury ETF: a tracking ETF for an index composed of U.S. government debt obligations.

Treasury note (a.k.a. T-note): a debt security issued by the U.S. Treasury with maturity between 1 and 10 years.

tree boosting: a machine learning technique.

trend: the general direction of a market or asset’s price, essentially, momentum.

trend following: a trading strategy that aims to capture gains from an asset’s momentum in a particular direction.

triangular arbitrage: see FX triangular arbitrage.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Twitter sentiment: the sentiment on stocks or other securities extracted from tweets.

U.S. regions: East, Mid-West, South and West.

unadjusted quantity: price or volume unadjusted for splits or dividends.

uncompounded rate: an interest rate applied to the principal during some period without any compounding.

underlying: underlying instrument (e.g., stock in a single-stock option).

underreaction: in financial markets, an insufficient response to news, as some market participants tend to be conservative and rely too much on their prior beliefs.

unexpected earnings: see standardized unexpected earnings.

value: a factor based on the book-to-price (B/P) ratio.

value strategy: buying high value (high B/P ratio) stocks and selling low value (low B/P ratio) stocks.

variable coupon bond: see floating coupon bond.

variable rate: see floating interest rate.

variance: a mean value of the squares of the deviations of the values of a quantity from their mean value.

variance swap: a derivative contract whose payoff at maturity is a product of a preset coefficient (variance notional) times the difference between the realized variance at maturity of the underlying and the preset variance strike.

Vega: the first derivative of the value of a derivative asset (e.g., option) w.r.t.   
the implied volatility of the underlying asset.

vertical spread: an option strategy that involves all identical put or all identical call options with the exception of their strike prices.

volatility: a statistical measure of the dispersion of returns for a security or market index, which is expressed via the standard deviation or variance of said returns.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

VIX: CBOE Volatility Index, a.k.a. the “uncertainty index” or the “fear gauge index”.

volatility carry strategy: a trading strategy consisting of shorting VXX and offsetting the short position with long VXZ (see volatility ETN), generally with a non-unit hedge ratio.

volatility ETN: an ETN that tracks VIX, e.g., VXX or VXZ.

volatility index: an index (e.g., VIX) that measures the market’s expectation of future (30-day for VIX) volatility based on implied volatilities of the underlying instruments (the S&P 500 stocks for VIX).

volatility risk premium: an empirical occurrence that implied volatility tends to be higher than realized volatility most of the time.

volatility skew: an empirical occurrence whereby, with all else being equal, the implied volatility for put options is higher than for call options.

volatility strategy: a trading strategy that aims to capitalize on an expected high volatility environment, e.g., by buying volatility.

volatility targeting strategy: a trading strategy that aims to maintain a constant volatility level (volatility target, or target volatility) by rebalancing between a risky asset and a risk-free asset.

volume: the number of shares or contracts traded in a security during some period.

watt: a unit of power in the International System of Units (SI).

weather derivative: a derivative (e.g., option or futures) on a synthetic weather index.

weather index: a synthetic index usually based on temperature, using, e.g., cooling-degree-days (CDD) and heating-degree-days (HDD).

weather risk: a risk stemming from businesses and sectors of the economy being affected by weather conditions.

weighted average: for N values $x _ { i } ( i = 1 , \ldots , N )$ , the weighted mean given by $\textstyle { \frac { 1 } { N } } \sum _ { i = 1 } ^ { \bar { N } } w _ { i } \ x _ { i } .$ , where wi are the weights.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

weighted regression: a linear regression with nonuniform regression weights.

weighting scheme: assigning portfolio weights according to some rule, e.g., by suppressing contributions of volatile stocks.

weights (in ANN): in an artificial neural network, the coefficients of the inputs in the argument of an activation function.

weights (in portfolios): see portfolio weights.

Whittaker-Henderson method: see Hodrick-Prescott filter.

wing: one of the 2 peripheral (by maturity in bond portfolios, and by strike price in option portfolios) legs of a butterfly portfolio.

winners: stocks or other assets in a portfolio or trading universe that outperform based on some criterion (benchmark).

word (a.k.a. keyword): a keyword in a learning vocabulary.

year-on-year (YoY) inflation: annual inflation (cf. cumulative inflation).

year-on-year inflation swap: an inflation swap that references annual inflation (cf. zero-coupon swap).

yield: see bond yield.

yield curve (a.k.a. term structure): the dependence of interest rates or bond yields on maturities.

yield curve spread: the spread between shorter and longer maturity bonds on the yield curve.

yield curve spread strategy: a bond strategy that makes a bet on the yield curve spread (flattener or steepener).

zero-cost strategy: a dollar-neutral strategy.

zero-coupon bond: see discount bond.

zero-coupon inflation swap: an inflation swap that has only one cash flow at maturity and references the cumulative inflation over the life of the swap (cf. year-on-year inflation swap).

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## Acronyms

ABS: asset-backed security.

ADDV: average daily dollar volume.

ANN: artificial neural network.

ATM: at-the-money.

B/P: book-to-price.

BA: banker’s acceptance.

BICS: Bloomberg Industry Classification System.

bps: basis point.

BTC: Bitcoin.

Btu: British thermal unit.

CA: commodity allocation percentage.

CBOE: Chicago Board Options Exchange.

CD: certificate of deposit.

CDD: cooling-degree-days.

CDO: collateralized debt obligation.

CDS: credit default swap.

CFTC: U.S. Commodity Futures Trading Commission.

CI: core inflation.

CIRP: Covered Interest Rate Parity.

CME: Chicago Mercantile Exchange.

COT: Commitments of Traders.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

CPI: Consumer Price Index.

CPS: cents-per-share.

CTA: commodity trading advisor.

DJIA: Dow Jones Industrial Average.

EMA: exponential moving average.

EMSD: exponential moving standard deviation.

ETF: exchange-traded fund.

ETH: Ethereum.

ETN: exchange-traded note.

EUR: euro.

FOMC: Federal Open Market Committee.

FX: foreign exchange.

GDP: Gross Domestic Product.

GICS: Global Industry Classification Standard.

HDD: heating-degree-days.

HFT: high frequency trading.

HI: headline inflation.

HMD: healthy-minus-distressed.

HML: High minus Low.

HP: hedging pressure; Hodrick-Prescott.

IBS: internal bar strength.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

ITM: in-the-money.

JPY: Japanese Yen.

LETF: leveraged (inverse) ETF.

LIBOR: London Interbank Offer Rate.

M&A: mergers and acquisitions.

MA: moving average.

ML: machine learning.

MBS: mortgage-backed security.

MBtu: 1,000 Btu.

MKT: market (excess) return.

MMBtu: 1,000,000 Btu.

MOM: Carhart’s momentum factor.

MSA: metropolitan statistical area.

MTM: mark-to-market.

Mwh: Megawatt hour.

NYSE: New York Stock Exchange.

OAS: option adjusted spread.

OTM: out-of-the-money.

P&L: profit(s) and loss(es).

P2P: peer-to-peer.

PCA: principal component analysis.

REIT: real estate investment trust.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

ReLU: rectified linear unit.

REPO/repo: repurchase agreement.

RMSE: root mean square error.

RSI: relative strength index.

S&P: Standard and Poor’s.

SIC: Standard Industrial Classification.

SMA: simple moving average.

SMB: Small minus Big.

SGD: stochastic gradient descent.

SS: sum of squares.

StatArb: statistical arbitrage.

STRIPS: Separate Trading of Registered Interest and Principal of Securities.

SUE: standardized unexpected earnings.

SVM: support vector machine.

TTM: time-to-maturity.

TIPS: Treasury Inflation-Protected Securities.

UIRP: Uncovered Interest Rate Parity.

USD: U.S. dollar.

VAR: vector autoregressive model.

VWAP: volume-weighted average price.

YoY: year-on-year.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

## Some Math Notations

iff if and only if.

max (min) maximum (minimum).

floor(x) the largest integer less than or equal x.

ceiling(x) the smallest integer greater than or equal x.

(x)+ max(x, 0).

sign(x) sign of x, defined as: +1 if x > 0; −1 if x < 0; 0 if x = 0.

|x| absolute value of x if x is a real number.

rank(xi) rank of $x _ { i }$ when N values $x _ { i } \ ( i = 1 , \ldots , N )$ are sorted in the ascending order.

exp(x) or ex natural exponent of x.

ln(x) natural log of x.

$\textstyle \sum _ { i = 1 } ^ { N } x _ { i }$ sum of N values $x _ { i } \ ( i = 1 , \ldots , N )$

$\textstyle \prod _ { i = 1 } ^ { N } x _ { i }$ product of N values $x _ { i } \ ( i = 1 , \ldots , N )$

$A | _ { B = b } \ \left( \operatorname { o r } \ A | _ { b } \right)$ the value of A when some quantity B it implicitly depends on (usually evident from the context) takes value b.

f (x) → min (max) minimizing (maximizing) f (x) w.r.t. x (where x can, e.g., be an N -vector xi, i = 1, . . . , N ).

argmax z f(z) the value of z for which f (z) is maximized.

∂f/∂x the first partial derivative of the function f (which may depend on variables other than x) w.r.t. x.

$\partial ^ { 2 } f / \partial x ^ { 2 }$ the second partial derivative of the function f (which may depend on variables other than x) w.r.t. x.

G : A 7→ B G is a map from set A to set B.

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

A ⊂ B set A is a subset of set B.

$\{ i | f ( i ) = a \}$ the set of values of i such that the condition f (i) = a is satisfied.

min $( i : f ( i ) > a )$ the minimum value of i such that the condition $f ( i ) > a$ is satisfied.

i ∈ J i is an element of set J.

|J | the number of elements of J if J is a finite set.

δAB (or δA,B) 1 if A = B; otherwise, 0 (Kronecker delta).

diag(xi) diagonal N × N matrix with $x _ { i } \ ( i = 1 , \ldots , N )$ on its diagonal.

AT transpose of matrix A.

A−1 inverse of matrix A.

Et(A) expected value of A at time t.

dX(t) an infinitesimal increment of a continuous process X(t).

dt an infinitesimal increment of time t.

P (A|B) conditional probability of A occurring assuming B is true.

## Explanatory Comments for Index

In the index entries, plural in many (but not all) cases is reduced to singular (so, e.g., “commodity” also includes “commodities”). Parentheses contain acronyms or definitions, and in some (but not all) cases both versions are present in the main text. Most (but not all) index entries with commas, i.e., “noun, adjective”, correspond to text entries such that the precise string “adjective noun” is not directly present in the text, but is present indirectly (e.g., as “adjective (...) noun”) or contextually.

## Index

absolute momentum, 62   
academic alpha, 59   
acquirer company, 52   
acquisition, 125   
activation function, 119   
active approach, 90   
active distressed investing, 109   
active investing, 109   
active management, 64   
actively managed ETF, 64   
adjusted close price, 127   
adjusted open price, 127   
adjusted price, 127   
adjustment factor, 127   
adverse selection, 58   
aggressive order, 58   
aggressive order flow, 58   
allocation weight, 80   
alpha, 59, 63, 64   
alpha combo, 59   
alpha combo strategy, 59   
alpha portfolio weights, 60   
alpha return, 60   
alpha rotation, 63   
alpha rotation strategy, 64   
alpha weights, 60   
alternative real estate vehicles, 113   
American option, 17   
American put option, 104   
announcement days, 123   
annual inflation, 105   
annualization factor, 84   
annualized return, 129   
annualized Sharpe ratio, 129   
anomaly, forward discount, 86   
appraised value, 115   
arbitrage, 106   
arbitrage trade, 77   
artificial neural network (ANN), 116–119   
Asian option, 17   
ask, 58, 89   
ask price, 80   
asset, 42   
asset class, 15, 16, 65, 80, 119, 121, 122,   
124   
asset-backed security (ABS), 97   
ATM option, 78   
ATM straddle, 83   
attachment, 98   
attachment point, 97   
average daily dollar volume (ADDV), 125,   
126   
average underlying price, 17   
B/P ratio, 42   
back leg, 75   
backspread, 30, 31   
backtest, 16, 55, 128, 129   
backtesting, 125, 128   
backtesting period, 129   
backwardation, 81, 89, 90   
bank deposit certificate (CD), 114   
banker’s acceptance, 114   
bankruptcy, 108–110, 125   
bankruptcy probability, 110   
bankruptcy protection, 109   
bankruptcy-filing month, 109   
barbell, 69, 70   
barbell portfolio, 70, 71   
barbell strategy, 69   
barrier option, 17   
base form, 120   
basis point (bps), 109, 126   
basis risk, 93   
basket, 82, 88, 97, 123   
Bayes’ theorem, 120   
bearish strategy, 18, 23   
Bermudan option, 17   
Bernoulli probability distribution, 120   
bias, 119

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

bid, 58, 89   
bid price, 80   
bid-ask spread, 58   
binary industry classification, 61, 128   
bisection method, 102   
Bitcoin (BTC), 116, 119–121   
Bitcoin trading, 121   
black-box machine learning techniques,   
92   
Black-Scholes model, 92   
blockchain, 116   
blockchain technology, 116   
Bloomberg Industry Classification System   
(BICS), 128   
body, 72   
bond, 15, 17, 66–71, 73–76, 94, 97, 98,   
100–102, 111, 112, 121–123   
bond credit rating, 73   
bond immunization, 70, 71   
bond maturity, 73   
bond portfolio, 70   
bond price, 66, 68, 69   
bond spread, 75, 76   
bond value, 74   
bond yield, 73–75, 94   
bond yield spread, 75   
bond, deliverable, 94   
bond, non-deliverable, 94   
bond, Treasury, 105   
book value, 42   
book-to-market ratio, 42   
book-to-price (B/P) ratio, 42   
Boolean, 125   
bounds, position, 57   
bounds, trading, 57   
box, 37   
box option strategies, 37   
break-even point, 26   
break-even price, 18   
breakeven rate, 105   
broad index, 76   
broad market, 62, 97   
broad market index, 63   
broad market index ETF, 62, 63   
brownfield project, 124   
Brownian motion, 91, 92   
BTC price, 117, 120   
Btu (British thermal unit), 108   
bullet, 69, 70   
bullet portfolio, 69, 71   
bullet strategy, 69   
bullish strategy, 18, 23   
business cycle, 122   
business cycle trends, 122   
butterfly, 32, 33, 35, 36, 72   
butterfly bond strategy, 72   
butterfly spread, 32   
butterfly strategy, 32, 33   
buy signal, 86, 92, 119   
buy-and-hold investment, 124   
buy-write strategy, 18

calendar call spread, 24, 25

calendar put spread, 24–26

calendar spread, 94

call option, 17–39, 84, 102, 107

call spread, 19, 20, 22, 23, 34, 36, 37

call, naked, 19

call, short, 19

Canary option, 17

capital allocation, 70

capital allocation weights, 95

capital gain strategy, 20–22, 26–32, 34– 39

Carhart’s momentum factor (MOM), 63

carry, 74, 77, 99, 100

carry factor, 74

carry strategy, 74, 86–88

carry trade, 86

cash, 15, 77, 114, 115

cash flow, 67, 68, 100, 102, 105, 106, 111, 124

cash flow shortfall, 115

cash merger, 52

cash-and-carry arbitrage, 77

cash-equivalent asset, 115

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

CDO notional, 98 commodity futures, 15, 89–91, 94, 115   
CDO tranche, 97, 98 commodity futures term structure, 91   
CDO tranche hedging, 99 commodity investment, 90   
CDS arbitrage trade, 76 commodity market, 90   
CDS basis, 75 commodity price, 122   
CDS basis arbitrage, 75 commodity return, 90   
CDS hedging, 100 common stock, 17   
CDS index, 98, 99 compounding period, 71, 86, 106   
CDS price, 75 computation, out-of-sample, 127   
CDS spread, 75, 76 conditional expectation, 92   
cents-per-share, 58, 129 conditional independence assumption, 121   
channel, 52, 60 conditional probability, 120, 121   
channel break, 52 condor, 34, 35   
channel indicator, 52 condor strategy, 32   
channel trading strategy, 52 constrained regression, 101   
Chapter 11, 109, 110 constraints, inhomogeneous, 57   
cheap stock, 45 constraints, nonlinear, 57   
Chicago Board Options Exchange Consumer Price Index (CPI), 105, 106,   
(CBOE), 80 122   
claim, 17 contango, 81, 82, 89, 90   
claim pricing argument, 92 continuous compounding, 66, 68, 69   
class, 120, 121 contrarian trading, 95   
close, 60, 82, 125 control rights, 110   
close price, 126 conversion factor, 94   
close-to-close return, 79 conversion factor model, 94   
close-to-open return, 127 conversion option, 101, 102   
closing price, 51, 65, 128 conversion price, 101   
cluster, 46–48 conversion ratio, 101   
clustering algorithm, 61 convertible arbitrage, 101   
Cochrane-Piazzesi predictor, 123 convertible arbitrage strategy, 101   
collar, 37 convertible bond, 15, 101, 102   
collar strategy, 37 convertible bond pricing, 102   
collateral, 115, 116 convertible option-adjusted spread, 102   
collateralized debt obligation (CDO), 15, convertibles, 101   
97, 98, 100 convexity, 68–71, 100   
combo, 21, 22, 38, 39 cooling-degree-days (CDD), 107   
combo strategy, 22 core inflation (CI), 122, 123   
commercial paper, 114 corporate actions, 52   
commercial real estate, 113 correlation, 65, 78, 79, 90, 91, 96, 111,   
Commitments of Traders (COT), 90 112, 116   
commodity, 15, 17, 89–91, 121–123 correlation matrix, 79   
commodity allocation percentage (CA), correlation trading, 78   
123 correlation, implied, 78

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

correlation, serial, 88

counterparty, 115

coupon, 66, 70, 94

coupon bond, 66, 74

coupon payment, 66, 67, 70, 105, 106

coupon payment, fixed rate, 76

coupon rate, 66, 106

covariance matrix, 44, 65, 96

covariance matrix, sample, 55

covered call, 18, 29, 37

covered call option strategy, 19

covered call strategy, 18, 24

covered interest arbitrage, 87

Covered Interest Rate Parity (CIRP), 86, 87

covered put, 18, 37

covered put option strategy, 19

covered put strategy, 19, 25

covered short straddle, 29

covered short strangle, 29

covered straddle, 26

credit default swap (CDS), 75, 76, 97, 98, 100

credit derivatives, 98

credit rating, 73, 97

credit spread, 73

cross-border tax arbitrage, 103, 104

cross-entropy, 119

cross-hedging, 93

cross-sectional analysis, 59, 123

cross-sectional standard deviation, 96

cross-sectional strategy, 54

cross-sectional trade, 87

cross-validation, 54

cryptoassets, 116

cryptocurrency, 15, 116, 119

cryptography, 116

cryptocurrency trading, 120, 121

cryptocurrency trading strategy, 116

cum-dividend, 103, 104

cumulative ETF return, 63

CTA (commodity trading advisor), 122

cumulative inflation, 105

cumulative return, 40, 53, 62, 65, 96, 97   
currency, 15, 17, 86–89, 121, 122   
currency carry trade, 87   
currency pair, 89   
curvature, 72   
curve trade, 100   
curve-neutrality, 72   
daily roll value, 81   
dark spread, 108   
data mining, 16   
data, cross-sectional, 60   
data, economic, 61   
data, fundamental, 53, 61   
data, single-stock, 60   
data, technical, 53   
debt seniority level, 109   
decentralized digital currency, 116   
decile, 40, 42–45, 62, 64, 65, 73, 74, 87,   
110, 122   
default, 75, 98, 108, 109   
default month, 109   
default payment, 98   
default risk, 97   
defaulted credit, 98   
deferred-month contracts, 94   
deferred-month futures, 94   
delay, 128   
delay-0 strategy, 128   
delay-1 strategy, 128   
delivery, 77, 93   
delivery date, 92   
delivery month, 94   
delivery price, 21   
delivery time, 77   
Delta, 83, 99, 102   
Delta-hedging, 84   
Delta-hedging strategy, 84   
demand, 94, 107   
demand hedging, 106   
demand risk, 107   
demeaned rank, 44   
demeaned return, 46–49, 97

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

derivative, 15, 81, 121   
derivative contract, 84   
desired holdings, 59, 128, 129   
detachment, 98   
detachment point, 97   
diagonal call spread, 25   
diagonal put spread, 25   
diagonal spread, 25   
directional exposure, 84   
directional strategy, 18, 84, 122   
discount bond, 66   
discount factor, 106   
discount rate, 76   
discretionary macro, 122   
discretionary strategy, 122   
dispersion strategy, 78, 85   
dispersion trading, 77, 78   
dispersion trading strategy, 79   
distress risk puzzle, 110   
distress risk puzzle strategy, 110   
distress situation, 109, 110   
distress, financial, 108   
distress, operational, 108   
distressed asset, 15, 108, 109   
distressed company, 109   
distressed debt, 108, 109   
distressed debt market, 109   
distressed debt passive trading strategy,   
109   
distressed debt portfolio, diversified, 109   
distressed firm, 109, 110   
distressed security, 108   
distributed ledger, 116   
diversification, 111–113, 124   
diversification power, 65   
diversification strategy, 90   
diversified portfolio, 69, 76   
diversifier, 116   
dividend, 40, 45, 77, 103, 104, 126   
dividend imputation, 103   
dividend payment, 103   
dollar carry trade, 88   
dollar duration, 68, 72, 75, 94   
dollar holding, 55, 125, 126   
dollar position, 47   
dollar-duration-neutral butterfly, 71, 72   
dollar-duration-neutrality, 72   
dollar-neutral book, 77   
dollar-neutral portfolio, 41–43, 45, 50, 56,   
57   
dollar-neutral strategy, 45, 62, 64, 76   
dollar-neutral trade, 87   
dollar-neutrality, 46, 56, 57, 72, 97, 128   
dollar-neutrality condition, 97   
dollar-neutrality constraint, 47, 56, 57   
domestic currency, 86, 87   
domestic interest rate, 86   
Donchian Channel, 52   
double-taxation system, 103   
Dow Jones Industrial Average (DJIA), 76   
downside risk, 65   
drawdown, 82, 114   
drift, 65   
dual-momentum sector rotation, 62   
dumb order flow, 58, 59   
dummy variable, 73   
duration, 68, 70   
duration-targeting strategy, 70   
dynamic asset allocation, 65   
earnings, 41, 42, 59   
earnings-momentum, 41   
earnings-momentum strategy, 42   
economic activity, 112   
economic announcement, 123   
economic diversification, 112   
effect, contrarian, 40   
effect, mean-reversion, 40, 96   
eigenvalue, 79   
electricity futures, 108   
electricity futures contract, 108   
electronic trading, 16   
embedded option, 101, 102   
EMSD (exponential moving standard de  
viation), 117, 118   
energy, 15, 47, 108, 124

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

energy hedging, 108   
energy spreads, 108   
equally-weighted portfolio, 126   
equities, 17, 95, 112, 119, 122, 123   
equity index, 77, 122   
equity market, 81, 90   
equity market excess return, 122   
equity portfolio, 90   
equity tranche, 99   
equity tranche credit events, 99   
equity tranche trade, 99   
equity value, 110   
eRank (effective rank), 79   
error function, 119   
establishing, 18, 54, 126   
estimation period, 63, 64, 86   
ETF alpha, 63   
ETF arbitrage, 79   
ETF portfolio, 65   
ETF return, 63, 65   
ETF, leveraged, 64   
ETF, leveraged inverse, 64   
ETH (ether/Ethereum), 116   
Euclidean distance, 44, 54   
EUR (euro), 116   
eurodollars, 114   
European call option, 17   
European option, 17   
European put option, 17   
ex-dividend, 103, 104   
excess return, 44, 52   
exchange rate, 89   
exchange-traded fund (ETF), 15, 61–65,   
79, 123   
exchange-traded note (ETN), 15, 82   
execution price, 59   
exercise date, 17   
exotic options, 17   
expected alpha return, 60   
expected return, 44, 54, 57–60, 65, 91,   
96, 125, 126, 128   
expected stock return, 55   
expiration, 17, 24, 25, 78, 89, 104

explanatory variable, 110   
exponential moving average (EMA), 50, 97, 117, 118   
exponential smoothing parameter, 117   
exposure, 43, 65, 70, 76, 90, 92, 94, 99, 111, 124   
extreme market events, 111

face value, 66, 69   
factor, 43, 44, 63, 65, 123   
factor investing, 123   
factor loadings matrix, 57   
factor portfolio, 44   
factor rankings, 44   
factor-based strategies, 111   
fair value, 77, 101   
false signal, 51, 85   
Fama puzzle, 86   
Fama-French factors, 44, 63   
fear gauge index, 81   
feature, 120, 121   
feature vector, 120   
Fed discount rate, 90   
Fed monetary policy, 90   
Federal Open Market Committee (FOMC),   
123   
fence, 37   
fiat currency, 116   
fifty-fifty butterfly, 72   
fill or kill limit order, 80   
fills, 58   
filter, Hodrick-Prescott, 85   
financed portfolio, 74   
financial crises, 111   
financial derivative, 17   
financial distress, 115   
financial markets, 16   
firm’s equity, 109, 110   
first-month contract, 81   
fix-and-flip, 114   
fixed coupon, 105   
fixed coupon bond, 67   
fixed coupon rate, 106

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

fixed income, 66   
fixed rate, 67, 105, 106   
fixed rate cash flow, 105   
fixed rate coupon bond, 68   
fixed rate payment, 67   
fixed-income asset, 93, 123   
fixed-income instrument, 101   
flattener, 75, 100   
floating coupon payment, 67   
floating rate, 105   
floating rate bond, 67   
floating rate cash flow, 105   
floating rate payment, 67   
FOMC announcements, 123   
forecasting future returns, 63   
foreign currency, 86–88   
foreign currency forward, 88   
foreign exchange (FX), 85   
foreign interest rate, 86   
formation period, 40, 45, 62   
forward, 86, 87   
forward contract, 21, 87   
forward discount, 86–88   
forward FX rate, 86   
forward premium, 86   
front leg, 75   
front-month futures price, 89   
fuel futures, 108   
fundamental analysis, 60, 61   
fundamental data, 59   
fundamental industry classification, 128,   
129   
fundamental macro momentum, 122   
fundamental trading strategies, 116   
fundamentals, 61, 94, 116   
futures, 15, 17, 77, 81–83, 89, 91–97, 108,   
113, 123   
futures basis, 94   
futures calendar spread, 94   
futures contract, 77, 89, 92–94   
futures contract size, 108   
futures contract, front-month, 82   
futures delivery basket, 94   
futures position, 21, 89, 93, 107   
futures price, 77, 81, 89, 91–93   
futures return, 82, 95   
futures spread, bear, 94   
futures spread, bull, 94   
futures yield, 94   
futures, CTA, 122   
futures, managed, 122   
futures, T-bond, 94   
futures, T-note, 94   
FX momentum strategy, 88   
FX rate, 86   
FX rate risk, 86, 87   
FX spot rate, 85   
FX spot rate time series, 85   
FX triangular arbitrage, 89   
Gamma, 83   
Gamma hedge, 84   
Gamma hedging, 83, 84, 102   
Gamma scalping, 84   
gas futures contract, 108   
GDP (gross domestic product), 122, 123   
geographic diversification, 113   
Global Industry Classification Standard   
(GICS), 128   
global macro, 15, 121   
global macro inflation hedge, 122   
global macro inflation hedge strategy, 123   
global macro strategy, 122   
government bond, 122, 123   
government security, 76   
Greeks, 83   
greenfield project, 124   
guts, 26–28   
guts strategy, 26   
hard-to-borrow securities, 77   
headline inflation (HI), 122, 123   
healthy-minus-distressed (HMD), 110, 111   
heat rate, 108   
heating-degree-days (HDD), 107   
hedge, 93, 94, 108, 113, 123   
hedge position, 93

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

hedge ratio, 82, 93, 94, 99–102, 107, 108   
hedgers, 90, 96   
hedging, 15, 82   
hedging pressure (HP), 90   
hedging strategy, 15, 18, 19   
heterotic risk model, 128   
hidden layer, 117, 119   
high frequency trading (HFT), 16, 58, 59,   
77   
high minus low (HML), 44   
High Yield bonds, 73   
high-minus-low carry, 87   
high-return-volatility portfolio, 42   
historical correlation, 45, 82, 83   
historical data, 72, 73, 92, 94, 101   
historical return, 43, 55, 78, 88, 91   
historical stock price, 50   
historical variance, 83, 88   
historical volatility, 43, 44, 49, 65, 80, 82,   
83, 95, 96, 126   
Hodrick-Prescott filter, 97   
holding horizon, 61   
holding period, 41–43, 45, 62, 90, 111,   
122   
holding weights, 55, 56   
horizon, 58, 59, 61, 112   
horizontal spread, 24   
HP filter, 85   
Hybrid Market, 16   
hybrid security, 101   
hyperbolic tangent (tanh), 119   
implied index volatility, 78   
implied volatility, 43, 78, 80, 83–85   
imputation system, 103   
income strategy, 20, 22, 23, 27, 28, 31,   
33, 34, 36   
income-generating real estate portfolio,   
111   
incomplete basket, 77   
index, 15, 17, 76–80, 85, 99, 100, 122   
index arbitrage, 77   
index basket, 77   
index constituents, 77, 85   
index ETF, 79   
index futures, 76, 77   
index futures price, 77   
index hedging, 99   
index implied volatility, 78   
index level, 78   
index option, 78, 83   
index option straddle, 78   
index portfolio, 77   
index position, 99   
index spot price, 77   
index volatility, 77, 78   
index volatility targeting, 80   
index, market cap weighted, 78   
index-based ETF, 76   
indexed payment, 106   
industrial properties, 112   
industry, 46, 49, 60–62, 109, 129   
industry classification, 61   
industry classification data, 59   
inflation, 104, 105, 113, 122, 123   
inflation hedge, 123   
inflation hedging, 104, 113, 124   
inflation index, 105   
inflation rate, 113   
inflation swap, 104, 105   
inflation-hedging investment, 124   
inflation-indexed products, 105   
infrastructure, 15, 123, 124   
infrastructure asset, 124   
infrastructure company, 124   
infrastructure fund, 124   
infrastructure investment, 124   
infrastructure project, 124   
input layer, 116–118   
institutional trader, 59   
integration, 114   
intercept, 44, 48, 49, 54, 60, 63, 74, 82   
interest, 67, 86, 115   
interest rate, 66, 68, 69, 72, 74, 75, 77,   
86, 87, 93, 94, 97, 100, 103, 115,   
116

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

interest rate exposure, 100   
interest rate futures, 93   
interest rate futures contract, 94   
interest rate futures hedge ratio, 94   
interest rate risk, 69, 70, 93   
interest rate risk hedging, 93   
interest rate spread, 72, 105   
interest rate swap, 76, 100, 104   
Internal Bar Strength (IBS), 64   
international trade, 122   
international trade trends, 122   
intra-asset diversification, 112   
intraday arbitrage, 79   
intraday signal, 58   
intraday strategy, 125   
intraday trading strategy, 126   
inverse, 56   
inverse ETF, 65   
inverse model covariance matrix, 128   
investment, 15, 41, 46, 47, 70, 86, 111,   
124   
Investment Grade bonds, 73   
investment level, 41, 43, 56, 125, 126   
investment opportunity, 115   
investment portfolio, 122   
investment strategy, 124   
investment style, 121   
investment vehicle, 76, 113   
investment, equity, 90   
iron butterfly, 32, 34   
iron condor, 36   
iShares, 79   
Jensen’s alpha, 59, 63   
Joule, 108   
JPY (Japanese Yen), 86   
k-nearest neighbor (KNN) algorithm, 53,   
54, 117   
Kalman filter, 97   
Kelly strategy, 115   
keyword, 120   
ladder, 22, 23, 70

ladder, 22, 23,70

ladder portfolio, 70   
ladder strategy, 23   
Lagrange multiplier, 57   
layering, 114   
learning vocabulary, 120, 121   
leg, contingent, 98   
leg, default, 98   
level, resistance, 51   
level, support, 51   
leverage, 64, 65, 80, 111   
leveraged ETF (LETF), 64, 65   
leveraged inverse ETF, 65   
limit order, 58   
limit order, aggressive, 58   
limit order, marketable, 80   
linear homogeneous constraints, 57   
linear model, 54   
linear regression, 47, 48   
linear trading costs, 125, 126   
liquid funds, 114   
liquid stake, 111   
liquid U.S. stocks, 59   
liquidating, 54   
liquidation, 115   
liquidity, 40, 61, 115   
liquidity management, 115   
liquidity management tool, 114   
listed infrastructure funds, 124   
loadings matrix, 48, 49, 61   
loan, 87, 98, 103, 115, 116   
loan shark, 116   
loan sharking, 116   
loan-to-own, 110   
log forward FX rate, 87   
log spot FX rate, 87   
log-return, 84   
log-volatility, 92   
logistic regression, 110, 121   
logit model, 121   
London Interbank Offer Rate (LIBOR),   
67, 76   
long portfolio, 73, 79   
long risk reversal strategy, 84

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

long-maturity wing, 72   
long-only, 50   
long-only portfolio, 40, 41   
long-only strategy, 62   
long-only trend-following portfolio, 65   
long-run mean, 92   
long-short strategy, 122   
lookback, 125   
lookback period, 79   
losers, 40–42, 44, 95, 97   
loss, contango, 82   
loss, roll, 82   
low-return-volatility portfolio, 42   
low-risk anomaly, 73   
low-risk factor, 73   
low-volatility anomaly, 42   
Macaulay duration, 68   
machine learning, 16, 53, 55, 59   
machine learning algorithm, 54   
machine learning classification scheme, 120   
machine learning methods, 59, 121   
machine learning techniques, 53, 116   
macro strategy, 122   
macro trading strategy, 121, 123   
macroeconomic trends, 122   
managed futures, 122   
Manhattan distance, 44, 54   
margin account, 76   
mark-to-market (MTM), 98, 99   
market, 16, 17, 58, 61, 65, 70, 83, 110,   
113   
market activity, 95   
market beta, 110   
market cap, 59, 78, 116   
market cap weighted index, 77   
market capitalization, 42, 44, 76, 116   
market crashes, 41   
market data, 89   
market downturn, 110   
market index, 95, 97   
market index return, 95, 97   
market portfolio, 44   
market price, 52, 92, 102, 114   
market underreaction, 122   
market value, 111   
market volatility, 94   
market-making, 58, 59   
married call, 19   
married put, 19   
maturity, 17, 18, 21, 24, 25, 66–71, 73–76,   
81, 82, 84, 87, 93, 94, 104–106   
maturity date, 69, 87   
maturity time, 17, 66   
maturity-weighted butterfly, 73   
MBS passthrough, 100   
MBS price, 100, 101   
MBtu, 108   
mean-reversion, 46, 47, 49, 54, 60, 64, 81,   
92, 95, 128   
mean-reversion parameter, 92   
mean-reversion strategy, 45, 47, 64, 81,   
95   
mean-variance optimization, 57, 112, 126   
Megawatt, 108   
Megawatt hour (Mwh), 108   
merger, 125   
merger arbitrage, 52   
merger arbitrage opportunity, 52   
mergers and acquisitions (M&A), 52   
metropolitan statistical area (MSA), 113   
mini-S&P 500 futures, 81, 82   
mishedge, 77   
mispricing, 45, 79   
mixed-asset diversification, 111   
MMBtu, 108   
model covariance matrix, 55, 57   
modified duration, 68–70, 72, 74, 94   
momentum, 43, 44, 61, 62, 65, 96, 97,   
123, 128   
momentum & carry combo, 88   
momentum effect, 40, 41, 60, 61, 113   
momentum strategy, 41, 60, 88, 96   
momentum, absolute, 62   
momentum, cross-sectional, 62   
momentum, industry, 62

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

momentum, relative, 62

momentum, sector, 62

momentum, time-series, 62

monetary policy, 122

monetary policy trends, 122

money laundering, 114

moneyness abbreviations (ATM, ITM, OTM), 18

mortgage, 100

mortgage-backed security (MBS), 15, 100, 102

moving average, 49–51, 53, 60, 62, 63, 65, 85, 86

moving average length, 117

moving average, exponential, 117

moving standard deviation, 125

moving standard deviation, exponential, 117

multi-asset portfolio, 65

multi-asset trend following, 65

multi-currency arbitrage, 89

multifactor model, 57, 91

multifactor risk model, 57

multifactor portfolio, 43, 123

multifactor strategy, 44

multinomial distribution, 120

municipal bond, 103, 124

municipal bond tax arbitrage, 102

mutual fund, 59, 63, 64, 111

mutual fund return, 63

naked call, 19

naked put, 18

near-month contract, 94

near-month futures, 94

neutral curve butterfly, 72

New York Stock Exchange (NYSE), 16

no-risk-free-arbitrage condition, 87

node, 118

noise, 85, 97, 122

non-announcement days, 123

non-deliverable bond, 94

non-directional strategy, 18

non-discretionary strategy, 122   
non-systematic risk, 112   
non-systematic risk reduction, 112   
nonlinear least squares, 92   
normalized demeaned return, 60   
notional, 106   
notional amount, 98   
objective function, 56, 57, 85   
open, 125, 128   
open interest, 95, 96   
open price, 51, 127   
operational distress, 108   
opportunity management tool, 114   
optimal hedge ratio, 82, 83, 93   
optimal weighting scheme, 43   
optimization, 55, 57, 128   
optimization strategy, 96   
optimization techniques, 71   
optimization, mean-variance, 125   
optimizer function, 128   
option, 15, 17, 18, 21, 78, 80, 81, 83, 84,   
104, 113   
option Gamma, 102   
option holder, 17   
option premia, 18, 84   
option pricing, 17   
option straddle, 78   
option styles, 17   
option trading strategy, 37–39, 80   
option writer, 17   
option, all-or-nothing, 17   
option, ATM (at-the-money), 19–34, 37–   
39, 78   
option, binary, 17   
option, call, 26, 27, 84, 104   
option, digital, 17   
option, ITM (in-the-money), 25–28, 31–   
35, 37, 104   
option, OTM (out-of-the-money), 18–23,   
25–27, 29–39, 84   
option, put, 26, 27, 84, 104   
option-adjusted spread (OAS), 102

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

order, 58, 128

order execution system, 80

order flow, dumb, 58

order flow, informed, 58

order flow, smart, 58

order flow, toxic, 58

order, market, 58

orders, cancel-replaced, 58

orders, canceled, 58

orders, placed, 58

Ornstein-Uhlenbeck process, 91

orthogonality condition, 49

OTM option, 78

out-of-sample backtest, 118

out-of-sample backtesting, 16, 125

outcome, 120, 121

output gap, 123

output layer, 116, 118, 119

over-fitting, 118

overnight return, 126

overreaction, 95, 109

P&L, 76, 84, 93, 100, 104, 129

P&L drawdown, 82

pairs trading, 45–47

pairs trading strategy, 46

parallel shift, 68, 70, 72, 75, 102

passive approach, 90

passive distressed debt strategy, 109

passive limit order, 58

period, formation, 90

periodic compounding, 66, 68, 71

passive trading strategy, 109

periodic premium payment, 97, 98

periodic premium payment rate, 97

physical commodity, 115

pivot point, 51

placement, 114

portfolio diversification, 90

portfolio construction techniques, 112

Porter stemming algorithm, 120

portfolio management, 115 portfolio, 15, 40, 41, 43, 44, 55, 62, 65, 67, 69–72, 74, 75, 78, 79, 82, 83, 90, 91, 95, 110, 112, 114, 115, 122, 123, 125, 126

portfolio optimization, 125

portfolio P&L, 55

portfolio performance, 112

portfolio weights, 56

portfolio, barbell, 69

portfolio, HML, 44

passthrough MBS, 100

portfolio, MKT, 44

portfolio, ladder, 69

portfolio, SMB, 44

position bounds, 125

passthrough MBS price, 101

position, bearish, 23

pawnbroker, 115

position, bullish, 23

predicted class, 119

predicted value, 54

predictor variable, 53

premium, 15, 17, 84, 99

premium leg, 98

pawnbroking, 115, 116

premium payment, 100

premium, annual, 75

pawnbroking strategy, 115

premium, periodic, 75

payment period, 66

prepayment model, 101

payment, coupon, 106

prepayment risk, 100

payment, principal, 106

price and volume data, 53, 126

payoff, 17–19, 78, 84, 93

price reversal, 52

peer-to-peer (P2P) internet protocol, 116

price, close, 64

pension fund, 59

price, fully adjusted, 40, 45, 126, 127

performance characteristics, 90, 112, 129

price, high, 51, 64, 126

price, intraday, 126

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

price, low, 51, 64, 126   
price-momentum, 40   
price-momentum strategy, 40–42, 44   
price-volume, 59   
pricing data, 61   
pricing model, 91, 102   
principal, 66, 67, 70, 94, 105, 106   
principal component analysis (PCA), 79   
principal components, 61, 79   
private equity-type investments, 124   
probability distribution, 120   
probability measure, 92   
property type, 113   
property type diversification, 112   
protection buyer, 98   
protection seller, 97   
protective call, 19   
protective call option strategy, 19   
protective put, 19   
protective put option strategy, 19   
protective put strategy, 19   
publicly traded company, 52   
publicly traded infrastructure companies,   
124   
put option, 17–39, 84, 104, 107   
put spread, 20, 23, 34, 36–38   
put, naked, 18   
put, short, 18   
put-call parity, 18   
quantile, 87, 118–120, 123   
quantitative trading alpha, 59   
quark spread, 108   
quintile, 44, 64, 90, 91   
R Package for Statistical Computing (R),   
125   
R-squared, 63   
R-squared strategy, 64   
rallies, 81   
rank, 44, 79   
ranking, 44, 122   
rate, fixed, 104   
rate, floating, 104   
ratio call spread, 31   
ratio put spread, 31   
raw close price, 127   
raw inflation, 122   
raw open price, 127   
raw spot rate, 85   
real estate, 15, 111–113, 124   
real estate asset, 111, 112   
real estate holdings, 112   
real estate investment, 111, 112   
real estate investment strategy, 114   
real estate investment trust (REIT), 111,   
113   
real estate momentum, 113   
real estate momentum strategy, 113   
real estate property, 113   
real estate return, 113   
real estate, commercial, 111   
real estate, residential, 111   
real interest rate, 123   
realized alpha return, 60   
realized P&L, 58   
realized profit, 50   
realized variance, 84   
realized volatility, 83, 85, 111   
rebalancing, 80, 82, 89, 90, 110   
recovery rate, 98   
rectified linear unit (ReLU), 119   
reference entities, 98   
reference pools, 98   
regression, 45, 48, 49, 54, 60, 72, 73   
regression coefficient, 45, 48, 63, 73, 74   
regression R-squared, 63   
regression residual, 48, 73   
regression weights, 49   
regression, cross-sectional, 73   
regression-weighted butterfly, 72, 73   
reinvestment risk, 70   
relative momentum, 62   
relative strength index (RSI), 117, 118   
relative value strategy, 122   
reorganization, 109, 110   
reorganization plan, 109

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

reorganization process, 109   
replication, 106   
repo rate, 76   
repo strategy, 115   
repurchase agreement (repo), 114, 115   
residual momentum, 44   
residual momentum strategy, 45   
resistance, 51, 60   
retail trader, 58   
return, risk-adjusted, 40, 45, 112, 124   
reverse repurchase agreement, 115   
rich stock, 45   
risk, 15, 19, 28, 33, 35, 36, 42, 52, 62, 70,   
77, 81, 82, 87, 92, 99, 100, 112,   
125   
risk arbitrage, 52   
risk factor, 49, 79   
risk management, 15, 57, 110, 128   
risk management tool, 114   
risk model, 125, 127, 128   
risk premium, 110   
risk reversal, 21, 22, 38, 39, 84   
risk sentiment, 122   
risk sentiment trends, 122   
risk, idiosyncratic, 79   
risk, interest rate, 70   
risk, specific, 79   
risk-free arbitrage, 87   
risk-free arbitrage opportunity, 86   
risk-free asset, 80, 86, 123   
risk-free discount factor, 98   
risk-free instrument, 75   
risk-free interest rate, 86   
risk-free interest rate curve, 102   
risk-free position, 87   
risk-free probability measure, 92   
risk-free profit, 27, 76   
risk-free rate, 44, 73–75, 77, 94   
riskless asset, 80   
risky duration, 99, 100   
roll loss, 82   
roll yield, 89   
roll-down component, 74   
rolling down the curve, 75   
rolling down the yield curve, 74   
rolling down the yield curve strategy, 75   
root mean square error (RMSE), 54   
rotation, industry, 62   
rotation, sector, 62   
Russell 3000, 76   
S&P 500, 76, 79, 83   
S&P 500 ETFs, 79   
S&P 500 option, 83   
sample correlation matrix, 78, 79   
sample covariance matrix, 55, 83, 88   
sample variance, 60   
scale invariance, 56, 57   
seagull spread, 37–39   
second-month futures price, 89   
sector, 46, 47, 49, 61, 62, 65, 106, 124   
sector ETF, 62   
sector momentum rotation, 61, 62   
sector momentum rotation strategy, 61–   
63, 65   
sector rotation signal, 62   
secured cash loan, 115   
secured loan, 110   
security, 115   
selectivity, 64   
sell signal, 86, 92, 119   
sell-offs, 81   
sell-write strategy, 18   
semiannual compounding, 94   
semiannual fixed coupons, 105   
sentiment analysis, 120   
sentiment data, 59, 121   
serial regression, 44, 63, 82, 93   
serial variance, 88   
serially demeaned return, 60, 117   
settlement, 81   
share, 17, 41, 42, 46, 52, 58   
shareholder, 103   
shares outstanding, 78   
Sharpe ratio, 55, 56, 58, 65   
Sharpe ratio maximization, 56, 57   
short-maturity wing, 72   
short-sale, 47   
short-selling issues, 77   
shorting ETFs, 62   
shorting stock, 18, 19, 28, 29, 42, 43, 45   
shorting Vega, 83   
shorting VIX futures, 81   
sideways market, 83   
sideways strategy, 18, 27–29, 32–36   
sigmoid, 119   
signal, 16, 50, 52, 54, 55, 58, 128   
signal, buy, 120   
signal, ephemeral, 16   
signal, machine learning, 57   
signal, mean-reversion, 57   
signal, momentum, 57   
signal, sell, 120   
simple moving average (SMA), 49, 50,   
127   
simple moving standard deviation, 127   
single-stock KNN, 53, 60   
single-stock KNN trading strategy, 117   
single-stock methods, 59   
single-stock option, 17, 78, 79, 83   
single-stock option straddle, 78   
single-stock strategy, 53   
single-stock technical analysis strategies,   
60   
single-stock trading, 54   
single-tranche CDO, 98   
skew, 84   
skewness, 91   
skewness premium, 91   
skip period, 40, 43, 45   
slippage, 16, 41, 77, 80   
Small minus Big (SMB), 44   
smart order flow, 58   
smoothing parameter, 85   
social media sentiment analysis, 120   
softmax, 119   
sorting, 64   
source code, 16, 57, 79, 125   
sovereign risk, 123   
spark spread, 108   
SPDR Trust, 79   
specialist system, 16   
specific risk, 57, 79   
speculative bubble, 116   
speculative buy-and-hold asset, 116   
speculator, 90, 108   
spike, 82   
splits, 40, 45, 126   
spot, 77, 82   
spot FX rate, 86, 122   
spot price, 77, 91, 93   
spot value, 77   
spread, 69, 75, 83, 100, 102, 108, 123   
spread change, 72   
spread curve, 100   
spread, calendar, 24   
spread, CDO tranche, 98–100   
spread, diagonal, 24   
spread, ratio, 30, 31   
standard deviation, 42   
Standard Industrial Classification (SIC),   
128   
standardized unexpected earnings (SUE),   
42   
state variable, 122   
statistical arbitrage, 15, 54, 55, 61   
statistical arbitrage strategy, 16, 61   
statistical industry classification, 125, 128   
statistical risk model, 79, 128   
steepener, 75, 100   
stemming, 120   
stochastic dynamics, 92   
stochastic gradient descent (SGD), 119   
stochastic processes, 91   
stochastic volatility models, 91   
stock loan, 104   
stock market, 61   
stock merger, 52   
stock price, break-even, 18   
stock trading strategy, 60   
stock, cheap, 46   
stock, rich, 46

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

stop-loss price, 24, 25   
stop-loss rule, 50   
stop-words, 120   
straddle, 26–29, 33, 35, 36, 79, 80, 83, 85   
strangle, 26, 27, 33, 35, 36   
strap, 30   
strategy, ANN, 120   
strategy, barbell, 69   
strategy, bullet, 69   
strategy, capital gain, 18, 35, 36   
strategy, contrarian, 49   
strategy, delay-0, 128   
strategy, delay-1, 128   
strategy, Delta-neutral, 83   
strategy, earnings-momentum, 42   
strategy, HMD, 110, 111   
strategy, income, 18, 35, 36   
strategy, ladder, 70   
strategy, mean-reversion, 49   
strategy, momentum, 60   
strategy, price-momentum, 42   
strategy, resistance, 51   
strategy, straddle, 26   
strategy, strangle, 26   
strategy, strap, 30   
strategy, strip, 30   
strategy, support, 51   
strategy, trend following, 60   
strategy, zero-cost, 110   
strike, 32–36, 84   
strike price, 17–39, 84, 104, 107   
strip, 30   
STRIPS (Separate Trading of Registered   
Interest and Principal of Securi  
ties), 106   
structured assets, 15, 97   
style factor, 61   
style risk factor, 61   
subset portfolio, 78   
sum of squares (SS), 63   
supply, 94   
support, 51, 60   
support vector machine (SVM), 121   
survivorship bias, 125   
swap, 67, 76, 105   
swap agreement, 104   
swap contract, 105   
swap fixed rate, 105   
swap rate, 101   
swap spread, 76   
swap strategy, 76, 104   
swap-spread arbitrage, 76   
synthetic call, 19, 28, 29   
synthetic CDO, 98   
synthetic coupon payment, 106   
synthetic forward, 21, 37   
synthetic forward contract, 21   
synthetic futures, 21   
synthetic index, 106   
synthetic portfolio, 106   
synthetic put, 19, 28   
synthetic short bond position, 76   
synthetic straddle, 28, 29   
systematic approach, 122   
systematic macro, 122   
systematic macro trading strategy, 123   
systematic risk, 79   
T-bond, 94   
T-note, 94   
tactical asset allocation, 90   
target company, 52   
target variable, 53   
target volatility, 111   
tax arbitrage, 15, 102   
tax credit, 103, 104   
tax credit rate, 103, 104   
tax shield, 103   
tax strategy, 37   
tax-exempt municipal bonds, 102, 103   
technical analysis strategies, 61   
technical indicator, 116, 117   
tercile, 91   
term spread, 123   
term structure, 74, 89, 92   
Theta, 83

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

Theta play, 83

trading strategy, 15–17, 52, 85, 90, 115

Theta-decay, 84

ticker, 79, 125–127

trading universe, 40, 59, 125, 127

ticker symbol, 127

traditional assets, 111, 112, 116

time series, 40, 43, 50, 55, 60, 78, 80, 91

traditional portfolio, 112

time-series filter, 97

training, 54, 118, 119

time-stamping, 116

training data, 120, 121

time-to-maturity (TTM), 18, 24, 25, 29

training dataset, 118

TIPS principal, 106

training period, 53

TIPS-Treasury arbitrage, 105

tranche, 97–100

tracking error, 82, 83

tranche hedging, 99

tracking ETF, 124

tranche MTM, 100

tradables, 15

tranche notional, 99, 100

trade execution system, 89

tranche value, 97

traded volume, 52

tranche, equity, 97, 99

trader’s outlook, 69

tranche, junior mezzanine, 97

trader’s outlook, bearish, 19–23, 25, 30, 38

tranche, senior, 97

trader’s outlook, bullish, 19–22, 25, 29, 30, 37, 39

tranche, senior mezzanine, 97

trader’s outlook, conservatively bearish, 23

tranche, super senior, 97

transaction costs, 17, 71, 77, 79, 80, 86, 87, 104, 106, 112, 115

trader’s outlook, conservatively bullish, 22

Treasuries, 123

trader’s outlook, moderately bullish, 37

Treasury bill rate, 44

Treasury bills, 80, 114

Treasury bond, 76, 105, 106, 109

trader’s outlook, neutral, 26–29, 32–37

Treasury bond coupons, 106

trader’s outlook, neutral to bearish, 19, 24, 31

Treasury curve, 102

trader’s outlook, neutral to bullish, 18, 24, 31

Treasury ETF, 63, 65

Treasury Inflation-Protected Securities (TIPS), 105, 106

trader’s outlook, non-directional, 22, 23

Treasury note, 105

trader’s outlook, strongly bearish, 31

tree boosting algorithms, 121

trend, 52, 63, 97, 122

trader’s outlook, strongly bullish, 30

trades, establishing, 58

trend component, 85

trend data mining, 116

trades, liquidating, 58

trend following, 96

trading bounds, 125

trend, ephemeral, 16

trading costs, 16, 41, 56, 57, 59

Twitter sentiment, 121

trading day, 17, 43, 50, 53, 79, 84, 126– 128

U.S. regions, 113

trading portfolio, 15, 96

unadjusted close price, 126

trading rule, 81, 119, 120

unadjusted open price, 126

trading signal, 51, 85, 119

unadjusted volume, 126

trading signal, faint, 16

uncertainty index, 80

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

uncompounded rate, 66

Uncovered Interest Rate Parity (UIRP), 86

underlying, 83, 84

underlying asset, 17, 76, 93

underlying index, 64, 65, 79

underlying index portfolio, 77

underlying instrument, 59, 65

underlying price, 93

underlying security, 17

underlying single-stock options, 79

underlying stock, 25, 26, 59, 62, 77, 101

underlying stock price, 101

underreaction, 122

unexpected earnings, 42

unlisted infrastructure fund, 124

USD (U.S. dollar), 86, 116

value, 42–44, 61, 73, 74, 90, 91, 123

value factor, 73

value strategy, 42, 90

value-based strategies, 116

variable coupon bond, 67

variable rate, 67

variable rate coupon payment, 76

variable, feature, 53

variable, predictor, 53

variance, 83, 88

variance notional, 84

variance strike, 84

variance swap, 84, 85

variance, conditional, 92

vector autoregressive model (VAR), 112

vector, feature, 120

Vega, 83

Vega play, 83

vertical spread, 19, 20, 22, 23

VIX (CBOE Volatility Index), 80–83

VIX futures, 81, 82

VIX futures basis, 81

VIX futures basis trading, 81

VIX futures contract, 82

VIX futures curve, 81, 82

VIX futures price, 81, 82

VIX price, 81

volatility carry, 82

volatility ETN, 82

volatility index, 81

volatility risk premium, 83

volatility skew, 84

volatility spike, 83

volatility target, 80

volatility targeting strategy, 80

volatility, constituent, 78

volatility, index, 78

volume, 53, 95, 96

weather, 15

weather conditions, 106, 107

weather derivative, 106, 107

weather index, 106, 107

weather risk, 106

weighted average, 44, 68, 95

weighted regression, 49, 57

weighting scheme, 41, 44, 54, 65, 95

well-diversified portfolio, 124

Whittaker-Henderson method, 85

wing, 72

winners, 40–42, 44, 95, 97

word, 120, 121

world, 122

year-on-year inflation swap, 105

yield, 66, 68–71, 74–76, 109

yield curve, 68–72, 74, 75

yield curve dynamics, 75

yield curve spread, 75

yield curve spread strategy, 75

YoY (year-on-year), 105, 123

zero-cost combination, 71

zero-cost long-short portfolio, 89

zero-cost portfolio, 42, 90, 91, 110, 122, 123

zero-cost strategy, 40, 72, 74, 91, 113

Copyright c 2018 Zura Kakushadze and Juan Andr´es Serur. All Rights Reserved.

zero-coupon bond, 66, 69, 70, 74

zero-coupon discount bond, 106

zero-coupon government Treasury curve,

zero-coupon inflation swap, 105, 106

zero-coupon swap, 105