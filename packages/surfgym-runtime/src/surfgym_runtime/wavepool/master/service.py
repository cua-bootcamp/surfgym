import asyncio

from surfgym_contracts.protocol.gateway_to_upstream import (
    GatewayAllocateRequest,
    GatewayReleaseRequest,
)
from surfgym_contracts.protocol.upstream_to_gateway import (
    MasterAllocateResponse,
    MasterReleaseResponse,
)

from surfgym_runtime.support import WavepoolConfig, master_logger
from surfgym_runtime.wavepool.master.error import OutOfInstanceError
from surfgym_runtime.wavepool.master.registry import LeaseRegistry
from surfgym_runtime.wavepool.master.transport import InstanceClient


class MasterService:
    def __init__(self, registry: LeaseRegistry, wavepool_config: WavepoolConfig):
        self.config = wavepool_config
        self.client = InstanceClient(wavepool_config.host, wavepool_config.process_timeout)
        self.registry = registry

        self._release_wakeup = asyncio.Event()

    async def close(self):
        await self.client.close()

    async def allocate(self, request: GatewayAllocateRequest):
        lease = await self.registry.reserve_lease()
        if lease is None:
            raise OutOfInstanceError("No available instance at the moment")

        try:
            await self.client.allocate(lease.port_slot.port, lease.context_id, request)
        except Exception:
            await self.registry.enqueue_release(lease.context_id)
            self._release_wakeup.set()
            raise

        return MasterAllocateResponse(
            context_id=lease.context_id,
            instance_port=lease.port_slot.port,
            instance_host=self.config.host,
        )

    async def release(self, context_id: str, request: GatewayReleaseRequest):
        await self.registry.enqueue_release(context_id, request)
        self._release_wakeup.set()
        return MasterReleaseResponse()

    async def release_all(self) -> None:
        for pending in await self.registry.pending_releases():
            try:
                await self.client.release(pending.context_id, pending.port, pending.release_request)
                await self.registry.complete_release(pending.context_id)
            except Exception:
                master_logger.warning(
                    "Failed releasing %s",
                    pending.context_id,
                    exc_info=True,
                )

    async def release_loop(self):
        while True:
            try:
                try:
                    await asyncio.wait_for(self._release_wakeup.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass

                self._release_wakeup.clear()
                await self.release_all()
            except asyncio.CancelledError:
                raise
            except Exception:
                master_logger.exception("Release loop iteration failed")
