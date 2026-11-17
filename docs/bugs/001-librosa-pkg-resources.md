# 001. MeloTTS 실행 시 `No module named 'pkg_resources'`

- 날짜: 2026-11-17 / 단계: 3단계
- 증상: `from melo.api import TTS` 실행 시 librosa에서 `ModuleNotFoundError: No module named 'pkg_resources'`
- 원인: MeloTTS가 요구하는 librosa 0.9.1은 `pkg_resources`를 쓰는데, 최신 setuptools(81 이상)에서 이 모듈이 빠짐.
- 해결: `setuptools<81` 설치 (현재 80.10.2). `scripts/install.ps1`에 반영.
- 관련 파일: `scripts/install.ps1`, `requirements.txt`
