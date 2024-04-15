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



VERSION = "directory_v1"

DEFAULT_FIELDS = "*"