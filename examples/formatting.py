"""
Demonstrates a few of the features of the Sheets, SheetsValueRange, and SheetSlice classes.

- Initialize a connection to a given Google Sheet.
- Perform various operations, including:
    - Resetting the sheet.
    - Updating individual cells and ranges.
    - Using batch updates to modify multiple rows simultaneously.
    - Clearing specified rows.
    - Formatting the sheet, including bolding text and resizing columns.
    - Converting data to a DataFrame and updating the sheet from that DataFrame.
    - Appending values to the sheet.

The examples encompass common CRUD operations (Create, Read, Update, Delete)
and illustrate advanced techniques such as slicing, batched updates, alignment, and formatting.
"""

from __future__ import annotations

from googleapiutils2 import Sheets, SheetsValueRange

sheets = Sheets()

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

Sheet1 = SheetsValueRange(sheets, SHEET_URL, sheet_name="Sheet100")

sheets.format(
    SHEET_URL,
    [Sheet1[2, ...], Sheet1[3, ...]],
    background_color="#d48686",
)

sheets.format(
    SHEET_URL,
    [Sheet1[2, ...], Sheet1[3, ...]],
    bold=True,
    number_format={
        # add a pattern to make all numbers 6 chars, padded with 5 0s:
        "pattern": "0000##",
        "type": "NUMBER",
    },
)

sheets_format_list = sheets.get_format(spreadsheet_id=SHEET_URL, range_name=Sheet1[1, ...])
sheets_format = sheets_format_list[0]


# sheets.format(
#     SHEET_URL,
#     Sheet1[1, 1],
#     cell_format={
#         "textFormat": {
#             "fontSize": 24,
#         }
#     },
# )


sheets.format(
    SHEET_URL,
    Sheet1[1, ...],
    cell_format={
        "textFormat": {
            "fontFamily": "Times New Roman",
            "fontSize": 16,
        }
    },
)


sheets.resize_dimensions(SHEET_URL, Sheet1.sheet_name, sizes=None)
