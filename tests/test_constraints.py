from maverick.agents.jobs.agent import JobsAgent, plan_maintenance
from maverick.brain.constraints import BEFORE, CSP, MAINTENANCE, Job, at_most, maintenance_csp, overlap
from maverick.core.background import Background

JOBS = {j.name: j for j in MAINTENANCE}


def rules_hold(answer, jobs=JOBS) -> bool:
    heavy = [n for n, j in jobs.items() if j.disk_heavy]
    for i, a in enumerate(heavy):
        for b in heavy[i + 1:]:
            if overlap(answer[a], jobs[a], answer[b], jobs[b]):
                return False
    return at_most(answer, jobs) and all(answer[a] + jobs[a].minutes <= answer[b] for a, b in BEFORE)


def test_a_tiny_csp():
    # Three people, three chairs, nobody shares one; Ann sits left of Bob.
    csp = CSP(["ann", "bob", "cat"], {v: [0, 1, 2] for v in ["ann", "bob", "cat"]},
              [("ann", "bob", lambda a, b: a < b), ("ann", "cat", lambda a, c: a != c), ("bob", "cat", lambda b, c: b != c)])
    for mrv, forward in [(False, False), (True, False), (False, True), (True, True)]:
        answer = csp.solve(mrv, forward)
        assert answer["ann"] < answer["bob"] and len(set(answer.values())) == 3


def test_every_search_finds_a_timetable_that_keeps_every_rule():
    for mrv, forward in [(False, False), (True, False), (False, True), (True, True)]:
        answer = maintenance_csp(23 * 60, 1 * 60).solve(mrv, forward)
        assert answer and rules_hold(answer)
        assert all(23 * 60 <= s and s + JOBS[n].minutes <= 25 * 60 for n, s in answer.items())


def test_an_impossible_window_has_no_answer():
    assert maintenance_csp(23 * 60, 23 * 60 + 45).solve() is None  # the 3 disk-heavy jobs need 60 minutes


def test_the_two_tricks_search_less_when_it_is_impossible():
    crowded = MAINTENANCE + [Job(f"extra {i}", 30, disk_heavy=True) for i in range(3)]
    plain = maintenance_csp(23 * 60, 75, crowded)
    both = maintenance_csp(23 * 60, 75, crowded)
    assert plain.solve(False, False) is None and both.solve(True, True) is None
    assert both.nodes * 10 < plain.nodes


def test_at_most_two_at_once():
    jobs = {"a": Job("a", 30), "b": Job("b", 30), "c": Job("c", 30)}
    assert at_most({"a": 0, "b": 0, "c": 30}, jobs)
    assert not at_most({"a": 0, "b": 15, "c": 15}, jobs)


def test_plan_maintenance_messages():
    good = plan_maintenance(22 * 60, 2 * 60)
    assert good.success and "plan only" in good.message and rules_hold(good.data["timetable"])
    bad = plan_maintenance(23 * 60, 23 * 60 + 30)
    assert not bad.success and "No timetable fits 23:00-23:30" in bad.message


def test_the_agent_reads_the_window():
    agent = JobsAgent(Background())
    assert agent.parse("schedule maintenance between 10 pm and 2 am").args == {"start": 22 * 60, "end": 2 * 60}
    assert agent.parse("plan maintenance from 23:00 to 01:30").args == {"start": 23 * 60, "end": 90}
    assert agent.parse("plan my maintenance").args == {"start": 23 * 60, "end": 60}
    assert agent.parse("when should my maintenance chores run").operation == "plan"
    assert agent.parse("stop job 2").operation == "stop"
