from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import ADMIN_TELEGRAM_ID
from app.database.database import async_session
from app.database.models import User, UserRole, UserSettings


router = Router()


def is_admin(message: Message) -> bool:
    return (
        message.from_user is not None
        and message.from_user.id == ADMIN_TELEGRAM_ID
    )


@router.message(Command("whitelist"))
async def whitelist_list(message: Message) -> None:
    if not is_admin(message):
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.id)
        )
        users = result.scalars().all()

    if not users:
        await message.answer("Список пользователей пуст.")
        return

    lines = ["**Пользователи бота:**", ""]

    for user in users:
        role = "Администратор" if user.role == UserRole.ADMIN.value else "Пользователь"
        status = "Активен" if user.is_active else "Заблокирован"

        lines.append(
            f"ID: `{user.telegram_id}`\n"
            f"Роль: {role}\n"
            f"Статус: {status}\n"
        )

    await message.answer(
        "\n".join(lines),
        parse_mode="Markdown",
    )


@router.message(Command("whitelist_add"))
async def whitelist_add(message: Message) -> None:
    if not is_admin(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(
            "Использование:\n"
            "/whitelist_add 123456789"
        )
        return

    telegram_id = int(parts[1])

    if telegram_id == ADMIN_TELEGRAM_ID:
        await message.answer("Администратор уже имеет постоянный доступ.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                role=UserRole.USER.value,
                is_active=True,
            )
            session.add(user)
        else:
            user.is_active = True

        await session.flush()

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
        f"Пользователь {telegram_id} добавлен в Whitelist."
    )


@router.message(Command("whitelist_remove"))
async def whitelist_remove(message: Message) -> None:
    if not is_admin(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(
            "Использование:\n"
            "/whitelist_remove 123456789"
        )
        return

    telegram_id = int(parts[1])

    if telegram_id == ADMIN_TELEGRAM_ID:
        await message.answer("Нельзя заблокировать администратора.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            await message.answer("Пользователь не найден.")
            return

        user.is_active = False
        await session.commit()

    await message.answer(
        f"Доступ пользователя {telegram_id} закрыт."
    )