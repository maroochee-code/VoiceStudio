"""3단계 테스트: MeloTTS 한국어 합성, 속도 조절, 파일 저장, 위스퍼로 되돌려 듣기."""
import os
from pathlib import Path

import pytest
import soundfile as sf

from app import tts

SENTENCE = "안녕하세요. 음성 합성 테스트입니다."


@pytest.fixture(scope="module")
def melo():
    engine = tts.MeloEngine()
    engine.load("cpu")
    yield engine
    engine.unload()


def test_empty_text_errors():
    with pytest.raises(tts.TTSError):
        tts.MeloEngine().synthesize("   ")


def test_speed_out_of_range_errors():
    with pytest.raises(tts.TTSError):
        tts.MeloEngine().synthesize("안녕", speed=5)


def test_melo_runs_on_cpu(melo):
    assert melo.device == "cpu"
    assert melo.status() == "켜짐 (CPU)"


def test_synthesize_produces_audio(melo):
    audio = melo.synthesize(SENTENCE)
    seconds = len(audio) / melo.sample_rate
    assert 1.0 < seconds < 15.0
    assert abs(audio).max() > 0.01  # 무음이 아님


def test_speed_changes_length(melo):
    normal = len(melo.synthesize(SENTENCE, speed=1.0))
    fast = len(melo.synthesize(SENTENCE, speed=1.5))
    slow = len(melo.synthesize(SENTENCE, speed=0.8))
    assert fast < normal < slow


def test_save_wav_file(melo, tmp_path):
    p = melo.synthesize_to_file(SENTENCE, path=tmp_path / "out.wav")
    info = sf.info(str(p))
    assert info.samplerate == melo.sample_rate and info.duration > 1.0


def test_roundtrip_whisper_understands_melo(melo, tmp_path):
    """멜로가 만든 음성을 위스퍼가 알아들으면 발음이 제대로 된 것."""
    from app.stt import WhisperEngine

    p = melo.synthesize_to_file(SENTENCE, path=tmp_path / "rt.wav")
    w = WhisperEngine()
    w.load("small")
    text = w.transcribe(p).replace(" ", "")
    w.unload()
    assert "안녕하세요" in text
    assert "테스트" in text


def test_japanese_mecab_not_broken():
    """한국어 분석기 추가가 일본어 분석기(MeCab)를 덮어쓰지 않았는지."""
    import MeCab

    assert "テスト" in MeCab.Tagger().parse("テスト")


def test_no_downloads_on_c_drive():
    assert not (Path(os.environ["APPDATA"]) / "nltk_data").exists()
    assert Path(os.environ["HF_HOME"]).resolve().drive.upper() == "D:"
    assert Path(os.environ["NLTK_DATA"]).resolve().drive.upper() == "D:"
