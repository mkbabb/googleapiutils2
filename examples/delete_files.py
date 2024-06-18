from __future__ import annotations

import json

from loguru import logger

from googleapiutils2 import Drive

drive = Drive()

file_count = 0
# find **files** ONLY owned by the service account
# and not shared with anyone else
total_size_in_mb = 0.0
query = "mimeType != 'application/vnd.google-apps.folder' and trashed = false"

drive.empty_trash()

about = drive.about_get()
with open("./data/about.json", "w") as f:
    json.dump(about, f)

for file in drive.list(query=query, order_by="modifiedTime asc"):
    size = int(file.get("size", 0))
    size_in_mb = round(size / 1024 / 1024, 2)

    permissions = file.get("permissions", file.get("permissionIds", []))

    logger.info(f"Checking {file['name']}...; size {size_in_mb} MB")

    if len(permissions) > 1:
        logger.info(f"Skipping {file['name']}: shared with {len(permissions)}")
        continue

    logger.info(f"Deleting {file['name']}...")

    drive.delete(file["id"])

    file_count += 1
    total_size_in_mb += size_in_mb

    logger.info(f"Deleted {file_count} files; total size deleted {total_size_in_mb} MB")
