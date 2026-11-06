import os
from pathlib import Path

import numpy as np

from maverick.agents.search import ops
from maverick.brain.rank import FEATURES, Ranker, features, made_up_searches, mrr

NOW = 1_800_000_000.0
DAY = 86400
# History (python -m maverick.brain.rank, 200 made-up test searches): disk order 0.339, newest first 0.422,
# hand-set weights 0.571, learned weights 0.718.
MIN_LEARNED_MRR = 0.65


def f(path, query="report", days_old=1):
    return dict(zip(FEATURES, features(Path(path), query, NOW - days_old * DAY, NOW)))


def test_features_read_the_name():
    assert f("C:/Users/me/Documents/report.docx")["exact name"] == 1
    assert f("C:/Users/me/Documents/q3_report.pdf")["whole words"] == 1
    assert f("C:/Users/me/code/reporter.py")["whole words"] == 0
    assert f("C:/Users/me/Documents/report_final.docx")["starts with query"] == 1


def test_features_read_the_place_and_age():
    assert f("C:/Users/me/Documents/report.docx")["own folder"] == 1
    assert f("C:/Users/me/AppData/Local/x/report.tmp")["junk folder"] == 1
    assert f("C:/Users/me/.config/report.json")["junk folder"] == 1
    assert f("C:/Users/me/Documents/report.docx", days_old=0)["recent"] == 1
    assert f("C:/Users/me/Documents/report.docx", days_old=5000)["recent"] == 0


def test_pairwise_learning_puts_the_meant_file_first():
    # Two numbers per file; the meant one always has the bigger first number.
    rng = np.random.default_rng(0)
    searches = []
    for _ in range(50):
        X = rng.uniform(0, 1, size=(6, 2))
        meant = int(np.argmax(X[:, 0]))
        searches.append((X, meant))
    ranker = Ranker([0.0, 0.0]).fit(searches)
    assert ranker.weights[0] > abs(ranker.weights[1])
    assert mrr(ranker.order, searches) >= 0.95  # the 2nd weight isn't exactly 0, so a near-tie can flip


def test_mrr():
    searches = [(np.zeros((3, 1)), 0), (np.zeros((3, 1)), 1)]
    assert mrr(lambda X: [0, 1, 2], searches) == (1 + 1 / 2) / 2


def test_learned_weights_beat_simple_orders():
    test = made_up_searches(200, seed=2)
    learned = Ranker().fit(made_up_searches(300, seed=1))
    newest = lambda X: list(np.argsort(-X[:, FEATURES.index("recent")], kind="stable"))  # noqa: E731
    assert mrr(learned.order, test) >= MIN_LEARNED_MRR
    assert mrr(learned.order, test) > mrr(Ranker().order, test) > mrr(newest, test)


def test_load_falls_back_to_hand_weights(tmp_path):
    assert list(Ranker.load(tmp_path / "missing.json").weights) == list(Ranker().weights)
    (tmp_path / "old.json").write_text('{"features": ["something else"], "weights": [1]}')
    assert list(Ranker.load(tmp_path / "old.json").weights) == list(Ranker().weights)


def test_search_puts_your_own_recent_file_first(tmp_path):
    cache = tmp_path / "AppData" / "cache"
    docs = tmp_path / "Documents"
    old = tmp_path / "backup"
    for folder in (cache, docs, old):
        folder.mkdir(parents=True)
    (cache / "report_123.tmp").write_text("x")
    (old / "report (1).docx").write_text("x")
    (docs / "report.docx").write_text("x")
    os.utime(old / "report (1).docx", (NOW - 2000 * DAY, NOW - 2000 * DAY))
    result = ops.find(root=str(tmp_path), name="report")
    assert result.data["files"][0] == str(docs / "report.docx")


def test_search_skips_hidden_folders(tmp_path):
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "report.md").write_text("x")
    (tmp_path / "report.txt").write_text("x")
    assert ops.find(root=str(tmp_path), name="report").data["files"] == [str(tmp_path / "report.txt")]
