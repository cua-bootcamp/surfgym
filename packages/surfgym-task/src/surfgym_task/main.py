import argparse
import json
from pathlib import Path
from typing import Literal, get_args

from surfgym_contracts.task import CriteriaEvaluation, Hook, LifecycleHooks, Task, Website

from surfgym_task.hoare import HoareStateGenerator
from surfgym_task.io import DetailWriter, InstructionLoader, SeedReader, Summary, TaskWriter
from surfgym_task.seed import Domain, Granularity, State


def _state_set_hooks(
    state: State,
    *,
    domain: Domain,
    timing: Literal["before", "after"],
) -> list[Hook]:
    if domain != "spreadsheet":
        return [Hook(script=atom.to_set(), timing=timing) for atom in state]

    atoms = [{"spec": atom.spec, "value": atom.value} for atom in state]
    payload = json.dumps(
        atoms,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return [Hook(script=f"window.surfgym.applyState({payload})", timing=timing)]


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
                is_full_task = (
                    hoare_state.origin_start_idx == 0
                    and hoare_state.origin_end_idx == len(seed.states) - 1
                )
                instruction = (
                    seed.instruction
                    if is_full_task
                    else instruction_loader.get(hoare_state.hash, seed, hoare_state)
                )

                observe_hooks = _state_set_hooks(
                    hoare_state.end_state,
                    domain=seed.domain,
                    timing="before",
                )
                if seed.domain == "impress":
                    observe_hooks.append(
                        Hook(
                            script="(() => {\n  return window.surfgym.release();\n})()",
                            timing="after",
                        )
                    )

                task = Task(
                    task_id=f"{seed_name}_{hoare_state.origin_start_idx}_{hoare_state.origin_end_idx}",
                    instruction=instruction,
                    website=[Website(url=seed.website)],
                    complexity=hoare_state.complexity,
                    evaluation=CriteriaEvaluation(
                        criteria=[atom.to_console_criteria() for atom in hoare_state.end_state]
                    ),
                    lifecycle_hooks=LifecycleHooks(
                        allocate=_state_set_hooks(
                            hoare_state.start_state,
                            domain=seed.domain,
                            timing="after",
                        ),
                        observe=observe_hooks,
                    ),
                )

                summary.task_count += 1

                detail_writer.write_task(task)
                task_writer.write(task)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--granularity", required=True, choices=get_args(Granularity.__value__))
    args = parser.parse_args()

    augment(
        target_dir=Path(args.target_dir),
        granularity=args.granularity,
    )


if __name__ == "__main__":
    main()
