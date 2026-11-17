# VoiceStudio

집 PC에서 인터넷 없이 돌아가는 한국어 음성 AI 툴 (Windows · RTX 2060 6GB 기준)

- **말 → 글자**: faster-whisper (GPU/CPU 자동 전환)
- **글자 → 말**: MeloTTS 한국어 (CPU)
- **목소리 학습·복제**: GPT-SoVITS v2Pro (1분 이상 녹음으로 학습, 3~10초 샘플로 흉내)
- **음성 대화**: Ollama (gemma3:4b) + 선택한 목소리로 답변
- **엔진 관리자**: GPU에는 한 번에 하나의 엔진만 올려 VRAM 6GB를 지킴

## 실행
바탕화면 **VoiceStudio** 아이콘 더블클릭 (또는 `VoiceStudio.bat`) → 브라우저 `http://127.0.0.1:7860`

## 설치 (모두 D:에 설치됨)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1         # 메인 (약 6GB)
powershell -ExecutionPolicy Bypass -File scripts\install_sovits.ps1  # 목소리 학습 (약 8GB)
powershell -ExecutionPolicy Bypass -File scripts\make_shortcut.ps1   # 바탕화면 아이콘
ollama pull gemma3:4b                                                # 대화 AI
```
필요: [uv](https://docs.astral.sh/uv/), git, ffmpeg(`winget install Gyan.FFmpeg`), [Ollama](https://ollama.com), NVIDIA 드라이버(CUDA 12.x)

## 문서
- [사용·기능 설명서](docs/user-guide.md)
- [구성도](docs/architecture.md)
- [샘플 목소리와 라이선스](docs/voice-samples.md)
- [작업 계획](docs/plan.md) · [변경 기록](CHANGELOG.md) · [결정 기록](docs/decisions/) · [버그 기록](docs/bugs/)

## 테스트
```powershell
.venv\Scripts\python.exe -m pytest tests -q              # 전체 (실제 학습 포함 약 10분)
.venv\Scripts\python.exe -m pytest tests -q -m "not slow"  # 빠른 확인
```

## 라이선스 참고
- MeloTTS: MIT · GPT-SoVITS: MIT · faster-whisper: MIT · Gemma 3: Gemma 이용약관
- 샘플 목소리 데이터는 각자 라이선스를 따름 (예: KSS = CC BY-NC-SA 4.0, 상업적 사용 불가)
