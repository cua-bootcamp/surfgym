import argparse
from pathlib import Path
from typing import get_args

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


def augment(seed_dir: Path, granularity: Granularity, profile: Profile):
    path = {
        "seeds": seed_dir / "seeds",
        "out": seed_dir / "out",
        "instructions": seed_dir / "instructions.sqlite3",
        "tasks": seed_dir / "out" / "tasks.sqlite3",
    }

    summary = Summary()
    hoare_state_generator = HoareStateGenerator(granularity=granularity)
    detail_writer = DetailWriter(path["out"])
    seed_entries = list(SeedReader(path["seeds"]).get_seed())
    for seed, _ in seed_entries:
        _validate_profile(seed.domain, profile)

    with (
        InstructionWriter(path["instructions"]) as instruction_writer,
        TaskWriter(path["tasks"]) as task_writer,
    ):
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

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    augment(seed_dir=Path(args.seed_dir), granularity=args.granularity, profile=args.profile)


if __name__ == "__main__":
    main()
