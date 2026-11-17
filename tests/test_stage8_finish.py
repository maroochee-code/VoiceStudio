"""8단계 테스트: 한국어 오류 메시지, 중복 실행 방지, 종료 시 하위 프로세스 정리, 실행 파일·문서."""
import ast
import re
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import gradio as gr
import pytest

ROOT = Path(__file__).resolve().parents[1]
HANGUL = re.compile(r"[가-힣]")


# ---------- 한국어 오류 ----------
def test_unexpected_error_becomes_korean():
    from app.ui import _wrap

    def boom():
        raise RuntimeError("CUDA error: out of memory")

    with pytest.raises(gr.Error) as e:
        _wrap(boom)()
    assert "GPU 메모리가 부족" in str(e.value.message)


def test_unknown_error_still_korean():
    from app.ui import _wrap

    with pytest.raises(gr.Error) as e:
        _wrap(lambda: 1 / 0)()
    assert "예상하지 못한 오류" in str(e.value.message)


def test_generator_handler_wrapped():
    from app.ui import _wrap

    def gen():
        yield "진행"
        raise ValueError("bad")

    g = _wrap(gen)()
    assert next(g) == "진행"
    with pytest.raises(gr.Error):
        next(g)


def test_all_handlers_wrapped():
    from app.ui import Handlers

    for name in ("transcribe", "speak", "voice_chat", "train_voice", "add_sample", "toggle"):
        assert hasattr(getattr(Handlers, name), "__wrapped__"), name


def test_error_messages_in_code_are_korean():
    """app/ 안에서 사용자에게 보이는 오류(raise XxxError("...") / gr.Error("..."))는 모두 한국어."""
    bad = []
    for py in (ROOT / "app").glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
                name = getattr(node.exc.func, "attr", getattr(node.exc.func, "id", ""))
                arg = node.exc.args[0]
                text = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else \
                    "".join(v.value for v in getattr(arg, "values", []) if isinstance(v, ast.Constant))
                if name.endswith("Error") and text and not HANGUL.search(text):
                    bad.append(f"{py.name}:{node.lineno} {text[:40]}")
    assert not bad, bad


# ---------- 중복 실행 ----------
def test_already_running_detection():
    from app import main as m

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        assert m.already_running(port=port)
    assert not m.already_running(port=port)


def test_second_launch_only_opens_browser(monkeypatch):
    from app import main as m

    opened = []
    monkeypatch.setattr(m, "already_running", lambda *a, **k: True)
    monkeypatch.setattr(m.webbrowser, "open", opened.append)
    assert m.main([]) == 0
    assert opened == [m.URL]


# ---------- 종료 시 하위 프로세스 정리 ----------
def test_children_die_with_parent(tmp_path):
    """부모(툴)를 강제로 끝내도 자식(예: GPT-SoVITS 서버)이 남지 않아야 한다."""
    parent_code = textwrap.dedent(f"""
        import subprocess, sys, time
        sys.path.insert(0, r"{ROOT}")
        from app import winjob
        assert winjob.kill_children_on_exit()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        print(child.pid, flush=True)
        time.sleep(120)
    """)
    parent = subprocess.Popen([sys.executable, "-c", parent_code], stdout=subprocess.PIPE, text=True)
    child_pid = int(parent.stdout.readline())
    subprocess.run(["taskkill", "/F", "/PID", str(parent.pid)], capture_output=True)  # /T 없이 부모만
    time.sleep(2)
    out = subprocess.run(["tasklist", "/FI", f"PID eq {child_pid}"], capture_output=True, text=True).stdout
    assert str(child_pid) not in out, "부모가 죽었는데 자식 프로세스가 남아 있음"


# ---------- 실행 파일·문서 ----------
def test_launcher_and_shortcut_files():
    bat = (ROOT / "VoiceStudio.bat").read_text(encoding="utf-8")
    assert "chcp 65001" in bat and "-m app.main" in bat
    assert (ROOT / "assets" / "voicestudio.ico").is_file()
    for ps1 in ("install.ps1", "install_sovits.ps1", "make_shortcut.ps1"):
        raw = (ROOT / "scripts" / ps1).read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf", f"{ps1}: PowerShell 5.1 한글 깨짐 방지용 BOM 필요"


def test_desktop_shortcut_exists():
    import os

    desktop = Path(subprocess.run(["powershell", "-NoProfile", "-Command",
                                   "[Environment]::GetFolderPath('Desktop')"],
                                  capture_output=True, text=True).stdout.strip())
    lnk = desktop / "VoiceStudio.lnk"
    if not lnk.exists():
        pytest.skip("바로가기 아직 안 만듦 (scripts/make_shortcut.ps1)")
    target = subprocess.run(["powershell", "-NoProfile", "-Command",
                             f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}').TargetPath"],
                            capture_output=True, text=True).stdout.strip()
    assert Path(target).resolve() == (ROOT / "VoiceStudio.bat").resolve()


def test_completion_documents():
    arch = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert arch.count("```mermaid") >= 2
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    for tab in ("녹음", "말 → 글자", "글자 → 말", "음성 대화", "목소리 학습", "목소리 관리", "엔진 상태"):
        assert tab in guide, tab
