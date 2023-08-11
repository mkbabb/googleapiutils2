from __future__ import annotations

import os
from pathlib import Path
from typing import *

import pytest

from googleapiutils2.drive import Drive
from googleapiutils2.sheets import Sheets
from googleapiutils2.utils import Credentials, GoogleMimeTypes, get_oauth2_creds


@pytest.fixture(scope="session", autouse=True)
def creds():
    config_path = Path(
        os.environ.get("GOOGLE_API_CREDENTIALS", "auth/credentials.json")
    )
    return get_oauth2_creds(client_config=config_path)


@pytest.fixture(scope="session", autouse=True)
def drive(creds: Credentials):
    return Drive(creds=creds)


@pytest.fixture(scope="session", autouse=True)
def sheets(creds: Credentials):
    return Sheets(creds=creds)


@pytest.fixture(scope="session", autouse=True)
def google_folders(drive: Drive):
    test_folder_path = Path(os.environ.get("GOOGLE_API_TEST_PATH", "googleapiutils2"))

    sheets_folder = test_folder_path / "sheets"
    drive_folder = test_folder_path / "drive"

    folder_paths = [sheets_folder, drive_folder]

    google_folders = {
        folder_path.name: drive.create(
            name=folder_path,
            mime_type=GoogleMimeTypes.folder,
            get_extant=True,
            recursive=True,
        )
        for folder_path in folder_paths
    }

    yield google_folders

    for folder in google_folders.values():
        drive.delete(folder["id"])
