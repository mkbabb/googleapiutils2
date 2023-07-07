from __future__ import annotations

from typing import *

from ..utils import GoogleMimeTypes

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import (
        DriveList,
        DriveResource,
        File,
        FileList,
        Permission,
        PermissionList,
    )

VERSION = "v3"

DOWNLOAD_LIMIT = 4 * 10**6  # size in bytes

DEFAULT_DOWNLOAD_CONVERSION_MAP = {
    GoogleMimeTypes.sheets: (GoogleMimeTypes.xlsx, ".xlsx"),
    GoogleMimeTypes.docs: (GoogleMimeTypes.doc, ".docx"),
    GoogleMimeTypes.slides: (GoogleMimeTypes.pdf, ".pdf"),
}

DEFAULT_FIELDS = "*"


def create_listing_fields(fields: str) -> str:
    if DEFAULT_FIELDS in fields:
        return fields

    REQUIRED_FIELDS = ["nextPageToken", "kind"]

    for r in REQUIRED_FIELDS:
        if r not in fields:
            fields += f",{r}"

    return fields


def list_drive_items(
    list_func: Callable[[str | None], FileList | PermissionList | Any]
) -> Iterable[FileList | PermissionList | list]:
    page_token = None
    while True:
        response = list_func(page_token)
        yield response
        if (page_token := response.get("nextPageToken", None)) is None:
            break
