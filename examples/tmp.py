from __future__ import annotations

from typing import *

from googleapiutils2 import Drive, GoogleMimeTypes, Sheets, SheetSlice, get_oauth2_creds

creds = get_oauth2_creds()
drive = Drive(creds=creds)

drive.upload(
    filepath="examples/hey.txt",
    name="Asset 1",
    mime_type=GoogleMimeTypes.docs,
)
