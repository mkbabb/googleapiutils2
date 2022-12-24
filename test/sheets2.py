from pathlib import Path
from typing import *

from googleapiutils.sheets import Sheets
from googleapiutils.utils import GoogleMimeTypes, get_oauth2_creds

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07HFq7wSbYPsuwBoJcd1E1R4F14RkeN-3GUyzvWepw/edit#gid=0"

dir = Path("auth")

config_path = dir.joinpath("friday-institute-reports.credentials.json")

creds = get_oauth2_creds(client_config=config_path)
sheets = Sheets(creds=creds)


values = sheets.values(SHEET_URL)["Sheet1", 1, 1]
df = sheets.to_frame(values)

print(df)
