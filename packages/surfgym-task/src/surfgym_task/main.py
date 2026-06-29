import argparse
from pathlib import Path
from typing import get_args

from surfgym_contracts.task import (
    ApiHook,
    CriteriaEvaluation,
    LifecycleHooks,
    LLMJudgeEvaluation,
    Task,
    Website,
)

from surfgym_task.hoare import HoareStateGenerator
from surfgym_task.io import (
    AugmentationWriter,
    InstructionLoader,
    RunStats,
    iterate_seed,
    resolve_datapaths,
)
from surfgym_task.seed import Granularity


class Augmentor:
    def __init__(self, target_dir: Path, granularity: Granularity) -> None:
        self.paths = resolve_datapaths(target_dir)
        self.granularity: Granularity = granularity
        self.instruction_loader = InstructionLoader(self.paths.instruction)
        self.hoare_state_generator = HoareStateGenerator(granularity=granularity)

    def run(self) -> None:
        stats = RunStats()

        try:
            with AugmentationWriter(self.paths.out_dir) as augment_writer:
                for seed, seed_id in iterate_seed(self.paths.seeds_dir):
                    stats.seed_count += 1

                    with augment_writer.open_seed(seed_id) as task_writer:
                        for hoare_state in self.hoare_state_generator.generate(seed):
                            task_hash = hoare_state.to_key()
                            f = hoare_state.origin_start_idx
                            t = hoare_state.origin_end_idx
                            task_id = f"{seed_id}_{f}_{t}"

                            instruction, payload = self.instruction_loader.get(
                                task_hash, seed, hoare_state
                            )

                            if seed.domain == "impress":
                                evaluation = LLMJudgeEvaluation()
                                lifecycle_hooks = LifecycleHooks(
                                    allocate=[
                                        ApiHook(
                                            method="POST",
                                            url="http://localhost:53001/impress/allocate",
                                            json_payload={
                                                "setup_file": "1.pptx",
                                            },
                                            timing="before",
                                        )
                                    ],
                                    release=[
                                        ApiHook(
                                            method="POST",
                                            url="http://localhost:53001/impress/release",
                                            timing="before",
                                        )
                                    ],
                                )
                            else:
                                evaluation = CriteriaEvaluation(
                                    criteria=[
                                        atom.to_console_criteria() for atom in hoare_state.end_state
                                    ]
                                )
                                lifecycle_hooks = LifecycleHooks(
                                    allocate=[
                                        atom.to_console_hook() for atom in hoare_state.start_state
                                    ],
                                    reference=[
                                        atom.to_console_hook() for atom in hoare_state.end_state
                                    ],
                                )

                            task = Task(
                                hash=task_hash,
                                task_id=task_id,
                                instruction=instruction,
                                website=[Website(url=seed.website)],
                                complexity=hoare_state.complexity,
                                evaluation=evaluation,
                                lifecycle_hooks=lifecycle_hooks,
                            )
                            stats.task_count += 1

                            augment_writer.write_task(task)
                            task_writer.write_task(f, t, task)
                            task_writer.write_payload(f, t, payload)
                augment_writer.write_summary(stats)
        finally:
            self.instruction_loader.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--granularity", required=True, choices=get_args(Granularity))
    args = parser.parse_args()

    augmentor = Augmentor(
        target_dir=Path(args.target_dir),
        granularity=args.granularity,
    )
    augmentor.run()


if __name__ == "__main__":
    main()
