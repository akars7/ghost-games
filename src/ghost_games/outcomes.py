"""Per-match outcomes from the home side's view (positive = home did better)."""

from __future__ import annotations

import numpy as np
import pandas as pd

OUTCOMES = {
    "goal_diff": "Home goals minus away goals",
    "home_points": "Points won by the home team (3/1/0)",
    "points_diff": "Home points minus away points (0 when there is no home edge)",
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
    # missing in some lower-league files, leave as NaN
    if {"home_yellows", "away_yellows"} <= set(out.columns):
        out["card_gap"] = out["away_yellows"] - out["home_yellows"]
    if {"home_fouls", "away_fouls"} <= set(out.columns):
        out["foul_gap"] = out["away_fouls"] - out["home_fouls"]
    return out
