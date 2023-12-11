from __future__ import annotations

import string
from dataclasses import dataclass, field
from enum import Enum
from types import EllipsisType
from typing import *

from ..utils import to_base

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.resources import (
        CellFormat,
    )

VERSION = "v4"

DEFAULT_SHEET_NAME = "'Sheet1'"

DEFAULT_SHEET_SHAPE = (1000, 26)

BASE = 26
OFFSET = 1

SheetsValues = list[list[Any]] | list[dict[str | Any, Any]] | list[object]


@dataclass
class SheetsFormat:
    cell_format: CellFormat | None = None
    row_sizes: list[int] | None = None
    column_sizes: list[int] | None = None


class SheetsDimension(Enum):
    """The dimension that this rule applies to."""

    # This conditional format rule applies to rows.
    rows = "ROWS"
    # This conditional format rule applies to columns.
    columns = "COLUMNS"


class ValueInputOption(Enum):
    """How the input data should be interpreted."""

    # The values the user has entered will not be parsed and will be stored as-is.
    unspecified = "INPUT_VALUE_OPTION_UNSPECIFIED"
    # The values will be parsed as if the user typed them into the UI. Numbers will stay as
    raw = "RAW"
    # The values will be parsed as if the user typed them into the UI, but numbers will be
    user_entered = "USER_ENTERED"


class ValueRenderOption(Enum):
    """How values should be represented in the output."""

    # The values will be represented as they are formatted in the sheet.
    formatted = "FORMATTED_VALUE"
    # The values will be represented as they are in the sheet, without formatting.
    unformatted = "UNFORMATTED_VALUE"
    # The values will be represented as the formula (e.g. "=A1+B1") that is stored in the sheet.
    formula = "FORMULA"


class InsertDataOption(Enum):
    """How the input data should be inserted."""

    # Rows are inserted for the new data.
    insert = "INSERT_ROWS"
    # Rows are overwritten with the new data.
    overwrite = "OVERWRITE"


class HorizontalAlignment(Enum):
    """Defines the horizontal alignment of the content in a cell."""

    # Default value; indicates that the horizontal alignment is unspecified.
    HORIZONTAL_ALIGN_UNSPECIFIED = "HORIZONTAL_ALIGN_UNSPECIFIED"
    # Aligns content to the left side of the cell.
    LEFT = "LEFT"
    # Centers content horizontally in the cell.
    CENTER = "CENTER"
    # Aligns content to the right side of the cell.
    RIGHT = "RIGHT"


class HyperlinkDisplayType(Enum):
    """Specifies how a hyperlink is displayed in the cell."""

    # Default value; indicates that the hyperlink display type is unspecified.
    HYPERLINK_DISPLAY_TYPE_UNSPECIFIED = "HYPERLINK_DISPLAY_TYPE_UNSPECIFIED"
    # Shows the hyperlink with its associated link.
    LINKED = "LINKED"
    # Displays the hyperlink text without the link.
    PLAIN_TEXT = "PLAIN_TEXT"


class TextDirection(Enum):
    """Determines the direction of text in a cell."""

    # Default value; indicates that the text direction is unspecified.
    TEXT_DIRECTION_UNSPECIFIED = "TEXT_DIRECTION_UNSPECIFIED"
    # Text is oriented from left to right.
    LEFT_TO_RIGHT = "LEFT_TO_RIGHT"
    # Text is oriented from right to left.
    RIGHT_TO_LEFT = "RIGHT_TO_LEFT"


class VerticalAlignment(Enum):
    """Defines the vertical alignment of the content in a cell."""

    # Default value; indicates that the vertical alignment is unspecified.
    VERTICAL_ALIGN_UNSPECIFIED = "VERTICAL_ALIGN_UNSPECIFIED"
    # Aligns content to the top of the cell.
    TOP = "TOP"
    # Centers content vertically in the cell.
    MIDDLE = "MIDDLE"
    # Aligns content to the bottom of the cell.
    BOTTOM = "BOTTOM"


class WrapStrategy(Enum):
    """Specifies how text should wrap within a cell."""

    # Default value; indicates that the wrap strategy is unspecified.
    WRAP_STRATEGY_UNSPECIFIED = "WRAP_STRATEGY_UNSPECIFIED"
    # Content will overflow the cell without wrapping.
    OVERFLOW_CELL = "OVERFLOW_CELL"
    # Legacy wrap strategy.
    LEGACY_WRAP = "LEGACY_WRAP"
    # Content will be clipped and not displayed beyond the cell.
    CLIP = "CLIP"
    # Content will wrap within the cell.
    WRAP = "WRAP"


def normalize_sheet_name(sheet_name: str) -> str:
    """Normalize a sheet name for use in a Google Sheets API request.
    Quotes sheet names if they're not already quoted.

    Args:
        sheet_name (str): The name of the sheet.
    """
    if not (sheet_name.startswith("'") and sheet_name.endswith("'")):
        sheet_name = f"'{sheet_name}'"

    return sheet_name


def split_sheet_range(range_name: Any) -> tuple[str, str | None]:
    range_name = str(range_name)

    if "!" in range_name:
        sheet_name, range_name = range_name.split("!")
        return normalize_sheet_name(sheet_name), range_name

    if ":" in range_name:
        return DEFAULT_SHEET_NAME, range_name
    else:
        return range_name, None


def format_range_name(
    sheet_name: str | None = None, range_name: str | None = None
) -> str:
    """Format a range name for use in a Google Sheets API request.
    Quotes sheet names if they're not already quoted.

    Args:
        sheet_name (str | None): The name of the sheet.
        range_name (str | None): The range name.
    """
    if sheet_name is not None and range_name is not None:
        sheet_name = normalize_sheet_name(sheet_name)
        return f"{sheet_name}!{range_name}"
    elif range_name is not None:
        return range_name
    elif sheet_name is not None:
        return sheet_name
    else:
        return ""


def int_to_A1(i: int) -> str:
    nums = to_base(i - OFFSET, base=BASE)
    return "".join(map(lambda x: string.ascii_letters[x].upper(), nums))


def rc_to_A1(row: int, col: int) -> str:
    t_col = int_to_A1(col) if col is not ... else ""
    t_row = str(row) if row is not ... else ""
    return f"{t_col}{t_row}"


def A1_to_int(a1: str) -> int:
    base = len(
        string.ascii_uppercase
    )  # The base for this operation is 26 (letters in the alphabet)
    a1 = a1.upper()
    result = 0
    for i, c in enumerate(a1[::-1]):
        result += (string.ascii_uppercase.index(c) + 1) * (base**i)
    return result


def A1_to_rc(a1: str) -> tuple[int | None, int | None]:
    col_part = "".join(filter(str.isalpha, a1))
    row_part = "".join(filter(str.isdigit, a1))

    col = A1_to_int(col_part) if col_part else None  # return None if no column part
    row = int(row_part) if row_part else None  # return None if no row part

    return row, col


def A1_to_slices(
    a1: str, shape: tuple[int, int] = DEFAULT_SHEET_SHAPE
) -> tuple[slice, slice]:
    # Parse sheet and range
    _, range_name = split_sheet_range(a1)

    if not range_name:  # The entire sheet is the range
        return slice(1, shape[0]), slice(1, shape[1])

    if ":" in range_name:  # Range is specified
        start_a1, end_a1 = range_name.split(":")
    else:  # Only a single cell is specified
        start_a1, end_a1 = range_name, range_name

    # Convert A1 notation to row and column indices
    start_row, start_col = A1_to_rc(start_a1)
    end_row, end_col = A1_to_rc(end_a1)

    # If start indices are not specified, set them to 1
    start_row = start_row if start_row is not None and start_row is not ... else 1
    start_col = start_col if start_col is not None else 1

    # If end indices are not specified, set them to the maximum row/column
    end_row = end_row if end_row is not None else shape[0]
    end_col = end_col if end_col is not None else shape[1]

    return slice(start_row, end_row), slice(start_col, end_col)


def slices_to_A1(row_ix: slice, col_ix: slice) -> tuple[str, str]:
    return (
        rc_to_A1(row_ix.start, col_ix.start),
        rc_to_A1(row_ix.stop, col_ix.stop),
    )


def expand_slices(
    row_ix: slice | int | EllipsisType,
    col_ix: slice | int | EllipsisType,
    shape: tuple[int, int] = DEFAULT_SHEET_SHAPE,
) -> str | None:
    def to_slice(ix: slice | int) -> slice:
        if isinstance(ix, slice):
            return ix
        elif isinstance(ix, str):
            if ":" in ix:
                ix = ix.split(":")
                return slice(A1_to_int(ix[0]), A1_to_int(ix[1]))
            else:
                ix = A1_to_int(ix)
                return slice(ix, ix)
        elif isinstance(ix, int):
            return slice(ix, ix)
        elif ix is ...:
            return slice(..., ...)
        else:
            raise TypeError("Indices must be slices or integers.")

    def normalize_ix(slc: slice, max_dim: int) -> slice:
        start, stop, step = slc.start, slc.stop, slc.step
        # handle None
        start = 1 if start is None else start
        stop = max_dim if stop is None else stop
        # check if A1 notation is used
        start = A1_to_int(start) if isinstance(start, str) else start
        stop = A1_to_int(stop) if isinstance(stop, str) else stop
        # handle ellipsis
        start = 1 if start is ... else start
        stop = max_dim if stop is ... else stop
        # handle negative indices
        start = max_dim + start + 1 if start < 0 else start
        stop = max_dim + stop + 1 if stop < 0 else stop
        return slice(start, stop, step)

    row_is_ellipsis = row_ix is ...
    col_is_ellipsis = col_ix is ...

    row_ix, col_ix = to_slice(row_ix), to_slice(col_ix)  # type: ignore
    row_ix, col_ix = normalize_ix(row_ix, shape[0]), normalize_ix(col_ix, shape[1])  # type: ignore

    if col_is_ellipsis:
        return f"{row_ix.start}:{row_ix.stop}"
    if row_is_ellipsis:
        start, stop = int_to_A1(col_ix.start), int_to_A1(col_ix.stop)
        return f"{start}:{stop}"

    row_ix, col_ix = slices_to_A1(row_ix, col_ix)  # type: ignore
    return f"{row_ix}:{col_ix}" if row_ix != "" and col_ix != "" else None  # type: ignore


def parse_sheet_slice_ixs(
    ixs: str | tuple[Any, ...], shape: tuple[int, int] = DEFAULT_SHEET_SHAPE
) -> tuple[str | None, str | None]:
    def parse():
        match ixs:
            # sheet name and a string range
            case str(sheet_name), str(range_name):
                return sheet_name, range_name
            # only a sheet name, but this may be sheet_name!range_name
            case str(sheet_name):
                return split_sheet_range(sheet_name)
            # sheet name name, row, and column indices
            case str(sheet_name), row_ix, col_ix:
                return sheet_name, expand_slices(row_ix, col_ix, shape=shape)
            # row and column indices
            case row_ix, col_ix:
                return None, expand_slices(row_ix, col_ix, shape=shape)
            case _:
                raise IndexError(f"Invalid index: {ixs}")

    sheet_name, range_name = parse()
    return (
        normalize_sheet_name(sheet_name) if sheet_name is not None else sheet_name,
        range_name,
    )


@dataclass(unsafe_hash=True)
class SheetSliceT:
    """For better indexing of a Sheet-like object, e.g. a Google Sheet.
    Allows you to index into a sheet using numpy-like syntax.

    The forms a slice index can take are:
        SheetSlice[sheet_name, row_ix, col_ix]
        SheetSlice[sheet_name, range_name]
        SheetSlice[row_ix, col_ix]
        SheetSlice[sheet_name]
        SheetSlice[range_name]

    The sheet_name and range_name must be a string.
    Where the row_ix and col_ix can be either a slice, an int, a string, or an ellipsis.
    If it's a string, it must be in A1 notation. Finally, a slice can include a step value, but it's ignored (for now).

    Examples (using the singleton SheetSlice object):
    >>> ix = SheetSlice[1:3, 2:4]
    >>> assert str(ix) == "Sheet1!B1:E3"]

    Notice the "Sheet1" name interpolated: if no sheet name is provided, the default sheet name is used.

    Allows for the usage of ellipsis notation:

    >>> ix = SheetSlice[..., 1:3]
    >>> assert str(ix) == "Sheet1!A1:Z3"]

    The ellipsis is expanded to the shape of the sheet, if known.
    Defaults to the default shape of a Google Sheet, which is (1000, 26).

    A SheetSliceT can be used also as key into a dict:

    >>> key = SheetSlice["Sheet1", "A1:B2"]
    >>> d = {key: 1}
    >>> assert d[key] == 1
    >>> assert str(key) == "Sheet1!A1:B2"
    """

    sheet_name: str = DEFAULT_SHEET_NAME
    range_name: str | None = None
    shape: tuple[int, int] = DEFAULT_SHEET_SHAPE

    slices: tuple[slice, slice] = field(init=False, repr=False, hash=False)

    def __post_init__(self) -> None:
        self.slices = (
            A1_to_slices(self.range_name, shape=self.shape)
            if self.range_name is not None
            else (
                slice(1, self.shape[0] + 1),
                slice(1, self.shape[1] + 1),
            )
        )

    @property
    def rows(self) -> slice:
        return self.slices[0]

    @property
    def columns(self) -> slice:
        return self.slices[1]

    def with_shape(self, shape: tuple[int, int]) -> SheetSliceT:
        return SheetSliceT(
            sheet_name=self.sheet_name, range_name=self.range_name, shape=shape
        )

    def __repr__(self) -> str:
        return format_range_name(self.sheet_name, self.range_name)

    def __getitem__(
        self, ixs: str | tuple[Any, ...] | SheetSliceT | Any
    ) -> SheetSliceT:
        if isinstance(ixs, SheetSliceT):
            return ixs

        if isinstance(ixs, tuple) and not len(ixs):
            raise IndexError("Empty index")

        sheet_name, range_name = parse_sheet_slice_ixs(ixs, shape=self.shape)
        return SheetSliceT(
            sheet_name if sheet_name is not None else self.sheet_name,
            range_name if range_name is not None else self.range_name,
            self.shape,
        )
