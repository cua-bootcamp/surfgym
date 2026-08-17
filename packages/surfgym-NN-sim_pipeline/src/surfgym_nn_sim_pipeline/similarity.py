"""Matrix computation, nearest-neighbor lookup, and the 5-metric summary.

This module does not know what "ours" or "OSWorld" mean. It takes a left set
and a right set of already-encoded vectors and their Instruction metadata, and
optionally masks the diagonal when left and right are the same set. The three
comparisons the design calls for (verdict, upper baseline, lower baseline) are
just three calls into this module with different left/right arguments -- see
baseline.py.
"""

from dataclasses import dataclass

import numpy as np

from surfgym_nn_sim_pipeline.corpus import Instruction

# n-guard (파이프라인 설계.md §3.4): a percentile below its minimum sample size
# is indistinguishable from the max, so we report it as missing rather than as
# a number that looks precise but isn't.
TAIL_MIN_SAMPLES = {
    "p90": 30,
    "p95": 50,
    "p99": 100,
}


@dataclass(frozen=True)
class Match:
    left_id: str
    left_text: str
    right_id: str
    right_text: str
    score: float


@dataclass(frozen=True)
class ScoreSummary:
    n: int
    median: float
    max: float
    p90: float | None
    p95: float | None
    p99: float | None


def cosine_similarity_matrix(left_vectors: np.ndarray, right_vectors: np.ndarray) -> np.ndarray:
    """left_vectors and right_vectors must already be L2-normalized (see embed.py)."""
    return left_vectors @ right_vectors.T


def find_nearest_neighbors(
    matrix: np.ndarray,
    left_items: list[Instruction],
    right_items: list[Instruction],
    k: int = 5,
    mask_diagonal: bool = False,
) -> list[list[Match]]:
    """For each left item, return its top-k right items by score, descending.

    mask_diagonal=True excludes right_items[i] from left_items[i]'s own row --
    use this when left and right are the same set (the OSWorld-internal
    leave-one-out baseline), so a task never matches itself.
    """
    scores = matrix.copy()
    if mask_diagonal:
        np.fill_diagonal(scores, -np.inf)

    neighbor_lists = []
    for row_idx, left_item in enumerate(left_items):
        row = scores[row_idx]
        top_k_idx = np.argsort(row)[::-1][:k]
        neighbor_lists.append(
            [
                Match(
                    left_id=left_item.id,
                    left_text=left_item.text,
                    right_id=right_items[col_idx].id,
                    right_text=right_items[col_idx].text,
                    score=float(row[col_idx]),
                )
                for col_idx in top_k_idx
                if np.isfinite(row[col_idx])
            ]
        )
    return neighbor_lists


def distinctiveness_ratios(neighbor_lists: list[list[Match]]) -> list[float]:
    """Lowe's nearest-neighbour distance ratio, d1/d2, on cosine distance.

    Near 0 means the top match stands alone; near 1 means the second match is
    just as close and the neighbourhood is ambiguous.
    """
    ratios = []
    for matches in neighbor_lists:
        if len(matches) < 2:
            continue
        d1 = 1.0 - matches[0].score
        d2 = 1.0 - matches[1].score
        if d2 > 0:
            ratios.append(d1 / d2)
    return ratios


def summarize_best_scores(neighbor_lists: list[list[Match]]) -> ScoreSummary:
    """Per-our-task NN-sim (파이프라인 설계.md §3.1): take each left item's top-1
    score, then summarize that distribution. Each value is already a max, which
    is why all five metrics carry signal here -- unlike aggregating the other way.
    """
    best_scores = np.array([matches[0].score for matches in neighbor_lists if matches])
    n = len(best_scores)

    def percentile_or_none(p: int) -> float | None:
        key = f"p{p}"
        if n < TAIL_MIN_SAMPLES[key]:
            return None
        return float(np.percentile(best_scores, p))

    return ScoreSummary(
        n=n,
        median=float(np.median(best_scores)),
        max=float(np.max(best_scores)),
        p90=percentile_or_none(90),
        p95=percentile_or_none(95),
        p99=percentile_or_none(99),
    )
