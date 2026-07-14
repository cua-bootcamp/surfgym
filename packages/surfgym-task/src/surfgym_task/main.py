import argparse
from pathlib import Path
from typing import get_args

from surfgym_contracts.task import CriteriaEvaluation, Hook, LifecycleHooks, Task, Website

from surfgym_task.hoare import HoareStateGenerator
from surfgym_task.io import DetailWriter, InstructionLoader, SeedReader, Summary, TaskWriter
from surfgym_task.seed import Granularity


def augment(target_dir: Path, granularity: Granularity):
    path = {
        "seeds": target_dir / "seeds",
        "out": target_dir / "out",
        "instructions": target_dir / "instructions.sqlite3",
        "tasks": target_dir / "out" / "tasks.sqlite3",
    }

    summary = Summary()
    hoare_state_generator = HoareStateGenerator(granularity=granularity)
    detail_writer = DetailWriter(path["out"])

    with (
        InstructionLoader(path["instructions"]) as instruction_loader,
        TaskWriter(path["tasks"]) as task_writer,
    ):
        for seed, seed_name in SeedReader(path["seeds"]).get_seed():
            summary.seed_count += 1

            for hoare_state in hoare_state_generator.generate(seed):
                observe_hooks = [
                    Hook(script=atom.to_script(type="action"), timing="before")
                    for atom in hoare_state.end_state
                ]
                if seed.domain == "impress":
                    observe_hooks.append(
                        Hook(
                            script="(() => {\n  return window.surfgym.release();\n})()",
                            timing="after",
                        )
                    )

                task_hash = hoare_state.to_key()
                task = Task(
                    hash=task_hash,
                    task_id=f"{seed_name}_{hoare_state.origin_start_idx}_{hoare_state.origin_end_idx}",
                    instruction=instruction_loader.get(task_hash, seed, hoare_state),
                    website=[Website(url=seed.website)],
                    complexity=hoare_state.complexity,
                    evaluation=CriteriaEvaluation(
                        criteria=[atom.to_console_criteria() for atom in hoare_state.end_state]
                    ),
                    lifecycle_hooks=LifecycleHooks(
                        allocate=[
                            Hook(script=atom.to_script(type="action"), timing="after")
                            for atom in hoare_state.start_state
                        ],
                        observe=observe_hooks,
                    ),
                )

                summary.task_count += 1

                detail_writer.write_task(task)
                task_writer.write(task)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--granularity", required=True, choices=get_args(Granularity))
    args = parser.parse_args()

    augment(
        target_dir=Path(args.target_dir),
        granularity=args.granularity,
    )


if __name__ == "__main__":
    main()
