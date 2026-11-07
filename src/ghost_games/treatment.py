"""Label matches as fans / empty / partial.

Real attendance is used when we have it. The dates in config/closed_doors.csv
are the backup for matches with no attendance.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CONFIG_PATH = Path("config/closed_doors.csv")
VALID_STATUSES = {"empty", "partial"}


def load_windows(path: str | Path = CONFIG_PATH) -> pd.DataFrame:
    windows = pd.read_csv(path, comment="#", parse_dates=["start", "end"])
    bad = set(windows["status"]) - VALID_STATUSES
    if bad:
        raise ValueError(f"Unknown status values in {path}: {sorted(bad)}")
    if (windows["end"] < windows["start"]).any():
        raise ValueError("A window ends before it starts")
    return windows


def assign_crowd_status(matches: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    """Adds crowd_status and a 0/1 closed_doors flag.

    Leagues with no window are assumed to have had fans, and are listed in attrs.
    """
    out = matches.copy()
    out["crowd_status"] = "fans"

    for window in windows.itertuples(index=False):
        in_window = (
            (out["league"] == window.league)
            & (out["date"] >= window.start)
            & (out["date"] <= window.end)
        )
        out.loc[in_window, "crowd_status"] = window.status

    # not called "empty" because df.empty already exists in pandas
    out["closed_doors"] = (out["crowd_status"] == "empty").astype(int)
    out.attrs["leagues_without_windows"] = sorted(set(out["league"]) - set(windows["league"]))
    return out


def assign_crowd_status_from_attendance(
    matches: pd.DataFrame, windows: pd.DataFrame, partial_below: float = 0.6
) -> pd.DataFrame:
    """Status from attendance first, from the config dates only when attendance is missing.

    Needs the attendance and crowd_share columns (see attendance.py).
    0 fans = empty, crowd_share below partial_below = partial, otherwise fans.
    Adds status_from_dates and crowd_source so the two methods can be compared.
    """
    out = assign_crowd_status(matches, windows)
    out["status_from_dates"] = out["crowd_status"]

    # 0 fans is always usable; a positive number needs a normal crowd to compare with
    usable = (out["attendance"] == 0) | out["crowd_share"].notna()
    from_attendance = np.select(
        [out["attendance"] == 0, out["crowd_share"] < partial_below],
        ["empty", "partial"],
        default="fans",
    )
    out.loc[usable, "crowd_status"] = from_attendance[usable.to_numpy()]
    out["crowd_source"] = np.where(usable, "attendance", "dates")
    out["closed_doors"] = (out["crowd_status"] == "empty").astype(int)
    return out


def compare_with_dates(matches: pd.DataFrame) -> pd.DataFrame:
    """How often the config dates agree with real attendance (rows: dates, columns: attendance).

    Large numbers off the diagonal mean a window in closed_doors.csv is wrong.
    """
    checked = matches[matches["crowd_source"] == "attendance"]
    return pd.crosstab(
        checked["status_from_dates"], checked["crowd_status"], margins=True
    ).rename_axis(index="from dates", columns="from attendance")
