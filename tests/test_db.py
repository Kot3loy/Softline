import pytest
from bot.database.db import (
    get_or_create_user, update_user, create_session,
    end_session, save_case_answer, get_user_stats,
    get_all_users, get_case_answers, get_global_stats,
)


@pytest.mark.asyncio
async def test_get_or_create_user_new(test_db):
    """Создание нового пользователя"""
    user = await get_or_create_user(111111, username="new_user", first_name="New")
    assert user["user_id"] == 111111
    assert user["username"] == "new_user"
    assert user["first_name"] == "New"
    assert user["voice_enabled"] == 0
    assert user["current_scenario"] == "university"


@pytest.mark.asyncio
async def test_get_or_create_user_existing(test_db):
    """Получение существующего пользователя"""
    await get_or_create_user(222222, username="first")
    user = await get_or_create_user(222222, username="updated")
    assert user["user_id"] == 222222
    # Username не должен обновляться при повторном вызове
    assert user["username"] == "first"


@pytest.mark.asyncio
async def test_update_user(test_db):
    """Обновление данных пользователя"""
    await get_or_create_user(333333)
    await update_user(333333, voice_enabled=1, current_scenario="job")
    user = await get_or_create_user(333333)
    assert user["voice_enabled"] == 1
    assert user["current_scenario"] == "job"


@pytest.mark.asyncio
async def test_update_user_invalid_field(test_db):
    """Обновление недопустимого поля игнорируется"""
    await get_or_create_user(444444)
    await update_user(444444, hacker=True, current_scenario="job")
    user = await get_or_create_user(444444)
    assert user["current_scenario"] == "job"
    assert not hasattr(user, "hacker")


@pytest.mark.asyncio
async def test_create_session(test_db):
    """Создание сессии"""
    await get_or_create_user(555555)
    session_id = await create_session(555555, "university", "exam", cases_total=5)
    assert session_id is not None
    assert session_id > 0


@pytest.mark.asyncio
async def test_end_session(test_db):
    """Завершение сессии"""
    await get_or_create_user(666666)
    session_id = await create_session(666666, "job", "exam", cases_total=3)
    await end_session(session_id, cases_completed=3, avg_score=7.5)

    stats = await get_user_stats(666666)
    assert stats["total_sessions"] == 1
    assert stats["avg_score"] == 7.5


@pytest.mark.asyncio
async def test_save_case_answer(test_db):
    """Сохранение ответа на кейс"""
    await get_or_create_user(777777)
    session_id = await create_session(777777, "university", "exam")
    await save_case_answer(
        session_id, 777777, "case_1", "university",
        "Мой ответ", 8, "Хороший ответ!"
    )

    answers = await get_case_answers(777777, "university")
    assert len(answers) == 1
    assert answers[0]["score"] == 8
    assert answers[0]["feedback"] == "Хороший ответ!"


@pytest.mark.asyncio
async def test_get_user_stats_empty(test_db):
    """Статистика пустого пользователя"""
    await get_or_create_user(888888)
    stats = await get_user_stats(888888)
    assert stats["total_sessions"] == 0
    assert stats["avg_score"] == 0
    assert stats["scenarios"] == {}


@pytest.mark.asyncio
async def test_get_user_stats_with_sessions(test_db):
    """Статистика с несколькими сессиями"""
    await get_or_create_user(999999)

    s1 = await create_session(999999, "university", "exam")
    await end_session(s1, cases_completed=3, avg_score=8.0)

    s2 = await create_session(999999, "job", "exam")
    await end_session(s2, cases_completed=2, avg_score=6.0)

    stats = await get_user_stats(999999)
    assert stats["total_sessions"] == 2
    assert "university" in stats["scenarios"]
    assert "job" in stats["scenarios"]


@pytest.mark.asyncio
async def test_get_all_users(test_db):
    """Получение списка пользователей"""
    await get_or_create_user(100001, username="user1")
    await get_or_create_user(100002, username="user2")

    users = await get_all_users(limit=10)
    user_ids = [u["user_id"] for u in users]
    assert 100001 in user_ids
    assert 100002 in user_ids


@pytest.mark.asyncio
async def test_get_global_stats(test_db):
    """Глобальная статистика"""
    await get_or_create_user(200001)
    s1 = await create_session(200001, "university", "exam")
    await end_session(s1, cases_completed=3, avg_score=7.0)

    stats = await get_global_stats()
    assert stats["total_users"] >= 1
    assert stats["total_sessions"] >= 1
    assert stats["completed_sessions"] >= 1


@pytest.mark.asyncio
async def test_foreign_key_constraint(test_db):
    """Проверка foreign key — ответ привязан к сессии"""
    await get_or_create_user(300001)
    session_id = await create_session(300001, "adaptation", "exam")
    await save_case_answer(session_id, 300001, "case_1", "adaptation", "Ответ", 7, "Ок")

    answers = await get_case_answers(300001)
    assert len(answers) == 1
    assert answers[0]["session_id"] == session_id
