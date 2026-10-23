
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import select

from app.database.database import async_session
from app.database.models import (
    Category,
    CategoryType,
    OperationType,
    SavingOperationType,
    Transaction,
    User,
)
from app.keyboards.main import (
    get_main_keyboard,
    get_transaction_cancel_keyboard,
    get_transaction_confirm_keyboard,
    get_transaction_description_keyboard,
)
from app.states.savings import SavingStates

router = Router()

DEPOSIT = SavingOperationType.DEPOSIT.value
WITHDRAW = SavingOperationType.WITHDRAW.value

SAVING_ACTIONS = {
    "➕ Пополнить накопления": DEPOSIT,
    "➖ Снять накопления": WITHDRAW,
}

SAVING_TITLES = {
    DEPOSIT: "Пополнение накоплений",
    WITHDRAW: "Снятие накоплений",
}

MAX_AMOUNT = Decimal("999999999999.99")

saving_action_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Пополнить накопления")],
        [KeyboardButton(text="➖ Снять накопления")],
        [KeyboardButton(text="❌ Отмена")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)


async def get_user_id(telegram_id: int) -> int | None:
    async with async_session() as session:
        result = await session.execute(
            select(User.id).where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()


@router.message(F.text == "🏦 Накопления")
async def start_savings(message: Message, state: FSMContext) -> None:
    await state.clear()

    user_id = await get_user_id(message.from_user.id)

    if user_id is None:
        await message.answer(
            "Профиль не найден. Отправьте /start.",
            reply_markup=get_main_keyboard(),
        )
        return

    await state.set_state(SavingStates.waiting_for_operation)

    await message.answer(
        "🏦 Управление накоплениями.\n"
        "Выберите действие:",
        reply_markup=saving_action_keyboard,
    )


@router.message(
    SavingStates.waiting_for_operation,
    F.text.in_(SAVING_ACTIONS.keys()),
)
async def choose_saving_operation(
    message: Message,
    state: FSMContext,
) -> None:
    saving_operation_type = SAVING_ACTIONS[message.text]

    user_id = await get_user_id(message.from_user.id)

    if user_id is None:
        await state.clear()
        await message.answer(
            "Профиль не найден. Отправьте /start.",
            reply_markup=get_main_keyboard(),
        )
        return

    async with async_session() as session:
        result = await session.execute(
            select(Category)
            .where(
                Category.user_id == user_id,
                Category.category_type == CategoryType.SAVING.value,
                Category.is_active.is_(True),
            )
            .order_by(Category.name)
        )
        categories = result.scalars().all()

    if not categories:
        await state.clear()
        await message.answer(
            "У вас пока нет категорий накоплений.\n"
            "Откройте «📁 Категории» → "
            "«➕ Добавить категорию» и создайте категорию "
            "типа «🏦 Накопления».",
            reply_markup=get_main_keyboard(),
        )
        return

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=category.name)]
            for category in categories
        ] + [[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        input_field_placeholder="Выберите категорию накоплений",
    )

    await state.update_data(
        saving_operation_type=saving_operation_type,
        categories={
            category.name: category.id
            for category in categories
        },
    )
    await state.set_state(SavingStates.waiting_for_category)

    await message.answer(
        f"Действие: {SAVING_TITLES[saving_operation_type]}.\n"
        "Выберите категорию:",
        reply_markup=keyboard,
    )


@router.message(
    SavingStates.waiting_for_category,
    F.text,
    F.text != "❌ Отмена",
)
async def choose_saving_category(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    category_id = data.get("categories", {}).get(message.text)

    if category_id is None:
        await message.answer(
            "Выберите категорию кнопкой из списка "
            "или нажмите «❌ Отмена»."
        )
        return

    await state.update_data(category_id=category_id)
    await state.set_state(SavingStates.waiting_for_amount)

    await message.answer(
        "Введите сумму, например 5000 или 1250,50.",
        reply_markup=get_transaction_cancel_keyboard(),
    )


@router.message(
    SavingStates.waiting_for_amount,
    F.text,
    F.text != "❌ Отмена",
)
async def enter_saving_amount(
    message: Message,
    state: FSMContext,
) -> None:
    raw_amount = message.text.strip().replace(",", ".")

    try:
        amount = Decimal(raw_amount)
    except InvalidOperation:
        await message.answer(
            "Введите сумму числом, например 1250,50."
        )
        return

    if not amount.is_finite() or amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return

    if amount > MAX_AMOUNT or amount.as_tuple().exponent < -2:
        await message.answer(
            "Максимум — 2 знака после запятой; "
            "сумма не должна превышать 999999999999,99."
        )
        return

    await state.update_data(amount=str(amount))
    await state.set_state(SavingStates.waiting_for_date)

    await message.answer(
        "Введите дату операции в формате ДД.ММ.ГГГГ.\n"
        f"Например: {datetime.now().strftime('%d.%m.%Y')}",
        reply_markup=get_transaction_cancel_keyboard(),
    )


@router.message(
    SavingStates.waiting_for_date,
    F.text,
    F.text != "❌ Отмена",
)
async def enter_saving_date(
    message: Message,
    state: FSMContext,
) -> None:
    try:
        operation_date = datetime.strptime(
            message.text.strip(),
            "%d.%m.%Y",
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        await message.answer(
            "Неверная дата. Используйте формат ДД.ММ.ГГГГ."
        )
        return

    await state.update_data(
        operation_date=operation_date.isoformat()
    )
    await state.set_state(SavingStates.waiting_for_description)

    await message.answer(
        "Добавьте комментарий или пропустите его.",
        reply_markup=get_transaction_description_keyboard(),
    )


async def show_saving_confirmation(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    category_name = next(
        (
            name
            for name, category_id in data["categories"].items()
            if category_id == data["category_id"]
        ),
        "Неизвестная категория",
    )

    operation_date = datetime.fromisoformat(data["operation_date"])
    amount = Decimal(data["amount"])
    saving_operation_type = data["saving_operation_type"]

    await state.set_state(SavingStates.waiting_for_confirmation)

    await message.answer(
        "Проверьте операцию:\n\n"
        f"Тип: {SAVING_TITLES[saving_operation_type]}\n"
        f"Категория: {category_name}\n"
        f"Сумма: {amount:.2f}\n"
        f"Дата: {operation_date.strftime('%d.%m.%Y')}\n"
        f"Комментарий: {data.get('description') or 'Не указан'}\n\n"
        "Сохранить операцию?",
        reply_markup=get_transaction_confirm_keyboard(),
    )


@router.message(
    SavingStates.waiting_for_description,
    F.text == "⏭️ Пропустить комментарий",
)
async def skip_saving_description(
    message: Message,
    state: FSMContext,
) -> None:
    await state.update_data(description=None)
    await show_saving_confirmation(message, state)


@router.message(
    SavingStates.waiting_for_description,
    F.text,
    F.text != "❌ Отмена",
    F.text != "⏭️ Пропустить комментарий",
)
async def enter_saving_description(
    message: Message,
    state: FSMContext,
) -> None:
    description = message.text.strip()

    if len(description) > 2000:
        await message.answer(
            "Комментарий слишком длинный. Максимум 2000 символов."
        )
        return

    await state.update_data(description=description or None)
    await show_saving_confirmation(message, state)



@router.message(
    SavingStates.waiting_for_confirmation,
    F.text == "✅ Сохранить",
)
async def save_saving_transaction(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    user_id = await get_user_id(message.from_user.id)

    if user_id is None:
        await state.clear()
        await message.answer(
            "Профиль не найден или отключён. Отправьте /start.",
            reply_markup=get_main_keyboard(),
        )
        return

    async with async_session() as session:
        result = await session.execute(
            select(Category).where(
                Category.id == data["category_id"],
                Category.user_id == user_id,
                Category.category_type == CategoryType.SAVING.value,
                Category.is_active.is_(True),
            )
        )
        category = result.scalar_one_or_none()

        if category is None:
            await state.clear()
            await message.answer(
                "Категория больше недоступна. Начните заново.",
                reply_markup=get_main_keyboard(),
            )
            return

        if data["saving_operation_type"] == WITHDRAW:
            result = await session.execute(
                select(Transaction).where(
                    Transaction.user_id == user_id,
                    Transaction.category_id == category.id,
                    Transaction.operation_type == OperationType.SAVING.value,
                )
            )
            existing_transactions = result.scalars().all()

            available_amount = sum(
                (
                    transaction.amount
                    if transaction.saving_operation_type == DEPOSIT
                    else -transaction.amount
                    if transaction.saving_operation_type == WITHDRAW
                    else Decimal("0")
                )
                for transaction in existing_transactions
            )

            requested_amount = Decimal(data["amount"])

            if requested_amount > available_amount:
                await state.set_state(SavingStates.waiting_for_amount)
                await message.answer(
                    "Недостаточно средств в этой категории.\n"
                    f"Доступно: {available_amount:.2f}\n"
                    f"Вы хотите снять: {requested_amount:.2f}\n\n"
                    "Введите меньшую сумму:",
                    reply_markup=get_transaction_cancel_keyboard(),
                )
                return

        transaction = Transaction(
            user_id=user_id,
            category_id=category.id,
            operation_type=OperationType.SAVING.value,
            saving_operation_type=data["saving_operation_type"],
            amount=Decimal(data["amount"]),
            operation_date=datetime.fromisoformat(data["operation_date"]),
            description=data.get("description"),
        )

        session.add(transaction)
        await session.commit()

        category_name = category.name

    amount = Decimal(data["amount"])
    title = SAVING_TITLES[data["saving_operation_type"]]
    date_text = datetime.fromisoformat(
        data["operation_date"]
    ).strftime("%d.%m.%Y")

    await state.clear()
    await message.answer(
        f"✅ {title} сохранено!\n"
        f"Категория: {category_name}\n"
        f"Сумма: {amount:.2f}\n"
        f"Дата: {date_text}",
        reply_markup=get_main_keyboard(),
    )



@router.message(
    SavingStates.waiting_for_confirmation,
    F.text,
    F.text != "❌ Отмена",
    F.text != "✅ Сохранить",
)
async def invalid_saving_confirmation(message: Message) -> None:
    await message.answer(
        "Нажмите «✅ Сохранить» или «❌ Отмена».",
        reply_markup=get_transaction_confirm_keyboard(),
    )


@router.message(
    SavingStates.waiting_for_operation,
    F.text == "❌ Отмена",
)
@router.message(
    SavingStates.waiting_for_category,
    F.text == "❌ Отмена",
)
@router.message(
    SavingStates.waiting_for_amount,
    F.text == "❌ Отмена",
)
@router.message(
    SavingStates.waiting_for_date,
    F.text == "❌ Отмена",
)
@router.message(
    SavingStates.waiting_for_description,
    F.text == "❌ Отмена",
)
@router.message(
    SavingStates.waiting_for_confirmation,
    F.text == "❌ Отмена",
)
async def cancel_saving(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()
    await message.answer(
        "Операция с накоплениями отменена.",
        reply_markup=get_main_keyboard(),
    )
