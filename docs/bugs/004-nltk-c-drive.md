# 004. 영어 발음 사전(nltk)이 C:에 내려받아짐

- 날짜: 2026-11-17 / 단계: 3단계
- 증상: `C:\Users\...\AppData\Roaming\nltk_data`에 약 20MB 생성
- 원인: `NLTK_DATA`로 D: 폴더를 지정했지만, nltk는 그 폴더가 **이미 존재할 때만** 거기에 받음. 없으면 C:의 기본 위치로 감.
- 해결: `app/config.py`에서 `models/nltk_data` 폴더를 미리 생성. C:에 받아진 파일은 D:로 옮기고 C: 폴더 삭제(오늘 생성된 파일만 있었음을 확인 후).
- 관련 파일: `app/config.py`, 테스트 `test_no_downloads_on_c_drive`
