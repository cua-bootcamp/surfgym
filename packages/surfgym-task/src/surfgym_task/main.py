import argparse
from pathlib import Path
from typing import cast, get_args

from src.schema import Granularity, State_Scope


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-dir-path")
    parser.add_argument("--granularity", default="FINE", choices=get_args(Granularity))
    parser.add_argument("--state-scope", default="DELTA", choices=get_args(State_Scope))
    args = parser.parse_args()

    from src.task_store import TaskStore

    task_store = TaskStore(
        seed_dir=Path(args.seed_dir_path),
        granularity=cast(Granularity, args.granularity),
        state_scope=cast(State_Scope, args.state_scope),
    )
    task_store.run()


if __name__ == "__main__":
    main()
