from pathlib import Path

import pandas as pd
from googleapiutils.sheets import Sheets, get_oauth2_creds

name = Path("friday-institute-reports")
dir = Path("auth")

token_path = dir.joinpath(name.with_suffix(".token.pickle"))
config_path = dir.joinpath(name.with_suffix(".credentials.json"))

google_creds = get_oauth2_creds(
    token_path=token_path, client_config=config_path, is_service_account=True
)

sheets = Sheets(google_creds)

url = "https://docs.google.com/spreadsheets/d/11hX5E0V-OwRI9wBvVRIh98mlBlN_NwVivaXhk0NTKlI/edit#gid=150061767"
t = sheets.get(url, "Config")
df = pd.DataFrame(t["values"])
df = df.rename(columns=df.iloc[0]).drop(df.index[0])

print(df)
