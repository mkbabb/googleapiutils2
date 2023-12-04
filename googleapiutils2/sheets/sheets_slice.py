from __future__ import annotations

from typing import *

from cachetools import cached

from googleapiutils2.sheets.misc import (
    DEFAULT_SHEET_SHAPE,
    SheetSliceT,
    split_sheet_range,
)

SheetSlice = SheetSliceT()

SheetsRange = str | SheetSliceT | Hashable


cache: dict[SheetSliceT, SheetSliceT] = {}


def sheets_rangekey(sheets_range: SheetsRange) -> SheetSliceT:
    if isinstance(sheets_range, str):
        sheet_name, range_name = split_sheet_range(sheets_range)
        return SheetSliceT(sheet_name=sheet_name, range_name=range_name)
    else:
        return sheets_range  # type: ignore


@cached(cache=cache, key=sheets_rangekey)
def to_sheet_slice(sheets_range: SheetsRange) -> SheetSliceT:
    """Convert a string range to a SheetSlice. See the SheetSliceT class for more details."""

    if isinstance(sheets_range, SheetSliceT):
        return sheets_range
    else:
        shape = (
            sheets_range.shape()
            if hasattr(sheets_range, "shape")
            else DEFAULT_SHEET_SHAPE
        )
        sheets_range = str(sheets_range)

        return SheetSliceT(shape=shape)[str(sheets_range)]
