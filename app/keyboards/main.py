
from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Доход"),
                KeyboardButton(text="➖ Расход"),
            ],
            [
                KeyboardButton(text="🏦 Накопления"),
                KeyboardButton(text="📊 Баланс"),
            ],
            [
                KeyboardButton(text="📜 История"),
                KeyboardButton(text="📁 Категории"),
            ],
            [
                KeyboardButton(text="📈 Финансовый отчёт"),
            ],
            [
                KeyboardButton(text="📊 Аналитика по категориям"),
            ],
            [
                KeyboardButton(text="💰 Бюджеты"),
            ],
            [
                KeyboardButton(text="⚙️ Настройки"),
            ],
            [
                KeyboardButton(text="📤 Экспорт в Excel"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def get_categories_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Добавить категорию"),
            ],
            [
                KeyboardButton(text="💰 Категории доходов"),
                KeyboardButton(text="🛒 Категории расходов"),
            ],
            [
                KeyboardButton(text="🏦 Категории накоплений"),
            ],
            [
                KeyboardButton(text="⬅️ Главное меню"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел категорий",
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="❌ Отмена"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите название категории",
    )

def get_category_type_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💰 Доход"),
                KeyboardButton(text="🛒 Расход"),
            ],
            [
                KeyboardButton(text="🏦 Накопления"),
            ],
            [
                KeyboardButton(text="❌ Отмена"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите тип категории",
    )

def get_transaction_type_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Доход"),
                KeyboardButton(text="➖ Расход"),
            ],
            [
                KeyboardButton(text="⬅️ Главное меню"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите тип операции",
    )


def get_transaction_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="❌ Отмена"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите значение",
    )

def get_transaction_date_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📅 Сегодня"),
            ],
            [
                KeyboardButton(text="❌ Отмена"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите дату операции",
    )

def get_transaction_description_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⏭️ Пропустить комментарий"),
            ],
            [
                KeyboardButton(text="❌ Отмена"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите комментарий или пропустите",
    )


def get_transaction_confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Сохранить"),
            ],
            [
                KeyboardButton(text="❌ Отмена"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Подтвердите операцию",
    )

