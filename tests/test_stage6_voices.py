"""6단계 테스트: 목소리 목록(기본/학습/샘플), 샘플 등록·라이선스, MP3 저장, 목소리 바꿔 읽기."""
import json

import numpy as np
import pytest
import soundfile as sf

from app import sovits, voices


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """실제 data/voices를 건드리지 않도록 임시 폴더 사용."""
    monkeypatch.setattr(voices, "SAMPLE_VOICES_DIR", tmp_path / "samples")
    monkeypatch.setattr(sovits, "VOICES_DIR", tmp_path / "trained")
    return tmp_path


def _wav(path, seconds, sr=16000):
    t = np.linspace(0, seconds, int(sr * seconds), dtype="float32")
    sf.write(str(path), 0.1 * np.sin(2 * np.pi * 220 * t), sr)
    return path


def test_melo_is_always_first(isolated):
    entries = voices.list_all()
    assert entries[0].id == voices.MELO_ID and entries[0].label == "기본 (멜로)"
    assert (voices.SAMPLE_VOICES_DIR / "_README.txt").is_file()  # 샘플 폴더 안내 자동 생성


def test_add_sample_with_license(isolated):
    lic = voices.License("KSS 데이터셋", "CC BY-NC-SA 4.0", "불가", "시험용")
    folder = voices.add_sample_voice("카에스에스", _wav(isolated / "a.wav", 5), "안녕하세요", lic)
    saved = json.loads((folder / "license.json").read_text(encoding="utf-8"))
    assert saved["license"] == "CC BY-NC-SA 4.0" and saved["commercial"] == "불가"
    e = voices.find("샘플: 카에스에스")
    assert e.kind == "sample" and e.license.commercial == "불가"


def test_sample_validation(isolated):
    lic = voices.License()
    with pytest.raises(voices.VoiceError, match="짧"):
        voices.add_sample_voice("짧음", _wav(isolated / "s.wav", 1.5), "문장", lic)
    with pytest.raises(voices.VoiceError):
        voices.add_sample_voice("문장없음", _wav(isolated / "b.wav", 5), "  ", lic)
    with pytest.raises(voices.VoiceError):
        voices.add_sample_voice("잘못", _wav(isolated / "c.wav", 5), "문장",
                                voices.License(commercial="아마도"))
    voices.add_sample_voice("중복", _wav(isolated / "d.wav", 5), "문장", lic)
    with pytest.raises(voices.VoiceError, match="이미"):
        voices.add_sample_voice("중복", _wav(isolated / "d.wav", 5), "문장", lic)


def test_long_reference_is_trimmed_to_10s(isolated):
    folder = voices.add_sample_voice("긴음성", _wav(isolated / "l.wav", 15), "문장", voices.License())
    assert sf.info(str(folder / "ref.wav")).duration == pytest.approx(10.0, abs=0.01)


def test_update_license(isolated):
    voices.add_sample_voice("수정", _wav(isolated / "e.wav", 4), "문장", voices.License())
    voices.update_license("샘플: 수정", voices.License("AI 허브", "데이터별 약관", "확인 필요", "신청 완료"))
    assert voices.find("샘플: 수정").license.source == "AI 허브"
    with pytest.raises(voices.VoiceError):
        voices.update_license("기본 (멜로)", voices.License())


def test_sample_uses_pretrained_model(isolated):
    voices.add_sample_voice("제로샷", _wav(isolated / "z.wav", 4), "문장입니다", voices.License())
    v = voices.to_sovits_voice(voices.find("샘플: 제로샷"))
    assert v.gpt_path.endswith("s1v3.ckpt") and v.sovits_path.endswith("s2Gv2Pro.pth")
    assert v.ref_text == "문장입니다"


def test_mp3_export(isolated):
    mp3 = voices.to_mp3(_wav(isolated / "m.wav", 2))
    assert mp3.suffix == ".mp3" and mp3.stat().st_size > 1000


# ---------------------------------------------------------------- 실제 엔진
@pytest.fixture(scope="module")
def handlers():
    from app.engine_manager import build_default_manager
    from app.ui import Handlers

    h = Handlers(build_default_manager())
    yield h
    h.m.unload_all()


def test_speak_melo_as_mp3(handlers):
    path, msg = handlers.speak("엠피쓰리 저장 시험입니다.", 1.0, "기본 (멜로)", "MP3")
    assert path.endswith(".mp3") and "MIT" in msg


@pytest.mark.slow
def test_switch_between_melo_and_sample_voice(handlers, isolated, korean_wav):
    """목록에서 목소리를 바꿔가며 읽기 (완료 조건)."""
    from app.stt import WhisperEngine

    voices.add_sample_voice("헤미", korean_wav, "안녕하세요. 오늘 날씨가 정말 좋습니다.",
                            voices.License("Windows 기본 음성", "시험용", "불가"))
    handlers.m.load("whisper", will_use_gpu=True, model_size="small", prefer="auto")
    sample_wav, msg = handlers.speak("오늘은 날씨가 정말 좋습니다.", 1.0, "샘플: 헤미", "WAV")
    assert "샘플: 헤미" in msg
    assert not handlers.m.get("whisper").loaded, "SoVITS 합성 전 위스퍼를 GPU에서 내려야 함"
    melo_wav, _ = handlers.speak("오늘은 날씨가 정말 좋습니다.", 1.0, "기본 (멜로)", "WAV")
    handlers.m.unload_all()
    w = WhisperEngine()
    w.load("small", prefer="cpu")
    assert "날씨" in w.transcribe(sample_wav)
    assert "날씨" in w.transcribe(melo_wav)
