"""Windows process-tree ownership backed by an atomically assigned Job Object.

``AssignProcessToJobObject`` after ``CreateProcess`` leaves a window where a
new child can outlive its supervisor.  This module instead passes a precreated
kill-on-close job through ``PROC_THREAD_ATTRIBUTE_JOB_LIST`` to CreateProcessW.
Windows therefore associates the root process before its user code can run;
normal descendants join the job as well because this job permits no breakaway.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from typing import Mapping, Sequence


_IS_WINDOWS = os.name == "nt"

_ERROR_INSUFFICIENT_BUFFER = 122
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_CREATE_NO_WINDOW = 0x08000000
_PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_INFINITE = 0xFFFFFFFF


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", _STARTUPINFOW), ("lpAttributeList", wintypes.LPVOID)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    ]


def _require_windows() -> None:
    if not _IS_WINDOWS:
        raise RuntimeError("OwnedProcessWindows is only available on Windows")


def _kernel32() -> ctypes.WinDLL:
    _require_windows()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
    )
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.InitializeProcThreadAttributeList.argtypes = (
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t),
    )
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = (
        wintypes.LPVOID, wintypes.DWORD, ctypes.c_size_t, wintypes.LPVOID,
        ctypes.c_size_t, wintypes.LPVOID, wintypes.LPVOID,
    )
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.DeleteProcThreadAttributeList.argtypes = (wintypes.LPVOID,)
    kernel32.DeleteProcThreadAttributeList.restype = None
    kernel32.CreateProcessW.argtypes = (
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID,
        wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        wintypes.LPVOID, ctypes.POINTER(_PROCESS_INFORMATION),
    )
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.QueryInformationJobObject.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    return kernel32


def _raise_last_error(operation: str) -> None:
    raise OSError(ctypes.get_last_error(), f"{operation} failed")


class OwnedProcessWindows:
    """A minimal Popen-like handle whose Job Object owns its whole process tree."""

    def __init__(self, *, process_handle: int, job_handle: int, pid: int) -> None:
        self._process_handle = process_handle
        self._job_handle = job_handle
        self.pid = pid
        self._exit_code: int | None = None
        self._closed = False

    @classmethod
    def spawn(
        cls,
        args: Sequence[str | os.PathLike[str]],
        *,
        cwd: str | os.PathLike[str] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> OwnedProcessWindows:
        """Create a root process already assigned to a kill-on-close job.

        This intentionally supports only the supervisor's simple no-pipe launch
        contract.  Adding inherited handles needs a separate attribute-list
        contract and must not silently weaken atomic job assignment.
        """
        _require_windows()
        if not args:
            raise ValueError("args must not be empty")

        kernel32 = _kernel32()
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            _raise_last_error("CreateJobObjectW")
        try:
            limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not kernel32.SetInformationJobObject(
                job,
                _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                _raise_last_error("SetInformationJobObject")

            size = ctypes.c_size_t()
            ctypes.set_last_error(0)
            kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
            if ctypes.get_last_error() != _ERROR_INSUFFICIENT_BUFFER:
                _raise_last_error("InitializeProcThreadAttributeList(size)")
            attributes = ctypes.create_string_buffer(size.value)
            attribute_list = ctypes.cast(attributes, wintypes.LPVOID)
            if not kernel32.InitializeProcThreadAttributeList(attribute_list, 1, 0, ctypes.byref(size)):
                _raise_last_error("InitializeProcThreadAttributeList")
            try:
                job_value = wintypes.HANDLE(job)
                if not kernel32.UpdateProcThreadAttribute(
                    attribute_list, 0, _PROC_THREAD_ATTRIBUTE_JOB_LIST,
                    ctypes.byref(job_value), ctypes.sizeof(job_value), None, None,
                ):
                    _raise_last_error("UpdateProcThreadAttribute(JOB_LIST)")

                startup = _STARTUPINFOEXW()
                startup.StartupInfo.cb = ctypes.sizeof(startup)
                startup.lpAttributeList = attribute_list
                process = _PROCESS_INFORMATION()
                command = subprocess.list2cmdline([os.fspath(item) for item in args])
                command_buffer = ctypes.create_unicode_buffer(command)
                environment = _environment_block(env)
                # The supervisor is a background service; its Python helpers must
                # not create a transient console window.  A headed browser has its
                # own process/UI policy and is not enabled by this flag.
                flags = _EXTENDED_STARTUPINFO_PRESENT | _CREATE_NO_WINDOW
                if environment is not None:
                    flags |= _CREATE_UNICODE_ENVIRONMENT
                created = kernel32.CreateProcessW(
                    None, command_buffer, None, None, False, flags,
                    environment, os.fspath(cwd) if cwd is not None else None,
                    ctypes.byref(startup.StartupInfo), ctypes.byref(process),
                )
                if not created:
                    _raise_last_error("CreateProcessW")
            finally:
                kernel32.DeleteProcThreadAttributeList(attribute_list)
            if not kernel32.CloseHandle(process.hThread):
                kernel32.CloseHandle(process.hProcess)
                _raise_last_error("CloseHandle(process thread)")
            return cls(process_handle=process.hProcess, job_handle=job, pid=process.dwProcessId)
        except BaseException:
            kernel32.CloseHandle(job)
            raise

    def poll(self) -> int | None:
        self._ensure_open()
        if self._exit_code is not None:
            return self._exit_code
        assert self._process_handle is not None
        # STILL_ACTIVE (259) is a valid Windows exit code.  Ask the waitable
        # process handle whether it has signalled before interpreting that value.
        state = _kernel32().WaitForSingleObject(self._process_handle, 0)
        if state == _WAIT_TIMEOUT:
            return None
        if state != _WAIT_OBJECT_0:
            _raise_last_error("WaitForSingleObject")
        return self._reap_root_exit()

    def wait(self, timeout: float | None = None) -> int:
        self._ensure_open()
        if self._exit_code is not None:
            return self._exit_code
        assert self._process_handle is not None
        milliseconds = _INFINITE if timeout is None else max(0, int(timeout * 1000))
        result = _kernel32().WaitForSingleObject(self._process_handle, milliseconds)
        if result == _WAIT_TIMEOUT:
            raise subprocess.TimeoutExpired(args=self.pid, timeout=timeout)
        if result != _WAIT_OBJECT_0:
            _raise_last_error("WaitForSingleObject")
        code = self.poll()
        assert code is not None
        return code

    def terminate(self) -> None:
        self._terminate_job(exit_code=1)

    def kill(self) -> None:
        self._terminate_job(exit_code=1)

    def active_process_count(self) -> int:
        self._ensure_open()
        accounting = _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        if not _kernel32().QueryInformationJobObject(
            self._job_handle, _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(accounting), ctypes.sizeof(accounting), None,
        ):
            _raise_last_error("QueryInformationJobObject")
        return accounting.ActiveProcesses

    def is_quiescent(self) -> bool:
        return self.active_process_count() == 0

    def wait_for_quiescence(self, timeout: float = 3.0) -> bool:
        """Wait for the Job's asynchronously updated active count to reach zero."""
        self._ensure_open()
        if timeout < 0:
            raise ValueError("timeout must not be negative")
        deadline = time.monotonic() + timeout
        while True:
            if self.is_quiescent():
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.02, max(0, deadline - time.monotonic())))

    def terminate_and_check_quiescent(self, timeout: float = 3.0) -> bool:
        """Kill the owned tree and prove quiescence from Job accounting."""
        if timeout < 0:
            raise ValueError("timeout must not be negative")
        self._terminate_job(exit_code=1)
        return self.wait_for_quiescence(timeout)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        kernel32 = _kernel32()
        try:
            # Closing the last job handle applies JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
            kernel32.CloseHandle(self._job_handle)
        finally:
            if self._process_handle is not None:
                kernel32.CloseHandle(self._process_handle)
                self._process_handle = None

    def _terminate_job(self, *, exit_code: int) -> None:
        self._ensure_open()
        if not _kernel32().TerminateJobObject(self._job_handle, exit_code):
            _raise_last_error("TerminateJobObject")

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("owned process handle is closed")

    def _reap_root_exit(self) -> int:
        """Cache exit status and release our process handle for Job zero-count proof."""
        assert self._process_handle is not None
        kernel32 = _kernel32()
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(self._process_handle, ctypes.byref(exit_code)):
            _raise_last_error("GetExitCodeProcess")
        if not kernel32.CloseHandle(self._process_handle):
            _raise_last_error("CloseHandle(process)")
        self._process_handle = None
        self._exit_code = exit_code.value
        return self._exit_code


def _environment_block(env: Mapping[str, str] | None) -> ctypes.Array[ctypes.c_wchar] | None:
    if env is None:
        return None
    entries = [f"{key}={value}" for key, value in sorted(env.items(), key=lambda item: item[0].upper())]
    if any("=" in key or "\x00" in key or "\x00" in value for key, value in env.items()):
        raise ValueError("environment keys and values must not contain NUL or '=' in keys")
    return ctypes.create_unicode_buffer("\x00".join(entries) + "\x00\x00")
