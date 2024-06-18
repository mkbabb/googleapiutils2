from __future__ import annotations

import asyncio
import contextlib
import gzip
import http
import json
import os
import pathlib
import tarfile
import tempfile
from typing import *

import requests
from aiohttp import ClientSession, ClientTimeout
from loguru import logger

from googleapiutils2 import Drive, GoogleMimeTypes, retry

if TYPE_CHECKING:
    from googleapiutils2 import File

logger.add(f"./log/{pathlib.Path(__file__).stem}.log", rotation="1 MB")


def get_size_in_mb(filepath: pathlib.Path) -> float:
    return round(filepath.stat().st_size / 1024 / 1024, 2)


@contextlib.contextmanager
def compress_files(
    filepaths: list[pathlib.Path],
    name: pathlib.Path | str | None = None,
    chunk_size: int = 64 * 1024 * 1024,  # Default to 64 MB
) -> Iterator[pathlib.Path]:
    if name is None:
        name = pathlib.Path(tempfile.NamedTemporaryFile().name)

    name = pathlib.Path(name)

    logger.info(
        f"Compressing {len(filepaths)} files for {name} with chunk size {chunk_size} bytes..."
    )

    with tempfile.TemporaryDirectory() as t_temp_dir:
        temp_dir = pathlib.Path(t_temp_dir)
        tar_filepath = temp_dir / name.with_suffix(".tar")

        with tarfile.open(tar_filepath, "w") as tar:
            for filepath in filepaths:
                tar.add(filepath, arcname=filepath.name)

        logger.info(f"Created {tar_filepath.name} for {name}; zipping...")

        gzip_filepath = temp_dir / name.with_suffix(".tar.gz")

        with open(tar_filepath, 'rb') as f_in, gzip.open(gzip_filepath, 'wb') as f_out:
            while True:
                chunk = f_in.read(chunk_size)  # Read in configurable chunks
                if not chunk:
                    break
                f_out.write(chunk)

        logger.info(f"Zipped {gzip_filepath.name} for {name}")

        try:
            yield gzip_filepath
        finally:
            pass


def compress_and_upload_files(
    filepaths: list[pathlib.Path],
    drive: Drive,
    folder: File,
    name: pathlib.Path | str | None = None,
):
    with compress_files(filepaths=filepaths, name=name) as gzip_filepath:
        size_in_mb = get_size_in_mb(gzip_filepath)

        logger.info(f"Uploading {gzip_filepath.name}; size {size_in_mb} MB...")

        if (
            extant_file := next(
                drive.list(query=f"name = '{gzip_filepath.name}'"), None
            )
        ) is not None:
            logger.info(f"Deleting extant {extant_file['name']}...")
            drive.delete(extant_file["id"])

        drive.upload(
            filepath=gzip_filepath,
            name=gzip_filepath.name,
            to_mime_type=GoogleMimeTypes.zip,
            parents=folder["id"],
        )

        logger.info(f"Uploaded {gzip_filepath.name}")


async def create_folder_for_org(
    org: dict,
    parent: str,
    drive: Drive,
):
    name, oid = org["name"], org["id"]

    # Replace any slashes in the name with underscores
    name = str(name).replace("/", "_")

    folder = drive.create(
        name=name,
        mime_type=GoogleMimeTypes.folder,
        parents=parent,
        get_extant=True,
    )

    logger.info(f"Created folder for {name}")

    return (name, oid), folder


@retry(retries=5, exponential_backoff=True)
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
        return filepath, True

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

        return filepath, False


async def process_org_item(
    org_item: tuple,
    base_url: str,
    endpoints: list,
    headers: dict,
    drive: Drive,
):
    (name, oid), folder = org_item

    async with ClientSession(
        timeout=ClientTimeout(
            total=30 * 60
        ),  # 30 minute timeout for the entire process
    ) as session:
        logger.info(f"Processing {name}: {folder['webViewLink']}...")

        if (
            done_file := next(drive.list(folder["id"], query="name = 'done'"), None)
        ) is not None:
            drive.delete(done_file["id"])

        tasks = [
            asyncio.create_task(
                download_endpoint(
                    name=name,
                    oid=oid,
                    session=session,
                    base_url=base_url,
                    endpoint=endpoint,
                    headers=headers,
                )
            )
            for endpoint in endpoints
        ]

        results = await asyncio.gather(*tasks)

        # if (all_cached := all(cached for _, cached in results)) and (
        #     (
        #         done_file := next(
        #             drive.list(folder["id"], query="name contains '.tar.gz'"), None
        #         )
        #     )
        #     is not None
        # ):
        #     logger.info(f"Skipping compression and upload for {name}: already uploaded")
        #     return

        filepaths = [filepath for filepath, _ in results]

        compress_and_upload_files(
            filepaths=filepaths, name=name, folder=folder, drive=drive
        )


async def main():
    drive = Drive()

    export_folder = "https://drive.google.com/drive/u/0/folders/0AMXg4ZUfGbSqUk9PVA"

    base_url = "https://console.runzero.com/api/v1.0/"

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

    runzero_token = os.getenv("RUNZERO_TOKEN")

    headers = {
        "Authorization": f"Bearer {runzero_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    get_all_orgs_endpoint = "account/orgs"

    orgs = requests.get(base_url + get_all_orgs_endpoint, headers=headers).json()

    logger.info(f"Got {len(orgs)} runZero orgs")

    async def process_org(
        org: dict,
    ):
        org_item = await create_folder_for_org(
            org=org, parent=export_folder, drive=drive
        )

        await process_org_item(
            org_item=org_item,
            base_url=base_url,
            endpoints=endpoints,
            headers=headers,
            drive=drive,
        )

    tasks = [
        asyncio.create_task(
            process_org(
                org=org,
            )
        )
        for org in orgs
    ]

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
