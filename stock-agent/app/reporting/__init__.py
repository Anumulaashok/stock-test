"""Structured investment research report generation.

`ReportService.generate(combined_analysis_result)` converts an
already-computed `CombinedAnalysisResult` into an `InvestmentResearchReport`
— pure assembly and formatting over Steps 2-8's results. This package
performs no financial calculation, calls no LLM, and calls no external
provider; it has no dependency besides an optional injectable clock.
`markdown.py` is an optional, equally pure text renderer.
"""
