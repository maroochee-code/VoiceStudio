# 변경 기록 (CHANGELOG)

## 0.1.0 — 2026-11-17 (1단계: 환경 준비)
### 추가
- Python 3.10.17 가상환경(`.venv`)을 D:에 생성 (파이썬 본체·캐시도 `D:\Github\VoiceStudio\.uv\`)
- CUDA 지원 PyTorch 2.5.1 (CUDA 12.4) 설치, RTX 2060 인식 확인
- `app/gpu_check.py`: GPU 이름·VRAM을 한국어로 보여주는 확인 스크립트
- `tests/test_env.py`: 환경 자동 테스트 8개
- `.gitignore`, `.env.example`, `requirements.txt`
- 결정 기록 `docs/decisions/001-python-torch-version.md`
