from __future__ import annotations

from typing import *

from googleapiutils2 import Drive, Sheets, SheetSlice

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File


def test_values(test_sheet: File, sheets: Sheets):
    sheet_id = test_sheet["id"]

    values = sheets.values(sheet_id, "Sheet1").get("values", [])

    assert len(values) == 0

    updates = [["a", "b", "c"], [1, 2, 3]]
    sheets.update(sheet_id, "Sheet1", updates)

    values = sheets.values(sheet_id, "Sheet1")["values"]

    assert len(values) == 2
    assert values == updates


def test_create_copy_to(test_sheet: File, sheets: Sheets, drive: Drive):
    sheet_id = test_sheet["id"]

    updates = [["a", "b", "c"], [1, 2, 3]]
    sheets.update(sheet_id, "Sheet1", updates)

    sheet_obj = sheets.get_by_sheet_name(sheet_id, name="Sheet1")
    new_sheet = sheets.create("My Sheet")

    copied_sheet = sheets.copy_to(
        from_spreadsheet_id=sheet_id,
        from_sheet_id=sheet_obj["properties"]["sheetId"],
        to_spreadsheet_id=new_sheet["spreadsheetId"],
    )

    old_df = sheets.to_frame(sheets.values(sheet_id))

    new_df = sheets.to_frame(
        sheets.values(new_sheet["spreadsheetId"], copied_sheet["title"])
    )

    assert old_df.equals(new_df)

    drive.delete(new_sheet["spreadsheetId"])


def test_update_align_columns(test_sheet: File, sheets: Sheets, drive: Drive):
    sheet_id = test_sheet["id"]

    updates = [["a", "b", "c"], [1, 2, 3]]
    sheets.update(sheet_id, "Sheet1", updates)

    slc = SheetSlice["Sheet1", 2:, ...]

    updates = [
        {
            "c": 6,
        }
    ]
    sheets.update(sheet_id, slc, updates)
    values = sheets.values(sheet_id, slc)["values"]

    assert values[0][2] == 6

    sheets.update(sheet_id, SheetSlice["Sheet1", 1:, ...], [["a", "b", "c", "d"]])

    updates = [
        {
            "d": 7,
        }
    ]
    sheets.update(sheet_id, slc, updates)
    values = sheets.values(sheet_id, slc)["values"]

    assert values[0][3] == 7
