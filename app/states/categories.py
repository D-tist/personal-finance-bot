
from aiogram.fsm.state import State, StatesGroup


class CategoryStates(StatesGroup):
    waiting_for_type = State()
    waiting_for_name = State()
