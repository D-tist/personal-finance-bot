from datetime import date, datetime, time, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select

from app.database.database import async_session
from app.database.models import Category, Transaction, User, UserSettings
from app.keyboards.export import (
    get_export_menu_keyboard,
    get_export_months_keyboard,
    get_export_years_keyboard,
)
from app.keyboards.main import get_main_keyboard
from app.services.excel_export import build_excel_export
from app.states.export import ExportStates


router = Router()


async def get_user_id(telegram_id: int) -> int | None:
    async with async_session() as session:
        result = await session.execute(
            select(User.id).where(
                User.telegram_id == telegram_id,
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()


async def get_user_dates(user_id: int) -> list[datetime]:
    async with async_session() as session:
        result = await session.execute(
            select(Transaction.operation_date).where(
                Transaction.user_id == user_id
            )
        )
        return list(result.scalars().all())


def get_years(dates: list[datetime]) -> list[int]:
    return sorted({item.year for item in dates}, reverse=True)


def get_months(dates: list[datetime], year: int) -> list[int]:
    return sorted(
        {
            item.month
            for item in dates
            if item.year == year
        }
    )


async def create_export(
    message: Message,
    telegram_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    filename: str = "finance_export.xlsx",
    state: FSMContext | None = None,
) -> None:
    user_id = await get_user_id(telegram_id)

    if user_id is None:
        await message.answer(
            "Профиль пользователя не найден.",
            reply_markup=get_main_keyboard(),
        )
        if state:
            await state.clear()
        return

    async with async_session() as session:
        query = (
            select(Transaction, Category.name)
            .join(
                Category,
                Transaction.category_id == Category.id,
            )
            .where(
                Transaction.user_id == user_id,
                Category.user_id == user_id,
            )
        )

        if start is not None:
            query = query.where(Transaction.operation_date >= start)

        if end is not None:
            query = query.where(Transaction.operation_date < end)

        query = query.order_by(
            Transaction.operation_date.asc(),
            Transaction.id.asc(),
        )

        result = await session.execute(query)
        transactions = result.all()

        if not transactions:
            await message.answer(
                "За выбранный период операций нет.",
                reply_markup=get_main_keyboard(),
            )
            if state:
                await state.clear()
            return

        categories_result = await session.execute(
            select(Category)
            .where(Category.user_id == user_id)
            .order_by(Category.name.asc())
        )
        categories = list(categories_result.scalars().all())

        settings_result = await session.execute(
            select(UserSettings).where(
                UserSettings.user_id == user_id
            )
        )
        settings = settings_result.scalar_one_or_none()

        currency = settings.currency if settings else "RUB"

    excel_data = build_excel_export(
        transactions=transactions,
        categories=categories,
        currency=currency,
    )

    document = BufferedInputFile(
        excel_data,
        filename=filename,
    )

    await message.answer_document(
        document=document,
        caption="Экспорт финансовых данных готов.",
        reply_markup=get_main_keyboard(),
    )

    if state:
        await state.clear()


@router.message(F.text == "📤 Экспорт в Excel")
async def start_export(message: Message, state: FSMContext) -> None:
    await state.clear()

    telegram_id = message.from_user.id
    user_id = await get_user_id(telegram_id)

    if user_id is None:
        await message.answer(
            "Профиль пользователя не найден.",
            reply_markup=get_main_keyboard(),
        )
        return

    dates = await get_user_dates(user_id)

    if not dates:
        await message.answer(
            "История операций пока пуста.",
            reply_markup=get_main_keyboard(),
        )
        return

    await message.answer(
        "Выберите период для экспорта:",
        reply_markup=get_export_menu_keyboard(),
    )


@router.callback_query(F.data == "export:month")
async def choose_month(callback: CallbackQuery) -> None:
    user_id = await get_user_id(callback.from_user.id)

    if user_id is None:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    dates = await get_user_dates(user_id)
    years = get_years(dates)

    if not years:
        await callback.answer("История операций пуста.", show_alert=True)
        return

    await callback.message.edit_text(
        "Сначала выберите год:",
        reply_markup=get_export_years_keyboard(years),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("export:year:"))
async def choose_year(callback: CallbackQuery) -> None:
    try:
        year = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("Некорректный год.", show_alert=True)
        return

    user_id = await get_user_id(callback.from_user.id)

    if user_id is None:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    dates = await get_user_dates(user_id)
    years = get_years(dates)

    if year not in years:
        await callback.answer("За этот год операций нет.", show_alert=True)
        return

    months = get_months(dates, year)

    await callback.message.edit_text(
        f"Выберите месяц за {year} год:",
        reply_markup=get_export_months_keyboard(year, months),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("export:month:"))
async def export_month(callback: CallbackQuery) -> None:
    try:
        _, _, year_text, month_text = callback.data.split(":")
        year = int(year_text)
        month = int(month_text)
    except (ValueError, IndexError):
        await callback.answer("Некорректный месяц.", show_alert=True)
        return

    user_id = await get_user_id(callback.from_user.id)

    if user_id is None:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    dates = await get_user_dates(user_id)

    if month not in get_months(dates, year):
        await callback.answer("За этот месяц операций нет.", show_alert=True)
        return

    start = datetime(year, month, 1, tzinfo=timezone.utc)

    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    filename = f"finance_export_{year}_{month:02d}.xlsx"

    await callback.answer("Формирую Excel-файл...")

    await create_export(
        message=callback.message,
        telegram_id=callback.from_user.id,
        start=start,
        end=end,
        filename=filename,
    )


@router.callback_query(F.data == "export:period")
async def choose_period(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(ExportStates.waiting_for_start_date)

    await callback.message.answer(
        "Введите начальную дату периода в формате ДД.ММ.ГГГГ.\n"
        "Например: 01.01.2026"
    )
    await callback.answer()


@router.message(ExportStates.waiting_for_start_date)
async def enter_start_date(
    message: Message,
    state: FSMContext,
) -> None:
    try:
        start_date = datetime.strptime(
            message.text.strip(),
            "%d.%m.%Y",
        ).date()
    except (ValueError, AttributeError):
        await message.answer(
            "Неверный формат даты. Используйте ДД.ММ.ГГГГ."
        )
        return

    await state.update_data(start_date=start_date.isoformat())
    await state.set_state(ExportStates.waiting_for_end_date)

    await message.answer(
        "Введите конечную дату периода в формате ДД.ММ.ГГГГ."
    )


@router.message(ExportStates.waiting_for_end_date)
async def enter_end_date(
    message: Message,
    state: FSMContext,
) -> None:
    try:
        end_date = datetime.strptime(
            message.text.strip(),
            "%d.%m.%Y",
        ).date()
    except (ValueError, AttributeError):
        await message.answer(
            "Неверный формат даты. Используйте ДД.ММ.ГГГГ."
        )
        return

    data = await state.get_data()
    start_date = date.fromisoformat(data["start_date"])

    if end_date < start_date:
        await message.answer(
            "Конечная дата не может быть раньше начальной. "
            "Введите конечную дату ещё раз."
        )
        return

    start = datetime.combine(
        start_date,
        time.min,
        tzinfo=timezone.utc,
    )

    end = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )

    filename = (
        f"finance_export_{start_date.isoformat()}_"
        f"{end_date.isoformat()}.xlsx"
    )

    await create_export(
        message=message,
        telegram_id=message.from_user.id,
        start=start,
        end=end,
        filename=filename,
        state=state,
    )


@router.callback_query(F.data == "export:all")
async def export_all(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.answer("Формирую Excel-файл...")

    await create_export(
        message=callback.message,
        telegram_id=callback.from_user.id,
        filename="finance_export_all.xlsx",
        state=state,
    )


@router.callback_query(F.data == "export:back")
async def back_to_export_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите период для экспорта:",
        reply_markup=get_export_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "export:month_back")
async def back_to_years(callback: CallbackQuery) -> None:
    user_id = await get_user_id(callback.from_user.id)

    if user_id is None:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    dates = await get_user_dates(user_id)
    years = get_years(dates)

    await callback.message.edit_text(
        "Сначала выберите год:",
        reply_markup=get_export_years_keyboard(years),
    )
    await callback.answer()


@router.callback_query(F.data == "export:cancel")
async def cancel_export(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    await callback.message.answer(
        "Экспорт отменён.",
        reply_markup=get_main_keyboard(),
    )
    await callback.answer()