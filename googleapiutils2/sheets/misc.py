from __future__ import annotations

import string
from dataclasses import dataclass
from enum import Enum
from types import EllipsisType
from typing import *
import re

from ..utils import to_base

VERSION = "v4"

DEFAULT_SHEET_NAME = "Sheet1"

DEFAULT_SHEET_SHAPE = (1000, 26)


class ValueInputOption(Enum):
    unspecified = "INPUT_VALUE_OPTION_UNSPECIFIED"
    raw = "RAW"
    user_entered = "USER_ENTERED"


class ValueRenderOption(Enum):
    formatted = "FORMATTED_VALUE"
    unformatted = "UNFORMATTED_VALUE"
    formula = "FORMULA"


class InsertDataOption(Enum):
    insert = "INSERT_ROWS"
    overwrite = "OVERWRITE"


def format_range_name(
    sheet_name: str | None = None, range_name: str | None = None
) -> str:
    if sheet_name is not None and range_name is not None:
        if not (sheet_name.startswith("'") and sheet_name.endswith("'")):
            sheet_name = f"'{sheet_name}'"
        return f"{sheet_name}!{range_name}"
    elif range_name is not None:
        return range_name
    elif sheet_name is not None:
        return sheet_name
    else:
        return ""


BASE = 26
OFFSET = 1


def int_to_A1(i: int) -> str:
    nums = to_base(i - OFFSET, base=BASE)
    return "".join(map(lambda x: string.ascii_letters[x].upper(), nums))


def rc_to_A1(row: int, col: int) -> str:
    t_col = int_to_A1(col) if col is not ... else ""
    t_row = str(row) if row is not ... else ""

    return f"{t_col}{t_row}"


def A1_to_rc(a1: str | int) -> tuple[int, int | None]:
    finder = lambda x: string.ascii_letters.find(x) + OFFSET

    if isinstance(a1, int) or a1 is ...:
        return a1, None

    a1 = a1.lower()
    if ":" in a1:
        row, col = a1.split(":")
        return finder(row), finder(col)
    else:
        row = finder(a1)
        return row, row


def slices_to_A1(row_ix: slice, col_ix: slice) -> tuple[str, str]:
    return (
        rc_to_A1(row_ix.start, col_ix.start),
        rc_to_A1(row_ix.stop, col_ix.stop),
    )


def normalize_ix(ix: slice, length: int) -> slice:
    handle_negative = lambda x: x + length + 1 if isinstance(x, int) and x < 0 else x
    handle_str = lambda x: A1_to_rc(x)[0] if isinstance(x, str) else x

    start, stop = ix.start, ix.stop

    start, stop = handle_str(start), handle_str(stop)

    none_stop = start is not None and stop is None
    ellipsis_stop = stop is ... and not start is ...

    if none_stop or ellipsis_stop:
        stop = length

    start, stop = handle_negative(start), handle_negative(stop)

    return slice(start, stop, ix.step)


def to_slice(
    *slices: slice | int | EllipsisType, shape: tuple[int, ...] | None = None
) -> tuple[slice, ...]:
    def inner(ix: slice | int | EllipsisType) -> slice:
        if isinstance(ix, slice):
            return ix
        elif isinstance(ix, int):
            return slice(ix, ix)
        elif isinstance(ix, str):
            return slice(*A1_to_rc(ix))
        elif ix is ...:
            return slice(..., ...)
        else:
            raise TypeError(f"Invalid type: {type(ix)}")

    ixs = map(inner, slices)

    if shape is None:
        return tuple(ixs)

    return tuple((normalize_ix(ix, shape[n]) for n, ix in enumerate(ixs)))


def expand_slices(
    row_ix: slice | int, col_ix: slice | int, shape: tuple[int, int] | None
) -> list[str | None]:
    row_ix, col_ix = to_slice(row_ix, col_ix, shape=shape)
    row_ix, col_ix = slices_to_A1(row_ix, col_ix)
    range_name = f"{row_ix}:{col_ix}" if row_ix != "" and col_ix != "" else None
    return range_name


def parse_sheets_ixs(
    ixs: str | tuple[Any, ...], shape: tuple[int, int] | None
) -> tuple[str | None, str | None]:
    match ixs:
        case str(sheet_name), str(range_name):
            return sheet_name, range_name
        case str(sheet_name):
            return sheet_name, None
        case str(sheet_name), row_ix, col_ix:
            return sheet_name, expand_slices(row_ix, col_ix, shape=shape)
        case row_ix, col_ix:
            return None, expand_slices(row_ix, col_ix, shape=shape)
        case _:
            raise IndexError(f"Invalid index: {ixs}")


def reverse_sheet_range(range_name: str) -> tuple[str, str]:
    if "!" in range_name:
        sheet_name, range_name = range_name.split("!")
        return sheet_name, range_name

    if ":" in range_name:
        return DEFAULT_SHEET_NAME, range_name
    else:
        return range_name, ""


@dataclass(frozen=True)
class SheetSliceT:
    sheet_name: str | None = None
    range_name: str | None = None
    shape: tuple[int, int] = DEFAULT_SHEET_SHAPE

    def __repr__(self) -> str:
        return format_range_name(self.sheet_name, self.range_name)

    def __getitem__(self, ixs: str | tuple[Any, ...]) -> SheetSliceT:
        if isinstance(ixs, SheetSliceT):
            return ixs
        if isinstance(ixs, tuple) and not len(ixs):
            raise IndexError("Empty index")

        sheet_name, range_name = parse_sheets_ixs(ixs, shape=self.shape)
        return SheetSliceT(
            sheet_name if sheet_name is not None else self.sheet_name,
            range_name if range_name is not None else self.range_name,
            self.shape,
        )


SheetSlice = SheetSliceT()
