import mimetypes
import os
from pathlib import Path
from typing import *

import googleapiclient
import googleapiclient.http
from googleapiclient import discovery
from googleapiclient._apis.drive.v3.resources import (
    DriveResource,
    File,
    FileHttpRequest,
)
from typing_extensions import reveal_type

from utils import CREDS_PATH, SCOPES, TOKEN_PATH, APIBase, FilePath

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
        self.service = cast(DriveResource, self.service)
        self.files = self.service.files()

    def read(self, file_id: str) -> Tuple[File, bytes]:
        metadata = self.files.get(fileId=file_id).execute()
        media = self.files.get_media(fileId=file_id).execute()

        return (metadata, media)

    def read_file_from_url(self, url: str) -> Tuple[File, bytes]:
        return self.read(file_id=self.get_id_from_url(url))

    def download(self, out_filepath: str, file_id: str, mime_type: str):
        request = self.files.export_media(fileId=file_id, mimeType=mime_type)

        with open(out_filepath, "wb") as out_file:
            downloader = googleapiclient.http.MediaIoBaseDownload(out_file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

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

    def list_files(self, query: str) -> Iterable[File]:
        page_token = None
        while True:
            response = self.files.list(q=query, pageToken=page_token).execute()

            for file in response.get("files", []):
                yield file

            page_token = response.get("nextPageToken", None)

            if page_token is None:
                break

    def list_files_in_folder(self, folder_id: str) -> Iterable[File]:
        return self.list_files(query=f"'{folder_id}' in parents")

    def create_drive_file_object(
        self,
        filepath: str,
        google_mime_type: str,
        kwargs: Optional[dict] = None,
    ) -> File:
        if kwargs is None:
            kwargs = {}

        kwargs["body"] = {
            "name": filepath,
            "mimeType": APIBase.create_google_mime_type(google_mime_type),
            **kwargs.get("body", {}),
        }
        return self.files.create(**kwargs).execute()

    def upload_file_object(
        self,
        filepath: FilePath,
        google_mime_type: str,
        mime_type: Optional[str] = None,
        kwargs: Optional[dict] = None,
    ) -> File:
        filepath = Path(filepath)

        if kwargs is None:
            kwargs = {}

        kwargs["body"] = {
            "name": str(filepath),
            "mimeType": APIBase.create_google_mime_type(google_mime_type),
            **kwargs.get("body", {}),
        }

        if google_mime_type == "folder":
            dirs = str(os.path.normpath(filepath)).split(os.sep)
            # The case of creating a nested folder set.
            # Recurse until we hit the end of the path.
            if len(dirs) > 1:
                parent_id = ""
                for dirname in dirs:
                    if parent_id != "":
                        kwargs["body"]["parents"] = [parent_id]

                    parent_req = self.upload_file_object(
                        dirname, google_mime_type, mime_type, kwargs
                    )
                    parent_id = parent_req.get("id", "")

            else:
                kwargs["body"]["name"] = dirs[0]

        else:
            # Else, we need to upload the file via a MediaFileUpload POST.
            kwargs["body"]["name"] = filepath.name
            mime_type = (
                mimetypes.guess_type(filepath)[0] if mime_type is None else mime_type
            )
            media = googleapiclient.http.MediaFileUpload(
                filepath, mimetype=mime_type, resumable=True
            )
            kwargs["media_body"] = media
        return self.files.create(**kwargs).execute()

    def create_folders_if_not_exists(
        self,
        folder_names: List[str],
        parent_id: str,
    ) -> Dict[str, File]:
        folder_dict = {i["name"]: i for i in self.list_files_in_folder(parent_id)}

        for name in folder_names:
            folder = folder_dict.get(name)
            if folder is None:
                folder = self.create_drive_file_object(
                    name,
                    "folder",
                    kwargs={"body": {"parents": [parent_id]}},
                )
                folder_dict[name] = folder

        return folder_dict


if __name__ == "__main__":
    pass

