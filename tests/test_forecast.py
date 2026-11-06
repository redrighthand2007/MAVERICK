import numpy as np

from maverick.agents.hardware import ops
from maverick.agents.hardware.agent import HardwareAgent
from maverick.brain.forecast import LinearRegression, backtest, made_up_history

GB = 1024 ** 3
DAY = 86400
NOW = 1_800_000_000.0


def test_a_perfect_line_is_found_exactly():
    line = LinearRegression().fit([0, 1, 2, 3], [5, 7, 9, 11])
    assert round(line.slope, 6) == 2 and round(line.intercept, 6) == 5 and round(line.r2, 6) == 1
    assert line.predict(10) == 25


def test_r2_is_low_for_noise():
    rng = np.random.default_rng(0)
    assert LinearRegression().fit(np.arange(50), rng.normal(0, 1, 50)).r2 < 0.2


def test_the_slope_range_contains_the_true_rate():
    x, y = made_up_history()
    low, high = LinearRegression().fit(x[:40], y[:40]).slope_range()
    assert low < 0.6 < high


def test_the_line_beats_the_naive_rules_in_the_backtest():
    misses = backtest(*made_up_history())
    line = misses["linear regression (last 30 days)"]
    assert line < misses["no change at all"] and line < misses["same as yesterday's change"]


def history(tmp_path, readings, drive="C:", total=500 * GB):
    """readings: (days ago, used GB)"""
    path = tmp_path / "disk_history.tsv"
    for days_ago, used_gb in readings:
        ops.record_disks(path, NOW - days_ago * DAY, usage=[(drive, int(used_gb * GB), total)])
    return path


def test_record_waits_an_hour_between_rows(tmp_path):
    path = tmp_path / "h.tsv"
    assert ops.record_disks(path, NOW, usage=[("C:", 1, 2), ("D:", 1, 2)]) == 2
    assert ops.record_disks(path, NOW + 600, usage=[("C:", 1, 2)]) == 0
    assert ops.record_disks(path, NOW + 3600, usage=[("C:", 1, 2)]) == 1
    assert len(ops.read_history(path)) == 3


def test_forecast_days_until_full(tmp_path):
    # 1 GB a day, 400 of 500 GB used today: full in about 100 days.
    path = history(tmp_path, [(d, 400 - d) for d in range(20, -1, -1)])
    result = ops.forecast("C", path, now=NOW)
    assert result.success
    assert round(result.data["days"]) == 100 and round(result.data["per_day_gb"], 2) == 1.0
    assert "3 months" in result.message and "steady" in result.message


def test_a_shrinking_disk_is_not_filling_up(tmp_path):
    path = history(tmp_path, [(d, 300 + d) for d in range(10, -1, -1)])
    assert "isn't filling up" in ops.forecast("C:", path, now=NOW).message


def test_too_little_history_says_so(tmp_path):
    path = history(tmp_path, [(0.5, 300), (0, 301)])
    result = ops.forecast("C:", path, now=NOW)
    assert result.data["days"] is None and "Not enough history" in result.message
    assert "No history for D:" in ops.forecast("D:", path, now=NOW).message


def test_old_readings_are_ignored(tmp_path):
    # Fast growth 60 days ago, flat for the last 30: only the recent past counts.
    path = history(tmp_path, [(d, 100 + 5 * (60 - d)) for d in range(60, 31, -1)] + [(d, 300) for d in range(29, -1, -1)])
    assert "isn't filling up" in ops.forecast("C:", path, now=NOW).message


def test_the_agent_understands_forecast_requests():
    agent = HardwareAgent()
    assert agent.parse("when will my D drive be full").args == {"drive": "D:"}
    assert agent.parse("how fast is my disk filling up").operation == "forecast"
    assert agent.parse("space left on D:").operation == "disks"
