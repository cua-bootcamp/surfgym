import argparse
from pathlib import Path
from typing import get_args

from surfgym_task.augmentation import Accumulation, Augmentor, Granularity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-dir-path")
    parser.add_argument("--granularity", default="COARSE", choices=get_args(Granularity))
    parser.add_argument("--accumulation", default="DELTA", choices=get_args(Accumulation))
    args = parser.parse_args()

    augmentor = Augmentor(
        seed_dir=Path(args.seed_dir_path),
        granularity=args.granularity,
        accumulation=args.accumulation,
    )
    augmentor.run()


if __name__ == "__main__":
    main()
