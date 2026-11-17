"""엔진 관리자(지휘자): 엔진을 켜고 끄며, GPU에는 한 번에 하나의 엔진만 올린다.

규칙 (기획서 5장)
- 위스퍼·멜로·GPT-SoVITS는 툴이 직접 로드/언로드한다.
- GPU를 쓰는 엔진을 올리기 전에 다른 GPU 엔진은 모두 내린다 (VRAM 6GB 보호).
- 멜로는 기본 CPU.
- 위스퍼는 GPU 여유가 없으면 CPU로 자동 전환 (stt.choose_device).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable


@dataclass
class EngineSlot:
    """관리자에 등록된 엔진 하나."""

    key: str            # 내부 이름 (whisper, melo, sovits, ollama)
    label: str          # 화면 이름
    engine: object      # load/unload/loaded/status/device 를 가진 객체

    def on_gpu(self) -> bool:
        dev = getattr(self.engine, "device", None) or ""
        return bool(getattr(self.engine, "loaded", False)) and str(dev).startswith("cuda")


def vram_info() -> dict:
    """GPU 전체 기준 VRAM 사용량(MB). 다른 프로그램이 쓰는 양도 포함.

    nvidia-smi를 먼저 쓴다: torch로 재면 그 자체로 VRAM 약 300MB(CUDA 기본 공간)를 차지하기 때문.
    """
    import subprocess

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        total, used, free = (int(x) for x in out.stdout.strip().splitlines()[0].split(","))
        return {"available": True, "total_mb": total, "used_mb": used, "free_mb": free}
    except Exception:
        pass
    try:
        import torch

        if not torch.cuda.is_available():
            return {"available": False, "total_mb": 0, "used_mb": 0, "free_mb": 0}
        free, total = torch.cuda.mem_get_info(0)
        mb = 1024 * 1024
        return {"available": True, "total_mb": total // mb, "used_mb": (total - free) // mb,
                "free_mb": free // mb}
    except Exception:
        return {"available": False, "total_mb": 0, "used_mb": 0, "free_mb": 0}


class EngineManager:
    def __init__(self) -> None:
        self.slots: dict[str, EngineSlot] = {}
        self.lock = threading.RLock()  # 버튼을 동시에 눌러도 엔진이 겹쳐 올라가지 않게
        self.log: list[str] = []

    # ---------- 등록 ----------
    def register(self, key: str, label: str, engine: object) -> None:
        self.slots[key] = EngineSlot(key, label, engine)

    def get(self, key: str):
        return self.slots[key].engine

    # ---------- GPU 규칙 ----------
    def free_gpu(self, except_key: str | None = None) -> list[str]:
        """except_key를 뺀 GPU 엔진을 모두 내린다. 내린 엔진 이름 목록을 돌려준다."""
        released = []
        with self.lock:
            for key, slot in self.slots.items():
                if key != except_key and slot.on_gpu():
                    slot.engine.unload()
                    released.append(slot.label)
        if released:
            self._note(f"GPU 비우기: {', '.join(released)} 내림")
        return released

    def gpu_engines(self) -> list[str]:
        return [s.label for s in self.slots.values() if s.on_gpu()]

    # ---------- 켜기/끄기 ----------
    def load(self, key: str, will_use_gpu: bool | Callable[[], bool] = False, **kwargs) -> str:
        """엔진을 켠다. GPU를 쓸 예정이면 먼저 다른 GPU 엔진을 내린다."""
        with self.lock:
            slot = self.slots[key]
            use_gpu = will_use_gpu() if callable(will_use_gpu) else will_use_gpu
            if use_gpu:
                self.free_gpu(except_key=key)
            status = slot.engine.load(**kwargs)
            # 켜고 나서도 두 개 이상이 GPU에 있으면 규칙 위반 → 방금 켠 것만 남긴다
            if slot.on_gpu():
                self.free_gpu(except_key=key)
            self._note(f"{slot.label} 켜짐: {slot.engine.status()}")
            return status

    def unload(self, key: str) -> str:
        with self.lock:
            slot = self.slots[key]
            slot.engine.unload()
            self._note(f"{slot.label} 꺼짐")
            return slot.engine.status()

    def unload_all(self) -> None:
        with self.lock:
            for key in self.slots:
                self.slots[key].engine.unload()
        self._note("모든 엔진 꺼짐")

    # ---------- 상태 ----------
    def status_rows(self) -> list[list[str]]:
        rows = []
        for slot in self.slots.values():
            loaded = getattr(slot.engine, "loaded", False)
            where = "-" if not loaded else ("GPU" if slot.on_gpu() else "CPU")
            rows.append([slot.label, "켜짐" if loaded else "꺼짐", where, slot.engine.status()])
        return rows

    def vram_text(self) -> str:
        v = vram_info()
        if not v["available"]:
            return "GPU를 찾을 수 없습니다 (CPU만 사용)"
        pct = 100 * v["used_mb"] / max(v["total_mb"], 1)
        on_gpu = ", ".join(self.gpu_engines()) or "없음"
        return (f"VRAM 사용 {v['used_mb']:,} / {v['total_mb']:,} MB ({pct:.0f}%) · "
                f"남은 용량 {v['free_mb']:,} MB · GPU에 올라간 엔진: {on_gpu}")

    def _note(self, msg: str) -> None:
        self.log.append(msg)
        del self.log[:-50]


def build_default_manager() -> EngineManager:
    """툴에서 쓰는 기본 관리자 (위스퍼, 멜로 등록)."""
    from app.stt import WhisperEngine
    from app.tts import MeloEngine

    m = EngineManager()
    m.register("whisper", "위스퍼 (말→글자)", WhisperEngine())
    m.register("melo", "멜로 (글자→말)", MeloEngine())
    return m
