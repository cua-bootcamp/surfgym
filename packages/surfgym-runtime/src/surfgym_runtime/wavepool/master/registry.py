import asyncio
import uuid
from dataclasses import dataclass
from time import monotonic
from typing import Optional
from urllib.parse import urlsplit

from surfgym_contracts.protocol.gateway_to_upstream import GatewayReleaseRequest
from surfgym_contracts.task import Website

from surfgym_runtime.wavepool.master.error import UnexpectedError


@dataclass
class PortSlot:
    _port: int
    _context_capacity: int
    _allocated_contexts: int = 0
    _retired: bool = False
    _exit_quiescent: bool = False

    @property
    def port(self) -> int:
        return self._port

    def can_reserve(self) -> bool:
        return not self._retired and self._allocated_contexts < self._context_capacity

    def allocate(self) -> None:
        self._allocated_contexts += 1

    def release(self) -> None:
        self._allocated_contexts = max(0, self._allocated_contexts - 1)

    def retire(self, *, quiescent: bool = False) -> None:
        self._retired = True
        self._exit_quiescent = self._exit_quiescent or quiescent


@dataclass(frozen=True)
class NativeCleanupBinding:
    origin: str
    website_id: str
    cleanup_capability: str


@dataclass(frozen=True)
class WebCleanupBinding:
    origin: str
    cookie_name: str
    reset_path: str


@dataclass(frozen=True)
class Lease:
    context_id: str
    port_slot: PortSlot
    cleanup_capability: str | None = None
    native_bindings: tuple[NativeCleanupBinding, ...] = ()
    web_bindings: tuple[WebCleanupBinding, ...] = ()


@dataclass(frozen=True)
class PendingRelease:
    context_id: str
    port: int
    release_request: GatewayReleaseRequest


class LeaseRegistry:
    _CLOSED_RETRY_HORIZON_SECONDS = 15 * 60
    def __init__(
        self,
        instance_start_port: int,
        instance_n: int,
        contexts_per_instance: int,
    ):
        self._slots: list[PortSlot] = [
            PortSlot(instance_start_port + i, contexts_per_instance) for i in range(instance_n)
        ]
        self._lease: dict[str, Lease] = {}
        self._pending_releases: dict[str, PendingRelease] = {}
        # Never evict an identifier inside the retry horizon: capacity pressure
        # is safer than allowing a late retry to affect a successor lease.
        self._closed_context_ids: dict[str, float] = {}

        self._lock = asyncio.Lock()

    async def reserve_lease(
        self,
        context_id: str | None = None,
        cleanup_capability: str | None = None,
        websites: list[Website] | None = None,
    ) -> Lease | None:
        async with self._lock:
            self._gc_closed_locked()
            if context_id is not None and (
                context_id in self._lease or context_id in self._closed_context_ids
            ):
                raise UnexpectedError(f"Context ID {context_id} is not reusable")
            slot = next((slot for slot in self._slots if slot.can_reserve()), None)

            if slot is not None:
                slot.allocate()
                lease = Lease(
                    port_slot=slot,
                    context_id=context_id or str(uuid.uuid4()),
                    cleanup_capability=cleanup_capability,
                    native_bindings=_native_bindings(websites or [], cleanup_capability),
                    web_bindings=_web_bindings(websites or []),
                )
                self._lease[lease.context_id] = lease
                return lease

    async def enqueue_release(
        self, context_id: str, request: Optional[GatewayReleaseRequest] = None
    ):
        async with self._lock:
            lease = self._lease.get(context_id)
            if lease is None:
                # A Gateway can fence the UUID before Master dispatch.  Keep a
                # bounded tombstone so a late allocate cannot resurrect it.
                self._closed_context_ids.setdefault(context_id, monotonic())
                return
            if context_id in self._pending_releases:
                # The initial descriptor owns this cleanup.  A duplicate
                # release must join it rather than replace its hooks.
                return
            self._pending_releases[context_id] = PendingRelease(
                context_id=lease.context_id,
                port=lease.port_slot.port,
                release_request=request or GatewayReleaseRequest(hooks=[]),
            )

    async def pending_releases(self) -> list[PendingRelease]:
        async with self._lock:
            return list(self._pending_releases.values())

    async def retire_port(self, port: int, *, quiescent: bool = False) -> tuple[Lease, ...]:
        """Fence a confirmed-dead Instance and snapshot only its owned leases."""
        async with self._lock:
            slot = next((candidate for candidate in self._slots if candidate.port == port), None)
            if slot is None:
                raise UnexpectedError(f"Instance port {port} is not registered")
            slot.retire(quiescent=quiescent)
            leases = tuple(lease for lease in self._lease.values() if lease.port_slot is slot)
            for lease in leases:
                self._pending_releases.setdefault(
                    lease.context_id,
                    PendingRelease(
                        context_id=lease.context_id,
                        port=port,
                        release_request=GatewayReleaseRequest(hooks=[]),
                    ),
                )
            return leases

    async def is_port_retired(self, port: int) -> bool:
        async with self._lock:
            slot = next((candidate for candidate in self._slots if candidate.port == port), None)
            return slot is not None and slot._retired

    async def is_port_exit_quiescent(self, port: int) -> bool:
        async with self._lock:
            slot = next((candidate for candidate in self._slots if candidate.port == port), None)
            return slot is not None and slot._exit_quiescent

    async def complete_release(self, context_id: str) -> None:
        async with self._lock:
            if self._pending_releases.pop(context_id, None) is None:
                if context_id in self._closed_context_ids:
                    return
                raise UnexpectedError(f"Context ID {context_id} not found in registry")
            lease = self.remove_lease(context_id)
            lease.port_slot.release()
            self._closed_context_ids[context_id] = monotonic()

    def _gc_closed_locked(self) -> None:
        cutoff = monotonic() - self._CLOSED_RETRY_HORIZON_SECONDS
        for context_id, closed_at in tuple(self._closed_context_ids.items()):
            if closed_at < cutoff:
                del self._closed_context_ids[context_id]

    def require_lease(self, context_id: str) -> Lease:
        lease = self._lease.get(context_id, None)
        if lease is None:
            raise UnexpectedError(f"Context ID {context_id} not found in registry")
        return lease

    def remove_lease(self, context_id: str):
        lease = self._lease.pop(context_id, None)
        if lease is None:
            raise UnexpectedError(f"Context ID {context_id} not found in registry")
        return lease


def _native_bindings(
    websites: list[Website], cleanup_capability: str | None
) -> tuple[NativeCleanupBinding, ...]:
    if cleanup_capability is None:
        return ()
    bindings: list[NativeCleanupBinding] = []
    for website in websites:
        if website.surface != "native":
            continue
        parsed = urlsplit(website.url)
        bindings.append(
            NativeCleanupBinding(
                origin=f"{parsed.scheme}://{parsed.netloc}",
                website_id=website.website_id,
                cleanup_capability=cleanup_capability,
            )
        )
    return tuple(bindings)


def _web_bindings(websites: list[Website]) -> tuple[WebCleanupBinding, ...]:
    bindings: dict[tuple[str, str], WebCleanupBinding] = {}
    for website in websites:
        descriptor = website.server_reset
        if descriptor is None:
            continue
        binding = WebCleanupBinding(
            origin=descriptor.origin.rstrip("/"),
            cookie_name=descriptor.cookie_name,
            reset_path=descriptor.reset_path,
        )
        bindings.setdefault((binding.origin, binding.cookie_name), binding)
    return tuple(bindings.values())
