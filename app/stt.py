"""말 → 글자: faster-whisper 엔진 (GPU 여유가 없으면 CPU로 자동 전환)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.config import TRANSCRIPTS_DIR, WHISPER_DIR, register_cuda_dlls

# 모델별 GPU(float16)에 필요한 대략적 VRAM(MB). 여유분 포함.
VRAM_NEED_MB = {"small": 1200, "medium": 2600}


class STTError(Exception):
    """말→글자 관련 오류 (메시지는 한국어)."""


def free_vram_mb() -> int:
    """현재 남은 VRAM(MB). GPU가 없으면 0."""
    try:
        import torch

        if not torch.cuda.is_available():
            return 0
        free, _ = torch.cuda.mem_get_info(0)
        return free // (1024 * 1024)
    except Exception:
        return 0


def choose_device(model_size: str, prefer: str = "auto", free_mb: int | None = None) -> tuple[str, str]:
    """(device, compute_type)을 고른다. prefer: auto / cuda / cpu."""
    if prefer == "cpu":
        return "cpu", "int8"
    if free_mb is None:
        free_mb = free_vram_mb()
    need = VRAM_NEED_MB.get(model_size, 2600)
    if free_mb >= need:
        return "cuda", "float16"
    if prefer == "cuda":
        raise STTError(f"GPU 메모리가 부족합니다 (필요 약 {need}MB, 남은 {free_mb}MB).")
    return "cpu", "int8"


class WhisperEngine:
    """위스퍼 엔진. load()로 올리고 unload()로 내린다."""

    def __init__(self) -> None:
        self.model = None
        self.model_size: str | None = None
        self.device: str | None = None

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def status(self) -> str:
        if not self.loaded:
            return "꺼짐"
        where = "GPU" if self.device == "cuda" else "CPU"
        return f"켜짐 ({self.model_size}, {where})"

    def load(self, model_size: str = "small", prefer: str = "auto") -> str:
        if self.loaded and self.model_size == model_size:
            return self.status()
        self.unload()
        register_cuda_dlls()
        from faster_whisper import WhisperModel

        device, compute = choose_device(model_size, prefer)
        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute,
                                      download_root=str(WHISPER_DIR))
        except Exception as e:
            if device == "cuda" and prefer != "cuda":
                # GPU 로드 실패 시 CPU로 재시도
                device, compute = "cpu", "int8"
                self.model = WhisperModel(model_size, device=device, compute_type=compute,
                                          download_root=str(WHISPER_DIR))
            else:
                raise STTError(f"위스퍼 모델을 불러오지 못했습니다: {e}") from e
        self.model_size, self.device = model_size, device
        return self.status()

    def unload(self) -> None:
        if self.model is None:
            return
        self.model = None
        self.model_size = self.device = None
        import gc

        gc.collect()

    def transcribe(self, audio_path: str | Path, language: str = "ko") -> str:
        if not self.loaded:
            self.load()
        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise STTError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")
        try:
            segments, _info = self.model.transcribe(str(audio_path), language=language,
                                                    beam_size=5, vad_filter=True)
            return " ".join(s.text.strip() for s in segments).strip()
        except Exception as e:
            raise STTError(f"음성 변환 중 오류가 났습니다: {e}") from e


def save_transcript(text: str, path: Path | None = None) -> Path:
    if path is None:
        path = TRANSCRIPTS_DIR / f"stt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
