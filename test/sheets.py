from pathlib import Path

import pandas as pd

from googleapiutils2.sheets.sheets import Sheets
from googleapiutils2.utils import get_oauth2_creds

config_path = Path("auth/friday-institute-reports.credentials.json")
creds = get_oauth2_creds(client_config=config_path)
sheets = Sheets(creds=creds)

url = "https://docs.google.com/spreadsheets/d/11hX5E0V-OwRI9wBvVRIh98mlBlN_NwVivaXhk0NTKlI/edit#gid=150061767"
df = sheets.to_frame(sheets.values(url, "Config"))

print(df)
