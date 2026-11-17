"""녹음 기능: K66 마이크로 녹음 → WAV 저장 → 학습 샘플 폴더로 보내기."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import RECORDINGS_DIR, SAMPLES_DIR

DEFAULT_SAMPLERATE = 44100  # 목소리 학습에도 쓰므로 고음질로 녹음
PREFERRED_MIC = "K66"


class RecorderError(Exception):
    """녹음 관련 오류 (메시지는 한국어)."""


def find_input_device(name_hint: str = PREFERRED_MIC) -> int | None:
    """이름에 name_hint가 들어간 입력 장치 번호. 없으면 None(=윈도우 기본 장치)."""
    import sounddevice as sd

    for idx, dev in enumerate(sd.query_devices()):
        # MME(번호가 가장 앞쪽) 장치를 먼저 고른다: 윈도우에서 가장 호환성이 좋음
        if dev["max_input_channels"] > 0 and name_hint.lower() in dev["name"].lower():
            return idx
    return None


def list_input_devices() -> list[str]:
    import sounddevice as sd

    return [f"{i}: {d['name']}" for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]


def record(seconds: float, samplerate: int = DEFAULT_SAMPLERATE, device: int | None = None) -> np.ndarray:
    """seconds초 동안 녹음해서 모노 float32 배열로 돌려준다."""
    import sounddevice as sd

    if seconds <= 0:
        raise RecorderError("녹음 시간은 0초보다 길어야 합니다.")
    if device is None:
        device = find_input_device()
    try:
        audio = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=1,
                       dtype="float32", device=device)
        sd.wait()
    except Exception as e:  # sounddevice는 다양한 PortAudio 오류를 낸다
        raise RecorderError(f"마이크 녹음에 실패했습니다. 마이크 연결과 윈도우 마이크 권한을 확인하세요. ({e})") from e
    return audio.reshape(-1)


def save_wav(audio: np.ndarray, samplerate: int = DEFAULT_SAMPLERATE,
             path: Path | None = None, prefix: str = "rec") -> Path:
    """WAV(16비트)로 저장. path가 없으면 data/recordings/에 날짜 이름으로 저장."""
    if path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = RECORDINGS_DIR / f"{prefix}_{stamp}.wav"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, samplerate, subtype="PCM_16")
    return path


def send_to_samples(wav_path: Path, voice_name: str = "my_voice") -> Path:
    """녹음 파일을 학습용 샘플 폴더(data/samples/<목소리이름>/)로 복사."""
    wav_path = Path(wav_path)
    if not wav_path.is_file():
        raise RecorderError(f"파일을 찾을 수 없습니다: {wav_path}")
    safe = "".join(c for c in voice_name if c.isalnum() or c in "-_ ").strip() or "my_voice"
    dest_dir = SAMPLES_DIR / safe
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / wav_path.name
    shutil.copy2(wav_path, dest)
    return dest


def total_sample_seconds(voice_name: str = "my_voice") -> float:
    """샘플 폴더에 모인 녹음 총 길이(초). 학습에는 60초 이상 필요."""
    folder = SAMPLES_DIR / voice_name
    if not folder.is_dir():
        return 0.0
    return sum(sf.info(str(p)).duration for p in folder.glob("*.wav"))
