"""공용 테스트 준비물."""
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures"
KOREAN_SENTENCE = "안녕하세요. 오늘 날씨가 정말 좋습니다."


TRAINING_SENTENCES = [
    "안녕하세요. 저는 보이스 스튜디오 테스트 목소리입니다.",
    "오늘은 날씨가 맑고 바람이 시원하게 불어옵니다.",
    "아침에 일어나서 따뜻한 커피를 한 잔 마셨습니다.",
    "도서관에 가서 재미있는 소설책을 두 권 빌렸습니다.",
    "주말에는 가족과 함께 공원으로 산책을 나갈 예정입니다.",
    "새로운 기술을 배우는 것은 언제나 즐거운 일입니다.",
    "점심으로 김치찌개와 계란말이를 맛있게 먹었습니다.",
    "버스를 타고 시내에 나가서 친구를 만났습니다.",
    "저녁에는 조용한 음악을 들으며 일기를 썼습니다.",
    "내일은 아침 일찍 회의가 있어서 서둘러야 합니다.",
    "봄이 되면 벚꽃이 피어서 거리가 아름다워집니다.",
    "컴퓨터 앞에 오래 앉아 있으면 허리가 아픕니다.",
    "운동을 꾸준히 하면 몸과 마음이 건강해집니다.",
    "여름 휴가에는 바닷가에 가서 수영을 하고 싶습니다.",
    "고양이가 창가에 앉아 햇볕을 쬐고 있습니다.",
    "이 문장들은 목소리 학습 시험을 위해 만들었습니다.",
]


def _sapi_to_wav(text: str, out: Path) -> None:
    text = text.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.SelectVoice('Microsoft Heami Desktop');"
        f"$s.SetOutputToWaveFile('{out}');"
        f"$s.Speak('{text}');$s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


@pytest.fixture(scope="session")
def training_samples_dir() -> Path:
    """목소리 학습 시험용 샘플 폴더 (윈도우 Heami 음성, 문장 사이 0.6초 쉼, 총 60초 이상)."""
    import numpy as np
    import soundfile as sf

    folder = FIXTURE_DIR / "train_samples"
    target = folder / "heami_training.wav"
    if target.exists():
        return folder
    folder.mkdir(parents=True, exist_ok=True)
    pieces = []
    sr = None
    for i, sentence in enumerate(TRAINING_SENTENCES):
        tmp = FIXTURE_DIR / f"_tmp_{i}.wav"
        _sapi_to_wav(sentence, tmp)
        data, sr = sf.read(str(tmp), dtype="float32")
        pieces += [data, np.zeros(int(sr * 0.6), dtype="float32")]
        tmp.unlink()
    audio = np.concatenate(pieces)
    while len(audio) / sr < 65:  # 60초가 안 되면 한 번 더 이어 붙임
        audio = np.concatenate([audio, audio])
    sf.write(str(target), audio, sr, subtype="PCM_16")
    return folder


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
