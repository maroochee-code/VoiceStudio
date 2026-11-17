# VoiceStudio 작업 계획

작성일: 2026-11-17 / 기준 문서: `CLAUDE.md` (로컬 음성 AI 툴 기획서)

## 0. 현재 PC 점검 결과 (2026-11-17 확인)

| 항목 | 상태 | 비고 |
|---|---|---|
| GPU | RTX 2060, VRAM 6144MB, 드라이버 610.88 | CUDA 12.x 지원 드라이버 |
| 디스크 여유 | C: 130GB / D: 678GB | 모든 설치는 D: |
| Python | 3.13 (C:), 3.9 (D:\anaconda3) | 둘 다 사용 안 함 (아래 설명) |
| uv | 0.7.2 설치됨 | 파이썬·패키지 설치 도구 |
| git / gh | 설치됨, GitHub 로그인 완료 (`maroochee-code`) | 저장소 생성 가능 |
| Ollama | 설치됨 | 7단계에서 사용 |

### 파이썬 버전 선택: 3.10 (새로 설치, D:에)
- 3.13은 너무 최신이라 MeloTTS 등 음성 라이브러리가 아직 지원하지 않을 가능성이 큼.
- 3.9(아나콘다)는 기존 환경과 섞일 위험이 있음.
- 3.10은 faster-whisper·MeloTTS 모두 사용 사례가 가장 많은 버전 → 설치 시 공식 문서로 재확인 예정.
- GPT-SoVITS는 의존성이 무거워 **별도 가상환경**으로 분리할 예정(5단계에서 결정, 결정 기록 남김).

## 1. 전체 폴더 구조 (예정)

```
D:\Github\VoiceStudio\
├─ app\            툴 본체 코드 (엔진 관리, UI)
├─ tests\          pytest 자동 테스트
├─ docs\           계획, 결정 기록, 버그 기록, 설명서
├─ data\           녹음/생성 음성, 학습 샘플 (Git 제외)
├─ models\         내려받은 모델 파일 (Git 제외)
├─ .venv\          파이썬 가상환경 (Git 제외)
└─ .uv\            파이썬 본체·다운로드 캐시 (C: 대신 D:에 두기 위함, Git 제외)
```

## 2. 단계별 계획

각 단계 끝에: pytest 자동 테스트 통과 → 사용자 직접 확인 → "N단계: 요약" 커밋·푸시 → CHANGELOG 기록 → 승인 후 다음 단계.

### 1단계: 환경 준비 (버전 0.1.0)
1. `git init`, `.gitignore`(가상환경·모델·.wav/.mp3·대용량·.env) 작성
2. uv 캐시와 파이썬 설치 위치를 D:로 지정 (`UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR` → `D:\Github\VoiceStudio\.uv\`)
3. Python 3.10 설치 + `.venv` 가상환경 생성
4. CUDA 지원 PyTorch 설치 → **2.5.1 + CUDA 12.4로 결정** (이유: `docs/decisions/001-python-torch-version.md`)
5. `app/gpu_check.py`: GPU 이름·VRAM 출력하는 확인 스크립트
6. `tests/test_env.py`: ① 파이썬 3.10인지 ② CUDA 사용 가능 ③ GPU 이름에 "2060" 포함 ④ 가상환경이 D:에 있는지
7. `CHANGELOG.md`, `docs/decisions/001-python-uv.md` 작성
8. 커밋 → `gh repo create VoiceStudio --private --source=. --push`
- **다운로드 예상**: Python 3.10 약 30MB, PyTorch(CUDA) 약 2.5~3GB, pytest 등 약 10MB → 총 약 3GB, 설치 후 D: 사용량 약 5~6GB
- **완료 조건**: `python app/gpu_check.py` 실행 시 RTX 2060 표시, 테스트 전부 통과

### 2단계: 녹음 + 말 → 글자 (0.2.0)
- `sounddevice`로 K66 마이크 녹음 → WAV 저장 → 샘플 폴더 복사 기능
- faster-whisper(small 기본, medium 선택) 한국어 변환, 결과 텍스트 저장
- GPU 여유 부족 시 CPU 자동 전환 로직
- 자동 테스트: 미리 만든 음성 파일 변환, 저장 경로, CPU 전환 로직 / 직접 확인: K66로 말해보기
- 다운로드: small 약 0.5GB, medium 약 1.5GB

### 3단계: 글자 → 말 MeloTTS (0.3.0)
- MeloTTS 한국어 설치(CPU 모드), 속도 조절, WAV 저장
- 자동 테스트: 문장 → WAV 생성·길이 확인 / 직접 확인: 귀로 듣기
- 다운로드: 약 1~2GB(모델 + 의존성, **확인 필요**)

### 4단계: 웹 UI 통합 (0.4.0)
- Gradio 탭: 녹음 / 말→글자 / 글자→말 / 엔진 상태(VRAM 표시)
- 엔진 관리자(지휘자) 기초: 엔진별 로드/언로드, 동시 GPU 로드 금지
- 자동 테스트: 엔진 관리자 규칙 / 직접 확인: 브라우저에서 버튼 조작

### 5단계: 목소리 학습 GPT-SoVITS (0.5.0)
- D:에 GPT-SoVITS 설치(별도 환경), 샘플 정리 → 학습 → 이름 붙여 저장
- 학습 전 위스퍼·Ollama 자동 언로드
- 실제: 다운로드 약 3GB(패키지) + 1.6GB(사전 학습 모델), v2Pro 사용 — `docs/decisions/003-gpt-sovits-setup.md`

### 6단계: 목소리 선택 + 샘플 목소리 (0.6.0)
- 목소리 목록(기본/학습/샘플), `data/voices/samples/` 폴더 + 라이선스 메모 파일
- KSS·AI 허브 데이터는 사용자가 직접 받아 넣음(AI 허브는 회원가입·신청 필요)
- MP3 저장(ffmpeg 필요 — 설치 위치 D:)

### 7단계: Ollama 연동 + 음성 대화 (0.7.0)
- `ollama serve` 자동 실행 확인, 답변 시에만 모델 로드 → `keep_alive=0`으로 즉시 내림
- 대화 기록 유지, 말하기 → 위스퍼 → Ollama → 선택 목소리
- Ollama 모델(Gemma 3 4B 약 3.3GB 등) 다운로드 필요

### 8단계: 마무리 (1.0.0)
- 바탕화면 바로가기(배치 파일), 오류 메시지 한국어화, 사용 설명서, 구성도(Mermaid), 기능 설명서

## 3. 위험 요소 / 미리 알려드릴 점
- **VRAM 6GB**: GPT-SoVITS 학습이 가장 빠듯함. 학습 중에는 다른 GPU 엔진 모두 내림.
- **라이브러리 호환성**: MeloTTS·GPT-SoVITS는 특정 라이브러리 버전을 요구해서 충돌 가능 → 환경 분리로 대응.
- **C: 드라이브 침범 방지**: uv·pip·허깅페이스(모델 다운로드) 캐시가 기본값으로 C:에 쌓이므로, 단계마다 캐시 위치를 D:로 지정함 (`HF_HOME` 등).
