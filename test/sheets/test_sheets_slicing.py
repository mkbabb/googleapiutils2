from __future__ import annotations

import itertools
from typing import *

from googleapiutils2.sheets import Sheets, SheetSlice, SheetsValueRange

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

        ixs = []
        if sheet is not None:
            ixs = [sheet]
        if row_slice is not None and col_slice is not None:
            ixs += [row_slice, col_slice]

        if len(ixs) == 1:
            ixs = ixs[0]
        else:
            ixs = tuple(ixs)

        try:
            slc = SheetSlice.__getitem__(ixs)
        except IndexError:
            continue
        except:
            raise


def test_many_slicing(sheets: Sheets, test_sheet: File):
    sheet_id = test_sheet["id"]

    Sheet1 = SheetsValueRange(sheets, sheet_id, sheet_name="Sheet1")

    rows = [
        {"Heyy": "99", "Gay Vibes": "hey", "9": "wow", "not there": "OMG"},
        {
            "5": "99",
            "6": "hey",
            "9": "wow",
        },
    ]
    Sheet1[2:3, ...].update(rows)
    Sheet1[4:5, ...].update(rows)

    Sheet1[4, "A"].update([["Frunk!"]])

    sheets.update(
        sheet_id,
        Sheet1[5, ...],
        values=[[11, 22, 33]],
    )

    Sheet1[6:, ...].clear()

    for _ in range(10):
        h = Sheet1.header()
        s = Sheet1.shape()
        print(h, s)

    sheets.batch_update(
        sheet_id,
        {
            Sheet1[6, ...]: [["Gay vibes", "wow"]],
            "7:7": [["Gayer vibes", "wower"]],
            Sheet1[-90, 1:3]: [["I'm down here", "wow I'm here"]],
            Sheet1[8, ...]: [
                {"Heyy": "99", "These Vibes...": "hey", "9": "wow", "not there": "OMG"}
            ],
        },
        align_columns=True,
    )

    Sheet1[-1, -1].update([["Heyy ;)))"]])

    slc = SheetSlice[..., ...]
    df = Sheet1[slc].to_frame()
    df[8] = "Frunk!"

    Sheet1.update(sheets.from_frame(df))
