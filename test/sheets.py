import asyncio
from collections import defaultdict
from pathlib import Path
from typing import *

import pandas as pd

from googleapiutils2.sheets.sheets import Sheets
from googleapiutils2.utils import get_oauth2_creds


async def main():
    config_path = Path("auth/friday-institute-reports.credentials.json")
    creds = get_oauth2_creds(client_config=config_path)
    sheets = Sheets(creds=creds)

    config_url = "https://docs.google.com/spreadsheets/d/11hX5E0V-OwRI9wBvVRIh98mlBlN_NwVivaXhk0NTKlI/edit#gid=150061767"

    config_sheet = await sheets.get_sheet(config_url, name="Config")
    my_sheet = await sheets.create("My Sheet")

    copied_sheet = await sheets.copy_to(
        from_spreadsheet_id=config_url,
        from_sheet_id=config_sheet["properties"]["sheetId"],
        to_spreadsheet_id=my_sheet["spreadsheetId"],
    )

    df = sheets.to_frame(
        await sheets.values(my_sheet["spreadsheetId"], copied_sheet["title"])
    )

    print(df)


if __name__ == "__main__":
    asyncio.run(main())
