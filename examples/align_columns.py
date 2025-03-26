from __future__ import annotations

import json
import random
import string

from googleapiutils2 import Sheets, SheetSlice, SheetsValueRange


# fn to generate a random blob of string data, up to size in bytes
def random_string(size: int = 10) -> str:
    return "".join(random.choices(string.ascii_letters, k=size))


sheets = Sheets()

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

Sheet1 = SheetsValueRange(sheets, SHEET_URL, sheet_name="Sheet6")
# sheets.reset_sheet(SHEET_URL, Sheet1.sheet_name, preserve_header=True)


row_count = 10000
col_count = 100
rows = [
    {f"Column {j}": f"{i}__{random_string(10)}__{i}" for j in range(col_count)}
    for i in range(row_count)
]


sheets.reset_sheet(SHEET_URL, Sheet1.sheet_name)


#  total size of the payload in bytes and MB:
total_size = sum(len(json.dumps(row)) for row in rows)

print(f"Total size of payload: {total_size} bytes, {total_size / 1024 / 1024} MB")

tmp = SheetSlice[row_count, col_count]

sheets.update(
    spreadsheet_id=SHEET_URL,
    range_name=Sheet1.sheet_name,
    values=rows,
)

sheets.batch_update(
    spreadsheet_id=SHEET_URL,
    data={
        "Sheet6!1:1": [["hey"] * col_count],
        "Sheet6!2:2": [["hey"] * col_count],
        "Sheet6!3:3": [["hey"] * col_count],
        "Sheet6!4:4": [["hey"] * col_count],
        "Sheet6!5:5": [["hey"] * col_count],
        "Sheet6!6:6": [["hey"] * col_count],
        # "Sheet6!A7:Z": [["hey"] * col_count],
        # "Sheet6!A8:Z": [["hey"] * col_count],
    },
    chunk_size_bytes=10,
)


sheets.format_header(
    spreadsheet_id=SHEET_URL,
    sheet_name=Sheet1.sheet_name,
)
