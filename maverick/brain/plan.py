"""Planning with utility scores (Stage 8.26): "free up 5 GB" -> which files, exactly?

A GOAL request: nobody says which files, only what they want in the end. MAVERICK has to choose.
Every candidate file has
  benefit: the space it frees (GB)
  regret:  how much you would probably miss it, 0 (temp junk) .. 1 (last week's photos)
and the plan is the set of files that frees AT LEAST the goal with the LEAST total regret.

That is a knapsack problem (pick items under a constraint, minimise a cost). Three ways to solve it:
  biggest first:  delete the largest files until the goal is met. Few files, but it happily takes your videos.
  greedy:         lowest regret per GB first. Usually good, sometimes takes a big file when a small one would do.
  optimal:        dynamic programming over "space still needed", which tries every combination without
                  trying them one by one: best[c] = the least regret that frees c more units.
Sizes are rounded to 16 MB units, so 5 GB is 320 steps and even 200 files plan in a blink.

Run:  python -m maverick.brain.plan     (compares the three on a made-up disk)
"""
import math
import random

UNIT = 16 * 1024 ** 2  # bytes per planning step


def biggest_first(items, goal: int) -> list[int]:
    """items: (size in bytes, regret). Returns indexes to delete."""
    return take_until(sorted(range(len(items)), key=lambda i: -items[i][0]), items, goal)


def greedy(items, goal: int) -> list[int]:
    return take_until(sorted(range(len(items)), key=lambda i: items[i][1] / max(items[i][0], 1)), items, goal)


def take_until(order, items, goal) -> list[int]:
    chosen, freed = [], 0
    for i in order:
        if freed >= goal:
            break
        chosen.append(i)
        freed += items[i][0]
    return chosen if freed >= goal else []


def optimal(items, goal: int) -> list[int]:
    """Least total regret that frees at least `goal` bytes; [] if all of them together aren't enough."""
    need = math.ceil(goal / UNIT)
    steps = [max(1, size // UNIT) for size, _ in items]  # round DOWN, so the plan never over-promises
    best = [0.0] + [math.inf] * need                      # best[c]: least regret that frees c more steps
    took = [[False] * (need + 1) for _ in items]
    for i, (step, (_, regret)) in enumerate(zip(steps, items)):
        for c in range(need, 0, -1):                       # backwards, so each file is used at most once
            option = best[max(0, c - step)] + regret
            if option < best[c]:
                best[c], took[i][c] = option, True
    if math.isinf(best[need]):
        return []
    chosen, c = [], need
    for i in range(len(items) - 1, -1, -1):               # walk the choices back from the goal
        if took[i][c]:
            chosen.append(i)
            c = max(0, c - steps[i])
    return sorted(chosen)


def total(items, chosen) -> tuple[int, float]:
    return sum(items[i][0] for i in chosen), sum(items[i][1] for i in chosen)


def made_up_disk(seed: int = 3) -> list[tuple[int, float]]:
    """40 candidates: lots of cheap junk, some big old installers and ISOs, and big recent videos/photos."""
    rng = random.Random(seed)
    GB = 1024 ** 3
    items = [(int(rng.uniform(0.05, 0.4) * GB), rng.uniform(0.0, 0.1)) for _ in range(15)]   # temp, caches
    items += [(int(rng.uniform(0.3, 2.5) * GB), rng.uniform(0.1, 0.3)) for _ in range(12)]  # old installers, ISOs
    items += [(int(rng.uniform(1.5, 6.0) * GB), rng.uniform(0.5, 0.85)) for _ in range(13)]  # videos, photo folders
    return items


def main() -> None:
    items = made_up_disk()
    GB = 1024 ** 3
    print(f"Made-up disk: {len(items)} candidates, {sum(s for s, _ in items) / GB:.1f} GB in all.")
    for goal_gb in (2, 5, 10, 20):
        print(f"\nGoal: free {goal_gb} GB")
        for name, method in [("biggest first", biggest_first), ("greedy (regret per GB)", greedy), ("optimal", optimal)]:
            chosen = method(items, goal_gb * GB)
            freed, regret = total(items, chosen)
            print(f"  {name:24} {len(chosen):2} files, frees {freed / GB:5.1f} GB, total regret {regret:.2f}")


if __name__ == "__main__":
    main()
