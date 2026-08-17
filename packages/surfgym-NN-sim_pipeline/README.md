# surfgym-NN-sim_pipeline

Computes nearest-neighbor cosine similarity between our seed task instructions
and OSWorld task instructions, and flags OSWorld eval items that are close to
something in our training set.

Two independent channels, both reported against the same four baseline sets
(`cross_floor` / `lower` / `verdict` / `upper`) so neither is read as an
absolute number:

- **embedding cosine** — `embed.py`, `similarity.py`; runs per model
- **lexical n-gram overlap** — `lexical.py`; the literature's standard
  (13-gram, GPT-3's definition) plus a gram-size sweep. Model-independent, so
  it is computed once per run rather than once per model.

## Install

```bash
uv sync --active --all-packages --inexact
pip install -e "packages/surfgym-NN-sim_pipeline[models,report]"
```

- `models` — sentence-transformers, model2vec (required to encode text)
- `report` — matplotlib, scipy (required to render figures)
- `paraphrase` — openai, dotenv (only for regenerating the paraphrase set)

## Run

```bash
python -m surfgym_nn_sim_pipeline.main \
    --model uae-large-v1 --model bge-large-en-v1.5 --model gte-large \
    --device cpu
```

| flag | default | notes |
|---|---|---|
| `--model` | `embed.DEFAULT_MODELS` | repeatable; one of the keys in `embed.MODELS` |
| `--device` | `cpu` | `cuda` if you have a GPU |
| `--data-dir` | `surfgym-task/.../data` | override to point at a different seed corpus |
| `--lexical-only` | off | n-gram channel only — no encoder, no model download, runs in seconds |

Output goes to `packages/surfgym-NN-sim_pipeline/runs/<run_id>/` — inside the
package, not the repo root, and not gitignored (past runs are committed, which
is what makes "did this number move" answerable).

```
runs/<run_id>/
    report.md      <- summary tables, pairs to review, provenance
    review.csv     <- flagged pairs worth reading by hand, worst first
    figures/
        distributions__{model}__{domain}.png
        dumbbell__{model}__{domain}.png
        top1_vs_gap__{model}.png
        ratio_density__{model}.png
        lexical_sweep.png          detection rate vs gram size, per domain
    data/
        summary.csv, metrics.csv, contamination.csv, neighbors.csv
        lexical.csv       n-gram overlap per domain x dataset x gram size
        manifest.json     input hashes, model revisions, OSWorld commit,
                          tokenization and undefined-pair policy
        matrices/*.npy    raw cosine matrices
```

`summary.csv` carries a bootstrap CI on `auc_vs_lower` (2000 resamples, seed 0)
and the exhausted/unused cohort split. Both were hand-computed for run 3, where
they reversed the headline reading — as run artifacts they cannot be skipped,
and unlike the hand computation they regenerate from the run directory.

`contamination.csv` reports the flag at three thresholds (`min`, `p5`, `p10`).
`min` stays the headline so runs remain comparable, but it is an extreme order
statistic: swapping the paraphrase generator once moved it by −0.10 and flipped
a domain from 0 to 2 flags with the tasks unchanged. Agreement across the three
is what says the verdict does not rest on one weak paraphrase.

## Derivation record

`data/exhausted_sources.json` lists the OSWorld tasks we used as design sources
(gimp 18/26, vlc 15/17, chrome 22/46). Derivation is a documented fact, not
something to infer from a score — so the pipeline's job is finding closeness to
items *not* in this file. Check it before claiming an axis is unused: the two
re-derivations found in run 3 both came from judging "unused" against our own
task list instead of OSWorld's.

A model's results are written to disk as soon as it finishes, so a later
model failing doesn't discard results from models that already completed.

## Models

Registered in `embed.py`, each pinned to a specific HF revision.

| key | repo |
|---|---|
| `uae-large-v1` | WhereIsAI/UAE-Large-V1 |
| `bge-large-en-v1.5` | BAAI/bge-large-en-v1.5 |
| `gte-large` | thenlper/gte-large |
| `potion-base-32m` | minishlab/potion-base-32M (fast, for dev/tests only) |
| `qwen3-embedding-8b` | Qwen/Qwen3-Embedding-8B (needs a GPU) |

## Scripts

```bash
# Re-extract the OSWorld snapshot if the reference commit changes
python -m surfgym_nn_sim_pipeline.vendor --osworld-repo /path/to/OSWorld

# Regenerate the paraphrase baseline (needs OPENAI_API_KEY)
python -m surfgym_nn_sim_pipeline.paraphrase
```

Both write into `src/surfgym_nn_sim_pipeline/data/`; review and commit the output.

## Tests

```bash
pytest packages/surfgym-NN-sim_pipeline/tests
```
