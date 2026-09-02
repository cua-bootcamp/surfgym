# surfgym_runtime/gateway/release_worker.py

import random
import time
from dataclasses import dataclass
from queue import SimpleQueue
from threading import Event, Thread, Timer

from surfgym_contracts.task import Hook

from surfgym_runtime.gateway.error import Deadline, GatewayError, RetryableError
from surfgym_runtime.gateway.registry import SessionState
from surfgym_runtime.gateway.transport import GatewayTransport
from surfgym_runtime.support import gateway_logger


@dataclass(frozen=True)
class ReleaseJob:
    context_id: str
    port: int
    release_hooks: list[Hook]
    attempts: int = 0

    @classmethod
    def from_session(cls, state: SessionState) -> "ReleaseJob":
        return cls(
            context_id=state.lease.context_id,
            port=state.lease.port,
            release_hooks=state.release_hooks,
        )


class ReleaseWorker:
    def __init__(
        self,
        *,
        transport: GatewayTransport,
        release_timeout: float,
    ) -> None:
        self._transport = transport
        self._release_timeout = release_timeout
        self._queue: SimpleQueue[ReleaseJob | None] = SimpleQueue()
        self._closed = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        self._thread = Thread(
            target=self._run,
            name="surfgym-release-worker",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._closed.set()
        self._queue.put(None)

        if self._thread is not None:
            self._thread.join()

    def enqueue(self, state: SessionState) -> None:
        self._queue.put(ReleaseJob.from_session(state))

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                return

            self._handle_job(job)

    def _handle_job(self, job: ReleaseJob) -> None:
        try:
            deadline = Deadline(time.monotonic() + self._release_timeout, "release")
            self._transport.release(
                deadline=deadline,
                context_id=job.context_id,
                release_hooks=job.release_hooks,
            )

        except RetryableError as exc:
            self._schedule_retry(job, exc)

        except GatewayError as exc:
            gateway_logger.warning(
                "Dropping non-retryable release failure: context_id=%s port=%s "
                "error_type=%s message=%s",
                job.context_id,
                job.port,
                exc.error_type,
                exc.message,
            )

        except Exception:
            gateway_logger.exception(
                "Unexpected release worker failure: context_id=%s port=%s",
                job.context_id,
                job.port,
            )

    def _schedule_retry(self, job: ReleaseJob, exc: RetryableError) -> None:
        retry_job = ReleaseJob(
            context_id=job.context_id,
            port=job.port,
            release_hooks=job.release_hooks,
            attempts=job.attempts + 1,
        )
        delay = min(2 ** min(job.attempts, 5), 30) + random.uniform(0, 1)

        gateway_logger.warning(
            "Release accept failed; requeueing: context_id=%s port=%s "
            "attempts=%s delay=%.2fs message=%s",
            job.context_id,
            job.port,
            retry_job.attempts,
            delay,
            exc.message,
        )

        timer = Timer(delay, self._requeue, args=(retry_job,))
        timer.daemon = True
        timer.start()

    def _requeue(self, job: ReleaseJob) -> None:
        if not self._closed.is_set():
            self._queue.put(job)
