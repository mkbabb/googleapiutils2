from __future__ import annotations

from io import BytesIO
import mimetypes
import os
from pathlib import Path
from typing import *


import googleapiclient
import googleapiclient.http
from googleapiclient import discovery

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import (
        DriveResource,
        File,
    )


from utils import CREDS_PATH, SCOPES, TOKEN_PATH, APIBase, FilePath, GoogleMimeTypes


VERSION = "v3"


class Drive(APIBase):
    def __init__(
        self,
        token_path: FilePath = TOKEN_PATH,
        creds_path: FilePath = CREDS_PATH,
        is_service_account: bool = False,
        scopes: List[str] = SCOPES,
    ):
        super().__init__(token_path, creds_path, is_service_account, scopes)

        self.service: DriveResource = discovery.build(
            "drive", VERSION, credentials=self.creds
        )
        self.files = self.service.files()

    def get(self, file_id: str) -> tuple[File, bytes]:
        metadata = self.files.get(fileId=file_id).execute()
        media = self.files.get_media(fileId=file_id).execute()

        return (metadata, media)

    def get_file_from_url(self, url: str) -> tuple[File, bytes]:
        return self.get(file_id=self.get_id_from_url(url))

    def download(self, out_filepath: FilePath, file_id: str, mime_type: str) -> Path:
        out_filepath = Path(out_filepath)
        request = self.files.export_media(fileId=file_id, mimeType=mime_type)

        with open(out_filepath, "wb") as out_file:
            downloader = googleapiclient.http.MediaIoBaseDownload(out_file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

        return out_filepath

    def copy(
        self,
        file_id: str,
        filename: Optional[str],
        folder_id: Optional[str],
    ) -> Optional[File]:
        body = {"name": filename, "parents": [folder_id]}
        try:
            return self.files.copy(fileId=file_id, body=body).execute()
        except:
            return None

    def update(self, file_id: str, filepath: FilePath) -> File:
        filepath = Path(filepath)
        return self.files.update(fileId=file_id, media_body=filepath).execute()

    def update_from_url(self, url: str, filepath: FilePath) -> File:
        return self.update(filepath=filepath, file_id=self.get_id_from_url(url))

    def list(self, query: str) -> Iterable[File]:
        page_token = None
        while True:
            response = self.files.list(q=query, pageToken=page_token).execute()

            for file in response.get("files", []):
                yield file

            page_token = response.get("nextPageToken", None)

            if page_token is None:
                break

    def list_children(self, parent_id: str) -> Iterable[File]:
        return self.list(query=f"'{parent_id}' in parents")

    def _upload_body_kwargs(
        self,
        google_mime_type: GoogleMimeTypes,
        kwargs: Optional[dict] = None,
    ) -> dict:
        if kwargs is None:
            kwargs = {}

        kwargs["body"] = {
            "mimeType": self.create_google_mime_type(google_mime_type),
            **kwargs.get("body", {}),
        }
        return kwargs

    def create_drive_file_object(
        self,
        filepath: str,
        google_mime_type: GoogleMimeTypes,
        kwargs: Optional[dict] = None,
    ) -> File:
        kwargs = self._upload_body_kwargs(
            google_mime_type=google_mime_type, kwargs=kwargs
        )
        kwargs["body"]["name"] = filepath
        return self.files.create(**kwargs).execute()

    def upload_file(
        self,
        filepath: FilePath,
        google_mime_type: GoogleMimeTypes,
        mime_type: Optional[str] = None,
        kwargs: Optional[dict] = None,
    ) -> File:
        filepath = Path(filepath)

        kwargs = self._upload_body_kwargs(
            google_mime_type=google_mime_type, kwargs=kwargs
        )
        kwargs["body"]["name"] = str(filepath)

        if google_mime_type == "folder":
            dirs = str(os.path.normpath(filepath)).split(os.sep)
            # The case of creating a nested folder set.
            # Recurse until we hit the end of the path.
            if len(dirs) > 1:
                parent_id = ""
                for dirname in dirs:
                    if parent_id != "":
                        kwargs["body"]["parents"] = [parent_id]

                    parent_req = self.upload_file(
                        dirname, google_mime_type, mime_type, kwargs
                    )
                    parent_id = parent_req.get("id", "")

            else:
                kwargs["body"]["name"] = dirs[0]

        else:
            # Else, we need to upload the file via a MediaFileUpload POST.
            mime_type = (
                mimetypes.guess_type(filepath)[0] if mime_type is None else mime_type
            )
            media = googleapiclient.http.MediaFileUpload(
                filepath, mimetype=mime_type, resumable=True
            )
            kwargs["media_body"] = media
        return self.files.create(**kwargs).execute()

    def upload(
        self,
        data: bytes,
        filename: str,
        google_mime_type: GoogleMimeTypes,
        mime_type: Optional[str] = None,
        kwargs: Optional[dict] = None,
    ) -> File:
        kwargs = self._upload_body_kwargs(
            google_mime_type=google_mime_type, kwargs=kwargs
        )
        kwargs["body"]["name"] = filename

        with BytesIO(data) as tio:
            media = googleapiclient.http.MediaIoBaseUpload(
                tio, mimetype=mime_type, resumable=True
            )
            kwargs["media_body"] = media
            return self.files.create(**kwargs).execute()

    def create_folders_if_not_exists(
        self,
        folder_names: List[str],
        parent_id: str,
    ) -> Dict[str, File]:
        folder_dict = {i["name"]: i for i in self.list_children(parent_id)}

        for name in folder_names:
            folder = folder_dict.get(name)
            if folder is None:
                folder = self.create_drive_file_object(
                    filepath=name,
                    google_mime_type="folder",
                    kwargs={"body": {"parents": [parent_id]}},
                )
                folder_dict[name] = folder

        return folder_dict


class Permission(APIBase):
    def create(
        self,
        file_id: str,
        email_address: str,
        permission: Optional[dict] = None,
    ):
        user_permission = {
            "type": "user",
            "role": "reader",
            "emailAddress": email_address,
        }
        if permission is not None:
            user_permission.update(permission)

        return (
            self.service.permissions()
            .create(
                fileId=file_id,
                body=user_permission,
                fields="id",
            )
            .execute()
        )


if __name__ == "__main__":
    name = Path("friday-institute-reports")
    dir = Path("auth")

    token_path = dir.joinpath(name.with_suffix(".token.pickle"))
    creds_path = dir.joinpath(name.with_suffix(".credentials.json"))

    drive = Drive(token_path=token_path, creds_path=creds_path, is_service_account=True)

    id = drive.get_id_from_url(
        "https://drive.google.com/drive/folders/1fyQNBMxpytjHtgjYQJIjY9dczzZgKBxJ?usp=sharing"
    )
    # id = drive.get_id_from_url(
    #     "https://docs.google.com/spreadsheets/d/1jrYwFsMrV2E6Ev6ZOUYo-5j2rXPfNpiB8VB_rgl3SmM/edit?usp=sharing"
    # )

    files = drive.list_children(parent_id=id)
    for file in files:
        print(file)

    # drive.upload(b"", "ff";;)

    print(drive)
