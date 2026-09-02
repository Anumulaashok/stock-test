"""Cache key schema version.

Bump this whenever the *shape* of a cached payload changes (a field is
added/removed/renamed on `FinancialDataFetchResult`, `MarketSnapshotResult`,
or any other model persisted verbatim by a cache wrapper in this
package) so old rows are addressed by a different key and simply age
out via TTL rather than being deserialized into a model that no longer
matches -- no manual cache flush required after a deploy.
"""

CACHE_SCHEMA_VERSION = "v1"
