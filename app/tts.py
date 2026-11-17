"""글자 → 말(기본): MeloTTS 한국어 엔진. 기본은 CPU로 돌려 GPU 경쟁을 피한다."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from app.config import OUTPUTS_DIR, PROJECT_ROOT

# 윈도우에서는 MeCab(일본어용)과 mecab(한국어용) 폴더 이름이 대소문자만 달라 충돌한다.
# 그래서 한국어용(python-mecab-ko)은 별도 폴더에 설치해 두고 여기서 경로만 추가한다.
MECAB_KO_DIR = PROJECT_ROOT / "engines" / "mecab_ko"

SPEED_MIN, SPEED_MAX = 0.5, 2.0


class TTSError(Exception):
    """글자→말 관련 오류 (메시지는 한국어)."""


def _patch_korean_mecab() -> None:
    """g2pkk(한국어 발음 변환기)가 윈도우에서 eunjeon 대신 python-mecab-ko를 쓰게 한다."""
    if str(MECAB_KO_DIR) not in sys.path:
        sys.path.append(str(MECAB_KO_DIR))
    try:
        import mecab  # python-mecab-ko
        import g2pkk.g2pkk as g2pkk_mod
    except ImportError as e:
        raise TTSError(
            "한국어 형태소 분석기(python-mecab-ko)를 찾을 수 없습니다. "
            "설치 방법은 docs/bugs/003-melotts-windows-korean.md를 보세요."
        ) from e
    g2pkk_mod.G2p.check_mecab = lambda self: None
    g2pkk_mod.G2p.get_mecab = lambda self: mecab.MeCab()


class MeloEngine:
    """MeloTTS 한국어 엔진. load()로 올리고 unload()로 내린다."""

    def __init__(self) -> None:
        self.model = None
        self.device: str | None = None
        self.speaker_id: int | None = None

    @property
    def loaded(self) -> bool:
        return self.model is not None

    @property
    def sample_rate(self) -> int:
        return self.model.hps.data.sampling_rate if self.loaded else 44100

    def status(self) -> str:
        if not self.loaded:
            return "꺼짐"
        return f"켜짐 ({'GPU' if self.device.startswith('cuda') else 'CPU'})"

    def load(self, device: str = "cpu") -> str:
        if self.loaded and self.device == device:
            return self.status()
        self.unload()
        _patch_korean_mecab()
        try:
            from melo.api import TTS

            self.model = TTS(language="KR", device=device)
        except Exception as e:
            self.model = None
            raise TTSError(f"MeloTTS를 불러오지 못했습니다: {e}") from e
        self.device = device
        self.speaker_id = self.model.hps.data.spk2id["KR"]
        return self.status()

    def unload(self) -> None:
        if self.model is None:
            return
        self.model = None
        self.device = self.speaker_id = None
        import gc

        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def synthesize(self, text: str, speed: float = 1.0):
        """텍스트를 음성(float32 numpy 배열)으로 만든다."""
        text = (text or "").strip()
        if not text:
            raise TTSError("읽을 문장을 입력하세요.")
        if not SPEED_MIN <= speed <= SPEED_MAX:
            raise TTSError(f"속도는 {SPEED_MIN}~{SPEED_MAX} 사이로 입력하세요.")
        if not self.loaded:
            self.load()
        try:
            return self.model.tts_to_file(text, self.speaker_id, None, speed=speed, quiet=True)
        except Exception as e:
            raise TTSError(f"음성 만들기에 실패했습니다: {e}") from e

    def synthesize_to_file(self, text: str, speed: float = 1.0, path: Path | None = None) -> Path:
        import soundfile as sf

        audio = self.synthesize(text, speed)
        if path is None:
            path = OUTPUTS_DIR / f"melo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), audio, self.sample_rate, subtype="PCM_16")
        return path


def play(path: Path) -> None:
    """윈도우 기본 스피커로 재생 (재생이 끝날 때까지 기다림)."""
    import sounddevice as sd
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32")
    sd.play(data, sr)
    sd.wait()
