"""툴이 꺼질 때 하위 프로세스(GPT-SoVITS 서버·학습)도 함께 끄기 (Windows 'Job Object').

검은 창을 X로 닫으면 파이썬 정리 코드가 실행되지 못할 수 있다. 그래서 운영체제에
"이 프로세스가 죽으면 같은 그룹(Job)의 자식들도 모두 끝내라"고 미리 등록해 둔다.
Ollama 서버는 다른 프로그램도 쓰므로 그룹에서 빼서(breakaway) 실행한다.
"""
from __future__ import annotations

import os

_job = None
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def kill_children_on_exit() -> bool:
    """성공하면 True. 윈도우가 아니거나 실패해도 툴은 정상 동작한다."""
    global _job
    if os.name != "nt" or _job is not None:
        return _job is not None
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x0800
    JobObjectExtendedLimitInformation = 9

    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return False
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
    ok = k32.SetInformationJobObject(wintypes.HANDLE(job), JobObjectExtendedLimitInformation,
                                     ctypes.byref(info), ctypes.sizeof(info))
    ok = ok and k32.AssignProcessToJobObject(wintypes.HANDLE(job), wintypes.HANDLE(k32.GetCurrentProcess()))
    if not ok:
        k32.CloseHandle(wintypes.HANDLE(job))
        return False
    _job = job  # 핸들을 닫지 않고 들고 있어야 함 (프로세스가 끝나면 OS가 닫으며 자식 종료)
    return True
