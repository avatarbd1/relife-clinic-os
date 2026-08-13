"""Request-local data spreadsheet selection."""
from contextlib import contextmanager
from contextvars import ContextVar

_sheet_override = ContextVar("relife_data_sheet_override", default=None)

def current_sheet_override():
    return _sheet_override.get()

def bind_sheet(sheet_id: str):
    if not str(sheet_id or "").strip():
        raise ValueError("sheet_id is required")
    return _sheet_override.set(str(sheet_id).strip())

@contextmanager
def use_sheet(sheet_id: str):
    token=bind_sheet(sheet_id)
    try:
        yield
    finally:
        _sheet_override.reset(token)
