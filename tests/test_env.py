"""1단계 환경 테스트: 파이썬 버전, 설치 위치(D:), GPU 인식, 실제 GPU 계산."""
import sys
from pathlib import Path

import pytest
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from app.gpu_check import get_gpu_info  # noqa: E402


def test_python_is_310():
    assert sys.version_info[:2] == (3, 10)


def test_venv_on_d_drive():
    assert Path(sys.executable).resolve().drive.upper() == "D:"
    assert Path(sys.prefix).resolve() == (PROJECT_ROOT / ".venv").resolve()


def test_torch_on_d_drive():
    assert Path(torch.__file__).resolve().drive.upper() == "D:"


def test_cuda_available():
    assert torch.cuda.is_available(), "CUDA(GPU)를 사용할 수 없습니다"


def test_gpu_is_rtx_2060():
    info = get_gpu_info()
    assert "2060" in info["name"]
    assert 5500 < info["vram_total_mb"] <= 6144


def test_torch_build_supports_turing():
    # RTX 2060 = Turing = sm_75. 빌드에 포함되어야 실제 계산이 가능하다.
    assert "sm_75" in torch.cuda.get_arch_list()


def test_gpu_actually_computes():
    a = torch.ones(512, 512, device="cuda")
    result = (a @ a).sum().item()
    assert result == pytest.approx(512 * 512 * 512)


def test_secrets_ignored_by_git():
    ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    for item in (".env", ".venv/", "*.wav", "*.mp3", "models/"):
        assert item in ignore
