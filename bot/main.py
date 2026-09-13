"""Главный модуль бота — инициализация и запуск polling + health endpoint для Render."""

import asyncio
import logging
import signal
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config, validate_config
from bot.database.db import init_db

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("gigachat").setLevel(logging.WARNING)

# глобальные объекты для shutdown
_bot: Bot = None
_dp: Dispatcher = None
_shutdown_event = asyncio.Event()
_web_runner = None


async def health_handler(request):
    """Health endpoint для Render / внешних пингеров"""
    return web.json_response({"status": "ok"})


async def start_web_server():
    """Запуск HTTP-сервера для health checks"""
    global _web_runner
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)
    _web_runner = web.AppRunner(app)
    await _web_runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(_web_runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health-сервер запущен на порту {port}")


async def on_startup():
    """Действия при запуске бота"""
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова")


async def on_shutdown():
    """Действия при остановке бота"""
    global _bot, _dp, _web_runner

    logger.info("Завершение работы...")

    # Закрываем health-сервер
    if _web_runner:
        try:
            await _web_runner.cleanup()
        except Exception:
            pass

    # Закрываем GigaChat клиент
    try:
        import bot.core.ai_engine as ai_mod
        if ai_mod._client:
            await ai_mod._client.__aexit__(None, None, None)
            logger.info("GigaChat клиент закрыт")
    except Exception as e:
        logger.warning(f"Ошибка при закрытии GigaChat: {e}")

    # Закрываем БД
    try:
        from bot.database.db import close_db
        await close_db()
    except Exception as e:
        logger.warning(f"Ошибка при закрытии БД: {e}")

    # Останавливаем polling
    if _dp:
        try:
            await _dp.stop_polling()
        except Exception:
            pass

    # Закрываем сессию бота
    if _bot:
        try:
            await _bot.session.close()
        except Exception as e:
            logger.warning(f"Ошибка при закрытии сессии: {e}")

    logger.info("Бот остановлен")
    _shutdown_event.set()


async def on_error(event: ErrorEvent):
    """Глобальный обработчик ошибок"""
    logger.error(f"Ошибка в обработчике: {event.update}", exc_info=event.exception)
    # Отправляем пользователю сообщение об ошибке
    try:
        update = event.update
        if update.message:
            await update.message.answer("❌ Произошла ошибка. Попробуй позже или начни заново через /start")
        elif update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
    except Exception:
        pass


def _setup_signals(loop):
    """Настройка обработчиков сигналов для graceful shutdown"""
    if sys.platform == "win32":
        # На Windows add_signal_handler не поддерживается — ловим через thread
        import threading
        def _signal_handler():
            loop.call_soon_threadsafe(_shutdown_event.set)
        signal.signal(signal.SIGINT, lambda s, f: threading.Thread(target=_signal_handler).start())
    else:
        # На Linux/Mac поддерживаем оба сигнала
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown_event.set()))


async def main():
    global _bot, _dp

    logger.info("Запуск бота...")

    validate_config()
    await on_startup()
    await start_web_server()

    _bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    _dp = Dispatcher(storage=storage)

    _dp.error.register(on_error)

    # Ленивая регистрация роутеров — импортируем только при старте
    from bot.handlers import start, info, examiner, voice, pdf_export, admin
    _dp.include_router(admin.router)
    _dp.include_router(start.router)
    _dp.include_router(info.router)
    _dp.include_router(examiner.router)
    _dp.include_router(voice.router)
    _dp.include_router(pdf_export.router)

    logger.info("Регистрация роутеров завершена, запускаю polling...")
    try:
        me = await _bot.get_me()
        logger.info(f"Бот подключён: @{me.username} (id={me.id})")
    except Exception as e:
        logger.error(f"Не удалось подключиться к Telegram: {e}")
        return

    # Настройка сигналов
    loop = asyncio.get_running_loop()
    _setup_signals(loop)

    # Запускаем polling и ждём сигнала на остановку
    polling_task = asyncio.create_task(_dp.start_polling(_bot))

    # Ждём пока не придёт сигнал
    await _shutdown_event.wait()

    # Даём polling завершиться
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

    await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
