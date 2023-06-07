import os
from pathlib import Path
from typing import *

from googleapiutils2 import Drive, Sheets, get_oauth2_creds, GoogleMimeTypes
from googleapiutils2.utils import hex_to_rgb

config_path = Path(os.environ.get("GOOGLE_API_CREDENTIALS"))
creds = get_oauth2_creds(client_config=config_path)

drive = Drive(creds=creds)
sheets = Sheets(creds=creds)

sheet_url = "https://docs.google.com/spreadsheets/d/14WRf-S-T5MFkk4zOm0Ejsr-3g83EYEQ6dUle9VrDp6I/edit#gid=0"
file = drive.get(sheet_url)

t = hex_to_rgb("#ffffff")
print(t)
