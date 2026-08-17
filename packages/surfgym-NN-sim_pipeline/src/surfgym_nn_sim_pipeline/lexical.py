"""Lexical n-gram overlap -- the standard contamination baseline, reported
alongside the embedding verdict (260731_유사도 해석 프레임.md §보강 우선순위 1).

Two reasons this exists:

1. The literature convention for training/eval contamination is n-gram overlap
   (13-gram, as GPT-3 defined it). Reporting only cosine invites "why didn't you
   use the standard method"; reporting both turns that into "we did, and here is
   what it showed."
2. It is a genuinely independent channel. Cosine and n-gram fail differently, so
   agreement between them is evidence, not redundancy.

Design constraints inherited from 파이프라인 설계.md:

- §3.3 -- the same function computes every dataset. n-gram overlap for `verdict`
  alone is an absolute number with no yardstick, which §4.1 rejects. Every
  metric here is computed for all four datasets in SCALE_ORDER, so the claim
  takes the same shape as the cosine one: "our lexical overlap sits inside the
  OSWorld-internal baseline."
- §3.1 -- aggregation is per-left-item top-1, then a distribution over those,
  mirroring the cosine path exactly so the two channels are read the same way.

Unlike everything else in this pipeline, these numbers are model-independent:
they are a property of the text. main.py computes them once per run rather than
once per model.
"""

import re
from dataclasses import dataclass

from surfgym_nn_sim_pipeline.corpus import Instruction

# 13 is the GPT-3 convention and the number a reviewer will look for. The rest
# are not padding: our instructions have a median length of 14 words, so a
# 13-gram barely exists in them, and the sweep is what shows *where* the
# criterion stops being computable rather than merely asserting that it does.
GRAM_SIZES = (3, 4, 5, 8, 13)

# Lowercase alphanumeric runs. Deliberately NOT stopword-filtered: the whole
# point of quoting a 13-gram result is that it is the literature's metric, and
# dropping stopwords would silently make it a different, more permissive one.
# Recorded in the manifest so the choice is visible rather than implicit.
TOKEN_PATTERN = r"[a-z0-9]+"
TOKENIZATION = "lowercase; [a-z0-9]+ runs; no stopword removal; no stemming"

# A pair where either side has fewer than n tokens cannot produce an n-gram at
# all. Scoring it 0 would be indistinguishable from "compared and found nothing"
# and would quietly inflate the denominator with items the metric never had an
# opinion about, so it is excluded and counted instead.
UNDEFINED_POLICY = (
    "items too short to form an n-gram are excluded from both numerator and "
    "denominator of detection_rate, not scored 0; counted in n_undefined"
)

_TOKEN_RE = re.compile(TOKEN_PATTERN)


@dataclass(frozen=True)
class LexicalRow:
    domain: str
    dataset: str
    metric: str  # "ngram_containment" | "jaccard_uni_bi"
    gram_size: int | None  # None for length-normalized metrics
    n_left: int
    n_undefined: int
    detection_rate: float | None  # share of left items with ANY overlap (GPT-3 criterion)
    median_top1: float | None
    max_top1: float | None


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def containment(left: set, right: set) -> float | None:
    """|L n R| / |L| -- asymmetric on purpose.

    The contamination question is directional ("how much of THIS item appears in
    that set"), and Jaccard's symmetric denominator would let a large right-hand
    set dilute the score of a short left-hand instruction.
    """
    if not left or not right:
        return None
    return len(left & right) / len(left)


def jaccard(left: set, right: set) -> float | None:
    if not left and not right:
        return None
    union = left | right
    return len(left & right) / len(union) if union else None


def _uni_bi(tokens: list[str]) -> set[tuple[str, ...]]:
    """Unigrams + bigrams as one set.

    This is the length-normalized companion to the n-gram sweep: it stays
    defined for every instruction we have, so the sweep going undefined at
    n=13 is visibly a property of the criterion and not a gap in the data.
    """
    return ngrams(tokens, 1) | ngrams(tokens, 2)


def _top1_per_left(
    left_sets: list[set],
    right_sets: list[set],
    score_fn,
    mask_diagonal: bool,
) -> tuple[list[float], int]:
    """Best score per left item, plus how many left items had no scoreable pair.

    Mirrors similarity.find_nearest_neighbors: same top-1 aggregation, same
    diagonal masking rule for the leave-one-out `lower` baseline.
    """
    best_scores: list[float] = []
    n_undefined = 0
    for i, left_set in enumerate(left_sets):
        scores = [
            score
            for j, right_set in enumerate(right_sets)
            if not (mask_diagonal and i == j)
            for score in (score_fn(left_set, right_set),)
            if score is not None
        ]
        if scores:
            best_scores.append(max(scores))
        else:
            n_undefined += 1
    return best_scores, n_undefined


def _summarize(
    domain: str,
    dataset: str,
    metric: str,
    gram_size: int | None,
    n_left: int,
    best_scores: list[float],
    n_undefined: int,
    with_detection_rate: bool,
) -> LexicalRow:
    if not best_scores:
        return LexicalRow(domain, dataset, metric, gram_size, n_left, n_undefined, None, None, None)
    ordered = sorted(best_scores)
    mid = len(ordered) // 2
    median = (
        ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    )
    return LexicalRow(
        domain=domain,
        dataset=dataset,
        metric=metric,
        gram_size=gram_size,
        n_left=n_left,
        n_undefined=n_undefined,
        # detection_rate is the GPT-3 criterion as originally stated -- a binary
        # "does any n-gram match" per item -- while median/max describe how much
        # overlaps when it does. The binary number is the one that is directly
        # comparable to published contamination rates. It is meaningless for a
        # length-normalized measure, where almost any pair sharing one word
        # scores above zero, so those rows leave it blank rather than report 1.0.
        #
        # Denominator is the DEFINED items (len(best_scores)), not n_left. An
        # instruction too short to form an n-gram was never tested, and counting
        # it as a non-detection would understate the rate exactly where the
        # criterion is weakest -- the same conflation UNDEFINED_POLICY exists to
        # prevent. n_undefined is reported alongside so the two are separable.
        detection_rate=(
            sum(1 for s in best_scores if s > 0) / len(best_scores)
            if with_detection_rate
            else None
        ),
        median_top1=median,
        max_top1=max(ordered),
    )


def lexical_rows(
    domain: str,
    dataset: str,
    left: list[Instruction],
    right: list[Instruction],
    mask_diagonal: bool,
) -> list[LexicalRow]:
    """Every lexical metric for one left/right comparison.

    Called with the same four (left, right, mask_diagonal) triples that
    main.run() feeds to run_comparison, so the scale ladder is identical.
    """
    left_tokens = [tokenize(item.text) for item in left]
    right_tokens = [tokenize(item.text) for item in right]

    rows = []
    for n in GRAM_SIZES:
        left_sets = [ngrams(t, n) for t in left_tokens]
        right_sets = [ngrams(t, n) for t in right_tokens]
        best, undefined = _top1_per_left(left_sets, right_sets, containment, mask_diagonal)
        rows.append(
            _summarize(
                domain, dataset, "ngram_containment", n, len(left), best, undefined, True
            )
        )

    left_ub = [_uni_bi(t) for t in left_tokens]
    right_ub = [_uni_bi(t) for t in right_tokens]
    best, undefined = _top1_per_left(left_ub, right_ub, jaccard, mask_diagonal)
    rows.append(
        _summarize(domain, dataset, "jaccard_uni_bi", None, len(left), best, undefined, False)
    )
    return rows
