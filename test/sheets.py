from pathlib import Path

import pandas as pd

from googlea_pi_utils.sheets import Sheets
from googlea_pi_utils.utils import get_oauth2_creds

dir = Path("auth")
config_path = dir.joinpath("friday-institute-reports.credentials.json")

creds = get_oauth2_creds(client_config=config_path)


sheets = Sheets(creds=creds)

url = "https://docs.google.com/spreadsheets/d/11hX5E0V-OwRI9wBvVRIh98mlBlN_NwVivaXhk0NTKlI/edit#gid=150061767"
df = sheets.to_frame(sheets.get(url, "Config"))

print(df)
