from pathlib import Path
from typing import *

from googleapiutils2.sheets import Sheets, SheetSlice, SheetsValueRange
from googleapiutils2.utils import get_oauth2_creds

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

config_path = Path("auth/friday-institute-reports.credentials.json")

creds = get_oauth2_creds(client_config=config_path)
sheets = Sheets(creds=creds)

Sheet = SheetsValueRange(sheets, SHEET_URL)

Sheet1 = Sheet["Sheet1"]


Sheet1[4, "A"].update([["Frunk!"]], auto_batch_size=1)

sheets.update(
    SHEET_URL,
    Sheet1[5, ...],
    values=[[11, 22, 33]],
)

Sheet1[6:, ...].clear()


sheets.batch_update(
    SHEET_URL,
    {
        Sheet1[6, ...]: [["Gay vibes", "wow"]],
        "7:7": [["Gayer vibes", "wower"]],
        Sheet1[-90, 1:3]: [["I'm down here", "wow I'm here"]],
    },
)

Sheet1[-1, -1].update([["Heyy ;)))"]])


slc = SheetSlice[..., ...]
df = Sheet1[slc].to_frame()
print(df)

df["Heyy"] = "Frunk!"

Sheet1.update(sheets.from_frame(df))
