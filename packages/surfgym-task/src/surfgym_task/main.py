import argparse
from pathlib import Path
from typing import Iterable, get_args

from surfgym_contracts.task import Hook, LifecycleHooks, Task, Website

from surfgym_task.hoare import HoareStateGenerator
from surfgym_task.io import DetailWriter, InstructionWriter, SeedReader, Summary, TaskWriter
from surfgym_task.seed import (
    CriteriaSeedTask,
    Domain,
    Granularity,
    InfeasibleSeedTask,
    LLMJudgeSeedTask,
    Profile,
    StateAtom,
)
from surfgym_task.web import DOCKER_FIXTURE_RELEASE_HOOK, WEB_STATE_RESET_HOOK

_DOCKER_FIXTURE_DOMAINS: frozenset[Domain] = frozenset(
    {
        "impress",
        "vlc",
        "gimp",
        "vscode",
        "chrome",
    }
)

_DEFAULT_PUBLISH_DOMAINS: tuple[Domain, ...] = (
    "chrome",
    "gimp",
    "impress",
    "spreadsheet",
    "vlc",
    "vscode",
    "web",
    "word",
)
_DATA_ROOT = Path(__file__).parent / "data"


def _release_hooks(domain: Domain) -> list[Hook]:
    if domain == "web":
        return [WEB_STATE_RESET_HOOK]
    if domain in _DOCKER_FIXTURE_DOMAINS:
        return [DOCKER_FIXTURE_RELEASE_HOOK]
    return []


def _validate_profile(domain: Domain, profile: Profile) -> None:
    if domain == "web" and profile == "SNAPSHOT":
        raise ValueError("Web seeds support only the ROLLOUT profile.")


def _allocate_hooks(domain: Domain, atoms: list[StateAtom]) -> list[Hook]:
    if not atoms:
        return []
    if domain != "web":
        return [Hook(script=atom.to_set(), timing="after") for atom in atoms]

    setters = "".join(f"await {atom.to_set()};" for atom in atoms)
    return [
        Hook(
            script=f"(async()=>{{{setters}location.reload();}})()",
            timing="after",
        )
    ]


def _planned_task_ids(
    seed_dir: Path,
    granularity: Granularity,
    profile: Profile,
) -> list[tuple[str, str]]:
    seed_entries = list(SeedReader(seed_dir / "seeds").get_seed())
    generator = HoareStateGenerator(granularity=granularity)
    task_ids: list[tuple[str, str]] = []
    for seed, seed_name in seed_entries:
        _validate_profile(seed.domain, profile)
        source = f"{seed_dir.name}/{seed_name}.json"
        match seed:
            case CriteriaSeedTask():
                task_ids.extend(
                    (
                        f"{seed_name}_{state.origin_start_idx}_{state.origin_end_idx}",
                        source,
                    )
                    for state in generator.generate(seed)
                )
            case LLMJudgeSeedTask() | InfeasibleSeedTask():
                task_ids.append((seed_name, source))
    return task_ids


def _compile_domain(
    seed_dir: Path,
    granularity: Granularity,
    profile: Profile,
    task_writer: TaskWriter,
) -> Summary:
    path = {
        "seeds": seed_dir / "seeds",
        "out": seed_dir / "out",
        "instructions": seed_dir / "instructions.sqlite3",
    }

    summary = Summary()
    hoare_state_generator = HoareStateGenerator(granularity=granularity)
    detail_writer = DetailWriter(path["out"])
    seed_entries = list(SeedReader(path["seeds"]).get_seed())
    for seed, _ in seed_entries:
        _validate_profile(seed.domain, profile)

    with InstructionWriter(path["instructions"]) as instruction_writer:
        for seed, seed_name in seed_entries:
            summary.seed_count += 1

            match seed:
                case LLMJudgeSeedTask():
                    task = Task(
                        task_id=f"{seed_name}",
                        instruction=seed.instruction,
                        website=[Website(url=seed.website)],
                        evaluation=seed.evaluation,
                        lifecycle_hooks=LifecycleHooks(
                            release=_release_hooks(seed.domain),
                        ),
                    )

                    summary.task_count += 1
                    detail_writer.write_task(task)
                    task_writer.write(task)
                case InfeasibleSeedTask():
                    task = Task(
                        task_id=f"{seed_name}",
                        instruction=seed.instruction,
                        website=[Website(url=seed.website)],
                        evaluation=seed.evaluation,
                        lifecycle_hooks=LifecycleHooks(
                            allocate=_allocate_hooks(
                                seed.domain,
                                seed.states[0].atoms if seed.states else [],
                            ),
                            release=_release_hooks(seed.domain),
                        ),
                        include_reward_image=profile == "SNAPSHOT",
                    )

                    summary.task_count += 1
                    detail_writer.write_task(task)
                    task_writer.write(task)
                case CriteriaSeedTask():
                    for hoare_state in hoare_state_generator.generate(seed):
                        is_full_task = (
                            hoare_state.origin_start_idx == 0
                            and hoare_state.origin_end_idx == len(seed.states) - 1
                        )
                        instruction = (
                            seed.instruction
                            if is_full_task
                            else instruction_writer.get(hoare_state.hash, seed, hoare_state)
                        )

                        task = Task(
                            task_id=f"{seed_name}_{hoare_state.origin_start_idx}_{hoare_state.origin_end_idx}",
                            instruction=instruction,
                            website=[Website(url=seed.website)],
                            complexity=hoare_state.complexity,
                            evaluation=hoare_state.end_state.to_criteria_evaluation(),
                            lifecycle_hooks=LifecycleHooks(
                                allocate=_allocate_hooks(
                                    seed.domain,
                                    hoare_state.start_state.atoms,
                                ),
                                observe=[
                                    Hook(script=atom.to_set(), timing="before")
                                    for atom in hoare_state.end_state.atoms
                                ]
                                if profile == "SNAPSHOT"
                                else [],
                                release=_release_hooks(seed.domain),
                            ),
                            include_reward_image=profile == "SNAPSHOT",
                        )

                        summary.task_count += 1
                        detail_writer.write_task(task)
                        task_writer.write(task)

    return summary


def augment(seed_dir: Path, granularity: Granularity, profile: Profile) -> Summary:
    """Compile one domain into its historical per-domain task database."""

    with TaskWriter(seed_dir / "out" / "tasks.sqlite3") as task_writer:
        return _compile_domain(seed_dir, granularity, profile, task_writer)


def publish(
    *,
    data_root: Path,
    domains: Iterable[Domain],
    output_path: Path,
    granularity: Granularity,
    profile: Profile,
) -> Summary:
    """Publish selected domains into one runtime task database."""

    selected_domains = list(domains)
    seen_task_ids: dict[str, str] = {}
    for domain in selected_domains:
        seed_dir = data_root / domain
        for task_id, source in _planned_task_ids(seed_dir, granularity, profile):
            previous = seen_task_ids.get(task_id)
            if previous is not None:
                raise ValueError(f"Duplicate task id {task_id}: {previous} and {source}.")
            seen_task_ids[task_id] = source

    summary = Summary()
    with TaskWriter(output_path) as task_writer:
        for domain in selected_domains:
            domain_summary = _compile_domain(
                data_root / domain,
                granularity,
                profile,
                task_writer,
            )
            summary.seed_count += domain_summary.seed_count
            summary.task_count += domain_summary.task_count
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate SurfGym tasks from seed tasks.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "seed_dir",
        type=Path,
    )

    parser.add_argument(
        "-g",
        "--granularity",
        type=str.upper,
        choices=get_args(Granularity.__value__),
        default="COARSE",
    )

    parser.add_argument(
        "-p",
        "--profile",
        type=str.upper,
        choices=get_args(Profile.__value__),
        default="ROLLOUT",
    )

    parser.add_argument(
        "--domain",
        action="append",
        choices=get_args(Domain.__value__),
        help="Domain to include when the seed directory is the publish command. Repeat to select.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Combined task database path for the publish command.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.seed_dir == Path("publish"):
        if args.output is None:
            raise SystemExit("publish requires --output.")
        summary = publish(
            data_root=_DATA_ROOT,
            domains=args.domain or _DEFAULT_PUBLISH_DOMAINS,
            output_path=args.output,
            granularity=args.granularity,
            profile=args.profile,
        )
        print(
            f"published {summary.task_count} task(s) from {summary.seed_count} seed(s) -> {args.output}"
        )
        return
    if args.domain is not None or args.output is not None:
        raise SystemExit("--domain and --output require the publish command.")
    augment(seed_dir=args.seed_dir, granularity=args.granularity, profile=args.profile)


if __name__ == "__main__":
    main()
