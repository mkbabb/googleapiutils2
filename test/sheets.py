from pathlib import Path

import pandas as pd

from googleapiutils.sheets.sheets import Sheets
from googleapiutils.utils import get_oauth2_creds

dir = Path("auth")
config_path = dir.joinpath("friday-institute-reports.credentials.json")

creds = get_oauth2_creds(client_config=config_path)


sheets = Sheets(creds=creds)

url = "https://docs.google.com/spreadsheets/d/11hX5E0V-OwRI9wBvVRIh98mlBlN_NwVivaXhk0NTKlI/edit#gid=150061767"
t = sheets.get(url, "Config")
df = pd.DataFrame(t["values"])
df = df.rename(columns=df.iloc[0]).drop(df.index[0])

print(df)
