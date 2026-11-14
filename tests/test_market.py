import numpy as np
import pandas as pd
import pytest

from ghost_games.market import add_market_prob, market_check


def test_margin_is_removed():
    odds = pd.DataFrame(
        {"odds_home": [2.0], "odds_draw": [3.4], "odds_away": [3.8], "home_win": [1]}
    )
    out = add_market_prob(odds)
    assert out["market_margin"].iloc[0] > 0
    assert out["market_p_home"].iloc[0] == pytest.approx(0.5 / (0.5 + 1 / 3.4 + 1 / 3.8))


def test_market_check_finds_overrated_home_teams():
    # the odds say 45% in both periods, but empty home teams really win 38%
    rng = np.random.default_rng(0)
    n = 4000
    empty = np.repeat([0, 1], n // 2)
    true_p = np.where(empty == 1, 0.38, 0.45)
    matches = pd.DataFrame(
        {
            "league": "E0",
            "date": pd.Timestamp("2019-08-01") + pd.to_timedelta(np.arange(n) // 10, unit="D"),
            "closed_doors": empty,
            "crowd_status": np.where(empty == 1, "empty", "fans"),
            "home_win": (rng.random(n) < true_p).astype(int),
            # odds that give 45% after the margin is removed
            "odds_home": 1 / (0.45 * 1.05),
            "odds_draw": 1 / (0.27 * 1.05),
            "odds_away": 1 / (0.28 * 1.05),
        }
    )
    table = market_check(matches, n_resamples=500)
    assert table.loc["fans", "ci_low"] < 0 < table.loc["fans", "ci_high"]
    assert table.loc["empty: later", "ci_high"] < 0
