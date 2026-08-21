"""Top-level application orchestration for ticker-based analysis.

`AnalysisApplicationService` is the only thing that knows about both
data acquisition (`app/data`) and analysis (`app/pipeline`) — it
composes them without either one depending on the other, so
`AnalysisPipelineService` remains completely unaware of where
`CompanyFinancials` came from.
"""
