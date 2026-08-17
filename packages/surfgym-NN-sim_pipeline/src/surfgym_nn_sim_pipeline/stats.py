"""Distribution comparison between the verdict distribution and a baseline."""

import numpy as np

# 260731_유사도 3차 런 결과: at n=14-18 the CI on this AUC is about +-0.15, so a
# point estimate moving by 0.04 between runs is noise. Three conclusions were
# reported from point estimates alone and had to be retracted once intervals
# were attached by hand. Attaching them here makes that non-optional and, unlike
# the hand computation, reproducible from the run directory.
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0


def probability_of_superiority(a: list[float], b: list[float]) -> float:
    """P(a random value from a > a random value from b), i.e. the Mann-Whitney U
    statistic normalized to [0, 1] (the AUC effect size). 0.5 = indistinguishable,
    1.0 = every value in a exceeds every value in b. Stable at small n, no binning.
    """
    a_arr = np.asarray(a, dtype=np.float64)
    b_arr = np.asarray(b, dtype=np.float64)

    wins = np.sum(a_arr[:, None] > b_arr[None, :])
    ties = np.sum(a_arr[:, None] == b_arr[None, :])
    total = len(a_arr) * len(b_arr)

    return float((wins + 0.5 * ties) / total)


def bootstrap_ci(
    a: list[float],
    b: list[float],
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = 0.05,
) -> tuple[float, float] | None:
    """Percentile bootstrap CI for probability_of_superiority(a, b).

    Both samples are resampled with replacement, since both are estimates -- an
    interval that treats the baseline as fixed would be too narrow. Returns None
    when either side is too small for the interval to mean anything.
    """
    if len(a) < 3 or len(b) < 3:
        return None

    rng = np.random.default_rng(seed)
    a_arr = np.asarray(a, dtype=np.float64)
    b_arr = np.asarray(b, dtype=np.float64)

    a_draws = rng.choice(a_arr, size=(resamples, len(a_arr)), replace=True)
    b_draws = rng.choice(b_arr, size=(resamples, len(b_arr)), replace=True)

    # (resamples, |a|, |b|) pairwise comparison in one vectorized pass.
    diff = a_draws[:, :, None] - b_draws[:, None, :]
    stats = (np.sum(diff > 0, axis=(1, 2)) + 0.5 * np.sum(diff == 0, axis=(1, 2))) / (
        len(a_arr) * len(b_arr)
    )

    lo, hi = np.percentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)
