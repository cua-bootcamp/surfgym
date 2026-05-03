import multiprocessing
import os
import signal
import threading
import traceback
from functools import lru_cache
from multiprocessing.pool import Pool
from typing import Any, Callable, ParamSpec, TypeVar, overload

from requests import Response

from src.config import InstanceConfig
from src.gateway.client import InstanceClient, MasterClient
from src.gateway.error import (
    HttpStackOperationTimeoutError,
    OmniboxBusyError,
)
from src.gateway.service import Deadline
from src.omnibox.protocol.instance_server_response import (
    InteractiveTreeResponse,
    ScreenshotResponse,
    SnapshotResponse,
)
from src.omnibox.protocol.master_server_response import GetInstanceResponse
from src.omnibox.protocol.omnibox_command import (
    InteractiveTreeCommand,
    NavigateCommand,
    OmniboxCommand,
    OmniboxCommandPayload,
    SnapShotCommand,
)

_R = TypeVar("_R")
_P = ParamSpec("_P")


class ProcessIsolator:
    def __init__(self, max_workers: int) -> None:
        self.max_workers = max_workers
        self.process_pool: Pool | None = None
        self._shutdown = False
        self._process_lock = threading.Lock()

    def run(
        self,
        func: Callable[_P, _R],
        check_timeout: Callable[[str], None],
        timeout: float,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        pool = self.process_pool
        if self._shutdown:
            raise RuntimeError("Process isolator is shut down")
        if pool is None:
            raise RuntimeError("Process isolator is not started")

        async_result = pool.apply_async(
            self._execute_wrapper,
            (func, args, kwargs, func.__name__, timeout),
        )

        elapsed = 0.0
        poll_interval = 1.0

        while elapsed < timeout:
            check_timeout(func.__name__)

            wait_for = min(poll_interval, timeout - elapsed)
            try:
                return async_result.get(timeout=wait_for)
            except multiprocessing.TimeoutError:
                elapsed += wait_for

        raise HttpStackOperationTimeoutError(f"Process timeout after {timeout:.0f}s")

    def start(self) -> None:
        with self._process_lock:
            if self._shutdown:
                raise RuntimeError("Process isolator is shut down")
            if self.process_pool is not None:
                raise RuntimeError("Process isolator alreay started")

            self.process_pool = multiprocessing.Pool(
                processes=self.max_workers,
                # initializer=self._worker_init,
            )

    def stop(self) -> None:
        with self._process_lock:
            self._shutdown = True
            pool = self.process_pool
            self.process_pool = None

        if pool is None:
            return

        pool.terminate()
        pool.join()

    # @staticmethod
    # def _worker_init() -> None:
    #     def signal_handler(signum, frame):
    #         os._exit(1)

    #     signal.signal(signal.SIGTERM, signal_handler)
    #     signal.signal(signal.SIGINT, signal_handler)
    #     os.setpgrp()

    @staticmethod
    def _execute_wrapper(func, args, kwargs, func_name: str, hard_timeout: float):
        worker_pid = os.getpid()

        def timeout_handler(signum, frame):
            os._exit(1)

        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(max(1, int(hard_timeout)))
            return func(*args, **kwargs)
        except Exception as exc:
            print(f"Worker {worker_pid} exception in {func_name}: {exc}")
            traceback.print_exc()
            raise
        finally:
            signal.alarm(0)


class GatewayPool:
    def __init__(
        self,
        *,
        pool_workers: int,
        instance_config: InstanceConfig,
    ):
        self.TIMEOUT_CAP = 10
        self._instance_config = instance_config

        control_workers = max(1, pool_workers // 10)
        general_workers = max(1, pool_workers - control_workers)
        self._control_pool = ProcessIsolator(
            max_workers=control_workers,
        )
        self._general_pool = ProcessIsolator(max_workers=general_workers)

    def start(self):
        self._control_pool.start()
        self._general_pool.start()

    def stop(self):
        self._control_pool.stop()
        self._general_pool.stop()

    def _run(
        self,
        pool: ProcessIsolator,
        context: str,
        deadline: Deadline,
        timeout_cap: float,
        func: Callable[_P, _R],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        deadline.check(context)
        return pool.run(
            func=func,
            check_timeout=deadline.check,
            timeout=deadline.timeout(timeout_cap),
            *args,
            **kwargs,
        )

    def allocate(self, deadline: Deadline):
        return self._run(
            self._control_pool,
            context="allocate",
            deadline=deadline,
            timeout_cap=self.TIMEOUT_CAP,
            func=allocate_instance,
            host=self._instance_config.host,
            port=self._instance_config.master_port,
        )

    def release(self, deadline: Deadline, instance_id: str, instance_port: int):
        return self._run(
            self._control_pool,
            context="release",
            deadline=deadline,
            timeout_cap=self.TIMEOUT_CAP,
            func=release_instance,
            host=self._instance_config.host,
            port=self._instance_config.master_port,
            instance_id=instance_id,
            instance_port=instance_port,
        )

    def execute_browser_command(
        self, deadline: Deadline, instance_id: str, instance_port: int, command: OmniboxCommand
    ):
        return self._run(
            self._general_pool,
            context="execute_browser_command",
            deadline=deadline,
            timeout_cap=self.TIMEOUT_CAP,
            func=execute_browser_command,
            host=self._instance_config.host,
            port=instance_port,
            instance_id=instance_id,
            command=command,
        )

    def screenshot(self, deadline: Deadline, instance_id: str, instance_port: int):
        return self._run(
            self._general_pool,
            context="screenshot",
            deadline=deadline,
            timeout_cap=self.TIMEOUT_CAP,
            func=screenshot,
            host=self._instance_config.host,
            port=instance_port,
            instance_id=instance_id,
        )

    def navigate(self, deadline: Deadline, instance_id: str, instance_port: int, url: str):
        self.execute_browser_command(deadline, instance_id, instance_port, NavigateCommand(url=url))

    def get_snapshot(
        self,
        deadline: Deadline,
        instance_id: str,
        instance_port: int,
        selectors: list[str],
        include_html: bool,
    ) -> SnapshotResponse:
        return self.execute_browser_command(
            deadline,
            instance_id,
            instance_port,
            SnapShotCommand(selectors=selectors, include_html=include_html),
        )

    def get_interactive_tree(
        self, deadline: Deadline, instance_id: str, instance_port: int
    ) -> InteractiveTreeResponse:
        return self.execute_browser_command(
            deadline, instance_id, instance_port, InteractiveTreeCommand()
        )


#########################
# pickle-safe functions #
#########################


def _handle_response(response: Response):
    if response.status_code != 200:
        if response.status_code >= 500:
            raise OmniboxBusyError(f"Error: {response.status_code} - {response.text}")
        raise Exception(f"Error: {response.status_code} - {response.text}")
    return response.json()


@lru_cache(maxsize=None)
def _master_client(host: str, port: int):
    return MasterClient(host=host, port=port)


def allocate_instance(host, port):
    response = _master_client(host=host, port=port).get_instance()
    json_payload = _handle_response(response)
    payload = GetInstanceResponse.model_validate(json_payload)
    return (payload.instance_id, payload.instance_host, payload.instance_port)


def release_instance(host, port, instance_id: str, instance_port: int):
    response = _master_client(host=host, port=port).reset(
        instance_id=instance_id, instance_port=instance_port
    )
    return _handle_response(response)


@lru_cache(maxsize=None)
def _instance_client(host: str, port: int):
    return InstanceClient(host=host, port=port)


@overload
def execute_browser_command(
    host: str,
    port: int,
    instance_id: str,
    command: InteractiveTreeCommand,
) -> InteractiveTreeResponse: ...


@overload
def execute_browser_command(
    host: str,
    port: int,
    instance_id: str,
    command: SnapShotCommand,
) -> SnapshotResponse: ...


@overload
def execute_browser_command(
    host: str,
    port: int,
    instance_id: str,
    command: OmniboxCommandPayload,
) -> Any: ...


def execute_browser_command(
    host: str,
    port: int,
    instance_id: str,
    command: OmniboxCommandPayload,
) -> SnapshotResponse | InteractiveTreeResponse | Any:
    response = _instance_client(host=host, port=port).execute(instance_id, command)
    json_payload = _handle_response(response)

    match command:
        case InteractiveTreeCommand():
            return InteractiveTreeResponse.model_validate(json_payload)

        case SnapShotCommand():
            return SnapshotResponse.model_validate(json_payload)

        case _:
            return json_payload


def screenshot(
    host: str,
    port: int,
    instance_id: str,
):
    response = _instance_client(host=host, port=port).screenshot(instance_id)
    json_payload = _handle_response(response)
    payload = ScreenshotResponse.model_validate(json_payload)
    return payload.snapshot_b64, payload.media_type, payload.x, payload.y
