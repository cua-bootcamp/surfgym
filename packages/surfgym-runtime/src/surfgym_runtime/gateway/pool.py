import multiprocessing
import os
import signal
import threading
import traceback
from functools import lru_cache
from multiprocessing.pool import Pool
from typing import Any, Callable, Optional, ParamSpec, TypeVar, overload

from requests import Response
from surfgym_contracts.command import (
    Command,
    CommandPayload,
    InteractiveTreeCommand,
    ObserveCommand,
)
from surfgym_contracts.protocol.instance_to_gateway import (
    InteractiveTreeResponse,
    ObservationResponse,
    ScreenshotResponse,
)
from surfgym_contracts.protocol.master_to_gateway import GetInstanceResponse
from surfgym_contracts.task import Action, Evaluation, Website

from surfgym_runtime.gateway.client import InstanceClient, MasterClient
from surfgym_runtime.gateway.error import (
    Deadline,
    HttpStackOperationTimeoutError,
    InstanceBusyError,
)
from surfgym_runtime.support.config import WavepoolConfig

_R = TypeVar("_R")
_P = ParamSpec("_P")
_IS_WINDOWS = os.name == "nt"


class ProcessIsolator:
    def __init__(self, max_workers: int) -> None:
        self.max_workers = max_workers
        self.process_pool: Pool | None = None
        self._started = False
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
        if self._shutdown:
            raise RuntimeError("Process isolator is shut down")
        if not self._started:
            raise RuntimeError("Process isolator is not started")

        if _IS_WINDOWS:
            check_timeout(func.__name__)
            return func(*args, **kwargs)

        pool = self.process_pool
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
            if self._started:
                raise RuntimeError("Process isolator already started")

            if _IS_WINDOWS:
                self._started = True
                return

            self.process_pool = multiprocessing.Pool(processes=self.max_workers)
            self._started = True

    def stop(self) -> None:
        with self._process_lock:
            self._shutdown = True
            self._started = False
            pool = self.process_pool
            self.process_pool = None

        if pool is None:
            return

        pool.terminate()
        pool.join()

    @staticmethod
    def _execute_wrapper(
        func: Callable[..., _R],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        func_name: str,
        hard_timeout: float,
    ) -> _R:
        worker_pid = os.getpid()

        if not hasattr(signal, "SIGALRM") or not hasattr(signal, "alarm"):
            return func(*args, **kwargs)

        def timeout_handler(signum: int, frame: object) -> None:
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
        instance_config: WavepoolConfig,
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

    def allocate(self, deadline: Deadline, websites: list[Website], setup: Optional[list[Action]]):
        return self._run(
            self._control_pool,
            context="allocate",
            deadline=deadline,
            timeout_cap=self.TIMEOUT_CAP,
            func=allocate_instance,
            host=self._instance_config.host,
            port=self._instance_config.master_port,
            websites=websites,
            setup=setup,
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
        self, deadline: Deadline, instance_id: str, instance_port: int, command: Command
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

    def get_snapshot(
        self,
        deadline: Deadline,
        instance_id: str,
        instance_port: int,
        evaluation: Evaluation,
    ) -> ObservationResponse:
        return self.execute_browser_command(
            deadline,
            instance_id,
            instance_port,
            ObserveCommand(evaluation=evaluation),
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
            raise InstanceBusyError(f"Error: {response.status_code} - {response.text}")
        raise Exception(f"Error: {response.status_code} - {response.text}")
    return response.json()


@lru_cache(maxsize=None)
def _master_client(host: str, port: int):
    return MasterClient(host=host, port=port)


def allocate_instance(host: str, port: int, websites: list[Website], setup: Optional[list[Action]]):
    response = _master_client(host=host, port=port).get_instance(websites, setup)
    json_payload = _handle_response(response)
    payload = GetInstanceResponse.model_validate(json_payload)
    return (payload.instance_id, payload.instance_host, payload.instance_port)


def release_instance(host: str, port: int, instance_id: str, instance_port: int):
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
    command: ObserveCommand,
) -> ObservationResponse: ...


@overload
def execute_browser_command(
    host: str,
    port: int,
    instance_id: str,
    command: CommandPayload,
) -> Any: ...


def execute_browser_command(
    host: str,
    port: int,
    instance_id: str,
    command: CommandPayload,
) -> ObservationResponse | InteractiveTreeResponse | Any:
    response = _instance_client(host=host, port=port).execute(instance_id, command)
    json_payload = _handle_response(response)

    match command:
        case InteractiveTreeCommand():
            return InteractiveTreeResponse.model_validate(json_payload)

        case ObserveCommand():
            return ObservationResponse.model_validate(json_payload)

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
