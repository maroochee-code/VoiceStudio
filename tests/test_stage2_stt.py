"""2단계 테스트: 녹음 저장, 샘플 폴더, 장치 선택, 위스퍼 한국어 변환(GPU·CPU)."""
import numpy as np
import pytest
import soundfile as sf

from app import recorder, stt


# ---------- 장치 선택 규칙 ----------
def test_choose_device_gpu_when_enough_vram():
    assert stt.choose_device("small", free_mb=5000) == ("cuda", "float16")


def test_choose_device_falls_back_to_cpu():
    assert stt.choose_device("medium", free_mb=1000) == ("cpu", "int8")


def test_choose_device_forced_cpu():
    assert stt.choose_device("small", prefer="cpu", free_mb=5000) == ("cpu", "int8")


def test_choose_device_forced_cuda_without_vram_errors():
    with pytest.raises(stt.STTError):
        stt.choose_device("medium", prefer="cuda", free_mb=100)


# ---------- 녹음 파일 처리 ----------
def test_save_wav_and_send_to_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SAMPLES_DIR", tmp_path / "samples")
    audio = np.zeros(44100, dtype="float32")  # 1초 무음
    wav = recorder.save_wav(audio, path=tmp_path / "a.wav")
    info = sf.info(str(wav))
    assert info.samplerate == 44100 and info.channels == 1 and info.subtype == "PCM_16"
    dest = recorder.send_to_samples(wav, "테스트 목소리")
    assert dest.is_file() and dest.parent.name == "테스트 목소리"
    assert recorder.total_sample_seconds("테스트 목소리") == pytest.approx(1.0, abs=0.01)


def test_send_missing_file_errors(tmp_path):
    with pytest.raises(recorder.RecorderError):
        recorder.send_to_samples(tmp_path / "없음.wav")


def test_record_rejects_zero_seconds():
    with pytest.raises(recorder.RecorderError):
        recorder.record(0)


def test_k66_microphone_found():
    names = recorder.list_input_devices()
    if not any("K66" in n for n in names):
        pytest.skip("K66 마이크가 연결되어 있지 않음")
    assert recorder.find_input_device() is not None


def test_real_microphone_short_recording():
    audio = recorder.record(0.5)
    assert audio.shape == (22050,)
    assert audio.dtype == np.float32


# ---------- 위스퍼 변환 ----------
def _check_korean(text: str):
    assert "안녕하세요" in text.replace(" ", "")
    assert "날씨" in text


def test_whisper_gpu_korean(korean_wav):
    engine = stt.WhisperEngine()
    engine.load("small", prefer="cuda")
    assert engine.device == "cuda"
    text = engine.transcribe(korean_wav)
    _check_korean(text)
    engine.unload()
    assert not engine.loaded and engine.status() == "꺼짐"


def test_whisper_cpu_korean(korean_wav):
    engine = stt.WhisperEngine()
    engine.load("small", prefer="cpu")
    assert engine.device == "cpu"
    _check_korean(engine.transcribe(korean_wav))
    engine.unload()


def test_save_transcript(tmp_path):
    p = stt.save_transcript("한국어 텍스트", tmp_path / "t.txt")
    assert p.read_text(encoding="utf-8") == "한국어 텍스트"


def test_whisper_model_stored_on_d_drive():
    from app.config import WHISPER_DIR

    assert WHISPER_DIR.resolve().drive.upper() == "D:"
