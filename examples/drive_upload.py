from __future__ import annotations

from typing import *
import requests

from googleapiutils2 import Drive, GoogleMimeTypes, get_oauth2_creds, Groups

creds = get_oauth2_creds()


drive = Drive(creds=creds)
# groups = Groups(creds=creds)

# group = groups.get(group_id="knowbe4_k12admins@lists.ncsu.edu")


# for i in groups.members_list(group_key="knowbe4_k12admins@lists.ncsu.edu"):
#     print(i)

drive.upload(
    filepath="examples/hey",
    name="Asset 1",
    to_mime_type=GoogleMimeTypes.docs,
)
