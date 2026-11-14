"""Per-match outcomes from the home side's view (positive = home did better)."""

from __future__ import annotations

import numpy as np
import pandas as pd

# biggest goal difference that counts in goal_diff_capped, so one 6-0 can't dominate an average
GOAL_DIFF_CAP = 3

OUTCOMES = {
    "goal_diff": "Home goals minus away goals",
    "goal_diff_capped": f"Goal difference limited to -{GOAL_DIFF_CAP}..+{GOAL_DIFF_CAP}",
    "home_points": "Points won by the home team (3/1/0)",
    "points_diff": "Home points minus away points (0 when there is no home edge)",
    "home_points_edge": "Home points above the no-edge level (= points_diff / 2)",
    "home_win": "1 if the home team won, else 0 (its mean is the home win rate)",
    "draw": "1 if the match was a draw, else 0",
    "away_win": "1 if the away team won, else 0",
    "card_gap": "Away yellows minus home yellows (referee leaning toward the home side)",
    "foul_gap": "Away fouls minus home fouls",
}


def add_outcomes(matches: pd.DataFrame) -> pd.DataFrame:
    out = matches.copy()
    out["goal_diff"] = out["home_goals"] - out["away_goals"]
    out["home_points"] = np.select([out["goal_diff"] > 0, out["goal_diff"] == 0], [3, 1], default=0)
    away_points = np.select([out["goal_diff"] < 0, out["goal_diff"] == 0], [3, 1], default=0)
    # use this one in models: home_points is about 1.4 even with no home edge, this is 0
    out["points_diff"] = out["home_points"] - away_points
    # per match this isn't "points above 1.37", but its average is exactly that (METHODS 2.5)
    out["home_points_edge"] = out["points_diff"] / 2

    out["goal_diff_capped"] = out["goal_diff"].clip(-GOAL_DIFF_CAP, GOAL_DIFF_CAP)

    # 0/1 columns: their average is a rate, e.g. mean of home_win = home win rate
    out["home_win"] = (out["goal_diff"] > 0).astype(int)
    out["draw"] = (out["goal_diff"] == 0).astype(int)
    out["away_win"] = (out["goal_diff"] < 0).astype(int)

    # missing in some lower-league files, leave as NaN
    if {"home_yellows", "away_yellows"} <= set(out.columns):
        out["card_gap"] = out["away_yellows"] - out["home_yellows"]
    if {"home_fouls", "away_fouls"} <= set(out.columns):
        out["foul_gap"] = out["away_fouls"] - out["home_fouls"]
    return out
