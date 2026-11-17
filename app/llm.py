"""대화 AI: Ollama 연동.

규칙 (기획서 5장)
- 툴 시작 시 Ollama 서버(ollama serve)가 꺼져 있으면 자동 실행
- 모델은 답변이 필요할 때만 올리고, 답변이 끝나면 keep_alive=0으로 즉시 내림
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = "gemma3:4b"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

SYSTEM_PROMPT = (
    "너는 음성으로 대화하는 친절한 한국어 비서야. 답변은 소리 내어 읽히니까 "
    "짧고 자연스러운 구어체로 2~3문장 이내로 말해. 목록, 표, 마크다운, 이모지, 특수기호는 쓰지 마."
)


class LLMError(Exception):
    """대화 AI 관련 오류 (메시지는 한국어)."""


def _request(path: str, body: dict | None = None, timeout: float = 300) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(OLLAMA_URL + path, data=data,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError(f"Ollama 요청 실패: {e.read().decode('utf-8', 'replace')[:300]}") from e


def server_running() -> bool:
    try:
        _request("/api/version", timeout=2)
        return True
    except Exception:
        return False


def find_ollama_exe() -> str | None:
    exe = shutil.which("ollama")
    if exe:
        return exe
    guess = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(guess) if guess.is_file() else None


def ensure_server(timeout: float = 30) -> str:
    """서버가 꺼져 있으면 켠다. 결과 문구를 돌려준다."""
    if server_running():
        return "Ollama 서버 실행 중"
    exe = find_ollama_exe()
    if not exe:
        raise LLMError("Ollama가 설치되어 있지 않습니다. https://ollama.com 에서 설치하세요.")
    from app.winjob import CREATE_BREAKAWAY_FROM_JOB

    # Ollama는 다른 프로그램과 함께 쓰므로 툴을 꺼도 계속 돌도록 그룹에서 뺀다 (app/winjob.py)
    flags = NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0)
    try:
        subprocess.Popen([exe, "serve"], creationflags=flags | CREATE_BREAKAWAY_FROM_JOB,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        subprocess.Popen([exe, "serve"], creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if server_running():
            return "Ollama 서버를 자동으로 켰습니다"
        time.sleep(0.5)
    raise LLMError("Ollama 서버를 켜지 못했습니다. 작업 표시줄의 Ollama 아이콘을 확인하세요.")


def list_models() -> list[str]:
    try:
        return sorted(m["name"] for m in _request("/api/tags", timeout=5).get("models", []))
    except Exception:
        return []


def loaded_models() -> list[dict]:
    try:
        return _request("/api/ps", timeout=3).get("models", [])
    except Exception:
        return []


class OllamaEngine:
    """엔진 관리자에 등록되는 Ollama 엔진. 상태는 Ollama 서버에 직접 물어본다."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model

    @property
    def loaded(self) -> bool:
        return bool(loaded_models())

    @property
    def device(self) -> str | None:
        ms = loaded_models()
        if not ms:
            return None
        return "cuda" if any(m.get("size_vram", 0) > 0 for m in ms) else "cpu"

    def status(self) -> str:
        ms = loaded_models()
        if not ms:
            return "모델 내려감 (답변할 때만 올라감)" if server_running() else "서버 꺼짐"
        return "켜짐: " + ", ".join(f"{m['name']} ({m.get('size_vram', 0) // 2**20}MB GPU)" for m in ms)

    def load(self, model: str | None = None) -> str:
        """서버 확인만 한다. 실제 모델은 chat()에서 답변할 때 올라가고 바로 내려간다."""
        if model:
            self.model = model
        ensure_server()
        return self.status()

    def unload(self) -> None:
        """올라가 있는 모든 Ollama 모델을 GPU/메모리에서 내린다 (keep_alive=0)."""
        for m in loaded_models():
            try:
                _request("/api/chat", {"model": m["name"], "messages": [], "keep_alive": 0}, timeout=30)
            except Exception:
                pass

    def chat(self, history: list[dict], user_text: str, model: str | None = None) -> str:
        user_text = (user_text or "").strip()
        if not user_text:
            raise LLMError("질문이 비어 있습니다.")
        model = model or self.model
        ensure_server()
        if model not in list_models():
            raise LLMError(f"'{model}' 모델이 없습니다. PowerShell에서 'ollama pull {model}' 실행 후 다시 시도하세요.")
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += [{"role": m["role"], "content": m["content"]} for m in history
                     if m.get("role") in ("user", "assistant")]
        messages.append({"role": "user", "content": user_text})
        body = {"model": model, "messages": messages, "stream": False, "keep_alive": 0,
                "options": {"temperature": 0.7}}
        if "qwen3" in model:  # 생각 과정을 출력하는 모델은 생각을 끄고 바로 답하게
            body["think"] = False
        resp = _request("/api/chat", body, timeout=600)
        text = (resp.get("message") or {}).get("content", "").strip()
        if not text:
            raise LLMError("대화 AI가 빈 답변을 보냈습니다. 다시 시도하세요.")
        return clean_for_speech(text)


def clean_for_speech(text: str) -> str:
    """읽기 어려운 기호(마크다운, 이모지 등)를 지운다."""
    import re

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"[*#`_>|~]+", "", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()
