from pathlib import Path
from typing import *

import pandas as pd

from googleapiutils2.sheets.sheets import Sheets
from googleapiutils2.utils import get_oauth2_creds


def test_values():
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

    config_path = Path("auth/friday-institute-reports.credentials.json")

    creds = get_oauth2_creds(client_config=config_path)
    sheets = Sheets(creds=creds)

    values_obj = sheets.values(SHEET_URL, "Sheet1")
    print(values_obj)


def test_create_copy_to():
    config_path = Path("auth/friday-institute-reports.credentials.json")
    creds = get_oauth2_creds(client_config=config_path)
    sheets = Sheets(creds=creds)

    CONFIG_URL = "https://docs.google.com/spreadsheets/d/11hX5E0V-OwRI9wBvVRIh98mlBlN_NwVivaXhk0NTKlI/edit#gid=150061767"

    config_sheet = sheets.get_sheet(CONFIG_URL, name="Config")
    my_sheet = sheets.create("My Sheet")

    copied_sheet = sheets.copy_to(
        from_spreadsheet_id=CONFIG_URL,
        from_sheet_id=config_sheet["properties"]["sheetId"],
        to_spreadsheet_id=my_sheet["spreadsheetId"],
    )

    old_df = sheets.to_frame(sheets.values(CONFIG_URL))

    new_df = sheets.to_frame(
        sheets.values(my_sheet["spreadsheetId"], copied_sheet["title"])
    )

    assert old_df.equals(new_df)
