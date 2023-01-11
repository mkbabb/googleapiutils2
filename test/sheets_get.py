from pathlib import Path
from typing import *

from googleapiutils2.sheets import Sheets, SheetSlice, SheetsValueRange
from googleapiutils2.utils import get_oauth2_creds


def main():
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

    config_path = Path("auth/friday-institute-reports.credentials.json")

    creds = get_oauth2_creds(client_config=config_path)
    sheets = Sheets(creds=creds)

    v1 = sheets.values(SHEET_URL, "Sheet1")
    print(v1)


if __name__ == "__main__":
    main()
