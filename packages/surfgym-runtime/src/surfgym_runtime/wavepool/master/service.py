import asyncio

from surfgym_contracts.protocol.gateway_to_upstream import (
    GatewayAllocateRequest,
    GatewayReleaseRequest,
)
from surfgym_contracts.protocol.upstream_to_gateway import MasterAllocateResponse, ReleaseResponse

from surfgym_runtime.support import WavepoolConfig, master_logger
from surfgym_runtime.wavepool.master.error import OutOfInstanceError
from surfgym_runtime.wavepool.master.registry import LeaseRegistry
from surfgym_runtime.wavepool.master.transport import InstanceClient


class MasterService:
    def __init__(self, registry: LeaseRegistry, wavepool_config: WavepoolConfig):
        self.config = wavepool_config
        self.client = InstanceClient(wavepool_config.host, wavepool_config.process_timeout)
        self.registry = registry

    async def close(self):
        await self.client.close()

    async def allocate(self, request: GatewayAllocateRequest) -> MasterAllocateResponse:
        lease = await self.registry.reserve_lease()
        if lease is None:
            raise OutOfInstanceError("No available instance at the moment")

        try:
            await self.client.allocate(lease.port_slot.port, lease.context_id, request)
        except Exception:
            await self.registry.mark_lease(lease.context_id)
            raise

        return MasterAllocateResponse(
            context_id=lease.context_id,
            instance_port=lease.port_slot.port,
            instance_host=self.config.host,
        )

    async def release(self, context_id: str, request: GatewayReleaseRequest) -> ReleaseResponse:
        try:
            lease = self.registry.require_lease(context_id)
            await self.client.release(context_id, lease.port_slot.port, request)
        except Exception:
            await self.registry.mark_lease(context_id, request)
            raise

        await self.registry.release_lease(context_id)
        return ReleaseResponse()

    # [TODO] Batch Release
    async def release_all(self):
        for lease in self.registry.broken_lease:
            try:
                await self.release(lease.context_id, lease.release_request)
            except Exception:
                master_logger.warning("Failed recovering %s", lease.context_id, exc_info=True)

    async def release_loop(self):
        while True:
            await asyncio.sleep(10)
            await self.release_all()
