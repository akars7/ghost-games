"""Match attendance from FBref, joined to the football-data results.

Download once on your own machine (needs Chrome; FBref blocks fast scraping):

    pip install -e ".[fbref]"
    ghost-games-fetch-attendance

If soccerdata gets blocked, export the fixtures table from each FBref season
page (Share & Export > Get table as CSV) and save it as data/raw/attendance/E0_1920.csv.
"""

from __future__ import annotations

import argparse
import difflib
import re
import unicodedata
from pathlib import Path

import pandas as pd

ATTENDANCE_DIR = Path("data/raw/attendance")
TEAM_NAMES_PATH = Path("config/team_names.csv")

FBREF_LEAGUES = {
    "E0": "ENG-Premier League",
    "D1": "GER-Bundesliga",
    "SP1": "ESP-La Liga",
    "I1": "ITA-Serie A",
    "F1": "FRA-Ligue 1",
}
SEASONS = ["1516", "1617", "1718", "1819", "1920", "2021", "2122", "2223"]

# soccerdata output and the manual FBref export use different column names
COLUMN_MAP = {
    "date": "date",
    "Date": "date",
    "home_team": "home_team",
    "Home": "home_team",
    "away_team": "away_team",
    "Away": "away_team",
    "attendance": "attendance",
    "Attendance": "attendance",
}


def fetch_fbref(
    leagues: list[str] | None = None,
    seasons: list[str] | None = None,
    out_dir: Path = ATTENDANCE_DIR,
) -> None:
    """Save one CSV per league-season. Files that already exist are skipped."""
    import soccerdata as sd  # optional dependency, only needed here

    out_dir.mkdir(parents=True, exist_ok=True)
    for league in leagues or list(FBREF_LEAGUES):
        for season in seasons or SEASONS:
            path = out_dir / f"{league}_{season}.csv"
            if path.exists():
                continue
            # soccerdata opens a Chrome window to get past FBref's bot check
            reader = sd.FBref(leagues=FBREF_LEAGUES[league], seasons=season)
            schedule = reader.read_schedule().reset_index()
            columns = ["date", "home_team", "away_team", "attendance"]
            missing = set(columns) - set(schedule.columns)
            if missing:
                raise ValueError(f"FBref table for {league} {season} has no {sorted(missing)}")
            schedule[columns].to_csv(path, index=False)
            print(f"saved {path} ({len(schedule)} matches)")


def load_attendance(raw_dir: str | Path = ATTENDANCE_DIR) -> pd.DataFrame:
    """One row per match: league, date, home_team, away_team, attendance (FBref names)."""
    files = sorted(Path(raw_dir).glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No attendance CSVs in {raw_dir}")

    frames = []
    for path in files:
        df = pd.read_csv(path).rename(columns=COLUMN_MAP)
        missing = {"date", "home_team", "away_team", "attendance"} - set(df.columns)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
        # the league code comes from the file name, e.g. E0_1920.csv
        df["league"] = path.stem.split("_")[0]
        frames.append(df[["league", "date", "home_team", "away_team", "attendance"]])

    out = pd.concat(frames, ignore_index=True)
    # FBref exports have empty separator rows between match weeks
    out = out.dropna(subset=["home_team", "away_team"])
    out["date"] = pd.to_datetime(out["date"])
    # "52,152" -> 52152, empty -> NaN
    out["attendance"] = pd.to_numeric(
        out["attendance"].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    return out.reset_index(drop=True)


def _normalise(name: str) -> str:
    """Lowercase, no accents, no club suffixes like FC or AC."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    words = [w for w in text.split() if w not in {"fc", "afc", "cf", "ac", "as", "sc", "ss", "1"}]
    return " ".join(words)


def match_team_names(results: pd.DataFrame, attendance: pd.DataFrame) -> pd.DataFrame:
    """Map each FBref team name to the football-data name for the same club.

    Names differ a lot ("Wolves" vs "Wolverhampton Wanderers"), so spelling alone
    isn't enough. The main signal is the schedule: the same club plays on exactly
    the same dates in both sources. Spelling similarity only breaks ties.

    Returns league, fbref_name, results_name, date_overlap, similarity.
    Check rows with date_overlap below about 0.9 by hand.
    """
    rows = []
    for league, fb in attendance.groupby("league"):
        res = results[results["league"] == league]
        fb_dates = _dates_by_team(fb)
        res_dates = _dates_by_team(res)

        scored = []
        for fb_name, fb_set in fb_dates.items():
            for res_name, res_set in res_dates.items():
                overlap = len(fb_set & res_set) / len(fb_set)
                similarity = difflib.SequenceMatcher(
                    None, _normalise(fb_name), _normalise(res_name)
                ).ratio()
                scored.append((overlap + 0.1 * similarity, fb_name, res_name, overlap, similarity))

        # greedy one-to-one: best pairs first, each name used once
        used_fb, used_res = set(), set()
        for _, fb_name, res_name, overlap, similarity in sorted(scored, reverse=True):
            if fb_name in used_fb or res_name in used_res:
                continue
            used_fb.add(fb_name)
            used_res.add(res_name)
            rows.append((league, fb_name, res_name, round(overlap, 3), round(similarity, 3)))

    return pd.DataFrame(
        rows, columns=["league", "fbref_name", "results_name", "date_overlap", "similarity"]
    ).sort_values(["league", "date_overlap"])


def _dates_by_team(matches: pd.DataFrame) -> dict[str, set]:
    home = matches.groupby("home_team")["date"].apply(set)
    away = matches.groupby("away_team")["date"].apply(set)
    teams = set(home.index) | set(away.index)
    return {t: home.get(t, set()) | away.get(t, set()) for t in teams}


def apply_overrides(mapping: pd.DataFrame, path: str | Path = TEAM_NAMES_PATH) -> pd.DataFrame:
    """Manual fixes in config/team_names.csv win over the automatic matches."""
    path = Path(path)
    if not path.exists():
        return mapping
    overrides = pd.read_csv(path, comment="#")
    keys = ["league", "fbref_name"]
    kept = mapping.merge(overrides[keys], on=keys, how="left", indicator=True)
    kept = kept[kept["_merge"] == "left_only"].drop(columns="_merge")
    return pd.concat(
        [kept, overrides.assign(date_overlap=None, similarity=None)], ignore_index=True
    )


def merge_attendance(
    results: pd.DataFrame, attendance: pd.DataFrame, mapping: pd.DataFrame
) -> pd.DataFrame:
    """Add an attendance column to the results. Unmatched matches get NaN.

    The share of matches that got a value is stored in attrs["attendance_coverage"].
    """
    lookup = mapping.set_index(["league", "fbref_name"])["results_name"]
    att = attendance.copy()
    for side in ("home_team", "away_team"):
        keys = pd.MultiIndex.from_arrays([att["league"], att[side]])
        att[side] = lookup.reindex(keys).to_numpy()
    att = att.dropna(subset=["home_team", "away_team"])

    keys = ["league", "date", "home_team", "away_team"]
    att = att.drop_duplicates(subset=keys)
    out = results.merge(att[[*keys, "attendance"]], on=keys, how="left")
    out.attrs = dict(results.attrs)
    out.attrs["attendance_coverage"] = float(out["attendance"].notna().mean())
    return out


def add_crowd_share(
    matches: pd.DataFrame,
    covid_start: str = "2020-03-01",
    covid_end: str = "2021-08-01",
) -> pd.DataFrame:
    """crowd_share = attendance / the home team's normal crowd (median outside COVID).

    1.0 is a normal crowd, 0.3 is the 30% periods, 0 is an empty stadium.
    Teams with no normal matches in the data get NaN.
    """
    out = matches.copy()
    normal_period = (out["date"] < covid_start) | (out["date"] >= covid_end)
    normal_crowd = (
        out[normal_period & (out["attendance"] > 0)].groupby("home_team")["attendance"].median()
    )
    out["normal_crowd"] = out["home_team"].map(normal_crowd)
    # clip: a big derby can be above the median, but not far above
    out["crowd_share"] = (out["attendance"] / out["normal_crowd"]).clip(upper=1.5)
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download FBref attendance.")
    parser.add_argument("--leagues", nargs="+", default=list(FBREF_LEAGUES))
    parser.add_argument("--seasons", nargs="+", default=SEASONS)
    args = parser.parse_args(argv)
    fetch_fbref(args.leagues, args.seasons)


if __name__ == "__main__":
    main()
