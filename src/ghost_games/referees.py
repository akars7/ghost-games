"""Referee-side checks: booking rate per foul, and how each referee changed without fans.

Only the Premier League files name the referee.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def booking_rate_gap(matches: pd.DataFrame) -> float:
    """Away yellows per away foul minus home yellows per home foul.

    Fouls mostly measure how teams play; cards per foul mostly measure how strictly
    the referee punishes them. A positive gap = away fouls are punished more often.
    """
    m = matches.dropna(subset=["home_fouls", "away_fouls", "home_yellows", "away_yellows"])
    away = m["away_yellows"].sum() / m["away_fouls"].sum()
    home = m["home_yellows"].sum() / m["home_fouls"].sum()
    return float(away - home)


def referee_table(
    matches: pd.DataFrame, outcome: str = "card_gap", min_fans: int = 30, min_empty: int = 10
) -> pd.DataFrame:
    """One row per referee: home edge with fans, without fans, and the change.

    With 10-30 empty matches per referee, the raw change is very noisy: the most
    extreme referees are often just lucky or unlucky. shrunk_change pulls each
    referee toward the overall change, more strongly when their sample is small
    (empirical Bayes, the same idea as ridge in RAPM). Rank referees by that one.
    """
    data = matches.dropna(subset=["referee", outcome])
    data = data[data["crowd_status"].isin(["fans", "empty"])]
    grouped = data.groupby(["referee", "closed_doors"])[outcome].agg(["mean", "var", "count"])
    table = grouped.unstack("closed_doors")
    table.columns = [f"{stat}_{'empty' if empty else 'fans'}" for stat, empty in table.columns]
    table = table[(table["count_fans"] >= min_fans) & (table["count_empty"] >= min_empty)]
    if table.empty:
        raise ValueError("No referee has enough matches with fans and without fans")

    out = pd.DataFrame(
        {
            "matches_fans": table["count_fans"].astype(int),
            "matches_empty": table["count_empty"].astype(int),
            "edge_fans": table["mean_fans"],
            "edge_empty": table["mean_empty"],
        }
    )
    out["change"] = out["edge_empty"] - out["edge_fans"]
    # standard error of a difference of two means: sqrt(var1/n1 + var2/n2)
    out["se"] = np.sqrt(
        table["var_fans"] / table["count_fans"] + table["var_empty"] / table["count_empty"]
    )

    # how much referees truly differ = spread of the raw changes minus the noise in them
    overall = np.average(out["change"], weights=1 / out["se"] ** 2)
    true_spread = max(out["change"].var() - (out["se"] ** 2).mean(), 0.0)
    # weight near 1 = trust the referee's own number, near 0 = mostly noise, use overall
    weight = true_spread / (true_spread + out["se"] ** 2)
    out["shrunk_change"] = weight * out["change"] + (1 - weight) * overall
    out["trust_weight"] = weight
    return out.sort_values("shrunk_change").round(3)
