"""7단계 테스트: Ollama 자동 실행, 답변 후 즉시 언로드, 대화 기록 유지, 음성 대화 전체 흐름."""
import time

import pytest

from app import llm

MODEL = llm.DEFAULT_MODEL


def _wait_unloaded(seconds=10) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if not any(m["name"] == MODEL for m in llm.loaded_models()):
            return True
        time.sleep(0.5)
    return False


def test_clean_for_speech():
    assert llm.clean_for_speech("**안녕**하세요 😀\n\n# 제목") == "안녕하세요 \n 제목"


def test_server_running_or_started():
    assert "Ollama" in llm.ensure_server()
    assert llm.server_running()


def test_default_model_installed():
    assert MODEL in llm.list_models(), f"'ollama pull {MODEL}' 필요"


def test_empty_question_rejected():
    with pytest.raises(llm.LLMError):
        llm.OllamaEngine().chat([], "   ")


def test_missing_model_gives_korean_hint():
    with pytest.raises(llm.LLMError, match="ollama pull"):
        llm.OllamaEngine().chat([], "안녕", model="없는모델:1b")


def test_answer_in_korean_and_unloaded_after():
    eng = llm.OllamaEngine()
    answer = eng.chat([], "한국의 수도는 어디야? 한 문장으로 답해.")
    assert "서울" in answer
    assert _wait_unloaded(), "답변 후 keep_alive=0으로 모델이 내려가야 함"


def test_conversation_history_is_used():
    eng = llm.OllamaEngine()
    history = [{"role": "user", "content": "내 이름은 김철수야. 기억해 줘."},
               {"role": "assistant", "content": "네, 김철수 님. 기억할게요."}]
    answer = eng.chat(history, "내 이름이 뭐라고 했지?")
    assert "철수" in answer


@pytest.fixture(scope="module")
def handlers():
    from app.engine_manager import build_default_manager
    from app.ui import Handlers

    h = Handlers(build_default_manager())
    yield h
    h.m.unload_all()


def test_ollama_evicts_whisper_from_gpu(handlers, korean_wav):
    handlers.m.load("whisper", will_use_gpu=True, model_size="small", prefer="cuda")
    assert handlers.m.get("whisper").device == "cuda"
    history, answer = handlers.ask("안녕? 짧게 인사해 줘.", [], MODEL)
    assert not handlers.m.get("whisper").loaded, "Ollama 답변 전 위스퍼를 GPU에서 내려야 함"
    assert len(history) == 2 and history[1]["role"] == "assistant" and answer


def test_voice_chat_full_flow_with_melo(handlers, korean_wav):
    """말하기(녹음 파일) → 위스퍼 → Ollama → 멜로 목소리로 답변 (완료 조건)."""
    history, audio, mic, typed, msg = handlers.voice_chat(
        str(korean_wav), "", [], MODEL, "기본 (멜로)", 1.0)
    assert "날씨" in history[0]["content"]           # 위스퍼가 알아들은 질문
    assert history[1]["role"] == "assistant"
    assert audio.endswith(".wav") and mic is None and typed == ""
    # 이어서 글자로 질문 → 대화 기록이 쌓임
    history, *_ = handlers.voice_chat(None, "방금 내가 무슨 얘기 했지?", history, MODEL, "기본 (멜로)", 1.0)
    assert len(history) == 4
    assert _wait_unloaded()


@pytest.mark.slow
def test_voice_chat_with_sovits_voice(handlers, korean_wav, tmp_path, monkeypatch):
    """Ollama(GPU) → SoVITS(GPU) 순서로 GPU를 번갈아 써도 문제없는지."""
    from app import voices

    monkeypatch.setattr(voices, "SAMPLE_VOICES_DIR", tmp_path / "samples")
    voices.add_sample_voice("헤미", korean_wav, "안녕하세요. 오늘 날씨가 정말 좋습니다.", voices.License())
    history, audio, *_ = handlers.voice_chat(None, "오늘 기분이 어때? 한 문장으로.", [], MODEL, "샘플: 헤미", 1.0)
    assert audio.endswith(".wav") and len(history) == 2
    assert not any(m["name"] == MODEL for m in llm.loaded_models())
    handlers.m.unload_all()
