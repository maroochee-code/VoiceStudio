"""직접 확인용: 마이크로 말하고 글자로 바꿔보기.

실행: .venv\\Scripts\\python.exe -m app.try_stt [녹음초=5] [모델=small]
"""
import sys

from app import recorder, stt


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 5
    size = sys.argv[2] if len(sys.argv) > 2 else "small"
    engine = stt.WhisperEngine()
    print("위스퍼 준비 중...", engine.load(size))
    dev = recorder.find_input_device()
    print(f"마이크: {'K66' if dev is not None else '윈도우 기본 장치'}")
    input(f"엔터를 누르면 {seconds:g}초 동안 녹음합니다. ")
    print("녹음 중... 말씀하세요")
    wav = recorder.save_wav(recorder.record(seconds))
    print("저장:", wav)
    text = engine.transcribe(wav)
    print("결과:", text or "(인식된 말이 없습니다)")
    print("텍스트 저장:", stt.save_transcript(text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
