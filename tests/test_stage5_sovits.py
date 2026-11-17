"""5단계 테스트: GPT-SoVITS 설치, 목소리 저장 형식, 학습 규칙, 실제 학습→합성 (slow)."""
import shutil

import numpy as np
import pytest
import soundfile as sf

from app import sovits
from app.engine_manager import EngineBusy, EngineManager, build_default_manager


def test_sovits_installed():
    assert sovits.is_installed(), "scripts/install_sovits.ps1 실행 필요"


def test_sovits_env_has_korean_analyzer():
    import subprocess

    out = subprocess.run([str(sovits.SOVITS_PY), "-c",
                          "from eunjeon import Mecab; print(Mecab().pos('날씨')[0][1])"],
                         capture_output=True, text=True, env=sovits.sovits_env())
    assert out.stdout.strip() == "NNG", out.stderr


def test_voice_save_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(sovits, "VOICES_DIR", tmp_path)
    v = sovits.Voice(name="내목소리", exp_id="vs_test", gpt_path="g", sovits_path="s",
                     ref_audio="r.wav", ref_text="안녕", created="2026-11-17T00:00:00")
    sovits.save_voice(v)
    assert [x.name for x in sovits.list_voices()] == ["내목소리"]
    assert sovits.find_voice("내목소리").exp_id == "vs_test"
    assert sovits.find_voice("vs_test").name == "내목소리"
    assert sovits.find_voice("없음") is None


def test_training_rejects_short_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(sovits, "SAMPLES_DIR", tmp_path)
    (tmp_path / "짧음").mkdir()
    sf.write(str(tmp_path / "짧음" / "a.wav"), np.zeros(16000 * 10, dtype="float32"), 16000)
    with pytest.raises(sovits.SovitsError, match="부족"):
        sovits.SovitsTrainer("짧음").check()


def test_empty_voice_name_rejected():
    with pytest.raises(sovits.SovitsError):
        sovits.SovitsTrainer("  ")


def test_training_step_retries_with_smaller_batch():
    t = sovits.SovitsTrainer("재시도", log=lambda m: None, batch_size=3)
    calls = []

    def flaky():
        calls.append(t.batch_size)
        if len(calls) == 1:
            raise sovits.SovitsError("CUDA error")
        return "ok"

    assert t._with_retry(flaky) == "ok"
    assert calls == [3, 1]
    t.batch_size = 1
    with pytest.raises(sovits.SovitsError):  # 더 줄일 수 없으면 그대로 실패
        t._with_retry(lambda: (_ for _ in ()).throw(sovits.SovitsError("x")))


def test_gpu_job_blocks_gpu_engines():
    from tests.test_stage4_ui import FakeEngine

    m = EngineManager()
    m.register("a", "A", FakeEngine("cuda"))
    m.register("c", "C", FakeEngine("cpu"))
    m.begin_gpu_job("목소리 학습")
    with pytest.raises(EngineBusy):
        m.load("a", will_use_gpu=True)
    with pytest.raises(EngineBusy):
        m.begin_gpu_job("또 학습")
    m.load("c", will_use_gpu=False)          # CPU 엔진은 괜찮음
    m.load("a", will_use_gpu=True, during_job=True)  # 학습 작업 자신은 허용
    m.end_gpu_job()
    assert m.gpu_job is None


# ---------------------------------------------------------------- 실제 학습 (수 분 걸림)
@pytest.mark.slow
def test_train_then_speak_with_trained_voice(training_samples_dir, tmp_path, monkeypatch):
    """60초 이상 샘플 → 학습 → 학습한 목소리로 읽기 → 위스퍼가 알아듣는지."""
    monkeypatch.setattr(sovits, "VOICES_DIR", tmp_path / "voices")
    monkeypatch.setattr(sovits, "SAMPLES_DIR", training_samples_dir.parent)
    m = build_default_manager()
    logs = []
    trainer = sovits.SovitsTrainer("테스트목소리", training_samples_dir.name, log=logs.append,
                                   sovits_epochs=2, gpt_epochs=2)
    m.begin_gpu_job("목소리 학습")
    try:
        m.load("whisper", will_use_gpu=True, during_job=True, model_size="small", prefer="auto")
        voice = trainer.run(m.get("whisper"), free_gpu=m.free_gpu)
    finally:
        m.end_gpu_job()
        shutil.rmtree(trainer.work, ignore_errors=True)
    assert not m.get("whisper").loaded, "학습 전에 위스퍼를 GPU에서 내려야 함"
    assert sovits.find_voice("테스트목소리") is not None
    for p in (voice.gpt_path, voice.sovits_path, voice.ref_audio):
        assert (tmp_path / "voices").resolve() in __import__("pathlib").Path(p).resolve().parents
    try:
        m.load("sovits", will_use_gpu=True, voice=voice)
        out = m.get("sovits").synthesize_to_file("오늘은 날씨가 정말 좋습니다.", voice,
                                                path=tmp_path / "out.wav")
        assert sf.info(str(out)).duration > 1.0
        # 합성 서버가 GPU를 쓰는 동안 위스퍼는 CPU로 확인 (GPU 동시 사용 금지)
        from app.stt import WhisperEngine

        w = WhisperEngine()
        w.load("small", prefer="cpu")
        text = w.transcribe(out)
        assert "날씨" in text, text
    finally:
        m.unload_all()
    assert not m.get("sovits").loaded
    # 학습·합성 과정의 어떤 프로세스도 C:에 nltk 사전을 받으면 안 됨 (버그 기록 004)
    import os
    from pathlib import Path

    assert not (Path(os.environ["APPDATA"]) / "nltk_data").exists()
