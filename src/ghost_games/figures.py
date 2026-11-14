"""The three README charts. Each function returns a matplotlib figure."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ghost_games.model import fit_home_advantage, home_advantage_over_time

# colours checked for colour-blind safety (dataviz validator, light background)
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_MUTED = "#52514e"
GRID = "#e4e3df"
FANS = "#2a78d6"  # blue
EMPTY = "#eb6834"  # orange

LEAGUES = {
    "E0": "Premier League",
    "D1": "Bundesliga",
    "SP1": "La Liga",
    "I1": "Serie A",
    "F1": "Ligue 1",
}
AXIS_LABELS = {
    "goal_diff": "Goals per match (home minus away)",
    "card_gap": "Yellow cards per match (away minus home)",
}
OUTCOME_LABELS = {
    "goal_diff": "Goal difference",
    "goal_diff_capped": "Goal difference (capped at ±3)",
    "points_diff": "Points difference",
    "card_gap": "Yellow card gap (referee)",
}


def _new_figure(width: float, height: float):
    fig, ax = plt.subplots(figsize=(width, height), facecolor=SURFACE)
    _style(ax)
    return fig, ax


def _style(ax) -> None:
    """Light grid, no box: the data should be the darkest thing on the chart."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_MUTED, labelsize=9)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _titles(fig, title: str, subtitle: str) -> None:
    fig.text(0.01, 0.97, title, fontsize=13, fontweight="bold", color=TEXT, va="top")
    fig.text(0.01, 0.905, subtitle, fontsize=9.5, color=TEXT_MUTED, va="top")


def plot_over_time(matches: pd.DataFrame, outcome: str = "goal_diff"):
    """Chart 1: home advantage per quarter, with empty-stadium periods shaded."""
    summary = home_advantage_over_time(matches, outcome, freq="QS")
    fig, ax = _new_figure(9, 4.6)

    # one shaded block per run of mostly-empty quarters (one block per quarter leaves white seams)
    empty = (summary["share_empty"] > 0.5).to_numpy()
    starts = summary["date"].to_numpy()
    run_ids = np.cumsum(np.r_[True, empty[1:] != empty[:-1]])
    for run in np.unique(run_ids[empty]):
        quarters = starts[run_ids == run]
        ax.axvspan(quarters[0], quarters[-1] + np.timedelta64(91, "D"), color=GRID, alpha=0.7, lw=0)

    ax.fill_between(
        summary["date"], summary["ci_low"], summary["ci_high"], color=FANS, alpha=0.15, lw=0
    )
    ax.plot(summary["date"], summary["mean"], color=FANS, lw=2, marker="o", ms=4)
    ax.axhline(0, color=TEXT_MUTED, lw=0.8)

    first_empty = starts[np.flatnonzero(empty)[0]]
    ax.text(
        first_empty,
        ax.get_ylim()[1] * 0.95,
        " Mostly empty\n stadiums",
        color=TEXT_MUTED,
        fontsize=9,
        va="top",
    )
    ax.set_ylabel(f"Mean home {OUTCOME_LABELS[outcome].lower()}", color=TEXT_MUTED, fontsize=9.5)
    ax.set_xlabel("Quarter", color=TEXT_MUTED, fontsize=9.5)
    _titles(
        fig,
        "Home advantage dropped when stadiums emptied",
        "Mean home goal difference per quarter, top 5 European leagues 2015–2023, with 95% CI",
    )
    fig.subplots_adjust(top=0.82, left=0.08, right=0.98, bottom=0.12)
    return fig


def plot_share_lost(matches: pd.DataFrame, outcomes=tuple(OUTCOME_LABELS)):
    """Chart 2: share of the home edge lost in empty stadiums, one row per outcome."""
    fits = [fit_home_advantage(matches, o) for o in outcomes]
    fig, ax = _new_figure(9, 3.8)
    y = np.arange(len(fits))[::-1]

    for yi, fit in zip(y, fits, strict=True):
        low, high = fit.share_ci
        share = fit.share_of_advantage_lost
        ax.plot([low * 100, high * 100], [yi, yi], color=FANS, lw=2, solid_capstyle="round")
        ax.plot(share * 100, yi, "o", color=FANS, ms=9, mec=SURFACE, mew=2)
        ax.text(high * 100 + 2, yi, f"{share:.0%}", color=TEXT, fontsize=10, va="center")

    ax.axvline(100, color=TEXT_MUTED, lw=1, ls="--")
    ax.text(
        100, y.max() + 0.55, "all of the home edge ", color=TEXT_MUTED, fontsize=8.5, ha="right"
    )
    ax.set_yticks(y, [OUTCOME_LABELS[o] for o in outcomes])
    ax.set_ylim(-0.6, y.max() + 0.8)
    ax.set_xlim(0, 145)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(
        "Share of home advantage lost in empty stadiums (%), with 95% CI",
        color=TEXT_MUTED,
        fontsize=9.5,
    )
    _titles(
        fig,
        "Empty stadiums removed most of the home edge, and all of the referee edge",
        "Model controlling for team strength, 13,845 matches",
    )
    fig.subplots_adjust(top=0.78, left=0.27, right=0.97, bottom=0.16)
    return fig


def plot_by_league(matches: pd.DataFrame, outcomes=("goal_diff", "card_gap")):
    """Chart 3: home edge with fans vs empty, per league, one panel per outcome."""
    fig, axes = plt.subplots(1, len(outcomes), figsize=(10, 4), facecolor=SURFACE, sharey=True)
    order = list(LEAGUES)[::-1]
    y = np.arange(len(order))

    for ax, outcome in zip(axes, outcomes, strict=True):
        _style(ax)
        for yi, league in zip(y, order, strict=True):
            fit = fit_home_advantage(matches[matches["league"] == league], outcome)
            fans, empty = fit.home_adv, fit.home_adv + fit.effect
            ax.plot([fans, empty], [yi, yi], color=GRID, lw=3, zorder=1)
            ax.plot(
                fans, yi, "o", color=FANS, ms=9, mec=SURFACE, mew=2, zorder=2, label="With fans"
            )
            ax.plot(empty, yi, "o", color=EMPTY, ms=9, mec=SURFACE, mew=2, zorder=2, label="Empty")
        ax.axvline(0, color=TEXT_MUTED, lw=0.8)
        ax.set_title(OUTCOME_LABELS[outcome], color=TEXT, fontsize=10.5, loc="left")
        ax.grid(axis="y", visible=False)
        ax.set_xlabel(AXIS_LABELS[outcome], color=TEXT_MUTED, fontsize=9)

    axes[0].set_yticks(y, [LEAGUES[k] for k in order])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles[:2],
        labels[:2],
        loc="upper right",
        frameon=False,
        ncol=2,
        fontsize=9.5,
        bbox_to_anchor=(0.98, 0.93),
    )
    _titles(
        fig,
        "The referee edge shrank to about zero in every league",
        "Home edge with fans vs empty stadiums, model controlling for team strength",
    )
    fig.text(
        0.01,
        0.015,
        "Serie A's drop in goal difference is within its margin of error. "
        "All other drops are larger than theirs.",
        fontsize=8.5,
        color=TEXT_MUTED,
    )
    fig.subplots_adjust(top=0.76, left=0.13, right=0.98, bottom=0.18, wspace=0.08)
    return fig


def plot_referees(table: pd.DataFrame):
    """Chart 4: each referee's change in the card gap without fans, with 95% CI."""
    t = table.sort_values("change", ascending=False)
    overall = float(t["shrunk_change"].iloc[0]) if t["trust_weight"].max() == 0 else None
    fig, ax = _new_figure(9, 6)
    y = np.arange(len(t))

    ax.hlines(y, t["change"] - 1.96 * t["se"], t["change"] + 1.96 * t["se"], color=FANS, lw=2)
    ax.plot(t["change"], y, "o", color=FANS, ms=8, mec=SURFACE, mew=2)
    ax.axvline(0, color=TEXT_MUTED, lw=0.8)
    if overall is not None:
        ax.axvline(overall, color=EMPTY, lw=1.5, ls="--")
        ax.text(
            overall,
            len(t) - 0.3,
            f"all referees: {overall:+.2f} ",
            color=TEXT,
            fontsize=9,
            ha="right",
        )

    ax.set_yticks(y, t.index)
    ax.set_ylim(-0.8, len(t))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(
        "Change in yellow card gap without fans (cards per match), with 95% CI",
        color=TEXT_MUTED,
        fontsize=9.5,
    )
    _titles(
        fig,
        "Referees changed by about the same amount without fans",
        "Premier League referees with 30+ fan matches and 10+ empty matches. "
        "Differences between them are within noise.",
    )
    fig.subplots_adjust(top=0.86, left=0.17, right=0.97, bottom=0.09)
    return fig
