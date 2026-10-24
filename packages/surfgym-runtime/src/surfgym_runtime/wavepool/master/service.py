import asyncio
import secrets
import time

from surfgym_contracts.protocol.gateway_to_upstream import (
    GatewayAllocateRequest,
    GatewayReleaseRequest,
    MasterAllocateRequest,
)
from surfgym_contracts.protocol.upstream_to_gateway import (
    MasterAllocateResponse,
    MasterReleaseResponse,
)

from surfgym_runtime.support import WavepoolConfig, master_logger
from surfgym_runtime.wavepool.master.error import (
    AllocationDispatchedError,
    MasterError,
    OutOfInstanceError,
)
from surfgym_runtime.wavepool.master.registry import LeaseRegistry
from surfgym_runtime.wavepool.master.transport import InstanceClient


class MasterService:
    _MAX_CONCURRENT_RELEASES = 4
    def __init__(self, registry: LeaseRegistry, wavepool_config: WavepoolConfig):
        self.config = wavepool_config
        self.client = InstanceClient(wavepool_config.host, wavepool_config.process_timeout)
        self.registry = registry

        self._release_wakeup = asyncio.Event()
        self._release_tasks: dict[str, asyncio.Task[None]] = {}
        self._release_semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_RELEASES)
        self._closing = False
        self._closed = False

    async def close(self):
        """Stop retained owners without treating cancellation as cleanup completion."""
        if self._closed:
            return
        # Set the fence before taking the snapshot.  A release_all() already
        # waiting on the registry rechecks it before it can publish a task.
        self._closing = True
        tasks = tuple(self._release_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._release_tasks.clear()
        await self.client.close()
        self._closed = True

    async def allocate(
        self,
        request: GatewayAllocateRequest,
        *,
        incoming_remaining_seconds: float | None = None,
    ):
        budget_started_at = time.monotonic()
        cleanup_capability = secrets.token_urlsafe(32)
        lease = await self.registry.reserve_lease(
            request.context_id, cleanup_capability, request.websites
        )
        if lease is None:
            raise OutOfInstanceError("No available instance at the moment")

        try:
            remaining_seconds = None
            instance_timeout = None
            if incoming_remaining_seconds is not None:
                remaining_seconds = incoming_remaining_seconds - (
                    time.monotonic() - budget_started_at
                )
                if remaining_seconds <= 0:
                    raise MasterError("allocation remaining budget expired before Instance dispatch", 504)
                instance_timeout = min(
                    self.config.process_timeout.allocate - self.config.process_timeout.layer_gap,
                    remaining_seconds,
                )
                remaining_seconds = instance_timeout - self.config.process_timeout.layer_gap
                if remaining_seconds <= 0:
                    raise MasterError("allocation remaining budget expired before Instance dispatch", 504)
            # Master is the sole normal-path issuer.  Retain the descriptor
            # first, then pass it only over the internal Master-to-Instance hop.
            instance_request = MasterAllocateRequest(
                **request.model_dump(), cleanup_capability=cleanup_capability
            )
            allocate_args = (
                lease.port_slot.port,
                lease.context_id,
                instance_request,
            )
            if remaining_seconds is None:
                await self.client.allocate(*allocate_args)
            else:
                await self.client.allocate(
                    *allocate_args,
                    timeout=instance_timeout,
                    remaining_seconds=remaining_seconds,
                )
        except BaseException as exc:
            await self.registry.enqueue_release(
                lease.context_id,
                GatewayReleaseRequest(hooks=request.release_hooks),
            )
            self._release_wakeup.set()
            # The release descriptor is now the sole owner of the Context ID.
            # Do not let Gateway retry a post-dispatch failure with that ID:
            # Instance navigation may already have admitted native state.
            if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
                raise
            if isinstance(exc, MasterError):
                raise AllocationDispatchedError(exc.message, exc.status_code) from exc
            raise AllocationDispatchedError(
                # A non-Master exception has not supplied a validated error
                # envelope.  Do not reflect arbitrary transport text here.
                "Instance allocation failed after dispatch", 502
            ) from exc

        return MasterAllocateResponse(
            context_id=lease.context_id,
            instance_port=lease.port_slot.port,
            instance_host=self.config.host,
        )

    async def release(self, context_id: str, request: GatewayReleaseRequest):
        await self.registry.enqueue_release(context_id, request)
        self._release_wakeup.set()
        return MasterReleaseResponse()

    async def release_all(self, *, wait_for_completion: bool = True) -> None:
        """Ensure every pending Context has one cleanup owner.

        A caller-facing release acknowledgement is deliberately separate from
        this owner.  In particular, an Instance request timeout says nothing
        about the downstream capability cleanup: replacing its owner could
        make a later caller race a successor Context.  The owner therefore
        remains in ``_release_tasks`` until it either completes the registry
        release or reaches its bounded cleanup horizon.
        """
        if getattr(self, "_closing", False):
            return
        pending_releases = await self.registry.pending_releases()
        # ``close`` can run while ``pending_releases`` awaits the registry
        # lock.  Never publish a new owner after its cancellation snapshot.
        if getattr(self, "_closing", False):
            return
        waiters: list[asyncio.Future[None]] = []
        for pending in pending_releases:
            tasks = getattr(self, "_release_tasks", None)
            if tasks is None:
                tasks = self._release_tasks = {}
            task = tasks.get(pending.context_id)
            if task is None:
                task = asyncio.create_task(self._release_pending(pending))
                tasks[pending.context_id] = task
            waiters.append(asyncio.shield(task))
        if waiters and wait_for_completion:
            await asyncio.gather(*waiters)

    async def _release_pending(self, pending) -> None:
        semaphore = getattr(self, "_release_semaphore", None)
        if semaphore is None:
            semaphore = self._release_semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_RELEASES)
        # A few focused ownership tests construct a bare service around a
        # fake client.  Production always supplies WavepoolConfig; keep those
        # test doubles on the documented defaults rather than giving a bare
        # object a different lifecycle policy.
        process_timeout = getattr(getattr(self, "config", None), "process_timeout", None)
        horizon = getattr(process_timeout, "binding_cleanup_horizon", 720.0)
        retry_interval = getattr(process_timeout, "binding_cleanup_retry_interval", 2.0)
        completed = False
        deferred_until_quiescent = False
        try:
            async with semaphore:
                # Queueing behind other retained owners is not a cleanup
                # attempt for this owner.  Start its bounded retry horizon
                # only after it owns a release-worker slot, so saturation
                # cannot turn a never-dispatched cleanup into UNKNOWN.
                deadline = time.monotonic() + horizon
                while True:
                    try:
                        if await self.registry.is_port_retired(pending.port):
                            if not await self.registry.is_port_exit_quiescent(pending.port):
                                # This is not an ambiguous cleanup outcome.
                                # A later confirmed-quiescent exit notification
                                # must be able to start the same descriptor.
                                deferred_until_quiescent = True
                                return
                            lease = self.registry.require_lease(pending.context_id)
                            await self.client.release_retained_bindings(lease)
                        else:
                            await self.client.release(
                                pending.context_id, pending.port, pending.release_request
                            )
                        await self.registry.complete_release(pending.context_id)
                        completed = True
                        return
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            master_logger.warning(
                                "Release cleanup horizon expired for %s; retaining the UNKNOWN "
                                "owner and lease without redispatch",
                                pending.context_id,
                                exc_info=True,
                            )
                            # A completed task left in _release_tasks is the
                            # bounded UNKNOWN replay record.  It fences the
                            # Context ID and prevents a later release caller
                            # from creating a new physical cleanup owner.
                            return
                        master_logger.warning(
                            "Release completion for %s is UNKNOWN; retaining the existing "
                            "owner and lease until terminal confirmation",
                            pending.context_id,
                            exc_info=True,
                        )
                        await asyncio.sleep(min(retry_interval, remaining))
        finally:
            if completed or deferred_until_quiescent:
                current = asyncio.current_task()
                if self._release_tasks.get(pending.context_id) is current:
                    self._release_tasks.pop(pending.context_id, None)

    async def recover_instance_exit(self, port: int, *, quiescent: bool = False) -> None:
        """Recover only the descriptors held for a confirmed-dead Instance."""
        await self.registry.retire_port(port, quiescent=quiescent)
        if quiescent:
            self._release_wakeup.set()

    async def release_loop(self):
        while True:
            try:
                try:
                    await asyncio.wait_for(self._release_wakeup.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass

                self._release_wakeup.clear()
                # Release owners run independently.  A single UNKNOWN reset
                # must not block admission of cleanup work for healthy slots.
                await self.release_all(wait_for_completion=False)
            except asyncio.CancelledError:
                raise
            except Exception:
                master_logger.exception("Release loop iteration failed")
