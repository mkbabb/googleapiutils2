from pathlib import Path
from typing import *

from googleapiutils2.drive.drive import Drive
from googleapiutils2.utils import GoogleMimeTypes, get_oauth2_creds


config_path = Path("auth/friday-institute-reports.credentials.json")
creds = get_oauth2_creds(client_config=config_path)
drive = Drive(creds=creds)


# shodan_folder = (
#     "https://drive.google.com/drive/u/0/folders/1wCWnDb-7dmOGJltGu_zziWU4nVYwr9Rl"
# )
# drive.download(
#     out_filepath="./data/heyy",
#     file_id=shodan_folder,
#     mime_type=GoogleMimeTypes.folder,
#     recursive=True,
# )

folder = "https://drive.google.com/drive/u/0/folders/1lWgLNquLCwKjW4lenekduwDZ3J7aqCZJ"

filepath = Path("toasting")
parent_folder = drive.create(
    filepath=filepath,
    create_folders=True,
    parents=[folder],
    mime_type=GoogleMimeTypes.folder,
    update=True,
)

filepath = Path("hey/what")
t_file = drive.create(
    filepath=filepath,
    create_folders=True,
    parents=[parent_folder["id"]],
    mime_type=GoogleMimeTypes.sheets,
    update=True,
)

filepath = filepath / "who!!!!/b's a really cool thing"
t_file = drive.create(
    filepath=filepath,
    create_folders=True,
    parents=[parent_folder["id"]],
    mime_type=GoogleMimeTypes.sheets,
    update=True,
)

drive.permissions_create(folder, "mike7400@gmail.com", sendNotificationEmail=False)
perms = drive.permissions_list(folder)
for p in perms:
    print(p)
