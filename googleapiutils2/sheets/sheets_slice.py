from __future__ import annotations

from typing import *

from cachetools import cached

from googleapiutils2.sheets.misc import SheetSliceT, split_sheet_range
from googleapiutils2.sheets.sheets_value_range import SheetsValueRange

SheetSlice = SheetSliceT()

SheetsRange = str | SheetSliceT | SheetsValueRange | Hashable


def sheets_rangekey(sheets_range: SheetsRange) -> SheetSliceT:
    if isinstance(sheets_range, str):
        sheet_name, range_name = split_sheet_range(sheets_range)
        return SheetSliceT(sheet_name=sheet_name, range_name=range_name)
    else:
        return sheets_range  # type: ignore


cache: dict[SheetSliceT, SheetSliceT] = {}


@cached(cache=cache, key=sheets_rangekey)
def normalize_sheets_range(sheets_range: SheetsRange) -> SheetSliceT:
    if isinstance(sheets_range, SheetSliceT):
        return sheets_range
    elif isinstance(sheets_range, SheetsValueRange):
        return SheetSliceT(
            sheet_name=sheets_range.sheet_name,
            range_name=sheets_range.range_name,
            shape=sheets_range.shape(),
        )
    else:
        sheets_range = str(sheets_range)

        return SheetSliceT()[str(sheets_range)]
