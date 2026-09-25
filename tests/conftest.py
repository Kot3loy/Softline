import pytest
import aiosqlite
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def project_root():
    return Path(__file__).parent.parent


@pytest.fixture
def data_dir(project_root):
    return project_root / "data"


@pytest.fixture
def config():
    from bot.config import config
    return config


@pytest.fixture
async def test_db():
    """In-memory SQLite database for testing — isolate from production DB"""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")

    # Patch _get_db to return our test db
    import bot.database.db as db_module
    original_get_db = db_module._get_db
    original_db = db_module._db

    async def mock_get_db():
        return db

    db_module._db = db
    db_module._get_db = mock_get_db

    # Create tables
    await db.execute("""
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER PRIMARY KEY
        )
    """)
    await db.execute("INSERT INTO db_version (version) VALUES (2)")

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

    yield db

    # Cleanup — восстанавливаем оригинальное состояние
    try:
        await db.close()
    except Exception:
        pass
    db_module._db = original_db
    db_module._get_db = original_get_db


@pytest.fixture(autouse=True)
def clear_last_msg():
    """Сбросить кэш последнего сообщения между тестами"""
    import bot.handlers.start as start_mod
    start_mod._last_msg.clear()
    yield
    start_mod._last_msg.clear()


@pytest.fixture
def mock_message():
    """Mock aiogram Message"""
    msg = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 123456789
    msg.from_user.username = "test_user"
    msg.from_user.first_name = "Test"
    msg.from_user.last_name = "User"
    msg.chat = MagicMock()
    msg.chat.id = 123456789
    msg.answer = AsyncMock()
    msg.answer_voice = AsyncMock()
    msg.answer_document = AsyncMock()
    msg.bot = AsyncMock()
    msg.bot.send_chat_action = AsyncMock()
    msg.bot.get_file = AsyncMock()
    msg.bot.download_file = AsyncMock()
    msg.text = "test message"
    msg.message_id = 100
    msg.voice = MagicMock()
    msg.voice.file_id = "test_voice_id"
    return msg


@pytest.fixture
def mock_callback():
    """Mock aiogram CallbackQuery"""
    cb = AsyncMock()
    cb.from_user = MagicMock()
    cb.from_user.id = 123456789
    cb.from_user.username = "test_user"
    cb.message = AsyncMock()
    cb.message.chat = MagicMock()
    cb.message.chat.id = 123456789
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    cb.message.answer_document = AsyncMock()
    cb.bot = AsyncMock()
    cb.answer = AsyncMock()
    cb.data = "test_callback"
    return cb
