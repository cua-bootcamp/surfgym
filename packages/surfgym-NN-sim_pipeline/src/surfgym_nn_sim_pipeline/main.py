"""CLI entry point: python -m surfgym_nn_sim_pipeline.main

Wires the three comparisons (ours / paraphrased / baseline, 유사도 파이프라인 설계 §4.2)
across the requested models and domains, then writes runs/<run_id>/.

This module intentionally does the least amount of work needed to call the
other modules in order -- it does not know anything about cosine similarity,
n-guards, or embeddings; it only owns argument parsing and file paths.
"""

import argparse
import hashlib
import json
import statistics
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from surfgym_nn_sim_pipeline import corpus, lexical
from surfgym_nn_sim_pipeline.embed import DEFAULT_MODELS, MODELS, check_encoder_sanity, get_encoder
from surfgym_nn_sim_pipeline.report import (
    ComparisonResult,
    plot_contamination_dumbbell,
    plot_distributions,
    plot_lexical_sweep,
    plot_ratio_density,
    plot_top1_vs_gap,
    write_run,
)
from surfgym_nn_sim_pipeline.similarity import (
    cosine_similarity_matrix,
    find_nearest_neighbors,
    summarize_best_scores,
)
from surfgym_nn_sim_pipeline.stats import bootstrap_ci, probability_of_superiority

KST = timezone(timedelta(hours=9))
PIPELINE_VERSION = "0.1.0"

MODULE_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = MODULE_DIR.parents[1]
REPO_ROOT = MODULE_DIR.parents[3]
RUNS_DIR = PACKAGE_DIR / "runs"
DEFAULT_DATA_DIR = REPO_ROOT / "packages" / "surfgym-task" / "src" / "surfgym_task" / "data"


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _hash_seed_domain(data_dir: Path, glob_pattern: str) -> str:
    hasher = hashlib.sha256()
    for path in sorted(data_dir.glob(glob_pattern)):
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def run_comparison(
    model_name: str,
    encoder,
    domain: str,
    dataset: str,
    left: list[corpus.Instruction],
    right: list[corpus.Instruction],
    mask_diagonal: bool,
) -> ComparisonResult:
    left_vectors = encoder([item.text for item in left])
    right_vectors = encoder([item.text for item in right])
    matrix = cosine_similarity_matrix(left_vectors, right_vectors)
    neighbors = find_nearest_neighbors(matrix, left, right, k=5, mask_diagonal=mask_diagonal)
    summary = summarize_best_scores(neighbors)
    return ComparisonResult(model_name, domain, dataset, matrix, left, right, neighbors, summary)


def _best_scores(result: ComparisonResult) -> list[float]:
    return [matches[0].score for matches in result.neighbors if matches]


def _median_by_task(left_items: list[corpus.Instruction], scores: list[float]) -> list[float]:
    """Collapse per-variant paraphrase scores to one median per OSWorld task.

    `min(upper_scores)` (the flag threshold, 260730_유사도_1차_판정_결과.md §7)
    is a statistic over whichever list this feeds -- with 1 variant/task that
    list *is* the per-task score, but with 5 variants/task the raw list is
    445 samples where a single freak-low variant would drag the threshold
    down regardless of task count. Grouping by the pre-"::v" id and taking
    the median restores "one number per task" before min() ever sees it.
    """
    groups: dict[str, list[float]] = defaultdict(list)
    for item, score in zip(left_items, scores):
        base_id = item.id.split("::v", 1)[0]
        groups[base_id].append(score)
    return [statistics.median(task_scores) for task_scores in groups.values()]


# The flag threshold is a statistic over the per-task paraphrase scores. `min`
# is the literal reading of "weakest observed paraphrase", but it is an extreme
# order statistic over 17-46 items: swapping the paraphrase generator moved it
# by -0.004 to -0.128 and flipped bge/chrome from 0 to 2 flags with `ours_max`
# unchanged to three decimals (260731_유사도 3차 런 결과 §임계값 이동량). v2 stabilized
# *within* an item via median-of-5 and left *across* items untouched -- the one
# reviewer attack 해석 프레임 still marks 미해결. Reporting all three turns a
# knife-edge into a curve: if the verdict is the same at min/p5/p10 then it does
# not rest on one freak paraphrase, and if it differs that is the finding.
THRESHOLD_QUANTILES = {"min": 0.0, "p5": 0.05, "p10": 0.10}
PRIMARY_THRESHOLD = "min"  # kept as headline so runs stay comparable to run1-3

COHORT_FIELDS = [
    "exhausted_n",
    "exhausted_median",
    "exhausted_max",
    "unused_n",
    "unused_median",
    "unused_max",
    "auc_exhausted_vs_unused",
]


def _thresholds(upper_scores: list[float] | None) -> dict[str, float | None]:
    if not upper_scores:
        return {name: None for name in THRESHOLD_QUANTILES}
    ordered = sorted(upper_scores)
    return {
        name: float(ordered[0]) if q == 0.0 else float(np.quantile(ordered, q))
        for name, q in THRESHOLD_QUANTILES.items()
    }


def _contamination_rows(
    model_name: str,
    domain: str,
    verdict: ComparisonResult,
    upper_scores: list[float] | None,
) -> list[dict]:
    """Re-aggregate the verdict matrix per OSWorld eval item instead of per our task.

    Transposes the already-computed matrix rather than re-encoding anything, so
    this costs nothing beyond the argsort.

    The flag threshold is the weakest observed paraphrase pair: if no eval item's
    nearest training neighbor even reaches the least-similar known reword of an
    OSWorld instruction, nothing in training is a restatement of an eval item.
    Calibrated rather than absolute, per 파이프라인 설계.md §4.1.
    """
    eval_items, training_items = verdict.right_items, verdict.left_items
    neighbors = find_nearest_neighbors(
        verdict.matrix.T, eval_items, training_items, k=1, mask_diagonal=False
    )

    thresholds = _thresholds(upper_scores)
    threshold = thresholds[PRIMARY_THRESHOLD]
    exhausted = corpus.load_exhausted_sources().get(domain, set())

    rows = []
    for matches in neighbors:
        if not matches:
            continue
        top = matches[0]
        row = {
            "model": model_name,
            "domain": domain,
            "osworld_id": top.left_id,
            "osworld_text": top.left_text,
            "max_sim_to_training": top.score,
            "nearest_training_id": top.right_id,
            "nearest_training_text": top.right_text,
            "exceeds_weakest_paraphrase": ""
            if threshold is None
            else int(top.score >= threshold),
            # carried per row so the file is self-describing -- a reader can
            # see what each flag was judged against without a second file
            "weakest_paraphrase_threshold": "" if threshold is None else threshold,
            # A high score against an item we knowingly derived from is expected
            # and resolved by document lookup; a high score against an unused
            # item is the unintended re-derivation this pipeline exists to find.
            "source_exhausted": int(top.left_id in exhausted) if exhausted else "",
        }
        for name in THRESHOLD_QUANTILES:
            t = thresholds[name]
            row[f"exceeds_at_{name}"] = "" if t is None else int(top.score >= t)
        rows.append(row)
    return rows


def _lexical_rows(
    domains: list[str],
    ours_by_domain: dict[str, list[corpus.Instruction]],
    osworld_by_domain: dict[str, list[corpus.Instruction]],
    paraphrases_by_domain: dict[str, list[corpus.Instruction]],
) -> list[dict]:
    """n-gram overlap for every domain x dataset, computed once for the whole run.

    The left/right/mask triples below are the same ones run() hands to
    run_comparison -- kept literally parallel so the lexical channel and the
    cosine channel can never drift onto different comparisons. Unlike the cosine
    path this sits outside the model loop: n-gram overlap is a property of the
    text, so computing it per model would just produce three identical copies.
    """
    rows = []
    for domain in domains:
        osworld = osworld_by_domain[domain]
        other_domain_osworld = [
            item for other in domains if other != domain for item in osworld_by_domain[other]
        ]
        comparisons = [
            ("ours", ours_by_domain[domain], osworld, False),
            ("baseline", osworld, osworld, True),
            ("floor", osworld, other_domain_osworld, False),
        ]
        paraphrases = paraphrases_by_domain.get(domain)
        if paraphrases:
            comparisons.append(("paraphrased", paraphrases, osworld, False))

        for dataset, left, right, mask_diagonal in comparisons:
            rows.extend(
                asdict(row)
                for row in lexical.lexical_rows(domain, dataset, left, right, mask_diagonal)
            )
    return rows


def _cohort_split(contamination_rows: list[dict]) -> dict:
    """Split the eval-item axis into documented sources vs untouched OSWorld items.

    260731_OSWorld 파생 소스 매핑 redefined what this pipeline is for: derivation
    from a documented source is intended and resolved by looking the mapping up,
    so the only thing left to *detect* is closeness to an item nobody recorded
    using. That makes the unused cohort the one worth watching -- a high
    `unused_max` is an unintended re-derivation, while a high `exhausted_max` is
    just the design working as recorded.

    Returns blank fields when no derivation record exists for the domain, so the
    split degrades to absent rather than to a misleading zero.
    """
    exhausted = [r["max_sim_to_training"] for r in contamination_rows if r["source_exhausted"] == 1]
    unused = [r["max_sim_to_training"] for r in contamination_rows if r["source_exhausted"] == 0]
    if not exhausted and not unused:
        return {k: "" for k in COHORT_FIELDS}

    def summarize(prefix: str, values: list[float]) -> dict:
        if not values:
            return {f"{prefix}_n": 0, f"{prefix}_median": "", f"{prefix}_max": ""}
        return {
            f"{prefix}_n": len(values),
            f"{prefix}_median": float(np.median(values)),
            f"{prefix}_max": float(np.max(values)),
        }

    out = {**summarize("exhausted", exhausted), **summarize("unused", unused)}
    # P(a documented source scores higher than an untouched one). 0.5 means the
    # derivation record explains none of the similarity.
    out["auc_exhausted_vs_unused"] = (
        probability_of_superiority(exhausted, unused) if exhausted and unused else ""
    )
    return out


def _build_manifest(
    run_id: str,
    data_dir: Path,
    completed_model_names: list[str],
    device: str,
    domains: list[str],
    paraphrases_available: bool,
) -> dict:
    osworld_meta = json.loads(corpus.VENDORED_OSWORLD_PATH.read_text(encoding="utf-8"))

    manifest: dict = {
        "run_id": run_id,
        "generated_at": datetime.now(KST).isoformat(),
        "pipeline_version": PIPELINE_VERSION,
        "device": device,
        "domain_mapping": corpus.DOMAIN_MAP,
        "domains_compared": domains,
        "models": {name: asdict(MODELS[name]) for name in completed_model_names},
        "osworld_source": {
            "repo": osworld_meta["osworld_repo"],
            "commit": osworld_meta["osworld_commit"],
            "vendored_extracted_at": osworld_meta["extracted_at"],
        },
        "input_hashes": {
            "surfgym_seeds": {
                surfgym_domain: _hash_seed_domain(data_dir, glob_pattern)
                for surfgym_domain, glob_pattern in corpus.SURFGYM_TASK_GLOBS.items()
            },
            "osworld_vendored": _hash_file(corpus.VENDORED_OSWORLD_PATH),
        },
        "paraphrases_available": paraphrases_available,
        # Both choices change the shape of the n-gram curve and are the first
        # thing a reviewer asks about, so they are recorded rather than implied
        # by the code.
        "lexical": {
            "gram_sizes": list(lexical.GRAM_SIZES),
            "tokenization": lexical.TOKENIZATION,
            "undefined_pair_policy": lexical.UNDEFINED_POLICY,
        },
    }

    if paraphrases_available:
        paraphrase_meta = json.loads(corpus.PARAPHRASE_PATH.read_text(encoding="utf-8"))
        manifest["input_hashes"]["paraphrases"] = _hash_file(corpus.PARAPHRASE_PATH)
        manifest["paraphrase_generation"] = {
            "model": paraphrase_meta["generation_model"],
            "prompt_version": paraphrase_meta["prompt_version"],
            "generated_at": paraphrase_meta["generated_at"],
            "variants_per_task": paraphrase_meta.get("variants_per_task", 1),
        }

    return manifest


def _persist(
    run_dir: Path,
    run_id: str,
    data_dir: Path,
    completed_model_names: list[str],
    device: str,
    domains: list[str],
    paraphrases_available: bool,
    all_results: list[ComparisonResult],
    baseline_rows: list[dict],
    contamination_rows: list[dict],
    lexical_rows: list[dict],
) -> None:
    """Write everything accumulated so far. Called after each model finishes,
    not just once at the end -- so a later model crashing (e.g. a broken
    trust_remote_code path) doesn't discard results a prior model already
    produced. Each call overwrites the same files with the fuller picture."""
    manifest = _build_manifest(
        run_id, data_dir, completed_model_names, device, domains, paraphrases_available
    )
    write_run(run_dir, manifest, all_results, baseline_rows, contamination_rows, lexical_rows)


def run(
    data_dir: Path,
    model_names: list[str],
    device: str,
    run_id: str,
    lexical_only: bool = False,
) -> Path:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ours_by_domain = corpus.group_by_domain(corpus.load_surfgym_instructions(data_dir))
    osworld_by_domain = corpus.group_by_domain(corpus.load_osworld_instructions())

    try:
        paraphrases_by_domain = corpus.group_by_domain(corpus.load_paraphrases())
    except FileNotFoundError:
        print(
            "no frozen paraphrase set found -- skipping the upper baseline and "
            "baseline_comparison.csv. Run `python -m surfgym_nn_sim_pipeline.paraphrase` first."
        )
        paraphrases_by_domain = {}

    domains = sorted(ours_by_domain.keys())
    paraphrases_available = bool(paraphrases_by_domain)

    # Model-independent, so it runs once up front rather than inside the model
    # loop -- and it lands in the output even if every encoder later fails.
    lexical_rows = _lexical_rows(
        domains, ours_by_domain, osworld_by_domain, paraphrases_by_domain
    )
    plot_lexical_sweep(run_dir, lexical_rows)

    all_results: list[ComparisonResult] = []
    if lexical_only:
        # The lexical channel needs no encoder, so it can be regenerated in
        # seconds without downloading ~4GB of models. Written through the same
        # _persist path, so the output layout does not fork.
        _persist(
            run_dir, run_id, data_dir, [], device, domains,
            paraphrases_available, [], [], [], lexical_rows,
        )
        return run_dir

    baseline_rows: list[dict] = []
    contamination_rows: list[dict] = []
    completed_model_names: list[str] = []

    for model_name in model_names:
        model = MODELS[model_name]
        check_encoder_sanity(model, device=device)
        encoder = get_encoder(model, device=device)

        for domain in domains:
            ours = ours_by_domain[domain]
            osworld = osworld_by_domain[domain]
            other_domain_osworld = [
                item for other in domains if other != domain for item in osworld_by_domain[other]
            ]

            verdict = run_comparison(
                model_name, encoder, domain, "ours", ours, osworld, mask_diagonal=False
            )
            lower = run_comparison(
                model_name, encoder, domain, "baseline", osworld, osworld, mask_diagonal=True
            )
            # Cross-domain floor: same corpus, DIFFERENT app. Establishes how much
            # of a raw cosine is just "this is a task instruction" before any task
            # content is shared -- for gte-large that turns out to be ~0.8, which is
            # why absolute scores are not comparable across models. Reported for
            # scale interpretation only; the duplication verdict stays anchored on
            # `lower` (same app, different task), which is the relevant peer group.
            floor = run_comparison(
                model_name,
                encoder,
                domain,
                "floor",
                osworld,
                other_domain_osworld,
                mask_diagonal=False,
            )
            all_results.extend([verdict, lower, floor])

            paraphrases = paraphrases_by_domain.get(domain)
            if not paraphrases:
                contamination_rows.extend(
                    _contamination_rows(model_name, domain, verdict, None)
                )
                continue

            upper = run_comparison(
                model_name, encoder, domain, "paraphrased", paraphrases, osworld, mask_diagonal=False
            )
            all_results.append(upper)

            v_scores, u_scores_raw, l_scores = (
                _best_scores(verdict),
                _best_scores(upper),
                _best_scores(lower),
            )
            # Threshold/AUC/dumbbell all want "one score per OSWorld task";
            # the distribution plot below wants the full per-variant spread,
            # so u_scores_raw stays untouched for that one call.
            u_scores = _median_by_task(upper.left_items, u_scores_raw)
            eval_best_training = _contamination_rows(model_name, domain, verdict, u_scores)
            contamination_rows.extend(eval_best_training)
            ci = bootstrap_ci(v_scores, l_scores)
            baseline_row = {
                "model": model_name,
                "domain": domain,
                "auc_vs_baseline": probability_of_superiority(v_scores, l_scores),
                "auc_vs_paraphrased": probability_of_superiority(u_scores, v_scores),
                "auc_vs_baseline_ci_lo": "" if ci is None else ci[0],
                "auc_vs_baseline_ci_hi": "" if ci is None else ci[1],
            }
            # Cohort split: is our closeness to OSWorld confined to the items we
            # knowingly derived from, or does it reach the untouched ones too?
            # Hand-computed in run 3, where it reversed the headline reading --
            # a run artifact now so the next comparison cannot skip it.
            baseline_row.update(_cohort_split(eval_best_training))
            baseline_rows.append(baseline_row)

            plot_distributions(
                run_dir,
                model_name,
                domain,
                {
                    "floor": _best_scores(floor),
                    "baseline": l_scores,
                    "ours": v_scores,
                    "paraphrased": u_scores_raw,
                },
            )

            # Dumbbell: each eval item's nearest training task vs its nearest
            # sibling inside OSWorld itself. `lower` is already exactly the
            # sibling distance, keyed by the same OSWorld items, so no new
            # computation is needed -- only an index join.
            sibling_by_id = {
                matches[0].left_id: matches[0].score for matches in lower.neighbors if matches
            }
            plot_contamination_dumbbell(
                run_dir,
                model_name,
                domain,
                [r["osworld_id"] for r in eval_best_training],
                [r["max_sim_to_training"] for r in eval_best_training],
                [sibling_by_id.get(r["osworld_id"], float("nan")) for r in eval_best_training],
                min(u_scores) if u_scores else None,
            )


        # Pooled across domains, so these go after the domain loop.
        plot_top1_vs_gap(run_dir, model_name, all_results)
        plot_ratio_density(run_dir, model_name, all_results)

        # Persist after every model, not just at the end of the whole run --
        # a later model failing (see gte's trust_remote_code breakage) must not
        # cost us the models that already finished.
        completed_model_names.append(model_name)
        _persist(
            run_dir,
            run_id,
            data_dir,
            completed_model_names,
            device,
            domains,
            paraphrases_available,
            all_results,
            baseline_rows,
            contamination_rows,
            lexical_rows,
        )

    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="surfgym-task data directory containing gimp/, vlc/, travel-ad-hub/ (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        choices=sorted(MODELS),
        help="repeatable; defaults to the routing set in embed.DEFAULT_MODELS",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--lexical-only",
        action="store_true",
        help="compute only the n-gram channel (no encoder, no model download)",
    )
    args = parser.parse_args()

    model_names = args.models or list(DEFAULT_MODELS)
    run_id = datetime.now(KST).strftime("%Y%m%dT%H%M%S+0900")

    run_dir = run(
        data_dir=args.data_dir,
        model_names=model_names,
        device=args.device,
        run_id=run_id,
        lexical_only=args.lexical_only,
    )
    print(f"run complete -> {run_dir}")


if __name__ == "__main__":
    main()
