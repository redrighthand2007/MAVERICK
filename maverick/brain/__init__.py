from pathlib import Path

import json

from maverick.brain.dataset import DATA_DIR
from maverick.brain.logistic_regression import LogisticRegression
from maverick.brain.mlp import MLP
from maverick.brain.naive_bayes import NaiveBayes
from maverick.brain.text import tokenize

MODELS_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODELS_DIR / "brain.json"
OLD_MODEL_PATH = MODELS_DIR / "naive_bayes.json"  # what Stages 2-7 saved; still loads until you retrain
INBOX_PATH = DATA_DIR / "inbox.tsv"
# Every kind of brain MAVERICK can train; the saved file says which one it is.
MODELS = {model.kind: model for model in (NaiveBayes, LogisticRegression, MLP)}
# Won the Stage 8.2 comparison. The 8.9 neural net ties it (79.5% vs 79.4%) but trains 4x slower: not worth it yet.
DEFAULT_KIND = "logistic_regression"


def load_model(path: Path):
    kind = json.loads(path.read_text(encoding="utf-8")).get("kind", "naive_bayes")
    return MODELS[kind].load(path)


class Brain:
    """MAVERICK's own trained model: sentence -> ("agent.operation", confidence)."""

    def __init__(self, model, log_path: Path | None = None):
        self.model = model
        self.log_path = log_path
        # Below this confidence the orchestrator trusts keyword rules instead; each model kind has its own.
        self.threshold = model.threshold

    @classmethod
    def load(cls, path: Path = MODEL_PATH, log_path: Path | None = INBOX_PATH) -> "Brain | None":
        """Returns None if the model hasn't been trained yet, so MAVERICK runs on rules only."""
        if not path.exists() and path == MODEL_PATH and OLD_MODEL_PATH.exists():
            path = OLD_MODEL_PATH
        if not path.exists():
            return None
        return cls(load_model(path), log_path)

    def predict(self, text: str) -> tuple[str, float]:
        label, confidence = self.model.predict(tokenize(text))
        self._log(text, label, confidence)
        return label, confidence

    def _log(self, text: str, label: str, confidence: float) -> None:
        # Real requests become future training data (inbox.tsv is gitignored: it holds your real paths).
        if self.log_path is None:
            return
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"{label}\t{confidence:.2f}\t{text.replace(chr(9), ' ')}\n")
