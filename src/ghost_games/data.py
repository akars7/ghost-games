"""Load football-data.co.uk CSVs from data/raw into one match table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")

COLUMN_MAP = {
    "Div": "league",
    "Date": "date",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "HY": "home_yellows",
    "AY": "away_yellows",
    "HR": "home_reds",
    "AR": "away_reds",
    "HF": "home_fouls",
    "AF": "away_fouls",
}
REQUIRED = ["league", "date", "home_team", "away_team", "home_goals", "away_goals"]


def season_of(date: pd.Timestamp) -> str:
    """Aug-May seasons, e.g. 2020-03-01 -> "2019-20"."""
    start_year = date.year if date.month >= 8 else date.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def season_from_filename(path: Path) -> str:
    """E0_1920.csv -> "2019-20"."""
    code = path.stem.split("_")[-1]
    if not (len(code) == 4 and code.isdigit()):
        raise ValueError(f"{path.name}: expected a name like E0_1920.csv")
    return f"20{code[:2]}-{code[2:]}"


def clean_matches(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=COLUMN_MAP)
    missing = [col for col in REQUIRED if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    keep = [col for col in [*COLUMN_MAP.values(), "season"] if col in df.columns]
    df = df[keep].dropna(subset=REQUIRED).copy()

    # older files use dd/mm/yy, newer ones dd/mm/yyyy
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, format="mixed")
    for col in df.columns.difference(["league", "date", "home_team", "away_team", "season"]):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # season from the file name when we have it: the dates are wrong for 2019-20,
    # which COVID pushed into August 2020
    if "season" not in df:
        df["season"] = df["date"].map(season_of)
    if df.duplicated(subset=["league", "date", "home_team", "away_team"]).any():
        raise ValueError("Duplicate matches found: was the same CSV saved twice?")
    return df.sort_values(["league", "date"]).reset_index(drop=True)


def load_matches(raw_dir: str | Path = RAW_DIR) -> pd.DataFrame:
    files = sorted(Path(raw_dir).glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSVs in {raw_dir}. See data/README.md for download steps.")
    # a failed download leaves an empty file, so name them instead of a confusing pandas error
    empty = [path.name for path in files if path.stat().st_size == 0]
    if empty:
        raise ValueError(f"Empty files, download them again: {', '.join(empty)}")
    # a few old files have non-utf8 bytes
    frames = [
        pd.read_csv(path, encoding_errors="replace").assign(season=season_from_filename(path))
        for path in files
    ]
    return clean_matches(pd.concat(frames, ignore_index=True))
