"""VoiceStudio 아이콘(assets/voicestudio.ico) 만들기: 원 안의 마이크 모양."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "assets" / "voicestudio.ico"


def draw(size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 256
    d.ellipse([8 * s, 8 * s, 248 * s, 248 * s], fill=(234, 88, 12, 255))           # 주황 원
    d.rounded_rectangle([98 * s, 52 * s, 158 * s, 150 * s], radius=30 * s, fill="white")  # 마이크 머리
    d.arc([76 * s, 92 * s, 180 * s, 182 * s], start=0, end=180, fill="white", width=int(12 * s))
    d.rectangle([122 * s, 180 * s, 134 * s, 206 * s], fill="white")                 # 기둥
    d.rounded_rectangle([92 * s, 202 * s, 164 * s, 214 * s], radius=6 * s, fill="white")  # 받침
    return img


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    draw().save(OUT, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("아이콘 저장:", OUT)
