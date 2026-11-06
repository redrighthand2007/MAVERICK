"""Regression and forecasting (Stage 8.24): "C: will be full in about 3 weeks".

Every model so far predicted a CATEGORY (files.copy, cut / keep, which group). Regression predicts a NUMBER.
The simplest kind draws the straight line  used = intercept + slope * day  that fits the history best:
"best" = the smallest sum of squared misses (least squares). It has an exact answer, no training loop needed:
  slope     = sum((x - mean x)(y - mean y)) / sum((x - mean x)^2)
  intercept = mean y - slope * mean x
Then forecasting is just following the line until it reaches the drive's size.

Two honesty checks come with it:
  R²: how much of the up-and-down the line explains (1 = every point on the line, 0 = no better than the average)
  slope range: the slope's standard error says how sure we are about the rate; ±2 of them is the range we report
And a warning that no model fixes: a straight line assumes you keep using the disk like you did lately.

Run:  python -m maverick.brain.forecast     (backtest on a made-up 60-day disk history, with a known answer)
"""
import numpy as np


class LinearRegression:
    def __init__(self):
        self.slope = self.intercept = self.r2 = 0.0
        self.slope_error = float("inf")

    def fit(self, x, y) -> "LinearRegression":
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        dx, dy = x - x.mean(), y - y.mean()
        self.slope = float((dx * dy).sum() / (dx ** 2).sum())
        self.intercept = float(y.mean() - self.slope * x.mean())
        misses = y - self.predict(x)
        total = (dy ** 2).sum()
        self.r2 = float(1 - (misses ** 2).sum() / total) if total > 0 else 1.0
        if len(x) > 2:
            self.slope_error = float(np.sqrt((misses ** 2).sum() / (len(x) - 2) / (dx ** 2).sum()))
        return self

    def predict(self, x):
        return self.intercept + self.slope * np.asarray(x, dtype=float)

    def slope_range(self) -> tuple[float, float]:
        """About 95% sure the real rate is in here (slope ± 2 standard errors)."""
        return self.slope - 2 * self.slope_error, self.slope + 2 * self.slope_error


def made_up_history(days: int = 60, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """A disk that grows ~0.6 GB a day with daily noise, plus a 15 GB clean-up on day 40: like a real one."""
    rng = np.random.default_rng(seed)
    x = np.arange(days, dtype=float)
    y = 300 + 0.6 * x + rng.normal(0, 1.5, days)
    y[40:] -= 15
    return x, y


def backtest(x, y, test_days: int = 14) -> dict[str, float]:
    """Hide the last two weeks, forecast them from what came before, and measure the average miss in GB."""
    train_x, train_y, test_x, test_y = x[:-test_days], y[:-test_days], x[-test_days:], y[-test_days:]
    window = train_x >= train_x[-1] - 30
    line = LinearRegression().fit(train_x[window], train_y[window])
    last_jump = train_y[-1] - train_y[-2]  # the naive rule: "it keeps changing like it did yesterday"
    return {
        "linear regression (last 30 days)": float(np.abs(line.predict(test_x) - test_y).mean()),
        "same as yesterday's change": float(np.abs(train_y[-1] + last_jump * (test_x - train_x[-1]) - test_y).mean()),
        "no change at all": float(np.abs(train_y[-1] - test_y).mean()),
    }


def main() -> None:
    x, y = made_up_history()
    print("Backtest on a made-up 60-day disk (grows ~0.6 GB/day, one 15 GB clean-up):")
    print("Forecast the last 14 days from the 46 before them; average miss:")
    for name, miss in backtest(x, y).items():
        print(f"  {name:34} {miss:5.1f} GB")
    from maverick.agents.hardware.ops import HISTORY_PATH, forecast
    print(f"\nYour real history ({HISTORY_PATH}):")
    print("  " + forecast("C:").message)


if __name__ == "__main__":
    main()
