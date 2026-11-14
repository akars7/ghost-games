"""Home advantage controlling for team strength.

    outcome = home_adv + effect * treatment + strength[home] - strength[away]

treatment is either closed_doors (0/1) or crowd_level (0 = empty, 1 = normal crowd).

Strength is +1 for the home team and -1 for the away team (same idea as RAPM),
so it can't take credit for the home edge.

Adding the same number to every team's strength gives the same predictions,
so we drop one team per league-season and measure the others against it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm


@dataclass(frozen=True)
class HomeAdvantageFit:
    outcome: str
    treatment: str
    home_adv: float  # home edge when treatment = 0
    effect: float  # change in the home edge when treatment goes from 0 to 1
    ci: tuple[float, float]
    p_value: float
    n_matches: int
    # variance of home_adv, variance of effect, covariance of the two (for share_ci)
    cov: tuple[float, float, float] = (float("nan"), float("nan"), float("nan"))

    @property
    def share_of_advantage_lost(self) -> float:
        """e.g. 0.6 = empty stadiums removed 60% of the home edge."""
        if self.treatment == "closed_doors":
            # home_adv is the edge with fans; effect is how much empty stadiums change it
            with_fans = self.home_adv
            return -self.effect / with_fans if with_fans else float("nan")
        # for crowd_level, home_adv is the edge with no crowd; a full crowd adds effect
        with_fans = self.home_adv + self.effect
        return self.effect / with_fans if with_fans else float("nan")

    @property
    def share_ci(self) -> tuple[float, float]:
        """95% CI for share_of_advantage_lost, with the delta method.

        The share is a ratio of two estimates, so its uncertainty comes from both.
        The delta method uses the slope of the ratio with respect to each estimate
        (the gradient) and their covariance: var = g' * Cov * g.
        """
        h, e = self.home_adv, self.effect
        if self.treatment == "closed_doors":  # share = -e / h
            grad = np.array([e / h**2, -1 / h])
        else:  # share = e / (h + e)
            grad = np.array([-e / (h + e) ** 2, h / (h + e) ** 2])
        var_h, var_e, cov_he = self.cov
        cov_matrix = np.array([[var_h, cov_he], [cov_he, var_e]])
        se = float(np.sqrt(grad @ cov_matrix @ grad))
        share = self.share_of_advantage_lost
        return share - 1.96 * se, share + 1.96 * se


def build_design(matches: pd.DataFrame, treatment: str = "closed_doors") -> pd.DataFrame:
    """Columns: const, the treatment, then one +1/-1 column per team-season."""
    home_key = matches["home_team"] + " | " + matches["season"]
    away_key = matches["away_team"] + " | " + matches["season"]
    teams = sorted(set(home_key) | set(away_key))

    # fill a numpy array first: editing pandas values in place can fail (read-only view)
    team_index = pd.Index(teams)
    rows = np.arange(len(matches))
    values = np.zeros((len(matches), len(teams)))
    values[rows, team_index.get_indexer(home_key)] += 1.0
    values[rows, team_index.get_indexer(away_key)] -= 1.0
    strength = pd.DataFrame(values, index=matches.index, columns=teams)

    # drop one reference team per league-season
    appearances = pd.concat(
        [
            pd.DataFrame(
                {"key": home_key, "league": matches["league"], "season": matches["season"]}
            ),
            pd.DataFrame(
                {"key": away_key, "league": matches["league"], "season": matches["season"]}
            ),
        ]
    ).drop_duplicates("key")
    reference_teams = appearances.groupby(["league", "season"])["key"].min()
    strength = strength.drop(columns=reference_teams.to_list())

    design = pd.DataFrame(
        {"const": 1.0, treatment: matches[treatment].astype(float)}, index=matches.index
    )
    return pd.concat([design, strength], axis=1)


def fit_home_advantage(
    matches: pd.DataFrame,
    outcome: str = "goal_diff",
    treatment: str = "closed_doors",
    exclude_partial: bool | None = None,
) -> HomeAdvantageFit:
    """Linear regression with robust standard errors (HC1).

    With closed_doors, partial-crowd games are left out by default (they are
    neither full nor empty). With crowd_level they are kept, because the crowd
    size is measured directly.
    """
    if exclude_partial is None:
        exclude_partial = treatment == "closed_doors"
    data = matches
    if "crowd_status" in data:
        data = data[data["crowd_status"] != "unknown"]
    if exclude_partial and "crowd_status" in data:
        data = data[data["crowd_status"] != "partial"]
    data = data.dropna(subset=[outcome, treatment])
    if data[treatment].nunique() < 2:
        raise ValueError(f"{treatment} has only one value, so its effect can't be estimated")

    design = build_design(data, treatment)
    result = sm.OLS(data[outcome].astype(float), design).fit(cov_type="HC1")
    ci_low, ci_high = result.conf_int().loc[treatment]
    return HomeAdvantageFit(
        outcome=outcome,
        treatment=treatment,
        home_adv=float(result.params["const"]),
        effect=float(result.params[treatment]),
        ci=(float(ci_low), float(ci_high)),
        p_value=float(result.pvalues[treatment]),
        n_matches=int(len(data)),
        cov=(
            float(result.cov_params().loc["const", "const"]),
            float(result.cov_params().loc[treatment, treatment]),
            float(result.cov_params().loc["const", treatment]),
        ),
    )


def home_advantage_over_time(
    matches: pd.DataFrame, outcome: str = "goal_diff", freq: str = "QS"
) -> pd.DataFrame:
    """Mean outcome and 95% CI per period, for the event-study chart."""
    grouped = matches.dropna(subset=[outcome]).groupby(pd.Grouper(key="date", freq=freq))
    summary = grouped[outcome].agg(["mean", "std", "count"])
    summary = summary[summary["count"] > 1]
    half_width = 1.96 * summary["std"] / np.sqrt(summary["count"])
    summary["ci_low"] = summary["mean"] - half_width
    summary["ci_high"] = summary["mean"] + half_width
    share_empty = grouped["closed_doors"].mean()
    summary["share_empty"] = share_empty.reindex(summary.index)
    return summary.reset_index()
