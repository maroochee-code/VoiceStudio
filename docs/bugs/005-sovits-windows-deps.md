# 005. GPT-SoVITS 윈도우 설치 문제 (빌드 필요 패키지, 경로, 누락 패키지)

- 날짜: 2026-11-17 / 단계: 5단계
- 증상과 해결:
  1. `eunjeon`(한국어), `jieba_fast`(중국어), `pyopenjtalk`(일본어)은 윈도우용 설치 파일이 없어 C++ 컴파일러가 필요
     → `eunjeon`: python-mecab-ko를 감싼 대체 모듈(`engines_setup/sovits_shims/eunjeon`)
     → `jieba_fast`: 순수 파이썬 `jieba`를 감싼 대체 모듈
     → `pyopenjtalk`: 윈도우 설치 파일이 있는 `pyopenjtalk-plus`로 교체
     → `opencc`: 원래 목록의 `--no-binary=opencc`(강제 빌드) 줄 삭제 → 윈도우 설치 파일 사용
  2. gradio 버전이 3.36으로 잘못 골라져 `No module named 'gradio_client.serializing'` → `gradio==4.44.1`로 고정
  3. 합성 시 `No module named 'resampy'` (원래 목록에 빠져 있음) → 추가
  4. 학습 스크립트가 `No module named 'tools'` → GPT-SoVITS 웹 화면이 시작할 때 몰래 만드는 `users.pth`(모듈 경로 파일)를 설치 단계에서 직접 생성
  5. 윈도우의 가상환경 python.exe는 진짜 파이썬을 자식 프로세스로 띄움 → 서버를 끌 때 `taskkill /T`로 자식까지 종료 (`kill_tree`)
- 관련 파일: `engines_setup/sovits-requirements.txt`, `engines_setup/sovits_shims/`, `scripts/install_sovits.ps1`, `app/sovits.py`
