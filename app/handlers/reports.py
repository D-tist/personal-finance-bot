
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from aiogram import F, Router
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import select

from app.database.database import async_session
from app.database.models import Category, OperationType, Transaction, User
from app.keyboards.main import get_main_keyboard

router = Router()

ZERO = Decimal("0.00")

HISTORY_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🕒 Последние 10 операций")],
        [KeyboardButton(text="📅 История за месяц")],
        [KeyboardButton(text="⬅️ Главное меню")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите период истории",
)


async def find_user_id(telegram_id: int) -> int | None:
    async with async_session() as session:
        result = await session.execute(
            select(User.id).where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()


def format_money(amount: Decimal) -> str:
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def format_operation(transaction: Transaction, category_name: str) -> str:
    date_text = transaction.operation_date.strftime("%d.%m.%Y")
    amount_text = format_money(transaction.amount)

    if transaction.operation_type == OperationType.INCOME.value:
        sign = "+"
        title = "Доход"
    elif transaction.operation_type == OperationType.EXPENSE.value:
        sign = "−"
        title = "Расход"
    elif transaction.operation_type == OperationType.SAVING.value:
        if transaction.saving_operation_type == "DEPOSIT":
            sign = "−"
            title = "Пополнение накоплений"
        elif transaction.saving_operation_type == "WITHDRAW":
            sign = "+"
            title = "Снятие накоплений"
        else:
            sign = ""
            title = "Операция с накоплениями"
    else:
        sign = ""
        title = "Операция"

    text = (
        f"{date_text} | {title}\n"
        f"Категория: {category_name}\n"
        f"Сумма: {sign}{amount_text}"
    )

    if transaction.description:
        text += f"\nКомментарий: {transaction.description}"

    return text


@router.message(F.text == "📊 Баланс")
async def show_balance(message: Message) -> None:
    user_id = await find_user_id(message.from_user.id)

    if user_id is None:
        await message.answer(
            "Профиль не найден. Отправьте /start.",
            reply_markup=get_main_keyboard(),
        )
        return

    async with async_session() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.user_id == user_id)
        )
        transactions = result.scalars().all()

    income = ZERO
    expense = ZERO
    deposits = ZERO
    withdrawals = ZERO

    for transaction in transactions:
        amount = transaction.amount

        if transaction.operation_type == OperationType.INCOME.value:
            income += amount
        elif transaction.operation_type == OperationType.EXPENSE.value:
            expense += amount
        elif transaction.operation_type == OperationType.SAVING.value:
            if transaction.saving_operation_type == "DEPOSIT":
                deposits += amount
            elif transaction.saving_operation_type == "WITHDRAW":
                withdrawals += amount

    free_balance = income - expense - deposits + withdrawals
    savings_balance = deposits - withdrawals

    await message.answer(
        "📊 Ваш финансовый баланс\n\n"
        f"Доходы: +{format_money(income)}\n"
        f"Расходы: −{format_money(expense)}\n"
        f"Пополнения накоплений: −{format_money(deposits)}\n"
        f"Снятия накоплений: +{format_money(withdrawals)}\n"
        "────────────────\n"
        f"Свободный баланс: {format_money(free_balance)}\n"
        f"Накопления: {format_money(savings_balance)}",
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "📜 История")
async def show_history_menu(message: Message) -> None:
    await message.answer(
        "📜 История операций.\nВыберите период:",
        reply_markup=HISTORY_KEYBOARD,
    )


async def send_history(
    message: Message,
    limit: int | None = None,
    current_month: bool = False,
) -> None:
    user_id = await find_user_id(message.from_user.id)

    if user_id is None:
        await message.answer(
            "Профиль не найден. Отправьте /start.",
            reply_markup=get_main_keyboard(),
        )
        return

    async with async_session() as session:
        query = (
            select(Transaction, Category.name)
            .join(Category, Transaction.category_id == Category.id)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.operation_date.desc(), Transaction.id.desc())
        )

        if current_month:
            now = datetime.now(timezone.utc)
            month_start = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )

            if month_start.month == 12:
                next_month = month_start.replace(
                    year=month_start.year + 1,
                    month=1,
                )
            else:
                next_month = month_start.replace(
                    month=month_start.month + 1,
                )

            query = query.where(
                Transaction.operation_date >= month_start,
                Transaction.operation_date < next_month,
            )

        if limit is not None:
            query = query.limit(limit)

        result = await session.execute(query)
        rows = result.all()

    if not rows:
        await message.answer(
            "За выбранный период операций пока нет.",
            reply_markup=HISTORY_KEYBOARD,
        )
        return

    title = (
        "📅 Операции за текущий месяц"
        if current_month
        else "🕒 Последние операции"
    )

    lines = [title, ""]

    for transaction, category_name in rows:
        lines.append(format_operation(transaction, category_name))
        lines.append("────────────")

    await message.answer(
        "\n".join(lines),
        reply_markup=HISTORY_KEYBOARD,
    )


@router.message(F.text == "🕒 Последние 10 операций")
async def show_recent_history(message: Message) -> None:
    await send_history(message, limit=10)


@router.message(F.text == "📅 История за месяц")
async def show_month_history(message: Message) -> None:
    await send_history(message, current_month=True)


@router.message(F.text == "⬅️ Главное меню")
async def return_to_main_menu(message: Message) -> None:
    await message.answer(
        "Главное меню.",
        reply_markup=get_main_keyboard(),
    )

def calculate_financial_metrics(
    transactions: list[Transaction],
) -> dict[str, Decimal]:
    metrics = {
        "income": ZERO,
        "expense": ZERO,
        "deposits": ZERO,
        "withdrawals": ZERO,
    }

    for transaction in transactions:
        amount = transaction.amount

        if transaction.operation_type == OperationType.INCOME.value:
            metrics["income"] += amount
        elif transaction.operation_type == OperationType.EXPENSE.value:
            metrics["expense"] += amount
        elif transaction.operation_type == OperationType.SAVING.value:
            if transaction.saving_operation_type == "DEPOSIT":
                metrics["deposits"] += amount
            elif transaction.saving_operation_type == "WITHDRAW":
                metrics["withdrawals"] += amount

    metrics["net"] = metrics["income"] - metrics["expense"]
    metrics["free_change"] = (
        metrics["income"]
        - metrics["expense"]
        - metrics["deposits"]
        + metrics["withdrawals"]
    )
    metrics["savings_change"] = (
        metrics["deposits"] - metrics["withdrawals"]
    )

    return metrics


def format_metric_comparison(
    current: Decimal,
    previous: Decimal,
) -> str:
    difference = current - previous

    if difference > ZERO:
        sign = "+"
    elif difference < ZERO:
        sign = "−"
    else:
        sign = ""

    return f"{sign}{format_money(abs(difference))}"


@router.message(F.text == "📈 Финансовый отчёт")
async def show_financial_report(message: Message) -> None:
    user_id = await find_user_id(message.from_user.id)

    if user_id is None:
        await message.answer(
            "Профиль не найден. Отправьте /start.",
            reply_markup=get_main_keyboard(),
        )
        return

    now = datetime.now(timezone.utc)
    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    if month_start.month == 1:
        previous_start = month_start.replace(
            year=month_start.year - 1,
            month=12,
        )
    else:
        previous_start = month_start.replace(
            month=month_start.month - 1,
        )

    previous_end = previous_start + (now - month_start)

    async with async_session() as session:
        result = await session.execute(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.operation_date >= previous_start,
                Transaction.operation_date < now,
            )
        )
        transactions = result.scalars().all()

    current_transactions = [
        transaction
        for transaction in transactions
        if transaction.operation_date >= month_start
    ]

    previous_transactions = [
        transaction
        for transaction in transactions
        if transaction.operation_date < previous_end
    ]

    current = calculate_financial_metrics(current_transactions)
    previous = calculate_financial_metrics(previous_transactions)

    month_names = [
        "января", "февраля", "марта", "апреля",
        "мая", "июня", "июля", "августа",
        "сентября", "октября", "ноября", "декабря",
    ]

    current_month_name = month_names[now.month - 1]
    previous_month_date = previous_start
    previous_month_name = month_names[previous_month_date.month - 1]

    lines = [
        "📈 ФИНАНСОВЫЙ ОТЧЁТ",
        "",
        f"Текущий период: 1–{now.day} {current_month_name}",
        "",
        "💰 ДОХОДЫ И РАСХОДЫ",
        f"Доходы: +{format_money(current['income'])}",
        f"Расходы: −{format_money(current['expense'])}",
        f"Разница: {format_money(current['net'])}",
        "",
        "🏦 НАКОПЛЕНИЯ",
        f"Пополнения: {format_money(current['deposits'])}",
        f"Снятия: {format_money(current['withdrawals'])}",
        f"Изменение накоплений: {format_money(current['savings_change'])}",
        "",
        f"Свободный баланс изменился на: "
        f"{format_money(current['free_change'])}",
        "",
        f"📊 СРАВНЕНИЕ С {previous_month_name.upper()}",
        "(за аналогичный промежуток времени)",
        (
            "Доходы: "
            + format_metric_comparison(
                current["income"], previous["income"]
            )
        ),
        (
            "Расходы: "
            + format_metric_comparison(
                current["expense"], previous["expense"]
            )
        ),
        (
            "Разница доходов и расходов: "
            + format_metric_comparison(
                current["net"], previous["net"]
            )
        ),
        (
            "Изменение свободного баланса: "
            + format_metric_comparison(
                current["free_change"], previous["free_change"]
            )
        ),
    ]

    await message.answer(
        "\n".join(lines),
        reply_markup=get_main_keyboard(),
    )

@router.message(F.text == "📊 Аналитика по категориям")
async def show_category_analytics(message: Message) -> None:
    user_id = await find_user_id(message.from_user.id)

    if user_id is None:
        await message.answer(
            "Профиль не найден. Отправьте /start.",
            reply_markup=get_main_keyboard(),
        )
        return

    now = datetime.now(timezone.utc)
    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    async with async_session() as session:
        result = await session.execute(
            select(Transaction, Category.name)
            .join(Category, Transaction.category_id == Category.id)
            .where(
                Transaction.user_id == user_id,
                Category.user_id == user_id,
                Transaction.operation_date >= month_start,
                Transaction.operation_date < now,
            )
        )
        rows = result.all()

    income_by_category: dict[str, Decimal] = {}
    expense_by_category: dict[str, Decimal] = {}

    for transaction, category_name in rows:
        if transaction.operation_type == OperationType.INCOME.value:
            income_by_category[category_name] = (
                income_by_category.get(category_name, ZERO)
                + transaction.amount
            )
        elif transaction.operation_type == OperationType.EXPENSE.value:
            expense_by_category[category_name] = (
                expense_by_category.get(category_name, ZERO)
                + transaction.amount
            )

    total_income = sum(income_by_category.values(), ZERO)
    total_expense = sum(expense_by_category.values(), ZERO)

    month_names = [
        "января", "февраля", "марта", "апреля",
        "мая", "июня", "июля", "августа",
        "сентября", "октября", "ноября", "декабря",
    ]
    period_text = f"{month_names[now.month - 1]} {now.year}"

    lines = [
        "📊 АНАЛИТИКА ПО КАТЕГОРИЯМ",
        f"Период: {period_text}",
        "",
        f"💰 Доходы: {format_money(total_income)}",
    ]

    if income_by_category:
        for name, amount in sorted(
            income_by_category.items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            share = (
                amount / total_income * 100
                if total_income > ZERO
                else ZERO
            )
            lines.append(
                f"• {name}: {format_money(amount)} "
                f"({share:.1f}%)"
            )
    else:
        lines.append("Операций с доходами пока нет.")

    lines.extend([
        "",
        f"🛒 Расходы: {format_money(total_expense)}",
    ])

    if expense_by_category:
        for name, amount in sorted(
            expense_by_category.items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            share = (
                amount / total_expense * 100
                if total_expense > ZERO
                else ZERO
            )
            lines.append(
                f"• {name}: {format_money(amount)} "
                f"({share:.1f}%)"
            )
    else:
        lines.append("Операций с расходами пока нет.")

    lines.extend([
        "",
        f"📈 Разница доходов и расходов: "
        f"{format_money(total_income - total_expense)}",
        "",
        "Пополнения и снятия накоплений в этих суммах "
        "не учитываются.",
    ])

    await message.answer(
        "\n".join(lines),
        reply_markup=get_main_keyboard(),
    )

