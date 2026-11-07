"""8.11 / 8.12 need PyTorch + transformers, which live only in .venv: in MAVERICK's own Python these skip."""
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

from maverick.llm.encoder import Frozen  # noqa: E402

TOY = [("files.copy", ["copy", "this", "file"]), ("files.copy", ["copy", "<path>"]),
       ("process.end", ["kill", "chrome"]), ("process.end", ["kill", "the", "app"])]


def test_frozen_learns_on_given_vectors():
    import numpy as np
    vectors = {" ".join(t): np.array([1.0, 0.0]) if label == "files.copy" else np.array([0.0, 1.0]) for label, t in TOY}
    vectors["duplicate this file"] = np.array([0.9, 0.1])
    model = Frozen(vectors).fit(TOY)
    assert model.predict(["duplicate", "this", "file"])[0] == "files.copy"
