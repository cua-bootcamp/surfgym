import asyncio
import uuid
from dataclasses import dataclass
from typing import Optional

from surfgym_contracts.protocol.gateway_to_upstream import GatewayReleaseRequest

from surfgym_runtime.wavepool.master.error import UnexpectedError


@dataclass
class PortSlot:
    _port: int
    _context_capacity: int
    _allocated_contexts: int = 0

    @property
    def port(self) -> int:
        return self._port

    def can_reserve(self) -> bool:
        return self._allocated_contexts < self._context_capacity

    def allocate(self) -> None:
        self._allocated_contexts += 1

    def release(self) -> None:
        self._allocated_contexts = max(0, self._allocated_contexts - 1)


@dataclass(frozen=True)
class Lease:
    context_id: str
    port_slot: PortSlot


@dataclass(frozen=True)
class PendingRelease:
    context_id: str
    port: int
    release_request: GatewayReleaseRequest


class LeaseRegistry:
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

        self._lock = asyncio.Lock()

    async def reserve_lease(self) -> Lease | None:
        async with self._lock:
            slot = next((slot for slot in self._slots if slot.can_reserve()), None)

            if slot is not None:
                slot.allocate()
                lease = Lease(port_slot=slot, context_id=str(uuid.uuid4()))
                self._lease[lease.context_id] = lease
                return lease

    async def enqueue_release(
        self, context_id: str, request: Optional[GatewayReleaseRequest] = None
    ):
        async with self._lock:
            lease = self.require_lease(context_id)
            self._pending_releases[context_id] = PendingRelease(
                context_id=lease.context_id,
                port=lease.port_slot.port,
                release_request=request or GatewayReleaseRequest(hooks=[]),
            )

    async def pending_releases(self) -> list[PendingRelease]:
        async with self._lock:
            return list(self._pending_releases.values())

    async def complete_release(self, context_id: str) -> None:
        async with self._lock:
            if self._pending_releases.pop(context_id, None) is None:
                raise UnexpectedError(f"Context ID {context_id} not found in registry")
            lease = self.remove_lease(context_id)
            lease.port_slot.release()

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
