from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy import select

from app.config import ADMIN_TELEGRAM_ID
from app.database.database import async_session
from app.database.models import User


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler,
        event: TelegramObject,
        data: dict,
    ):
        if not isinstance(event, Update):
            return None

        telegram_user = event.event_from_user

        # Обновления без пользователя не пропускаем.
        if telegram_user is None:
            return None

        # Администратор определяется только по Telegram ID.
        # Ему не требуется проверка базы данных.
        if telegram_user.id == ADMIN_TELEGRAM_ID:
            return await handler(event, data)

        # Проверяем наличие активной записи в Whitelist.
        async with async_session() as session:
            result = await session.execute(
                select(User.id).where(
                    User.telegram_id == telegram_user.id,
                    User.is_active.is_(True),
                )
            )
            user_id = result.scalar_one_or_none()

        if user_id is None:
            if event.message:
                await event.message.answer(
                    "Доступ к боту закрыт. "
                    "Обратитесь к администратору."
                )
            elif event.callback_query:
                await event.callback_query.answer(
                    "Доступ запрещён.",
                    show_alert=True,
                )

            return None

        return await handler(event, data)