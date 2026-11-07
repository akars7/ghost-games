"""Raw fans vs empty comparisons. No controls here, see model.py for that."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GapEstimate:
    fans_mean: float
    empty_mean: float
    difference: float  # empty - fans
    ci_low: float
    ci_high: float
    p_value: float | None = None


def _as_clean_array(values) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        raise ValueError("group has no non-missing values")
    return arr


def bootstrap_gap(fans, empty, n_resamples: int = 5000, alpha: float = 0.05, seed: int = 0):
    """Bootstrap CI for mean(empty) - mean(fans)."""
    fans, empty = _as_clean_array(fans), _as_clean_array(empty)
    rng = np.random.default_rng(seed)
    fans_means = rng.choice(fans, size=(n_resamples, fans.size)).mean(axis=1)
    empty_means = rng.choice(empty, size=(n_resamples, empty.size)).mean(axis=1)
    diffs = empty_means - fans_means
    low, high = np.quantile(diffs, [alpha / 2, 1 - alpha / 2])
    return GapEstimate(fans.mean(), empty.mean(), empty.mean() - fans.mean(), low, high)


def permutation_test(fans, empty, n_permutations: int = 5000, seed: int = 0) -> float:
    """Two-sided permutation p-value for the difference in means."""
    fans, empty = _as_clean_array(fans), _as_clean_array(empty)
    observed = abs(empty.mean() - fans.mean())
    pooled = np.concatenate([fans, empty])
    rng = np.random.default_rng(seed)

    extreme = 0
    for _ in range(n_permutations):
        rng.shuffle(pooled)
        gap = pooled[fans.size :].mean() - pooled[: fans.size].mean()
        extreme += abs(gap) >= observed
    # add 1 so p is never exactly 0 (we only run a limited number of shuffles)
    return (extreme + 1) / (n_permutations + 1)
