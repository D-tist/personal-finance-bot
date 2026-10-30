
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database.database import async_session
from app.database.models import User, UserSettings
from app.keyboards.main import get_main_keyboard


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    telegram_user = message.from_user

    if telegram_user is None:
        return

    async with async_session() as session:
        user_insert = insert(User).values(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        user_upsert = user_insert.on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "username": user_insert.excluded.username,
                "first_name": user_insert.excluded.first_name,
                "last_name": user_insert.excluded.last_name,
            },
        ).returning(User.id)

        result = await session.execute(user_upsert)
        user_id = result.scalar_one()

        settings_insert = insert(UserSettings).values(
            user_id=user_id,
            currency="RUB",
        )

        settings_upsert = settings_insert.on_conflict_do_nothing(
            index_elements=[UserSettings.user_id]
        )

        await session.execute(settings_upsert)
        await session.commit()

    await message.answer(
        f"\u041f\u0440\u0438\u0432\u0435\u0442, {telegram_user.first_name}!\n\n"
        "\u0422\u0432\u043e\u0438 \u0434\u0430\u043d\u043d\u044b\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u044b.\n\n"
        "\u0412\u044b\u0431\u0435\u0440\u0438 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u0432 \u0433\u043b\u0430\u0432\u043d\u043e\u043c \u043c\u0435\u043d\u044e:",
        reply_markup=get_main_keyboard(),
    )
