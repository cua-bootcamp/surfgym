from surfgym_nn_sim_pipeline import lexical
from surfgym_nn_sim_pipeline.corpus import Instruction


def _inst(id_: str, text: str) -> Instruction:
    return Instruction(id=id_, text=text, domain="gimp", source="test")


def test_tokenize_lowercases_and_drops_punctuation():
    assert lexical.tokenize("Set the Undo levels to 50!") == [
        "set", "the", "undo", "levels", "to", "50",
    ]


def test_ngrams_empty_when_text_shorter_than_n():
    assert lexical.ngrams(["a", "b", "c"], 5) == set()
    assert len(lexical.ngrams(["a", "b", "c"], 3)) == 1


def test_containment_is_undefined_not_zero_for_short_text():
    """The distinction the whole undefined-pair policy rests on: a pair that
    cannot form an n-gram must not be reported as 'compared, found nothing'."""
    short = lexical.ngrams(lexical.tokenize("Open the file"), 13)
    long = lexical.ngrams(lexical.tokenize(" ".join(str(i) for i in range(40))), 13)
    assert lexical.containment(short, long) is None
    assert lexical.containment(long, long) == 1.0


def test_identical_text_scores_one_at_every_gram_size():
    # Deliberately longer than the largest gram size, so every row is defined --
    # a real instruction (median 14 words) would leave n=13 undefined instead.
    text = " ".join(f"word{i}" for i in range(20))
    rows = lexical.lexical_rows("gimp", "ours", [_inst("a", text)], [_inst("b", text)], False)
    for row in rows:
        assert row.max_top1 == 1.0, row
        assert row.n_undefined == 0
        # Only the n-gram rows carry the GPT-3 binary criterion; the
        # length-normalized row leaves it blank on purpose.
        expected = 1.0 if row.metric == "ngram_containment" else None
        assert row.detection_rate == expected, row


def test_diagonal_masking_excludes_self_match():
    """`lower` compares OSWorld against itself; without masking every row would
    trivially score 1.0 against its own entry."""
    items = [_inst("a", "rotate the image ninety degrees"), _inst("b", "export as png")]
    masked = lexical.lexical_rows("gimp", "baseline", items, items, True)
    unmasked = lexical.lexical_rows("gimp", "baseline", items, items, False)
    defined = [r.max_top1 for r in unmasked if r.max_top1 is not None]
    assert defined and max(defined) == 1.0
    assert all(r.max_top1 == 0.0 for r in masked if r.max_top1 is not None)


def test_undefined_pairs_are_counted_and_excluded_from_the_rate():
    """One item is long enough for a 13-gram, one is not. The short one must
    land in n_undefined rather than dragging detection_rate down as a zero."""
    long_text = " ".join(f"word{i}" for i in range(20))
    left = [_inst("long", long_text), _inst("short", "open the file")]
    rows = {r.gram_size: r for r in lexical.lexical_rows("gimp", "ours", left, [_inst("r", long_text)], False)}
    row13 = rows[13]
    assert row13.n_undefined == 1
    assert row13.n_left == 2
    assert row13.max_top1 == 1.0
    # 1 of 1 DEFINED item detected -- not 1 of 2. Counting the short item as a
    # non-detection would understate the rate exactly where the criterion is
    # weakest, which is what UNDEFINED_POLICY forbids.
    assert row13.detection_rate == 1.0


def test_jaccard_stays_defined_where_ngrams_do_not():
    short_a, short_b = _inst("a", "export as png"), _inst("b", "export as webp")
    rows = {(r.metric, r.gram_size): r for r in lexical.lexical_rows("gimp", "ours", [short_a], [short_b], False)}
    assert rows[("ngram_containment", 13)].median_top1 is None
    assert rows[("jaccard_uni_bi", None)].median_top1 > 0
