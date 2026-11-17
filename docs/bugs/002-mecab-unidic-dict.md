# 002. MeCab 초기화 실패 (`mecabrc` 없음)

- 날짜: 2026-11-17 / 단계: 3단계
- 증상: MeloTTS 불러올 때 `Failed initializing MeCab ... unidic\dicdir\mecabrc: no such file`
- 원인: MeloTTS는 언어 모듈을 전부 한꺼번에 불러오는데, 일본어 모듈이 `unidic`(대용량 일본어 사전)을 찾음. 이 사전은 `python -m unidic download`로 따로 받아야 함(수백 MB 이상).
- 해결: 한국어에는 필요 없으므로 `unidic` 패키지를 제거 → MeCab이 이미 설치된 소형 사전 `unidic-lite`를 자동 사용.
- 주의: MeloTTS를 다시 설치하면 `unidic`이 다시 깔리므로 `scripts/install.ps1`에서 제거까지 수행.
- 관련 파일: `scripts/install.ps1`
