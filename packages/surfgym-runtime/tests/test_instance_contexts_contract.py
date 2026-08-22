import asyncio

import httpx
from fastapi.routing import APIRoute

from surfgym_runtime.support.config import ProcessTimeout
from surfgym_runtime.wavepool.instance.server import create_app
from surfgym_runtime.wavepool.master.transport import InstanceClient


def test_instance_contexts_endpoint_exposes_an_empty_context_snapshot_before_allocate():
    app = create_app(contexts_per_instance=1)
    route = next(route for route in app.routes if isinstance(route, APIRoute) and route.path == "/contexts")

    response = asyncio.run(route.endpoint())

    assert response.context_ids == ()


def test_master_transport_reads_instance_context_snapshot():
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/contexts"
            return httpx.Response(200, json={"context_ids": ["context-a"]})

        client = InstanceClient(
            "instance.test",
            ProcessTimeout(
                allocate=2,
                release=2,
                screenshot=2,
                observe=2,
                execute=2,
                layer_gap=0.1,
            ),
        )
        await client.client.aclose()
        client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            assert await client.live_context_ids(9000) == ("context-a",)
        finally:
            await client.close()

    asyncio.run(scenario())
