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


COVID_START = "2020-03-01"
COVID_END = "2022-06-30"


def assign_crowd_status_from_attendance(
    matches: pd.DataFrame,
    windows: pd.DataFrame,
    partial_below: float = 0.6,
    covid_start: str = COVID_START,
    covid_end: str = COVID_END,
) -> pd.DataFrame:
    """Status from attendance first, from the config dates only when attendance is missing.

    Needs the attendance and crowd_share columns (see attendance.py).
    0 fans = empty, crowd_share below partial_below = partial, otherwise fans.
    No attendance and no window = unknown (left out of the analysis).
    Partial is only possible between covid_start and covid_end.
    Adds status_from_dates and crowd_source so the two methods can be compared.
    """
    out = assign_crowd_status(matches, windows)
    out["status_from_dates"] = out["crowd_status"]

    # 0 fans is always usable; a positive number needs a normal crowd to compare with
    usable = (out["attendance"] == 0) | out["crowd_share"].notna()
    # small crowds outside COVID are low demand, not restrictions, so they stay "fans"
    covid = out["date"].between(covid_start, covid_end)
    from_attendance = np.select(
        [out["attendance"] == 0, covid & (out["crowd_share"] < partial_below)],
        ["empty", "partial"],
        default="fans",
    )
    out.loc[usable, "crowd_status"] = from_attendance[usable.to_numpy()]
    out["crowd_source"] = np.where(usable, "attendance", "dates")

    # no attendance and no window: the dates can't tell us anything, so don't guess "fans"
    no_window = ~usable & (out["status_from_dates"] == "fans")
    out.loc[no_window, "crowd_status"] = "unknown"
    out.loc[no_window, "crowd_source"] = "none"
    out["closed_doors"] = (out["crowd_status"] == "empty").astype(int)

    # crowd_level: only crowd changes forced by COVID rules. Outside COVID, crowd size
    # follows demand (good teams draw big crowds and also win), so it is set to 1.
    out["crowd_level"] = np.where(covid, out["crowd_share"].clip(upper=1), 1.0)
    out.loc[out["crowd_status"] == "empty", "crowd_level"] = 0.0
    return out


def compare_with_dates(matches: pd.DataFrame) -> pd.DataFrame:
    """How often the config dates agree with real attendance (rows: dates, columns: attendance).

    Large numbers off the diagonal mean a window in closed_doors.csv is wrong.
    """
    checked = matches[matches["crowd_source"] == "attendance"]
    return pd.crosstab(
        checked["status_from_dates"], checked["crowd_status"], margins=True
    ).rename_axis(index="from dates", columns="from attendance")
