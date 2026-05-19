# Fed Macro Quant Backtester

## Project Introduction

This is a macro quant backtesting pipeline that generates S&P 500 (SPY) investment signals by analyzing the sentiment of the U.S. Federal Reserve (Fed) Beige Book text using NLP (FinBERT) and combining it with data on changes in the Fed's total assets (liquidity).

## Key Features

1. Beige Book Crawling: Automatic collection of the Beige Book (HTML/PDF) from the Fed website and text cleaning

2. FinBERT Sentiment Analysis: Sentence-level scaling of positive/negative/neutral scores (0–200) using a finance-specific LLM

3. Macro Signal Combination: Generation of long/cash position signals by combining the rate of change in sentiment scores with the growth rate of total assets (WALCL)

4. Random Search Optimization & Backtesting: Calculation of cumulative returns and visualization of performance comparisons with market returns (Buy & Hold)

## Libraries Used

`pandas`, `numpy`, `torch`, `transformers`, `yfinance`, `pdfminer.six`, `beautifulsoup4`, `matplotlib`
