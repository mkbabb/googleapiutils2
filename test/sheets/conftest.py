from __future__ import annotations

from typing import *

import pytest

from googleapiutils2 import Drive, GoogleMimeTypes

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File


@pytest.fixture(scope="function", autouse=True)
def test_sheet(drive: Drive, google_folders: dict[str, File]):
    sheets_folder = google_folders["sheets"]

    test_sheet = drive.create(
        filepath="test_sheet",
        mime_type=GoogleMimeTypes.sheets,
        parents=[sheets_folder["id"]],
        get_extant=True,
    )

    yield test_sheet

    drive.delete(test_sheet["id"])
