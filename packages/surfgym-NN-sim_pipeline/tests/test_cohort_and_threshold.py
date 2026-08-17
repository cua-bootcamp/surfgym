import json

from surfgym_nn_sim_pipeline import corpus, main


def test_exhausted_sources_ids_all_exist_in_the_snapshot():
    """The derivation record is hand-transcribed from vault notes; a typo would
    silently shrink the exhausted cohort and make re-derivation look fine."""
    exhausted = corpus.load_exhausted_sources()
    snapshot = json.loads(corpus.VENDORED_OSWORLD_PATH.read_text(encoding="utf-8"))
    by_domain: dict[str, set[str]] = {}
    for task in snapshot["tasks"]:
        by_domain.setdefault(task["domain"], set()).add(task["id"])

    for domain, ids in exhausted.items():
        assert ids <= by_domain[domain], (domain, ids - by_domain[domain])


def test_exhausted_counts_match_the_documented_mapping():
    exhausted = corpus.load_exhausted_sources()
    assert len(exhausted["gimp"]) == 18
    assert len(exhausted["vlc"]) == 15
    assert len(exhausted["chrome"]) == 22


def test_thresholds_are_ordered_and_min_is_the_smallest():
    scores = [0.5, 0.7, 0.8, 0.9, 0.95, 0.6, 0.75, 0.85, 0.88, 0.92]
    t = main._thresholds(scores)
    assert t["min"] == min(scores)
    assert t["min"] <= t["p5"] <= t["p10"]


def test_thresholds_blank_without_paraphrases():
    assert all(v is None for v in main._thresholds(None).values())
    assert all(v is None for v in main._thresholds([]).values())


def _row(osworld_id, sim, exhausted):
    return {"osworld_id": osworld_id, "max_sim_to_training": sim, "source_exhausted": exhausted}


def test_cohort_split_separates_documented_from_untouched():
    rows = [_row("a", 0.9, 1), _row("b", 0.8, 1), _row("c", 0.4, 0), _row("d", 0.3, 0)]
    out = main._cohort_split(rows)
    assert out["exhausted_n"] == 2 and out["unused_n"] == 2
    assert out["exhausted_max"] == 0.9
    assert out["unused_max"] == 0.4
    # Every documented source outscores every untouched item.
    assert out["auc_exhausted_vs_unused"] == 1.0


def test_cohort_split_flags_when_untouched_items_score_high():
    """The signal the pipeline exists for: AUC near 0.5 means the derivation
    record explains none of the similarity, i.e. we are re-deriving blind."""
    rows = [_row("a", 0.9, 1), _row("b", 0.3, 1), _row("c", 0.9, 0), _row("d", 0.3, 0)]
    out = main._cohort_split(rows)
    assert out["auc_exhausted_vs_unused"] == 0.5
    assert out["unused_max"] == 0.9


def test_cohort_split_blank_without_a_derivation_record():
    rows = [_row("a", 0.9, ""), _row("b", 0.3, "")]
    out = main._cohort_split(rows)
    assert set(out.values()) == {""}
