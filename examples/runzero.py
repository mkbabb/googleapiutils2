from __future__ import annotations

import asyncio
import contextlib
import gzip
import http
import os
import pathlib
import tarfile
import tempfile
from typing import *

import requests
from aiohttp import ClientSession
from loguru import logger

from googleapiutils2 import Drive, GoogleMimeTypes, Sheets, retry

logger.add("./log/log.log", rotation="1 MB")


def get_size_in_mb(filepath: pathlib.Path) -> float:
    return round(filepath.stat().st_size / 1024 / 1024, 2)


@contextlib.contextmanager
def compress_files(
    filepaths: list[pathlib.Path], name: pathlib.Path | str | None = None
) -> Iterator[pathlib.Path]:
    if name is None:
        name = pathlib.Path(tempfile.NamedTemporaryFile().name)

    name = pathlib.Path(name)

    with tempfile.TemporaryDirectory() as t_temp_dir:
        temp_dir = pathlib.Path(t_temp_dir)
        tar_filepath = temp_dir / name.with_suffix(".tar")

        # Create a tar file with the JSON files
        with tarfile.open(tar_filepath, "w") as tar:
            for filepath in filepaths:
                tar.add(filepath, arcname=filepath.name)

        # Compress the tar file using gzip
        gzip_filepath = temp_dir / name.with_suffix(".tar.gz")

        with open(tar_filepath, 'rb') as f_in:
            with gzip.open(gzip_filepath, 'wb') as f_out:
                f_out.writelines(f_in)

        try:
            yield gzip_filepath
        finally:
            pass


async def create_folder_for_org(org: dict, drive: Drive, parent: str):
    name, oid = org["name"], org["id"]

    # Replace any slashes in the name with underscores
    name = name.replace("/", "_")

    folder = drive.create(
        name=name,
        mime_type=GoogleMimeTypes.folder,
        parents=parent,
        get_extant=True,
    )

    logger.info(f"Created folder for {name}")

    return (name, oid), folder


@retry(retries=10, exponential_backoff=True)
async def download_endpoint(
    name: str,
    oid: str,
    session: ClientSession,
    base_url: str,
    endpoint: str,
    headers: dict,
):

    t_filename = endpoint.split("/")[-1]
    if t_filename == "{org_id}":
        t_filename = "org_info"

    filename = pathlib.Path(t_filename).with_suffix(".json")

    filepath = pathlib.Path(f"./data/{name}/{filename}")
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if filepath.exists() and filepath.stat().st_size > 0:
        logger.info(f"Skipping {filename} for {name}: already downloaded")
        return filepath

    params = {}
    if str(filename) == "tasks.json":
        params["search"] = "recur:true"

    url = (base_url + endpoint).format(org_id=oid)

    logger.info(f"Downloading {filename} for {name}...")

    async with session.get(url, headers=headers, params={"_oid": oid, **params}) as r:
        if r.status != http.HTTPStatus.OK:
            raise Exception(
                f"Failed to download {url} for {name}: {r.status}; {r.reason} {r}"
            )

        logger.info(
            f"Initial request for {filename} for {name} successful, downloading content..."
        )

        try:
            with open(filepath, "ab") as f:
                async for data in r.content.iter_any():
                    f.write(data)
        except Exception as e:
            logger.error(f"Failed to stream content from {url} for {name}: {e}")
            filepath.unlink(missing_ok=True)
            raise e

        size_in_mb = get_size_in_mb(filepath)

        logger.info(f"Downloaded {filename} for {name}; size {size_in_mb} MB")

        return filepath


async def process_org_folder(
    org_folders: dict,
    base_url: str,
    endpoints: list,
    headers: dict,
):
    async with ClientSession() as session:
        for (name, oid), folder in org_folders.items():

            logger.info(f"Processing {name}: {folder['webViewLink']}...")

            if (
                done_file := next(drive.list(folder["id"], query="name = 'done'"), None)
            ) is not None:
                drive.delete(done_file["id"])

            tasks = []
            for endpoint in endpoints:
                task = asyncio.create_task(
                    download_endpoint(
                        name=name,
                        oid=oid,
                        session=session,
                        base_url=base_url,
                        endpoint=endpoint,
                        headers=headers,
                    )
                )
                tasks.append(task)

            filepaths = await asyncio.gather(*tasks)

            logger.info(f"Compressing {len(filepaths)} files for {name}...")

            with compress_files(filepaths=filepaths, name="done") as gzip_filepath:
                size_in_mb = get_size_in_mb(gzip_filepath)

                logger.info(
                    f"Uploading {gzip_filepath.name}; size {size_in_mb} MB for {name}..."
                )

                drive.upload(
                    filepath=gzip_filepath,
                    name=gzip_filepath.name,
                    to_mime_type=GoogleMimeTypes.zip,
                    parents=folder["id"],
                )

                logger.info(f"Uploaded {gzip_filepath.name} for {name}")


drive = Drive()
sheets = Sheets()

export_folder = (
    "https://drive.google.com/drive/u/0/folders/1JGyx-4tsi1VME0Pab-cjX9ygs_kkgGj1"
)

runzero_token = os.getenv("RUNZERO_TOKEN")

base_url = "https://console.runzero.com/api/v1.0/"

headers = {
    "Authorization": f"Bearer {runzero_token}",
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

logger.info(f"Got {len(orgs)} runZero orgs")

org_folders = dict(
    (
        asyncio.run(create_folder_for_org(org=org, drive=drive, parent=export_folder))
        for org in orgs
    )
)

asyncio.run(
    process_org_folder(
        org_folders=org_folders,
        base_url=base_url,
        endpoints=endpoints,
        headers=headers,
    )
)
