import numpy as np
import pandas as pd
import pytest

from ghost_games.attendance import (
    add_crowd_share,
    apply_overrides,
    load_attendance,
    match_team_names,
    merge_attendance,
    save_by_season,
)
from ghost_games.model import fit_home_advantage
from ghost_games.treatment import assign_crowd_status_from_attendance, compare_with_dates

# same four clubs, spelled differently in each source
FBREF = ["Manchester City", "Wolverhampton Wanderers", "Arsenal", "Nottingham Forest"]
RESULTS = ["Man City", "Wolves", "Arsenal", "Nott'm Forest"]


def round_robin(names, start="2019-08-10"):
    """Every pair plays home and away, one match per date, so each team has its own dates."""
    rows, day = [], pd.Timestamp(start)
    for home in names:
        for away in names:
            if home != away:
                rows.append({"league": "E0", "date": day, "home_team": home, "away_team": away})
                day += pd.Timedelta(days=3)
    return pd.DataFrame(rows)


def test_load_manual_fbref_export(tmp_path):
    folder = tmp_path / "attendance"
    folder.mkdir()
    (folder / "E0_1920.csv").write_text(
        "Wk,Date,Home,Score,Away,Attendance,Venue\n"
        '1,2019-08-09,Liverpool,4–1,Norwich City,"53,333",Anfield\n'
        ",,,,,,\n"
        "2,2020-06-17,Aston Villa,0–0,Sheffield Utd,,Villa Park\n"
    )
    att = load_attendance(folder)
    assert list(att["league"]) == ["E0", "E0"]
    assert att["attendance"].iloc[0] == 53333
    assert np.isnan(att["attendance"].iloc[1])


def test_team_names_matched_by_schedule_not_spelling():
    fb = round_robin(FBREF)
    res = fb.replace(dict(zip(FBREF, RESULTS, strict=True)))
    mapping = match_team_names(res, fb).set_index("fbref_name")["results_name"]
    # "Wolves" looks nothing like "Wolverhampton Wanderers", the dates give it away
    assert mapping.to_dict() == dict(zip(FBREF, RESULTS, strict=True))


def test_overrides_replace_automatic_matches(tmp_path):
    mapping = pd.DataFrame(
        {
            "league": ["E0"],
            "fbref_name": ["Arsenal"],
            "results_name": ["Wrong"],
            "date_overlap": [0.5],
            "similarity": [0.1],
        }
    )
    path = tmp_path / "team_names.csv"
    path.write_text("league,fbref_name,results_name\nE0,Arsenal,Arsenal\n")
    fixed = apply_overrides(mapping, path)
    assert fixed.set_index("fbref_name").loc["Arsenal", "results_name"] == "Arsenal"
    assert len(fixed) == 1


def test_merge_fills_attendance_and_reports_coverage():
    fb = round_robin(FBREF).assign(attendance=30000.0)
    fb.loc[0, "attendance"] = np.nan
    res = fb.drop(columns="attendance").replace(dict(zip(FBREF, RESULTS, strict=True)))
    mapping = match_team_names(res, fb)
    merged = merge_attendance(res, fb, mapping)
    assert len(merged) == len(res)
    assert merged.attrs["attendance_coverage"] == pytest.approx(11 / 12)


def test_status_uses_attendance_and_falls_back_to_dates():
    matches = pd.DataFrame(
        {
            "league": ["E0"] * 6,
            "date": pd.to_datetime(
                ["2019-09-01", "2019-10-01", "2020-07-01", "2020-10-01", "2020-11-01", "2021-12-01"]
            ),
            "home_team": ["A"] * 6,
            "away_team": ["B"] * 6,
            "attendance": [40000, 42000, 0, 12000, np.nan, np.nan],
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
    out = assign_crowd_status_from_attendance(add_crowd_share(matches), windows)
    assert list(out["crowd_status"]) == ["fans", "fans", "empty", "partial", "empty", "unknown"]
    assert list(out["crowd_source"]) == ["attendance"] * 4 + ["dates", "none"]
    # the dates said "empty" for the 12,000 crowd: the check table shows that disagreement
    table = compare_with_dates(out)
    assert table.loc["empty", "partial"] == 1


def test_crowd_share_model_recovers_dose_effect():
    rng = np.random.default_rng(3)
    teams = [f"t{i}" for i in range(16)]
    strength = dict(zip(teams, rng.normal(0, 0.4, len(teams)), strict=True))
    rows = []
    for _ in range(6000):
        home, away = rng.choice(teams, 2, replace=False)
        share = rng.choice([0.0, 0.3, 1.0])
        goal_diff = 0.1 + 0.3 * share + strength[home] - strength[away] + rng.normal(0, 1.5)
        rows.append(
            {
                "league": "E0",
                "season": "2020-21",
                "home_team": home,
                "away_team": away,
                "crowd_share": share,
                "goal_diff": goal_diff,
            }
        )
    fit = fit_home_advantage(pd.DataFrame(rows), treatment="crowd_share")
    assert fit.effect == pytest.approx(0.3, abs=0.1)
    assert fit.home_adv == pytest.approx(0.1, abs=0.08)


def test_save_by_season_writes_one_file_per_season(tmp_path):
    schedule = pd.DataFrame(
        {
            "season": ["1920", "1920", "2021"],
            "date": ["2019-08-09", "2019-08-10", "2020-09-12"],
            "home_team": ["Liverpool", "Arsenal", "Fulham"],
            "away_team": ["Norwich City", "Burnley", "Arsenal"],
            "attendance": [53333, 60000, None],
        }
    )
    saved = save_by_season(schedule, "E0", tmp_path)
    assert [p.name for p in saved] == ["E0_1920.csv", "E0_2021.csv"]
    assert len(pd.read_csv(tmp_path / "E0_1920.csv")) == 2
