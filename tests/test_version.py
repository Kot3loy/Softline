"""Блок версии в «О боте»: коммит и дата изменения."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from bot.utils import version
from bot.utils.version import format_block, get_version_block


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch):
    version.reset_cache()
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    yield
    version.reset_cache()


def test_format_block_links_short_sha_and_date():
    changed = datetime(2026, 10, 21, 18, 42, tzinfo=timezone.utc)

    block = format_block("60b73d3aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", changed)

    assert '<a href="https://github.com/Kot3loy/Softline/commit/60b73d3' in block
    assert ">60b73d3</a>" in block
    assert "21.10.2026 18:42 UTC" in block


def test_format_block_without_date_shows_only_sha():
    block = format_block("60b73d3aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", None)

    assert "60b73d3" in block
    assert "UTC" not in block


def test_format_block_without_sha_is_empty():
    assert format_block("", datetime(2026, 10, 21, tzinfo=timezone.utc)) == ""


@pytest.mark.asyncio
async def test_version_block_uses_render_commit(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abcdef1234567890")
    monkeypatch.setattr(
        version,
        "_fetch_commit_date",
        AsyncMock(return_value=datetime(2026, 10, 21, 18, 42, tzinfo=timezone.utc)),
    )

    block = await get_version_block("ru")

    assert "abcdef1" in block
    assert "21.10.2026 18:42 UTC" in block


@pytest.mark.asyncio
async def test_version_block_without_api_keeps_sha(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abcdef1234567890")
    monkeypatch.setattr(version, "_fetch_commit_date", AsyncMock(return_value=None))

    block = await get_version_block("ru")

    assert "abcdef1" in block
    assert "UTC" not in block


@pytest.mark.asyncio
async def test_version_block_is_cached(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abcdef1234567890")
    fetch = AsyncMock(return_value=datetime(2026, 10, 21, 18, 42, tzinfo=timezone.utc))
    monkeypatch.setattr(version, "_fetch_commit_date", fetch)

    await get_version_block("ru")
    await get_version_block("en")

    assert fetch.await_count == 1


@pytest.mark.asyncio
async def test_about_screen_includes_version(monkeypatch, test_db, mock_message):
    from bot.handlers import start as start_mod

    monkeypatch.setattr(
        start_mod,
        "get_version_block",
        AsyncMock(return_value="🛠 <b>Версия</b>\nСборка: abc1234"),
    )

    await start_mod.cmd_help(mock_message)

    text = mock_message.answer.await_args.args[0]
    assert "🛠 <b>Версия</b>" in text
    assert "abc1234" in text


@pytest.mark.asyncio
async def test_version_block_empty_without_commit(monkeypatch):
    monkeypatch.setattr(version, "_read_sha", lambda: "")

    assert await get_version_block("ru") == ""
