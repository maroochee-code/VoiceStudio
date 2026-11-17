"""VoiceStudio 실행 진입점.

실행: .venv\\Scripts\\python.exe -m app.main
"""
import sys
import warnings

warnings.filterwarnings("ignore")

import app.config  # noqa: E402,F401
from app.ui import build_ui  # noqa: E402

HOST, PORT = "127.0.0.1", 7860  # 내 PC에서만 접속 가능


def main() -> int:
    demo = build_ui()
    print(f"VoiceStudio 시작: http://{HOST}:{PORT}  (끄려면 이 창을 닫거나 Ctrl+C)")
    demo.launch(server_name=HOST, server_port=PORT, inbrowser="--no-browser" not in sys.argv,
                show_error=True, footer_links=["settings"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
