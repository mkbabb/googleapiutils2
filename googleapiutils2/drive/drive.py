from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import *

import googleapiclient
import googleapiclient.http
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from ..utils import (
    FilePath,
    GoogleMimeTypes,
    download_large_file,
    parse_file_id,
    q_escape,
)
from .misc import DEFAULT_DOWNLOAD_CONVERSION_MAP, DOWNLOAD_LIMIT, VERSION

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import (
        DriveList,
        DriveResource,
        File,
        FileList,
        Permission,
        PermissionList,
    )


class Drive:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service: DriveResource = discovery.build(
            "drive", VERSION, credentials=self.creds
        )  # type: ignore
        self.files: DriveResource.FilesResource = self.service.files()

    def get(self, file_id: str, fields: str = "*", **kwargs: Any) -> File:
        """Get a file by its ID."""
        file_id = parse_file_id(file_id)
        return self.files.get(fileId=file_id, fields=fields, **kwargs).execute()

    def get_by_filename(
        self, name: str, parents: List[str], q: str | None = None
    ) -> Optional[File]:
        """Get a file by its name and its parent folder(s).
        If multiple files are found, the first one is returned.
        If no file is found, None is returned.

        Args:
            name (str): The name of the file.
            parents (List[str]): The ID(s) of the parent folder(s).
            q (str, optional): A query string to filter the results. Defaults to None.
        """
        parents = list(map(parse_file_id, parents)) if parents is not None else []
        return next(self._query_children(name=name, parents=parents, q=q), None)

    def _download(self, file_id: str, out_filepath: Path, mime_type: GoogleMimeTypes):
        request = self.files.export_media(fileId=file_id, mimeType=mime_type.value)  # type: ignore
        with out_filepath.open("wb") as out_file:
            downloader = googleapiclient.http.MediaIoBaseDownload(out_file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

        return out_filepath

    def _download_nested_filepath(
        self,
        out_filepath: FilePath,
        file_id: str,
    ) -> Path:
        """Internal usage function. Download a folder given by "out_filepath" and its contents recursively.

        Args:
            out_filepath (FilePath): The path to the folder to download to.
            file_id (str): The ID of the folder to download.
        """
        out_filepath = Path(out_filepath)

        for file in self.list_children(file_id):
            t_name, t_file_id, t_mime_type = (
                file["name"],
                file["id"],
                GoogleMimeTypes(file["mimeType"]),
            )
            t_out_filepath = out_filepath.joinpath(t_name)

            if t_mime_type == GoogleMimeTypes.folder:
                self._download_nested_filepath(
                    out_filepath=t_out_filepath, file_id=t_file_id
                )
            else:
                self.download(
                    out_filepath=t_out_filepath,
                    file_id=t_file_id,
                    mime_type=t_mime_type,
                    recursive=True,
                )
        return out_filepath

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
        """Download a file from Google Drive. If the file is larger than 10MB, it's downloaded in chunks.

        Args:
            out_filepath (FilePath): The path to the file to download to.
            file_id (str): The ID of the file to download.
            mime_type (GoogleMimeTypes): The mime type of the file to download.
            recursive (bool, optional): If the file is a folder, download its contents recursively. Defaults to False.
            conversion_map (dict[GoogleMimeTypes, tuple[GoogleMimeTypes, str]], optional): A dictionary mapping mime types to their corresponding file extensions. Defaults to DEFAULT_DOWNLOAD_CONVERSION_MAP.
        """
        file_id = parse_file_id(file_id)
        out_filepath = Path(out_filepath)

        if recursive and mime_type == GoogleMimeTypes.folder:
            return self._download_nested_filepath(out_filepath, file_id)

        mime_type, ext = conversion_map.get(mime_type, (mime_type, ""))
        out_filepath = out_filepath.with_suffix(ext)
        out_filepath.parent.mkdir(parents=True, exist_ok=True)

        file = self.get(file_id=file_id)

        if float(file["size"]) >= DOWNLOAD_LIMIT:
            link = file["exportLinks"].get(mime_type.value, "")
            return download_large_file(url=link, filepath=out_filepath)
        else:
            return self._download(file_id, out_filepath, mime_type)

    def copy(
        self,
        from_file_id: str,
        parents: List[str],
        name: str | None = None,
        body: File | None = None,
        **kwargs: Any,
    ) -> File:
        """Copy a file on Google Drive.

        Args:
            from_file_id (str): The ID of the file to copy.
            parents (List[str]): The ID(s) of the parent folder(s).
            name (str, optional): The name of the copied file. Defaults to None, results in the same name as the original file.
            body (File, optional): The body of the copied file. Defaults to None.
            **kwargs (Any): Additional keyword arguments to pass to the API call.
        """
        from_file_id = parse_file_id(from_file_id)
        parents = list(map(parse_file_id, parents)) if parents is not None else []

        kwargs |= {
            "fileId": from_file_id,
            "body": body if body is not None else {},
        }
        kwargs["body"]["parents"] = parents
        if name is not None:
            kwargs["body"]["name"] = name

        return self.files.copy(**kwargs).execute()

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
        query: str = "",
        fields: str = "*",
        order_by: str = "modifiedTime desc",
        team_drives: bool = True,
        **kwargs: Any,
    ) -> Iterable[File]:
        """List files in Google Drive.

        Example:
            query = "name contains 'hello'"
            fields = "files(id, name, mimeType, size, modifiedTime)"
            order_by = "modifiedTime desc"
            team_drives = True

            files = drive.list(query=query, fields=fields, order_by=order_by, team_drives=team_drives)

        Args:
            query (str): The query to use to filter files. For more information see https://developers.google.com/drive/api/v3/search-files.
            fields (str, optional): The fields to return. Defaults to "*". For more information see https://developers.google.com/drive/api/v3/reference/files/list.
            order_by (str, optional): The order to return files in. Defaults to "modifiedTime desc".
            team_drives (bool, optional): Whether to include files from Team Drives. Defaults to True.
        """
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
            yield from response.get("files", [])  # type: ignore

    def list_children(
        self, parent_id: str, fields: str = "*", **kwargs: Any
    ) -> Iterable[File]:
        """List files in a folder.

        Args:
            parent_id (str): The ID of the folder to list files in.
            fields (str, optional): The fields to return. Defaults to "*". For more information see https://developers.google.com/drive/api/v3/reference/files/list.
        """
        parent_id = parse_file_id(parent_id)
        return self.list(
            query=f"{q_escape(parent_id)} in parents", fields=fields, **kwargs
        )

    def _query_children(self, name: str, parents: List[str], q: str | None = None):
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

    def _create_nested_folders(
        self, filepath: Path, parents: List[str], update: bool = True
    ) -> List[str]:
        """Create nested folders in Google Drive. Walks up the filepath creating folders as it goes.

        Args:
            filepath (Path): The filepath to create folders for.
            parents (List[str]): The parent folders to create the folders in.
            update (bool, optional): Whether to update the folder if it already exists. Defaults to True.
        """

        def create_or_get_if_exists(name: str, parents: List[str]):
            folders = self._query_children(
                name=name,
                parents=parents,
                q=f"mimeType='{GoogleMimeTypes.folder.value}'",
            )
            if update and (folder := next(folders, None)) is not None:
                return folder

            body: File = {
                "name": dirname,
                "parents": parents,
                "mimeType": GoogleMimeTypes.folder.value,
            }
            return self.files.create(
                body=body,
            ).execute()

        for dirname in filepath.parts[:-1]:
            folder = create_or_get_if_exists(dirname, parents)
            parents = [folder["id"]]

        return parents

    def create(
        self,
        filepath: FilePath,
        mime_type: GoogleMimeTypes,
        parents: List[str] | None = None,
        create_folders: bool = False,
        get_extant: bool = False,
        fields: str = "*",
        **kwargs: Any,
    ) -> File:
        """Create's a file on Google Drive.

        For more information, see: https://developers.google.com/drive/api/v3/reference/files/create

        Args:
            filepath (FilePath): Filepath to the file to be uploaded.
            mime_type (GoogleMimeTypes): Mime type of the file.
            parents (List[str], optional): List of parent folder IDs wherein the file will be created. Defaults to None.
            create_folders (bool, optional): Create parent folders if they don't exist. Defaults to False.
            get_extant (bool, optional): If a file with the same name already exists, return it. Defaults to False.
            fields (str, optional): Fields to be returned. Defaults to "*".
        """
        filepath = Path(filepath)
        parents = list(map(parse_file_id, parents)) if parents is not None else []

        if create_folders:
            parents = self._create_nested_folders(
                filepath=filepath, parents=parents, update=get_extant
            )

        if (
            get_extant
            and (file := self.get_by_filename(filepath.name, parents=parents))
            is not None
        ):
            return file

        kwargs |= {
            "body": {
                "name": filepath.name,
            },
            "fields": fields,
        }
        if parents is not None:
            kwargs["body"]["parents"] = parents
        if mime_type is not None:
            kwargs["body"]["mimeType"] = mime_type.value

        file = self.files.create(**kwargs).execute()
        return file

    def delete(self, file_id: str, trash: bool = True, **kwargs: Any):
        """Delete a file from Google Drive.
        If `trash` is True, the file will be moved to the trash. Otherwise, it will be deleted permanently.

        For more information on deleting files, see: https://developers.google.com/drive/api/v3/reference/files/delete

        Args:
            file_id (str): The ID of the file to delete.
            trash (bool, optional): Whether to trash the file instead of deleting it. Defaults to True.
        """
        file_id = parse_file_id(file_id)

        if trash:
            return self.files.update(
                fileId=file_id,
                body={"trashed": True},
            )
        else:
            return self.files.delete(fileId=file_id, **kwargs).execute()

    def _upload(
        self,
        uploader: Callable[[GoogleMimeTypes], Any],
        name: str,
        filepath: FilePath,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | None = None,
        body: File | None = None,
        update: bool = True,
        **kwargs,
    ) -> File:
        filepath = Path(filepath)
        parents = list(map(parse_file_id, parents)) if parents is not None else []
        mime_type = (
            mime_type
            if mime_type is not None
            else GoogleMimeTypes[filepath.suffix.lstrip(".")]
        )

        kwargs |= {
            "body": body if body is not None else {},
            "media_body": uploader(mime_type),
        }

        if update and (file := self.get_by_filename(name, parents=parents)):
            kwargs["fileId"] = file["id"]
            return self.files.update(**kwargs).execute()

        if name is not None:
            kwargs["body"]["name"] = name
        if parents is not None:
            kwargs["body"]["parents"] = parents
        if mime_type is not None:
            kwargs["body"]["mimeType"] = mime_type.value

        return self.files.create(**kwargs).execute()

    def upload_file(
        self,
        filepath: FilePath,
        name: str | None = None,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | None = None,
        body: File | None = None,
        update: bool = True,
        **kwargs: Any,
    ) -> File:
        """Uploads a file to Google Drive. Filepath variant.

        For more information on the File object (for the body, etc.), see https://developers.google.com/drive/api/v3/reference/files#resource
        The `body` and kwargs arguments are expanded within the `body` argument of the underlying Google Drive API call.

        Args:
            filepath (FilePath): The path to the file to upload.
            name (str, optional): The name of the file. Defaults to None, which will use the name of the file at the filepath.
            mime_type (GoogleMimeTypes, optional): The mime type of the file. Defaults to None, which will use the mime type of the file at the filepath.
            parents (List[str], optional): The list of parent IDs. Defaults to None.
            body (File, optional): The body of the file. Defaults to None.
            update (bool, optional): Whether to update the file if it already exists. Defaults to True.
        """
        filepath = Path(filepath)

        def uploader(mime_type: GoogleMimeTypes):
            return googleapiclient.http.MediaFileUpload(
                str(filepath), resumable=True, mimetype=mime_type.value
            )

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
        mime_type: GoogleMimeTypes,
        parents: List[str] | None = None,
        body: File | None = None,
        update: bool = True,
        **kwargs: Any,
    ) -> File:
        """Uploads data to Google Drive. Bytes variant of `upload_file`

        Args:
            data (bytes): Data to upload
            name (str): Name of the file
            mime_type (GoogleMimeTypes): Mime type of the file
            parents (List[str], optional): List of parent IDs. Defaults to None.
            body (File, optional): File body. Defaults to None.
            update (bool, optional): Whether to update the file if it exists. Defaults to True.
        """
        with BytesIO(data) as tio:

            def uploader(mime_type: GoogleMimeTypes):
                return googleapiclient.http.MediaIoBaseUpload(
                    tio, resumable=True, mimetype=mime_type.value
                )

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

    def export(
        self,
        file_id: str,
        mime_type: GoogleMimeTypes,
    ) -> bytes:
        """Exports a Google Drive file to a different mime type. The exported content is limited to 10MB.

        See https://developers.google.com/drive/api/reference/rest/v3/files/export for more information.

        Args:
            file_id (str): The ID of the file to export.
            mime_type (GoogleMimeTypes): The mime type to export to.
        """
        file_id = parse_file_id(file_id)
        return self.files.export(fileId=file_id, mimeType=mime_type.value).execute()

    def permissions_get(
        self, file_id: str, permission_id: str, **kwargs: Any
    ) -> Permission:
        """Gets a permission by ID.

        Args:
            file_id (str): The ID of the file.
            permission_id (str): The ID of the permission.
        """
        file_id = parse_file_id(file_id)
        return (
            self.service.permissions()
            .get(fileId=file_id, permissionId=permission_id, **kwargs)
            .execute()
        )

    def permissions_list(
        self, file_id: str, fields: str = "*", **kwargs: Any
    ) -> Iterable[Permission]:
        """Lists permissions for a file.

        Args:
            file_id (str): The ID of the file.
            fields (str, optional): The fields to return. Defaults to "*".
        """
        file_id = parse_file_id(file_id)
        list_func = (
            lambda x: self.service.permissions()
            .list(
                fileId=file_id, pageToken=x, fields=self._list_fields(fields), **kwargs
            )
            .execute()
        )
        for response in self._list(list_func):
            yield from response.get("permissions", [])  # type: ignore

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
        """Creates a permission for a file. Defaults to a reader permission of type user.

        Args:
            file_id (str): The ID of the file.
            email_address (str): The email address of the user to give permission to.
            permission (Permission, optional): The permission to give. Defaults to None, which will give a reader permission of type user.
            sendNotificationEmail (bool, optional): Whether to send a notification email. Defaults to True.
            update (bool, optional): Whether to update the permission if it already exists. Defaults to False.
        """
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
        """Deletes a permission from a file.

        Args:
            file_id (str): The ID of the file.
            permission_id (str): The ID of the permission.
        """
        file_id = parse_file_id(file_id)
        return (
            self.service.permissions()
            .delete(fileId=file_id, permissionId=permission_id, **kwargs)
            .execute()
        )
