"""가짜 jieba_fast: 빌드가 필요한 jieba_fast 대신 같은 기능의 jieba(순수 파이썬)를 쓴다."""
from jieba import *  # noqa: F401,F403
from jieba import setLogLevel  # noqa: F401
