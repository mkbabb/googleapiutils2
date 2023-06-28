from __future__ import annotations

import os
from pathlib import Path
from typing import *

from googleapiutils2 import Sheets, SheetSlice, SheetsValueRange, get_oauth2_creds

config_path = Path(os.environ.get("GOOGLE_API_CREDENTIALS", ""))
creds = get_oauth2_creds(client_config=config_path)

sheets = Sheets(creds=creds)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

Sheet1 = SheetsValueRange(sheets, SHEET_URL, sheet_name="Sheet1")

sheets.reset_sheet(SHEET_URL, Sheet1.sheet_name)


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

sheets.format(SHEET_URL, Sheet1[2:, ...], bold=True)

sheets.resize_columns(SHEET_URL, Sheet1.sheet_name, width=None)
