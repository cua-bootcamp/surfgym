# surfgym_runtime/gateway/release_worker.py

import random
import time
from dataclasses import dataclass
from queue import SimpleQueue
from threading import Event, Lock, Thread, Timer

from surfgym_contracts.task import Hook

from surfgym_runtime.gateway.error import Deadline, GatewayError, RetryableError
from surfgym_runtime.gateway.registry import SessionState
from surfgym_runtime.gateway.transport import GatewayTransport
from surfgym_runtime.support import gateway_logger


@dataclass(frozen=True)
class ReleaseJob:
    context_id: str
    port: int | None
    release_hooks: tuple[Hook, ...]
    attempts: int = 0

    @classmethod
    def from_session(cls, state: SessionState) -> "ReleaseJob":
        return cls(
            context_id=state.lease.context_id,
            port=state.lease.port,
            release_hooks=tuple(state.release_hooks),
        )

    @classmethod
    def from_allocation(
        cls, *, context_id: str, release_hooks: list[Hook]
    ) -> "ReleaseJob":
        """Release a pre-dispatch allocation whose instance port is unknown."""
        return cls(context_id=context_id, port=None, release_hooks=tuple(release_hooks))


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
        self._lifecycle_lock = Lock()
        self._pending_context_ids: set[str] = set()
        self._thread: Thread | None = None

    def start(self) -> None:
        self._thread = Thread(
            target=self._run,
            name="surfgym-release-worker",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        with self._lifecycle_lock:
            if not self._closed.is_set():
                self._closed.set()
                self._queue.put(None)
            thread = self._thread

        if thread is not None:
            thread.join()

    def enqueue(self, state: SessionState | ReleaseJob) -> None:
        job = state if isinstance(state, ReleaseJob) else ReleaseJob.from_session(state)
        with self._lifecycle_lock:
            if self._closed.is_set():
                raise RuntimeError("Release worker is closed")
            if job.context_id in self._pending_context_ids:
                return
            self._pending_context_ids.add(job.context_id)
            self._queue.put(job)

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
                release_hooks=list(job.release_hooks),
            )
            with self._lifecycle_lock:
                self._pending_context_ids.discard(job.context_id)

        except RetryableError as exc:
            self._schedule_retry(job, exc)

        except GatewayError as exc:
            gateway_logger.warning(
                "Release completion is UNKNOWN; retaining and retrying: context_id=%s port=%s "
                "error_type=%s message=%s",
                job.context_id,
                job.port,
                exc.error_type,
                exc.message,
            )
            self._schedule_retry(job, RetryableError(exc.message))

        except Exception as exc:
            gateway_logger.exception(
                "Release completion is UNKNOWN; retaining and retrying: context_id=%s port=%s",
                job.context_id,
                job.port,
            )
            self._schedule_retry(job, RetryableError(str(exc)))

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
        with self._lifecycle_lock:
            if self._closed.is_set():
                return
            self._queue.put(job)
