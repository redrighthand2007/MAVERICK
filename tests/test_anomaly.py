import numpy as np

from maverick.agents.process import ops
from maverick.agents.process.agent import ProcessAgent
from maverick.brain.anomaly import IsolationForest, average_path, reasons


def crowd_with_outliers(seed=0):
    """200 ordinary points in 4 numbers, plus 3 that are odd in just ONE number each."""
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, size=(200, 4))
    outliers = np.zeros((3, 4))
    outliers[0, 0], outliers[1, 2], outliers[2, 3] = 8, -8, 8
    return np.vstack([X, outliers])


def test_average_path_matches_the_paper():
    assert average_path(1) == 0 and average_path(2) == 1
    assert round(average_path(256), 2) == 10.24


def test_outliers_get_the_highest_scores():
    X = crowd_with_outliers()
    scores = IsolationForest().fit(X).scores(X)
    assert set(np.argsort(-scores)[:3]) == {200, 201, 202}
    # Odd in only ONE of 4 numbers: random cuts pick that column only 1 time in 4, so ~0.6, not ~0.9.
    assert scores[200:].min() > 0.55 > np.median(scores[:200])


def test_the_same_seed_gives_the_same_scores():
    X = crowd_with_outliers()
    assert np.allclose(IsolationForest(seed=1).fit(X).scores(X), IsolationForest(seed=1).fit(X).scores(X))


def test_identical_points_are_all_normal():
    X = np.ones((50, 3))
    scores = IsolationForest().fit(X).scores(X)
    assert np.allclose(scores, scores[0])


def test_reasons_name_the_odd_column():
    X = crowd_with_outliers()
    assert reasons(X, 201, ["a", "b", "c", "d"]) == ["c"]
    assert reasons(X, 5, ["a", "b", "c", "d"]) == []  # ordinary: nothing to explain


def test_features_judge_behaviour_not_size():
    one = {"ram": 100 * 1024 ** 2, "ram growth": 0, "cpu": 2, "threads": 20, "handles": 400, "connections": 2, "copies": 1}
    many = {key: value * 50 for key, value in one.items()} | {"ram growth": 0}  # 50 copies of the same program
    assert np.allclose(ops.featurize(one), ops.featurize(many))


def test_planted_fakes_each_change_one_habit():
    raw = [{"ram": r * 1024 ** 2, "ram growth": 0, "cpu": 1, "threads": 10, "handles": 200, "connections": 0, "copies": 1}
           for r in range(10, 30)]
    typical = ops.featurize(dict(raw[10], copies=1))
    for name, values in ops.planted_fakes(raw):
        changed = [c for c, a, b in zip(ops.COLUMNS, ops.featurize(values), typical) if abs(a - b) > 0.5]
        assert len(changed) >= 1, name


def fake_table(names_and_values):
    names = [n for n, _ in names_and_values]
    raw = [v for _, v in names_and_values]
    return lambda seconds: (names, [ops.featurize(v) for v in raw], raw)


def test_unusual_reports_the_odd_program(monkeypatch):
    rng = np.random.default_rng(3)
    programs = [(f"app{i}.exe", {"ram": int(rng.uniform(20, 200)) * 1024 ** 2, "ram growth": 0, "cpu": float(rng.uniform(0, 2)),
                                 "threads": int(rng.uniform(5, 40)), "handles": int(rng.uniform(100, 800)),
                                 "connections": int(rng.integers(0, 3)), "copies": 1}) for i in range(60)]
    chatty = dict(programs[0][1], connections=400)
    monkeypatch.setattr(ops, "program_table", fake_table(programs + [("chatty.exe", chatty)]))
    result = ops.unusual(seconds=3)
    assert result.success
    assert result.data["unusual"][0] == "chatty.exe"
    assert "400 network connections" in result.message


def test_unusual_with_nothing_odd(monkeypatch):
    same = {"ram": 50 * 1024 ** 2, "ram growth": 0, "cpu": 1.0, "threads": 10, "handles": 200, "connections": 0, "copies": 1}
    monkeypatch.setattr(ops, "program_table", fake_table([(f"app{i}.exe", same) for i in range(30)]))
    result = ops.unusual(seconds=3)
    assert result.data["unusual"] == [] and "none stands out" in result.message


def test_the_agent_understands_unusual_requests():
    agent = ProcessAgent()
    for text in ["any unusual programs running", "is anything suspicious on my pc", "which apps are acting weird"]:
        intent = agent.parse(text)
        assert intent is not None and intent.operation == "unusual", text
    assert agent.parse("watch for unusual programs for 30 seconds").args == {"seconds": 30}
    assert agent.parse("that odd file in downloads") is None  # "odd" alone isn't about programs
