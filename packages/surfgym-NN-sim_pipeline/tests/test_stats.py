import numpy as np
from surfgym_nn_sim_pipeline.stats import bootstrap_ci, probability_of_superiority


def test_probability_of_superiority_bounds():
    assert probability_of_superiority([3.0, 4.0], [1.0, 2.0]) == 1.0
    assert probability_of_superiority([1.0, 2.0], [3.0, 4.0]) == 0.0
    assert probability_of_superiority([1.0, 2.0], [1.0, 2.0]) == 0.5


def test_bootstrap_ci_brackets_the_point_estimate():
    rng = np.random.default_rng(1)
    a = list(rng.normal(0.85, 0.05, 18))
    b = list(rng.normal(0.73, 0.05, 26))
    point = probability_of_superiority(a, b)
    lo, hi = bootstrap_ci(a, b)
    assert lo <= point <= hi
    assert 0.0 <= lo < hi <= 1.0


def test_bootstrap_ci_is_deterministic():
    """Seeded on purpose: a CI that moves between runs of the same data would
    make run-to-run comparison meaningless, which is why it exists."""
    a, b = [0.9, 0.8, 0.85, 0.7, 0.95], [0.6, 0.65, 0.7, 0.55, 0.75]
    assert bootstrap_ci(a, b) == bootstrap_ci(a, b)


def test_bootstrap_ci_is_wide_at_small_n():
    """The whole point of attaching intervals: at these sample sizes the CI must
    be wide enough that a ~0.04 shift in the point estimate is not a finding."""
    rng = np.random.default_rng(2)
    a = list(rng.normal(0.85, 0.05, 15))
    b = list(rng.normal(0.80, 0.05, 15))
    lo, hi = bootstrap_ci(a, b)
    assert hi - lo > 0.20


def test_bootstrap_ci_none_when_sample_too_small():
    assert bootstrap_ci([0.5, 0.6], [0.1, 0.2, 0.3]) is None
    assert bootstrap_ci([0.1, 0.2, 0.3], [0.5, 0.6]) is None
