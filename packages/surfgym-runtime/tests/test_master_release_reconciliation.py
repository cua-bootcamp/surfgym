import asyncio
from collections import Counter
from types import SimpleNamespace

import pytest
import surfgym_runtime.wavepool.master.service as master_service
from surfgym_contracts.protocol.gateway_to_upstream import GatewayReleaseRequest
from surfgym_contracts.task import ServerReset, Website
from surfgym_runtime.wavepool.bindings import web_cleanup_cookie
from surfgym_runtime.wavepool.master.error import InstanceRequestFailed
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
    master.config = SimpleNamespace(
        process_timeout=SimpleNamespace(
            binding_cleanup_horizon=0.08,
            binding_cleanup_retry_interval=0.001,
        )
    )
    master._release_tasks = {}
    master._release_semaphore = asyncio.Semaphore(MasterService._MAX_CONCURRENT_RELEASES)
    master._closing = False
    master._closed = False
    return master, registry, lease.context_id


def _master_with_retained_release_owner(client: object, registry: LeaseRegistry) -> MasterService:
    """Construct only the Master state used by the retained-release tests.

    Production normally creates this state in ``MasterService.__init__``.  The
    focused tests avoid an HTTP client and pin the ownership contract directly.
    """
    master = object.__new__(MasterService)
    master.registry = registry
    master.client = client
    master.config = SimpleNamespace(
        process_timeout=SimpleNamespace(
            binding_cleanup_horizon=0.08,
            binding_cleanup_retry_interval=0.001,
        )
    )
    master._release_wakeup = asyncio.Event()
    master._release_tasks = {}
    master._release_semaphore = asyncio.Semaphore(MasterService._MAX_CONCURRENT_RELEASES)
    master._closing = False
    master._closed = False
    return master


def test_release_response_loss_keeps_lease_even_when_context_listing_is_empty():
    client = LostReleaseResponseClient(live_context_ids=set())
    master, registry, context_id = _master_with_pending_release(client)

    asyncio.run(master.release_all())

    assert len(client.release_calls) >= 2
    assert set(client.release_calls) == {context_id}
    assert client.live_context_calls == []
    assert [pending.context_id for pending in asyncio.run(registry.pending_releases())] == [
        context_id
    ]
    assert asyncio.run(registry.reserve_lease()) is None


def test_release_response_loss_keeps_lease_when_instance_still_has_context():
    client = LostReleaseResponseClient(live_context_ids={"context-id"})
    master, registry, context_id = _master_with_pending_release(client)
    client._live_context_ids = {context_id}

    asyncio.run(master.release_all())

    assert len(client.release_calls) >= 2
    assert set(client.release_calls) == {context_id}
    assert client.live_context_calls == []
    assert [pending.context_id for pending in asyncio.run(registry.pending_releases())] == [
        context_id
    ]
    assert asyncio.run(registry.reserve_lease()) is None


def test_instance_unknown_retries_inside_one_retained_master_release_owner():
    """An Instance timeout must not replace the pending release owner.

    The first caller observes only ``UNKNOWN``.  The retained Master task then
    retries the same descriptor; a duplicate ``release_all`` joins that task
    and cannot create another dispatch while the lease still owns capacity.
    """

    class UnknownThenTerminalClient:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.first_unknown = asyncio.Event()
            self.second_started = asyncio.Event()
            self.allow_terminal = asyncio.Event()

        async def release(
            self, context_id: str, _port: int, _request: GatewayReleaseRequest
        ) -> None:
            self.calls.append(context_id)
            if len(self.calls) == 1:
                self.first_unknown.set()
                raise InstanceRequestFailed("Instance release response is UNKNOWN")
            self.second_started.set()
            await self.allow_terminal.wait()

    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
        lease = await registry.reserve_lease("context-id")
        assert lease is not None
        await registry.enqueue_release(lease.context_id, GatewayReleaseRequest(hooks=[]))
        client = UnknownThenTerminalClient()
        master = _master_with_retained_release_owner(client, registry)
        first_waiter = asyncio.create_task(master.release_all())
        duplicate_waiter: asyncio.Task[None] | None = None
        try:
            await asyncio.wait_for(client.first_unknown.wait(), 1)
            await asyncio.wait_for(client.second_started.wait(), 1)
            retained = master._release_tasks[lease.context_id]
            assert not retained.done()
            assert await registry.reserve_lease() is None

            duplicate_waiter = asyncio.create_task(master.release_all())
            await asyncio.sleep(0)
            assert master._release_tasks[lease.context_id] is retained
            assert client.calls == [lease.context_id, lease.context_id]

            client.allow_terminal.set()
            await asyncio.wait_for(asyncio.gather(first_waiter, duplicate_waiter), 1)
            assert client.calls == [lease.context_id, lease.context_id]
            assert await registry.pending_releases() == []
            assert await registry.reserve_lease() is not None
        finally:
            client.allow_terminal.set()
            for waiter in (first_waiter, duplicate_waiter):
                if waiter is not None and not waiter.done():
                    waiter.cancel()
                if waiter is not None:
                    with __import__("contextlib").suppress(asyncio.CancelledError):
                        await waiter

    asyncio.run(scenario())


def test_retained_master_owner_replays_horizon_unknown_without_redispatch():
    """A bounded UNKNOWN result fences capacity and replays without a new call."""

    class AlwaysUnknownClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def release(
            self, context_id: str, _port: int, _request: GatewayReleaseRequest
        ) -> None:
            self.calls.append(context_id)
            raise InstanceRequestFailed("Instance release response is UNKNOWN")

    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
        lease = await registry.reserve_lease("context-id")
        assert lease is not None
        await registry.enqueue_release(lease.context_id, GatewayReleaseRequest(hooks=[]))
        client = AlwaysUnknownClient()
        master = _master_with_retained_release_owner(client, registry)
        await asyncio.wait_for(master.release_all(), 1)

        retained = master._release_tasks[lease.context_id]
        assert retained.done()
        calls_at_horizon = len(client.calls)
        assert calls_at_horizon >= 2
        assert await registry.reserve_lease() is None

        await master.release_all()
        assert master._release_tasks[lease.context_id] is retained
        assert len(client.calls) == calls_at_horizon
        assert [pending.context_id for pending in await registry.pending_releases()] == [
            lease.context_id
        ]

    asyncio.run(scenario())


def test_semaphore_queue_does_not_spend_owner_cleanup_horizon_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fifth owner starts its horizon only after a release-worker slot opens.

    Four owners occupy the fixed four-wide semaphore.  The controlled Master
    clock advances past the configured 720-second horizon while the fifth is
    queued; its first dispatch is UNKNOWN and its retry must retain the same
    owner until terminal completion.  No wall-clock wait is used.
    """

    clock = [0.0]
    monkeypatch.setattr(master_service, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    class SaturatedThenTerminalClient:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.first_four_started = asyncio.Event()
            self.allow_first_four = asyncio.Event()
            self.fifth_unknown = asyncio.Event()
            self.fifth_retry_started = asyncio.Event()
            self.allow_fifth_terminal = asyncio.Event()
            self._started: set[str] = set()

        async def release(
            self, context_id: str, _port: int, _request: GatewayReleaseRequest
        ) -> None:
            self.calls.append(context_id)
            if context_id != "owner-4":
                self._started.add(context_id)
                if len(self._started) == MasterService._MAX_CONCURRENT_RELEASES:
                    self.first_four_started.set()
                await self.allow_first_four.wait()
                return
            if self.calls.count(context_id) == 1:
                self.fifth_unknown.set()
                raise InstanceRequestFailed("first fifth-owner response is UNKNOWN")
            self.fifth_retry_started.set()
            await self.allow_fifth_terminal.wait()

    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=5)
        client = SaturatedThenTerminalClient()
        master = _master_with_retained_release_owner(client, registry)
        master.config.process_timeout.binding_cleanup_horizon = 720.0
        master.config.process_timeout.binding_cleanup_retry_interval = 0.0
        context_ids = [f"owner-{index}" for index in range(5)]
        for context_id in context_ids:
            lease = await registry.reserve_lease(context_id)
            assert lease is not None
            await registry.enqueue_release(context_id, GatewayReleaseRequest(hooks=[]))

        first_waiter = asyncio.create_task(master.release_all())
        duplicate_waiter: asyncio.Task[None] | None = None
        try:
            await asyncio.wait_for(client.first_four_started.wait(), 1)
            # The queued fifth owner has not dispatched.  Advancing only the
            # Master's clock past 720 seconds must not consume its horizon.
            clock[0] = 721.0
            client.allow_first_four.set()
            await asyncio.wait_for(client.fifth_unknown.wait(), 1)
            await asyncio.wait_for(client.fifth_retry_started.wait(), 1)

            retained = master._release_tasks["owner-4"]
            assert not retained.done()
            assert registry.require_lease("owner-4").context_id == "owner-4"
            assert registry._slots[0]._allocated_contexts == 1

            duplicate_waiter = asyncio.create_task(master.release_all())
            await asyncio.sleep(0)
            assert master._release_tasks["owner-4"] is retained
            assert Counter(client.calls) == Counter(
                {"owner-0": 1, "owner-1": 1, "owner-2": 1, "owner-3": 1, "owner-4": 2}
            )

            client.allow_fifth_terminal.set()
            await asyncio.wait_for(asyncio.gather(first_waiter, duplicate_waiter), 1)
            assert Counter(client.calls) == Counter(
                {"owner-0": 1, "owner-1": 1, "owner-2": 1, "owner-3": 1, "owner-4": 2}
            )
            assert await registry.pending_releases() == []
            assert master._release_tasks == {}
            assert registry._slots[0]._allocated_contexts == 0
        finally:
            client.allow_first_four.set()
            client.allow_fifth_terminal.set()
            for waiter in (first_waiter, duplicate_waiter):
                if waiter is not None and not waiter.done():
                    waiter.cancel()
                if waiter is not None:
                    with __import__("contextlib").suppress(asyncio.CancelledError):
                        await waiter

    asyncio.run(scenario())


def test_master_close_cancels_waiter_not_instance_cleanup_or_capacity() -> None:
    """Graceful close stops local owners without claiming downstream success."""
    class Client:
        def __init__(self) -> None:
            self.request_started = asyncio.Event()
            self.allow_instance_cleanup = asyncio.Event()
            self.closed = 0
            self.instance_cleanup = asyncio.create_task(self._cleanup())

        async def _cleanup(self) -> None:
            await self.allow_instance_cleanup.wait()

        async def release(
            self, _context_id: str, _port: int, _request: GatewayReleaseRequest
        ) -> None:
            self.request_started.set()
            # Model Instance.release(): its HTTP waiter is cancellable, while
            # its retained downstream cleanup owner is shielded.
            await asyncio.shield(self.instance_cleanup)

        async def close(self) -> None:
            self.closed += 1

    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
        lease = await registry.reserve_lease("context-id")
        assert lease is not None
        await registry.enqueue_release(lease.context_id, GatewayReleaseRequest(hooks=[]))
        client = Client()
        master = _master_with_retained_release_owner(client, registry)
        waiter = asyncio.create_task(master.release_all())
        try:
            await asyncio.wait_for(client.request_started.wait(), 1)
            retained = master._release_tasks[lease.context_id]
            await master.close()
            assert retained.done() and master._release_tasks == {}
            assert not client.instance_cleanup.done()
            assert [item.context_id for item in await registry.pending_releases()] == [lease.context_id]
            assert await registry.reserve_lease() is None
            await master.close()
            assert client.closed == 1
            with pytest.raises(asyncio.CancelledError):
                await waiter
            client.allow_instance_cleanup.set()
            await asyncio.wait_for(client.instance_cleanup, 1)
        finally:
            client.allow_instance_cleanup.set()
            if not waiter.done():
                waiter.cancel()
            with __import__("contextlib").suppress(asyncio.CancelledError):
                await waiter
            if not client.instance_cleanup.done():
                await client.instance_cleanup

    asyncio.run(scenario())


def test_master_close_is_idempotent_after_healthy_terminal_release() -> None:
    class Client:
        def __init__(self) -> None:
            self.closed = 0

        async def release(self, *_args: object) -> None:
            return None

        async def close(self) -> None:
            self.closed += 1

    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
        lease = await registry.reserve_lease("context-id")
        assert lease is not None
        await registry.enqueue_release(lease.context_id, GatewayReleaseRequest(hooks=[]))
        client = Client()
        master = _master_with_retained_release_owner(client, registry)
        await master.release_all()
        assert master._release_tasks == {}
        assert await registry.pending_releases() == []
        await master.close()
        await master.close()
        assert client.closed == 1

    asyncio.run(scenario())


def test_completed_context_id_is_a_bounded_tombstone_and_cannot_be_resurrected():
    registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
    lease = asyncio.run(registry.reserve_lease("context-id"))
    assert lease is not None
    asyncio.run(registry.enqueue_release(lease.context_id, GatewayReleaseRequest(hooks=[])))
    asyncio.run(registry.complete_release(lease.context_id))

    with pytest.raises(Exception, match="not reusable"):
        asyncio.run(registry.reserve_lease("context-id"))


def test_release_before_dispatch_fences_late_allocate_and_completed_replay_is_safe():
    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
        await registry.enqueue_release("context-id", GatewayReleaseRequest(hooks=[]))
        with pytest.raises(Exception, match="not reusable"):
            await registry.reserve_lease("context-id")
        await registry.complete_release("context-id")
        await registry.complete_release("context-id")
        lease = await registry.reserve_lease()
        assert lease is not None
        await registry.enqueue_release(lease.context_id, GatewayReleaseRequest(hooks=[]))
        await registry.complete_release(lease.context_id)
        await registry.complete_release(lease.context_id)
        assert (await registry.reserve_lease()) is not None

    asyncio.run(scenario())


def test_web_cleanup_cookie_has_a_stable_cross_process_vector():
    assert web_cleanup_cookie(
        "5e9408dc-75b7-4a54-9b94-e9ebb2749f1e",
        "http://127.0.0.1:3002/",
        "surfgym_session_id",
    ) == "df46aa25-7fb3-5207-addd-ee140829bdf5"


def test_confirmed_instance_exit_retries_retained_bindings_without_reusing_port():
    class RetainedBindingClient:
        def __init__(self) -> None:
            self.calls = 0
            self.bindings = []

        async def release_retained_bindings(self, lease):
            self.calls += 1
            self.bindings.append(lease)
            if self.calls == 1:
                raise RuntimeError("first finalizer response lost")

    async def scenario() -> None:
        registry = LeaseRegistry(instance_start_port=5400, instance_n=1, contexts_per_instance=1)
        website = Website(
            website_id="travel",
            url="http://127.0.0.1:3002/",
            server_reset=ServerReset(
                origin="http://127.0.0.1:3002",
                cookie_name="surfgym_session_id",
                reset_path="/api/state",
            ),
        )
        lease = await registry.reserve_lease("context-id", "secret-capability", [website])
        assert lease is not None
        client = RetainedBindingClient()
        master = object.__new__(MasterService)
        master.registry = registry
        master.client = client
        master._release_wakeup = asyncio.Event()
        master._release_tasks = {}

        await master.recover_instance_exit(5400, quiescent=True)
        assert master._release_wakeup.is_set()
        await master.release_all()
        assert await registry.pending_releases() == []
        assert await registry.reserve_lease() is None
        assert client.calls == 2
        assert client.bindings[0].web_bindings == lease.web_bindings

    asyncio.run(scenario())
