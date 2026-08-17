import numpy as np
from surfgym_nn_sim_pipeline.corpus import Instruction
from surfgym_nn_sim_pipeline.similarity import (
    cosine_similarity_matrix,
    find_nearest_neighbors,
    summarize_best_scores,
)


def _make_items(n: int, domain: str = "d", source: str = "osworld") -> list[Instruction]:
    return [
        Instruction(id=f"{source}{i}", text=f"text {i}", domain=domain, source=source)
        for i in range(n)
    ]


def test_n_guard_drops_unstable_percentiles():
    # 20 samples clears p90's threshold (30) for nothing -- p90/p95/p99 should
    # all be None, since none of the thresholds (30/50/100) are met.
    items = _make_items(20)
    vectors = np.eye(20, dtype=np.float32)  # orthogonal, no diagonal masking needed here
    matrix = cosine_similarity_matrix(vectors, vectors)
    neighbors = find_nearest_neighbors(matrix, items, items, k=1, mask_diagonal=False)

    summary = summarize_best_scores(neighbors)

    assert summary.n == 20
    assert summary.p90 is None
    assert summary.p95 is None
    assert summary.p99 is None
    # median/max always reported regardless of n
    assert summary.max == 1.0  # each item matches itself when the diagonal isn't masked


def test_n_guard_reports_p90_above_threshold():
    items = _make_items(30)
    rng = np.random.default_rng(0)
    raw = rng.normal(size=(30, 16)).astype(np.float32)
    vectors = raw / np.linalg.norm(raw, axis=1, keepdims=True)
    matrix = cosine_similarity_matrix(vectors, vectors)
    neighbors = find_nearest_neighbors(matrix, items, items, k=1, mask_diagonal=False)

    summary = summarize_best_scores(neighbors)

    assert summary.n == 30
    assert summary.p90 is not None
    assert summary.p95 is None
    assert summary.p99 is None


def test_diagonal_mask_prevents_self_match():
    items = _make_items(10)
    vectors = np.eye(10, dtype=np.float32)  # each item is only similar to itself
    matrix = cosine_similarity_matrix(vectors, vectors)

    unmasked = find_nearest_neighbors(matrix, items, items, k=1, mask_diagonal=False)
    masked = find_nearest_neighbors(matrix, items, items, k=1, mask_diagonal=True)

    assert all(matches[0].score == 1.0 for matches in unmasked)
    assert all(matches[0].score == 0.0 for matches in masked)


def test_masked_leave_one_out_never_returns_the_query_itself():
    items = _make_items(5)
    vectors = np.eye(5, dtype=np.float32)
    matrix = cosine_similarity_matrix(vectors, vectors)

    neighbors = find_nearest_neighbors(matrix, items, items, k=5, mask_diagonal=True)

    for left_idx, matches in enumerate(neighbors):
        assert all(match.right_id != items[left_idx].id for match in matches)
