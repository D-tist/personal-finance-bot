
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select

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
        result = await session.execute(
            select(User).where(
                User.telegram_id == telegram_user.id
            )
        )
        user = result.scalar_one_or_none()

        is_new_user = user is None

        if is_new_user:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
            )
            session.add(user)
            await session.flush()

        else:
            user.username = telegram_user.username
            user.first_name = telegram_user.first_name
            user.last_name = telegram_user.last_name

        settings_result = await session.execute(
            select(UserSettings).where(
                UserSettings.user_id == user.id
            )
        )
        settings = settings_result.scalar_one_or_none()

        if settings is None:
            session.add(
                UserSettings(
                    user_id=user.id,
                    currency="RUB",
                )
            )

        await session.commit()

    if is_new_user:
        greeting = (
            f"Привет, {telegram_user.first_name}!\n\n"
            "Ты зарегистрирован в финансовом боте."
        )
    else:
        greeting = (
            f"С возвращением, {telegram_user.first_name}!\n\n"
            "Твои данные сохранены."
        )

    await message.answer(
        f"{greeting}\n\n"
        "Выбери действие в главном меню:",
        reply_markup=get_main_keyboard(),
    )
