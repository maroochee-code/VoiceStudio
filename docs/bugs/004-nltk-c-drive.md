# 004. 영어 발음 사전(nltk)이 C:에 내려받아짐

- 날짜: 2026-11-17 / 단계: 3단계
- 증상: `C:\Users\...\AppData\Roaming\nltk_data`에 약 20MB 생성
- 원인: `NLTK_DATA`로 D: 폴더를 지정했지만, nltk는 그 폴더가 **이미 존재할 때만** 거기에 받음. 없으면 C:의 기본 위치로 감.
- 해결: `app/config.py`에서 `models/nltk_data` 폴더를 미리 생성. C:에 받아진 파일은 D:로 옮기고 C: 폴더 삭제(오늘 생성된 파일만 있었음을 확인 후).
- 관련 파일: `app/config.py`, 테스트 `test_no_downloads_on_c_drive`

## 재발 (2026-11-17, 5단계)
- 증상: 실제 학습·합성 테스트 뒤 C:에 `nltk_data/corpora/cmudict`가 다시 생김 (단계별 테스트를 따로 돌리면 재현 안 됨, 학습 테스트에서만 발생)
- 원인: GPT-SoVITS 학습/합성 중 어느 하위 프로세스가 `NLTK_DATA`를 보지 못한 상태에서 nltk 사전을 찾음 → C: 기본 위치로 다운로드. 정확히 어느 프로세스인지는 **확인 필요**.
- 해결: 두 가상환경 안에 `nltk_data` 폴더(D:)를 만들고 사전을 복사. nltk는 C:보다 먼저 "파이썬 환경 안의 nltk_data 폴더"를 찾고 그곳에 받으므로, 어떤 프로세스든 D:에 남음. (GPT-SoVITS 공식 설치도 같은 위치를 씀)
- 확인: 실제 학습 테스트 후 C: 폴더 없음. 학습 테스트 끝에 C: 검사 추가.
- 관련 파일: `scripts/install.ps1`, `scripts/install_sovits.ps1`, `tests/test_stage5_sovits.py`
