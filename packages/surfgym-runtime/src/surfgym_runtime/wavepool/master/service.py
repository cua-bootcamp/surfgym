import asyncio

from surfgym_contracts.protocol.gateway_to_upstream import AllocateRequest
from surfgym_contracts.protocol.upstream_to_gateway import AllocateResponse, ReleaseResponse

from surfgym_runtime.support import WavepoolConfig, master_logger
from surfgym_runtime.wavepool.master.error import OutOfInstanceError
from surfgym_runtime.wavepool.master.transport import InstanceClient


class PortRegistry:
    def __init__(self, instance_start_port: int, instance_n: int):
        self.ports = {instance_start_port + i for i in range(instance_n)}
        self._available = {instance_start_port + i for i in range(instance_n)}
        self._broken: set[int] = set()
        self._recovering: set[int] = set()
        self._lock = asyncio.Lock()

    async def claim(self) -> int | None:
        async with self._lock:
            return self._available.pop() if self._available else None

    async def release(self, port: int):
        # [TODO] Need port checking logic?
        # if port not in self.ports:
        #     raise ValueError
        async with self._lock:
            self._broken.discard(port)
            self._recovering.discard(port)
            self._available.add(port)

    async def mark_broken(self, port: int):
        async with self._lock:
            self._available.discard(port)
            self._recovering.discard(port)
            self._broken.add(port)

    async def recover_all(self) -> list[int]:
        async with self._lock:
            candidates = list(self._broken - self._recovering)
            self._recovering.update(candidates)
            return candidates


class MasterService:
    def __init__(self, registry: PortRegistry, wavepool_config: WavepoolConfig):
        self.config = wavepool_config
        self.client = InstanceClient(wavepool_config.host, wavepool_config.process_timeout)
        self.registry = registry

    async def close(self):
        await self.client.close()

    async def allocate(self, request: AllocateRequest) -> AllocateResponse:
        port = await self.registry.claim()

        if port is None:
            await self.recover_all()
            port = await self.registry.claim()

        if port is None:
            raise OutOfInstanceError("No available instance at the moment")

        try:
            instance_id = await self.client.allocate(port, request)
            return AllocateResponse(
                instance_id=instance_id, instance_port=port, instance_host=self.config.host
            )
        except Exception:
            await self.registry.mark_broken(port)
            raise

    async def release(self, instance_id: str, port: int):
        try:
            await self.client.release(instance_id, port)
            await self.registry.release(port)
            return ReleaseResponse()
        except Exception:
            await self.registry.mark_broken(port)
            raise

    async def recover_all(self):
        candidates = await self.registry.recover_all()
        for port in candidates:
            try:
                if await self.client.is_idle(port):
                    await self.registry.release(port)
                    continue

                await self.client.force_release(port)

                if await self.client.is_idle(port):
                    await self.registry.release(port)
            except Exception:
                master_logger.warning("""Failed recovering %s""", port)
                await self.registry.mark_broken(port)

    async def recover_loop(self):
        while True:
            await asyncio.sleep(10)
            await self.recover_all()
