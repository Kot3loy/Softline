"""Главный модуль бота — запуск polling + health endpoint."""

import asyncio
import logging
import signal
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config, validate_config
from bot.database.db import init_db
from bot.translations import t

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
bot = None
dp = None
shutdown_event = asyncio.Event()
web_runner = None


async def health_handler(request):
    """Health endpoint"""
    return web.json_response({"status": "ok"})


async def start_web_server():
    """Запуск HTTP-сервера для health checks"""
    global web_runner
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)
    web_runner = web.AppRunner(app)
    await web_runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(web_runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health-сервер запущен на порту {port}")


async def on_startup():
    """Действия при запуске бота"""
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова")


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("Завершение работы...")

    # Закрываем health-сервер
    if web_runner:
        try:
            await web_runner.cleanup()
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
    if dp:
        try:
            await dp.stop_polling()
        except Exception:
            pass

    # Закрываем сессию бота
    if bot:
        try:
            await bot.session.close()
        except Exception as e:
            logger.warning(f"Ошибка при закрытии сессии: {e}")

    logger.info("Бот остановлен")
    shutdown_event.set()


async def on_error(event: ErrorEvent):
    """Глобальный обработчик ошибок"""
    logger.error(f"Ошибка в обработчике: {event.update}", exc_info=event.exception)
    try:
        update = event.update
        if update.message:
            user_data = None
            try:
                from bot.database.db import get_or_create_user
                user_data = await get_or_create_user(update.message.from_user.id)
            except Exception:
                pass
            lang = user_data.get("language", "ru") if user_data else "ru"
            await update.message.answer(t("error_general", lang))
        elif update.callback_query:
            await update.callback_query.answer(t("error_general_short", "ru"), show_alert=True)
    except Exception:
        pass


def setup_signals(loop):
    """Настройка обработчиков сигналов"""
    if sys.platform == "win32":
        import threading
        def signal_handler():
            loop.call_soon_threadsafe(shutdown_event.set)
        signal.signal(signal.SIGINT, lambda s, f: threading.Thread(target=signal_handler).start())
    else:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: shutdown_event.set())


async def main():
    global bot, dp

    logger.info("Запуск бота...")

    validate_config()
    await on_startup()
    await start_web_server()

    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.error.register(on_error)

    from bot.handlers import start, info, examiner, voice, pdf_export, inline
    dp.include_router(start.router)
    dp.include_router(info.router)
    dp.include_router(examiner.router)
    dp.include_router(voice.router)
    dp.include_router(pdf_export.router)
    dp.include_router(inline.router)

    logger.info("Регистрация роутеров завершена, запускаю polling...")
    try:
        me = await bot.get_me()
        logger.info(f"Бот подключён: @{me.username} (id={me.id})")

        await bot.set_my_commands([
            BotCommand(command="start", description="Начать работу с ботом"),
            BotCommand(command="help", description="Помощь и информация"),
            BotCommand(command="export", description="Скачать PDF-отчёт"),
        ])
        logger.info("Команды бота установлены")
    except Exception as e:
        logger.error(f"Не удалось подключиться к Telegram: {e}")
        return

    loop = asyncio.get_running_loop()
    setup_signals(loop)

    polling_task = asyncio.create_task(dp.start_polling(bot))
    await shutdown_event.wait()

    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

    await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
