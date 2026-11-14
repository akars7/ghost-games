"""Build the analysis table in one call, so every notebook uses the same steps."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ghost_games.attendance import (
    add_crowd_share,
    apply_overrides,
    load_attendance,
    match_team_names,
    merge_attendance,
)
from ghost_games.data import load_matches
from ghost_games.outcomes import add_outcomes
from ghost_games.treatment import assign_crowd_status_from_attendance, load_windows


def build_matches(project_dir: str | Path = ".") -> pd.DataFrame:
    """Results + attendance + crowd status + outcomes, one row per match.

    project_dir is the ghost-games folder (use ".." from inside notebooks/).
    """
    root = Path(project_dir)
    results = load_matches(root / "data/raw")
    attendance = load_attendance(root / "data/raw/attendance")
    mapping = apply_overrides(match_team_names(results, attendance), root / "config/team_names.csv")
    matches = add_crowd_share(merge_attendance(results, attendance, mapping))
    windows = load_windows(root / "config/closed_doors.csv")
    return add_outcomes(assign_crowd_status_from_attendance(matches, windows))
