from __future__ import annotations

import os
import time
from pathlib import Path
from typing import *

from googleapiutils2 import Sheets, SheetSlice, SheetsValueRange, get_oauth2_creds

config_path = Path(os.environ.get("GOOGLE_API_CREDENTIALS", ""))
creds = get_oauth2_creds(client_config=config_path)

sheets = Sheets(creds=creds)

sheet_id = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

Sheet1 = SheetsValueRange(sheets, sheet_id, sheet_name="Sheet1")

rows = [
    {
        "Heyy": "99",
        "Gay Vibes": "hey",
        "9": "wow",
        "not there": "OMG",
        "Column: NOOOOOOOOOOOOOOOOOOOOOOOOOOOO": "ok",
    },
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

batches = {}
for i in range(100):
    key = "Heyyyyyy"
    if i > 0 and i % 10 == 0:
        key += f"{i}"

    row = {
        key: "go frunk yourself",
    }
    batches[Sheet1[7 + i, ...]] = [row]


sheets.batch_update(sheet_id, batches)

# time.sleep(10)

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
sheets.resize_columns(sheet_id, Sheet1.sheet_name)

time.sleep(10)

sheets.clear(sheet_id, "Sheet1")
