import itertools
import os
import time

from maverick.agents.cleanup import ops
from maverick.agents.cleanup.agent import CleanupAgent
from maverick.brain.plan import UNIT, biggest_first, greedy, made_up_disk, optimal, total

GB = 1024 ** 3


def brute_force(items, goal):
    """Try every combination: the slow, sure answer the DP must match."""
    best = None
    for n in range(len(items) + 1):
        for combo in itertools.combinations(range(len(items)), n):
            freed, regret = total(items, combo)
            if freed >= goal and (best is None or regret < best[1]):
                best = (combo, regret)
    return best


def test_optimal_matches_brute_force():
    items = [(10 * UNIT, 0.5), (6 * UNIT, 0.1), (5 * UNIT, 0.2), (4 * UNIT, 0.05), (12 * UNIT, 0.9), (3 * UNIT, 0.3)]
    for goal in (3 * UNIT, 9 * UNIT, 15 * UNIT, 25 * UNIT):
        chosen = optimal(items, goal)
        assert total(items, chosen)[0] >= goal
        assert abs(total(items, chosen)[1] - brute_force(items, goal)[1]) < 1e-9


def test_impossible_goal_gives_no_plan():
    assert optimal([(UNIT, 0.1)], 5 * UNIT) == []
    assert greedy([(UNIT, 0.1)], 5 * UNIT) == []


def test_optimal_never_regrets_more_than_the_simple_ways():
    items = made_up_disk()
    for goal in (2 * GB, 5 * GB, 10 * GB, 20 * GB):
        best = total(items, optimal(items, goal))[1]
        assert best <= total(items, greedy(items, goal))[1] + 1e-9
        assert best <= total(items, biggest_first(items, goal))[1] + 1e-9


def test_regret_rules():
    now = time.time()
    home = ops.Path.home()
    assert ops.regret(home / "Downloads" / "setup.exe", now - 400 * 86400, now) == 0.0
    assert ops.regret(home / "Documents" / "photo.jpg", now - 5 * 86400, now) == 1.0
    assert ops.regret(home / "Videos" / "trip.mp4", now - 400 * 86400, now) == 0.5


def make(path, size, days_old):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(size)  # a sparse file: big on paper, no real disk space used
    old = time.time() - days_old * 86400
    os.utime(path, (old, old))


def test_free_shows_a_plan_and_deletes_exactly_it(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "old_temp_items", lambda now=None: [])
    recycled = []
    monkeypatch.setattr(ops, "send_to_recycle_bin", lambda items: recycled.extend(items))
    make(tmp_path / "old_installer.exe", 300 * 1024 ** 2, 400)
    make(tmp_path / "game.iso", 400 * 1024 ** 2, 300)
    make(tmp_path / "thesis.docx", 900 * 1024 ** 2, 2)       # recent document: never offered
    question = ops.describe_free(600 * 1024 ** 2, str(tmp_path))
    assert "old_installer.exe" in question and "game.iso" in question and "thesis.docx" not in question
    result = ops.free(600 * 1024 ** 2, str(tmp_path))
    assert result.success
    assert sorted(p.name for p in recycled) == ["game.iso", "old_installer.exe"]
    assert not ops.free(600 * 1024 ** 2, str(tmp_path)).success  # the approval is used up


def test_free_without_a_shown_plan_deletes_nothing(tmp_path, monkeypatch):
    recycled = []
    monkeypatch.setattr(ops, "send_to_recycle_bin", lambda items: recycled.extend(items))
    make(tmp_path / "big.iso", 300 * 1024 ** 2, 400)
    assert not ops.free(100 * 1024 ** 2, str(tmp_path)).success
    assert recycled == []


def test_not_enough_safe_space_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "old_temp_items", lambda now=None: [])
    make(tmp_path / "small.iso", 60 * 1024 ** 2, 400)
    assert "only find" in ops.describe_free(5 * GB, str(tmp_path))


def test_the_agent_understands_goals():
    agent = CleanupAgent()
    assert agent.parse("free up 5 gb").args == {"goal": 5 * GB, "root": ""}
    assert agent.parse("i need 10 GB of room on D:").args["root"] == "D:\\"
    assert agent.parse("make 500 mb of space").args["goal"] == 500 * 1024 ** 2
    assert agent.parse("free up space").operation == "scan"
    assert agent.is_risky(agent.parse("free up 5 gb"))
