import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from snapshots.generate.client import ClientResult
from snapshots.generate.run import build_manifest, record_task_failure
from snapshots.generate.schema import TaskFailure


class SnapshotGenerateManifestTest(unittest.TestCase):
    def test_build_manifest_summarizes_successes_and_failures(self) -> None:
        tasks = [
            SimpleNamespace(task_id="task_ok"),
            SimpleNamespace(task_id="task_failed"),
        ]
        failures = {
            "task_failed": TaskFailure(
                snapshot_dir=Path("task_failed"),
                error_type="ValueError",
                error_message="boom",
                traceback="ValueError: boom",
            )
        }

        manifest = build_manifest(
            tasks=tasks,
            task_path=Path("tasks.jsonl"),
            elapsed_seconds=1.25,
            results_by_task_id={
                "task_ok": ClientResult(
                    task_id="task_ok",
                    snapshot_dir=Path("task_ok"),
                    reward=1.0,
                )
            },
            failures_by_task_id=failures,
        )

        self.assertEqual(manifest.summary.total, 2)
        self.assertEqual(manifest.summary.succeeded, 1)
        self.assertEqual(manifest.summary.failed, 1)
        self.assertEqual(manifest.summary.reward_sum, 1.0)
        self.assertEqual(set(manifest.tasks), {"task_ok"})
        self.assertEqual(set(manifest.failures), {"task_failed"})

    def test_record_task_failure_writes_failure_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_root = Path(temp_dir)
            exc = RuntimeError("gateway died")

            failure = record_task_failure(snapshot_root, "task_failed", exc)

            self.assertEqual(failure.snapshot_dir, Path("task_failed"))
            self.assertEqual(failure.error_type, "RuntimeError")
            self.assertEqual(failure.error_message, "gateway died")
            self.assertIn("RuntimeError: gateway died", failure.traceback)
            self.assertIn(
                "RuntimeError: gateway died",
                (snapshot_root / "task_failed" / "failure.txt").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
