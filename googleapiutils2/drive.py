from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import *

import googleapiclient
import googleapiclient.http
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from .utils import (
    FilePath,
    GoogleMimeTypes,
    download_large_file,
    parse_file_id,
    q_escape,
)

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import (
        DriveList,
        DriveResource,
        File,
        FileList,
        Permission,
        PermissionList,
    )

    from .utils import FileId


DEFAULT_DOWNLOAD_CONVERSION_MAP = {
    GoogleMimeTypes.sheets: (GoogleMimeTypes.xlsx, ".xlsx"),
    GoogleMimeTypes.docs: (GoogleMimeTypes.doc, ".docx"),
    GoogleMimeTypes.slides: (GoogleMimeTypes.pdf, ".pdf"),
}

DOWNLOAD_LIMIT = 4e6

VERSION = "v3"


class Drive:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service: DriveResource = discovery.build(
            "drive", VERSION, credentials=self.creds
        )
        self.files: DriveResource.FilesResource = self.service.files()

    def get(self, file_id: FileId, fields: str = "*", **kwargs: Any) -> File:
        file_id = parse_file_id(file_id)
        return self.files.get(fileId=file_id, fields=fields, **kwargs).execute()

    def download(
        self,
        out_filepath: FilePath,
        file_id: FileId,
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
        parents: List[FileId] | None = None,
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
        file_id: FileId,
        to_filename: str,
        to_folder_id: str,
        body: File | None = None,
        **kwargs: Any,
    ) -> File | None:
        # TODO! Check if this and update returns valid File object.

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
        file_id: FileId,
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
    def _list_fields(fields: str) -> str:
        if "*" in fields:
            return fields

        REQUIRED_FIELDS = ["nextPageToken", "kind"]

        for r in REQUIRED_FIELDS:
            if r not in fields:
                fields += f",{r}"
        return fields

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
        team_drives: bool = True,
        **kwargs: Any,
    ) -> Iterable[File]:
        if team_drives:
            kwargs.update(
                {"includeItemsFromAllDrives": True, "supportsAllDrives": True}
            )

        list_func = lambda x: self.files.list(
            q=query,
            pageToken=x,
            fields=self._list_fields(fields),
            orderBy=order_by,
            **kwargs,
        ).execute()

        for response in self._list(list_func):
            for file in response.get("files", []):
                yield file

    def list_children(
        self, parent_id: FileId, fields: str = "*", **kwargs: Any
    ) -> Iterable[File]:
        parent_id = parse_file_id(parent_id)

        return self.list(
            query=f"{q_escape(parent_id)} in parents", fields=fields, **kwargs
        )

    def _query_children(self, name: str, parents: List[FileId], q: str | None = None):
        filename = Path(name)

        parents_list = " or ".join(
            (f"{q_escape(parent)} in parents" for parent in parents)
        )
        names_list = " or ".join(
            (
                f"name = {q_escape(str(filename))}",
                f"name = {q_escape(filename.stem)}",
            )
        )

        queries = [parents_list, names_list, "trashed = false"]
        if q is not None:
            queries.append(q)

        query = " and ".join((f"({i})" for i in queries))

        return self.list(query=query)

    def _update_if_exists(
        self,
        name: str,
        filepath: FilePath,
        parents: List[FileId] | None = None,
        team_drives: bool = True,
    ) -> File | None:

        if parents is None:
            return None

        files = self._query_children(name=name, parents=parents)

        for file in files:
            return self.update(file["id"], filepath, supportsAllDrives=team_drives)
        else:
            return None

    def _create_nested_folders(
        self, filepath: Path, parents: List[FileId] | None, update: bool = True
    ) -> None:
        def create_or_get_if_exists(name: str, parents: List[FileId]):
            folders = self._query_children(
                name=name,
                parents=parents,
                q=f"mimeType = '{GoogleMimeTypes.folder.value}'",
            )

            if update and (folder := next(folders, None)) is not None:
                return folder
            else:
                return self.files.create(
                    **self._upload_file_body(
                        name=dirname,
                        parents=parents,
                        mimeType=GoogleMimeTypes.folder.value,
                    )
                ).execute()

        for dirname in filepath.parts[:-1]:
            folder = create_or_get_if_exists(dirname, parents)
            parents = [folder["id"]]

        return parents

    def create(
        self,
        filepath: FilePath,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[FileId] | None = None,
        create_folders: bool = False,
        update: bool = False,
        fields: str = "*",
        **kwargs: Any,
    ) -> File:
        filepath = Path(filepath)
        parents = parse_file_id(parents)

        if create_folders:
            parents = self._create_nested_folders(
                filepath=filepath, parents=parents, update=update
            )

        if (
            update
            and (file := next(self._query_children(filepath.name, parents), None))
            is not None
        ):
            return file

        if mime_type is not None:
            kwargs = {
                **self._upload_file_body(
                    name=filepath.name, parents=parents, mimeType=mime_type.value
                ),
                **kwargs,
            }
            file = self.files.create(**kwargs).execute()

            return self.get(file_id=file["id"], fields=fields)

    def _upload(
        self,
        uploader: Callable,
        name: str,
        filepath: FilePath,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[FileId] | None = None,
        body: File | None = None,
        update: bool = True,
        fields: str = "*",
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
                name=name, parents=parents, body=body, mimeType=mime_type.value
            ),
            **kwargs,
        }

        kwargs["media_body"] = uploader()
        return self.files.create(**kwargs).execute()

    def upload_file(
        self,
        filepath: FilePath,
        name: str | None = None,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[FileId] | None = None,
        body: File | None = None,
        update: bool = True,
        **kwargs: Any,
    ) -> File:
        filepath = Path(filepath)

        def uploader():
            return googleapiclient.http.MediaFileUpload(str(filepath), resumable=True)

        return self._upload(
            uploader=uploader,
            name=name if name is not None else filepath.name,
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
        parents: List[FileId] | None = None,
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

    def permissions_get(
        self, file_id: FileId, permission_id: str, **kwargs: Any
    ) -> Permission:
        file_id = parse_file_id(file_id)

        return (
            self.service.permissions()
            .get(fileId=file_id, permissionId=permission_id, **kwargs)
            .execute()
        )

    def permissions_list(
        self, file_id: FileId, fields: str = "*", **kwargs: Any
    ) -> Iterable[Permission]:
        file_id = parse_file_id(file_id)

        list_func = (
            lambda x: self.service.permissions()
            .list(
                fileId=file_id, pageToken=x, fields=self._list_fields(fields), **kwargs
            )
            .execute()
        )

        for response in self._list(list_func):
            for file in response.get("permissions", []):
                yield file

    def _permission_update_if_exists(
        self, file_id: FileId, user_permission: Permission
    ) -> Permission | None:
        for p in self.permissions_list(file_id):
            if p["emailAddress"].strip().lower() == user_permission["emailAddress"]:
                return p
        else:
            return None

    def permissions_create(
        self,
        file_id: FileId,
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

    def permissions_delete(self, file_id: FileId, permission_id: str, **kwargs: Any):
        file_id = parse_file_id(file_id)

        return (
            self.service.permissions()
            .delete(fileId=file_id, permissionId=permission_id, **kwargs)
            .execute()
        )
