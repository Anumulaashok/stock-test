"""End-to-end orchestration layer.

`AnalysisPipelineService` (in `service.py`) coordinates the existing
Step 2-5 services — `FinancialAnalysisService`, `ValuationService`,
`ScoringService`, `AnalystService` — via dependency injection. It
performs no financial calculation and no LLM interaction of its own;
`adapters.py` only reshapes data between stages.
"""
