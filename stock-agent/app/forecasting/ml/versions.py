"""Version tags stamped onto every persisted ML forecast (`forecast_predictions`)
so a schema/logic change never gets silently blended with old rows when
computing accuracy or serving `/forecast/history` -- bump the relevant
constant whenever the corresponding module's output shape or semantics
change, mirroring `app.cache.versioning.CACHE_SCHEMA_VERSION`.
"""

FEATURE_VERSION = "features_v1"
MODEL_VERSION = "ensemble_v1"
NEWS_MODEL_VERSION = "news_event_v1"
