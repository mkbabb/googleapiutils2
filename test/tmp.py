from pathlib import Path
from typing import *

from googleapiutils.drive import Drive
from googleapiutils.utils import GoogleMimeTypes, get_oauth2_creds

dir = Path("auth")

config_path = dir.joinpath("friday-institute-reports.credentials.json")

creds = get_oauth2_creds(client_config=config_path)
drive = Drive(creds=creds)


# download_folder = (
#     "https://drive.google.com/drive/u/0/folders/1wCWnDb-7dmOGJltGu_zziWU4nVYwr9Rl"
# )

# drive.download("heyy", download_folder, GoogleMimeTypes.folder, True)

folder = "https://drive.google.com/drive/u/0/folders/1lWgLNquLCwKjW4lenekduwDZ3J7aqCZJ"

filepath = "googleapiutils"
parent_folder = drive.create(
    filepath=filepath,
    create_folders=True,
    parents=[folder],
    mime_type=GoogleMimeTypes.folder,
    update=True,
)

filepath = "googleapiutils/hey/what"
t_file = drive.create(
    filepath=filepath,
    create_folders=True,
    parents=[parent_folder],
    mime_type=GoogleMimeTypes.sheets,
    update=True,
)


filepath = "googleapiutils/hey/what/who!!!!/b's a really cool thing"
t_file = drive.create(
    filepath=filepath,
    create_folders=True,
    parents=[parent_folder],
    mime_type=GoogleMimeTypes.sheets,
    update=True,
)

drive.permissions_create(folder, "mike7400@gmail.com", sendNotificationEmail=False)
perms = drive.permissions_list(folder)

for p in perms:
    print(p)
