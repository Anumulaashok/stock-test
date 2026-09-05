"""On-disk trained-model artifacts (spec section 32: training happens
through a dedicated job, not per-request; prediction only ever loads).

Kept as plain files under `var/ml_forecast/` rather than in the database
-- these are large, binary, machine-specific (scikit-learn pickles) blobs
that would be awkward to store as `Text` columns, unlike every other
piece of persisted state in this project. `TRAINING_MANIFEST` records
which universe/version produced the artifacts currently on disk so the
prediction path can refuse to serve a stale/missing model instead of
silently falling back to an untrained one.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from app.forecasting.ml.horizons import MlHorizon
from app.forecasting.ml.versions import FEATURE_VERSION, MODEL_VERSION

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT_DIR = Path("var/ml_forecast")


@dataclass
class TrainingManifest:
    trained_at: str
    training_data_end_date: str
    model_version: str
    feature_version: str
    tickers: list[str]
    row_count: int
    horizons: list[str] = field(default_factory=lambda: [h.value for h in MlHorizon])


class ArtifactStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or DEFAULT_ARTIFACT_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _model_path(self, horizon: MlHorizon, model_name: str) -> Path:
        return self._base_dir / f"model_{horizon.value}_{model_name}.joblib"

    def _dataset_path(self) -> Path:
        return self._base_dir / "pooled_dataset.joblib"

    def _weights_path(self) -> Path:
        return self._base_dir / "model_weights.json"

    def _manifest_path(self) -> Path:
        return self._base_dir / "manifest.json"

    def save_model(self, horizon: MlHorizon, model_name: str, model: object) -> None:
        joblib.dump(model, self._model_path(horizon, model_name))

    def load_model(self, horizon: MlHorizon, model_name: str) -> object | None:
        path = self._model_path(horizon, model_name)
        if not path.exists():
            return None
        return joblib.load(path)

    def save_pooled_dataset(self, dataset: pd.DataFrame) -> None:
        joblib.dump(dataset, self._dataset_path())

    def load_pooled_dataset(self) -> pd.DataFrame | None:
        path = self._dataset_path()
        if not path.exists():
            return None
        return joblib.load(path)

    def save_weights(self, weights: dict[str, dict[str, float]]) -> None:
        self._weights_path().write_text(json.dumps(weights, indent=2))

    def load_weights(self) -> dict[str, dict[str, float]] | None:
        path = self._weights_path()
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def save_manifest(self, manifest: TrainingManifest) -> None:
        self._manifest_path().write_text(json.dumps(asdict(manifest), indent=2))

    def load_manifest(self) -> TrainingManifest | None:
        path = self._manifest_path()
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return TrainingManifest(**data)

    @property
    def is_trained(self) -> bool:
        return self._manifest_path().exists() and self._dataset_path().exists()


def new_manifest(*, tickers: list[str], row_count: int, training_data_end_date: str) -> TrainingManifest:
    return TrainingManifest(
        trained_at=datetime.now(timezone.utc).isoformat(),
        training_data_end_date=training_data_end_date,
        model_version=MODEL_VERSION,
        feature_version=FEATURE_VERSION,
        tickers=tickers,
        row_count=row_count,
    )
