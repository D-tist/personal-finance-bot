from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_export_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\U0001F4C5 Выбрать месяц",
                    callback_data="export:month",
                )
            ],
            [
                InlineKeyboardButton(
                    text="\U0001F4C6 Выбрать период",
                    callback_data="export:period",
                )
            ],
            [
                InlineKeyboardButton(
                    text="\U0001F4E6 Все данные",
                    callback_data="export:all",
                )
            ],
            [
                InlineKeyboardButton(
                    text="\u274C Отмена",
                    callback_data="export:cancel",
                )
            ],
        ]
    )


def get_export_years_keyboard(years: list[int]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=str(year),
            callback_data=f"export:year:{year}",
        )
        for year in years
    ]

    rows = [
        buttons[index:index + 3]
        for index in range(0, len(buttons), 3)
    ]

    rows.append([
        InlineKeyboardButton(
            text="\u2B05 Назад",
            callback_data="export:back",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_export_months_keyboard(
    year: int,
    months: list[int],
) -> InlineKeyboardMarkup:
    month_names = [
        "Январь", "Февраль", "Март",
        "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь",
        "Октябрь", "Ноябрь", "Декабрь",
    ]

    buttons = [
        InlineKeyboardButton(
            text=month_names[month - 1],
            callback_data=f"export:month:{year}:{month}",
        )
        for month in months
        if 1 <= month <= 12
    ]

    rows = [
        buttons[index:index + 3]
        for index in range(0, len(buttons), 3)
    ]

    rows.append([
        InlineKeyboardButton(
            text="\u2B05 Назад",
            callback_data="export:month_back",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
