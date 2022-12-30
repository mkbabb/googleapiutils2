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


def to_slice(*slices: slice | int) -> tuple[slice, ...]:
    func = lambda slc: slc if isinstance(slc, slice) else slice(slc, slc)
    return tuple(map(func, slices))


def ix_to_str(ix: int | str | EllipsisType) -> str:
    return str(ix) if ix is not ... else ""


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
    t_col = (
        "".join(
            map(
                lambda x: string.ascii_letters[x - 1].upper(),
                to_base(col, base=26),
            )
        )
        if col is not ...
        else ""
    )
    t_row = ix_to_str(row)
    return f"{t_col}{t_row}"


slice_or_int = (slice, int)


def is_valid_ix(ix: slice | int | EllipsisType) -> bool:
    return isinstance(ix, slice_or_int) or ix is ...


def is_valid_sheet_name(sheet_name: str | None) -> bool:
    return isinstance(sheet_name, str) or sheet_name is None


def slices_to_a1(slices: tuple[slice, slice] | slice | int) -> tuple[str, str | None]:
    match slices:
        case row_ix, col_ix:
            r1 = number_to_A1(row_ix.start, col_ix.start)
            r2 = number_to_A1(row_ix.stop, col_ix.stop)
            return r1, r2
        case row_ix if isinstance(row_ix, slice):
            return ix_to_str(row_ix.start), ix_to_str(row_ix.stop)
        case row_ix:
            return ix_to_str(row_ix)


def parse_sheets_ixs(ixs: tuple[str, slice, slice] | slice | int) -> str:
    sheet_name = None
    r1, r2 = None, None

    match ixs:
        case t_sheet_name if is_valid_sheet_name(t_sheet_name):
            sheet_name = t_sheet_name
        case t_sheet_name, *slices if isinstance(t_sheet_name, str):
            sheet_name = t_sheet_name
            r1, r2 = slices_to_a1(to_slice(*slices))
        case t_sheet_name, t_range_name if is_valid_sheet_name(
            t_sheet_name
        ) and is_valid_sheet_name(t_range_name):
            return t_sheet_name, t_range_name
        case row_ix, col_ix if is_valid_ix(row_ix) and is_valid_ix(col_ix):
            r1, r2 = slices_to_a1(to_slice(row_ix, col_ix))
        case row_ix if is_valid_ix(row_ix):
            r1 = slices_to_a1(row_ix)
        case _:
            raise ValueError(f"Invalid ixs: {ixs}")

    range_name = None

    if r1 is not None and r2 is not None:
        range_name = f"{r1}:{r2}"
    elif r1 is not None:
        range_name = str(r1)

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
