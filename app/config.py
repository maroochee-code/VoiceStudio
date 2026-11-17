"""공통 설정: 폴더 위치와 환경변수(.env).

다른 모듈보다 먼저 import 되어야 허깅페이스 캐시가 D:에 잡힌다.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# .env가 없어도 C:에 쌓이지 않도록 기본값을 D: 프로젝트 폴더로 강제
os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / "models" / "huggingface"))
os.environ.setdefault("NLTK_DATA", str(PROJECT_ROOT / "models" / "nltk_data"))
os.environ.setdefault("CACHED_PATH_CACHE_ROOT", str(PROJECT_ROOT / "models" / "cached_path"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# Gradio: 인터넷으로 사용 통계 보내지 않기, 브라우저 녹음 임시파일을 C:\Temp 대신 D:에
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("GRADIO_TEMP_DIR", str(PROJECT_ROOT / "data" / "tmp"))
Path(os.environ["GRADIO_TEMP_DIR"]).mkdir(parents=True, exist_ok=True)
# nltk는 지정 폴더가 '이미 있어야' 거기에 받는다. 없으면 C:\Users\...\AppData로 가버리므로 미리 만든다.
Path(os.environ["NLTK_DATA"]).mkdir(parents=True, exist_ok=True)

DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
RECORDINGS_DIR = DATA_DIR / "recordings"      # 녹음 원본
SAMPLES_DIR = DATA_DIR / "samples"            # 목소리 학습용 샘플
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"    # 말→글자 결과
OUTPUTS_DIR = DATA_DIR / "outputs"            # 생성 음성
WHISPER_DIR = MODELS_DIR / "whisper"

for _d in (RECORDINGS_DIR, SAMPLES_DIR, TRANSCRIPTS_DIR, OUTPUTS_DIR, WHISPER_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def register_cuda_dlls() -> None:
    """윈도우에서 faster-whisper(CTranslate2)가 PyTorch에 들어있는 CUDA DLL을 찾게 한다."""
    if os.name != "nt":
        return
    try:
        import torch

        lib = Path(torch.__file__).parent / "lib"
        if lib.is_dir():
            os.add_dll_directory(str(lib))
            os.environ["PATH"] = str(lib) + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass
