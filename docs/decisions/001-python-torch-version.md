# 001. 파이썬·PyTorch 버전과 설치 도구

날짜: 2026-11-17

## 고른 것
- 파이썬 3.10.17 (uv로 D:에 새로 설치)
- PyTorch 2.5.1 + CUDA 12.4 빌드
- 설치 도구: uv (캐시·파이썬 본체 위치를 환경변수로 D:에 고정)

## 왜
- 3.10은 faster-whisper·MeloTTS 사용 사례가 가장 많은 버전.
- PyTorch 2.6부터 `torch.load`의 기본 동작(weights_only=True)이 바뀌어 2024년 이전 모델 코드(MeloTTS 등)가 오류를 낼 수 있음 → 그 직전 버전 2.5.1 선택.
- CUDA 12.4 빌드는 RTX 2060(sm_75)을 지원하고 cuDNN 9를 포함해 faster-whisper(CTranslate2)와도 맞음.
- numpy는 오래된 음성 라이브러리 호환을 위해 1.x(1.26.4)로 고정.

## 다른 후보
- 기존 Python 3.13: 너무 최신이라 음성 라이브러리 미지원 가능성.
- 아나콘다 3.9: 기존 환경과 섞일 위험.
- 최신 PyTorch 2.14: 위의 torch.load 변경 때문에 보류. 문제가 없으면 나중에 올릴 수 있음.
