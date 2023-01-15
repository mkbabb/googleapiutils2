from __future__ import annotations

from typing import *

import pytest

from googleapiutils2.drive import Drive, GoogleMimeTypes

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File


@pytest.fixture(scope="function", autouse=True)
def test_folder(drive: Drive, google_folders: dict[str, File]):
    drive_folder = google_folders["drive"]

    test_folder = drive.create(
        filepath="test_folder",
        mime_type=GoogleMimeTypes.folder,
        parents=[drive_folder["id"]],
        update=True,
    )

    yield test_folder

    drive.delete(test_folder["id"])
