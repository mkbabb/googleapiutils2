from __future__ import annotations

from enum import Enum
from typing import *

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import (
        DriveList,
        DriveResource,
        File,
        FileList,
        Permission,
        PermissionList,
    )


class DataFrameExportFileTypes(Enum):
    csv = "csv"
    xlsx = "xlsx"
    json = "json"
    sheets = "sheets"


VERSION = "v3"

DOWNLOAD_LIMIT = 4 * 10**6  # size in bytes


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
