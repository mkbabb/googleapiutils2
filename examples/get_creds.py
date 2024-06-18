from __future__ import annotations

import os
from googleapiutils2 import Drive, get_oauth2_creds

client_config_path = os.environ.get("GOOGLE_API_CLIENT_CREDENTIALS")

creds = get_oauth2_creds(client_config=client_config_path)
drive = Drive()

for file in drive.list():
    print(file)
