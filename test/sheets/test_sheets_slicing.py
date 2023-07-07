from __future__ import annotations

import itertools
from typing import *

from googleapiutils2 import Sheets, SheetSlice, SheetsValueRange

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File


def test_sheet_slice():
    sheets = ["Sheet1", None]
    start_ixs = ["A", 0, 2, ..., None]
    end_ixs = [None, 1, 6, ..., "B", -2]

    for sheet, row_start_ix, row_end_ix, col_start_ix, col_end_ix in itertools.product(
        sheets, start_ixs, end_ixs, start_ixs, end_ixs
    ):
        row_slice = (
            slice(row_start_ix, row_end_ix)
            if not (row_start_ix is None or row_end_ix is None)
            else None
        )
        col_slice = (
            slice(col_start_ix, col_end_ix)
            if not (col_start_ix is None or col_end_ix is None)
            else None
        )
        if (row_slice is None) ^ (col_slice is None):
            continue

        ixs: list = []
        if sheet is not None:
            ixs = [sheet]
        if row_slice is not None and col_slice is not None:
            ixs += [row_slice, col_slice]

        if len(ixs) == 1:
            ixs = ixs[0]
        else:
            ixs = tuple(ixs)  # type: ignore

        try:
            slc = SheetSlice.__getitem__(ixs)  # type: ignore
            print(slc)
        except IndexError:
            continue
        except:
            raise
