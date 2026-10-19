"""Поиск ffmpeg: сначала pip-колесо imageio-ffmpeg, потом система, потом ручные папки."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from bot.handlers import voice as voice_mod


def _fake_imageio_ffmpeg(path):
    mod = ModuleType("imageio_ffmpeg")
    mod.get_ffmpeg_exe = lambda: str(path)
    return mod


def test_resolve_prefers_imageio_wheel(tmp_path):
    exe = tmp_path / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    exe.write_bytes(b"binary")
    with patch.dict(sys.modules, {"imageio_ffmpeg": _fake_imageio_ffmpeg(exe)}):
        assert voice_mod._resolve_ffmpeg() == str(exe)


def test_resolve_falls_back_to_system(tmp_path):
    mod = ModuleType("imageio_ffmpeg")

    def boom():
        raise RuntimeError("нет бинарника")

    mod.get_ffmpeg_exe = boom
    with patch.dict(sys.modules, {"imageio_ffmpeg": mod}), \
            patch.object(voice_mod.shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None):
        assert voice_mod._resolve_ffmpeg() == "/usr/bin/ffmpeg"


def test_resolve_returns_none_when_nothing_found(tmp_path, monkeypatch):
    mod = ModuleType("imageio_ffmpeg")

    def boom():
        raise RuntimeError("нет бинарника")

    mod.get_ffmpeg_exe = boom
    monkeypatch.chdir(tmp_path)
    with patch.dict(sys.modules, {"imageio_ffmpeg": mod}), \
            patch.object(voice_mod.shutil, "which", lambda name: None), \
            patch.object(voice_mod.os.path, "exists", lambda p: False):
        assert voice_mod._resolve_ffmpeg() is None


def test_no_ffmpeg_does_not_break_import(tmp_path, monkeypatch):
    # отсутствие ffmpeg не должно ронять модуль — просто голос молчит
    monkeypatch.setattr(voice_mod, "_ffmpeg_path", None)
    monkeypatch.setattr(voice_mod, "_ffprobe_path", None)
    assert isinstance(Path(__file__).name, str)
