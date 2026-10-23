
from aiogram.fsm.state import State, StatesGroup


class SavingStates(StatesGroup):
    waiting_for_operation = State()
    waiting_for_category = State()
    waiting_for_amount = State()
    waiting_for_date = State()
    waiting_for_description = State()
    waiting_for_confirmation = State()
