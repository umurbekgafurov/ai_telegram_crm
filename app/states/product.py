"""FSM states for the 'Add product' conversation flow."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ProductForm(StatesGroup):
    """Steps: name -> sku -> price -> stock -> confirm."""

    name = State()
    sku = State()
    price = State()
    stock = State()
    confirm = State()
