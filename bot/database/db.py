"""Модуль работы с базой данных — singleton соединение, миграции, CRUD."""

import logging
import asyncio
import aiosqlite
from bot.config import config

logger = logging.getLogger(__name__)

DB_PATH = config.DATABASE_DIR / config.DATABASE_NAME
_db: aiosqlite.Connection | None = None
_db_lock = asyncio.Lock()
_DB_VERSION = 2


async def _get_db() -> aiosqlite.Connection:
    """Получить singleton соединение с reconnection"""
    global _db
    async with _db_lock:
        if _db is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _db = await aiosqlite.connect(str(DB_PATH))
            _db.row_factory = aiosqlite.Row
            await _db.execute("PRAGMA foreign_keys = ON")
            await _db.execute("PRAGMA journal_mode = WAL")
            logger.info("Соединение с БД установлено")
        else:
            # Проверяем соединение — если упало, пересоздаём
            try:
                await _db.execute("SELECT 1")
            except Exception as e:
                logger.warning(f"Соединение с БД потеряно: {e}, пересоздаю...")
                try:
                    await _db.close()
                except Exception:
                    pass
                _db = await aiosqlite.connect(str(DB_PATH))
                _db.row_factory = aiosqlite.Row
                await _db.execute("PRAGMA foreign_keys = ON")
                await _db.execute("PRAGMA journal_mode = WAL")
                logger.info("Соединение с БД пересоздано")
        return _db


async def close_db():
    """Закрыть соединение"""
    global _db
    async with _db_lock:
        if _db:
            await _db.close()
            _db = None
            logger.info("Соединение с БД закрыто")


async def init_db():
    """Инициализация базы данных + миграции"""
    db = await _get_db()

    # Таблица версий
    await db.execute("""
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER PRIMARY KEY
        )
    """)
    await db.commit()

    # Текущая версия
    cursor = await db.execute("SELECT version FROM db_version LIMIT 1")
    row = await cursor.fetchone()
    current_version = row["version"] if row else 0

    if current_version == 0:
        # Первоначальная установка
        await _create_tables(db)
        await db.execute("INSERT INTO db_version (version) VALUES (?)", (_DB_VERSION,))
        await db.commit()
        logger.info(f"БД создана (версия {_DB_VERSION})")
    elif current_version < _DB_VERSION:
        # Миграции
        await _migrate(db, current_version)
        await db.execute("UPDATE db_version SET version = ?", (_DB_VERSION,))
        await db.commit()
        logger.info(f"БД обновлена до версии {_DB_VERSION}")
    else:
        logger.info(f"БД актуальна (версия {current_version})")


async def _create_tables(db: aiosqlite.Connection):
    """Создать все таблицы"""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            voice_enabled INTEGER DEFAULT 0,
            current_scenario TEXT DEFAULT 'university',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scenario TEXT NOT NULL,
            mode TEXT NOT NULL,
            cases_total INTEGER DEFAULT 0,
            cases_completed INTEGER DEFAULT 0,
            avg_score REAL DEFAULT 0,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS case_answers (
            answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            case_id TEXT NOT NULL,
            scenario TEXT NOT NULL,
            user_answer TEXT,
            score INTEGER,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    await db.commit()


async def _migrate(db: aiosqlite.Connection, from_version: int):
    """Выполнить миграции до целевой версии"""
    if from_version < 2:
        # Миграция v1 → v2: добавляем индексы
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_answers_user ON case_answers(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_answers_session ON case_answers(session_id)")
        logger.info("Миграция v1→v2: добавлены индексы")


# ─── CRUD ───


async def get_or_create_user(user_id: int, username: str = None,
                              first_name: str = None, last_name: str = None) -> dict:
    """Получить или создать пользователя"""
    db = await _get_db()

    cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()

    if row:
        await db.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        return dict(row)

    await db.execute(
        "INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
        (user_id, username, first_name, last_name),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    return dict(row)


async def update_user(user_id: int, **kwargs):
    """Обновить данные пользователя"""
    allowed_fields = {"username", "first_name", "last_name", "voice_enabled", "current_scenario"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return

    db = await _get_db()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]
    await db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
    await db.commit()


async def reset_user_progress(user_id: int):
    """Сбросить прогресс пользователя: ответы на кейсы и сессии"""
    db = await _get_db()
    await db.execute("DELETE FROM case_answers WHERE user_id = ?", (user_id,))
    await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    await db.execute(
        "UPDATE users SET current_scenario = 'university' WHERE user_id = ?",
        (user_id,),
    )
    await db.commit()
    logger.info(f"Прогресс сброшен для user={user_id}")


async def create_session(user_id: int, scenario: str, mode: str, cases_total: int = 0) -> int:
    """Создать новую сессию"""
    db = await _get_db()
    cursor = await db.execute(
        "INSERT INTO sessions (user_id, scenario, mode, cases_total) VALUES (?, ?, ?, ?)",
        (user_id, scenario, mode, cases_total),
    )
    await db.commit()
    return cursor.lastrowid


async def end_session(session_id: int, cases_completed: int, avg_score: float):
    """Завершить сессию"""
    db = await _get_db()
    await db.execute(
        "UPDATE sessions SET cases_completed = ?, avg_score = ?, ended_at = CURRENT_TIMESTAMP WHERE session_id = ?",
        (cases_completed, avg_score, session_id),
    )
    await db.commit()


async def save_case_answer(session_id: int, user_id: int, case_id: str,
                            scenario: str, user_answer: str, score: int, feedback: str):
    """Сохранить ответ на кейс"""
    db = await _get_db()
    await db.execute(
        """INSERT INTO case_answers
        (session_id, user_id, case_id, scenario, user_answer, score, feedback)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, user_id, case_id, scenario, user_answer, score, feedback),
    )
    await db.commit()


async def get_user_stats(user_id: int) -> dict:
    """Получить статистику пользователя"""
    db = await _get_db()

    cursor = await db.execute(
        """SELECT COUNT(*) as total_sessions, AVG(avg_score) as avg_score
        FROM sessions WHERE user_id = ? AND cases_completed > 0""",
        (user_id,),
    )
    row = await cursor.fetchone()

    cursor = await db.execute(
        """SELECT scenario, COUNT(*) as sessions, AVG(avg_score) as avg_score
        FROM sessions WHERE user_id = ? AND cases_completed > 0
        GROUP BY scenario""",
        (user_id,),
    )
    scenarios = await cursor.fetchall()

    return {
        "total_sessions": row["total_sessions"] if row else 0,
        "avg_score": round(row["avg_score"] or 0, 1) if row else 0,
        "scenarios": {s["scenario"]: {"sessions": s["sessions"], "avg_score": round(s["avg_score"] or 0, 1)} for s in scenarios},
    }


async def get_all_users(limit: int = 9999) -> list:
    """Получить список пользователей (с пагинацией)"""
    db = await _get_db()
    # Если limit слишком большой — берём всех
    if limit >= 9999:
        cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
    else:
        cursor = await db.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_case_answers(user_id: int, scenario: str = None) -> list:
    """Получить ответы на кейсы пользователя"""
    db = await _get_db()
    if scenario:
        cursor = await db.execute(
            """SELECT ca.*, s.mode FROM case_answers ca
            JOIN sessions s ON ca.session_id = s.session_id
            WHERE ca.user_id = ? AND ca.scenario = ?
            ORDER BY ca.created_at""",
            (user_id, scenario),
        )
    else:
        cursor = await db.execute(
            """SELECT ca.*, s.mode FROM case_answers ca
            JOIN sessions s ON ca.session_id = s.session_id
            WHERE ca.user_id = ?
            ORDER BY ca.created_at""",
            (user_id,),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_global_stats() -> dict:
    """Глобальная статистика для админки"""
    db = await _get_db()

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM users")
    row = await cursor.fetchone()
    total_users = row["cnt"]

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM sessions")
    row = await cursor.fetchone()
    total_sessions = row["cnt"]

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt, AVG(avg_score) as avg_score FROM sessions WHERE cases_completed > 0"
    )
    row = await cursor.fetchone()
    completed_sessions = row["cnt"]
    avg_score = round(row["avg_score"] or 0, 1)

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM case_answers")
    row = await cursor.fetchone()
    total_answers = row["cnt"]

    cursor = await db.execute(
        """SELECT scenario, COUNT(*) as sessions, AVG(avg_score) as avg_score
        FROM sessions WHERE cases_completed > 0
        GROUP BY scenario"""
    )
    scenarios = {s["scenario"]: {"sessions": s["sessions"], "avg_score": round(s["avg_score"] or 0, 1)} for s in await cursor.fetchall()}

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "completed_sessions": completed_sessions,
        "avg_score": avg_score,
        "total_answers": total_answers,
        "by_scenario": scenarios,
    }
