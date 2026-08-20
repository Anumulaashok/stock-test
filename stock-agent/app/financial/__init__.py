"""Deterministic financial calculation engine.

Pure calculation functions live in `calculations.py`; `service.py`
orchestrates them into a `FinancialAnalysisResult`. Nothing in this
package performs I/O, and it never uses an LLM for numeric results.
"""
