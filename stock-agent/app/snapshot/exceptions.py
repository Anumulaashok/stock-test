class ResearchInProgressError(Exception):
    """Raised only when a concurrent NORMAL request for the same
    ticker+research_date wins the DB-level race (see
    `ResearchRunRow`'s partial unique index) and this request's own run
    row insert is rejected, yet no COMPLETED/PARTIAL row exists yet to
    return instead (the winner is still RUNNING). In a single-process
    deployment of this app this is vanishingly rare; it is handled by
    surfacing a clear, retryable error rather than a distributed lock.
    """
