"""Версия сборки для раздела «О боте»: коммит и дата изменения."""

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timezone

import aiohttp

from bot.translations import t

logger = logging.getLogger(__name__)

REPO = "Kot3loy/Softline"
SHORT_SHA_LEN = 7

_cached_sha = ""
_cached_date = None
_cache_lock = asyncio.Lock()


def reset_cache():
    # сброс кэша (тесты и повторная инициализация)
    global _cached_sha, _cached_date
    _cached_sha = ""
    _cached_date = None


def _short(sha: str) -> str:
    return (sha or "").strip()[:SHORT_SHA_LEN]


def _read_sha() -> str:
    # Render подставляет коммит сам; локально берём из git
    sha = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or ""
    if sha:
        return sha.strip()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.debug(f"git rev-parse недоступен: {e}")
    return ""


async def _fetch_commit_date(sha: str) -> datetime | None:
    # дата коммита из публичного GitHub API, без токена хватает 60 запросов/час
    repo = os.getenv("GITHUB_REPO", REPO)
    url = f"https://api.github.com/repos/{repo}/commits/{sha}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "softline-bot"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    timeout = aiohttp.ClientTimeout(total=5)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(f"GitHub API вернул {resp.status} для {sha[:7]}")
                    return None
                data = await resp.json()
                raw = (data.get("commit", {}).get("committer") or {}).get("date")
                if not raw:
                    return None
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception as e:
        logger.warning(f"Не удалось получить дату коммита: {e}")
        return None


def format_block(sha: str, changed: datetime | None, lang: str = "ru") -> str:
    # «Версия»: короткий коммит ссылкой и дата изменения; без даты — только коммит
    short = _short(sha)
    if not short:
        return ""

    repo = os.getenv("GITHUB_REPO", REPO)
    link = f'<a href="https://github.com/{repo}/commit/{sha.strip()}">{short}</a>'
    if changed:
        stamp = changed.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
        build = f"{link} · {stamp}"
    else:
        build = link

    return t("version_title", lang) + "\n" + t("version_build", lang, version=build)


async def get_version_block(lang: str = "ru") -> str:
    # блок версии с кэшем: GitHub дёргаем один раз за жизнь процесса
    global _cached_sha, _cached_date

    sha = _read_sha()
    if not sha:
        return ""

    async with _cache_lock:
        if _cached_sha != sha:
            _cached_sha = sha
            _cached_date = await _fetch_commit_date(sha)
        changed = _cached_date
    return format_block(sha, changed, lang)
