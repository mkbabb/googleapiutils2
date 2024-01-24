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
from typing import *
import json

from googleapiutils2 import Sheets, SheetSlice, SheetsValueRange

sheets = Sheets()

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

Sheet1 = SheetsValueRange(sheets, SHEET_URL, sheet_name="Sheet1")

sheets.add(SHEET_URL, ["Sheet99", "Sheet100"])

sheets.delete(SHEET_URL, ["Sheet99", "Sheet101"])

sheets.reset_sheet(SHEET_URL, Sheet1.sheet_name, preserve_header=True)


rows = [
    {
        "Column 1": "99",
        "Column 2": "hey",
        "Column 3": "wow",
        "Column 4": "OMG",
        "Column 5": "ok",
    },
]

Sheet1[2:3, ...].update(rows)
Sheet1[4:5, ...].update(rows)
Sheet1[4, "A"].update([["Frunk!"]])


sheets.update(
    SHEET_URL,
    Sheet1[5, ...],
    values=[[11, 22, 33]],
)


for _ in range(10):
    values = [list(range(64))]
    sheets.append(
        SHEET_URL,
        Sheet1.sheet_name,
        values=values,
    )

Sheet1[5:, ...].clear()


for i in range(100):
    batches: dict = {}
    key = "Heyyyyyy"
    if i > 0 and i % 10 == 0:
        key += f"{i}"

    row = {
        key: "go frunk yourself",
    }
    batches[Sheet1[7 + i, ...]] = [row]
    sheets.batch_update(SHEET_URL, batches, batch_size=10, ensure_shape=True)

sheets.batched_update_remaining(SHEET_URL)


# time.sleep(10)

sheets.batch_update(
    SHEET_URL,
    {
        Sheet1[6, ...]: [["Gay vibes", "wow"]],
        "7:7": [["Gayer vibes", "wower"]],
        Sheet1[-90, 1:3]: [["I'm down here", "wow I'm here"]],
        Sheet1[8, ...]: [
            {"Heyy": "99", "These Vibes...": "Ok vibes...", "Heyyyyyy90": "Ok"}
        ],
    },
    align_columns=True,
)

Sheet1[-1, -1].update([["Heyy ;)))"]])

slc = SheetSlice[..., ...]
df = Sheet1[slc].to_frame()
if df is None:
    raise ValueError("df is None")

df[8] = "Frunk!"
data = sheets.from_frame(df, True)
Sheet1.update(data)

sheets.append(
    SHEET_URL,
    "Sheet1",
    values=[
        {
            "Column 1": "99",
        }
    ],
)


sheemt = sheets.get(
    spreadsheet_id=SHEET_URL,
    name="Sheet1",
    include_grid_data=True,
    ranges=Sheet1[1, ...],
)

# dump to a json file:
with open("sheet.json", "w") as f:
    json.dump(sheemt, f, indent=4)

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

sheets_format_list = sheets.get_format(
    spreadsheet_id=SHEET_URL, range_name=Sheet1[1, ...]
)
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
