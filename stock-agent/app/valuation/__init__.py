"""Deterministic valuation engine.

DCF (`dcf.py`), comparable multiples (`multiples.py`), and sensitivity
analysis (`sensitivity.py`) are pure calculation modules; `service.py`
orchestrates them into a `ValuationRange`. Nothing in this package
performs I/O, calls an LLM, or makes an investment recommendation.
"""
