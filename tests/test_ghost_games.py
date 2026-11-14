import numpy as np
import pandas as pd
import pytest

from ghost_games.data import clean_matches, load_matches, season_of
from ghost_games.inference import bootstrap_gap, permutation_test
from ghost_games.model import fit_home_advantage, home_advantage_over_time
from ghost_games.outcomes import add_outcomes
from ghost_games.referees import booking_rate_gap, referee_table
from ghost_games.treatment import assign_crowd_status

TRUE_HOME_ADV = 0.35
TRUE_EMPTY_EFFECT = -0.25


def simulate_matches(seed: int = 0) -> pd.DataFrame:
    """Two seasons of a 20-team league, the second one played empty."""
    rng = np.random.default_rng(seed)
    teams = [f"team_{i}" for i in range(20)]
    rows = []
    for season_start, empty in [(2018, 0), (2019, 1)]:
        strength = dict(zip(teams, rng.normal(0, 0.5, len(teams)), strict=True))
        date = pd.Timestamp(f"{season_start}-08-10")
        for home in teams:
            for away in teams:
                if home == away:
                    continue
                for _ in range(3):  # 3 games per pair, so the estimate is more precise
                    expected = (
                        TRUE_HOME_ADV + TRUE_EMPTY_EFFECT * empty + strength[home] - strength[away]
                    )
                    rows.append(
                        {
                            "league": "E0",
                            "date": date,
                            "season": f"{season_start}-{str(season_start + 1)[-2:]}",
                            "home_team": home,
                            "away_team": away,
                            "goal_diff": expected + rng.normal(0, 1.6),
                            "closed_doors": empty,
                            "crowd_status": "empty" if empty else "fans",
                        }
                    )
    return pd.DataFrame(rows)


def test_model_recovers_true_effects():
    fit = fit_home_advantage(simulate_matches())
    assert fit.home_adv == pytest.approx(TRUE_HOME_ADV, abs=0.08)
    assert fit.effect == pytest.approx(TRUE_EMPTY_EFFECT, abs=0.1)
    assert fit.ci[0] < TRUE_EMPTY_EFFECT < fit.ci[1]
    low, high = fit.share_ci
    assert low < fit.share_of_advantage_lost < high
    assert low < -TRUE_EMPTY_EFFECT / TRUE_HOME_ADV < high
    assert fit.share_of_advantage_lost == pytest.approx(0.71, abs=0.3)


def test_model_requires_both_groups():
    only_fans = simulate_matches().query("closed_doors == 0")
    with pytest.raises(ValueError, match="only one value"):
        fit_home_advantage(only_fans)


def test_partial_crowds_are_excluded():
    df = simulate_matches()
    df.loc[df.index[:100], "crowd_status"] = "partial"
    assert fit_home_advantage(df).n_matches == len(df) - 100


def test_season_assignment():
    assert season_of(pd.Timestamp("2020-03-01")) == "2019-20"
    assert season_of(pd.Timestamp("2020-09-12")) == "2020-21"


def test_clean_matches_parses_mixed_dates_and_renames():
    raw = pd.DataFrame(
        {
            "Div": ["E0", "E0"],
            "Date": ["10/08/19", "17/08/2019"],
            "HomeTeam": ["A", "B"],
            "AwayTeam": ["B", "A"],
            "FTHG": [2, 0],
            "FTAG": [1, 0],
            "HY": [1, 2],
            "AY": [3, 2],
        }
    )
    clean = clean_matches(raw)
    assert list(clean["date"].dt.month) == [8, 8]
    assert {"home_goals", "away_yellows", "season"} <= set(clean.columns)


def test_clean_matches_rejects_duplicates():
    raw = pd.DataFrame(
        {
            "Div": ["E0"] * 2,
            "Date": ["10/08/19"] * 2,
            "HomeTeam": ["A"] * 2,
            "AwayTeam": ["B"] * 2,
            "FTHG": [1, 1],
            "FTAG": [0, 0],
        }
    )
    with pytest.raises(ValueError, match="Duplicate"):
        clean_matches(raw)


def test_outcomes_and_treatment_assignment():
    matches = pd.DataFrame(
        {
            "league": ["E0", "E0", "SP1"],
            "date": pd.to_datetime(["2020-01-01", "2020-07-01", "2020-07-01"]),
            "home_goals": [2, 1, 0],
            "away_goals": [0, 1, 1],
            "home_yellows": [1, 2, 3],
            "away_yellows": [3, 2, 1],
        }
    )
    windows = pd.DataFrame(
        {
            "league": ["E0"],
            "start": pd.to_datetime(["2020-06-17"]),
            "end": pd.to_datetime(["2021-05-17"]),
            "status": ["empty"],
        }
    )
    out = add_outcomes(assign_crowd_status(matches, windows))
    assert list(out["closed_doors"]) == [0, 1, 0]
    assert list(out["home_points"]) == [3, 1, 0]
    assert list(out["points_diff"]) == [3, 0, -3]
    assert list(out["card_gap"]) == [2, 0, -2]
    assert out.attrs["leagues_without_windows"] == ["SP1"]


def test_bootstrap_and_permutation_detect_real_gap():
    rng = np.random.default_rng(1)
    fans, empty = rng.normal(0.35, 1.6, 3000), rng.normal(0.05, 1.6, 3000)
    gap = bootstrap_gap(fans, empty, n_resamples=1000)
    assert gap.ci_high < 0
    assert permutation_test(fans, empty, n_permutations=500) < 0.01


def test_permutation_no_gap_is_not_significant():
    rng = np.random.default_rng(2)
    values = rng.normal(0, 1, 2000)
    assert permutation_test(values[:1000], values[1000:], n_permutations=500) > 0.05


def test_time_series_has_one_row_per_bucket():
    summary = home_advantage_over_time(simulate_matches(), freq="YS")
    assert {"mean", "ci_low", "ci_high", "share_empty"} <= set(summary.columns)


def test_empty_download_gives_clear_error(tmp_path):
    (tmp_path / "E0_1920.csv").write_text("")
    with pytest.raises(ValueError, match="E0_1920.csv"):
        load_matches(tmp_path)


def test_season_comes_from_file_name(tmp_path):
    # last round of Serie A 2019-20 was played in August 2020
    (tmp_path / "I1_1920.csv").write_text(
        "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\nI1,02/08/2020,Roma,Juventus,3,1\n"
    )
    assert load_matches(tmp_path)["season"].iloc[0] == "2019-20"


def test_robustness_outcomes():
    matches = pd.DataFrame({"home_goals": [6, 1, 0], "away_goals": [0, 1, 1]})
    out = add_outcomes(matches)
    assert list(out["goal_diff_capped"]) == [3, 0, -1]  # 6-0 counts as +3
    assert list(out["home_win"]) == [1, 0, 0]
    assert list(out["draw"]) == [0, 1, 0]
    assert list(out["away_win"]) == [0, 0, 1]
    assert list(out["home_points_edge"]) == [1.5, 0, -1.5]
    # the average edge equals home points above the no-edge level 1.5 - 0.5 * draw rate
    no_edge_level = 1.5 - 0.5 * out["draw"].mean()
    assert out["home_points_edge"].mean() == pytest.approx(
        (out["home_points"] - no_edge_level).mean()
    )


def test_booking_rate_gap():
    matches = pd.DataFrame(
        {
            "home_yellows": [1, 1],
            "away_yellows": [2, 2],
            "home_fouls": [10, 10],
            "away_fouls": [10, 10],
        }
    )
    assert booking_rate_gap(matches) == pytest.approx(0.1)  # 0.2 - 0.1 cards per foul


def test_referee_shrinkage_pulls_noisy_referees_to_the_middle():
    rng = np.random.default_rng(5)
    rows = []
    for ref in range(12):
        # every referee has the same true change (-0.3), so any spread is noise
        for empty, n in [(0, 60), (1, 15)]:
            for value in rng.normal(0.3 - 0.3 * empty, 1.5, n):
                rows.append(
                    {
                        "referee": f"ref{ref}",
                        "closed_doors": empty,
                        "card_gap": value,
                        "crowd_status": "empty" if empty else "fans",
                    }
                )
    table = referee_table(pd.DataFrame(rows), min_fans=30, min_empty=10)
    assert len(table) == 12
    # shrunk values are much closer together than the raw ones
    assert table["shrunk_change"].std() < table["change"].std() / 2
    assert table["shrunk_change"].mean() == pytest.approx(-0.3, abs=0.3)
