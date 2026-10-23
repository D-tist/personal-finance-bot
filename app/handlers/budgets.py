
from datetime import datetime
from decimal import Decimal

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import async_session
from app.database.models import (
    Budget,
    Category,
    CategoryType,
    OperationType,
    Transaction,
    User,
)

router = Router()

async def get_user_id(session: AsyncSession, telegram_id: int) -> int | None:
    return await session.scalar(
        select(User.id).where(
            User.telegram_id == telegram_id,
            User.is_active.is_(True),
        )
    )

class BudgetStates(StatesGroup):
    choosing_category = State()
    entering_amount = State()


def get_budgets_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Установить лимит")],
            [KeyboardButton(text="📋 Мои бюджеты")],
            [KeyboardButton(text="⬅️ Главное меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def get_budget_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


async def get_current_month_spending(
    session: AsyncSession,
    user_id: int,
    category_id: int,
) -> Decimal:
    now = datetime.now().astimezone()
    month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).replace(tzinfo=None)

    if now.month == 12:
        next_month = month_start.replace(
            year=month_start.year + 1, month=1
        )
    else:
        next_month = month_start.replace(month=month_start.month + 1)

    result = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.category_id == category_id,
            Transaction.operation_type == OperationType.EXPENSE.value,
            Transaction.operation_date >= month_start,
            Transaction.operation_date < next_month,
        )
    )
    return Decimal(str(result or 0))


@router.message(F.text == "💰 Бюджеты")
async def show_budgets_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()
    await message.answer(
        "💰 Управление месячными бюджетами\n\n"
        "Здесь можно установить лимит расходов для каждой категории "
        "и следить за его использованием.",
        reply_markup=get_budgets_keyboard(),
    )


@router.message(F.text == "📋 Мои бюджеты")
async def show_my_budgets(message: Message) -> None:
    async with async_session() as session:
        user_id = await get_user_id(session, message.from_user.id)

        if user_id is None:
            await message.answer("Пользователь не найден. Нажми /start.")
            return
        categories_result = await session.execute(
            select(Budget, Category)
            .join(Category, Budget.category_id == Category.id)
            .where(
                Budget.user_id == user_id,
                Category.user_id == user_id,
                Category.category_type == CategoryType.EXPENSE.value,
                Category.is_active.is_(True),
            )
            .order_by(Category.name)
        )
        budgets = categories_result.all()

        if not budgets:
            await message.answer(
                "У тебя пока нет установленных бюджетов.",
                reply_markup=get_budgets_keyboard(),
            )
            return

        lines = ["📋 Твои бюджеты на текущий месяц:\n"]

        for budget, category in budgets:
            spent = await get_current_month_spending(
                session,
                user_id,
                category.id,
            )

            remaining = budget.amount - spent
            percent = (
                spent / budget.amount * Decimal("100")
                if budget.amount > 0
                else Decimal("0")
            )

            if percent >= 100:
                status = "🔴 Лимит превышен или исчерпан"
            elif percent >= 80:
                status = "🟠 Лимит почти исчерпан"
            else:
                status = "🟢 В пределах лимита"

            lines.append(
                f"• {category.name}\n"
                f"  Лимит: {budget.amount:.2f}\n"
                f"  Потрачено: {spent:.2f} ({percent:.1f}%)\n"
                f"  Остаток: {remaining:.2f}\n"
                f"  {status}\n"
            )

    await message.answer(
        "\n".join(lines),
        reply_markup=get_budgets_keyboard(),
    )

async def get_budget_status(
    session: AsyncSession,
    user_id: int,
    category_id: int,
) -> tuple[Decimal, Decimal, Decimal] | None:
    budget = await session.scalar(
        select(Budget).where(
            Budget.user_id == user_id,
            Budget.category_id == category_id,
        )
    )

    if budget is None:
        return None

    spent = await get_current_month_spending(
        session,
        user_id,
        category_id,
    )

    percent = (
        spent / budget.amount * Decimal("100")
        if budget.amount > 0
        else Decimal("0")
    )

    return budget.amount, spent, percent

@router.message(F.text == "➕ Установить лимит")
async def choose_budget_category(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    async with async_session() as session:
        user_id = await get_user_id(session, message.from_user.id)

        if user_id is None:
            await message.answer("Пользователь не найден. Нажми /start.")
            return

        result = await session.scalars(
            select(Category)
            .where(
                Category.user_id == user_id,
                Category.category_type == CategoryType.EXPENSE.value,
                Category.is_active.is_(True),
            )
            .order_by(Category.name)
        )
        categories = list(result.all())

    if not categories:
        await message.answer(
            "Сначала создай хотя бы одну активную категорию расходов.",
            reply_markup=get_budgets_keyboard(),
        )
        return

    await state.set_state(BudgetStates.choosing_category)
    await state.update_data(
        categories={
            str(category.id): category.name for category in categories
        }
    )

    keyboard = [
        [KeyboardButton(text=category.name)]
        for category in categories
    ]
    keyboard.append([KeyboardButton(text="❌ Отмена")])

    await message.answer(
        "Выбери категорию расходов, для которой установить месячный лимит:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        ),
    )


@router.message(BudgetStates.choosing_category)
async def budget_category_selected(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Настройка бюджета отменена.",
            reply_markup=get_budgets_keyboard(),
        )
        return

    data = await state.get_data()
    categories = data.get("categories", {})
    category_id = next(
        (
            int(category_id)
            for category_id, name in categories.items()
            if name == message.text
        ),
        None,
    )

    if category_id is None:
        await message.answer(
            "Выбери категорию кнопкой из списка."
        )
        return

    async with async_session() as session:
        user_id = await get_user_id(session, message.from_user.id)

        if user_id is None:
            await state.clear()
            await message.answer("Пользователь не найден. Нажми /start.")
            return

        category = await session.scalar(
            select(Category).where(
                Category.id == category_id,
                Category.user_id == user_id,
                Category.category_type == CategoryType.EXPENSE.value,
                Category.is_active.is_(True),
            )
        )

    if category is None:
        await state.clear()
        await message.answer(
            "Категория не найдена или недоступна.",
            reply_markup=get_budgets_keyboard(),
        )
        return

    await state.update_data(category_id=category_id)
    await state.set_state(BudgetStates.entering_amount)
    await message.answer(
        f"Введи месячный лимит для категории «{category.name}».\n"
        "Например: 15000 или 15000.50",
        reply_markup=get_budget_cancel_keyboard(),
    )


@router.message(BudgetStates.entering_amount)
async def save_budget_amount(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(
            "Настройка бюджета отменена.",
            reply_markup=get_budgets_keyboard(),
        )
        return

    raw_amount = (message.text or "").strip().replace(",", ".")

    try:
        amount = Decimal(raw_amount)
    except Exception:
        await message.answer("Введи сумму числом, например 15000 или 15000.50.")
        return

    if not amount.is_finite() or amount <= 0:
        await message.answer("Лимит должен быть положительным числом.")
        return

    if amount.as_tuple().exponent < -2:
        await message.answer("Допускается не более двух знаков после запятой.")
        return

    if amount >= Decimal("1000000000000"):
        await message.answer("Сумма слишком большая. Введи меньший лимит.")
        return

    data = await state.get_data()
    category_id = data.get("category_id")

    async with async_session() as session:
        user_id = await get_user_id(session, message.from_user.id)

        if user_id is None:
            await state.clear()
            await message.answer("Пользователь не найден. Нажми /start.")
            return

        category = await session.scalar(
            select(Category).where(
                Category.id == category_id,
                Category.user_id == user_id,
                Category.category_type == CategoryType.EXPENSE.value,
                Category.is_active.is_(True),
            )
        )

        if category is None:
            await state.clear()
            await message.answer(
                "Категория недоступна. Начни настройку заново.",
                reply_markup=get_budgets_keyboard(),
            )
            return

        budget = await session.scalar(
            select(Budget).where(
                Budget.user_id == user_id,
                Budget.category_id == category_id,
            )
        )

        if budget is None:
            budget = Budget(
                user_id=user_id,
                category_id=category_id,
                amount=amount,
            )
            session.add(budget)
        else:
            budget.amount = amount

        await session.commit()
        category_name = category.name

    await state.clear()
    await message.answer(
        f"✅ Месячный бюджет сохранён.\n\n"
        f"Категория: {category_name}\n"
        f"Лимит: {amount:.2f}\n\n"
        "Бюджет будет использоваться каждый месяц.",
        reply_markup=get_budgets_keyboard(),
    )


@router.message(F.text == "⬅️ Главное меню")
async def return_to_main_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    from app.keyboards.main import get_main_keyboard

    await message.answer(
        "Главное меню.",
        reply_markup=get_main_keyboard(),
    )
