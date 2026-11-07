"""MiniLM brain: a pretrained sentence encoder + our own logistic regression (8.11, shipped without PyTorch).

How a request is understood:
  "duplicate this file"
    -> tokenizer: word pieces -> ids        (tokenizers, reads tokenizer.json)
    -> MiniLM: 384 numbers of MEANING       (onnxruntime, runs model.onnx; nothing in it ever changes)
    -> our logistic regression: a label     (the only part that learns: seconds, no GPU)

Because MiniLM stays frozen, teaching MAVERICK new sentences (8.13 review) still just retrains the small
logistic regression on top. The files come from `.venv\\Scripts\\python -m maverick.llm.export_onnx`.

Fallback: this brain also trains and saves the 8.5 ensemble next to it. If the model files or onnxruntime
are missing on a PC, MAVERICK quietly uses the ensemble instead, so nothing breaks.
"""
import json
from pathlib import Path

import numpy as np

from maverick.brain.ensemble import Ensemble
from maverick.brain.logistic_regression import LogisticRegression

MINILM_DIR = Path(__file__).parent / "models" / "minilm"
MODEL_FILE = MINILM_DIR / "model.onnx"
TOKENIZER_FILE = MINILM_DIR / "tokenizer.json"
REFERENCE_FILE = MINILM_DIR / "reference.npz"
MAX_PIECES = 128  # requests are short; longer ones are cut


def available(directory: Path = MINILM_DIR) -> bool:
    """True when the exported files AND the two small runtime libraries are present."""
    if not ((directory / MODEL_FILE.name).exists() and (directory / TOKENIZER_FILE.name).exists()):
        return False
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
    except ImportError:
        return False
    return True


class Encoder:
    """Sentences -> 384 numbers each, length 1. Remembers sentences it has already seen."""

    def __init__(self, directory: Path = MINILM_DIR):
        import onnxruntime
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(directory / TOKENIZER_FILE.name))
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")  # shorter sentences are filled up
        self.tokenizer.enable_truncation(MAX_PIECES)
        options = onnxruntime.SessionOptions()
        options.log_severity_level = 3  # only real errors
        self.session = onnxruntime.InferenceSession(str(directory / MODEL_FILE.name), options,
                                                    providers=["CPUExecutionProvider"])
        self.cache: dict[str, np.ndarray] = {}

    def embed(self, sentences: list[str], batch_size: int = 64) -> np.ndarray:
        new = [s for s in dict.fromkeys(sentences) if s not in self.cache]
        for i in range(0, len(new), batch_size):
            chunk = new[i:i + batch_size]
            pieces = self.tokenizer.encode_batch(chunk)
            feed = {"input_ids": np.array([p.ids for p in pieces], dtype=np.int64),
                    "attention_mask": np.array([p.attention_mask for p in pieces], dtype=np.int64)}
            self.cache.update(zip(chunk, self.session.run(None, feed)[0]))
        if len(self.cache) > 20000:  # a long-running MAVERICK shouldn't grow forever
            self.cache = {s: self.cache[s] for s in sentences}
        return np.array([self.cache[s] for s in sentences])


_shared: Encoder | None = None


def encoder() -> Encoder:
    """One Encoder per run: loading the model takes about a second, so it's loaded once."""
    global _shared
    if _shared is None:
        _shared = Encoder()
    return _shared


class VectorLR(LogisticRegression):
    """Logistic regression whose features are MiniLM's 384 numbers instead of TF-IDF word counts."""

    # Same settings as encoder.Frozen in 8.11 (fewer epochs: 384 dense numbers learn faster than words).
    def __init__(self, epochs: int = 400, learning_rate: float = 4.0, l2: float = 1e-5, seed: int = 0):
        super().__init__(epochs, learning_rate, l2, seed)

    def features(self, docs: list[list[str]]) -> np.ndarray:
        return encoder().embed([" ".join(tokens) for tokens in docs])


class MiniLM:
    kind = "minilm"
    # Cut-off sweep (5-fold, as MAVERICK runs / hard cases): 0.2 -> 91.3% / 87%, 0.3 -> 91.6% / 86%,
    # 0.4 -> 91.1% / 83% (exactly 8.11's PyTorch result: ONNX lost nothing), 0.5 -> 90.6% / 75%.
    HEAD_THRESHOLD = 0.3

    def __init__(self):
        self.head = VectorLR()
        self.fallback = Ensemble()
        self.ready = available()

    @staticmethod
    def usable() -> bool:
        """Can this brain be TRAINED here? (Loading always works: it falls back to the ensemble.)"""
        return available()

    @property
    def active(self):
        return self.head if self.ready else self.fallback

    @property
    def threshold(self) -> float:
        return self.HEAD_THRESHOLD if self.ready else self.fallback.threshold

    def fit(self, examples) -> "MiniLM":
        if not self.ready:
            raise RuntimeError("MiniLM files missing: run  .venv\\Scripts\\python -m maverick.llm.export_onnx  first.")
        self.head.fit(examples)
        self.fallback.fit(examples)
        return self

    def predict_proba(self, tokens) -> dict[str, float]:
        return self.active.predict_proba(tokens)

    def predict(self, tokens) -> tuple[str, float]:
        return self.active.predict(tokens)

    def part_path(self, path: Path, part: str) -> Path:
        return path.with_name(f"{path.stem}.{part}.json")  # brain.json -> brain.minilm_head.json

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.head.save(self.part_path(path, "minilm_head"))
        self.fallback.save(self.part_path(path, "fallback"))
        path.write_text(json.dumps({"kind": self.kind}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "MiniLM":
        model = cls()
        model.fallback = Ensemble.load(model.part_path(path, "fallback"))
        if model.ready:
            model.head = VectorLR.load(model.part_path(path, "minilm_head"))
        return model
