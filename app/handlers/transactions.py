
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import select

from app.database.database import async_session
from app.database.models import Category, OperationType, Transaction, User
from app.keyboards.main import (
    get_main_keyboard,
    get_transaction_cancel_keyboard,
    get_transaction_confirm_keyboard,
    get_transaction_description_keyboard,
    get_transaction_type_keyboard,
    get_transaction_date_keyboard,
)
from app.states.transactions import TransactionStates

from app.handlers.budgets import get_budget_status

router = Router()

OPERATION_TYPES = {
    "➕ Доход": OperationType.INCOME.value,
    "➖ Расход": OperationType.EXPENSE.value,
}

CATEGORY_TYPES = {
    OperationType.INCOME.value: "INCOME",
    OperationType.EXPENSE.value: "EXPENSE",
}

OPERATION_TITLES = {
    OperationType.INCOME.value: "Доход",
    OperationType.EXPENSE.value: "Расход",
}

MAX_AMOUNT = Decimal("999999999999.99")


async def get_user_id(session, telegram_id: int) -> int | None:
    result = await session.execute(
        select(User.id).where(
            User.telegram_id == telegram_id,
            User.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


@router.message(F.text.in_(OPERATION_TYPES.keys()))
async def start_transaction(message: Message, state: FSMContext) -> None:
    operation_type = OPERATION_TYPES[message.text]
    category_type = CATEGORY_TYPES[operation_type]

    await state.clear()

    async with async_session() as session:
        user_id = await get_user_id(session, message.from_user.id)

        if user_id is None:
            await message.answer("Профиль не найден. Отправьте /start.")
            return

        result = await session.execute(
            select(Category)
            .where(
                Category.user_id == user_id,
                Category.category_type == category_type,
                Category.is_active.is_(True),
            )
            .order_by(Category.name)
        )
        categories = result.scalars().all()

    if not categories:
        await message.answer(
            "У вас пока нет категорий для этого типа операции.\n"
            "Откройте «📁 Категории» и сначала создайте категорию.",
            reply_markup=get_main_keyboard(),
        )
        return

    category_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=category.name)]
            for category in categories
        ]
        + [[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        input_field_placeholder="Выберите категорию",
    )

    await state.update_data(
        operation_type=operation_type,
        categories={
            category.name: category.id
            for category in categories
        },
    )
    await state.set_state(TransactionStates.waiting_for_category)

    await message.answer(
        f"Вы выбрали: {OPERATION_TITLES[operation_type].lower()}.\n"
        "Теперь выберите категорию:",
        reply_markup=category_keyboard,
    )


@router.message(
    TransactionStates.waiting_for_category,
    F.text,
    F.text != "❌ Отмена",
)
async def process_category(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    categories = data.get("categories", {})
    category_id = categories.get(message.text)

    if category_id is None:
        await message.answer(
            "Выберите категорию кнопкой из списка или нажмите «❌ Отмена»."
        )
        return

    await state.update_data(category_id=category_id)
    await state.set_state(TransactionStates.waiting_for_amount)

    await message.answer(
        "Введите сумму операции, например: 1250 или 1250,50",
        reply_markup=get_transaction_cancel_keyboard(),
    )


@router.message(
    TransactionStates.waiting_for_amount,
    F.text,
    F.text != "❌ Отмена",
)
async def process_amount(message: Message, state: FSMContext) -> None:
    raw_amount = message.text.strip().replace(",", ".")

    try:
        amount = Decimal(raw_amount)
    except InvalidOperation:
        await message.answer("Введите сумму числом, например 1250,50.")
        return

    if not amount.is_finite() or amount <= 0:
        await message.answer("Сумма должна быть положительным числом.")
        return

    if amount > MAX_AMOUNT or amount.as_tuple().exponent < -2:
        await message.answer(
            "Максимум — 2 знака после запятой; "
            "сумма не должна превышать 999999999999,99."
        )
        return

    await state.update_data(amount=str(amount))
    await state.set_state(TransactionStates.waiting_for_date)

    today = datetime.now().strftime("%d.%m.%Y")

    await message.answer(
        f"Введите дату операции в формате ДД.ММ.ГГГГ.\n"
        f"Например, сегодня: {today}",
        reply_markup=get_transaction_date_keyboard(),
    )

@router.message(
    TransactionStates.waiting_for_date,
    F.text == "📅 Сегодня",
)
async def process_today(message: Message, state: FSMContext) -> None:
    operation_date = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    await state.update_data(
        operation_date=operation_date.isoformat()
    )
    await state.set_state(TransactionStates.waiting_for_description)

    await message.answer(
        "Дата операции: сегодня.\n\n"
        "Добавьте комментарий к операции или нажмите "
        "«⏭️ Пропустить комментарий».",
        reply_markup=get_transaction_description_keyboard(),
    )

@router.message(
    TransactionStates.waiting_for_date, 
    F.text,
    F.text != "❌ Отмена"
)
async def process_date(message: Message, state: FSMContext) -> None:
    try:
        operation_date = datetime.strptime(
            message.text.strip(),
            "%d.%m.%Y",
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        await message.answer(
            "Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ, "
            "например 23.10.2026."
        )
        return

    await state.update_data(operation_date=operation_date.isoformat())
    await state.set_state(TransactionStates.waiting_for_description)

    await message.answer(
        "Добавьте комментарий к операции или нажмите «⏭️ Пропустить комментарий».",
        reply_markup=get_transaction_description_keyboard(),
    )


async def show_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()

    operation_type = data["operation_type"]
    amount = Decimal(data["amount"])
    operation_date = datetime.fromisoformat(data["operation_date"])
    categories = data["categories"]

    category_name = next(
        (
            name
            for name, category_id in categories.items()
            if category_id == data["category_id"]
        ),
        "Неизвестная категория",
    )

    description = data.get("description") or "Не указан"

    await state.set_state(TransactionStates.waiting_for_confirmation)

    await message.answer(
        "Проверьте операцию:\n\n"
        f"Тип: {OPERATION_TITLES[operation_type]}\n"
        f"Категория: {category_name}\n"
        f"Сумма: {amount:.2f}\n"
        f"Дата: {operation_date.strftime('%d.%m.%Y')}\n"
        f"Комментарий: {description}\n\n"
        "Сохранить операцию?",
        reply_markup=get_transaction_confirm_keyboard(),
    )


@router.message(
    TransactionStates.waiting_for_description,
    F.text == "⏭️ Пропустить комментарий",
)
async def skip_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=None)
    await show_confirmation(message, state)


@router.message(
    TransactionStates.waiting_for_description, 
    F.text,
    F.text != "❌ Отмена",
)
async def process_description(message: Message, state: FSMContext) -> None:
    description = message.text.strip()

    if len(description) > 2000:
        await message.answer(
            "Комментарий слишком длинный. Максимум 2000 символов."
        )
        return

    await state.update_data(description=description or None)
    await show_confirmation(message, state)


@router.message(
    TransactionStates.waiting_for_confirmation,
    F.text == "✅ Сохранить",
)
async def save_transaction(message: Message, state: FSMContext) -> None:
    data = await state.get_data()

    async with async_session() as session:
        user_id = await get_user_id(session, message.from_user.id)

        if user_id is None:
            await state.clear()
            await message.answer(
                "Профиль не найден или отключён. Отправьте /start."
            )
            return

        result = await session.execute(
            select(Category).where(
                Category.id == data["category_id"],
                Category.user_id == user_id,
                Category.category_type == CATEGORY_TYPES[data["operation_type"]],
                Category.is_active.is_(True),
            )
        )
        category = result.scalar_one_or_none()

        if category is None:
            await state.clear()
            await message.answer(
                "Категория больше недоступна. Начните операцию заново.",
                reply_markup=get_main_keyboard(),
            )
            return

        transaction = Transaction(
            user_id=user_id,
            category_id=category.id,
            operation_type=data["operation_type"],
            amount=Decimal(data["amount"]),
            operation_date=datetime.fromisoformat(data["operation_date"]),
            description=data.get("description"),
        )

        session.add(transaction)
        await session.commit()

        budget_status = None

        if data["operation_type"] == OperationType.EXPENSE.value:
            budget_status = await get_budget_status(
                session,
                user_id,
                category.id,
            )

    amount = Decimal(data["amount"])
    operation_title = OPERATION_TITLES[data["operation_type"]]

    await state.clear()
    response = (
        f"✅ {operation_title} сохранён!\n"
        f"Категория: {category.name}\n"
        f"Сумма: {amount:.2f}\n"
        f"Дата: {datetime.fromisoformat(data['operation_date']).strftime('%d.%m.%Y')}"
    )

    if budget_status is not None:
        budget_amount, spent, percent = budget_status
        remaining = budget_amount - spent

        if percent >= Decimal("100"):
            response += (
                "\n\n🔴 Внимание! Лимит бюджета исчерпан или превышен.\n"
                f"Лимит: {budget_amount:.2f}\n"
                f"Потрачено: {spent:.2f} ({percent:.1f}%)\n"
                f"Остаток: {remaining:.2f}"
            )
        elif percent >= Decimal("80"):
            response += (
                "\n\n🟠 Внимание! Использовано более 80% бюджета.\n"
                f"Лимит: {budget_amount:.2f}\n"
                f"Потрачено: {spent:.2f} ({percent:.1f}%)\n"
                f"Осталось: {remaining:.2f}"
            )

    await message.answer(
        response,
        reply_markup=get_main_keyboard(),
    )


@router.message(
    TransactionStates.waiting_for_confirmation,
    F.text,
    F.text != "❌ Отмена",
)
async def invalid_confirmation(message: Message) -> None:
    await message.answer(
        "Нажмите «✅ Сохранить» или «❌ Отмена».",
        reply_markup=get_transaction_confirm_keyboard(),
    )


@router.message(
    TransactionStates.waiting_for_category,
    F.text == "❌ Отмена",
)
@router.message(
    TransactionStates.waiting_for_amount,
    F.text == "❌ Отмена",
)
@router.message(
    TransactionStates.waiting_for_date,
    F.text == "❌ Отмена",
)
@router.message(
    TransactionStates.waiting_for_description,
    F.text == "❌ Отмена",
)
@router.message(
    TransactionStates.waiting_for_confirmation,
    F.text == "❌ Отмена",
)
async def cancel_transaction(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Операция отменена.",
        reply_markup=get_main_keyboard(),
    )
