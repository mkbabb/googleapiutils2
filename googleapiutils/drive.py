from __future__ import annotations

import mimetypes
import os
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import *

import googleapiclient
import googleapiclient.http
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from .utils import FilePath, parse_file_id

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource, File, Permission


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


VERSION: Final = "v3"


class Drive:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service: DriveResource = discovery.build(
            "drive", VERSION, credentials=self.creds
        )
        self.files: DriveResource.FilesResource = self.service.files()

    def get(self, file_id: str) -> tuple[File, bytes]:
        file_id = parse_file_id(file_id)
        metadata = self.files.get(fileId=file_id).execute()
        media = self.files.get_media(fileId=file_id).execute()

        return (metadata, media)

    def download(self, out_filepath: FilePath, file_id: str, mime_type: str) -> Path:
        file_id = parse_file_id(file_id)
        out_filepath = Path(out_filepath)

        request = self.files.export_media(fileId=file_id, mimeType=mime_type)

        with open(out_filepath, "wb") as out_file:
            downloader = googleapiclient.http.MediaIoBaseDownload(out_file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

        return out_filepath

    def copy(
        self, file_id: str, filename: str, folder_id: str, **kwargs: Any
    ) -> Optional[File]:
        file_id = parse_file_id(file_id)
        folder_id = parse_file_id(folder_id)

        body: File = {"name": filename, "parents": [folder_id]}

        try:
            return self.files.copy(fileId=file_id, body=body, **kwargs).execute()
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
    def _list(list_func: Any):
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
        self, parent_id: str, fields: str = "*", **kwargs
    ) -> Iterable[File]:
        parent_id = parse_file_id(parent_id)

        return self.list(query=f"'{parent_id}' in parents", fields=fields, **kwargs)

    def _replace_if_exists(
        self,
        name: str,
        filepath: FilePath,
        parents: List[str] | None = None,
    ) -> File | None:
        if parents is None:
            return None

        query = f"name = '{name}' and '{parents[0]}' in parents"
        files = self.list(query)

        for file in files:
            return self.update(file["id"], filepath)
        else:
            return None

    @staticmethod
    def upload_file_body(
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

    def create_drive_file_object(
        self,
        filepath: FilePath,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | None = None,
        create_folders: bool = False,
        **kwargs: Any,
    ) -> File:
        filepath = Path(filepath)
        parents = parse_file_id(parents)

        if create_folders:
            dirs = str(os.path.normpath(filepath)).split(os.sep)

            for dirname in dirs[:-1]:
                t_kwargs = self.upload_file_body(
                    name=dirname, parents=parents, mimeType=GoogleMimeTypes.folder.value
                )
                file = self.files.create(**t_kwargs).execute()
                parents = [file["id"]]

        if mime_type is not None:
            kwargs["mimeType"] = mime_type.value

            kwargs = self.upload_file_body(
                name=filepath.name, parents=parents, **kwargs
            )
            return self.files.create(**kwargs).execute()

    def upload_file(
        self,
        filepath: FilePath,
        parents: List[str] | None = None,
        body: File | None = None,
        replace_if_exists: bool = True,
    ) -> File:
        filepath = Path(filepath)
        parents = parse_file_id(parents)

        kwargs = self.upload_file_body(name=filepath.name, parents=parents, body=body)

        if replace_if_exists:
            if (
                file := self._replace_if_exists(
                    name=filepath.name,
                    filepath=filepath,
                    parents=parents,
                )
            ) is not None:
                return file

        mime_type = mimetypes.guess_type(str(filepath))[0]
        media = googleapiclient.http.MediaFileUpload(
            str(filepath), mimetype=mime_type, resumable=True
        )
        kwargs["media_body"] = media

        return self.files.create(**kwargs).execute()

    def upload_data(
        self,
        data: bytes,
        filename: str,
        parents: List[str] | None = None,
        body: File | None = None,
        replace_if_exists: bool = True,
        **kwargs: Any,
    ) -> File:
        parents = parse_file_id(parents)

        kwargs = self.upload_file_body(
            name=filename, parents=parents, body=body, **kwargs
        )

        with BytesIO(data) as tio:
            if replace_if_exists:
                if (
                    file := self._replace_if_exists(
                        name=filename, filepath=tio.name, parents=parents
                    )
                ) is not None:
                    return file

            mime_type = mimetypes.guess_type(tio.name)[0]
            media = googleapiclient.http.MediaIoBaseUpload(
                tio, mimetype=mime_type, resumable=True
            )
            kwargs["media_body"] = media

            return self.files.create(**kwargs).execute()

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
                    google_mime_type="folder",
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

    def permissions_create(
        self,
        file_id: str,
        email_address: str,
        permission: Permission | None = None,
        sendNotificationEmail: bool = True,
        replace_if_exists: bool = True,
        **kwargs: Any,
    ):
        file_id = parse_file_id(file_id)

        user_permission: Permission = {
            "type": "user",
            "role": "reader",
            "emailAddress": email_address.strip().lower(),
        }
        if permission is not None:
            user_permission.update(permission)

        if replace_if_exists:
            for p in self.permissions_list(file_id):
                if (
                    p["emailAddress"].strip().lower()
                    == user_permission["emailAddress"]
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
