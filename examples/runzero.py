from __future__ import annotations

import asyncio
import os
import pathlib
import tempfile
from datetime import datetime
from typing import *

import requests
from aiohttp import ClientSession
from loguru import logger

from googleapiutils2 import Drive, GoogleMimeTypes, Sheets

if TYPE_CHECKING:
    from googleapiutils2 import File

logger.add("./log/log.log", rotation="1 MB")


async def create_folder_for_org(o: dict, drive: Drive, base_folder: str):
    name, oid = o["name"], o["id"]
    logger.info(f"Creating folder for {name}...")

    folder = drive.create(
        name=name,
        mime_type=GoogleMimeTypes.folder,
        parents=base_folder,
        get_extant=True,
    )

    logger.info(f"Created folder for {name}")

    return (name, oid), folder


async def download_and_upload(
    session: ClientSession,
    base_url: str,
    endpoint: str,
    oid: str,
    headers: dict,
    folder: dict,
    name: str,
):
    filename = endpoint.split("/")[-1]
    if filename == "{org_id}":
        filename = "org_info"

    url = (base_url + endpoint).format(org_id=oid)

    logger.info(f"Downloading {filename}")

    try:
        async with session.get(url, headers=headers, params={"_oid": oid}) as r:
            r.raise_for_status()
            text = await r.text()
    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}")
        return

    size_in_mb = round(len(text) / 1024 / 1024, 4)
    logger.info(f"Downloaded {filename}: size {size_in_mb} MB")

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(text)
        temp_filepath = f.name

    filepath = pathlib.Path(f"./data/{name}/{filename}")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(text)

    logger.info(f"Uploading {filename} to {folder['name']}...")

    try:
        drive.upload(
            filepath=temp_filepath,
            name=filename,
            to_mime_type=GoogleMimeTypes.csv,
            parents=folder["id"],
        )
        logger.info(f"Uploaded {name} to {folder['name']}")
    except Exception as e:
        logger.warning(f"Failed to upload {name} to {folder['name']}: {e}")


async def process_org_folder(
    base_url: str, org_folders: dict, endpoints: list, headers: dict
):
    async def create_done_file(folder: File):
        logger.info(f"Finished processing {folder['name']}: {folder['webViewLink']}...")

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(f"Finished at {datetime.now()}")

            drive.upload(
                filepath=f.name,
                name="done",
                to_mime_type=GoogleMimeTypes.txt,
                parents=folder["id"],
            )

    async with ClientSession() as session:
        tasks = []

        for (name, oid), folder in org_folders.items():
            logger.info(f"Processing {name}: {folder['webViewLink']}...")

            if (
                done_file := next(drive.list(folder["id"], query="name = 'done'"), None)
            ) is not None:
                logger.info(f"Skipping {name} as it is already processed")
                continue

            for endpoint in endpoints:
                task = asyncio.create_task(
                    download_and_upload(
                        session=session,
                        base_url=base_url,
                        endpoint=endpoint,
                        oid=oid,
                        headers=headers,
                        folder=folder,
                        name=name,
                    )
                )
                tasks.append(task)

        await asyncio.gather(*tasks)

        await create_done_file(folder)


drive = Drive()
sheets = Sheets()

base_folder = (
    "https://drive.google.com/drive/u/0/folders/1JGyx-4tsi1VME0Pab-cjX9ygs_kkgGj1"
)

token = os.getenv("RUNZERO_TOKEN")

base_url = "https://console.runzero.com/api/v1.0/"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

endpoints = [
    "export/org/assets.csv",
    "export/org/services.csv",
    "export/org/sites.csv",
    "export/org/wireless.csv",
    "export/org/software.csv",
    "export/org/vulnerabilities.csv",
    "export/org/users.csv",
    "export/org/groups.csv",
    "account/orgs/{org_id}",
    "org/agents",
    "org/tasks",
]

get_all_orgs_endpoint = "account/orgs"

orgs = requests.get(base_url + get_all_orgs_endpoint, headers=headers).json()

orgs = orgs[:2]

logger.info(f"Got {len(orgs)} orgs")

org_folders = dict(
    (
        asyncio.run(create_folder_for_org(o, drive=drive, base_folder=base_folder))
        for o in orgs
    )
)

asyncio.run(
    process_org_folder(
        base_url=base_url,
        org_folders=org_folders,
        endpoints=endpoints,
        headers=headers,
    )
)
