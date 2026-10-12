import asyncio
from bot.database.db import init_db, save_dialog, get_dialog

async def t():
    await init_db()
    await save_dialog(999, "test_q", "test_a")
    res = await get_dialog(999)
    print("DB PERSIST OK:", res)

asyncio.run(t())
