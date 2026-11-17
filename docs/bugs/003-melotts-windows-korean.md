# 003. 윈도우에서 한국어 발음 변환(g2pkk) 실패

- 날짜: 2026-11-17 / 단계: 3단계
- 증상: 한국어 문장 합성 시 `you have to install eunjeon` 후 `TypeError: exceptions must derive from BaseException`
- 원인:
  1. g2pkk는 윈도우에서 오래된 `eunjeon` 패키지만 찾고, 없으면 시스템 `pip`로 몰래 설치를 시도함(가상환경이 아닌 C: 파이썬으로 갈 위험).
  2. 대안인 `python-mecab-ko`를 그냥 설치하면 폴더 이름 `mecab`이 일본어용 `MeCab`과 대소문자만 달라서, 윈도우에서는 같은 폴더로 취급되어 일본어용 파일을 덮어씀.
- 해결:
  - `python-mecab-ko`를 별도 폴더 `engines/mecab_ko`에 설치 (`uv pip install --target engines\mecab_ko --no-deps python-mecab-ko python-mecab-ko-dic`)
  - `app/tts.py`의 `_patch_korean_mecab()`이 그 폴더를 경로에 추가하고, g2pkk가 eunjeon 대신 python-mecab-ko를 쓰도록 바꿔 끼움(MeloTTS·g2pkk 원본 코드는 수정 안 함)
  - 테스트 `test_japanese_mecab_not_broken`으로 충돌 재발 감시
- 관련 파일: `app/tts.py`, `scripts/install.ps1`, `tests/test_stage3_tts.py`
