"""공용 테스트 준비물."""
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures"
KOREAN_SENTENCE = "안녕하세요. 오늘 날씨가 정말 좋습니다."


@pytest.fixture(scope="session")
def korean_wav() -> Path:
    """윈도우 기본 한국어 음성(Heami)으로 테스트용 WAV를 만든다 (Git에는 안 올라감)."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    out = FIXTURE_DIR / "korean_hello.wav"
    if not out.exists():
        ps = (
            "Add-Type -AssemblyName System.Speech;"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            "$s.SelectVoice('Microsoft Heami Desktop');"
            f"$s.SetOutputToWaveFile('{out}');"
            f"$s.Speak('{KOREAN_SENTENCE}');$s.Dispose()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    return out
