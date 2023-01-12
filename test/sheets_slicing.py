
from pathlib import Path
from typing import *

from googleapiutils2.sheets import Sheets, SheetSlice, SheetsValueRange
from googleapiutils2.utils import get_oauth2_creds


def main():
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

    config_path = Path("auth/friday-institute-reports.credentials.json")

    creds = get_oauth2_creds(client_config=config_path)
    sheets = Sheets(creds=creds)

    Sheet1 = SheetsValueRange(sheets, SHEET_URL, sheet_name="Sheet1").sync()

    rows = [
        {
            "Heyy": "99",
            "Gay Vibes": "hey",
            "9": "wow",
            "not there": "OMG"
        },
        {
            "5": "99",
            "6": "hey",
            "9": "wow",
        },
    ]
    Sheet1[2:3, ...].update(rows, auto_batch_size=2)
    Sheet1[4:5, ...].update(rows, auto_batch_size=2)

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
    df[8] = "Frunk!"

    Sheet1.update(sheets.from_frame(df))


if __name__ == "__main__":
    main()
