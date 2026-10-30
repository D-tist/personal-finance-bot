
import asyncio

from aiogram import Bot, Dispatcher

from app.config import BOT_TOKEN
from app.database.database import engine
from app.handlers.start import router as start_router
from app.handlers.transactions import router as transactions_router
from app.handlers.categories import router as categories_router
from app.handlers.reports import router as reports_router
from app.handlers.savings import router as savings_router
from app.handlers.budgets import router as budgets_router
from app.handlers.export import router as export_router

async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dispatcher = Dispatcher()

    dispatcher.include_router(start_router)
    dispatcher.include_router(transactions_router)
    dispatcher.include_router(categories_router)
    dispatcher.include_router(savings_router)
    dispatcher.include_router(reports_router)
    dispatcher.include_router(budgets_router)
    dispatcher.include_router(export_router)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
