"""Did betting odds see the drop in home advantage? Market check, no betting advice."""

from __future__ import annotations

import numpy as np
import pandas as pd

FIRST_WEEKS_DAYS = 60


def add_market_prob(matches: pd.DataFrame) -> pd.DataFrame:
    """Add the market's home-win probability and the surprise (actual - predicted).

    1/odds gives a probability, but the three add up to about 1.05: the extra
    is the bookmaker's margin. Dividing by the sum removes it.
    """
    out = matches.copy()
    inverse = 1 / out[["odds_home", "odds_draw", "odds_away"]]
    out["market_margin"] = inverse.sum(axis=1) - 1
    out["market_p_home"] = inverse["odds_home"] / inverse.sum(axis=1)
    # positive = home teams won more often than the odds said
    out["market_surprise"] = out["home_win"] - out["market_p_home"]
    return out


def label_period(matches: pd.DataFrame, first_weeks_days: int = FIRST_WEEKS_DAYS) -> pd.Series:
    """'fans', 'empty: first weeks' or 'empty: later' (days from the league's first empty match)."""
    empty = matches["closed_doors"] == 1
    first_empty = matches[empty].groupby("league")["date"].min()
    days_in = (matches["date"] - matches["league"].map(first_empty)).dt.days
    period = pd.Series("fans", index=matches.index)
    period[empty & (days_in < first_weeks_days)] = "empty: first weeks"
    period[empty & (days_in >= first_weeks_days)] = "empty: later"
    return period


def market_check(matches: pd.DataFrame, n_resamples: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Mean predicted vs actual home-win rate per period, with a bootstrap CI for the gap."""
    df = add_market_prob(matches)
    df = df[df["crowd_status"].isin(["fans", "empty"])].dropna(subset=["market_p_home"])
    df = df.assign(period=label_period(df))

    rng = np.random.default_rng(seed)
    rows = []
    for period, group in df.groupby("period"):
        surprise = group["market_surprise"].to_numpy()
        # resample matches, keep the mean surprise each time
        boot = rng.choice(surprise, size=(n_resamples, surprise.size)).mean(axis=1)
        low, high = np.quantile(boot, [0.025, 0.975])
        rows.append(
            {
                "period": period,
                "matches": len(group),
                "predicted": group["market_p_home"].mean(),
                "actual": group["home_win"].mean(),
                "gap": surprise.mean(),
                "ci_low": low,
                "ci_high": high,
            }
        )
    return pd.DataFrame(rows).set_index("period")
