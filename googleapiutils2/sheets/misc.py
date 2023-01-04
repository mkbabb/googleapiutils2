import string
from dataclasses import dataclass
from enum import Enum
from types import EllipsisType
from typing import *

from ..utils import to_base

VERSION = "v4"

DEFAULT_SHEET_NAME = "Sheet1"


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
        return f"'{sheet_name}'!{range_name}"
    elif range_name is not None:
        return range_name
    elif sheet_name is not None:
        return sheet_name
    else:
        return ""


def int_to_A1(i: int) -> str:
    nums = to_base(i, base=26)
    return "".join(map(lambda x: string.ascii_letters[x].upper(), nums))


def rc_to_A1(row: int, col: int) -> str:
    t_col = int_to_A1(col) if col is not ... else ""
    t_row = str(row) if row is not ... else ""
    return f"{t_col}{t_row}"


def A1_to_rc(a1: str | int) -> tuple[int, int | None]:
    if isinstance(a1, int) or a1 is ...:
        return a1, None

    a1 = a1.lower()
    if ":" in a1:
        row, col = a1.split(":")
        return string.ascii_letters.find(row), string.ascii_letters.find(col)
    else:
        return string.ascii_letters.find(a1), None


def slices_to_A1(row_ix: slice, col_ix: slice) -> tuple[str, str]:
    return (
        rc_to_A1(row_ix.start, col_ix.start),
        rc_to_A1(row_ix.stop, col_ix.stop),
    )


def expand_ellipsis(ix: slice, length: int) -> slice:
    if isinstance(ix.start, str) or isinstance(ix.stop, str):
        ix = slice(A1_to_rc(ix.start)[0], A1_to_rc(ix.stop)[0])

    if ix.stop is ... and not ix.start is ...:
        return slice(ix.start, length)
    else:
        return ix


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

    if shape is not None:
        ixs = (expand_ellipsis(ix, shape[n]) for n, ix in enumerate(ixs))

    return tuple(ixs)


SheetSliceArg = (
    tuple[str, slice, slice] | tuple[str, slice] | tuple[slice, slice] | tuple[str, str]
)


def parse_sheets_ixs(ixs: SheetSliceArg, shape: tuple[int, int] | None) -> str:
    def complete_ix(sheet_name: str | None, row_ix: slice | int, col_ix: slice | int):


        
        row_ix, col_ix = slices_to_A1(*to_slice(row_ix, col_ix, shape=shape))
        range_name = f"{row_ix}:{col_ix}" if row_ix != "" and col_ix != "" else None
        
        return sheet_name, range_name

    match ixs:
        case str(sheet_name), str(range_name):
            return sheet_name, range_name
        case str(sheet_name):
            return sheet_name, None
        case str(sheet_name), row_ix, col_ix:
            return complete_ix(sheet_name, row_ix, col_ix)
        case row_ix, col_ix:
            return complete_ix(None, row_ix, col_ix)
        case _:
            raise IndexError(f"Invalid index: {ixs}")


@dataclass(frozen=True)
class SheetSliceT:
    sheet_name: str | None = None
    range_name: str | None = None
    shape: tuple[int, int] = (10000, 26)

    def __str__(self) -> str:
        sheet_name = (
            self.sheet_name if self.sheet_name is not None else DEFAULT_SHEET_NAME
        )
        return format_range_name(sheet_name, self.range_name)

    def __getitem__(
        self, ixs: tuple[str, slice, slice] | tuple[slice, slice]
    ) -> "SheetSliceT":
        if isinstance(ixs, SheetSliceT):
            return ixs
        if isinstance(ixs, tuple) and not len(ixs):
            raise IndexError("Empty index")

        sheet_name, range_name = parse_sheets_ixs(ixs, shape=self.shape)
        return SheetSliceT(sheet_name, range_name, self.shape)


SheetSlice = SheetSliceT()
