from __future__ import annotations

import hashlib
import tempfile
from io import BytesIO
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generator,
    Iterable,
    List,
    Literal,
)

import googleapiclient
import googleapiclient.http
import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from googleapiutils2.drive.misc import (
    DEFAULT_FIELDS,
    DOWNLOAD_LIMIT,
    VERSION,
    DataFrameExportFileTypes,
    create_listing_fields,
    list_drive_items,
)
from googleapiutils2.utils import (
    DEFAULT_DOWNLOAD_CONVERSION_MAP,
    EXECUTE_TIME,
    THROTTLE_TIME,
    DriveBase,
    FilePath,
    GoogleMimeTypes,
    ServiceAccountCredentials,
    download_large_file,
    export_mime_type,
    guess_mime_type,
    mime_type_to_google_mime_type,
    parse_file_id,
    q_escape,
    html_to_markdown,
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


class Drive(DriveBase):
    """A wrapper around the Google Drive API.

    Args:
        creds (Credentials, optional): The credentials to use. If None, the following paths will be tried:
            - ~/auth/credentials.json
            - env var: GOOGLE_API_CREDENTIALS
        execute_time (float, optional): The time to wait between requests. Defaults to EXECUTE_TIME (0.1).
        throttle_time (float, optional): The time to wait between requests. Defaults to THROTTLE_TIME (30).
        team_drives (bool, optional): Whether to include files from Team Drives. Defaults to True.
    """

    def __init__(
        self,
        creds: Credentials | ServiceAccountCredentials | None = None,
        execute_time: float = EXECUTE_TIME,
        throttle_time: float = THROTTLE_TIME,
        team_drives: bool = True,
    ):
        super().__init__(
            creds=creds, execute_time=execute_time, throttle_time=throttle_time
        )

        self.service: DriveResource = discovery.build(
            "drive", VERSION, credentials=self.creds
        )  # type: ignore
        self.files: DriveResource.FilesResource = self.service.files()
        self.about: DriveResource.AboutResource = self.service.about()

        self.team_drives = team_drives

    def get(
        self,
        file_id: str | None = None,
        name: FilePath | None = None,
        parents: List[str] | str | None = None,
        fields: str = DEFAULT_FIELDS,
        q: str | None = None,
        **kwargs: Any,
    ) -> File:
        """Get a file by its:
            - ID
            - Name and parent folder(s)

        If multiple files are found, the first one is returned.
        If no file is found, a FileNotFoundError is raised.
        If the name is a Path, the file will be searched for parent-wise, starting at the root `parent`.

        Args:
            file_id (str, optional): The ID of the file to get. Defaults to None.
            name (FilePath, optional): The name of the file to get. Defaults to None.
            parents (List[str], optional): The parent folder(s) of the file to get. Defaults to None.
            fields (str, optional): The fields to return. Defaults to DEFAULT_FIELDS.
            q (str, optional): A query string to filter the results. Defaults to None.
            team_drives (bool, optional): Whether to include files from Team Drives. Defaults to True.
        """
        if file_id is not None:
            kwargs |= self._team_drives_payload(self.team_drives, kind="update")
            file_id = parse_file_id(file_id)

            return self.execute(self.files.get(fileId=file_id, fields=fields, **kwargs))  # type: ignore
        elif name is None:
            raise ValueError("Either file_id or name must be specified.")

        parents = [parents] if isinstance(parents, str) else parents
        parents = list(map(parse_file_id, parents)) if parents is not None else []
        name = Path(name) if name is not None else None

        if name is not None:
            for parent in name.parents[1:]:
                if (
                    t_parents := next(
                        self._query_children(
                            parents=parents,
                            name=str(parent),
                            fields=fields,
                            q=q,
                        ),
                        None,
                    )
                ) is not None:
                    parents = [t_parents["id"]]
                else:
                    raise FileNotFoundError(
                        f"File with name {name} and direct parent of {parent} of {name.parents} not found."
                    )
            name = name.name

        file = next(
            self._query_children(
                name=name,
                parents=parents,
                fields=fields,
                q=q,
            ),
            None,
        )
        if file is None:
            raise FileNotFoundError(
                f"File with name {name} and parents {parents} not found."
            )

        return file

    def get_if_exists(
        self,
        file_id: str | None = None,
        name: str | None = None,
        parents: List[str] | str | None = None,
        fields: str = DEFAULT_FIELDS,
        q: str | None = None,
        **kwargs: Any,
    ) -> File | None:
        """Get a file (if it exists). See `get` for more information."""
        try:
            return self.get(
                file_id=file_id,
                name=name,
                parents=parents,
                fields=fields,
                q=q,
                **kwargs,
            )
        except FileNotFoundError:
            return None

    def _download(self, file: File, filepath: Path, mime_type: GoogleMimeTypes):
        """Internal usage function. Download a file given by "filepath" and its contents.

        If the file is a Google Apps file, it's exported to the given mime type (export_media),
        else it's downloaded as-is (get_media)
        If the file is larger than 10MB, it's downloaded in chunks."""
        file_id = file["id"]

        request = (
            self.files.export_media(fileId=file_id, mimeType=mime_type.value)  # type: ignore
            if "google-apps" in file["mimeType"]
            else self.files.get_media(fileId=file_id)  # type: ignore
        )

        with filepath.open("wb") as out_file:
            downloader = googleapiclient.http.MediaIoBaseDownload(out_file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

        return filepath

    def _download_nested_filepath(
        self,
        filepath: FilePath,
        file_id: str,
        overwrite: bool = True,
    ) -> Path:
        """Internal usage function. Download a folder given by "filepath" and its contents recursively.

        Args:
            filepath (FilePath): The path to the folder to download to.
            file_id (str): The ID of the folder to download.
        """
        filepath = Path(filepath)

        for file in self.list(parents=file_id):
            t_name, t_file_id, t_mime_type = (
                file["name"],
                file["id"],
                GoogleMimeTypes(file["mimeType"]),
            )
            t_filepath = filepath.joinpath(t_name)

            if t_mime_type == GoogleMimeTypes.folder:
                t_filepath.mkdir(parents=True, exist_ok=True)

            self.download(
                filepath=t_filepath,
                file_id=t_file_id,
                mime_type=t_mime_type,
                recursive=True,
                overwrite=overwrite,
            )

        return filepath

    def _download_file(
        self,
        file_id: str,
        filepath: FilePath,
        mime_type: GoogleMimeTypes | None = None,
        recursive: bool = False,
        overwrite: bool = True,
        conversion_map: dict[
            GoogleMimeTypes, GoogleMimeTypes
        ] = DEFAULT_DOWNLOAD_CONVERSION_MAP,
    ) -> Path:
        """Download a file from Google Drive. If the file is larger than 10MB, it's downloaded in chunks.

        Args:
            file_id (str): The ID of the file to download.
            filepath (FilePath): The path to the file to download to.
            mime_type (GoogleMimeTypes): The mime type of the file to download.
            recursive (bool, optional): If the file is a folder, download its contents recursively. Defaults to False.
            conversion_map (dict[GoogleMimeTypes, GoogleMimeTypes], optional): A dictionary mapping mime types to their corresponding file extensions. Defaults to DEFAULT_DOWNLOAD_CONVERSION_MAP.
        """
        file_id = parse_file_id(file_id)
        filepath = Path(filepath)

        if filepath.exists() and not overwrite:
            return filepath

        file = self.get(file_id=file_id)

        # If the filepath exists, check if the file has the same md5 hash:
        if filepath.exists():
            md5 = hashlib.md5(filepath.read_bytes()).hexdigest()
            if file.get("md5Checksum") == md5:
                return filepath

        mime_type = (
            mime_type if mime_type is not None else GoogleMimeTypes(file["mimeType"])
        )
        if recursive and mime_type == GoogleMimeTypes.folder:
            return self._download_nested_filepath(
                filepath=filepath, file_id=file_id, overwrite=overwrite
            )

        mime_type, ext = export_mime_type(mime_type, conversion_map)

        if not filepath.suffix or ext:
            filepath = filepath.with_suffix(ext)

        filepath.parent.mkdir(parents=True, exist_ok=True)

        if float(file["size"]) >= DOWNLOAD_LIMIT:
            if "exportLinks" in file:
                link = file["exportLinks"].get(mime_type.value, "")  # type: ignore

                return download_large_file(url=link, filepath=filepath)
            else:
                raise ValueError(
                    f"File {file['webViewLink']}: {file['name']} is too large to download ({file['size']}). Use the Google Drive web interface to download it."
                )
        else:
            return self._download(
                file=file, filepath=filepath, mime_type=mime_type  # type: ignore
            )

    def _download_data(
        self,
        file_id: str,
        buf: BytesIO,
        mime_type: GoogleMimeTypes | None = None,
        recursive: bool = False,
        overwrite: bool = True,
        conversion_map: dict[
            GoogleMimeTypes, GoogleMimeTypes
        ] = DEFAULT_DOWNLOAD_CONVERSION_MAP,
    ):
        with tempfile.NamedTemporaryFile() as temp:
            out = self._download_file(
                file_id=file_id,
                filepath=temp.name,
                mime_type=mime_type,
                recursive=recursive,
                overwrite=overwrite,
                conversion_map=conversion_map,
            )
            buf.write(temp.read())
            return out

    def download(
        self,
        filepath: FilePath | BytesIO,
        file_id: str,
        mime_type: GoogleMimeTypes | None = None,
        recursive: bool = False,
        overwrite: bool = True,
        conversion_map: dict[
            GoogleMimeTypes, GoogleMimeTypes
        ] = DEFAULT_DOWNLOAD_CONVERSION_MAP,
    ):
        """Download a file from Google Drive. If the file is larger than 10MB, it's downloaded in chunks.

        Args:
            filepath (FilePath | BytesIO): The path to the file to download to, or a BytesIO to write to.
            file_id (str): The ID of the file to download.
            mime_type (GoogleMimeTypes, optional): The mime type of the file to download. Defaults to None, which will use the mime type of the file.
            recursive (bool, optional): If the file is a folder, download its contents recursively. Defaults to False.
            conversion_map (dict[GoogleMimeTypes, GoogleMimeTypes], optional): A dictionary mapping mime types to their corresponding file extensions. Defaults to DEFAULT_DOWNLOAD_CONVERSION_MAP.
        """

        def download_file_or_data():
            if isinstance(filepath, (str, Path)):
                return self._download_file(
                    file_id=file_id,
                    filepath=filepath,
                    mime_type=mime_type,
                    recursive=recursive,
                    overwrite=overwrite,
                    conversion_map=conversion_map,
                )
            elif isinstance(filepath, BytesIO):
                return self._download_data(
                    file_id=file_id,
                    buf=filepath,
                    mime_type=mime_type,
                    recursive=recursive,
                    overwrite=overwrite,
                    conversion_map=conversion_map,
                )
            else:
                raise TypeError(
                    f"Expected a filepath or BytesIO, got {type(filepath)} instead."
                )

        downloaded_filepath = download_file_or_data()

        if mime_type == GoogleMimeTypes.md:
            # If the mimetype is, we've downloaded it as HTML and need to convert it to markdown:
            md_filepath = downloaded_filepath.with_suffix(".md")

            md = html_to_markdown(
                downloaded_filepath.read_text(encoding="utf-8"),
            )

            md_filepath.write_text(md, encoding="utf-8")

            downloaded_filepath.unlink()

            return md_filepath
        else:
            return downloaded_filepath

    def copy(
        self,
        from_file_id: str,
        parents: List[str] | str,
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
        parents = [parents] if isinstance(parents, str) else parents
        parents = list(map(parse_file_id, parents))

        kwargs |= {
            "fileId": from_file_id,
            "body": body if body is not None else {},
        }
        kwargs["body"]["parents"] = parents
        if name is not None:
            kwargs["body"]["name"] = name

        return self.execute(self.files.copy(**kwargs))  # type: ignore

    @staticmethod
    def _team_drives_payload(
        team_drives: bool, kind: Literal["list", "update"] = "list"
    ) -> dict[str, Any]:
        if not team_drives:
            return {}

        payload = {
            "supportsAllDrives": team_drives,
        }

        if kind == "list":
            payload["includeItemsFromAllDrives"] = team_drives
        elif kind == "update":
            payload["supportsTeamDrives"] = team_drives

        return payload

    def list(
        self,
        parents: List[str] | str | None = None,
        query: str | None = None,
        fields: str = DEFAULT_FIELDS,
        order_by: str = "modifiedTime desc",
    ) -> Generator[File, None, None]:
        """List files in Google Drive.

        If `parents` is specified, only files in the given parent folder(s) will be returned.

        Args:
            parents (List[str], optional): The parent folder(s) to list files in. Defaults to None.
            query (str): The query to use to filter files. For more information see https://developers.google.com/drive/api/v3/search-files.
            fields (str, optional): The fields to return. Defaults to DEFAULT_FIELDS. For more information see https://developers.google.com/drive/api/v3/reference/files/list.
            order_by (str, optional): The order to return files in. Defaults to "modifiedTime desc".
            team_drives (bool, optional): Whether to include files from Team Drives. Defaults to True.
        """
        if parents is not None:
            parents = [parents] if isinstance(parents, str) else parents
            parents = list(map(parse_file_id, parents))

            yield from self._query_children(
                parents=parents,
                fields=fields,
                q=query,
            )
            return

        if query is None:
            query = "trashed = false"

        kwargs = self._team_drives_payload(self.team_drives)
        list_func = lambda x: self.execute(
            self.files.list(
                q=query,
                pageToken=x,
                fields=create_listing_fields(fields),
                orderBy=order_by,
                **kwargs,
            )
        )

        for response in list_drive_items(list_func):
            yield from response.get("files", [])  # type: ignore

    def _query_children(
        self,
        parents: List[str],
        name: str | None = None,
        fields: str = DEFAULT_FIELDS,
        q: str | None = None,
    ):
        """Internal usage function. Query children of a parent folder.
        If `name` is specified, only files with the given name will be returned.
        Only non-trashed files will be returned."""
        queries: List[str] = []

        if len(parents):
            parents_list = " or ".join(
                (f"{q_escape(parent)} in parents" for parent in parents)
            )
            queries.append(parents_list)

        if name is not None:
            filename = Path(name)
            names_list = " or ".join(
                (
                    f"name = {q_escape(str(filename))}",
                    f"name = {q_escape(filename.stem)}",
                )
            )
            queries.append(names_list)
        if q is not None:
            queries.append(q)

        queries.append("trashed = false")

        query = " and ".join((f"({i})" for i in queries))

        return self.list(query=query, fields=fields)

    def _create_nested_folders(
        self,
        filepath: Path,
        parents: List[str],
        owners: List[str],
        get_extant: bool = True,
    ) -> List[str]:
        """Create nested folders in Google Drive. Walks up the filepath creating folders as it goes.

        Args:
            filepath (Path): The filepath to create folders for.
            parents (List[str]): The parent folders to create the folders in.
            owners (List[str]): The owner IDs of the folders.
            get_extant (bool, optional): Whether to get the folder if it already exists. Defaults to True.
        """

        def create_or_get_if_exists(name: str, parents: List[str]) -> File:
            folders = self._query_children(
                parents=parents,
                name=name,
                q=f"mimeType='{GoogleMimeTypes.folder.value}'",
            )
            if get_extant and (folder := next(folders, None)) is not None:
                return folder

            body: File = {
                "name": dirname,
                "parents": parents,
                "mimeType": GoogleMimeTypes.folder.value,
            }

            if len(owners):
                body["owners"] = owners  # type: ignore

            return self.execute(
                self.files.create(
                    body=body,
                )
            )  # type: ignore

        for dirname in filepath.parts[:-1]:
            folder = create_or_get_if_exists(dirname, parents)
            parents = [folder["id"]]

        return parents

    def create(
        self,
        name: FilePath,
        mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | str | None = None,
        owners: List[str] | str | None = None,
        recursive: bool = False,
        get_extant: bool = False,
        fields: str = DEFAULT_FIELDS,
        **kwargs: Any,
    ) -> File:
        """Create's a file on Google Drive.

        For more information, see: https://developers.google.com/drive/api/v3/reference/files/create

        Args:
            name (FilePath): Filepath to the file to be uploaded.
            mime_type (GoogleMimeTypes): Mime type of the file.
            parents (List[str], optional): List of parent folder IDs wherein the file will be created. Defaults to None.
            owners (List[str], optional): List of owner IDs. Defaults to None.
            recursive (bool, optional): Create parent folders if they don't exist. Defaults to False.
            get_extant (bool, optional): If a file with the same name already exists, return it. Defaults to False.
            fields (str, optional): Fields to be returned. Defaults to DEFAULT_FIELDS.
        """
        filepath = Path(name)
        parents = [parents] if isinstance(parents, str) else parents
        parents = list(map(parse_file_id, parents)) if parents is not None else []

        owners = [owners] if isinstance(owners, str) else owners
        owners = owners if owners is not None else []

        if recursive:
            parents = self._create_nested_folders(
                filepath=filepath, parents=parents, owners=owners, get_extant=get_extant
            )

        if (
            get_extant
            and (file := self.get_if_exists(name=filepath.name, parents=parents))
            is not None
        ):
            return file

        kwargs |= {
            "body": {
                "name": filepath.name,
            },
            "fields": fields,
        }
        if len(parents):
            kwargs["body"]["parents"] = parents
        if len(owners):
            kwargs["body"]["owners"] = owners
        if mime_type is not None:
            kwargs["body"]["mimeType"] = mime_type.value

        kwargs |= self._team_drives_payload(self.team_drives, kind="update")

        return self.execute(self.files.create(**kwargs))  # type: ignore

    def update(
        self,
        file_id: str,
        name: FilePath | None = None,
        mime_type: GoogleMimeTypes | None = None,
        body: File | None = None,
        **kwargs: Any,
    ) -> File:
        """Update a file on Google Drive, editing its name (filename, ext), mime type, and/or body (File metadata).

        For more information, see: https://developers.google.com/drive/api/v3/reference/files/update

        Args:
            file_id (str): The ID of the file to update.
            name (FilePath, optional): The new filename. Defaults to None, which will not change the filename.
            mime_type (GoogleMimeTypes, optional): The new mime type. Defaults to None, which will not change the mime type.
            body (File, optional): The new body. Defaults to None, which will not change the body.
            team_drives (bool, optional): Whether to include files from Team Drives. Defaults to True.
            **kwargs (Any): Additional keyword arguments to pass to the API call.
        """
        file_id = parse_file_id(file_id)

        kwargs |= {
            "fileId": file_id,
            "body": body if body is not None else {},
            **self._team_drives_payload(self.team_drives, kind="update"),
        }
        if name is not None:
            filepath = Path(name)
            kwargs["body"]["name"] = filepath.name

        if mime_type is not None:
            kwargs["body"]["mimeType"] = mime_type.value

        return self.execute(self.files.update(**kwargs))  # type: ignore

    def delete(self, file_id: str, trash: bool = True, **kwargs: Any) -> File:
        """Delete a file from Google Drive.
        If `trash` is True, the file will be moved to the trash. Otherwise, it will be deleted permanently.

        For more information on deleting files, see: https://developers.google.com/drive/api/v3/reference/files/delete

        Args:
            file_id (str): The ID of the file to delete.
            trash (bool, optional): Whether to trash the file instead of deleting it. Defaults to True.
        """
        file_id = parse_file_id(file_id)

        if trash:
            return self.execute(
                self.files.update(
                    fileId=file_id,
                    body={"trashed": True},
                )
            )  # type: ignore
        else:
            return self.execute(self.files.delete(fileId=file_id, **kwargs))  # type: ignore

    def _upload(
        self,
        uploader: Callable[[GoogleMimeTypes], Any],
        name: str,
        filepath: FilePath,
        to_mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | str | None = None,
        owners: List[str] | str | None = None,
        body: File | None = None,
        update: bool = True,
        from_mime_type: GoogleMimeTypes | None = None,
        **kwargs,
    ) -> File:
        filepath = Path(filepath)
        parents = [parents] if isinstance(parents, str) else parents
        parents = list(map(parse_file_id, parents)) if parents is not None else []

        owners = [owners] if isinstance(owners, str) else owners
        owners = owners if owners is not None else []

        file = self.get_if_exists(name=name, parents=parents)

        # If the filepath exists, check if the file has the same md5 hash:
        if file is not None:
            md5 = hashlib.md5(filepath.read_bytes()).hexdigest()
            if file.get("md5Checksum") == md5:
                return file

        if from_mime_type is None:
            if file is not None:
                from_mime_type = mime_type_to_google_mime_type(file["mimeType"])
            else:
                from_mime_type = guess_mime_type(filepath=filepath)

        from_mime_type = (
            from_mime_type if from_mime_type is not None else GoogleMimeTypes.file
        )

        to_mime_type = to_mime_type if to_mime_type is not None else from_mime_type

        kwargs |= {
            "body": body if body is not None else {},
            "media_body": uploader(from_mime_type),  # type: ignore
            **self._team_drives_payload(self.team_drives, kind="update"),
        }

        if update and file is not None:
            kwargs["fileId"] = file["id"]
            return self.execute(self.files.update(**kwargs))  # type: ignore

        if name is not None:
            kwargs["body"]["name"] = name
        if len(parents):
            kwargs["body"]["parents"] = parents
        if len(owners):
            kwargs["body"]["owners"] = owners
        if to_mime_type is not None:
            kwargs["body"]["mimeType"] = to_mime_type.value

        return self.execute(self.files.create(**kwargs))  # type: ignore

    def _upload_file(
        self,
        filepath: FilePath,
        name: str | None = None,
        to_mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | str | None = None,
        owners: List[str] | str | None = None,
        recursive: bool = False,
        body: File | None = None,
        update: bool = True,
        from_mime_type: GoogleMimeTypes | None = None,
        **kwargs: Any,
    ) -> File:
        """Uploads a file to Google Drive. Filepath variant.

        For more information on the File object (for the body, etc.), see https://developers.google.com/drive/api/v3/reference/files#resource
        The `body` and kwargs arguments are expanded within the `body` argument of the underlying Google Drive API call.

        Args:
            filepath (FilePath): The path to the file to upload.
            name (str, optional): The name of the file. Defaults to None, which will use the name of the file at the filepath.
            to_mime_type (GoogleMimeTypes, optional): The mime type of the file. Defaults to None, which will use the mime type of the file at the filepath.
            parents (List[str], optional): The list of parent IDs. Defaults to None.
            owners (List[str], optional): The list of owner IDs. Defaults to None.
            recursive (bool, optional): If the file is a folder, upload its contents recursively. Defaults to False.
            body (File, optional): The body of the file. Defaults to None.
            update (bool, optional): Whether to update the file if it already exists. Defaults to True.
        """
        filepath = Path(filepath)

        def uploader(mime_type: GoogleMimeTypes):
            return googleapiclient.http.MediaFileUpload(
                str(filepath), resumable=True, mimetype=mime_type.value
            )

        if recursive and filepath.is_dir():
            for file in filepath.glob("*"):
                # Ignore .DS_Store files:
                if file.name == ".DS_Store":
                    continue

                t_file = file.relative_to(filepath)

                t_parents = (
                    self.create(
                        name=t_file,
                        mime_type=GoogleMimeTypes.folder,
                        parents=parents,
                        owners=owners,
                        recursive=True,
                        get_extant=True,
                    )["id"]
                    if file.is_dir()
                    else parents
                )

                self._upload_file(
                    filepath=file,
                    name=t_file.name,
                    to_mime_type=to_mime_type,
                    parents=t_parents,
                    owners=owners,
                    recursive=recursive,
                    body=body,
                    update=update,
                    from_mime_type=from_mime_type,
                    **kwargs,
                )

            parents = [parents] if isinstance(parents, str) else parents
            file_id = parents[0] if parents is not None else None

            return self.get(file_id=file_id)

        return self._upload(
            uploader=uploader,
            name=name if name is not None else filepath.name,
            filepath=filepath,
            to_mime_type=to_mime_type,
            parents=parents,
            owners=owners,
            body=body,
            update=update,
            from_mime_type=from_mime_type,
            **kwargs,
        )

    def _upload_data(
        self,
        data: bytes,
        name: str,
        to_mime_type: GoogleMimeTypes,
        parents: List[str] | str | None = None,
        owners: List[str] | str | None = None,
        body: File | None = None,
        update: bool = True,
        from_mime_type: GoogleMimeTypes | None = None,
        **kwargs: Any,
    ) -> File:
        """Uploads data to Google Drive. Bytes variant of `upload_file`

        Args:
            data (bytes): Data to upload.
            name (str): Name of the file.
            to_mime_type (GoogleMimeTypes): Mime type of the file.
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
                to_mime_type=to_mime_type,
                parents=parents,
                owners=owners,
                body=body,
                update=update,
                from_mime_type=from_mime_type,
                **kwargs,
            )

    def _upload_frame(
        self,
        df: pd.DataFrame,
        name: str,
        to_mime_type: GoogleMimeTypes,
        parents: List[str] | str | None = None,
        owners: List[str] | str | None = None,
        body: File | None = None,
        update: bool = True,
        from_mime_type: GoogleMimeTypes | None = None,
        **kwargs: Any,
    ) -> File:
        """
        Uploads a DataFrame to Google Drive.

        Args:
            df (DataFrame): The DataFrame to upload.
            name (str): The name of the file.
            to_mime_type (GoogleMimeTypes): The mime type of the file.
            file_format (str, optional): The file format ("csv", "xlsx", etc.). Defaults to "csv".
            parents (List[str], optional): The list of parent IDs. Defaults to None.
            owners (List[str], optional): The list of owner IDs. Defaults to None.
            body (File, optional): The body of the file. Defaults to None.
            update (bool, optional): Whether to update the file if it already exists. Defaults to True.
        """
        if to_mime_type.name not in DataFrameExportFileTypes.__members__:
            raise ValueError(
                f"Invalid export mime type {to_mime_type.value} for DataFrame. Must be one of {', '.join(DataFrameExportFileTypes.__members__.keys())}."
            )

        export_file_type = DataFrameExportFileTypes[to_mime_type.name]
        use_index = df.index.name is not None

        with tempfile.NamedTemporaryFile(
            suffix=f".{export_file_type.value}"
        ) as tmp_file:
            match export_file_type:
                case DataFrameExportFileTypes.csv:
                    df.to_csv(tmp_file.name, index=use_index)
                case DataFrameExportFileTypes.sheets:
                    to_mime_type = GoogleMimeTypes.sheets
                    df.to_csv(tmp_file.name, index=use_index)
                case DataFrameExportFileTypes.xlsx:
                    with pd.ExcelWriter(tmp_file.name, engine="openpyxl") as writer:
                        df.to_excel(writer, index=use_index)
                case DataFrameExportFileTypes.json:
                    df.to_json(tmp_file.name, orient="records")

            return self._upload_file(
                filepath=tmp_file.name,
                name=name,
                to_mime_type=to_mime_type,
                parents=parents,
                owners=owners,
                body=body,
                update=update,
                from_mime_type=from_mime_type,
                **kwargs,
            )

    def upload(
        self,
        filepath: FilePath | pd.DataFrame | BytesIO,
        name: str | None = None,
        to_mime_type: GoogleMimeTypes | None = None,
        parents: List[str] | str | None = None,
        owners: List[str] | str | None = None,
        recursive: bool = False,
        body: File | None = None,
        update: bool = True,
        from_mime_type: GoogleMimeTypes | None = None,
        **kwargs: Any,
    ):
        """Uploads a file to Google Drive.
        A file can be either a filepath, a DataFrame, or bytes.

        Args:
            filepath (FilePath | DataFrame | BytesIO): The file to upload.
            name (str, optional): The name of the file. Defaults to None, which will use the name of the file at the filepath.
            to_mime_type (GoogleMimeTypes, optional): The mime type of the file. Defaults to None, which will use the mime type of the file at the filepath.
            parents (List[str], optional): The list of parent IDs. Defaults to None.
            owners (List[str], optional): The list of owner IDs. Defaults to None.
            recursive (bool, optional): If the file is a folder, upload its contents recursively. Defaults to False.
            body (File, optional): The body of the file. Defaults to None.
            update (bool, optional): Whether to update the file if it already exists. Defaults to True.
        """
        if isinstance(filepath, (str, Path)):
            return self._upload_file(
                filepath=filepath,
                name=name,
                to_mime_type=to_mime_type,
                parents=parents,
                owners=owners,
                recursive=recursive,
                body=body,
                update=update,
                from_mime_type=from_mime_type,
                **kwargs,
            )
        elif isinstance(filepath, pd.DataFrame):
            if name is None or to_mime_type is None:
                raise ValueError(
                    "If uploading a dataframe, both name and mime_type must be specified."
                )
            return self._upload_frame(
                df=filepath,
                name=name,
                to_mime_type=to_mime_type,
                parents=parents,
                owners=owners,
                body=body,
                update=update,
                from_mime_type=from_mime_type,
                **kwargs,
            )
        elif isinstance(filepath, bytes):
            if name is None or to_mime_type is None:
                raise ValueError(
                    "If uploading bytes, both name and mime_type must be specified."
                )
            return self._upload_data(
                data=filepath,
                name=name,
                to_mime_type=to_mime_type,
                parents=parents,
                owners=owners,
                body=body,
                update=update,
                from_mime_type=from_mime_type,
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
        return self.execute(self.files.export(fileId=file_id, mimeType=mime_type.value))  # type: ignore

    def sync(
        self,
        filepath: Path,
        folder_id: str,
        recursive: bool = False,
    ):
        """Syncs a local folder to a Google Drive folder, and vice versa.
        If a collision occurs, the file will be resolved based on the `collision` argument.

        If `collision` is "newest", the newest file will be kept.
        If `collision` is "local", the local file will be kept.
        If `collision` is "drive", the Google Drive file will be kept.

        Args:
            filepath (Path): The local folder to sync.
            folder_id (str): The ID of the Google Drive folder to sync.
            recursive (bool, optional): Whether to sync recursively. Defaults to False.
            collision (Literal["newest", "local", "drive"], optional): How to handle collisions. Defaults to "local".
        """
        filepath = Path(filepath)
        folder_id = parse_file_id(folder_id)
        self.upload(
            filepath=filepath, parents=folder_id, recursive=recursive, update=True
        )
        self.download(
            filepath=filepath,
            file_id=folder_id,
            recursive=recursive,
            overwrite=False,
        )

    def empty_trash(self):
        """Empty the trash on Google Drive.
        See https://developers.google.com/drive/api/v3/reference/files/emptyTrash for more information.
        """
        return self.execute(self.files.emptyTrash())

    def about_get(self):
        """Get information about the user's Google Drive account.
        See https://developers.google.com/drive/api/v3/reference/about/get for more information.
        """
        return self.execute(self.about.get(fields=DEFAULT_FIELDS))


class Permissions:
    def __init__(self, drive: Drive):
        self.drive = drive
        self.permissions = drive.service.permissions()

    def get(self, file_id: str, permission_id: str, **kwargs: Any) -> Permission:
        """Gets a permission by ID.

        Args:
            file_id (str): The ID of the file.
            permission_id (str): The ID of the permission.
        """
        file_id = parse_file_id(file_id)
        return self.drive.execute(
            self.permissions.get(fileId=file_id, permissionId=permission_id, **kwargs)
        )  # type: ignore

    def list(
        self, file_id: str, fields: str = DEFAULT_FIELDS, **kwargs: Any
    ) -> Iterable[Permission]:
        """Lists permissions for a file.

        Args:
            file_id (str): The ID of the file.
            fields (str, optional): The fields to return. Defaults to DEFAULT_FIELDS.
        """
        file_id = parse_file_id(file_id)
        list_func = lambda x: self.drive.execute(
            self.permissions.list(
                fileId=file_id,
                pageToken=x,
                fields=create_listing_fields(fields),
                **kwargs,
            )
        )
        for response in list_drive_items(list_func):
            yield from response.get("permissions", [])  # type: ignore

    def _permission_get_if_exists(
        self, file_id: str, user_permission: Permission
    ) -> Permission | None:
        for p in self.list(file_id):
            if p["emailAddress"].strip().lower() == user_permission["emailAddress"]:
                return p
        else:
            return None

    def create(
        self,
        file_id: str,
        email_address: str | List[str],
        permission: Permission | None = None,
        send_notification_email: bool = True,
        get_extant: bool = False,
        update: bool = False,
        **kwargs: Any,
    ) -> Permission | List[Permission]:
        """Creates a permission for a file. Defaults to a reader permission of type user.

        Args:
            file_id (str): The ID of the file.
            email_address (str): The email address of the user to give permission to.
            permission (Permission, optional): The permission to give. Defaults to None, which will give a reader permission of type user.
            send_notification_email (bool, optional): Whether to send a notification email. Defaults to True.
            get_extant (bool, optional): Whether to get_extant the permission if it already exists. Defaults to False.
            update (bool, optional): Whether to update the permission if it already exists. Defaults to False.
        """
        file_id = parse_file_id(file_id)

        def _create(email_address: str) -> Permission:
            user_permission: Permission = {
                "type": "user",
                "role": "reader",
                "emailAddress": email_address.strip().lower(),
            }

            if permission is not None:
                user_permission.update(permission)

            if (get_extant or update) and (
                p := self._permission_get_if_exists(file_id, user_permission)
            ) is not None:
                if update:
                    return self.update(
                        file_id=file_id,
                        permission_id=p["id"],
                        permission=user_permission,
                    )
                else:
                    return p

            return self.drive.execute(
                self.permissions.create(
                    fileId=file_id,
                    body=user_permission,
                    fields=DEFAULT_FIELDS,
                    sendNotificationEmail=send_notification_email,
                    **kwargs,
                )
            )  # type: ignore

        email_addresses = (
            [email_address] if isinstance(email_address, str) else email_address
        )

        return (
            [_create(email_address) for email_address in email_addresses]
            if len(email_addresses) > 1
            else _create(email_addresses[0])
        )

    @staticmethod
    def _sanitize_update_permission(permission: Permission) -> Permission:
        """Sanitize the permission body for an update request.

        Keeps only:
        - role
        - allowFileDiscovery
        - expirationTime
        """
        ALLOWED_KEYS = ["role", "allowFileDiscovery", "expirationTime"]

        permission = {
            k: v for k, v in permission.items() if k in ALLOWED_KEYS
        }  # type: ignore

        return permission

    def update(
        self,
        file_id: str,
        permission_id: str,
        permission: Permission,
        **kwargs: Any,
    ) -> Permission:
        """Updates a permission for a file.

        Args:
            file_id (str): The ID of the file.
            permission_id (str): The ID of the permission.
            permission (Permission): The new permission.
        """
        file_id = parse_file_id(file_id)

        permission = self._sanitize_update_permission(permission)

        return self.drive.execute(
            self.permissions.update(
                fileId=file_id, permissionId=permission_id, body=permission, **kwargs
            )
        )  # type: ignore

    def delete(self, file_id: str, permission_id: str, **kwargs: Any) -> Permission:
        """Deletes a permission from a file.

        Args:
            file_id (str): The ID of the file.
            permission_id (str): The ID of the permission.
        """
        file_id = parse_file_id(file_id)
        return self.drive.execute(
            self.permissions.delete(
                fileId=file_id, permissionId=permission_id, **kwargs
            )
        )  # type: ignore
