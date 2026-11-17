"""웹 화면 (Gradio): 녹음 / 말→글자 / 글자→말 / 엔진 상태.

실행: .venv\\Scripts\\python.exe -m app.main
"""
from __future__ import annotations

import shutil
from pathlib import Path

import app.config  # noqa: F401  (환경변수 먼저 설정)
import gradio as gr

from app import recorder, stt, tts
from app.engine_manager import EngineManager, build_default_manager

STATUS_HEADERS = ["엔진", "상태", "위치", "자세히"]


class Handlers:
    """버튼이 눌렸을 때 실행되는 기능 모음. 화면과 분리해서 테스트하기 쉽게 한다."""

    def __init__(self, manager: EngineManager | None = None) -> None:
        self.m = manager or build_default_manager()

    # ---------- 녹음 ----------
    def record_with_k66(self, seconds: float):
        try:
            wav = recorder.save_wav(recorder.record(float(seconds)))
            return str(wav), f"녹음 완료: {wav.name} ({float(seconds):g}초)"
        except recorder.RecorderError as e:
            raise gr.Error(str(e))

    def save_browser_recording(self, audio_path: str | None):
        if not audio_path:
            raise gr.Error("먼저 녹음하거나 파일을 올려주세요.")
        import soundfile as sf

        data, sr = sf.read(audio_path, dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)  # 스테레오 → 모노
        wav = recorder.save_wav(data, samplerate=sr)
        return str(wav), f"저장 완료: {wav}"

    def send_to_samples(self, audio_path: str | None, voice_name: str):
        if not audio_path:
            raise gr.Error("보낼 녹음이 없습니다. 먼저 녹음하세요.")
        name = (voice_name or "my_voice").strip()
        path = Path(audio_path)
        if path.suffix.lower() != ".wav":
            path, _ = self.save_browser_recording(audio_path)
        try:
            dest = recorder.send_to_samples(Path(path), name)
        except recorder.RecorderError as e:
            raise gr.Error(str(e))
        total = recorder.total_sample_seconds(dest.parent.name)
        need = "학습 가능" if total >= 60 else f"학습까지 {60 - total:.0f}초 더 필요"
        return f"샘플 폴더로 보냄: {dest}\n'{dest.parent.name}' 샘플 총 {total:.1f}초 ({need})"

    # ---------- 말 → 글자 ----------
    def transcribe(self, audio_path: str | None, model_size: str, device_choice: str):
        if not audio_path:
            raise gr.Error("변환할 녹음이나 오디오 파일을 넣어주세요.")
        prefer = {"자동": "auto", "GPU": "cuda", "CPU": "cpu"}.get(device_choice, "auto")
        try:
            self.m.load("whisper", will_use_gpu=prefer != "cpu", model_size=model_size, prefer=prefer)
            text = self.m.get("whisper").transcribe(audio_path)
        except stt.STTError as e:
            raise gr.Error(str(e))
        return text or "(인식된 말이 없습니다)", self.m.get("whisper").status()

    def save_text(self, text: str):
        if not (text or "").strip():
            raise gr.Error("저장할 글자가 없습니다.")
        p = stt.save_transcript(text)
        return str(p)

    # ---------- 글자 → 말 ----------
    def speak(self, text: str, speed: float):
        try:
            if not self.m.get("melo").loaded:
                self.m.load("melo", will_use_gpu=False, device="cpu")
            p = self.m.get("melo").synthesize_to_file(text, speed=float(speed))
        except tts.TTSError as e:
            raise gr.Error(str(e))
        return str(p), f"저장: {p}"

    # ---------- 엔진 상태 ----------
    def status(self):
        return self.m.status_rows(), self.m.vram_text(), "\n".join(reversed(self.m.log[-10:]))

    def toggle(self, key: str, on: bool):
        try:
            if on:
                if key == "whisper":
                    self.m.load("whisper", will_use_gpu=True, model_size="small", prefer="auto")
                else:
                    self.m.load("melo", will_use_gpu=False, device="cpu")
            else:
                self.m.unload(key)
        except Exception as e:
            raise gr.Error(f"엔진 전환 실패: {e}")
        return self.status()

    def unload_all(self):
        self.m.unload_all()
        return self.status()


def build_ui(handlers: Handlers | None = None) -> gr.Blocks:
    h = handlers or Handlers()

    with gr.Blocks(title="VoiceStudio") as demo:
        gr.Markdown("# 🎙️ VoiceStudio\n집 PC에서 인터넷 없이 돌아가는 음성 AI 툴")

        with gr.Tabs():
            # ---------------- 녹음 ----------------
            with gr.Tab("녹음"):
                gr.Markdown("**방법 1** 브라우저 마이크로 녹음 (브라우저에서 K66 선택)  ·  "
                            "**방법 2** PC에서 K66으로 바로 녹음")
                rec_audio = gr.Audio(sources=["microphone", "upload"], type="filepath",
                                     label="녹음 / 파일", buttons=["download"])
                with gr.Row():
                    rec_seconds = gr.Slider(1, 120, value=10, step=1, label="K66 녹음 시간(초)")
                    rec_k66_btn = gr.Button("K66으로 녹음 시작", variant="primary")
                with gr.Row():
                    rec_save_btn = gr.Button("WAV로 저장")
                    voice_name = gr.Textbox(value="my_voice", label="목소리 이름 (샘플 폴더)")
                    rec_send_btn = gr.Button("학습용 샘플로 보내기")
                rec_msg = gr.Textbox(label="결과", interactive=False, lines=2)

                rec_k66_btn.click(h.record_with_k66, rec_seconds, [rec_audio, rec_msg])
                rec_save_btn.click(h.save_browser_recording, rec_audio, [rec_audio, rec_msg])
                rec_send_btn.click(h.send_to_samples, [rec_audio, voice_name], rec_msg)

            # ---------------- 말 → 글자 ----------------
            with gr.Tab("말 → 글자"):
                stt_audio = gr.Audio(sources=["microphone", "upload"], type="filepath",
                                     label="녹음하거나 오디오 파일 올리기")
                with gr.Row():
                    stt_model = gr.Radio(["small", "medium"], value="small",
                                         label="모델 (medium: 더 정확, 더 느림)")
                    stt_device = gr.Radio(["자동", "GPU", "CPU"], value="자동", label="실행 위치")
                stt_btn = gr.Button("글자로 바꾸기", variant="primary")
                stt_text = gr.Textbox(label="결과 (오른쪽 위 버튼으로 복사)", lines=6, buttons=["copy"])
                stt_engine = gr.Textbox(label="위스퍼 상태", interactive=False)
                with gr.Row():
                    stt_save_btn = gr.Button("텍스트 파일로 저장")
                    stt_file = gr.File(label="저장된 파일")
                stt_btn.click(h.transcribe, [stt_audio, stt_model, stt_device], [stt_text, stt_engine])
                stt_save_btn.click(h.save_text, stt_text, stt_file)

            # ---------------- 글자 → 말 ----------------
            with gr.Tab("글자 → 말"):
                tts_text = gr.Textbox(label="읽을 문장", lines=4,
                                      value="안녕하세요. 보이스 스튜디오입니다.")
                tts_speed = gr.Slider(0.5, 2.0, value=1.0, step=0.1, label="속도")
                tts_btn = gr.Button("읽기 (멜로 기본 목소리)", variant="primary")
                tts_audio = gr.Audio(label="결과 음성", type="filepath", autoplay=True,
                                     interactive=False, buttons=["download"])
                tts_msg = gr.Textbox(label="결과", interactive=False)
                tts_btn.click(h.speak, [tts_text, tts_speed], [tts_audio, tts_msg])

            # ---------------- 엔진 상태 ----------------
            with gr.Tab("엔진 상태"):
                vram = gr.Textbox(label="VRAM", interactive=False)
                table = gr.Dataframe(headers=STATUS_HEADERS, interactive=False, wrap=True)
                with gr.Row():
                    w_on = gr.Button("위스퍼 켜기")
                    w_off = gr.Button("위스퍼 끄기")
                    m_on = gr.Button("멜로 켜기")
                    m_off = gr.Button("멜로 끄기")
                    all_off = gr.Button("모두 끄기", variant="stop")
                    refresh = gr.Button("새로고침")
                log = gr.Textbox(label="최근 기록", lines=6, interactive=False)
                outs = [table, vram, log]
                w_on.click(lambda: h.toggle("whisper", True), None, outs)
                w_off.click(lambda: h.toggle("whisper", False), None, outs)
                m_on.click(lambda: h.toggle("melo", True), None, outs)
                m_off.click(lambda: h.toggle("melo", False), None, outs)
                all_off.click(h.unload_all, None, outs)
                refresh.click(h.status, None, outs)
                timer = gr.Timer(5)
                timer.tick(h.status, None, outs, api_visibility="private")

        demo.load(h.status, None, [table, vram, log])
    return demo
