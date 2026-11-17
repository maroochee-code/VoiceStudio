"""목소리 목록 관리: 기본(멜로) / 학습한 목소리 / 샘플 목소리.

샘플 목소리 폴더 구조 (data/voices/samples/<이름>/)
- ref.wav       참고 음성 (3~10초, 한 문장)
- ref.txt       참고 음성에서 말한 문장
- license.json  출처·라이선스·상업적 사용 가능 여부 메모

샘플 목소리는 따로 학습하지 않고, GPT-SoVITS 기본 모델이 참고 음성을 흉내 내서 읽는다(제로샷).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from app import sovits
from app.config import DATA_DIR

SAMPLE_VOICES_DIR = DATA_DIR / "voices" / "samples"
MELO_ID = "melo"
COMMERCIAL_CHOICES = ["확인 필요", "가능", "불가"]
REF_MIN, REF_MAX = 3.0, 10.0

SAMPLES_README = """샘플 목소리 폴더 안내 (VoiceStudio)

여기에 넣은 목소리는 '목소리 관리' 탭에서 등록하면 자동으로 만들어집니다.
직접 넣을 때는 폴더 하나에 아래 3개 파일을 두세요.
  ref.wav       3~10초짜리 한 문장 음성
  ref.txt       그 음성에서 말한 문장
  license.json  {"source": "...", "license": "...", "commercial": "가능/불가/확인 필요", "memo": "..."}

무료 샘플 데이터 예시
  KSS 데이터셋: https://www.kaggle.com/datasets/bryanpark/korean-single-speaker-speech-dataset
    라이선스 CC BY-NC-SA 4.0 → 상업적 사용 불가, 출처 표시 필요 (용량 약 4.3GB, Kaggle 로그인 필요)
  AI 허브: https://aihub.or.kr  (회원가입 + 데이터별 이용 신청·승인 필요, 라이선스는 데이터마다 다름 → 확인 필요)
"""


class VoiceError(Exception):
    """목소리 관리 오류 (메시지는 한국어)."""


@dataclass
class License:
    source: str = ""
    license: str = ""
    commercial: str = "확인 필요"
    memo: str = ""
    updated: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class VoiceEntry:
    id: str          # melo / trained:<exp_id> / sample:<폴더>
    label: str       # 목록에 보이는 이름
    kind: str        # melo / trained / sample
    name: str
    license: License | None = None


def ensure_samples_dir() -> Path:
    SAMPLE_VOICES_DIR.mkdir(parents=True, exist_ok=True)
    readme = SAMPLE_VOICES_DIR / "_README.txt"
    if not readme.exists():
        readme.write_text(SAMPLES_README, encoding="utf-8")
    return SAMPLE_VOICES_DIR


def _safe_name(name: str) -> str:
    safe = "".join(c for c in (name or "") if c.isalnum() or c in "-_ ").strip()
    if not safe:
        raise VoiceError("목소리 이름을 입력하세요 (한글·영문·숫자·-·_ 사용 가능).")
    return safe


def read_license(folder: Path) -> License:
    p = folder / "license.json"
    if not p.is_file():
        return License()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return License(**{k: v for k, v in data.items() if k in License.__dataclass_fields__})
    except Exception:
        return License(memo="license.json을 읽지 못했습니다")


def write_license(folder: Path, lic: License) -> None:
    if lic.commercial not in COMMERCIAL_CHOICES:
        raise VoiceError(f"상업적 사용은 {', '.join(COMMERCIAL_CHOICES)} 중에서 고르세요.")
    lic.updated = datetime.now().isoformat(timespec="seconds")
    (folder / "license.json").write_text(json.dumps(asdict(lic), ensure_ascii=False, indent=2),
                                         encoding="utf-8")


# ---------------------------------------------------------------- 목록
def list_sample_folders() -> list[Path]:
    ensure_samples_dir()
    return sorted(p for p in SAMPLE_VOICES_DIR.iterdir()
                  if p.is_dir() and (p / "ref.wav").is_file() and (p / "ref.txt").is_file())


def list_all() -> list[VoiceEntry]:
    entries = [VoiceEntry(MELO_ID, "기본 (멜로)", "melo", "멜로",
                          License("MeloTTS (MyShell)", "MIT", "가능", "기본 내장 목소리"))]
    for v in sovits.list_voices():
        entries.append(VoiceEntry(f"trained:{v.exp_id}", f"학습: {v.name}", "trained", v.name,
                                  read_license(v.folder) if (v.folder / "license.json").exists()
                                  else License("직접 녹음", "본인 목소리", "가능", "")))
    for f in list_sample_folders():
        entries.append(VoiceEntry(f"sample:{f.name}", f"샘플: {f.name}", "sample", f.name, read_license(f)))
    return entries


def find(voice_id: str) -> VoiceEntry | None:
    return next((e for e in list_all() if e.id == voice_id or e.label == voice_id), None)


def to_sovits_voice(entry: VoiceEntry) -> sovits.Voice:
    """학습/샘플 목소리를 GPT-SoVITS 합성에 쓸 수 있는 형태로 바꾼다."""
    if entry.kind == "trained":
        v = sovits.find_voice(entry.id.split(":", 1)[1])
        if v is None:
            raise VoiceError(f"학습한 목소리를 찾을 수 없습니다: {entry.name}")
        return v
    if entry.kind == "sample":
        folder = SAMPLE_VOICES_DIR / entry.name
        return sovits.Voice(
            name=entry.label, exp_id=entry.id,
            gpt_path=str(sovits.SOVITS_DIR / sovits.PRETRAINED["s1"]),
            sovits_path=str(sovits.SOVITS_DIR / sovits.PRETRAINED["s2G"]),
            ref_audio=str(folder / "ref.wav"),
            ref_text=(folder / "ref.txt").read_text(encoding="utf-8").strip(),
            created="", kind="sample")
    raise VoiceError("멜로 목소리는 GPT-SoVITS를 쓰지 않습니다.")


# ---------------------------------------------------------------- 샘플 등록
def add_sample_voice(name: str, audio_path: str | Path, ref_text: str, lic: License,
                     overwrite: bool = False) -> Path:
    """참고 음성 하나로 샘플 목소리를 등록한다. 3~10초를 넘으면 앞부분 10초만 쓴다."""
    import soundfile as sf

    safe = _safe_name(name)
    if not audio_path or not Path(audio_path).is_file():
        raise VoiceError("참고 음성 파일을 넣어주세요.")
    if not (ref_text or "").strip():
        raise VoiceError("참고 음성에서 말한 문장을 입력하세요 (비워두면 위스퍼로 자동 받아쓰기).")
    folder = ensure_samples_dir() / safe
    if folder.exists() and not overwrite:
        raise VoiceError(f"'{safe}' 샘플 목소리가 이미 있습니다.")
    data, sr = sf.read(str(audio_path), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    dur = len(data) / sr
    if dur < REF_MIN:
        raise VoiceError(f"참고 음성이 너무 짧습니다 ({dur:.1f}초). {REF_MIN:.0f}~{REF_MAX:.0f}초짜리를 넣어주세요.")
    if dur > REF_MAX:
        data = data[: int(sr * REF_MAX)]
    folder.mkdir(parents=True, exist_ok=True)
    sf.write(str(folder / "ref.wav"), data, sr, subtype="PCM_16")
    (folder / "ref.txt").write_text(ref_text.strip(), encoding="utf-8")
    write_license(folder, lic)
    return folder


def update_license(voice_id: str, lic: License) -> None:
    e = find(voice_id)
    if e is None or e.kind == "melo":
        raise VoiceError("라이선스를 바꿀 수 있는 목소리를 고르세요 (학습·샘플 목소리).")
    folder = SAMPLE_VOICES_DIR / e.name if e.kind == "sample" else sovits.find_voice(e.id.split(":", 1)[1]).folder
    write_license(folder, lic)


# ---------------------------------------------------------------- 파일 형식
def to_mp3(wav_path: Path, bitrate: str = "192k") -> Path:
    """WAV를 MP3로 바꾼다 (ffmpeg 사용)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise VoiceError("MP3로 저장하려면 ffmpeg가 필요합니다. PowerShell에서 'winget install Gyan.FFmpeg' 실행")
    mp3 = Path(wav_path).with_suffix(".mp3")
    r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(wav_path), "-codec:a", "libmp3lame",
                        "-b:a", bitrate, str(mp3)], capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not mp3.is_file():
        raise VoiceError(f"MP3 변환 실패: {r.stderr.strip()[:200]}")
    return mp3
