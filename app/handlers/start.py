from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import ADMIN_TELEGRAM_ID
from app.database.database import async_session
from app.database.models import User, UserSettings, UserRole
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

        # Администратор всегда имеет доступ.
        if telegram_user.id == ADMIN_TELEGRAM_ID:
            if user is None:
                user = User(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                    role=UserRole.ADMIN.value,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
            else:
                user.role = UserRole.ADMIN.value
                user.is_active = True

        # Остальные должны быть заранее добавлены администратором.
        elif user is None or not user.is_active:
            await message.answer(
                "Доступ к боту закрыт. Обратитесь к администратору."
            )
            return

        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.last_name = telegram_user.last_name

        settings_insert = insert(UserSettings).values(
            user_id=user.id,
            currency="RUB",
        )

        settings_upsert = settings_insert.on_conflict_do_nothing(
            index_elements=[UserSettings.user_id]
        )

        await session.execute(settings_upsert)
        await session.commit()

    await message.answer(
        f"Привет, {telegram_user.first_name}!\n\n"
        "Твои данные сохранены.\n\n"
        "Выбери действие в главном меню:",
        reply_markup=get_main_keyboard(),
    )