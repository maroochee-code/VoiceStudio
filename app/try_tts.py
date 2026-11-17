"""직접 확인용: 문장을 멜로 목소리로 읽고 스피커로 재생, 파일 저장.

실행: .venv\\Scripts\\python.exe -m app.try_tts "읽을 문장" [속도=1.0]
"""
import sys
import warnings

warnings.filterwarnings("ignore")

from app import tts  # noqa: E402


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else "안녕하세요. 보이스 스튜디오입니다."
    speed = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    engine = tts.MeloEngine()
    print("멜로 준비 중...", engine.load("cpu"))
    path = engine.synthesize_to_file(text, speed=speed)
    print("저장:", path)
    print("재생 중...")
    tts.play(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
