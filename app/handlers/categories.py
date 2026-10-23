
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from app.database.database import async_session
from app.database.models import Category, User
from app.keyboards.main import (
    get_cancel_keyboard,
    get_categories_keyboard,
    get_category_type_keyboard,
    get_main_keyboard,
)
from app.states.categories import CategoryStates

router = Router()


CATEGORY_TYPES = {
    "💰 Доход": "INCOME",
    "🛒 Расход": "EXPENSE",
    "🏦 Накопления": "SAVING",
}

CATEGORY_TITLES = {
    "INCOME": "доходов",
    "EXPENSE": "расходов",
    "SAVING": "накоплений",
}


@router.message(F.text == "📁 Категории")
async def show_categories_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "📁 Управление категориями.\nВыберите действие:",
        reply_markup=get_categories_keyboard(),
    )


@router.message(F.text == "⬅️ Главное меню")
async def return_to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Главное меню.",
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "❌ Отмена")
async def cancel_category_action(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=get_categories_keyboard(),
    )


@router.message(F.text == "➕ Добавить категорию")
async def start_add_category(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CategoryStates.waiting_for_type)
    await message.answer(
        "Выберите тип новой категории:",
        reply_markup=get_category_type_keyboard(),
    )


@router.message(CategoryStates.waiting_for_type, F.text.in_(CATEGORY_TYPES.keys()))
async def process_category_type(message: Message, state: FSMContext) -> None:
    category_type = CATEGORY_TYPES[message.text]
    await state.update_data(category_type=category_type)
    await state.set_state(CategoryStates.waiting_for_name)
    await message.answer(
        "Введите название категории (до 255 символов):",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(CategoryStates.waiting_for_type)
async def invalid_category_type(message: Message) -> None:
    await message.answer(
        "Пожалуйста, выберите тип с помощью кнопок ниже.",
        reply_markup=get_category_type_keyboard(),
    )


@router.message(CategoryStates.waiting_for_name)
async def process_category_name(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text:
        await message.answer("Название должно быть текстом. Попробуйте ещё раз.")
        return

    name = message.text.strip()

    if not name:
        await message.answer("Название не должно быть пустым. Введите его ещё раз.")
        return

    if len(name) > 255:
        await message.answer(
            "Название слишком длинное. Максимум 255 символов. Попробуйте ещё раз."
        )
        return

    data = await state.get_data()
    category_type = data.get("category_type")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            await state.clear()
            await message.answer(
                "Не удалось найти ваш профиль. Отправьте /start."
            )
            return

        duplicate_result = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.category_type == category_type,
                Category.name.ilike(name),
                Category.is_active.is_(True),
            )
        )
        existing_category = duplicate_result.scalar_one_or_none()

        if existing_category is not None:
            await message.answer(
                "Такая активная категория уже существует. "
                "Введите другое название:",
                reply_markup=get_cancel_keyboard(),
            )
            return

        category = Category(
            user_id=user.id,
            name=name,
            category_type=category_type,
            is_active=True,
        )
        session.add(category)
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Категория «{name}» добавлена в раздел "
        f"{CATEGORY_TITLES[category_type]}.",
        reply_markup=get_categories_keyboard(),
    )


async def list_categories(
    message: Message,
    category_type: str,
) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            await message.answer("Отправьте /start, чтобы создать профиль.")
            return

        result = await session.execute(
            select(Category)
            .where(
                Category.user_id == user.id,
                Category.category_type == category_type,
                Category.is_active.is_(True),
            )
            .order_by(Category.name)
        )
        categories = result.scalars().all()

    title = CATEGORY_TITLES[category_type].capitalize()

    if not categories:
        text = f"В категории {title.lower()} пока нет записей."
    else:
        lines = [f"• {category.name}" for category in categories]
        text = f"📁 Категории {title.lower()}:\n" + "\n".join(lines)

    await message.answer(text, reply_markup=get_categories_keyboard())


@router.message(F.text == "💰 Категории доходов")
async def list_income_categories(message: Message) -> None:
    await list_categories(message, "INCOME")


@router.message(F.text == "🛒 Категории расходов")
async def list_expense_categories(message: Message) -> None:
    await list_categories(message, "EXPENSE")


@router.message(F.text == "🏦 Категории накоплений")
async def list_saving_categories(message: Message) -> None:
    await list_categories(message, "SAVING")
