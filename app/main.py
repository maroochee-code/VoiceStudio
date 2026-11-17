"""VoiceStudio 실행 진입점.

실행: VoiceStudio.bat (바탕화면 아이콘) 또는 .venv\\Scripts\\python.exe -m app.main
옵션: --no-browser  브라우저를 자동으로 열지 않음
"""
import socket
import sys
import warnings
import webbrowser

warnings.filterwarnings("ignore")

import app.config  # noqa: E402,F401

HOST, PORT = "127.0.0.1", 7860  # 내 PC에서만 접속 가능
URL = f"http://{HOST}:{PORT}"


def already_running(host: str = HOST, port: int = PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    open_browser = "--no-browser" not in argv
    if already_running():
        print(f"VoiceStudio가 이미 켜져 있습니다. 브라우저로 엽니다: {URL}")
        if open_browser:
            webbrowser.open(URL)
        return 0

    from app import llm, winjob

    if winjob.kill_children_on_exit():
        print("창을 닫으면 GPT-SoVITS 등 하위 프로그램도 함께 꺼집니다.")
    try:  # 기획서 5장: 시작 시 Ollama 서버 확인, 꺼져 있으면 자동 실행
        print(llm.ensure_server())
    except llm.LLMError as e:
        print(f"[알림] {e} (음성 대화 탭만 쓸 수 없고 나머지 기능은 정상)")

    print("화면 준비 중... (처음에는 30초 정도 걸릴 수 있습니다)")
    from app.ui import build_ui

    demo = build_ui()
    print(f"VoiceStudio 시작: {URL}  (끄려면 이 창을 닫으세요)")
    try:
        demo.launch(server_name=HOST, server_port=PORT, inbrowser=open_browser,
                    show_error=True, footer_links=["settings"])
    except OSError as e:
        print(f"[오류] {PORT}번 포트를 열 수 없습니다. 다른 프로그램이 쓰고 있는지 확인하세요. ({e})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
