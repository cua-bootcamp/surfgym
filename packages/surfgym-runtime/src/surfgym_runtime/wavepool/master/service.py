import asyncio

from surfgym_contracts.protocol.gateway_to_upstream import AllocateRequest
from surfgym_contracts.protocol.upstream_to_gateway import AllocateResponse

from surfgym_runtime.support import WavepoolConfig, master_logger
from surfgym_runtime.wavepool.master.error import MasterError, OutOfInstanceError
from surfgym_runtime.wavepool.master.transport import InstanceClient

_PORT_HEALTH_ERROR_TYPES = {
    "INSTANCE_REQUEST_FAILED",
    "UNEXPECTED",
    "INSTANCE_UNEXPECTED",
    "INSTANCE_NOT_IDLE",
}


class SlotRegistry:
    def __init__(
        self,
        instance_start_port: int,
        instance_n: int,
        contexts_per_instance: int,
    ):
        if contexts_per_instance < 1:
            raise ValueError("contexts_per_instance must be >= 1")

        self.ports = {instance_start_port + i for i in range(instance_n)}
        self.contexts_per_instance = contexts_per_instance

        self._allocated_by_port = {port: 0 for port in self.ports}
        self._lease_by_instance: dict[str, int] = {}
        self._broken: set[int] = set()
        self._recovering: set[int] = set()
        self._lock = asyncio.Lock()

    async def claim(self) -> int | None:
        async with self._lock:
            for port in sorted(self.ports):
                if port in self._broken or port in self._recovering:
                    continue

                if self._allocated_by_port[port] < self.contexts_per_instance:
                    self._allocated_by_port[port] += 1
                    return port

            return None

    async def commit(self, instance_id: str, port: int) -> None:
        async with self._lock:
            if port not in self.ports:
                raise ValueError(f"Unknown port: {port}")

            if instance_id in self._lease_by_instance:
                raise ValueError(f"Duplicate instance_id lease: {instance_id}")

            self._lease_by_instance[instance_id] = port

    async def rollback_claim(self, port: int) -> None:
        async with self._lock:
            if port not in self.ports:
                return

            self._allocated_by_port[port] = max(0, self._allocated_by_port[port] - 1)

    async def release(self, instance_id: str, port: int) -> None:
        async with self._lock:
            leased_port = self._lease_by_instance.pop(instance_id, None)

            if leased_port is None:
                return

            if leased_port != port:
                master_logger.warning(
                    "Release port mismatch: instance_id=%s lease_port=%s request_port=%s",
                    instance_id,
                    leased_port,
                    port,
                )

            self._allocated_by_port[leased_port] = max(
                0,
                self._allocated_by_port[leased_port] - 1,
            )

    async def mark_broken(self, port: int) -> None:
        async with self._lock:
            if port not in self.ports:
                return

            self._recovering.discard(port)
            self._broken.add(port)

    async def mark_recovered(self, port: int) -> None:
        async with self._lock:
            if port not in self.ports:
                return

            if self._allocated_by_port[port] != 0:
                self._recovering.discard(port)
                self._broken.add(port)
                return

            self._recovering.discard(port)
            self._broken.discard(port)

    async def recover_all(self) -> list[int]:
        async with self._lock:
            candidates = [
                port
                for port in self._broken - self._recovering
                if self._allocated_by_port[port] == 0
            ]
            self._recovering.update(candidates)
            return candidates


class MasterService:
    def __init__(self, registry: SlotRegistry, wavepool_config: WavepoolConfig):
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
            await self.registry.commit(instance_id, port)
            return AllocateResponse(
                instance_id=instance_id,
                instance_port=port,
                instance_host=self.config.host,
            )
        except MasterError as exc:
            await self.registry.rollback_claim(port)

            if _should_mark_port_broken(exc):
                await self.registry.mark_broken(port)

            raise
        except Exception:
            await self.registry.rollback_claim(port)
            await self.registry.mark_broken(port)
            raise

    async def release(self, instance_id: str, port: int):
        try:
            response = await self.client.release(instance_id, port)
            return response
        except MasterError as exc:
            if _should_mark_port_broken(exc):
                await self.registry.mark_broken(port)

            raise
        except Exception:
            await self.registry.mark_broken(port)
            raise
        finally:
            await self.registry.release(instance_id, port)

    async def recover_all(self):
        candidates = await self.registry.recover_all()

        for port in candidates:
            try:
                if not await self.client.is_idle(port):
                    await self.client.force_release(port)

                if await self.client.is_idle(port):
                    await self.registry.mark_recovered(port)
                else:
                    await self.registry.mark_broken(port)
            except Exception:
                master_logger.warning("Failed recovering %s", port, exc_info=True)
                await self.registry.mark_broken(port)

    async def recover_loop(self):
        while True:
            await asyncio.sleep(10)
            await self.recover_all()


def _should_mark_port_broken(exc: MasterError) -> bool:
    return exc.error_type in _PORT_HEALTH_ERROR_TYPES
