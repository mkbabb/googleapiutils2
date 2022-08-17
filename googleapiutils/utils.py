from __future__ import annotations

import json
import pickle
import urllib.parse
from pathlib import Path
from typing import *

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


GoogleMimeTypes = Literal[
    "audio",
    "document",
    "drive-sdk",
    "drawing",
    "file",
    "folder",
    "form",
    "fusiontable",
    "jam",
    "map",
    "photo",
    "presentation",
    "script",
    "shortcut",
    "site",
    "spreadsheet",
    "unknown",
    "video",
]


def url_components(url: str) -> Dict[str, List[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


def update_url_params(url: str, params: dict) -> str:
    url_obj = urllib.parse.urlparse(url)
    params.update(urllib.parse.parse_qsl(url_obj.query))

    query = urllib.parse.urlencode(params)

    url_obj = urllib.parse.ParseResult(
        url_obj.scheme,
        url_obj.netloc,
        url_obj.path,
        url_obj.params,
        query,
        url_obj.fragment,
    )

    return url_obj.geturl()


GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]


MIME_TYPES = {
    "docs": {"text": "text/plain"},
    "sheets": {
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
        "pdf": "application/pdf",
        "tsv": "text/tab-separated-values",
        "zip": "application/zip",
        "sheets": "application/vnd.google-apps.spreadsheet",
    },
}


TOKEN_PATH = "auth/token.pickle"
CONFIG_PATH = "auth/credentials.json"

FilePath = str | Path


def get_oauth2_creds(
    token_path: FilePath = TOKEN_PATH,
    client_config: FilePath | dict = CONFIG_PATH,
    is_service_account: bool = False,
    scopes: List[str] = SCOPES,
) -> Optional[Credentials]:
    token_path = Path(token_path)

    if not isinstance(client_config, dict):
        path = Path(client_config)
        client_config = json.loads(path.read_bytes())

    if not is_service_account:
        creds: Credentials = None

        if token_path.exists():
            creds = pickle.loads(token_path.read_bytes())

        if creds is not None and not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

        elif creds is None:
            flow = InstalledAppFlow.from_client_config(client_config, scopes)
            creds = flow.run_local_server(port=0)
            token_path.write_bytes(pickle.dumps(creds))
        return creds
    else:
        return service_account.Credentials.from_service_account_info(
            client_config, scopes=scopes
        )


def create_google_mime_type(google_mime_type: GoogleMimeTypes) -> str:
    return f"application/vnd.google-apps.{google_mime_type}"


def get_id_from_url(url: str) -> Optional[str]:
    url_obj = urllib.parse.urlparse(url)
    path = url_obj.path
    paths = path.split("/")

    get_adjacent = (
        lambda x: paths[t_ix]
        if x in paths and (t_ix := paths.index(x) + 1) < len(paths)
        else None
    )

    id = get_adjacent("folders") or get_adjacent("d")

    if id is not None:
        return id
    else:
        comps = url_components(url)
        if (ids := comps.get("id")) is not None:
            return ids[0]
        else:
            return None


def _parse_file_id() -> Callable[..., Optional[str]]:
    parsed: dict[str, Optional[str]] = {}

    def inner(file_id: str) -> Optional[str]:
        def get() -> Optional[str]:
            if file_id in parsed:
                return parsed[file_id]

            if file_id.find("http") != -1:
                return get_id_from_url(file_id)
            else:
                return file_id

        t_id = get()
        parsed[file_id] = t_id
        return t_id

    return inner


parse_file_id: Callable[[str], Optional[str]] = _parse_file_id()
