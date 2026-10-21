# работа с базой данных — singleton соединение, миграции, CRUD

import logging
import asyncio
import aiosqlite
from bot.config import config

logger = logging.getLogger(__name__)

DB_PATH = config.DATABASE_DIR / config.DATABASE_NAME
_db = None
_db_lock = asyncio.Lock()
_DB_VERSION = 5


async def _get_db():
    # получаем singleton соединение с reconnection
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
    # закрыть соединение
    global _db
    async with _db_lock:
        if _db:
            await _db.close()
            _db = None
            logger.info("Соединение с БД закрыто")


async def init_db():
    # инициализация базы данных + миграции
    db = await _get_db()

    await db.execute("""
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER PRIMARY KEY
        )
    """)
    await db.commit()

    cursor = await db.execute("SELECT version FROM db_version LIMIT 1")
    row = await cursor.fetchone()
    current_version = row["version"] if row else 0

    if current_version == 0:
        await _create_tables(db)
        await db.execute("INSERT INTO db_version (version) VALUES (?)", (_DB_VERSION,))
        await db.commit()
        logger.info(f"БД создана (версия {_DB_VERSION})")
    elif current_version < _DB_VERSION:
        await _migrate(db, current_version)
        await db.execute("UPDATE db_version SET version = ?", (_DB_VERSION,))
        await db.commit()
        logger.info(f"БД обновлена до версии {_DB_VERSION}")
    else:
        logger.info(f"БД актуальна (версия {current_version})")


async def _create_tables(db):
    # создать все таблицы
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            voice_enabled INTEGER DEFAULT 0,
            current_scenario TEXT DEFAULT 'university',
            language TEXT DEFAULT 'ru',
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
        CREATE TABLE IF NOT EXISTS exam_sessions (
            exam_session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scenario TEXT NOT NULL,
            mode TEXT NOT NULL,
            total_cases INTEGER DEFAULT 0,
            completed_cases INTEGER DEFAULT 0,
            current_case INTEGER DEFAULT 0,
            cases_data TEXT,
            answers_data TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_exam_sessions_user ON exam_sessions(user_id)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS dialog_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question TEXT,
            answer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_dialog_user ON dialog_history(user_id)")
    await db.commit()

    await db.execute("""
        CREATE TABLE IF NOT EXISTS case_answers (
            answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            case_id TEXT NOT NULL,
            scenario TEXT NOT NULL,
            question TEXT,
            user_answer TEXT,
            score INTEGER,
            feedback TEXT,
            sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    await db.commit()


async def _migrate(db, from_version):
    # выполнить миграции до целевой версии
    if from_version < 2:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_answers_user ON case_answers(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_answers_session ON case_answers(session_id)")
        logger.info("Миграция v1→v2: добавлены индексы")

    if from_version < 4:
        try:
            await db.execute("CREATE TABLE IF NOT EXISTS dialog_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, question TEXT, answer TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_dialog_user ON dialog_history(user_id)")
            logger.info("Миграция v3→v4: добавлена таблица dialog_history")
        except Exception as e:
            logger.warning(f"Миграция dialog_history не удалась: {e}")

    if from_version < 5:
        # v5: в ответах кейсов храним текст задания и источники — PDF становится диалогом
        for column, coltype in (("question", "TEXT"), ("sources", "TEXT")):
            try:
                await db.execute(f"ALTER TABLE case_answers ADD COLUMN {column} {coltype}")
                logger.info(f"Миграция v4→v5: добавлено поле {column}")
            except Exception:
                pass

    if from_version < 3:
        try:
            await db.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
            logger.info("Миграция v2→v3: добавлено поле language")
        except Exception:
            pass


# основные операции (CRUD)


async def get_or_create_user(user_id, username=None, first_name=None, last_name=None):
    # получить или создать пользователя
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
        "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
        (user_id, username, first_name, last_name),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    return dict(row)


async def update_user(uid, **kwargs):
    # обновить данные пользователя
    allowed_fields = {"username", "first_name", "last_name", "voice_enabled", "current_scenario", "language"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return

    db = await _get_db()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [uid]
    await db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
    await db.commit()


async def reset_progress(uid):
    # сбросить прогресс пользователя
    db = await _get_db()
    await db.execute("DELETE FROM case_answers WHERE user_id = ?", (uid,))
    await db.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
    await db.execute(
        "UPDATE users SET current_scenario = 'university' WHERE user_id = ?",
        (uid,),
    )
    await db.commit()
    logger.info(f"Прогресс сброшен для user={uid}")


async def create_session(uid, scenario, mode, cases_total=0):
    # создать новую сессию
    db = await _get_db()
    cursor = await db.execute(
        "INSERT INTO sessions (user_id, scenario, mode, cases_total) VALUES (?, ?, ?, ?)",
        (uid, scenario, mode, cases_total),
    )
    await db.commit()
    return cursor.lastrowid


async def create_exam_session(uid, scenario, mode, total_cases, cases_data):
    # создать экзаменационную сессию в БД
    db = await _get_db()
    cursor = await db.execute(
        """INSERT INTO exam_sessions
        (user_id, scenario, mode, total_cases, cases_data, status)
        VALUES (?, ?, ?, ?, ?, 'active')""",
        (uid, scenario, mode, total_cases, cases_data),
    )
    await db.commit()
    return cursor.lastrowid


async def update_exam_session(exam_session_id, **kwargs):
    # обновить поля экзаменационной сессии
    if not kwargs:
        return
    db = await _get_db()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    kwargs["updated_at"] = "CURRENT_TIMESTAMP"
    values = list(kwargs.values()) + [exam_session_id]
    await db.execute(
        f"UPDATE exam_sessions SET {set_clause} WHERE exam_session_id = ?",
        values,
    )
    await db.commit()


async def get_exam_session(exam_session_id):
    # получить экзаменационную сессию по ID
    db = await _get_db()
    cursor = await db.execute(
        "SELECT * FROM exam_sessions WHERE exam_session_id = ?",
        (exam_session_id,),
    )
    return await cursor.fetchone()


async def get_active_exam_session(uid):
    # получить активную экзаменационную сессию пользователя
    db = await _get_db()
    cursor = await db.execute(
        "SELECT * FROM exam_sessions WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
        (uid,),
    )
    return await cursor.fetchone()


async def end_exam_session(exam_session_id, completed_cases, avg_score):
    # завершить экзаменационную сессию
    db = await _get_db()
    await db.execute(
        """UPDATE exam_sessions
        SET status = 'completed', completed_cases = ?, avg_score = ?, ended_at = CURRENT_TIMESTAMP
        WHERE exam_session_id = ?""",
        (completed_cases, avg_score, exam_session_id),
    )
    await db.commit()


async def abandon_exam_session(exam_session_id):
    # бросить экзамен (статус abandoned)
    db = await _get_db()
    await db.execute(
        "UPDATE exam_sessions SET status = 'abandoned', ended_at = CURRENT_TIMESTAMP WHERE exam_session_id = ?",
        (exam_session_id,),
    )
    await db.commit()


async def end_session(sid, cases_completed, avg_score):
    # завершить сессию
    db = await _get_db()
    await db.execute(
        "UPDATE sessions SET cases_completed = ?, avg_score = ?, ended_at = CURRENT_TIMESTAMP WHERE session_id = ?",
        (cases_completed, avg_score, sid),
    )
    await db.commit()


async def save_case_answer(session_id, user_id, case_id, scenario, user_answer, score, feedback, question=None, sources=None):
    # сохранить ответ на кейс (question и sources — чтобы PDF был диалогом)
    db = await _get_db()
    if isinstance(sources, (list, tuple)):
        import json as _json
        sources = _json.dumps(list(sources), ensure_ascii=False) if sources else None
    await db.execute(
        """INSERT INTO case_answers
        (session_id, user_id, case_id, scenario, question, user_answer, score, feedback, sources)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, user_id, case_id, scenario, question, user_answer, score, feedback, sources),
    )
    await db.commit()


async def get_user_stats(uid):
    # получить статистику пользователя
    db = await _get_db()

    cursor = await db.execute(
        """SELECT COUNT(*) as total_sessions, AVG(avg_score) as avg_score
        FROM sessions WHERE user_id = ? AND cases_completed > 0""",
        (uid,),
    )
    row = await cursor.fetchone()

    cursor = await db.execute(
        """SELECT scenario, COUNT(*) as sessions, AVG(avg_score) as avg_score
        FROM sessions WHERE user_id = ? AND cases_completed > 0
        GROUP BY scenario""",
        (uid,),
    )
    scenarios = await cursor.fetchall()

    return {
        "total_sessions": row["total_sessions"] if row else 0,
        "avg_score": round(row["avg_score"] or 0, 1) if row else 0,
        "scenarios": {s["scenario"]: {"sessions": s["sessions"], "avg_score": round(s["avg_score"] or 0, 1)} for s in scenarios},
    }


async def get_all_users(limit=9999):
    # получить список пользователей
    db = await _get_db()
    if limit >= 9999:
        cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
    else:
        cursor = await db.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_case_answers(uid, scenario=None, only_completed: bool = False):
    # ответы на кейсы. only_completed — брать только из закрытых сессий,
    # иначе в отчёт попадут брошенные экзамены
    db = await _get_db()

    conditions = ["ca.user_id = ?"]
    params: list = [uid]

    if scenario:
        conditions.append("ca.scenario = ?")
        params.append(scenario)
    if only_completed:
        conditions.append("s.cases_completed > 0")

    # без текста ответа строка бессмысленна — в отчёт не идёт
    conditions.append("TRIM(COALESCE(ca.user_answer, '')) != ''")

    sql = (
        "SELECT ca.*, s.mode, s.cases_total, s.cases_completed "
        "FROM case_answers ca "
        "JOIN sessions s ON ca.session_id = s.session_id "
        f"WHERE {' AND '.join(conditions)} "
        "ORDER BY ca.created_at"
    )

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_global_stats():
    # глобальная статистика
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


async def save_dialog(user_id: int, question: str, answer: str):
    # сохранить диалог для памяти (ограничено до 4 последних сообщений)
    db = await _get_db()
    await db.execute(
        "INSERT INTO dialog_history (user_id, question, answer) VALUES (?, ?, ?)",
        (user_id, question, answer),
    )
    await db.execute(
        "DELETE FROM dialog_history WHERE user_id = ? AND id NOT IN (SELECT id FROM dialog_history WHERE user_id = ? ORDER BY id DESC LIMIT 4)",
        (user_id, user_id),
    )
    await db.commit()


async def clear_dialog_history(user_id: int):
    # удалить сохранённый диалог (сессия прервана)
    db = await _get_db()
    await db.execute("DELETE FROM dialog_history WHERE user_id = ?", (user_id,))
    await db.commit()


async def get_dialog(user_id: int, limit: int = 4) -> list:
    # загрузить диалог из базы
    db = await _get_db()
    cursor = await db.execute(
        "SELECT question, answer FROM dialog_history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    rows = await cursor.fetchall()
    result = []
    for r in rows:
        result.append({"question": r["question"], "answer": r["answer"]})
    result.reverse()
    return result
