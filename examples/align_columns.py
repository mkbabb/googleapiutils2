from typing import *
import json
from googleapiutils2 import Sheets, SheetSlice, SheetsValueRange

sheets = Sheets()

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

Sheet1 = SheetsValueRange(sheets, SHEET_URL, sheet_name="Sheet1")
# sheets.reset_sheet(SHEET_URL, Sheet1.sheet_name, preserve_header=True)


rows = [
    {
        "Column 1": "99",
        "Column 5": "ok",
    },
]

sheets.update(
    spreadsheet_id=SHEET_URL,
    range_name=Sheet1.sheet_name,
    values=rows,
)
