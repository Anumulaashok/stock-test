"""Curated sector → constituent-ticker universe for Market Opportunity
ranking.

Deliberately small and hardcoded rather than discovered from a
provider: neither configured financial data provider (FMP free tier,
IndianAPI) exposes a "list all NSE tickers by sector" endpoint, and
scoring every constituent means one real provider call per ticker, so
the universe is kept to a handful of large, liquid NSE names per
sector to bound both latency and API quota usage. Extend this list
directly to cover more sectors/tickers.
"""

SECTOR_UNIVERSE: dict[str, list[str]] = {
    "Healthcare": ["SUNPHARMA", "DRREDDY", "APOLLOHOSP"],
    "Power & Electricity": ["TATAPOWER", "NTPC", "POWERGRID"],
    "IT": ["TCS", "INFY", "WIPRO"],
    "Defence": ["HAL", "BEL"],
    "Banking & Finance": ["HDFCBANK", "ICICIBANK", "SBIN"],
    "Auto / EV": ["TATAMOTORS", "M&M", "BAJAJ-AUTO"],
    "Gold & Commodities": ["TITAN", "HINDALCO"],
}
