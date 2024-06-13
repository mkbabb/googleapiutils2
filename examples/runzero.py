from __future__ import annotations

import asyncio
import gzip
import http
import os
import pathlib
import tarfile
import tempfile
from datetime import datetime
from typing import *

import requests
from aiohttp import ClientSession
from loguru import logger

from googleapiutils2 import (
    Drive,
    GoogleMimeTypes,
    Sheets,
    cache_with_stale_interval,
    retry,
)

if TYPE_CHECKING:
    from googleapiutils2 import File

logger.add("./log/log.log", rotation="1 MB")


async def create_folder_for_org(o: dict, drive: Drive, base_folder: str):
    name, oid = o["name"], o["id"]

    name = name.replace("/", "_")

    logger.info(f"Creating folder for {name}...")

    folder = drive.create(
        name=name,
        mime_type=GoogleMimeTypes.folder,
        parents=base_folder,
        get_extant=True,
    )

    logger.info(f"Created folder for {name}")

    return (name, oid), folder


@retry(retries=10, exponential_backoff=True)
async def download_and_upload(
    session: ClientSession,
    base_url: str,
    headers: dict,
    name: str,
    oid: str,
    folder: dict,
    endpoint: str,
):

    t_filename = endpoint.split("/")[-1]
    if t_filename == "{org_id}":
        t_filename = "org_info"

    filename = pathlib.Path(t_filename).with_suffix(".json")

    params = {}
    if str(filename) == "tasks.json":
        params["search"] = "recur:true"

    url = (base_url + endpoint).format(org_id=oid)

    logger.info(f"Downloading {filename} for {name}...")

    @cache_with_stale_interval()
    async def get_url(
        url: str,
        headers: dict,
        oid: str,
        params: dict,
    ):

        async with session.get(
            url, headers=headers, params={"_oid": oid, **params}
        ) as r:
            if r.status != http.HTTPStatus.OK:
                raise Exception(
                    f"Failed to download {url} for {name}: {r.status}; {r.reason} {r}"
                )

            text = await r.text()

            size_in_mb = round(len(text) / 1024 / 1024, 2)

            logger.info(f"Downloading {filename}: size {size_in_mb} MB")

            return text

    text = await get_url(
        url=url,
        headers=headers,
        oid=oid,
        params=params,
    )

    filepath = pathlib.Path(f"./data/{name}/{filename}")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(text)

    return filepath


def compress_files(filepaths: List[pathlib.Path]):
    name = tempfile.NamedTemporaryFile().name

    with tempfile.TemporaryDirectory() as t_temp_dir:
        temp_dir = pathlib.Path(t_temp_dir)

        tar_filepath = temp_dir / f"{name}.tar"

        # Create a tar file with the JSON files
        with tarfile.open(tar_filepath, "w") as tar:
            for filepath in filepaths:
                tar.add(filepath, arcname=filepath.name)

        # Compress the tar file using gzip
        gzip_name = f"{name}.tar.gz"
        gzip_filepath = temp_dir / gzip_name
        with open(tar_filepath, 'rb') as f_in:
            with gzip.open(gzip_filepath, 'wb') as f_out:
                f_out.writelines(f_in)

        return gzip_filepath


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
        for (name, oid), folder in org_folders.items():

            logger.info(f"Processing {name}: {folder['webViewLink']}...")

            # if (
            #     done_file := next(drive.list(folder["id"], query="name = 'done'"), None)
            # ) is not None:
            #     logger.info(f"Skipping {name}: already processed")
            #     continue

            tasks = []
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

            filepaths = await asyncio.gather(*tasks)

            await create_done_file(folder)

            logger.info(f"Compressing {len(filepaths)} files for {name}...")

            gzip_name = f"{name}.tar.gz"
            gzip_filepath = compress_files(
                filepaths=filepaths,
            )

            size_in_mb = round(gzip_filepath.stat().st_size / 1024 / 1024, 2)

            logger.info(f"Uploading {gzip_name}; size {size_in_mb} MB for {name}...")

            drive.upload(
                filepath=gzip_filepath,
                name=gzip_name,
                to_mime_type=GoogleMimeTypes.zip,
                parents=folder["id"],
            )


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
    "export/org/assets.json",
    "export/org/services.json",
    "export/org/sites.json",
    "export/org/wireless.json",
    "export/org/software.json",
    "export/org/vulnerabilities.json",
    "export/org/users.json",
    "export/org/groups.json",
    "account/orgs/{org_id}",
    "org/explorers",
    "org/tasks",
]

get_all_orgs_endpoint = "account/orgs"

orgs = requests.get(base_url + get_all_orgs_endpoint, headers=headers).json()

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
