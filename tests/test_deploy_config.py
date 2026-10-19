"""Конфиг деплоя: сборка не должна зависеть от загрузок с чужих сайтов."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_render_build_does_not_download_ffmpeg():
    # раньше buildCommand тянул ffmpeg с johnvansickle.com — сборка падала по SSL-таймауту
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "curl" not in text
    assert "johnvansickle" not in text


def test_ffmpeg_comes_from_pip():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "imageio-ffmpeg" in requirements
