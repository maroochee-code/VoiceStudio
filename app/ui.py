"""웹 화면 (Gradio): 녹음 / 말→글자 / 글자→말 / 음성 대화 / 목소리 학습 / 목소리 관리 / 엔진 상태.

실행: .venv\\Scripts\\python.exe -m app.main
"""
from __future__ import annotations

import functools
import inspect
import logging
from pathlib import Path

import app.config  # noqa: F401  (환경변수 먼저 설정)
import gradio as gr

from app import llm, recorder, sovits, stt, tts, voices
from app.engine_manager import EngineBusy, EngineManager, build_default_manager

STATUS_HEADERS = ["엔진", "상태", "위치", "자세히"]
log = logging.getLogger("voicestudio")

# 자주 나오는 영어 오류 → 한국어 안내
ERROR_HINTS = [
    ("out of memory", "GPU 메모리가 부족합니다. '엔진 상태' 탭에서 '모두 끄기' 후 다시 시도하세요."),
    ("CUDA", "GPU 작업 중 오류가 났습니다. '엔진 상태' 탭에서 '모두 끄기' 후 다시 시도하세요."),
    ("Connection refused", "엔진 서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요."),
    ("timed out", "응답 시간이 너무 오래 걸렸습니다. 잠시 후 다시 시도하세요."),
    ("No such file", "파일을 찾을 수 없습니다. 파일을 다시 넣어주세요."),
    ("Permission", "파일에 접근할 권한이 없습니다. 다른 프로그램이 파일을 쓰고 있는지 확인하세요."),
    ("PortAudio", "오디오 장치 오류입니다. 마이크·스피커 연결을 확인하세요."),
]


def korean_error(e: Exception) -> gr.Error:
    """예상하지 못한 오류를 한국어 안내로 바꾼다 (원래 내용은 검은 창 기록에 남김)."""
    msg = str(e)
    for key, hint in ERROR_HINTS:
        if key.lower() in msg.lower():
            return gr.Error(f"{hint}\n(자세한 내용: {msg[:200]})")
    return gr.Error(f"예상하지 못한 오류가 났습니다: {msg[:200]}\n같은 문제가 반복되면 툴을 껐다 켜주세요.")


def _wrap(fn):
    """버튼 기능에서 나는 모든 오류를 한국어로 보여주게 감싼다."""
    if inspect.isgeneratorfunction(fn):
        @functools.wraps(fn)
        def gen(*args, **kwargs):
            try:
                yield from fn(*args, **kwargs)
            except gr.Error:
                raise
            except Exception as e:
                log.exception("오류")
                raise korean_error(e) from e
        return gen

    @functools.wraps(fn)
    def plain(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except gr.Error:
            raise
        except Exception as e:
            log.exception("오류")
            raise korean_error(e) from e
    return plain


def korean_errors(cls):
    for name, fn in list(vars(cls).items()):
        if callable(fn) and not name.startswith("_"):
            setattr(cls, name, _wrap(fn))
    return cls


@korean_errors
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

    # ---------- 글자 → 말 (목소리 선택) ----------
    def speak(self, text: str, speed: float, voice_label: str | None = None, fmt: str = "WAV"):
        entry = voices.find(voice_label or voices.MELO_ID)
        if entry is None:
            raise gr.Error("목소리 목록에서 목소리를 다시 고르세요 (목록 새로고침).")
        try:
            if entry.kind == "melo":
                if not self.m.get("melo").loaded:
                    self.m.load("melo", will_use_gpu=False, device="cpu")
                p = self.m.get("melo").synthesize_to_file(text, speed=float(speed))
            else:
                v = voices.to_sovits_voice(entry)
                self.m.load("sovits", will_use_gpu=True, voice=v)  # 위스퍼 등은 자동으로 GPU에서 내림
                p = self.m.get("sovits").synthesize_to_file(text, v, speed=float(speed))
            if fmt == "MP3":
                p = voices.to_mp3(p)
        except (tts.TTSError, sovits.SovitsError, voices.VoiceError, EngineBusy) as e:
            raise gr.Error(str(e))
        lic = entry.license
        note = f" · 라이선스: {lic.license or '미기록'} (상업적 사용 {lic.commercial})" if lic else ""
        return str(p), f"[{entry.label}] 저장: {p}{note}"

    def voice_labels(self):
        labels = [e.label for e in voices.list_all()]
        return gr.update(choices=labels, value=labels[0])

    # ---------- 목소리 관리 ----------
    def voice_table(self):
        rows = []
        for e in voices.list_all():
            lic = e.license or voices.License()
            rows.append([e.label, {"melo": "기본", "trained": "학습", "sample": "샘플"}[e.kind],
                         lic.source, lic.license, lic.commercial, lic.memo])
        return rows

    def add_sample(self, name, audio_path, ref_text, source, license_name, commercial, memo):
        text = (ref_text or "").strip()
        if audio_path and not text:  # 문장을 비워두면 위스퍼로 받아쓰기
            try:
                self.m.load("whisper", will_use_gpu=True, model_size="small", prefer="auto")
                text = self.m.get("whisper").transcribe(audio_path)
            except (stt.STTError, EngineBusy) as e:
                raise gr.Error(str(e))
        try:
            folder = voices.add_sample_voice(name, audio_path, text,
                                             voices.License(source, license_name, commercial, memo))
        except voices.VoiceError as e:
            raise gr.Error(str(e))
        return f"등록 완료: {folder}\n참고 문장: {text}", self.voice_table()

    def edit_license(self, voice_label, source, license_name, commercial, memo):
        try:
            voices.update_license(voice_label, voices.License(source, license_name, commercial, memo))
        except voices.VoiceError as e:
            raise gr.Error(str(e))
        return "라이선스 메모 저장 완료", self.voice_table()

    # ---------- 목소리 학습 (GPT-SoVITS) ----------
    def sample_folders(self):
        from app.config import SAMPLES_DIR

        names = sorted(p.name for p in SAMPLES_DIR.iterdir() if p.is_dir()) if SAMPLES_DIR.is_dir() else []
        return gr.update(choices=names, value=names[0] if names else None)

    def sample_info(self, folder: str | None):
        if not folder:
            return "샘플 폴더가 없습니다. 녹음 탭에서 '학습용 샘플로 보내기'를 먼저 하세요."
        total = recorder.total_sample_seconds(folder)
        ok = "✅ 학습 가능" if total >= sovits.MIN_TRAIN_SECONDS else \
            f"❌ {sovits.MIN_TRAIN_SECONDS - total:.0f}초 더 필요"
        return f"'{folder}' 샘플 총 {total:.0f}초 · {ok}"

    def voice_choices(self):
        names = [v.name for v in sovits.list_voices()]
        return gr.update(choices=names, value=names[-1] if names else None)

    def train_voice(self, voice_name: str, folder: str | None, sovits_epochs: float, gpt_epochs: float):
        """학습을 별도 스레드에서 돌리고, 진행 기록을 화면에 계속 보여준다(제너레이터)."""
        import threading

        if not folder:
            raise gr.Error("학습에 쓸 샘플 폴더를 고르세요.")
        name = (voice_name or folder).strip()
        if sovits.find_voice(name):
            raise gr.Error(f"'{name}' 이름의 목소리가 이미 있습니다. 다른 이름을 쓰세요.")
        lines: list[str] = []
        result: dict = {}
        try:
            trainer = sovits.SovitsTrainer(name, folder, log=lines.append,
                                           sovits_epochs=int(sovits_epochs), gpt_epochs=int(gpt_epochs))
            trainer.check()
            self.m.begin_gpu_job("목소리 학습")
        except (sovits.SovitsError, EngineBusy) as e:
            raise gr.Error(str(e))
        self.trainer = trainer

        def work():
            try:
                self.m.unload("sovits")
                self.m.load("whisper", will_use_gpu=True, during_job=True, model_size="small", prefer="auto")
                result["voice"] = trainer.run(self.m.get("whisper"), free_gpu=self.m.free_gpu)
            except Exception as e:  # 오류는 화면 기록에 남긴다
                result["error"] = str(e)
            finally:
                self.m.end_gpu_job()
                self.trainer = None

        th = threading.Thread(target=work, daemon=True)
        th.start()
        while th.is_alive():
            th.join(timeout=2)
            yield "\n".join(lines[-300:])
        if "error" in result:
            lines.append(f"\n❌ 실패: {result['error']}")
        else:
            lines.append(f"\n✅ 완료! '목소리로 읽기'에서 '{result['voice'].name}'를 골라 들어보세요.")
        yield "\n".join(lines[-300:])

    def cancel_training(self):
        t = getattr(self, "trainer", None)
        if t is None:
            return "진행 중인 학습이 없습니다."
        t.cancel()
        return "취소 요청함 (현재 단계를 멈추는 중...)"

    def speak_trained(self, text: str, voice_name: str | None, speed: float):
        v = sovits.find_voice(voice_name or "")
        if v is None:
            raise gr.Error("읽을 목소리를 고르세요. (학습한 목소리가 없으면 먼저 학습하세요)")
        try:
            self.m.load("sovits", will_use_gpu=True, voice=v)  # 위스퍼 등 다른 GPU 엔진은 자동으로 내림
            p = self.m.get("sovits").synthesize_to_file(text, v, speed=float(speed))
        except (sovits.SovitsError, EngineBusy) as e:
            raise gr.Error(str(e))
        return str(p), f"저장: {p}"

    # ---------- 음성 대화 (Ollama) ----------
    def model_choices(self):
        names = llm.list_models()
        value = llm.DEFAULT_MODEL if llm.DEFAULT_MODEL in names else (names[0] if names else None)
        return gr.update(choices=names, value=value)

    def ask(self, user_text: str, history: list | None, model: str | None):
        """글자 질문 → Ollama 답변. GPU의 다른 엔진은 먼저 내리고, 답변 후 모델은 바로 내려감."""
        history = list(history or [])
        try:
            self.m.load("ollama", will_use_gpu=True, model=model or llm.DEFAULT_MODEL)
            answer = self.m.get("ollama").chat(history, user_text, model)
        except (llm.LLMError, EngineBusy) as e:
            raise gr.Error(str(e))
        history += [{"role": "user", "content": user_text.strip()},
                    {"role": "assistant", "content": answer}]
        return history, answer

    def voice_chat(self, audio_path: str | None, typed: str, history: list | None, model: str | None,
                   voice_label: str | None, speed: float):
        """말하기(또는 글자) → 위스퍼 → Ollama 답변 → 선택한 목소리로 읽기."""
        question = (typed or "").strip()
        if audio_path and not question:
            # 대화 중에는 위스퍼를 CPU로: GPU는 Ollama·SoVITS가 번갈아 써야 해서 위스퍼까지 올리면 매번 교체됨
            try:
                self.m.load("whisper", will_use_gpu=False, model_size="small", prefer="cpu")
                question = self.m.get("whisper").transcribe(audio_path)
            except stt.STTError as e:
                raise gr.Error(str(e))
        if not question:
            raise gr.Error("마이크로 말하거나 질문을 입력하세요.")
        history, answer = self.ask(question, history, model)
        audio, msg = self.speak(answer, speed, voice_label, "WAV")
        return history, audio, None, "", f"질문: {question}\n{msg}"

    def reset_chat(self):
        return [], None, "대화 기록을 지웠습니다."

    # ---------- 엔진 상태 ----------
    def status(self):
        return self.m.status_rows(), self.m.vram_text(), "\n".join(reversed(self.m.log[-10:]))

    def toggle(self, key: str, on: bool):
        try:
            if on:
                if key == "whisper":
                    self.m.load("whisper", will_use_gpu=True, model_size="small", prefer="auto")
                elif key == "sovits":
                    self.m.load("sovits", will_use_gpu=True)
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
                with gr.Row():
                    tts_voice = gr.Dropdown(label="목소리 (기본 / 학습 / 샘플)", choices=["기본 (멜로)"],
                                            value="기본 (멜로)", interactive=True)
                    tts_voice_reload = gr.Button("목록 새로고침", scale=0)
                tts_text = gr.Textbox(label="읽을 문장", lines=4,
                                      value="안녕하세요. 보이스 스튜디오입니다.")
                with gr.Row():
                    tts_speed = gr.Slider(0.5, 2.0, value=1.0, step=0.1, label="속도")
                    tts_fmt = gr.Radio(["WAV", "MP3"], value="WAV", label="저장 형식")
                tts_btn = gr.Button("읽기", variant="primary")
                tts_audio = gr.Audio(label="결과 음성", type="filepath", autoplay=True,
                                     interactive=False, buttons=["download"])
                tts_msg = gr.Textbox(label="결과", interactive=False)
                tts_btn.click(h.speak, [tts_text, tts_speed, tts_voice, tts_fmt], [tts_audio, tts_msg])
                tts_voice_reload.click(h.voice_labels, None, tts_voice)

            # ---------------- 목소리 학습 ----------------
            with gr.Tab("목소리 학습"):
                gr.Markdown("녹음 탭에서 보낸 샘플(1분 이상)로 내 목소리를 학습합니다. "
                            "학습 중에는 GPU를 다른 엔진이 쓸 수 없습니다. RTX 2060 기준 수 분~수십 분.")
                with gr.Row():
                    tr_folder = gr.Dropdown(label="샘플 폴더", choices=[], interactive=True)
                    tr_reload = gr.Button("목록 새로고침", scale=0)
                tr_info = gr.Textbox(label="샘플 상태", interactive=False)
                with gr.Row():
                    tr_name = gr.Textbox(label="저장할 목소리 이름", placeholder="예: 내목소리")
                    tr_s2 = gr.Slider(2, 20, value=8, step=1, label="SoVITS 반복 횟수 (음색)")
                    tr_s1 = gr.Slider(2, 30, value=15, step=1, label="GPT 반복 횟수 (말투)")
                with gr.Row():
                    tr_btn = gr.Button("학습 시작", variant="primary")
                    tr_cancel = gr.Button("학습 취소", variant="stop")
                tr_log = gr.Textbox(label="진행 기록", lines=14, max_lines=14, autoscroll=True,
                                    interactive=False)

                gr.Markdown("### 학습한 목소리로 읽기")
                with gr.Row():
                    sv_voice = gr.Dropdown(label="목소리", choices=[], interactive=True)
                    sv_reload = gr.Button("목록 새로고침", scale=0)
                sv_text = gr.Textbox(label="읽을 문장", lines=3, value="안녕하세요. 제 목소리로 읽어 드립니다.")
                sv_speed = gr.Slider(0.5, 2.0, value=1.0, step=0.1, label="속도")
                sv_btn = gr.Button("읽기", variant="primary")
                sv_audio = gr.Audio(label="결과 음성", type="filepath", autoplay=True,
                                    interactive=False, buttons=["download"])
                sv_msg = gr.Textbox(label="결과", interactive=False)

                tr_reload.click(h.sample_folders, None, tr_folder)
                tr_folder.change(h.sample_info, tr_folder, tr_info)
                tr_btn.click(h.train_voice, [tr_name, tr_folder, tr_s2, tr_s1], tr_log).then(
                    h.voice_choices, None, sv_voice)
                tr_cancel.click(h.cancel_training, None, tr_log)
                sv_reload.click(h.voice_choices, None, sv_voice)
                sv_btn.click(h.speak_trained, [sv_text, sv_voice, sv_speed], [sv_audio, sv_msg])

            # ---------------- 음성 대화 ----------------
            with gr.Tab("음성 대화"):
                gr.Markdown("말하기 → 위스퍼(글자) → Ollama 답변 → 선택한 목소리로 읽기. "
                            "답변이 끝나면 대화 AI는 GPU에서 바로 내려갑니다. "
                            "학습·샘플 목소리는 매번 GPU를 바꿔 쓰느라 멜로보다 느립니다.")
                with gr.Row():
                    ch_model = gr.Dropdown(label="대화 AI 모델", choices=[], interactive=True)
                    ch_voice = gr.Dropdown(label="답변 목소리", choices=["기본 (멜로)"], value="기본 (멜로)",
                                           interactive=True)
                    ch_speed = gr.Slider(0.5, 2.0, value=1.0, step=0.1, label="속도")
                    ch_reload = gr.Button("목록 새로고침", scale=0)
                chatbot = gr.Chatbot(label="대화", height=380)
                with gr.Row():
                    ch_mic = gr.Audio(sources=["microphone", "upload"], type="filepath", label="말로 질문")
                    ch_text = gr.Textbox(label="또는 글자로 질문", lines=3)
                with gr.Row():
                    ch_send = gr.Button("보내기", variant="primary")
                    ch_reset = gr.Button("대화 기록 지우기")
                ch_audio = gr.Audio(label="답변 음성", type="filepath", autoplay=True, interactive=False)
                ch_msg = gr.Textbox(label="결과", interactive=False, lines=2)

                ch_send.click(h.voice_chat, [ch_mic, ch_text, chatbot, ch_model, ch_voice, ch_speed],
                              [chatbot, ch_audio, ch_mic, ch_text, ch_msg])
                ch_mic.stop_recording(h.voice_chat, [ch_mic, ch_text, chatbot, ch_model, ch_voice, ch_speed],
                                      [chatbot, ch_audio, ch_mic, ch_text, ch_msg], api_visibility="private")
                ch_reset.click(h.reset_chat, None, [chatbot, ch_audio, ch_msg])
                ch_reload.click(h.model_choices, None, ch_model).then(h.voice_labels, None, ch_voice)

            # ---------------- 목소리 관리 ----------------
            with gr.Tab("목소리 관리"):
                vm_table = gr.Dataframe(headers=["목소리", "종류", "출처", "라이선스", "상업적 사용", "메모"],
                                        interactive=False, wrap=True)
                vm_reload = gr.Button("목록 새로고침")
                gr.Markdown("### 샘플 목소리 추가\n3~10초짜리 한 문장 음성을 넣으면, 학습 없이 그 목소리를 흉내 내 읽습니다. "
                            "무료 샘플 예: KSS 데이터셋(CC BY-NC-SA 4.0, **상업적 사용 불가**), "
                            "AI 허브(데이터마다 다름, 확인 필요). 자세한 안내: `data/voices/samples/_README.txt`")
                with gr.Row():
                    vm_name = gr.Textbox(label="목소리 이름")
                    vm_audio = gr.Audio(sources=["upload", "microphone"], type="filepath", label="참고 음성 (3~10초)")
                vm_text = gr.Textbox(label="참고 음성에서 말한 문장 (비워두면 위스퍼가 받아씀)")
                with gr.Row():
                    vm_source = gr.Textbox(label="출처", placeholder="예: KSS 데이터셋 (Kyubyong Park)")
                    vm_license = gr.Textbox(label="라이선스", placeholder="예: CC BY-NC-SA 4.0")
                    vm_commercial = gr.Dropdown(voices.COMMERCIAL_CHOICES, value="확인 필요", label="상업적 사용")
                vm_memo = gr.Textbox(label="메모")
                vm_add = gr.Button("샘플 목소리 등록", variant="primary")
                gr.Markdown("### 라이선스 메모 고치기 (학습·샘플 목소리)")
                vm_target = gr.Dropdown(label="목소리", choices=[], interactive=True)
                vm_edit = gr.Button("위 출처·라이선스·상업적 사용·메모로 저장")
                vm_msg = gr.Textbox(label="결과", interactive=False, lines=2)

                vm_reload.click(h.voice_table, None, vm_table).then(h.voice_labels, None, vm_target)
                vm_add.click(h.add_sample, [vm_name, vm_audio, vm_text, vm_source, vm_license, vm_commercial,
                                            vm_memo], [vm_msg, vm_table]).then(
                    h.voice_labels, None, tts_voice).then(h.voice_labels, None, vm_target)
                vm_edit.click(h.edit_license, [vm_target, vm_source, vm_license, vm_commercial, vm_memo],
                              [vm_msg, vm_table])

            # ---------------- 엔진 상태 ----------------
            with gr.Tab("엔진 상태"):
                vram = gr.Textbox(label="VRAM", interactive=False)
                table = gr.Dataframe(headers=STATUS_HEADERS, interactive=False, wrap=True)
                with gr.Row():
                    w_on = gr.Button("위스퍼 켜기")
                    w_off = gr.Button("위스퍼 끄기")
                    m_on = gr.Button("멜로 켜기")
                    m_off = gr.Button("멜로 끄기")
                    s_on = gr.Button("SoVITS 켜기")
                    s_off = gr.Button("SoVITS 끄기")
                    o_off = gr.Button("Ollama 모델 내리기")
                    all_off = gr.Button("모두 끄기", variant="stop")
                    refresh = gr.Button("새로고침")
                log = gr.Textbox(label="최근 기록", lines=6, interactive=False)
                outs = [table, vram, log]
                w_on.click(lambda: h.toggle("whisper", True), None, outs)
                w_off.click(lambda: h.toggle("whisper", False), None, outs)
                m_on.click(lambda: h.toggle("melo", True), None, outs)
                m_off.click(lambda: h.toggle("melo", False), None, outs)
                s_on.click(lambda: h.toggle("sovits", True), None, outs)
                s_off.click(lambda: h.toggle("sovits", False), None, outs)
                o_off.click(lambda: h.toggle("ollama", False), None, outs)
                all_off.click(h.unload_all, None, outs)
                refresh.click(h.status, None, outs)
                timer = gr.Timer(5)
                timer.tick(h.status, None, outs, api_visibility="private")

        demo.load(h.status, None, [table, vram, log])
        demo.load(h.sample_folders, None, tr_folder)
        demo.load(h.voice_choices, None, sv_voice)
        demo.load(h.voice_labels, None, tts_voice)
        demo.load(h.voice_labels, None, vm_target)
        demo.load(h.voice_table, None, vm_table)
        demo.load(h.model_choices, None, ch_model)
        demo.load(h.voice_labels, None, ch_voice)
    return demo
