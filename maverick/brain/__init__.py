from pathlib import Path

from maverick.brain.dataset import DATA_DIR
from maverick.brain.naive_bayes import NaiveBayes
from maverick.brain.text import tokenize

MODEL_PATH = Path(__file__).parent / "models" / "naive_bayes.json"
INBOX_PATH = DATA_DIR / "inbox.tsv"


class Brain:
    """MAVERICK's own trained model: sentence -> ("agent.operation", confidence)."""

    def __init__(self, model: NaiveBayes, log_path: Path | None = None):
        self.model = model
        self.log_path = log_path

    @classmethod
    def load(cls, path: Path = MODEL_PATH, log_path: Path | None = INBOX_PATH) -> "Brain | None":
        """Returns None if the model hasn't been trained yet, so MAVERICK runs on rules only."""
        if not path.exists():
            return None
        return cls(NaiveBayes.load(path), log_path)

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
