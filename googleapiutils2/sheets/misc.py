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


def format_range_name(range_name: str | None, sheet_name: str | None = None) -> str:
    if sheet_name is not None and range_name is not None:
        return f"'{sheet_name}'!{range_name}"
    elif range_name is not None:
        return range_name
    elif sheet_name is not None:
        return sheet_name
    else:
        return ""


def number_to_A1(row: int, col: int) -> str:
    t_col = "".join(
        map(
            lambda x: string.ascii_letters[x - 1].upper(),
            to_base(col, base=26),
        )
    )
    return f"{t_col}{row}"


slice_or_int = (slice, int)


def is_valid_ix(ix: slice | int | EllipsisType) -> bool:
    return isinstance(ix, slice_or_int) or ix is ...


def is_valid_sheet_name(sheet_name: str | None) -> bool:
    return isinstance(sheet_name, str) or sheet_name is None


def slices_to_a1(row_ix: slice, col_ix: slice) -> tuple[str, str]:
    return number_to_A1(row_ix.start, col_ix.start), number_to_A1(
        row_ix.stop, col_ix.stop
    )


def tmpp(*slices: slice):
    match slices:
        case t_row_ix, t_col_ix:
            return
        case t_row_ix:
            return


def parse_sheets_ixs(ixs: tuple[str, slice, slice] | slice | int) -> str:
    sheet_name = None
    row_ix, col_ix = None, None

    match ixs:
        case t_sheet_name, t_range_name if is_valid_sheet_name(
            t_sheet_name
        ) and is_valid_sheet_name(t_range_name):
            return t_sheet_name, t_range_name

        case t_sheet_name, *slices if is_valid_sheet_name(t_sheet_name):
            sheet_name = t_sheet_name
            row_ix, col_ix = tmpp(slices)

        case t_row_ix, *slices:
            row_ix, col_ix = tmpp((t_row_ix, *slices))

    r1, r2 = slices_to_a1(row_ix, col_ix)
    range_name = f"{r1}:{r2}"

    return sheet_name, range_name


@dataclass(frozen=True)
class SheetSliceT:
    sheet_name: str | None = None
    range_name: str | None = None

    def __str__(self) -> str:
        sheet_name = (
            self.sheet_name if self.sheet_name is not None else DEFAULT_SHEET_NAME
        )
        return format_range_name(self.range_name, sheet_name)

    # TODO! Redo all of this - add support for range size inference
    def __getitem__(
        self, ixs: tuple[str, slice, slice] | tuple[slice, slice]
    ) -> "SheetSliceT":
        if isinstance(ixs, SheetSliceT):
            return ixs
        else:
            return SheetSliceT(*parse_sheets_ixs(ixs))


SheetSlice = SheetSliceT()
