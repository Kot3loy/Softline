"""Миграция БД и готовность приложения к запуску."""

import json

import aiosqlite
import pytest


@pytest.mark.asyncio
async def test_migration_v4_to_v5_adds_question_and_sources(tmp_path, monkeypatch):
    # старая база v4: в case_answers нет текста задания и источников
    import bot.database.db as dbm

    path = tmp_path / "old.db"
    conn = await aiosqlite.connect(str(path))
    await conn.execute("CREATE TABLE db_version (version INTEGER PRIMARY KEY)")
    await conn.execute("INSERT INTO db_version (version) VALUES (4)")
    await conn.execute(
        """CREATE TABLE case_answers (
            answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            case_id TEXT NOT NULL,
            scenario TEXT NOT NULL,
            user_answer TEXT,
            score INTEGER,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    await conn.commit()
    await conn.close()

    monkeypatch.setattr(dbm, "DB_PATH", path)
    monkeypatch.setattr(dbm, "_db", None)
    try:
        await dbm.init_db()
        conn = await aiosqlite.connect(str(path))
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("PRAGMA table_info(case_answers)")
        columns = {row["name"] for row in await cursor.fetchall()}
        cursor = await conn.execute("SELECT version FROM db_version")
        version = (await cursor.fetchone())["version"]
        await conn.close()
    finally:
        await dbm.close_db()

    assert {"question", "sources"} <= columns
    assert version == 5


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    from bot.main import health_handler

    response = await health_handler(None)

    assert response.status == 200
    assert json.loads(response.body) == {"status": "ok"}


def test_all_routers_are_registered():
    from bot.handlers import start, info, examiner, voice, pdf_export, inline

    for module in (start, info, examiner, voice, pdf_export, inline):
        assert module.router is not None
        assert module.router.name
