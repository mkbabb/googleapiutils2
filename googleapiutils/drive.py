from __future__ import annotations


import os
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import *

import googleapiclient
import googleapiclient.http
from google.oauth2.credentials import Credentials
from googleapiclient import discovery
import requests


from .utils import FilePath, parse_file_id

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import (
        DriveList,
        DriveResource,
        File,
        FileList,
        Permission,
        PermissionList,
    )


class GoogleMimeTypes(Enum):
    xls = "application/vnd.ms-excel"
    xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    xml = "text/xml"
    ods = "application/vnd.oasis.opendocument.spreadsheet"
    csv = "text/plain"
    tmpl = "text/plain"
    pdf = "application/pdf"
    php = "application/x-httpd-php"
    jpg = "image/jpeg"
    png = "image/png"
    gif = "image/gif"
    bmp = "image/bmp"
    txt = "text/plain"
    doc = "application/msword"
    js = "text/js"
    swf = "application/x-shockwave-flash"
    mp3 = "audio/mpeg"
    zip = "application/zip"
    rar = "application/rar"
    tar = "application/tar"
    arj = "application/arj"
    cab = "application/cab"
    html = "text/html"
    htm = "text/html"
    default = "application/octet-stream"
    folder = "application/vnd.google-apps.folder"
    sheets = "application/vnd.google-apps.spreadsheet"


DEFAULT_DOWNLOAD_CONVERSION_MAP = {
    GoogleMimeTypes.sheets: (GoogleMimeTypes.xlsx, ".xlsx")
}

DOWNLOAD_LIMIT = 4e6

VERSION: Final = "v3"


def download_large_file(url: str, filepath: FilePath, chunk_size=8192):
    filepath = Path(filepath)

    with requests.get(url, stream=True) as r:
        r.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)


class Drive:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.open()

    def open(self):
        self.service: DriveResource = discovery.build(
            "drive", VERSION, credentials=self.creds
        )
        self.files: DriveResource.FilesResource = self.service.files()

        return self

    def get(self, file_id: str, fields: str = "*", **kwargs: Any) -> File:
        file_id = parse_file_id(file_id)
        return self.files.get(fileId=file_id, fields=fields, **kwargs).execute()

    def download(
        self,
        out_filepath: FilePath,
        file_id: str,
        mime_type: GoogleMimeTypes,
        recursive: bool = False,
        conversion_map: dict[
            GoogleMimeTypes, tuple[GoogleMimeTypes, str]
        ] = DEFAULT_DOWNLOAD_CONVERSION_MAP,
    ) -> Path:
        file_id = parse_file_id(file_id)
        out_filepath = Path(out_filepath)

        if recursive and mime_type == GoogleMimeTypes.folder:
            for file in self.list_children(file_id):
                t_name, t_id, t_mime_type = (
                    file["name"],
                    file["id"],
                    GoogleMimeTypes(file["mimeType"]),
                )

                t_path = out_filepath.joinpath(t_name)

                self.download(
                    out_filepath=t_path,
                    file_id=t_id,
                    mime_type=t_mime_type,
                    recursive=recursive,
                )
        else:
            mime_type, ext = conversion_map.get(mime_type, (mime_type, ""))
            out_filepath = out_filepath.with_suffix(ext)

            request = self.files.export_media(fileId=file_id, mimeType=mime_type.value)

            out_filepath.parent.mkdir(parents=True, exist_ok=True)

            file = self.get(file_id=file_id)

            if float(file["size"]) >= DOWNLOAD_LIMIT:
                link = file["exportLinks"].get(mime_type.value, "")
                download_large_file(url=link, filepath=out_filepath)
            else:
                with out_filepath.open("wb") as out_file:
                    downloader = googleapiclient.http.MediaIoBaseDownload(
                        out_file, request
                    )
                    done = False
                    while done is False:
                        status, done = downloader.next_chunk()

        return out_filepath

    @staticmethod
    def _upload_file_body(
        name: str,
        parents: List[str] | None = None,
        body: File | None = None,
        **kwargs: Any,
    ) -> dict[str, File | Any]:
        body = body if body is not None else {}
        kwargs = {
            "body": {
                "name": name,
                **body,
                **kwargs,
            }
        }

        if parents is not None:
            kwargs["body"].setdefault("parents", parents)

        return kwargs

    def copy(
        self,
        file_id: str,
        to_filename: str,
        to_folder_id: str,
        body: File | None = None,
        **kwargs: Any,
    ) -> Optional[File]:
        file_id = parse_file_id(file_id)
        to_folder_id = parse_file_id(to_folder_id)

        kwargs = {
            "fileId": file_id,
            **self._upload_file_body(
                name=to_filename, parents=[to_folder_id], body=body
            ),
            **kwargs,
        }

        try:
            return self.files.copy(**kwargs).execute()
        except:
            return None

    def update(
        self,
        file_id: str,
        filepath: FilePath,
        body: File | None = None,
        **kwargs: Any,
    ) -> File:
        file_id = parse_file_id(file_id)
        body = body if body is not None else {}

        return self.files.update(
            fileId=file_id,
            media_body=str(filepath),
            body=body,
            **kwargs,
        ).execute()

    @staticmethod
    def _list(
        list_func: Callable[[str | None], FileList | PermissionList]
    ) -> Iterable[FileList | PermissionList]:
        page_token = None
        while True:
            response = list_func(page_token)
            yield response

            if (page_token := response.get("nextPageToken", None)) is None:
                break

    def list(
        self,
        query: str,
        fields: str = "*",
        order_by: str = "modifiedTime desc",
        **kwargs: Any,
    ) -> Iterable[File]:
        list_func = lambda x: self.files.list(
            q=query, pageToken=x, fields=fields, orderBy=order_by, **kwargs
        ).execute()

        for response in self._list(list_func):
            for file in response.get("files", []):
                yield file

    def list_children(
        self, parent_id: str, fields: str = "*", **kwargs: Any
    ) -> Iterable[File]:
        parent_id = parse_file_id(parent_id)

        return self.list(query=f"'{parent_id}' in parents", fields=fields, **kwargs)

    def _update_if_exists(
        self,
        name: str,
        filepath: FilePath,
        parents: List[str] | None = None,
        team_drives: bool = True,
    ) -> File | None:

        if parents is None:
            return None

        filename = Path(name)

        parents_list = " or ".join((f"'{parent}' in parents" for parent in parents))
        names_list = " or ".join((f"name = '{filename}'", f"name = '{filename.stem}'"))

        queries = [parents_list, names_list, "trashed = false"]

        query = " and ".join((f"({i})" for i in queries))

        kwargs = (
            dict(supportsAllDrives=True, includeItemsFromAllDrives=True)
            if team_drives
            else {}
        )

        files = self.list(query=query, **kwargs)

        for file in files:
            return self.update(file["id"], filepath, supportsAllDrives=team_drives)
        else:
            return None

    def _create_nested_folders(self, filepath: Path, parents: List[str] | None) -> None:
        dirs = str(os.path.normpath(filepath)).split(os.sep)

        for dirname in dirs[:-1]:
            t_kwargs = self._upload_file_body(
                name=dirname, parents=parents, mimeType=GoogleMimeTypes.folder.value
            )
            file = self.files.create(**t_kwargs).execute()
            parents = [file["id"]]

    def create_drive_file_object(
        self,
        filepath: FilePath,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | None = None,
        create_folders: bool = False,
        update: bool = False,
        **kwargs: Any,
    ) -> File:
        filepath = Path(filepath)
        parents = parse_file_id(parents)

        if (
            update
            and (file := self._update_if_exists(filepath.name, filepath, parents))
            is not None
        ):
            return file

        if create_folders:
            self._create_nested_folders(filepath=filepath, parents=parents)

        if mime_type is not None:
            kwargs = {
                **self._upload_file_body(
                    name=filepath.name, parents=parents, mimeType=mime_type
                ),
                **kwargs,
            }
            return self.files.create(**kwargs).execute()

    def _upload(
        self,
        uploader: Callable,
        name: str,
        filepath: FilePath,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | None = None,
        body: File | None = None,
        update: bool = True,
        **kwargs,
    ) -> File:
        filepath = Path(filepath)
        parents = parse_file_id(parents)

        if (
            update
            and (file := self._update_if_exists(name, filepath, parents)) is not None
        ):
            return file

        kwargs = {
            **self._upload_file_body(
                name=name, parents=parents, body=body, mimeType=mime_type
            ),
            **kwargs,
        }

        kwargs["media_body"] = uploader()

        return self.files.create(**kwargs).execute()

    def upload_file(
        self,
        filepath: FilePath,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | None = None,
        body: File | None = None,
        update: bool = True,
        **kwargs: Any,
    ) -> File:
        filepath = Path(filepath)

        def uploader():
            return googleapiclient.http.MediaFileUpload(str(filepath), resumable=True)

        return self._upload(
            uploader=uploader,
            name=filepath.name,
            filepath=filepath,
            mime_type=mime_type,
            parents=parents,
            body=body,
            update=update,
            **kwargs,
        )

    def upload_data(
        self,
        data: bytes,
        name: str,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | None = None,
        body: File | None = None,
        update: bool = True,
        **kwargs: Any,
    ) -> File:
        with BytesIO(data) as tio:

            def uploader():
                return googleapiclient.http.MediaIoBaseUpload(tio, resumable=True)

            return self._upload(
                uploader=uploader,
                name=name,
                filepath=tio.name,
                mime_type=mime_type,
                parents=parents,
                body=body,
                update=update,
                **kwargs,
            )

    def create_folders_if_not_exists(
        self,
        folder_names: List[str],
        parent_id: str,
    ) -> dict[str, File]:
        parent_id = parse_file_id(parent_id)

        folder_dict = {i["name"]: i for i in self.list_children(parent_id)}

        for name in folder_names:
            folder = folder_dict.get(name)
            if folder is None:
                folder = self.create_drive_file_object(
                    filepath=name,
                    mime_type=GoogleMimeTypes.folder,
                    parents=[parent_id],
                )
                folder_dict[name] = folder

        return folder_dict

    def permissions_get(
        self, file_id: str, permission_id: str, **kwargs: Any
    ) -> Permission:
        file_id = parse_file_id(file_id)

        return (
            self.service.permissions()
            .get(fileId=file_id, permissionId=permission_id, **kwargs)
            .execute()
        )

    def permissions_list(
        self, file_id: str, fields: str = "*", **kwargs: Any
    ) -> Iterable[Permission]:
        file_id = parse_file_id(file_id)

        list_func = (
            lambda x: self.service.permissions()
            .list(fileId=file_id, pageToken=x, fields=fields, **kwargs)
            .execute()
        )

        for response in self._list(list_func):
            for file in response.get("permissions", []):
                yield file

    def _permission_update_if_exists(
        self, file_id: str, user_permission: Permission
    ) -> Permission | None:
        for p in self.permissions_list(file_id):
            if p["emailAddress"].strip().lower() == user_permission["emailAddress"]:
                return p
        else:
            return None

    def permissions_create(
        self,
        file_id: str,
        email_address: str,
        permission: Permission | None = None,
        sendNotificationEmail: bool = True,
        update: bool = False,
        **kwargs: Any,
    ) -> Permission:
        file_id = parse_file_id(file_id)

        user_permission: Permission = {
            "type": "user",
            "role": "reader",
            "emailAddress": email_address.strip().lower(),
        }

        if permission is not None:
            user_permission.update(permission)

        if (
            not update
            and (p := self._permission_update_if_exists(file_id, user_permission))
            is not None
        ):
            return p

        return (
            self.service.permissions()
            .create(
                fileId=file_id,
                body=user_permission,
                fields="*",
                sendNotificationEmail=sendNotificationEmail,
                **kwargs,
            )
            .execute()
        )

    def permissions_delete(self, file_id: str, permission_id: str, **kwargs: Any):
        file_id = parse_file_id(file_id)

        return (
            self.service.permissions()
            .delete(fileId=file_id, permissionId=permission_id, **kwargs)
            .execute()
        )
