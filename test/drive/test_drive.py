from __future__ import annotations

from pathlib import Path
from typing import *

from googleapiutils2 import Drive, GoogleMimeTypes

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File


def test_lists(drive: Drive):
    test_folder_url = (
        "https://drive.google.com/drive/u/0/folders/1lWgLNquLCwKjW4lenekduwDZ3J7aqCZJ"
    )

    files = drive.list_children(parent_id=test_folder_url)
    for file in files:
        print(file)

    perms = drive.permissions_list(test_folder_url)
    for p in perms:
        print(p)


def test_upload(drive: Drive):
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
    # drive.download(
    #     out_filepath="./data/shodan_data",
    #     file_id=shodan_folder,
    #     mime_type=GoogleMimeTypes.folder,
    #     recursive=True,
    # )


def test_nested_files(test_folder: File, drive: Drive):
    folder_id = test_folder["id"]

    filepath = Path("toasting")
    parent_folder = drive.create(
        filepath=filepath,
        create_folders=True,
        parents=[folder_id],
        mime_type=GoogleMimeTypes.folder,
        update=True,
    )
    assert parent_folder["name"] == filepath.name

    name = "what"
    filepath = Path(f"hey/{name}")
    t_file = drive.create(
        filepath=filepath,
        create_folders=True,
        parents=[parent_folder["id"]],
        mime_type=GoogleMimeTypes.sheets,
        update=True,
    )
    assert t_file["name"] == name

    name = "b's a really cool thing"
    filepath = filepath / f"who!!!!/{name}"
    t_file = drive.create(
        filepath=filepath,
        create_folders=True,
        parents=[parent_folder["id"]],
        mime_type=GoogleMimeTypes.sheets,
        update=True,
    )
    assert t_file["name"] == name
