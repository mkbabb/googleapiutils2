from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import (
        DriveList,
        DriveResource,
        File,
        FileList,
        Permission,
        PermissionList,
    )


VERSION = "directory_v1"

DEFAULT_FIELDS = "*"
