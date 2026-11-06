import pytest

from maverick.agents.hardware import ops as hardware_ops


@pytest.fixture(autouse=True)
def private_disk_history(tmp_path, monkeypatch):
    """Every test gets its own disk history (8.24): tests that fake the drives must never write
    fake readings into the real ~/.maverick/disk_history.tsv."""
    monkeypatch.setattr(hardware_ops, "HISTORY_PATH", tmp_path / "disk_history.tsv")
