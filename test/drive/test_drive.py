from pathlib import Path
from typing import *

from googleapiutils2.drive.drive import Drive
from googleapiutils2.utils import GoogleMimeTypes, get_oauth2_creds


config_path = Path("auth/friday-institute-reports.credentials.json")
creds = get_oauth2_creds(client_config=config_path)
drive = Drive(creds=creds)


def test_lists():
    test_folder_url = (
        "https://drive.google.com/drive/u/0/folders/1lWgLNquLCwKjW4lenekduwDZ3J7aqCZJ"
    )

    files = drive.list_children(parent_id=test_folder_url)
    for file in files:
        print(file)

    perms = drive.permissions_list(test_folder_url)
    for p in perms:
        print(p)


def test_upload():
    ECF_FOLDER = (
        "https://drive.google.com/drive/u/0/folders/1fB2mj-hl7KIduiNidbWLlMAFXZ76GmN8"
    )
    filepath = "/Users/mkbabb/Programming/ecf-dedup/data/ECF Deduped.csv"
    t_file = drive.upload_file(filepath=filepath, parents=[ECF_FOLDER], update=True)

    print(t_file)


def test_recursive_download():
    shodan_folder = (
        "https://drive.google.com/drive/u/0/folders/1wCWnDb-7dmOGJltGu_zziWU4nVYwr9Rl"
    )
    drive.download(
        out_filepath="./data/shodan_data",
        file_id=shodan_folder,
        mime_type=GoogleMimeTypes.folder,
        recursive=True,
    )


def test_nested_files():
    FOLDER_URL = (
        "https://drive.google.com/drive/u/0/folders/1lWgLNquLCwKjW4lenekduwDZ3J7aqCZJ"
    )

    filepath = Path("toasting")
    parent_folder = drive.create(
        filepath=filepath,
        create_folders=True,
        parents=[FOLDER_URL],
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
