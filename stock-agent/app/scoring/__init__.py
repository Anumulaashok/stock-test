"""Deterministic scoring and risk engine.

Consumes a `FinancialAnalysisResult` (Step 2) and an optional
`ValuationRange` (Step 3) and produces a `ScoringResult`: category
scores, risk indicators, and an overall 0-100 score with a descriptive
band. Every number is explainable via fixed thresholds in
`thresholds.py` and deterministic template text in `normalization.py`
— nothing here calls an LLM, and nothing here makes a buy/sell/hold
recommendation.
"""
