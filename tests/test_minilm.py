"""The shipped MiniLM brain (ONNX). The fallback tests always run; the rest need the exported files."""
import numpy as np
import pytest

import maverick.brain.minilm as minilm
from maverick.brain import load_model
from maverick.brain.minilm import MiniLM, available

TOY = [("files.copy", ["copy", "this", "file"]), ("files.copy", ["copy", "<path>", "to", "<path>"]),
       ("files.copy", ["please", "copy", "<path>"]), ("process.end", ["kill", "chrome"]),
       ("process.end", ["kill", "the", "app"]), ("process.end", ["please", "close", "notepad"]),
       ("hardware.ram", ["how", "much", "ram"]), ("hardware.ram", ["ram", "size"]),
       ("hardware.ram", ["show", "my", "memory"])]

needs_files = pytest.mark.skipif(not available(), reason="run .venv python -m maverick.llm.export_onnx first")


def test_missing_files_means_not_available(tmp_path):
    assert not available(tmp_path)


def test_without_the_files_it_uses_the_saved_ensemble(tmp_path, monkeypatch):
    from maverick.brain.ensemble import Ensemble
    fallback = Ensemble().fit(TOY)
    fallback.save(tmp_path / "brain.fallback.json")
    (tmp_path / "brain.json").write_text('{"kind": "minilm"}', encoding="utf-8")
    monkeypatch.setattr(minilm, "available", lambda directory=None: False)
    model = load_model(tmp_path / "brain.json")
    assert not model.ready and model.threshold == Ensemble.threshold
    assert model.predict(["kill", "firefox"])[0] == "process.end"


def test_training_without_the_files_explains_what_to_run(monkeypatch):
    monkeypatch.setattr(minilm, "available", lambda directory=None: False)
    with pytest.raises(RuntimeError, match="export_onnx"):
        MiniLM().fit(TOY)


@needs_files
def test_onnx_gives_the_same_numbers_as_pytorch():
    reference = np.load(minilm.REFERENCE_FILE)
    sentences = [str(s) for s in reference["sentences"]]
    encoder = minilm.Encoder()
    assert np.abs(encoder.embed(sentences) - reference["vectors"]).max() < 1e-4
    encoder.cache = {}
    one_by_one = np.array([encoder.embed([s])[0] for s in sentences])  # other lengths, no padding
    assert np.abs(one_by_one - reference["vectors"]).max() < 1e-4


@needs_files
def test_it_understands_meaning_not_just_words():
    v = minilm.encoder().embed(["duplicate this file", "copy this file", "kill chrome"])
    assert v[0] @ v[1] > 0.6 > v[2] @ v[1]


@needs_files
def test_trains_saves_and_loads(tmp_path):
    model = MiniLM().fit(TOY)
    assert model.predict(["duplicate", "this", "file"])[0] == "files.copy"  # "duplicate" never seen
    model.save(tmp_path / "brain.json")
    loaded = load_model(tmp_path / "brain.json")
    assert loaded.ready and loaded.threshold == MiniLM.HEAD_THRESHOLD
    (label, confidence), (again, again_confidence) = model.predict(["kill", "chrome"]), loaded.predict(["kill", "chrome"])
    assert again == label and abs(again_confidence - confidence) < 1e-4
