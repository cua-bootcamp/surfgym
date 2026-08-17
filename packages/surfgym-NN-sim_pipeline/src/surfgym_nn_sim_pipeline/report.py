"""Write one run's output.

Layout is deliberately shallow: one file a human reads, one file a human
reviews by hand, and everything machine-oriented tucked under data/.

    runs/<run_id>/
        report.md      -- conclusions, tables, what to review, provenance
        review.csv     -- the pairs worth eyeballing, worst first
        figures/
        data/          -- summary.csv, metrics.csv, contamination.csv,
                          manifest.json, matrices/

Binary artifacts never go in the vault; the vault gets the run_id and a path.
"""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from surfgym_nn_sim_pipeline.corpus import Instruction
from surfgym_nn_sim_pipeline.similarity import TAIL_MIN_SAMPLES, Match, ScoreSummary

# Datasets, in the order they should be read as a scale.
SCALE_ORDER = ["floor", "baseline", "ours", "paraphrased"]
SCALE_LABEL = {
    "floor": "different app",
    "baseline": "same app, different task",
    "ours": "OURS vs OSWorld",
    "paraphrased": "same task, paraphrased",
}

METRICS_FIELDS = ["model", "domain", "dataset", "n", "median", "max", "p90", "p95", "p99"]
NEIGHBOR_FIELDS = [
    "model",
    "domain",
    "dataset",
    "left_id",
    "top1",
    "top2",
    "gap",
    "ratio",
    "top1_right_id",
]
REVIEW_FIELDS = [
    "model",
    "domain",
    "score",
    "ratio",
    "our_id",
    "our_instruction",
    "osworld_id",
    "osworld_instruction",
]
CONTAMINATION_FIELDS = [
    "model",
    "domain",
    "osworld_id",
    "osworld_text",
    "max_sim_to_training",
    "nearest_training_id",
    "nearest_training_text",
    "exceeds_weakest_paraphrase",
    "weakest_paraphrase_threshold",
    "source_exhausted",
    "exceeds_at_min",
    "exceeds_at_p5",
    "exceeds_at_p10",
]
LEXICAL_FIELDS = [
    "domain",
    "dataset",
    "metric",
    "gram_size",
    "n_left",
    "n_undefined",
    "detection_rate",
    "median_top1",
    "max_top1",
]
SUMMARY_FIELDS = [
    "model",
    "domain",
    "n_ours",
    "floor_median",
    "baseline_median",
    "ours_median",
    "paraphrased_median",
    "ours_max",
    "ours_p90",
    "ours_p95",
    "ours_p99",
    "auc_vs_baseline",
    "auc_vs_baseline_ci_lo",
    "auc_vs_baseline_ci_hi",
    "auc_vs_paraphrased",
    "n_eval_items",
    "eval_max_sim_to_training",
    "flag_threshold",
    "n_flagged",
    "n_flagged_at_p5",
    "n_flagged_at_p10",
    "exhausted_n",
    "exhausted_median",
    "exhausted_max",
    "unused_n",
    "unused_median",
    "unused_max",
    "auc_exhausted_vs_unused",
]


@dataclass(frozen=True)
class ComparisonResult:
    """One left/right comparison for one model, one domain, one dataset label.

    dataset is one of SCALE_ORDER -- see 유사도 파이프라인 설계 §4.2.
    """

    model_name: str
    domain: str
    dataset: str
    matrix: np.ndarray
    left_items: list[Instruction]
    right_items: list[Instruction]
    neighbors: list[list[Match]]
    summary: ScoreSummary


def _cell(value) -> str:
    if value is None or value == "":
        return "--"
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def _lexical_cells(rows: list[dict]) -> list[dict]:
    """Blank out the Nones so the CSV shows an empty cell, not the word "None"."""
    return [{k: ("" if v is None else v) for k, v in row.items()} for row in rows]


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


COHORT_SUMMARY_FIELDS = [
    "exhausted_n",
    "exhausted_median",
    "exhausted_max",
    "unused_n",
    "unused_median",
    "unused_max",
    "auc_exhausted_vs_unused",
]


def _count_flags(rows: list[dict], field: str) -> int | str:
    """Blank rather than 0 when the column is absent, so "no threshold computed"
    never reads as "computed, nothing flagged"."""
    values = [r.get(field) for r in rows]
    if not rows or all(v in ("", None) for v in values):
        return ""
    return sum(1 for v in values if v in (1, "1"))


def _build_summary(
    results: list[ComparisonResult],
    baseline_rows: list[dict],
    contamination_rows: list[dict],
) -> list[dict]:
    """One row per model x domain, joining the three things a reader wants at
    once: where our score sits on the scale, how far it is from the paraphrase
    baseline, and whether any eval item got flagged."""
    by_key: dict[tuple[str, str], dict[str, ComparisonResult]] = {}
    for r in results:
        by_key.setdefault((r.model_name, r.domain), {})[r.dataset] = r

    baselines = {(b["model"], b["domain"]): b for b in baseline_rows}

    contamination: dict[tuple[str, str], list[dict]] = {}
    for row in contamination_rows:
        contamination.setdefault((row["model"], row["domain"]), []).append(row)

    rows = []
    for (model, domain), datasets in by_key.items():
        verdict = datasets.get("ours")
        if verdict is None:
            continue
        b = baselines.get((model, domain), {})
        cont = contamination.get((model, domain), [])
        sims = [float(c["max_sim_to_training"]) for c in cont]
        flagged = [c for c in cont if c.get("exceeds_weakest_paraphrase") in (1, "1")]

        def median_of(name: str):
            r = datasets.get(name)
            return r.summary.median if r else ""

        rows.append(
            {
                "model": model,
                "domain": domain,
                "n_ours": verdict.summary.n,
                "floor_median": median_of("floor"),
                "baseline_median": median_of("baseline"),
                "ours_median": verdict.summary.median,
                "paraphrased_median": median_of("paraphrased"),
                "ours_max": verdict.summary.max,
                "ours_p90": "" if verdict.summary.p90 is None else verdict.summary.p90,
                "ours_p95": "" if verdict.summary.p95 is None else verdict.summary.p95,
                "ours_p99": "" if verdict.summary.p99 is None else verdict.summary.p99,
                "auc_vs_baseline": b.get("auc_vs_baseline", ""),
                "auc_vs_baseline_ci_lo": b.get("auc_vs_baseline_ci_lo", ""),
                "auc_vs_baseline_ci_hi": b.get("auc_vs_baseline_ci_hi", ""),
                "auc_vs_paraphrased": b.get("auc_vs_paraphrased", ""),
                "n_eval_items": len(cont),
                "eval_max_sim_to_training": max(sims) if sims else "",
                "flag_threshold": cont[0].get("weakest_paraphrase_threshold", "")
                if cont
                else "",
                "n_flagged": len(flagged) if cont else "",
                "n_flagged_at_p5": _count_flags(cont, "exceeds_at_p5"),
                "n_flagged_at_p10": _count_flags(cont, "exceeds_at_p10"),
                **{f: b.get(f, "") for f in COHORT_SUMMARY_FIELDS},
            }
        )
    rows.sort(key=lambda r: (r["model"], r["domain"]))
    return rows


def _build_neighbors(results: list[ComparisonResult]) -> list[dict]:
    """Per left item: the numbers every figure is drawn from."""
    rows = []
    for r in results:
        for matches in r.neighbors:
            if not matches:
                continue
            top1 = matches[0].score
            top2 = matches[1].score if len(matches) >= 2 else None
            rows.append(
                {
                    "model": r.model_name,
                    "domain": r.domain,
                    "dataset": r.dataset,
                    "left_id": matches[0].left_id,
                    "top1": round(top1, 6),
                    "top2": "" if top2 is None else round(top2, 6),
                    "gap": "" if top2 is None else round(top1 - top2, 6),
                    "ratio": ""
                    if top2 is None or top2 >= 1.0
                    else round((1.0 - top1) / (1.0 - top2), 6),
                    "top1_right_id": matches[0].right_id,
                }
            )
    return rows


def _build_review(results: list[ComparisonResult]) -> list[dict]:
    """Only the verdict pairs, top-1 each, worst (most similar) first.

    The baselines produce neighbour lists too, but nobody reviews those by
    hand -- keeping them was what made the old matches.csv 1.1 MB.
    """
    rows = []
    for r in results:
        if r.dataset != "ours":
            continue
        for matches in r.neighbors:
            if not matches:
                continue
            m = matches[0]
            ratio = ""
            if len(matches) >= 2 and matches[1].score < 1.0:
                ratio = round((1.0 - m.score) / (1.0 - matches[1].score), 4)
            rows.append(
                {
                    "model": r.model_name,
                    "domain": r.domain,
                    "score": round(m.score, 4),
                    "ratio": ratio,
                    "our_id": m.left_id,
                    "our_instruction": m.left_text,
                    "osworld_id": m.right_id,
                    "osworld_instruction": m.right_text,
                }
            )
    rows.sort(key=lambda r: -r["score"])
    return rows


def _threshold_sensitivity_section(summary_rows: list[dict]) -> list[str]:
    """Does the flag count survive moving the threshold off the single minimum?

    Closes the one reviewer objection 해석 프레임 still lists as 미해결.
    """
    if not any(r.get("n_flagged_at_p5") != "" for r in summary_rows):
        return []
    out = ["### 3-1. 임계값 민감도", ""]
    out.append("임계값은 패러프레이즈 점수의 순서통계량이라, `min`을 쓰면 89문항 중")
    out.append("**가장 어설픈 하나**가 게이트 전체를 정합니다. 실제로 생성기를 바꾸자 임계값이")
    out.append("−0.004~−0.128 움직였고, 태스크가 그대로인 채 플래그가 0 → 2로 바뀐 적이 있습니다.")
    out.append("아래 세 값이 같으면 판정이 그 하나에 의존하지 않는다는 뜻입니다.")
    out.append("")
    out.append("| model | domain | flagged<br>@min | flagged<br>@p5 | flagged<br>@p10 |")
    out.append("|---|---|---:|---:|---:|")
    for r in summary_rows:
        out.append(
            f"| {r['model']} | {r['domain']} | {r['n_flagged']} | "
            f"{r['n_flagged_at_p5']} | {r['n_flagged_at_p10']} |"
        )
    out.append("")
    out.append("헤드라인 수치는 run1~3과 비교 가능하도록 `@min`을 그대로 씁니다.")
    out.append("")
    return out


def _cohort_section(summary_rows: list[dict]) -> list[str]:
    """Exhausted vs unused OSWorld items -- the pipeline's actual job.

    Derivation from a documented source is intended; closeness to an item nobody
    recorded using is the unintended re-derivation worth acting on.
    """
    if not any(r.get("unused_n") not in ("", None) for r in summary_rows):
        return []
    out = ["### 3-2. 소진 / 미소진 코호트", ""]
    out.append("OSWorld 항목을 **우리가 설계 소스로 쓴 것(소진)**과 **손대지 않은 것(미소진)**으로")
    out.append("나눈 값입니다. 소진 쪽 점수가 높은 건 설계대로이고 문서 조회로 해소됩니다 —")
    out.append("**행동이 필요한 건 미소진 쪽 max가 높을 때**이며, 그것이 의도치 않은 재파생입니다.")
    out.append("출처는 `data/exhausted_sources.json`.")
    out.append("")
    out.append("| model | domain | 소진 n | 소진 med | 소진 max | 미소진 n | 미소진 med | **미소진 max** | AUC<br>소진>미소진 |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in summary_rows:
        out.append(
            f"| {r['model']} | {r['domain']} | {r.get('exhausted_n','')} | "
            f"{_cell(r.get('exhausted_median'))} | {_cell(r.get('exhausted_max'))} | "
            f"{r.get('unused_n','')} | {_cell(r.get('unused_median'))} | "
            f"**{_cell(r.get('unused_max'))}** | {_cell(r.get('auc_exhausted_vs_unused'))} |"
        )
    out.append("")
    out.append("- AUC가 0.5 부근이면 문서화된 파생이 유사도를 전혀 설명하지 못한다는 뜻입니다.")
    out.append("")
    return out


def _lexical_section(manifest: dict, lexical_rows: list[dict]) -> list[str]:
    """The n-gram counterpart to §1's scale table.

    Reported for the same four datasets so it can be read the same way: the
    question is never "is our overlap high" but "is it higher than OSWorld's
    own internal overlap."
    """
    cfg = manifest.get("lexical", {})
    gram_sizes = cfg.get("gram_sizes", [])
    by_key = {(r["domain"], r["dataset"], r["metric"], r["gram_size"]): r for r in lexical_rows}
    domains = sorted({r["domain"] for r in lexical_rows})
    datasets = [d for d in SCALE_ORDER if any(r["dataset"] == d for r in lexical_rows)]

    out = ["## 3-B. 어휘 중첩 (n-gram) — 표준 기법 병기", ""]
    out.append("코사인과 독립된 채널입니다. 오염 검출 문헌의 관례는 13-gram 중첩(GPT-3 정의)이므로")
    out.append("같은 네 기준 집합에 그대로 적용했습니다. 값은 **왼쪽 항목 중 오른쪽 집합과")
    out.append("n-gram이 하나라도 겹치는 비율**(GPT-3 기준을 그대로 옮긴 이진 판정)입니다.")
    out.append("")
    max_gram = max(gram_sizes) if gram_sizes else None
    out.append(
        "| domain | dataset | n | "
        + " | ".join(f"n={g}" for g in gram_sizes)
        + f" | undef<br>@n={max_gram} | Jaccard<br>(uni+bi) |"
    )
    out.append("|---|---|---:|" + "---:|" * (len(gram_sizes) + 2))
    for domain in domains:
        for dataset in datasets:
            cells = []
            n_left = ""
            undef_max = "--"
            for g in gram_sizes:
                row = by_key.get((domain, dataset, "ngram_containment", g))
                if row is None:
                    cells.append("--")
                    continue
                n_left = row["n_left"]
                cells.append(_cell(row["detection_rate"]))
                if g == max_gram:
                    undef_max = f"{row['n_undefined']}/{row['n_left']}"
            jac = by_key.get((domain, dataset, "jaccard_uni_bi", None))
            jac_cell = _cell(jac["median_top1"]) if jac else "--"
            label = SCALE_LABEL.get(dataset, dataset)
            bold = "**" if dataset == "ours" else ""
            out.append(
                f"| {domain} | {bold}{label}{bold} | {n_left} | "
                + " | ".join(cells)
                + f" | {undef_max} | {jac_cell} |"
            )
    out.append("")
    out.append(f"`undef@n={max_gram}` — 그 항목이 {max_gram}단어보다 짧아 n-gram을 만들 수조차 없는 수.")
    out.append("**검출률의 분모는 정의된 항목만**이며(짧은 항목은 분자·분모 양쪽에서 제외),")
    out.append("따라서 검출률이 0이라는 것은 '재보니 없었다'는 뜻이지 '못 쟀다'가 아닙니다.")
    out.append("")
    out.append("- **`same task, paraphrased` 행이 이 표의 정답지입니다.** 설계상 의도적으로 말만 바꾼")
    out.append("  쌍이므로, 어떤 검출 기법이든 여기서 신호가 나와야 합니다.")
    out.append("- 그 행조차 n=13에서 검출률이 0 부근이면, 이 문장 길이에서 표준 기준은 **명백한")
    out.append("  복제조차 못 잡는다**는 뜻입니다. 우리 값이 0인 것은 그때 근거가 되지 못합니다.")
    out.append("- Jaccard(uni+bi) 열은 중앙값이며, 문장이 짧아도 항상 정의되는 대조군입니다.")
    out.append("- **집계 단위 주의** — `same task, paraphrased`의 n은 문항당 5변형을 각각 한 항목으로")
    out.append("  센 것입니다(코사인 채널은 `_median_by_task`로 문항당 1개로 접은 뒤 임계값을 냄).")
    out.append("  이진 검출률에는 median 접기가 정의되지 않아 변형 단위를 유지했습니다.")
    out.append(f"- 토큰화: {cfg.get('tokenization')}")
    out.append(f"- 짧은 쌍 처리: {cfg.get('undefined_pair_policy')} (`data/lexical.csv`의 `n_undefined`)")
    out.append("- 그림: `figures/lexical_sweep.png`")
    out.append("")
    return out


def _report_markdown(
    manifest: dict,
    summary_rows: list[dict],
    review_rows: list[dict],
    lexical_rows: list[dict] | None = None,
) -> str:
    models = list(manifest.get("models", {}).keys())
    total_eval = sum(int(r["n_eval_items"] or 0) for r in summary_rows if r["model"] == models[0]) if models else 0
    total_flagged = sum(int(r["n_flagged"] or 0) for r in summary_rows if r["n_flagged"] != "")
    has_upper = manifest.get("paraphrases_available")

    out: list[str] = []
    out.append(f"# Similarity run {manifest.get('run_id')}")
    out.append("")
    out.append(f"{manifest.get('generated_at')} | models: {', '.join(models)} | device: {manifest.get('device')}")
    out.append("")

    out.append("## 결론")
    out.append("")
    if not models:
        # --lexical-only. Without this guard the has_upper branch below reports
        # "flagged 0" from an empty summary, which reads as an all-clear for a
        # contamination check that was never run.
        out.append(
            "- **어휘 채널(n-gram)만 계산한 실행입니다.** 임베딩 코사인·오염 플래그는 "
            "산출하지 않았습니다 — §3-B만 유효하며, 나머지 절의 빈 표는 미실행을 뜻합니다."
        )
        out.append("- 전체 판정을 보려면 `--lexical-only` 없이 다시 실행하세요.")
    elif has_upper:
        out.append(
            f"- OSWorld 평가 문항 {total_eval}개 × 모델 {len(models)}종 중 **플래그 {total_flagged}건**. "
            f"어떤 평가 문항도 학습셋에 '가장 약한 패러프레이즈' 수준으로 근접한 이웃을 갖지 않습니다."
            if total_flagged == 0
            else f"- 평가 문항 {total_eval}개 × 모델 {len(models)}종에서 **플래그 {total_flagged}건** 발생. "
            f"`data/contamination.csv`를 확인하세요."
        )
        out.append(
            "- 플래그의 의미: 어떤 평가 문항에 대해, 그 문항을 의도적으로 말만 바꿔 쓴 것만큼이나 "
            "가까운 무언가가 학습셋에 있다는 뜻입니다. 0건이면 평가 문항이 학습셋에 다시 쓰인 적이 없다는 의미입니다."
        )
    else:
        out.append(
            "- 고정된 패러프레이즈 세트가 없어 상한 기준과 오염 플래그를 산출하지 못했습니다. "
            "`python -m surfgym_nn_sim_pipeline.paraphrase`를 먼저 실행하세요."
        )
    out.append("")

    out.append("## 1. 척도 — 네 기준 집합의 중앙값")
    out.append("")
    out.append("네 열 모두 **top-1 코사인의 중앙값**입니다. 왼쪽 항목마다 오른쪽 집합 전체와")
    out.append("비교해 최댓값을 취하고, 그 최댓값들의 중앙값입니다. 왼쪽에서 오른쪽으로 갈수록")
    out.append("'더 닮은 관계'가 되며, OURS가 그 사이 어디에 놓이는지가 판정 내용입니다.")
    out.append("")
    out.append(
        "| model | domain | n | med<br>different app | med<br>same app,<br>diff task | **med<br>OURS** | med<br>same task,<br>paraphrased |"
    )
    out.append("|---|---|---:|---:|---:|---:|---:|")
    for r in summary_rows:
        out.append(
            f"| {r['model']} | {r['domain']} | {r['n_ours']} | {_cell(r['floor_median'])} | "
            f"{_cell(r['baseline_median'])} | **{_cell(r['ours_median'])}** | {_cell(r['paraphrased_median'])} |"
        )
    out.append("")

    out.append("## 2. OURS 분포의 지표")
    out.append("")
    out.append("§1의 OURS 열을 만든 분포(top-1 값 n개)의 지표와, 그 분포가 하한에 대해")
    out.append("얼마나 큰지(AUC)입니다. **절대값은 모델 간 비교 불가**이고(모델마다 바닥값이")
    out.append("다름), 비교 가능한 것은 AUC 열입니다.")
    out.append("")
    out.append(
        "| model | domain | n | median | max | p90 | p95 | p99 | AUC<br>vs baseline | 95% CI |"
    )
    out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in summary_rows:
        lo, hi = r.get("auc_vs_baseline_ci_lo", ""), r.get("auc_vs_baseline_ci_hi", "")
        ci = f"[{lo:.2f}, {hi:.2f}]" if isinstance(lo, float) and isinstance(hi, float) else "--"
        out.append(
            f"| {r['model']} | {r['domain']} | {r['n_ours']} | {_cell(r['ours_median'])} | "
            f"{_cell(r['ours_max'])} | {_cell(r['ours_p90'])} | {_cell(r['ours_p95'])} | "
            f"{_cell(r['ours_p99'])} | {_cell(r['auc_vs_baseline'])} | {ci} |"
        )
    out.append("")
    out.append("- `AUC vs baseline` — 우리 값 하나가 하한 값 하나보다 클 확률. 0.5면 구별 불가")
    out.append(
        "- **CI가 겹치면 차이를 주장하지 마세요.** n=15~46에서 폭이 ±0.15 수준이라 "
        "점추정 0.04 변동은 노이즈입니다. 부트스트랩 2000회·seed 0, 양쪽 표본 모두 재표본."
    )
    if has_upper:
        auc_uppers = [r["auc_vs_paraphrased"] for r in summary_rows if r["auc_vs_paraphrased"] != ""]
        if auc_uppers:
            out.append(
                f"- 상한(패러프레이즈) 분포와의 AUC는 전 도메인 {min(auc_uppers):.3f} 이상으로 "
                "사실상 완전 분리이므로 열로 싣지 않습니다"
            )
    out.append("")

    if has_upper:
        out.append("## 3. 오염 검사 (평가 문항 축)")
        out.append("")
        out.append("OSWorld 평가 문항 각각에 대해 학습셋에서 가장 가까운 이웃을 찾은 결과입니다.")
        out.append("§1·§2와 집계 축이 반대입니다 — 누수는 '평가 문항이 뚫렸는가'를 묻기 때문입니다.")
        out.append("판단 근거는 max와 플래그 개수이며 중앙값은 쓰지 않습니다. 평가 문항 하나만")
        out.append("뚫려도 문제라, 안심시키는 중앙값은 정작 중요한 꼬리에 대해 아무 말도 안 해줍니다.")
        out.append("")
        out.append("| model | domain | eval items | max sim | flag threshold | flagged |")
        out.append("|---|---|---:|---:|---:|---:|")
        for r in summary_rows:
            out.append(
                f"| {r['model']} | {r['domain']} | {r['n_eval_items']} | "
                f"{_cell(r['eval_max_sim_to_training'])} | {_cell(r['flag_threshold'])} | "
                f"**{r['n_flagged']}** |"
            )
        out.append("")
        out.extend(_threshold_sensitivity_section(summary_rows))
        out.extend(_cohort_section(summary_rows))

    if lexical_rows:
        out.extend(_lexical_section(manifest, lexical_rows))

    out.append("## 4. 사람이 직접 볼 쌍")
    out.append("")
    out.append("점수가 높은 순입니다. **높은 점수는 판정이 아니라 두 문장을 읽어보라는 신호입니다** —")
    out.append("텍스트 유사도는 '베껴서 값만 바꾼 것'과 '독립적으로 만들었는데 같은 기능에 수렴한 것'을")
    out.append("구분하지 못합니다. 전체 목록은 `review.csv`에 있습니다.")
    out.append("")
    out.append("`ratio`는 1등이 2등보다 얼마나 압도적인지입니다(거리 기준 d1/d2, Lowe 2004 §7.1).")
    out.append("**0에 가까우면 특정 하나만 유독 가까운 것**이고, 1에 가까우면 그 도메인 전체와")
    out.append("고만고만하게 닮은 것입니다. 점수가 같아도 성격이 반대일 수 있으므로,")
    out.append("**score가 높으면서 ratio가 낮은 행부터** 읽으면 됩니다.")
    out.append("")
    # Collapse the same pair reported by several models into one line, keeping
    # the highest score -- otherwise a 3-model run shows each pair three times
    # and the review queue reads as three times longer than it is.
    best_per_pair: dict[tuple[str, str, str], dict] = {}
    for r in review_rows:
        key = (r["domain"], r["our_id"], r["osworld_id"])
        if key not in best_per_pair or r["score"] > best_per_pair[key]["score"]:
            best_per_pair[key] = r
    unique_pairs = sorted(best_per_pair.values(), key=lambda r: -r["score"])

    out.append("표시된 점수는 그 쌍에 대해 여러 모델 중 가장 높은 값입니다.")
    out.append("")
    out.append("| score | ratio | domain | ours | OSWorld |")
    out.append("|---:|---:|---|---|---|")
    for r in unique_pairs[:12]:
        ours = r["our_instruction"].replace("|", "\\|")[:70]
        osw = r["osworld_instruction"].replace("|", "\\|")[:70]
        ratio = f"{r['ratio']:.2f}" if isinstance(r.get("ratio"), float) else "--"
        out.append(f"| {r['score']:.3f} | {ratio} | {r['domain']} | {ours} | {osw} |")
    out.append("")

    out.append("## 5. 읽을 때 주의할 점")
    out.append("")
    out.append(
        "- **`data/metrics.csv`의 빈 백분위 칸은 의도된 것입니다.** 표본이 최소 크기에 못 미치면 "
        "백분위는 max에 이름만 바꾼 값이 되므로, 숫자를 찍는 대신 비웁니다. "
        f"최소 표본: {', '.join(f'{k}는 n>={v}' for k, v in TAIL_MIN_SAMPLES.items())}. "
        "현재 코퍼스 규모에서는 대부분의 도메인 행이 median과 max만 채워집니다."
    )
    out.append(
        "- **절대 임계값(0.9 등)은 쓰지 않습니다.** 같은 앱의 무관한 지시문 두 개도 이미 높은 점수가 나오고 "
        "그 바닥값이 모델마다 다르기 때문에, 코사인 원값 자체로는 아무것도 판단할 수 없습니다. "
        "판정은 §1에서 두 기준선(lower/upper) 사이 어디에 있는지와, §2의 AUC로 합니다."
    )
    out.append(
        "- **중복 판정의 기준선은 'same app, different task'입니다.** 그게 비교 대상으로 타당한 집단이기 "
        "때문입니다. 'different app'은 척도가 어떻게 생겼는지 보여주고 모델 간 비교를 가능하게 하려고 "
        "함께 싣는 것이며, 판정 기준이 아닙니다."
    )
    out.append(
        "- **이 파이프라인은 스크리닝 도구입니다.** 정답 수준의 중복 여부는 텍스트가 아니라 "
        "평가식으로 판정해야 하며, 여기서 걸러진 쌍을 사람이 확인하는 것까지가 한 묶음입니다."
    )
    out.append("")

    out.append("## 6. 출처 (재현 정보)")
    out.append("")
    src = manifest.get("osworld_source", {})
    out.append(f"- OSWorld: `{src.get('repo')}` @ `{src.get('commit')}`")
    for name, spec in manifest.get("models", {}).items():
        out.append(f"- {name}: `{spec.get('repo_id')}` @ `{spec.get('revision')}`")
    gen = manifest.get("paraphrase_generation")
    if gen:
        out.append(
            f"- 패러프레이즈: {gen.get('model')} / prompt {gen.get('prompt_version')} / {gen.get('generated_at')}"
        )
    out.append(f"- 도메인 매핑: `{manifest.get('domain_mapping')}`")
    out.append(f"- 파이프라인 버전: {manifest.get('pipeline_version')}")
    out.append("- 입력 파일 해시와 전체 설정: `data/manifest.json`")
    out.append("")
    return "\n".join(out)


def write_run(
    run_dir: Path,
    manifest: dict,
    results: list[ComparisonResult],
    baseline_rows: list[dict],
    contamination_rows: list[dict],
    lexical_rows: list[dict] | None = None,
) -> None:
    """Single entry point -- writes the whole tree. Called after each model
    finishes so an interrupted run keeps whatever already completed."""
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    lexical_rows = lexical_rows or []
    summary_rows = _build_summary(results, baseline_rows, contamination_rows)
    review_rows = _build_review(results)

    (data_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(data_dir / "summary.csv", SUMMARY_FIELDS, summary_rows)
    _write_csv(data_dir / "lexical.csv", LEXICAL_FIELDS, _lexical_cells(lexical_rows))
    _write_csv(data_dir / "contamination.csv", CONTAMINATION_FIELDS, contamination_rows)
    _write_csv(data_dir / "neighbors.csv", NEIGHBOR_FIELDS, _build_neighbors(results))
    _write_csv(
        data_dir / "metrics.csv",
        METRICS_FIELDS,
        [
            {
                "model": r.model_name,
                "domain": r.domain,
                "dataset": r.dataset,
                "n": r.summary.n,
                "median": r.summary.median,
                "max": r.summary.max,
                "p90": "" if r.summary.p90 is None else r.summary.p90,
                "p95": "" if r.summary.p95 is None else r.summary.p95,
                "p99": "" if r.summary.p99 is None else r.summary.p99,
            }
            for r in results
        ],
    )

    matrices_dir = data_dir / "matrices"
    matrices_dir.mkdir(parents=True, exist_ok=True)
    for r in results:
        np.save(matrices_dir / f"{r.model_name}__{r.domain}__{r.dataset}.npy", r.matrix)

    _write_csv(run_dir / "review.csv", REVIEW_FIELDS, review_rows)
    (run_dir / "report.md").write_text(
        _report_markdown(manifest, summary_rows, review_rows, lexical_rows), encoding="utf-8"
    )


SCALE_STYLE = {
    "floor": ("#BBBBBB", "different app"),
    "baseline": ("#56B4E9", "same app, different task"),
    "ours": ("#000000", "OURS vs OSWorld"),
    "paraphrased": ("#D55E00", "same task, paraphrased"),
}


def plot_distributions(
    run_dir: Path,
    model_name: str,
    domain: str,
    scores_by_dataset: dict[str, list[float]],
) -> Path:
    """Rug of every observation over an ECDF of the same values.

    Not a kernel density: per-domain n is 15-46, where the bandwidth would drive
    the shape and a kernel spills mass past cosine=1.0 where `upper` piles up.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    present = [d for d in SCALE_ORDER if scores_by_dataset.get(d)]

    fig, (ax_rug, ax) = plt.subplots(
        2,
        1,
        figsize=(7.5, 6),
        sharex=True,
        gridspec_kw={"height_ratios": [len(present) * 0.55, 4], "hspace": 0.08},
    )

    for row, dataset in enumerate(present):
        colour, label = SCALE_STYLE[dataset]
        values = np.asarray(scores_by_dataset[dataset], dtype=np.float64)

        ax_rug.plot(values, np.full_like(values, len(present) - row), "|",
                    color=colour, markersize=11, markeredgewidth=1.6, alpha=0.85)
        ax_rug.plot(np.median(values), len(present) - row, "o", color=colour,
                    markersize=6, markeredgecolor="white", markeredgewidth=0.8)

        ordered = np.sort(values)
        y = np.arange(1, len(ordered) + 1) / len(ordered)
        ax.step(ordered, y, color=colour,
                linewidth=2.4 if dataset == "ours" else 1.5,
                label=f"{label}  (n={len(ordered)}, med={np.median(values):.3f})",
                where="post")

    ax_rug.set_yticks([len(present) - i for i in range(len(present))],
                      [SCALE_STYLE[d][1] for d in present], fontsize=7)
    ax_rug.set_ylim(0.4, len(present) + 0.6)
    ax_rug.tick_params(axis="x", length=0)
    for side in ("top", "right", "bottom"):
        ax_rug.spines[side].set_visible(False)
    ax_rug.set_title(f"{model_name} / {domain}", fontsize=11)

    if scores_by_dataset.get("baseline") and scores_by_dataset.get("paraphrased"):
        lo = float(np.median(scores_by_dataset["baseline"]))
        hi = float(np.median(scores_by_dataset["paraphrased"]))
        ax.axvspan(min(lo, hi), max(lo, hi), color="#F0F0F0", zorder=0)

    ax.set_xlabel("cosine similarity (top-1 per item)")
    ax.set_ylabel("cumulative fraction")
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.25, linewidth=0.5)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    # constrained_layout instead of tight_layout: the rug panel's height_ratios
    # are fractional, which tight_layout cannot solve, so it warned and then
    # clipped the left-hand rug labels ("same app, different task" etc.) off the
    # canvas. Harmless while the figure was an internal artifact, not once it is
    # embedded in a report.
    fig.set_layout_engine("constrained")

    path = figures_dir / f"distributions__{model_name}__{domain}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_top1_vs_gap(run_dir: Path, model_name: str, results: list[ComparisonResult]) -> Path:
    """Separates "close to one specific task" from "this app is just dense".

    x = top-1 score, y = top-1 minus top-2. A high score with a large gap means
    the task is singularly close to one OSWorld task -- the shape a near-duplicate
    makes. A high score with a small gap means the whole neighbourhood is close,
    which is what a narrow action space (GIMP, VLC) produces on its own.

    Needed because raw cosine cannot tell those apart, and in gimp the floor is
    high enough that most of a 0.9 is topic signal rather than task overlap.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    domain_colour = {"gimp": "#0072B2", "vlc": "#009E73", "chrome": "#CC79A7"}

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    for result in results:
        if result.dataset != "ours" or result.model_name != model_name:
            continue
        xs, ys, labels = [], [], []
        for matches in result.neighbors:
            if len(matches) < 2:
                continue
            xs.append(matches[0].score)
            ys.append(matches[0].score - matches[1].score)
            labels.append(matches[0].left_id)
        ax.scatter(
            xs,
            ys,
            s=42,
            alpha=0.8,
            color=domain_colour.get(result.domain, "#888888"),
            edgecolors="white",
            linewidths=0.6,
            label=f"{result.domain} (n={len(xs)})",
        )
        # name only the handful worth opening
        for x, y, name in zip(xs, ys, labels):
            if x >= 0.85 or y >= 0.06:
                ax.annotate(name, (x, y), fontsize=6, alpha=0.75,
                            xytext=(3, 3), textcoords="offset points")

    ax.set_xlabel("top-1 cosine  (how close is the nearest OSWorld task)")
    ax.set_ylabel("top-1 minus top-2  (how much it stands out)")
    ax.set_title(f"{model_name} -- singular match vs dense neighbourhood")
    ax.grid(alpha=0.25, linewidth=0.5)
    ax.legend(fontsize=8)
    ax.text(
        0.99,
        0.03,
        "upper right = close to one specific task\nlower right = whole domain is close",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        color="#555555",
        bbox={"facecolor": "white", "edgecolor": "#DDDDDD", "boxstyle": "round,pad=0.4", "alpha": 0.9},
    )
    fig.tight_layout()

    path = figures_dir / f"top1_vs_gap__{model_name}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_contamination_dumbbell(
    run_dir: Path,
    model_name: str,
    domain: str,
    eval_ids: list[str],
    sim_to_training: list[float],
    sim_to_osworld_sibling: list[float],
    threshold: float | None,
) -> Path:
    """Per eval item: is our training set closer to it than its own benchmark siblings?

    One row per OSWorld eval item, two dots joined. If the training dot sits to
    the right of the sibling dot, that eval item is nearer to something we trained
    on than to anything in its own benchmark -- the most direct reading of the
    leakage question there is.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    order = np.argsort(sim_to_training)
    y = np.arange(len(order))

    fig, ax = plt.subplots(figsize=(7.5, max(3.0, 0.16 * len(order) + 1.2)))
    for row, idx in enumerate(order):
        ax.plot(
            [sim_to_osworld_sibling[idx], sim_to_training[idx]],
            [row, row],
            color="#CCCCCC",
            linewidth=1.0,
            zorder=1,
        )
    ax.scatter(
        [sim_to_osworld_sibling[i] for i in order], y,
        s=26, color="#56B4E9", label="nearest OSWorld sibling", zorder=2,
    )
    ax.scatter(
        [sim_to_training[i] for i in order], y,
        s=26, color="#000000", label="nearest training task", zorder=3,
    )
    if threshold is not None:
        ax.axvline(threshold, color="#D55E00", linestyle="--", linewidth=1.2,
                   label=f"flag threshold {threshold:.3f}")

    # Label each row with its eval item id. Without this the figure shows a
    # distribution shape but a reader cannot name the item any row refers to,
    # which is exactly what a flagged row needs to be actionable.
    ax.set_yticks(y, [eval_ids[i][:8] for i in order], fontsize=6)
    ax.set_ylabel(f"{len(order)} eval items (sorted by nearest training task)")
    ax.set_xlabel("cosine similarity")
    ax.set_title(f"{model_name} / {domain} -- eval item vs training set")
    ax.grid(axis="x", alpha=0.25, linewidth=0.5)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()

    path = figures_dir / f"dumbbell__{model_name}__{domain}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path




def plot_ratio_density(
    run_dir: Path, model_name: str, results: list[ComparisonResult]
) -> Path:
    """Density of the nearest-neighbour distance ratio, pooled across domains.

    Domains are pooled because per-domain n is 15-46, where a kernel shows its
    own bandwidth more than the data. Pooled n is 55-89 and the ratio is
    scale-normalised, so domains share an axis. Rug marks every observation.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.stats import gaussian_kde

    from surfgym_nn_sim_pipeline.similarity import distinctiveness_ratios

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    pooled: dict[str, list[float]] = {"paraphrased": [], "ours": [], "baseline": []}
    for r in results:
        if r.model_name == model_name and r.dataset in pooled:
            pooled[r.dataset].extend(distinctiveness_ratios(r.neighbors))

    grid = np.linspace(0.0, 1.0, 400)
    fig, ax = plt.subplots(figsize=(7.5, 5))

    for dataset in ("paraphrased", "ours", "baseline"):
        values = np.asarray(pooled[dataset], dtype=np.float64)
        if len(values) < 3:
            continue
        colour, label = SCALE_STYLE[dataset]
        kde = gaussian_kde(values)
        density = kde(grid)
        ax.fill_between(grid, density, color=colour, alpha=0.22, zorder=1)
        ax.plot(grid, density, color=colour, linewidth=2.0, zorder=2,
                label=f"{label}  (n={len(values)}, med={np.median(values):.3f})")
        ax.plot(values, np.full_like(values, -0.12), "|", color=colour,
                markersize=8, markeredgewidth=1.2, alpha=0.7, zorder=2)

    ax.axvline(0.8, color="#666666", linestyle="--", linewidth=1.1, zorder=3)
    ax.text(0.8, ax.get_ylim()[1], " Lowe 0.8", fontsize=7, color="#666666", va="top")

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(bottom=-0.25)
    ax.set_xlabel("nearest-neighbour distance ratio  d1/d2   (0 = top match stands alone)")
    ax.set_ylabel("density")
    ax.set_title(f"{model_name} -- all domains pooled")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.2, linewidth=0.5)
    fig.tight_layout()

    path = figures_dir / f"ratio_density__{model_name}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_lexical_sweep(run_dir: Path, lexical_rows: list[dict]) -> Path:
    """Detection rate vs gram size, one panel per domain.

    The point of the sweep is the cliff, and a table makes a reader reconstruct
    it column by column. What matters visually is whether the `upper` curve --
    known deliberate rewordings, the positive control -- also collapses at the
    conventional n=13. If it does, the criterion is uninformative at these
    sentence lengths for everyone, ourselves included.

    No model dimension: n-gram overlap is a property of the text.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    gram_rows = [r for r in lexical_rows if r["metric"] == "ngram_containment"]
    domains = sorted({r["domain"] for r in gram_rows})
    gram_sizes = sorted({r["gram_size"] for r in gram_rows})

    fig, axes = plt.subplots(
        1, len(domains), figsize=(4.2 * len(domains), 4.2), sharey=True, squeeze=False
    )

    for ax, domain in zip(axes[0], domains):
        for dataset in SCALE_ORDER:
            series = {
                r["gram_size"]: r["detection_rate"]
                for r in gram_rows
                if r["domain"] == domain and r["dataset"] == dataset
            }
            if not series:
                continue
            colour, label = SCALE_STYLE[dataset]
            ys = [series.get(g) for g in gram_sizes]
            ax.plot(
                gram_sizes,
                ys,
                marker="o",
                markersize=5,
                color=colour,
                linewidth=2.4 if dataset == "ours" else 1.5,
                label=label,
            )

        ax.axvline(13, color="#666666", linestyle="--", linewidth=1.1)
        ax.text(12.6, 1.02, "GPT-3 13-gram", fontsize=7, color="#666666", va="top", ha="right")
        ax.set_xticks(gram_sizes)
        ax.set_xlabel("n (gram size)")
        ax.set_title(domain)
        ax.set_ylim(-0.03, 1.10)
        ax.grid(alpha=0.2, linewidth=0.5)

    axes[0][0].set_ylabel("share of left items with any n-gram overlap")
    # One figure-level legend under the panels: a per-axes legend lands on the
    # top-right corner, which is exactly where the 13-gram annotation sits.
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=8, ncol=len(labels), loc="lower center",
               frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.06, 1, 1))

    path = figures_dir / "lexical_sweep.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
