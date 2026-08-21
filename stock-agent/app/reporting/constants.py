"""Report-layer constants — presentation precision and versioning only.
No financial thresholds live here; those remain in `app.scoring.thresholds`."""

from decimal import Decimal

REPORT_VERSION = "1.0"

PERCENT_DECIMALS = 2
CURRENCY_DECIMALS = 2
SCORE_DECIMALS = 1
RATIO_DECIMALS = 2

PERCENT_QUANT = Decimal("1." + "0" * PERCENT_DECIMALS)
CURRENCY_QUANT = Decimal("1." + "0" * CURRENCY_DECIMALS)
SCORE_QUANT = Decimal("1." + "0" * SCORE_DECIMALS)
RATIO_QUANT = Decimal("1." + "0" * RATIO_DECIMALS)
