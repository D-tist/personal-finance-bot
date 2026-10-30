from aiogram.fsm.state import State, StatesGroup


class ExportStates(StatesGroup):
    waiting_for_start_date = State()
    waiting_for_end_date = State()
