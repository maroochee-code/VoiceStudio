"""4단계 테스트: 엔진 관리자(GPU 하나만 규칙), 버튼 기능, 실제 웹 서버 띄워서 버튼 호출."""
import urllib.request

import gradio as gr
import pytest

from app.engine_manager import EngineManager, build_default_manager
from app import recorder


class FakeEngine:
    """실제 모델 없이 관리자 규칙만 시험하는 가짜 엔진."""

    def __init__(self, device="cuda"):
        self.want = device
        self.device = None
        self.loaded = False

    def load(self, **kw):
        self.loaded, self.device = True, kw.get("device", self.want)
        return self.status()

    def unload(self):
        self.loaded, self.device = False, None

    def status(self):
        return f"켜짐 ({self.device})" if self.loaded else "꺼짐"


# ---------- 지휘자 규칙 ----------
def test_only_one_gpu_engine_at_a_time():
    m = EngineManager()
    m.register("a", "A", FakeEngine("cuda"))
    m.register("b", "B", FakeEngine("cuda"))
    m.load("a", will_use_gpu=True)
    m.load("b", will_use_gpu=True)
    assert m.gpu_engines() == ["B"]
    assert not m.get("a").loaded


def test_cpu_engine_does_not_evict_gpu_engine():
    m = EngineManager()
    m.register("gpu", "G", FakeEngine("cuda"))
    m.register("cpu", "C", FakeEngine("cpu"))
    m.load("gpu", will_use_gpu=True)
    m.load("cpu", will_use_gpu=False)
    assert m.get("gpu").loaded and m.get("cpu").loaded


def test_rule_enforced_even_if_caller_forgets_gpu_flag():
    m = EngineManager()
    m.register("a", "A", FakeEngine("cuda"))
    m.register("b", "B", FakeEngine("cuda"))
    m.load("a", will_use_gpu=True)
    m.load("b", will_use_gpu=False)  # 실수로 False를 줘도 켠 뒤 GPU 검사로 정리됨
    assert m.gpu_engines() == ["B"]


def test_status_rows_and_unload_all():
    m = EngineManager()
    m.register("a", "A", FakeEngine("cuda"))
    m.load("a", will_use_gpu=True)
    assert m.status_rows()[0][:3] == ["A", "켜짐", "GPU"]
    m.unload_all()
    assert m.status_rows()[0][:3] == ["A", "꺼짐", "-"]
    assert "VRAM" in m.vram_text()


# ---------- 버튼 기능 (실제 엔진) ----------
@pytest.fixture(scope="module")
def handlers():
    from app.ui import Handlers

    h = Handlers(build_default_manager())
    yield h
    h.m.unload_all()


def test_empty_inputs_show_korean_error(handlers):
    with pytest.raises(gr.Error):
        handlers.transcribe(None, "small", "자동")
    with pytest.raises(gr.Error):
        handlers.speak("", 1.0)
    with pytest.raises(gr.Error):
        handlers.send_to_samples(None, "x")


def test_transcribe_button(handlers, korean_wav):
    text, status = handlers.transcribe(str(korean_wav), "small", "자동")
    assert "날씨" in text
    assert "GPU" in status


def test_speak_button_keeps_whisper_on_gpu(handlers):
    path, msg = handlers.speak("테스트 문장입니다.", 1.2)
    assert path.endswith(".wav")
    # 멜로는 CPU라서 위스퍼를 내리지 않아야 함
    rows = {r[0]: r for r in handlers.m.status_rows()}
    assert rows["멜로 (글자→말)"][2] == "CPU"


def test_send_to_samples_button(handlers, korean_wav, tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "SAMPLES_DIR", tmp_path)
    msg = handlers.send_to_samples(str(korean_wav), "테스트")
    assert "학습까지" in msg


# ---------- 실제 웹 서버 ----------
def test_web_server_and_buttons(handlers, korean_wav):
    from gradio_client import Client, handle_file

    from app.ui import build_ui

    demo = build_ui(handlers)
    demo.launch(server_name="127.0.0.1", server_port=7861, prevent_thread_lock=True,
                inbrowser=False, quiet=True)
    try:
        html = urllib.request.urlopen("http://127.0.0.1:7861", timeout=10).read().decode("utf-8")
        assert "VoiceStudio" in html
        client = Client("http://127.0.0.1:7861/", verbose=False)
        text, _ = client.predict(handle_file(str(korean_wav)), "small", "자동", api_name="/transcribe")
        assert "날씨" in text
        audio, _ = client.predict("웹 화면 테스트입니다.", 1.0, "기본 (멜로)", "WAV", api_name="/speak")
        assert str(audio).endswith(".wav")
    finally:
        demo.close()
