from __future__ import annotations

from googleapiutils2 import Drive, GoogleMimeTypes, get_oauth2_creds

creds = get_oauth2_creds()


drive = Drive(creds=creds)

drive.upload(
    filepath="examples/hey",
    name="Asset 1",
    to_mime_type=GoogleMimeTypes.docs,
)
