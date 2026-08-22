import asyncio

from surfgym_contracts.protocol.gateway_to_upstream import GatewayReleaseRequest
from surfgym_runtime.wavepool.master.registry import LeaseRegistry
from surfgym_runtime.wavepool.master.service import MasterService


class LostReleaseResponseClient:
    def __init__(self, live_context_ids: set[str]):
        self._live_context_ids = live_context_ids
        self.release_calls: list[str] = []
        self.live_context_calls: list[int] = []

    async def release(self, context_id: str, _port: int, _request: GatewayReleaseRequest):
        self.release_calls.append(context_id)
        raise RuntimeError("release response was lost")

    async def live_context_ids(self, port: int) -> set[str]:
        self.live_context_calls.append(port)
        return self._live_context_ids


def _master_with_pending_release(client: LostReleaseResponseClient):
    registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
    lease = asyncio.run(registry.reserve_lease())
    assert lease is not None
    asyncio.run(registry.enqueue_release(lease.context_id, GatewayReleaseRequest(hooks=[])))

    master = object.__new__(MasterService)
    master.registry = registry
    master.client = client
    return master, registry, lease.context_id


def test_release_response_loss_completes_lease_only_when_instance_confirms_context_gone():
    client = LostReleaseResponseClient(live_context_ids=set())
    master, registry, context_id = _master_with_pending_release(client)

    asyncio.run(master.release_all())

    assert client.release_calls == [context_id]
    assert client.live_context_calls == [5400]
    assert asyncio.run(registry.pending_releases()) == []
    assert asyncio.run(registry.reserve_lease()) is not None


def test_release_response_loss_keeps_lease_when_instance_still_has_context():
    client = LostReleaseResponseClient(live_context_ids={"context-id"})
    master, registry, context_id = _master_with_pending_release(client)
    client._live_context_ids = {context_id}

    asyncio.run(master.release_all())

    assert client.release_calls == [context_id]
    assert client.live_context_calls == [5400]
    assert [pending.context_id for pending in asyncio.run(registry.pending_releases())] == [
        context_id
    ]
    assert asyncio.run(registry.reserve_lease()) is None
