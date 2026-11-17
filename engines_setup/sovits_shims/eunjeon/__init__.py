"""가짜 eunjeon: 윈도우용 설치 파일이 없는 eunjeon 대신 python-mecab-ko를 쓴다.

GPT-SoVITS / g2pk2 는 윈도우에서 `from eunjeon import Mecab` 을 쓰므로 같은 모양만 맞춰준다.
(VoiceStudio docs/bugs/005 참고)
"""
import mecab as _mecab


class Mecab:
    def __init__(self, dicpath=None):
        self._m = _mecab.MeCab()

    def pos(self, phrase, flatten=True, join=False):
        result = self._m.pos(phrase)
        if join:
            return [f"{w}/{t}" for w, t in result]
        return result

    def morphs(self, phrase):
        return self._m.morphs(phrase)

    def nouns(self, phrase):
        return self._m.nouns(phrase)
