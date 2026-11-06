"""Constraint solving (Stage 8.27): a timetable where every rule holds at once.

A constraint satisfaction problem (CSP) has
  variables:   the things to decide (when each job starts)
  domains:     the values each may take (every 15-minute slot in the window that leaves room to finish)
  constraints: rules between them ("these two never overlap", "clear temp before the junk scan")
A solution gives every variable a value with no rule broken. There's no score to maximise: it fits or it doesn't.

Backtracking search: pick a job, try its first slot, go on to the next job; when a rule breaks, undo the
last choice and try its next slot. Two classic tricks make that search much smaller:
  most constrained first (MRV): decide the job with the FEWEST slots left first; it's the likeliest to get stuck
  forward checking:             after each choice, cross out the slots it rules out for the other jobs;
                                if some job has none left, back up at once instead of finding out 3 levels later
`nodes` counts the choices tried, to show the difference.

Run:  python -m maverick.brain.constraints     (plain backtracking vs the two tricks on a crowded night)
"""
from dataclasses import dataclass, field


@dataclass
class CSP:
    variables: list[str]
    domains: dict[str, list[int]]
    # (a, b, ok): ok(value of a, value of b) must be True whenever both a and b have a value
    constraints: list[tuple[str, str, object]] = field(default_factory=list)
    # A rule about many variables at once (e.g. "at most 2 jobs at the same time"), checked on the full answer.
    whole: object = None
    nodes: int = 0

    def consistent(self, var: str, value: int, assignment: dict) -> bool:
        for a, b, ok in self.constraints:
            if a == var and b in assignment and not ok(value, assignment[b]):
                return False
            if b == var and a in assignment and not ok(assignment[a], value):
                return False
        return True

    def solve(self, mrv: bool = True, forward: bool = True) -> dict[str, int] | None:
        self.nodes = 0
        return self.search({}, {v: list(d) for v, d in self.domains.items()}, mrv, forward)

    def search(self, assignment, domains, mrv, forward):
        if len(assignment) == len(self.variables):
            return dict(assignment) if self.whole is None or self.whole(assignment) else None
        left = [v for v in self.variables if v not in assignment]
        var = min(left, key=lambda v: len(domains[v])) if mrv else left[0]
        for value in domains[var]:
            self.nodes += 1
            if not self.consistent(var, value, assignment):
                continue
            assignment[var] = value
            pruned = self.prune(var, value, assignment, domains) if forward else domains
            if pruned is not None:
                found = self.search(assignment, pruned, mrv, forward)
                if found:
                    return found
            del assignment[var]
        return None

    def prune(self, var, value, assignment, domains):
        """Forward checking: keep only the values of unassigned variables still possible after var = value."""
        new = dict(domains)
        for other in self.variables:
            if other in assignment:
                continue
            keep =[x for x in domains[other] if self.pair_ok(var, value, other, x)]
            if not keep:
                return None  # a job with no slot left: this choice can't work
            new[other] = keep
        return new

    def pair_ok(self, a, va, b, vb) -> bool:
        for x, y, ok in self.constraints:
            if (x, y) == (a, b) and not ok(va, vb):
                return False
            if (x, y) == (b, a) and not ok(vb, va):
                return False
        return True


# --- MAVERICK's maintenance jobs ---

SLOT = 15  # minutes


@dataclass(frozen=True)
class Job:
    name: str
    minutes: int
    disk_heavy: bool = False


MAINTENANCE = [
    Job("clear old temp files", 15, disk_heavy=True),
    Job("scan for junk (free up space)", 30, disk_heavy=True),
    Job("record disk usage (8.24)", 15),
    Job("check for unusual programs (8.22)", 15),
    Job("check log sizes", 15, disk_heavy=True),
]
BEFORE = [("clear old temp files", "scan for junk (free up space)"),   # scan what's left after the clean-up
          ("scan for junk (free up space)", "record disk usage (8.24)")]  # record the disk after both
MAX_AT_ONCE = 2


def overlap(start_a: int, job_a: Job, start_b: int, job_b: Job) -> bool:
    return start_a < start_b + job_b.minutes and start_b < start_a + job_a.minutes


def maintenance_csp(window_start: int, window_end: int, jobs=MAINTENANCE) -> CSP:
    """Minutes since midnight; a window past midnight (23:00-02:00) just runs on past 1440."""
    if window_end <= window_start:
        window_end += 24 * 60
    by_name = {j.name: j for j in jobs}
    domains = {j.name: list(range(window_start, window_end - j.minutes + 1, SLOT)) for j in jobs}
    constraints = []
    for i, a in enumerate(jobs):
        for b in jobs[i + 1:]:
            if a.disk_heavy and b.disk_heavy:  # two disk-heavy jobs at once slow each other (and you) down
                constraints.append((a.name, b.name, lambda sa, sb, a=a, b=b: not overlap(sa, a, sb, b)))
    for first, then in BEFORE:
        constraints.append((first, then, lambda sa, sb, f=by_name[first]: sa + f.minutes <= sb))
    return CSP([j.name for j in jobs], domains, constraints, whole=lambda answer: at_most(answer, by_name))


def at_most(solution: dict[str, int], jobs: dict[str, Job], limit: int = MAX_AT_ONCE) -> bool:
    """A rule about 3+ jobs at once can't be written as pairs; checked on the finished timetable."""
    for t in set(solution.values()):
        if sum(1 for n, s in solution.items() if s <= t < s + jobs[n].minutes) > limit:
            return False
    return True


def clock(minutes: int) -> str:
    return f"{minutes // 60 % 24:02d}:{minutes % 60:02d}"


def main() -> None:
    crowded = MAINTENANCE + [Job(f"extra disk job {i}", 30, disk_heavy=True) for i in range(1, 4)]
    print("8 jobs (6 disk-heavy, never together; at most 2 at once; clear temp -> scan -> record), from 23:00.")
    print("Choices tried by each search (x = proved that no timetable fits):")
    ways = [("plain", False, False), ("MRV", True, False), ("forward", False, True), ("both", True, True)]
    print(f"  {'until':8}" + "".join(f"{name:>10}" for name, _, _ in ways))
    for end in (2 * 60, 90, 75, 60):
        row = ""
        for _, mrv, forward in ways:
            csp = maintenance_csp(23 * 60, end, crowded)
            found = csp.solve(mrv, forward)
            row += f"{csp.nodes:>9,}{' ' if found else 'x'}"
        print(f"  {clock(end):8}{row}")
    print("MRV alone can be WORSE: without forward checking no slot is ever crossed out, so 'fewest slots left'")
    print("only looks at the original windows. Together they prove an impossible night ~280x faster.")


if __name__ == "__main__":
    main()
