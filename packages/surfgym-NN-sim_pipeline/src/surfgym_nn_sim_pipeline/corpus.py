"""Load instruction text from surfgym seed tasks, vendored OSWorld tasks, and
frozen paraphrases into one common shape.

Everything downstream (embed.py, similarity.py) only ever sees `Instruction`.
It does not know whether a text came from our tasks or from OSWorld.
"""

import json
from dataclasses import dataclass
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
VENDORED_OSWORLD_PATH = MODULE_DIR / "data" / "osworld_1_0.json"
# v2: 5 diverse variants per OSWorld task (see paraphrase.py / 260731 Gemini
# regen). Superseded v1 (1 variant/task) -- variant count matters because the
# flag threshold is min(median-per-task), and a median over 1 sample is just
# that sample, so v1 gave the same fragility this schema exists to fix.
PARAPHRASE_PATH = MODULE_DIR / "data" / "osworld_1_0_paraphrases_v2.json"
# OSWorld ids we already used as design sources. Derivation is documented fact
# (260731_OSWorld 파생 소스 매핑), so it is read from a file rather than inferred
# from scores -- the pipeline's job is finding the derivations NOT in this file.
EXHAUSTED_SOURCES_PATH = MODULE_DIR / "data" / "exhausted_sources.json"

# surfgym seed directory name -> OSWorld domain name it is compared against.
# This mapping is a design decision (web is compared to chrome only,
# not the broader multi_apps pool), not a code detail. Change it here only.
DOMAIN_MAP = {
    "gimp": "gimp",
    "vlc": "vlc",
    "web": "chrome",
}

# Where each surfgym domain's corpus instructions live, relative to a data root.
# All active corpus inputs use their canonical seeds.
SURFGYM_TASK_GLOBS = {
    "gimp": "gimp/seeds/*.json",
    "vlc": "vlc/seeds/*.json",
    "web": "web/seeds/*.json",
}


@dataclass(frozen=True)
class Instruction:
    id: str
    text: str
    domain: str  # normalized domain name (OSWorld side naming, e.g. "chrome")
    source: str  # "surfgym" | "osworld" | "paraphrase"


def load_surfgym_instructions(data_dir: Path) -> list[Instruction]:
    """Read our corpus instructions from packages/surfgym-task's data directory.

    Canonical seeds do not carry ``task_id``. Desktop-app historical IDs were
    ``<domain>_<filename>``. The 36 former Travel Ad Hub IDs were already equal
    to their filenames, so web seeds retain that shape without storing IDs.
    """
    items = []
    for surfgym_domain, glob_pattern in SURFGYM_TASK_GLOBS.items():
        domain = DOMAIN_MAP[surfgym_domain]
        for path in sorted(data_dir.glob(glob_pattern)):
            raw = json.loads(path.read_text(encoding="utf-8"))
            task_id = raw.get("task_id")
            if not isinstance(task_id, str) or not task_id.strip():
                task_id = (
                    path.stem
                    if surfgym_domain == "web"
                    else f"{surfgym_domain}_{path.stem}"
                )
            items.append(
                Instruction(
                    id=task_id,
                    text=raw["instruction"],
                    domain=domain,
                    source="surfgym",
                )
            )
    return items


def load_osworld_instructions() -> list[Instruction]:
    """Read the vendored OSWorld 1.0 snapshot (see vendor.py)."""
    snapshot = json.loads(VENDORED_OSWORLD_PATH.read_text(encoding="utf-8"))
    return [
        Instruction(
            id=task["id"],
            text=task["instruction"],
            domain=task["domain"],
            source="osworld",
        )
        for task in snapshot["tasks"]
    ]


def load_paraphrases() -> list[Instruction]:
    """Read the frozen paraphrase set (see paraphrase.py). 5 rows per OSWorld task
    (v2 schema: "variants": [str, ...]) -- the id suffix (::v0..v4) keeps each
    variant addressable while `main._median_by_task` groups them back by the
    base id (everything before "::v") to compute the per-task median score."""
    snapshot = json.loads(PARAPHRASE_PATH.read_text(encoding="utf-8"))
    return [
        Instruction(
            id=f"{task['osworld_id']}::v{i}",
            text=variant,
            domain=task["domain"],
            source="paraphrase",
        )
        for task in snapshot["paraphrases"]
        for i, variant in enumerate(task["variants"])
    ]


def load_exhausted_sources() -> dict[str, set[str]]:
    """OSWorld ids per domain that we already used as a design source.

    Returns an empty mapping if the file is absent, so a corpus without a
    documented derivation record still runs -- the cohort split just drops out.
    """
    if not EXHAUSTED_SOURCES_PATH.exists():
        return {}
    doc = json.loads(EXHAUSTED_SOURCES_PATH.read_text(encoding="utf-8"))
    return {domain: set(ids) for domain, ids in doc["exhausted"].items()}


def group_by_domain(items: list[Instruction]) -> dict[str, list[Instruction]]:
    grouped: dict[str, list[Instruction]] = {}
    for item in items:
        grouped.setdefault(item.domain, []).append(item)
    return grouped
