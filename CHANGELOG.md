# 변경 기록 (CHANGELOG)

## 0.3.0 — 2026-11-17 (3단계: 글자 → 말 MeloTTS)
### 추가
- `app/tts.py`: MeloTTS 한국어 엔진(켜기/끄기/상태), CPU 기본, 속도 조절(0.5~2.0배), WAV 저장, 스피커 재생
- `app/try_tts.py`: 문장을 바로 읽어보는 실행 파일
- `scripts/install.ps1`: 처음부터 똑같이 다시 설치하는 스크립트, `requirements-lock.txt`(정확한 버전 목록)
- 테스트 9개 추가(멜로 음성을 위스퍼로 다시 알아듣는지 왕복 확인 포함)
### 수정
- 윈도우에서 MeloTTS가 안 되던 문제 3가지 우회 (`docs/bugs/001~003`)
- 영어 발음 사전이 C:에 받아지던 문제 수정, D:로 이동 (`docs/bugs/004`)

## 0.2.0 — 2026-11-17 (2단계: 녹음 + 말 → 글자)
### 추가
- `app/recorder.py`: K66 마이크 자동 선택, 녹음(44.1kHz 모노), WAV 저장, 학습 샘플 폴더로 보내기, 샘플 총 길이 계산
- `app/stt.py`: faster-whisper 엔진(켜기/끄기/상태), 한국어 변환, 결과 텍스트 저장
- VRAM이 부족하면 자동으로 CPU 모드로 전환(small 약 1.2GB, medium 약 2.6GB 기준)
- `app/config.py`: 폴더 위치 모음, 모델 캐시를 D:로 고정
- `app/try_stt.py`: 마이크로 말해서 바로 확인하는 실행 파일
- 테스트 13개 추가(윈도우 한국어 음성으로 만든 파일로 GPU·CPU 변환 확인)

## 0.1.0 — 2026-11-17 (1단계: 환경 준비)
### 추가
- Python 3.10.17 가상환경(`.venv`)을 D:에 생성 (파이썬 본체·캐시도 `D:\Github\VoiceStudio\.uv\`)
- CUDA 지원 PyTorch 2.5.1 (CUDA 12.4) 설치, RTX 2060 인식 확인
- `app/gpu_check.py`: GPU 이름·VRAM을 한국어로 보여주는 확인 스크립트
- `tests/test_env.py`: 환경 자동 테스트 8개
- `.gitignore`, `.env.example`, `requirements.txt`
- 결정 기록 `docs/decisions/001-python-torch-version.md`
