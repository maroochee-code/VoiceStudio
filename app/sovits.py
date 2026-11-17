"""목소리 학습·복제: GPT-SoVITS 연동.

GPT-SoVITS는 의존성이 무거워서 별도 가상환경(engines/GPT-SoVITS/.venv)에서 돌린다.
- 학습: GPT-SoVITS의 준비·학습 스크립트를 순서대로 하위 프로세스로 실행
- 합성: GPT-SoVITS의 api_v2 서버를 띄워서 HTTP로 요청
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.config import DATA_DIR, OUTPUTS_DIR, PROJECT_ROOT, SAMPLES_DIR

SOVITS_DIR = PROJECT_ROOT / "engines" / "GPT-SoVITS"
SOVITS_PY = SOVITS_DIR / ".venv" / "Scripts" / "python.exe"
VOICES_DIR = DATA_DIR / "voices" / "trained"
TRAIN_DIR = DATA_DIR / "train"
VERSION = "v2Pro"
API_HOST, API_PORT = "127.0.0.1", 9880
INFER_CONFIG = "GPT_SoVITS/configs/voicestudio_infer.yaml"

PRETRAINED = {
    "bert": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large",
    "hubert": "GPT_SoVITS/pretrained_models/chinese-hubert-base",
    "sv": "GPT_SoVITS/pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt",
    "s2G": "GPT_SoVITS/pretrained_models/v2Pro/s2Gv2Pro.pth",
    "s2D": "GPT_SoVITS/pretrained_models/v2Pro/s2Dv2Pro.pth",
    "s1": "GPT_SoVITS/pretrained_models/s1v3.ckpt",
}

MIN_TRAIN_SECONDS = 60
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

LogFn = Callable[[str], None]


class SovitsError(Exception):
    """GPT-SoVITS 관련 오류 (메시지는 한국어)."""


# ---------------------------------------------------------------- 공통
def is_installed() -> bool:
    return SOVITS_PY.is_file() and (SOVITS_DIR / PRETRAINED["s2G"]).is_file()


def sovits_env(extra: dict | None = None) -> dict:
    env = os.environ.copy()
    env.update({
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "version": VERSION,
        "is_half": "True",
        "no_proxy": "localhost, 127.0.0.1, ::1",
        "KMP_DUPLICATE_LIB_OK": "TRUE",
        "TEMP": str(SOVITS_DIR / "TEMP"),
        "TMP": str(SOVITS_DIR / "TEMP"),
    })
    (SOVITS_DIR / "TEMP").mkdir(exist_ok=True)
    # 메인 가상환경의 파이썬 경로가 섞이지 않게
    env.pop("VIRTUAL_ENV", None)
    env.pop("PYTHONPATH", None)
    if extra:
        env.update({k: str(v) for k, v in extra.items()})
    return env


def kill_tree(pid: int) -> None:
    """윈도우에서 프로세스와 그 자식까지 모두 종료 (venv의 python.exe는 실제 파이썬을 자식으로 띄움)."""
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True,
                   creationflags=NO_WINDOW)


def run_step(args: list[str], env: dict, log: LogFn, title: str,
             on_start: Callable[[subprocess.Popen], None] | None = None) -> None:
    """GPT-SoVITS 스크립트 하나를 실행하고 출력을 log로 흘려보낸다. 실패하면 SovitsError."""
    log(f"▶ {title}")
    proc = subprocess.Popen([str(SOVITS_PY), "-s", *args], cwd=str(SOVITS_DIR), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=NO_WINDOW, text=True, encoding="utf-8", errors="replace")
    if on_start:
        on_start(proc)
    tail: list[str] = []
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            tail.append(line)
            del tail[:-30]
            log("   " + line)
    proc.wait()
    if proc.returncode != 0:
        raise SovitsError(f"'{title}' 단계에서 실패했습니다 (코드 {proc.returncode}).\n" + "\n".join(tail[-10:]))


# ---------------------------------------------------------------- 목소리 정보
@dataclass
class Voice:
    name: str            # 화면에 보이는 이름 (한국어 가능)
    exp_id: str          # 내부 영문 이름
    gpt_path: str
    sovits_path: str
    ref_audio: str
    ref_text: str
    created: str
    kind: str = "trained"
    note: str = ""

    @property
    def folder(self) -> Path:
        return VOICES_DIR / self.exp_id


def list_voices() -> list[Voice]:
    voices = []
    if VOICES_DIR.is_dir():
        for f in sorted(VOICES_DIR.glob("*/voice.json")):
            try:
                voices.append(Voice(**json.loads(f.read_text(encoding="utf-8"))))
            except Exception:
                continue
    return voices


def find_voice(name: str) -> Voice | None:
    return next((v for v in list_voices() if v.name == name or v.exp_id == name), None)


def save_voice(v: Voice) -> Path:
    v.folder.mkdir(parents=True, exist_ok=True)
    p = v.folder / "voice.json"
    p.write_text(json.dumps(asdict(v), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ---------------------------------------------------------------- 학습
class SovitsTrainer:
    """녹음 샘플 → 자르기 → 받아쓰기 → 특징 추출 → SoVITS 학습 → GPT 학습 → 목소리 저장."""

    def __init__(self, voice_name: str, sample_folder: str | None = None, log: LogFn = print,
                 sovits_epochs: int = 8, gpt_epochs: int = 15, batch_size: int = 3) -> None:
        self.voice_name = voice_name.strip()
        if not self.voice_name:
            raise SovitsError("목소리 이름을 입력하세요.")
        self.sample_dir = SAMPLES_DIR / (sample_folder or self.voice_name)
        self.log = log
        self.sovits_epochs, self.gpt_epochs, self.batch_size = sovits_epochs, gpt_epochs, batch_size
        self.exp_id = "vs_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        self.work = TRAIN_DIR / self.exp_id
        self.sliced = self.work / "sliced"
        self.list_file = self.work / "train.list"
        self.opt_dir = SOVITS_DIR / "logs" / self.exp_id
        self.proc: subprocess.Popen | None = None
        self.cancelled = False

    # ----- 확인
    def check(self) -> float:
        import soundfile as sf

        if not is_installed():
            raise SovitsError("GPT-SoVITS가 설치되어 있지 않습니다. scripts/install_sovits.ps1을 실행하세요.")
        wavs = sorted(self.sample_dir.glob("*.wav")) if self.sample_dir.is_dir() else []
        total = sum(sf.info(str(w)).duration for w in wavs)
        if total < MIN_TRAIN_SECONDS:
            raise SovitsError(f"학습 샘플이 부족합니다: {total:.0f}초 (최소 {MIN_TRAIN_SECONDS}초 필요). "
                              f"녹음 탭에서 '{self.sample_dir.name}' 이름으로 샘플을 더 보내주세요.")
        return total

    def _track(self, p: subprocess.Popen) -> None:
        self.proc = p

    def cancel(self) -> None:
        self.cancelled = True
        if self.proc and self.proc.poll() is None:
            kill_tree(self.proc.pid)

    def _step(self, args, env, title):
        if self.cancelled:
            raise SovitsError("학습을 취소했습니다.")
        run_step(args, env, self.log, title, on_start=self._track)

    # ----- 1. 자르기
    def slice_audio(self) -> list[Path]:
        self.sliced.mkdir(parents=True, exist_ok=True)
        # 기본값은 GPT-SoVITS 웹 화면 기본값과 같음
        self._step(["tools/slice_audio.py", str(self.sample_dir), str(self.sliced),
                    "-34", "4000", "300", "10", "500", "0.9", "0.25", "0", "1"],
                   sovits_env(), "1/6 녹음을 문장 단위로 자르기")
        clips = sorted(self.sliced.glob("*.wav"))
        if not clips:
            raise SovitsError("녹음을 자르지 못했습니다. 너무 조용하거나 잡음만 있는지 확인하세요.")
        return clips

    # ----- 2. 받아쓰기 (메인 환경의 위스퍼 사용)
    def transcribe(self, clips: list[Path], whisper) -> int:
        import soundfile as sf

        self.log("▶ 2/6 잘라낸 조각을 위스퍼로 받아쓰기")
        lines = []
        for c in clips:
            dur = sf.info(str(c)).duration
            if dur < 1.0:
                continue
            text = whisper.transcribe(c).strip()
            if text:
                lines.append(f"{c.resolve()}|{self.exp_id}|ko|{text}")
                self.log(f"   {c.name} ({dur:.1f}초): {text}")
        if len(lines) < 3:
            raise SovitsError("받아쓴 문장이 너무 적습니다(3개 미만). 말소리가 또렷한 녹음을 더 넣어주세요.")
        self.list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return len(lines)

    # ----- 3. 특징 추출
    def prepare_features(self) -> None:
        self.opt_dir.mkdir(parents=True, exist_ok=True)
        base = {
            "inp_text": self.list_file, "inp_wav_dir": "", "exp_name": self.exp_id,
            "opt_dir": self.opt_dir, "i_part": 0, "all_parts": 1, "_CUDA_VISIBLE_DEVICES": 0,
        }
        self._step(["GPT_SoVITS/prepare_datasets/1-get-text.py"],
                   sovits_env({**base, "bert_pretrained_dir": PRETRAINED["bert"]}), "3/6 발음 분석")
        part = self.opt_dir / "2-name2text-0.txt"
        (self.opt_dir / "2-name2text.txt").write_text(part.read_text(encoding="utf-8"), encoding="utf-8")
        part.unlink()

        env_b = sovits_env({**base, "cnhubert_base_dir": PRETRAINED["hubert"], "sv_path": PRETRAINED["sv"]})
        self._step(["GPT_SoVITS/prepare_datasets/2-get-hubert-wav32k.py"], env_b, "3/6 음색 특징 추출")
        self._step(["GPT_SoVITS/prepare_datasets/2-get-sv.py"], env_b, "3/6 화자 특징 추출")

        self._step(["GPT_SoVITS/prepare_datasets/3-get-semantic.py"],
                   sovits_env({**base, "pretrained_s2G": PRETRAINED["s2G"],
                               "s2config_path": f"GPT_SoVITS/configs/s2{VERSION}.json"}),
                   "3/6 의미 토큰 추출")
        part = self.opt_dir / "6-name2semantic-0.tsv"
        body = part.read_text(encoding="utf-8").strip("\n")
        (self.opt_dir / "6-name2semantic.tsv").write_text("item_name\tsemantic_audio\n" + body + "\n",
                                                         encoding="utf-8")
        part.unlink()

    # ----- 4. SoVITS 학습
    def train_sovits(self) -> Path:
        cfg = json.loads((SOVITS_DIR / f"GPT_SoVITS/configs/s2{VERSION}.json").read_text(encoding="utf-8"))
        (self.opt_dir / f"logs_s2_{VERSION}").mkdir(parents=True, exist_ok=True)
        t = cfg["train"]
        t.update(batch_size=self.batch_size, epochs=self.sovits_epochs, text_low_lr_rate=0.4,
                 pretrained_s2G=PRETRAINED["s2G"], pretrained_s2D=PRETRAINED["s2D"],
                 if_save_latest=True, if_save_every_weights=True, save_every_epoch=self.sovits_epochs,
                 gpu_numbers="0", grad_ckpt=False, lora_rank="32")
        cfg["model"]["version"] = VERSION
        cfg["data"]["exp_dir"] = cfg["s2_ckpt_dir"] = str(self.opt_dir)
        cfg["save_weight_dir"] = f"SoVITS_weights_{VERSION}"
        cfg["name"] = self.exp_id
        cfg["version"] = VERSION
        path = self.work / "tmp_s2.json"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        (SOVITS_DIR / cfg["save_weight_dir"]).mkdir(exist_ok=True)
        self._step(["GPT_SoVITS/s2_train.py", "--config", str(path)], sovits_env(),
                   f"4/6 SoVITS 학습 ({self.sovits_epochs}회 반복)")
        return self._newest(SOVITS_DIR / cfg["save_weight_dir"], f"{self.exp_id}_e*.pth", "SoVITS")

    # ----- 5. GPT 학습
    def train_gpt(self) -> Path:
        import yaml

        cfg = yaml.safe_load((SOVITS_DIR / "GPT_SoVITS/configs/s1longer-v2.yaml").read_text(encoding="utf-8"))
        (self.opt_dir / "logs_s1").mkdir(parents=True, exist_ok=True)
        save_dir = f"GPT_weights_{VERSION}"
        cfg["train"].update(batch_size=self.batch_size, epochs=self.gpt_epochs,
                            save_every_n_epoch=self.gpt_epochs, if_save_every_weights=True,
                            if_save_latest=True, if_dpo=False, half_weights_save_dir=save_dir,
                            exp_name=self.exp_id)
        cfg["pretrained_s1"] = PRETRAINED["s1"]
        cfg["train_semantic_path"] = str(self.opt_dir / "6-name2semantic.tsv")
        cfg["train_phoneme_path"] = str(self.opt_dir / "2-name2text.txt")
        cfg["output_dir"] = str(self.opt_dir / f"logs_s1_{VERSION}")
        path = self.work / "tmp_s1.yaml"
        path.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True), encoding="utf-8")
        (SOVITS_DIR / save_dir).mkdir(exist_ok=True)
        self._step(["GPT_SoVITS/s1_train.py", "--config_file", str(path)],
                   sovits_env({"_CUDA_VISIBLE_DEVICES": 0, "hz": "25hz"}),
                   f"5/6 GPT 학습 ({self.gpt_epochs}회 반복)")
        return self._newest(SOVITS_DIR / save_dir, f"{self.exp_id}-e*.ckpt", "GPT")

    @staticmethod
    def _newest(folder: Path, pattern: str, what: str) -> Path:
        files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime)
        if not files:
            raise SovitsError(f"{what} 학습 결과 파일을 찾을 수 없습니다 ({folder}).")
        return files[-1]

    # ----- 6. 저장
    def register(self, gpt: Path, sovits: Path) -> Voice:
        import soundfile as sf

        self.log("▶ 6/6 목소리 저장")
        # 참고 음성: 3~10초 사이에서 가장 긴 조각 (GPT-SoVITS 권장 길이)
        best = None
        for line in self.list_file.read_text(encoding="utf-8").splitlines():
            wav, _, _, text = line.split("|", 3)
            d = sf.info(wav).duration
            if 3.0 <= d <= 10.0 and (best is None or d > best[1]):
                best = (wav, d, text)
        if best is None:
            raise SovitsError("참고 음성(3~10초 문장)을 찾지 못했습니다. 문장 단위로 또렷하게 녹음해 주세요.")
        v = Voice(name=self.voice_name, exp_id=self.exp_id, gpt_path="", sovits_path="",
                  ref_audio="", ref_text=best[2], created=datetime.now().isoformat(timespec="seconds"))
        v.folder.mkdir(parents=True, exist_ok=True)
        v.gpt_path = str(shutil.copy2(gpt, v.folder / "gpt.ckpt"))
        v.sovits_path = str(shutil.copy2(sovits, v.folder / "sovits.pth"))
        v.ref_audio = str(shutil.copy2(best[0], v.folder / "ref.wav"))
        save_voice(v)
        self.log(f"완료: '{v.name}' 목소리 저장 ({v.folder})")
        return v

    def cleanup(self) -> None:
        """GPT-SoVITS 쪽 중간 파일 정리 (최종 결과는 data/voices에 복사되어 있음)."""
        shutil.rmtree(self.opt_dir, ignore_errors=True)
        for folder, pattern in ((f"SoVITS_weights_{VERSION}", f"{self.exp_id}_e*.pth"),
                                (f"GPT_weights_{VERSION}", f"{self.exp_id}-e*.ckpt")):
            for f in (SOVITS_DIR / folder).glob(pattern):
                f.unlink(missing_ok=True)

    # ----- 전체
    def run(self, whisper, free_gpu: Callable[[], None]) -> Voice:
        total = self.check()
        self.log(f"학습 시작: '{self.voice_name}' 샘플 {total:.0f}초, 내부 이름 {self.exp_id}")
        t0 = time.time()
        clips = self.slice_audio()
        n = self.transcribe(clips, whisper)
        self.log(f"   받아쓴 문장 {n}개")
        free_gpu()  # 기획서 5장: 학습 전 위스퍼·Ollama를 GPU에서 내림
        self.prepare_features()
        sovits = self.train_sovits()
        gpt = self.train_gpt()
        v = self.register(gpt, sovits)
        self.cleanup()
        self.log(f"총 소요 시간: {(time.time() - t0) / 60:.1f}분")
        return v


# ---------------------------------------------------------------- 합성 서버
class SovitsEngine:
    """GPT-SoVITS 합성 서버(api_v2)를 켜고 끄며, 학습한 목소리로 읽는다."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.device: str | None = None
        self.voice: Voice | None = None
        self.log_path = DATA_DIR / "tmp" / "sovits_server.log"

    @property
    def loaded(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def status(self) -> str:
        if not self.loaded:
            return "꺼짐"
        return f"켜짐 (GPU, 목소리: {self.voice.name if self.voice else '기본'})"

    def _url(self, path: str, **params) -> str:
        q = ("?" + urllib.parse.urlencode(params)) if params else ""
        return f"http://{API_HOST}:{API_PORT}{path}{q}"

    def _get(self, path: str, timeout: float = 60, **params) -> bytes:
        try:
            with urllib.request.urlopen(self._url(path, **params), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            raise SovitsError(f"GPT-SoVITS 요청 실패: {e.read().decode('utf-8', 'replace')[:300]}") from e

    def _write_config(self) -> None:
        (SOVITS_DIR / INFER_CONFIG).write_text(
            "custom:\n"
            f"  bert_base_path: {PRETRAINED['bert']}\n"
            f"  cnhuhbert_base_path: {PRETRAINED['hubert']}\n"
            "  device: cuda\n"
            "  is_half: true\n"
            f"  t2s_weights_path: {PRETRAINED['s1']}\n"
            f"  version: {VERSION}\n"
            f"  vits_weights_path: {PRETRAINED['s2G']}\n",
            encoding="utf-8",
        )

    def load(self, voice: Voice | None = None, timeout: float = 240) -> str:
        if not is_installed():
            raise SovitsError("GPT-SoVITS가 설치되어 있지 않습니다. scripts/install_sovits.ps1을 실행하세요.")
        if not self.loaded:
            self._write_config()
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            logf = open(self.log_path, "w", encoding="utf-8")
            self.proc = subprocess.Popen(
                [str(SOVITS_PY), "-s", "api_v2.py", "-a", API_HOST, "-p", str(API_PORT), "-c", INFER_CONFIG],
                cwd=str(SOVITS_DIR), env=sovits_env(), stdout=logf, stderr=subprocess.STDOUT,
                creationflags=NO_WINDOW)
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.proc.poll() is not None:
                    self.proc = None
                    raise SovitsError("GPT-SoVITS 서버가 시작하지 못했습니다. 기록: " + str(self.log_path))
                try:
                    self._get("/docs", timeout=2)
                    break
                except Exception:
                    time.sleep(1)
            else:
                self.unload()
                raise SovitsError("GPT-SoVITS 서버 시작 시간이 너무 오래 걸립니다.")
            self.device = "cuda"
            self.voice = None
        if voice is not None:
            self.set_voice(voice)
        return self.status()

    def set_voice(self, voice: Voice) -> None:
        if self.voice and self.voice.exp_id == voice.exp_id:
            return
        self._get("/set_gpt_weights", timeout=120, weights_path=voice.gpt_path)
        self._get("/set_sovits_weights", timeout=120, weights_path=voice.sovits_path)
        self.voice = voice

    def unload(self) -> None:
        if self.proc is None:
            return
        try:
            self._get("/control", timeout=3, command="exit")
        except Exception:
            pass
        kill_tree(self.proc.pid)
        self.proc = None
        self.device = None
        self.voice = None

    def synthesize_to_file(self, text: str, voice: Voice, speed: float = 1.0,
                           path: Path | None = None) -> Path:
        text = (text or "").strip()
        if not text:
            raise SovitsError("읽을 문장을 입력하세요.")
        self.load(voice)
        body = {
            "text": text, "text_lang": "ko",
            "ref_audio_path": voice.ref_audio, "prompt_text": voice.ref_text, "prompt_lang": "ko",
            "text_split_method": "cut5", "batch_size": 1, "media_type": "wav",
            "speed_factor": float(speed),
        }
        req = urllib.request.Request(self._url("/tts"), data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            raise SovitsError(f"음성 만들기 실패: {e.read().decode('utf-8', 'replace')[:300]}") from e
        if path is None:
            path = OUTPUTS_DIR / f"sovits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path
